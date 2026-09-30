"""Synchronous Story Service – used by the CLI.

Mirrors SyncStoryService but uses synchronous SQLAlchemy sessions
so it can run without an async event loop.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.context_builder import ContextBuilder
from app.agents.memory_updater import MemoryUpdaterAgent
from app.agents.planner import PlannerAgent
from app.agents.workflow import get_episode_workflow, EpisodeWorkflowState
from app.config import get_settings
from app.db.models import (
    EpisodeStatus, StoryStatus, FeedbackAction, Story,
)
from app.db.repositories import (
    StorySyncRepo, PlanSyncRepo, EpisodeSyncRepo, CharacterSyncRepo,
    WorldFactSyncRepo, OpenThreadSyncRepo, FeedbackSyncRepo,
    MemorySummarySyncRepo, AgentRunSyncRepo,
)
from app.llm.client import LLMRunner
from app.schemas.models import EpisodeOutput, CriticResult

logger = logging.getLogger(__name__)
settings = get_settings()


class SyncStoryService:
    """Synchronous service for CLI use."""

    def __init__(self, db: Session):
        self.db = db
        self.stories = StorySyncRepo(db)
        self.plans = PlanSyncRepo(db)
        self.episodes = EpisodeSyncRepo(db)
        self.characters = CharacterSyncRepo(db)
        self.world_facts = WorldFactSyncRepo(db)
        self.threads = OpenThreadSyncRepo(db)
        self.feedback = FeedbackSyncRepo(db)
        self.memory = MemorySummarySyncRepo(db)
        self.runs = AgentRunSyncRepo(db)

    # ─── Story lifecycle ─────────────────────────────

    def create_story(self, premise: str) -> dict:
        import uuid as _uuid
        from app.db.models import Story
        from datetime import datetime, timezone
        story = Story(id=str(_uuid.uuid4()), premise=premise)
        self.db.add(story)
        self.db.commit()
        self.db.refresh(story)
        return {"id": story.id, "premise": story.premise, "status": story.status}

    def get_story(self, story_id: str) -> Optional[dict]:
        story = self.stories.get(story_id)
        if not story:
            return None
        return {
            "id": story.id,
            "title": story.title,
            "premise": story.premise,
            "genre": story.genre,
            "tone": story.tone,
            "status": story.status,
            "current_episode": story.current_episode,
            "total_planned": story.total_planned,
        }

    def list_stories(self) -> list[dict]:
        stories = self.stories.list_all()
        return [
            {
                "id": s.id,
                "title": s.title,
                "premise": s.premise[:80] + "..." if len(s.premise) > 80 else s.premise,
                "status": s.status,
                "current_episode": s.current_episode,
            }
            for s in stories
        ]

    # ─── Plan ────────────────────────────────────────

    def generate_plan(self, story_id: str) -> dict:
        story = self.stories.get(story_id)
        if not story:
            raise ValueError(f"Story {story_id} not found")

        self.stories.update(story_id, status=StoryStatus.PLANNING)
        run_id = str(uuid.uuid4())
        planner = PlannerAgent()

        try:
            plan_data, meta = planner.generate_plan(story_id, story.premise, run_id=run_id)
        except Exception as e:
            self.stories.update(story_id, status=StoryStatus.CREATED)
            raise RuntimeError(f"Plan generation failed: {e}") from e

        plan = self.plans.create_or_replace(story_id, {
            "arc_structure": {str(a["arc_number"]): a for a in plan_data.get("arcs", [])},
            "episode_plans": plan_data.get("episodes", []),
            "world_rules": plan_data.get("world_rules", []),
            "major_turning_points": plan_data.get("major_turning_points", []),
            "planned_resolutions": plan_data.get("planned_resolutions", []),
        })

        self.stories.update(story_id,
            title=plan_data.get("title"),
            genre=plan_data.get("genre"),
            tone=plan_data.get("tone"),
            status=StoryStatus.PLAN_PENDING_REVIEW,
        )

        # Persist characters
        for char_data in plan_data.get("characters", []):
            self.characters.upsert(
                story_id, char_data["name"],
                role=char_data.get("role"),
                personality=char_data.get("personality"),
                goals=char_data.get("goals", []),
                relationships=char_data.get("relationships", {}),
                current_state=char_data.get("current_state"),
                important_facts=char_data.get("important_facts", []),
                character_arc=char_data.get("character_arc"),
                status=char_data.get("status", "alive"),
            )

        # Log agent run
        self.runs.create(story_id,
            run_id=run_id, agent="planner", model=meta.get("model"),
            status="success", input_tokens=meta.get("input_tokens"),
            output_tokens=meta.get("output_tokens"), cost=meta.get("cost"),
            latency_ms=meta.get("latency_ms"),
        )

        return {
            "plan_id": plan.id,
            "title": plan_data.get("title"),
            "episodes_planned": len(plan_data.get("episodes", [])),
        }

    def get_plan(self, story_id: str) -> Optional[dict]:
        plan = self.plans.get(story_id)
        if not plan:
            return None
        return {
            "id": plan.id,
            "story_id": plan.story_id,
            "approved": plan.approved,
            "arc_structure": plan.arc_structure,
            "episode_plans": plan.episode_plans,
            "world_rules": plan.world_rules,
            "major_turning_points": plan.major_turning_points,
            "planned_resolutions": plan.planned_resolutions,
            "version": plan.version,
        }

    def approve_plan(self, story_id: str) -> None:
        self.plans.approve(story_id)
        self.stories.update(story_id, status=StoryStatus.ACTIVE)

    # ─── Episode generation ─────────────────────────

    def generate_next_episode(self, story_id: str) -> dict:
        story = self.stories.get(story_id)
        if not story:
            raise ValueError(f"Story {story_id} not found")

        plan = self.plans.get(story_id)
        if not plan or not plan.approved:
            raise ValueError("Plan not approved yet")

        last_approved = self.episodes.get_last_approved_number(story_id)
        next_ep_num = last_approved + 1

        if next_ep_num > settings.total_episodes:
            raise ValueError("Story complete.")

        run_id = str(uuid.uuid4())

        # Build context
        builder = ContextBuilder()
        recent_eps = self._get_recent_approved(story_id, 24)
        rolling = self.memory.get_rolling(story_id)
        chars = self.characters.get_all(story_id)
        facts = self.world_facts.get_all(story_id)
        threads = self.threads.get_open(story_id)
        instructions = self.feedback.get_active_instructions(story_id)

        context = builder.build(
            story_id=story_id,
            episode_number=next_ep_num,
            story_title=story.title or "Untitled",
            premise=story.premise,
            genre=story.genre or "",
            tone=story.tone or "",
            episode_plans=plan.episode_plans or [],
            arc_structure=plan.arc_structure or {},
            recent_episodes=recent_eps,
            rolling_summary=rolling,
            characters=chars,
            world_facts=facts,
            open_threads=threads,
            active_instructions=instructions,
        )

        # Rejection reason
        existing = self.episodes.get(story_id, next_ep_num)
        rejection_reason = None
        if existing and existing.status == EpisodeStatus.REJECTED:
            rejection_reason = existing.rejection_reason

        # Create episode record
        if existing:
            self.episodes.update(
                existing.id,
                status=EpisodeStatus.GENERATING,
                is_stale=False,
                stale_reason=None,
            )
            ep_id = existing.id
        else:
            ep = self.episodes.create(story_id, next_ep_num, status=EpisodeStatus.GENERATING)
            ep_id = ep.id

        # Run LangGraph workflow
        initial_state: EpisodeWorkflowState = {
            "story_id": story_id,
            "episode_number": next_ep_num,
            "run_id": run_id,
            "context": context,
            "episode": None,
            "critic_result": None,
            "revision_count": 0,
            "max_revisions": settings.max_revisions,
            "rejection_reason": rejection_reason,
            "decision": None,
            "error": None,
            "episode_cost": 0.0,
            "cost_capped": False,
            "agent_run_metadata": [],
        }

        workflow = get_episode_workflow()
        final_state = workflow.invoke(initial_state)

        ep_output: EpisodeOutput = final_state["episode"]
        critic: CriticResult = final_state.get("critic_result")
        if isinstance(ep_output, dict):
            ep_output = EpisodeOutput.model_validate(ep_output)
        word_count = len((ep_output.content or "").split())

        update_data = {
            "title": ep_output.title,
            "content": ep_output.content,
            "summary": ep_output.summary,
            "hook": ep_output.hook,
            "word_count": word_count,
            "status": EpisodeStatus.HUMAN_REVIEW,
            "characters_present": ep_output.characters_present,
            "facts_introduced": ep_output.facts_introduced,
            "threads_opened": ep_output.threads_opened,
            "threads_resolved": ep_output.threads_resolved,
            "revision_count": final_state.get("revision_count", 0),
        }
        if critic:
            update_data.update({
                "critic_score": critic.score,
                "critic_issues": [i.model_dump() for i in critic.issues],
                "critic_passed": critic.passed,
            })

        self.episodes.update(ep_id, **update_data)

        # Persist agent runs
        for run_meta in final_state.get("agent_run_metadata", []):
            payload = {key: value for key, value in run_meta.items() if key != "story_id"}
            self.runs.create(story_id, **payload)

        return {
            "episode_number": next_ep_num,
            "episode_id": ep_id,
            "status": EpisodeStatus.HUMAN_REVIEW,
            "critic_passed": critic.passed if critic else None,
            "critic_score": critic.score if critic else None,
        }

    # ─── Human review ────────────────────────────────

    def approve_episode(self, story_id: str, episode_number: int) -> dict:
        ep = self.episodes.get(story_id, episode_number)
        if not ep:
            raise ValueError(f"Episode {episode_number} not found")

        self.episodes.update(ep.id, status=EpisodeStatus.APPROVED)
        self.stories.update(story_id, current_episode=episode_number)
        self._run_memory_updater(story_id, ep)

        self.feedback.create(story_id,
            episode_id=ep.id, after_episode=episode_number,
            action=FeedbackAction.APPROVE, is_active=False,
        )
        return {"status": "approved", "episode_number": episode_number}

    def edit_episode(self, story_id: str, episode_number: int, content: str, edit_notes: str = "") -> dict:
        ep = self.episodes.get(story_id, episode_number)
        if not ep:
            raise ValueError(f"Episode {episode_number} not found")

        word_count = len(content.split())
        self.episodes.update(ep.id,
            content=content, word_count=word_count,
            human_edited=True, edit_notes=edit_notes,
            status=EpisodeStatus.APPROVED,
        )
        self.stories.update(story_id, current_episode=episode_number)
        ep.content = content
        self._run_memory_updater(story_id, ep)
        self._mark_future_stale(story_id, episode_number, "Human-edited episode")

        self.feedback.create(story_id,
            episode_id=ep.id, after_episode=episode_number,
            action=FeedbackAction.EDIT, edited_content=content, is_active=False,
        )
        return {"status": "edited", "episode_number": episode_number, "word_count": word_count}

    def reject_episode(self, story_id: str, episode_number: int, reason: str) -> dict:
        ep = self.episodes.get(story_id, episode_number)
        if not ep:
            raise ValueError(f"Episode {episode_number} not found")

        self.episodes.update(ep.id, status=EpisodeStatus.REJECTED, rejection_reason=reason)
        self.feedback.create(story_id,
            episode_id=ep.id, after_episode=episode_number,
            action=FeedbackAction.REJECT, rejection_reason=reason, is_active=False,
        )
        return {"status": "rejected", "episode_number": episode_number}

    def add_feedback(self, story_id: str, episode_number: int, instruction: str) -> dict:
        ep = self.episodes.get(story_id, episode_number)
        ep_id = ep.id if ep else None
        fb = self.feedback.create(story_id,
            episode_id=ep_id, after_episode=episode_number,
            action=FeedbackAction.FEEDBACK, instruction=instruction, is_active=True,
        )
        logger.info(f"[HumanFeedback] {story_id} after ep {episode_number}: {instruction}")
        return {"id": fb.id, "instruction": instruction, "active": True}

    # ─── Memory helpers ──────────────────────────────

    def _get_recent_approved(self, story_id: str, limit: int):
        from sqlalchemy import select, and_
        from app.db.models import Episode
        result = self.db.execute(
            select(Episode).where(
                and_(
                    Episode.story_id == story_id,
                    Episode.status == EpisodeStatus.APPROVED,
                    Episode.is_stale.is_(False),
                )
            ).order_by(Episode.episode_number.desc()).limit(limit)
        ).scalars().all()
        return list(result)

    def _run_memory_updater(self, story_id: str, episode) -> None:
        run_id = str(uuid.uuid4())
        updater = MemoryUpdaterAgent()
        chars = self.characters.get_all(story_id)
        threads = self.threads.get_open(story_id)
        rolling = self.memory.get_rolling(story_id)

        current_chars = [{"name": c.name, "status": c.status, "current_state": c.current_state} for c in chars]
        current_threads = [{"title": t.title, "description": t.description} for t in threads]

        ep_output = EpisodeOutput(
            episode_number=episode.episode_number,
            title=episode.title or f"Episode {episode.episode_number}",
            content=episode.content or "",
            summary=episode.summary or "",
            characters_present=episode.characters_present or [],
            facts_introduced=episode.facts_introduced or [],
            threads_opened=episode.threads_opened or [],
            threads_resolved=episode.threads_resolved or [],
            hook=episode.hook or "",
            word_count=episode.word_count or 0,
        )

        updates, meta = updater.extract_updates(
            episode=ep_output,
            current_characters=current_chars,
            current_threads=current_threads,
            existing_rolling_summary=rolling.content if rolling else "",
        )

        # Apply character updates
        for cu in updates.get("character_updates", []):
            name = cu.get("name")
            if not name:
                continue
            kwargs = {}
            if cu.get("current_state"):
                kwargs["current_state"] = cu["current_state"]
            if cu.get("status"):
                kwargs["status"] = cu["status"]
            if cu.get("important_facts"):
                existing_c = self.characters.get_by_name(story_id, name)
                if existing_c:
                    facts = list(existing_c.important_facts or []) + cu["important_facts"]
                    kwargs["important_facts"] = list(set(facts))
            if kwargs:
                self.characters.upsert(story_id, name, last_updated_episode=episode.episode_number, **kwargs)

        # New world facts
        for fact in updates.get("new_world_facts", []):
            self.world_facts.upsert(
                story_id, fact.get("category", "other"),
                fact.get("key", ""), fact.get("value", ""), episode.episode_number,
            )

        # Open threads
        for td in updates.get("threads_to_open", []):
            self.threads.create(story_id,
                thread_type=td.get("thread_type", "other"),
                title=td.get("title", "Unknown"),
                description=td.get("description", ""),
                episode_introduced=episode.episode_number,
                importance=td.get("importance", "medium"),
                planned_resolution=td.get("planned_resolution"),
            )

        # Resolve threads
        all_threads = self.threads.get_all(story_id)
        resolved = set(t.lower() for t in updates.get("threads_to_resolve", []))
        for thread in all_threads:
            if thread.title.lower() in resolved:
                self.threads.resolve(thread.id, episode.episode_number)

        # Rolling summary
        new_summary = updates.get("new_rolling_summary", "")
        if new_summary:
            self.memory.upsert_rolling(story_id, new_summary, episode.episode_number)

        # Agent run log
        self.runs.create(story_id,
            run_id=run_id, episode_number=episode.episode_number,
            agent="memory_updater", model=meta.get("model"),
            status="success", input_tokens=meta.get("input_tokens"),
            output_tokens=meta.get("output_tokens"), cost=meta.get("cost"),
            latency_ms=meta.get("latency_ms"),
        )

    def _mark_future_stale(self, story_id: str, from_episode: int, reason: str) -> None:
        all_eps = self.episodes.list_all(story_id)
        for ep in all_eps:
            if ep.episode_number > from_episode and ep.status == EpisodeStatus.APPROVED:
                self.episodes.update(ep.id, is_stale=True, stale_reason=reason)

    # ─── Views ───────────────────────────────────────

    def get_memory(self, story_id: str) -> dict:
        rolling = self.memory.get_rolling(story_id)
        chars = self.characters.get_all(story_id)
        facts = self.world_facts.get_all(story_id)
        threads = self.threads.get_open(story_id)
        instructions = self.feedback.get_active_instructions(story_id)

        return {
            "rolling_summary": rolling.content if rolling else None,
            "characters": [
                {"name": c.name, "role": c.role, "personality": c.personality,
                 "goals": c.goals, "relationships": c.relationships,
                 "current_state": c.current_state, "important_facts": c.important_facts,
                 "character_arc": c.character_arc, "status": c.status,
                 "first_appeared": c.first_appeared}
                for c in chars
            ],
            "world_facts": [{"category": f.category, "key": f.key, "value": f.value} for f in facts],
            "open_threads": [
                {"title": t.title, "description": t.description,
                 "thread_type": t.thread_type, "importance": t.importance,
                 "episode_introduced": t.episode_introduced}
                for t in threads
            ],
            "active_instructions": [fb.instruction for fb in instructions if fb.instruction],
        }

    def get_logs(self, story_id: str, limit: int = 100) -> list[dict]:
        runs = self.runs.get_for_story(story_id, limit=limit)
        return [
            {"id": r.id, "run_id": r.run_id, "episode_number": r.episode_number,
             "agent": r.agent, "model": r.model, "status": r.status,
             "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
             "cost": r.cost, "latency_ms": r.latency_ms,
             "retry_count": r.retry_count, "created_at": r.created_at.isoformat()}
            for r in runs
        ]

    def get_episode(self, story_id: str, episode_number: int) -> Optional[dict]:
        ep = self.episodes.get(story_id, episode_number)
        if not ep:
            return None
        return {
            "id": ep.id, "story_id": ep.story_id,
            "episode_number": ep.episode_number, "title": ep.title,
            "content": ep.content, "summary": ep.summary, "hook": ep.hook,
            "status": ep.status, "word_count": ep.word_count,
            "revision_count": ep.revision_count,
            "characters_present": ep.characters_present or [],
            "facts_introduced": ep.facts_introduced or [],
            "threads_opened": ep.threads_opened or [],
            "threads_resolved": ep.threads_resolved or [],
            "critic_score": ep.critic_score, "critic_issues": ep.critic_issues or [],
            "critic_passed": ep.critic_passed, "human_edited": ep.human_edited,
            "rejection_reason": ep.rejection_reason,
            "is_stale": ep.is_stale, "stale_reason": ep.stale_reason,
        }

    def list_episodes(self, story_id: str) -> list[dict]:
        eps = self.episodes.list_all(story_id)
        return [
            {"episode_number": ep.episode_number, "title": ep.title,
             "status": ep.status, "word_count": ep.word_count,
             "critic_score": ep.critic_score, "is_stale": ep.is_stale}
            for ep in eps
        ]

    def get_last_approved_episode_number(self, story_id: str) -> int:
        return self.episodes.get_last_approved_number(story_id)
