"""Rich-powered CLI for the Agentic Serial Story Writer.

Provides a full human-in-the-loop interactive interface:
  story-cli create          – Create story from premise
  story-cli plan            – Generate 200-episode plan
  story-cli approve-plan    – Approve the plan
  story-cli generate        – Generate next episode
  story-cli review          – Review + approve/edit/reject episode
  story-cli feedback        – Add persistent instruction
  story-cli memory          – View story memory
  story-cli logs            – View agent run logs
  story-cli resume          – Resume from last completed episode
  story-cli list            – List all stories
  story-cli demo            – Run automated demo
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich import print as rprint

# Bootstrap path so the CLI works from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.db.models import Base, EpisodeStatus, StoryStatus
from app.db.session import SyncSessionLocal, sync_engine
from app.services.sync_story_service import SyncStoryService

app_cli = typer.Typer(
    name="story-cli",
    help="🌙 Agentic Serial Story Writer – Human-in-the-Loop CLI",
    add_completion=False,
    pretty_exceptions_show_locals=False,
)
console = Console()
settings = get_settings()


def _ensure_db():
    """Create tables if they don't exist."""
    Base.metadata.create_all(sync_engine)


def _get_svc(db) -> SyncStoryService:
    return SyncStoryService(db)


def _story_panel(story: dict) -> Panel:
    content = (
        f"[bold]ID:[/bold] {story['id']}\n"
        f"[bold]Title:[/bold] {story.get('title') or '[dim]Not yet planned[/dim]'}\n"
        f"[bold]Status:[/bold] [cyan]{story['status']}[/cyan]\n"
        f"[bold]Episode:[/bold] {story['current_episode']} / {story['total_planned']}\n"
        f"[bold]Premise:[/bold] {story['premise']}"
    )
    return Panel(content, title="[bold magenta]📖 Story[/bold magenta]", border_style="magenta")


def _episode_panel(ep: dict) -> Panel:
    issues_text = ""
    if ep.get("critic_issues"):
        issues_text = "\n\n[bold red]Critic Issues:[/bold red]\n" + "\n".join(
            f"  • [{i.get('severity','?').upper()}] {i.get('type','?')}: {i.get('description','')}"
            for i in ep["critic_issues"]
        )

    stale_warning = ""
    if ep.get("is_stale"):
        stale_warning = f"\n\n[yellow]⚠ STALE: {ep.get('stale_reason', '')}[/yellow]"

    content = (
        f"[bold]Episode {ep['episode_number']}:[/bold] {ep.get('title','')}\n"
        f"[bold]Status:[/bold] [cyan]{ep['status']}[/cyan]  "
        f"[bold]Words:[/bold] {ep.get('word_count', 0)}  "
        f"[bold]Critic score:[/bold] {ep.get('critic_score') or 'N/A'}\n"
        f"[bold]Revisions:[/bold] {ep.get('revision_count', 0)}\n"
        + stale_warning + issues_text
    )
    return Panel(content, title="[bold cyan]📄 Episode Info[/bold cyan]", border_style="cyan")


# ─────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────

@app_cli.command("init-db")
def init_db():
    """Initialize the database (creates all tables)."""
    _ensure_db()
    console.print("[green]✔ Database initialized.[/green]")


@app_cli.command("create")
def create_story(
    premise: Optional[str] = typer.Option(None, "--premise", "-p", help="One-line story premise"),
):
    """Create a new story from a premise."""
    _ensure_db()
    if not premise:
        premise = Prompt.ask(
            "[bold]Enter your story premise[/bold]",
            default="A delivery rider realizes every address on today's route belongs to someone who died in the same building."
        )
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        story = svc.create_story(premise)
    console.print(Panel(
        f"[green]✔ Story created![/green]\n\nID: [bold]{story['id']}[/bold]\nPremise: {premise}",
        title="Story Created", border_style="green"
    ))
    console.print(f"\n[dim]Next: story-cli plan --story-id {story['id']}[/dim]")


