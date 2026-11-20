---
title: "Supporting Information for: The missing negative: documented drug non-interactions are structured claims, and resources and algorithms flatten them"
---

Adeeb Noor and Michel Dumontier

Corresponding author: Adeeb Noor, arnoor@kau.edu.sa

**This PDF file includes:** Supporting text S1–S13; Tables S1 to S12 (S3, S6, S8 and S10 in two parts).

## S1. Data sources and versions

**Table S1. Inputs.** Third-party resources marked † were used for analysis only and are not redistributed.

| Input | Version or date | Use |
|---|---|---|
| openFDA drug label bulk files (14 files) | retrieved 17 Nov 2026 | Source text of all statements |
| RxNorm IN/PIN/MIN list (RxNav) | release of 2 Nov 2026 | Ingredient normalization |
| DailyMed SPL → RxNorm mappings | 17 Nov 2026 | Label set identifier to ingredient |
| FDA tables of substrates, inhibitors and inducers | page current 29 May 2026; retrieved 18 Nov 2026 | Undocumented direction; positive and reversed items for the language-model experiment |
| EMA medicines table and English product information | 17 Nov 2026; 1,162 of 1,165 originator products | Replication |
| NHANES 2017–March 2020 P_RXQ_RX, P_DEMO | public release | Population exposure |
| DDInter 2.0 downloadable files † | downloaded Nov 2026 | Database comparison; predictor positives |
| D3 gold annotations (GoldD3R) † | as published with ref. 8 of the main text | Mechanism annotation |
| PK-DDI DB (github harryscpt/pk-ddip) † | downloaded 20 Nov 2026 | Prior-art comparison |
| Wikidata (UMLS, DrugBank, RxNorm, SMILES, ATC) | queried 19–20 Nov 2026 | Identifier bridges and structures |

## S2. Extractors and acceptance

**Extractor A (rules, v1.2).** Sentences were segmented from the drug-interaction and clinical-pharmacology sections. A sentence became a candidate when it contained a negation of an interaction or of an exposure change ("no clinically significant", "did not affect", "no effect on", "were not altered", and related forms) and named a second RxNorm ingredient (2,660 ingredients). The direction was taken from the grammatical subject (perpetrator) and object (victim) of the negated clause; symmetric constructions ("between A and B", "of either drug") were assigned to both directions. Seven flags marked weak evidence: long sentence (character-length threshold in the code), population-pharmacokinetic analysis, table-like text, endogenous substance, a positive interaction cue in the same sentence, a partial parameter (half-life or Tmax only) and a partner that belongs to the label drug's own regimen. Unflagged single-ingredient candidates form the CORE set (5,250 sentence–partner units).

**Extractor B (language model).** Model claude-sonnet-5-5; batch interface; strict JSON schema; default sampling settings; maximum 2,048 output tokens. Each unit was read four times: two runs with the label drug named first and two with the partner named first. System prompt SHA-256 prefix cbfc70f9d910743d (full text in S11). Schema fields: pair is the subject; co-administration observed; finding (no clinically significant interaction, interaction, other); direction (label drug affects partner, partner affects label drug, both, unspecified); evidence basis; parameters assessed; partner in the label drug's regimen; verbatim quote.

**Acceptance.** A unit was accepted when A proposed it, all four B runs returned "pair is the subject", "co-administration observed" and "no clinically significant interaction", the quote matched the sentence, the B runs agreed on direction, and A and B did not give opposite single directions. When B's direction was "both" and A's was a single direction, or the reverse, the single direction was kept; when B's direction was "unspecified", A's direction was used.

**Table S2. Agreement and stability (5,250 CORE units, four runs).**

