"""
research-pipeline.orchestrator
==============================

The Python package that runs the BOTB Tier 2 / Tier 3 research-to-publish
pipeline.

Top-level layout:

    config.py    Loads config.yaml + .env, validates everything before
                 anything expensive happens.
    state.py     SQLite-backed job tracker. Knows what's been done, what
                 it cost, and where to resume after a crash.
    clients/     Thin wrappers around the OpenAI and xAI Grok APIs with
                 retries, cost tracking, and dry-run support.
    stages/      One module per pipeline stage (research, dossiers, draft,
                 redteam, revise, polish, publish). Each is a single
                 callable that takes the prior state and produces output.
    main.py      CLI entry point. Wires the stages together.

Design constraints:
    1. The pipeline must be resumable. Every stage writes its output to
       disk before returning. State is tracked in SQLite. A crashed run
       can be resumed with `python -m orchestrator botb --resume`.
    2. The pipeline must respect cost caps. Before any API call, the
       orchestrator checks projected vs. allowed spend and aborts the
       run if it would exceed the cap.
    3. The pipeline must support dry-run. With `--dry-run`, every API
       call returns a stub response and no money is spent. Useful for
       verifying wiring before a real run.
    4. The safety gate is non-negotiable. Any article flagged as
       critical-severity by the safety reviewer is routed to
       manual-review-queue/ instead of being auto-published.
"""

__version__ = "0.1.0"