@app_cli.command("list")
def list_stories():
    """List all stories."""
    _ensure_db()
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        stories = svc.list_stories()

    if not stories:
        console.print("[yellow]No stories found. Run: story-cli create[/yellow]")
        return

    table = Table(title="📚 All Stories", box=box.ROUNDED, border_style="magenta")
    table.add_column("ID", style="dim", width=36)
    table.add_column("Title", style="bold")
    table.add_column("Status", style="cyan")
    table.add_column("Episode", justify="right")
    table.add_column("Premise", max_width=50)

    for s in stories:
        table.add_row(
            s["id"],
            s.get("title") or "—",
            s["status"],
            str(s["current_episode"]),
            s["premise"],
        )
    console.print(table)


@app_cli.command("plan")
def generate_plan(
    story_id: str = typer.Option(..., "--story-id", "-s", help="Story ID"),
):
    """Generate the 200-episode arc plan."""
    _ensure_db()
    console.print(f"[bold yellow]⚙ Generating 200-episode plan...[/bold yellow] (this may take 30–90 seconds)")

    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        try:
            result = svc.generate_plan(story_id)
        except Exception as e:
            console.print(f"[red]✘ Error: {e}[/red]")
            raise typer.Exit(1)

    console.print(Panel(
        f"[green]✔ Plan generated![/green]\n"
        f"Title: [bold]{result.get('title')}[/bold]\n"
        f"Episodes planned: {result.get('episodes_planned', 0)}\n\n"
        f"[dim]Next: story-cli approve-plan --story-id {story_id}[/dim]\n"
        f"[dim]Or view the plan: story-cli show-plan --story-id {story_id}[/dim]",
        title="Plan Generated", border_style="green"
    ))


@app_cli.command("show-plan")
def show_plan(
    story_id: str = typer.Option(..., "--story-id", "-s"),
    arc: Optional[int] = typer.Option(None, "--arc", "-a", help="Show episodes for specific arc number"),
    episodes: bool = typer.Option(False, "--episodes", "-e", help="Show all episode summaries"),
):
    """Display the story plan."""
    _ensure_db()
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        plan = svc.get_plan(story_id)

    if not plan:
        console.print("[red]No plan found. Run: story-cli plan --story-id ...[/red]")
        raise typer.Exit(1)

    # Arc overview
    console.print(Panel(
        f"[bold]Story Plan[/bold] (v{plan['version']}) – Approved: {'✔' if plan['approved'] else '✘'}\n"
        f"World rules: {len(plan.get('world_rules', []))}\n"
        f"Turning points: {len(plan.get('major_turning_points', []))}",
        title="📋 Plan Overview", border_style="blue"
    ))

    arc_data = plan.get("arc_structure", {})
    if arc_data:
        table = Table(title="Story Arcs", box=box.SIMPLE)
        table.add_column("Arc", justify="center", width=5)
        table.add_column("Title", style="bold")
        table.add_column("Episodes", justify="center")
        table.add_column("Summary", max_width=60)
        for arc_key, arc_info in sorted(arc_data.items(), key=lambda x: int(x[0])):
            if arc and int(arc_key) != arc:
                continue
            table.add_row(
                arc_key,
                arc_info.get("title", ""),
                f"{arc_info.get('episode_start')}–{arc_info.get('episode_end')}",
                arc_info.get("summary", "")[:80],
            )
        console.print(table)

    if episodes or arc:
        ep_plans = plan.get("episode_plans", [])
        if arc:
            ep_plans = [e for e in ep_plans if e.get("arc_number") == arc]
        table = Table(title=f"Episode Plans {'(Arc ' + str(arc) + ')' if arc else ''}", box=box.SIMPLE)
        table.add_column("#", justify="right", width=4)
        table.add_column("Title", style="bold", max_width=35)
        table.add_column("Summary", max_width=60)
        table.add_column("Hook", max_width=40, style="italic")
        for ep in ep_plans[:50]:  # limit display
            table.add_row(
                str(ep.get("episode_number", "")),
                ep.get("title", ""),
                ep.get("summary", "")[:60],
                ep.get("planned_hook", "")[:40],
            )
        console.print(table)
        if len(plan.get("episode_plans", [])) > 50 and not arc:
            console.print(f"[dim](Showing first 50 of {len(plan['episode_plans'])} episodes. Use --arc N to filter.)[/dim]")


