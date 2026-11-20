"""NullDDI step 3, v1.2: extractor B (LLM), independent of extractor A's rules.

v1.2 (18 Nov 2026), after the 2 x 100 pilot (kappa accept 0.974, finding 0.879, direction 0.891):
  * max_tokens 600 -> 2048: the model thinks before answering; 11/200 pilot answers were cut
    at 600 tokens (parse errors), all on long/table units.
  * RIDI execution floor: four runs, r1 and r1b (label drug first) and r2 and r2b (partner
    first). With repeats present, a unit is accepted only if ALL runs pass and agree on direction;
    a version that disagrees with itself is 'unstable' and not evidence.
  * Direction combination: equal directions agree; 'unspecified' defers to the other source;
    'both' vs one direction keeps the narrower (single) direction; two different single
    directions reject. If every source is unspecified the null is kept as 'undirected'
    ("no PK interaction was observed when X was co-administered with Y").
  * export-ridi writes results.csv in the ridi-check contract (nokey mode) for the
    RIDI report and gate.

v1.1 (18 Nov 2026): input = extractor A v1.2. Schema adds parameters_assessed and
partner_in_label_regimen; acceptance also requires that the null is not limited to
T1/2/Tmax, that the partner is not part of the label drug's own regimen, and that the
direction (which drug's PK/effect was measured) agrees between r1, r2 and, when A
resolved it, A's rule. The accepted unit is DIRECTIONAL (perpetrator -> victim).

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
import argparse, getpass, hashlib, json, os, re, sys, time, urllib.request, urllib.error
from collections import Counter
from pathlib import Path

VERSION = "1.2"
API = "https://api.anthropic.com/v1/messages/batches"
API_VERSION = "2026-10-21"
DEFAULT_MODEL = "claude-sonnet-5-5"
RUNS = ["r1", "r1b", "r2", "r2b"]
FLAGS = ["long_sentence", "population_pk", "table_like", "endogenous_context", "positive_cue",
         "partial_parameter", "regimen_partner"]

SYSTEM = """You are extractor B in a reproducible pharmacology data pipeline. You read ONE sentence taken verbatim from a US FDA drug label and judge it strictly from its own wording. Do not use outside knowledge about these drugs; if the sentence does not say it, it is not there.

Definitions:
- "Co-administration observed": the sentence reports that both named drugs were actually given together to humans (a clinical pharmacokinetic or pharmacodynamic study, or clinical co-use data) and an outcome was measured.
- "No clinically significant interaction": the sentence states that giving the two drugs together produced no clinically significant / relevant / meaningful change (in pharmacokinetics, exposure, or the reported pharmacodynamic effect) for the drugs it names.
- The two drugs of interest are the ones named in the request. A metabolite, an endogenous substance or a laboratory analyte is not a co-administered drug.
- Direction: the drug whose pharmacokinetics or effect was MEASURED is the one affected. "A did not alter the pharmacokinetics of B" means A was tested as the affecting drug and B as the affected drug; it says nothing about the effect of B on A.
- If the PARTNER DRUG is given as part of the label drug's own regimen (for example "darunavir/ritonavir" or "boosted with ritonavir") and the statement is about a third drug, the pair is not the subject.
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
        "parameters_assessed": {"type": "string",
            "enum": ["exposure_auc_or_cmax", "pk_unspecified", "half_life_or_tmax_only", "pd_effect_only",
                     "pk_and_pd", "not_stated"]},
        "partner_in_label_regimen": {"type": "boolean"},
        "direction": {"type": "string",
            "enum": ["partner_affects_label_drug", "label_drug_affects_partner", "both", "unspecified"]},
        "quote": {"type": "string"},
    },
    "required": ["pair_is_the_subject", "partner_role", "coadministration_observed", "evidence_basis",
                 "finding", "parameters_assessed", "partner_in_label_regimen", "direction", "quote"],
}
ACCEPT_BASIS = {"clinical_pk", "clinical_pd", "clinical_pk_and_pd", "not_stated"}


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
                                "flags": fl, "direction_rule": r.get("direction_rule", "unspecified"),
                                "n_records": 0, "set_ids": set(), "sections": set()}
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
    (out / "prompt_extractor_B_v1_1.txt").write_text(SYSTEM + "\n\nSCHEMA:\n" + json.dumps(SCHEMA, indent=1),
                                                   encoding="utf-8")
    (out / "units_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))


def load_units(d):
    with open(Path(d) / "units.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f]


# ---------------------------------------------------------------- API helpers
_KEY = None


def api_key():
    """ANTHROPIC_API_KEY from the environment, else a hidden prompt. Never stored or logged."""
    global _KEY
    if _KEY is None:
        _KEY = os.environ.get("ANTHROPIC_API_KEY") or getpass.getpass("Paste Anthropic API key (hidden input): ").strip()
        if not _KEY:
            raise SystemExit("No API key given.")
    return _KEY


def api(method, url, body=None):
    key = api_key()
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json", "x-api-key": key,
                                          "anthropic-version": API_VERSION})
    for attempt in range(1, 5):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:2000]}")
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            # network drop before any HTTP response (e.g. WinError 10053): safe to retry
            print(f"network error (attempt {attempt}/4): {e}; retrying in {15 * attempt}s")
            if attempt == 4:
                raise SystemExit("Network kept dropping. Check the internet connection / VPN / antivirus and run again.")
            time.sleep(15 * attempt)


