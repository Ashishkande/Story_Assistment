"""pytest configuration and shared fixtures."""
from __future__ import annotations

import uuid
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base, Story, StoryPlan, Episode, Character, EpisodeStatus, StoryStatus


# ─── In-memory SQLite engine for tests ────────────────────
TEST_DB_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    """Create all tables once per test session."""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Fresh DB session per test, rolled back after."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def story_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def sample_story(db: Session, story_id: str) -> Story:
    story = Story(
        id=story_id,
        premise="A delivery rider realizes every address belongs to someone who died.",
        status=StoryStatus.ACTIVE,
        current_episode=0,
        total_planned=200,
    )
    db.add(story)
    db.commit()
    return story


@pytest.fixture
def approved_plan(db: Session, sample_story: Story) -> StoryPlan:
    plan = StoryPlan(
        id=str(uuid.uuid4()),
        story_id=sample_story.id,
        approved=True,
        arc_structure={
            "1": {"arc_number": 1, "title": "The Discovery", "episode_start": 1, "episode_end": 20,
                  "summary": "The rider uncovers the pattern.", "turning_point": "First death confirmed."}
        },
        episode_plans=[
            {
                "episode_number": i,
                "title": f"Episode {i}",
                "summary": f"Summary of episode {i}",
                "major_events": [f"Event {i}"],
                "characters_involved": ["Arjun"],
                "threads_opened": [],
                "threads_resolved": [],
                "planned_hook": f"Cliffhanger for episode {i}",
                "arc_number": 1,
            }
            for i in range(1, 201)
        ],
        world_rules=["Building 7 is cursed", "Every death was ruled accidental"],
        major_turning_points=["The rider discovers the pattern", "Police become involved"],
        planned_resolutions=["The truth about Building 7 is revealed"],
        version=1,
    )
    db.add(plan)
    db.commit()
    return plan


@pytest.fixture
def mock_llm_runner():
    """Mock LLMRunner so tests don't call real LLMs."""
    with patch("app.llm.client.LLMRunner") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


MOCK_PLAN_RESPONSE = {
    "title": "The Dead Route",
    "premise": "A delivery rider realizes every address belongs to someone who died.",
    "genre": "Mystery Thriller",
    "tone": "Dark, suspenseful",
    "characters": [
        {
            "name": "Arjun Sharma",
            "role": "protagonist",
            "personality": "Curious, persistent, haunted",
            "goals": ["Uncover the truth", "Protect himself"],
            "relationships": {"Maya Patel": "reluctant ally"},
            "current_state": "Starting his delivery route",
            "important_facts": ["Works night shifts", "Ex-military"],
            "character_arc": "Goes from oblivious rider to reluctant investigator",
            "status": "alive",
        },
        {
            "name": "Maya Patel",
            "role": "supporting",
            "personality": "Skeptical, intelligent",
            "goals": ["Report the truth"],
            "relationships": {"Arjun Sharma": "reluctant ally"},
            "current_state": "Investigative journalist",
            "important_facts": ["Knows building 7 history"],
            "character_arc": "Becomes convinced of the conspiracy",
            "status": "alive",
        },
    ],
    "world_rules": ["Building 7 at 14 Crescent Lane is the epicenter"],
    "major_turning_points": ["Arjun connects all addresses to Building 7"],
    "planned_resolutions": ["The true killer is revealed in episode 180"],
    "arcs": [
        {
            "arc_number": 1, "title": "The Pattern", "episode_start": 1, "episode_end": 20,
            "summary": "Arjun notices the pattern.", "major_themes": ["death", "mystery"],
            "turning_point": "He discovers all addresses link to one building.",
        }
    ],
    "episodes": [
        {
            "episode_number": i,
            "title": f"Chapter {i}",
            "summary": f"Events of episode {i}.",
            "major_events": [f"Major event in episode {i}"],
            "characters_involved": ["Arjun Sharma"],
            "threads_opened": [],
            "threads_resolved": [],
            "planned_hook": f"Cliffhanger ending episode {i}",
            "arc_number": 1,
        }
        for i in range(1, 201)
    ],
}

MOCK_EPISODE_RESPONSE = {
    "episode_number": 1,
    "title": "The First Address",
    "content": (
        "Arjun Sharma pulled his motorcycle to the curb outside 14 Crescent Lane, "
        "the delivery bag heavy on his back. The address felt familiar in the wrong way — "
        "a cold prickling at the edge of memory he couldn't quite place. He checked the name "
        "on the package: R. Krishnamurthy, Flat 4B. The intercom buzzed to static. "
        "He pressed again. Nothing. A neighbor hurrying past paused, eyes going wide. "
        "'You're delivering to 4B?' she said. 'Mr. Krishnamurthy died three weeks ago.' "
        "Arjun stared at the package. Then at the next address on his route. Then back. "
        "Something tightened in his chest — the particular feeling he'd learned in the army "
        "to call a bad pattern. He photographed the delivery slip with his phone, hands "
        "steadier than his heartbeat, and moved to his bike. The next address was two streets away. "
        "He arrived to find an empty flat, a cracked window, and a death notice still taped to the door. "
        "By the fifth address, Arjun had stopped ringing doorbells. He sat on his bike "
        "in the falling dark and scrolled through his delivery list. Every single name. "
        "Every one of them dead. He typed a text to his dispatcher — just a question about route origins. "
        "The reply came back instantly: all packages had been queued by the same anonymous sender. "
        "Account created three days ago. Prepaid. Untraceable. "
        "Arjun looked up at the building across the street — 14 Crescent Lane again, "
        "somehow the last address on a circular route — and felt the hairs on his arm rise. "
        "The light in Flat 4B was on."
    ),
    "summary": "Arjun discovers all his deliveries go to dead people, all linked to one building.",
    "characters_present": ["Arjun Sharma"],
    "facts_introduced": ["All packages were sent by anonymous sender", "14 Crescent Lane is the link"],
    "threads_opened": ["Who sent the packages?", "Why are all recipients dead?"],
    "threads_resolved": [],
    "hook": "The light in Flat 4B was on.",
}

MOCK_CRITIC_RESPONSE = {
    "passed": True,
    "score": 0.92,
    "issues": [],
    "repetition_detected": False,
    "hook_quality": "strong",
    "human_instructions_followed": True,
    "arc_adherence": True,
    "positive_aspects": ["Strong atmosphere", "Good mystery setup"],
}

MOCK_MEMORY_RESPONSE = {
    "character_updates": [
        {
            "name": "Arjun Sharma",
            "current_state": "Investigating suspicious deliveries",
            "important_facts": ["All packages from anonymous sender"],
            "relationship_updates": {},
            "status": "alive",
        }
    ],
    "new_world_facts": [
        {"category": "location", "key": "14 Crescent Lane", "value": "Central location connecting all deaths"},
        {"category": "revelation", "key": "anonymous_sender", "value": "All packages sent by same untraceable account"},
    ],
    "threads_to_open": [
        {
            "thread_type": "mystery",
            "title": "Who sent the packages",
            "description": "All deliveries came from an anonymous untraceable account",
            "importance": "critical",
            "planned_resolution": "Revealed in episode 50",
        }
    ],
    "threads_to_resolve": [],
    "new_rolling_summary": (
        "Arjun Sharma, a delivery rider, discovered that all addresses on his route belong to deceased individuals. "
        "Every package was sent by the same anonymous untraceable account. The connection point is 14 Crescent Lane. "
        "The light was on in Flat 4B — occupied by someone who should be dead."
    ),
}
