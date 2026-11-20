"""NullDDI step 16b v1.0: adjudicate whether the labels document an interaction for the same
directed pair OUTSIDE the restriction of a conditional null (ground truth for "unconditional
reassurance" errors). Candidates come from 16a (own label of the perpetrator or the victim,
sentence names the other drug). Rules cannot judge them (v12c), so a pinned model does, twice.

Design fixed before results:
  - cases: all 150 nulls restricted by a strong condition (v0.2) + a control of 150 general nulls
    drawn with random.Random(20261120).
  - at most 15 candidate sentences per null; sentences carrying an exposure change or a dose
    action word come first, then the rest in label order.
  - a null counts as "interaction documented outside the restriction" when at least one of its
    sentences gets verdict interaction_outside_restriction in both runs.
Model: claude-sonnet-5-5, runs a1 and a2, strict JSON schema. No human review.

Commands (from the NullDDI folder; key from ANTHROPIC_API_KEY, never stored):
  prepare --cand .../cand16/ground_truth.jsonl --condition .../condition/nullddi_nulls_condition_llm.jsonl --dir .../adjudicate
  submit | status | collect --dir ...
  analyze --dir ... [--answers-root data/interim/v1_2]   (adds the four models' stable answers)
"""
import argparse, csv, hashlib, importlib.util, json, random, re, time
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.0"
MODEL = "claude-sonnet-5-5"
RUNS = ["a1", "a2"]
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("x3", here / "03_llm_extract_v1_2.py")
x3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(x3)
api, API, API_VERSION = x3.api, x3.API, x3.API_VERSION
PRIO = re.compile(r"(increas|decreas|reduc|elevat|lower)\w*|\b(auc|cmax|c max|exposure|concentration)|avoid|contraindicat|not recommended|dose|dosage|monitor", re.I)

SYSTEM = """A drug label states that a PERPETRATOR drug has no clinically relevant effect on a VICTIM drug, but only under a RESTRICTION (for example a single dose of the perpetrator, or one product of the victim). RESTRICTION may be 'none' when the statement is general.

You will see one other SENTENCE from the label of one of the two drugs. Decide what this sentence documents about the effect of the PERPETRATOR on the VICTIM.

verdict:
- interaction_outside_restriction: the sentence documents a clinically relevant change in the victim's exposure or effect caused by the perpetrator (a substantial change, or a recommendation to avoid, adjust the dose or monitor), under conditions that differ from the RESTRICTION (for example repeated doses instead of a single dose, or another product). When RESTRICTION is 'none', any such documented interaction counts.
- interaction_within_restriction_only: an interaction is documented, but only under the same conditions as the RESTRICTION.
- small_or_not_relevant: a change is reported but described as small or not clinically relevant, or the sentence is about something else (efficacy, adverse events of either drug alone, dosing of one drug).
- other_direction_or_other_drug: the sentence is about the victim affecting the perpetrator, or about a different drug.
- unclear: cannot be decided from the sentence.
Use only what the sentence says. quote: the shortest exact words that support the verdict."""
SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"verdict": {"type": "string", "enum": ["interaction_outside_restriction", "interaction_within_restriction_only",
                                                              "small_or_not_relevant", "other_direction_or_other_drug", "unclear"]},
                         "quote": {"type": "string"}},
          "required": ["verdict", "quote"]}