def build_request(u, run, model):
    return {"custom_id": f"{u['unit_id']}_{run}",
            "params": {"model": model, "max_tokens": 2048,
                       "system": SYSTEM,
                       "messages": [{"role": "user", "content": user_message(u, "r1" if run.startswith("r1") else "r2")}],
                       "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}}


def cmd_submit(a):
    d = Path(a.dir); units = load_units(d)
    tag = a.run
    if getattr(a, "core_only", False):
        units = [u for u in units if not u["flags"]]
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


def cmd_pilot(a):
    for run in ("r1", "r2"):
        ns = argparse.Namespace(dir=a.dir, run=run, model=a.model, dry_run=False, force=False, pilot=a.n)
        cmd_submit(ns)
    print("Both pilot batches submitted. Check with: status --run r1_pilot / r2_pilot")


def cmd_full(a):
    """plan all4: four runs on every unit. plan core4: r1 on every unit (flag validation),
    r1b/r2/r2b on CORE units only (the units that can enter the dataset)."""
    for run in RUNS:
        if (Path(a.dir) / f"run_{run}.json").exists() and not a.dry_run:
            print(f"{run}: already submitted, skipped"); continue
        core_only = a.plan == "core4" and run != "r1"
        cmd_submit(argparse.Namespace(dir=a.dir, run=run, model=a.model, dry_run=a.dry_run, force=False,
                                      pilot=0, core_only=core_only))


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
    q = norm(ans.get("quote", ""))
    checks = [("pair_not_subject", ans["pair_is_the_subject"]),
              ("partner_not_coadministered", ans["partner_role"] == "coadministered_drug"),
              ("no_observed_coadministration", ans["coadministration_observed"]),
              ("basis_not_clinical", ans["evidence_basis"] in ACCEPT_BASIS),
              ("finding_not_null", ans["finding"] == "no_clinically_significant_interaction"),
              ("partial_parameters_only", ans["parameters_assessed"] != "half_life_or_tmax_only"),
              ("partner_in_label_regimen", not ans["partner_in_label_regimen"]),
              ("quote_not_verbatim", bool(q) and q in norm(sentence))]
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


def combine_direction(ds):
    """ds: directions from the sources (B runs and A rule). Returns direction or None (conflict)."""
    single = {d for d in ds if d in ("label_drug_affects_partner", "partner_affects_label_drug")}
    if len(single) > 1:
        return None
    if single:
        return single.pop()
    if "both" in ds:
        return "both"
    return "undirected"


def load_answers(d, runs):
    out = {}
    for run in runs:
        fp = Path(d) / f"answers_{run}.jsonl"
        if fp.exists():
            with open(fp, encoding="utf-8") as f:
                out[run] = {r["unit_id"]: r.get("answer") for r in map(json.loads, f)}
    return out


def cmd_agree(a):
    d = Path(a.dir); units = {u["unit_id"]: u for u in load_units(d)}
    sfx = "_pilot" if a.pilot else ""
    ans = load_answers(d, [r + sfx for r in RUNS])
    runs = list(ans)
    if not {"r1" + sfx, "r2" + sfx} <= set(runs):
        raise SystemExit("need at least r1 and r2 answers")
    repeats = [r for r in runs if r.rstrip("_pilot").endswith("b")]
    stats, by_group, reasons = Counter(), {}, Counter()
    fpairs, apairs, dpairs, floor = [], [], [], []
    r1_by_group = {}
    for uid, u in units.items():
        if uid in ans["r1" + sfx]:
            grp = "core" if not u["flags"] else "flagged"
            for g_name in [grp] + ["flag:" + f for f in u["flags"]]:
                g = r1_by_group.setdefault(g_name, Counter()); g["units"] += 1
                g["r1_pass"] += accepts(ans["r1" + sfx][uid], u["sentence"])[0]
    with open(d / f"accepted_units{sfx}.jsonl", "w", encoding="utf-8") as out:
        for uid, u in units.items():
            if any(uid not in ans[r] for r in runs):
                continue
            A = {r: ans[r][uid] for r in runs}
            res = {r: accepts(A[r], u["sentence"]) for r in runs}
            r1, r2 = A["r1" + sfx], A["r2" + sfx]
            if r1 and r2:
                fpairs.append((r1["finding"], r2["finding"])); apairs.append((res["r1" + sfx][0], res["r2" + sfx][0]))
                dpairs.append((r1["direction"], r2["direction"]))
            for rb in repeats:
                base = rb[:2] + sfx
                if A[rb] and A[base]:
                    floor.append((res[base][0], res[rb][0]))
            stats["units"] += 1
            ok_all = all(v[0] for v in res.values())
            grp = "core" if not u["flags"] else "flagged"
            for g_name in [grp] + ["flag:" + f for f in u["flags"]]:
                g = by_group.setdefault(g_name, Counter()); g["units"] += 1; g["passed_all_runs"] += ok_all
            if repeats and any(res[rb][0] != res[rb[:2] + sfx][0] for rb in repeats):
                stats["unstable_on_rerun"] += 1; reasons["unstable_on_rerun"] += 1
                continue
            if not ok_all:
                reasons[next(v[1] for v in res.values() if not v[0])] += 1
                continue
            stats["passed_content_all_runs"] += 1
            b_dirs = {A[r]["direction"] for r in runs}
            if len(b_dirs) > 1:
                stats["direction_B_runs_disagree"] += 1; reasons["direction_B_runs_disagree"] += 1
                continue
            dA = u.get("direction_rule", "unspecified")
            direction = combine_direction(b_dirs | {dA})
            if direction is None:
                stats["direction_A_B_conflict"] += 1; reasons["direction_A_B_conflict"] += 1
                continue
            stats["accepted"] += 1; stats["accepted_" + direction] += 1
            out.write(json.dumps({**{k: u[k] for k in ("unit_id", "sentence", "sentence_sha1", "label_in_rxcuis",
                                  "label_names", "partner_in_rxcui", "partner_name", "flags", "n_set_ids",
                                  "sections")},
                                  "direction": direction, "direction_rule_A": dA,
                                  "direction_B": sorted(b_dirs),
                                  "evidence_basis": sorted({A[r]["evidence_basis"] for r in runs}),
                                  "parameters_assessed": sorted({A[r]["parameters_assessed"] for r in runs}),
                                  "quotes": {r: A[r]["quote"] for r in runs}}, ensure_ascii=False) + "\n")
    rep = {"script_version": VERSION, "runs": runs, "stats": dict(stats),
           "kappa_finding_r1_r2": kappa(fpairs), "kappa_accept_r1_r2": kappa(apairs),
           "kappa_direction_r1_r2": kappa(dpairs),
           "execution_floor_accept_agreement": (round(sum(x == y for x, y in floor) / len(floor), 4) if floor else None),
           "pass_rate_by_group": {k: {**v, "rate": round(v["passed_all_runs"] / v["units"], 4)} for k, v in by_group.items()},
           "first_rejection_reason": dict(reasons.most_common()),
           "flag_validation_r1": {k: {**v, "rate": round(v["r1_pass"] / v["units"], 4)} for k, v in r1_by_group.items()}}
    (d / f"agreement_report{sfx}.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


def canon(ans, sentence):
    if not ans:
        return "NO_ANSWER"
    ok, why = accepts(ans, sentence)
    return f"ACCEPT:{ans['direction']}" if ok else f"REJECT:{why}"


def cmd_export_ridi(a):
    """results.csv in the ridi-check contract: baseline = label-first runs, updated = partner-first."""
    import csv
    d = Path(a.dir); sfx = "_pilot" if a.pilot else ""
    ans = load_answers(d, [r + sfx for r in RUNS])
    cols = [("baseline_answer", "r1"), ("baseline_repeat_answer", "r1b"),
            ("updated_answer", "r2"), ("updated_repeat_answer", "r2b")]
    cols = [(c, r + sfx) for c, r in cols if r + sfx in ans]
    n = 0
    with open(d / f"ridi_results{sfx}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(["case_id", "question"] + [c for c, _ in cols] + ["run_errors"])
        for u in load_units(d):
            if any(u["unit_id"] not in ans[r] for _, r in cols):
                continue
            q = f"{' + '.join(u['label_names'])} vs {u['partner_name']}: {u['sentence'][:300]}"
            vals = [canon(ans[r][u["unit_id"]], u["sentence"]) for _, r in cols]
            errs = "; ".join(f"{r}: no parseable answer" for (_, r), v in zip(cols, vals) if v == "NO_ANSWER")
            w.writerow([u["unit_id"], q] + vals + [errs]); n += 1
    print(f"wrote {d / f'ridi_results{sfx}.csv'} ({n} cases, runs: {[r for _, r in cols]})")


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("prepare"); p.add_argument("--candidates", required=True); p.add_argument("--rxnorm", required=True)
    p.add_argument("--out", required=True)
    for name in ("submit", "status", "collect"):
        p = sp.add_parser(name); p.add_argument("--dir", required=True); p.add_argument("--run", choices=RUNS + [r + "_pilot" for r in RUNS], required=True)
        if name == "submit":
            p.add_argument("--model", default=DEFAULT_MODEL); p.add_argument("--dry-run", action="store_true")
            p.add_argument("--force", action="store_true")
            p.add_argument("--pilot", type=int, default=0, help="send only N evenly spaced units (tag *_pilot)")
            p.add_argument("--core-only", action="store_true", help="send only CORE (unflagged) units")
    p = sp.add_parser("pilot"); p.add_argument("--dir", required=True); p.add_argument("--n", type=int, default=100)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p = sp.add_parser("full"); p.add_argument("--dir", required=True); p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--plan", choices=["all4", "core4"], default="core4")
    p.add_argument("--dry-run", action="store_true")
    p = sp.add_parser("export-ridi"); p.add_argument("--dir", required=True); p.add_argument("--pilot", action="store_true")
    p = sp.add_parser("agree"); p.add_argument("--dir", required=True); p.add_argument("--pilot", action="store_true")
    a = ap.parse_args()
    {"prepare": cmd_prepare, "submit": cmd_submit, "pilot": cmd_pilot, "full": cmd_full,
     "export-ridi": cmd_export_ridi, "status": cmd_status,
     "collect": cmd_collect, "agree": cmd_agree}[a.cmd](a)


if __name__ == "__main__":
    main()
