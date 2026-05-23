"""
orchestrator.stages.research
============================

Tier 2 Research Stage. Fires all 6 research prompts in parallel:

    4 article-level prompts  -> OpenAI Deep Research (via Responses API)
    2 cross-cutting prompts  -> OpenAI Deep Research + Grok DeepSearch

Plus a Grok community-signal call per article topic, run in parallel
alongside the Deep Research calls.

Output: one markdown file per prompt under botb/tier2/research/, named
by prompt id. The dossier-assembly stage reads these files.

Cost enforcement:
    Before each call, we check whether starting it would push total spend
    past the tier2 cap. If so, we abort the run and surface a clear error
    asking the user to either raise the cap or narrow the run.

Resumability:
    Each research call checks state.sqlite first. If the corresponding
    job is already 'done' and the output file exists on disk, we skip it.
    This makes the entire pipeline safely resumable.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiofiles
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from ..clients.grok_client import GrokClient, GrokResult
from ..clients.openai_client import CallResult, OpenAIClient
from ..config import Settings
from ..state import StateStore

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _read_prompt(pipeline_root: Path, relpath: str) -> str:
    """Load a prompt file from disk. The body is everything; we send it as-is."""
    path = pipeline_root / relpath
    async with aiofiles.open(path, "r") as f:
        return await f.read()


async def _write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w") as f:
        await f.write(content)


def _check_cost_cap(current_total: float, cap: float, label: str) -> None:
    """Raise if spending would exceed the cap. Called before each call."""
    if current_total >= cap:
        raise RuntimeError(
            f"Aborting before {label}: tier2 cost cap (${cap:.2f}) "
            f"would be exceeded. Current spend: ${current_total:.2f}. "
            "Raise cost_caps_usd.tier2_total in config.yaml or narrow the run."
        )


# ---------------------------------------------------------------------------
# Per-call worker functions
# ---------------------------------------------------------------------------


async def _run_deep_research_call(
    *,
    settings: Settings,
    state: StateStore,
    openai: OpenAIClient,
    article_id: str,             # "supplements", "medications", etc. -- or "intervention_landscape" etc. for cross-cutting
    prompt_relpath: str,
    output_filename: str,
    stage_label: str,
    progress: Progress,
    task_id: int,
) -> tuple[str, float]:
    """
    Run one Deep Research call. Returns (output_path, cost_usd).

    Skips the call if state shows it's already done.
    """
    job_id = await state.start_job(article_id, stage_label)

    # Resume check: if already done and output exists, skip.
    existing = await state.get_job(article_id, stage_label)
    output_path = settings.tier2_research_dir / output_filename
    if existing and existing.status == "done" and output_path.exists():
        progress.update(task_id, description=f"[dim]skip[/dim] {article_id}", completed=100)
        return (str(output_path), 0.0)

    # Cost-cap check.
    current_total = await state.total_cost_usd()
    _check_cost_cap(
        current_total + settings.cost_caps.per_research_call,
        settings.cost_caps.tier2_total,
        f"Deep Research call for {article_id}",
    )

    # Load prompt.
    prompt = await _read_prompt(settings.pipeline_root, prompt_relpath)

    progress.update(task_id, description=f"running {article_id} (Deep Research)")

    # The actual call. This is the slow one — 20-40 minutes.
    try:
        result: CallResult = await openai.deep_research(
            prompt,
            model=settings.models.deep_research,
        )
    except Exception as e:
        # Fall back to the standard reasoning model with web_search_preview.
        # Useful when the dedicated Deep Research model ID isn't available
        # on the account tier.
        console.log(
            f"[yellow]deep_research model failed for {article_id}: {e}. "
            f"Falling back to {settings.models.deep_research_fallback}.[/yellow]"
        )
        result = await openai.deep_research(
            prompt,
            model=settings.models.deep_research_fallback,
        )

    # Persist output.
    await _write_output(output_path, result.content)

    # Log the API call + finish the job in state.
    await state.log_api_call(
        job_id=job_id,
        model=result.model,
        api="openai",
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        dry_run=result.dry_run,
    )
    await state.finish_job(
        article_id,
        stage_label,
        output_path=str(output_path),
        cost_usd=result.cost_usd,
        status="done",
    )

    progress.update(
        task_id,
        completed=100,
        description=f"[green]done[/green] {article_id} (${result.cost_usd:.2f})",
    )
    return (str(output_path), result.cost_usd)


async def _run_grok_community_call(
    *,
    settings: Settings,
    state: StateStore,
    grok: GrokClient,
    article_id: str,
    prompt_relpath: str,
    output_filename: str,
    stage_label: str,
    progress: Progress,
    task_id: int,
) -> tuple[str, float]:
    """Run one Grok DeepSearch call for community signal."""
    job_id = await state.start_job(article_id, stage_label)

    existing = await state.get_job(article_id, stage_label)
    output_path = settings.tier2_research_dir / output_filename
    if existing and existing.status == "done" and output_path.exists():
        progress.update(task_id, description=f"[dim]skip[/dim] grok-{article_id}", completed=100)
        return (str(output_path), 0.0)

    current_total = await state.total_cost_usd()
    _check_cost_cap(
        current_total + 2.0,  # rough upper bound for one grok call
        settings.cost_caps.tier2_total,
        f"Grok DeepSearch call for {article_id}",
    )

    prompt = await _read_prompt(settings.pipeline_root, prompt_relpath)

    progress.update(task_id, description=f"running grok-{article_id}")

    result: GrokResult = await grok.deep_search(
        prompt,
        model=settings.models.grok,
    )

    # Save markdown body plus a sidecar with the cited sources.
    await _write_output(output_path, result.content)
    if result.sources_used:
        import json as _json
        sources_path = output_path.with_suffix(".sources.json")
        async with aiofiles.open(sources_path, "w") as f:
            await f.write(_json.dumps(result.sources_used, indent=2))

    await state.log_api_call(
        job_id=job_id,
        model=result.model,
        api="grok",
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        dry_run=result.dry_run,
    )
    await state.finish_job(
        article_id,
        stage_label,
        output_path=str(output_path),
        cost_usd=result.cost_usd,
        status="done",
    )

    progress.update(
        task_id,
        completed=100,
        description=f"[green]done[/green] grok-{article_id} (${result.cost_usd:.2f})",
    )
    return (str(output_path), result.cost_usd)


# ---------------------------------------------------------------------------
# Main entry point for the research stage
# ---------------------------------------------------------------------------


async def run(settings: Settings, state: StateStore, *, dry_run: bool) -> dict[str, Any]:
    """
    Fire all Tier 2 research calls in parallel.

    Returns a dict summary suitable for printing or logging.
    """
    settings.tier2_research_dir.mkdir(parents=True, exist_ok=True)

    openai = OpenAIClient(settings.openai_api_key, dry_run=dry_run)
    async with GrokClient(settings.xai_api_key, dry_run=dry_run) as grok:

        # Build the work list. Each entry is one parallel call.
        # We schedule both the Deep Research and Grok calls together;
        # Grok finishes in minutes while Deep Research finishes in tens
        # of minutes, so by the time Deep Research returns, Grok is long done.

        deep_research_tasks: list[dict[str, Any]] = []
        # 4 article-level Deep Research calls.
        for article in settings.articles:
            deep_research_tasks.append({
                "article_id": article.id,
                "prompt": article.prompt,
                "filename": f"{article.id}.deep-research.md",
            })
        # 2 cross-cutting Deep Research calls.
        for cc in settings.cross_cutting:
            deep_research_tasks.append({
                "article_id": cc.id,
                "prompt": cc.prompt,
                "filename": f"{cc.id}.deep-research.md",
            })

        # Grok community-signal calls — one per Deep Research call so each
        # article topic gets a community angle. We reuse the same prompt
        # text; Grok's behavior with live search produces different output
        # than Deep Research even with identical prompts.
        grok_tasks: list[dict[str, Any]] = []
        for article in settings.articles:
            grok_tasks.append({
                "article_id": f"{article.id}-grok",
                "prompt": article.prompt,
                "filename": f"{article.id}.grok-community.md",
            })
        # And one community-specific Grok call using the dedicated community prompt.
        community_prompt = next(c for c in settings.cross_cutting if c.id == "community_protocols")
        grok_tasks.append({
            "article_id": "community-pulse",
            "prompt": community_prompt.prompt,
            "filename": "community-pulse.grok.md",
        })

        # Live progress dashboard.
        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=False,
        ) as progress:

            # Create progress tasks up front so they all appear immediately.
            dr_tasks_with_ids = []
            for t in deep_research_tasks:
                tid = progress.add_task(f"queued {t['article_id']}", total=100)
                dr_tasks_with_ids.append((t, tid))

            grok_tasks_with_ids = []
            for t in grok_tasks:
                tid = progress.add_task(f"queued grok-{t['article_id']}", total=100)
                grok_tasks_with_ids.append((t, tid))

            # Bounded concurrency via semaphores.
            dr_sem = asyncio.Semaphore(settings.parallelism.deep_research)
            grok_sem = asyncio.Semaphore(settings.parallelism.grok_search)

            async def _bounded_dr(task: dict[str, Any], tid: int):
                async with dr_sem:
                    return await _run_deep_research_call(
                        settings=settings,
                        state=state,
                        openai=openai,
                        article_id=task["article_id"],
                        prompt_relpath=task["prompt"],
                        output_filename=task["filename"],
                        stage_label="research",
                        progress=progress,
                        task_id=tid,
                    )

            async def _bounded_grok(task: dict[str, Any], tid: int):
                async with grok_sem:
                    return await _run_grok_community_call(
                        settings=settings,
                        state=state,
                        grok=grok,
                        article_id=task["article_id"],
                        prompt_relpath=task["prompt"],
                        output_filename=task["filename"],
                        stage_label="research-grok",
                        progress=progress,
                        task_id=tid,
                    )

            coros = []
            for t, tid in dr_tasks_with_ids:
                coros.append(_bounded_dr(t, tid))
            for t, tid in grok_tasks_with_ids:
                coros.append(_bounded_grok(t, tid))

            # return_exceptions lets a single failure not bring down the whole batch.
            results = await asyncio.gather(*coros, return_exceptions=True)

    # Summarize.
    total_cost = await state.total_cost_usd()
    failures = [r for r in results if isinstance(r, Exception)]
    successes = [r for r in results if not isinstance(r, Exception)]

    summary = {
        "calls_attempted": len(results),
        "successes": len(successes),
        "failures": len(failures),
        "failure_messages": [repr(f) for f in failures],
        "total_cost_so_far_usd": total_cost,
    }

    console.print()
    console.rule("[bold]Research stage complete[/bold]")
    console.print(f"Calls: {summary['successes']} ok, {summary['failures']} failed")
    console.print(f"Total spend: ${total_cost:.2f}")
    if failures:
        console.print("[red]Failures:[/red]")
        for f in failures:
            console.print(f"  - {f!r}")

    return summary
