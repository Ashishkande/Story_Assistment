# 🌙 Agentic Serial Story Writer

> An agentic system that takes a one-line story premise and generates a coherent, long-running 200-episode serial story with human-in-the-loop control, layered memory, and full observability.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Problem Statement](#problem-statement)
3. [Architecture](#architecture)
4. [Technology Choices](#technology-choices)
5. [Setup Instructions](#setup-instructions)
6. [Environment Variables](#environment-variables)
7. [Database Setup](#database-setup)
8. [How to Run](#how-to-run)
9. [How to Run Tests](#how-to-run-tests)
10. [How to Run the Demo](#how-to-run-the-demo)
11. [HITL Workflow](#hitl-workflow)
12. [Memory Architecture](#memory-architecture)
13. [Consistency Checking](#consistency-checking)
14. [Resume Behavior](#resume-behavior)
15. [Cost Estimation](#cost-estimation)
16. [Retroactive Edit Support](#retroactive-edit-support)
17. [Limitations](#limitations)
18. [API Reference](#api-reference)
19. [DECISIONS.md](../DECISIONS.md)

---

## Project Overview

The Agentic Serial Story Writer generates serialized fiction across 200 episodes from a single premise. Each episode is 400–700 words, ends with a cliffhanger, and maintains consistency with all prior story facts, character states, and open plot threads.

The system does **not** solve the "long context" problem by sending all prior episodes to the LLM. Instead, it uses **layered story memory** (structured character state, world facts, open threads, rolling summaries, a short plot-beat index) that remains compact from episode 1 through episode 200.

Assignment write-up of memory, HITL, and failure modes: [DECISIONS.md](DECISIONS.md) (one page). Demo: `python -m cli.main demo --episodes 15` (plan + 15 episodes + two HITL instructions). Screen recording and public URL are operator tasks; this repo is web UI + CLI.

---

## Problem Statement

Generating a 200-episode coherent serial story with an LLM is hard because:

- **Context limits**: You cannot fit 200 × 500 words ≈ 100,000 words in a prompt
- **Consistency drift**: Characters contradict themselves, facts change, timelines break
- **Repetition**: The same emotional beats or plot events recur
- **Human control**: Writers need to redirect the story mid-generation
- **Cost**: 200 episodes at naive full-context retrieval could cost $50–$200+

This system solves all of these.

---

## Architecture

```
User Premise
    ↓
[Planner Agent] → 200-Episode Arc Plan
    ↓
[Human Review] ← Approve / Edit / Regenerate
    ↓
[Context Builder] ← Layered Memory (DB)
    ↓
[Episode Writer] → Draft Episode (LangGraph)
    ↓
[Consistency Critic] → Pass / Issues
    ↓         ↗ (retry up to MAX_REVISIONS)
[Reviser] ←─────────────────────┘
    ↓
[Human Review] ← Approve / Edit / Reject / Feedback
    ↓
[Memory Updater] → Update Characters, Facts, Threads, Rolling Summary
    ↓
Next Episode → Repeat
```

### LangGraph Episode Workflow

```
START → build_context → write_episode → critique ─┬─ [pass]  → send_to_human → END
                              ↑                    └─ [fail, retries left] → revise ─┘
                              └─────────────────────── [fail, max retries] → send_to_human → END
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **Planner** | Generates full 200-episode arc plan from premise |
| **Context Builder** | Assembles compact layered memory for each episode |
| **Episode Writer** | Generates episode prose + structured metadata |
| **Critic** | Validates consistency, repetition, hooks, human instructions |
| **Reviser** | Rewrites based on critic issues (same Writer, different prompt) |
| **Memory Updater** | Extracts and persists character/fact/thread updates |
| **Human Review Controller** | Gate that holds flow until human approves |

---

## Technology Choices

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend | FastAPI | Async, clean, self-documenting |
| Agent Orchestration | LangGraph | State-machine workflow, supports conditional routing |
| LLM | OpenAI / Anthropic / Google (configurable) | Provider abstraction via env var |
| Database | PostgreSQL | Structured state, JSON columns (JSONB), transactions |
| CLI | Rich + Typer | Optional fallback for the same service methods |
| Web UI | React + TypeScript + Tailwind | Browser workflow for planning, review, memory, and logs |
| Migrations | Alembic | Schema versioning |
| Testing | pytest + pytest-asyncio | Standard, fixtures-based |

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (or use Docker)
- An API key for at least one LLM provider

### Option A: Local (recommended for development)

```bash
# 1. Clone and enter directory
cd "c:\Users\Ashish K\Desktop\Assistment"

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # Linux/Mac

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Set up environment
copy .env.example .env
# Edit .env with your API key and database URL

# 5. Start PostgreSQL (via Docker)
docker compose up -d database

# 6. Initialize database
python -m cli.main init-db
```

### Option B: Full stack with Docker

```bash
copy .env.example .env
# Edit .env and set the LLM API key for your provider

docker compose up --build
```

Then open:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

The Compose network is `frontend` → `backend:8000` → `database:5432`. The backend container uses the hostname `database`, not `localhost`. Alembic runs before Uvicorn, so `python -m cli.main init-db` is not required for this path. The Typer CLI remains available for local debugging.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_PROVIDER` | Yes | `openai` \| `anthropic` \| `google` |
| `LLM_MODEL` | Yes | Model name (e.g., `gpt-4o-mini`) |
| `OPENAI_API_KEY` | If using OpenAI | Your OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Your Anthropic API key |
| `GOOGLE_API_KEY` | If using Google | Your Google API key |
| `DATABASE_URL` | Yes | Async DB URL for FastAPI |
| `DATABASE_URL_SYNC` | Yes | Sync DB URL for CLI |
| `MAX_REVISIONS` | No | Max critic→revise cycles (default: 2) |
| `MAX_COST_PER_EPISODE` | No | Cost budget per episode in USD (default: 0.50) |
| `MAX_TOKENS_PER_EPISODE` | No | Max output tokens (default: 4000) |
| `EPISODE_MIN_WORDS` | No | Minimum episode word count (default: 400) |
| `EPISODE_MAX_WORDS` | No | Maximum episode word count (default: 700) |
| `CORS_ORIGINS` | No | Comma-separated browser origins (default `http://localhost:3000`) |
| `VITE_API_URL` | Frontend build | API base URL the browser calls (default `http://localhost:8000`) |
| `APP_ENV` | No | `production` skips auto table-create; Docker runs Alembic instead |

---

## Database Setup

```bash
# Using Docker (recommended)
docker compose up -d database

# Run Alembic migrations
alembic upgrade head

# Or let the app auto-create tables (development)
python -m cli.main init-db
```

**Schema overview:**

| Table | Purpose |
|-------|---------|
| `stories` | Story metadata and status |
| `story_plans` | Full 200-episode plan (JSONB) |
| `episodes` | Episode content, status, critic results |
| `characters` | Character state (persistent, updated after each episode) |
| `world_facts` | Established world facts (locations, timeline, objects) |
| `open_threads` | Open/resolved story threads |
| `human_feedback` | HITL actions and persistent instructions |
| `memory_summaries` | Rolling and arc summaries |
| `agent_runs` | Observability: tokens, cost, latency per agent call |

---

## How to Run

### Web application

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs

From the UI you can create a story, generate and approve the 200-episode plan, generate and review episodes, edit or reject them, save persistent instructions, inspect memory, read agent logs, resume from the last approved episode, and run the automated demo.

For frontend development without Docker:

```bash
cd frontend
npm install
npm run dev
```

`frontend/.env.example` sets `VITE_API_URL`. The Vite dev server also proxies `/api` to `http://localhost:8000`.

### FastAPI Server

```bash
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### CLI (recommended for HITL workflow)

```bash
# Initialize DB
python -m cli.main init-db

# Create a story
python -m cli.main create --premise "A delivery rider realizes every address on today's route belongs to someone who died in the same building."

# Generate the 200-episode plan
python -m cli.main plan --story-id <ID>

# Review and approve the plan
python -m cli.main approve-plan --story-id <ID>

# Generate next episode (interactive review)
python -m cli.main generate --story-id <ID>

# Add persistent feedback
python -m cli.main feedback --story-id <ID> --episode 5 \
  --instruction "Do not reveal the killer yet"

# View story memory
python -m cli.main memory --story-id <ID>

# View agent logs and costs
python -m cli.main logs --story-id <ID>

# Resume from last approved episode
python -m cli.main resume --story-id <ID>

# List all stories
python -m cli.main list
```

---

## How to Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_episode_generation.py -v

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

Tests use SQLite in-memory for speed. All LLM calls are mocked.

---

## How to Run the Demo

The demo generates 15 episodes with 2 documented HITL interventions:

```bash
python -m cli.main demo --episodes 15
```

**What the demo does:**
1. Creates a story with the canonical premise
2. Generates a 200-episode plan
3. Approves the plan
4. Generates episodes 1–3 and approves them
5. **HITL #1** (after episode 3): `"Do not reveal the killer's identity yet; maintain mystery and suspense"`
6. Generates episodes 4–7 (HITL #1 active in context)
7. **HITL #2** (after episode 7): `"Introduce a new detective character who is skeptical of the protagonist"`
8. Generates episodes 8–15 (both HITL instructions active)
9. Shows final summary with cost, memory state, and active instructions

**Evidence that HITL affects future episodes:**
- The `active_instructions` field in each episode context (logged)
- The critic explicitly checks if human instructions were followed
- The rolling summary reflects the tone changes

---

## HITL Workflow

### Plan Review

```
POST /stories/{id}/plan        → Generate plan
GET  /stories/{id}/plan        → Review plan
PUT  /stories/{id}/plan        → Edit plan  
POST /stories/{id}/plan/approve → Approve plan
```

### Episode Review

After generation, each episode waits in `human_review` status:

```
POST /stories/{id}/episodes/{n}/approve  → Approve + update memory
PUT  /stories/{id}/episodes/{n}          → Edit + save
POST /stories/{id}/episodes/{n}/reject   → Reject + reason
POST /stories/{id}/episodes/{n}/feedback → Add persistent instruction
```

### Feedback Propagation

Feedback given after episode N is stored with `is_active=True`. The `ContextBuilder` retrieves all active instructions for every subsequent episode, inserting them in a `HUMAN INSTRUCTIONS (MUST FOLLOW)` section that the critic also validates.

**Demonstration:**
- Episode 5 feedback: `"Slow down the romance between Arjun and Maya"`
- Episodes 6–200: `ContextBuilder` retrieves this instruction
- Critic scores human_instructions_followed=false → triggers revision if not respected

---

## Memory Architecture

### At Episode 150, the LLM context contains (~3,000–4,500 tokens):

| Layer | Content | Source |
|-------|---------|--------|
| **Long-term** | Full episode 150 plan | `story_plans.episode_plans[150]` |
| **Long-term** | Current arc summary | `story_plans.arc_structure` |
| **Long-term** | All character states | `characters` table |
| **Long-term** | All world facts | `world_facts` table |
| **Long-term** | All open threads | `open_threads` table |
| **Medium-term** | Rolling summary (ep 1–149) | `memory_summaries` |
| **Medium-term** | Last ~24 plot one-liners | approved, non-stale `episodes` |
| **Short-term** | Last 3 episode summaries | `episodes` table |
| **Human** | Active instructions | `human_feedback` |

### What is NOT sent:
- Full text of episodes 1–147
- Full text of any episode older than 3

---

## Consistency Checking

The `CriticAgent` reviews every draft before human review, after **deterministic guards** (empty prose, 400–700 words, hook alignment, plot-beat overlap).

**Checks performed:**
1. Character consistency (personality, goals, status)
2. Relationship consistency
3. Timeline consistency
4. Location/world fact consistency
5. Open-thread continuity
6. Repeated plot beats (last 3 summaries **and** last ~24 one-line beats)
7. Arc plan adherence and word-count range
8. Hook quality (strong/adequate/weak/missing)
9. Human instruction compliance (fail closed if the critic says they were ignored)

**Scoring:**
- Score ≥ 0.7 + no high/critical issues → pass → human review
- Score < 0.7 or high/critical issues → revise (up to `MAX_REVISIONS`)
- Per-episode spend ≥ `MAX_COST_PER_EPISODE` → **no further LLM revisions**; send to human with issues
- After max revisions → human review with detected issues listed

---

## Resume Behavior

The system is fully resumable. Every state is persisted to PostgreSQL.

```bash
# Stop at any point
# Restart later
python -m cli.main resume --story-id <ID>
```

The resume command:
1. Queries `episodes` for the last row with `status=approved` and `is_stale=false`
2. Determines `next_episode = last_approved + 1`
3. Rebuilds context from DB (no in-memory state needed)
4. Calls `generate_next_episode()`

If the app crashes mid-generation, the episode will be in `generating` status. On restart, it is regenerated cleanly.

In-flight **operations** (plan/episode/demo jobs) live in API process memory. A backend restart drops the job tracker; story rows in Postgres remain. Re-queue Generate plan / Generate episode.

---

## Cost Estimation

### Observed token usage (gpt-4o-mini, per episode):

| Agent | Input tokens | Output tokens | Cost |
|-------|-------------|---------------|------|
| Planner | ~12k–40k (batched) | varies | ~$0.02–$0.04 (one-time) |
| Context Builder | (no LLM) | — | $0 |
| Episode Writer | ~2,500 | ~900 | ~$0.0009 |
| Critic | ~1,800 | ~400 | ~$0.0004 |
| Reviser (if needed) | ~1,500 | ~900 | ~$0.0007 |
| Memory Updater | ~1,200 | ~400 | ~$0.0003 |

**Per episode (no revision):** ~$0.0016  
**Per episode (1 revision):** ~$0.0023  
**Per episode (2 revisions):** ~$0.0030  

**Time (unattended, gpt-4o-mini):** planner often 3–8 minutes; one episode with critic ~15–40 seconds. Two hundred episodes ≈ **1.5–3 hours** of model time, plus human review. A 15-episode demo is typically **20–40 minutes**.

### 200-episode total estimate:

| Scenario | Cost | Notes |
|----------|------|------|
| Best case (no revisions) | ~$0.40–$0.70 | Plus planner |
| Typical (30% revision rate) | ~$0.50–$0.80 | |
| Worst case (all max revisions) | ~$0.70–$1.00 | Still under default $0.50 **per episode** cap |
| **Planner + all 200 episodes** | **about $0.50–$1.00** on gpt-4o-mini | GPT-4-class models are ~20–30× |

**Bound:** `MAX_COST_PER_EPISODE` (default `$0.50`) stops further writer/critic revisions for that episode once cumulative logged spend hits the cap. `MAX_REVISIONS` (default 2) is the other stop. `MAX_TOKENS_PER_EPISODE` caps completion length.

### Cost reduction strategies:

1. **Smaller model for critic / memory updater**
2. **Keep memory compact** (thread/fact lists already truncated in prompts)
3. **Do not send full episode history** (already the default)
4. **Skip a second revision** when the remaining issues are low severity
5. **Human-edit** instead of burning two reviser calls

---

## Retroactive Edit Support

When a human edits episode 40 (or clicks **Reconcile later episodes**):

1. The edit is saved; `human_edited=True`; memory updater runs on that episode
2. Episodes 41+ that were approved are marked `is_stale=True`
3. `current_episode` is set to 40
4. **Next generate skips stale tips:** last canonical approved is 40, so episode 41 is rewritten
5. `POST /api/stories/{id}/reconcile` with `{ "from_episode": 40 }` does the stale marking explicitly

**Supported:** Detection, marking, resume-from-canonical, sequential rewrite of stale numbers  
**Not automatic:** Replaying memory from episodes 1–39 from scratch (would be a future `replay` job)

---

## Limitations

1. **LLM hallucination**: The critic reduces but does not eliminate subtle contradictions. Human review is required.
2. **Long-range repetition**: Last 3 summaries plus ~24 plot one-liners. Episode 12 vs 110 can still rhyme if the rolling summary forgot the first beat.
3. **Retroactive edits**: 41+ are marked stale and regenerated **in sequence** when you Generate next; they are not rewritten in one batch job.
4. **Memory replay**: Editing episode 40 updates memory from that episode only; facts unique to 41–60 stay until those episodes are rewritten.
5. **Character relationships**: Flat dicts, not a graph.
6. **Rolling summary drift** at episode 150+.
7. **Cost at scale**: GPT-4-class models are ~20–30× gpt-4o-mini.
8. **One generate per story** at a time (lock). Operations queue is in-process.

---

## API architecture

The React app talks only to FastAPI. Routes under `/api` call the existing `StoryService` methods used by the CLI (`create_story`, `generate_plan`, `approve_plan`, `generate_next_episode`, `approve_episode`, `edit_episode`, `reject_episode`, `add_feedback`, `get_memory`, `get_logs`, and the resume point). Agents, memory updates, and cost tracking stay in that service layer.

Long-running plan, episode, and demo work is queued:

```http
POST /api/operations
GET  /api/operations/{operation_id}
```

The same story routes also remain at `/stories/...` without the `/api` prefix.

## Frontend architecture

```text
frontend/src/api        HTTP client and resource calls
frontend/src/pages      Dashboard, stories, workspace tabs, demo
frontend/src/layouts    Sidebar shell
frontend/src/components Shared status, empty, error, and modal UI
```

Story workspace tabs are Overview, Plan, Episodes, Memory, Feedback, and Logs.

## Story generation and HITL

1. Create a story from a premise.
2. Generate the 200-episode plan and approve the draft.
3. Generate the next episode. The writer and critic run in the existing service.
4. Approve, edit, or reject the episode. An edit is stored and approved, and later episodes can be marked stale.
5. Save a persistent instruction. Later episodes receive it the same way as `story-cli feedback`.
6. Resume reports the last approved episode and the next number to generate.

## Troubleshooting

- **Frontend cannot reach the API.** Confirm `VITE_API_URL` points at the host-published API (`http://localhost:8000`) and that `CORS_ORIGINS` includes `http://localhost:3000`.
- **Backend cannot connect to Postgres inside Compose.** `DATABASE_URL` must use host `database`, not `localhost`.
- **Plan or episode request looks stuck.** The UI polls `GET /api/operations/{id}`. Open that URL or the story Logs tab. A failed job stores the error on the operation. Those jobs live in API memory and are cleared when the backend process restarts.
- **Docker build is huge or slow.** The backend image ignores the local virtualenv via `.dockerignore`.
- **Empty story list.** The API is up but no stories have been created. Use Create Story or Run demo.
- **LLM errors.** Set `LLM_PROVIDER` and the matching API key in `.env`. Do not put that key in the React app.

## API Reference

```
GET  /health
POST /stories                           Create story
GET  /stories                           List stories
GET  /stories/{id}                      Get story
POST /stories/{id}/plan                 Generate plan
GET  /stories/{id}/plan                 Get plan
PUT  /stories/{id}/plan                 Edit plan
POST /stories/{id}/plan/approve         Approve plan
POST /stories/{id}/episodes/next        Generate next episode
GET  /stories/{id}/episodes             List episodes
GET  /stories/{id}/episodes/{n}         Get episode
POST /stories/{id}/episodes/{n}/approve Approve episode
PUT  /stories/{id}/episodes/{n}         Edit episode
POST /stories/{id}/episodes/{n}/reject  Reject episode
POST /stories/{id}/episodes/{n}/feedback Add persistent instruction
GET  /stories/{id}/memory               View story memory
GET  /stories/{id}/logs                 View agent logs

Web UI routes (same handlers, `/api` prefix):

GET  /api/dashboard
POST /api/stories
GET  /api/stories
GET  /api/stories/{id}
POST /api/stories/{id}/plan
GET  /api/stories/{id}/plan
POST /api/stories/{id}/plan/approve
POST /api/stories/{id}/episodes/generate
GET  /api/stories/{id}/episodes
GET  /api/stories/{id}/episodes/{n}
POST /api/stories/{id}/episodes/{n}/approve
PUT  /api/stories/{id}/episodes/{n}
POST /api/stories/{id}/episodes/{n}/reject
POST /api/stories/{id}/feedback
GET  /api/stories/{id}/feedback
GET  /api/stories/{id}/memory
GET  /api/stories/{id}/logs?limit=100
POST /api/stories/{id}/resume
POST /api/stories/{id}/reconcile
POST /api/operations
GET  /api/operations/{operation_id}
POST /api/demo
```

Full interactive docs: `http://localhost:8000/docs`
