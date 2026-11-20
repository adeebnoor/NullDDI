"""NullDDI step 13 v1.0: condition of each released null (dataset v0.2 fields), extractor B style.
Rules (11_condition_tags.py) catch single-dose and staggered wording but cannot judge whether a
brand, dosage form, dose level or population in the sentence RESTRICTS the null or only describes
the study. That judgement is asked of the model, sentence by sentence, with a strict JSON schema.

Unit = one distinct evidence sentence of one directional null (perpetrator -> victim).
Two independent runs of the same pinned model (c1, c2). A field is accepted when both runs agree;
otherwise it is 'uncertain'. No human review.

Null-level rule (written before seeing results):
  unconditional  at least one sentence is accepted with generalizes_to_ingredients = true
  conditional    every sentence is accepted with generalizes_to_ingredients = false
  uncertain      anything else
The condition types of a conditional null are the union over its sentences.

Commands (run from the NullDDI folder; key from ANTHROPIC_API_KEY, never stored):
  prepare --nulls data/release/v0_1/nullddi_nulls.jsonl --dir data/interim/v1_2/condition
  submit  --dir ...            (two batches c1, c2; refuses to resubmit an existing run)
  status  --dir ...
  collect --dir ...
  analyze --dir ... --nulls ... (writes nullddi_nulls_condition_llm.jsonl + condition_report.json)
"""
import argparse, hashlib, importlib.util, json, re, time
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.0"
MODEL = "claude-sonnet-5-5"
RUNS = ["c1", "c2"]
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("x3", here / "03_llm_extract_v1_2.py")
x3 = importlib.util.module_from_spec(spec); spec.loader.exec_module(x3)
api, API, API_VERSION = x3.api, x3.API, x3.API_VERSION

SYSTEM = """You read one sentence from a drug label that states that a PERPETRATOR drug has no clinically relevant effect on a VICTIM drug. Decide whether the sentence restricts that no-interaction statement to particular conditions, or whether it supports it for the two ingredients in general (usual doses, usual products).

Report only what the sentence itself says. Do not use outside knowledge about the drugs.

dosing_condition:
- none: no restriction on how the perpetrator was given, or the dose is only a routine description of the study.
- single_dose_perpetrator: the perpetrator was given as a single dose (repeated dosing is not covered).
- specific_dose_or_regimen: the statement is limited to a stated dose, dose range or regimen of the perpetrator (for example 'lower doses', 'at 200 mg once daily'), wording that implies other doses may differ.
- staggered_administration: the drugs were given at separated times.
formulation_restriction:
- none: the statement applies to the drug generally.
- victim_specific_product: the statement is limited to one product, brand or dosage form of the VICTIM (for example a named oral solution or a delayed-release tablet) when other products of the same ingredient exist or are implied.
- perpetrator_specific_product: the same for the PERPETRATOR.
- specific_route: limited to one route (for example intravenous, topical).
population_restriction:
- none, or specific_population (for example only in patients with a named disease, only in children).
generalizes_to_ingredients: true when the sentence, as written, supports a no-interaction statement for the two ingredients at usual doses and products; false when any restriction above limits it.
condition_quote: the shortest exact words from the sentence that carry the restriction, or an empty string."""

SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {
              "dosing_condition": {"type": "string", "enum": ["none", "single_dose_perpetrator", "specific_dose_or_regimen", "staggered_administration"]},
              "formulation_restriction": {"type": "string", "enum": ["none", "victim_specific_product", "perpetrator_specific_product", "specific_route"]},
              "population_restriction": {"type": "string", "enum": ["none", "specific_population"]},
              "generalizes_to_ingredients": {"type": "boolean"},
              "condition_quote": {"type": "string"}},
          "required": ["dosing_condition", "formulation_restriction", "population_restriction", "generalizes_to_ingredients", "condition_quote"]}
FIELDS = ["dosing_condition", "formulation_restriction", "population_restriction", "generalizes_to_ingredients"]


def norm(s):
    return re.sub(r"\W+", " ", s.lower()).strip()


