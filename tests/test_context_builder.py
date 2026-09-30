"""Tests for context builder and memory architecture."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.agents.context_builder import ContextBuilder, EpisodeContext
from app.db.models import (
    Episode, Character, WorldFact, OpenThread, HumanFeedback,
    EpisodeStatus,
)


def _make_episode(ep_num: int, summary: str = "", hook: str = "") -> Episode:
    ep = Episode()
    ep.id = str(uuid.uuid4())
    ep.episode_number = ep_num
    ep.summary = summary or f"Summary of episode {ep_num}"
    ep.hook = hook or f"Hook for episode {ep_num}"
    ep.status = EpisodeStatus.APPROVED
    ep.characters_present = []
    ep.facts_introduced = []
    ep.threads_opened = []
    ep.threads_resolved = []
    return ep


def _make_character(name: str, role: str = "supporting", state: str = "active") -> Character:
    char = Character()
    char.name = name
    char.role = role
    char.personality = "Determined"
    char.goals = ["Survive"]
    char.relationships = {}
    char.current_state = state
    char.important_facts = [f"{name} fact 1"]
    char.character_arc = "Growth arc"
    char.status = "alive"
    return char


def _make_thread(title: str, importance: str = "medium", ep: int = 1) -> OpenThread:
    thread = OpenThread()
    thread.id = str(uuid.uuid4())
    thread.title = title
    thread.description = f"Description of {title}"
    thread.thread_type = "mystery"
    thread.importance = importance
    thread.episode_introduced = ep
    thread.planned_resolution = "TBD"
    return thread


def _make_instruction(text: str, after_ep: int = 3) -> HumanFeedback:
    fb = HumanFeedback()
    fb.instruction = text
    fb.after_episode = after_ep
    fb.is_active = True
    return fb


class TestContextBuilder:
    def test_context_includes_episode_plan(self):
        builder = ContextBuilder()
        episode_plans = [
            {"episode_number": 5, "title": "Dark Revelation", "summary": "Something big happens.",
             "planned_hook": "Big cliffhanger", "arc_number": 1}
        ]
        ctx = builder.build(
            story_id="s1", episode_number=5,
            story_title="The Dead Route", premise="A rider...",
            genre="Mystery", tone="Dark",
            episode_plans=episode_plans, arc_structure={},
            recent_episodes=[], rolling_summary=None,
            characters=[], world_facts=[], open_threads=[],
            active_instructions=[],
        )
        assert ctx.episode_plan["title"] == "Dark Revelation"
        assert ctx.episode_plan["planned_hook"] == "Big cliffhanger"

    def test_context_includes_recent_episodes(self):
        builder = ContextBuilder()
        recent = [_make_episode(i, f"Summary {i}") for i in [3, 4]]
        ctx = builder.build(
            story_id="s1", episode_number=5,
            story_title="T", premise="P",
            episode_plans=[], arc_structure={},
            recent_episodes=recent, rolling_summary=None,
            characters=[], world_facts=[], open_threads=[],
            active_instructions=[],
        )
        assert len(ctx.recent_episode_summaries) == 2
        ep_nums = [e["episode_number"] for e in ctx.recent_episode_summaries]
        assert 3 in ep_nums
        assert 4 in ep_nums

    def test_context_capped_at_3_recent_episodes(self):
        """Only last 3 episodes are included for short-term memory."""
        builder = ContextBuilder()
        # Give it 10 approved episodes
        recent = [_make_episode(i) for i in range(1, 11)]
        ctx = builder.build(
            story_id="s1", episode_number=11,
            story_title="T", premise="P",
            episode_plans=[], arc_structure={},
            recent_episodes=recent, rolling_summary=None,
            characters=[], world_facts=[], open_threads=[],
            active_instructions=[],
        )
        assert len(ctx.recent_episode_summaries) <= 3

    def test_context_includes_characters(self):
        builder = ContextBuilder()
        chars = [_make_character("Arjun"), _make_character("Maya")]
        ctx = builder.build(
            story_id="s1", episode_number=10,
            story_title="T", premise="P",
            episode_plans=[], arc_structure={},
            recent_episodes=[], rolling_summary=None,
            characters=chars, world_facts=[], open_threads=[],
            active_instructions=[],
        )
        names = [c["name"] for c in ctx.relevant_characters]
        assert "Arjun" in names
        assert "Maya" in names

    def test_context_includes_open_threads(self):
        builder = ContextBuilder()
        threads = [_make_thread("Who sent the packages", "critical")]
        ctx = builder.build(
            story_id="s1", episode_number=10,
            story_title="T", premise="P",
            episode_plans=[], arc_structure={},
            recent_episodes=[], rolling_summary=None,
            characters=[], world_facts=[], open_threads=threads,
            active_instructions=[],
        )
        assert len(ctx.open_threads) == 1
        assert ctx.open_threads[0]["title"] == "Who sent the packages"

    def test_context_includes_human_instructions(self):
        builder = ContextBuilder()
        instructions = [
            _make_instruction("Do not reveal the killer yet."),
            _make_instruction("Add a skeptical detective."),
        ]
        ctx = builder.build(
            story_id="s1", episode_number=10,
            story_title="T", premise="P",
            episode_plans=[], arc_structure={},
            recent_episodes=[], rolling_summary=None,
            characters=[], world_facts=[], open_threads=[],
            active_instructions=instructions,
        )
        assert len(ctx.active_instructions) == 2
        assert "killer" in ctx.active_instructions[0]
        assert "detective" in ctx.active_instructions[1]

    def test_context_to_prompt_text_contains_key_sections(self):
        builder = ContextBuilder()
        threads = [_make_thread("Mystery Thread", "high")]
        chars = [_make_character("Arjun", "protagonist")]
        instructions = [_make_instruction("Keep the tone dark.")]

        ctx = builder.build(
            story_id="s1", episode_number=10,
            story_title="The Dead Route", premise="A rider discovers...",
            genre="Mystery", tone="Dark Thriller",
            episode_plans=[{"episode_number": 10, "title": "Ep 10", "summary": "Revelation",
                           "planned_hook": "The truth emerges", "arc_number": 1}],
            arc_structure={},
            recent_episodes=[_make_episode(9, "Previous events")],
            rolling_summary=None,
            characters=chars, world_facts=[], open_threads=threads,
            active_instructions=instructions,
        )
        prompt = ctx.to_prompt_text()

        assert "The Dead Route" in prompt
        assert "EPISODE 10 PLAN" in prompt
        assert "OPEN STORY THREADS" in prompt
        assert "Mystery Thread" in prompt
        assert "HUMAN INSTRUCTIONS" in prompt
        assert "Keep the tone dark." in prompt
        assert "Arjun" in prompt

    def test_context_does_not_include_all_episodes(self):
        """Context builder NEVER includes all episode content — only summaries."""
        builder = ContextBuilder()
        # Simulate 100 approved episodes, but only 3 should appear
        recent = [_make_episode(i, f"Content of episode {i}") for i in range(1, 101)]
        ctx = builder.build(
            story_id="s1", episode_number=101,
            story_title="T", premise="P",
            episode_plans=[], arc_structure={},
            recent_episodes=recent,  # builder should cap this
            rolling_summary=None,
            characters=[], world_facts=[], open_threads=[],
            active_instructions=[],
        )
        # Only 3 recent summaries, not 100
        assert len(ctx.recent_episode_summaries) <= 3
        # Verify it's the most recent ones
        ep_nums = [e["episode_number"] for e in ctx.recent_episode_summaries]
        assert all(n >= 98 for n in ep_nums)
