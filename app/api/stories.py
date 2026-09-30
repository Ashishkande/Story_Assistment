"""FastAPI router for story endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.services.story_service import StoryService
from app.schemas.models import (
    StoryCreate, PlanEdit, EpisodeEdit, EpisodeReject, EpisodeFeedback,
    FeedbackCreate, ReconcileRequest,
)

router = APIRouter(prefix="/stories", tags=["stories"])


def get_service(db: AsyncSession = Depends(get_async_session)) -> StoryService:
    return StoryService(db)


# ─── Story CRUD ──────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_story(body: StoryCreate, svc: StoryService = Depends(get_service)):
    """Create a new story from a one-line premise."""
    return await svc.create_story(body.premise)


@router.get("")
async def list_stories(svc: StoryService = Depends(get_service)):
    """List all stories."""
    return await svc.list_stories()


@router.get("/{story_id}")
async def get_story(story_id: str, svc: StoryService = Depends(get_service)):
    """Get story state."""
    story = await svc.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


# ─── Plan ────────────────────────────────────────────────

@router.post("/{story_id}/plan")
async def generate_plan(story_id: str, svc: StoryService = Depends(get_service)):
    """Generate the 200-episode arc plan."""
    try:
        return await svc.generate_plan(story_id)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{story_id}/plan")
async def get_plan(story_id: str, svc: StoryService = Depends(get_service)):
    """Get the story plan."""
    plan = await svc.get_plan(story_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.put("/{story_id}/plan")
async def update_plan(story_id: str, body: PlanEdit, svc: StoryService = Depends(get_service)):
    """Edit the story plan."""
    try:
        await svc.update_plan(story_id, body.model_dump(exclude_none=True))
        return {"status": "updated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{story_id}/plan/approve")
async def approve_plan(story_id: str, svc: StoryService = Depends(get_service)):
    """Approve the plan and begin episode generation."""
    await svc.approve_plan(story_id)
    return {"status": "plan approved", "next": "POST /stories/{story_id}/episodes/next"}


# ─── Episodes ────────────────────────────────────────────

@router.post("/{story_id}/episodes/next")
@router.post("/{story_id}/episodes/generate")
async def generate_next_episode(story_id: str, svc: StoryService = Depends(get_service)):
    """Generate the next episode (sequential)."""
    try:
        return await svc.generate_next_episode(story_id)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{story_id}/episodes")
async def list_episodes(story_id: str, svc: StoryService = Depends(get_service)):
    """List all episodes with their status."""
    return await svc.list_episodes(story_id)


@router.get("/{story_id}/episodes/{episode_number}")
async def get_episode(story_id: str, episode_number: int, svc: StoryService = Depends(get_service)):
    """Get a specific episode."""
    ep = await svc.get_episode(story_id, episode_number)
    if not ep:
        raise HTTPException(status_code=404, detail=f"Episode {episode_number} not found")
    return ep


@router.post("/{story_id}/episodes/{episode_number}/approve")
async def approve_episode(story_id: str, episode_number: int, svc: StoryService = Depends(get_service)):
    """Approve an episode (updates memory and advances story)."""
    try:
        return await svc.approve_episode(story_id, episode_number)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{story_id}/episodes/{episode_number}")
async def edit_episode(
    story_id: str, episode_number: int,
    body: EpisodeEdit,
    svc: StoryService = Depends(get_service)
):
    """Human edits an episode (saved + marks future episodes potentially stale)."""
    try:
        return await svc.edit_episode(story_id, episode_number, body.content, body.edit_notes or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{story_id}/episodes/{episode_number}/reject")
async def reject_episode(
    story_id: str, episode_number: int,
    body: EpisodeReject,
    svc: StoryService = Depends(get_service)
):
    """Reject an episode (will be regenerated on next call)."""
    try:
        return await svc.reject_episode(story_id, episode_number, body.reason)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{story_id}/episodes/{episode_number}/feedback")
async def add_feedback(
    story_id: str, episode_number: int,
    body: EpisodeFeedback,
    svc: StoryService = Depends(get_service)
):
    """Submit persistent human feedback/instruction for future episodes."""
    return await svc.add_feedback(story_id, episode_number, body.instruction)


# ─── Memory & Logs ───────────────────────────────────────

@router.get("/{story_id}/memory")
async def get_memory(story_id: str, svc: StoryService = Depends(get_service)):
    """View current story memory state."""
    return await svc.get_memory(story_id)


@router.post("/{story_id}/feedback", status_code=status.HTTP_201_CREATED)
async def create_story_feedback(
    story_id: str,
    body: FeedbackCreate,
    svc: StoryService = Depends(get_service),
):
    """Store a persistent instruction that applies to later episodes."""
    story = await svc.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return await svc.add_feedback(story_id, body.episode, body.instruction)


@router.get("/{story_id}/feedback")
async def list_story_feedback(story_id: str, svc: StoryService = Depends(get_service)):
    """List human feedback and persistent instructions for a story."""
    story = await svc.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return await svc.list_feedback(story_id)


@router.post("/{story_id}/reconcile")
async def reconcile_story(story_id: str, body: ReconcileRequest, svc: StoryService = Depends(get_service)):
    """Mark later episodes stale after a retroactive edit and resume from that episode."""
    try:
        return await svc.reconcile_from(story_id, body.from_episode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{story_id}/resume")
async def resume_story(story_id: str, svc: StoryService = Depends(get_service)):
    """Return the last approved episode and the next episode to generate."""
    try:
        return await svc.resume_point(story_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{story_id}/logs")
async def get_logs(
    story_id: str,
    limit: int = 100,
    svc: StoryService = Depends(get_service)
):
    """View agent execution logs with cost and token totals."""
    story = await svc.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    runs = await svc.get_logs(story_id, limit=limit)
    input_tokens = sum(run.get("input_tokens") or 0 for run in runs)
    output_tokens = sum(run.get("output_tokens") or 0 for run in runs)
    latencies = [run.get("latency_ms") or 0 for run in runs if run.get("latency_ms") is not None]
    return {
        "runs": runs,
        "summary": {
            "total_cost": sum(run.get("cost") or 0.0 for run in runs),
            "total_input_tokens": input_tokens,
            "total_output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "total_runs": len(runs),
            "average_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
        },
    }
