"""NullDDI step 18 v1.0: two follow-ups to step 17 (open inputs, no API cost).

A. Robustness: a third, published-style model. DeepDDI-style structural similarity profiles (SSP): each
   drug = Tanimoto similarity of its Morgan fingerprint to a fixed reference set of 512 drugs (seed 11);
   pair = [sum, |difference|] of the two profiles (order-free); multilayer perceptron (sklearn).
B. Intervention: does adding documented non-interactions to training repair the false alarms?
   5-fold cross-validation over the documented pairs (N_doc from step 17's definition): in each fold the
   training set = DDInter positives + random negatives + documented negatives of the other 4 folds
   (each documented negative weighted 5x); test = held-out positives / random pairs as in step 17 and the
   held-out fold of documented pairs. Compared with the same fold scored by a model trained without them.
Same seeds, splits, threshold rule (90% sensitivity on held-out positives) as step 17. Fixed before results.
"""
import argparse, importlib.util, json, random, sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from rdkit import DataStructs
from rdkit.Chem import rdFingerprintGenerator
from rdkit import Chem

here = Path(__file__).resolve().parent
# reuse step 17 data preparation by executing its top part
src = (here / "17_predictor_negatives.py").read_text()
prep = src[: src.index("for seed in range(a.seeds):")]
sys.argv = [sys.argv[0]] + sys.argv[1:]
g = {"__file__": str(here / "17_predictor_negatives.py"), "__name__": "prep17"}
exec(compile(prep, "17_prep", "exec"), g)
a, drugs, smiles, pos, nd_all, N_doc, N_doc2, dd_drugs, X17, P_all = (g[k] for k in ("a", "drugs", "smiles", "pos", "nd_all", "N_doc", "N_doc2", "dd_drugs", "X", "P_all"))

# --- A. SSP features
gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
bv = {d: gen.GetFingerprint(Chem.MolFromSmiles(smiles[d])) for d in drugs}
ref = random.Random(11).sample(sorted(drugs), 512)
refv = [bv[r] for r in ref]
dl = sorted(drugs); di = {d: i for i, d in enumerate(dl)}
S = np.array([DataStructs.BulkTanimotoSimilarity(bv[d], refv) for d in dl], dtype=np.float32)
def Xssp(keys):
    if not keys:
        return np.zeros((0, 1024), dtype=np.float32)
    ia = np.array([di[p] for p, q in keys]); ib = np.array([di[q] for p, q in keys])
    return np.concatenate([S[ia] + S[ib], np.abs(S[ia] - S[ib])], axis=1)

out = {"A_ssp_mlp": [], "B_intervention": []}
docs = sorted(N_doc)
for seed in range(a.seeds):
    rng = random.Random(1000 + seed)
    P = P_all[:]; rng.shuffle(P); cut = int(0.8 * len(P)); Ptr, Pte = P[:cut], P[cut:]
    excl = set(pos) | nd_all
    def rand_pairs(n, banned):
        s = set()
        while len(s) < n:
            k = tuple(sorted(rng.sample(dd_drugs, 2)))
            if k not in excl and k not in banned:
                s.add(k)
        return list(s)
    Rte = rand_pairs(len(Pte), set()); Rtr = rand_pairs(len(Ptr), set(Rte))
    ytr = np.r_[np.ones(len(Ptr)), np.zeros(len(Rtr))]
    # A
    mlp = MLPClassifier(hidden_layer_sizes=(256, 64), max_iter=60, early_stopping=True, random_state=seed)
    mlp.fit(Xssp(Ptr + Rtr), ytr)
    sp, sr, sn, sn2 = (mlp.predict_proba(Xssp(k))[:, 1] for k in (Pte, Rte, docs, N_doc2))
    thr = np.quantile(sp, 0.10)
    auc = lambda neg: float(roc_auc_score(np.r_[np.ones(len(sp)), np.zeros(len(neg))], np.r_[sp, neg]))
    out["A_ssp_mlp"].append({"seed": seed, "auc_vs_random": auc(sr), "auc_vs_documented": auc(sn),
                             "fpr_random": float((sr >= thr).mean()), "fpr_documented": float((sn >= thr).mean()),
                             "fpr_documented_N2": float((sn2 >= thr).mean())})
    # B (gradient boosting, as in step 17)
    order = docs[:]; random.Random(500 + seed).shuffle(order)
    folds = [order[i::5] for i in range(5)]
    base = HistGradientBoostingClassifier(max_iter=300, random_state=seed).fit(X17(Ptr + Rtr), ytr)
    bp = base.predict_proba(X17(Pte))[:, 1]; bthr = np.quantile(bp, 0.10)
    br = base.predict_proba(X17(Rte))[:, 1]
    for f in range(5):
        test = folds[f]; train_docs = [k for j in range(5) if j != f for k in folds[j]]
        Xi = X17(Ptr + Rtr + train_docs); yi = np.r_[ytr, np.zeros(len(train_docs))]
        w = np.r_[np.ones(len(Ptr) + len(Rtr)), np.full(len(train_docs), 5.0)]
        m = HistGradientBoostingClassifier(max_iter=300, random_state=seed).fit(Xi, yi, sample_weight=w)
        ip = m.predict_proba(X17(Pte))[:, 1]; ithr = np.quantile(ip, 0.10)
        it = m.predict_proba(X17(test))[:, 1]; bt = base.predict_proba(X17(test))[:, 1]
        ir = m.predict_proba(X17(Rte))[:, 1]
        out["B_intervention"].append({"seed": seed, "fold": f, "n_test_docs": len(test),
                                      "fpr_documented_without": float((bt >= bthr).mean()), "fpr_documented_with": float((it >= ithr).mean()),
                                      "fpr_random_without": float((br >= bthr).mean()), "fpr_random_with": float((ir >= ithr).mean()),
                                      "auc_random_without": float(roc_auc_score(np.r_[np.ones(len(bp)), np.zeros(len(br))], np.r_[bp, br])),
                                      "auc_random_with": float(roc_auc_score(np.r_[np.ones(len(ip)), np.zeros(len(ir))], np.r_[ip, ir]))})
    print("seed", seed, "done", flush=True)
summ = {}
for k, rows in out.items():
    keys = [c for c in rows[0] if c not in ("seed", "fold", "n_test_docs")]
    summ[k] = {c: [round(float(np.mean([r[c] for r in rows])), 4), round(float(np.std([r[c] for r in rows])), 4)] for c in keys}
res = {"n_documented": len(docs), "n_documented_N2": len(N_doc2), "summary_mean_sd": summ, "rows": out}
Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(json.dumps(res, indent=1))
print(json.dumps(summ, indent=1))