@app_cli.command("approve-plan")
def approve_plan(
    story_id: str = typer.Option(..., "--story-id", "-s"),
):
    """Approve the story plan and begin episode generation."""
    _ensure_db()
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        plan = svc.get_plan(story_id)
        if not plan:
            console.print("[red]No plan found.[/red]")
            raise typer.Exit(1)

        console.print(f"\n[bold]Plan has {len(plan.get('episode_plans', []))} episodes across "
                      f"{len(plan.get('arc_structure', {}))} arcs.[/bold]")
        confirmed = Confirm.ask("Approve this plan and begin episode generation?", default=True)
        if not confirmed:
            console.print("[yellow]Plan approval cancelled.[/yellow]")
            raise typer.Exit(0)

        svc.approve_plan(story_id)

    console.print(f"[green]✔ Plan approved! Ready to generate episodes.[/green]")
    console.print(f"[dim]Next: story-cli generate --story-id {story_id}[/dim]")


@app_cli.command("generate")
def generate_episode(
    story_id: str = typer.Option(..., "--story-id", "-s"),
    auto_review: bool = typer.Option(False, "--auto", "-a", help="Skip interactive review (batch mode)"),
):
    """Generate the next episode."""
    _ensure_db()
    console.print("[bold yellow]⚙ Generating episode...[/bold yellow] (30–60 seconds)")

    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        try:
            result = svc.generate_next_episode(story_id)
        except Exception as e:
            console.print(f"[red]✘ Error: {e}[/red]")
            raise typer.Exit(1)

    ep_num = result["episode_number"]
    critic_passed = result.get("critic_passed")
    score = result.get("critic_score")

    status_icon = "✔" if critic_passed else "⚠"
    console.print(Panel(
        f"[green]{status_icon} Episode {ep_num} ready for review![/green]\n"
        f"Critic score: [bold]{score:.2f if score else 'N/A'}[/bold]  "
        f"Passed: [bold]{'✔' if critic_passed else '✘'}[/bold]\n\n"
        f"[dim]Next: story-cli review --story-id {story_id} --episode {ep_num}[/dim]",
        title=f"Episode {ep_num} Generated", border_style="green" if critic_passed else "yellow"
    ))

    if not auto_review:
        review = Confirm.ask("Review this episode now?", default=True)
        if review:
            _review_episode_interactive(story_id, ep_num)


@app_cli.command("review")
def review_episode(
    story_id: str = typer.Option(..., "--story-id", "-s"),
    episode: int = typer.Option(..., "--episode", "-e"),
):
    """Review an episode and approve/edit/reject/give feedback."""
    _ensure_db()
    _review_episode_interactive(story_id, episode)


