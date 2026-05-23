"""
orchestrator.preflight
======================

Cheap validation pass that runs before any expensive call.

Checks:
  1. config.yaml loads and validates.
  2. Both API keys are present.
  3. Voice exemplars folder has at least 1 file (besides README).
  4. Style guide and disclaimer files exist.
  5. All 4 article schemas exist and are valid yaml.
  6. All 6 prompt files exist.
  7. OpenAI key is valid (1 cheap probe call).
  8. xAI key is valid (1 cheap probe call).
  9. Jekyll root exists and contains a _posts/ directory.
  10. The 4 BOTB post stubs exist at the expected paths.

If any check fails, we print a clear human-readable error and return
exit code 1 without touching anything expensive.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

from .clients.grok_client import GrokClient
from .clients.openai_client import OpenAIClient
from .config import Settings

console = Console()


async def run_preflight(settings: Settings, *, dry_run: bool = False) -> bool:
    """Execute every preflight check. Returns True if all pass."""
    table = Table(title="Preflight checks", show_lines=False)
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail", overflow="fold")

    ok_overall = True

    def add(name: str, ok: bool, detail: str = "") -> None:
        nonlocal ok_overall
        table.add_row(name, "[green]ok[/green]" if ok else "[red]FAIL[/red]", detail)
        if not ok:
            ok_overall = False

    # ---- 1. Config loaded (we already have settings, so this passed by virtue of being here).
    add("config.yaml parses", True, str(settings.pipeline_root / "config.yaml"))

    # ---- 2. API keys present.
    add(
        "OPENAI_API_KEY",
        bool(settings.openai_api_key),
        f"starts with {settings.openai_api_key[:7]}..." if settings.openai_api_key else "missing",
    )
    add(
        "XAI_API_KEY",
        bool(settings.xai_api_key),
        f"starts with {settings.xai_api_key[:6]}..." if settings.xai_api_key else "missing",
    )

    # ---- 3. Voice exemplars.
    if not settings.voice_exemplars_dir.exists():
        add("voice exemplars dir", False, str(settings.voice_exemplars_dir))
    else:
        exemplars = [
            f for f in settings.voice_exemplars_dir.iterdir()
            if f.is_file() and not f.name.startswith(".") and f.name != "README.md"
        ]
        add(
            "voice exemplars",
            len(exemplars) >= settings.raw.voice.min_exemplars_required,
            f"found {len(exemplars)}, need >= {settings.raw.voice.min_exemplars_required}",
        )

    # ---- 4. Style guide + disclaimer.
    add("style-guide.md", settings.style_guide_path.exists(), str(settings.style_guide_path))
    add("disclaimer.md", settings.disclaimer_path.exists(), str(settings.disclaimer_path))

    # ---- 5. Schemas.
    for article in settings.articles:
        path = settings.pipeline_root / article.schema_path
        ok = path.exists()
        detail = str(path)
        if ok:
            try:
                with path.open("r") as f:
                    yaml.safe_load(f)
            except Exception as e:
                ok = False
                detail = f"invalid yaml: {e}"
        add(f"schema: {article.id}", ok, detail)

    # ---- 6. Prompts.
    all_prompts = [a.prompt for a in settings.articles] + [c.prompt for c in settings.cross_cutting]
    for p in all_prompts:
        full = settings.pipeline_root / p
        add(f"prompt: {p}", full.exists(), str(full))

    # ---- 7 + 8. API key probes (cheap calls).
    if settings.openai_api_key:
        openai = OpenAIClient(settings.openai_api_key, dry_run=dry_run)
        result = await openai.probe(settings.models.writer)
        add(
            f"OpenAI probe ({settings.models.writer})",
            bool(result.get("ok")),
            result.get("reply") or result.get("error", ""),
        )
        # Also probe the Deep Research model — if it fails, the fallback will be used.
        dr_result = await openai.probe(settings.models.deep_research)
        add(
            f"OpenAI probe ({settings.models.deep_research})",
            bool(dr_result.get("ok")),
            (dr_result.get("reply") or dr_result.get("error", ""))
            + (" -- will fall back to "
               + settings.models.deep_research_fallback if not dr_result.get("ok") else ""),
        )

    if settings.xai_api_key:
        async with GrokClient(settings.xai_api_key, dry_run=dry_run) as grok:
            result = await grok.probe(settings.models.grok)
        add(
            f"xAI probe ({settings.models.grok})",
            bool(result.get("ok")),
            result.get("reply") or result.get("error", ""),
        )

    # ---- 9. Jekyll root + _posts.
    add("jekyll root", settings.jekyll_root.exists(), str(settings.jekyll_root))
    posts_dir = settings.jekyll_root / "_posts"
    add("_posts directory", posts_dir.exists(), str(posts_dir))

    # ---- 10. Stub posts.
    for article in settings.articles:
        target = settings.jekyll_root / article.post_path
        add(
            f"post stub: {article.id}",
            target.exists(),
            str(target),
        )

    console.print(table)
    if ok_overall:
        console.print("[bold green]All preflight checks passed.[/bold green]")
    else:
        console.print("[bold red]Preflight FAILED. Fix the issues above before running.[/bold red]")
    return ok_overall
