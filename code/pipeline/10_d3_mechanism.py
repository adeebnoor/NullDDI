"""NullDDI step 10 v1.1: mechanism of listed interactions for NullDDI pairs, using the
D3 gold file (Noor et al., JAMIA 2017; GoldD3R.txt: UMLS CUI pairs with inferred mechanisms).
ANALYSIS ONLY: D3 gold derives from third-party sources; only aggregates are reported and
no D3 record enters the CC BY release.
UMLS CUI -> RxNorm via Wikidata (P2892 x P3345), then to RxNorm IN with the project lexicon.
D3 pairs are undirected, so the comparison is at pair level; the null's own dimension
(PK / PD) is taken from nullddi_nulls_directional.csv."""
import argparse, csv, importlib.util, json, re
from collections import Counter, defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tb", here / "05_tier_b_fda_tables.py")
tb = importlib.util.module_from_spec(spec); spec.loader.exec_module(tb)
PK = {"MetabolismInhibition", "MetabolismInduction", "TransporterInhibition", "TransporterInduction",
      "ProteinBinding", "Competition", "MultiPathways", "Pharmacogenetic"}
PD = {"Synergistic", "Additive"}
ap = argparse.ArgumentParser()
for k in ("gold", "wikidata", "rxnorm", "pairs", "nulls", "ddinter", "out"):
    ap.add_argument("--" + k, required=True)
a = ap.parse_args()
ex, lex, _ = tb.load_lexicon(a.rxnorm)
concepts = {c["rxcui"]: c for c in json.load(open(next(Path(a.rxnorm).glob("rxnorm_ingredients_*.json")), encoding="utf-8"))["concepts"]}

# --- CUI -> IN
raw = defaultdict(set)
for u, r, _l in json.load(open(a.wikidata, encoding="utf-8"))["rows"]:
    raw[u].add(r)
cui2in, why = {}, Counter()
def resolve(cui):
    ins = set()
    for r in raw.get(cui, ()):
        c = concepts.get(r)
        if not c:
            continue
        if c["tty"] == "IN":
            ins.add(r)
        else:
            x = tb.to_in(c["name"].lower(), ex, lex)[0]
            if x:
                ins.add(x)
    return ins
gold, cuis = {}, set()
for line in open(a.gold, encoding="utf-8", errors="replace"):
    line = line.strip()
    m = re.match(r"^(C\d+),(C\d+)(?:,\[(.*)\])?$", line)
    if not m:
        continue
    mech = {x.strip() for x in (m.group(3) or "").split(",") if x.strip()}
    k = tuple(sorted((m.group(1), m.group(2))))
    cuis.update(k); gold.setdefault(k, set()).update(mech)
for c in cuis:
    ins = resolve(c)
    if len(ins) == 1:
        cui2in[c] = next(iter(ins)); why["mapped"] += 1
    elif not raw.get(c):
        why["no_wikidata_link"] += 1
    elif not ins:
        why["rxcui_not_single_ingredient"] += 1
    else:
        why["ambiguous"] += 1
d3 = {}
for (x, y), mech in gold.items():
    if x in cui2in and y in cui2in and cui2in[x] != cui2in[y]:
        d3.setdefault(tuple(sorted((cui2in[x], cui2in[y]))), set()).update(mech)
d3_drugs = set(cui2in.values())
def klass(mech):
    pk, pd = bool(mech & PK), bool(mech & PD)
    return "PK+PD" if pk and pd else "PK_only" if pk else "PD_only" if pd else "no_mechanism"

# --- DDInter listing per pair (analysis only)
dd, cache = {}, {}
for fp in sorted(Path(a.ddinter).glob("ddinter_downloads_code_*.csv")):
    with open(fp, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            ids = []
            for n in (r["Drug_A"].strip().lower(), r["Drug_B"].strip().lower()):
                if n not in cache:
                    cache[n] = tb.to_in(n, ex, lex)[0]
                ids.append(cache[n])
            if None in ids or ids[0] == ids[1]:
                continue
            dd[tuple(sorted(ids))] = r["Level"].strip()
dd_drugs = {x for k in dd for x in k}

# --- null dimension per pair
dim = defaultdict(set)
for r in csv.DictReader(open(a.nulls, encoding="utf-8")):
    dim[tuple(sorted((r["perpetrator_rxcui"], r["victim_rxcui"])))].add(r["dimension"])
def pdim(k):
    d = dim.get(k, set())
    if not d:
        return "undirected"
    return "PK" if d == {"PK"} else "has_PD" if any("PD" in x for x in d) else "other"

res = defaultdict(Counter)
rows = []
for r in csv.DictReader(open(a.pairs, encoding="utf-8")):
    k = tuple(sorted((r["rxcui_a"], r["rxcui_b"])))
    both = k[0] in d3_drugs and k[1] in d3_drugs
    cl = klass(d3[k]) if k in d3 else None
    for g in ("ALL", r["status"], "nulldim_" + pdim(k), "ddinter_listed" if k in dd else
              "ddinter_not_listed_both_present" if (k[0] in dd_drugs and k[1] in dd_drugs) else "ddinter_drug_absent"):
        c = res[g]; c["pairs"] += 1; c["both_drugs_in_d3"] += both
        if cl:
            c["in_d3_gold"] += 1; c["d3_" + cl] += 1
            for mname in d3[k]:
                c["mech_" + mname] += 1
    rows.append((k, r["status"], pdim(k), cl, dd.get(k)))
out = {"mapping": {"d3_cuis": len(cuis), **why, "d3_pairs": len(gold), "d3_pairs_mapped": len(d3),
                   "d3_mapped_pair_classes": dict(Counter(klass(m) for m in d3.values()))},
       "groups": {g: {**v, "in_d3_pct_of_both_present": round(100 * v["in_d3_gold"] / max(1, v["both_drugs_in_d3"]), 1)}
                  for g, v in sorted(res.items())}}
# dimension-aware reading: PK-only nulls vs D3 mechanism class
x = Counter()
for k, st, pdm, cl, lv in rows:
    if cl:
        x[(pdm, cl)] += 1
out["nulldim_x_d3class"] = {f"{p}|{c}": n for (p, c), n in sorted(x.items())}
# DDInter-listed pairs explained by D3
y = Counter()
for k, st, pdm, cl, lv in rows:
    if lv:
        y[(lv, cl or "not_in_d3")] += 1
out["ddinter_level_x_d3class"] = {f"{l}|{c}": n for (l, c), n in sorted(y.items())}
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
# PK-null pairs for which D3 holds a PK mechanism: pair status / reverse-direction FDA status
z = Counter(); st = {}
for r in csv.DictReader(open(a.pairs, encoding="utf-8")):
    st[tuple(sorted((r["rxcui_a"], r["rxcui_b"])))] = (r["status"], r["reverse_fda"] or "-")
for k, s, pdm, cl, lv in rows:
    if pdm == "PK" and cl in ("PK_only", "PK+PD"):
        z["|".join(st[k])] += 1
out["pknull_with_d3_pk_mechanism_by_status"] = dict(z)
Path(a.out).write_text(json.dumps(out, indent=1)); print(json.dumps(out["pknull_with_d3_pk_mechanism_by_status"], indent=1))
