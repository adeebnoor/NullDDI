"""NullDDI step 19 v1.0: does giving a language model the negative evidence, and its structure, fix its errors?

Same question and answer schema as step 9b (pharmacokinetics, one direction). Three evidence arms:
  none        no label text (as in 9b)
  sentence    the label sentence that documents the non-interaction, as written
  structured  a NullDDI record: documented direction, dimension, condition (if any), the sentence, and an
              explicit line stating which direction is NOT documented
Item sets (fixed before results):
  REV   the undocumented direction of every one-direction pair (N1): perpetrator and victim swapped.
        Correct answers: insufficient_evidence, or a documented interaction; "no clinically significant
        interaction" from the evidence alone is a transfer of the null to the wrong direction.  Arms: none, sentence, structured.
  COND  the 150 nulls restricted by a strong condition, asked in their own direction, generally.
        Measured: unqualified "no clinically significant interaction" (generalising a restricted null).  Arms: sentence, structured.
  DOC   all other directional nulls in their own direction (fidelity check: expect no interaction). Arms: sentence, structured.
Model: claude-sonnet-5-5, two runs (s1, s2), strict JSON schema; stable answer = same in both runs.
Commands (from the NullDDI folder; key from ANTHROPIC_API_KEY, never stored):
  prepare --condition data/interim/v1_2/condition/nullddi_nulls_condition_llm.jsonl --pairs data/release/v0_1/nullddi_pairs.csv --dir data/interim/v1_2/evidence
  submit | status | collect --dir ...
  analyze --dir ...
"""
import argparse, csv, hashlib, importlib.util, json, time
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.1"
MODEL = "claude-sonnet-5-5"
RUNS = ["s1", "s2"]
here = Path(__file__).resolve().parent
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, here / fn)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
b9 = load("b9", "09b_llm_overwarning_pk.py"); x3 = load("x3", "03_llm_extract_v1_2.py")
api, API, API_VERSION = x3.api, x3.API, x3.API_VERSION
SYSTEM = b9.SYSTEM + "\nIf EVIDENCE is provided, use it together with what you know. Evidence about one direction says nothing about the other direction unless it says so."
SCHEMA = b9.SCHEMA
STRONG = {"single_dose_perpetrator", "victim_specific_product", "perpetrator_specific_product", "specific_route", "staggered_administration"}
DIM = {"PK": "pharmacokinetics (exposure)", "PK+PD": "pharmacokinetics and pharmacodynamics", "PD": "pharmacodynamics (effect)"}


def record(x, cond, status):
    lines = [f"Documented non-interaction: {x['perpetrator']} does not change {x['victim']} to a clinically significant extent.",
             f"Dimension: {DIM.get(x.get('dimension'), 'not stated')}."]
    if cond:
        lines.append("Condition: valid only " + "; ".join(x.get("condition_quotes", [])[:2]) + ".")
    else:
        lines.append("Condition: none stated.")
    if status.startswith("N2"):
        lines.append(f"Also documented: {x['victim']} does not change {x['perpetrator']} to a clinically significant extent.")
    else:
        lines.append(f"Not documented: any effect of {x['victim']} on {x['perpetrator']}.")
    lines.append("Source sentence: " + x["evidence"][0]["sentence"][:700])
    return "\n".join(lines)