| Measure | Value |
|---|---|
| Passed content checks in all four runs | 4,744 (90.4%) |
| Accepted | 4,547 (86.6%) |
| κ acceptance, label-first vs partner-first | 0.927 |
| κ finding, label-first vs partner-first | 0.900 |
| κ direction, label-first vs partner-first | 0.973 |
| Same-order re-run agreement on acceptance | 99.69% |
| Rejected: unstable on same-order re-run | 30 |
| Rejected: B runs disagree on direction | 59 |
| Rejected: A and B give opposite single directions | 138 |
| ridi-check 0.10.1, label-first vs partner-first: same / stable change / unstable | 5,082 / 90 / 78 |
| First-run change between orders (95% CI) | 2.4% (2.0–2.8%) |
| Execution floor within each order | 0.8% |
| Pass rate of extractor B, CORE vs flagged units (all 8,478 units) | 91.1% vs 33.7% |

All 168 units that ridi-check marked as changed or unstable were excluded by the acceptance rule.

## S3. Direction: provenance and sensitivity analysis

**Table S3a. Direction of the 4,547 accepted units by extractor.**

| Extractor A | Extractor B (four runs) | Final | Units |
|---|---|---|---|
| label → partner | label → partner | label → partner | 1,500 |
| partner → label | partner → label | partner → label | 969 |
| unspecified | label → partner | label → partner | 614 |
| unspecified | unspecified | undirected | 527 |
| unspecified | partner → label | partner → label | 258 |
| partner → label | both | partner → label | 246 |
| both | unspecified | both | 162 |
| both | both | both | 111 |
| label → partner | both | label → partner | 72 |
| both | label → partner | label → partner | 65 |
| unspecified | both | both | 15 |
| both | partner → label | partner → label | 8 |

Every unit in which A assigned "both" to a contrastive sentence ("had no effect on X but reduced the Cmax of Y") was resolved by B to a single direction or rejected; no accepted unit carries a "both" direction from such a sentence. The 162 units in which only A assigned "both" are all phrased symmetrically, for example "no clinically significant interaction was observed between efavirenz and zidovudine". Such sentences state a symmetric regulatory conclusion, but the underlying study may have measured one drug only.

**Table S3b. Sensitivity of pair status to the reading of symmetric phrasing.** The dataset was rebuilt with the 162 symmetric-only units set to undirected (`04_build_dataset.py`, identical code). In the release, the 76 directional statements that depend only on such phrasing carry `symmetric_phrasing_only = 1`.

| | Main analysis (as written) | Symmetric phrasing read as undirected |
|---|---|---|
| Directional statements | 1,032 | 956 |
| Undirected statements | 72 | 114 |
| N2, both directions documented | 136 (14.2%) | 94 (9.8%) |
| N1, one direction only | 760 (79.6%) | 768 (80.4%) |
| N0, undirected statements only | 59 (6.2%) | 93 (9.7%) |

The conclusion that most documented non-interacting pairs leave one direction unaddressed strengthens under the conservative reading.

## S4. Dimension and numeric grade

Dimension (1,032 directional statements): pharmacokinetics only 961; pharmacokinetics and pharmacodynamics 45; pharmacodynamics only 14; not stated 12. Parameters: unspecified pharmacokinetics 3,400 units; AUC or Cmax named 518; pharmacokinetics and pharmacodynamics 247; pharmacodynamics only 117 (units may overlap across statements).

**Table S4. Numeric grade of statements with a geometric-mean-ratio table in the same direction.** Tables were read from the label's structured table fields (23,065 pharmacokinetic tables); direction came from the caption or column header only.

| Grade | Definition | Statements |
|---|---|---|
| Exposure-equivalent | all AUC and Cmax ratios within 0.80–1.25 | 46 |
| Weak change | a ratio outside 0.80–1.25 but within 0.50–2.00 | 10 |
| Strong change | a ratio ≤0.50 or ≥2.00 | 2 (doravirine with ketoconazole, 3.06; with ritonavir, 3.54) |
| No table in the same direction | — | 974 |

PK-DDI DB comparison: of our 1,032 directional statements, 455 are negatives in PK-DDI DB, 11 are recorded there as exposure changes outside 0.80–1.25 (median 1.40-fold, maximum 3.54-fold) and 566 do not occur in it. Of its 2,290 negative pairs, 536 (23.4%) are negative in both directions.

## S5. EMA replication

**Table S5. FDA and EMA at the same pipeline stage (extractor A, CORE records, single-ingredient documents).**

