"""Story Planner Agent – generates the 200-episode arc plan."""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.client import LLMRunner
from app.config import get_settings

logger = logging.getLogger(__name__)


PLANNER_SYSTEM = """You are a professional serial story writer and narrative architect.
Your task is to create a detailed, coherent long-form story plan.

The plan must:
- Have a compelling story title
- Identify genre and tone
- Create 3-6 main characters with clear arcs
- Group episodes into meaningful larger arcs (each about 20 episodes)
- Make every episode feel like part of a cohesive whole
- Ensure each arc has a turning point
- Track open threads and their planned resolutions
- Create hooks and cliffhangers that span multiple episodes

Return a single JSON object and nothing else.
Do not wrap the JSON in markdown fences or add commentary."""


OUTLINE_PROMPT = """Given this story premise:

"{premise}"

Design the story outline for exactly {total_episodes} episodes.
Do NOT include a per-episode list. Episode outlines are generated separately.

Return a JSON object with this exact structure:
{{
  "title": "Story title",
  "premise": "One-line summary",
  "genre": "genre",
  "tone": "tone description",
  "characters": [
    {{
      "name": "...",
      "role": "protagonist|antagonist|supporting",
      "personality": "...",
      "goals": ["..."],
      "relationships": {{"other_char": "relationship description"}},
      "current_state": "...",
      "important_facts": ["..."],
      "character_arc": "brief arc description",
      "status": "alive"
    }}
  ],
  "world_rules": ["rule 1", "rule 2"],
  "major_turning_points": ["turning point 1", "turning point 2"],
  "planned_resolutions": ["resolution 1"],
  "arcs": [
    {{
      "arc_number": 1,
      "title": "Arc title",
      "episode_start": 1,
      "episode_end": 20,
      "summary": "What happens in this arc",
      "major_themes": ["theme1"],
      "turning_point": "What changes at end of arc"
    }}
  ]
}}

Arcs must cover episodes 1 through {total_episodes} with no gaps.
Each arc should cover approximately 20 episodes."""


EPISODE_BATCH_PROMPT = """Continue this serial story plan.

PREMISE: {premise}
TITLE: {title}
GENRE: {genre}
TONE: {tone}
CHARACTERS: {characters}
WORLD RULES: {world_rules}

CURRENT ARC:
{arc}

Write episode outlines for episodes {start} through {end} only.
{continuity}

Return a JSON object:
{{
  "episodes": [
    {{
      "episode_number": {start},
      "title": "Episode title",
      "summary": "What happens in this episode (2-3 sentences)",
      "major_events": ["event 1", "event 2"],
      "characters_involved": ["Name1", "Name2"],
      "threads_opened": ["new mystery or conflict"],
      "threads_resolved": [],
      "planned_hook": "Hook/cliffhanger description",
      "arc_number": {arc_number}
    }}
  ]
}}

Include every episode number from {start} to {end}, in order.
Keep cause-and-effect continuity with the arc summary and the previous hook."""


# One outline call plus these batches stay inside max_tokens_per_episode.
EPISODE_BATCH_SIZE = 10


def _json_candidates(text: str) -> list[str]:
    """Pull possible JSON payloads out of a model reply."""
    candidates: list[str] = []
    closed = re.search(r"```(?:json|JSON)?\s*(.*?)```", text, re.DOTALL)
    if closed:
        candidates.append(closed.group(1).strip())
    unclosed = re.search(r"```(?:json|JSON)?\s*(.*)$", text, re.DOTALL)
    if unclosed:
        candidates.append(unclosed.group(1).strip())
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1].strip())
    candidates.append(text.strip())
    # Preserve order while dropping duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            unique.append(candidate)
    return unique


