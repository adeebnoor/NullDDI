"""NullDDI step 9b (v2): PK-only, direction-explicit version of the over-warning experiment.

Changes from 09 v1.0 (whose question covered "exposure or effect", so pharmacodynamic answers
were legitimate): the question is restricted to PHARMACOKINETICS (systemic exposure of the
victim), and a fourth item class measures DIRECTION TRANSFER directly:
  null              NullDDI directional nulls (label-measured)                       expect: no
  positive          FDA index pairs: strong inhibitor/inducer -> sensitive substrate  expect: yes
  positive_reverse  the same pairs asked in the opposite direction (substrate -> strong
                    perpetrator), kept only when the FDA tables profile both drugs and show
                    NO CYP/transporter path in that direction AND list the substrate with no
                    inhibitor/inducer role of any kind (a "pure substrate" in the FDA tables). Expected: not "interaction".
                    This is mechanism-absent, not label-measured, evidence.
Direction transfer = P(answer "interaction" on positive_reverse), read against the over-warning
rate on nulls and each model's re-run floor.

--- v1.0 header follows ---
NullDDI step 9: do LLM "interaction checkers" over-warn on label-documented nulls?
(RIDI design: two pinned models, each run twice; no training, no human review.)

Items (directional question: does PERPETRATOR change the exposure/effect of VICTIM to a
clinically significant extent?):
  null      every directional null of NullDDI v0.1 (label-verified measured null)
  positive  open positive controls from the FDA CYP/transporter tables: strong inhibitor or
            strong inducer -> sensitive substrate of the same enzyme (clinical index drugs),
            excluding any direction present in NullDDI
The model is asked WITHOUT any label text and must choose one of:
  interaction / no_clinically_significant_interaction / insufficient_evidence
Outcomes: over-warning rate on nulls (answer = interaction), sensitivity on positives,
abstention rate, and, with ridi-check, stable per-item differences between the two models
against each model's own re-run floor.

Commands (API key from ANTHROPIC_API_KEY or hidden prompt; never stored):
  prepare --nulls data/release/v0_1/nullddi_nulls_directional.csv --fda-tables data/raw/fda_ddi_tables
          --rxnorm data/raw/rxnorm --out data/interim/v1_2/overwarn
  submit  --dir ... [--dry-run]      (4 batches: mA_1, mA_2, mB_1, mB_2)
  collect --dir ...
  analyze --dir ...
"""
import argparse, csv, hashlib, importlib.util, json, time
from collections import Counter
from pathlib import Path

VERSION = "2.0"
MODELS = {"mA": "claude-sonnet-5-5", "mB": "claude-haiku-5-5"}
RUNS = ["mA_1", "mA_2", "mB_1", "mB_2"]
here = Path(__file__).resolve().parent


def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, here / fn)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


SYSTEM = """You are a drug-interaction checker. Answer about PHARMACOKINETICS and ONE direction only: whether co-administration of the PERPETRATOR drug changes the systemic exposure (plasma concentrations, AUC or Cmax) of the VICTIM drug to a clinically significant extent. Ignore pharmacodynamic interactions (additive or opposing effects, shared toxicities). Do not consider the opposite direction, that is, any effect of the victim on the perpetrator. Choose exactly one answer:
- interaction: a clinically significant change in the victim's exposure caused by the perpetrator is expected or documented.
- no_clinically_significant_interaction: evidence indicates no clinically significant change in the victim's exposure.
- insufficient_evidence: you do not know of evidence either way."""
SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"answer": {"type": "string", "enum": ["interaction", "no_clinically_significant_interaction",
                                                               "insufficient_evidence"]},
                         "mechanism": {"type": "string", "enum": ["enzyme_inhibition", "enzyme_induction", "transporter",
                                                                  "absorption", "other_pk", "none", "unknown"]}},
          "required": ["answer", "mechanism"]}


