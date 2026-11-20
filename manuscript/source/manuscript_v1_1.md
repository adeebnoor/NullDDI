---
title: "The missing negative: documented drug non-interactions are structured claims, and resources and algorithms flatten them"
---

**Authors:** Adeeb Noor^a,1^ and Michel Dumontier^b^

^a^ Department of Information Technology, Faculty of Computing and Information Technology, King Abdulaziz University, Jeddah, Saudi Arabia. ^b^ Institute of Data Science, Faculty of Science and Engineering, Maastricht University, Maastricht, The Netherlands.

^1^ To whom correspondence may be addressed. Email: arnoor@kau.edu.sa. ORCID: A.N. 0000-0002-8251-1853; M.D. 0000-0003-4727-9435.

**Classification:** Biological Sciences — Medical Sciences; Physical Sciences — Computer Sciences.

**Keywords:** negative knowledge; drug–drug interactions; drug labels; machine learning; language models

**Author contributions:** A.N. and M.D. conceived the research question; A.N. designed the study, wrote the code, performed the analyses and wrote the paper; M.D. advised on knowledge representation and revised the paper.

**Competing interest statement:** The authors declare no competing interest.

## Abstract

Drug-interaction knowledge is recorded almost entirely as positives. Unlisted pairs are treated as safe by clinicians and as negative training labels by prediction algorithms, yet documented non-interactions have rarely been assembled or examined as claims. We extracted them from 264,800 US drug labels with two independent extractors, accepting only statements on which both agreed and tracing each to its sentence: 1,032 directional statements covering 955 pairs. These statements are structured. Only 14% of pairs are documented in both directions, a pattern replicated in European labels and in an independent manually curated resource. Ninety-three percent concern drug exposure rather than effect; they are clinical-relevance judgments that can coexist with a tripling of exposure; and one in seven holds only for a single dose, a specific product or a route. In a nationally representative survey, 10.9 million US residents used a pair cleared in one direction with no evidence on the other, and 3.6 million used a pair whose only statements were restricted. A widely used database listed 34% of documented pairs as interactions. Three prediction models trained in the standard way raised 1.5 to 1.7 times more false alarms on documented negatives than on the random negatives used for benchmarking, partly because of the drugs involved; adding documented negatives to training cut these alarms by 30%. Language models from three developers warned more often on one-direction pairs, and one model given restricted statements generalized them in 97% of cases. Negative evidence must be represented with its direction, dimension and conditions.

## Significance Statement

Drug-interaction resources record only interactions. The absence of an entry is read as safety by clinicians and as a negative label by prediction algorithms. We assembled 1,032 regulator-documented non-interactions from US drug labels and found that they are structured claims: directional, specific to drug exposure, judged by clinical relevance rather than equivalence, and in one case in seven valid only for a particular dose or product. About 11 million US residents take a pair cleared in one direction only. Prediction models benchmarked on assumed negatives raise about 1.6 times more false alarms on documented ones, and a language model generalizes restricted statements even when shown them. Negative evidence must be recorded with its structure.

## Introduction

Negative results are reported and curated far less often than positive ones. In medicine the imbalance has a direct cost: a prescriber choosing between two drugs needs to know which combinations are safe as much as which are dangerous, yet the resources that support that choice record almost only interactions (1, 2).

Drug–drug interactions are the clearest case. Interaction databases, clinical decision support systems and, increasingly, large language models answer questions about pairs of drugs. When a pair is absent from a database, the absence is ambiguous: the pair may have been studied and found not to interact, or never studied at all. Clinical alerting systems resolve the ambiguity by warning, and clinicians override most interaction alerts (3). Alerting that takes into account when a pair does not interact in a given patient removes most of these alerts without losing sensitivity (4, 5), but it depends on negative knowledge that databases rarely hold. Language models resolve the ambiguity by inference from drug classes, which can be right or wrong (6).

Yet a large body of documented non-interaction already exists. Regulators require sponsors to study interactions with likely co-medications, and the results, including null results, are written into the product label (7). A label sentence such as "no clinically significant differences in the pharmacokinetics of drug B were observed when co-administered with drug A" is regulator-reviewed evidence. To our knowledge, these sentences have not been assembled as statements and their logical form has not been examined.