def cmd_prepare(a):
    d = Path(a.dir); d.mkdir(parents=True, exist_ok=True)
    quotes = {}
    for l in open(a.condition, encoding="utf-8"):
        x = json.loads(l)
        if x["kind"] == "directional":
            quotes[(x["perpetrator_rxcui"], x["victim_rxcui"])] = "; ".join(x.get("condition_quotes", [])[:3])
    C = [json.loads(l) for l in open(a.cand, encoding="utf-8")]
    strong = [x for x in C if x["group"] == "strong_conditional"]
    general = sorted([x for x in C if x["group"] == "general"], key=lambda x: (x["perp_rxcui"], x["vic_rxcui"]))
    control = random.Random(20261120).sample(general, 150)
    units, n = [], 0
    for grp, xs in (("strong_conditional", strong), ("control_general", control)):
        for x in xs:
            sents = x["positive_sentences"]
            sents = [s for s in sents if PRIO.search(s["sentence"])] + [s for s in sents if not PRIO.search(s["sentence"])]
            for s in sents[:15]:
                n += 1
                units.append({"unit_id": f"j{n:05d}", "group": grp, "perp": x["perp_rxcui"], "vic": x["vic_rxcui"],
                              "perp_name": x["perp"], "vic_name": x["vic"], "types": x["types"],
                              "restriction": (quotes.get((x["perp_rxcui"], x["vic_rxcui"])) or "none") if grp == "strong_conditional" else "none",
                              "label_of": s["label_of"], "set_id": s["set_id"], "sentence": s["sentence"]})
    cases = [{"group": g, "perp": x["perp_rxcui"], "vic": x["vic_rxcui"], "perp_name": x["perp"], "vic_name": x["vic"]}
             for g, xs in (("strong_conditional", strong), ("control_general", control)) for x in xs]
    for f, rows in (("units.jsonl", units), ("cases.jsonl", cases)):
        with open(d / f, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    meta = {"script_version": VERSION, "model": MODEL, "cases": Counter(c["group"] for c in cases), "units": Counter(u["group"] for u in units),
            "prompt_sha256": hashlib.sha256((SYSTEM + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()}
    (d / "units_meta.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta))


def units_of(d):
    return [json.loads(l) for l in open(Path(d) / "units.jsonl", encoding="utf-8")]


def cmd_submit(a):
    d = Path(a.dir)
    for run in RUNS:
        rf = d / f"run_{run}.json"
        if rf.exists():
            print(f"{run}: already submitted, skipped"); continue
        reqs = [{"custom_id": f"{u['unit_id']}_{run}",
                 "params": {"model": MODEL, "max_tokens": 600, "system": SYSTEM,
                            "messages": [{"role": "user", "content": f"PERPETRATOR: {u['perp_name']}\nVICTIM: {u['vic_name']}\nRESTRICTION: {u['restriction']}\nSENTENCE (from the label of the {u['label_of']}): {u['sentence']}"}],
                            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}} for u in units_of(d)]
        resp = json.loads(api("POST", API, {"requests": reqs}))
        rec = {"run": run, "model": MODEL, "batch_id": resp["id"], "n_requests": len(reqs), "api_version": API_VERSION,
               "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "script_version": VERSION}
        rf.write_text(json.dumps(rec, indent=1)); print(json.dumps(rec))


def cmd_status(a):
    for run in RUNS:
        rec = json.loads((Path(a.dir) / f"run_{run}.json").read_text())
        b = json.loads(api("GET", f"{API}/{rec['batch_id']}")); print(run, b["processing_status"], json.dumps(b["request_counts"]))


def cmd_collect(a):
    d = Path(a.dir)
    for run in RUNS:
        rec = json.loads((d / f"run_{run}.json").read_text())
        b = json.loads(api("GET", f"{API}/{rec['batch_id']}"))
        if b["processing_status"] != "ended":
            raise SystemExit(f"{run} not ended yet: {b['processing_status']} {b['request_counts']}. Run collect again later.")
        raw = api("GET", b["results_url"]); (d / f"raw_{run}.jsonl").write_bytes(raw)
        st = Counter()
        with open(d / f"answers_{run}.jsonl", "w", encoding="utf-8") as f:
            for line in raw.decode("utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line); t = r["result"]["type"]; st[t] += 1
                row = {"unit_id": r["custom_id"].rsplit("_", 1)[0], "result_type": t}
                if t == "succeeded":
                    txt = "".join(c.get("text", "") for c in r["result"]["message"]["content"] if c.get("type") == "text")
                    try:
                        row["answer"] = json.loads(txt)
                    except json.JSONDecodeError:
                        st["parse_error"] += 1
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        rec["collected"] = dict(st); rec["raw_sha256"] = hashlib.sha256(raw).hexdigest()
        (d / f"run_{run}.json").write_text(json.dumps(rec, indent=1)); print(run, json.dumps(rec["collected"]))
    print("COLLECT COMPLETE")


def stable_answers(root, f1, f2):
    def load(f):
        R = {}
        for l in open(f, encoding="utf-8"):
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if x["answer"] != "NO_ANSWER":
                R[x["item_id"]] = x["answer"]
        return R
    a1, a2 = load(root / f1), load(root / f2)
    return {i: (a1[i] if a1[i] == a2[i] else "unstable") for i in set(a1) & set(a2)}


def cmd_analyze(a):
    d = Path(a.dir); units = {u["unit_id"]: u for u in units_of(d)}
    ans = {r: {} for r in RUNS}
    for r in RUNS:
        for l in open(d / f"answers_{r}.jsonl", encoding="utf-8"):
            x = json.loads(l)
            if "answer" in x:
                ans[r][x["unit_id"]] = x["answer"]["verdict"]
    agree = sum(1 for u in units if ans["a1"].get(u) == ans["a2"].get(u)) / len(units)
    pos = defaultdict(list)
    vc = Counter()
    for u, x in units.items():
        v1, v2 = ans["a1"].get(u), ans["a2"].get(u)
        vc[(x["group"], v1 if v1 == v2 else "disagree")] += 1
        if v1 == v2 == "interaction_outside_restriction":
            pos[(x["perp"], x["vic"])].append({"sentence": x["sentence"], "label_of": x["label_of"], "set_id": x["set_id"]})
    cases = [json.loads(l) for l in open(d / "cases.jsonl", encoding="utf-8")]
    res = defaultdict(Counter); out = []
    for c in cases:
        k = (c["perp"], c["vic"]); c["interaction_documented_outside"] = bool(pos.get(k)); c["evidence"] = pos.get(k, [])[:3]
        res[c["group"]]["n"] += 1; res[c["group"]]["documented"] += c["interaction_documented_outside"]; out.append(c)
    rep = {"unit_agreement": round(agree, 4), "verdicts": {f"{g}|{v}": n for (g, v), n in sorted(vc.items())},
           "cases": {g: dict(v, pct=round(100 * v["documented"] / v["n"], 1)) for g, v in res.items()}}
    if a.answers_root:
        R = Path(a.answers_root)
        items = {json.loads(l)["item_id"]: json.loads(l) for l in open(R / "overwarn_pk/items.jsonl", encoding="utf-8")}
        key = {(x["perp"], x["vic"]): i for i, x in items.items() if x["cls"] == "null"}
        models = {"Sonnet 5.5": ("overwarn_pk/answers_mA_1.jsonl", "overwarn_pk/answers_mA_2.jsonl"),
                  "Haiku 5.5": ("overwarn_pk/answers_mB_1.jsonl", "overwarn_pk/answers_mB_2.jsonl"),
                  "GPT-6.2 Sol": ("overwarn_pk_openai/answers_g_1.jsonl", "overwarn_pk_openai/answers_g_2.jsonl"),
                  "Gemini 4 Carbon": ("overwarn_pk_google/answers_g_1.jsonl", "overwarn_pk_google/answers_g_2.jsonl")}
        mres = {}
        for m, (f1, f2) in models.items():
            S = stable_answers(R, f1, f2); cnt = defaultdict(Counter)
            for c in out:
                i = key.get((c["perp"], c["vic"]))
                if i is None or i not in S:
                    continue
                g = c["group"] + ("|documented" if c["interaction_documented_outside"] else "|not_documented")
                cnt[g]["n"] += 1; cnt[g][S[i]] += 1
            mres[m] = {g: dict(v, no_interaction_pct=round(100 * v["no_clinically_significant_interaction"] / v["n"], 1) if v["n"] else None)
                       for g, v in sorted(cnt.items())}
        rep["models_stable_answers"] = mres
    with open(d / "adjudicated_cases.jsonl", "w", encoding="utf-8") as f:
        for c in out:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    (d / "adjudication_report.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("--cand", required=True); p.add_argument("--condition", required=True); p.add_argument("--dir", required=True)
    for c in ("submit", "status", "collect"):
        p = sp.add_parser(c); p.add_argument("--dir", required=True)
    p = sp.add_parser("analyze"); p.add_argument("--dir", required=True); p.add_argument("--answers-root")
    a = ap.parse_args()
    {"prepare": cmd_prepare, "submit": cmd_submit, "status": cmd_status, "collect": cmd_collect, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
