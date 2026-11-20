"""NullDDI step 6b: how often does DDInter 2.0 list as INTERACTING a pair whose FDA label
documents a measured null? (false-alarm burden, lower bound)

DDInter 2.0 (CC BY-NC-SA 4.0) is used for analysis only and is NOT redistributed in
NullDDI (CC BY 4.0); only aggregate counts are published.
The public download covers interactions involving ATC groups A, B, D, H, L, P, R, V only,
so pairs not found in it are 'not listed in the downloadable subset' (not 'non-interacting'),
and every listing rate here is a lower bound.
Pairs are stratified by NullDDI directional status (tier B v1.1): a one-directional label
null does NOT contradict an interaction listed for the other direction.
"""
import argparse, csv, importlib.util, json
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.0"
LEVEL_RANK = {"Major": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tb", here / "05_tier_b_fda_tables.py")
tb = importlib.util.module_from_spec(spec); spec.loader.exec_module(tb)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ddinter", required=True); ap.add_argument("--rxnorm", required=True)
    ap.add_argument("--directional", required=True, help="tier_b v1.1 pairs_directional.jsonl")
    ap.add_argument("--legacy", help="legacy_pairs_2026_check.jsonl (optional)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    ex, lex, _ = tb.load_lexicon(a.rxnorm)

    dd, drug_map, unm = {}, {}, Counter()
    files = sorted(Path(a.ddinter).glob("ddinter_downloads_code_*.csv"))
    rows = 0
    for fp in files:
        with open(fp, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                rows += 1
                ids = []
                for name in (r["Drug_A"], r["Drug_B"]):
                    n = name.strip().lower()
                    if n not in drug_map:
                        drug_map[n] = tb.to_in(n, ex, lex)[0]
                    if drug_map[n] is None:
                        unm[n] += 1
                    ids.append(drug_map[n])
                if None in ids or ids[0] == ids[1]:
                    continue
                k = tuple(sorted(ids)); lv = r["Level"].strip()
                if k not in dd or LEVEL_RANK.get(lv, 0) > LEVEL_RANK.get(dd[k], 0):
                    dd[k] = lv
    present = {x for k in dd for x in k}

    res = defaultdict(Counter)
    with open(a.directional, encoding="utf-8") as f:
        for line in f:
            p = json.loads(line); k = tuple(sorted(p["pair"]))
            st = p["status"]
            for grp in (st, "ALL"):
                c = res[grp]; c["pairs"] += 1
                both_present = k[0] in present and k[1] in present
                c["both_drugs_in_ddinter"] += both_present
                if k in dd:
                    c["listed"] += 1; c["listed_" + dd[k]] += 1
    out = {"script_version": VERSION, "ddinter_rows": rows, "ddinter_unique_pairs_mapped": len(dd),
           "ddinter_drug_names": len(drug_map), "ddinter_names_unmapped": sum(1 for v in drug_map.values() if v is None),
           "by_status": {k: dict(v) for k, v in sorted(res.items())},
           "files_sha256": {fp.name: tb.sha256(fp) for fp in files}}
    if a.legacy:
        lc = Counter()
        with open(a.legacy, encoding="utf-8") as f:
            for line in f:
                p = json.loads(line); k = tuple(sorted(p["pair"]))
                lc["pairs"] += 1
                if k in dd:
                    lc["listed"] += 1; lc["listed_" + dd[k]] += 1
        out["legacy_antiddi_2022"] = dict(lc)
    (a.out / "ddinter_listing_stats.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
