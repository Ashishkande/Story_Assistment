"""Memory Updater Agent – updates story memory after episode approval.

Updates:
- Character state
- World facts
- Open threads (open/resolve)
- Rolling summary
- Episode compact summary
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import LLMRunner
from app.schemas.models import EpisodeOutput
from app.agents.planner import parse_json_from_response

logger = logging.getLogger(__name__)


MEMORY_UPDATER_SYSTEM = """You are a story memory manager for a serialized fiction system.
After each episode is approved, you extract structured updates to keep story memory accurate.
Return ONLY valid JSON. Be concise and precise."""


MEMORY_UPDATER_PROMPT = """After Episode {episode_number} was approved, extract memory updates.

EPISODE CONTENT:
Title: {title}
Summary: {summary}
Prose (source of truth, may be truncated):
{prose}
Characters present: {characters}
Facts introduced: {facts_introduced}
Threads opened: {threads_opened}
Threads resolved: {threads_resolved}

CURRENT CHARACTER STATES (to update):
{current_characters}

CURRENT OPEN THREADS:
{current_threads}

EXISTING ROLLING SUMMARY:
{existing_rolling}

Return this JSON:
{{
  "character_updates": [
    {{
      "name": "Character name (must match existing)",
      "current_state": "Updated current state",
      "important_facts": ["new fact to add"],
      "relationship_updates": {{"other_character_name": "updated relationship"}},
      "status": "alive|dead|missing|unknown"
    }}
  ],
  "new_world_facts": [
    {{
      "category": "location|timeline|object|rule|history|revelation",
      "key": "fact identifier",
      "value": "fact value"
    }}
  ],
  "threads_to_open": [
    {{
      "thread_type": "mystery|conflict|question|promise|foreshadowing|relationship|other",
      "title": "Short thread name",
      "description": "What this thread is about",
      "importance": "low|medium|high|critical",
      "planned_resolution": "How you expect this to resolve (if known)",
      "planned_resolution_episode": null
    }}
  ],
  "threads_to_resolve": ["Thread title to mark as resolved"],
  "new_rolling_summary": "Updated 3-5 sentence rolling summary of the story so far, ending with Episode {episode_number}"
}}"""


class MemoryUpdaterAgent:
    """Extracts and persists memory updates from approved episodes."""

    def __init__(self, runner: LLMRunner | None = None):
        self.runner = runner or LLMRunner()

    def extract_updates(
        self,
        episode: EpisodeOutput,
        current_characters: list[dict],
        current_threads: list[dict],
        existing_rolling_summary: str,
    ) -> tuple[dict, dict]:
        """
        Extract memory updates for an episode.
        Returns (updates_dict, run_metadata).
        """
        logger.info(f"[MemoryUpdater] Extracting updates for episode {episode.episode_number}")

        chars_text = "\n".join(
            f"  - {c['name']} ({c.get('status', 'alive')}): {c.get('current_state', 'Unknown')}"
            for c in current_characters[:10]
        )

        threads_text = "\n".join(
            f"  - {t.get('title', 'Unknown')}: {t.get('description', '')}"
            for t in current_threads[:10]
        )

        prose = (episode.content or "")[:4000]
        prompt = MEMORY_UPDATER_PROMPT.format(
            episode_number=episode.episode_number,
            title=episode.title,
            summary=episode.summary,
            prose=prose or "(empty)",
            characters=", ".join(episode.characters_present),
            facts_introduced="\n".join(f"  - {f}" for f in episode.facts_introduced),
            threads_opened="\n".join(f"  - {t}" for t in episode.threads_opened),
            threads_resolved="\n".join(f"  - {t}" for t in episode.threads_resolved),
            current_characters=chars_text or "None yet",
            current_threads=threads_text or "None yet",
            existing_rolling=existing_rolling_summary or "Story just beginning.",
        )

        messages = [
            SystemMessage(content=MEMORY_UPDATER_SYSTEM),
            HumanMessage(content=prompt),
        ]

        content, meta = self.runner.invoke(messages, agent_name="memory_updater")

        try:
            updates = parse_json_from_response(content)
        except Exception as e:
            logger.warning(f"[MemoryUpdater] Failed to parse updates: {e}. Using empty updates.")
            updates = {
                "character_updates": [],
                "new_world_facts": [],
                "threads_to_open": [],
                "threads_to_resolve": [],
                "new_rolling_summary": existing_rolling_summary,
            }

        logger.info(
            f"[MemoryUpdater] Updates: "
            f"chars={len(updates.get('character_updates', []))} "
            f"facts={len(updates.get('new_world_facts', []))} "
            f"threads_opened={len(updates.get('threads_to_open', []))} "
            f"threads_resolved={len(updates.get('threads_to_resolve', []))}"
        )
        return updates, meta