def cmd_prepare(a):
    tb = load("tb", "05_tier_b_fda_tables.py")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    ex, lex, _ = tb.load_lexicon(a.rxnorm)
    roles, *_ = tb.build_roles(a.fda_tables, ex, lex)
    names = {v["rxcui"]: n for n, v in lex.info.items() if v["tty"] == "IN"}
    items, nulls = [], set()
    with open(a.nulls, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nulls.add((r["perpetrator_rxcui"], r["victim_rxcui"]))
            items.append({"cls": "null", "perp": r["perpetrator_rxcui"], "vic": r["victim_rxcui"],
                          "perp_name": r["perpetrator"], "vic_name": r["victim"], "dimension": r["dimension"],
                          "numeric_grade": r["numeric_grade"], "reverse_fda": r["reverse_fda"]})
    pos = []
    for p, rp in roles.items():
        if p.startswith("NAME:"):
            continue
        strong = {(role, t) for role, st, t, _ in rp if role in ("inhibitor", "inducer") and st == "strong"}
        for v, rv in roles.items():
            if v == p or v.startswith("NAME:") or (p, v) in nulls or (v, p) in nulls:
                continue
            sens = {t for role, st, t, _ in rv if role == "substrate" and st == "sensitive"}
            hit = sorted((role, t) for role, t in strong if t in sens)
            if hit:
                pos.append({"cls": "positive", "perp": p, "vic": v, "perp_name": names.get(p, p),
                            "vic_name": names.get(v, v), "basis": f"strong {hit[0][0]} of CYP{hit[0][1]} -> sensitive substrate"})
    pos.sort(key=lambda x: hashlib.sha1((x["perp"] + ">" + x["vic"]).encode()).hexdigest())  # fixed pseudo-random order
    pos = pos[:len(items)]
    posset = {(x["perp"], x["vic"]) for x in pos}
    rev = [{"cls": "positive_reverse", "perp": x["vic"], "vic": x["perp"], "perp_name": x["vic_name"],
            "vic_name": x["perp_name"], "basis": "reverse of: " + x["basis"]} for x in pos
           if not tb.paths(roles[x["vic"]], roles[x["perp"]]) and (x["vic"], x["perp"]) not in posset
           and not any(role in ("inhibitor", "inducer") for role, *_ in roles[x["vic"]])   # pure substrate: no perpetrator role at all
           and (x["vic"], x["perp"]) not in nulls]
    items += pos + rev
    items.sort(key=lambda x: hashlib.sha1((x["perp"] + ">" + x["vic"]).encode()).hexdigest())
    with open(out / "items.jsonl", "w", encoding="utf-8") as f:
        for i, it in enumerate(items, 1):
            it["item_id"] = f"q{i:05d}"; f.write(json.dumps(it) + "\n")
    meta = {"script_version": VERSION, "items": len(items), "nulls": len(items) - len(pos) - len(rev), "positives": len(pos), "positive_reverse": len(rev),
            "models": MODELS, "prompt_sha256": hashlib.sha256((SYSTEM + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest()}
    (out / "items_meta.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta))


def items_of(d):
    with open(Path(d) / "items.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def cmd_submit(a):
    B = load("b", "03_llm_extract_v1_2.py"); d = Path(a.dir); its = items_of(d)
    for run in RUNS:
        runf = d / f"run_{run}.json"
        if runf.exists() and not a.dry_run:
            print(run, "already submitted"); continue
        model = MODELS[run[:2]]
        reqs = [{"custom_id": f"{it['item_id']}_{run}",
                 "params": {"model": model, "max_tokens": 1024, "system": SYSTEM,
                            "messages": [{"role": "user", "content": f"PERPETRATOR: {it['perp_name']}\nVICTIM: {it['vic_name']}"}],
                            "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}} for it in its]
        if a.dry_run:
            print(f"dry-run {run}: {len(reqs)} requests, model {model}. Nothing sent."); continue
        resp = json.loads(B.api("POST", B.API, {"requests": reqs}))
        rec = {"run": run, "model": model, "batch_id": resp["id"], "n_requests": len(reqs),
               "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        runf.write_text(json.dumps(rec, indent=1)); print(json.dumps(rec))


def cmd_collect(a):
    B = load("b", "03_llm_extract_v1_2.py"); d = Path(a.dir)
    for run in RUNS:
        rec = json.loads((d / f"run_{run}.json").read_text())
        b = json.loads(B.api("GET", f"{B.API}/{rec['batch_id']}"))
        print(run, b["processing_status"], b["request_counts"])
        if b["processing_status"] != "ended":
            raise SystemExit("not finished yet")
        raw = B.api("GET", b["results_url"]); (d / f"raw_{run}.jsonl").write_bytes(raw)
        with open(d / f"answers_{run}.jsonl", "w", encoding="utf-8") as f:
            for line in raw.decode().splitlines():
                r = json.loads(line); row = {"item_id": r["custom_id"].split("_")[0]}
                if r["result"]["type"] == "succeeded":
                    m = r["result"]["message"]
                    try:
                        row.update(json.loads("".join(c.get("text", "") for c in m["content"] if c.get("type") == "text")))
                        row["model"] = m.get("model")
                    except json.JSONDecodeError:
                        row["answer"] = "NO_ANSWER"
                else:
                    row["answer"] = "NO_ANSWER"
                f.write(json.dumps(row) + "\n")


def cmd_analyze(a):
    d = Path(a.dir); its = {i["item_id"]: i for i in items_of(d)}
    ans = {}
    for run in RUNS:
        with open(d / f"answers_{run}.jsonl") as f:
            ans[run] = {r["item_id"]: r for r in map(json.loads, f)}
    rep = {}
    for run in RUNS:
        c = {"null": Counter(), "positive": Counter(), "positive_reverse": Counter()}
        for i, it in its.items():
            c[it["cls"]][ans[run][i]["answer"]] += 1
        rep[run] = {k: dict(v) for k, v in c.items()}
        n, p = sum(c["null"].values()), sum(c["positive"].values())
        rep[run]["overwarning_rate_on_nulls"] = round(c["null"]["interaction"] / n, 4)
        rep[run]["sensitivity_on_positives"] = round(c["positive"]["interaction"] / p, 4)
        rep[run]["null_recognised_rate"] = round(c["null"]["no_clinically_significant_interaction"] / n, 4)
        r = sum(c["positive_reverse"].values())
        rep[run]["direction_transfer_rate_on_positive_reverse"] = round(c["positive_reverse"]["interaction"] / max(1, r), 4)
    for m in ("mA", "mB"):
        rep[m + "_rerun_disagreement"] = round(sum(ans[m + "_1"][i]["answer"] != ans[m + "_2"][i]["answer"] for i in its) / len(its), 4)
        st = Counter()
        for i, it in its.items():
            if it["cls"] != "positive" and ans[m + "_1"][i]["answer"] == ans[m + "_2"][i]["answer"] == "interaction":
                st["stable_" + it["cls"]] += 1; st[it["cls"] + "_mech_" + ans[m + "_1"][i].get("mechanism", "?")] += 1
        st["n_null"] = sum(1 for it in its.values() if it["cls"] == "null")
        st["n_positive_reverse"] = sum(1 for it in its.values() if it["cls"] == "positive_reverse")
        rep[m + "_stable_overwarning_on_nulls"] = dict(st)
    with open(d / "ridi_results.csv", "w", newline="", encoding="utf-8") as f:   # ridi-check contract, key mode
        w = csv.writer(f); w.writerow(["case_id", "question", "expected_answer", "baseline_answer", "baseline_repeat_answer",
                                       "updated_answer", "updated_repeat_answer"])
        for i, it in sorted(its.items()):
            exp = "interaction" if it["cls"] == "positive" else "no_clinically_significant_interaction"   # positive_reverse: mechanism-absent expectation
            w.writerow([i, f"{it['perp_name']} -> {it['vic_name']}", exp] + [ans[r][i]["answer"] for r in RUNS])
    (d / "overwarning_report.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare")
    for k in ("nulls", "fda-tables", "rxnorm", "out"):
        p.add_argument("--" + k, required=True)
    for n in ("submit", "collect", "analyze"):
        p = sp.add_parser(n); p.add_argument("--dir", required=True)
        if n == "submit":
            p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    {"prepare": cmd_prepare, "submit": cmd_submit, "collect": cmd_collect, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
