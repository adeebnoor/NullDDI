# PDS 2026 submission alignment

**Manuscript:** *Evidence-Graded Negative Controls for Drug-Drug Interaction Evaluation*  
**Target journal:** *Pharmacoepidemiology and Drug Safety*  
**Repository:** Anti-DDI v3.0.1 main branch

This note maps the submission's principal claims to the repository files that support them and records boundaries that reviewers should be able to inspect directly.

## Primary contribution

The manuscript's novelty claim is the **evidence-graded pair-level negative-control design**. Each pair carries provenance, normalized identifiers, observation opportunity, a minimum detectable effect-size measure, an evidence state, external-screening information, and structural metadata.

It does **not** claim that degree bias in biomolecular-network negative sampling is newly discovered. The degree experiments are stress tests showing why a negative-control resource must expose structural comparability.

## Claim-to-file map

| Submission claim | Repository evidence |
|---|---|
| 797 audited pair records | `data/antiddi_v3_dataset.csv`; historical v2 table in `data/antiddi_v2_dataset.csv` |
| 538 T1/T2 higher-support benchmark candidates | `data/antiddi_v3_benchmark.csv`; `data/p0_sensitivity.csv` |
| Source defects and normalization audit | `data/audit_defects.csv`; `data/audit_drug_normalization.csv`; `data/audit_summary.md` |
| Drug-pair popularity diagnostic: AUC 0.934 / 0.947 / 0.498 | `data/benchmark_replicates.csv`; checked by the legacy validation harness |
| ATC5 robustness diagnostic: AUC 0.908 / 0.900 / 0.501 | `analysis/run_degree_bias_atc5.py`; `data/degree_bias_atc5_replicates.csv`; `data/degree_bias_atc5_summary.json` |
| p0 sensitivity of T1/T2 boundary | `data/p0_sensitivity.csv` |
| FDA-label screening and exclusions | `data/label_screening.csv` |
| Disproportionality outputs | `data/signal_detection_t1.csv` |
| Equivalence-style diagnostics | `data/equivalence_analysis.csv` |
| Retraction/provenance boundary | `DISCLOSURE_retraction.md` |
| Withdrawn classifier/RIDI experiment | `VALIDATION_NOTICE_20260820.md` |

## Two structural diagnostics, not one

The PDS manuscript reports the **drug-pair** diagnostic from `data/benchmark_replicates.csv`:

- random unlabelled negatives: mean AUC ≈ 0.934;
- curated Anti-DDI pairs: mean AUC ≈ 0.947;
- degree-matched curated pairs: mean AUC ≈ 0.498.

A later robustness analysis operates at **ATC level 5**, excludes class-pair overlap with a frozen positive reference, and reports approximately 0.908 / 0.900 / 0.501. The unit of analysis and positive-reference construction differ, so the numerical values are expected to differ. The qualitative conclusion is the same: popularity-only discrimination collapses after structural matching.

## Clinical boundary

Anti-DDI is a research evidence framework and benchmark resource. Membership in the T1/T2 set is **not** a declaration that a pair is clinically safe, does not authorize co-prescribing, and must not be used to suppress a clinical alert without independent patient-specific validation.

## Corrective transparency

The four-arm classifier/RIDI experiment documented in v3.0.0 was withdrawn after an adversarial audit identified label leakage and an invalid safety comparison. It is not used as evidence in the PDS manuscript. The correction is preserved in `VALIDATION_NOTICE_20260820.md`.

## Reproducibility

The repository intentionally preserves both historical and current artifacts so that manuscript-era results remain inspectable while later robustness analyses remain available. Users should report the exact branch/commit and the diagnostic they reproduce.
