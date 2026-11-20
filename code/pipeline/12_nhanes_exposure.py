"""NullDDI step 12 v1.1: population exposure to NullDDI pairs in the US (NHANES 2017-March 2020
pre-pandemic, prescription medications used in the past 30 days; public-use files P_RXQ_RX, P_DEMO).
NHANES 2021-2023 public files carry no drug names (RDC only), so 2017-2020 is the latest usable cycle.

Concurrent use = the same participant reports both ingredients in the 30-day medication list in two
different products (a pair found only inside one fixed-dose combination product is not counted). Weighted with WTINTPRP (interview weight,
2017-March 2020 pre-pandemic); standard errors by Taylor linearisation over SDMVSTRA/SDMVPSU
(with-replacement PSU approximation). Estimates with n < 30 or RSE > 30% are flagged unreliable
(NCHS presentation standard for this design).

Questions answered:
  Q1 how many US residents concurrently use at least one NullDDI pair (all / by pair status)
  Q2 how many of them use a pair that DDInter 2.0 lists as an interaction (an alert a label
     statement contradicts in at least one direction) - analysis only, DDInter not redistributed
  Q3 against all residents exposed to any DDInter-listed pair (within the drugs DDInter's
     download covers), what share of that alert exposure involves a NullDDI pair
  Q4 the most used NullDDI pairs
"""
import argparse, csv, importlib.util, json, math
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tb", here / "05_tier_b_fda_tables.py")
tb = importlib.util.module_from_spec(spec); spec.loader.exec_module(tb)
ap = argparse.ArgumentParser()
for k in ("nhanes", "rxnorm", "pairs", "nulls", "ddinter", "out"):
    ap.add_argument("--" + k, required=True)
a = ap.parse_args()
ex, lex, _ = tb.load_lexicon(a.rxnorm)
lex_name = {c["rxcui"]: c["name"] for c in json.load(open(next(Path(a.rxnorm).glob("rxnorm_ingredients_*.json")), encoding="utf-8"))["concepts"]}
N = Path(a.nhanes)
dm = pd.read_sas(N / "P_DEMO.xpt", format="xport", encoding="latin1")[["SEQN", "WTINTPRP", "SDMVSTRA", "SDMVPSU"]]
rx = pd.read_sas(N / "P_RXQ_RX.xpt", format="xport", encoding="latin1")
rx = rx[rx.RXDUSE == 1]

# --- map NHANES generic names to RxNorm IN
cache, names_n, names_ok = {}, Counter(), Counter()
person = defaultdict(set)
products = defaultdict(list)          # per person: list of ingredient sets, one per reported product
for seqn, drug in zip(rx.SEQN, rx.RXDDRUG.fillna("")):
    prod = set()
    for part in drug.split(";"):
        p = part.strip().lower()
        if not p or p.startswith("99999") or "unspecified" in p:
            continue
        if p not in cache:
            cache[p] = tb.to_in(p, ex, lex)[0]
        names_n[p] += 1
        if cache[p]:
            names_ok[p] += 1; person[seqn].add(cache[p]); prod.add(cache[p])
    if prod:
        products[seqn].append(prod)
mapping = {"distinct_names": len(names_n), "distinct_mapped": sum(1 for p in names_n if cache[p]),
           "mentions": sum(names_n.values()), "mentions_mapped": sum(names_ok.values()),
           "unmapped_top": [p for p, _ in Counter({p: c for p, c in names_n.items() if not cache[p]}).most_common(25)]}