| | FDA labels | EMA product information |
|---|---|---|
| Documents | 264,800 | 1,162 (926 with section 4.5 and a mapped ingredient) |
| Pairs | 1,160 | 329 |
| One direction only | 63.3% | 61.4% |
| Both directions | 12.5% | 17.9% |
| Direction unresolved | 24.2% | 20.7% |

129 pairs occur in both. Of the 99 that both regulators resolve: identical direction set 79; overlapping 16; complementary 4. Section 4.5 was located by heading; EU international non-proprietary names were mapped to US names with a documented table.

## S6. Conditions and adjudication

**Classification.** 2,548 distinct evidence sentences, two independent runs (claude-sonnet-5-5; prompt SHA-256 prefix 91dd60573d18b94c; full text in S11). Run-to-run agreement: dosing 99.2%, product 99.3%, population 98.8%, generalization 98.6%. A statement is unconditional when at least one of its sentences generalizes, conditional when all are restricted, and uncertain otherwise.

**Table S6a. Conditions of the 1,032 directional statements.**

| Class | Statements |
|---|---|
| Unconditional | 689 (66.8%) |
| Conditional, strong restriction | 150 (14.5%) |
| Conditional, study dose or population only (not counted as conditional) | 178 (17.2%) |
| Uncertain | 15 (1.5%) |
| Strong restriction types (a statement may carry several): single dose of perpetrator 56; victim-specific product 44; perpetrator-specific product 41; route 20; staggered administration 11 | |

Known cases were classified as expected: rifampin → selpercatinib (single dose), fluconazole → elagolix (single dose), omeprazole → levothyroxine (one oral solution), omeprazole → dasatinib (one product), posaconazole → indinavir (one regimen); quinidine → metoprolol, amlodipine → atorvastatin and pantoprazole → clopidogrel stayed unconditional. The model sometimes treats a description of the study as a restriction (for example "in patients with breast cancer"), which is why the 178 study-context statements were not counted.

**Adjudication.** For each of the 150 strong-restriction statements and 150 randomly drawn unconditional statements (seed 20261120), up to 15 candidate sentences mentioning both drugs were taken from the two drugs' own labels (1,506 sentences). Each sentence was judged twice (prompt SHA-256 prefix 4ebfea38496674ce; agreement 99.1%). A statement counts as "interaction documented outside the restriction" when at least one sentence received that verdict in both runs.

**Table S6b. Adjudication.**

| | Strong restriction (n = 150) | Unconditional control (n = 150) |
|---|---|---|
| Interaction documented outside the restriction | 18 (12.0%) | 10 (6.7%) |
| Sentence verdicts: interaction outside restriction / within restriction only / small or not relevant / other direction or drug / unclear / runs disagree | 65 / 39 / 521 / 203 / 42 / 10 | 27 / — / 446 / 116 / 33 / 4 |

## S7. Population exposure

NHANES 2017–March 2020 prescription files list each reported product with up to several ingredient names separated by semicolons. Each ingredient name was mapped to an RxNorm ingredient by name. A participant uses a pair when two different reported products contain the two ingredients; a pair present only inside one fixed-dose combination does not count. Weights: WTINTPRP; variance: Taylor-series linearization over SDMVSTRA and SDMVPSU; reliability: NCHS presentation standards (ref. 15 of the main text). A pair is generalizable when at least one of its directional statements carries no strong restriction.

**Table S7. US residents using pairs with documented non-interactions (population 322.3 million; 15,560 participants).**

| Group | Participants | Millions (SE) |
|---|---|---|
| Any pair in the reference | 816 | 17.9 (1.3) |
| Any pair with a generalizable statement | 717 | 15.1 (1.1) |
| One direction only (N1) | 553 | 12.3 (0.9) |
| N1, other direction undetermined | 493 | 10.9 (0.8) |
| N1, other direction ruled out by FDA tables | 109 | 2.5 (0.4) |
| N1, other direction pathway expected or possible | 0 | — |
| Both directions (N2) | 146 | 3.1 (0.5) |
| Only restricted statements | 135 | 3.6 (0.7) |
| Generalizable pair listed by DDInter as an interaction | 212 | 5.4 (0.6) |

