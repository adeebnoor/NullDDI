"""NullDDI step 17 v1.0: what a standard DDI predictor does with documented non-interactions.

Standard practice (reviewed in refs) trains DDI predictors with database interactions as positives and
randomly drawn unlisted pairs as "negatives", and evaluates on the same kind of random negatives. This
script reproduces that practice with open inputs and then scores the label-documented non-interactions.

Inputs (all open or analysis-only): DDInter 2.0 pairs (positives; analysis only), Wikidata SMILES/ATC per
RxNorm CUI, NullDDI v0.1 pairs + v0.2 condition classes.
Features per drug: Morgan fingerprint (radius 2, 1024 bits) + ATC level-2 one-hot. Pair features are
order-free: elementwise OR and AND of the two drug vectors.
Model: logistic regression (L2) and histogram gradient boosting; 5 seeds (resampled negatives and split).
Positives: a fixed random sample of at most 30,000 DDInter pairs (seed 7) for tractability.
All NullDDI pairs are removed from training (positives and negatives).

Evaluation sets (fixed before results):
  P_test   held-out DDInter positives (20% of pairs)
  R_test   held-out random unlisted pairs, same size as P_test
  N_doc    NullDDI pairs with a generalizable statement, both drugs featurised, NOT listed in DDInter
  N_doc2   the subset documented in both directions (N2)
  N_listed NullDDI pairs that DDInter lists (reported separately; label and database disagree)
Reported: AUROC(P_test vs R_test), AUROC(P_test vs N_doc), false-positive rate of R_test and N_doc at the
threshold giving 90% sensitivity on P_test, and decision flips of N_doc pairs across seeds (execution floor).
"""
import argparse, csv, importlib.util, json, random, re
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import rdFingerprintGenerator
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
RDLogger.DisableLog("rdApp.*")
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tb", here / "05_tier_b_fda_tables.py")
tb = importlib.util.module_from_spec(spec); spec.loader.exec_module(tb)
ap = argparse.ArgumentParser()
for k in ("rxnorm", "ddinter", "wikidata", "pairs", "condition", "out"):
    ap.add_argument("--" + k, required=True)
ap.add_argument("--seeds", type=int, default=5)
ap.add_argument("--max-pos", type=int, default=30000)
a = ap.parse_args()
ex, lex, _ = tb.load_lexicon(a.rxnorm)
concepts = {c["rxcui"]: c for c in json.load(open(next(Path(a.rxnorm).glob("rxnorm_ingredients_*.json")), encoding="utf-8"))["concepts"]}

# --- drug features (Wikidata rxcui may be IN or other TTY; map to IN)
smiles, atc = {}, defaultdict(set)
for qid, rx, smi, iso, code in json.load(open(a.wikidata, encoding="utf-8"))["rows"]:
    c = concepts.get(rx)
    if not c:
        continue
    inn = rx if c["tty"] == "IN" else tb.to_in(c["name"].lower(), ex, lex)[0]
    if not inn:
        continue
    s = smi or iso
    if s and inn not in smiles:
        smiles[inn] = s
    if code:
        atc[inn].add(code[:3])
gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024)
fp = {}
for inn, s in smiles.items():
    m = Chem.MolFromSmiles(s)
    if m is not None:
        fp[inn] = np.array(gen.GetFingerprintAsNumPy(m), dtype=np.uint8)
atc_codes = sorted({c for v in atc.values() for c in v})
ai = {c: i for i, c in enumerate(atc_codes)}
def vec(d):
    v = np.zeros(1024 + len(atc_codes), dtype=np.uint8); v[:1024] = fp[d]
    for c in atc.get(d, ()):
        v[1024 + ai[c]] = 1
    return v
drugs = set(fp)

# --- DDInter positives (analysis only)
pos, cache = {}, {}
for f in sorted(Path(a.ddinter).glob("ddinter_downloads_code_*.csv")):
    for r in csv.DictReader(open(f, encoding="utf-8", newline="")):
        ids = []
        for n in (r["Drug_A"].strip().lower(), r["Drug_B"].strip().lower()):
            if n not in cache:
                cache[n] = tb.to_in(n, ex, lex)[0]
            ids.append(cache[n])
        if None in ids or ids[0] == ids[1] or ids[0] not in drugs or ids[1] not in drugs:
            continue
        pos[tuple(sorted(ids))] = r["Level"].strip()
dd_drugs = sorted({x for k in pos for x in k})

