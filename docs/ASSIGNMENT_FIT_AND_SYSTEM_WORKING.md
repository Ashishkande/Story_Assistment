# Assignment fit and exact system working

This document answers two questions:

1. Does this application meet the 200-episode agentic serial-writer brief?
2. How does the application actually run, end to end?

**Verdict:** Yes, as a **demonstrable system**, not as 200 finished chapters. It plans all 200 episodes, writes one episode at a time from compact memory, gates the human at plan and episode, stores persistent instructions that apply to later episodes, and resumes from PostgreSQL. It is not a guarantee of perfect consistency at episode 150. The design is built for that scale; quality still depends on memory extraction, the critic, and human review.

---

## 1. Requirements matrix

| Requirement | Status | How it is implemented |
|---|---|---|
| One-line premise in | Met | `POST /api/stories` stores `premise`. Title, genre, and tone come from the planner. |
| Plan the full 200-episode arc | Met | Planner writes an outline (arcs, characters, turning points), then episode outlines in batches of 10. Stored as JSON in `story_plans`. |
| Episodes 400–700 words, sequential | Met in design | Config: `EPISODE_MIN_WORDS` / `EPISODE_MAX_WORDS`. Next episode = last **approved** number + 1. Word count is enforced by prompt + critic, not a hard tokenizer gate. |
| End on a hook | Met in design | Writer must return `hook`; critic flags missing/weak hooks. |
| Consistency: characters, relationships, timeline, threads | Met as architecture | Structured tables + Context Builder. Critic checks drafts. Not a formal knowledge graph; drift is still possible. |
| HITL: approve / edit plan before writing | Met | Status `plan_pending_review`. UI/API: view, edit, approve. Writing is blocked until `approved=true`. |
| HITL: review / edit / reject episode | Met | Status `human_review`. Approve, edit (save + approve), reject with reason. |
| Feedback like “slow down the romance” carries forward | Met | `human_feedback.is_active=true` is injected as `HUMAN INSTRUCTIONS (MUST FOLLOW)` on every later generate. Critic is told to fail if instructions are ignored. |
| Resume after stopping (e.g. episode 12) | Met | All state is in Postgres. `POST /api/stories/{id}/resume` returns last approved and next number. Generate rebuilds context from DB. |
| Meaningful slice, not all 200 in 24h | Met | Demo generates a short run (default 7, CLI can do 15) with two HITL instructions. |
| Observability and cost awareness | Partial | Each agent call logs tokens, cost, latency in `agent_runs`. `MAX_COST_PER_EPISODE` **warns** in logs; it does not abort the call. |
| Output quality | Depends | Hooks and critic notes exist. Empty-content bugs and generic prose have already shown up in real runs. Human review is the quality gate. |

---

## 2. What the application is

A FastAPI + React app (CLI optional) that orchestrates **six agents** around **PostgreSQL**:

| Agent | LLM? | Job |
|---|---|---|
| Planner | Yes | 200-episode outline + per-episode plans |
| Context Builder | No | Assemble a compact prompt from DB memory |
| Episode Writer | Yes | Draft JSON: prose, summary, hook, metadata |
| Critic | Yes | Score consistency / hook / human instructions |
| Reviser | Yes | Same writer, revision prompt, up to `MAX_REVISIONS` (default 2) |
| Memory Updater | Yes | After **approve**, update characters, facts, threads, rolling summary |

LangGraph runs only the episode loop:

```
START → build_context → write_episode → critique
                              ↑              │
                              │         pass → human_review → END
                              │         fail and retries left → revise
                              └──────── fail and max retries → human_review → END
```

The human is **not** a LangGraph interrupt. The graph always ends at `human_review`. The API/UI then wait. Approve/edit/reject happen in `StoryService`.

---

## 3. Exact working: user journey

### 3.1 Create a story

1. UI: Dashboard → Create Story, or `POST /api/stories` with `{ "premise": "..." }`.
2. Row in `stories`: status `created`, `current_episode=0`, `total_planned=200`.
3. No LLM yet.

### 3.2 Generate the 200-episode plan

1. UI header **Generate plan** (or `POST /api/operations` with `type: "plan"`). Long jobs are queued in **process memory** and polled via `GET /api/operations/{id}`.
2. Status → `planning`.
3. **Planner** (`app/agents/planner.py`):
   - Call 1: outline — title, premise, genre, tone, characters, world rules, turning points, arcs (~20 episodes each covering 1–200).
   - Then, per arc, batches of **10 episode outlines**: title, summary, major events, characters, threads, planned hook, arc number.
   - Validates coverage: every episode 1…200 exists, no gaps.
