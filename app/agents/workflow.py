"""LangGraph workflow for episode generation.

State machine:
  START → build_context → write_episode → critique → [revise → critique]* → human_review → END

The workflow handles:
- Automatic retry with revision up to MAX_REVISIONS times
- Human-in-the-loop at key checkpoints (plan approval, episode approval)
- Persistent state (not in-memory LangGraph state, but DB-backed)
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.context_builder import ContextBuilder, EpisodeContext
from app.agents.critic import CriticAgent
from app.agents.episode_writer import EpisodeWriterAgent
from app.agents.memory_updater import MemoryUpdaterAgent
from app.llm.client import LLMRunner
from app.schemas.models import CriticResult, EpisodeOutput
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ─────────────────────────────────────────────
# LangGraph State
# ─────────────────────────────────────────────

class EpisodeWorkflowState(TypedDict):
    """State that flows through the LangGraph episode workflow."""
    story_id: str
    episode_number: int
    run_id: str

    # Context (built once, reused)
    context: EpisodeContext | None

    # Episode draft(s)
    episode: EpisodeOutput | None

    # Critic result
    critic_result: CriticResult | None

    # Revision tracking
    revision_count: int
    max_revisions: int

    # Rejection (from previous attempt)
    rejection_reason: str | None

    # Final decision
    decision: Literal["approved", "rejected", "human_review"] | None
    error: str | None
    episode_cost: float
    cost_capped: bool

    # Metadata for all agent runs (to be persisted)
    agent_run_metadata: list[dict]


# ─────────────────────────────────────────────
# Node functions
# ─────────────────────────────────────────────

def build_context_node(state: EpisodeWorkflowState) -> dict:
    """Build episode context from pre-loaded data passed in state."""
    # Context is pre-built before invoking the graph
    # This node is a pass-through (context already in state)
    logger.debug(f"[Workflow] Context ready for episode {state['episode_number']}")
    return {}


def _spend(state: EpisodeWorkflowState, meta: dict) -> dict:
    cost = float(meta.get("cost") or 0.0)
    total = float(state.get("episode_cost") or 0.0) + cost
    capped = total >= settings.max_cost_per_episode
    if capped:
        logger.warning(
            f"[Workflow] Episode {state['episode_number']} hit cost cap "
            f"${total:.4f} >= ${settings.max_cost_per_episode:.2f}"
        )
    return {"episode_cost": total, "cost_capped": capped}


def write_episode_node(state: EpisodeWorkflowState) -> dict:
    """Call the episode writer to produce a draft."""
    runner = LLMRunner()
    writer = EpisodeWriterAgent(runner=runner)

    episode, meta = writer.write_episode(
        context=state["context"],
        story_id=state["story_id"],
        run_id=state["run_id"],
        rejection_reason=state.get("rejection_reason"),
    )

    run_record = {
        "run_id": state["run_id"],
        "story_id": state["story_id"],
        "episode_number": state["episode_number"],
        "agent": "episode_writer",
        "model": meta.get("model"),
        "status": "success",
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "cost": meta.get("cost"),
        "latency_ms": meta.get("latency_ms"),
        "retry_count": state.get("revision_count", 0),
        "decision": "draft",
    }

    return {
        "episode": episode,
        "agent_run_metadata": state.get("agent_run_metadata", []) + [run_record],
        **_spend(state, meta),
    }


def critique_node(state: EpisodeWorkflowState) -> dict:
    """Run the critic on the current episode draft."""
    runner = LLMRunner()
    critic = CriticAgent(runner=runner)

    recent_sums = []
    if state["context"] and state["context"].recent_episode_summaries:
        recent_sums = state["context"].recent_episode_summaries

    critic_result, meta = critic.critique(
        episode=state["episode"],
        context=state["context"],
        recent_summaries=recent_sums,
    )

    run_record = {
        "run_id": state["run_id"],
        "story_id": state["story_id"],
        "episode_number": state["episode_number"],
        "agent": "critic",
        "model": meta.get("model"),
        "status": "success",
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "cost": meta.get("cost"),
        "latency_ms": meta.get("latency_ms"),
        "retry_count": state.get("revision_count", 0),
        "decision": (meta.get("decision") or ("pass" if critic_result.passed else "revise")),
    }

    return {
        "critic_result": critic_result,
        "agent_run_metadata": state.get("agent_run_metadata", []) + [run_record],
        **_spend(state, meta),
    }


def revise_node(state: EpisodeWorkflowState) -> dict:
    """Call the writer to revise based on critic issues."""
    runner = LLMRunner()
    writer = EpisodeWriterAgent(runner=runner)

    issues_src = state["critic_result"]
    if isinstance(issues_src, dict):
        issues = issues_src.get("issues") or []
    else:
        issues = [i.model_dump() for i in issues_src.issues]
    revised_episode, meta = writer.revise_episode(
        original=state["episode"],
        issues=issues,
        context=state["context"],
        run_id=state["run_id"],
    )

    new_revision_count = state.get("revision_count", 0) + 1

    run_record = {
        "run_id": state["run_id"],
        "story_id": state["story_id"],
        "episode_number": state["episode_number"],
        "agent": "episode_reviser",
        "model": meta.get("model"),
        "status": "success",
        "input_tokens": meta.get("input_tokens"),
        "output_tokens": meta.get("output_tokens"),
        "cost": meta.get("cost"),
        "latency_ms": meta.get("latency_ms"),
        "retry_count": new_revision_count,
        "decision": "revise",
    }

    return {
        "episode": revised_episode,
        "revision_count": new_revision_count,
        "agent_run_metadata": state.get("agent_run_metadata", []) + [run_record],
        **_spend(state, meta),
    }


def send_to_human_review_node(state: EpisodeWorkflowState) -> dict:
    """Mark episode ready for human review."""
    critic = state.get("critic_result")
    if critic is None:
        score = "N/A"
    elif isinstance(critic, dict):
        score = f"{float(critic.get('score') or 0):.2f}"
    else:
        score = f"{critic.score:.2f}"
    logger.info(
        f"[Workflow] Episode {state['episode_number']} → human review (score={score})"
    )
    return {"decision": "human_review"}


# ─────────────────────────────────────────────
# Routing functions
# ─────────────────────────────────────────────

def route_after_critique(state: EpisodeWorkflowState) -> str:
    """Decide next step after critique."""
    critic = state.get("critic_result")
    if critic is None:
        return "send_to_human"

    if state.get("cost_capped"):
        logger.warning(
            f"[Workflow] Cost cap reached for episode {state['episode_number']}; skipping further revisions."
        )
        return "send_to_human"

    passed = critic.get("passed") if isinstance(critic, dict) else critic.passed
    if passed:
        # Good enough – send to human
        return "send_to_human"

    revision_count = state.get("revision_count", 0)
    max_rev = state.get("max_revisions", settings.max_revisions)

    if revision_count < max_rev:
        return "revise"
    else:
        # Max revisions reached – send to human anyway with issues
        logger.warning(
            f"[Workflow] Max revisions ({max_rev}) reached for episode {state['episode_number']}. "
            f"Sending to human with unresolved issues."
        )
        return "send_to_human"


# ─────────────────────────────────────────────
# Graph construction
# ─────────────────────────────────────────────

def build_episode_workflow() -> StateGraph:
    """Build the episode generation LangGraph workflow."""
    graph = StateGraph(EpisodeWorkflowState)

    graph.add_node("build_context", build_context_node)
    graph.add_node("write_episode", write_episode_node)
    graph.add_node("critique", critique_node)
    graph.add_node("revise", revise_node)
    graph.add_node("send_to_human", send_to_human_review_node)

    graph.add_edge(START, "build_context")
    graph.add_edge("build_context", "write_episode")
    graph.add_edge("write_episode", "critique")
    graph.add_conditional_edges(
        "critique",
        route_after_critique,
        {
            "revise": "revise",
            "send_to_human": "send_to_human",
        },
    )
    graph.add_edge("revise", "critique")
    graph.add_edge("send_to_human", END)

    return graph.compile()


# Compiled graph (module-level singleton)
_episode_workflow = None


def get_episode_workflow():
    global _episode_workflow
    if _episode_workflow is None:
        _episode_workflow = build_episode_workflow()
    return _episode_workflow
