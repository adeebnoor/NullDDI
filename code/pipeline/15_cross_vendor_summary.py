"""NullDDI step 15 v1.0: four-model, three-developer summary of the PK-only over-warning experiment.
Stable answer = same answer in both runs of a model; items lacking a valid answer in either run are
excluded for that model (reported as n). Nulls split by pair status (N1/N2) and by condition
(general vs strong-conditional, v0.2). Inputs: overwarn_pk (Anthropic mA/mB), overwarn_pk_openai,
overwarn_pk_google (g_1/g_2), condition/nullddi_nulls_condition_llm.jsonl, release pairs csv."""
import json, csv, collections, sys
from pathlib import Path
B = Path("data/interim/v1_2")
its = {json.loads(l)["item_id"]: json.loads(l) for l in open(B / "overwarn_pk/items.jsonl")}
st = {tuple(sorted((r["rxcui_a"], r["rxcui_b"]))): r["status"] for r in csv.DictReader(open("data/release/v0_1/nullddi_pairs.csv"))}
S = {"single_dose_perpetrator", "victim_specific_product", "perpetrator_specific_product", "specific_route", "staggered_administration"}
cond = {}
for l in open(B / "condition/nullddi_nulls_condition_llm.jsonl"):
    x = json.loads(l)
    if x["kind"] == "directional":
        cond[(x["perpetrator_rxcui"], x["victim_rxcui"])] = "strong_conditional" if x["condition_llm"] == "conditional" and set(x.get("condition_types", [])) & S else ("uncertain" if x["condition_llm"] == "uncertain" else "general")
def load(f):
    R = {}
    for l in open(f):
        try: x = json.loads(l)
        except ValueError: continue
        if x["answer"] != "NO_ANSWER": R[x["item_id"]] = x["answer"]
    return R
M = {"Sonnet 5.5 (Anthropic)": ("overwarn_pk/answers_mA_1.jsonl", "overwarn_pk/answers_mA_2.jsonl"),
     "Haiku 5.5 (Anthropic)": ("overwarn_pk/answers_mB_1.jsonl", "overwarn_pk/answers_mB_2.jsonl"),
     "GPT-6.2 Sol (OpenAI)": ("overwarn_pk_openai/answers_g_1.jsonl", "overwarn_pk_openai/answers_g_2.jsonl"),
     "Gemini 4 Carbon (Google)": ("overwarn_pk_google/answers_g_1.jsonl", "overwarn_pk_google/answers_g_2.jsonl")}
out = {}
for name, (f1, f2) in M.items():
    a1, a2 = load(B / f1), load(B / f2)
    ids = set(a1) & set(a2)
    c = collections.defaultdict(collections.Counter)
    for i in ids:
        x = its[i]; s = a1[i] if a1[i] == a2[i] else "unstable"
        gs = [x["cls"]]
        if x["cls"] == "null":
            k = (x["perp"], x["vic"]); gs += ["null_" + st.get(tuple(sorted(k)), "?")[:2], "null_" + cond.get(k, "?"),
                                             "null_" + cond.get(k, "?") + "_" + st.get(tuple(sorted(k)), "?")[:2]]
        for g in gs:
            c[g]["n"] += 1; c[g][s] += 1
    pct = lambda g, k: round(100 * c[g][k] / c[g]["n"], 1) if c[g]["n"] else None
    out[name] = {"items_with_both_runs": len(ids), "rerun_disagreement_pct": round(100 * sum(1 for i in ids if a1[i] != a2[i]) / len(ids), 1),
                 "stable_overwarning_nulls_pct": pct("null", "interaction"), "N1": pct("null_N1", "interaction"), "N2": pct("null_N2", "interaction"),
                 "general_N1": pct("null_general_N1", "interaction"), "general_N2": pct("null_general_N2", "interaction"),
                 "strong_conditional_stable_no_interaction_pct": pct("null_strong_conditional", "no_clinically_significant_interaction"),
                 "strong_conditional_stable_interaction_pct": pct("null_strong_conditional", "interaction"),
                 "sensitivity_stable_pct": pct("positive", "interaction"), "reverse_stable_interaction_pct": pct("positive_reverse", "interaction"),
                 "null_recognised_stable_pct": pct("null", "no_clinically_significant_interaction"),
                 "n": {g: v["n"] for g, v in c.items()}}
Path(B / "cross_vendor").mkdir(exist_ok=True)
(B / "cross_vendor/cross_vendor_summary.json").write_text(json.dumps(out, indent=1))
for k, v in out.items():
    print(k, {kk: vv for kk, vv in v.items() if kk != "n"})
