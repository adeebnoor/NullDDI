"""NullDDI step 7: numeric DDI tables from FDA labels -> objective validation key.

Many labels carry DDI tables ("Effect of Coadministered Drugs on the Pharmacokinetics of
X", "Effect of X on ... Other Drugs") with geometric mean ratios (GMR, with/without the
co-administered drug) for AUC and Cmax, often with 90% CIs. These numbers are an external
key for the narrative nulls of extractors A/B, needing no human judgement:
  no_effect_strict  every reported AUC/Cmax 90% CI lies within 0.80-1.25 (if no CI: GMR)
  no_effect_point   every reported AUC/Cmax GMR lies within 0.80-1.25
  weak_change       some GMR outside 0.80-1.25 but within 0.50-2.00
  strong_change     some GMR <= 0.50 or >= 2.00
The 0.80-1.25 no-effect boundary is the FDA default; 2-fold is the FDA moderate-perpetrator
boundary. "No clinically significant" in a label may legitimately tolerate weak changes, so
both are reported and neither is called an error automatically.

Direction comes from the table caption only (victim = the drug whose PK the table reports);
tables whose caption does not resolve the direction are skipped and counted.

Usage: python 07_table_extractor.py --raw data/raw/openfda_label --rxnorm data/raw/rxnorm \
          --out data/interim/v1_2/tables
"""
import argparse, hashlib, importlib.util, json, re
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup
import warnings
warnings.filterwarnings("ignore")

VERSION = "1.1"
# v1.1: when the caption is missing or does not resolve the direction, the direction is read
# from (1) a title written in the first table row, then (2) the group header above the AUC
# column ("Atorvastatin | Ratio of AUC" -> victim = label drug; "Co-administered drug ... |
# Ratio of AUC" -> victim = partner; "Effect of X on the Pharmacokinetics of Co-administered
# Drug"). The row partner is searched in every non-numeric cell, not only the first column.
TABLE_FIELDS = ["pharmacokinetics_table", "clinical_pharmacology_table", "drug_interactions_table"]
GENERIC = r"(?:co-?administered|concomitant(?:ly administered)?|other|interacting)\s+(?:drugs?|medications?|agents?)"
NUM = r"[0-9]+(?:\.[0-9]+)?"
here = Path(__file__).resolve().parent


def load_ex():
    spec = importlib.util.spec_from_file_location("ex", here / "02_extract_null_statements_v1_2.py")
    ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
    return ex


def text(el):
    for fn in el.find_all("footnote"):
        fn.decompose()
    return re.sub(r"\s+", " ", el.get_text(" ")).strip()


def _span(v):
    try:
        return max(1, min(50, int(str(v).strip()))) if v is not None else 1
    except ValueError:
        return 1


def grid(table):
    rows, spans = [], {}
    for tr in table.find_all("tr"):
        row, c = [], 0
        cells = tr.find_all(["td", "th"])
        k = 0
        while k < len(cells) or (c in spans):
            if c in spans:
                t, left = spans[c]; row.append(t)
                spans[c] = (t, left - 1)
                if left - 1 <= 0:
                    del spans[c]
                c += 1; continue
            cell = cells[k]; k += 1
            t = text(cell)
            cs, rs = _span(cell.get("colspan")), _span(cell.get("rowspan"))
            for _ in range(max(cs, 1)):
                row.append(t)
                if rs > 1:
                    spans[c] = (t, rs - 1)
                c += 1
        rows.append(row)
    return rows


def caption_direction(cap, aliases):
    c = cap.lower()
    m = re.search(r"\bon\b(.*)$", c)
    victim_side = None
    if re.search(r"\bin the presence of\b", c):
        mm = re.search(r"\bfor\b(.*?)\bin the presence of\b", c)
        victim_side = mm.group(1) if mm else None
    elif m and re.search(r"\beffects? of\b", c):
        victim_side = m.group(1)
    elif re.search(r"exposure (?:to|of)\b", c):
        victim_side = c.split("exposure", 1)[1]
    if victim_side is None:
        return None
    own = any(re.search(r"\b" + re.escape(a) + r"\b", victim_side) for a in aliases)
    gen = re.search(GENERIC, victim_side) is not None
    if own and not gen:
        return "partner_affects_label_drug"
    if gen and not own:
        return "label_drug_affects_partner"
    return None


