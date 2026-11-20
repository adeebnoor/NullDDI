"""NullDDI step 21 (v1.0): build the public data release (CC BY 4.0) from the analysed files.

Inputs (all produced earlier in the pipeline, no third-party data):
  data/interim/v1_2/condition/nullddi_nulls_condition_llm.jsonl   statements + condition fields
  data/release/v0_1/nullddi_pairs.csv                              pair status (N2/N1/N0)
  data/interim/v1_2/llm/accepted_units.jsonl                       4,547 accepted sentence units
  --sensitivity  nullddi_nulls.jsonl from 04_build_dataset.py run with the 162 units whose only
                 direction evidence is symmetric "between X and Y" phrasing set to undirected
Output: <out>/ with statements (jsonl, csv), evidence sentences (csv), pairs (csv),
        accepted units (jsonl), stats.json and SHA-256 checksums.
No DDInter, D3, PK-DDI DB or NHANES record is written to the release.
"""
import argparse, csv, hashlib, json
from collections import Counter
from pathlib import Path

STRONG = {"single_dose_perpetrator", "victim_specific_product", "perpetrator_specific_product",
          "specific_route", "staggered_administration"}
VERSION = "1.0"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(".."))
    ap.add_argument("--sensitivity", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); R = a.root; a.out.mkdir(parents=True, exist_ok=True)

    sens = {(r["perpetrator_rxcui"], r["victim_rxcui"]) for r in map(json.loads, open(a.sensitivity, encoding="utf-8"))
            if r["kind"] == "directional"}
    rows = [json.loads(l) for l in open(R / "data/interim/v1_2/condition/nullddi_nulls_condition_llm.jsonl", encoding="utf-8")]
    st = Counter()
    with open(a.out / "nullddi_statements.jsonl", "w", encoding="utf-8") as fj, \
         open(a.out / "nullddi_statements.csv", "w", newline="", encoding="utf-8") as fc, \
         open(a.out / "nullddi_evidence_sentences.csv", "w", newline="", encoding="utf-8") as fe:
        wc = csv.writer(fc); we = csv.writer(fe)
        wc.writerow(["statement_id", "kind", "perpetrator", "perpetrator_rxcui", "victim", "victim_rxcui",
                     "dimension", "parameters", "numeric_grade", "numeric_gmr", "reverse_direction_fda",
                     "condition", "condition_types", "restriction_strong", "symmetric_phrasing_only",
                     "n_sentences", "n_labels"])
        we.writerow(["statement_id", "unit_id", "label_ingredient_rxcui", "set_id", "label_version",
                     "effective_time", "section", "quote", "sentence"])
        for i, r in enumerate(rows, 1):
            sid = f"NDDI-{i:05d}"
            strong = r["kind"] == "directional" and r.get("condition_llm", "not_assessed") == "conditional" and bool(STRONG & set(r.get("condition_types") or []))
            sym = r["kind"] == "directional" and (r["perpetrator_rxcui"], r["victim_rxcui"]) not in sens
            rec = {"statement_id": sid, "dataset_version": VERSION, **r,
                   "restriction_strong": strong, "symmetric_phrasing_only": sym}
            fj.write(json.dumps(rec, ensure_ascii=False) + "\n")
            wc.writerow([sid, r["kind"], r.get("perpetrator", ""), r.get("perpetrator_rxcui", ""), r.get("victim", ""),
                         r.get("victim_rxcui", ""), r["dimension"], ";".join(r.get("parameters") or []),
                         r.get("numeric_grade") or "", ";".join(map(str, r.get("numeric_gmr") or [])),
                         r.get("reverse_fda") or "", r.get("condition_llm", "not_assessed"), ";".join(r.get("condition_types") or []),
                         int(strong), int(sym), r["n_sentences"], r["n_labels"]])
            for e in r["evidence"]:
                for lb in e["labels"]:
                    we.writerow([sid, e["unit_id"], e["label_in"], lb["set_id"], lb["version"], lb["effective_time"],
                                 lb["section"], e.get("quote", ""), e["sentence"]])
            st["statements_" + r["kind"]] += 1
            if r["kind"] == "directional":
                st["condition_" + r.get("condition_llm", "not_assessed")] += 1; st["restriction_strong"] += strong
                st["symmetric_phrasing_only"] += sym; st["dimension_" + r["dimension"]] += 1

    pairs = list(csv.DictReader(open(R / "data/release/v0_1/nullddi_pairs.csv", encoding="utf-8")))
    with open(a.out / "nullddi_pairs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(pairs[0].keys())); w.writeheader(); w.writerows(pairs)
    for p in pairs:
        st["pairs_" + p["status"]] += 1
    st["pairs"] = len(pairs)

    with open(R / "data/interim/v1_2/llm/accepted_units.jsonl", encoding="utf-8") as fi, \
         open(a.out / "nullddi_accepted_units.jsonl", "w", encoding="utf-8") as fo:
        n = 0
        for l in fi:
            fo.write(l if l.endswith("\n") else l + "\n"); n += 1
    st["accepted_units"] = n

    (a.out / "stats.json").write_text(json.dumps({"dataset_version": VERSION, "stats": dict(sorted(st.items()))}, indent=1), encoding="utf-8")
    with open(a.out / "CHECKSUMS.sha256", "w", encoding="utf-8") as f:
        for p in sorted(a.out.iterdir()):
            if p.name != "CHECKSUMS.sha256" and p.is_file():
                f.write(f"{sha(p)}  {p.name}\n")
    print(json.dumps(dict(sorted(st.items())), indent=1))


if __name__ == "__main__":
    main()