def _review_episode_interactive(story_id: str, episode_number: int):
    """Interactive episode review loop."""
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        ep = svc.get_episode(story_id, episode_number)

    if not ep:
        console.print(f"[red]Episode {episode_number} not found.[/red]")
        return

    # Show episode info
    console.print(_episode_panel(ep))

    # Show content
    console.rule("Episode Content")
    console.print(Markdown(ep.get("content", "_No content_")))
    console.rule(f"Hook: {ep.get('hook', '')}")

    # Show threads and characters
    if ep.get("characters_present"):
        console.print(f"\n[bold]Characters:[/bold] {', '.join(ep['characters_present'])}")
    if ep.get("threads_opened"):
        console.print(f"[bold]Threads opened:[/bold] {', '.join(ep['threads_opened'])}")
    if ep.get("threads_resolved"):
        console.print(f"[bold]Threads resolved:[/bold] {', '.join(ep['threads_resolved'])}")

    # Action menu
    console.print("\n[bold]Actions:[/bold]")
    console.print("  [1] Approve")
    console.print("  [2] Edit")
    console.print("  [3] Reject")
    console.print("  [4] Give feedback (persistent instruction)")
    console.print("  [5] Skip for now")

    choice = Prompt.ask("Choose action", choices=["1", "2", "3", "4", "5"], default="1")

    with SyncSessionLocal() as db:
        svc = _get_svc(db)

        if choice == "1":
            svc.approve_episode(story_id, episode_number)
            console.print(f"[green]✔ Episode {episode_number} approved. Memory updated.[/green]")

        elif choice == "2":
            console.print("[dim]Enter your edited content (type END on a new line to finish):[/dim]")
            lines = []
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            edited = "\n".join(lines)
            notes = Prompt.ask("Edit notes (optional)", default="")
            svc.edit_episode(story_id, episode_number, edited, notes)
            console.print(f"[green]✔ Episode {episode_number} edited and approved.[/green]")

        elif choice == "3":
            reason = Prompt.ask("Rejection reason")
            svc.reject_episode(story_id, episode_number, reason)
            console.print(f"[yellow]Episode {episode_number} rejected. It will be regenerated.[/yellow]")

        elif choice == "4":
            instruction = Prompt.ask("[bold]Enter persistent instruction[/bold] (will affect all future episodes)")
            result = svc.add_feedback(story_id, episode_number, instruction)
            console.print(Panel(
                f"[green]✔ Instruction stored![/green]\n"
                f"Instruction: [italic]{instruction}[/italic]\n"
                f"Active from: Episode {episode_number + 1} onwards",
                title="Human Instruction Saved", border_style="green"
            ))

            # Also ask if they want to approve after feedback
            if Confirm.ask("Also approve this episode?", default=True):
                svc.approve_episode(story_id, episode_number)
                console.print(f"[green]✔ Episode {episode_number} approved.[/green]")

        elif choice == "5":
            console.print("[dim]Skipped.[/dim]")


@app_cli.command("feedback")
def add_feedback(
    story_id: str = typer.Option(..., "--story-id", "-s"),
    episode: int = typer.Option(..., "--episode", "-e", help="Episode number this feedback follows"),
    instruction: Optional[str] = typer.Option(None, "--instruction", "-i"),
):
    """Add a persistent human instruction for future episodes."""
    _ensure_db()
    if not instruction:
        instruction = Prompt.ask("[bold]Enter your persistent instruction[/bold]")
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        result = svc.add_feedback(story_id, episode, instruction)
    console.print(Panel(
        f"[green]✔ Instruction stored![/green]\n"
        f"[italic]{instruction}[/italic]\n\n"
        f"Will affect: Episode {episode + 1} onwards",
        title="Human Instruction", border_style="green"
    ))


