"""Context Builder – assembles layered memory context before episode generation.

This is the key component that makes the system scale to Episode 150+
without putting all previous episodes in the prompt.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from app.db.models import (
    Episode, Character, WorldFact, OpenThread,
    HumanFeedback, MemorySummary, StoryPlan,
)

from app.agents.guards import parse_word_limits
from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class EpisodeContext:
    """Structured context package passed to the episode writer."""
    story_id: str
    episode_number: int

    # Current episode plan
    episode_plan: dict = field(default_factory=dict)

    # Arc info
    current_arc: dict = field(default_factory=dict)
    upcoming_arc_events: list[str] = field(default_factory=list)

    # Short-term: recent episodes (last 3)
    recent_episode_summaries: list[dict] = field(default_factory=list)

    # Medium-term: rolling summary
    rolling_summary: str = ""

    # Long-term: structured memory
    relevant_characters: list[dict] = field(default_factory=list)
    relevant_world_facts: list[dict] = field(default_factory=list)
    open_threads: list[dict] = field(default_factory=list)

    # Human instructions (persistent)
    active_instructions: list[str] = field(default_factory=list)

    # Compact plot index (last ~24 approved one-liners) for long-range repetition
    plot_beats: list[str] = field(default_factory=list)

    min_words: int = 400
    max_words: int = 700

    # Story metadata
    story_title: str = ""
    premise: str = ""
    genre: str = ""
    tone: str = ""

    def to_prompt_text(self) -> str:
        """Format this context into a concise, structured prompt section."""
        parts = []

        parts.append(f"=== STORY: {self.story_title} ===")
        parts.append(f"Premise: {self.premise}")
        parts.append(f"Genre/Tone: {self.genre} / {self.tone}")
        parts.append(f"WORD COUNT TARGET: {self.min_words}–{self.max_words} words of prose. Do not exceed {self.max_words}.")
        parts.append("")

        if self.current_arc:
            parts.append(f"=== CURRENT ARC: {self.current_arc.get('title', '')} ===")
            parts.append(self.current_arc.get("summary", ""))
            if self.upcoming_arc_events:
                parts.append("Upcoming planned events in this arc:")
                for evt in self.upcoming_arc_events[:3]:
                    parts.append(f"  - {evt}")
            parts.append("")

        parts.append(f"=== EPISODE {self.episode_number} PLAN ===")
        ep = self.episode_plan
        parts.append(f"Title: {ep.get('title', 'Unknown')}")
        parts.append(f"Summary: {ep.get('summary', '')}")
        if ep.get("major_events"):
            parts.append(f"Key events: {', '.join(ep['major_events'])}")
        parts.append(f"Planned hook: {ep.get('planned_hook', '')}")
        parts.append(f"Characters involved: {', '.join(ep.get('characters_involved', []))}")
        if ep.get("threads_resolved"):
            parts.append(f"Threads to resolve: {', '.join(ep['threads_resolved'])}")
        parts.append("")

        if self.rolling_summary:
            parts.append("=== RECENT STORY STATE ===")
            parts.append(self.rolling_summary)
            parts.append("")

        if self.recent_episode_summaries:
            parts.append("=== RECENT EPISODES ===")
            for ep_sum in self.recent_episode_summaries:
                parts.append(f"Episode {ep_sum.get('episode_number')}: {ep_sum.get('summary', '')}")
                if ep_sum.get("hook"):
                    parts.append(f"  Hook: {ep_sum['hook']}")
            parts.append("")

        if self.relevant_characters:
            parts.append("=== KEY CHARACTERS ===")
            for char in self.relevant_characters:
                parts.append(f"• {char['name']} ({char.get('role', '')}): {char.get('current_state', '')}")
                if char.get("important_facts"):
                    for fact in char["important_facts"][:3]:
                        parts.append(f"  - {fact}")
                if char.get("relationships"):
                    rel_str = "; ".join(f"{k}: {v}" for k, v in list(char["relationships"].items())[:3])
                    parts.append(f"  Relationships: {rel_str}")
            parts.append("")

        if self.relevant_world_facts:
            parts.append("=== WORLD FACTS ===")
            for fact in self.relevant_world_facts[:10]:
                parts.append(f"• [{fact.get('category', 'fact')}] {fact['key']}: {fact['value']}")
            parts.append("")

        if self.plot_beats:
            parts.append("=== PRIOR PLOT BEATS (do not repeat) ===")
            for beat in self.plot_beats[-24:]:
                parts.append(f"• {beat}")
            parts.append("")

        if self.open_threads:
            parts.append("=== OPEN STORY THREADS ===")
            for thread in self.open_threads[:8]:
                importance = thread.get("importance", "medium")
                parts.append(
                    f"• [{importance.upper()}] {thread['title']}: {thread['description']}"
                )
                if thread.get("planned_resolution"):
                    parts.append(f"  → Planned resolution: {thread['planned_resolution']}")
            parts.append("")

        if self.active_instructions:
            parts.append("=== HUMAN INSTRUCTIONS (MUST FOLLOW) ===")
            for instr in self.active_instructions:
                parts.append(f"• {instr}")
            parts.append("")

        return "\n".join(parts)


class ContextBuilder:
    """
    Builds a compact EpisodeContext for episode generation.

    Strategy:
    - Episode plan: from story_plan.episode_plans[N]
    - Arc info: from story_plan.arc_structure
    - Recent summaries: last 3 approved episodes (short-term memory)
    - Rolling summary: maintained rolling summary (medium-term memory)
    - Characters: all characters with recent state (long-term memory)
    - World facts: all active facts (long-term memory)
    - Open threads: all open threads (long-term memory)
    - Human instructions: all active instructions
    """

    def build(
        self,
        *,
        story_id: str,
        episode_number: int,
        story_title: str,
        premise: str,
        genre: str = "",
        tone: str = "",
        episode_plans: list[dict],
        arc_structure: dict,
        recent_episodes: list[Episode],
        rolling_summary: Optional[MemorySummary],
        characters: list[Character],
        world_facts: list[WorldFact],
        open_threads: list[OpenThread],
        active_instructions: list[HumanFeedback],
    ) -> EpisodeContext:

        ctx = EpisodeContext(
            story_id=story_id,
            episode_number=episode_number,
            story_title=story_title,
            premise=premise,
            genre=genre,
            tone=tone,
        )

        # Episode plan
        ep_plans_by_num = {ep.get("episode_number"): ep for ep in episode_plans}
        ctx.episode_plan = ep_plans_by_num.get(episode_number, {"episode_number": episode_number})

        # Arc info – find which arc this episode belongs to
        arc_num = ctx.episode_plan.get("arc_number", 1)
        arc_key = str(arc_num)
        if arc_key in arc_structure:
            ctx.current_arc = arc_structure[arc_key]
        elif isinstance(arc_structure, dict):
            # Try numeric key
            for arc in arc_structure.values():
                if isinstance(arc, dict):
                    start = arc.get("episode_start", 0)
                    end = arc.get("episode_end", 9999)
                    if start <= episode_number <= end:
                        ctx.current_arc = arc
                        break

        # Upcoming arc events (next 2 episodes in the same arc)
        upcoming = []
        for ep_n in [episode_number + 1, episode_number + 2]:
            ep_plan = ep_plans_by_num.get(ep_n)
            if ep_plan:
                upcoming.append(ep_plan.get("summary", ""))
        ctx.upcoming_arc_events = [u for u in upcoming if u]

        # Recent episode summaries (last 3, short-term)
        recent_sorted = sorted(recent_episodes, key=lambda e: e.episode_number, reverse=True)[:3]
        ctx.recent_episode_summaries = [
            {
                "episode_number": ep.episode_number,
                "summary": ep.summary or "",
                "hook": ep.hook or "",
            }
            for ep in reversed(recent_sorted)
        ]
        ctx.plot_beats = [
            f"Ep {ep.episode_number}: {' '.join(((ep.summary or ep.hook or '')).split()[:24])}"
            for ep in sorted(recent_episodes, key=lambda e: e.episode_number)
            if (ep.summary or ep.hook)
        ]

        # Rolling summary (medium-term)
        ctx.rolling_summary = rolling_summary.content if rolling_summary else ""

        # Characters – include all (long-term memory)
        ctx.relevant_characters = [
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
            }
            for c in characters
        ]

        # World facts (long-term memory)
        ctx.relevant_world_facts = [
            {"category": f.category, "key": f.key, "value": f.value}
            for f in world_facts
        ]

        # Open threads (long-term memory)
        ctx.open_threads = [
            {
                "title": t.title,
                "description": t.description,
                "thread_type": t.thread_type,
                "importance": t.importance,
                "episode_introduced": t.episode_introduced,
                "planned_resolution": t.planned_resolution,
            }
            for t in open_threads
        ]

        # Human instructions
        ctx.active_instructions = [
            fb.instruction for fb in active_instructions
            if fb.instruction and fb.instruction.strip().lower() not in {"generate the context", "generate context"}
        ]
        settings = get_settings()
        ctx.min_words, ctx.max_words = parse_word_limits(
            ctx.active_instructions,
            settings.episode_min_words,
            settings.episode_max_words,
        )

        logger.debug(
            f"[ContextBuilder] Episode {episode_number}: "
            f"chars={len(ctx.relevant_characters)} "
            f"facts={len(ctx.relevant_world_facts)} "
            f"threads={len(ctx.open_threads)} "
            f"instructions={len(ctx.active_instructions)}"
        )

        return ctx