Largest restricted pair: levothyroxine with omeprazole (about 2 million users).

## S8. Language-model experiments

**Question.** The system prompt (SHA-256 prefix 6c485128f76c8b4c; full text in S11) asks whether co-administration of the perpetrator changes the systemic exposure of the victim to a clinically significant extent, pharmacokinetics and one direction only, with three answers: interaction, no clinically significant interaction, insufficient evidence. Items: 1,032 documented directional non-interactions; 894 established interactions (strong index inhibitor or inducer with a sensitive index substrate of the same enzyme); 698 reversed versions of those interactions. Two runs per model.

**Table S8. Stable answers by model.**

| | Sonnet 5.5 | Haiku 5.5 | GPT-6.2 Sol | Gemini 4 Carbon |
|---|---|---|---|---|
| Developer | Anthropic | Anthropic | OpenAI | Google |
| Questions with two runs | 2,624 | 2,619 | 2,624 | 2,059 |
| Run-to-run disagreement | 2.7% | 12.8% | 6.1% | 0.5% |
| Established interactions recognized | 98.1% | 88.0% | 98.8% | 99.7% |
| Warned on any documented non-interaction | 5.1% | 8.3% | 4.1% | 4.5% |
| — one-direction statements (N1) | 6.6% | 10.6% | 5.1% | 5.5% |
| — both-direction statements (N2) | 1.1% | 1.8% | 1.1% | 1.9% |
| — unrestricted only, N1 / N2 | 5.8 / 0.9% | 10.0 / 2.1% | 3.9 / 0.9% | 4.2 / 1.6% |
| Restricted statements: "no interaction" | 77.3% | 44.0% | 73.3% | 86.7% |
| Restricted statements: "interaction" | 9.3% | 10.7% | 10.0% | 10.0% |
| Reversed interactions: "interaction" | 7.7% | 7.7% | 5.9% | 8.3% |

For the 18 restricted statements whose labels document an interaction outside the restriction, the four models answered "no interaction" for 33–50% (Sonnet 5.5: 8 of 18). Of 66 warnings on reversed interactions by Sonnet 5.5 and Haiku 5.5, 62 involved HIV protease inhibitors that the FDA tables list only as substrates. OpenRouter models received one added instruction line requesting JSON, because structured output was not guaranteed.

**Table S8b. One- versus two-direction statements: warnings by model (stable answers, both runs counted in the denominator).**

| | Sonnet 5.5 | Haiku 5.5 | GPT-6.2 Sol | Gemini 4 Carbon |
|---|---|---|---|---|
| N1 warnings (95% CI) | 50/760, 6.6% (5.0–8.6) | 80/755, 10.6% (8.6–13.0) | 39/760, 5.1% (3.8–6.9) | 33/603, 5.5% (3.9–7.6) |
| N2 warnings (95% CI) | 3/272, 1.1% (0.4–3.2) | 5/272, 1.8% (0.8–4.2) | 3/272, 1.1% (0.4–3.2) | 4/214, 1.9% (0.7–4.7) |
| Odds ratio, Fisher's exact *P* | 6.3, 1.6 × 10⁻⁴ | 6.3, 6.4 × 10⁻⁷ | 4.9, 2.1 × 10⁻³ | 3.0, 0.034 |
| Within perpetrator: MH odds ratio (N1 / N2 warnings in informative strata) | 1.2 (10/230 vs 2/160) | 5.4 (25/228 vs 2/160) | 4.5 (12/230 vs 1/160) | 1.5 (9/148 vs 3/121) |
| Within victim: MH odds ratio | 3.4 (22/399 vs 3/175) | 3.0 (24/397 vs 3/175) | 6.9 (12/399 vs 2/175) | 2.8 (10/292 vs 3/129) |

Within-drug strata contain few warnings; the odds ratios keep the direction of the overall difference but are imprecise.

