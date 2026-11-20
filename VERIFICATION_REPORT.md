# Verification report — NullDDI PNAS submission v1.1 (20 Nov 2026)

## 1. Numbers in the manuscript checked against the run outputs
| Claim | Source file | Value in file | Status |
|---|---|---|---|
| 4,547 accepted; κ 0.927 / 0.900 / 0.973; re-run 99.69%; rejections 138 / 59 / 30 | `llm/agreement_report.json` | identical | ✓ |
| 1,032 directional, 72 undirected, 955 pairs, 509 drugs; N2 136, N1 760, N0 59; PK 961 | `release/v0_1/nullddi_stats.json`; rebuilt by `04_build_dataset.py` | identical (direction counts reproduce exactly) | ✓ |
| Sensitivity: N2 94 (9.8%), N1 768 (80.4%), N0 93; 76 statements flagged | `sensitivity_symmetric/nullddi_stats.json`; release `stats.json` | identical | ✓ |
| Conditions 689 / 328 / 15; strong 150 (56, 44, 41, 20, 11); agreement 98.6–99.3% | `condition/condition_report.json`; release `stats.json` | identical | ✓ |
| Adjudication 18/150 vs 10/150; agreement 99.1% | `adjudicate/adjudication_report.json` | identical | ✓ |
| Evidence experiment 99.2/99.7; 75.8→54.5/58.0; 13.9→32.6/30.5; 77.3→97.3 | `evidence/evidence_report.json` | identical | ✓ |
| Outside-restriction subset 8/18 → 14/18 | recomputed from `evidence/answers_s1,s2` × `adjudicated_cases.jsonl` | 44.4% → 77.8% (earlier draft said 19 items, 79%; corrected) | ✓ corrected |
| Four LLMs: sensitivity, N1/N2, conditional, reversed, disagreement | `cross_vendor/cross_vendor_summary.json` | identical | ✓ |
| NHANES 17.9, 15.1, 12.3, 10.9, 2.5, 3.1, 3.6, 5.4 (SE) | `nhanes/nhanes_exposure_v1_2.json` | identical; all RSE < 30% | ✓ |
| Predictors LR/GB AUROC 0.85/0.89 vs 0.72/0.78; FPR 36.9/29.0 vs 62.9/47.6; N2 54.4/37.2; listed 96%; seed instability 17.4/27.3% | `predictor/predictor_negatives.json` | identical; AUROC drop is 0.14 (LR) and 0.11 (GB) — text corrected to "0.11–0.14" | ✓ corrected |
| DeepDDI-style 0.84/0.71; FPR 42.9/64.7/59.4; remedy 47.5→33.2, 28.9→29.6, AUROC 0.889/0.888 | `predictor/predictor_intervention.json` | identical | ✓ |
| Fig. 4B values (44.4, 77.8, 77.8; n = 18) | `pipeline/20_figures.py` v1.1 | updated | ✓ |
| Fig. 1 example (rifampin single dose; −87% with repeated doses) | label text in `tier_b_v1_1` and condition files | verbatim match | ✓ |

## 1b. Numbers added in v1.1, checked against the run outputs
| Claim | Source file | Value in file | Status |
|---|---|---|---|
| N1 vs N2 warning odds ratios 3.0–6.3 (four models) | `cross_vendor/n1_n2_tests.json` | 3.04, 4.85, 6.31, 6.33 | ✓ |
| Drug-matched control negatives: LR FPR 53.3% vs documented 63.1%; GB 38.6% vs 48.6%; ≈+10 points in 5/5 seeds | `predictor/predictor_matched_negatives.json` | 0.5328 / 0.6313; 0.3858 / 0.4859; diff 0.0985 and 0.1001, n = 5 | ✓ |
| Degree-weighted negatives FPR 77.9% (LR) and 66.0% (GB) | `predictor/predictor_matched_negatives.json` | 0.7787; 0.6603 | ✓ |
| PK-DDI DB concordance 455/466 = 97.6% | manuscript text vs concordance run | 455/466 | ✓ |

## 2. References
All 26 references were checked against the publisher, PubMed, Crossref or the official page on 20 Nov 2026. Ref. 9 is cited with its retraction notice (doi:10.1155/2023/9892301). Ref. 10 is the first author's manuscript under review (not included in this public repository; available on request). Ref. 12 (ridi-check) resolves to the Zenodo concept DOI shown on the public GitHub repository.

## 3. PNAS format
| Item | Limit | This submission |
|---|---|---|
| Abstract | ≤250 words | 249 |
| Significance statement | ≤120 words | 114 |
| Main text | ~4,000 words for 6 pages; ≤12 pages | ~3,430 words + 4 figures |
| References | ~50 for 6 pages | 26 |
| Graphical elements | ~4 for 6 pages | 4 figures (tables moved to SI) |

## 4. Data release
No DDInter, D3, PK-DDI DB or NHANES record is in the release. No API key appears in any file of the project folder (regex scan for Anthropic, OpenRouter, RunPod and Google key formats: 0 matches).

## 5. Known limits stated in the paper
Model-based condition classification and adjudication (two agreeing runs, no experts); no ground truth for the undocumented direction; one model in the evidence experiment; Gemini second run 2,059 of 2,624 questions; standard predictor architectures.