@app_cli.command("memory")
def view_memory(
    story_id: str = typer.Option(..., "--story-id", "-s"),
):
    """View the current story memory state."""
    _ensure_db()
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        memory = svc.get_memory(story_id)

    if memory.get("rolling_summary"):
        console.print(Panel(memory["rolling_summary"], title="📜 Rolling Summary", border_style="blue"))

    # Characters
    if memory.get("characters"):
        table = Table(title="👥 Characters", box=box.SIMPLE)
        table.add_column("Name", style="bold")
        table.add_column("Role")
        table.add_column("Status", style="cyan")
        table.add_column("Current State", max_width=50)
        for c in memory["characters"]:
            table.add_row(c["name"], c.get("role",""), c.get("status",""), c.get("current_state","")[:50])
        console.print(table)

    # World facts
    if memory.get("world_facts"):
        table = Table(title="🌍 World Facts", box=box.SIMPLE)
        table.add_column("Category", style="dim")
        table.add_column("Key", style="bold")
        table.add_column("Value", max_width=60)
        for f in memory["world_facts"]:
            table.add_row(f.get("category",""), f["key"], f["value"][:60])
        console.print(table)

    # Open threads
    if memory.get("open_threads"):
        table = Table(title="🧵 Open Threads", box=box.SIMPLE)
        table.add_column("Importance", justify="center")
        table.add_column("Title", style="bold")
        table.add_column("Description", max_width=60)
        for t in memory["open_threads"]:
            imp = t.get("importance","medium").upper()
            color = {"CRITICAL": "red", "HIGH": "yellow", "MEDIUM": "cyan", "LOW": "dim"}.get(imp, "")
            table.add_row(f"[{color}]{imp}[/{color}]", t["title"], t["description"][:60])
        console.print(table)

    # Active instructions
    if memory.get("active_instructions"):
        console.print(Panel(
            "\n".join(f"• {i}" for i in memory["active_instructions"]),
            title="📌 Active Human Instructions", border_style="yellow"
        ))


@app_cli.command("logs")
def view_logs(
    story_id: str = typer.Option(..., "--story-id", "-s"),
    limit: int = typer.Option(20, "--limit", "-n"),
):
    """View agent execution logs (tokens, cost, latency)."""
    _ensure_db()
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        logs = svc.get_logs(story_id, limit=limit)

    if not logs:
        console.print("[yellow]No logs yet.[/yellow]")
        return

    table = Table(title="📊 Agent Run Logs", box=box.ROUNDED)
    table.add_column("Ep", justify="right", width=4)
    table.add_column("Agent", style="bold", width=16)
    table.add_column("Status", width=8)
    table.add_column("Tokens (in+out)", justify="right", width=14)
    table.add_column("Cost $", justify="right", width=8)
    table.add_column("Latency ms", justify="right", width=10)
    table.add_column("Retries", justify="right", width=7)

    total_cost = 0.0
    total_tokens_in = 0
    total_tokens_out = 0
    for r in logs:
        status_color = "green" if r["status"] == "success" else "red"
        in_t = r.get("input_tokens") or 0
        out_t = r.get("output_tokens") or 0
        cost = r.get("cost") or 0.0
        total_cost += cost
        total_tokens_in += in_t
        total_tokens_out += out_t
        table.add_row(
            str(r.get("episode_number") or "—"),
            r["agent"],
            f"[{status_color}]{r['status']}[/{status_color}]",
            f"{in_t:,}+{out_t:,}",
            f"{cost:.4f}",
            str(r.get("latency_ms") or "—"),
            str(r.get("retry_count", 0)),
        )

    console.print(table)
    console.print(Panel(
        f"Total cost: [bold green]${total_cost:.4f}[/bold green]\n"
        f"Total tokens: [bold]{total_tokens_in:,} input + {total_tokens_out:,} output[/bold]\n"
        f"Runs shown: {len(logs)}",
        title="Cost Summary", border_style="green"
    ))


@app_cli.command("resume")
def resume_story(
    story_id: str = typer.Option(..., "--story-id", "-s"),
):
    """Resume story generation from the last completed episode."""
    _ensure_db()
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        story = svc.get_story(story_id)
        if not story:
            console.print("[red]Story not found.[/red]")
            raise typer.Exit(1)

        last = svc.get_last_approved_episode_number(story_id)

    console.print(Panel(
        f"[bold]Story:[/bold] {story.get('title') or 'Untitled'}\n"
        f"[bold]Status:[/bold] {story['status']}\n"
        f"[bold]Last approved episode:[/bold] {last}\n"
        f"[bold]Next episode to generate:[/bold] {last + 1}",
        title="📍 Resume Point", border_style="blue"
    ))

    confirmed = Confirm.ask(f"Generate episode {last + 1}?", default=True)
    if confirmed:
        generate_episode(story_id=story_id, auto_review=False)


