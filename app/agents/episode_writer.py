"""Episode Writer Agent – generates individual story episodes."""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.context_builder import EpisodeContext
from app.llm.client import LLMRunner
from app.schemas.models import EpisodeOutput
from app.config import get_settings
from app.agents.planner import _json_candidates, parse_json_from_response

logger = logging.getLogger(__name__)


WRITER_SYSTEM = """You are a master serial fiction writer.
Write gripping, emotionally resonant episodes in a serialized format.

STRICT RULES:
1. Each episode must strictly be {min_words}–{max_words} words of actual story prose. Do NOT exceed {max_words} words under any circumstances.
2. End every episode with an immediate, escalating cliffhanger or hook:
   - The final 1–2 sentences must place a character in direct physical or psychological danger, reveal an alarming clue, or present an urgent dilemma matching the episode plan.
   - Do NOT end on a passive dialogue warning (e.g. a character simply saying 'be careful' or 'you are getting too close to danger'). The danger or threat must be actively happening, arriving, or confronting the protagonist right in the closing moment.
3. Follow the provided episode plan and context EXACTLY.
4. Maintain character consistency – personalities, goals, relationships do NOT change arbitrarily.
5. Respect ALL human instructions in the context.
6. Do not contradict established world facts or timeline.
7. Advance at least one open story thread.
8. STRICT NO-REPETITION:
   - Do NOT use repetitive cliché phrases such as 'dark path', 'slippery slope', or 'chill down the spine'.
   - Do NOT repeat generic atmospheric concepts like 'feeling watched' or 'eyes in the dark' without significant, concrete new plot development.
   - Every episode must advance the story through new physical actions, new clues, dialogue revelations, or direct confrontations.

Return ONLY valid JSON with no text outside the JSON block."""


WRITER_PROMPT = """Write Episode {episode_number} of the serial story.

{context}

Generate the episode as JSON with this exact structure:
{{
  "episode_number": {episode_number},
  "title": "Episode title (not just 'Episode N')",
  "content": "Full episode prose text (STRICTLY {min_words}–{max_words} words)",
  "summary": "2-3 sentence summary for memory storage",
  "characters_present": ["Name1", "Name2"],
  "facts_introduced": ["new fact 1", "new fact 2"],
  "threads_opened": ["new mystery or conflict opened"],
  "threads_resolved": ["thread that was resolved"],
  "hook": "The specific cliffhanger/hook sentence that ends the episode, connecting directly to the impending danger, threat, or major revelation"
}}

IMPORTANT:
- "content" must be complete prose fiction, STRICTLY {min_words}–{max_words} words. Do NOT exceed {max_words} words.
- "hook" must be 1-2 sentences matching the very end of "content" and must present clear, active danger or dramatic shock.
- "summary" must be concise (2-3 sentences) for memory storage.
- Do NOT put the same text in both "content" and "summary".
- Return ONLY the JSON object, nothing else."""


_CONTENT_KEYS = ("content", "prose", "body", "text", "episode_content", "story")


def _as_prose(value: Any) -> str:
    """Normalize LLM content fields that may be a string, list, or nested object."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n\n".join(part for part in (_as_prose(item) for item in value) if part)
    if isinstance(value, dict):
        for key in _CONTENT_KEYS:
            text = _as_prose(value.get(key))
            if text:
                return text
        return ""
    return str(value).strip()


def _flatten_episode_dict(data: dict) -> dict:
    """Lift nested episode objects so title/content live at the top level."""
    nested = data.get("episode")
    if not isinstance(nested, dict):
        return data
    merged = {**nested, **{key: value for key, value in data.items() if key != "episode"}}
    if not _as_prose(merged.get("content")) and _as_prose(nested.get("content")):
        merged["content"] = nested["content"]
    return merged


def _prose_outside_json(text: str) -> str:
    """Recover story text when the model puts valid JSON metadata in a fence and prose outside it."""
    without_fences = re.sub(r"```(?:json|JSON)?\s*.*?```", "", text, flags=re.DOTALL)
    start = without_fences.find("{")
    end = without_fences.rfind("}")
    if start != -1 and end > start:
        leftover = (without_fences[:start] + without_fences[end + 1 :]).strip()
    else:
        leftover = without_fences.strip()
    leftover = leftover.strip("`").strip()
    if len(leftover.split()) < 50:
        return ""
    return leftover


def episode_payload_from_response(text: str) -> dict:
    """Parse writer/reviser JSON, preferring payloads that actually contain episode prose."""
    parsed_dicts: list[dict] = []
    for candidate in _json_candidates(text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            parsed_dicts.append(_flatten_episode_dict(parsed))

    if not parsed_dicts:
        parsed_dicts.append(_flatten_episode_dict(parse_json_from_response(text)))

    def _word_score(data: dict) -> int:
        return len(_as_prose(next((data.get(key) for key in _CONTENT_KEYS if _as_prose(data.get(key))), "")).split())

    best = max(parsed_dicts, key=_word_score)
    content = next((_as_prose(best.get(key)) for key in _CONTENT_KEYS if _as_prose(best.get(key))), "")
    if not content:
        content = _prose_outside_json(text)
    if content:
        best["content"] = content
    return best


REVISION_PROMPT = """Revise Episode {episode_number} to fix the following issues:

