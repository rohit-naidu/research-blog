# BOTB Research Pipeline

Automated research + drafting + red-team + publish pipeline for the
4 Best-of-the-Best articles on `the-internet's-largest-glp-side-effect-blog`.

## What this does

For each of 4 articles ("Highest ROI Supplements", "Highest ROI Medications",
"Dosing Protocols (Core Theory Revisited)", "Why Optimize?"), this pipeline:

1. **Researches** — fires 6 parallel autonomous research calls. 4 article-
   level Deep Research calls + 2 cross-cutting ones, plus Grok DeepSearch
   calls for community signal.
2. **Assembles** an article-specific dossier from the shared research corpus.
3. **Drafts** the article using your voice exemplars and the article schema.
4. **Red-teams** each draft with 3 parallel reviewers (clinical accuracy,
   voice/lacuna, safety).
5. **Revises** the draft to address every reviewer issue.
6. **Safety gates** — any article with surviving critical safety issues is
   routed to `manual-review-queue/` instead of being published.
7. **Polishes** the markdown — adds disclaimer, validates footnotes, link-checks.
8. **Publishes** by writing into the Jekyll `_posts/` directory and running
   `jekyll build` to verify nothing is broken.

Two execution tiers:

- **Tier 2 (default)**: 1 round of research, ~60 minutes wallclock, $75-150.
- **Tier 3 (upgrade)**: 3 rounds (cumulative cascade), ~3-5 hours wallclock,
  $170-220 incremental. Not yet implemented; current code is Tier 2 only.
  Tier 3 will add `--tier 3` execution that reuses Tier 2 outputs as inputs
  to deeper round-2 and round-3 research.

## Prerequisites

- Python 3.11+
- OpenAI API key with access to GPT-5 + Responses API (Deep Research path is
  ideal but the pipeline falls back to GPT-5 + web_search_preview if your
  account doesn't have the dedicated Deep Research model).
- xAI API key with access to Grok 4 + live search.
- The Jekyll site living at the parent directory (`../`) with the 4 BOTB
  post stubs already created.

## Setup

```bash
cd research-pipeline

python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
$EDITOR .env
```

Drop 1-2 pieces of your existing writing into `style/voice-exemplars/`.
See the README in that folder for what works best.

## Run

```bash
source venv/bin/activate

python -m orchestrator preflight

python -m orchestrator botb --tier 2 --dry-run

python -m orchestrator botb --tier 2

python -m orchestrator status

python -m orchestrator botb --tier 2 --resume

python -m orchestrator botb --tier 2 --stage draft
```

## Safety controls

- **Cost cap**: hard ceiling of `cost_caps_usd.tier2_total` in `config.yaml`.
  The pipeline aborts before any call that would push spend past the cap.
- **Dry-run mode**: `--dry-run` returns stub responses for every API call.
  No money spent. Useful for testing the whole pipeline end-to-end without
  paying.
- **Confirmation prompt**: real (non-dry-run) runs require typing "yes"
  before starting. Bypass with `--yes` or `-y` for non-interactive runs.
- **Resume**: every stage writes its output to disk and records status in
  SQLite before returning. A crashed run can be resumed with `--resume`
  and only the unfinished stages re-run.
- **Safety gate**: after the revision pass, every article is re-checked by
  the safety reviewer. Critical-severity issues route the article to
  `manual-review-queue/` instead of publishing it.

## Layout

```
research-pipeline/
├── config.yaml                        Single source of truth for models,
│                                      cost caps, paths, parallelism.
├── requirements.txt                   pip deps.
├── .env                               API keys (gitignored).
├── .env.example                       Template.
├── README.md                          You are here.
├── state.sqlite                       Runtime state (gitignored).
├── style/
│   ├── style-guide.md                 Voice + anti-pattern rules.
│   ├── disclaimer.md                  Auto-appended medical disclaimer.
│   └── voice-exemplars/               YOUR existing writing (gitignored).
├── botb/
│   ├── prompts/                       The 6 Tier 2 research prompts.
│   ├── schemas/                       Per-article output schemas.
│   ├── tier2/                         Tier 2 outputs (gitignored).
│   │   ├── research/                  Raw research outputs per prompt.
│   │   ├── dossiers/                  Per-article assembled dossiers.
│   │   ├── drafts/                    First-pass drafts.
│   │   ├── reviews/                   3-reviewer JSON per article.
│   │   └── final/                     Revised + polished markdown.
│   └── tier3/                         (Tier 3 outputs, future).
├── orchestrator/                      The Python pipeline code.
│   ├── main.py                        CLI entry point.
│   ├── config.py                      config.yaml + .env loader.
│   ├── state.py                       SQLite job + cost ledger.
│   ├── preflight.py                   Pre-run validation.
│   ├── clients/
│   │   ├── openai_client.py
│   │   ├── grok_client.py
│   │   └── pricing.py
│   └── stages/
│       ├── research.py
│       ├── dossiers.py
│       ├── draft.py
│       ├── redteam.py
│       ├── revise.py
│       ├── polish.py
│       └── publish.py
├── logs/                              Per-run logs (gitignored).
└── manual-review-queue/               Safety-held articles (gitignored).
```

## What to expect during a real run

- **Preflight**: ~30 seconds. Validates env, hits each API with one cheap
  probe call. Worst case it tells you which key is wrong before you spend
  anything.
- **Research stage**: 25-40 minutes. The 4 Deep Research calls run in
  parallel; you'll see a live progress dashboard with one row per call.
  Grok calls finish in 2-5 minutes; Deep Research dominates the wall time.
- **Dossiers**: <1 minute. Pure file IO.
- **Draft**: 5-10 minutes. 4 GPT-5 calls in parallel.
- **Red-team**: 5-10 minutes. 12 calls in parallel.
- **Revise**: 5-10 minutes. 4 calls + 4 safety re-checks in parallel.
- **Polish**: 1-2 minutes (mostly link checking).
- **Publish**: <1 minute + however long `jekyll build` takes.

Total: ~55-70 minutes for the full Tier 2 run.

## When something goes wrong

- A stage crashes mid-flight: just run again with `--resume`. Completed
  stages and completed calls within the current stage will be skipped.
- An article gets safety-held: open it from `manual-review-queue/` and
  the associated `.safety.json` file. Fix manually, then drop the
  corrected file into `botb/tier2/final/` named `{article_id}.polished.md`
  and re-run `python -m orchestrator botb --tier 2 --stage publish`.
- Jekyll build fails after publish: the original empty stubs are backed
  up at `*.prepub.bak`. Restore them with
  `mv path/to/post.md.prepub.bak path/to/post.md`.
- Cost cap hit: edit `cost_caps_usd.tier2_total` in `config.yaml` and
  re-run with `--resume`.

## Tier 3 upgrade (planned)

After reviewing the Tier 2 output, the Tier 3 upgrade will:

1. Extract the highest-signal interventions from Tier 2 dossiers.
2. Fire Round 2: targeted Deep Research calls digging deeper into the
   ones that need more depth.
3. Fire Round 3: cross-cutting synthesis calls that integrate Round 1 +
   Round 2 evidence per article.
4. Re-draft, re-red-team, re-revise.
5. Overwrite the Tier 2 published versions in `_posts/`.

Estimated additional spend: $170-220 on top of Tier 2.

Wired but not yet implemented — Tier 3 requires the user to review Tier 2
output and approve before spending the extra money.