@app_cli.command("episodes")
def list_episodes(
    story_id: str = typer.Option(..., "--story-id", "-s"),
):
    """List all episodes and their status."""
    _ensure_db()
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        eps = svc.list_episodes(story_id)

    if not eps:
        console.print("[yellow]No episodes yet.[/yellow]")
        return

    table = Table(title="📄 Episodes", box=box.ROUNDED)
    table.add_column("#", justify="right", width=4)
    table.add_column("Title", style="bold", max_width=40)
    table.add_column("Status", width=14)
    table.add_column("Words", justify="right", width=6)
    table.add_column("Score", justify="right", width=7)
    table.add_column("Stale")

    for ep in eps:
        status_colors = {
            "approved": "green",
            "human_review": "yellow",
            "rejected": "red",
            "generating": "blue",
            "stale": "dim",
        }
        s = ep["status"]
        color = status_colors.get(s, "white")
        table.add_row(
            str(ep["episode_number"]),
            ep.get("title") or "—",
            f"[{color}]{s}[/{color}]",
            str(ep.get("word_count") or "—"),
            f"{ep['critic_score']:.2f}" if ep.get("critic_score") else "—",
            "⚠" if ep.get("is_stale") else "",
        )

    console.print(table)


@app_cli.command("demo")
def run_demo(
    premise: str = typer.Option(
        "A delivery rider realizes every address on today's route belongs to someone who died in the same building.",
        "--premise", "-p"
    ),
    num_episodes: int = typer.Option(15, "--episodes", "-n", help="How many episodes to generate in demo"),
):
    """Run an automated demo: create story → plan → generate N episodes with 2 HITL interventions."""
    _ensure_db()
    console.rule("[bold magenta]🚀 DEMO: Agentic Serial Story Writer[/bold magenta]")
    console.print(f"[bold]Premise:[/bold] {premise}")
    console.print(f"[bold]Episodes to generate:[/bold] {num_episodes}")
    console.print()

    # Step 1: Create story
    console.print("[bold cyan]Step 1: Creating story...[/bold cyan]")
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        story = svc.create_story(premise)
    story_id = story["id"]
    console.print(f"[green]✔ Story created: {story_id}[/green]")

    # Step 2: Generate plan
    console.print("\n[bold cyan]Step 2: Generating 200-episode plan...[/bold cyan]")
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        plan_result = svc.generate_plan(story_id)
    console.print(f"[green]✔ Plan: {plan_result.get('title')} ({plan_result.get('episodes_planned', 0)} episodes)[/green]")

    # Step 3: Approve plan
    console.print("\n[bold cyan]Step 3: Approving plan (human review)...[/bold cyan]")
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        svc.approve_plan(story_id)
    console.print("[green]✔ Plan approved[/green]")

    # Step 4: Generate first 3 episodes
    for i in range(1, min(4, num_episodes + 1)):
        console.print(f"\n[bold cyan]Step 4.{i}: Generating Episode {i}...[/bold cyan]")
        with SyncSessionLocal() as db:
            svc = _get_svc(db)
            result = svc.generate_next_episode(story_id)
        ep_num = result["episode_number"]
        console.print(f"[green]✔ Episode {ep_num} ready (score={result.get('critic_score', 'N/A')})[/green]")

        with SyncSessionLocal() as db:
            svc = _get_svc(db)
            svc.approve_episode(story_id, ep_num)
        console.print(f"[green]✔ Episode {ep_num} approved[/green]")

    # Step 5: HITL Intervention #1 – after episode 3
    console.print("\n" + "─" * 60)
    console.print("[bold yellow]🧑‍💻 HITL INTERVENTION #1 (after Episode 3)[/bold yellow]")
    instr1 = "Do not reveal the killer's identity yet; maintain mystery and suspense across upcoming episodes."
    console.print(f"[italic]Human instruction: \"{instr1}\"[/italic]")
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        svc.add_feedback(story_id, 3, instr1)
    console.print("[green]✔ Instruction stored – will affect all future episodes[/green]")
    console.print("─" * 60)

    # Step 6: Generate episodes 4–7
    for i in range(4, min(8, num_episodes + 1)):
        console.print(f"\n[bold cyan]Generating Episode {i} (with HITL #1 active)...[/bold cyan]")
        with SyncSessionLocal() as db:
            svc = _get_svc(db)
            result = svc.generate_next_episode(story_id)
        ep_num = result["episode_number"]
        console.print(f"[green]✔ Episode {ep_num} ready[/green]")
        with SyncSessionLocal() as db:
            svc = _get_svc(db)
            svc.approve_episode(story_id, ep_num)
        console.print(f"[green]✔ Episode {ep_num} approved[/green]")

    # Step 7: HITL Intervention #2
    if num_episodes >= 7:
        console.print("\n" + "─" * 60)
        console.print("[bold yellow]🧑‍💻 HITL INTERVENTION #2 (after Episode 7)[/bold yellow]")
        instr2 = "Introduce a new detective character who is skeptical of the protagonist's investigation."
        console.print(f"[italic]Human instruction: \"{instr2}\"[/italic]")
        with SyncSessionLocal() as db:
            svc = _get_svc(db)
            svc.add_feedback(story_id, 7, instr2)
        console.print("[green]✔ Instruction stored – will affect Episode 8 onwards[/green]")
        console.print("─" * 60)

        # Generate remaining episodes with both HITL instructions active
        for i in range(8, num_episodes + 1):
            console.print(f"\n[bold cyan]Generating Episode {i} (with HITL #1 + #2 active)...[/bold cyan]")
            with SyncSessionLocal() as db:
                svc = _get_svc(db)
                result = svc.generate_next_episode(story_id)
            ep_num = result["episode_number"]
            console.print(f"[green]✔ Episode {ep_num} ready[/green]")
            with SyncSessionLocal() as db:
                svc = _get_svc(db)
                svc.approve_episode(story_id, ep_num)
            console.print(f"[green]✔ Episode {ep_num} approved[/green]")

    # Summary
    console.print("\n")
    console.rule("[bold magenta]✅ DEMO COMPLETE[/bold magenta]")
    with SyncSessionLocal() as db:
        svc = _get_svc(db)
        story_final = svc.get_story(story_id)
        logs = svc.get_logs(story_id)
        memory = svc.get_memory(story_id)

    total_cost = sum(r.get("cost") or 0.0 for r in logs)

    console.print(Panel(
        f"[bold]Story ID:[/bold] {story_id}\n"
        f"[bold]Episodes generated:[/bold] {story_final['current_episode']}\n"
        f"[bold]Characters in memory:[/bold] {len(memory.get('characters', []))}\n"
        f"[bold]World facts:[/bold] {len(memory.get('world_facts', []))}\n"
        f"[bold]Open threads:[/bold] {len(memory.get('open_threads', []))}\n"
        f"[bold]Active instructions:[/bold] {len(memory.get('active_instructions', []))}\n"
        f"[bold]Total agent runs:[/bold] {len(logs)}\n"
        f"[bold]Total cost:[/bold] [green]${total_cost:.4f}[/green]\n\n"
        f"[bold]HITL Interventions:[/bold]\n"
        f"  1. After Ep 3: \"Do not reveal the killer's identity yet\"\n"
        f"  2. After Ep 7: \"Introduce a new skeptical detective\"\n\n"
        f"[dim]Run: story-cli logs --story-id {story_id}[/dim]\n"
        f"[dim]Run: story-cli memory --story-id {story_id}[/dim]",
        title="🎉 Demo Summary", border_style="magenta"
    ))


if __name__ == "__main__":
    app_cli()