def cmd_prepare(a):
    d = Path(a.dir); d.mkdir(parents=True, exist_ok=True)
    units, n = [], 0
    for line in open(a.nulls, encoding="utf-8"):
        x = json.loads(line)
        if x["kind"] != "directional":
            continue
        seen = set()
        for e in x["evidence"]:
            k = norm(e["sentence"])
            if k in seen:
                continue
            seen.add(k); n += 1
            units.append({"unit_id": f"k{n:05d}", "perp": x["perpetrator_rxcui"], "vic": x["victim_rxcui"],
                          "perp_name": x["perpetrator"], "vic_name": x["victim"], "sentence": e["sentence"]})
    with open(d / "units.jsonl", "w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    meta = {"script_version": VERSION, "model": MODEL, "units": len(units),
            "prompt_sha256": hashlib.sha256((SYSTEM + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest(),
            "nulls_sha256": hashlib.sha256(Path(a.nulls).read_bytes()).hexdigest()}
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
                 "params": {"model": MODEL, "max_tokens": 1024, "system": SYSTEM,
                            "messages": [{"role": "user", "content":
                                          f"PERPETRATOR: {u['perp_name']}\nVICTIM: {u['vic_name']}\nSENTENCE: {u['sentence']}"}],
                            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}} for u in units_of(d)]
        resp = json.loads(api("POST", API, {"requests": reqs}))
        rec = {"run": run, "model": MODEL, "batch_id": resp["id"], "n_requests": len(reqs), "api_version": API_VERSION,
               "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "script_version": VERSION}
        rf.write_text(json.dumps(rec, indent=1)); print(json.dumps(rec))


def cmd_status(a):
    for run in RUNS:
        rec = json.loads((Path(a.dir) / f"run_{run}.json").read_text())
        b = json.loads(api("GET", f"{API}/{rec['batch_id']}"))
        print(run, b["processing_status"], json.dumps(b["request_counts"]))


def cmd_collect(a):
    d = Path(a.dir)
    for run in RUNS:
        rec = json.loads((d / f"run_{run}.json").read_text())
        b = json.loads(api("GET", f"{API}/{rec['batch_id']}"))
        if b["processing_status"] != "ended":
            raise SystemExit(f"{run} not ended yet: {b['processing_status']} {b['request_counts']}. Run collect again later.")
        raw = api("GET", b["results_url"]); (d / f"raw_{run}.jsonl").write_bytes(raw)
        st, rows = Counter(), []
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line); uid = r["custom_id"].rsplit("_", 1)[0]; t = r["result"]["type"]; st[t] += 1
            row = {"unit_id": uid, "result_type": t}
            if t == "succeeded":
                m = r["result"]["message"]
                txt = "".join(c.get("text", "") for c in m["content"] if c.get("type") == "text")
                try:
                    row["answer"] = json.loads(txt)
                except json.JSONDecodeError:
                    st["parse_error"] += 1
                row["model"] = m.get("model")
            rows.append(row)
        with open(d / f"answers_{run}.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        rec["collected"] = dict(st); rec["raw_sha256"] = hashlib.sha256(raw).hexdigest()
        (d / f"run_{run}.json").write_text(json.dumps(rec, indent=1)); print(run, json.dumps(rec["collected"]))
    print("COLLECT COMPLETE")


def cmd_analyze(a):
    d = Path(a.dir); units = {u["unit_id"]: u for u in units_of(d)}
    ans = {}
    for run in RUNS:
        ans[run] = {}
        for l in open(d / f"answers_{run}.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if "answer" in r:
                ans[run][r["unit_id"]] = r["answer"]
    agree, acc = Counter(), {}
    for uid in units:
        a1, a2 = ans["c1"].get(uid), ans["c2"].get(uid)
        if not a1 or not a2:
            acc[uid] = None; agree["missing"] += 1; continue
        rec = {}
        for f in FIELDS:
            same = a1[f] == a2[f]; agree[f + "_agree"] += same
            rec[f] = a1[f] if same else "uncertain"
        rec["condition_quote"] = a1["condition_quote"] if a1["condition_quote"] == a2["condition_quote"] else a1["condition_quote"] or a2["condition_quote"]
        acc[uid] = rec
    by_null = defaultdict(list)
    for uid, u in units.items():
        by_null[(u["perp"], u["vic"])].append((uid, acc[uid]))
    lvl, types, out = Counter(), Counter(), []
    for line in open(a.nulls, encoding="utf-8"):
        x = json.loads(line)
        if x["kind"] == "directional":
            recs = [r for _, r in by_null.get((x["perpetrator_rxcui"], x["victim_rxcui"]), [])]
            g = [r["generalizes_to_ingredients"] if r else "uncertain" for r in recs]
            if any(v is True for v in g):
                c = "unconditional"
            elif g and all(v is False for v in g):
                c = "conditional"
            else:
                c = "uncertain"
            x["condition_llm"] = c
            ty = set()
            if c == "conditional":
                for r in recs:
                    for f in ("dosing_condition", "formulation_restriction", "population_restriction"):
                        if r[f] not in ("none", "uncertain"):
                            ty.add(r[f])
                x["condition_types"] = sorted(ty)
                x["condition_quotes"] = sorted({r["condition_quote"] for r in recs if r["condition_quote"]})
                for t in ty:
                    types[t] += 1
            lvl[c] += 1
        out.append(x)
    with open(d / "nullddi_nulls_condition_llm.jsonl", "w", encoding="utf-8") as f:
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    n = len(units)
    rep = {"units": n, "field_agreement": {k: round(v / n, 4) for k, v in agree.items()},
           "null_level": dict(lvl), "conditional_types": dict(types)}
    (d / "condition_report.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("--nulls", required=True); p.add_argument("--dir", required=True)
    for c in ("submit", "status", "collect"):
        p = sp.add_parser(c); p.add_argument("--dir", required=True)
    p = sp.add_parser("analyze"); p.add_argument("--dir", required=True); p.add_argument("--nulls", required=True)
    a = ap.parse_args()
    {"prepare": cmd_prepare, "submit": cmd_submit, "status": cmd_status, "collect": cmd_collect, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
