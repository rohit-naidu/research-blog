"""
orchestrator.stages.draft
=========================

Drafting stage. Takes per-article dossiers + voice exemplars + style guide
and produces a full markdown draft for each of the 4 articles.

One GPT-5 call per article, run in parallel.

Why we use the writer model (typically `gpt-5`) and not Deep Research:
    Drafting doesn't need browsing — the dossier already has everything.
    Using a cheaper, faster, non-browsing model means each draft completes
    in ~3-5 minutes instead of 20-40.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import aiofiles
from rich.console import Console

from ..clients.openai_client import OpenAIClient
from ..config import ArticleConfig, Settings
from ..state import StateStore

console = Console()


async def _load_voice_exemplars(exemplars_dir: Path) -> str:
    """Concatenate all voice exemplar files into one block, with headers."""
    exemplars = []
    for f in sorted(exemplars_dir.iterdir()):
        # Skip README and hidden files.
        if f.name.startswith(".") or f.name == "README.md":
            continue
        if f.is_dir():
            continue
        async with aiofiles.open(f, "r") as fh:
            content = await fh.read()
        exemplars.append(f"--- VOICE EXEMPLAR: {f.name} ---\n\n{content}\n")
    if not exemplars:
        raise RuntimeError(
            f"No voice exemplars found in {exemplars_dir}. "
            "Drop at least 1 piece of your existing writing there before drafting."
        )
    return "\n\n".join(exemplars)


async def _load_style_guide(path: Path) -> str:
    async with aiofiles.open(path, "r") as f:
        return await f.read()


async def _draft_one(
    *,
    settings: Settings,
    state: StateStore,
    openai: OpenAIClient,
    article: ArticleConfig,
    style_guide: str,
    voice_block: str,
    dossier_path: Path,
) -> Path:
    """Produce one draft. Returns the output markdown path."""

    # Resume check.
    existing = await state.get_job(article.id, "draft")
    output_path = settings.tier2_drafts_dir / f"{article.id}.draft.md"
    if existing and existing.status == "done" and output_path.exists():
        console.print(f"[dim]skip draft[/dim] {article.id} (already done)")
        return output_path

    # Cost cap.
    current_total = await state.total_cost_usd()
    if current_total + settings.cost_caps.per_draft_call > settings.cost_caps.tier2_total:
        raise RuntimeError(
            f"Aborting draft for {article.id}: would exceed tier2 cost cap."
        )

    job_id = await state.start_job(article.id, "draft")

    # Load the dossier.
    async with aiofiles.open(dossier_path, "r") as f:
        dossier_text = await f.read()

    # System prompt: who the writer is and the rules.
    system_prompt = (
        "You are the senior writer for a research blog called "
        "'The Internet's Largest GLP Side Effect Blog', co-authored by Rohit "
        "Naidu (UC Berkeley computational biology, competitive programmer) "
        "and Mahesh Arunachalam (biotech researcher, published in Journal of "
        "Investigative Medicine). Articles are written in first-person plural "
        "('we'). Your job is to produce a publishable markdown draft that "
        "matches the supplied voice exemplars and respects the supplied "
        "style guide and article schema absolutely.\n\n"
        "Output the article body in markdown. Do not include Jekyll front "
        "matter (the publishing stage adds it). Do not include the medical "
        "disclaimer (the publishing stage appends it). Start directly with "
        "the opening paragraph; the article H1 is set by the Jekyll layout."
    )

    # User prompt: dossier + style guide + voice + schema.
    user_prompt = (
        f"# Article to write: {article.title}\n\n"
        f"## Voice exemplars (write like these — adopt cadence, vocabulary, "
        f"hedging patterns, and structural habits)\n\n"
        f"{voice_block}\n\n"
        f"---\n\n"
        f"## Style guide (follow strictly)\n\n"
        f"{style_guide}\n\n"
        f"---\n\n"
        f"## Research dossier (the source of every concrete claim)\n\n"
        f"{dossier_text}\n\n"
        f"---\n\n"
        f"## Your task\n\n"
        f"Produce the full article body in markdown. Target length: "
        f"~{article.target_word_count} words. Every concrete claim must be "
        f"footnoted (Kramdown-style `[^1]` inline, footnotes at the bottom). "
        f"Every recommendation gets an inline evidence tag `[E:A]` through "
        f"`[E:E]`. Follow the article schema's section ordering exactly. "
        f"Do not use any of the anti-pattern phrases listed in the style guide.\n\n"
        f"Start the article now. Begin with the opening paragraph (no H1, "
        f"no front matter, no disclaimer)."
    )

    result = await openai.chat_complete(
        system=system_prompt,
        user=user_prompt,
        model=settings.models.writer,
        temperature=0.55,
        max_tokens=12000,
    )

    # Persist.
    settings.tier2_drafts_dir.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(output_path, "w") as f:
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
    await state.finish_job(
        article.id,
        "draft",
        output_path=str(output_path),
        cost_usd=result.cost_usd,
        status="done",
    )

    console.print(f"[green]draft[/green] {article.id} -> {output_path.name} (${result.cost_usd:.2f})")
    return output_path


async def run(settings: Settings, state: StateStore, *, dry_run: bool) -> dict[str, Any]:
    """Draft all 4 articles in parallel."""
    settings.tier2_drafts_dir.mkdir(parents=True, exist_ok=True)

    # Preflight: voice exemplars must exist.
    voice_block = await _load_voice_exemplars(settings.voice_exemplars_dir)
    style_guide = await _load_style_guide(settings.style_guide_path)

    openai = OpenAIClient(settings.openai_api_key, dry_run=dry_run)

    sem = asyncio.Semaphore(settings.parallelism.drafts)

    async def _bounded(article: ArticleConfig):
        async with sem:
            dossier = settings.tier2_dossiers_dir / f"{article.id}.dossier.md"
            return await _draft_one(
                settings=settings,
                state=state,
                openai=openai,
                article=article,
                style_guide=style_guide,
                voice_block=voice_block,
                dossier_path=dossier,
            )

    paths = await asyncio.gather(*[_bounded(a) for a in settings.articles])
    return {"drafts": [str(p) for p in paths]}