# --- DDInter listing (analysis only)
dd, dcache = {}, {}
for fp in sorted(Path(a.ddinter).glob("ddinter_downloads_code_*.csv")):
    with open(fp, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            ids = []
            for n in (r["Drug_A"].strip().lower(), r["Drug_B"].strip().lower()):
                if n not in dcache:
                    dcache[n] = tb.to_in(n, ex, lex)[0]
                ids.append(dcache[n])
            if None in ids or ids[0] == ids[1]:
                continue
            dd[tuple(sorted(ids))] = r["Level"].strip()

pairs = {}
for r in csv.DictReader(open(a.pairs, encoding="utf-8")):
    pairs[tuple(sorted((r["rxcui_a"], r["rxcui_b"])))] = r
dim = defaultdict(set)
for r in csv.DictReader(open(a.nulls, encoding="utf-8")):
    dim[tuple(sorted((r["perpetrator_rxcui"], r["victim_rxcui"])))].add(r["dimension"])

# --- per person indicators
dm = dm.set_index("SEQN")
groups = ["any_nullddi", "N2_bidirectional", "N1_one_direction", "N0_undirected_only", "nullddi_listed_in_ddinter",
          "nullddi_listed_major_or_moderate", "N2_listed_in_ddinter", "N2_listed_major_or_moderate", "nullddi_pk_only_dimension", "any_ddinter_pair", "any_ddinter_major_or_moderate"]
ind = {g: {} for g in groups}
pair_users = defaultdict(list)
for seqn in dm.index:
    s = sorted(person.get(seqn, ()))
    hit = Counter()
    for i in range(len(s)):
        for j in range(i + 1, len(s)):
            k = (s[i], s[j])
            # co-use counts only when the two ingredients come from different products (separate prescribing
            # decisions); a pair present only inside one fixed-dose combination product is not counted
            if not any(s[i] in p1 and s[j] in p2 and p1 is not p2 for p1 in products[seqn] for p2 in products[seqn]):
                continue
            lv = dd.get(k)
            if lv:
                hit["any_ddinter_pair"] = 1
                if lv in ("Major", "Moderate"):
                    hit["any_ddinter_major_or_moderate"] = 1
            if k in pairs:
                pair_users[k].append(seqn)
                hit["any_nullddi"] = 1; hit[pairs[k]["status"]] = 1
                if lv:
                    hit["nullddi_listed_in_ddinter"] = 1
                    if lv in ("Major", "Moderate"):
                        hit["nullddi_listed_major_or_moderate"] = 1
                    if pairs[k]["status"] == "N2_bidirectional":
                        hit["N2_listed_in_ddinter"] = 1
                        if lv in ("Major", "Moderate"):
                            hit["N2_listed_major_or_moderate"] = 1
                if dim.get(k) == {"PK"}:
                    hit["nullddi_pk_only_dimension"] = 1
    for g in groups:
        ind[g][seqn] = hit[g]

w, st, psu = dm.WTINTPRP, dm.SDMVSTRA, dm.SDMVPSU
def total(z):
    z = pd.Series(z).reindex(dm.index).fillna(0) * w
    t = z.sum()
    v = 0.0
    for h, sub in pd.DataFrame({"z": z, "h": st, "p": psu}).groupby("h"):
        c = sub.groupby("p").z.sum(); n = len(c)
        if n > 1:
            v += n / (n - 1) * ((c - c.mean()) ** 2).sum()
    return t, math.sqrt(v)
pop = w.sum()
res = {}
for g in groups:
    t, se = total(ind[g]); n = int(sum(ind[g].values()))
    res[g] = {"n_participants": n, "weighted_millions": round(t / 1e6, 3), "se_millions": round(se / 1e6, 3),
              "pct_of_population": round(100 * t / pop, 3), "rse_pct": round(100 * se / t, 1) if t else None,
              "reliable": bool(n >= 30 and t and se / t <= 0.30)}
top = []
for k, users in pair_users.items():
    t, se = total({u: 1 for u in users})
    r = pairs[k]
    nm = lambda x, c: x if x and not x.isdigit() else lex_name.get(c, c)
    top.append({"pair": f"{nm(r['drug_a'], r['rxcui_a'])} + {nm(r['drug_b'], r['rxcui_b'])}", "status": r["status"], "documented": r["documented"],
                "ddinter_level": dd.get(k, ""), "dimension": "/".join(sorted(dim.get(k, {"undirected"}))),
                "n_participants": len(users), "weighted_thousands": float(round(t / 1e3, 1)), "rse_pct": float(round(100 * se / t, 1)),
                "reliable": bool(len(users) >= 30 and se / t <= 0.30)})
top.sort(key=lambda x: -x["weighted_thousands"])
q3 = None
if res["any_ddinter_pair"]["weighted_millions"]:
    q3 = round(100 * res["nullddi_listed_in_ddinter"]["weighted_millions"] / res["any_ddinter_pair"]["weighted_millions"], 1)
out = {"source": "NHANES 2017-March 2020 pre-pandemic, P_RXQ_RX + P_DEMO (public use)", "population_millions": round(pop / 1e6, 1),
       "participants": int(len(dm)), "participants_with_mapped_rx": len(person), "name_mapping": mapping,
       "nullddi_pairs_used_by_anyone": len(pair_users), "groups": res,
       "share_of_ddinter_alert_exposure_involving_a_nullddi_pair_pct": q3, "top_pairs": top[:40]}
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(out, indent=1)); print(json.dumps({k: v for k, v in out.items() if k != "top_pairs"}, indent=1))
for x in top[:25]:
    print(x)
