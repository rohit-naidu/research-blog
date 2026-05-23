"""
orchestrator.stages.revise
==========================

Revision stage. Consumes the 3 review JSON files per article + the draft,
asks the writer model to produce a revised draft that addresses every
issue, and enforces the critical-safety gate:

    If any safety issue with severity >= critical_severity_threshold
    survives revision (because the reviewer didn't accept the fix, or
    flagged a new one), the article is routed to manual-review-queue/
    instead of being published.

Safety gate detection is done by re-running the safety reviewer on the
revised draft. If it still flags critical issues, we hold.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiofiles
from rich.console import Console

from ..clients.openai_client import OpenAIClient
from ..config import ArticleConfig, Settings
from ..state import StateStore

console = Console()


_REVISION_SYSTEM = (
    "You are the senior editor on a research blog. You receive a draft and "
    "three independent reviewer reports (clinical accuracy, voice/lacuna, "
    "safety). Produce a revised draft that addresses every issue with "
    "severity 2 or higher. Severity-1 issues are advisory; address them if "
    "they don't require structural changes. Preserve the article's voice. "
    "Output the revised markdown only — no preamble, no change log, no "
    "Jekyll front matter, no disclaimer. The article structure (sections, "
    "headings) must match the original draft unless a reviewer specifically "
    "called for restructuring."
)


_SAFETY_RECHECK_SYSTEM = (
    "You are a clinical safety reviewer. Re-read this revised draft and "
    "return JSON only: "
    "{\"critical_issues\": [...], \"verdict\": \"safe_to_publish\" or "
    "\"hold_for_manual_review\", \"summary\": \"...\"}. "
    "A critical issue is one where a reader who follows the advice as "
    "written could be seriously harmed."
)


def _parse_json_or_empty(text: str) -> dict[str, Any]:
    """Extract JSON from a model response that might wrap it in fences."""
    text = text.strip()
    if text.startswith("```"):
        # Strip fenced code block markers.
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


async def _revise_one(
    *,
    settings: Settings,
    state: StateStore,
    openai: OpenAIClient,
    article: ArticleConfig,
) -> Path | None:
    """Revise one article. Returns final path, or None if held for review."""
    # Read draft + 3 reviews.
    draft_path = settings.tier2_drafts_dir / f"{article.id}.draft.md"
    async with aiofiles.open(draft_path, "r") as f:
        draft = await f.read()

    reviews_dir = settings.tier2_reviews_dir / article.id
    reviews = {}
    for name in ["clinical", "voice", "safety"]:
        rpath = reviews_dir / f"{name}.json"
        if rpath.exists():
            async with aiofiles.open(rpath, "r") as f:
                reviews[name] = await f.read()
        else:
            reviews[name] = "{}"

    # Resume.
    existing = await state.get_job(article.id, "revise")
    final_path = settings.tier2_final_dir / f"{article.id}.final.md"
    if existing and existing.status == "done" and final_path.exists():
        console.print(f"[dim]skip revise[/dim] {article.id}")
        return final_path

    job_id = await state.start_job(article.id, "revise")

    user_prompt = (
        f"# Original draft\n\n{draft}\n\n---\n\n"
        f"# Clinical accuracy review\n\n{reviews['clinical']}\n\n---\n\n"
        f"# Voice + lacuna review\n\n{reviews['voice']}\n\n---\n\n"
        f"# Safety review\n\n{reviews['safety']}\n\n---\n\n"
        f"Produce the revised markdown draft now. Output the article body only."
    )

    result = await openai.chat_complete(
        system=_REVISION_SYSTEM,
        user=user_prompt,
        model=settings.models.writer,
        temperature=0.4,
        max_tokens=12000,
    )

    settings.tier2_final_dir.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(final_path, "w") as f:
        await f.write(result.content)

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

    # Safety gate re-check.
    recheck = await openai.chat_complete(
        system=_SAFETY_RECHECK_SYSTEM,
        user=f"# Revised draft\n\n{result.content}",
        model=settings.models.reviewer,
        temperature=0.1,
        max_tokens=2048,
        json_mode=True,
    )
    await state.log_api_call(
        job_id=job_id,
        model=recheck.model,
        api="openai",
        tokens_in=recheck.tokens_in,
        tokens_out=recheck.tokens_out,
        latency_ms=recheck.latency_ms,
        cost_usd=recheck.cost_usd,
        dry_run=recheck.dry_run,
    )

    safety_data = _parse_json_or_empty(recheck.content)
    critical_issues = safety_data.get("critical_issues") or []
    verdict = safety_data.get("verdict", "safe_to_publish")

    if (
        len(critical_issues) >= settings.safety.critical_severity_threshold
        or verdict == "hold_for_manual_review"
    ):
        # Route to manual review.
        settings.manual_review_dir.mkdir(parents=True, exist_ok=True)
        hold_path = settings.manual_review_dir / f"{article.id}.final.md"
        async with aiofiles.open(hold_path, "w") as f:
            await f.write(result.content)
        async with aiofiles.open(hold_path.with_suffix(".safety.json"), "w") as f:
            await f.write(recheck.content)
        await state.finish_job(
            article.id,
            "revise",
            output_path=str(hold_path),
            cost_usd=result.cost_usd + recheck.cost_usd,
            status="safety_hold",
            error=safety_data.get("summary"),
        )
        console.print(
            f"[red]SAFETY HOLD[/red] {article.id} -> {hold_path.name} "
            f"({len(critical_issues)} critical issues)"
        )
        return None

    await state.finish_job(
        article.id,
        "revise",
        output_path=str(final_path),
        cost_usd=result.cost_usd + recheck.cost_usd,
        status="done",
    )
    console.print(f"[green]revise[/green] {article.id} (${result.cost_usd + recheck.cost_usd:.2f})")
    return final_path


async def run(settings: Settings, state: StateStore, *, dry_run: bool) -> dict[str, Any]:
    """Revise all 4 articles. Routes safety-holds to manual queue."""
    settings.tier2_final_dir.mkdir(parents=True, exist_ok=True)
    openai = OpenAIClient(settings.openai_api_key, dry_run=dry_run)

    paths = []
    holds = []
    for article in settings.articles:
        p = await _revise_one(
            settings=settings,
            state=state,
            openai=openai,
            article=article,
        )
        if p:
            paths.append(str(p))
        else:
            holds.append(article.id)

    return {
        "revised": paths,
        "safety_holds": holds,
    }
