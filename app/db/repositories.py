"""Repository classes for all domain entities."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.models import (
    Story, StoryPlan, Episode, Character, WorldFact,
    OpenThread, HumanFeedback, MemorySummary, AgentRun,
    EpisodeStatus, StoryStatus, ThreadStatus,
)


def _utcnow():
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────
# Story Repository
# ─────────────────────────────────────────────

class StoryRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, premise: str) -> Story:
        story = Story(id=str(uuid.uuid4()), premise=premise)
        self.db.add(story)
        await self.db.commit()
        await self.db.refresh(story)
        return story

    async def get(self, story_id: str) -> Optional[Story]:
        result = await self.db.execute(select(Story).where(Story.id == story_id))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[Story]:
        result = await self.db.execute(select(Story).order_by(Story.created_at.desc()))
        return list(result.scalars().all())

    async def update(self, story_id: str, **kwargs) -> Optional[Story]:
        await self.db.execute(
            update(Story).where(Story.id == story_id).values(**kwargs, updated_at=_utcnow())
        )
        await self.db.commit()
        return await self.get(story_id)

    async def set_status(self, story_id: str, status: str) -> None:
        await self.update(story_id, status=status)


class StorySyncRepo:
    """Sync version for CLI / scripts."""
    def __init__(self, db: Session):
        self.db = db

    def get(self, story_id: str) -> Optional[Story]:
        return self.db.get(Story, story_id)

    def list_all(self) -> list[Story]:
        return self.db.execute(select(Story).order_by(Story.created_at.desc())).scalars().all()

    def update(self, story_id: str, **kwargs) -> Optional[Story]:
        self.db.execute(update(Story).where(Story.id == story_id).values(**kwargs, updated_at=_utcnow()))
        self.db.commit()
        return self.get(story_id)


# ─────────────────────────────────────────────
# Plan Repository
# ─────────────────────────────────────────────

class PlanRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_or_replace(self, story_id: str, data: dict) -> StoryPlan:
        existing = await self.get(story_id)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            existing.updated_at = _utcnow()
            existing.version += 1
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        plan = StoryPlan(id=str(uuid.uuid4()), story_id=story_id, **data)
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def get(self, story_id: str) -> Optional[StoryPlan]:
        result = await self.db.execute(select(StoryPlan).where(StoryPlan.story_id == story_id))
        return result.scalar_one_or_none()

    async def approve(self, story_id: str) -> None:
        await self.db.execute(
            update(StoryPlan).where(StoryPlan.story_id == story_id).values(approved=True)
        )
        await self.db.commit()

    async def update_episode_plan(self, story_id: str, episode_number: int, plan_data: dict) -> None:
        plan = await self.get(story_id)
        if not plan:
            return
        plans = plan.episode_plans or []
        for i, ep in enumerate(plans):
            if ep.get("episode_number") == episode_number:
                plans[i] = {**ep, **plan_data}
                break
        plan.episode_plans = plans
        plan.updated_at = _utcnow()
        await self.db.commit()


class PlanSyncRepo:
    def __init__(self, db: Session):
        self.db = db

    def get(self, story_id: str) -> Optional[StoryPlan]:
        return self.db.execute(select(StoryPlan).where(StoryPlan.story_id == story_id)).scalar_one_or_none()

    def create_or_replace(self, story_id: str, data: dict) -> StoryPlan:
        existing = self.get(story_id)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            existing.updated_at = _utcnow()
            existing.version = (existing.version or 1) + 1
            self.db.commit()
            self.db.refresh(existing)
            return existing
        plan = StoryPlan(id=str(uuid.uuid4()), story_id=story_id, **data)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def approve(self, story_id: str) -> None:
        self.db.execute(update(StoryPlan).where(StoryPlan.story_id == story_id).values(approved=True))
        self.db.commit()


# ─────────────────────────────────────────────
# Episode Repository
# ─────────────────────────────────────────────

class EpisodeRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, story_id: str, episode_number: int, **kwargs) -> Episode:
        ep = Episode(id=str(uuid.uuid4()), story_id=story_id, episode_number=episode_number, **kwargs)
        self.db.add(ep)
        await self.db.commit()
        await self.db.refresh(ep)
        return ep

    async def get(self, story_id: str, episode_number: int) -> Optional[Episode]:
        result = await self.db.execute(
            select(Episode).where(
                and_(Episode.story_id == story_id, Episode.episode_number == episode_number)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, episode_id: str) -> Optional[Episode]:
        return await self.db.get(Episode, episode_id)

    async def list_approved(self, story_id: str, limit: int = 10) -> list[Episode]:
        result = await self.db.execute(
            select(Episode)
            .where(and_(
                Episode.story_id == story_id,
                Episode.status == EpisodeStatus.APPROVED,
                Episode.is_stale.is_(False),
            ))
            .order_by(Episode.episode_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_all(self, story_id: str) -> list[Episode]:
        result = await self.db.execute(
            select(Episode).where(Episode.story_id == story_id).order_by(Episode.episode_number)
        )
        return list(result.scalars().all())

    async def update(self, episode_id: str, **kwargs) -> Optional[Episode]:
        await self.db.execute(
            update(Episode).where(Episode.id == episode_id).values(**kwargs, updated_at=_utcnow())
        )
        await self.db.commit()
        return await self.get_by_id(episode_id)

    async def set_status(self, episode_id: str, status: str) -> None:
        await self.update(episode_id, status=status)

    async def get_last_approved_number(self, story_id: str) -> int:
        result = await self.db.execute(
            select(Episode.episode_number)
            .where(and_(
                Episode.story_id == story_id,
                Episode.status == EpisodeStatus.APPROVED,
                Episode.is_stale.is_(False),
            ))
            .order_by(Episode.episode_number.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row or 0


class EpisodeSyncRepo:
    def __init__(self, db: Session):
        self.db = db

    def get(self, story_id: str, episode_number: int) -> Optional[Episode]:
        return self.db.execute(
            select(Episode).where(
                and_(Episode.story_id == story_id, Episode.episode_number == episode_number)
            )
        ).scalar_one_or_none()

    def list_all(self, story_id: str) -> list[Episode]:
        return self.db.execute(
            select(Episode).where(Episode.story_id == story_id).order_by(Episode.episode_number)
        ).scalars().all()

    def create(self, story_id: str, episode_number: int, **kwargs) -> Episode:
        ep = Episode(id=str(uuid.uuid4()), story_id=story_id, episode_number=episode_number, **kwargs)
        self.db.add(ep)
        self.db.commit()
        self.db.refresh(ep)
        return ep

    def update(self, episode_id: str, **kwargs) -> None:
        self.db.execute(update(Episode).where(Episode.id == episode_id).values(**kwargs, updated_at=_utcnow()))
        self.db.commit()

    def get_last_approved_number(self, story_id: str) -> int:
        result = self.db.execute(
            select(Episode.episode_number)
            .where(and_(
                Episode.story_id == story_id,
                Episode.status == EpisodeStatus.APPROVED,
                Episode.is_stale.is_(False),
            ))
            .order_by(Episode.episode_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        return result or 0


# ─────────────────────────────────────────────
# Character Repository
# ─────────────────────────────────────────────

class CharacterRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, story_id: str) -> list[Character]:
        result = await self.db.execute(select(Character).where(Character.story_id == story_id))
        return list(result.scalars().all())

    async def get_by_name(self, story_id: str, name: str) -> Optional[Character]:
        result = await self.db.execute(
            select(Character).where(and_(Character.story_id == story_id, Character.name == name))
        )
        return result.scalar_one_or_none()

    async def upsert(self, story_id: str, name: str, **kwargs) -> Character:
        existing = await self.get_by_name(story_id, name)
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            existing.updated_at = _utcnow()
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        char = Character(id=str(uuid.uuid4()), story_id=story_id, name=name, **kwargs)
        self.db.add(char)
        await self.db.commit()
        await self.db.refresh(char)
        return char


class CharacterSyncRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, story_id: str) -> list[Character]:
        return self.db.execute(select(Character).where(Character.story_id == story_id)).scalars().all()

    def get_by_name(self, story_id: str, name: str) -> Optional[Character]:
        return self.db.execute(
            select(Character).where(and_(Character.story_id == story_id, Character.name == name))
        ).scalar_one_or_none()

    def upsert(self, story_id: str, name: str, **kwargs) -> Character:
        existing = self.get_by_name(story_id, name)
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            existing.updated_at = _utcnow()
            self.db.commit()
            return existing
        char = Character(id=str(uuid.uuid4()), story_id=story_id, name=name, **kwargs)
        self.db.add(char)
        self.db.commit()
        return char


# ─────────────────────────────────────────────
# WorldFact Repository
# ─────────────────────────────────────────────

class WorldFactRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, story_id: str) -> list[WorldFact]:
        result = await self.db.execute(
            select(WorldFact).where(and_(WorldFact.story_id == story_id, WorldFact.is_active == True))
        )
        return list(result.scalars().all())

    async def upsert(self, story_id: str, category: str, key: str, value: str, episode: int) -> WorldFact:
        result = await self.db.execute(
            select(WorldFact).where(and_(WorldFact.story_id == story_id, WorldFact.key == key))
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            existing.category = category
            await self.db.commit()
            return existing
        fact = WorldFact(
            id=str(uuid.uuid4()), story_id=story_id, category=category,
            key=key, value=value, episode_introduced=episode
        )
        self.db.add(fact)
        await self.db.commit()
        await self.db.refresh(fact)
        return fact


class WorldFactSyncRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, story_id: str) -> list[WorldFact]:
        return self.db.execute(
            select(WorldFact).where(and_(WorldFact.story_id == story_id, WorldFact.is_active == True))
        ).scalars().all()

    def upsert(self, story_id: str, category: str, key: str, value: str, episode: int) -> WorldFact:
        existing = self.db.execute(
            select(WorldFact).where(and_(WorldFact.story_id == story_id, WorldFact.key == key))
        ).scalar_one_or_none()
        if existing:
            existing.value = value
            self.db.commit()
            return existing
        fact = WorldFact(
            id=str(uuid.uuid4()), story_id=story_id, category=category,
            key=key, value=value, episode_introduced=episode
        )
        self.db.add(fact)
        self.db.commit()
        return fact


# ─────────────────────────────────────────────
# OpenThread Repository
# ─────────────────────────────────────────────

class OpenThreadRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_open(self, story_id: str) -> list[OpenThread]:
        result = await self.db.execute(
            select(OpenThread).where(and_(OpenThread.story_id == story_id, OpenThread.status == ThreadStatus.OPEN))
        )
        return list(result.scalars().all())

    async def get_all(self, story_id: str) -> list[OpenThread]:
        result = await self.db.execute(select(OpenThread).where(OpenThread.story_id == story_id))
        return list(result.scalars().all())

    async def create(self, story_id: str, **kwargs) -> OpenThread:
        thread = OpenThread(id=str(uuid.uuid4()), story_id=story_id, **kwargs)
        self.db.add(thread)
        await self.db.commit()
        await self.db.refresh(thread)
        return thread

    async def resolve(self, thread_id: str, episode_number: int) -> None:
        await self.db.execute(
            update(OpenThread).where(OpenThread.id == thread_id)
            .values(status=ThreadStatus.RESOLVED, episode_resolved=episode_number, updated_at=_utcnow())
        )
        await self.db.commit()


class OpenThreadSyncRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_open(self, story_id: str) -> list[OpenThread]:
        return self.db.execute(
            select(OpenThread).where(and_(OpenThread.story_id == story_id, OpenThread.status == ThreadStatus.OPEN))
        ).scalars().all()

    def get_all(self, story_id: str) -> list[OpenThread]:
        return self.db.execute(select(OpenThread).where(OpenThread.story_id == story_id)).scalars().all()

    def create(self, story_id: str, **kwargs) -> OpenThread:
        thread = OpenThread(id=str(uuid.uuid4()), story_id=story_id, **kwargs)
        self.db.add(thread)
        self.db.commit()
        return thread

    def resolve(self, thread_id: str, episode_number: int) -> None:
        self.db.execute(
            update(OpenThread).where(OpenThread.id == thread_id)
            .values(status=ThreadStatus.RESOLVED, episode_resolved=episode_number)
        )
        self.db.commit()


# ─────────────────────────────────────────────
# HumanFeedback Repository
# ─────────────────────────────────────────────

class FeedbackRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, story_id: str, **kwargs) -> HumanFeedback:
        fb = HumanFeedback(id=str(uuid.uuid4()), story_id=story_id, **kwargs)
        self.db.add(fb)
        await self.db.commit()
        await self.db.refresh(fb)
        return fb

    async def get_active_instructions(self, story_id: str) -> list[HumanFeedback]:
        result = await self.db.execute(
            select(HumanFeedback).where(
                and_(
                    HumanFeedback.story_id == story_id,
                    HumanFeedback.is_active == True,
                    HumanFeedback.instruction != None,
                )
            ).order_by(HumanFeedback.created_at)
        )
        return list(result.scalars().all())

    async def deactivate(self, feedback_id: str) -> Optional[HumanFeedback]:
        await self.db.execute(
            update(HumanFeedback).where(HumanFeedback.id == feedback_id).values(is_active=False)
        )
        await self.db.commit()
        return await self.db.get(HumanFeedback, feedback_id)

    async def deactivate_word_count_instructions(self, story_id: str, keep_id: str) -> int:
        from app.agents.guards import is_word_count_instruction
        rows = await self.get_active_instructions(story_id)
        count = 0
        for row in rows:
            if row.id == keep_id or not is_word_count_instruction(row.instruction or ""):
                continue
            await self.deactivate(row.id)
            count += 1
        return count
        result = await self.db.execute(
            select(HumanFeedback).where(HumanFeedback.story_id == story_id).order_by(HumanFeedback.created_at)
        )
        return list(result.scalars().all())


class FeedbackSyncRepo:
    def __init__(self, db: Session):
        self.db = db

    def create(self, story_id: str, **kwargs) -> HumanFeedback:
        fb = HumanFeedback(id=str(uuid.uuid4()), story_id=story_id, **kwargs)
        self.db.add(fb)
        self.db.commit()
        return fb

    def get_active_instructions(self, story_id: str) -> list[HumanFeedback]:
        return self.db.execute(
            select(HumanFeedback).where(
                and_(
                    HumanFeedback.story_id == story_id,
                    HumanFeedback.is_active == True,
                    HumanFeedback.instruction != None,
                )
            ).order_by(HumanFeedback.created_at)
        ).scalars().all()

    def get_all(self, story_id: str) -> list[HumanFeedback]:
        return self.db.execute(
            select(HumanFeedback).where(HumanFeedback.story_id == story_id).order_by(HumanFeedback.created_at)
        ).scalars().all()


# ─────────────────────────────────────────────
# MemorySummary Repository
# ─────────────────────────────────────────────

class MemorySummaryRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_rolling(self, story_id: str) -> Optional[MemorySummary]:
        result = await self.db.execute(
            select(MemorySummary)
            .where(and_(MemorySummary.story_id == story_id, MemorySummary.summary_type == "rolling"))
            .order_by(MemorySummary.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def upsert_rolling(self, story_id: str, content: str, episode_end: int) -> MemorySummary:
        existing = await self.get_rolling(story_id)
        if existing:
            existing.content = content
            existing.episode_end = episode_end
            existing.updated_at = _utcnow()
            await self.db.commit()
            return existing
        summary = MemorySummary(
            id=str(uuid.uuid4()), story_id=story_id,
            summary_type="rolling", episode_end=episode_end, content=content
        )
        self.db.add(summary)
        await self.db.commit()
        await self.db.refresh(summary)
        return summary

    async def get_arc_summaries(self, story_id: str) -> list[MemorySummary]:
        result = await self.db.execute(
            select(MemorySummary).where(
                and_(MemorySummary.story_id == story_id, MemorySummary.summary_type == "arc")
            ).order_by(MemorySummary.episode_start)
        )
        return list(result.scalars().all())


class MemorySummarySyncRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_rolling(self, story_id: str) -> Optional[MemorySummary]:
        return self.db.execute(
            select(MemorySummary)
            .where(and_(MemorySummary.story_id == story_id, MemorySummary.summary_type == "rolling"))
            .order_by(MemorySummary.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def upsert_rolling(self, story_id: str, content: str, episode_end: int) -> MemorySummary:
        existing = self.get_rolling(story_id)
        if existing:
            existing.content = content
            existing.episode_end = episode_end
            self.db.commit()
            return existing
        summary = MemorySummary(
            id=str(uuid.uuid4()), story_id=story_id,
            summary_type="rolling", episode_end=episode_end, content=content
        )
        self.db.add(summary)
        self.db.commit()
        return summary


# ─────────────────────────────────────────────
# AgentRun Repository
# ─────────────────────────────────────────────

class AgentRunRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, story_id: str, **kwargs) -> AgentRun:
        run = AgentRun(id=str(uuid.uuid4()), story_id=story_id, **kwargs)
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def get_for_story(self, story_id: str, limit: int = 100) -> list[AgentRun]:
        result = await self.db.execute(
            select(AgentRun).where(AgentRun.story_id == story_id)
            .order_by(AgentRun.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


class AgentRunSyncRepo:
    def __init__(self, db: Session):
        self.db = db

    def create(self, story_id: str, **kwargs) -> AgentRun:
        run = AgentRun(id=str(uuid.uuid4()), story_id=story_id, **kwargs)
        self.db.add(run)
        self.db.commit()
        return run

    def get_for_story(self, story_id: str, limit: int = 100) -> list[AgentRun]:
        return self.db.execute(
            select(AgentRun).where(AgentRun.story_id == story_id)
            .order_by(AgentRun.created_at.desc()).limit(limit)
        ).scalars().all()
