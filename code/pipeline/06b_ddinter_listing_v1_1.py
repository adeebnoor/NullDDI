"""NullDDI step 6b v1.1: DDInter 2.0 listing of the released pairs (nullddi_pairs.csv),
by pair status and, for N1 pairs, by reverse-direction FDA status. Same caveats as v1.0:
DDInter is CC BY-NC-SA (analysis only, aggregates published); the download covers ATC
A,B,D,H,L,P,R,V only (lower bound); a listing is not a contradiction unless its mechanism
is PK in the documented direction (mechanism is not in the download)."""
import argparse, csv, importlib.util, json
from collections import Counter, defaultdict
from pathlib import Path
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tb", here / "05_tier_b_fda_tables.py")
tb = importlib.util.module_from_spec(spec); spec.loader.exec_module(tb)
RANK = {"Major": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}
ap = argparse.ArgumentParser()
for k in ("ddinter", "rxnorm", "pairs", "out"):
    ap.add_argument("--" + k, required=True)
a = ap.parse_args()
ex, lex, _ = tb.load_lexicon(a.rxnorm)
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
            k = tuple(sorted(ids))
            if k not in dd or RANK.get(r["Level"], 0) > RANK.get(dd[k], 0):
                dd[k] = r["Level"].strip()
present = {x for k in dd for x in k}
res = defaultdict(Counter)
with open(a.pairs, encoding="utf-8") as f:
    for r in csv.DictReader(f):
        k = tuple(sorted((r["rxcui_a"], r["rxcui_b"])))
        groups = ["ALL", r["status"]] + ([r["status"] + "/reverse_" + r["reverse_fda"]] if r["reverse_fda"] else [])
        for g in groups:
            c = res[g]; c["pairs"] += 1; c["both_drugs_in_ddinter"] += k[0] in present and k[1] in present
            if k in dd:
                c["listed"] += 1; c["listed_" + dd[k]] += 1
out = {g: {**v, "listed_pct": round(100 * v["listed"] / v["pairs"], 1),
           "listed_pct_of_both_present": round(100 * v["listed"] / max(1, v["both_drugs_in_ddinter"]), 1)} for g, v in sorted(res.items())}
Path(a.out).write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
