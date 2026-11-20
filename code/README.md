# NullDDI pipeline (code, MIT licence)

Scripts that build the NullDDI reference and reproduce every analysis in the paper. Run from `pipeline/`. Raw inputs are downloaded by the scripts or listed in SI Appendix Table S1; third-party files (DDInter 2.0, D3, PK-DDI DB) must be obtained from their providers under their own licences.

## Order
01 fetch openFDA labels → 02 extractor A (v1.2) → 03 extractor B (v1.2, batch API) → 04 build dataset → 04b active moieties → 05 undocumented direction (v1.1) → 06b DDInter listing (v1.1) → 07 numeric tables (v1.1) → 08/08a/08b EMA replication → 09b/09d language-model question → 10 D3 mechanisms → 12 NHANES (v1.2) → 13 conditions → 15 cross-vendor summary → 16a/16b adjudication → 17/18 predictors → 19 evidence experiment → 20 figures → 21 release.

## Keys
Language-model scripts read API keys from the environment at run time. No key is stored in any file.

## Requirements
Python ≥ 3.10; `pip install -r requirements.txt`.
