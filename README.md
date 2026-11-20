# NullDDI — documented drug non-interactions as structured claims

This repository holds the paper, data and code for

> A. Noor, M. Dumontier. **The missing negative: documented drug non-interactions are structured claims, and resources and algorithms flatten them.** Manuscript prepared for *PNAS* (v1.1, November 2026; not yet peer reviewed).

Drug-interaction resources record only interactions. NullDDI assembles the non-interactions that US drug labels actually document, extracted from 264,800 openFDA labels by two independent extractors and traced to their sentences:

- **1,032 directional statements** (perpetrator → victim) and 72 undirected statements
- **955 drug pairs**, 509 ingredients (RxNorm), 4,547 accepted label sentences
- each statement carries direction, dimension (PK / PD), a numeric grade where the label gives one, conditions (single dose, product, route, staggered dosing) and full provenance

## Contents

| Folder | What is in it |
|---|---|
| [`manuscript/`](manuscript/) | Manuscript and SI Appendix (PDF and Word), with the Markdown sources in `manuscript/source/` |
| [`figures/`](figures/) | Figures 1–4 (PDF and PNG) |
| [`data/NullDDI_v1.0/`](data/NullDDI_v1.0/) | The NullDDI v1.0 data release: statements, pairs, evidence sentences, accepted units, data dictionary, checksums (CC BY 4.0) |
| [`code/`](code/) | The full pipeline that builds the release and reproduces every analysis in the paper (MIT) |
| [`VERIFICATION_REPORT.md`](VERIFICATION_REPORT.md) | Every number in the manuscript checked against the run outputs; reference and format checks |

Start with [`data/NullDDI_v1.0/README.md`](data/NullDDI_v1.0/README.md) to use the data, and [`code/README.md`](code/README.md) to rerun the pipeline.

## Third-party resources

No record from DDInter, D3, PK-DDI DB or NHANES is redistributed here. The scripts that compare NullDDI with those resources expect you to obtain them from their providers under their own licences. Language-model scripts read API keys from the environment; no key is stored in any file.

## Licences

Data: [CC BY 4.0](data/NullDDI_v1.0/LICENSE.txt). Code: [MIT](code/LICENSE.txt). Source label texts are US government works (openFDA).

## Citation

See [`CITATION.cff`](CITATION.cff).

## Not medical advice

NullDDI records what drug labels state. It is a research resource, not a clinical decision tool.

---

### Looking for Anti-DDI v3?

This repository was previously **Anti-DDI v3.0.1** (the resource cited by the manuscript *Evidence-Graded Negative Controls for Drug-Drug Interaction Evaluation*). That content is preserved unchanged on the branch [`archive/anti-ddi-v3-main`](https://github.com/adeebnoor/NullDDI/tree/archive/anti-ddi-v3-main); all other earlier branches are kept as they were.
