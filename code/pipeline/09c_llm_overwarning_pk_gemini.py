"""NullDDI step 9c v1.0: second-vendor replication of the PK-only over-warning experiment (09b v2)
with a Google Gemini model. Same items (overwarn_pk/items.jsonl), same system prompt and answer
schema as 09b (imported, not copied). One pinned model, two runs (g_1, g_2).

Synchronous calls (no batch), 4 workers, resumable: answers are appended as they arrive and
finished items are skipped on restart, so the launcher can simply be run again after a quota
stop or a network drop. The API key is read from GEMINI_API_KEY only and is never written.

Model pinning: `run` lists the models the key can use, keeps stable names of the form
gemini-<major>.<minor>-<tier> (no preview/exp/lite/latest aliases) that support generateContent,
and takes the highest version of the requested tier (default flash). The choice and the full
model list are written to model.json; later restarts reuse model.json and never re-select.

Commands:
  run     --items data/interim/v1_2/overwarn_pk/items.jsonl --out data/interim/v1_2/overwarn_pk_gemini [--tier flash|pro] [--model NAME] [--limit N]
  analyze --out ... --pairs data/release/v0_1/nullddi_pairs.csv [--anthropic data/interim/v1_2/overwarn_pk]
"""
import argparse, csv, hashlib, importlib.util, json, os, re, threading, time, urllib.error, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VERSION = "1.0"
BASE = "https://generativelanguage.googleapis.com/v1beta"
RUNS = ["g_1", "g_2"]
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("b9", here / "09b_llm_overwarning_pk.py")
b9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b9)
SYSTEM = b9.SYSTEM
ANSWERS = b9.SCHEMA["properties"]["answer"]["enum"]; MECHS = b9.SCHEMA["properties"]["mechanism"]["enum"]
GSCHEMA = {"type": "OBJECT", "properties": {"answer": {"type": "STRING", "enum": ANSWERS},
                                            "mechanism": {"type": "STRING", "enum": MECHS}},
           "required": ["answer", "mechanism"]}


class Quota(Exception):
    pass


def http(method, url, body=None, tries=5):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit("GEMINI_API_KEY is not set")
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for k in range(tries):
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")[:1500]
            last = f"HTTP {e.code}: {txt}"
            if e.code in (400, 401, 403, 404):
                raise SystemExit(last)
            if e.code == 429 and re.search(r"per ?day|PerDay|daily", txt, re.I):
                raise Quota(last)
            time.sleep(min(60, 4 * 2 ** k))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = repr(e); time.sleep(min(60, 4 * 2 ** k))
    if last and "429" in last:
        raise Quota(last)
    raise RuntimeError(last)


def pick_model(out, tier, forced):
    mf = out / "model.json"
    if mf.exists():
        return json.loads(mf.read_text())["model"]
    models, tok = [], ""
    while True:
        r = http("GET", f"{BASE}/models?pageSize=200" + (f"&pageToken={tok}" if tok else ""))
        models += r.get("models", []); tok = r.get("nextPageToken", "")
        if not tok:
            break
    names = sorted(m["name"] for m in models if "generateContent" in m.get("supportedGenerationMethods", []))
    if forced:
        model = forced if forced.startswith("models/") else "models/" + forced
        if model not in names:
            raise SystemExit(f"{model} is not available to this key. Available: {names}")
    else:
        cand = []
        for n in names:
            m = re.fullmatch(rf"models/gemini-(\d+)(?:\.(\d+))?-{tier}", n)
            if m:
                cand.append(((int(m.group(1)), int(m.group(2) or 0)), n))
        if not cand:
            raise SystemExit(f"No stable gemini-*-{tier} model for this key. Available: {names}")
        model = max(cand)[1]
    info = next(m for m in models if m["name"] == model)
    mf.write_text(json.dumps({"model": model, "tier": tier, "selected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                              "version": info.get("version"), "displayName": info.get("displayName"),
                              "available_generateContent_models": names}, indent=1))
    return model


def ask(model, it):
    body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": f"PERPETRATOR: {it['perp_name']}\nVICTIM: {it['vic_name']}"}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseSchema": GSCHEMA, "maxOutputTokens": 4096}}
    r = http("POST", f"{BASE}/{model}:generateContent", body)
    row = {"item_id": it["item_id"], "model": model, "model_version": r.get("modelVersion")}
    try:
        c = r["candidates"][0]
        txt = "".join(p.get("text", "") for p in c.get("content", {}).get("parts", []) if not p.get("thought"))
        j = json.loads(txt)
        if j.get("answer") not in ANSWERS:
            raise ValueError("answer outside enum")
        row.update(answer=j["answer"], mechanism=j.get("mechanism", "unknown"))
    except Exception as e:
        fr = (r.get("candidates") or [{}])[0].get("finishReason") or r.get("promptFeedback", {}).get("blockReason")
        row.update(answer="NO_ANSWER", error=f"{type(e).__name__}: {fr}")
    return row


