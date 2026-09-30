"""Tests for story creation and persistence."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db.models import Story, StoryStatus
from app.db.repositories import StorySyncRepo, EpisodeSyncRepo, PlanSyncRepo


class TestStoryCreation:
    def test_create_story_basic(self, db: Session):
        """Story can be created with a premise."""
        story = Story(
            id=str(uuid.uuid4()),
            premise="A rider finds all recipients are dead.",
            status=StoryStatus.CREATED,
            current_episode=0,
            total_planned=200,
        )
        db.add(story)
        db.commit()
        assert story.id is not None
        assert story.premise == "A rider finds all recipients are dead."
        assert story.status == StoryStatus.CREATED

    def test_story_default_values(self, db: Session):
        """Verify defaults are correct."""
        story = Story(
            id=str(uuid.uuid4()),
            premise="Test premise",
        )
        db.add(story)
        db.commit()
        assert story.current_episode == 0
        assert story.total_planned == 200
        assert story.title is None

    def test_story_repo_get(self, db: Session, sample_story: Story):
        """StoryRepo can retrieve a story by ID."""
        repo = StorySyncRepo(db)
        retrieved = repo.get(sample_story.id)
        assert retrieved is not None
        assert retrieved.id == sample_story.id
        assert retrieved.premise == sample_story.premise

    def test_story_repo_list(self, db: Session, sample_story: Story):
        """StoryRepo lists all stories."""
        repo = StorySyncRepo(db)
        stories = repo.list_all()
        assert len(stories) >= 1
        ids = [s.id for s in stories]
        assert sample_story.id in ids

    def test_story_repo_update(self, db: Session, sample_story: Story):
        """StoryRepo can update story fields."""
        repo = StorySyncRepo(db)
        repo.update(sample_story.id, title="The Dead Route", genre="Mystery")
        updated = repo.get(sample_story.id)
        assert updated.title == "The Dead Route"
        assert updated.genre == "Mystery"

    def test_story_status_transitions(self, db: Session, sample_story: Story):
        """Story status transitions work correctly."""
        repo = StorySyncRepo(db)
        repo.update(sample_story.id, status=StoryStatus.PLANNING)
        assert repo.get(sample_story.id).status == StoryStatus.PLANNING
        repo.update(sample_story.id, status=StoryStatus.PLAN_PENDING_REVIEW)
        assert repo.get(sample_story.id).status == StoryStatus.PLAN_PENDING_REVIEW
        repo.update(sample_story.id, status=StoryStatus.ACTIVE)
        assert repo.get(sample_story.id).status == StoryStatus.ACTIVE