**Table S9. Evidence experiment (Sonnet 5.5, two runs, 8,688 requests).** Arms: no evidence; the label sentence; a structured record stating direction, dimension, numeric grade and restriction, followed by the sentence. The added system instruction (prefix of the base prompt as above) states that evidence about one direction says nothing about the other unless it says so.

| Item set | Answer | No evidence | Sentence | Structured record |
|---|---|---|---|---|
| Documented direction (882 unrestricted statements) | no interaction | — | 99.2% | 99.7% |
| Undocumented direction (760) | no interaction | 75.8% | 54.5% | 58.0% |
| Undocumented direction (760) | insufficient evidence | 13.9% | 32.6% | 30.5% |
| Restricted statements (150) | no interaction | 77.3% | 97.3% | 97.3% |
| Restricted, interaction documented outside restriction (18) | no interaction | 8/18 (44.4%) | 14/18 (77.8%) | 14/18 (77.8%) |

## S9. Prediction models

**Design.** Positives: 30,000 DDInter 2.0 pairs sampled from 99,771 representable pairs (seed 7). Drug features: Morgan fingerprint (radius 2, 1,024 bits) from Wikidata SMILES plus ATC level-2 one-hot; pair features: element-wise OR and AND (order-invariant). Training negatives: random unlisted pairs, equal in number to positives. Every pair in the reference was removed from training. Test sets: 20% held-out positives; an equal number of held-out random pairs; 396 documented pairs with a generalizable statement not listed by DDInter (71 documented in both directions); 236 documented pairs that DDInter lists; 69 pairs with only restricted statements. Threshold: 90% sensitivity on held-out positives. Five seeds.

**Table S10. Predictors trained in the standard way (mean of five seeds).**

| | Logistic regression | Gradient boosting | DeepDDI-style MLP |
|---|---|---|---|
| AUROC, random negatives | 0.85 | 0.89 | 0.84 |
| AUROC, documented negatives | 0.72 | 0.78 | 0.71 |
| AUROC, documented in both directions | 0.79 | 0.85 | — |
| False alarms, random negatives | 36.9% | 29.0% | 42.9% |
| False alarms, documented negatives | 62.9% | 47.6% | 64.7% |
| False alarms, documented in both directions | 54.4% | 37.2% | 59.4% |
| Flagged, documented pairs that DDInter lists | 96.0% | 96.2% | — |
| Documented pairs flagged under all five seeds | 53.3% | 33.6% | — |
| Documented pairs whose call changes across seeds | 17.4% | 27.3% | — |

**Table S10b. Drug-matched and degree-weighted control negatives (same training as Table S10, mean ± SD over five seeds; 1,980 control pairs per set; 291 distinct drugs in the 396 documented pairs).**

| False alarms at 90% sensitivity | Logistic regression | Gradient boosting |
|---|---|---|
| Random unlisted pairs | 37.0 ± 0.9% | 29.2 ± 0.5% |
| Random pairs of the same drugs as the documented pairs | 53.3 ± 1.2% | 38.6 ± 2.0% |
| Documented non-interactions | 63.1 ± 1.4% | 48.6 ± 1.3% |
| Documented minus drug-matched (seeds with a positive difference) | +9.9 ± 1.1 points (5/5) | +10.0 ± 1.2 points (5/5) |
| Random pairs weighted by number of listed interactions | 77.9 ± 1.0% | 66.0 ± 0.8% |
| AUROC: random / drug-matched / documented / degree-weighted | 0.85 / 0.79 / 0.71 / 0.61 | 0.89 / 0.85 / 0.78 / 0.71 |

Degree-weighted pairs are harder than documented pairs but are not known to be negative; some are likely unrecorded interactions.

**Table S11. Remedy: documented negatives in training (gradient boosting, five-fold cross-validation over documented pairs, sample weight 5, five seeds).**

| | Without documented negatives | With documented negatives |
|---|---|---|
| False alarms on unseen documented pairs | 47.5% | 33.2% |
| False alarms on random negatives | 28.9% | 29.6% |
| AUROC, usual benchmark | 0.889 | 0.888 |

