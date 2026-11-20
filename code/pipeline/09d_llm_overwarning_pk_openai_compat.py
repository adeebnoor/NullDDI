"""NullDDI step 9d v1.0: second-vendor replication of the PK-only over-warning experiment (09b v2)
with an open-weight model served through an OpenAI-compatible chat-completions endpoint
(default: Runpod Public Endpoint, openai/gpt-oss-120b). Same items and same system prompt as 09b
(imported, not copied). Because structured output is not guaranteed on such endpoints, the answer
schema is stated as one extra instruction line appended to the system prompt (JSON_LINE) and the
reply is parsed; anything outside the allowed values is recorded as NO_ANSWER. One model, two
runs (g_1, g_2; run names kept identical to 09c so the analysis code is shared).

Synchronous, resumable; v1.1 adds --rpm (client-side per-minute ceiling) and waits out per-minute 429s instead of stopping. The key is read from LLM_API_KEY only and is never written.

Commands:
  run     --items .../overwarn_pk/items.jsonl --out .../overwarn_pk_gptoss [--base URL] [--model NAME] [--limit N]
  analyze --items ... --out ... --pairs data/release/v0_1/nullddi_pairs.csv [--anthropic .../overwarn_pk]
"""
import argparse, csv, hashlib, importlib.util, json, os, re, threading, time, urllib.error, urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VERSION = "1.2"
BASE = "https://api.runpod.ai/v2/gpt-oss-120b/openai/v1"
MODEL = "openai/gpt-oss-120b"
RUNS = ["g_1", "g_2"]
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("b9", here / "09b_llm_overwarning_pk.py")
b9 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b9)
SYSTEM = b9.SYSTEM
ANSWERS = b9.SCHEMA["properties"]["answer"]["enum"]; MECHS = b9.SCHEMA["properties"]["mechanism"]["enum"]
JSON_LINE = ("\nReply with one JSON object and nothing else: {\"answer\": one of " + json.dumps(ANSWERS) +
             ", \"mechanism\": one of " + json.dumps(MECHS) + "}.")
GSCHEMA = {"json_line": JSON_LINE}


class Quota(Exception):
    pass


RPM = [0.0]                      # requests per minute ceiling for this process (0 = none)
_slot = [0.0]; _slot_lock = threading.Lock()


def throttle():
    if RPM[0] <= 0:
        return
    with _slot_lock:
        now = time.time(); t = max(now, _slot[0]); _slot[0] = t + 60.0 / RPM[0]
    if t > now:
        time.sleep(t - now)


def http(method, url, body=None, tries=5, rate_tries=40):
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key:
        raise SystemExit("LLM_API_KEY is not set")
    data = json.dumps(body).encode() if body is not None else None
    last, k, rk = None, 0, 0
    while k < tries and rk < rate_tries:
        throttle()
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")[:1500]
            last = f"HTTP {e.code}: {txt}"
            if e.code in (400, 401, 402, 403, 404):
                raise SystemExit(last)
            if e.code == 429:
                if re.search(r"per ?day|PerDay|daily|credits", txt, re.I):
                    raise Quota(last)
                rk += 1; time.sleep(65); continue          # per-minute limit: wait it out, do not count as failure
            k += 1; time.sleep(min(60, 4 * 2 ** k))
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = repr(e); k += 1; time.sleep(min(60, 4 * 2 ** k))
    if last and "429" in last:
        raise Quota(last)
    raise RuntimeError(last)


