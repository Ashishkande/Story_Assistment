"""Dashboard, demo, and long-running operation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.models import DemoRequest, OperationCreate
from app.services.operations import get_job, start_operation
from app.services.story_service import StoryService

router = APIRouter(tags=["platform"])


def get_service(db: AsyncSession = Depends(get_async_session)) -> StoryService:
    return StoryService(db)


@router.get("/dashboard")
async def dashboard(svc: StoryService = Depends(get_service)):
    """Aggregate counts for the web dashboard."""
    return await svc.dashboard()


@router.post("/demo", status_code=status.HTTP_202_ACCEPTED)
async def start_demo(body: DemoRequest):
    """Start the CLI demo workflow in the background."""

    async def runner(service: StoryService, report):
        return await service.run_demo(body.premise, body.episodes, progress=report)

    try:
        return start_operation("demo", None, runner)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/operations", status_code=status.HTTP_202_ACCEPTED)
async def create_operation(body: OperationCreate):
    """Queue plan generation, the next episode, or the automated demo."""
    kind = body.type.strip().lower()
    if kind not in {"plan", "episode", "demo"}:
        raise HTTPException(status_code=422, detail="type must be plan, episode, or demo")
    if kind in {"plan", "episode"} and not body.story_id:
        raise HTTPException(status_code=422, detail="story_id is required")

    async def runner(service: StoryService, report):
        if kind == "plan":
            report("Generating 200-episode plan...")
            return await service.generate_plan(body.story_id)
        if kind == "episode":
            report("Generating episode...")
            return await service.generate_next_episode(body.story_id)
        report("Starting demo...")
        premise = body.premise or (
            "A delivery rider realizes every address on today's route belongs to someone who died in the same building."
        )
        return await service.run_demo(premise, body.episodes, progress=report)

    try:
        return start_operation(kind, body.story_id if kind != "demo" else None, runner)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/operations/{operation_id}")
async def read_operation(operation_id: str):
    """Poll a background generation job."""
    job = get_job(operation_id)
    if not job:
        raise HTTPException(status_code=404, detail="Operation not found")
    return job
