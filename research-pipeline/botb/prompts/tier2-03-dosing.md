# Tier 2 — Dosing Protocols (Core Theory Revisited)

## SYSTEM

You are a meticulous clinical pharmacologist + obesity medicine specialist
preparing a research brief for an expert blog article on alternative GLP-1
dosing protocols. Audience: smart adults on semaglutide / tirzepatide /
orforglipron who are experiencing side effects on the standard FDA titration
schedule and want to know what alternative protocols exist, what evidence
supports them, and how they differ.

You read primary sources. You distinguish what is published from what is
community-reported. You handle injection pharmacology carefully and never
encourage anything that crosses into dangerous territory.

## USER

Produce a comprehensive research brief titled "Alternative GLP-1 Dosing
Protocols: What Works Better Than Standard Titration."

### Scope

In scope: any dosing strategy that deviates from the FDA-approved titration
schedule for semaglutide (Ozempic / Wegovy), tirzepatide (Mounjaro / Zepbound),
or orforglipron (Foundayo). Includes slow titration, microdosing, weekend
cycling, pulse dosing, dose splitting, timing optimization, hydration
loading, and any other documented variant.

Out of scope: off-label drug substitution (e.g., taking research-grade
compounds), illegal sourcing, and protocols that fundamentally change the
drug indication.

### Required topics

For each of the 3 drugs (semaglutide, tirzepatide, orforglipron), produce:

#### 1. The standard FDA titration schedule
- Exact dose-by-week schedule per label
- The population the schedule was derived from
- Discontinuation rates at each titration step from published trial data
- The most common side effects per titration step

#### 2. Slow titration
- Specific alternative schedule (week-by-week)
- Who it's appropriate for
- What evidence or clinical experience supports it
- Tradeoffs (longer time to therapeutic dose, etc.)

#### 3. Microdosing
- Practical mechanics — how to physically divide an injectable dose
- Typical microdose ranges and starting doses
- Published evidence vs. community-reported usage
- Population this is most appropriate for (those with severe side effects;
  those primarily seeking metabolic benefits over weight loss; some peri-
  and post-bariatric uses)
- Specific safety considerations

#### 4. Weekend / pulse / non-weekly cycling
- Schedule options (every 10 days, every 2 weeks, pulse-then-rest)
- Rationale and evidence
- Specific warnings (rebound, especially in diabetes patients)

#### 5. Dose splitting (same weekly total, split into multiple injections)
- Mechanics of splitting a pen dose safely
- Evidence on side effect reduction with steadier blood levels
- Drug-by-drug differences in steady-state PK

#### 6. Timing optimization
- Best day of week to inject (most patients pick Saturday/Sunday — what
  does the evidence say about peak PK timing relative to lifestyle)
- Best time of day
- Meal timing in the 24 hours after injection
- Hydration protocols (specific volumes, electrolyte ratios)
- Exercise timing

#### 7. Oral-specific protocols (orforglipron and semaglutide tablet/Rybelsus)
- Pill vs. injection PK differences
- Strict absorption requirements (water volume, fasting state, etc.)
- What doesn't transfer from injectable protocols
- Tablet-specific microdosing approaches (split scoring, etc.)

#### 8. The decision tree
- Map reader situation to recommended protocol:
  - Primary goal (weight loss / metabolic / diabetes / sustainability)
  - Severity of side effects on standard titration
  - Time pressure (event-driven, slow lifestyle)
  - Comorbidities (CKD, GI disorders, mental health history)
- For each branch, specific recommended starting parameters

#### 9. When to abandon a protocol and switch
- Concrete signals that a chosen protocol isn't working
- Specific switch recommendations

### Output structure

For each protocol section above, return:

```
{
  "protocol_name": "Slow titration",
  "applicable_drugs": ["semaglutide", "tirzepatide", "orforglipron"],
  "schedule_by_drug": {
    "semaglutide": {
      "weeks_1_4": "0.125 mg weekly (half the label start dose)",
      "weeks_5_8": "0.25 mg weekly",
      "..."
    }
  },
  "evidence": {
    "grade": "B",
    "key_sources": [...],
    "what_published_says": "...",
    "what_community_reports": "..."
  },
  "best_for": [...],
  "not_for": [...],
  "tradeoffs": [...],
  "practical_notes": [...],
  "safety_warnings": [...],
  "red_flags_for_drafter": []
}
```

### Required sourcing

- FDA labels are mandatory primary sources for the standard titration
  schedules.
- Published RCT data for any protocol claiming evidence support.
- Endocrinologist or obesity medicine specialist statements for clinical
  experience-supported protocols.
- For community-only protocols, label them as such and don't claim formal
  evidence.

### Evidence grading scheme

Same A through E scale.

### Length

No limit. Be exhaustive. This article requires the most physiological depth
of the 4 BOTB articles because the recommendations directly affect drug
administration.