We asked three questions. First, can label-documented non-interactions be extracted at scale with sentence-level provenance and without human curation? Second, what kind of claim is a regulatory non-interaction statement? Third, do the resources people use, the prediction models built on them and the language models people increasingly consult represent that claim correctly, and how many people take drug pairs where the answer matters?

We find that a non-interaction statement has four properties. It is directional (drug A does not alter drug B, which says nothing about B altering A), specific to one dimension (exposure or effect), a regulatory judgment of clinical relevance rather than a claim of equivalence, and sometimes conditional on dose, product or route. We refer to these properties as the structure of negative evidence. A widely used interaction database, standard prediction models and four language models from three developers do not represent this structure, and population data show that the gaps it leaves concern millions of people.

Label-derived negatives are not new in themselves: Jang et al. manually extracted 2,438 pairs whose exposure ratio fell within 0.80–1.25 from FDA labels to train an exposure model, noting that interaction databases hold no record that a pair does not interact (2). Our reference adds 566 directional statements absent from that resource, but our question is different: what kind of claim a non-interaction is, and what its absence from resources costs. This work also builds on earlier efforts to represent drug-interaction mechanisms (8) and to assemble non-interaction evidence (9), and it complements a study of evidence-graded negative controls for interaction evaluation in pharmacovigilance data (10).

## Results

### An open, sentence-traceable reference of documented non-interactions

We processed a full snapshot of US drug labels from openFDA (11) (November 2026; 264,800 labels with interaction or pharmacology text). A rule-based extractor (A) proposed 115,275 candidate non-interaction records. A language-model extractor (B) read each candidate sentence independently, four times under two prompt orders, and returned the perpetrator, the victim, the direction and whether the sentence states a non-interaction. A statement entered the reference only when A and all four B runs agreed and the direction was consistent.

Agreement was high. Across the 5,250 unflagged candidates, B's runs under swapped prompt orders agreed on acceptance with Cohen's κ = 0.93, on the finding with κ = 0.90 and on direction with κ = 0.97, same-order re-runs agreed on 99.7% of decisions, and 4,547 (86.6%) were accepted. A repeated-execution check (ridi-check; 12) showed that presentation order changed 2.4% of first-run decisions against an execution floor of 0.8%; every such unit is excluded from the reference by design (*SI Appendix*, Table S2).

The reference holds 1,032 directional statements (perpetrator → victim) and 72 undirected ones, covering 955 drug pairs and 509 ingredients normalized to RxNorm. Every statement links to its sentence, label set identifier, version and section. The reference contains no human-curated content and is released under CC BY 4.0 (Fig. 1). As an external check, we compared it with PK-DDI DB, whose negatives were curated by hand from the same kind of labels (2): of 466 directional statements present in both, 455 (97.6%) are negatives there, and the remaining 11 are exposure changes that the labels judged not clinically significant.

### Non-interaction is directional

A label states that a perpetrator does not alter a victim; it rarely states the reverse. Of the 955 pairs, 136 (14.2%) are documented in both directions, 760 (79.6%) in one direction only and 59 (6.2%) only by undirected statements. Four of five documented non-interacting pairs therefore leave one direction unaddressed. Some labels phrase a result symmetrically ("no clinically significant interaction between A and B"); we counted these as covering both directions, as written. Reading them instead as undirected lowers the bidirectional share to 9.8% and raises the one-direction share to 80.4% (*SI Appendix*, Table S3).

The pattern is not an artifact of one regulator or one method. Applying the same rules to 1,162 European Medicines Agency product information documents gave 329 pairs, of which 61.4% were documented in one direction only, against 63.3% for FDA labels at the same pipeline stage (Fig. 2). Of 99 pairs whose direction both regulators resolved, 79 had identical direction sets, 16 overlapped and 4 were complementary, each regulator documenting the direction the other omitted. The same asymmetry appears in a resource built by hand: in PK-DDI DB, whose negatives were curated manually from exposure ratios (2), only 536 of 2,290 negative pairs (23.4%) are recorded in both directions.

