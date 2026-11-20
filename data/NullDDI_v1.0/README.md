# NullDDI v1.0 — documented drug non-interactions from US drug labels

An open, sentence-traceable reference of regulator-documented drug **non**-interactions, extracted from US FDA drug labels (openFDA, retrieved 17 November 2026) without human curation.

- 1,032 **directional** statements (perpetrator → victim) and 72 undirected statements
- 955 drug pairs, 509 ingredients (RxNorm), 4,547 accepted label sentences
- Each statement carries direction, dimension (PK / PD), a numeric grade where the label gives a geometric mean ratio, the FDA-table class of the undocumented direction, conditions (single dose, product, route, staggered dosing) and provenance to the sentence, label set identifier, version and section.

Companion paper: A. Noor, M. Dumontier, "The missing negative: documented drug non-interactions are structured claims, and resources and algorithms flatten them" (submitted to PNAS).

## Files
| File | Content |
|---|---|
| `nullddi_statements.jsonl` | One JSON record per statement, with full evidence |
| `nullddi_statements.csv` | Flat table of the same statements (no sentences) |
| `nullddi_evidence_sentences.csv` | One row per statement × sentence × label version |
| `nullddi_pairs.csv` | One row per pair: status N2 (both directions), N1 (one direction), N0 (undirected only) |
| `nullddi_accepted_units.jsonl` | The 4,547 accepted sentence units with the directions given by extractor A (rules) and extractor B (language model) |
| `stats.json` | Counts |
| `CHECKSUMS.sha256` | SHA-256 of every file |
| `DATA_DICTIONARY.md` | Field definitions |

## How to read a statement
`perpetrator → victim, dimension PK` means the label reports that the perpetrator does not change the victim's exposure to a clinically significant extent. It says nothing about the reverse direction, nor about additive effects. Check `restriction_strong` before generalizing: when it is 1, the statement holds only under the restriction in `condition_types` / `condition_quotes`. `symmetric_phrasing_only = 1` marks statements whose only support is a symmetric sentence ("no interaction between A and B"); a conservative user may treat them as undirected.

## Method in brief
Rule-based extractor A proposed 115,275 candidates; a language model (claude-sonnet-5-5) read each candidate sentence four times under two prompt orders; a statement was accepted only when A and all four runs agreed (κ 0.90–0.97; re-run agreement 99.7%). Conditions were classified twice by the same model and accepted on agreement (98.6–99.3%). Full methods, prompts and code: see the paper's SI Appendix and the code release.

## Licence and sources
Released under **CC BY 4.0**. Source texts are US government works (openFDA, public domain). Ingredient identifiers are RxNorm RXCUIs (NLM). No record from DDInter, D3, PK-DDI DB or NHANES is included.

## Not medical advice
This is a research resource. It records what labels state; it is not a clinical decision tool.

## Citation
See `CITATION.cff`.