def parse_value(s, col_kind):
    """Per-cell parse. The main value is the text before any bracket; arrows or a minus sign give
    the direction; 'fold' and '%' are read from the cell itself."""
    s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-")
    parts = re.split(r"[\(\[]", s, maxsplit=1)
    main, rest = (parts[0], parts[1]) if len(parts) == 2 else (s, "")
    mm = re.search(r"(-)?\s*(" + NUM + ")", main)
    if not mm:
        return None
    point = float(mm.group(2))
    down = ("\u2193" in main and "\u2191" not in main) or bool(mm.group(1)) or bool(re.search(r"(?i)decrease", main))
    ci = None
    cm = re.match(r"\s*(\u2193|\u2191|-)?\s*(" + NUM + r")\s*(?:,|to|;|\s-\s|-)\s*(\u2193|\u2191|-)?\s*(" + NUM + r")\s*[\)\]]", rest)
    if re.search(r"(?i)fold", main):
        g = 1 / point if down else point
        return {"gmr": round(g, 4), "ci": None, "kind": "fold"} if g > 0 else None
    is_pct = "%" in main or (col_kind == "percent" and "." not in mm.group(2) and point >= 5)
    if is_pct:
        g = 1 + (-1 if down else 1) * point / 100.0
        if cm:
            lo = 1 + (-1 if cm.group(1) in ("\u2193", "-") else 1) * float(cm.group(2)) / 100.0
            hi = 1 + (-1 if cm.group(3) in ("\u2193", "-") else 1) * float(cm.group(4)) / 100.0
            ci = (round(min(lo, hi), 4), round(max(lo, hi), 4))
        return {"gmr": round(g, 4), "ci": ci, "kind": "percent"} if g > 0 else None
    if "." in mm.group(2) and 0.05 < point < 20 and not mm.group(1) and "\u2193" not in main and "\u2191" not in main:
        if cm and not cm.group(1) and not cm.group(3):
            ci = (float(cm.group(2)), float(cm.group(4)))
        return {"gmr": round(point, 4), "ci": ci, "kind": "ratio"}
    return None


def column_kind(h):
    h = h.lower()
    if "%" in h or "percent" in h:
        return "percent"
    if "ratio" in h or "no effect = 1" in h or "gmr" in h or "geometric mean" in h:
        return "ratio"
    return "unknown"


