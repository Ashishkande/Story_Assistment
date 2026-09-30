"""Database models compatible with both PostgreSQL (production) and SQLite (testing)."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    JSON,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


def _json_col(default_factory=dict):
    """Returns JSON column with appropriate default – works in both PG and SQLite."""
    return mapped_column(JSON, default=default_factory)


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class StoryStatus(str, PyEnum):
    CREATED = "created"
    PLANNING = "planning"
    PLAN_PENDING_REVIEW = "plan_pending_review"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class EpisodeStatus(str, PyEnum):
    PLANNED = "planned"
    GENERATING = "generating"
    CRITIC_REVIEW = "critic_review"
    REVISING = "revising"
    HUMAN_REVIEW = "human_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    STALE = "stale"


class ThreadStatus(str, PyEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DROPPED = "dropped"


class ThreadType(str, PyEnum):
    MYSTERY = "mystery"
    CONFLICT = "conflict"
    QUESTION = "question"
    PROMISE = "promise"
    FORESHADOWING = "foreshadowing"
    RELATIONSHIP = "relationship"
    OTHER = "other"


class CharacterStatus(str, PyEnum):
    ALIVE = "alive"
    DEAD = "dead"
    MISSING = "missing"
    UNKNOWN = "unknown"


class FeedbackAction(str, PyEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    FEEDBACK = "feedback"


class AgentRunStatus(str, PyEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ─────────────────────────────────────────────
# Stories
# ─────────────────────────────────────────────

class Story(Base):
    __tablename__ = "stories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str | None] = mapped_column(String(500))
    premise: Mapped[str] = mapped_column(Text, nullable=False)
    genre: Mapped[str | None] = mapped_column(String(200))
    tone: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(50), default=StoryStatus.CREATED, nullable=False)
    current_episode: Mapped[int] = mapped_column(Integer, default=0)
    total_planned: Mapped[int] = mapped_column(Integer, default=200)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    plan: Mapped[StoryPlan | None] = relationship("StoryPlan", back_populates="story", uselist=False)
    episodes: Mapped[list[Episode]] = relationship("Episode", back_populates="story", order_by="Episode.episode_number")
    characters: Mapped[list[Character]] = relationship("Character", back_populates="story")
    world_facts: Mapped[list[WorldFact]] = relationship("WorldFact", back_populates="story")
    open_threads: Mapped[list[OpenThread]] = relationship("OpenThread", back_populates="story")
    human_feedback: Mapped[list[HumanFeedback]] = relationship("HumanFeedback", back_populates="story")
    memory_summaries: Mapped[list[MemorySummary]] = relationship("MemorySummary", back_populates="story")
    agent_runs: Mapped[list[AgentRun]] = relationship("AgentRun", back_populates="story")

    __table_args__ = (Index("ix_stories_status", "status"),)


# ─────────────────────────────────────────────
# Story Plans
# ─────────────────────────────────────────────

class StoryPlan(Base):
    __tablename__ = "story_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    story_id: Mapped[str] = mapped_column(String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    arc_structure: Mapped[Any] = mapped_column(JSON, default=dict)
    episode_plans: Mapped[Any] = mapped_column(JSON, default=list)
    world_rules: Mapped[Any] = mapped_column(JSON, default=list)
    major_turning_points: Mapped[Any] = mapped_column(JSON, default=list)
    planned_resolutions: Mapped[Any] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    story: Mapped[Story] = relationship("Story", back_populates="plan")

    __table_args__ = (UniqueConstraint("story_id", name="uq_story_plan"),)


# ─────────────────────────────────────────────
# Episodes
# ─────────────────────────────────────────────

class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    story_id: Mapped[str] = mapped_column(String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    episode_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    content: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    hook: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default=EpisodeStatus.PLANNED)
    word_count: Mapped[int | None] = mapped_column(Integer)
    revision_count: Mapped[int] = mapped_column(Integer, default=0)
    characters_present: Mapped[Any] = mapped_column(JSON, default=list)
    facts_introduced: Mapped[Any] = mapped_column(JSON, default=list)
    threads_opened: Mapped[Any] = mapped_column(JSON, default=list)
    threads_resolved: Mapped[Any] = mapped_column(JSON, default=list)
    critic_score: Mapped[float | None] = mapped_column(Float)
    critic_issues: Mapped[Any] = mapped_column(JSON, default=list)
    critic_passed: Mapped[bool | None] = mapped_column(Boolean)
    human_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    edit_notes: Mapped[str | None] = mapped_column(Text)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False)
    stale_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    story: Mapped[Story] = relationship("Story", back_populates="episodes")

    __table_args__ = (
        UniqueConstraint("story_id", "episode_number", name="uq_story_episode"),
        Index("ix_episodes_story_number", "story_id", "episode_number"),
        Index("ix_episodes_status", "status"),
    )


# ─────────────────────────────────────────────
# Characters
# ─────────────────────────────────────────────

class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    story_id: Mapped[str] = mapped_column(String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str | None] = mapped_column(String(100))
    personality: Mapped[str | None] = mapped_column(Text)
    goals: Mapped[Any] = mapped_column(JSON, default=list)
    relationships: Mapped[Any] = mapped_column(JSON, default=dict)
    current_state: Mapped[str | None] = mapped_column(Text)
    important_facts: Mapped[Any] = mapped_column(JSON, default=list)
    character_arc: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default=CharacterStatus.ALIVE)
    first_appeared: Mapped[int | None] = mapped_column(Integer)
    last_updated_episode: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    story: Mapped[Story] = relationship("Story", back_populates="characters")

    __table_args__ = (
        UniqueConstraint("story_id", "name", name="uq_story_character"),
        Index("ix_characters_story", "story_id"),
    )


# ─────────────────────────────────────────────
# World Facts
# ─────────────────────────────────────────────

class WorldFact(Base):
    __tablename__ = "world_facts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    story_id: Mapped[str] = mapped_column(String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(300), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    episode_introduced: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    story: Mapped[Story] = relationship("Story", back_populates="world_facts")

    __table_args__ = (Index("ix_world_facts_story_category", "story_id", "category"),)


# ─────────────────────────────────────────────
# Open Threads
# ─────────────────────────────────────────────

class OpenThread(Base):
    __tablename__ = "open_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    story_id: Mapped[str] = mapped_column(String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    thread_type: Mapped[str] = mapped_column(String(50), default=ThreadType.OTHER)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    episode_introduced: Mapped[int] = mapped_column(Integer, nullable=False)
    episode_resolved: Mapped[int | None] = mapped_column(Integer)
    planned_resolution: Mapped[str | None] = mapped_column(Text)
    planned_resolution_episode: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default=ThreadStatus.OPEN)
    importance: Mapped[str] = mapped_column(String(20), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    story: Mapped[Story] = relationship("Story", back_populates="open_threads")

    __table_args__ = (Index("ix_open_threads_story_status", "story_id", "status"),)


# ─────────────────────────────────────────────
# Human Feedback
# ─────────────────────────────────────────────

class HumanFeedback(Base):
    __tablename__ = "human_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    story_id: Mapped[str] = mapped_column(String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    episode_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("episodes.id", ondelete="SET NULL"))
    after_episode: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    instruction: Mapped[str | None] = mapped_column(Text)
    edited_content: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    story: Mapped[Story] = relationship("Story", back_populates="human_feedback")

    __table_args__ = (Index("ix_human_feedback_story_active", "story_id", "is_active"),)


# ─────────────────────────────────────────────
# Memory Summaries
# ─────────────────────────────────────────────

class MemorySummary(Base):
    __tablename__ = "memory_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    story_id: Mapped[str] = mapped_column(String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    summary_type: Mapped[str] = mapped_column(String(50))
    episode_start: Mapped[int | None] = mapped_column(Integer)
    episode_end: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    story: Mapped[Story] = relationship("Story", back_populates="memory_summaries")

    __table_args__ = (Index("ix_memory_summaries_story_type", "story_id", "summary_type"),)


# ─────────────────────────────────────────────
# Agent Runs
# ─────────────────────────────────────────────

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(String(36), default=new_uuid)
    story_id: Mapped[str] = mapped_column(String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    episode_number: Mapped[int | None] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default=AgentRunStatus.SUCCESS)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[Any] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    story: Mapped[Story] = relationship("Story", back_populates="agent_runs")

    __table_args__ = (
        Index("ix_agent_runs_story_episode", "story_id", "episode_number"),
        Index("ix_agent_runs_run_id", "run_id"),
    )
