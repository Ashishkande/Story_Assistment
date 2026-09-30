"""Deterministic episode checks that do not depend on the critic LLM."""
from __future__ import annotations

import re
from typing import Iterable

from app.config import get_settings
from app.schemas.models import CriticIssue, CriticResult, EpisodeOutput

_WORD_RE = re.compile(r"[a-z0-9]{4,}")
_RANGE_RE = re.compile(
    r"(?:word\s*count|words?|length).{0,40}?(?:between|from|of)?\s*(\d{3,4})\s*(?:to|-|–|and)\s*(\d{3,4})",
    re.IGNORECASE,
)
_RANGE_RE_FLIP = re.compile(
    r"(?:between|from)\s*(\d{3,4})\s*(?:to|-|–|and)\s*(\d{3,4})\s*words?",
    re.IGNORECASE,
)
_MAX_RE = re.compile(
    r"(?:under|less\s+than|max|maximum|at\s+most|no\s+more\s+than|below|cap\s+at|within|limit\s*(?:to|of)?)\s*(\d{3,4})\s*words?",
    re.IGNORECASE,
)
_MIN_RE = re.compile(
    r"(?:at\s+least|minimum|min|more\s+than|above|no\s+less\s+than)\s*(\d{3,4})\s*words?",
    re.IGNORECASE,
)
_ABOUT_RE = re.compile(
    r"(?:around|about|approximately|roughly)\s*(\d{3,4})\s*words?",
    re.IGNORECASE,
)


def parse_word_limits(
    instructions: Iterable[str] | None,
    default_min: int,
    default_max: int,
) -> tuple[int, int]:
    """Use the latest human word-count range if present; otherwise settings defaults."""
    min_words, max_words = default_min, default_max
    for text in instructions or []:
        parsed = _limits_from_text(text, default_min, default_max)
        if parsed:
            min_words, max_words = parsed
    if min_words > max_words:
        min_words, max_words = max_words, min_words
    return min_words, max_words


def is_word_count_instruction(text: str) -> bool:
    return _limits_from_text(text, 400, 700) is not None


def _limits_from_text(text: str, default_min: int = 400, default_max: int = 700) -> tuple[int, int] | None:
    if not text:
        return None
    match = _RANGE_RE.search(text) or _RANGE_RE_FLIP.search(text)
    if match:
        low, high = int(match.group(1)), int(match.group(2))
        if low > high:
            low, high = high, low
        return low, high
    
    max_match = _MAX_RE.search(text)
    if max_match:
        high = int(max_match.group(1))
        low = min(default_min, max(250, high - 100))
        return low, high

    min_match = _MIN_RE.search(text)
    if min_match:
        low = int(min_match.group(1))
        high = max(default_max, low + 200)
        return low, high

    about_match = _ABOUT_RE.search(text)
    if about_match:
        target = int(about_match.group(1))
        return max(250, target - 50), target + 50

    return None


def word_count(text: str) -> int:
    return len((text or "").split())


def plot_tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def beat_line(episode_number: int, summary: str, hook: str = "") -> str:
    snippet = " ".join((summary or hook or "").split()[:24])
    return f"Ep {episode_number}: {snippet}".strip()


def structural_issues(
    episode: EpisodeOutput,
    *,
    prior_beats: Iterable[str] | None = None,
    min_words: int | None = None,
    max_words: int | None = None,
) -> list[CriticIssue]:
    settings = get_settings()
    min_words = min_words if min_words is not None else settings.episode_min_words
    max_words = max_words if max_words is not None else settings.episode_max_words
    issues: list[CriticIssue] = []
    content = episode.content or ""
    count = episode.word_count or word_count(content)

    if not content.strip():
        issues.append(CriticIssue(
            type="consistency",
            severity="critical",
            description="Episode content is empty.",
        ))
        return issues

    if count < min_words:
        issues.append(CriticIssue(
            type="arc",
            severity="high",
            description=f"Word count is {count}, below the required {min_words}–{max_words} range.",
        ))
    elif count > max_words:
        issues.append(CriticIssue(
            type="arc",
            severity="high",
            description=f"Word count is {count}, above the required {min_words}–{max_words} range.",
        ))

    hook = (episode.hook or "").strip()
    if not hook:
        issues.append(CriticIssue(
            type="hook",
            severity="high",
            description="Hook field is empty. Every episode must end on a cliffhanger.",
        ))

    current = plot_tokens(f"{episode.summary} {content[:800]}")
    for beat in prior_beats or []:
        if jaccard(current, plot_tokens(beat)) >= 0.72:
            issues.append(CriticIssue(
                type="repetition",
                severity="high",
                description=f"Plot overlap with earlier beat: {beat[:160]}",
            ))
            break

    return issues


def merge_critic_result(
    llm_result: CriticResult,
    extra: list[CriticIssue],
    *,
    instructions_followed: bool = True,
) -> CriticResult:
    issues = list(llm_result.issues) + extra
    if extra:
        seen = {(i.type, i.description) for i in llm_result.issues}
        issues = list(llm_result.issues) + [i for i in extra if (i.type, i.description) not in seen]

    if not instructions_followed:
        already = any(
            i.type in {"feedback", "human_instructions"}
            or "word count" in (i.description or "").lower()
            or "instruction" in (i.description or "").lower()
            for i in issues
        )
        if not already:
            issues.append(CriticIssue(
                type="feedback",
                severity="high",
                description="Human instructions were not followed.",
            ))

    high = any(i.severity in {"high", "critical"} for i in issues)
    score = llm_result.score
    if extra or not instructions_followed:
        score = min(score, 0.65 if high else 0.75)
    if any(i.severity == "critical" for i in issues):
        score = min(score, 0.4)

    passed = score >= 0.7 and not high and instructions_followed
    return CriticResult(passed=passed, score=score, issues=issues)
