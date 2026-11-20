"""NullDDI step 4b: active-moiety relations mined from the labels themselves (no human review).

A null between a drug and its own prodrug/active metabolite is not a drug-drug non-interaction
(e.g. famciclovir -> penciclovir). Relations are read from each single-ingredient label's
Description / Clinical Pharmacology / Mechanism text with fixed patterns:
   "<own> is a prodrug of <Y>", "<own> ... converted|hydrolyzed|metabolized to (its) active
   (metabolite|moiety|form)[,] <Y>"  (v1.1: Description and Mechanism of Action sections only;
   v1.0 also read PK text and picked up partner drugs such as "active metabolite of clopidogrel")
Y must be an RxNorm ingredient different from the label's own. A relation is kept when found in
>= 2 distinct labels (set_id) of the same ingredient. Output: moiety_relations.csv and the list
of dataset nulls whose two drugs are moiety-related (to be excluded in v0.2).
"""
import argparse, csv, importlib.util, json, re
from collections import defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ex", here / "02_extract_null_statements_v1_2.py")
ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
PAT = re.compile(
    r"prodrug of ([^.;]{3,60})|"
    r"(?:converted|hydrolyzed|hydrolysed|metabolized|metabolised|biotransformed|deesterified|de-esterified|activated)[^.;]{0,60}? to (?:its |the )?(?:pharmacologically )?active (?:metabolite|moiety|form|drug|compound)s?,? ([^.;]{3,60})", re.I)
ap = argparse.ArgumentParser()
for k in ("raw", "rxnorm", "nulls", "out"):
    ap.add_argument("--" + k, required=True)
a = ap.parse_args(); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
lexf = next(Path(a.rxnorm).glob("rxnorm_ingredients_*.json"))
lex = ex.Lexicon(json.loads(lexf.read_text(encoding="utf-8"))["concepts"])
sm, _ = ex.load_setid_ingredients(a.rxnorm, lex)
full = {}
for n in lex.info:
    t = ex.TOKEN.findall(n)
    if t and len(n) > 3:
        full.setdefault(t[0], []).append((t, n))
for k in full:
    full[k].sort(key=lambda t: -len(t[0]))
rel = defaultdict(set)
for _, rec in ex.iter_labels(a.raw):
    own = sm.get(rec.get("set_id"), set()) | ex.own_from_openfda(rec, lex)
    own_in = {lex.info[n]["in_rxcui"] for n in own}
    if len(own_in) != 1:
        continue
    o = next(iter(own_in))
    # v1.1: only text that describes the label's own drug (Description, Mechanism of Action)
    txt = " ".join(b for f in ("description", "mechanism_of_action") for b in rec.get(f, []))
    for m in PAT.finditer(txt):
        frag = next(g for g in m.groups() if g)
        for n in lex.find(frag, full):
            y = lex.info[n]["in_rxcui"]
            if y != o:
                rel[(o, y)].add(rec.get("set_id"))
names = {v["rxcui"]: n for n, v in lex.info.items() if v["tty"] == "IN"}
keep = {k: v for k, v in rel.items() if len(v) >= 2}
with open(out / "moiety_relations.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["parent", "moiety", "parent_rxcui", "moiety_rxcui", "n_labels"])
    for (o, y), v in sorted(keep.items(), key=lambda x: names.get(x[0][0], "")):
        w.writerow([names.get(o, o), names.get(y, y), o, y, len(v)])
und = {frozenset(k) for k in keep}
hits = []
with open(a.nulls, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        if frozenset((r["perpetrator_rxcui"], r["victim_rxcui"])) in und:
            hits.append([r["perpetrator"], r["victim"], r["n_sentences"], r["n_labels"]])
with open(out / "nulls_moiety_related.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["perpetrator", "victim", "n_sentences", "n_labels"]); w.writerows(hits)
print(json.dumps({"relations_found": len(rel), "relations_kept_2plus_labels": len(keep), "nulls_flagged": len(hits)}))
for h in hits: print(h)
