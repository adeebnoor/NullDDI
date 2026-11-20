"""NullDDI step 6a: temporal/evidence check of the legacy Anti-DDI 2022 pairs (797 unique).

For every legacy pair (built in 2022 by EXCLUSION: not listed as interacting) report:
  * RxNorm IN mapping of both names;
  * label evidence 2026 from extractor A v1.2 (any record, CORE records, direction coverage);
  * FDA CYP/transporter path in either direction (tier B, both drugs profiled only).
No human review; descriptive only.
Usage: python 06a_legacy_antiddi_check.py --legacy legacy/AntiDDI-dataset_2022.xlsx \
   --candidates data/interim/v1_2/candidates.jsonl --tables data/raw/fda_ddi_tables \
   --rxnorm data/raw/rxnorm --out data/interim/v1_2/legacy
"""
import argparse, importlib.util, json
from collections import Counter, defaultdict
from pathlib import Path
import openpyxl

VERSION = "1.1"
# Documented name normalisation for the 2022 sheet (INN/brand/truncation -> RxNorm IN).
# 'penicillin' is left unmapped on purpose: it does not identify one ingredient.
SYNONYMS = {"paracetamol": "acetaminophen", "salbutamol": "albuterol", "dextromethorph": "dextromethorphan",
            "glyceryl trini.": "nitroglycerin", "humalog": "insulin lispro", "lantus": "insulin glargine",
            "conjugated estrogens": "estrogens, conjugated (usp)"}
FLAGS = ["long_sentence", "population_pk", "table_like", "endogenous_context", "positive_cue",
         "partial_parameter", "regimen_partner"]
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tb", here / "05_tier_b_fda_tables.py")
tb = importlib.util.module_from_spec(spec); spec.loader.exec_module(tb)


def main():
    ap = argparse.ArgumentParser()
    for k in ("legacy", "candidates", "tables", "rxnorm"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    ex, lex, _ = tb.load_lexicon(a.rxnorm)
    roles, *_ = tb.build_roles(a.tables, ex, lex)
    names = {v["rxcui"]: n for n, v in lex.info.items() if v["tty"] == "IN"}

    ws = openpyxl.load_workbook(a.legacy, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))[1:]
    legacy, unmapped = {}, Counter()
    for _, x, y in rows:
        if not x or not y:
            continue
        x, y = (SYNONYMS.get(v, v) for v in (str(x).strip().lower(), str(y).strip().lower()))
        rx = [tb.to_in(n, ex, lex)[0] for n in (x, y)]
        for n, r in zip((x, y), rx):
            if r is None:
                unmapped[n] += 1
        key = tuple(sorted(r or "NAME:" + n for n, r in zip((x, y), rx)))
        legacy.setdefault(key, {"names_2022": sorted((x, y)), "mapped": all(rx)})

    ev = defaultdict(lambda: {"records": 0, "core_records": 0, "dirs": set()})
    with open(a.candidates, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            P = r["partner_in_rxcui"]
            for L in r["label_in_rxcuis"]:
                k = tuple(sorted((L, P)))
                if k not in legacy:
                    continue
                e = ev[k]; e["records"] += 1
                core = r["own_mentioned"] and not any(r.get(x) for x in FLAGS) and len(r["label_in_rxcuis"]) == 1
                if core:
                    e["core_records"] += 1
                    d = r["direction_rule"]
                    if d == "both":
                        e["dirs"] |= {(L, P), (P, L)}
                    elif d == "label_drug_affects_partner":
                        e["dirs"].add((L, P))
                    elif d == "partner_affects_label_drug":
                        e["dirs"].add((P, L))

    st = Counter()
    with open(a.out / "legacy_pairs_2026_check.jsonl", "w", encoding="utf-8") as out:
        for k, v in sorted(legacy.items()):
            e = ev.get(k, {"records": 0, "core_records": 0, "dirs": set()})
            x, y = k
            fda = {}
            for p, q in ((x, y), (y, x)):
                if p in roles and q in roles:
                    ps = tb.paths(roles[p], roles[q])
                    fda[f"{p}->{q}"] = ("path_expected" if any(z["grade"] == "expected" for z in ps)
                                        else "path_possible" if ps else "no_path")
                else:
                    fda[f"{p}->{q}"] = "undetermined"
            label_ev = ("none" if not e["records"] else "flagged_only" if not e["core_records"]
                        else "bidirectional" if len(e["dirs"]) == 2 else "one_direction" if e["dirs"] else "direction_unresolved")
            fda_pair = ("undetermined" if "undetermined" in fda.values() else
                        "path_expected" if "path_expected" in fda.values() else
                        "path_possible" if "path_possible" in fda.values() else "no_path")
            st["pairs"] += 1; st["mapped"] += v["mapped"]
            st["label_" + label_ev] += 1; st["fda_" + fda_pair] += 1
            out.write(json.dumps({"pair": list(k), "names_2022": v["names_2022"],
                                  "names_in": [names.get(z, z) for z in k], "mapped": v["mapped"],
                                  "label_evidence_2026": label_ev, "label_records": e["records"],
                                  "core_records": e["core_records"], "fda_tables": fda, "fda_pair": fda_pair},
                                 ensure_ascii=False) + "\n")
    meta = {"script_version": VERSION, "legacy_rows": len(rows), "stats": dict(st),
            "unmapped_names": dict(unmapped.most_common()),
            "synonyms_applied": SYNONYMS, "legacy_sha256": tb.sha256(a.legacy), "candidates_sha256": tb.sha256(a.candidates)}
    (a.out / "legacy_check_stats.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
