"""NullDDI step 4: assemble the directional dataset from accepted units (A AND B x4 runs).

Record = one directional null: perpetrator IN -> victim IN (or 'undirected' for statements
that name no victim), aggregated over all accepted units (sentences) and labels, with:
  dimension        PK / PD / PK+PD / not stated (from extractor B, all runs)
  numeric_grade    from label GMR tables in the same direction, when present:
                   exposure_equivalent (AUC and Cmax within 0.80-1.25) / weak_change /
                   strong_change / mixed ; else null
  reverse_fda      FDA CYP/transporter table status of the opposite, untested direction
  provenance       every supporting sentence with set_id, label version, effective_time, section
Pair table = unordered pair with status:
  N2  bidirectional null
  N1  one-direction null (reverse_fda: no_path / undetermined / path_possible / path_expected)
  N0  undirected statement only
Only single-ingredient labels define pairs; units from combination labels are kept in the
unit file but not aggregated (the subject ingredient is ambiguous).

Usage: python 04_build_dataset.py --accepted .../llm/accepted_units.jsonl --candidates .../candidates.jsonl
          --tables-records .../tables_v1_1/table_records.jsonl --fda-tables data/raw/fda_ddi_tables
          --rxnorm data/raw/rxnorm --out data/release/v0_1
"""
import argparse, csv, hashlib, importlib.util, json
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "0.1"
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tb", here / "05_tier_b_fda_tables.py")
tb = importlib.util.module_from_spec(spec); spec.loader.exec_module(tb)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def dim(bases):
    b = set(bases)
    pk = any("pk" in x for x in b); pd = any("pd" in x for x in b)
    return "PK+PD" if pk and pd else "PK" if pk else "PD" if pd else "not_stated"


def grade(c):
    tot = sum(c.values())
    if not tot:
        return None
    nf = sum(v for k, v in c.items() if k.startswith("no_effect"))
    if c["strong_change"] / tot > 0.5:
        return "strong_change"
    if nf / tot > 0.5:
        return "exposure_equivalent"
    if c["weak_change"] / tot >= 0.5:
        return "weak_change"
    return "mixed"


