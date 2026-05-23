"""
orchestrator.config
===================

Loads config.yaml and .env, validates the result, and exposes a single
typed `Settings` object that every other module imports.

Why this exists as its own module:
    Hard-coding paths and model IDs scattered across the codebase is the
    fastest way to ship a broken pipeline. Centralizing everything in
    config.yaml + this loader means the next person (you, in two weeks)
    knows exactly where to change a model name or raise a cost cap.

Validation philosophy:
    Fail loudly and early. If the config is missing a required field or
    has an obviously wrong value, raise here so the user sees the error
    in 50 ms — not 35 minutes into a Deep Research call.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Pydantic models that mirror the structure of config.yaml.
#
# Why pydantic and not raw dicts?
#   1. We get type checking for free — if config.yaml drops a required field,
#      pydantic raises a clear error pointing at the field name.
#   2. IDE autocomplete on `settings.models.deep_research` works correctly.
#   3. Adding fields later is a one-line schema change.
# ---------------------------------------------------------------------------


class ModelsConfig(BaseModel):
    """Which model ID gets sent to each API call site."""

    deep_research: str
    deep_research_fallback: str
    writer: str
    reviewer: str
    utility: str
    grok: str


class CostCapsConfig(BaseModel):
    """Hard ceilings on spend. Pipeline aborts before exceeding these."""

    tier2_total: float
    tier3_total: float
    per_research_call: float
    per_draft_call: float


class ParallelismConfig(BaseModel):
    """How many of each call type run concurrently."""

    deep_research: int
    grok_search: int
    drafts: int
    redteam: int


class ArticleConfig(BaseModel):
    """One of the 4 BOTB articles."""

    id: str
    title: str
    slug: str
    post_path: str
    schema_path: str = Field(alias="schema")  # 'schema' is reserved in pydantic v2
    prompt: str
    target_word_count: int

    model_config = {"populate_by_name": True}


class CrossCuttingConfig(BaseModel):
    """A cross-cutting research prompt (intervention landscape, community)."""

    id: str
    prompt: str


class DrugConfig(BaseModel):
    name: str
    brands: list[str]


class PublishingConfig(BaseModel):
    jekyll_root: str
    build_command: str
    link_check: bool
    capture_screenshots: bool


class SafetyConfig(BaseModel):
    critical_severity_threshold: int
    manual_review_dir: str
    require_disclaimer: bool
    disclaimer_file: str


class VoiceConfig(BaseModel):
    exemplars_dir: str
    style_guide: str
    min_exemplars_required: int


class OutputConfig(BaseModel):
    state_db: str
    log_dir: str


class RawConfig(BaseModel):
    """Top-level config.yaml shape."""

    models: ModelsConfig
    cost_caps_usd: CostCapsConfig
    parallelism: ParallelismConfig
    articles: list[ArticleConfig]
    cross_cutting: list[CrossCuttingConfig]
    drugs: list[DrugConfig]
    publishing: PublishingConfig
    safety: SafetyConfig
    voice: VoiceConfig
    output: OutputConfig

    @model_validator(mode="after")
    def _check_article_count(self) -> "RawConfig":
        if len(self.articles) != 4:
            raise ValueError(
                f"Expected exactly 4 BOTB articles in config.yaml, got {len(self.articles)}"
            )
        return self


# ---------------------------------------------------------------------------
# The runtime Settings object. It wraps RawConfig with environment-derived
# values (API keys) and absolute paths.
# ---------------------------------------------------------------------------


@dataclass
class Settings:
    """Everything the pipeline needs to know about its environment."""

    # The parsed contents of config.yaml.
    raw: RawConfig

    # API keys loaded from .env. Required ones are validated to be non-empty.
    openai_api_key: str
    xai_api_key: str
    anthropic_api_key: str | None  # optional

    # Absolute paths derived from the pipeline root.
    pipeline_root: Path
    jekyll_root: Path

    # Convenience: resolved absolute paths to common locations.
    state_db_path: Path = field(init=False)
    log_dir: Path = field(init=False)
    voice_exemplars_dir: Path = field(init=False)
    style_guide_path: Path = field(init=False)
    disclaimer_path: Path = field(init=False)
    manual_review_dir: Path = field(init=False)
    tier2_research_dir: Path = field(init=False)
    tier2_dossiers_dir: Path = field(init=False)
    tier2_drafts_dir: Path = field(init=False)
    tier2_reviews_dir: Path = field(init=False)
    tier2_final_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.state_db_path = self.pipeline_root / self.raw.output.state_db
        self.log_dir = self.pipeline_root / self.raw.output.log_dir
        self.voice_exemplars_dir = self.pipeline_root / self.raw.voice.exemplars_dir
        self.style_guide_path = self.pipeline_root / self.raw.voice.style_guide
        self.disclaimer_path = self.pipeline_root / self.raw.safety.disclaimer_file
        self.manual_review_dir = self.pipeline_root / self.raw.safety.manual_review_dir
        self.tier2_research_dir = self.pipeline_root / "botb" / "tier2" / "research"
        self.tier2_dossiers_dir = self.pipeline_root / "botb" / "tier2" / "dossiers"
        self.tier2_drafts_dir = self.pipeline_root / "botb" / "tier2" / "drafts"
        self.tier2_reviews_dir = self.pipeline_root / "botb" / "tier2" / "reviews"
        self.tier2_final_dir = self.pipeline_root / "botb" / "tier2" / "final"

    # Convenience accessors that match the deeper config tree.
    @property
    def models(self) -> ModelsConfig:
        return self.raw.models

    @property
    def cost_caps(self) -> CostCapsConfig:
        return self.raw.cost_caps_usd

    @property
    def parallelism(self) -> ParallelismConfig:
        return self.raw.parallelism

    @property
    def articles(self) -> list[ArticleConfig]:
        return self.raw.articles

    @property
    def cross_cutting(self) -> list[CrossCuttingConfig]:
        return self.raw.cross_cutting

    @property
    def safety(self) -> SafetyConfig:
        return self.raw.safety

    @property
    def publishing(self) -> PublishingConfig:
        return self.raw.publishing


# ---------------------------------------------------------------------------
# Loader function. The single entry point for the rest of the codebase.
# ---------------------------------------------------------------------------


def load_settings(pipeline_root: Path | str | None = None) -> Settings:
    """
    Load and validate the pipeline configuration.

    Args:
        pipeline_root: Path to the research-pipeline/ directory. If None,
            we assume the caller is inside the directory.

    Returns:
        Validated Settings object.

    Raises:
        FileNotFoundError: if config.yaml or .env is missing.
        ValueError: if required env vars are missing or config is malformed.
    """
    root = Path(pipeline_root).resolve() if pipeline_root else Path.cwd()
    if not (root / "config.yaml").exists():
        # User probably ran from the wrong directory.
        # Try one level up in case they're inside orchestrator/.
        if (root.parent / "config.yaml").exists():
            root = root.parent
        else:
            raise FileNotFoundError(
                f"config.yaml not found at {root}/config.yaml. "
                "Run from the research-pipeline/ directory."
            )

    # Load .env into os.environ. This is a no-op if .env doesn't exist;
    # in that case we still try the existing env vars (so the user can
    # also pass keys via shell env if they prefer).
    load_dotenv(root / ".env", override=False)

    # Parse config.yaml through pydantic for validation.
    with (root / "config.yaml").open("r") as f:
        raw_data: dict[str, Any] = yaml.safe_load(f)
    raw = RawConfig.model_validate(raw_data)

    # Required env vars. We allow ANTHROPIC_API_KEY to be empty since
    # Tier 2 doesn't use Claude.
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    xai_key = os.environ.get("XAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip() or None

    missing = []
    if not openai_key:
        missing.append("OPENAI_API_KEY")
    if not xai_key:
        missing.append("XAI_API_KEY")
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill them in, or export them in your shell."
        )

    # Resolve the Jekyll root. The config gives a relative path; we make it absolute.
    jekyll_env = os.environ.get("JEKYLL_ROOT", "").strip()
    jekyll_rel = jekyll_env if jekyll_env else raw.publishing.jekyll_root
    jekyll_root = (root / jekyll_rel).resolve()
    if not jekyll_root.exists():
        raise ValueError(
            f"Jekyll root resolved to {jekyll_root} but that directory doesn't exist. "
            f"Check publishing.jekyll_root in config.yaml or the JEKYLL_ROOT env var."
        )

    return Settings(
        raw=raw,
        openai_api_key=openai_key,
        xai_api_key=xai_key,
        anthropic_api_key=anthropic_key,
        pipeline_root=root,
        jekyll_root=jekyll_root,
    )
