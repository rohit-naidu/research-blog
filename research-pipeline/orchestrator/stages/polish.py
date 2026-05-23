"""
orchestrator.stages.polish
==========================

Final mechanical polishing pass:

  1. Attach the standardized medical disclaimer.
  2. Validate footnote numbering and reference integrity (every [^N] inline
     has a matching footnote at the bottom and vice versa).
  3. Quick link check on all URLs in the article (HEAD request; mark
     broken links so the publish stage can flag them).
  4. Prepend Jekyll front matter matching the existing post stubs.

No LLM calls here — pure deterministic text manipulation.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import aiofiles
import httpx
from rich.console import Console

from ..config import ArticleConfig, Settings
from ..state import StateStore

console = Console()


_INLINE_FOOTNOTE_RE = re.compile(r"\[\^(\d+)\]")
_URL_RE = re.compile(r"https?://[^\s)\]]+")


def _front_matter_for(article: ArticleConfig) -> str:
    """Build the Jekyll front matter block."""
    return (
        f"---\n"
        f"layout: post\n"
        f'title: "{article.title}"\n'
        f'drug: "Best of the Best (BOTB)"\n'
        f'drug_slug: "botb"\n'
        f'system: "Essentials"\n'
        f"---\n\n"
    )


def _validate_footnotes(text: str) -> list[str]:
    """Return a list of footnote integrity issues."""
    issues: list[str] = []
    inline_nums = set(int(m) for m in _INLINE_FOOTNOTE_RE.findall(text))
    # Footnote definitions look like `[^N]: text`
    def_nums = set(int(m) for m in re.findall(r"^\[\^(\d+)\]:", text, flags=re.MULTILINE))
    missing_defs = inline_nums - def_nums
    orphan_defs = def_nums - inline_nums
    if missing_defs:
        issues.append(f"Footnotes referenced but not defined: {sorted(missing_defs)}")
    if orphan_defs:
        issues.append(f"Footnotes defined but not referenced: {sorted(orphan_defs)}")
    return issues


async def _check_links(text: str, timeout: float = 6.0) -> list[str]:
    """HEAD-check every URL. Returns list of broken-link strings."""
    urls = list(set(_URL_RE.findall(text)))
    if not urls:
        return []
    broken: list[str] = []
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async def _check(url: str):
            try:
                r = await client.head(url)
                if r.status_code >= 400:
                    # Some sites disallow HEAD; try GET as fallback.
                    r = await client.get(url)
                if r.status_code >= 400:
                    broken.append(f"{url} -> HTTP {r.status_code}")
            except Exception as e:
                broken.append(f"{url} -> {type(e).__name__}")
        await asyncio.gather(*[_check(u) for u in urls], return_exceptions=True)
    return broken


async def _polish_one(
    settings: Settings,
    state: StateStore,
    article: ArticleConfig,
    disclaimer: str,
) -> Path | None:
    """Polish one article. Returns the polished path or None if not ready."""
    final_path = settings.tier2_final_dir / f"{article.id}.final.md"
    if not final_path.exists():
        console.print(f"[yellow]skip polish[/yellow] {article.id} (no final draft; check safety-hold queue)")
        return None

    polished_path = settings.tier2_final_dir / f"{article.id}.polished.md"

    # Resume.
    existing = await state.get_job(article.id, "polish")
    if existing and existing.status == "done" and polished_path.exists():
        console.print(f"[dim]skip polish[/dim] {article.id}")
        return polished_path

    await state.start_job(article.id, "polish")

    async with aiofiles.open(final_path, "r") as f:
        body = await f.read()

    issues = _validate_footnotes(body)
    if issues:
        for i in issues:
            console.print(f"[yellow]footnote issue ({article.id}):[/yellow] {i}")

    # Link check (best-effort; broken links are warnings, not aborts).
    if settings.publishing.link_check:
        broken = await _check_links(body)
        if broken:
            console.print(f"[yellow]broken links in {article.id}:[/yellow]")
            for b in broken:
                console.print(f"  {b}")

    # Assemble final markdown.
    front = _front_matter_for(article)
    polished = f"{front}{body.strip()}\n\n{disclaimer.strip()}\n"

    async with aiofiles.open(polished_path, "w") as f:
        await f.write(polished)

    await state.finish_job(
        article.id,
        "polish",
        output_path=str(polished_path),
        cost_usd=0.0,
        status="done",
    )
    console.print(f"[green]polish[/green] {article.id}")
    return polished_path


async def run(settings: Settings, state: StateStore, *, dry_run: bool) -> dict[str, Any]:
    """Polish all 4 articles (or skip articles in safety hold)."""
    async with aiofiles.open(settings.disclaimer_path, "r") as f:
        disclaimer = await f.read()

    paths = []
    for article in settings.articles:
        p = await _polish_one(settings, state, article, disclaimer)
        if p:
            paths.append(str(p))
    return {"polished": paths}
