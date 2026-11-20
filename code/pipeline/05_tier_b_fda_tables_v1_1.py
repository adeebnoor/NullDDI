"""NullDDI step 5, v1.1: directional tier B.

v1.0 classified unordered pairs. The v1.1 check showed that most label nulls cover ONE
direction (perpetrator -> victim); e.g. "dabigatran did not alter the PK of amiodarone"
says nothing about amiodarone (P-gp inhibitor) -> dabigatran (P-gp substrate).
v1.1 therefore works on directions, using extractor A v1.2 `direction_rule`.

For every unordered pair from single-ingredient labels (CORE records only):
  documented directions D = directions with a label null (A rule; 'both' covers two)
  for each direction (perpetrator X -> victim Y) the FDA table gives:
     no_path / path_expected / path_possible / undetermined (X or Y not profiled)
Pair status:
  P1_bidirectional_null           nulls documented in both directions
  P2_null_plus_reverse_no_cyp_transporter_path    one direction documented, the other has no FDA path
                                  (both drugs profiled)
  P3_null_reverse_undetermined    one direction documented, reverse not assessable
  P4_null_reverse_mechanism       one direction documented, FDA path in the reverse
                                  direction -> NOT a non-interacting pair (directional
                                  null only)
  P5_direction_unresolved         rule could not tell the direction
P2 is CYP/transporter-only: gastric-pH/absorption, chelation, protein binding and
pharmacodynamic mechanisms are NOT assessed by the FDA tables (e.g. dasatinib with
acid-reducing agents, warfarin with antiplatelets), so P2 is weaker than P1.
Additionally `documented_direction_conflict`: a documented null in a direction where the
FDA table predicts an expected path (label null despite mechanism; reported, not removed).
"""
import argparse, importlib.util, json
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.1"
FLAGS = ["long_sentence", "population_pk", "table_like", "endogenous_context", "positive_cue",
         "partial_parameter", "regimen_partner"]

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tb", here / "05_tier_b_fda_tables.py")
tb = importlib.util.module_from_spec(spec); spec.loader.exec_module(tb)


def dir_status(x, y, roles):
    """x = perpetrator, y = victim."""
    if x not in roles or y not in roles:
        return "undetermined", []
    p = tb.paths(roles[x], roles[y])
    if not p:
        return "no_path", []
    return ("path_expected" if any(q["grade"] == "expected" for q in p) else "path_possible"), p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", required=True); ap.add_argument("--rxnorm", required=True)
    ap.add_argument("--candidates", required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    ex, lex, lexf = tb.load_lexicon(a.rxnorm)
    roles, src, unmapped, asof = tb.build_roles(a.tables, ex, lex)
    names = {v["rxcui"]: n for n, v in lex.info.items() if v["tty"] == "IN"}

    pairs = defaultdict(lambda: {"documented": set(), "records": 0, "unresolved_records": 0})
    with open(a.candidates, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if len(r["label_in_rxcuis"]) != 1 or not r["own_mentioned"] or any(r.get(k) for k in FLAGS):
                continue
            L, P = r["label_in_rxcuis"][0], r["partner_in_rxcui"]
            v = pairs[tuple(sorted((L, P)))]; v["records"] += 1
            d = r["direction_rule"]
            if d == "both":
                v["documented"] |= {(L, P), (P, L)}
            elif d == "label_drug_affects_partner":
                v["documented"].add((L, P))
            elif d == "partner_affects_label_drug":
                v["documented"].add((P, L))
            else:
                v["unresolved_records"] += 1

    st, conflicts = Counter(), Counter()
    with open(a.out / "pairs_directional.jsonl", "w", encoding="utf-8") as f:
        for (x, y), v in sorted(pairs.items()):
            doc = v["documented"]
            dirs = {}
            for perp, vic in ((x, y), (y, x)):
                s, p = dir_status(perp, vic, roles)
                dirs[f"{perp}->{vic}"] = {"documented_null": (perp, vic) in doc, "fda": s, "paths": p}
            conflict = any(d["documented_null"] and d["fda"] == "path_expected" for d in dirs.values())
            if len(doc) == 2:
                status = "P1_bidirectional_null"
            elif len(doc) == 1:
                (perp, vic), = doc
                rev = dirs[f"{vic}->{perp}"]["fda"]
                status = {"no_path": "P2_null_plus_reverse_no_cyp_transporter_path", "undetermined": "P3_null_reverse_undetermined"
                          }.get(rev, "P4_null_reverse_mechanism")
            else:
                status = "P5_direction_unresolved"
            st[status] += 1; conflicts[status] += conflict
            f.write(json.dumps({"pair": [x, y], "names": [names.get(x, x), names.get(y, y)], "status": status,
                                "documented_direction_conflict": conflict, "records": v["records"],
                                "unresolved_records": v["unresolved_records"], "directions": dirs},
                               ensure_ascii=False) + "\n")
    meta = {"script_version": VERSION, "fda_table1_current_as_of": asof, "pairs": len(pairs),
            "status": dict(st), "documented_direction_conflicts": dict(conflicts),
            "inputs": {"candidates_sha256": tb.sha256(a.candidates)}}
    (a.out / "directional_stats.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
