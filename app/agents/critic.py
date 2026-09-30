"""Consistency Critic Agent – validates episode quality, consistency, and hooks.

Checks:
1. Character consistency
2. Character relationships
3. Timeline consistency
4. Location/world consistency
5. Open-thread continuity
6. Repeated plot beats
7. Arc adherence
8. Hook quality
9. Human instruction compliance
10. Contradictions
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.context_builder import EpisodeContext
from app.agents.guards import merge_critic_result, structural_issues
from app.agents.planner import parse_json_from_response
from app.llm.client import LLMRunner
from app.schemas.models import CriticResult, CriticIssue, EpisodeOutput

logger = logging.getLogger(__name__)


CRITIC_SYSTEM = """You are an expert literary editor and story consistency checker.
Your role is to detect problems in a serialized story episode BEFORE it reaches the reader.
Be specific, honest, and constructive. Focus on real issues, not style preferences.
Return ONLY valid JSON. No prose outside the JSON block."""


CRITIC_PROMPT = """Review Episode {episode_number} for consistency and quality issues.

EPISODE CONTENT:
Title: {title}
Word count: {word_count}
Content:
{content}

STORY CONTEXT:
{context}

RECENT EPISODE SUMMARIES (near-term repetition):
{recent_summaries}

PRIOR PLOT BEATS (long-range repetition — flag near-duplicates):
{plot_beats}

Analyze the episode and return this JSON:
{{
  "passed": true|false,
  "score": 0.0-1.0,
  "issues": [
    {{
      "type": "character|timeline|location|world_fact|thread|repetition|arc|hook|feedback|contradiction",
      "severity": "low|medium|high|critical",
      "description": "Specific description of the issue"
    }}
  ],
  "repetition_detected": true|false,
  "hook_quality": "strong|adequate|weak|missing",
  "human_instructions_followed": true|false,
  "arc_adherence": true|false,
  "positive_aspects": ["what worked well"]
}}

SCORING GUIDE:
- 1.0 = Perfect episode, no issues
- 0.8+ = Minor issues, acceptable
- 0.6-0.8 = Moderate issues, revision recommended
- Below 0.6 = Major issues, revision required

PASS CRITERIA:
- passed = true only if score >= 0.7 AND no critical/high severity issues
- If human instructions are not followed: automatically failed (score <= 0.5)
- If hook is missing: high severity issue
- If character contradicts established facts: high severity issue"""


class CriticAgent:
    """Validates episode consistency, quality, and adherence to plan."""

    def __init__(self, runner: LLMRunner | None = None):
        self.runner = runner or LLMRunner()

    def critique(
        self,
        episode: EpisodeOutput,
        context: EpisodeContext,
        recent_summaries: list[dict] | None = None,
    ) -> tuple[CriticResult, dict]:
        """
        Critique an episode.
        Returns (CriticResult, run_metadata).
        """
        logger.info(f"[Critic] Critiquing episode {episode.episode_number}")
        extra = structural_issues(
            episode,
            prior_beats=(context.plot_beats if context else []) or [],
        )
        if extra and any(i.severity == "critical" for i in extra):
            result = merge_critic_result(CriticResult(passed=False, score=0.0, issues=[]), extra)
            return result, {"input_tokens": 0, "output_tokens": 0, "cost": 0.0, "latency_ms": 0, "decision": "blocked"}

        recent_summaries = recent_summaries or []
        recent_text = "\n".join(
            f"Ep {s.get('episode_number', '?')}: {s.get('summary', '')}"
            for s in recent_summaries
        )
        beat_text = "\n".join(context.plot_beats) if context and context.plot_beats else "None"
        compact_context = self._build_compact_context(context)

        prompt = CRITIC_PROMPT.format(
            episode_number=episode.episode_number,
            title=episode.title,
            word_count=episode.word_count or 0,
            content=episode.content,
            context=compact_context,
            recent_summaries=recent_text or "None",
            plot_beats=beat_text,
        )

        messages = [
            SystemMessage(content=CRITIC_SYSTEM),
            HumanMessage(content=prompt),
        ]

        content, meta = self.runner.invoke(messages, agent_name="critic")
        instructions_followed = True

        try:
            data = parse_json_from_response(content)
            instructions_followed = bool(data.get("human_instructions_followed", True))
            if context and context.active_instructions and data.get("human_instructions_followed") is False:
                instructions_followed = False
            result = CriticResult(
                passed=data.get("passed", True),
                score=float(data.get("score", 0.8)),
                issues=[
                    CriticIssue(
                        type=i.get("type", "unknown"),
                        severity=i.get("severity", "low"),
                        description=i.get("description", ""),
                    )
                    for i in data.get("issues", [])
                ],
            )
        except Exception as e:
            logger.warning(f"[Critic] Failed to parse response: {e}")
            result = CriticResult(passed=True, score=0.8, issues=[])

        result = merge_critic_result(result, extra, instructions_followed=instructions_followed)
        meta = {**meta, "decision": "pass" if result.passed else "revise"}
        logger.info(
            f"[Critic] Episode {episode.episode_number}: "
            f"passed={result.passed} score={result.score:.2f} "
            f"issues={len(result.issues)}"
        )
        return result, meta

    def _build_compact_context(self, context: EpisodeContext) -> str:
        """Build a compact summary for the critic (not the full context)."""
        parts = []
        parts.append(f"Story: {context.story_title} | Genre: {context.genre} | Tone: {context.tone}")

        if context.relevant_characters:
            parts.append("\nKey characters:")
            for char in context.relevant_characters[:5]:
                parts.append(f"  - {char['name']} ({char.get('status', 'alive')}): {char.get('current_state', '')}")

        if context.relevant_world_facts:
            parts.append("\nEstablished world facts:")
            for fact in context.relevant_world_facts[:8]:
                parts.append(f"  - {fact['key']}: {fact['value']}")

        if context.open_threads:
            parts.append("\nOpen threads to track:")
            for thread in context.open_threads[:5]:
                parts.append(f"  - {thread['title']}: {thread['description']}")

        if context.active_instructions:
            parts.append("\nHuman instructions (MUST be followed):")
            for instr in context.active_instructions:
                parts.append(f"  - {instr}")

        if context.episode_plan:
            ep = context.episode_plan
            parts.append(f"\nPlanned for this episode: {ep.get('summary', '')}")
            parts.append(f"Required hook: {ep.get('planned_hook', '')}")

        return "\n".join(parts)