def cmd_run(a):
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    its = [json.loads(l) for l in open(a.items, encoding="utf-8")]
    if a.limit:
        its = its[:a.limit]
    model = pick_model(out, a.tier, a.model)
    meta = {"script_version": VERSION, "model": model, "items": len(its), "runs": RUNS,
            "items_sha256": hashlib.sha256(Path(a.items).read_bytes()).hexdigest(),
            "prompt_sha256": hashlib.sha256((SYSTEM + json.dumps(GSCHEMA, sort_keys=True)).encode()).hexdigest()}
    (out / "run_meta.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta))
    lock = threading.Lock(); stop = threading.Event()
    for run in RUNS:
        f = out / f"answers_{run}.jsonl"
        done = set()
        if f.exists():
            for l in open(f, encoding="utf-8"):
                r = json.loads(l)
                if r.get("answer") != "NO_ANSWER":
                    done.add(r["item_id"])
        todo = [it for it in its if it["item_id"] not in done]
        print(f"{run}: {len(done)} done, {len(todo)} to ask", flush=True)
        n = [0]

        def work(it):
            if stop.is_set():
                return
            try:
                row = ask(model, it)
            except Quota as e:
                stop.set(); print("\nQUOTA:", str(e)[:1500], flush=True); return
            except Exception as e:
                row = {"item_id": it["item_id"], "model": model, "answer": "NO_ANSWER", "error": repr(e)[:200]}
            with lock:
                with open(f, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row) + "\n")
                n[0] += 1
                if n[0] % 100 == 0:
                    print(f"  {run}: {n[0]}/{len(todo)}", flush=True)
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            list(ex.map(work, todo))
        if stop.is_set():
            raise SystemExit("Stopped on quota. Run the launcher again later (it resumes), or enable billing for the key.")
    print("RUN COMPLETE")


def load_answers(f):
    ans = {}
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        if r["item_id"] not in ans or r.get("answer") != "NO_ANSWER":
            ans[r["item_id"]] = r
    return ans


def cmd_analyze(a):
    out = Path(a.out)
    its = {}
    for l in open(a.items, encoding="utf-8"):
        d = json.loads(l); its[d["item_id"]] = d
    ans = {r: load_answers(out / f"answers_{r}.jsonl") for r in RUNS}
    miss = {r: sum(1 for i in its if ans[r].get(i, {}).get("answer", "NO_ANSWER") == "NO_ANSWER") for r in RUNS}
    rep = {"model": json.loads((out / "model.json").read_text())["model"], "items": len(its), "missing_or_no_answer": miss}
    g = lambda r, i: ans[r].get(i, {}).get("answer", "NO_ANSWER")
    for r in RUNS:
        c = defaultdict(Counter)
        for i, it in its.items():
            c[it["cls"]][g(r, i)] += 1
        tot = lambda k: max(1, sum(c[k].values()))
        rep[r] = {k: dict(v) for k, v in c.items()}
        rep[r].update(overwarning_rate_on_nulls=round(c["null"]["interaction"] / tot("null"), 4),
                      sensitivity_on_positives=round(c["positive"]["interaction"] / tot("positive"), 4),
                      null_recognised_rate=round(c["null"]["no_clinically_significant_interaction"] / tot("null"), 4),
                      direction_transfer_rate_on_positive_reverse=round(c["positive_reverse"]["interaction"] / tot("positive_reverse"), 4))
    rep["rerun_disagreement"] = round(sum(1 for i in its if g("g_1", i) != g("g_2", i)) / len(its), 4)
    stable = {i for i in its if g("g_1", i) == g("g_2", i) == "interaction"}
    st = {}
    for r in csv.DictReader(open(a.pairs, encoding="utf-8")):
        st[tuple(sorted((r["rxcui_a"], r["rxcui_b"])))] = r["status"]
    by = defaultdict(Counter)
    for i, it in its.items():
        if it["cls"] == "null":
            for grp in ("ALL", st.get(tuple(sorted((it["perp"], it["vic"]))), "?"), "dim_" + it["dimension"],
                        "grade_" + (it["numeric_grade"] or "none")):
                by[grp]["n"] += 1; by[grp]["stable_overwarning"] += i in stable
    rep["stable_overwarning_on_nulls"] = {k: dict(v, pct=round(100 * v["stable_overwarning"] / v["n"], 1)) for k, v in sorted(by.items())}
    rv = Counter(); rn = Counter()
    for i, it in its.items():
        if it["cls"] == "positive_reverse":
            rn[it["perp_name"]] += 1; rv[it["perp_name"]] += i in stable
    rep["stable_positive_reverse"] = {"n": sum(rn.values()), "stable": sum(rv.values()),
                                      "by_perpetrator": {k: [v, rn[k]] for k, v in rv.most_common() if v}}
    if a.anthropic:
        ad = Path(a.anthropic); X = {}
        for m in ("mA", "mB"):
            r1, r2 = load_answers(ad / f"answers_{m}_1.jsonl"), load_answers(ad / f"answers_{m}_2.jsonl")
            X[m] = {i for i in its if r1.get(i, {}).get("answer") == r2.get(i, {}).get("answer") == "interaction"}
        cv = {}
        for cls in ("null", "positive_reverse", "positive"):
            ids = {i for i, it in its.items() if it["cls"] == cls}
            G, A, B = stable & ids, X["mA"] & ids, X["mB"] & ids
            cv[cls] = {"n": len(ids), "gemini": len(G), "sonnet": len(A), "haiku": len(B), "gemini_and_sonnet": len(G & A),
                       "gemini_and_haiku": len(G & B), "all_three": len(G & A & B), "any": len(G | A | B)}
        rep["cross_vendor_stable_interaction"] = cv
        rep["nulls_warned_by_all_three"] = sorted(f"{its[i]['perp_name']} -> {its[i]['vic_name']}" for i in stable & X["mA"] & X["mB"]
                                                  if its[i]["cls"] == "null")
    (out / "overwarning_report_gemini.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("run")
    p.add_argument("--items", required=True); p.add_argument("--out", required=True)
    p.add_argument("--tier", default="flash", choices=["flash", "pro"]); p.add_argument("--model")
    p.add_argument("--limit", type=int, default=0); p.add_argument("--workers", type=int, default=4)
    p = sp.add_parser("analyze")
    p.add_argument("--items", required=True); p.add_argument("--out", required=True); p.add_argument("--pairs", required=True)
    p.add_argument("--anthropic")
    a = ap.parse_args()
    {"run": cmd_run, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
