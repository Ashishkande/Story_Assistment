"""Story Service – orchestrates the full story generation pipeline.

This is the main business logic layer that:
1. Creates stories
2. Generates 200-episode plans
3. Runs the LangGraph episode workflow
4. Handles human feedback and propagation
5. Manages memory updates
6. Supports resumability
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.agents.context_builder import ContextBuilder
from app.agents.memory_updater import MemoryUpdaterAgent
from app.agents.planner import PlannerAgent
from app.agents.workflow import get_episode_workflow, EpisodeWorkflowState
from app.config import get_settings
from app.db.models import (
    EpisodeStatus, StoryStatus, FeedbackAction,
)
from app.db.repositories import (
    StoryRepo, PlanRepo, EpisodeRepo, CharacterRepo,
    WorldFactRepo, OpenThreadRepo, FeedbackRepo,
    MemorySummaryRepo, AgentRunRepo,
)
from app.llm.client import LLMRunner
from app.schemas.models import EpisodeOutput, CriticResult

logger = logging.getLogger(__name__)
settings = get_settings()


class StoryService:
    """Async service layer for the FastAPI backend."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.stories = StoryRepo(db)
        self.plans = PlanRepo(db)
        self.episodes = EpisodeRepo(db)
        self.characters = CharacterRepo(db)
        self.world_facts = WorldFactRepo(db)
        self.threads = OpenThreadRepo(db)
        self.feedback = FeedbackRepo(db)
        self.memory = MemorySummaryRepo(db)
        self.runs = AgentRunRepo(db)

    # ─── Story lifecycle ─────────────────────────────

    async def create_story(self, premise: str) -> dict:
        story = await self.stories.create(premise)
        return {"id": story.id, "premise": story.premise, "status": story.status}

    async def get_story(self, story_id: str) -> Optional[dict]:
        story = await self.stories.get(story_id)
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
            "created_at": story.created_at.isoformat(),
            "updated_at": story.updated_at.isoformat(),
        }

    async def list_stories(self) -> list[dict]:
        stories = await self.stories.list_all()
        return [
            {
                "id": s.id,
                "title": s.title,
                "premise": s.premise,
                "status": s.status,
                "current_episode": s.current_episode,
                "total_planned": s.total_planned,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in stories
        ]

    # ─── Plan generation ─────────────────────────────

    async def generate_plan(self, story_id: str) -> dict:
        story = await self.stories.get(story_id)
        if not story:
            raise ValueError(f"Story {story_id} not found")

        await self.stories.set_status(story_id, StoryStatus.PLANNING)

        run_id = str(uuid.uuid4())
        planner = PlannerAgent()

        try:
            plan_data, meta = planner.generate_plan(story_id, story.premise, run_id=run_id)
        except Exception as e:
            await self.stories.set_status(story_id, StoryStatus.CREATED)
            raise RuntimeError(f"Plan generation failed: {e}") from e

        # Persist plan
        plan = await self.plans.create_or_replace(story_id, {
            "arc_structure": {str(a["arc_number"]): a for a in plan_data.get("arcs", [])},
            "episode_plans": plan_data.get("episodes", []),
            "world_rules": plan_data.get("world_rules", []),
            "major_turning_points": plan_data.get("major_turning_points", []),
            "planned_resolutions": plan_data.get("planned_resolutions", []),
        })

        # Update story metadata
        await self.stories.update(story_id,
            title=plan_data.get("title"),
            genre=plan_data.get("genre"),
            tone=plan_data.get("tone"),
            status=StoryStatus.PLAN_PENDING_REVIEW,
        )

        # Persist characters from plan
        for char_data in plan_data.get("characters", []):
            await self.characters.upsert(
                story_id,
                char_data["name"],
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
        await self.runs.create(story_id,
            run_id=run_id,
            agent="planner",
            model=meta.get("model"),
            status="success",
            input_tokens=meta.get("input_tokens"),
            output_tokens=meta.get("output_tokens"),
            cost=meta.get("cost"),
            latency_ms=meta.get("latency_ms"),
        )

        return {"plan_id": plan.id, "title": plan_data.get("title"), "episodes_planned": len(plan_data.get("episodes", []))}

    async def approve_plan(self, story_id: str) -> None:
        await self.plans.approve(story_id)
        await self.stories.set_status(story_id, StoryStatus.ACTIVE)

    async def update_plan(self, story_id: str, updates: dict) -> None:
        plan = await self.plans.get(story_id)
        if not plan:
            raise ValueError("No plan found")
        update_data = {k: v for k, v in updates.items() if v is not None}
        await self.plans.create_or_replace(story_id, update_data)

    async def get_plan(self, story_id: str) -> Optional[dict]:
        plan = await self.plans.get(story_id)
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
            "created_at": plan.created_at.isoformat(),
        }

    # ─── Episode generation ─────────────────────────

    async def generate_next_episode(self, story_id: str) -> dict:
        story = await self.stories.get(story_id)
        if not story:
            raise ValueError(f"Story {story_id} not found")
        if story.status not in (StoryStatus.ACTIVE, StoryStatus.PAUSED):
            raise ValueError(f"Story is not in active state: {story.status}")

        plan = await self.plans.get(story_id)
        if not plan or not plan.approved:
            raise ValueError("Story plan has not been approved yet")

        # Determine next episode number
        last_approved = await self.episodes.get_last_approved_number(story_id)
        next_ep_num = last_approved + 1

        if next_ep_num > settings.total_episodes:
            raise ValueError(f"Story complete. All {settings.total_episodes} episodes generated.")

        # Check if episode is already in progress
        existing = await self.episodes.get(story_id, next_ep_num)
        if existing and existing.status == EpisodeStatus.HUMAN_REVIEW and not existing.is_stale:
            return {"episode_number": next_ep_num, "status": "already_in_human_review", "episode_id": existing.id}

        run_id = str(uuid.uuid4())

        # Build context
        builder = ContextBuilder()
        recent_eps = await self.episodes.list_approved(story_id, limit=24)
        rolling = await self.memory.get_rolling(story_id)
        chars = await self.characters.get_all(story_id)
        facts = await self.world_facts.get_all(story_id)
        threads = await self.threads.get_open(story_id)
        instructions = await self.feedback.get_active_instructions(story_id)

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

        # Get rejection reason if this episode was previously rejected
        rejection_reason = None
        if existing and existing.status == EpisodeStatus.REJECTED:
            rejection_reason = existing.rejection_reason

        # Create/update episode record
        if existing:
            await self.episodes.update(
                existing.id,
                status=EpisodeStatus.GENERATING,
                revision_count=existing.revision_count,
                is_stale=False,
                stale_reason=None,
            )
            ep_id = existing.id
        else:
            ep = await self.episodes.create(story_id, next_ep_num, status=EpisodeStatus.GENERATING)
            ep_id = ep.id

        await self.stories.update(story_id, status=StoryStatus.ACTIVE)

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

        # Persist results
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
            if isinstance(critic, dict):
                critic = CriticResult.model_validate(critic)
            update_data.update({
                "critic_score": critic.score,
                "critic_issues": [i.model_dump() if hasattr(i, "model_dump") else i for i in critic.issues],
                "critic_passed": critic.passed,
            })

        await self.episodes.update(ep_id, **update_data)

        # Persist all agent run metadata
        allowed = {
            "run_id", "episode_number", "agent", "model", "status",
            "input_tokens", "output_tokens", "cost", "latency_ms",
            "retry_count", "decision", "error_message", "extra",
        }
        for run_meta in final_state.get("agent_run_metadata", []):
            payload = {key: value for key, value in run_meta.items() if key in allowed}
            await self.runs.create(story_id, **payload)

        return {
            "episode_number": next_ep_num,
            "episode_id": ep_id,
            "status": EpisodeStatus.HUMAN_REVIEW,
            "critic_passed": critic.passed if critic else None,
            "critic_score": critic.score if critic else None,
        }

    # ─── Human review actions ────────────────────────

    async def approve_episode(self, story_id: str, episode_number: int) -> dict:
        ep = await self.episodes.get(story_id, episode_number)
        if not ep:
            raise ValueError(f"Episode {episode_number} not found")

        await self.episodes.set_status(ep.id, EpisodeStatus.APPROVED)
        await self.stories.update(story_id, current_episode=episode_number)

        # Run memory updater
        await self._run_memory_updater(story_id, ep)

        # Record feedback
        await self.feedback.create(story_id,
            episode_id=ep.id,
            after_episode=episode_number,
            action=FeedbackAction.APPROVE,
            is_active=False,
        )

        return {"status": "approved", "episode_number": episode_number}

    async def edit_episode(self, story_id: str, episode_number: int, content: str, edit_notes: str = "") -> dict:
        ep = await self.episodes.get(story_id, episode_number)
        if not ep:
            raise ValueError(f"Episode {episode_number} not found")

        word_count = len(content.split())
        await self.episodes.update(ep.id,
            content=content,
            word_count=word_count,
            human_edited=True,
            edit_notes=edit_notes,
            status=EpisodeStatus.APPROVED,
        )
        await self.stories.update(story_id, current_episode=episode_number)

        # Run memory updater (with edited content)
        ep.content = content
        ep.summary = None  # Will be regenerated lazily
        await self._run_memory_updater(story_id, ep)

        # Mark future episodes as potentially stale
        await self._mark_future_episodes_stale(story_id, episode_number, "Episode was human-edited")

        # Record feedback
        await self.feedback.create(story_id,
            episode_id=ep.id,
            after_episode=episode_number,
            action=FeedbackAction.EDIT,
            edited_content=content,
            is_active=False,
        )

        return {"status": "edited", "episode_number": episode_number, "word_count": word_count}

    async def reject_episode(self, story_id: str, episode_number: int, reason: str) -> dict:
        ep = await self.episodes.get(story_id, episode_number)
        if not ep:
            raise ValueError(f"Episode {episode_number} not found")

        await self.episodes.update(ep.id,
            status=EpisodeStatus.REJECTED,
            rejection_reason=reason,
        )

        # Record feedback
        await self.feedback.create(story_id,
            episode_id=ep.id,
            after_episode=episode_number,
            action=FeedbackAction.REJECT,
            rejection_reason=reason,
            is_active=False,
        )

        return {"status": "rejected", "episode_number": episode_number}

    async def add_feedback(self, story_id: str, episode_number: int, instruction: str) -> dict:
        """Add a persistent human instruction that affects future episodes."""
        ep = await self.episodes.get(story_id, episode_number)
        ep_id = ep.id if ep else None

        fb = await self.feedback.create(story_id,
            episode_id=ep_id,
            after_episode=episode_number,
            action=FeedbackAction.FEEDBACK,
            instruction=instruction,
            is_active=True,  # persistent!
        )

        logger.info(f"[HumanFeedback] Stored instruction for story {story_id} after ep {episode_number}: {instruction}")
        return {
            "id": fb.id,
            "instruction": instruction,
            "active": True,
            "will_affect_episodes": f"Episode {episode_number + 1} onwards",
        }

    # ─── Memory helpers ──────────────────────────────

    async def _run_memory_updater(self, story_id: str, episode) -> None:
        """Run memory updater after episode approval."""
        run_id = str(uuid.uuid4())
        updater = MemoryUpdaterAgent()

        chars = await self.characters.get_all(story_id)
        threads = await self.threads.get_open(story_id)
        rolling = await self.memory.get_rolling(story_id)

        current_chars = [
            {"name": c.name, "status": c.status, "current_state": c.current_state}
            for c in chars
        ]
        current_threads = [
            {"title": t.title, "description": t.description}
            for t in threads
        ]

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

        # Apply updates
        for char_update in updates.get("character_updates", []):
            name = char_update.get("name")
            if not name:
                continue
            update_kwargs = {}
            if char_update.get("current_state"):
                update_kwargs["current_state"] = char_update["current_state"]
            if char_update.get("status"):
                update_kwargs["status"] = char_update["status"]
            if char_update.get("important_facts"):
                existing_char = await self.characters.get_by_name(story_id, name)
                if existing_char:
                    existing_facts = list(existing_char.important_facts or [])
                    existing_facts.extend(char_update["important_facts"])
                    update_kwargs["important_facts"] = list(set(existing_facts))
            if char_update.get("relationship_updates"):
                existing_char = await self.characters.get_by_name(story_id, name)
                if existing_char:
                    rels = dict(existing_char.relationships or {})
                    rels.update(char_update["relationship_updates"])
                    update_kwargs["relationship_updates"] = rels
            if update_kwargs:
                await self.characters.upsert(story_id, name, last_updated_episode=episode.episode_number, **update_kwargs)

        # Persist new world facts
        for fact in updates.get("new_world_facts", []):
            await self.world_facts.upsert(
                story_id,
                fact.get("category", "other"),
                fact.get("key", ""),
                fact.get("value", ""),
                episode.episode_number,
            )

        # Open new threads
        for thread_data in updates.get("threads_to_open", []):
            await self.threads.create(story_id,
                thread_type=thread_data.get("thread_type", "other"),
                title=thread_data.get("title", "Unknown thread"),
                description=thread_data.get("description", ""),
                episode_introduced=episode.episode_number,
                importance=thread_data.get("importance", "medium"),
                planned_resolution=thread_data.get("planned_resolution"),
                planned_resolution_episode=thread_data.get("planned_resolution_episode"),
            )

        # Resolve threads
        all_threads = await self.threads.get_all(story_id)
        resolved_titles = set(t.lower() for t in updates.get("threads_to_resolve", []))
        for thread in all_threads:
            if thread.title.lower() in resolved_titles:
                await self.threads.resolve(thread.id, episode.episode_number)

        # Update rolling summary
        new_summary = updates.get("new_rolling_summary", "")
        if new_summary:
            await self.memory.upsert_rolling(story_id, new_summary, episode.episode_number)

        # Log agent run
        await self.runs.create(story_id,
            run_id=run_id,
            episode_number=episode.episode_number,
            agent="memory_updater",
            model=meta.get("model"),
            status="success",
            input_tokens=meta.get("input_tokens"),
            output_tokens=meta.get("output_tokens"),
            cost=meta.get("cost"),
            latency_ms=meta.get("latency_ms"),
        )

    async def _mark_future_episodes_stale(self, story_id: str, from_episode: int, reason: str) -> None:
        """Mark episodes after from_episode as potentially stale."""
        all_eps = await self.episodes.list_all(story_id)
        for ep in all_eps:
            if ep.episode_number > from_episode and ep.status == EpisodeStatus.APPROVED:
                await self.episodes.update(ep.id, is_stale=True, stale_reason=reason)
                logger.info(f"[Staleness] Marked episode {ep.episode_number} as stale: {reason}")

    async def reconcile_from(self, story_id: str, from_episode: int) -> dict:
        """Handle a retroactive edit: mark later episodes stale and resume from from_episode.

        Next generate uses the last non-stale approved episode, so episode N+1 is rewritten
        instead of skipping to the old tip of the serial.
        """
        ep = await self.episodes.get(story_id, from_episode)
        if not ep:
            raise ValueError(f"Episode {from_episode} not found")
        await self._mark_future_episodes_stale(
            story_id, from_episode, f"Reconcile after episode {from_episode}"
        )
        await self.stories.update(story_id, current_episode=from_episode, status=StoryStatus.ACTIVE)
        stale = [
            e.episode_number
            for e in await self.episodes.list_all(story_id)
            if e.is_stale and e.episode_number > from_episode
        ]
        last = await self.episodes.get_last_approved_number(story_id)
        return {
            "from_episode": from_episode,
            "stale_episodes": stale,
            "last_canonical_episode": last,
            "next_episode": last + 1,
            "note": "Generate next to rewrite stale episodes in order. Memory was last updated from the canonical episode.",
        }

    # ─── Memory / logs views ─────────────────────────

    async def get_memory(self, story_id: str) -> dict:
        rolling = await self.memory.get_rolling(story_id)
        chars = await self.characters.get_all(story_id)
        facts = await self.world_facts.get_all(story_id)
        threads = await self.threads.get_open(story_id)
        instructions = await self.feedback.get_active_instructions(story_id)

        return {
            "rolling_summary": rolling.content if rolling else None,
            "characters": [
                {
                    "name": c.name,
                    "role": c.role,
                    "personality": c.personality,
                    "goals": c.goals,
                    "relationships": c.relationships,
                    "current_state": c.current_state,
                    "important_facts": c.important_facts,
                    "character_arc": c.character_arc,
                    "status": c.status,
                    "first_appeared": c.first_appeared,
                }
                for c in chars
            ],
            "world_facts": [
                {"category": f.category, "key": f.key, "value": f.value}
                for f in facts
            ],
            "open_threads": [
                {
                    "title": t.title,
                    "description": t.description,
                    "thread_type": t.thread_type,
                    "importance": t.importance,
                    "episode_introduced": t.episode_introduced,
                }
                for t in threads
            ],
            "active_instructions": [fb.instruction for fb in instructions if fb.instruction],
        }

    async def get_logs(self, story_id: str, limit: int = 100) -> list[dict]:
        runs = await self.runs.get_for_story(story_id, limit=limit)
        return [
            {
                "id": r.id,
                "run_id": r.run_id,
                "episode_number": r.episode_number,
                "agent": r.agent,
                "model": r.model,
                "status": r.status,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "cost": r.cost,
                "latency_ms": r.latency_ms,
                "retry_count": r.retry_count,
                "created_at": r.created_at.isoformat(),
            }
            for r in runs
        ]

    async def get_episode(self, story_id: str, episode_number: int) -> Optional[dict]:
        ep = await self.episodes.get(story_id, episode_number)
        if not ep:
            return None
        return {
            "id": ep.id,
            "story_id": ep.story_id,
            "episode_number": ep.episode_number,
            "title": ep.title,
            "content": ep.content,
            "summary": ep.summary,
            "hook": ep.hook,
            "status": ep.status,
            "word_count": ep.word_count,
            "revision_count": ep.revision_count,
            "characters_present": ep.characters_present,
            "facts_introduced": ep.facts_introduced,
            "threads_opened": ep.threads_opened,
            "threads_resolved": ep.threads_resolved,
            "critic_score": ep.critic_score,
            "critic_issues": ep.critic_issues,
            "critic_passed": ep.critic_passed,
            "human_edited": ep.human_edited,
            "rejection_reason": ep.rejection_reason,
            "is_stale": ep.is_stale,
            "stale_reason": ep.stale_reason,
            "created_at": ep.created_at.isoformat(),
            "updated_at": ep.updated_at.isoformat(),
        }

    async def list_episodes(self, story_id: str) -> list[dict]:
        eps = await self.episodes.list_all(story_id)
        return [
            {
                "episode_number": ep.episode_number,
                "title": ep.title,
                "status": ep.status,
                "word_count": ep.word_count,
                "critic_score": ep.critic_score,
                "is_stale": ep.is_stale,
                "revision_count": ep.revision_count,
            }
            for ep in eps
        ]

    async def get_last_approved_episode_number(self, story_id: str) -> int:
        return await self.episodes.get_last_approved_number(story_id)

    async def resume_point(self, story_id: str) -> dict:
        story = await self.get_story(story_id)
        if not story:
            raise ValueError(f"Story {story_id} not found")
        last = await self.get_last_approved_episode_number(story_id)
        return {
            "story_id": story_id,
            "last_approved_episode": last,
            "next_episode": last + 1,
            "status": story["status"],
            "title": story.get("title"),
        }

    async def list_feedback(self, story_id: str) -> list[dict]:
        rows = await self.feedback.get_all(story_id)
        return [
            {
                "id": row.id,
                "episode": row.after_episode,
                "action": row.action,
                "instruction": row.instruction,
                "rejection_reason": row.rejection_reason,
                "is_active": row.is_active,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    async def dashboard(self) -> dict:
        stories = await self.list_stories()
        recent_activity: list[dict] = []
        for story in stories[:12]:
            logs = await self.get_logs(story["id"], limit=3)
            for log in logs:
                recent_activity.append({**log, "story_id": story["id"], "story_title": story.get("title")})
        recent_activity.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return {
            "total_stories": len(stories),
            "generating": sum(1 for story in stories if story["status"] in {"planning", "active"}),
            "completed": sum(1 for story in stories if story["status"] == "completed"),
            "episodes_generated": sum(story.get("current_episode") or 0 for story in stories),
            "recent_stories": stories[:6],
            "recent_activity": recent_activity[:8],
        }

    async def run_demo(self, premise: str, num_episodes: int = 15, progress=None) -> dict:
        """Same automated demo the CLI runs: plan, approve, generate, two HITL notes."""

        def step(message: str) -> None:
            logger.info(f"[Demo] {message}")
            if progress:
                progress(message)

        step("Creating story")
        story = await self.create_story(premise)
        story_id = story["id"]

        step("Generating 200-episode plan")
        plan_result = await self.generate_plan(story_id)

        step("Approving plan")
        await self.approve_plan(story_id)

        async def _generate_and_approve(label: str) -> int:
            step(label)
            result = await self.generate_next_episode(story_id)
            episode_number = result["episode_number"]
            await self.approve_episode(story_id, episode_number)
            return episode_number

        generated: list[int] = []
        for index in range(1, min(4, num_episodes + 1)):
            generated.append(await _generate_and_approve(f"Generating episode {index}"))

        interventions: list[dict] = []
        instruction_one = (
            "Do not reveal the killer's identity yet; maintain mystery and suspense across upcoming episodes."
        )
        step("Recording HITL instruction after episode 3")
        await self.add_feedback(story_id, 3, instruction_one)
        interventions.append({"after_episode": 3, "instruction": instruction_one})

        for index in range(4, min(8, num_episodes + 1)):
            generated.append(
                await _generate_and_approve(f"Generating episode {index} with the first instruction")
            )

        if num_episodes >= 7:
            instruction_two = (
                "Introduce a new detective character who is skeptical of the protagonist's investigation."
            )
            step("Recording HITL instruction after episode 7")
            await self.add_feedback(story_id, 7, instruction_two)
            interventions.append({"after_episode": 7, "instruction": instruction_two})
            for index in range(8, num_episodes + 1):
                generated.append(
                    await _generate_and_approve(f"Generating episode {index} with both instructions")
                )

        story_final = await self.get_story(story_id)
        logs = await self.get_logs(story_id)
        memory = await self.get_memory(story_id)
        total_cost = sum((row.get("cost") or 0.0) for row in logs)
        step("Demo complete")
        return {
            "story_id": story_id,
            "title": plan_result.get("title") or (story_final or {}).get("title"),
            "episodes_generated": generated,
            "current_episode": (story_final or {}).get("current_episode", 0),
            "characters": len(memory.get("characters") or []),
            "world_facts": len(memory.get("world_facts") or []),
            "open_threads": len(memory.get("open_threads") or []),
            "active_instructions": memory.get("active_instructions") or [],
            "interventions": interventions,
            "total_runs": len(logs),
            "total_cost": total_cost,
        }