Limitations: DDInter positives include pharmacodynamic interactions while most documented statements are pharmacokinetic. The remedy experiment splits documented pairs, not drugs, between folds, so a drug in a test pair may occur in a training pair.

## S10. Interaction database and D3

**Table S12. DDInter 2.0 listing of documented pairs by status.**

| Status | Pairs | Both drugs in DDInter | Listed | % listed | Major / Moderate / Minor / Unknown |
|---|---|---|---|---|---|
| All | 955 | 735 | 251 | 34.1 | 27 / 93 / 30 / 101 |
| N2 both directions | 136 | 116 | 36 | 31.0 | 4 / 16 / 4 / 12 |
| N1 one direction | 760 | 572 | 201 | 35.1 | 23 / 74 / 25 / 79 |
| N1, reverse no pathway | 102 | 81 | 33 | 40.7 | 8 / 6 / 6 / 13 |
| N1, reverse pathway expected | 11 | 9 | 5 | 55.6 | 1 / 2 / 2 / 0 |
| N0 undirected only | 59 | 47 | 14 | 29.8 | 0 / 3 / 1 / 10 |

D3: 1,064 of 1,599 UMLS concepts mapped to RxNorm through Wikidata. Of 96 documented pairs annotated in D3 as interacting: pharmacodynamic mechanism only 56; pharmacokinetic and pharmacodynamic 24; pharmacokinetic only 4; none 12. Of 25 pairs with a purely pharmacokinetic statement and a pharmacokinetic D3 mechanism, 23 are documented in one direction only.

## S11. Prompts (verbatim system prompts)

**Extractor B** (SHA-256 prefix cbfc70f9d910743d):

> You are extractor B in a reproducible pharmacology data pipeline. You read ONE sentence taken verbatim from a US FDA drug label and judge it strictly from its own wording. Do not use outside knowledge about these drugs; if the sentence does not say it, it is not there.
>
> Definitions:
> - "Co-administration observed": the sentence reports that both named drugs were actually given together to humans (a clinical pharmacokinetic or pharmacodynamic study, or clinical co-use data) and an outcome was measured.
> - "No clinically significant interaction": the sentence states that giving the two drugs together produced no clinically significant / relevant / meaningful change (in pharmacokinetics, exposure, or the reported pharmacodynamic effect) for the drugs it names.
> - The two drugs of interest are the ones named in the request. A metabolite, an endogenous substance or a laboratory analyte is not a co-administered drug.
> - Direction: the drug whose pharmacokinetics or effect was MEASURED is the one affected. "A did not alter the pharmacokinetics of B" means A was tested as the affecting drug and B as the affected drug; it says nothing about the effect of B on A.
> - If the PARTNER DRUG is given as part of the label drug's own regimen (for example "darunavir/ritonavir" or "boosted with ritonavir") and the statement is about a third drug, the pair is not the subject.
>
> Answer every field. The quote must be copied character-for-character from the sentence and must be the shortest span that supports your finding.

**Language-model question** (SHA-256 prefix 6c485128f76c8b4c):

> You are a drug-interaction checker. Answer about PHARMACOKINETICS and ONE direction only: whether co-administration of the PERPETRATOR drug changes the systemic exposure (plasma concentrations, AUC or Cmax) of the VICTIM drug to a clinically significant extent. Ignore pharmacodynamic interactions (additive or opposing effects, shared toxicities). Do not consider the opposite direction, that is, any effect of the victim on the perpetrator. Choose exactly one answer:
> - interaction: a clinically significant change in the victim's exposure caused by the perpetrator is expected or documented.
> - no_clinically_significant_interaction: evidence indicates no clinically significant change in the victim's exposure.
> - insufficient_evidence: you do not know of evidence either way.

Evidence arms append: "If EVIDENCE is provided, use it together with what you know. Evidence about one direction says nothing about the other direction unless it says so."

**Condition classification** (SHA-256 prefix 91dd60573d18b94c):

