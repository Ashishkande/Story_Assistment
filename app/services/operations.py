"""In-process job tracker for long-running plan, episode, and demo work."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from app.db.session import AsyncSessionLocal
from app.services.story_service import StoryService

logger = logging.getLogger(__name__)

_jobs: dict[str, dict[str, Any]] = {}
_story_locks: set[str] = set()


def get_job(job_id: str) -> dict[str, Any] | None:
    job = _jobs.get(job_id)
    return dict(job) if job else None


def _new_job(kind: str, story_id: str | None) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "type": kind,
        "story_id": story_id,
        "status": "queued",
        "message": "Queued",
        "result": None,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def start_operation(kind: str, story_id: str | None, runner: Callable) -> dict[str, Any]:
    """Queue a background job. `runner` is async (service, report) -> result."""
    if story_id and story_id in _story_locks:
        raise RuntimeError("This story already has a generation job running")

    job = _new_job(kind, story_id)
    _jobs[job["id"]] = job
    if story_id:
        _story_locks.add(story_id)
    asyncio.create_task(_execute(job["id"], story_id, runner))
    return dict(job)


async def _execute(job_id: str, story_id: str | None, runner: Callable) -> None:
    job = _jobs[job_id]

    def report(message: str) -> None:
        job["message"] = message
        job["updated_at"] = datetime.now(timezone.utc).isoformat()

    job["status"] = "running"
    report(job["message"] if job["message"] != "Queued" else "Agent is working...")
    try:
        async with AsyncSessionLocal() as session:
            service = StoryService(session)
            job["result"] = await runner(service, report)
        job["status"] = "succeeded"
        if job["message"] == "Agent is working...":
            report("Finished")
        else:
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
    except Exception as exc:
        logger.exception("Operation %s failed", job_id)
        job["status"] = "failed"
        job["error"] = str(exc)
        job["updated_at"] = datetime.now(timezone.utc).isoformat()
    finally:
        if story_id:
            _story_locks.discard(story_id)
