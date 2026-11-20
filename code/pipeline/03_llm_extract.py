"""NullDDI step 3: extractor B (LLM), independent of extractor A's rules.

Each unit = (sentence, label ingredient(s), partner ingredient) from extractor A v1.1,
deduplicated across manufacturers. Extractor B reads the sentence with a fixed
prompt and returns a JSON object constrained by a schema (structured outputs).
Two runs are made with the same pinned model:
  r1: label drug presented first;  r2: partner presented first (order swap).
A unit is ACCEPTED only if extractor A found it AND both runs independently return
a measured null interaction between exactly these two drugs, with a verbatim quote.
No human review anywhere; run-to-run agreement is the execution floor.

Commands (run from the NullDDI folder; the API key is read from ANTHROPIC_API_KEY
and is never written to disk or logs):
  python pipeline/03_llm_extract.py prepare --candidates data/interim/v1_1/candidates.jsonl \
         --rxnorm data/raw/rxnorm --out data/interim/v1_1/llm
  python pipeline/03_llm_extract.py submit  --dir data/interim/v1_1/llm --run r1 --pilot 100   (pilot first)
  python pipeline/03_llm_extract.py submit  --dir data/interim/v1_1/llm --run r1 [--dry-run]
  python pipeline/03_llm_extract.py submit  --dir data/interim/v1_1/llm --run r2
  python pipeline/03_llm_extract.py status  --dir data/interim/v1_1/llm --run r1
  python pipeline/03_llm_extract.py collect --dir data/interim/v1_1/llm --run r1
  python pipeline/03_llm_extract.py agree   --dir data/interim/v1_1/llm
"""
import argparse, hashlib, json, os, re, sys, time, urllib.request, urllib.error
from collections import Counter
from pathlib import Path

VERSION = "1.0"
API = "https://api.anthropic.com/v1/messages/batches"
API_VERSION = "2026-10-21"
DEFAULT_MODEL = "claude-sonnet-5-5"
FLAGS = ["long_sentence", "population_pk", "table_like", "endogenous_context", "positive_cue"]

