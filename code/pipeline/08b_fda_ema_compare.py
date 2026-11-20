"""NullDDI step 8b: FDA vs EMA replication of directional label nulls (extractor A rules).

Unit: directional null (perpetrator IN -> victim IN) from CORE records of single-ingredient
labels/SmPCs (no flag raised, own drug named in the sentence). For each regulator:
  * pairs with a bidirectional null vs a one-directional null vs direction unresolved
  * overlap of directional nulls between regulators, and agreement on direction
  * pairs whose direction is documented by one regulator and the reverse by the other
These are pre-extractor-B numbers; they are recomputed on accepted units later.
"""
import argparse, json
from collections import Counter, defaultdict

FLAGS = ["long_sentence", "population_pk", "table_like", "endogenous_context", "positive_cue",
         "partial_parameter", "regimen_partner"]


def load(path):
    dirs, pairs = defaultdict(set), set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if len(r["label_in_rxcuis"]) != 1 or not r.get("own_mentioned", True) or any(r.get(k) for k in FLAGS):
                continue
            L, P = r["label_in_rxcuis"][0], r["partner_in_rxcui"]
            k = tuple(sorted((L, P))); pairs.add(k)
            d = r["direction_rule"]
            if d == "both":
                dirs[k] |= {(L, P), (P, L)}
            elif d == "label_drug_affects_partner":
                dirs[k].add((L, P))
            elif d == "partner_affects_label_drug":
                dirs[k].add((P, L))
    return pairs, dirs


def profile(pairs, dirs):
    c = Counter()
    for k in pairs:
        n = len(dirs.get(k, ()))
        c["bidirectional" if n == 2 else "one_direction" if n == 1 else "unresolved"] += 1
    c["pairs"] = len(pairs)
    return dict(c)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fda", required=True); ap.add_argument("--ema", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fp, fd = load(a.fda); ep, ed = load(a.ema)
    both = fp & ep
    fdir = {d for k in fd for d in fd[k]}; edir = {d for k in ed for d in ed[k]}
    comp = Counter()
    for k in both:
        F, E = fd.get(k, set()), ed.get(k, set())
        if F and E:
            comp["same_direction_set" if F == E else "overlapping" if F & E else "complementary_directions"] += 1
            if (F | E) == {(k[0], k[1]), (k[1], k[0])} and len(F) == 1 and len(E) == 1 and F != E:
                comp["bidirectional_only_when_combined"] += 1
        else:
            comp["direction_unresolved_in_one"] += 1
    rep = {"fda": profile(fp, fd), "ema": profile(ep, ed), "pairs_in_both": len(both),
           "directional_nulls": {"fda": len(fdir), "ema": len(edir), "shared": len(fdir & edir)},
           "pairs_in_both_detail": dict(comp),
           "ema_only_pairs": len(ep - fp), "fda_only_pairs": len(fp - ep)}
    with open(a.out, "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