ISSUES FOUND:
{issues}

ORIGINAL EPISODE:
{original_content}

CONTEXT (for reference):
{context_brief}

SPECIFIC INSTRUCTIONS FOR FIXING CRITIC ISSUES:
1. WORD COUNT OVERAGE: If an issue indicates word count exceeds a limit (e.g. over 500 words), you MUST aggressively cut filler, condense sentences, and tighten pacing so the revised prose is strictly within the allowed range.
2. WEAK HOOK / LACK OF DANGER: If the hook was flagged as weak or not connected to danger, rewrite the final 2–3 sentences of the episode with an active cliffhanger of direct jeopardy, an alarming revelation, or an immediate threat. Do NOT end with passive dialogue warnings.
3. REPETITION: If repeated themes (such as 'dark path', 'being watched', or generic dread) were flagged, remove the repetitive sensory clichés and introduce a brand new clue, a physical confrontation, or dialogue action that moves the mystery forward.
4. HUMAN INSTRUCTIONS: Ensure every directive under Human Instructions is strictly honored.

Return the revised episode as valid JSON with this exact structure:
{{
  "episode_number": {episode_number},
  "title": "Episode title",
  "content": "Full revised prose text",
  "summary": "2-3 sentence summary",
  "characters_present": ["Name1", "Name2"],
  "facts_introduced": ["fact 1"],
  "threads_opened": ["new thread opened"],
  "threads_resolved": ["thread resolved"],
  "hook": "The specific cliffhanger sentence ending the episode"
}}"""


class EpisodeWriterAgent:
    """Generates individual story episodes following the plan and context."""

    def __init__(self, runner: LLMRunner | None = None):
        self.runner = runner or LLMRunner()
        self.settings = get_settings()

    def write_episode(
        self,
        context: EpisodeContext,
        story_id: str,
        run_id: str | None = None,
        rejection_reason: str | None = None,
    ) -> tuple[EpisodeOutput, dict]:
        """
        Write an episode from context.
        Returns (EpisodeOutput, run_metadata).
        """
        run_id = run_id or str(uuid.uuid4())
        ep_num = context.episode_number
        logger.info(f"[EpisodeWriter] Writing episode {ep_num}")

        context_text = context.to_prompt_text()

        rejection_note = ""
        if rejection_reason:
            rejection_note = f"\n\nNOTE: A previous version was rejected for: {rejection_reason}\nDo NOT repeat that mistake.\n"

        min_words, max_words = context.min_words, context.max_words
        prompt = WRITER_PROMPT.format(
            episode_number=ep_num,
            context=context_text + rejection_note,
            min_words=min_words,
            max_words=max_words,
        )

        system = WRITER_SYSTEM.format(
            min_words=min_words,
            max_words=max_words,
        )

        messages = [
            SystemMessage(content=system),
            HumanMessage(content=prompt),
        ]

        content, meta = self.runner.invoke(messages, agent_name="episode_writer")
        episode_data = episode_payload_from_response(content)

        # Validate and post-process
        episode_output = self._parse_output(episode_data, ep_num)
        if episode_output.word_count == 0:
            logger.warning(
                f"[EpisodeWriter] Episode {ep_num} parsed with 0 words. "
                f"Raw response starts: {(content or '')[:300]!r}"
            )
        if not episode_output.characters_present and context:
            plan_chars = context.episode_plan.get("characters_involved") or []
            if plan_chars:
                episode_output.characters_present = [str(c) for c in plan_chars if c]
            elif context.relevant_characters:
                found = [
                    c["name"] for c in context.relevant_characters
                    if c.get("name") and c["name"].lower() in episode_output.content.lower()
                ]
                if found:
                    episode_output.characters_present = found

        logger.info(f"[EpisodeWriter] Episode {ep_num} written. words={episode_output.word_count}")
        return episode_output, meta

    def revise_episode(
        self,
        original: EpisodeOutput,
        issues: list[dict],
        context: EpisodeContext,
        run_id: str | None = None,
    ) -> tuple[EpisodeOutput, dict]:
        """Revise an episode based on critic issues."""
        run_id = run_id or str(uuid.uuid4())
        logger.info(f"[EpisodeWriter] Revising episode {original.episode_number}")

        issues_text = "\n".join(
            f"[{i.get('severity', 'medium').upper()}] {i.get('type', 'issue')}: {i.get('description', '')}"
            for i in issues
        )

        # Brief context for revision (no need to repeat everything)
        context_brief = f"""Story: {context.story_title}