def verdict(vals):
    pts = [v["gmr"] for v in vals]
    if not pts:
        return None
    if any(p <= 0.5 or p >= 2.0 for p in pts):
        return "strong_change"
    if any(p < 0.8 or p > 1.25 for p in pts):
        return "weak_change"
    cis = [v["ci"] for v in vals if v["ci"]]
    if len(cis) == len(vals) and all(0.8 <= lo and hi <= 1.25 for lo, hi in cis):
        return "no_effect_strict"
    if not cis:
        return "no_effect_strict_point_only"
    return "no_effect_point"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True); ap.add_argument("--rxnorm", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    ex = load_ex()
    lexf = next(Path(a.rxnorm).glob("rxnorm_ingredients_*.json"))
    lexj = json.loads(lexf.read_text(encoding="utf-8")); lex = ex.Lexicon(lexj["concepts"])
    setid_names, _ = ex.load_setid_ingredients(a.rxnorm, lex)
    allowed = set()
    for _, rec in ex.iter_labels(a.raw):
        if rec.get("clinical_pharmacology"):
            for n in setid_names.get(rec.get("set_id"), ()):
                allowed.add(lex.info[n]["in_rxcui"])
    lex.build_index(allowed)

    st = Counter(); seen = set()
    with open(a.out / "table_records.jsonl", "w", encoding="utf-8") as out:
        for zname, rec in ex.iter_labels(a.raw):
            own = setid_names.get(rec.get("set_id"), set()) | ex.own_from_openfda(rec, lex)
            if not own:
                own = ex.own_from_spl_elements(rec, lex)
            if not own:
                continue
            own_in = {lex.info[n]["in_rxcui"] for n in own}
            aliases = ex.own_aliases(rec, own)
            for fld in TABLE_FIELDS:
                for html in rec.get(fld, []):
                    h = hashlib.sha1(html.encode()).hexdigest()
                    if (rec.get("set_id"), h) in seen:
                        continue          # same table repeated in two fields of one label
                    seen.add((rec.get("set_id"), h))
                    if not re.search(r"(?i)auc", html) or not re.search(r"(?i)c\s*(?:<sub>)?\s*max", html):
                        continue
                    soup = BeautifulSoup(html, "lxml"); tb = soup.find("table")
                    if tb is None:
                        continue
                    cap_el = tb.find("caption"); cap = text(cap_el) if cap_el else ""
                    st["pk_tables"] += 1
                    g = grid(tb)
                    if len(g) < 2:
                        continue
                    width = max(len(r) for r in g)
                    g = [r + [""] * (width - len(r)) for r in g]
                    direction, dsrc = caption_direction(cap, aliases), "caption"
                    if direction is None and g:
                        direction, dsrc = caption_direction(" ".join(dict.fromkeys(g[0])), aliases), "first_row_title"
                    # header rows: those mentioning AUC/Cmax; a column's label = joined header cells
                    hdr_idx = [i for i, r in enumerate(g[:6]) if any(re.search(r"(?i)\bauc|c ?max", c) for c in r)]
                    if not hdr_idx:
                        st["tables_no_header"] += 1; continue
                    last_hdr = max(hdr_idx)
                    col_lab = [" ".join(g[i][j] for i in range(0, last_hdr + 1)) for j in range(width)]
                    lab = [max((g[i][j] for i in hdr_idx), key=lambda t: bool(re.search(r"(?i)\bauc|c ?max", t)) * 1000 - len(t))
                           for j in range(width)]
                    auc_cols = [j for j in range(width) if re.search(r"(?i)\bauc", lab[j]) and not re.search(r"(?i)c ?max", lab[j])]
                    cmax_cols = [j for j in range(width) if re.search(r"(?i)c ?max", lab[j]) and not re.search(r"(?i)\bauc", lab[j])]
                    if not auc_cols:
                        st["tables_no_auc_col"] += 1; continue
                    if direction is None:
                        grp = " ".join(dict.fromkeys(g[i][auc_cols[0]] for i in range(0, last_hdr + 1))).lower()
                        # the GMR definition ("with/without co-administered drug", "No Effect = 1.00")
                        # names no victim; drop it before reading the header
                        grp = re.sub(r"\(?\s*(?:ratio\s*)?with\s*/\s*without\s+(?:the\s+)?co-?administered\s+drugs?\s*\)?|no effect\s*=\s*1(?:\.0+)?", " ", grp)
                        direction, dsrc = caption_direction(grp, aliases), "auc_group_header_title"
                        if direction is None:
                            own_h = any(re.search(r"\b" + re.escape(x) + r"\b", grp) for x in aliases)
                            gen_h = re.search(r"(?:^|\bof\s+(?:the\s+)?)co-?administered drugs?|^\s*co-?administered drug|concomitant drugs?|other drugs?", grp.strip()) is not None
                            if own_h and not gen_h:
                                direction, dsrc = "partner_affects_label_drug", "auc_group_header"
                            elif gen_h and not own_h:
                                direction, dsrc = "label_drug_affects_partner", "auc_group_header"
                    if direction is None:
                        st["tables_direction_unresolved"] += 1; continue
                    st["tables_direction_" + direction] += 1; st["direction_source_" + dsrc] += 1
                    num_cols = set(auc_cols + cmax_cols)
                    current = None
                    for r in g[last_hdr + 1:]:
                        txt = " ".join(c for j, c in enumerate(r) if j not in num_cols and c)
                        if txt.strip():
                            found = {d for d in lex.find(txt) if lex.info[d]["in_rxcui"] not in own_in}
                            # a named row without a recognised partner resets the carry-over
                            current = found or None
                        if not current:
                            continue
                        vals, kinds = {}, {}
                        for name, cols in (("auc", auc_cols[:1]), ("cmax", cmax_cols[:1])):
                            for j in cols:
                                v = parse_value(r[j], column_kind(col_lab[j]))
                                if v:
                                    kinds[name] = v.pop("kind"); vals[name] = v
                        if "auc" not in vals:
                            continue
                        if direction == "label_drug_affects_partner" and dsrc != "caption" and any(
                                re.search(r"\b" + re.escape(x) + r"\b", txt.lower()) for x in aliases if len(x) > 3):
                            st["rows_skipped_own_named_in_partner_victim_table"] += 1
                            continue
                        if direction == "partner_affects_label_drug" and dsrc != "caption" and any(
                                len(re.findall(r"\b" + re.escape(p) + r"\b", txt.lower())) >= 2 for p in current):
                            # partner named again in an analyte column: the victim may be the partner
                            st["rows_skipped_partner_named_as_analyte"] += 1
                            continue
                        vd = verdict(list(vals.values()))
                        for p in sorted(current):
                            st["records"] += 1; st["verdict_" + vd] += 1
                            out.write(json.dumps({
                                "set_id": rec.get("set_id"), "label_in_rxcuis": sorted(own_in), "partner": p,
                                "partner_in_rxcui": lex.info[p]["in_rxcui"], "direction": direction,
                                "caption": cap[:300], "direction_source": dsrc, "row_text": " | ".join(r)[:300], "values": vals,
                                "value_kinds": kinds, "verdict": vd, "field": fld, "source_file": zname},
                                ensure_ascii=False) + "\n")
    meta = {"script_version": VERSION, "stats": dict(st)}
    (a.out / "table_stats.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
