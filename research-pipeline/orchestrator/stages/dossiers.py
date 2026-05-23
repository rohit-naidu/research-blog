"""
orchestrator.stages.dossiers
============================

Assemble 4 article-specific dossiers from the shared Tier 2 research corpus.

A dossier is what the drafting stage actually reads. It's a single
self-contained markdown brief per article containing:

  1. The article's schema (so the drafter knows what shape to produce)
  2. The relevant Tier 2 Deep Research output for that article
  3. Excerpts from the cross-cutting intervention landscape relevant to
     this article
  4. The Grok community signal for this article topic
  5. The Grok community-pulse output (shared across all articles)

We don't ask an LLM to assemble dossiers — this is deterministic file
concatenation with markdown headings. Saves money, removes a source of
hallucination, and makes the dossiers human-readable for QA.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import aiofiles
import yaml
from rich.console import Console

from ..config import ArticleConfig, Settings
from ..state import StateStore

console = Console()


async def _read(path: Path) -> str:
    if not path.exists():
        return f"<!-- Missing source file: {path} -->\n"
    async with aiofiles.open(path, "r") as f:
        return await f.read()


def _load_schema(pipeline_root: Path, schema_relpath: str) -> dict[str, Any]:
    with open(pipeline_root / schema_relpath, "r") as f:
        return yaml.safe_load(f)


def _format_schema_for_drafter(schema: dict[str, Any]) -> str:
    """Render the yaml schema as a markdown checklist the drafter can follow."""
    out = [f"## Required article structure: {schema['title']}", ""]
    out.append(f"Target word count: ~{schema['target_word_count']}")
    out.append("")
    out.append("### Sections (in this order)")
    for section in schema.get("sections", []):
        heading = section.get("heading") or "(opening paragraph, no heading)"
        out.append(f"- **{heading}** ({section.get('target_words', '?')} words)")
        out.append(f"  - Purpose: {section.get('purpose', '')}")
        for must in section.get("must_include", []) or []:
            out.append(f"  - Must include: {must}")
    out.append("")
    qr = schema.get("quality_requirements") or {}
    if qr:
        out.append("### Quality requirements (red-team checks for these)")
        for k, v in qr.items():
            out.append(f"- `{k}`: {v}")
    return "\n".join(out)


async def _assemble_one(
    settings: Settings,
    state: StateStore,
    article: ArticleConfig,
) -> Path:
    """Build one article's dossier and write to disk. Returns the path."""
    research_dir = settings.tier2_research_dir

    # Pull all the relevant raw research outputs.
    article_research = await _read(research_dir / f"{article.id}.deep-research.md")
    grok_for_article = await _read(research_dir / f"{article.id}.grok-community.md")
    cross_cutting = await _read(research_dir / "intervention_landscape.deep-research.md")
    community_pulse = await _read(research_dir / "community-pulse.grok.md")

    # Load the schema and render it as a structured brief.
    schema = _load_schema(settings.pipeline_root, article.schema_path)
    schema_brief = _format_schema_for_drafter(schema)

    # Assemble the dossier as one markdown file with clear section headers.
    parts = [
        f"# Dossier: {article.title}",
        "",
        f"_Tier 2 research corpus for the BOTB article `{article.id}`._",
        "",
        schema_brief,
        "",
        "---",
        "",
        "## Article-specific Deep Research (primary source)",
        "",
        article_research,
        "",
        "---",
        "",
        "## Cross-cutting intervention landscape (shared across all 4 articles)",
        "",
        cross_cutting,
        "",
        "---",
        "",
        "## Grok community signal for this article",
        "",
        grok_for_article,
        "",
        "---",
        "",
        "## Grok community pulse (shared across all 4 articles)",
        "",
        community_pulse,
    ]
    dossier_text = "\n".join(parts)

    # Write to disk.
    settings.tier2_dossiers_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.tier2_dossiers_dir / f"{article.id}.dossier.md"
    async with aiofiles.open(out_path, "w") as f:
        await f.write(dossier_text)

    # Update state. No API spend here — pure file IO.
    await state.start_job(article.id, "dossier")
    await state.finish_job(
        article.id,
        "dossier",
        output_path=str(out_path),
        cost_usd=0.0,
        status="done",
    )
    return out_path


async def run(settings: Settings, state: StateStore, *, dry_run: bool) -> dict[str, Any]:
    """Build all 4 dossiers. Cheap and fast — no API calls."""
    paths = []
    for article in settings.articles:
        path = await _assemble_one(settings, state, article)
        paths.append(str(path))
        console.print(f"[green]dossier[/green] {article.id} -> {path.name}")
    return {"dossiers": paths}