For most one-direction pairs, the missing direction cannot be inferred. Using the FDA tables of clinical index inhibitors, inducers and substrates (13), a pathway for the undocumented direction could be ruled out for only 129 of 1,032 statements and was undetermined for 888, because one of the drugs is not profiled.

### Non-interaction is dimension-specific and regulatory

Of the 1,032 directional statements, 961 (93.1%) concern pharmacokinetics only, 45 both pharmacokinetics and pharmacodynamics, 14 pharmacodynamics only and 12 do not say. A statement that drug A does not change the exposure of drug B is silent on whether their effects add up, for example on sedation, bleeding or blood pressure.

The statements are clinical-relevance judgments, not equivalence claims. For 58 statements the same label gives a geometric mean ratio for the same direction: 46 fall within the conventional no-effect band of 0.80–1.25, 10 show a weak change and 2 a strong one. Both strong cases come from one label, which reports no clinically significant change in doravirine concentrations with ketoconazole and with ritonavir while its own table shows doravirine exposure ratios of 3.06 and 3.54. A tripling of exposure was judged clinically acceptable. PK-DDI DB, which defines a negative by the 0.80–1.25 band, records these 11 statements as exposure changes (2).

### Non-interaction is often conditional

Some statements hold only under the conditions of the study that produced them. We asked a language model, twice and independently, whether each of the 2,548 distinct evidence sentences restricts its statement, and accepted fields on which both runs agreed (agreement 98.6–99.3% by field). A statement was classed as conditional when every sentence supporting it carried a restriction.

One statement in seven (150 of 1,032; 14.5%) is valid only under a restriction that matters in practice: a single dose of the perpetrator (56), a specific product of the victim (44) or of the perpetrator (41), one route (20) or staggered administration (11); a statement can carry more than one. A further 178 statements mention only the study's dose or population; we did not count these as conditional. Examples include a single dose of rifampin with selpercatinib, whereas repeated rifampin lowers selpercatinib exposure by 87% according to the same label, and omeprazole with levothyroxine, a statement that applies only to one oral solution.

### Millions of people take pairs where the structure matters

We linked the reference to the prescription medication files of the US National Health and Nutrition Examination Survey (NHANES 2017–March 2020, 15,560 participants, weighted to 322.3 million residents) (14). A participant counted as using a pair when both ingredients were reported in separate products in the past 30 days; pairs found only inside one fixed-dose combination were not counted. All estimates below have a relative standard error under 30% and meet NCHS reliability criteria (15).

An estimated 15.1 million residents (SE 1.1 million) used at least one pair with a generalizable documented non-interaction. For 12.3 million the pair was documented in one direction only, and for 10.9 million (SE 0.8 million) neither the label nor the FDA index tables said anything about the other direction. Only 2.5 million used a one-direction pair whose missing direction the tables could rule out, and 3.1 million used a pair documented in both directions (Fig. 3).

Restricted statements matter at the same scale. An estimated 3.6 million residents (SE 0.7 million) used a pair whose only documented non-interaction is conditional. The largest single pair is levothyroxine with omeprazole (about 2 million users), for which the label statement covers one oral solution while most users take tablets, whose absorption depends on gastric acidity (16–18).

### Databases and language models do not represent the structure

**An interaction database.** DDInter 2.0 (19), a widely used open interaction database, contained both drugs of 735 documented pairs and listed 251 (34.1%) of them as interactions, including 31.0% of pairs documented in both directions. Its downloadable records carry a severity level but no direction and no mechanism. To ask which dimension those listings concern, we used mechanism annotations from an earlier knowledge base (D3) (8): of 96 documented pairs annotated there as interacting, 56 carried only a pharmacodynamic mechanism. Of 25 pairs whose label statement is purely pharmacokinetic yet carried a pharmacokinetic mechanism in D3, 23 were documented in one direction only, consistent with an interaction in the undocumented direction rather than a contradiction.