def parse_json_from_response(text: str) -> dict:
    """Extract a JSON object from an LLM response, including fenced output."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Failed to parse JSON from LLM response: response was empty")

    last_error: json.JSONDecodeError | None = None
    for candidate in _json_candidates(text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed

    stripped = text.strip()
    truncated = stripped.startswith("```") or not stripped.rstrip().endswith("}")
    hint = ""
    if truncated:
        hint = (
            " The response looks truncated or wrapped in a markdown fence."
            " A full 200-episode plan does not fit in one completion."
        )
    detail = str(last_error) if last_error else "response was not a JSON object"
    raise ValueError(
        f"Failed to parse JSON from LLM response: {detail}.{hint}\n\nResponse: {text[:500]}"
    )


class PlannerAgent:
    """Generates the complete 200-episode story arc plan."""

    def __init__(self, runner: LLMRunner | None = None):
        self.runner = runner or LLMRunner()
        self.settings = get_settings()

    def generate_plan(self, story_id: str, premise: str, run_id: str | None = None) -> tuple[dict, dict]:
        """
        Generate the full story plan.
        Returns (plan_data, run_metadata).

        The outline and episode batches are separate calls. A single completion
        cannot hold every episode outline under the configured token cap, which
        previously truncated the JSON and failed parsing.
        """
        run_id = run_id or str(uuid.uuid4())
        total = self.settings.total_episodes
        logger.info(f"[Planner] Generating plan for story={story_id} episodes={total}")

        outline, meta = self._generate_outline(premise, total)
        episodes = outline.get("episodes") or []
        metas = [meta]

        if len(episodes) >= total:
            outline["episodes"] = episodes[:total]
        else:
            outline.pop("episodes", None)
            arcs = self._cover_arcs(outline.get("arcs") or [], total)
            outline["arcs"] = arcs
            built: list[dict] = []
            for arc in arcs:
                built.extend(self._generate_arc_episodes(premise, outline, arc, built, metas))
            outline["episodes"] = built

        self._validate_plan(outline)

        logger.info(
            f"[Planner] Done. arcs={len(outline.get('arcs', []))} "
            f"episodes={len(outline.get('episodes', []))}"
        )
        return outline, _merge_metadata(metas)

    def _generate_outline(self, premise: str, total: int) -> tuple[dict, dict]:
        messages = [
            SystemMessage(content=PLANNER_SYSTEM),
            HumanMessage(content=OUTLINE_PROMPT.format(premise=premise, total_episodes=total)),
        ]
        content, meta = self.runner.invoke(messages, agent_name="planner")
        self._ensure_not_truncated(content, meta, "story outline")
        outline = parse_json_from_response(content)
        self._validate_outline(outline)
        return outline, meta

    def _generate_arc_episodes(
        self,
        premise: str,
        outline: dict,
        arc: dict,
        prior: list[dict],
        metas: list[dict],
    ) -> list[dict]:
        start = int(arc["episode_start"])
        end = int(arc["episode_end"])
        episodes: list[dict] = []
        cursor = start
        while cursor <= end:
            batch_end = min(cursor + EPISODE_BATCH_SIZE - 1, end)
            batch, meta = self._generate_episode_range(
                premise, outline, arc, cursor, batch_end, prior + episodes
            )
            metas.append(meta)
            episodes.extend(batch)
            cursor = batch_end + 1
        return episodes

    def _generate_episode_range(
        self,
        premise: str,
        outline: dict,
        arc: dict,
        start: int,
        end: int,
        prior: list[dict],
    ) -> tuple[list[dict], dict]:
        messages = [
            SystemMessage(content=PLANNER_SYSTEM),
            HumanMessage(content=self._episode_prompt(premise, outline, arc, start, end, prior)),
        ]
        content, meta = self.runner.invoke(messages, agent_name="planner")
        truncated = self._looks_truncated(content, meta)
        try:
            parsed = None if truncated else parse_json_from_response(content)
            episodes = [] if parsed is None else self._coerce_episodes(parsed, start, end, arc)
        except ValueError:
            parsed = None
            episodes = []

        if episodes:
            return episodes, meta

        if end > start:
            mid = (start + end) // 2
            logger.warning(
                f"[Planner] Episode batch {start}-{end} was truncated or invalid; splitting"
            )
            left, left_meta = self._generate_episode_range(premise, outline, arc, start, mid, prior)
            right, right_meta = self._generate_episode_range(
                premise, outline, arc, mid + 1, end, prior + left
            )
            return left + right, _merge_metadata([left_meta, right_meta])

        raise ValueError(
            f"Failed to generate episode {start}: model output was truncated or not valid JSON.\n\n"
            f"Response: {content[:500]}"
        )

    def _episode_prompt(
        self,
        premise: str,
        outline: dict,
        arc: dict,
        start: int,
        end: int,
        prior: list[dict],
    ) -> str:
        names = [
            c.get("name") for c in outline.get("characters", []) if isinstance(c, dict) and c.get("name")
        ]
        continuity = "This is the start of the story."
        if prior:
            last = prior[-1]
            continuity = (
                f"Previous episode {last.get('episode_number')}: {last.get('title')}. "
                f"Summary: {last.get('summary')} Hook: {last.get('planned_hook')}"
            )
        return EPISODE_BATCH_PROMPT.format(
            premise=premise,
            title=outline.get("title", ""),
            genre=outline.get("genre", ""),
            tone=outline.get("tone", ""),
            characters=", ".join(names) or "See arc summary",
            world_rules="; ".join(outline.get("world_rules") or []),
            arc=json.dumps(arc, ensure_ascii=False),
            start=start,
            end=end,
            continuity=continuity,
            arc_number=arc.get("arc_number", 1),
        )

    def _coerce_episodes(self, parsed: dict, start: int, end: int, arc: dict) -> list[dict]:
        raw = parsed.get("episodes")
        if raw is None and "episode_number" in parsed:
            raw = [parsed]
        if not isinstance(raw, list):
            raise ValueError("Episode batch missing episodes array")
        expected = list(range(start, end + 1))
        if len(raw) != len(expected):
            raise ValueError(f"Expected {len(expected)} episodes, got {len(raw)}")
        episodes: list[dict] = []
        for episode, number in zip(raw, expected):
            if not isinstance(episode, dict):
                raise ValueError(f"Episode {number} was not an object")
            episode = dict(episode)
            episode["episode_number"] = number
            episode["arc_number"] = arc.get("arc_number", episode.get("arc_number"))
            episodes.append(episode)
        return episodes

    def _cover_arcs(self, arcs: list, total: int) -> list[dict]:
        """Use model arcs when they cover 1..total; otherwise build 20-episode arcs."""
        cleaned: list[dict] = []
        for arc in arcs:
            if not isinstance(arc, dict):
                continue
            try:
                start = int(arc["episode_start"])
                end = int(arc["episode_end"])
            except (KeyError, TypeError, ValueError):
                continue
            if end < start:
                continue
            item = dict(arc)
            item["episode_start"] = start
            item["episode_end"] = end
            cleaned.append(item)
        cleaned.sort(key=lambda arc: arc["episode_start"])

        if cleaned and cleaned[0]["episode_start"] <= 1 and cleaned[-1]["episode_end"] >= total:
            cursor = 1
            covered = True
            for arc in cleaned:
                if arc["episode_start"] > cursor:
                    covered = False
                    break
                cursor = max(cursor, arc["episode_end"] + 1)
            if covered:
                clipped: list[dict] = []
                for arc in cleaned:
                    if arc["episode_start"] > total:
                        break
                    item = dict(arc)
                    item["episode_start"] = max(item["episode_start"], 1)
                    item["episode_end"] = min(item["episode_end"], total)
                    clipped.append(item)
                return clipped

        generated: list[dict] = []
        start = 1
        number = 1
        while start <= total:
            end = min(start + 19, total)
            generated.append({
                "arc_number": number,
                "title": f"Arc {number}",
                "episode_start": start,
                "episode_end": end,
                "summary": "Continue the serial from the previous arc.",
                "major_themes": [],
                "turning_point": "The arc reaches its turning point.",
            })
            start = end + 1
            number += 1
        return generated

    def _looks_truncated(self, content: str, meta: dict) -> bool:
        """True when the completion was cut off before a finished JSON object."""
        stripped = (content or "").strip()
        unclosed_fence = (
            stripped.startswith("```")
            and "```" not in stripped[3:]
            and not stripped.endswith("}")
        )
        hit_limit = meta.get("finish_reason") in {"length", "max_tokens", "MAX_TOKENS"}
        if not hit_limit:
            return unclosed_fence
        try:
            parse_json_from_response(content)
        except ValueError:
            return True
        return False

    def _ensure_not_truncated(self, content: str, meta: dict, label: str) -> None:
        if self._looks_truncated(content, meta):
            raise ValueError(
                f"Failed to generate {label}: model output hit the token limit "
                f"before the JSON completed.\n\nResponse: {content[:500]}"
            )

    def _validate_outline(self, plan: dict) -> None:
        for field in ("title", "characters", "arcs"):
            if field not in plan:
                raise ValueError(f"Plan missing required field: {field}")

    def _validate_plan(self, plan: dict) -> None:
        self._validate_outline(plan)
        episodes = plan.get("episodes") or []
        if len(episodes) < self.settings.total_episodes:
            raise ValueError(
                f"Plan has too few episodes: {len(episodes)}/{self.settings.total_episodes}"
            )


def _merge_metadata(metas: list[dict]) -> dict:
    if not metas:
        return {}
    return {
        "input_tokens": sum(m.get("input_tokens") or 0 for m in metas),
        "output_tokens": sum(m.get("output_tokens") or 0 for m in metas),
        "cost": sum(m.get("cost") or 0 for m in metas),
        "latency_ms": sum(m.get("latency_ms") or 0 for m in metas),
        "model": next((m.get("model") for m in reversed(metas) if m.get("model")), None),
        "finish_reason": metas[-1].get("finish_reason"),
    }