def pick_model(out, base, model):
    mf = out / "model.json"
    if mf.exists():
        return json.loads(mf.read_text())
    rec = {"base": base, "model": model, "selected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    mf.write_text(json.dumps(rec, indent=1)); return rec


def parse(txt):
    txt = re.sub(r"<think>.*?</think>", "", txt or "", flags=re.S)
    for m in reversed(list(re.finditer(r"\{[^{}]*\}", txt))):
        try:
            j = json.loads(m.group(0))
        except Exception:
            continue
        if j.get("answer") in ANSWERS:
            return j
    raise ValueError("no valid JSON answer")


def ask(cfg, it):
    body = {"model": cfg["model"], "max_tokens": 4096,
            "messages": [{"role": "system", "content": SYSTEM + JSON_LINE},
                         {"role": "user", "content": f"PERPETRATOR: {it['perp_name']}\nVICTIM: {it['vic_name']}"}]}
    r = http("POST", cfg["base"].rstrip("/") + "/chat/completions", body)
    row = {"item_id": it["item_id"], "model": r.get("model") or cfg["model"]}
    try:
        j = parse(r["choices"][0]["message"].get("content"))
        row.update(answer=j["answer"], mechanism=j.get("mechanism") if j.get("mechanism") in MECHS else "unknown")
    except Exception as e:
        ch = (r.get("choices") or [{}])[0]
        row.update(answer="NO_ANSWER", error=f"{type(e).__name__}: {ch.get('finish_reason')}: {str((ch.get('message') or {}).get('content'))[:120]}")
    return row


def cmd_run(a):
    RPM[0] = a.rpm
    if os.name == "nt":                     # ask Windows not to sleep while this process runs (released on exit)
        try:
            import ctypes; ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        except Exception:
            pass
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    its = [json.loads(l) for l in open(a.items, encoding="utf-8")]
    if a.limit:
        its = its[:a.limit]
    cfg = pick_model(out, a.base, a.model); model = cfg["model"]
    meta = {"script_version": VERSION, "model": model, "base": cfg["base"], "items": len(its), "runs": RUNS,
            "items_sha256": hashlib.sha256(Path(a.items).read_bytes()).hexdigest(),
            "prompt_sha256": hashlib.sha256((SYSTEM + json.dumps(GSCHEMA, sort_keys=True)).encode()).hexdigest()}
    (out / "run_meta.json").write_text(json.dumps(meta, indent=1)); print(json.dumps(meta))
    lock = threading.Lock(); stop = threading.Event()
    for run in RUNS:
        f = out / f"answers_{run}.jsonl"
        done = set()
        if f.exists():
            for l in open(f, encoding="utf-8"):
                try:
                    r = json.loads(l)
                except ValueError:          # a line cut off by an abrupt stop (sleep, closed window): ignore, item is re-asked
                    continue
                if r.get("answer") != "NO_ANSWER":
                    done.add(r["item_id"])
        todo = [it for it in its if it["item_id"] not in done]
        print(f"{run}: {len(done)} done, {len(todo)} to ask", flush=True)
        n = [0]

        def work(it):
            if stop.is_set():
                return
            try:
                row = ask(cfg, it)
            except Quota as e:
                stop.set(); print("\nQUOTA:", str(e)[:300], flush=True); return
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
            raise SystemExit("Stopped on quota. Run the launcher again later (it resumes), or add credit to the account.")
    print("RUN COMPLETE")


def load_answers(f):
    ans = {}
    for l in open(f, encoding="utf-8"):
        try:
            r = json.loads(l)
        except ValueError:
            continue
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
            cv[cls] = {"n": len(ids), "second_vendor": len(G), "sonnet": len(A), "haiku": len(B), "second_vendor_and_sonnet": len(G & A),
                       "second_vendor_and_haiku": len(G & B), "all_three": len(G & A & B), "any": len(G | A | B)}
        rep["cross_vendor_stable_interaction"] = cv
        rep["nulls_warned_by_all_three"] = sorted(f"{its[i]['perp_name']} -> {its[i]['vic_name']}" for i in stable & X["mA"] & X["mB"]
                                                  if its[i]["cls"] == "null")
    (out / "overwarning_report_second_vendor.json").write_text(json.dumps(rep, indent=1)); print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("run")
    p.add_argument("--items", required=True); p.add_argument("--out", required=True)
    p.add_argument("--base", default=BASE); p.add_argument("--model", default=MODEL)
    p.add_argument("--limit", type=int, default=0); p.add_argument("--workers", type=int, default=4)
    p.add_argument("--rpm", type=float, default=0)
    p = sp.add_parser("analyze")
    p.add_argument("--items", required=True); p.add_argument("--out", required=True); p.add_argument("--pairs", required=True)
    p.add_argument("--anthropic")
    a = ap.parse_args()
    {"run": cmd_run, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