**Language models.** We asked four models from three developers whether the perpetrator changes the victim's exposure to a clinically significant degree, with no label text, twice per model: 1,032 documented non-interactions, 894 established interactions from the FDA index tables (strong inhibitor or inducer with a sensitive substrate) and 698 reversed versions of those interactions. We report answers that were identical in both runs (*SI Appendix*, Table S8).

All four models recognized established interactions (88.0–99.7%), and none simply transferred an interaction to the reverse direction; most warnings on reversed pairs involved HIV protease inhibitors that the FDA tables list only as substrates although they also inhibit CYP3A. Warnings on documented non-interactions were more frequent in every model when only one direction was documented (5.1–10.6% versus 1.1–1.9%; odds ratios 3.0–6.3, Fisher's exact *P* = 0.03 to <0.001; Fig. 4*A*). Part of this gap reflects which drugs appear in one-direction statements; within the same perpetrator or the same victim drug the difference kept its direction in all four models (Mantel–Haenszel odds ratios 1.2–6.9), but these within-drug comparisons rest on few warnings (*SI Appendix*, Table S8b). Three of the four models answered "no clinically significant interaction" without qualification for 73–87% of statements that hold only under a restriction.

Unqualified reassurance is unsupported rather than proven wrong in most cases. For 18 of the 150 conditional statements (12.0%; control 6.7% of 150 general statements), the labels themselves document an interaction outside the restriction, as adjudicated by a model in two agreeing runs. Models still answered "no interaction" for 33–50% of these 18 pairs.

Supplying the evidence does not repair this. When one model (Sonnet 5.5) was given the label sentence, or a structured record stating the direction, dimension and restriction, it answered the documented direction correctly (99.2–99.7%) and became more cautious about the undocumented one ("insufficient evidence" rose from 13.9% to 30.5–32.6%). For restricted statements, however, unqualified reassurance rose from 77.3% without evidence to 97.3% with it, even when the record stated that the statement held only for a single dose. For the pairs whose labels document an interaction outside the restriction, wrong reassurance rose from 8 of 18 (44%) to 14 of 18 (78%) (Fig. 4*B*).

### Without documented negatives, predictors look more specific than they are

Interaction prediction models are trained and evaluated with randomly drawn unlisted pairs standing in for non-interactions, because no source of true negatives has been available (20, 21). We reproduced this practice with open inputs: 30,000 interacting pairs from DDInter as positives, molecular fingerprints and ATC classes as features, two standard classifiers and five random seeds, with every documented pair removed from training. We then scored 396 documented non-interacting pairs that DDInter does not list.

At the threshold giving 90% sensitivity on held-out interactions, documented non-interactions drew 1.6–1.7 times more false alarms than the random pairs used as negatives in standard benchmarks (logistic regression 62.9% versus 36.9%; gradient boosting 47.6% versus 29.0%), and discrimination fell by 0.11–0.14 AUROC (*SI Appendix*, Tables S10 and S11). The excess persisted for the 71 pairs documented in both directions (54.4% and 37.2%). Part of this excess reflects the drugs involved: documented pairs concern well-studied drugs with many listed interactions. Random unlisted pairs formed from the same 291 drugs drew 53.3% and 38.6% false alarms, and documented pairs still drew about 10 percentage points more (63.1% and 48.6% in the same runs), in every seed and for both models (*SI Appendix*, Table S10b). Sampling random pairs in proportion to each drug's number of listed interactions, a common way to make benchmarks harder, raised false alarms further (77.9% and 66.0%), but such pairs are not known to be negative; documented non-interactions are. The 236 documented pairs that DDInter lists as interactions were flagged in 96% of cases, so database listings pass directly into learned models, and the call on 17–27% of documented pairs changed with the random seed alone.

The pattern held for a third, DeepDDI-style model (22) built on structural similarity profiles (false alarms 64.7% on documented versus 42.9% on random negatives). Documented negatives also improved the models. Adding them to training, in five-fold cross-validation, cut false alarms on unseen documented pairs from 47.5% to 33.2% without changing the usual benchmark (AUROC 0.889 versus 0.888; Fig. 4*C*).

## Discussion

Regulatory statements of non-interaction carry a direction, a dimension, a standard of clinical relevance and, often, a condition. These properties can be read from the label text without human curation, and the directional pattern recurs in a second regulator and in a manually curated resource. Storing such a statement as an unordered pair, or answering it as a yes-or-no question, discards them.

The consequences differ by system. The interaction database lists documented pairs as interactions at a similar rate whether one or both directions are documented (34.1% vs 31.0%), as expected of a store without direction. Prediction models trained without any documented negative assign interaction-like scores to many of them, and benchmarks built from random pairs do not reveal this. The language models distinguish the two directions to some extent, but warn more often on one-direction statements, and three of four generalize statements that hold only for one dose or product; supplying the statement to one model increased this. The common factor is that the qualifiers of negative evidence are not available to these systems in a usable form.

The population estimates indicate how often these gaps arise in practice. About 10.9 million US residents use a pair for which the label documents one direction and neither the label nor the FDA tables address the other. This does not show harm. It shows that, for these patients, the open sources we examined give no documented answer to whether the second drug is affected.

We draw three practical conclusions. First, interaction resources should store negative statements as first-class records carrying direction, dimension, numeric effect where available and condition, with provenance to the sentence, as consensus recommendations already ask of interaction evidence (23); a FAIR, nanopublication-style representation of negative assertions is a natural fit (24, 25). Second, prediction models should be trained and benchmarked with documented negatives; in our experiment a few hundred of them reduced false alarms on new documented pairs by 30% without changing the usual benchmark. Third, evaluations of language models in pharmacology, and retrieval systems that feed them evidence, should test negative and conditional knowledge, not only recall of known interactions. Where the reverse direction has already been studied, closing the gap may require only one added sentence in the label.

The study has limits. The reference covers single-ingredient US labels and English EMA documents, and extraction depends on how labels phrase results. Extraction, conditions and adjudications relied on a language model with agreeing runs rather than on experts, and a model of the same family (Sonnet 5.5) was also among the models evaluated, although it answered without label text and the other developers' models behaved similarly; the 178 statements tied only to a study dose or population were deliberately left unconditional, which makes our estimates conservative. The undocumented direction has no ground truth, so for it we measure caution, not correctness. NHANES records use within 30 days, not same-day co-administration, and predates some recent drugs. DDInter's mechanism information was not available for its listings, and D3 covers a minority of them. The prediction experiments use standard architectures rather than every published model, and the remedy experiment split documented pairs, not drugs, between folds; the evidence experiment used one language model. Finally, the language-model results describe the models available in November 2026.

## Materials and Methods

Protocols, prompts (with SHA-256 hashes), code and run logs are in *SI Appendix* and the code release. No step used human annotation.

**Labels.** openFDA drug label snapshot (14 files, retrieved 17 November 2026). Ingredients were normalized to RxNorm (26) (release of 2 November 2026) with DailyMed set-identifier mappings; the reference is restricted to single-ingredient labels.

**Extractor A (rules).** Sentence segmentation, a negation lexicon, partner detection against 2,660 RxNorm ingredients, direction from the grammatical subject and object of the negated clause, and flags for weak evidence (long sentences, population pharmacokinetics, table-like text, endogenous substances, positive cues, partial parameters, regimen partners).

**Extractor B (language model).** claude-sonnet-5-5 through a batch interface with a strict JSON schema and default sampling settings, four runs (two presentation orders, each repeated). Acceptance required agreement of A and all four runs on the finding and a consistent direction; units on which A and B gave opposite single directions (138) or on which B's runs disagreed (59) were rejected. Where B left the direction unspecified, A's direction was used (162 units, all phrased "between A and B"; sensitivity analysis in *SI Appendix*). Execution stability was assessed with ridi-check 0.10.1 (12).

**Numeric grade.** Geometric mean ratios parsed from label tables whose caption resolves the direction; 0.80–1.25 = no effect, 0.50–2.00 = weak change, ≤0.50 or ≥2.00 = strong change.

**Undocumented direction.** FDA tables of clinical index inhibitors, inducers and substrates (13) classify the undocumented direction as no pathway, pathway expected or possible, or undetermined.

**EMA replication.** 1,162 originator product information documents (English), section 4.5, extractor A rules with an EU→US name table.

**PK-DDI DB comparison.** The released PK-DDI DB file (4,277 directional rows) was mapped from DrugBank to RxNorm through Wikidata; a pair is negative when its fold change lies within 0.80–1.25 (2). Used for analysis only.

**Conditions.** Each distinct evidence sentence was classified twice by claude-sonnet-5-5 for dosing, product, route and population restrictions; fields were accepted on agreement; a statement is conditional when all its sentences are restricted. To test whether restricted statements generalize, candidate sentences from the two drugs' own labels (up to 15 per statement) were adjudicated twice, with a random control of 150 general statements (seed 20261120).

**Population exposure.** NHANES 2017–March 2020 prescription medication and demographic files (14); drug names were split into ingredients and mapped to RxNorm; interview weights; Taylor-series standard errors over strata and primary sampling units; NCHS reliability criteria (15). A pair is generalizable when at least one of its directional statements carries no strong restriction.

**Interaction database and D3.** DDInter 2.0 downloadable files (19) (analysis only; not redistributed). D3 gold annotations (8) mapped from UMLS to RxNorm through Wikidata (1,064 of 1,599 concepts).

**Language models.** claude-sonnet-5-5 and claude-haiku-5-5 (Anthropic batch interface, strict schema); openai/gpt-6.2-sol and google/gemini-4-carbon (OpenRouter, JSON requested by one added instruction line). The same 2,624 questions and system prompt were used for all models, two runs each; a stable answer is identical in both runs. For the second Gemini run, 2,059 of 2,624 questions completed; its rates use those questions. In the evidence experiment, Sonnet 5.5 answered 882 documented-direction items (statements without a strong restriction), 760 reversed-direction items and 150 restricted items under three arms (no evidence, label sentence, structured record), twice each.

**Prediction models.** Positives: 30,000 DDInter pairs (fixed sample, seed 7). Drugs: Morgan fingerprints (radius 2, 1,024 bits) from Wikidata structures plus ATC level-2 classes; symmetric pair encoding (OR and AND). Models: logistic regression (C = 0.5) and histogram gradient boosting (300 iterations), five seeds; negatives: random unlisted pairs; every documented pair removed from training. The DeepDDI-style model used structural-similarity profiles (2,048-bit fingerprints) and a two-layer perceptron (256, 64). The remedy experiment added documented negatives to training (sample weight 5) and scored held-out documented pairs by five-fold cross-validation.

**Statistics.** Agreement: Cohen's κ. Survey estimates: weighted totals with Taylor-series standard errors and 95% CIs. Language models: Wilson 95% CIs; one- versus two-direction warning rates by Fisher's exact test and, within perpetrator or victim strata, by the Mantel–Haenszel odds ratio. Predictors: AUROC and false-alarm rate at the threshold giving 90% sensitivity on held-out positives, mean and SD over five seeds. Control negatives: random unlisted pairs drawn from the drugs of the documented pairs (drug-matched) or with probability proportional to each drug's number of DDInter interactions (degree-weighted), five times the documented set, excluding listed and documented pairs.

**Use of AI tools.** Apart from the language models studied and used as extractors (described above), Claude (Anthropic) assisted with writing analysis code and with drafting and editing the text. The authors reviewed the code, verified every number against the analysis outputs and take full responsibility for the content.

## Data, Materials, and Software Availability

The reference (1,032 directional and 72 undirected statements, 955 pairs, 4,547 accepted sentence units, evidence sentences with label set identifiers, condition annotations and the symmetric-phrasing flag) is released under CC BY 4.0 on Zenodo (DOI to be assigned on deposit). Code is released under the MIT licence with the same record. ridi-check is available at https://github.com/adeebnoor/ridi-check (doi:10.5281/zenodo.24193754). openFDA labels, RxNorm, the FDA interaction tables and NHANES are public. DDInter 2.0, D3 and PK-DDI DB were used for analysis only and are not redistributed; the scripts reproduce every comparison from the public downloads.

## Acknowledgments

The authors received no specific funding for this work.

## References

1. S. Ayvaz et al., Toward a complete dataset of drug-drug interaction information from publicly available sources. *J. Biomed. Inform.* **55**, 206–217 (2015).
2. H. Y. Jang et al., Machine learning-based quantitative prediction of drug exposure in drug-drug interactions using drug label information. *NPJ Digit. Med.* **5**, 88 (2022).
3. H. van der Sijs, J. Aarts, A. Vulto, M. Berg, Overriding of drug safety alerts in computerized physician order entry. *J. Am. Med. Inform. Assoc.* **13**, 138–147 (2006).
4. J. Horn, S. Ueng, The effect of patient-specific drug-drug interaction alerting on the frequency of alerts: A pilot study. *Ann. Pharmacother.* **53**, 1087–1092 (2019).
5. S. N. Shah, D. L. Seger, J. M. Fiskio, J. R. Horn, D. W. Bates, Comparison of medication alerts from two commercial applications in the USA. *Drug Saf.* **44**, 661–668 (2021).
6. F. Y. Al-Ashwal, M. Zawiah, L. Gharaibeh, R. Abu-Farha, A. N. Bitar, Evaluating the sensitivity, specificity, and accuracy of ChatGPT-3.5, ChatGPT-4, Bing AI, and Bard against conventional drug-drug interactions clinical tools. *Drug Healthc. Patient Saf.* **15**, 137–147 (2023).
7. International Council for Harmonisation, "M12 Drug Interaction Studies" (ICH Harmonised Guideline, adopted 21 May 2024; issued by the US Food and Drug Administration as final guidance, August 2024).
8. A. Noor, A. Assiri, S. Ayvaz, C. Clark, M. Dumontier, Drug-drug interaction discovery and demystification using Semantic Web technologies. *J. Am. Med. Inform. Assoc.* **24**, 556–564 (2017).
9. A. Assiri, A. Noor, Anti-DDI resource: A dataset for potential negative reported interaction combinations to improve medical research and decision-making. *J. Healthc. Eng.* **2022**, 8904342 (2022). Retracted in: *J. Healthc. Eng.* **2023**, 9892301 (2023).
10. A. Noor, Evidence-graded negative controls for drug-drug interaction evaluation. Submitted.
11. T. A. Kass-Hout et al., OpenFDA: An innovative platform providing access to a wealth of FDA's publicly available data. *J. Am. Med. Inform. Assoc.* **23**, 596–600 (2016).
12. A. Noor, ridi-check (software). Zenodo. https://doi.org/10.5281/zenodo.24193754. Deposited 2026.
13. US Food and Drug Administration, Drug development and drug interactions: Table of substrates, inhibitors and inducers. https://www.fda.gov/drugs/drug-interactions-labeling/drug-development-and-drug-interactions-table-substrates-inhibitors-and-inducers. Accessed 18 November 2026.
14. B. Stierman et al., National Health and Nutrition Examination Survey 2017–March 2020 prepandemic data files: Development of files and prevalence estimates for selected health outcomes. *Natl. Health Stat. Rep.* **158** (2021).
15. J. D. Parker et al., National Center for Health Statistics data presentation standards for proportions. *Vital Health Stat. 2* **175**, 1–22 (2017).
16. M. Centanni et al., Thyroxine in goiter, *Helicobacter pylori* infection, and chronic gastritis. *N. Engl. J. Med.* **354**, 1787–1795 (2006).
17. I. Sachmechi et al., Effect of proton pump inhibitors on serum thyroid-stimulating hormone level in euthyroid patients treated with levothyroxine for hypothyroidism. *Endocr. Pract.* **13**, 345–349 (2007).
18. C. Seng Yue, S. Benvenga, C. Scarsi, L. Loprete, M. P. Ducharme, When bioequivalence in healthy volunteers may not translate to bioequivalence in patients: Differential effects of increased gastric pH on the pharmacokinetics of levothyroxine capsules and tablets. *J. Pharm. Pharm. Sci.* **18**, 844–855 (2015).
19. Y. Tian et al., DDInter 2.0: An enhanced drug interaction resource with expanded data coverage, new interaction types, and improved user interface. *Nucleic Acids Res.* **53**, D1356–D1362 (2025).
20. Y. Zheng et al., DDI-PULearn: A positive-unlabeled learning method for large-scale prediction of drug-drug interactions. *BMC Bioinformatics* **20**, 661 (2019).
21. X. Lin et al., Comprehensive evaluation of deep and graph learning on drug–drug interactions prediction. *Brief. Bioinform.* **24**, bbad235 (2023).
22. J. Y. Ryu, H. U. Kim, S. Y. Lee, Deep learning improves prediction of drug-drug and drug-food interactions. *Proc. Natl. Acad. Sci. U.S.A.* **115**, E4304–E4311 (2018).
23. R. T. Scheife et al., Consensus recommendations for systematic evaluation of drug–drug interaction evidence for clinical decision support. *Drug Saf.* **38**, 197–206 (2015).
24. M. D. Wilkinson et al., The FAIR Guiding Principles for scientific data management and stewardship. *Sci. Data* **3**, 160018 (2016).
25. J. M. Banda, T. Kuhn, N. H. Shah, M. Dumontier, "Provenance-centered dataset of drug-drug interactions" in *The Semantic Web – ISWC 2015*, Lecture Notes in Computer Science (Springer, 2015), pp. 293–300.
26. S. J. Nelson, K. Zeng, J. Kilbourne, T. Powell, R. Moore, Normalized names for clinical drugs: RxNorm at 6 years. *J. Am. Med. Inform. Assoc.* **18**, 441–448 (2011).

## Figure legends

**Fig. 1. From labels to a structured reference.** (*A*) Pipeline without human curation: 264,800 US labels (openFDA) → 115,275 candidate records from the rule-based extractor A → four independent readings by a language model (extractor B) → 4,547 sentences accepted when A and all four B runs agree → 1,032 directional statements covering 955 pairs and 509 ingredients, each traceable to its sentence. (*B*) The four properties of one record, illustrated with rifampin → selpercatinib: direction (the reverse is not documented), dimension (pharmacokinetics, not effect), standard (clinical relevance, not equivalence) and condition (a single dose of rifampin; the same label reports an 87% fall in selpercatinib AUC with repeated doses).

**Fig. 2. Most documented non-interactions cover one direction only.** Share of documented non-interacting pairs covered in both directions (dark grey), in one direction only (blue) or only by undirected statements (light grey), in four sources: the final reference (955 pairs), FDA labels after the rules only (1,160 pairs), EMA product information after the same rules (329 pairs) and PK-DDI DB, an independent manually curated resource (2) (2,290 negative pairs).

**Fig. 3. The gap at population scale.** Estimated US residents (millions; 95% CI, Taylor-series) who reported both drugs of a pair, from separate products, in the past 30 days. Top bar: any pair with a generalizable documented non-interaction. Below it, by direction: one direction only, of which the other direction has no evidence in labels or FDA index tables (blue) or is ruled out by those tables, and both directions. Bottom bar (blue): a pair whose only statements are restricted. Groups overlap because one person can use several pairs. NHANES 2017–March 2020; 15,560 participants weighted to 322.3 million.

**Fig. 4. Language models and prediction models.** (*A*) Share of documented non-interactions on which four language models warned (answers identical in two runs, no label text), for pairs documented in both directions (grey) and in one direction only (blue). (*B*) Share of the 150 restricted statements that Sonnet 5.5 answered "no clinically significant interaction" when given no evidence, the label sentence, or a structured record stating direction, dimension and restriction; blue, the 18 statements whose labels document an interaction outside the restriction. (*C*) False alarms at 90% sensitivity for three prediction models trained with DDInter interactions and randomly drawn negatives, on random negatives (grey) and on documented non-interactions (blue); open circles, random pairs of the same drugs as the documented pairs; diamond, gradient boosting with documented negatives added to training (five-fold cross-validation).
