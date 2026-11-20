"""NullDDI step 11 v1.0: condition tags for released nulls (dataset v0.2 field `condition`).
A label null can be conditional on the perpetrator's dosing (single dose, a stated dose
level, staggered timing) or specific to one product/formulation of the label's own drug.
Tags are derived from the evidence sentence only (rules, no human review):
  single_dose_perpetrator  "single dose" tied to the perpetrator
  dose_qualified           a dose level / "lower doses" tied to the perpetrator
  staggered_timing         separated administration
  formulation_specific     own drug named by brand or by a dosage form in the null clause
A null is `conditional` when EVERY evidence sentence carries at least one tag, `unconditional`
when none does, `mixed` otherwise. Output: tagged jsonl + stats json."""
import argparse, json, re
from collections import Counter
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument("--nulls", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
FORM = r"(?:delayed[- ]release|extended[- ]release|orally disintegrating|oral (?:solution|suspension)|injection|intravenous|subcutaneous|transdermal|ophthalmic|topical|nasal spray|inhal\w+)"
NOTBRAND = {"CYP", "AUC", "CMAX", "UGT", "OATP", "BCRP", "MATE", "HIV", "TDF", "QTC", "INR", "NSAID", "NSAIDS", "DNA", "RNA", "FDA", "PPI",
            "PPIS", "OCT", "OAT", "HCV", "HBV", "CNS", "SSRI", "SSRIS", "MAO", "MAOI", "ACE", "PGP", "TMAX", "CLCR", "EGFR", "ECG", "HMG", "COA"}
def near(s, name, pat, w=60):
    out = False
    for m in re.finditer(re.escape(name), s, re.I):
        seg = s[max(0, m.start() - w): m.end() + w]
        if re.search(pat, seg, re.I):
            out = True
    return out
def tags(s, perp, own_is_victim):
    t = set()
    names = [perp] if perp else []
    for n in names:
        if near(s, n, r"single[- ]dose"):
            # exclude "single dose of <victim>" patterns where the phrase sits right before another drug name
            if re.search(r"single[- ]dose(?: of)?(?: \w+){0,2} " + re.escape(n), s, re.I) or re.search(re.escape(n) + r"[^.;]{0,40}single[- ]dose\)", s, re.I) \
               or re.search(re.escape(n) + r" \([^)]*single[- ]dose", s, re.I):
                t.add("single_dose_perpetrator")
        if re.search(r"(?:lower|low|higher|high|therapeutic) doses?[^.;]{0,30}" + re.escape(n), s, re.I) or \
           re.search(re.escape(n) + r"[^.;,]{0,12}\(?\d+(?:\.\d+)? ?(?:mg|mcg|g)\b", s, re.I) or \
           re.search(r"doses? (?:of |up to )?\d+[^.;]{0,25}" + re.escape(n), s, re.I):
            t.add("dose_qualified")
    if re.search(r"\b\d+ ?(?:hours?|h) (?:before|after|apart)|separated by|staggered", s, re.I):
        t.add("staggered_timing")
    brand = [w for w in re.findall(r"\b[A-Z][A-Z\-]{3,}\b", s) if w.replace("-", "") not in NOTBRAND and not re.match(r"^(CYP|UGT|OATP|OAT|OCT|MATE)", w)]
    if own_is_victim is not None and (brand or re.search(FORM, s, re.I)):
        t.add("formulation_specific")
    return t
st, per_tag, by_dim = Counter(), Counter(), Counter()
out = []
for line in open(a.nulls, encoding="utf-8"):
    x = json.loads(line)
    perp = x.get("perpetrator")
    ev_t = []
    for e in x["evidence"]:
        own_v = (e.get("label_in") == x.get("victim_rxcui")) if x["kind"] == "directional" else None
        tg = tags(e["sentence"], perp, own_v) if x["kind"] == "directional" else set()
        e["condition_tags"] = sorted(tg); ev_t.append(tg)
    n_tag = sum(1 for t in ev_t if t)
    x["condition"] = "conditional" if n_tag == len(ev_t) and n_tag else "unconditional" if n_tag == 0 else "mixed"
    dose = {"single_dose_perpetrator", "dose_qualified", "staggered_timing"}
    x["condition_dose"] = "conditional" if all(t & dose for t in ev_t) and ev_t else "unconditional" if not any(t & dose for t in ev_t) else "mixed"
    if x["kind"] == "directional":
        st[x["condition"]] += 1; st["dose_" + x["condition_dose"]] += 1
        for t in set().union(*ev_t) if ev_t else ():
            per_tag[t] += 1
    out.append(x)
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
with open(a.out, "w", encoding="utf-8") as f:
    for x in out:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")
rep = {"directional_nulls": sum(1 for x in out if x["kind"] == "directional"), "condition": dict(st), "nulls_with_tag_in_any_sentence": dict(per_tag)}
Path(a.out).with_suffix(".stats.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))