def cmd_prepare(a):
    d = Path(a.dir); d.mkdir(parents=True, exist_ok=True)
    st = {tuple(sorted((r["rxcui_a"], r["rxcui_b"]))): r["status"] for r in csv.DictReader(open(a.pairs, encoding="utf-8"))}
    items, n = [], 0
    def add(**kw):
        nonlocal n
        n += 1; kw["item_id"] = f"e{n:05d}"; items.append(kw)
    for l in open(a.condition, encoding="utf-8"):
        x = json.loads(l)
        if x["kind"] != "directional":
            continue
        k = tuple(sorted((x["perpetrator_rxcui"], x["victim_rxcui"])))
        cond = x.get("condition_llm") == "conditional" and bool(set(x.get("condition_types", [])) & STRONG)
        sent = x["evidence"][0]["sentence"][:700]
        rec = record(x, cond, st.get(k, ""))
        if st.get(k, "").startswith("N1"):
            for arm, ev in (("none", ""), ("sentence", sent), ("structured", rec)):
                add(set="REV", arm=arm, perp=x["victim"], vic=x["perpetrator"], evidence=ev, key=list(k))
        if cond:
            for arm, ev in (("sentence", sent), ("structured", rec)):
                add(set="COND", arm=arm, perp=x["perpetrator"], vic=x["victim"], evidence=ev, key=list(k))
        else:
            for arm, ev in (("sentence", sent), ("structured", rec)):
                add(set="DOC", arm=arm, perp=x["perpetrator"], vic=x["victim"], evidence=ev, key=list(k))
    with open(d / "items.jsonl", "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    meta = {"script_version": VERSION, "model": MODEL, "items": Counter(f"{i['set']}|{i['arm']}" for i in items),
            "prompt_sha256": hashlib.sha256((SYSTEM + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()}
    (d / "items_meta.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta))


def items_of(d):
    return [json.loads(l) for l in open(Path(d) / "items.jsonl", encoding="utf-8")]


def cmd_submit(a):
    d = Path(a.dir)
    for run in RUNS:
        rf = d / f"run_{run}.json"
        if rf.exists():
            print(f"{run}: already submitted, skipped"); continue
        reqs = []
        for it in items_of(d):
            msg = f"PERPETRATOR: {it['perp']}\nVICTIM: {it['vic']}"
            if it["evidence"]:
                msg += "\nEVIDENCE:\n" + it["evidence"]
            reqs.append({"custom_id": f"{it['item_id']}_{run}", "params": {"model": MODEL, "max_tokens": 600, "system": SYSTEM,
                         "messages": [{"role": "user", "content": msg}], "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}})
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
        if (d / f"answers_{run}.jsonl").exists() and rec.get("collected"):
            print(run, "already collected"); continue
        raw = None
        for k in range(6):                      # v1.1: the results download can break mid-stream (TLS errors); retry it
            try:
                raw = api("GET", b["results_url"]); break
            except Exception as e:
                print(f"{run}: download attempt {k + 1} failed: {type(e).__name__}; retrying", flush=True); time.sleep(10 * (k + 1))
        if raw is None:
            raise SystemExit(f"{run}: results download failed 6 times. Run collect again later.")
        (d / f"raw_{run}.jsonl").write_bytes(raw)
        st = Counter()
        with open(d / f"answers_{run}.jsonl", "w", encoding="utf-8") as f:
            for line in raw.decode("utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line); t = r["result"]["type"]; st[t] += 1
                row = {"item_id": r["custom_id"].rsplit("_", 1)[0], "result_type": t}
                if t == "succeeded":
                    txt = "".join(c.get("text", "") for c in r["result"]["message"]["content"] if c.get("type") == "text")
                    try:
                        row["answer"] = json.loads(txt)["answer"]
                    except (json.JSONDecodeError, KeyError):
                        st["parse_error"] += 1
                f.write(json.dumps(row) + "\n")
        rec["collected"] = dict(st); rec["raw_sha256"] = hashlib.sha256(raw).hexdigest()
        (d / f"run_{run}.json").write_text(json.dumps(rec, indent=1)); print(run, json.dumps(rec["collected"]))
    print("COLLECT COMPLETE")


def cmd_analyze(a):
    d = Path(a.dir); its = {i["item_id"]: i for i in items_of(d)}
    A = {}
    for run in RUNS:
        A[run] = {}
        for l in open(d / f"answers_{run}.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if "answer" in r:
                A[run][r["item_id"]] = r["answer"]
    c = defaultdict(Counter)
    for i, it in its.items():
        a1, a2 = A["s1"].get(i), A["s2"].get(i)
        s = a1 if a1 == a2 and a1 else "unstable"
        g = f"{it['set']}|{it['arm']}"; c[g]["n"] += 1; c[g][s] += 1
    rep = {g: dict(v, pct_no_interaction=round(100 * v["no_clinically_significant_interaction"] / v["n"], 1),
                   pct_interaction=round(100 * v["interaction"] / v["n"], 1),
                   pct_insufficient=round(100 * v["insufficient_evidence"] / v["n"], 1)) for g, v in sorted(c.items())}
    (d / "evidence_report.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("--condition", required=True); p.add_argument("--pairs", required=True); p.add_argument("--dir", required=True)
    for c in ("submit", "status", "collect", "analyze"):
        p = sp.add_parser(c); p.add_argument("--dir", required=True)
    a = ap.parse_args()
    {"prepare": cmd_prepare, "submit": cmd_submit, "status": cmd_status, "collect": cmd_collect, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
