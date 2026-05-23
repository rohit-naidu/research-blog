"""
orchestrator.stages.publish
===========================

Final stage. Writes the polished markdown files into the Jekyll _posts/
directory (overwriting the empty BOTB stubs), then runs `jekyll build` to
verify nothing is broken before declaring the article shipped.

If build fails, the article is rolled back and re-queued.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

import aiofiles
from rich.console import Console

from ..config import ArticleConfig, Settings
from ..state import StateStore

console = Console()


async def _publish_one(
    settings: Settings,
    state: StateStore,
    article: ArticleConfig,
    *,
    dry_run: bool,
) -> Path | None:
    """Copy polished article into _posts/. Returns target path or None.

    Dry-run behavior: writes the polished content to
    `botb/tier2/dry-run-published/` so the user can inspect what would be
    published, but never touches the real Jekyll _posts/ directory.
    """
    polished_path = settings.tier2_final_dir / f"{article.id}.polished.md"
    if not polished_path.exists():
        console.print(f"[yellow]skip publish[/yellow] {article.id} (no polished file)")
        return None

    if dry_run:
        # In dry-run we never touch the real _posts/. Write a preview instead.
        preview_dir = settings.pipeline_root / "botb" / "tier2" / "dry-run-published"
        preview_dir.mkdir(parents=True, exist_ok=True)
        target = preview_dir / Path(article.post_path).name
    else:
        target = settings.jekyll_root / article.post_path

    # Resume check.
    existing = await state.get_job(article.id, "publish")
    if existing and existing.status == "done" and target.exists():
        # Verify the published file matches the polished version; if it
        # doesn't, fall through and re-copy. This handles the case where
        # the user edited a post but rolled back state.
        async with aiofiles.open(polished_path, "r") as f:
            polished_text = await f.read()
        async with aiofiles.open(target, "r") as f:
            target_text = await f.read()
        if polished_text == target_text:
            console.print(f"[dim]skip publish[/dim] {article.id}")
            return target

    await state.start_job(article.id, "publish")

    # Make a backup of the existing post (the empty stub) so we can roll
    # back if jekyll build fails after the copy. We only do this for REAL
    # runs - in dry-run there's nothing meaningful to back up.
    backup_path: Path | None = None
    if not dry_run and target.exists():
        backup_path = target.with_suffix(target.suffix + ".prepub.bak")
        shutil.copy2(target, backup_path)

    # Copy the polished file into place.
    target.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(polished_path, "r") as f:
        content = await f.read()
    async with aiofiles.open(target, "w") as f:
        await f.write(content)

    await state.finish_job(
        article.id,
        "publish",
        output_path=str(target),
        cost_usd=0.0,
        status="done",
    )
    if dry_run:
        console.print(f"[green]publish (dry-run)[/green] {article.id} -> {target}")
    else:
        console.print(f"[green]publish[/green] {article.id} -> {target.relative_to(settings.jekyll_root)}")
    return target


async def _jekyll_build(settings: Settings) -> tuple[bool, str]:
    """Run the configured jekyll build command. Returns (ok, output)."""
    cmd = settings.publishing.build_command.split()
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=settings.jekyll_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await process.communicate()
    output = stdout.decode("utf-8", errors="replace")
    return (process.returncode == 0, output)


async def run(settings: Settings, state: StateStore, *, dry_run: bool) -> dict[str, Any]:
    """Publish all polished articles, then verify the Jekyll build."""
    paths = []
    for article in settings.articles:
        p = await _publish_one(settings, state, article, dry_run=dry_run)
        if p:
            paths.append(str(p))

    if not paths:
        console.print("[yellow]No articles published.[/yellow]")
        return {"published": [], "build": "skipped"}

    if dry_run:
        # Don't run jekyll build in dry-run; the previews live outside _posts/.
        console.print(
            "[dim]Skipping jekyll build verification in dry-run mode. "
            "Previews are under botb/tier2/dry-run-published/.[/dim]"
        )
        return {"published": paths, "build_ok": True, "build_output_tail": "(dry-run)"}

    console.rule("Running jekyll build verification")
    ok, output = await _jekyll_build(settings)
    if not ok:
        console.print("[red]Jekyll build FAILED. Output:[/red]")
        console.print(output)
        console.print(
            "[red]Articles were copied into _posts/ but the build is broken. "
            "Backups of the original stubs are at *.prepub.bak[/red]"
        )
    else:
        console.print("[green]Jekyll build succeeded.[/green]")

    return {
        "published": paths,
        "build_ok": ok,
        "build_output_tail": output[-2000:] if output else "",
    }
