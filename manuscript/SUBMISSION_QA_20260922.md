# Submission QA — 22 September 2026

Target manuscript: Evidence-Graded Negative Controls for Drug-Drug Interaction Evaluation
Target journal: Pharmacoepidemiology and Drug Safety

## Repository validation performed before submission

The public main branch was downloaded as a clean snapshot and validated on 22 September 2026.

Commands executed:

python validate.py --verbose
python validate_v3.py

Results:

- validate.py: 116 quantities checked; 116 passed; 0 failed; 2 documented skips.
- validate_v3.py: all Anti-DDI v3 semantic and release checks passed.
- The two skipped v2-harness checks require non-redistributed third-party resources and are explicitly reported by the harness rather than silently omitted.

## Principal manuscript quantities verified

- 797 distinct audited drug-pair records.
- 538 T1/T2 higher-support benchmark candidates.
- 217 T1 well-powered and 321 T2 moderate-evidence pairs at p0=0.01.
- Popularity-only mean AUC: 0.934 random negatives; 0.947 curated negatives; 0.498 degree-matched negatives.
- 20 benchmark replicates.
- 246 candidate-negative pairs and 12 established positive controls in the disproportionality analysis.
- Strongest-signal AUC 0.577, p=0.367.
- Fraction-flagged AUC 0.632, p=0.124 after recomputation from the shipped file.
- 782/827 predecessor rows carry at least one documented defect or design consequence.
- The 13-drug vertex cover spans all 797 distinct pairs.

## Scientific boundary

The PDS manuscript does not claim that degree bias is newly discovered. The primary contribution is an evidence-graded pair-level negative-control design with provenance, observation opportunity, detectability, external screening, and structural metadata.

Anti-DDI is a research evidence framework. It is not a universal safety list and does not authorize co-prescribing or alert suppression.

## Retraction and corrective transparency

The repository preserves an objective disclosure of the predecessor retraction in DISCLOSURE_retraction.md and the withdrawn classifier/RIDI experiment in VALIDATION_NOTICE_20260820.md. Neither the retracted article nor the withdrawn experiment is used as validation evidence for the current PDS manuscript.