4. Persist:
   - `story_plans` JSON (`arc_structure`, `episode_plans`, world rules, turning points, resolutions).
   - Seed `characters` from the outline.
   - One `agent_runs` row for the planner (aggregated token/cost).
5. Story status → `plan_pending_review`. Writing is blocked until approval.

### 3.3 Human reviews the plan

| Action | Effect |
|---|---|
| View Plan tab | Read arcs and episode list |
| Edit (`PUT /api/stories/{id}/plan`) | Replace JSON fields; version increments |
| Approve | `story_plans.approved=true`, status `active`. Next step is generate episode. |

Without approval, `generate_next_episode` raises: plan not approved.

### 3.4 Generate the next episode (only after last approved)

`next_episode = last_approved_episode_number + 1`.

You cannot skip ahead. Episode 5 is not written until 1–4 are approved (or you never created them; first generate is episode 1).

1. **Context Builder** loads:
   - This episode’s plan + current arc + next 1–2 planned summaries
   - Rolling summary (if any)
   - Last **3 approved** episode summaries + hooks
   - All characters, all world facts, open threads
   - All **active** human instructions
2. If this episode was previously **rejected**, the rejection reason is appended so the writer must not repeat it.
3. Episode row status → `generating`.
4. LangGraph: write → critic → optional revise (max 2) → always `human_review`.
5. Persist title, content, summary, hook, word count, critic score/issues, revision count.
6. Persist each agent call on `agent_runs`.

UI: Episodes tab. Status `human_review`. Critic issues are listed. The human decides.

### 3.5 Human review of an episode

| Action | What happens |
|---|---|
| **Approve** | Status `approved`. `stories.current_episode` = this number. **Memory Updater** runs. Future generate uses this as last approved. |
| **Edit** | New prose saved, word count recast, `human_edited=true`, status approved, memory updater runs on the edited text, later approved episodes marked `is_stale`. |
| **Reject** | Status `rejected`, reason stored. Next **Generate** regenerates **this same number**, with the reason in the writer prompt. |
| **Give feedback** | Instruction stored `is_active=true` for `after_episode=N`. Does **not** rewrite this episode. It appears in context for episode N+1 onward. |

Feedback examples that match the brief: “slow down the romance”, “do not reveal the killer”, “kill off this character”. They are plain text. The writer and critic see them; there is no separate rule engine.

### 3.6 Memory update (only after approve or edit)

`MemoryUpdaterAgent` reads episode **metadata** (title, summary, characters_present, facts, threads) plus current character/thread snapshots. It returns JSON:

- character state / facts / relationships / alive-dead
- new world facts
- threads to open or resolve
- new rolling summary (3–5 sentences)

That is written to `characters`, `world_facts`, `open_threads`, `memory_summaries`.

**Honest gap:** the updater prompt does **not** include the full episode prose. If the writer left `summary` / `facts_introduced` empty, memory can be thin or wrong even when the chapter text is fine.

### 3.7 Resume

Stop the process at any time. State lives in Postgres, not in LangGraph checkpoints.

`POST /api/stories/{id}/resume` returns:

```json
{
  "last_approved_episode": 12,
  "next_episode": 13,
  "status": "active"
}
```

Generate again rebuilds context from tables. If a crash left status `generating`, the next generate retries that number.

**Caveat:** in-memory **operations** (plan/episode/demo jobs) die if the backend process restarts mid-job. Story rows remain; you start a new operation.

### 3.8 Demo (slice for evaluators)

`POST /api/demo` or CLI `python -m cli.main demo`:

1. Create story with the delivery-rider premise (or yours).
2. Generate and **auto-approve** the 200-episode plan.
3. Generate and auto-approve a few episodes.
4. Insert HITL instruction 1 (e.g. do not reveal the killer).
5. Generate more episodes with that instruction in context.
6. Insert HITL instruction 2 (e.g. add a skeptical detective).
7. Generate the rest of the slice.
8. Return story id, costs, memory snapshot.

This proves **propagation**, not a human reading every chapter. For the real HITL path, use the UI and approve/reject yourself.

---

## 4. Memory design (why episode 150 is possible)

The writer never receives episodes 1–147 as full text. At episode 150 the prompt is roughly:

| Layer | Source | Typical size |
|---|---|---|
| Premise, genre, tone | `stories` | small |
| Arc + this episode plan | `story_plans` | one outline |
| Rolling summary | `memory_summaries` | a few sentences covering 1–149 |
| Last 3 summaries + hooks | `episodes` | short-term continuity |
| Character cards | `characters` | all rows |
| World facts | `world_facts` | all active (prompt shows first 10) |
| Open threads | `open_threads` | first 8 in the prompt |
| Human instructions | `human_feedback` | all active |

