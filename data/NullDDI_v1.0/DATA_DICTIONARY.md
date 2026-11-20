# NullDDI v1.0 — data dictionary

## nullddi_statements.jsonl / .csv
| Field | Type | Meaning |
|---|---|---|
| statement_id | string | Stable identifier `NDDI-00001` … |
| dataset_version | string | `1.0` |
| kind | `directional` / `undirected` | Directional: perpetrator → victim. Undirected: the label does not say which drug was measured |
| perpetrator, perpetrator_rxcui | string | Drug whose effect was tested (RxNorm ingredient). For undirected statements, the first drug of the pair |
| victim, victim_rxcui | string | Drug whose exposure or effect was measured |
| dimension | `PK` / `PD` / `PK+PD` / `not_stated` | Pharmacokinetic (exposure) or pharmacodynamic (effect) |
| parameters | list | Parameters named by the sentence (e.g. `auc_cmax`, `pk_unspecified`) |
| numeric_grade | `exposure_equivalent` / `weak_change` / `strong_change` / empty | From a label geometric-mean-ratio table in the same direction: 0.80–1.25; 0.50–2.00; ≤0.50 or ≥2.00 |
| numeric_gmr | list | Ratios read from the table |
| reverse_fda | `no_path` / `undetermined` / `path_possible` / `path_expected` | FDA index-table class of the undocumented (reverse) direction |
| condition_llm | `unconditional` / `conditional` / `uncertain` | Conditional when every supporting sentence is restricted (two agreeing model runs) |
| condition_types | list | `single_dose_perpetrator`, `victim_specific_product`, `perpetrator_specific_product`, `specific_route`, `staggered_administration`, `specific_dose_or_regimen`, `specific_population` |
| condition_quotes | list | Exact words carrying the restriction |
| restriction_strong | bool | Conditional with at least one of the first five types above (150 statements) |
| symmetric_phrasing_only | bool | Direction rests only on symmetric phrasing ("between A and B") (76 statements) |
| evidence | list | Per sentence: `unit_id`, `sentence`, `quote`, `label_in` (label ingredient RXCUI), `labels` (set_id, version, effective_time, section) |
| n_sentences, n_labels | int | Supporting sentences and label versions |

## nullddi_pairs.csv
| Field | Meaning |
|---|---|
| drug_a, drug_b, rxcui_a, rxcui_b | Pair (alphabetical by RXCUI) |
| status | `N2_bidirectional`, `N1_one_direction`, `N0_undirected_only` |
| documented | Documented direction(s), e.g. `quetiapine->antipyrine` |
| reverse_fda | For N1: class of the undocumented direction |

## nullddi_evidence_sentences.csv
`statement_id, unit_id, label_ingredient_rxcui, set_id, label_version, effective_time, section, quote, sentence`

## nullddi_accepted_units.jsonl
`unit_id, sentence, sentence_sha1, label_in_rxcuis, label_names, partner_in_rxcui, partner_name, flags, n_set_ids, sections, direction, direction_rule_A, direction_B, evidence_basis, parameters_assessed, quotes`
