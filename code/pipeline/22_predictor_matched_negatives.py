"""NullDDI step 22 v1.0: are documented non-interactions hard because of WHICH drugs they involve?

Alternative explanation for step 17: documented pairs involve well-studied drugs (CYP inhibitors, inducers,
antiretrovirals) that have many DDInter interactions, so any pair containing them scores high. Two control
negative sets, drawn per seed and fixed before results:
  R_drug    "drug-matched": random unlisted pairs whose two drugs are drawn from the multiset of drugs
            in the documented pairs (same drugs, same frequencies, randomly recombined).
  R_degree  "degree-matched": random unlisted pairs whose drugs are drawn with probability proportional
            to their number of DDInter interactions (popular drugs, as in degree-biased benchmarks).
Excluded from both: DDInter-listed pairs and all NullDDI pairs. Size: 5x the documented set.
Same training, seeds, models and 90%-sensitivity threshold as step 17. Reported: false-alarm rate and
AUROC (held-out positives vs each negative set), and the paired difference documented - drug-matched
over seeds.
"""
import json, random, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

here = Path(__file__).resolve().parent
src = (here / "17_predictor_negatives.py").read_text()
prep = src[: src.index("for seed in range(a.seeds):")]
g = {"__file__": str(here / "17_predictor_negatives.py"), "__name__": "prep17"}
exec(compile(prep, "17_prep", "exec"), g)
a, pos, nd_all, N_doc, N_doc2, dd_drugs, X, P_all, drugs = (g[k] for k in ("a", "pos", "nd_all", "N_doc", "N_doc2", "dd_drugs", "X", "P_all", "drugs"))

deg = Counter()
for p, q in pos:
    deg[p] += 1; deg[q] += 1
doc_drugs = [d for k in N_doc for d in k]
dd = sorted(set(dd_drugs)); w = np.array([deg[d] for d in dd], dtype=float); w /= w.sum()
excl = set(pos) | nd_all

res = defaultdict(list)
for seed in range(a.seeds):
    rng = random.Random(1000 + seed); nrng = np.random.default_rng(5000 + seed)
    P = P_all[:]; rng.shuffle(P); cut = int(0.8 * len(P)); Ptr, Pte = P[:cut], P[cut:]
    def rand_pairs(n, banned, draw):
        s = set(); tries = 0
        while len(s) < n and tries < 200 * n:
            tries += 1
            u, v = draw()
            if u == v:
                continue
            k = tuple(sorted((u, v)))
            if k not in excl and k not in banned:
                s.add(k)
        return list(s)
    uni = lambda: tuple(rng.sample(dd_drugs, 2))
    Rte = rand_pairs(len(Pte), set(), uni); Rtr = rand_pairs(len(Ptr), set(Rte), uni)
    n_ctrl = 5 * len(N_doc)
    R_drug = rand_pairs(n_ctrl, set(Rtr), lambda: (rng.choice(doc_drugs), rng.choice(doc_drugs)))
    R_deg = rand_pairs(n_ctrl, set(Rtr), lambda: tuple(nrng.choice(dd, 2, p=w)))
    Xtr = X(Ptr + Rtr); ytr = np.r_[np.ones(len(Ptr)), np.zeros(len(Rtr))]
    for name, mdl in (("logreg", LogisticRegression(C=0.5, max_iter=2000)),
                      ("gboost", HistGradientBoostingClassifier(max_iter=300, random_state=seed))):
        mdl.fit(Xtr, ytr)
        s = lambda keys: mdl.predict_proba(X(keys))[:, 1]
        sp, sr, sd, sg, sn, sn2 = s(Pte), s(Rte), s(R_drug), s(R_deg), s(N_doc), s(N_doc2)
        thr = np.quantile(sp, 0.10)
        fpr = lambda x: float((x >= thr).mean())
        auc = lambda neg: float(roc_auc_score(np.r_[np.ones(len(sp)), np.zeros(len(neg))], np.r_[sp, neg]))
        res[name].append({"seed": seed, "n_drug_matched": len(R_drug), "n_degree_matched": len(R_deg),
                          "fpr_random": fpr(sr), "fpr_drug_matched": fpr(sd), "fpr_degree_matched": fpr(sg),
                          "fpr_documented": fpr(sn), "fpr_documented_N2": fpr(sn2),
                          "auc_random": auc(sr), "auc_drug_matched": auc(sd), "auc_degree_matched": auc(sg),
                          "auc_documented": auc(sn)})
        print(seed, name, {k: round(v, 3) for k, v in res[name][-1].items() if k.startswith(("fpr", "auc"))}, flush=True)

summ = {}
for name, rows in res.items():
    agg = {k: (round(float(np.mean([r[k] for r in rows])), 4), round(float(np.std([r[k] for r in rows])), 4)) for k in rows[0] if k != "seed"}
    diff = [r["fpr_documented"] - r["fpr_drug_matched"] for r in rows]
    agg["diff_documented_minus_drug_matched"] = (round(float(np.mean(diff)), 4), round(float(np.std(diff)), 4), int(sum(d > 0 for d in diff)))
    summ[name] = agg
out = {"N_doc": len(N_doc), "N_doc2": len(N_doc2), "distinct_drugs_in_documented_pairs": len(set(doc_drugs)),
       "summary_mean_sd_over_seeds": summ, "per_seed": res}
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(out, indent=1))
print(json.dumps(summ, indent=1))
