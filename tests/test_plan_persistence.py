"""Tests for 200-episode plan generation and persistence."""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.db.models import Story, StoryPlan, StoryStatus
from app.db.repositories import PlanSyncRepo
from app.agents.planner import PlannerAgent, parse_json_from_response
from tests.conftest import MOCK_PLAN_RESPONSE


class TestPlanParsing:
    def test_parse_json_from_clean_response(self):
        """parse_json_from_response handles plain JSON."""
        data = {"title": "Test", "episodes": []}
        result = parse_json_from_response(json.dumps(data))
        assert result["title"] == "Test"

    def test_parse_json_from_markdown_block(self):
        """parse_json_from_response handles ```json...``` blocks."""
        data = {"title": "Test Story", "episodes": [{"episode_number": 1}]}
        response = f"Here is the plan:\n```json\n{json.dumps(data)}\n```"
        result = parse_json_from_response(response)
        assert result["title"] == "Test Story"

    def test_parse_json_invalid_raises(self):
        """parse_json_from_response raises ValueError for invalid JSON."""
        with pytest.raises(ValueError):
            parse_json_from_response("This is not JSON at all.")

    def test_parse_json_from_unclosed_markdown_fence(self):
        """A finished object inside an unclosed ```json fence still parses."""
        data = {"title": "Deliveries from Beyond", "goals": ["Uncover the mystery"]}
        response = f"```json\n{json.dumps(data)}\n"
        result = parse_json_from_response(response)
        assert result["title"] == "Deliveries from Beyond"

    def test_parse_truncated_fence_explains_failure(self):
        """Truncated fenced JSON reports truncation instead of a bare char-0 error."""
        response = (
            '```json\n{\n  "title": "Deliveries from Beyond",\n'
            '  "goals": ["Uncover the mystery behind the addresse'
        )
        with pytest.raises(ValueError, match="truncated or wrapped"):
            parse_json_from_response(response)


class TestPlannerAgent:
    def test_planner_generates_plan(self):
        """PlannerAgent calls LLM and returns structured plan."""
        mock_runner = MagicMock()
        mock_runner.invoke.return_value = (json.dumps(MOCK_PLAN_RESPONSE), {
            "input_tokens": 1000, "output_tokens": 5000, "cost": 0.01, "latency_ms": 5000, "model": "gpt-4o-mini"
        })

        planner = PlannerAgent(runner=mock_runner)
        plan_data, meta = planner.generate_plan("story-123", "A rider discovers all recipients are dead.")

        assert plan_data["title"] == "The Dead Route"
        assert len(plan_data["episodes"]) == 200
        assert len(plan_data["arcs"]) >= 1
        assert len(plan_data["characters"]) >= 1
        assert meta["cost"] == 0.01

    def test_planner_generates_episodes_in_batches_when_outline_has_none(self):
        """A complete outline without episodes is filled in bounded batches."""
        outline = {
            "title": "The Dead Route",
            "premise": "A rider discovers all recipients are dead.",
            "genre": "Mystery Thriller",
            "tone": "Dark",
            "characters": MOCK_PLAN_RESPONSE["characters"],
            "world_rules": ["Building 7 is the epicenter"],
            "major_turning_points": ["The pattern is confirmed"],
            "planned_resolutions": ["The truth is revealed"],
            "arcs": [
                {
                    "arc_number": 1,
                    "title": "The Pattern",
                    "episode_start": 1,
                    "episode_end": 2,
                    "summary": "The rider notices the pattern.",
                    "major_themes": ["death"],
                    "turning_point": "Both addresses are dead.",
                }
            ],
        }

        def episode(number: int) -> dict:
            return {
                "episode_number": number,
                "title": f"Chapter {number}",
                "summary": f"Events of episode {number}.",
                "major_events": [f"Event {number}"],
                "characters_involved": ["Arjun Sharma"],
                "threads_opened": [],
                "threads_resolved": [],
                "planned_hook": f"Hook {number}",
                "arc_number": 1,
            }

        mock_runner = MagicMock()
        mock_runner.invoke.side_effect = [
            (json.dumps(outline), {"input_tokens": 10, "output_tokens": 20, "cost": 0.01, "latency_ms": 5, "model": "gpt-4o-mini"}),
            (json.dumps({"episodes": [episode(1), episode(2)]}), {"input_tokens": 10, "output_tokens": 20, "cost": 0.02, "latency_ms": 5, "model": "gpt-4o-mini"}),
        ]
        planner = PlannerAgent(runner=mock_runner)
        planner.settings = planner.settings.model_copy(update={"total_episodes": 2})

        plan_data, meta = planner.generate_plan("story-123", outline["premise"])

        assert mock_runner.invoke.call_count == 2
        assert [ep["episode_number"] for ep in plan_data["episodes"]] == [1, 2]
        assert meta["cost"] == pytest.approx(0.03)
        first_prompt = mock_runner.invoke.call_args_list[0].args[0][1].content
        assert "Do NOT include a per-episode list" in first_prompt

    def test_planner_validates_required_fields(self):
        """PlannerAgent raises if plan missing required fields."""
        mock_runner = MagicMock()
        mock_runner.invoke.return_value = (json.dumps({"title": "Test"}), {})

        planner = PlannerAgent(runner=mock_runner)
        with pytest.raises(ValueError, match="missing required field"):
            planner.generate_plan("story-123", "A premise.")


class TestPlanPersistence:
    def test_plan_created_in_db(self, db: Session, sample_story: Story):
        """Plan can be created and retrieved from DB."""
        repo = PlanSyncRepo(db)
        plan = repo.create_or_replace(sample_story.id, {
            "arc_structure": {"1": {"title": "Arc 1", "episode_start": 1, "episode_end": 20}},
            "episode_plans": [{"episode_number": 1, "title": "Ep 1"}],
            "world_rules": ["Rule 1"],
            "major_turning_points": ["Turning point 1"],
            "planned_resolutions": ["Resolution 1"],
        })
        assert plan.id is not None
        assert plan.story_id == sample_story.id
        assert plan.approved is False

    def test_plan_approval(self, db: Session, sample_story: Story):
        """Plan can be approved."""
        repo = PlanSyncRepo(db)
        repo.create_or_replace(sample_story.id, {
            "arc_structure": {}, "episode_plans": [], "world_rules": [],
            "major_turning_points": [], "planned_resolutions": [],
        })
        repo.approve(sample_story.id)
        plan = repo.get(sample_story.id)
        assert plan.approved is True

    def test_plan_upsert_increments_version(self, db: Session, sample_story: Story):
        """Upserting a plan increments the version."""
        repo = PlanSyncRepo(db)
        repo.create_or_replace(sample_story.id, {
            "arc_structure": {}, "episode_plans": [], "world_rules": [],
            "major_turning_points": [], "planned_resolutions": [],
        })
        plan_v1 = repo.get(sample_story.id)
        assert plan_v1.version == 1

        repo.create_or_replace(sample_story.id, {"world_rules": ["New rule"]})
        plan_v2 = repo.get(sample_story.id)
        assert plan_v2.version == 2

    def test_plan_stores_200_episodes(self, db: Session, sample_story: Story, approved_plan: StoryPlan):
        """Plan stores all 200 episode plans."""
        repo = PlanSyncRepo(db)
        plan = repo.get(sample_story.id)
        assert len(plan.episode_plans) == 200
        ep_numbers = [ep["episode_number"] for ep in plan.episode_plans]
        assert 1 in ep_numbers
        assert 200 in ep_numbers