That is the argument for 200 episodes: **structured compression**, not a growing transcript.

What this does **not** do:

- Embeddings / semantic search (`ENABLE_EMBEDDINGS` is off).
- Detect “episode 12 and 112 have the same beat”.
- Keep unbounded facts in the prompt (lists are truncated).
- Guarantee the rolling summary still contains a detail from episode 17.

---

## 5. Consistency and critic

The critic sees the draft plus compact context (characters, facts, threads, **required hook from the plan**, human instructions) and last-3 summaries.

Pass rule: score ≥ 0.7 and no high/critical issues. Otherwise revise until `MAX_REVISIONS`, then send to the human **with issues attached**.

Empty content now fails as a critical issue (so you do not get fake “Clara wasn’t set up” notes on a blank file). On a real draft, issues like Clara / diary / weak hook are **editorial**, not platform bugs.

---

## 6. Engineering: cost, logs, stack

| Piece | Role |
|---|---|
| FastAPI `StoryService` | Orchestration used by UI and `/stories` |
| LangGraph | Episode write/critique/revise only |
| PostgreSQL | Source of truth |
| `agent_runs` | Per-call tokens, cost, latency |
| Logs tab | Sum of cost and tokens |
| LLM providers | OpenAI / Anthropic / Google via env |
| Docker Compose | frontend :3000, backend :8000, Postgres |

Cost control is **observability plus a warning**, not a hard stop. Token cap `MAX_TOKENS_PER_EPISODE` (default 4000) limits writer output.

---

## 7. How this maps to the evaluation rubric

**Memory and consistency:** Layered DB memory is the right shape for 200 episodes. Weakest links: memory updater not seeing full prose, truncated thread/fact lists, last-3-only repetition, rolling-summary loss.

**HITL:** Plan gate and per-episode gate are the right intervention points. Feedback is stored and re-injected. Critic is asked to enforce it. Enforcement is still an LLM judgment, not a compiler.

**Design reasoning:** No vector DB, no multi-agent debate, no 200-episode single completion. Planner is batched because one JSON of 200 outlines does not fit. Complexity is mostly tables + one graph.

**Output quality:** Prompts demand hooks and 400–700 words. Quality is uneven; critic + human are required. Earlier empty-content persistence was a real failure mode.

**Engineering:** Sequential, resumable via SQL, logs, tests with mocked LLM. Jobs in RAM are a resume hole for in-flight operations.

**Honesty:** See section 8.

---

## 8. Where the system breaks (say this in an evaluation)

1. **Memory is only as good as extraction.** Approve an empty or metadata-poor episode and later context is wrong.
2. **Long-range repetition** is not checked.
3. **Human instructions** can be ignored; critic may miss that.
4. **Word count** is not a hard filter; a 822-word episode can still be stored.
5. **Stale episodes** after a mid-run edit are flagged, not auto-rewritten.
6. **Plan quality at episode 150** is an LLM batch outline, not a simulated playthrough.
7. **Cost cap** does not cancel a run.
8. **One story generate at a time** (lock); no parallel episode writes.
9. **Operations queue** is in-process; restart loses the job tracker, not the DB.
10. **Consistency is statistical**, not proven. Episode 150 “holding up” is a design claim plus human review, not a theorem.

---

## 9. What to show in a review

1. Create story with the delivery-rider premise.
2. Generate plan → show 200 episode rows, arcs, turning points → edit one beat → approve.
3. Generate episode 1 → show critic → approve or reject.
4. After episode 3, add feedback: “Do not reveal the killer yet.”
5. Generate episode 4 → show the instruction in Memory/Feedback and in the writer context (Logs).
6. Stop. Resume. Confirm next episode is last approved + 1.
7. Open Logs: tokens and cost per agent.
8. Optional: Demo for a timed slice with two stacked instructions.

---

## 10. Main code map

| Path | Responsibility |
|---|---|
| `app/agents/planner.py` | 200-episode plan in outline + batches |
| `app/agents/context_builder.py` | Compact prompt from DB |
| `app/agents/episode_writer.py` | Write / revise JSON + prose recovery |
| `app/agents/critic.py` | Consistency / hook / instructions |
| `app/agents/memory_updater.py` | Post-approve memory JSON |
| `app/agents/workflow.py` | LangGraph episode machine |
| `app/services/story_service.py` | Lifecycle, HITL, resume, demo |
| `app/services/operations.py` | Background plan/episode/demo jobs |
| `app/db/models.py` | Stories, plans, episodes, memory, runs |
| `frontend/src/pages/*` | Plan, Episodes, Memory, Feedback, Logs |
| `cli/main.py` | Same flows without the UI |
