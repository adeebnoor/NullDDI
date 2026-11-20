"""NullDDI step 5: evidence tier B from the FDA CYP/transporter tables (open, public domain).

D3 logic (Noor et al., JAMIA 2017) rebuilt on open sources only: a pharmacokinetic DDI
needs a path perpetrator -> target -> victim, i.e. drug X inhibits or induces an enzyme
or transporter T and drug Y is a substrate of T (either direction).

Source: FDA "For Healthcare Professionals | FDA's Examples of Drugs that Interact with
CYP Enzymes and Transporter Systems" (Table 1, 245 drugs/substances), plus the clinical
index tables 2-1..2-3 of "Drug Development and Drug Interactions | Table of Substrates,
Inhibitors and Inducers". In-vitro tables (1-x, 3-x) are not used.

IMPORTANT scope limit (stated by FDA itself): the lists are EXAMPLES, not comprehensive,
and exclude absorption, protein-binding and pharmacodynamic mechanisms. Therefore a pair
is classified only when BOTH drugs are profiled in the table:
  B_no_path         both profiled, no perpetrator->target->victim path in the table
  B_path_expected   path with a strong/moderate perpetrator and a (moderately) sensitive
                    CYP substrate, or a transporter inhibitor and transporter substrate
  B_path_possible   path with a weak perpetrator only
  B_undetermined    at least one drug not profiled (absence from an example list is not
                    evidence of absence; NullDDI never treats it as such)

Usage:
  python 05_tier_b_fda_tables.py --tables data/raw/fda_ddi_tables --rxnorm data/raw/rxnorm \
     --pairs data/interim/v1_1/candidates.jsonl --out data/interim/v1_1/tier_b
"""
import argparse, hashlib, importlib.util, json, re
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.0"
CYP = ["1A2", "2B6", "2C8", "2C9", "2C19", "2D6", "3A"]
TRANSPORTERS = ["P-gp", "BCRP", "OATP1B1", "OATP1B3", "OAT1", "OAT3", "MATE1", "MATE2-K", "OCT2"]
COLS = {  # Table 1 column -> (role, strength, kind)
    "CYP Strg INH": ("inhibitor", "strong", "cyp"), "CYP Mod INH": ("inhibitor", "moderate", "cyp"),
    "CYP WK INH": ("inhibitor", "weak", "cyp"), "CYP Strg IND": ("inducer", "strong", "cyp"),
    "CYP Mod IND": ("inducer", "moderate", "cyp"), "CYP WK IND": ("inducer", "weak", "cyp"),
    "CYP SENS SUB": ("substrate", "sensitive", "cyp"), "CYP Mod SENS SUB": ("substrate", "moderate", "cyp"),
    "TRNSP INH": ("inhibitor", "unspecified", "transporter"), "TRNSP SUB": ("substrate", "unspecified", "transporter"),
}


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_lexicon(rxdir):
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("ex", here / "02_extract_null_statements_v1_1.py")
    ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
    lexf = next(Path(rxdir).glob("rxnorm_ingredients_*.json"))
    return ex, ex.Lexicon(json.loads(lexf.read_text(encoding="utf-8"))["concepts"]), lexf


def clean_name(n):
    n = n.replace(" ", " ").replace("’", "'").strip().lower()
    n = re.sub(r"[\d\s,]+$", "", n)            # trailing footnote numbers
    n = re.sub(r"\(\w(?:,\w)*\)", "", n)        # (a), (c,d) footnotes in tables 2-x
    return re.sub(r"\s+", " ", n).strip()


def targets_in(cell, kind):
    t = cell.replace("\u00a0", " ").replace("CYP", " ")
    vocab = CYP if kind == "cyp" else TRANSPORTERS
    found = []
    if kind == "transporter" and re.search(r"OATP1B(?![0-9])", t):   # 'OATP1B' = both isoforms
        found += ["OATP1B1", "OATP1B3"]; t = re.sub(r"OATP1B(?![0-9])", " ", t)
    for v in sorted(vocab, key=len, reverse=True):
        pat = (r"(?<![0-9A-Z])" + re.escape(v) + r"(?![0-9A-Z])") if kind == "cyp" else re.escape(v)
        if re.search(pat, t):
            found.append(v); t = re.sub(pat, " ", t)
    return found


def to_in(name, ex, lex):
    for cand in (name, ex.strip_salt(name), name.replace("s-", "").strip()):
        if cand in lex.info:
            return lex.info[cand]["in_rxcui"], cand
    return None, None


