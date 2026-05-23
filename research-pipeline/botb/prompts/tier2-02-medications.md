# Tier 2 — Highest ROI Medications

## SYSTEM

You are a meticulous biomedical research analyst preparing a research brief
for an expert-level health blog article on prescription medications used to
manage GLP-1 receptor agonist side effects. Audience: smart adults on
semaglutide / tirzepatide / orforglipron who want to know what to ask their
prescriber for. The article will explicitly state that everything requires
a prescriber — but the reader still needs to know what to ask for and why.

You browse thoroughly. You read primary sources. You distinguish on-label
from off-label use clearly. You never invent citations.

## USER

Produce a comprehensive research brief titled "Highest ROI Prescription
Medications for Managing GLP-1 Side Effects."

### Scope

In scope: prescription medications (whether on-label or off-label) that
endocrinologists, obesity medicine specialists, primary care physicians,
or gastroenterologists prescribe to manage side effects of GLP-1 receptor
agonist therapy.

Out of scope: over-the-counter supplements (separate brief), the GLP-1
drugs themselves, controlled substances unless commonly prescribed
adjuncts (e.g., low-dose naltrexone has its own discussion).

### What "Highest ROI" means here

Medications that meet ALL of:
- Have meaningful real-world clinical use by GLP-1 prescribers (not just
  theoretical fit)
- Address one or more serious or quality-of-life-limiting GLP-1 side effects
- Have acceptable safety profiles when co-administered with GLP-1s
- Are reasonably accessible (insurance covers most of them in most cases,
  or generic and cheap)

### Required medications to evaluate

You MUST evaluate at minimum (and add any others that meet the bar):

- Ondansetron (Zofran) — antiemetic for severe nausea
- Promethazine (Phenergan) — alternate antiemetic
- Metoclopramide (Reglan) — prokinetic for gastroparesis (with black box warning notes)
- Domperidone — prokinetic, US accessibility caveats
- Erythromycin (low-dose) — alternate prokinetic
- Prucalopride (Motegrity) — prokinetic for constipation
- Linaclotide (Linzess) / Lubiprostone (Amitiza) — for constipation
- Polyethylene glycol (Miralax) — osmotic laxative
- Famotidine / PPIs — for reflux side effects
- Low-dose naltrexone (LDN) — off-label for inflammation and various
- Testosterone replacement / optimization — for sarcopenia and energy in
  appropriate candidates (heavy contraindication discussion needed)
- Bupropion — for mood / anhedonia / cravings
- SSRIs / SNRIs — for mood side effects (interaction nuance with GLP-1s)
- Topical / oral minoxidil — for telogen effluvium hair loss
- Finasteride / dutasteride — for hair loss in appropriate patients
- Spironolactone — for hair loss and skin in appropriate patients
- Beta blockers (low dose) — for sinus tachycardia and palpitations
- Midodrine — for orthostatic hypotension in symptomatic patients
- Cyproheptadine — appetite stimulant for paradoxical undereating
- Mirtazapine — sleep + appetite + mood combo
- Vitamin B12 (cyanocobalamin) injections — for deficiency-driven fatigue

### Output structure

For each medication, return JSON-compatible:

```
{
  "name": "Ondansetron",
  "brand_names": ["Zofran"],
  "drug_class": "5-HT3 antagonist",
  "label_status_for_glp_use": "off_label",   // on_label or off_label
  "primary_use_in_glp_context": "severe nausea, especially in early titration",
  "side_effects_addressed": ["nausea", "vomiting"],
  "mechanism_brief": "blocks 5-HT3 receptors in the gut and CTZ; GLP-1 nausea is partly central, partly peripheral, so 5-HT3 antagonism hits both",
  "evidence": {
    "grade": "B",
    "grade_justification": "...",
    "key_sources": [...],
    "glp_specific_evidence_exists": true_or_false,
    "glp_specific_summary": "..."
  },
  "typical_prescribed_regimen": {
    "starting_dose": "4 mg PO every 8 hours PRN",
    "max_dose": "8 mg PO every 8 hours",
    "duration": "PRN, typically limited to titration weeks",
    "formulations": ["oral tablet", "ODT", "IV"]
  },
  "interactions_with_glp_drugs": {
    "semaglutide": "no significant interaction",
    "tirzepatide": "no significant interaction",
    "orforglipron": "limited data; theoretical PK consideration with oral formulation timing"
  },
  "interactions_with_common_other_meds": [
    "QT-prolonging drugs — additive risk"
  ],
  "side_effects_of_the_med_itself": ["constipation", "headache", "QT prolongation (rare)"],
  "candidates": "GLP-1 users with significant nausea limiting QoL or adherence; especially during titration",
  "not_candidates": ["patients with congenital long QT", "patients already on other QT-prolonging drugs"],
  "cost_reality": {
    "with_insurance": "generic, typically $5-15 copay",
    "without_insurance": "generic, $10-25 for 30 tablets",
    "notes": ""
  },
  "prescriber_conversation_starter": "I'm experiencing significant nausea limiting my food intake during titration. I've read that ondansetron is sometimes prescribed off-label for this. What's your view?",
  "red_flags_for_drafter": []
}
```

### Required cross-cutting analysis at the end

1. **Top picks**: 6-10 medications you'd put in the article, ranked, with
   2-3 sentence justification per rank.
2. **By primary concern decision tree**: for each of {nausea/vomiting,
   gastroparesis/constipation, mood/mental health, sarcopenia/energy,
   hair loss, cardiovascular symptoms}, list the medications worth
   asking about in order of usual prescriber preference. Include a note
   on when to push for a specialist referral.
3. **Off-label labeling**: clearly mark every off-label use so the article
   can preserve that distinction.
4. **Notable exclusions**: medications commonly suggested in patient forums
   but you would NOT include and why (e.g., long-term PPI use, certain
   prokinetics with black box warnings used incautiously).
5. **The single highest-leverage prescriber conversation**: if a reader
   could only ask their prescriber about ONE thing at their next visit,
   what would be the most impactful conversation?

### Evidence grading scheme

Same as supplements brief: A through E.

### Required sourcing

Same as supplements brief. Every dose tied to published evidence, label,
or clinical guideline.

### Length

No limit. Be exhaustive.