SYSTEM = """You are extractor B in a reproducible pharmacology data pipeline. You read ONE sentence taken verbatim from a US FDA drug label and judge it strictly from its own wording. Do not use outside knowledge about these drugs; if the sentence does not say it, it is not there.

Definitions:
- "Co-administration observed": the sentence reports that both named drugs were actually given together to humans (a clinical pharmacokinetic or pharmacodynamic study, or clinical co-use data) and an outcome was measured.
- "No clinically significant interaction": the sentence states that giving the two drugs together produced no clinically significant / relevant / meaningful change (in pharmacokinetics, exposure, or the reported pharmacodynamic effect) for the drugs it names.
- The two drugs of interest are the ones named in the request. A metabolite, an endogenous substance or a laboratory analyte is not a co-administered drug.
Answer every field. The quote must be copied character-for-character from the sentence and must be the shortest span that supports your finding."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "pair_is_the_subject": {"type": "boolean",
            "description": "True if the statement is about these two drugs (or the label drug's active moiety) being given together; false if it concerns other drugs."},
        "partner_role": {"type": "string",
            "enum": ["coadministered_drug", "metabolite", "endogenous_or_analyte", "other_or_absent"]},
        "coadministration_observed": {"type": "boolean"},
        "evidence_basis": {"type": "string",
            "enum": ["clinical_pk", "clinical_pd", "clinical_pk_and_pd", "population_pk",
                     "in_vitro_or_model", "not_stated"]},
        "finding": {"type": "string",
            "enum": ["no_clinically_significant_interaction", "interaction_present", "mixed", "unclear"]},
        "direction": {"type": "string",
            "enum": ["partner_affects_label_drug", "label_drug_affects_partner", "both", "unspecified"]},
        "quote": {"type": "string"},
    },
    "required": ["pair_is_the_subject", "partner_role", "coadministration_observed", "evidence_basis",
                 "finding", "direction", "quote"],
}
ACCEPT_BASIS = {"clinical_pk", "clinical_pd", "clinical_pk_and_pd"}


def sha256_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def prompt_fingerprint():
    return sha256_text(SYSTEM + json.dumps(SCHEMA, sort_keys=True))


def user_message(u, run):
    lab = " + ".join(u["label_names"])
    a, b = (("LABEL DRUG", lab), ("PARTNER DRUG", u["partner_name"]))
    first, second = (a, b) if run == "r1" else (b, a)
    return (f"{first[0]}: {first[1]}\n{second[0]}: {second[1]}\n"
            f"(The sentence comes from the label of the LABEL DRUG.)\n\n"
            f"SENTENCE:\n<<<{u['sentence']}>>>\n\n"
            f"Judge whether this sentence reports a measured absence of a clinically significant "
            f"interaction between the LABEL DRUG and the PARTNER DRUG.")


# ---------------------------------------------------------------- prepare
def cmd_prepare(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    lexf = next(Path(a.rxnorm).glob("rxnorm_ingredients_*.json"))
    names = {c["rxcui"]: c["name"] for c in json.loads(lexf.read_text(encoding="utf-8"))["concepts"]
             if c["tty"] in ("IN", "PIN")}
    units = {}
    with open(a.candidates, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            k = (r["sentence_sha1"], tuple(r["label_in_rxcuis"]), r["partner_in_rxcui"])
            u = units.get(k)
            if u is None:
                fl = [x for x in FLAGS if r.get(x)] + ([] if r.get("own_mentioned", True) else ["own_not_mentioned"])
                u = units[k] = {"sentence": r["sentence"], "sentence_sha1": r["sentence_sha1"],
                                "label_in_rxcuis": list(k[1]),
                                "label_names": [names.get(x, x) for x in k[1]],
                                "partner_in_rxcui": k[2], "partner_name": names.get(k[2], r["partner"]),
                                "flags": fl, "n_records": 0, "set_ids": set(), "sections": set()}
            u["n_records"] += 1; u["set_ids"].add(r["set_id"]); u["sections"].add(r["section"])
    rows = sorted(units.values(), key=lambda u: (u["flags"] != [], u["sentence_sha1"], u["partner_in_rxcui"]))
    with open(out / "units.jsonl", "w", encoding="utf-8") as f:
        for i, u in enumerate(rows, 1):
            u["unit_id"] = f"u{i:06d}"
            u["n_set_ids"] = len(u.pop("set_ids")); u["sections"] = sorted(u["sections"])
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    meta = {"script_version": VERSION, "units": len(rows),
            "core_units": sum(not u["flags"] for u in rows),
            "flag_counts": dict(Counter(x for u in rows for x in u["flags"])),
            "prompt_sha256": prompt_fingerprint(),
            "candidates_sha256": hashlib.sha256(Path(a.candidates).read_bytes()).hexdigest()}
    (out / "prompt_extractor_B_v1.txt").write_text(SYSTEM + "\n\nSCHEMA:\n" + json.dumps(SCHEMA, indent=1),
                                                   encoding="utf-8")
    (out / "units_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))


def load_units(d):
    with open(Path(d) / "units.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f]


# ---------------------------------------------------------------- API helpers
def api(method, url, body=None):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("ANTHROPIC_API_KEY is not set in this terminal.")
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "x-api-key": key,
                                          "anthropic-version": API_VERSION})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:2000]}")


def build_request(u, run, model):
    return {"custom_id": f"{u['unit_id']}_{run}",
            "params": {"model": model, "max_tokens": 600,
                       "system": SYSTEM,
                       "messages": [{"role": "user", "content": user_message(u, run)}],
                       "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}}


def cmd_submit(a):
    d = Path(a.dir); units = load_units(d)
    tag = a.run
    if a.pilot:
        # fixed, reproducible pilot sample: every k-th unit across core and flagged units
        step = max(1, len(units) // a.pilot); units = units[::step][:a.pilot]; tag = f"{a.run}_pilot"
    reqs = [build_request(u, a.run.split("_")[0], a.model) for u in units]
    runf = d / f"run_{tag}.json"
    if a.dry_run:
        (d / f"dryrun_{tag}_first3.json").write_text(json.dumps(reqs[:3], indent=1, ensure_ascii=False))
        size = len(json.dumps({"requests": reqs}).encode())
        print(f"dry-run: {len(reqs)} requests, {size/1e6:.1f} MB; first 3 written. Nothing sent.")
        return
    if runf.exists() and not a.force:
        raise SystemExit(f"{runf} exists (batch already submitted). Use status/collect, or --force.")
    resp = json.loads(api("POST", API, {"requests": reqs}))
    rec = {"run": tag, "model": a.model, "batch_id": resp["id"], "n_requests": len(reqs),
           "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "prompt_sha256": prompt_fingerprint(), "api_version": API_VERSION, "script_version": VERSION}
    runf.write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec))


def cmd_status(a):
    rec = json.loads((Path(a.dir) / f"run_{a.run}.json").read_text())
    b = json.loads(api("GET", f"{API}/{rec['batch_id']}"))
    print(json.dumps({"status": b["processing_status"], "counts": b["request_counts"]}))


def cmd_collect(a):
    d = Path(a.dir); rec = json.loads((d / f"run_{a.run}.json").read_text())
    b = json.loads(api("GET", f"{API}/{rec['batch_id']}"))
    if b["processing_status"] != "ended":
        raise SystemExit(f"not ended yet: {b['processing_status']} {b['request_counts']}")
    raw = api("GET", b["results_url"])
    (d / f"raw_{a.run}.jsonl").write_bytes(raw)
    stats, out = Counter(), []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line); uid = r["custom_id"].rsplit("_", 1)[0]
        t = r["result"]["type"]; stats[t] += 1
        row = {"unit_id": uid, "result_type": t}
        if t == "succeeded":
            m = r["result"]["message"]
            txt = "".join(c.get("text", "") for c in m["content"] if c.get("type") == "text")
            try:
                row["answer"] = json.loads(txt)
            except json.JSONDecodeError:
                row["parse_error"] = True; stats["parse_error"] += 1
            row["model"] = m.get("model"); row["usage"] = m.get("usage"); row["stop_reason"] = m.get("stop_reason")
        else:
            row["error"] = r["result"].get("error")
        out.append(row)
    with open(d / f"answers_{a.run}.jsonl", "w", encoding="utf-8") as f:
        for row in sorted(out, key=lambda x: x["unit_id"]):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    retry = [r["unit_id"] for r in out if r["result_type"] != "succeeded" or r.get("parse_error")]
    (d / f"retry_{a.run}.txt").write_text("\n".join(retry))
    rec["collected"] = dict(stats); rec["raw_sha256"] = hashlib.sha256(raw).hexdigest()
    (d / f"run_{a.run}.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec["collected"]), f"retry={len(retry)}")


# ---------------------------------------------------------------- agreement
def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def accepts(ans, sentence):
    if not ans:
        return False, "no_answer"
    q = ans.get("quote", "")
    checks = [("pair_not_subject", ans["pair_is_the_subject"]),
              ("partner_not_coadministered", ans["partner_role"] == "coadministered_drug"),
              ("no_observed_coadministration", ans["coadministration_observed"]),
              ("basis_not_clinical", ans["evidence_basis"] in ACCEPT_BASIS),
              ("finding_not_null", ans["finding"] == "no_clinically_significant_interaction"),
              ("quote_not_verbatim", isinstance(q, str) and bool(q) and q in sentence)]
    for name, ok in checks:
        if not ok:
            return False, name
    return True, "accepted"


def kappa(pairs):
    n = len(pairs)
    if not n:
        return None
    po = sum(x == y for x, y in pairs) / n
    cx, cy = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum(cx[k] * cy[k] for k in set(cx) | set(cy)) / n / n
    return None if pe == 1 else round((po - pe) / (1 - pe), 4)


def cmd_agree(a):
    d = Path(a.dir); units = {u["unit_id"]: u for u in load_units(d)}
    sfx = "_pilot" if a.pilot else ""
    ans = {}
    for run in ("r1" + sfx, "r2" + sfx):
        with open(d / f"answers_{run}.jsonl", encoding="utf-8") as f:
            ans[run] = {r["unit_id"]: r.get("answer") for r in map(json.loads, f)}
    stats, by_group, reasons = Counter(), {}, Counter()
    fpairs, apairs = [], []
    with open(d / f"accepted_units{sfx}.jsonl", "w", encoding="utf-8") as out:
        for uid, u in units.items():
            if a.pilot and (uid not in ans["r1" + sfx] or uid not in ans["r2" + sfx]):
                continue
            a1, a2 = ans["r1" + sfx].get(uid), ans["r2" + sfx].get(uid)
            ok1, why1 = accepts(a1, u["sentence"]); ok2, why2 = accepts(a2, u["sentence"])
            if a1 and a2:
                fpairs.append((a1["finding"], a2["finding"])); apairs.append((ok1, ok2))
            acc = ok1 and ok2
            grp = "core" if not u["flags"] else "flagged"
            g = by_group.setdefault(grp, Counter()); g["units"] += 1; g["accepted"] += acc
            for fl in u["flags"]:
                gf = by_group.setdefault("flag:" + fl, Counter()); gf["units"] += 1; gf["accepted"] += acc
            stats["units"] += 1; stats["accepted"] += acc
            stats["r1_accept"] += ok1; stats["r2_accept"] += ok2; stats["run_disagree"] += ok1 != ok2
            if not acc:
                reasons[why1 if not ok1 else why2] += 1
                continue
            direction = a1["direction"] if a1["direction"] == a2["direction"] else "unspecified"
            out.write(json.dumps({**{k: u[k] for k in ("unit_id", "sentence", "sentence_sha1", "label_in_rxcuis",
                                  "label_names", "partner_in_rxcui", "partner_name", "flags", "n_set_ids",
                                  "sections")},
                                  "direction": direction, "evidence_basis": [a1["evidence_basis"], a2["evidence_basis"]],
                                  "quote_r1": a1["quote"], "quote_r2": a2["quote"]}, ensure_ascii=False) + "\n")
    rep = {"script_version": VERSION, "stats": dict(stats),
           "kappa_finding_r1_r2": kappa(fpairs), "kappa_accept_r1_r2": kappa(apairs),
           "accept_rate_by_group": {k: {**v, "rate": round(v["accepted"] / v["units"], 4)} for k, v in by_group.items()},
           "first_rejection_reason": dict(reasons.most_common())}
    (d / f"agreement_report{sfx}.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("--candidates", required=True); p.add_argument("--rxnorm", required=True)
    p.add_argument("--out", required=True)
    for name in ("submit", "status", "collect"):
        p = sp.add_parser(name); p.add_argument("--dir", required=True); p.add_argument("--run", choices=["r1", "r2", "r1_pilot", "r2_pilot"], required=True)
        if name == "submit":
            p.add_argument("--model", default=DEFAULT_MODEL); p.add_argument("--dry-run", action="store_true")
            p.add_argument("--force", action="store_true")
            p.add_argument("--pilot", type=int, default=0, help="send only N evenly spaced units (tag *_pilot)")
    p = sp.add_parser("agree"); p.add_argument("--dir", required=True); p.add_argument("--pilot", action="store_true")
    a = ap.parse_args()
    {"prepare": cmd_prepare, "submit": cmd_submit, "status": cmd_status,
     "collect": cmd_collect, "agree": cmd_agree}[a.cmd](a)


if __name__ == "__main__":
    main()