def build_roles(tables, ex, lex):
    t1 = json.loads((Path(tables) / next(p.name for p in Path(tables).glob("fda_ddi_clinical_examples_table_*.json"))).read_text(encoding="utf-8"))
    roles, unmapped, src = defaultdict(set), [], {}
    hdr = t1["header"]
    for row in t1["rows"]:
        name = clean_name(row[0]); rx, matched = to_in(name, ex, lex)
        key = rx or "NAME:" + name
        src[key] = {"fda_name": row[0], "name": name, "rxcui_in": rx, "matched_lexicon_name": matched}
        if rx is None:
            unmapped.append(name)
        for col, cell in zip(hdr[1:], row[1:]):
            if not cell.strip():
                continue
            role, strength, kind = COLS[col]
            tg = targets_in(cell, kind)
            if not tg:
                raise SystemExit(f"unparsed cell {row[0]!r} {col!r}: {cell!r}")
            for t in tg:
                roles[key].add((role, strength, t, "table1"))
    dev = json.loads(next(Path(tables).glob("fda_ddi_table_development_*.json")).read_text(encoding="utf-8"))
    for t in dev["tables"]:
        title = t["title"]
        if not re.match(r"Table 2-[123]", title):
            continue
        head = t["rows"][0]
        for row in t["rows"][1:]:
            enz = targets_in(row[0].replace("CYP", ""), "cyp")
            for col, cell in zip(head[1:], row[1:]):
                if cell.strip() in ("", "-"):
                    continue
                if title.startswith("Table 2-1"):
                    role, strength = "substrate", "sensitive"
                else:
                    role = "inhibitor" if title.startswith("Table 2-2") else "inducer"
                    strength = "strong" if col.lower().startswith("strong") else "moderate"
                for drug in re.split(r",\s*", cell):
                    name = clean_name(drug); rx, matched = to_in(name, ex, lex)
                    key = rx or "NAME:" + name
                    src.setdefault(key, {"fda_name": drug, "name": name, "rxcui_in": rx, "matched_lexicon_name": matched})
                    for e in enz:
                        roles[key].add((role, strength, e, "index_" + title[6:9]))
    return roles, src, sorted(set(unmapped)), t1.get("current_as_of")


def paths(ra, rb):
    """perpetrator->target->victim paths from a to b, with grade."""
    out = []
    for role, st, t, _ in ra:
        if role not in ("inhibitor", "inducer"):
            continue
        for r2, st2, t2, _ in rb:
            if r2 != "substrate" or t2 != t:
                continue
            if t in TRANSPORTERS:
                g = "expected"
            elif st in ("strong", "moderate"):
                g = "expected"
            else:
                g = "possible"
            out.append({"perpetrator_role": role, "perpetrator_strength": st, "target": t,
                        "victim_sensitivity": st2, "grade": g})
    return out


def classify(a, b, roles):
    if a not in roles or b not in roles:
        return "B_undetermined", []
    p = [dict(x, direction="label->partner") for x in paths(roles[a], roles[b])] + \
        [dict(x, direction="partner->label") for x in paths(roles[b], roles[a])]
    if not p:
        return "B_no_path", []
    return ("B_path_expected" if any(x["grade"] == "expected" for x in p) else "B_path_possible"), p


def read_pairs(pfile):
    pairs = defaultdict(lambda: {"records": 0, "core_records": 0})
    with open(pfile, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            labs = r["label_in_rxcuis"]
            if len(labs) != 1:          # pairs only from single-ingredient labels
                continue
            k = tuple(sorted((labs[0], r["partner_in_rxcui"])))
            v = pairs[k]; v["records"] += 1
            core = r.get("own_mentioned", True) and not any(r.get(x) for x in
                   ("long_sentence", "population_pk", "table_like", "endogenous_context", "positive_cue"))
            v["core_records"] += core
            v.setdefault("label_side", labs[0])
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", required=True); ap.add_argument("--rxnorm", required=True)
    ap.add_argument("--pairs", required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    ex, lex, lexf = load_lexicon(a.rxnorm)
    roles, src, unmapped, asof = build_roles(a.tables, ex, lex)
    with open(a.out / "fda_roles.jsonl", "w", encoding="utf-8") as f:
        for k in sorted(roles):
            f.write(json.dumps({**src[k], "key": k, "roles": sorted(map(list, roles[k]))}, ensure_ascii=False) + "\n")
    pairs = read_pairs(a.pairs)
    st, st_core = Counter(), Counter()
    names = {v["rxcui"]: n for n, v in lex.info.items() if v["tty"] == "IN"}
    with open(a.out / "tier_b_pairs.jsonl", "w", encoding="utf-8") as f:
        for (x, y), v in sorted(pairs.items()):
            lab = v["label_side"]; par = y if lab == x else x
            cls, p = classify(lab, par, roles)
            st[cls] += 1
            if v["core_records"]:
                st_core[cls] += 1
            f.write(json.dumps({"pair": [x, y], "label_in": lab, "partner_in": par,
                                "label_name": names.get(lab, lab), "partner_name": names.get(par, par),
                                "records": v["records"], "core_records": v["core_records"],
                                "tier_b": cls, "paths": p}, ensure_ascii=False) + "\n")
    meta = {"script_version": VERSION, "fda_table1_current_as_of": asof,
            "profiled_entities": len(roles), "profiled_mapped_to_rxnorm": sum(1 for k in roles if not k.startswith("NAME:")),
            "unmapped_names": unmapped,
            "pairs_all": len(pairs), "tier_b_all": dict(st),
            "pairs_with_core_records": sum(1 for v in pairs.values() if v["core_records"]), "tier_b_core": dict(st_core),
            "inputs": {"pairs": {"file": Path(a.pairs).name, "sha256": sha256(a.pairs)},
                       "lexicon": {"file": lexf.name, "sha256": sha256(lexf)},
                       "tables": {p.name: sha256(p) for p in sorted(Path(a.tables).glob("*.json"))}}}
    (a.out / "tier_b_stats.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps({k: meta[k] for k in ("profiled_entities", "profiled_mapped_to_rxnorm", "unmapped_names",
                                          "pairs_all", "tier_b_all", "pairs_with_core_records", "tier_b_core")}, indent=1))


if __name__ == "__main__":
    main()
