# 🧪 Complete API Testing Guide & Specification

> **Project:** Agentic Serial Story Writer  
> **Base URL:** `http://localhost:8000`  
> **Interactive Swagger UI:** `http://localhost:8000/docs`  
> **OpenAPI JSON:** `http://localhost:8000/openapi.json`  
> **Dual Routing Note:** All story endpoints are accessible with the `/api` prefix (e.g. `/api/stories`) as well as the root alias (e.g. `/stories`). Platform and operation routes are mounted at `/api/...`.

---

## Table of Contents

1. [Environment & Test Setup](#1-environment--test-setup)
2. [End-to-End Story Lifecycle Sequence](#2-end-to-end-story-lifecycle-sequence)
3. [Master Test Case Matrix](#3-master-test-case-matrix)
4. [Step-by-Step API Test Cases](#4-step-by-step-api-test-cases)
   - [Phase 1: Diagnostics & Health Checks](#phase-1-diagnostics--health-checks)
   - [Phase 2: Story Creation & Library Management](#phase-2-story-creation--library-management)
   - [Phase 3: 200-Episode Arc Planning](#phase-3-200-episode-arc-planning)
   - [Phase 4: Story Resumption Check](#phase-4-story-resumption-check)
   - [Phase 5: Episode Generation](#phase-5-episode-generation)
   - [Phase 6: Human-in-the-Loop Review Gates (Approve / Edit / Reject)](#phase-6-human-in-the-loop-review-gates-approve--edit--reject)
   - [Phase 7: Human Feedback & Steering Instructions](#phase-7-human-feedback--steering-instructions)
   - [Phase 8: Layered Story Memory Inspection](#phase-8-layered-story-memory-inspection)
   - [Phase 9: Retroactive Edits & Staleness Reconciliation](#phase-9-retroactive-edits--staleness-reconciliation)
   - [Phase 10: Observability, Cost & Agent Execution Logs](#phase-10-observability-cost--agent-execution-logs)
   - [Phase 11: End-to-End Automated Demo](#phase-11-end-to-end-automated-demo)
5. [Common Failure Modes & Debugging Tips](#5-common-failure-modes--debugging-tips)

---

## 1. Environment & Test Setup

### Prerequisites
1. **PostgreSQL Database** running:
   ```bash
   docker compose up -d database
   ```
2. **Environment Variables (`.env`)**:
   Ensure `DATABASE_URL` is set and at least one LLM key (e.g. `OPENAI_API_KEY` or `GEMINI_API_KEY`) is populated.
3. **Start the FastAPI Server**:
   ```bash
   # From the workspace root
   python -m uvicorn app.main:app --reload --port 8000
   ```
4. Verify server is live by visiting `http://localhost:8000/docs` in your browser.

---

## 2. End-to-End Story Lifecycle Sequence

Follow this exact testing order to simulate the true lifecycle of a serial story:

```
[1. GET /health] → Verify server is running
       ↓
[2. GET /api/dashboard] → Read initial dashboard state
       ↓
[3. POST /api/stories] → Create Story with premise (status: 'created')
       ↓
[4. GET /api/stories/{id}] → Verify initial story record
       ↓
[5. POST /api/operations (type: "plan")] → Queue 200-episode plan generation
       ↓
[6. GET /api/operations/{id}] → Poll until plan status is 'succeeded'
       ↓
[7. GET /api/stories/{id}/plan] → Inspect generated 200-episode arc plan
       ↓
[8. PUT /api/stories/{id}/plan] → Optional: Edit world rules or arcs
       ↓
[9. POST /api/stories/{id}/plan/approve] → Approve plan (status moves to 'active')
       ↓
[10. POST /api/stories/{id}/resume] → Check resume point (last_approved: 0, next: 1)
       ↓
[11. POST /api/operations (type: "episode")] → Queue Episode 1 generation
       ↓
[12. GET /api/operations/{id}] → Poll until episode generation succeeds
       ↓
[13. GET /api/stories/{id}/episodes/1] → Inspect prose, critic score, issues, and hook
       ↓
[14. Review Gate (Choose A, B, or C)]:
       ├── (A) POST /api/stories/{id}/episodes/1/approve  → Approve episode
       ├── (B) PUT  /api/stories/{id}/episodes/1          → Edit content & approve
       └── (C) POST /api/stories/{id}/episodes/1/reject   → Reject & request regenerate
       ↓
[15. POST /api/stories/{id}/feedback] → Add persistent instruction for future episodes
       ↓
[16. GET /api/stories/{id}/memory] → Check memory updater (characters, facts, threads)
       ↓
[17. POST /api/stories/{id}/reconcile] → Test retroactive stale marking and rewind
       ↓
[18. GET /api/stories/{id}/logs] → Verify token counts, latencies, and dollar cost
       ↓
[19. POST /api/demo] → Automated multi-episode test with background worker
```

---

## 3. Master Test Case Matrix

| ID | Method | Endpoint | Phase | Expected Status | Description |
|:---|:---|:---|:---|:---|:---|
| **API-01** | `GET` | `/health` | Diagnostics | `200 OK` | Process liveness check |
| **API-02** | `GET` | `/api/dashboard` | Diagnostics | `200 OK` | Dashboard statistics & summary counts |
| **API-03** | `POST` | `/api/stories` | Story Management | `201 Created` | Create new story from 1-line premise |
| **API-04** | `GET` | `/api/stories` | Story Management | `200 OK` | List all library stories |
| **API-05** | `GET` | `/api/stories/{id}` | Story Management | `200 OK` | Fetch detailed story record |
| **API-06** | `POST` | `/api/operations` (`plan`) | Arc Planning | `202 Accepted` | Queue async 200-episode plan job |
| **API-07** | `GET` | `/api/operations/{id}` | Job Tracking | `200 OK` | Poll background worker progress |
| **API-08** | `POST` | `/api/stories/{id}/plan` | Arc Planning | `200 OK` | Synchronous plan generation (blocking) |
| **API-09** | `GET` | `/api/stories/{id}/plan` | Arc Planning | `200 OK` | Read stored 200-episode plan |
| **API-10** | `PUT` | `/api/stories/{id}/plan` | Arc Planning | `200 OK` | Edit plan rules or structure |
| **API-11** | `POST` | `/api/stories/{id}/plan/approve`| Arc Planning | `200 OK` | Approve plan & activate story |
| **API-12** | `POST` | `/api/stories/{id}/resume` | Resumption | `200 OK` | Find canonical last & next episode |
| **API-13** | `POST` | `/api/operations` (`episode`)| Episode Generation| `202 Accepted` | Queue async episode generation |
| **API-14** | `POST` | `/api/stories/{id}/episodes/generate` | Episode Generation| `200 OK` | Synchronous episode generation |
| **API-15** | `GET` | `/api/stories/{id}/episodes` | Episode Review | `200 OK` | List all generated episodes |
| **API-16** | `GET` | `/api/stories/{id}/episodes/{n}`| Episode Review | `200 OK` | Get prose, critic review, metadata |
| **API-17** | `POST` | `/api/stories/{id}/episodes/{n}/approve` | Review Gate | `200 OK` | Approve episode & run memory updater |
| **API-18** | `PUT` | `/api/stories/{id}/episodes/{n}`| Review Gate | `200 OK` | Human-edit prose & mark downstream stale |
| **API-19** | `POST` | `/api/stories/{id}/episodes/{n}/reject` | Review Gate | `200 OK` | Reject episode with rewrite reason |
| **API-20** | `POST` | `/api/stories/{id}/feedback` | Steering | `201 Created` | Add persistent human instruction |
| **API-21** | `GET` | `/api/stories/{id}/feedback` | Steering | `200 OK` | List human instructions & actions |
| **API-22** | `GET` | `/api/stories/{id}/memory` | Layered Memory | `200 OK` | View characters, facts, threads, rolling |
| **API-23** | `POST` | `/api/stories/{id}/reconcile` | Retroactive Edit | `200 OK` | Stale-mark subsequent episodes |
| **API-24** | `GET` | `/api/stories/{id}/logs` | Observability | `200 OK` | Cost, tokens, and agent run timings |
| **API-25** | `POST` | `/api/demo` | End-to-End Demo | `202 Accepted` | Run automated plan + 15 episodes demo |

---

## 4. Step-by-Step API Test Cases

### Phase 1: Diagnostics & Health Checks

#### API-01: Liveness Health Check
* **Method & Path:** `GET /health`
* **Purpose:** Ensure the FastAPI application process is up and accepting HTTP connections.
* **Preconditions:** Server is running.
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/health
  ```
* **PowerShell Command:**
  ```powershell
  Invoke-RestMethod -Uri "http://localhost:8000/health" -Method Get
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "status": "ok",
    "version": "0.1.0"
  }
  ```
* **Validation Checks:**
  - Status code is 200.
  - Body contains `"status": "ok"`.

---

#### API-02: Aggregated Dashboard Metrics
* **Method & Path:** `GET /api/dashboard`
* **Purpose:** Provide high-level dashboard metrics (story count, generating status, completed stories, and recent activity).
* **Preconditions:** Database connection is active.
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/api/dashboard
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "total_stories": 0,
    "generating": 0,
    "completed": 0,
    "episodes_generated": 0,
    "recent_stories": [],
    "recent_activity": []
  }
  ```
* **Validation Checks:**
  - Status code is 200.
  - Response contains numerical fields (`total_stories`, `generating`, `episodes_generated`) and array fields (`recent_stories`, `recent_activity`).

---

### Phase 2: Story Creation & Library Management

#### API-03: Create Story from Premise
* **Method & Path:** `POST /api/stories` *(Alias: `POST /stories`)*
* **Purpose:** Initialize a new serial story record from a raw one-line premise.
* **Preconditions:** Premise must be between 10 and 2000 characters.
* **Request Headers:** `Content-Type: application/json`
* **Request Body:**
  ```json
  {
    "premise": "A night shift subway conductor discovers an abandoned train station that only appears at 3:33 AM."
  }
  ```
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/stories \
    -H "Content-Type: application/json" \
    -d "{\"premise\": \"A night shift subway conductor discovers an abandoned train station that only appears at 3:33 AM.\"}"
  ```
* **PowerShell Command:**
  ```powershell
  $story = Invoke-RestMethod -Uri "http://localhost:8000/api/stories" -Method Post -ContentType "application/json" -Body '{"premise": "A night shift subway conductor discovers an abandoned train station that only appears at 3:33 AM."}'
  $STORY_ID = $story.id
  Write-Host "Created Story ID: $STORY_ID"
  ```
* **Expected Status:** `201 Created`
* **Expected Response Body:**
  ```json
  {
    "id": "e6742517-5421-4d32-9cb1-c85da29f79e8",
    "premise": "A night shift subway conductor discovers an abandoned train station that only appears at 3:33 AM.",
    "status": "created"
  }
  ```
* **Database State Change:**
  - New row in `stories` table with `status = 'created'`, `current_episode = 0`, `total_planned = 200`.
* **Negative Test Cases:**
  - **Premise too short (< 10 chars):**
    `{"premise": "Ghost"}` $\rightarrow$ Returns `422 Unprocessable Entity` with validation detail `string_too_short`.

---

#### API-04: List All Stories
* **Method & Path:** `GET /api/stories` *(Alias: `GET /stories`)*
* **Purpose:** Retrieve all stories in the database for the library and sidebar list.
* **Preconditions:** None.
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/api/stories
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  [
    {
      "id": "e6742517-5421-4d32-9cb1-c85da29f79e8",
      "title": null,
      "premise": "A night shift subway conductor discovers...",
      "status": "created",
      "current_episode": 0,
      "total_planned": 200,
      "created_at": "2026-09-30T12:00:00.000000+00:00",
      "updated_at": "2026-09-30T12:00:00.000000+00:00"
    }
  ]
  ```

---

#### API-05: Get Single Story Record
* **Method & Path:** `GET /api/stories/{story_id}` *(Alias: `GET /stories/{story_id}`)*
* **Purpose:** Fetch detailed story metadata, current episode pointer, and lifecycle status.
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/api/stories/YOUR_STORY_ID
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "id": "YOUR_STORY_ID",
    "title": null,
    "premise": "A night shift subway conductor discovers...",
    "genre": null,
    "tone": null,
    "status": "created",
    "current_episode": 0,
    "total_planned": 200,
    "created_at": "2026-09-30T12:00:00+00:00",
    "updated_at": "2026-09-30T12:00:00+00:00"
  }
  ```
* **Negative Test Cases:**
  - Non-existent UUID $\rightarrow$ Returns `404 Not Found` with `{"detail": "Story not found"}`.

---

### Phase 3: 200-Episode Arc Planning

#### API-06: Queue Background Plan Generation (Recommended)
* **Method & Path:** `POST /api/operations`
* **Purpose:** Queue the long-running LLM Planner agent asynchronously so the HTTP connection does not time out.
* **Preconditions:** Story exists. No active job currently running on this story.
* **Request Body:**
  ```json
  {
    "type": "plan",
    "story_id": "YOUR_STORY_ID"
  }
  ```
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/operations \
    -H "Content-Type: application/json" \
    -d "{\"type\": \"plan\", \"story_id\": \"YOUR_STORY_ID\"}"
  ```
* **PowerShell Command:**
  ```powershell
  $op = Invoke-RestMethod -Uri "http://localhost:8000/api/operations" -Method Post -ContentType "application/json" -Body "{`"type`": `"plan`", `"story_id`": `"$STORY_ID`"}"
  $OP_ID = $op.id
  Write-Host "Queued Operation ID: $OP_ID"
  ```
* **Expected Status:** `202 Accepted`
* **Expected Response Body:**
  ```json
  {
    "id": "OP_UUID",
    "type": "plan",
    "story_id": "YOUR_STORY_ID",
    "status": "queued",
    "message": "Queued",
    "result": null,
    "error": null,
    "created_at": "2026-09-30T12:05:00+00:00",
    "updated_at": "2026-09-30T12:05:00+00:00"
  }
  ```
* **Negative Test Cases:**
  - Submitting another generation while one is running $\rightarrow$ Returns `409 Conflict` with `{"detail": "This story already has a generation job running"}`.
  - Invalid type $\rightarrow$ Returns `422 Unprocessable Entity` with `{"detail": "type must be plan, episode, or demo"}`.

---

#### API-07: Poll Operation Status
* **Method & Path:** `GET /api/operations/{operation_id}`
* **Purpose:** Poll background worker status until generation is complete.
* **Preconditions:** `operation_id` received from API-06, API-13, or API-25.
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/api/operations/YOUR_OPERATION_ID
  ```
* **Expected Status:** `200 OK`
* **While Running Response Body:**
  ```json
  {
    "id": "YOUR_OPERATION_ID",
    "type": "plan",
    "story_id": "YOUR_STORY_ID",
    "status": "running",
    "message": "Generating 200-episode plan...",
    "result": null,
    "error": null
  }
  ```
* **Upon Success Response Body:**
  ```json
  {
    "id": "YOUR_OPERATION_ID",
    "type": "plan",
    "story_id": "YOUR_STORY_ID",
    "status": "succeeded",
    "message": "Finished",
    "result": {
      "plan_id": "PLAN_UUID",
      "title": "Station 33",
      "episodes_planned": 200
    },
    "error": null
  }
  ```
* **Validation Checks:**
  - Status becomes `"succeeded"`.
  - `result.episodes_planned` is `200`.

---

#### API-08: Synchronous Plan Generation (Alternative)
* **Method & Path:** `POST /api/stories/{story_id}/plan` *(Alias: `POST /stories/{story_id}/plan`)*
* **Purpose:** Runs the Planner agent synchronously and holds the connection until the entire 200-episode plan is returned.
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "plan_id": "PLAN_UUID",
    "title": "Station 33",
    "episodes_planned": 200
  }
  ```

---

#### API-09: Get 200-Episode Arc Plan
* **Method & Path:** `GET /api/stories/{story_id}/plan` *(Alias: `GET /stories/{story_id}/plan`)*
* **Purpose:** View full arc structure, world rules, turning points, and episode outlines.
* **Preconditions:** A plan has been generated.
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/api/stories/YOUR_STORY_ID/plan
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body Schema:**
  ```json
  {
    "id": "PLAN_UUID",
    "story_id": "YOUR_STORY_ID",
    "approved": false,
    "version": 1,
    "world_rules": [
      "The station only manifests between 3:33 AM and 3:34 AM.",
      "Any passenger boarding the ghost train forgets their destination."
    ],
    "major_turning_points": [
      "Episode 50: The conductor discovers his own name on a 1920 manifest."
    ],
    "planned_resolutions": [],
    "arc_structure": {
      "1": {
        "arc_number": 1,
        "title": "The First Arrival",
        "episode_start": 1,
        "episode_end": 20,
        "summary": "Initial sightings and discovery."
      }
    },
    "episode_plans": [
      {
        "episode_number": 1,
        "title": "The 3:33 Signal",
        "summary": "Conductor Marcus notices red track lights flickering in an abandoned spur line.",
        "characters_involved": ["Marcus Kane"],
        "threads_opened": ["The 3:33 signal glitch"],
        "threads_resolved": [],
        "planned_hook": "Marcus opens the cab door to silence, stepping onto platform tiles coated in antique dust.",
        "arc_number": 1
      }
    ],
    "created_at": "2026-09-30T12:06:00+00:00"
  }
  ```
* **Validation Checks:**
  - `episode_plans` contains 200 outline entries.
  - `approved` is initially `false`.

---

#### API-10: Edit Plan (Human Intervention)
* **Method & Path:** `PUT /api/stories/{story_id}/plan` *(Alias: `PUT /stories/{story_id}/plan`)*
* **Purpose:** Human overrides or refines world rules, turning points, or episode outlines prior to approval.
* **Request Body:**
  ```json
  {
    "world_rules": [
      "The station only manifests between 3:33 AM and 3:34 AM.",
      "Time moves twice as slow while standing on Platform 4."
    ]
  }
  ```
* **cURL Command:**
  ```bash
  curl -X PUT http://localhost:8000/api/stories/YOUR_STORY_ID/plan \
    -H "Content-Type: application/json" \
    -d "{\"world_rules\": [\"The station only manifests between 3:33 AM and 3:34 AM.\", \"Time moves twice as slow while standing on Platform 4.\"]}"
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "status": "updated"
  }
  ```
* **Database State Change:**
  - `plans.version` is incremented.
  - `plans.world_rules` updated.

---

#### API-11: Approve Plan
* **Method & Path:** `POST /api/stories/{story_id}/plan/approve` *(Alias: `POST /stories/{story_id}/plan/approve`)*
* **Purpose:** Human approves the arc plan, locking the blueprint and unlocking episode generation.
* **Preconditions:** Plan exists for this story.
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/stories/YOUR_STORY_ID/plan/approve
  ```
* **PowerShell Command:**
  ```powershell
  Invoke-RestMethod -Uri "http://localhost:8000/api/stories/$STORY_ID/plan/approve" -Method Post
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "status": "plan approved",
    "next": "POST /stories/{story_id}/episodes/next"
  }
  ```
* **Critical Database State Verification:**
  - `plans.approved` becomes `true`.
  - `stories.status` shifts from `plan_pending_review` $\rightarrow$ `active`.
  - *Note:* If story status is not `active`, subsequent episode generation will fail with HTTP 400.

---

### Phase 4: Story Resumption Check

#### API-12: Read Story Resume Point
* **Method & Path:** `POST /api/stories/{story_id}/resume`
* **Purpose:** Determine the exact canonical continuation point without writing prose. Used by client apps to resume after pause/interruption.
* **Preconditions:** Story exists.
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/stories/YOUR_STORY_ID/resume
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body (Initial Before Any Episodes):**
  ```json
  {
    "story_id": "YOUR_STORY_ID",
    "last_approved_episode": 0,
    "next_episode": 1,
    "status": "active",
    "title": "Station 33"
  }
  ```
* **Validation Checks:**
  - `last_approved_episode` is 0.
  - `next_episode` is 1.

---

### Phase 5: Episode Generation

#### API-13: Queue Next Episode Generation (Background)
* **Method & Path:** `POST /api/operations`
* **Purpose:** Runs the LangGraph multi-agent episode workflow (Context Builder $\rightarrow$ Episode Writer $\rightarrow$ Consistency Critic $\rightarrow$ Optional Reviser) in the background.
* **Preconditions:** Plan is approved, story status is `active`.
* **Request Body:**
  ```json
  {
    "type": "episode",
    "story_id": "YOUR_STORY_ID"
  }
  ```
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/operations \
    -H "Content-Type: application/json" \
    -d "{\"type\": \"episode\", \"story_id\": \"YOUR_STORY_ID\"}"
  ```
* **PowerShell Command:**
  ```powershell
  $epOp = Invoke-RestMethod -Uri "http://localhost:8000/api/operations" -Method Post -ContentType "application/json" -Body "{`"type`": `"episode`", `"story_id`": `"$STORY_ID`"}"
  Write-Host "Episode Op ID: $($epOp.id)"
  # Poll until finished:
  do {
      Start-Sleep -Seconds 3
      $poll = Invoke-RestMethod -Uri "http://localhost:8000/api/operations/$($epOp.id)" -Method Get
      Write-Host "Status: $($poll.status) - $($poll.message)"
  } while ($poll.status -eq "running" -or $poll.status -eq "queued")
  ```
* **Expected Status:** `202 Accepted`
* **Poll (API-07) Succeeded Response:**
  ```json
  {
    "status": "succeeded",
    "result": {
      "episode_number": 1,
      "episode_id": "EPISODE_UUID",
      "status": "human_review",
      "critic_passed": true,
      "critic_score": 0.88
    }
  }
  ```

---

#### API-14: Generate Next Episode (Synchronous)
* **Method & Path:** `POST /api/stories/{story_id}/episodes/generate` *(Alias: `POST /stories/{story_id}/episodes/next`)*
* **Purpose:** Synchronous endpoint to generate the next sequential episode.
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "episode_number": 1,
    "episode_id": "EPISODE_UUID",
    "status": "human_review",
    "critic_passed": true,
    "critic_score": 0.88
  }
  ```
* **Edge Case - Already in Human Review:**
  If Episode 1 has already been generated but not approved, calling this again does NOT re-bill or overwrite. It safely returns:
  ```json
  {
    "episode_number": 1,
    "status": "already_in_human_review",
    "episode_id": "EPISODE_UUID"
  }
  ```

---

#### API-15: List Generated Episodes
* **Method & Path:** `GET /api/stories/{story_id}/episodes` *(Alias: `GET /stories/{story_id}/episodes`)*
* **Purpose:** Fetch summary list of all generated episodes for navigation.
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/api/stories/YOUR_STORY_ID/episodes
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  [
    {
      "episode_number": 1,
      "title": "The 3:33 Signal",
      "status": "human_review",
      "word_count": 584,
      "critic_score": 0.88,
      "is_stale": false,
      "revision_count": 0
    }
  ]
  ```

---

#### API-16: Get Episode Detail & Critic Feedback
* **Method & Path:** `GET /api/stories/{story_id}/episodes/{episode_number}`
* **Purpose:** Inspect full generated prose, synopsis, hook, characters present, facts introduced, threads opened, and critic issues.
* **Preconditions:** Episode number has been generated.
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/api/stories/YOUR_STORY_ID/episodes/1
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "id": "EPISODE_UUID",
    "story_id": "YOUR_STORY_ID",
    "episode_number": 1,
    "title": "The 3:33 Signal",
    "content": "Marcus Kane gripped the throttle...",
    "summary": "Marcus halts train 44 at the mysterious spur...",
    "hook": "Beyond the rusted gate, a station clock ticked in reverse.",
    "status": "human_review",
    "word_count": 584,
    "revision_count": 0,
    "characters_present": ["Marcus Kane"],
    "facts_introduced": ["Train 44 has an analog speedometer"],
    "threads_opened": ["The backwards ticking clock"],
    "threads_resolved": [],
    "critic_score": 0.88,
    "critic_issues": [],
    "critic_passed": true,
    "human_edited": false,
    "rejection_reason": null,
    "is_stale": false,
    "stale_reason": null,
    "created_at": "2026-09-30T12:10:00+00:00",
    "updated_at": "2026-09-30T12:10:00+00:00"
  }
  ```
* **Negative Test Cases:**
  - Requesting Episode 99 when only 1 is generated $\rightarrow$ `404 Not Found` with `{"detail": "Episode 99 not found"}`.

---

### Phase 6: Human-in-the-Loop Review Gates (Approve / Edit / Reject)

#### API-17: Approve Episode (Path A)
* **Method & Path:** `POST /api/stories/{story_id}/episodes/{episode_number}/approve`
* **Purpose:** Human approves episode. **Triggers the Memory Updater agent** in the background to update character dossiers, world facts, open threads, and the rolling summary. Advances `current_episode`.
* **Preconditions:** Episode exists.
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/stories/YOUR_STORY_ID/episodes/1/approve
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "status": "approved",
    "episode_number": 1
  }
  ```
* **Database State Change:**
  - `episodes.status` becomes `'approved'`.
  - `stories.current_episode` advances to `1`.
  - `characters`, `world_facts`, `open_threads`, `memory_summaries` updated.

---

#### API-18: Human-Edit Episode Prose (Path B)
* **Method & Path:** `PUT /api/stories/{story_id}/episodes/{episode_number}`
* **Purpose:** Human rewrites or edits prose. Saves the new text, marks `human_edited = true`, auto-approves the episode, and **automatically marks all subsequent approved episodes as stale**.
* **Request Body:**
  ```json
  {
    "content": "Marcus Kane gripped the dead-man switch. Ahead on Track 3, the signal lamp glowed an unnatural violet.",
    "edit_notes": "Strengthened the atmospheric opening"
  }
  ```
* **cURL Command:**
  ```bash
  curl -X PUT http://localhost:8000/api/stories/YOUR_STORY_ID/episodes/1 \
    -H "Content-Type: application/json" \
    -d "{\"content\": \"Marcus Kane gripped the dead-man switch. Ahead on Track 3, the signal lamp glowed an unnatural violet.\", \"edit_notes\": \"Strengthened opening\"}"
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "status": "edited",
    "episode_number": 1,
    "word_count": 18
  }
  ```
* **Validation Checks:**
  - `human_edited` is set to `true`.
  - `word_count` recalculates accurately.

---

#### API-19: Reject Episode (Path C)
* **Method & Path:** `POST /api/stories/{story_id}/episodes/{episode_number}/reject`
* **Purpose:** Human rejects the draft with a specific feedback reason. The episode status becomes `rejected`. On the next generate call, the writer receives this rejection reason and rewrites the episode.
* **Request Body:**
  ```json
  {
    "reason": "The tone is too comedic. Marcus should feel genuinely unsettled by the empty station."
  }
  ```
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/stories/YOUR_STORY_ID/episodes/1/reject \
    -H "Content-Type: application/json" \
    -d "{\"reason\": \"The tone is too comedic. Marcus should feel unsettled.\"}"
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "status": "rejected",
    "episode_number": 1
  }
  ```
* **Validation Checks:**
  - `episodes.status` becomes `rejected`.
  - `episodes.rejection_reason` stores the feedback text.
  - Story `current_episode` does NOT advance.

---

### Phase 7: Human Feedback & Steering Instructions

#### API-20: Save Persistent Story Instruction
* **Method & Path:** `POST /api/stories/{story_id}/feedback` *(Alias: `POST /api/stories/{story_id}/episodes/{n}/feedback`)*
* **Purpose:** Submit a persistent instruction that injects into all future episode contexts.
* **Preconditions:** Instruction must be $\ge 5$ characters. `episode` is the episode after which it takes effect.
* **Request Body:**
  ```json
  {
    "episode": 1,
    "instruction": "Maintain a slow-burn psychological horror mystery; do not introduce monsters or physical entities yet."
  }
  ```
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/stories/YOUR_STORY_ID/feedback \
    -H "Content-Type: application/json" \
    -d "{\"episode\": 1, \"instruction\": \"Maintain a slow-burn psychological horror mystery; do not introduce monsters yet.\"}"
  ```
* **Expected Status:** `201 Created`
* **Expected Response Body:**
  ```json
  {
    "id": "FEEDBACK_UUID",
    "instruction": "Maintain a slow-burn psychological horror mystery; do not introduce monsters yet.",
    "active": true,
    "will_affect_episodes": "Episode 2 onwards"
  }
  ```

---

#### API-21: List Story Feedback & Human Actions
* **Method & Path:** `GET /api/stories/{story_id}/feedback`
* **Purpose:** Audit all human interventions, approvals, edits, rejections, and steering instructions.
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/api/stories/YOUR_STORY_ID/feedback
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  [
    {
      "id": "FEEDBACK_UUID",
      "episode": 1,
      "action": "feedback",
      "instruction": "Maintain a slow-burn psychological horror mystery...",
      "rejection_reason": null,
      "is_active": true,
      "created_at": "2026-09-30T12:15:00+00:00"
    }
  ]
  ```

---

### Phase 8: Layered Story Memory Inspection

#### API-22: View Layered Story Memory
* **Method & Path:** `GET /api/stories/{story_id}/memory`
* **Purpose:** Inspect the layered memory assembled for upcoming episodes (rolling summary, character states, world facts, open threads, active instructions).
* **cURL Command:**
  ```bash
  curl -X GET http://localhost:8000/api/stories/YOUR_STORY_ID/memory
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "rolling_summary": "Conductor Marcus stopped train 44 at an unregistered platform at 3:33 AM...",
    "characters": [
      {
        "name": "Marcus Kane",
        "role": "protagonist",
        "personality": "Observant, cautious veteran conductor",
        "goals": ["Understand the ghost station signal", "Keep passengers safe"],
        "relationships": {},
        "current_state": "Disturbed by the reversed clock",
        "important_facts": ["15 years seniority on the night route"],
        "character_arc": "Skeptic to seeker",
        "status": "alive",
        "first_appeared": 1
      }
    ],
    "world_facts": [
      {
        "category": "supernatural",
        "key": "signal_timing",
        "value": "Station 33 only materializes between 3:33 AM and 3:34 AM"
      }
    ],
    "open_threads": [
      {
        "title": "The backwards ticking clock",
        "description": "Platform 4 has an antique brass clock that ticks backward.",
        "thread_type": "mystery",
        "importance": "high",
        "episode_introduced": 1
      }
    ],
    "active_instructions": [
      "Maintain a slow-burn psychological horror mystery; do not introduce monsters yet."
    ]
  }
  ```
* **Validation Checks:**
  - `active_instructions` contains active feedback.
  - Characters, facts, and open threads are accurately updated after approval.

---

### Phase 9: Retroactive Edits & Staleness Reconciliation

#### API-23: Reconcile After Retroactive Edit
* **Method & Path:** `POST /api/stories/{story_id}/reconcile`
* **Purpose:** When an earlier episode (e.g. Episode 2) is revised after Episode 5 is already generated, mark all subsequent episodes (3, 4, 5) as `is_stale = true` and rewind the canonical pointer to Episode 2.
* **Preconditions:** `from_episode` must exist ($\ge 1$).
* **Request Body:**
  ```json
  {
    "from_episode": 1
  }
  ```
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/stories/YOUR_STORY_ID/reconcile \
    -H "Content-Type: application/json" \
    -d "{\"from_episode\": 1}"
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "from_episode": 1,
    "stale_episodes": [],
    "last_canonical_episode": 1,
    "next_episode": 2,
    "note": "Generate next to rewrite stale episodes in order. Memory was last updated from the canonical episode."
  }
  ```
* **Validation Checks:**
  - Any approved episodes with `episode_number > from_episode` get `is_stale = true`.
  - Next call to generate begins cleanly from `from_episode + 1`.

---

### Phase 10: Observability, Cost & Agent Execution Logs

#### API-24: Agent Run Execution Logs & Cost Analysis
* **Method & Path:** `GET /api/stories/{story_id}/logs?limit=50`
* **Purpose:** Inspect detailed metrics for every agent invocation (planner, writer, critic, reviser, memory_updater), including model names, prompt/completion tokens, latency (ms), and calculated dollar costs.
* **Query Parameters:** `limit` (int, default: 100).
* **cURL Command:**
  ```bash
  curl -X GET "http://localhost:8000/api/stories/YOUR_STORY_ID/logs?limit=50"
  ```
* **Expected Status:** `200 OK`
* **Expected Response Body:**
  ```json
  {
    "runs": [
      {
        "id": "RUN_UUID",
        "run_id": "BATCH_UUID",
        "episode_number": 1,
        "agent": "writer",
        "model": "gpt-4o-mini",
        "status": "success",
        "input_tokens": 1420,
        "output_tokens": 680,
        "cost": 0.00045,
        "latency_ms": 3200,
        "retry_count": 0,
        "created_at": "2026-09-30T12:09:50+00:00"
      },
      {
        "id": "RUN_UUID_2",
        "run_id": "BATCH_UUID",
        "episode_number": 1,
        "agent": "critic",
        "model": "gpt-4o-mini",
        "status": "success",
        "input_tokens": 980,
        "output_tokens": 210,
        "cost": 0.00018,
        "latency_ms": 1450,
        "retry_count": 0,
        "created_at": "2026-09-30T12:09:55+00:00"
      }
    ],
    "summary": {
      "total_cost": 0.00063,
      "total_input_tokens": 2400,
      "total_output_tokens": 890,
      "total_tokens": 3290,
      "total_runs": 2,
      "average_latency_ms": 2325
    }
  }
  ```
* **Validation Checks:**
  - Token counts are non-zero.
  - Latency is recorded in milliseconds.
  - `summary.total_cost` accurately sums the individual runs.

---

### Phase 11: End-to-End Automated Demo

#### API-25: Automated End-to-End Demo Run
* **Method & Path:** `POST /api/demo`
* **Purpose:** Runs the complete turnkey workflow: generates a story, builds and approves the 200-episode plan, writes episodes 1 through 15 sequentially, injects human instructions after episode 3 and episode 7, and updates story memory.
* **Preconditions:** LLM key is configured. `episodes` is between 1 and 30.
* **Request Body:**
  ```json
  {
    "premise": "A delivery rider realizes every address on today's route belongs to someone who died in the same building.",
    "episodes": 3
  }
  ```
* **cURL Command:**
  ```bash
  curl -X POST http://localhost:8000/api/demo \
    -H "Content-Type: application/json" \
    -d "{\"premise\": \"A delivery rider realizes every address belongs to someone who died in the building.\", \"episodes\": 3}"
  ```
* **Expected Status:** `202 Accepted`
* **Immediate Response Body:**
  ```json
  {
    "id": "DEMO_OPERATION_UUID",
    "type": "demo",
    "story_id": null,
    "status": "queued",
    "message": "Queued",
    "result": null
  }
  ```
* **Polling `GET /api/operations/{id}` Succeeded Response:**
  ```json
  {
    "status": "succeeded",
    "result": {
      "story_id": "NEW_DEMO_STORY_UUID",
      "title": "The Dead Route",
      "episodes_generated": [1, 2, 3],
      "current_episode": 3,
      "characters": 3,
      "world_facts": 2,
      "open_threads": 2,
      "active_instructions": [
        "Do not reveal the killer's identity yet; maintain mystery and suspense across upcoming episodes."
      ],
      "interventions": [
        {
          "after_episode": 3,
          "instruction": "Do not reveal the killer's identity yet; maintain mystery and suspense across upcoming episodes."
        }
      ],
      "total_runs": 8,
      "total_cost": 0.042
    }
  }
  ```

---

## 5. Common Failure Modes & Debugging Tips

| Symptom | Cause | Solution |
|:---|:---|:---|
| `400 "Story is not in active state: planning"` | Attempted to generate an episode before approving the plan. | Call `POST /api/stories/{id}/plan/approve` first. |
| `400 "Story plan has not been approved yet"` | `plans.approved` is still false. | Approve plan via `POST /api/stories/{id}/plan/approve`. |
| `409 "This story already has a generation job running"` | An in-process operation lock is active for this `story_id`. | Wait for the previous job to finish or restart the server to clear memory locks. |
| `422 "string_too_short"` on premise or feedback | Provided string didn't meet minimum length (premise $\ge 10$, feedback $\ge 5$). | Provide descriptive text matching minimum character length. |
| Operation status `failed` with model error | API key missing, quota exceeded, or LLM rate-limit hit. | Check `.env` for `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GEMINI_API_KEY`. Inspect `error` key in `GET /api/operations/{id}`. |
| `500 Internal Server Error` on DB calls | PostgreSQL is down or connection string is invalid. | Run `docker compose up -d database` and check `DATABASE_URL` in `.env`. |
