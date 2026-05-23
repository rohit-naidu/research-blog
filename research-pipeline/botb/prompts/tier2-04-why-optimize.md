# Tier 2 — Why Optimize?

## SYSTEM

You are a research analyst preparing a brief for an opinion-essayistic
article on the case for actively managing GLP-1 side effects rather than
passively enduring them. Audience: smart adults on or considering GLP-1
therapy who treat side effects as the unavoidable price of admission. The
article argues otherwise and uses real long-term-consequence data to make
the case.

You browse primary sources. You distinguish lived experience from cited
evidence. You don't fearmonger — the case is honest, calibrated, and
backed by data, not catastrophizing.

## USER

Produce a comprehensive research brief titled "The Long-Term Case for
Optimizing GLP-1 Therapy."

### Scope

This is the evidence base for an opinion essay. We need:

1. **Discontinuation data** — how often, why, what happens after.
2. **Per-side-effect long-term cost** for the 5-6 highest-stakes side effects.
3. **Compounding upside** evidence for sustained, optimized therapy.

### Required topics

#### 1. Discontinuation statistics

- Published 1-year, 2-year, 3-year discontinuation rates for each of:
  semaglutide (Ozempic and Wegovy), tirzepatide (Mounjaro and Zepbound),
  orforglipron where data exists
- Reasons cited for discontinuation, ranked by frequency
- Rebound weight gain trajectories after discontinuation (STEP 4, SURMOUNT-4
  extension data, real-world studies)
- What predicts adherence vs. drop-out — the patient characteristics and
  the experience characteristics that matter most

#### 2. Long-term costs of unmitigated specific side effects

For each of the 6 below, produce: the short-term experience (what
patients focus on), the long-term consequence most patients don't see,
and what the evidence says about reversibility after discontinuation
or proper mitigation.

- **Sarcopenia / lean mass loss**: short term = "feeling weak"; long
  term = sustained metabolic rate damage, increased fall and fracture
  risk in older age, faster weight regain after discontinuation
- **Gastroparesis**: short term = nausea and early satiety; long term =
  permanent gastric dysmotility risk, anesthesia and surgical aspiration
  risk, nutritional deficiencies
- **Mental health side effects**: short term = anhedonia, irritability;
  long term = therapy discontinuation, untreated depression rebound,
  documented suicidal ideation signals
- **Nutrient deficiencies**: short term = fatigue, hair changes; long term
  = bone density loss, neurologic effects from B12 deficiency, hair loss
  that may not fully recover
- **Cardiovascular adaptations**: short term = palpitations, mild HR
  increase; long term = sustained resting HR elevation, autonomic
  adaptation effects, atrial fibrillation risk in susceptible patients
- **Renal strain**: short term = mild dehydration; long term = cumulative
  AKI risk on top of existing CKD, irreversible nephron loss in
  susceptible patients

#### 3. Compounding upside of optimization

- Cardiometabolic gains data (SELECT trial CV outcomes, SURPASS metabolic
  outcomes, weight-loss-independent A1c improvements)
- Quality of life during treatment metrics (when patients can sustain
  therapy, the data on energy, mood, and daily function)
- Discontinuation prevention as the upstream lever — every percentage
  point of improved adherence has compounding downstream value
- The social and professional cost of bad side effects — work disruption,
  social withdrawal, sex life disruption, exercise capacity loss

#### 4. The philosophy of intervention

(Not data; we need the framing.) Produce a research-grounded discussion of:
- What "optimization" should mean — smallest effective intervention,
  evidence-graded, sustained, vs. what it should NOT mean (extreme
  biohacking, supplement-stacking-for-its-own-sake)
- The principle that most optimization is bottom-up (sleep, protein,
  electrolytes, dose pacing) before top-down (HMB, ondansetron,
  microdosing)
- Why "do nothing" is the default and why it's almost always wrong

### Output structure

```
{
  "discontinuation_data": {
    "semaglutide_1yr_rate_pct": "...",
    "semaglutide_2yr_rate_pct": "...",
    "tirzepatide_1yr_rate_pct": "...",
    "primary_reasons_ranked": [...],
    "rebound_weight_gain_trajectory": "...",
    "sources": [...]
  },
  "long_term_costs": {
    "sarcopenia": {
      "short_term": "...",
      "long_term": "...",
      "reversibility": "...",
      "evidence_grade": "...",
      "sources": [...]
    },
    "gastroparesis": {...},
    "mental_health": {...},
    "nutrient_deficiencies": {...},
    "cardiovascular": {...},
    "renal": {...}
  },
  "compounding_upside": {
    "cardiometabolic": {...},
    "quality_of_life": {...},
    "adherence_lever": {...},
    "social_professional": {...},
    "sources": [...]
  },
  "philosophy_anchors": {
    "smallest_effective_intervention": "supporting evidence and citations",
    "bottom_up_before_top_down": "supporting evidence and citations",
    "do_nothing_is_wrong": "evidence that passive management is worse than active"
  },
  "narrative_hooks": [
    "specific anecdotes or community-reported turning-point stories that could anchor sections"
  ],
  "red_flags_for_drafter": []
}
```

### Required sourcing

Every claim with a number must have a citation. Discontinuation rates and
rebound weight gain trajectories must trace to specific published trials
(STEP, SURMOUNT, SUSTAIN, etc.) or peer-reviewed real-world cohorts.

### Evidence grading scheme

Same A through E scale.

### Length

No limit. This article needs less individual-intervention depth and more
narrative arc evidence — discontinuation curves, long-term consequence
trajectories, and the human stories that anchor the case.