# --- NullDDI pairs and condition
STRONG = {"single_dose_perpetrator", "victim_specific_product", "perpetrator_specific_product", "specific_route", "staggered_administration"}
usable = defaultdict(bool)
for l in open(a.condition, encoding="utf-8"):
    x = json.loads(l)
    if x["kind"] == "directional":
        k = tuple(sorted((x["perpetrator_rxcui"], x["victim_rxcui"])))
        usable[k] |= not (x.get("condition_llm") == "conditional" and set(x.get("condition_types", [])) & STRONG)
nd_all, nd_status = set(), {}
for r in csv.DictReader(open(a.pairs, encoding="utf-8")):
    k = tuple(sorted((r["rxcui_a"], r["rxcui_b"])))
    nd_all.add(k); nd_status[k] = r["status"]
feat = lambda k: k[0] in drugs and k[1] in drugs
N_doc = [k for k in nd_all if feat(k) and k not in pos and (usable[k] or nd_status[k].startswith("N0"))]
N_doc2 = [k for k in N_doc if nd_status[k].startswith("N2")]
N_listed = [k for k in nd_all if feat(k) and k in pos]
N_cond = [k for k in nd_all if feat(k) and k not in pos and not usable[k] and not nd_status[k].startswith("N0")]

dl = sorted(drugs); di = {d: i for i, d in enumerate(dl)}
M = np.stack([vec(d) for d in dl])
def X(keys):
    if not keys:
        return np.zeros((0, 2 * M.shape[1]), dtype=np.uint8)
    ia = np.array([di[p] for p, q in keys]); ib = np.array([di[q] for p, q in keys])
    u, v = M[ia], M[ib]
    return np.concatenate([u | v, u & v], axis=1)

res = defaultdict(list); flips = defaultdict(list)
P_all = sorted(k for k in pos if k not in nd_all)
if len(P_all) > a.max_pos:
    P_all = random.Random(7).sample(P_all, a.max_pos)
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
    Xtr = X(Ptr + Rtr); ytr = np.r_[np.ones(len(Ptr)), np.zeros(len(Rtr))]
    for name, mdl in (("logreg", LogisticRegression(C=0.5, max_iter=2000)), ("gboost", HistGradientBoostingClassifier(max_iter=300, random_state=seed))):
        mdl.fit(Xtr, ytr)
        s = lambda keys: mdl.predict_proba(X(keys))[:, 1] if keys else np.array([])
        sp, sr, sn, sn2, sl, sc = s(Pte), s(Rte), s(N_doc), s(N_doc2), s(N_listed), s(N_cond)
        thr = np.quantile(sp, 0.10)                  # 90% sensitivity on held-out positives
        fpr = lambda x: float((x >= thr).mean()) if len(x) else None
        auc = lambda neg: float(roc_auc_score(np.r_[np.ones(len(sp)), np.zeros(len(neg))], np.r_[sp, neg])) if len(neg) else None
        res[name].append({"seed": seed, "auc_vs_random": auc(sr), "auc_vs_documented": auc(sn), "auc_vs_documented_N2": auc(sn2),
                          "fpr_random": fpr(sr), "fpr_documented": fpr(sn), "fpr_documented_N2": fpr(sn2),
                          "fpr_documented_but_listed": fpr(sl), "fpr_conditional": fpr(sc),
                          "mean_score_random": float(sr.mean()), "mean_score_documented": float(sn.mean())})
        flips[name].append((sn >= thr).astype(int))
summ = {}
for name, rows in res.items():
    agg = {k: (round(float(np.mean([r[k] for r in rows if r[k] is not None])), 4), round(float(np.std([r[k] for r in rows if r[k] is not None])), 4))
           for k in rows[0] if k != "seed"}
    F = np.array(flips[name]); unstable = float(((F.min(0) == 0) & (F.max(0) == 1)).mean())
    agg["documented_pairs_flagged_in_all_seeds"] = float((F.min(0) == 1).mean())
    agg["documented_pairs_unstable_across_seeds"] = unstable
    summ[name] = agg
out = {"drugs_featurised": len(drugs), "ddinter_positive_pairs_featurised": len(pos), "positives_used": len(P_all),
       "N_doc": len(N_doc), "N_doc2": len(N_doc2), "N_listed": len(N_listed), "N_conditional": len(N_cond),
       "summary_mean_sd_over_seeds": summ, "per_seed": res}
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "per_seed"}, indent=1))
