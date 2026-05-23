"""
orchestrator.stages.redteam
===========================

Three-way adversarial review of each draft, in parallel.

Reviewers per article (3 calls each, all run in parallel):
  1. Clinical accuracy   (GPT-5 in hostile-peer-review mode)
  2. Voice + lacuna      (Grok 4; flags AI-tic phrasing and missing
                          interventions a community member would expect)
  3. Safety              (GPT-5 in safety-reviewer mode; rates issues
                          by severity 1=minor through 5=critical)

Each reviewer returns a structured JSON issue list. The revise stage
consumes all three reports per article.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import aiofiles
from rich.console import Console

from ..clients.grok_client import GrokClient
from ..clients.openai_client import OpenAIClient
from ..config import ArticleConfig, Settings
from ..state import StateStore

console = Console()


# ---------------------------------------------------------------------------
# Reviewer prompts
# ---------------------------------------------------------------------------

_CLINICAL_SYSTEM = (
    "You are a hostile peer reviewer for a top-tier medical journal "
    "evaluating a health blog article on managing GLP-1 receptor agonist "
    "side effects. Your job is to find every clinical inaccuracy, "
    "overconfident claim, missing citation, mechanism error, or factual "
    "weakness. Be aggressive — assume the writer is overconfident and you "
    "need to push back. Return your findings as JSON only, with the schema "
    "described in the user prompt. Do not write prose outside the JSON."
)


_VOICE_SYSTEM = (
    "You are a long-time member of the GLP-1 user community (r/Semaglutide, "
    "r/Mounjaro, r/Tirzepatide). You are reading a draft of a blog post that "
    "claims to be the authoritative resource on a topic you live. Find every "
    "sentence that sounds like a chatbot wrote it, every recommendation that "
    "doesn't ring true to lived experience, and every well-known intervention "
    "or community-recognized tactic that the draft is missing. Return JSON only."
)


_SAFETY_SYSTEM = (
    "You are a clinical safety reviewer for a health blog. Your sole job is "
    "to identify passages where a reader who follows the advice could be harmed. "
    "Consider: dangerous drug interactions glossed over, doses recommended "
    "outside safe ranges, conditions where a recommendation could be lethal "
    "but isn't flagged, recommendations that bypass medical supervision when "
    "they shouldn't. Rate each issue by severity 1 (minor wording) to 5 "
    "(critical, must not publish). Return JSON only."
)


_ISSUE_SCHEMA_DESCRIPTION = """
Return a JSON object with exactly this shape:
{
  "issues": [
    {
      "severity": 1-5,         // 1=minor, 5=critical
      "category": "string",    // e.g. "clinical_accuracy", "missing_citation",
                               //      "voice", "safety", "lacuna", etc.
      "quote": "verbatim quote of the problematic passage (max 200 chars)",
      "problem": "1-2 sentence description of what's wrong",
      "recommendation": "specific fix the revise stage should apply"
    }
  ],
  "verdict": "ok | needs_revision | reject",
  "summary": "1-2 sentence overall take"
}
"""


# ---------------------------------------------------------------------------
# Per-article review functions
# ---------------------------------------------------------------------------


async def _review(
    *,
    state: StateStore,
    settings: Settings,
    article: ArticleConfig,
    draft_text: str,
    reviewer_name: str,
    system_prompt: str,
    call_fn,   # async callable that returns a CallResult-like
) -> Path:
    """Run one reviewer, save the JSON output, log to state."""
    output_dir = settings.tier2_reviews_dir / article.id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{reviewer_name}.json"

    # Resume.
    existing = await state.get_job(article.id, f"review-{reviewer_name}")
    if existing and existing.status == "done" and output_path.exists():
        console.print(f"[dim]skip review[/dim] {article.id}/{reviewer_name}")
        return output_path

    job_id = await state.start_job(article.id, f"review-{reviewer_name}")

    user_prompt = (
        f"# Article to review\n\n{draft_text}\n\n---\n\n"
        f"# Output format\n{_ISSUE_SCHEMA_DESCRIPTION}\n\n"
        f"Return JSON only. No markdown fences, no prose outside the JSON."
    )

    result = await call_fn(system=system_prompt, user=user_prompt)

    async with aiofiles.open(output_path, "w") as f:
        await f.write(result.content)

    await state.log_api_call(
        job_id=job_id,
        model=result.model,
        api="openai" if reviewer_name != "voice" else "grok",
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
        dry_run=result.dry_run,
    )
    await state.finish_job(
        article.id,
        f"review-{reviewer_name}",
        output_path=str(output_path),
        cost_usd=result.cost_usd,
    )
    return output_path


async def _review_article(
    *,
    settings: Settings,
    state: StateStore,
    openai: OpenAIClient,
    grok: GrokClient,
    article: ArticleConfig,
) -> dict[str, Path]:
    """All 3 reviewers for one article, in parallel."""
    draft_path = settings.tier2_drafts_dir / f"{article.id}.draft.md"
    async with aiofiles.open(draft_path, "r") as f:
        draft = await f.read()

    async def _openai_clinical(*, system, user):
        return await openai.chat_complete(
            system=system,
            user=user,
            model=settings.models.reviewer,
            temperature=0.3,
            max_tokens=4096,
            json_mode=True,
        )

    async def _grok_voice(*, system, user):
        return await grok.chat_complete(
            system=system,
            user=user,
            model=settings.models.grok,
            temperature=0.3,
            max_tokens=4096,
        )

    async def _openai_safety(*, system, user):
        return await openai.chat_complete(
            system=system,
            user=user,
            model=settings.models.reviewer,
            temperature=0.2,
            max_tokens=4096,
            json_mode=True,
        )

    tasks = [
        _review(
            state=state,
            settings=settings,
            article=article,
            draft_text=draft,
            reviewer_name="clinical",
            system_prompt=_CLINICAL_SYSTEM,
            call_fn=_openai_clinical,
        ),
        _review(
            state=state,
            settings=settings,
            article=article,
            draft_text=draft,
            reviewer_name="voice",
            system_prompt=_VOICE_SYSTEM,
            call_fn=_grok_voice,
        ),
        _review(
            state=state,
            settings=settings,
            article=article,
            draft_text=draft,
            reviewer_name="safety",
            system_prompt=_SAFETY_SYSTEM,
            call_fn=_openai_safety,
        ),
    ]
    paths = await asyncio.gather(*tasks)
    return {"clinical": paths[0], "voice": paths[1], "safety": paths[2]}


async def run(settings: Settings, state: StateStore, *, dry_run: bool) -> dict[str, Any]:
    """Run all 12 review calls (4 articles x 3 reviewers) in parallel."""
    settings.tier2_reviews_dir.mkdir(parents=True, exist_ok=True)

    openai = OpenAIClient(settings.openai_api_key, dry_run=dry_run)
    async with GrokClient(settings.xai_api_key, dry_run=dry_run) as grok:

        sem = asyncio.Semaphore(settings.parallelism.redteam)

        async def _bounded(article: ArticleConfig):
            async with sem:
                return await _review_article(
                    settings=settings,
                    state=state,
                    openai=openai,
                    grok=grok,
                    article=article,
                )

        results = await asyncio.gather(*[_bounded(a) for a in settings.articles])

    summary = {a.id: {k: str(v) for k, v in r.items()} for a, r in zip(settings.articles, results)}
    console.print(f"[green]redteam[/green] complete: {len(results)} articles x 3 reviewers = {len(results)*3} reports")
    return summary
