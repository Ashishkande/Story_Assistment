"""Pydantic schemas for all API request/response objects."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Episode Plan (nested in StoryPlan)
# ─────────────────────────────────────────────

class EpisodePlan(BaseModel):
    episode_number: int
    title: str
    summary: str
    major_events: list[str] = []
    characters_involved: list[str] = []
    threads_opened: list[str] = []
    threads_resolved: list[str] = []
    planned_hook: str = ""
    arc_number: int = 1


class ArcPlan(BaseModel):
    arc_number: int
    title: str
    episode_start: int
    episode_end: int
    summary: str
    major_themes: list[str] = []
    turning_point: str = ""


# ─────────────────────────────────────────────
# Story Schemas
# ─────────────────────────────────────────────

class StoryCreate(BaseModel):
    premise: str = Field(..., min_length=10, max_length=2000)


class StoryRead(BaseModel):
    id: str
    title: Optional[str]
    premise: str
    genre: Optional[str]
    tone: Optional[str]
    status: str
    current_episode: int
    total_planned: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Plan Schemas
# ─────────────────────────────────────────────

class PlanRead(BaseModel):
    id: str
    story_id: str
    approved: bool
    arc_structure: dict
    episode_plans: list[EpisodePlan]
    world_rules: list[str]
    major_turning_points: list[str]
    planned_resolutions: list[str]
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanEdit(BaseModel):
    arc_structure: Optional[dict] = None
    episode_plans: Optional[list[dict]] = None
    world_rules: Optional[list[str]] = None
    major_turning_points: Optional[list[str]] = None
    planned_resolutions: Optional[list[str]] = None


# ─────────────────────────────────────────────
# Episode Schemas
# ─────────────────────────────────────────────

class CriticIssue(BaseModel):
    type: str   # timeline | character | repetition | consistency | arc | hook | feedback
    severity: str   # low | medium | high | critical
    description: str


class CriticResult(BaseModel):
    passed: bool
    score: float
    issues: list[CriticIssue] = []


class EpisodeOutput(BaseModel):
    episode_number: int
    title: str
    content: str
    summary: str
    characters_present: list[str] = []
    facts_introduced: list[str] = []
    threads_opened: list[str] = []
    threads_resolved: list[str] = []
    hook: str = ""
    word_count: int = 0


class EpisodeRead(BaseModel):
    id: str
    story_id: str
    episode_number: int
    title: Optional[str]
    content: Optional[str]
    summary: Optional[str]
    hook: Optional[str]
    status: str
    word_count: Optional[int]
    revision_count: int
    characters_present: list[str]
    facts_introduced: list[str]
    threads_opened: list[str]
    threads_resolved: list[str]
    critic_score: Optional[float]
    critic_issues: list[dict]
    critic_passed: Optional[bool]
    human_edited: bool
    rejection_reason: Optional[str]
    is_stale: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EpisodeEdit(BaseModel):
    content: str
    edit_notes: Optional[str] = None


class EpisodeReject(BaseModel):
    reason: str


class ReconcileRequest(BaseModel):
    from_episode: int = Field(..., ge=1)


class EpisodeFeedback(BaseModel):
    instruction: str = Field(..., min_length=5)


class FeedbackCreate(BaseModel):
    episode: int = Field(..., ge=0)
    instruction: str = Field(..., min_length=5)


class DemoRequest(BaseModel):
    premise: str = Field(
        default="A delivery rider realizes every address on today's route belongs to someone who died in the same building.",
        min_length=10,
        max_length=2000,
    )
    episodes: int = Field(default=15, ge=1, le=30)


class OperationCreate(BaseModel):
    type: str = Field(..., description="plan | episode | demo")
    story_id: Optional[str] = None
    premise: Optional[str] = None
    episodes: int = Field(default=15, ge=1, le=30)


# ─────────────────────────────────────────────
# Character Schemas
# ─────────────────────────────────────────────

class CharacterRead(BaseModel):
    id: str
    name: str
    role: Optional[str]
    personality: Optional[str]
    goals: list[str]
    relationships: dict
    current_state: Optional[str]
    important_facts: list[str]
    character_arc: Optional[str]
    status: str
    first_appeared: Optional[int]

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# Memory / Context Schemas
# ─────────────────────────────────────────────

class MemoryView(BaseModel):
    rolling_summary: Optional[str] = None
    characters: list[CharacterRead] = []
    world_facts: list[dict] = []
    open_threads: list[dict] = []
    active_instructions: list[str] = []
    recent_episode_summaries: list[dict] = []


# ─────────────────────────────────────────────
# AgentRun Schemas
# ─────────────────────────────────────────────

class AgentRunRead(BaseModel):
    id: str
    run_id: str
    episode_number: Optional[int]
    agent: str
    model: Optional[str]
    status: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    cost: Optional[float]
    latency_ms: Optional[int]
    retry_count: int
    decision: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
