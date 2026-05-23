"""
orchestrator.main
=================

CLI entry point. Wires the stages together.

Usage:

    # 1. Run preflight checks first. Validates everything cheaply.
    python -m orchestrator preflight

    # 2. Dry-run the full Tier 2 pipeline. No money spent.
    python -m orchestrator botb --tier 2 --dry-run

    # 3. Real Tier 2 run. ~60 minutes wallclock, ~$75-110 spend.
    python -m orchestrator botb --tier 2

    # 4. Resume a crashed run from wherever it left off.
    python -m orchestrator botb --tier 2 --resume

    # 5. Run only a specific stage (useful for re-running with tweaks).
    python -m orchestrator botb --tier 2 --stage draft

    # 6. Inspect what's happened so far.
    python -m orchestrator status
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable

from rich.console import Console
from rich.table import Table

from .config import Settings, load_settings
from .preflight import run_preflight
from .stages import dossiers, draft, polish, publish, redteam, research, revise
from .state import StateStore

console = Console()

# Map stage names -> async run() functions, in execution order.
_STAGES: dict[str, Callable[[Settings, StateStore], Awaitable[Any]]] = {
    "research": research.run,
    "dossiers": dossiers.run,
    "draft": draft.run,
    "redteam": redteam.run,
    "revise": revise.run,
    "polish": polish.run,
    "publish": publish.run,
}

_STAGE_ORDER = list(_STAGES.keys())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def cmd_preflight(args: argparse.Namespace) -> int:
    settings = load_settings(args.pipeline_root)
    ok = await run_preflight(settings, dry_run=args.dry_run)
    return 0 if ok else 1


async def cmd_botb(args: argparse.Namespace) -> int:
    """Run the BOTB pipeline (Tier 2 by default)."""
    settings = load_settings(args.pipeline_root)

    # Always run preflight first unless explicitly skipped.
    if not args.skip_preflight:
        console.rule("[bold]Preflight[/bold]")
        ok = await run_preflight(settings, dry_run=args.dry_run)
        if not ok and not args.force:
            console.print(
                "[red]Aborting. Pass --force to run anyway (not recommended) "
                "or --skip-preflight to skip checks entirely.[/red]"
            )
            return 1

    # Choose which stages to run.
    if args.stage:
        stages_to_run = [args.stage]
        if args.stage not in _STAGES:
            console.print(f"[red]Unknown stage: {args.stage}. Valid: {list(_STAGES)}[/red]")
            return 1
    else:
        stages_to_run = _STAGE_ORDER

    # Confirmation prompt for real (non-dry-run) runs unless forced.
    if not args.dry_run and not args.yes:
        cap = settings.cost_caps.tier2_total
        console.print(
            f"\n[bold yellow]About to run a REAL Tier {args.tier} pipeline. "
            f"Estimated spend: $75-150. Hard cap: ${cap:.2f}.[/bold yellow]"
        )
        try:
            confirm = input("Type 'yes' to proceed: ").strip().lower()
        except EOFError:
            console.print("[red]No TTY; pass --yes to run non-interactively.[/red]")
            return 1
        if confirm != "yes":
            console.print("Cancelled.")
            return 0

    async with StateStore(settings.state_db_path) as state:
        for stage_name in stages_to_run:
            console.rule(f"[bold]Stage: {stage_name}[/bold]")
            run_fn = _STAGES[stage_name]
            try:
                result = await run_fn(settings, state, dry_run=args.dry_run)
            except Exception as e:
                console.print(f"[red]Stage {stage_name} crashed: {e!r}[/red]")
                # Don't auto-continue past a crash; user can --resume to retry.
                return 2
            console.print(f"[dim]Stage {stage_name} returned:[/dim] {result}")

        total = await state.total_cost_usd()
        console.rule("[bold]Run complete[/bold]")
        console.print(f"Total spend this database: [bold]${total:.2f}[/bold]")

    return 0


async def cmd_status(args: argparse.Namespace) -> int:
    """Print a summary of the current state DB."""
    settings = load_settings(args.pipeline_root)
    if not settings.state_db_path.exists():
        console.print("No state.sqlite yet — nothing has been run.")
        return 0

    async with StateStore(settings.state_db_path) as state:
        jobs = await state.all_jobs()
        total = await state.total_cost_usd()
        by_stage = await state.cost_by_stage()

    table = Table(title="Pipeline state")
    table.add_column("Article")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Cost")
    table.add_column("Output")

    for j in jobs:
        status_color = {
            "done": "green",
            "running": "yellow",
            "failed": "red",
            "safety_hold": "red",
        }.get(j.status, "white")
        table.add_row(
            j.article_id,
            j.stage,
            f"[{status_color}]{j.status}[/{status_color}]",
            f"${j.cost_usd:.2f}",
            (j.output_path or "")[-60:],
        )
    console.print(table)

    cost_table = Table(title="Cost by stage")
    cost_table.add_column("Stage")
    cost_table.add_column("Cost (USD)")
    for stage, cost in sorted(by_stage.items()):
        cost_table.add_row(stage, f"${cost:.2f}")
    cost_table.add_row("[bold]TOTAL[/bold]", f"[bold]${total:.2f}[/bold]")
    console.print(cost_table)
    return 0


# ---------------------------------------------------------------------------
# Argparse wiring
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="orchestrator", description="BOTB research pipeline")
    p.add_argument(
        "--pipeline-root",
        default=str(Path(__file__).resolve().parent.parent),
        help="Path to research-pipeline/ directory. Defaults to the parent of orchestrator/.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("preflight", help="Validate everything cheaply before spending money")
    pf.add_argument("--dry-run", action="store_true", help="Probe in dry-run mode")

    bot = sub.add_parser("botb", help="Run the BOTB pipeline")
    bot.add_argument("--tier", type=int, default=2, choices=[2, 3])
    bot.add_argument("--stage", help="Run only a single stage (research/dossiers/draft/redteam/revise/polish/publish)")
    bot.add_argument("--dry-run", action="store_true", help="No real API calls; use stub responses")
    bot.add_argument("--resume", action="store_true", help="Resume from last successful stage")
    bot.add_argument("--skip-preflight", action="store_true", help="Skip preflight checks (not recommended)")
    bot.add_argument("--force", action="store_true", help="Run even if preflight failed")
    bot.add_argument("--yes", "-y", action="store_true", help="Skip the cost-confirmation prompt")

    sub.add_parser("status", help="Show pipeline state")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "preflight":
        return asyncio.run(cmd_preflight(args))
    if args.command == "botb":
        return asyncio.run(cmd_botb(args))
    if args.command == "status":
        return asyncio.run(cmd_status(args))
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
