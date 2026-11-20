"""NullDDI step 14 v1.1: label-text ground truth for conditional nulls.
Question: when a null is valid only under a restriction (single dose, one product, one route,
staggered timing), do the labels themselves document an interaction for the same directed pair
outside that restriction? If so, an unconditional "no clinically significant interaction"
answer is demonstrably wrong, not merely incomplete.

Evidence searched: every openFDA SPL label (same 14-part snapshot as step 01), sections
drug_interactions, clinical_pharmacology, pharmacokinetics, warnings_and_cautions,
contraindications, dosage_and_administration, boxed_warning. A sentence counts as a positive
statement for perpetrator P -> victim V when
  - it names P, and names V or sits in a label whose own ingredient is V (generic/substance name),
  - it carries a positive cue: a quantified change in exposure, or an action (avoid,
    contraindicated, not recommended, adjust/reduce/increase the dose, monitor ... levels),
  - it carries no negation cue (no clinically, did not, not affect, no effect, no significant ...).
v1.1: only the own label of V or of P is searched; sentences over 450 characters or listing more than four
items are skipped; in V's label the change must not be stated for P, and in P's label it must be stated for V
(exposure word followed by "of V" or "V" followed by an exposure word). Sentences are kept for audit.
Control: the same search for unconditional nulls (expected to be rarer).
Rules only; no human review. Output: ground_truth.jsonl + ground_truth_report.json
"""
import argparse, json, re, zipfile
from collections import Counter, defaultdict
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--labels", required=True); ap.add_argument("--condition", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
SECTIONS = ["drug_interactions", "clinical_pharmacology", "pharmacokinetics", "warnings_and_cautions",
            "contraindications", "dosage_and_administration", "boxed_warning", "warnings", "precautions"]
STRONG = {"single_dose_perpetrator", "victim_specific_product", "perpetrator_specific_product", "specific_route", "staggered_administration"}
POS = re.compile(r"(increas|decreas|reduc|elevat|lower|rais)\w*[^.;]{0,60}\b(auc|c ?max|exposure|concentration|level|plasma|bioavailability|clearance)"
                 r"|\b(auc|c ?max|exposure|concentration|level)s?\b[^.;]{0,60}(increas|decreas|reduc|elevat)\w*"
                 r"|\bavoid\b|contraindicated|not recommended|\b(reduce|increase|adjust|decrease)\w*\s+(the\s+)?(dose|dosage)"
                 r"|\bmonitor\w*[^.;]{0,40}\b(level|concentration)", re.I)
PK_OF = r"((auc|c ?max|exposure|concentrations?|levels?|clearance)\w*\s+(\w+\s+){{0,3}}of\s+{0}\b|\b{0}\s+(auc|c ?max|exposure|concentrations?|levels?|clearance))"
NEG = re.compile(r"no clinically|not clinically|no significant|not significantly|did not|does not|do not (alter|affect|change)|"
                 r"no effect|no meaningful|no relevant|not affect|not alter|no change|no dose adjustment|no apparent|unaffected|not expected", re.I)

nulls = []
for line in open(a.condition, encoding="utf-8"):
    x = json.loads(line)
    if x["kind"] != "directional":
        continue
    strong = x.get("condition_llm") == "conditional" and bool(set(x.get("condition_types", [])) & STRONG)
    grp = "strong_conditional" if strong else ("uncertain" if x.get("condition_llm") == "uncertain" else "general")
    nulls.append({"perp": x["perpetrator"].lower(), "vic": x["victim"].lower(), "perp_rxcui": x["perpetrator_rxcui"],
                  "vic_rxcui": x["victim_rxcui"], "group": grp, "types": sorted(set(x.get("condition_types", [])) & STRONG)})
names = {n["perp"] for n in nulls} | {n["vic"] for n in nulls}
names = {n for n in names if n and not n.isdigit() and len(n) >= 4}
by_name = defaultdict(list)
for i, n in enumerate(nulls):
    by_name[n["perp"]].append(i)
wb = {n: re.compile(r"\b" + re.escape(n) + r"\b", re.I) for n in names}
split = re.compile(r"(?<=[.;])\s+(?=[A-Z0-9])")


def scan(fp):
    hits, n_labels = defaultdict(list), 0
    z = zipfile.ZipFile(fp)
    for r in json.load(z.open(z.namelist()[0]))["results"]:
        of = r.get("openfda", {})
        own = {s.lower() for s in of.get("generic_name", []) + of.get("substance_name", [])}
        own_words = " ; ".join(own)
        text = " ".join(" ".join(r.get(s, [])) for s in SECTIONS)
        if not text:
            continue
        n_labels += 1
        low = text.lower()
        cand = [i for n in names if n in low for i in by_name.get(n, [])]
        sents = None
        for i in cand:
            nl = nulls[i]
            # v1.1: only the own labels of the two drugs (third-party labels list many drugs)
            vic_own, perp_own = nl["vic"] in own, nl["perp"] in own
            if not (vic_own or perp_own) or (vic_own and perp_own):
                continue
            other = nl["perp"] if vic_own else nl["vic"]
            if other not in wb or not wb[other].search(text):
                continue
            if sents is None:
                sents = split.split(text)
            for s in sents:
                if len(s) > 450 or s.count(",") > 4 or not wb[other].search(s):
                    continue
                if not (POS.search(s) and not NEG.search(s)):
                    continue
                # direction: the change must fall on the victim, not on the perpetrator
                if vic_own and re.search(PK_OF.format(re.escape(nl["perp"])), s, re.I):
                    continue
                if perp_own and not re.search(PK_OF.format(re.escape(nl["vic"])), s, re.I):
                    continue
                hits[i].append({"set_id": r.get("set_id"), "own": sorted(own)[:3], "label_of": "victim" if vic_own else "perpetrator",
                                "sentence": s[:600]})
    print(fp.name, n_labels, len(hits), flush=True)
    return dict(hits), n_labels


from multiprocessing import Pool
with Pool(2) as pool:
    res = pool.map(scan, sorted(Path(a.labels).glob("drug-label-*.json.zip")), chunksize=1)
hits, n_labels = defaultdict(list), 0
for h, n in res:
    n_labels += n
    for i, v in h.items():
        hits[i].extend(v)
out, rep = [], defaultdict(Counter)
for i, nl in enumerate(nulls):
    h = hits.get(i, [])
    nl["label_positive_for_pair"] = bool(h); nl["positive_sentences"] = h[:5]; nl["n_positive_sentences"] = len(h)
    rep[nl["group"]]["n"] += 1; rep[nl["group"]]["with_positive"] += bool(h)
    for t in nl["types"]:
        rep["type_" + t]["n"] += 1; rep["type_" + t]["with_positive"] += bool(h)
    out.append(nl)
Path(a.out).mkdir(parents=True, exist_ok=True)
with open(Path(a.out) / "ground_truth.jsonl", "w", encoding="utf-8") as f:
    for nl in out:
        f.write(json.dumps(nl, ensure_ascii=False) + "\n")
R = {"labels_scanned": n_labels, "groups": {k: dict(v, pct=round(100 * v["with_positive"] / v["n"], 1)) for k, v in rep.items()}}
(Path(a.out) / "ground_truth_report.json").write_text(json.dumps(R, indent=1)); print(json.dumps(R, indent=1))