def main():
    ap = argparse.ArgumentParser()
    for k in ("accepted", "candidates", "tables-records", "fda-tables", "rxnorm"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    ex, lex, lexf = tb.load_lexicon(a.rxnorm)
    roles, *_ = tb.build_roles(a.fda_tables, ex, lex)
    names = {v["rxcui"]: n for n, v in lex.info.items() if v["tty"] == "IN"}

    prov = defaultdict(list)     # (sentence_sha1, label INs, partner IN) -> label provenance
    with open(a.candidates, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            prov[(r["sentence_sha1"], tuple(r["label_in_rxcuis"]), r["partner_in_rxcui"])].append(
                {"set_id": r["set_id"], "version": r["version"], "effective_time": r["effective_time"],
                 "section": r["section"]})

    key = defaultdict(Counter); gmr = defaultdict(list)
    with open(a.tables_records, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if len(r["label_in_rxcuis"]) != 1:
                continue
            L, P = r["label_in_rxcuis"][0], r["partner_in_rxcui"]
            d = (P, L) if r["direction"] == "partner_affects_label_drug" else (L, P)
            key[d][r["verdict"]] += 1
            gmr[d].append({k: v["gmr"] for k, v in r["values"].items()})

    rec = defaultdict(lambda: {"units": [], "bases": [], "params": [], "labels": set()})
    n_units = Counter()
    with open(a.accepted, encoding="utf-8") as f:
        for line in f:
            u = json.loads(line); n_units["accepted_units"] += 1
            if len(u["label_in_rxcuis"]) != 1:
                n_units["combination_label_units_not_aggregated"] += 1; continue
            L, P = u["label_in_rxcuis"][0], u["partner_in_rxcui"]
            ds = {"both": [(L, P), (P, L)], "label_drug_affects_partner": [(L, P)],
                  "partner_affects_label_drug": [(P, L)]}.get(u["direction"])
            keys = [("directional",) + d for d in ds] if ds else [("undirected",) + tuple(sorted((L, P)))]
            pv = prov[(u["sentence_sha1"], tuple(u["label_in_rxcuis"]), P)]
            for k in keys:
                x = rec[k]
                x["units"].append({"unit_id": u["unit_id"], "sentence": u["sentence"], "label_in": L,
                                   "quote": u["quotes"].get("r1"), "labels": pv})
                x["bases"] += u["evidence_basis"]; x["params"] += u["parameters_assessed"]
                x["labels"] |= {p["set_id"] for p in pv}

    st = Counter()
    rows = []
    with open(a.out / "nullddi_nulls.jsonl", "w", encoding="utf-8") as out:
        for k, x in sorted(rec.items()):
            kind, p1, p2 = k
            r = {"kind": kind, "n_sentences": len(x["units"]), "n_labels": len(x["labels"]),
                 "dimension": dim(x["bases"]), "parameters": sorted(set(x["params"])), "evidence": x["units"]}
            if kind == "directional":
                rv, _ = (("undetermined", []) if p1 not in roles or p2 not in roles else
                         (lambda ps: (("path_expected" if any(q["grade"] == "expected" for q in ps) else "path_possible")
                                      if ps else "no_path", ps))(tb.paths(roles[p2], roles[p1])))
                r.update({"perpetrator_rxcui": p1, "perpetrator": names.get(p1, p1),
                          "victim_rxcui": p2, "victim": names.get(p2, p2),
                          "numeric_grade": grade(key.get((p1, p2), Counter())),
                          "numeric_gmr": gmr.get((p1, p2), [])[:5], "reverse_fda": rv})
                st["directional_nulls"] += 1; st["dim_" + r["dimension"]] += 1
                st["grade_" + str(r["numeric_grade"])] += 1
                rows.append([r["perpetrator"], r["victim"], p1, p2, r["dimension"], r["numeric_grade"] or "",
                             r["reverse_fda"], r["n_sentences"], r["n_labels"]])
            else:
                r.update({"drug_a_rxcui": p1, "drug_a": names.get(p1, p1), "drug_b_rxcui": p2, "drug_b": names.get(p2, p2)})
                st["undirected_nulls"] += 1
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(a.out / "nullddi_nulls_directional.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["perpetrator", "victim", "perpetrator_rxcui", "victim_rxcui", "dimension",
                                       "numeric_grade", "reverse_fda", "n_sentences", "n_labels"]); w.writerows(rows)

    D = {(k[1], k[2]) for k in rec if k[0] == "directional"}
    U = {(k[1], k[2]) for k in rec if k[0] == "undirected"}
    pairs = {tuple(sorted(d)) for d in D} | U
    with open(a.out / "nullddi_pairs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["drug_a", "drug_b", "rxcui_a", "rxcui_b", "status", "documented", "reverse_fda"])
        for x, y in sorted(pairs):
            doc = [d for d in ((x, y), (y, x)) if d in D]
            if len(doc) == 2:
                s, rv = "N2_bidirectional", ""
            elif len(doc) == 1:
                p, v = doc[0]
                rv = ("undetermined" if p not in roles or v not in roles else
                      (lambda ps: ("path_expected" if any(q["grade"] == "expected" for q in ps) else "path_possible") if ps else "no_path")(tb.paths(roles[v], roles[p])))
                s = "N1_one_direction"
            else:
                s, rv = "N0_undirected_only", ""
            st[s] += 1
            if rv:
                st["N1_reverse_" + rv] += 1
            w.writerow([names.get(x, x), names.get(y, y), x, y, s,
                        "; ".join(f"{names.get(p, p)}->{names.get(v, v)}" for p, v in doc), rv])
    st["pairs"] = len(pairs); st["drugs"] = len({z for p in pairs for z in p})
    meta = {"dataset_version": VERSION, "stats": {**n_units, **st},
            "inputs_sha256": {"accepted": sha(a.accepted), "candidates": sha(a.candidates),
                              "table_records": sha(a.tables_records), "lexicon": sha(lexf)}}
    (a.out / "nullddi_stats.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta["stats"], indent=1))


if __name__ == "__main__":
    main()
