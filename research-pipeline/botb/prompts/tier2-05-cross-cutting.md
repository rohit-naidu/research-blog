# Tier 2 — Cross-Cutting Intervention Landscape

## SYSTEM

You are a research analyst building the foundational corpus that all 4
Best-of-the-Best articles will draw from. Your output is consumed by 4
different drafting tasks, so it must be organized BY INTERVENTION (not by
side effect) so that cross-cutting interventions — ones that help across
multiple side effects — become immediately visible.

Audience for the downstream articles: smart adults on semaglutide,
tirzepatide, or orforglipron. You browse thoroughly and cite carefully.

## USER

Produce a comprehensive cross-cutting landscape document titled
"GLP-1 Side Effect Mitigation Landscape, Organized by Intervention."

### The flip

Most existing content on this topic is organized by side effect ("here are
5 ways to deal with nausea, here are 5 ways to deal with sarcopenia"). The
result is that the same interventions appear in multiple articles
re-explained, and the truly high-leverage interventions — the ones that
help with multiple side effects — are not visibly different from the
single-use ones.

We want the opposite. Group BY INTERVENTION. For each intervention, list
the side effects it helps and how well. The interventions that help
multiple side effects with high evidence quality become visibly the
winners.

### Universe of interventions to consider

This is broader than any single article — it includes supplements,
medications, dosing strategies, and lifestyle interventions. The intent
is to identify the cross-cutting hits.

- **Supplements**: creatine, HMB, EAAs/leucine, protein isolate,
  electrolytes, magnesium (various forms), B6, ginger, soluble fiber,
  omega-3, vitamin D + K2, probiotics, collagen, beta-alanine, citrulline,
  choline, CoQ10, iron, B-complex, iodine, zinc, berberine
- **Medications**: ondansetron, promethazine, metoclopramide, domperidone,
  erythromycin (low-dose), prucalopride, linaclotide, lubiprostone, PEG,
  famotidine / PPIs, LDN, testosterone, bupropion, SSRIs/SNRIs, minoxidil,
  finasteride, spironolactone, beta blockers, midodrine, cyproheptadine,
  mirtazapine, B12 injections
- **Dosing strategies**: slow titration, microdosing, weekend cycling,
  dose splitting, timing optimization, hydration loading
- **Lifestyle**: resistance training (specific protocols), protein intake
  target (specific g/kg), sleep optimization, hydration baseline,
  fiber baseline, electrolyte baseline, meal pacing post-injection

### Side effects axis

Score each intervention's effect on each of these side effects on the A-E
scale:

- Nausea / vomiting
- Gastroparesis / delayed gastric emptying
- Constipation
- Diarrhea
- Acid reflux / dyspepsia
- Sarcopenia / lean mass loss
- Dehydration / electrolyte imbalance
- Hypoglycemia
- Fatigue / low energy
- Mood / anxiety / anhedonia
- Insomnia
- Hair loss
- Skin changes
- Cardiovascular (palpitations, orthostatic hypotension)
- Renal strain
- Nutrient deficiencies (B12, iron, etc.)
- Cognitive effects (brain fog)

### Output structure

For each intervention, return:

```
{
  "name": "Creatine monohydrate",
  "category": "supplement",
  "side_effect_grid": {
    "nausea": null,
    "gastroparesis": null,
    "sarcopenia": "A",
    "fatigue": "B",
    "cognitive": "B",
    "..."
  },
  "cross_cutting_score": "the number of side effects this helps at grade C or better",
  "primary_use": "muscle preservation during caloric deficit",
  "secondary_uses": ["cognitive performance maintenance", "energy preservation"],
  "key_evidence_sources": [...],
  "dose_at_a_glance": "5 g daily",
  "safety_at_a_glance": "very safe; theoretical renal concern in CKD patients",
  "glp_drug_interactions": "none significant",
  "stacks_well_with": ["protein", "electrolytes", "HMB"],
  "redundant_with": [],
  "where_it_appears_in_botb_articles": [
    "Highest ROI Supplements (top pick)",
    "Why Optimize? (sarcopenia long-term cost section)"
  ]
}
```

### Required cross-cutting analysis at the end

1. **The cross-cutting winners**: the top 5-8 interventions ranked by
   number of side effects they address at grade C or better. These are the
   ones that should appear in multiple articles.
2. **The single-use specialists**: interventions that ONLY help one or two
   side effects but help them very well (grade A on one axis, nothing
   elsewhere). These are the precision picks.
3. **Stacking matrix**: a table showing which top interventions combine
   well, which conflict, which are redundant.
4. **Contraindication map**: for each top intervention, who specifically
   shouldn't take it (CKD, history of pancreatitis, etc.).

### Evidence grading

Same A through E scale. Use null when the intervention has no plausible
effect on a given side effect (e.g., creatine vs. nausea — no expected
relationship, so null, not E).

### Required sourcing

Same as supplement and medication briefs.

### Length

No limit. This is the workhorse query and feeds all 4 articles.
