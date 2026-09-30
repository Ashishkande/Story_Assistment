"""Build the API test report PDF from the live route contract."""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).with_name("API_Test_Report.pdf")
BASE = "http://localhost:8000"
STORY = "634e82a1-9780-40bc-8b78-fde9b3dbe2f4"


class Report(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(90, 90, 90)
        self.cell(0, 6, "Agentic Serial Story Writer  |  API Test Report", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 160, 60)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def multi_cell(self, w=0, h=None, text="", *args, **kwargs):
        kwargs.setdefault("new_x", "LMARGIN")
        kwargs.setdefault("new_y", "NEXT")
        return super().multi_cell(w, h=h, text=text, *args, **kwargs)

    def h1(self, text: str) -> None:
        self.ln(2)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 8, text)
        self.ln(1)

    def h2(self, text: str) -> None:
        self.ln(1)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(90, 60, 10)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def p(self, text: str) -> None:
        self.set_font("Helvetica", "", 10)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def code(self, text: str) -> None:
        self.set_font("Courier", "", 8)
        self.set_fill_color(245, 243, 238)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 4, text, fill=True)
        self.ln(2)

    def ensure(self, height: float) -> None:
        if self.get_y() + height > self.h - 18:
            self.add_page()


def case(pdf: Report, number: str, title: str, method: str, path: str, purpose: str, pre: str, request: str, status: str, expected: str, fail: str) -> None:
    pdf.ensure(70)
    pdf.h2(f"{number}  {method} {path}")
    pdf.p(title)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 5, "Purpose", new_x="LMARGIN", new_y="NEXT")
    pdf.p(purpose)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "Preconditions", new_x="LMARGIN", new_y="NEXT")
    pdf.p(pre)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "Request", new_x="LMARGIN", new_y="NEXT")
    pdf.code(request)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, f"Expected status: {status}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "Expected response", new_x="LMARGIN", new_y="NEXT")
    pdf.code(expected)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "Expected failure", new_x="LMARGIN", new_y="NEXT")
    pdf.p(fail)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 5, "Tester result:  [ ] Pass    [ ] Fail     Notes: _______________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def build() -> None:
    pdf = Report(format="A4")
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.set_margins(14, 14, 14)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(40, 30, 10)
    pdf.multi_cell(0, 10, "API Test Report")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(0, 7, "Agentic Serial Story Writer\nExpected results for every HTTP API")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(
        0,
        5,
        "Document type: test specification with expected output.\n"
        "Base URL: http://localhost:8000\n"
        "Sample story: 634e82a1-9780-40bc-8b78-fde9b3dbe2f4\n"
        "Date: 29 September 2026\n"
        "Routes are served twice: /api/... for the React UI, and the same handlers without /api.",
    )
    pdf.ln(2)
    pdf.h1("How to execute")
    pdf.p(
        "Run the cases in order. Plan generation and episode generation call the LLM and can take minutes. "
        "Prefer POST /api/operations for those two, then poll GET /api/operations/{id} until status is succeeded or failed. "
        "The synchronous POST /plan and POST /episodes/generate endpoints return the same final payload, but the HTTP call stays open until the agent finishes. "
        "Record Pass only when the status code and the listed JSON fields match."
    )
    pdf.h1("Order of a full story test")
    pdf.p(
        "1. Health and dashboard. 2. Create story. 3. List and get story. "
        "4. Queue a plan (operation type=plan) and poll until succeeded. 5. GET plan. 6. PUT plan. "
        "7. Approve plan (story status becomes active). 8. Resume (next_episode is 1). "
        "9. Queue an episode and poll. 10. List and get the episode. "
        "11. Approve, or edit, or reject. 12. Save feedback. 13. GET memory, feedback, and logs. "
        "14. Optional: POST /api/demo on a fresh premise."
    )
    pdf.p(
        "Known gate: episode generation returns 400 if stories.status is still planning, even when the plan row is approved. "
        "Approve plan sets status to active. The sample row was observed as planning with current_episode 0."
    )

    story = STORY
    case(
        pdf, "API-01", "Service is up.",
        "GET", "/health",
        "Confirm the API process is running before any story call.",
        "Backend is started.",
        f"GET {BASE}/health",
        "200",
        '{\n  "status": "ok",\n  "version": "0.1.0"\n}',
        "Connection refused if Uvicorn is not running. There is no JSON error body in that case.",
    )
    case(
        pdf, "API-02", "Dashboard counts.",
        "GET", "/api/dashboard",
        "Load totals used by the home page.",
        "Database is reachable.",
        f"GET {BASE}/api/dashboard",
        "200",
        "{\n"
        '  "total_stories": 1,\n'
        '  "generating": 1,\n'
        '  "completed": 0,\n'
        '  "episodes_generated": 0,\n'
        '  "recent_stories": [\n'
        "    {\n"
        f'      "id": "{story}",\n'
        '      "title": null,\n'
        '      "premise": "A delivery rider realizes every address...",\n'
        '      "status": "planning",\n'
        '      "current_episode": 0,\n'
        '      "total_planned": 200\n'
        "    }\n"
        "  ],\n"
        '  "recent_activity": []\n'
        "}",
        "500 if Postgres is down. generating counts stories whose status is planning or active.",
    )
    case(
        pdf, "API-03", "Create a story from a premise.",
        "POST", "/api/stories",
        "Insert a story. This does not generate a plan.",
        "Premise length is 10 to 2000 characters.",
        "POST " + BASE + "/api/stories\n"
        "Content-Type: application/json\n\n"
        "{\n"
        '  "premise": "A delivery rider realizes every address on today\'s route belongs to someone who died in the same building."\n'
        "}",
        "201",
        "{\n"
        '  "id": "<uuid>",\n'
        '  "premise": "A delivery rider realizes every address on today\'s route belongs to someone who died in the same building.",\n'
        '  "status": "created"\n'
        "}",
        '422 if premise is shorter than 10 characters:\n{"detail": [{"type": "string_too_short", "loc": ["body", "premise"], ...}]}',
    )
    case(
        pdf, "API-04", "List every story.",
        "GET", "/api/stories",
        "Return the library used by the Stories page.",
        "None. An empty database returns an empty array.",
        f"GET {BASE}/api/stories",
        "200",
        "[\n"
        "  {\n"
        f'    "id": "{story}",\n'
        '    "title": null,\n'
        '    "premise": "<full premise>",\n'
        '    "status": "planning",\n'
        '    "current_episode": 0,\n'
        '    "total_planned": 200,\n'
        '    "created_at": "2026-09-29T11:38:54.305177+00:00",\n'
        '    "updated_at": "2026-09-29T11:38:54.313863+00:00"\n'
        "  }\n"
        "]",
        "200 with [] when no stories exist. Title stays null until a plan is saved.",
    )
    case(
        pdf, "API-05", "Read one story.",
        "GET", "/api/stories/{story_id}",
        "Return story metadata for the workspace header.",
        "Story id exists.",
        f"GET {BASE}/api/stories/{story}",
        "200",
        "{\n"
        f'  "id": "{story}",\n'
        '  "title": "<plan title or null>",\n'
        '  "premise": "<full premise>",\n'
        '  "genre": "<genre or null>",\n'
        '  "tone": "<tone or null>",\n'
        '  "status": "planning",\n'
        '  "current_episode": 0,\n'
        '  "total_planned": 200,\n'
        '  "created_at": "<iso8601>",\n'
        '  "updated_at": "<iso8601>"\n'
        "}",
        '404 {"detail": "Story not found"} for an unknown id.',
    )
    case(
        pdf, "API-06", "Generate the 200-episode plan in the background.",
        "POST", "/api/operations",
        "Queue the planner. The UI uses this instead of waiting on the synchronous plan route.",
        "Story exists. No other plan or episode job is already running for this story_id.",
        "POST " + BASE + "/api/operations\n"
        "Content-Type: application/json\n\n"
        "{\n"
        '  "type": "plan",\n'
        f'  "story_id": "{story}"\n'
        "}",
        "202",
        "{\n"
        '  "id": "<operation-uuid>",\n'
        '  "type": "plan",\n'
        f'  "story_id": "{story}",\n'
        '  "status": "queued",\n'
        '  "message": "Queued",\n'
        '  "result": null,\n'
        '  "error": null,\n'
        '  "created_at": "<iso8601>",\n'
        '  "updated_at": "<iso8601>"\n'
        "}",
        '422 {"detail": "story_id is required"} if story_id is omitted.\n'
        '422 {"detail": "type must be plan, episode, or demo"} for any other type.\n'
        '409 {"detail": "This story already has a generation job running"} if a job for this story is still queued or running.',
    )
    case(
        pdf, "API-07", "Poll a background job until it finishes.",
        "GET", "/api/operations/{operation_id}",
        "Read plan, episode, or demo progress.",
        "operation_id came from API-06, API-13, or API-22. Poll about every 2 seconds.",
        f"GET {BASE}/api/operations/<operation-uuid>",
        "200",
        "While running:\n"
        "{\n"
        '  "status": "running",\n'
        '  "message": "Generating 200-episode plan...",\n'
        '  "result": null,\n'
        '  "error": null\n'
        "}\n\n"
        "When the plan succeeds, status is succeeded and result is:\n"
        "{\n"
        '  "plan_id": "<uuid>",\n'
        '  "title": "<story title>",\n'
        '  "episodes_planned": 200\n'
        "}\n\n"
        "When an episode succeeds, result is:\n"
        "{\n"
        '  "episode_number": 1,\n'
        '  "episode_id": "<uuid>",\n'
        '  "status": "human_review",\n'
        '  "critic_passed": true,\n'
        '  "critic_score": 0.86\n'
        "}",
        '404 {"detail": "Operation not found"} for an unknown id or after the API process restarts.\n'
        'On failure the same 200 body has "status": "failed" and "error" set to the agent or validation message. '
        "A truncated planner response is a failed job, not HTTP 500.",
    )
    case(
        pdf, "API-08", "Generate the plan on the request thread.",
        "POST", "/api/stories/{story_id}/plan",
        "Same planner as API-06, but the HTTP call blocks until the plan is stored.",
        "Story exists. Expect a long response time.",
        f"POST {BASE}/api/stories/{story}/plan",
        "200",
        "{\n"
        '  "plan_id": "<uuid>",\n'
        '  "title": "<story title>",\n'
        '  "episodes_planned": 200\n'
        "}",
        '400 {"detail": "Plan generation failed: ..."} if the model output cannot be parsed or the plan is incomplete.\n'
        '400 {"detail": "Story <id> not found"} if the id does not exist.\n'
        "After success, GET story status is plan_pending_review and title, genre, and tone are filled.",
    )
    case(
        pdf, "API-09", "Read the stored plan.",
        "GET", "/api/stories/{story_id}/plan",
        "Return arcs, world rules, turning points, and all episode outlines.",
        "A plan has been generated for the story.",
        f"GET {BASE}/api/stories/{story}/plan",
        "200",
        "{\n"
        '  "id": "<plan uuid>",\n'
        f'  "story_id": "{story}",\n'
        '  "approved": false,\n'
        '  "version": 2,\n'
        '  "world_rules": ["The building has a dark history..."],\n'
        '  "major_turning_points": ["Alex uncovers the first death..."],\n'
        '  "planned_resolutions": [],\n'
        '  "arc_structure": {\n'
        '    "1": {\n'
        '      "arc_number": 1,\n'
        '      "title": "The First Delivery",\n'
        '      "episode_start": 1,\n'
        '      "episode_end": 20,\n'
        '      "summary": "Alex starts his delivery route..."\n'
        "    }\n"
        "  },\n"
        '  "episode_plans": [\n'
        "    {\n"
        '      "episode_number": 1,\n'
        '      "title": "The Route Begins",\n'
        '      "summary": "Alex Martin embarks on his delivery route...",\n'
        '      "planned_hook": "As Alex leaves the building, he hears a faint whisper...",\n'
        '      "arc_number": 1\n'
        "    }\n"
        "  ],\n"
        '  "created_at": "<iso8601>"\n'
        "}",
        '404 {"detail": "Plan not found"} before the first successful plan.\n'
        "episode_plans length must be 200 and arc_structure must cover episodes 1 through 200.",
    )
    case(
        pdf, "API-10", "Edit plan fields without regenerating.",
        "PUT", "/api/stories/{story_id}/plan",
        "Replace any supplied plan section. Omitted fields stay as they are.",
        "A plan exists.",
        "PUT " + BASE + f"/api/stories/{story}/plan\n"
        "Content-Type: application/json\n\n"
        "{\n"
        '  "world_rules": [\n'
        '    "The building has a dark history that connects all its residents.",\n'
        '    "Ghosts can communicate with the living but cannot physically interact."\n'
        "  ]\n"
        "}",
        "200",
        '{ "status": "updated" }',
        '400 {"detail": "No plan found"} if no plan exists.\n'
        "version increments by 1. approved is not cleared by this update.",
    )
    case(
        pdf, "API-11", "Approve the plan.",
        "POST", "/api/stories/{story_id}/plan/approve",
        "Mark the plan approved and set the story to active so episodes can be generated.",
        "A plan exists.",
        f"POST {BASE}/api/stories/{story}/plan/approve",
        "200",
        "{\n"
        '  "status": "plan approved",\n'
        '  "next": "POST /stories/{story_id}/episodes/next"\n'
        "}",
        "After this call, GET plan has approved true and GET story has status active. "
        "If status is still planning, episode generation will return 400.",
    )
    case(
        pdf, "API-12", "Read the resume point.",
        "POST", "/api/stories/{story_id}/resume",
        "Report the last approved episode and the next number to generate. This does not generate prose.",
        "Story exists.",
        f"POST {BASE}/api/stories/{story}/resume",
        "200",
        "{\n"
        f'  "story_id": "{story}",\n'
        '  "last_approved_episode": 0,\n'
        '  "next_episode": 1,\n'
        '  "status": "active",\n'
        '  "title": "<story title>"\n'
        "}",
        '404 {"detail": "Story <id> not found"} for an unknown id.\n'
        "After episode 1 is approved, last_approved_episode is 1 and next_episode is 2.",
    )
    case(
        pdf, "API-13", "Queue the next episode.",
        "POST", "/api/operations",
        "Write exactly one episode: last approved number plus one.",
        "Plan is approved and story status is active or paused.",
        "POST " + BASE + "/api/operations\n"
        "Content-Type: application/json\n\n"
        "{\n"
        '  "type": "episode",\n'
        f'  "story_id": "{story}"\n'
        "}",
        "202",
        "{\n"
        '  "id": "<operation-uuid>",\n'
        '  "type": "episode",\n'
        f'  "story_id": "{story}",\n'
        '  "status": "queued",\n'
        '  "message": "Queued",\n'
        '  "result": null,\n'
        '  "error": null\n'
        "}",
        "Poll API-07. Failure error when the story is still planning:\n"
        '"Story is not in active state: planning"\n'
        'Also fails with "Story plan has not been approved yet" if approved is false.',
    )
    case(
        pdf, "API-14", "Generate the next episode on the request thread.",
        "POST", "/api/stories/{story_id}/episodes/generate",
        "Same writer and critic as API-13. Also registered as POST /episodes/next.",
        "Plan approved. Story status active or paused. No episode already waiting in human_review for that number.",
        f"POST {BASE}/api/stories/{story}/episodes/generate",
        "200",
        "{\n"
        '  "episode_number": 1,\n'
        '  "episode_id": "<uuid>",\n'
        '  "status": "human_review",\n'
        '  "critic_passed": true,\n'
        '  "critic_score": 0.86\n'
        "}",
        '400 {"detail": "Story is not in active state: planning"}\n'
        '400 {"detail": "Story plan has not been approved yet"}\n'
        '400 {"detail": "Story complete. All 200 episodes generated."} after episode 200 is approved.\n'
        "If episode 1 is already in human_review, the body is "
        '{"episode_number": 1, "status": "already_in_human_review", "episode_id": "<uuid>"} and the model is not called again.',
    )
    case(
        pdf, "API-15", "List generated episodes.",
        "GET", "/api/stories/{story_id}/episodes",
        "Sidebar list. Planned outlines that were never written are not included.",
        "Story id can be any existing or unknown id; an unknown story returns an empty list.",
        f"GET {BASE}/api/stories/{story}/episodes",
        "200",
        "[\n"
        "  {\n"
        '    "episode_number": 1,\n'
        '    "title": "The Route Begins",\n'
        '    "status": "human_review",\n'
        '    "word_count": 612,\n'
        '    "critic_score": 0.86,\n'
        '    "is_stale": false,\n'
        '    "revision_count": 0\n'
        "  }\n"
        "]",
        "200 [] before the first episode is generated. status is one of generating, human_review, approved, rejected, stale.",
    )
    case(
        pdf, "API-16", "Read one generated episode.",
        "GET", "/api/stories/{story_id}/episodes/{episode_number}",
        "Full prose, critic issues, characters, and threads for the review screen.",
        "That episode number has been generated.",
        f"GET {BASE}/api/stories/{story}/episodes/1",
        "200",
        "{\n"
        '  "id": "<uuid>",\n'
        f'  "story_id": "{story}",\n'
        '  "episode_number": 1,\n'
        '  "title": "The Route Begins",\n'
        '  "content": "<400 to 700 words of prose>",\n'
        '  "summary": "<2 to 3 sentences>",\n'
        '  "hook": "<closing hook>",\n'
        '  "status": "human_review",\n'
        '  "word_count": 612,\n'
        '  "revision_count": 0,\n'
        '  "characters_present": ["Alex Martin"],\n'
        '  "facts_introduced": [],\n'
        '  "threads_opened": [],\n'
        '  "threads_resolved": [],\n'
        '  "critic_score": 0.86,\n'
        '  "critic_issues": [\n'
        "    {\n"
        '      "type": "hook",\n'
        '      "severity": "low",\n'
        '      "description": "<issue text>"\n'
        "    }\n"
        "  ],\n"
        '  "critic_passed": true,\n'
        '  "human_edited": false,\n'
        '  "rejection_reason": null,\n'
        '  "is_stale": false,\n'
        '  "stale_reason": null\n'
        "}",
        '404 {"detail": "Episode 1 not found"} if that number has not been generated. Episode plans are not returned by this route.',
    )
    case(
        pdf, "API-17", "Approve an episode and update memory.",
        "POST", "/api/stories/{story_id}/episodes/{episode_number}/approve",
        "Mark the episode approved, set current_episode, and run the memory updater.",
        "The episode exists.",
        f"POST {BASE}/api/stories/{story}/episodes/1/approve",
        "200",
        '{ "status": "approved", "episode_number": 1 }',
        '400 {"detail": "Episode 1 not found"}.\n'
        "After success, GET story current_episode is 1, episode status is approved, and GET memory includes the new summary, characters, facts, and threads.",
    )
    case(
        pdf, "API-18", "Save edited prose and approve it.",
        "PUT", "/api/stories/{story_id}/episodes/{episode_number}",
        "Store human prose, set status approved, and mark later approved episodes stale.",
        "The episode exists. content is required.",
        "PUT " + BASE + f"/api/stories/{story}/episodes/1\n"
        "Content-Type: application/json\n\n"
        "{\n"
        '  "content": "Alex Martin stopped at the first door. A pale mark sat above the number, and someone whispered his name.",\n'
        '  "edit_notes": "Shortened the opening."\n'
        "}",
        "200",
        "{\n"
        '  "status": "edited",\n'
        '  "episode_number": 1,\n'
        '  "word_count": 24\n'
        "}",
        '400 {"detail": "Episode 1 not found"}.\n'
        "422 if content is missing. human_edited becomes true. Later approved episodes get is_stale true.",
    )
    case(
        pdf, "API-19", "Reject an episode.",
        "POST", "/api/stories/{story_id}/episodes/{episode_number}/reject",
        "Mark the episode rejected. The next generate call rewrites the same number and receives this reason.",
        "The episode exists. reason is required.",
        "POST " + BASE + f"/api/stories/{story}/episodes/1/reject\n"
        "Content-Type: application/json\n\n"
        '{ "reason": "The whisper hook is missing from the last paragraph." }',
        "200",
        '{ "status": "rejected", "episode_number": 1 }',
        '400 {"detail": "Episode 1 not found"}.\n'
        "422 if reason is missing. current_episode does not advance.",
    )
    case(
        pdf, "API-20", "Save a persistent instruction for later episodes.",
        "POST", "/api/stories/{story_id}/feedback",
        "Store an instruction that the writer receives from the next episode onward.",
        "Story exists. instruction length is at least 5. episode is the episode this note follows.",
        "POST " + BASE + f"/api/stories/{story}/feedback\n"
        "Content-Type: application/json\n\n"
        "{\n"
        '  "episode": 3,\n'
        '  "instruction": "Do not reveal the killer identity yet. Keep the mystery across later episodes."\n'
        "}",
        "201",
        "{\n"
        '  "id": "<uuid>",\n'
        '  "instruction": "Do not reveal the killer identity yet. Keep the mystery across later episodes.",\n'
        '  "active": true,\n'
        '  "will_affect_episodes": "Episode 4 onwards"\n'
        "}",
        '404 {"detail": "Story not found"}.\n'
        "422 if instruction is shorter than 5 characters.\n"
        "The same payload can be posted to /episodes/{episode_number}/feedback with body {\"instruction\": \"...\"}.",
    )
    case(
        pdf, "API-21", "List feedback rows.",
        "GET", "/api/stories/{story_id}/feedback",
        "Return approvals, edits, rejections, and active instructions.",
        "Story exists.",
        f"GET {BASE}/api/stories/{story}/feedback",
        "200",
        "[\n"
        "  {\n"
        '    "id": "<uuid>",\n'
        '    "episode": 3,\n'
        '    "action": "feedback",\n'
        '    "instruction": "Do not reveal the killer identity yet...",\n'
        '    "rejection_reason": null,\n'
        '    "is_active": true,\n'
        '    "created_at": "<iso8601>"\n'
        "  }\n"
        "]",
        '404 {"detail": "Story not found"}. An existing story with no notes returns [].',
    )
    case(
        pdf, "API-22", "Read story memory.",
        "GET", "/api/stories/{story_id}/memory",
        "Return the layered memory used for the next episode prompt.",
        "None beyond a reachable database. Missing story still returns empty sections.",
        f"GET {BASE}/api/stories/{story}/memory",
        "200",
        "Before any approval:\n"
        "{\n"
        '  "rolling_summary": null,\n'
        '  "characters": [],\n'
        '  "world_facts": [],\n'
        '  "open_threads": [],\n'
        '  "active_instructions": []\n'
        "}\n\n"
        "After episode 1 is approved, characters and world_facts are objects, for example:\n"
        "{\n"
        '  "rolling_summary": "<compressed story so far>",\n'
        '  "characters": [\n'
        '    {"name": "Alex Martin", "role": "protagonist", "status": "alive", "current_state": "<state>"}\n'
        "  ],\n"
        '  "world_facts": [\n'
        '    {"category": "location", "key": "building", "value": "<fact>"}\n'
        "  ],\n"
        '  "open_threads": [\n'
        '    {"title": "<thread>", "description": "<text>", "importance": "high"}\n'
        "  ],\n"
        '  "active_instructions": ["Do not reveal the killer identity yet..."]\n'
        "}",
        "active_instructions contains only rows with is_active true and a non-empty instruction. Approve and reject rows are not instructions.",
    )
    case(
        pdf, "API-23", "Read agent logs and cost totals.",
        "GET", "/api/stories/{story_id}/logs",
        "Return planner, writer, critic, and memory-updater runs.",
        "Story exists. Optional query limit defaults to 100.",
        f"GET {BASE}/api/stories/{story}/logs?limit=20",
        "200",
        "{\n"
        '  "runs": [\n'
        "    {\n"
        '      "id": "<uuid>",\n'
        '      "run_id": "<uuid>",\n'
        '      "episode_number": 1,\n'
        '      "agent": "writer",\n'
        '      "model": "gpt-4o-mini",\n'
        '      "status": "success",\n'
        '      "input_tokens": 1800,\n'
        '      "output_tokens": 900,\n'
        '      "cost": 0.012,\n'
        '      "latency_ms": 4200,\n'
        '      "retry_count": 0,\n'
        '      "created_at": "<iso8601>"\n'
        "    }\n"
        "  ],\n"
        '  "summary": {\n'
        '    "total_cost": 0.012,\n'
        '    "total_input_tokens": 1800,\n'
        '    "total_output_tokens": 900,\n'
        '    "total_tokens": 2700,\n'
        '    "total_runs": 1,\n'
        '    "average_latency_ms": 4200\n'
        "  }\n"
        "}",
        '404 {"detail": "Story not found"}.\n'
        "Totals cover only the runs returned for the requested limit, not runs older than that page.",
    )
    case(
        pdf, "API-24", "Run the automated demo in the background.",
        "POST", "/api/demo",
        "Create a new story, generate and approve a plan, write episodes, and store the two sample instructions. Same body is accepted as POST /api/operations with type demo.",
        "LLM key is configured. episodes is 1 to 30.",
        "POST " + BASE + "/api/demo\n"
        "Content-Type: application/json\n\n"
        "{\n"
        '  "premise": "A delivery rider realizes every address on today\'s route belongs to someone who died in the same building.",\n'
        '  "episodes": 1\n'
        "}",
        "202",
        "Immediate body:\n"
        "{\n"
        '  "id": "<operation-uuid>",\n'
        '  "type": "demo",\n'
        '  "story_id": null,\n'
        '  "status": "queued",\n'
        '  "message": "Queued",\n'
        '  "result": null\n'
        "}\n\n"
        "Poll API-07. Succeeded result:\n"
        "{\n"
        '  "story_id": "<new uuid>",\n'
        '  "title": "<plan title>",\n'
        '  "episodes_generated": [1],\n'
        '  "current_episode": 1,\n'
        '  "characters": 2,\n'
        '  "world_facts": 1,\n'
        '  "open_threads": 1,\n'
        '  "active_instructions": ["Do not reveal the killer\'s identity yet..."],\n'
        '  "interventions": [\n'
        '    {"after_episode": 3, "instruction": "Do not reveal the killer\'s identity yet..."}\n'
        "  ],\n"
        '  "total_runs": 4,\n'
        '  "total_cost": 0.05\n'
        "}",
        "422 if episodes is greater than 30 or premise is shorter than 10 characters. "
        "The first instruction is stored even when fewer than 3 episodes are requested. "
        "The second instruction is stored only when episodes is at least 7.",
    )

    pdf.h1("Legacy paths")
    pdf.p(
        "Every /api/stories route above also exists without the /api prefix, for example POST /stories and GET /stories/{id}/plan. "
        "Expected status and JSON are identical. /health, /api/dashboard, /api/operations, and /api/demo do not have an unprefixed alias except /health."
    )
    pdf.h1("Pass rule")
    pdf.p(
        "A case passes when the HTTP status matches and every field named in the expected body is present with the stated type. "
        "Prose, titles, scores, token counts, and UUIDs will differ between runs. Do not require the sample sentences to match exactly. "
        "A case fails when the status differs, a required field is missing, or episode generation is allowed while the story status is still planning."
    )

    pdf.output(str(OUT))
    print(OUT)


if __name__ == "__main__":
    build()
