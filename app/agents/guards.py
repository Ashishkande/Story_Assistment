"""Deterministic episode checks that do not depend on the critic LLM."""
from __future__ import annotations

import re
from typing import Iterable

from app.config import get_settings
from app.schemas.models import CriticIssue, CriticResult, EpisodeOutput

_WORD_RE = re.compile(r"[a-z0-9]{4,}")


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
) -> list[CriticIssue]:
    settings = get_settings()
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

    if count < settings.episode_min_words:
        issues.append(CriticIssue(
            type="arc",
            severity="high",
            description=(
                f"Word count is {count}, below the {settings.episode_min_words}–"
                f"{settings.episode_max_words} range."
            ),
        ))
    elif count > settings.episode_max_words:
        issues.append(CriticIssue(
            type="arc",
            severity="high",
            description=(
                f"Word count is {count}, above the {settings.episode_min_words}–"
                f"{settings.episode_max_words} range."
            ),
        ))

    hook = (episode.hook or "").strip()
    tail = " ".join(content.strip().split()[-40:]).lower()
    if not hook:
        issues.append(CriticIssue(
            type="hook",
            severity="high",
            description="Hook field is empty. Every episode must end on a cliffhanger.",
        ))
    elif len(hook.split()) >= 4 and not any(
        token in tail for token in hook.lower().split()[:6] if len(token) > 3
    ):
        issues.append(CriticIssue(
            type="hook",
            severity="medium",
            description="The stated hook does not match the closing lines of the episode.",
        ))

    current = plot_tokens(f"{episode.summary} {content[:800]}")
    for beat in prior_beats or []:
        if jaccard(current, plot_tokens(beat)) >= 0.55:
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