Word count target: {context.min_words}–{context.max_words} words
Recent state: {context.rolling_summary[:300] if context.rolling_summary else 'N/A'}
Human instructions: {'; '.join(context.active_instructions) if context.active_instructions else 'None'}"""

        prompt = REVISION_PROMPT.format(
            episode_number=original.episode_number,
            issues=issues_text,
            original_content=original.content,
            context_brief=context_brief,
        )

        messages = [
            SystemMessage(content=WRITER_SYSTEM.format(
                min_words=context.min_words,
                max_words=context.max_words,
            )),
            HumanMessage(content=prompt),
        ]

        content, meta = self.runner.invoke(messages, agent_name="episode_reviser")
        episode_data = episode_payload_from_response(content)
        episode_output = self._parse_output(episode_data, original.episode_number)
        if not episode_output.content.strip() and original.content.strip():
            logger.warning(
                "[EpisodeWriter] Revision returned empty prose; keeping the previous draft "
                f"for episode {original.episode_number}"
            )
            episode_output = original

        # Carry over metadata from original if missing in revision
        if not episode_output.characters_present and original.characters_present:
            episode_output.characters_present = original.characters_present
        elif not episode_output.characters_present and context:
            plan_chars = context.episode_plan.get("characters_involved") or []
            if plan_chars:
                episode_output.characters_present = [str(c) for c in plan_chars if c]
            elif context.relevant_characters:
                found = [
                    c["name"] for c in context.relevant_characters
                    if c.get("name") and c["name"].lower() in episode_output.content.lower()
                ]
                if found:
                    episode_output.characters_present = found

        if not episode_output.threads_opened and original.threads_opened:
            episode_output.threads_opened = original.threads_opened
        if not episode_output.threads_resolved and original.threads_resolved:
            episode_output.threads_resolved = original.threads_resolved
        if not episode_output.facts_introduced and original.facts_introduced:
            episode_output.facts_introduced = original.facts_introduced

        logger.info(
            f"[EpisodeWriter] Revision complete for episode {original.episode_number}. "
            f"words={episode_output.word_count}"
        )
        return episode_output, meta

    def _parse_output(self, data: dict, episode_number: int) -> EpisodeOutput:
        """Parse and validate raw LLM output into EpisodeOutput."""
        data = _flatten_episode_dict(data)
        content = _as_prose(next((data.get(key) for key in _CONTENT_KEYS if _as_prose(data.get(key))), ""))
        word_count = len(content.split()) if content else 0
        title = _as_prose(data.get("title")) or f"Episode {episode_number}"
        hook = _as_prose(data.get("hook"))
        hook = _closing_hook(content, hook)

        chars_raw = (
            data.get("characters_present")
            or data.get("characters")
            or data.get("characters_involved")
            or data.get("cast")
            or []
        )
        facts_raw = (
            data.get("facts_introduced")
            or data.get("new_facts")
            or data.get("facts")
            or []
        )
        threads_op_raw = (
            data.get("threads_opened")
            or data.get("open_threads")
            or data.get("new_threads")
            or data.get("threads")
            or []
        )
        threads_res_raw = (
            data.get("threads_resolved")
            or data.get("resolved_threads")
            or data.get("threads_closed")
            or []
        )

        return EpisodeOutput(
            episode_number=data.get("episode_number", episode_number),
            title=title,
            content=content,
            summary=_as_prose(data.get("summary")),
            characters_present=_as_string_list(chars_raw),
            facts_introduced=_as_string_list(facts_raw),
            threads_opened=_as_string_list(threads_op_raw),
            threads_resolved=_as_string_list(threads_res_raw),
            hook=hook,
            word_count=word_count,
        )


def _closing_hook(content: str, hook: str) -> str:
    """Preserve explicit hook, falling back to the closing sentences if empty."""
    if hook and hook.strip():
        return hook.strip()
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", content.strip()) if part.strip()]
    return " ".join(sentences[-2:]) if sentences else ""


def _as_string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, dict):
                val = item.get("name") or item.get("title") or item.get("description") or ""
                if val:
                    result.append(str(val).strip())
            elif item is not None and str(item).strip():
                result.append(str(item).strip())
        return result
    return []