> You read one sentence from a drug label that states that a PERPETRATOR drug has no clinically relevant effect on a VICTIM drug. Decide whether the sentence restricts that no-interaction statement to particular conditions, or whether it supports it for the two ingredients in general (usual doses, usual products).
>
> Report only what the sentence itself says. Do not use outside knowledge about the drugs.
>
> dosing_condition: none (no restriction on how the perpetrator was given, or the dose is only a routine description of the study); single_dose_perpetrator (the perpetrator was given as a single dose; repeated dosing is not covered); specific_dose_or_regimen (the statement is limited to a stated dose, dose range or regimen of the perpetrator, wording that implies other doses may differ); staggered_administration (the drugs were given at separated times).
> formulation_restriction: none; victim_specific_product (limited to one product, brand or dosage form of the VICTIM when other products of the same ingredient exist or are implied); perpetrator_specific_product (the same for the PERPETRATOR); specific_route (limited to one route).
> population_restriction: none, or specific_population.
> generalizes_to_ingredients: true when the sentence, as written, supports a no-interaction statement for the two ingredients at usual doses and products; false when any restriction above limits it.
> condition_quote: the shortest exact words from the sentence that carry the restriction, or an empty string.

**Adjudication** (SHA-256 prefix 4ebfea38496674ce):

> A drug label states that a PERPETRATOR drug has no clinically relevant effect on a VICTIM drug, but only under a RESTRICTION (for example a single dose of the perpetrator, or one product of the victim). RESTRICTION may be 'none' when the statement is general.
>
> You will see one other SENTENCE from the label of one of the two drugs. Decide what this sentence documents about the effect of the PERPETRATOR on the VICTIM.
>
> verdict: interaction_outside_restriction (the sentence documents a clinically relevant change in the victim's exposure or effect caused by the perpetrator, under conditions that differ from the RESTRICTION; when RESTRICTION is 'none', any such documented interaction counts); interaction_within_restriction_only; small_or_not_relevant; other_direction_or_other_drug; unclear. Use only what the sentence says. quote: the shortest exact words that support the verdict.

## S12. Data release: files and fields

| File | Content |
|---|---|
| `nullddi_statements.jsonl` / `.csv` | One record per statement (1,032 directional, 72 undirected) |
| `nullddi_evidence_sentences.csv` | One row per statement × sentence × label version |
| `nullddi_pairs.csv` | One row per pair (955) with status N2 / N1 / N0 and the undocumented-direction class |
| `nullddi_accepted_units.jsonl` | The 4,547 accepted sentence units with extractor A and B directions |
| `stats.json`, `CHECKSUMS.sha256` | Counts and SHA-256 checksums |

Statement fields: `statement_id`; `kind` (directional, undirected); `perpetrator`, `perpetrator_rxcui`, `victim`, `victim_rxcui`; `dimension` (PK, PD, PK+PD, not_stated); `parameters`; `numeric_grade` (exposure_equivalent, weak_change, strong_change, empty) and `numeric_gmr`; `reverse_fda` (no_path, undetermined, path_possible, path_expected); `condition_llm` (unconditional, conditional, uncertain); `condition_types`; `condition_quotes`; `restriction_strong` (single dose, product, route or staggered); `symmetric_phrasing_only`; `evidence` (sentence, quote, label ingredient, and for each label: set identifier, version, effective time, section); `n_sentences`; `n_labels`.

## S13. Reproducibility

Scripts run in this order (all in `pipeline/`): 01 fetch labels; 02 extractor A (v1.2); 03 extractor B (v1.2); 04 build dataset; 04b active moieties; 05 undocumented direction (v1.1); 06b DDInter listing (v1.1); 07 numeric tables (v1.1); 08, 08a, 08b EMA; 09b, 09d language-model question; 10 D3 mechanisms; 12 NHANES (v1.2); 13 conditions; 15 cross-vendor summary; 16a, 16b adjudication; 17, 18 predictors; 19 evidence experiment; 20 figures; 21 release. Language-model calls use batch identifiers recorded in each run log; raw responses are kept. API keys are read at run time and never written to disk. Re-running step 04 on the accepted units reproduces the release counts exactly; numeric grades require the step-07 table records.
