"""NullDDI step 8: replication in a second regulator: EMA SmPC section 4.5.

Input : English product-information PDFs of EU centrally authorised originator medicines
        (data/raw/ema/pi_pdf/<slug>.pdf) and EMA's medicines table (active substances).
Method: identical rules to extractor A v1.2 (same negation patterns, speculative filter,
        flags, clause/heading splitting and rule-based direction), applied to SmPC
        section 4.5 "Interaction with other medicinal products ...". Partners come from the
        same RxNorm lexicon and allowed-ingredient set, plus a documented EU-name table
        (INN spellings that differ from USAN), so FDA and EMA results are directly comparable
        at RxNorm IN level.
Output: data/interim/v1_2/ema/ema_candidates.jsonl and ema_stats.json

Usage: python 08_ema_extract.py --ema data/raw/ema --rxnorm data/raw/rxnorm \
          --allowed data/raw/rxnorm/allowed_partner_in_rxcuis_20261117.json --out data/interim/v1_2/ema
"""
import argparse, hashlib, importlib.util, json, re, subprocess
from collections import Counter
from pathlib import Path

import openpyxl

VERSION = "1.0"
EU_TO_US = {  # INN (EU) spelling -> RxNorm (US) ingredient name
    "paracetamol": "acetaminophen", "salbutamol": "albuterol", "glibenclamide": "glyburide",
    "ciclosporin": "cyclosporine", "rifampicin": "rifampin", "frusemide": "furosemide",
    "adrenaline": "epinephrine", "noradrenaline": "norepinephrine", "colecalciferol": "cholecalciferol",
    "oestradiol": "estradiol", "aciclovir": "acyclovir", "valaciclovir": "valacyclovir",
    "ethinylestradiol": "ethinyl estradiol", "clomifene": "clomiphene", "phenobarbitone": "phenobarbital",
    "dosulepin": "dothiepin", "lignocaine": "lidocaine", "bendrofluazide": "bendroflumethiazide",
    "ciclosporine": "cyclosporine", "rifabutine": "rifabutin", "pethidine": "meperidine",
    "levonorgestrel": "levonorgestrel", "mesalazine": "mesalamine", "glyceryl trinitrate": "nitroglycerin",
    "isoprenaline": "isoproterenol", "orciprenaline": "metaproterenol", "thiamazole": "methimazole",
    "dexamfetamine": "dextroamphetamine", "amfetamine": "amphetamine", "metamizole": "dipyrone",
    "valproate": "valproic acid", "sodium valproate": "valproic acid",
}
here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("ex", here / "02_extract_null_statements_v1_2.py")
ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)

S45 = re.compile(r"(?:^|\n)\s*4\.5\.?\s+Interaction[s]? with other medicinal products.*?(?=\n\s*4\.6\.?\s+[A-Z])", re.S | re.I)
FLAGS = ["long_sentence", "population_pk", "table_like", "endogenous_context", "positive_cue",
         "partial_parameter", "regimen_partner"]


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pdf_text(p):
    t = subprocess.run(["pdftotext", "-enc", "UTF-8", str(p), "-"], capture_output=True, text=True).stdout
    return t


def clean(block):
    block = re.sub(r"-\n(?=[a-z])", "", block)          # hyphenated line breaks
    block = re.sub(r"\n\s*\d+\s*\n", "\n", block)        # page numbers
    return re.sub(r"\s+", " ", block)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ema", required=True); ap.add_argument("--rxnorm", required=True)
    ap.add_argument("--allowed", required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(); a.out.mkdir(parents=True, exist_ok=True)
    lexf = next(Path(a.rxnorm).glob("rxnorm_ingredients_*.json"))
    lex = ex.Lexicon(json.loads(lexf.read_text(encoding="utf-8"))["concepts"])
    for eu, us in EU_TO_US.items():                        # EU spellings share the US entry
        if us in lex.info and eu not in lex.info:
            lex.info[eu] = dict(lex.info[us])
    allowed = set(json.loads(Path(a.allowed).read_text())["allowed_in_rxcuis"])
    lex.build_index(allowed)

    xl = next(Path(a.ema).glob("medicines-output-medicines-report_en_*.xlsx"))
    ws = openpyxl.load_workbook(xl, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True)); h = rows[8]
    meta = {}
    for r in rows[9:]:
        d = dict(zip(h, r))
        if d.get("Medicine URL"):
            meta[d["Medicine URL"].rstrip("/").split("/")[-1]] = d

    st = Counter()
    with open(a.out / "ema_candidates.jsonl", "w", encoding="utf-8") as out:
        for pdf in sorted(Path(a.ema, "pi_pdf").glob("*.pdf")):
            slug = pdf.stem; d = meta.get(slug, {}); st["pdfs"] += 1
            subs = re.split(r"\s*(?:,|;| / | and )\s*", (d.get("Active substance") or "").lower())
            own = set()
            for s0 in subs:
                for c in (s0, ex.strip_salt(s0), EU_TO_US.get(s0, "")):
                    if c and c in lex.info:
                        own.add(c)
            if not own:
                st["pdfs_no_own_ingredient"] += 1; continue
            own_in = {lex.info[n]["in_rxcui"] for n in own}
            name = re.sub(r"\s*\(previously.*", "", d.get("Name of medicine") or slug).lower()
            aliases = {b for b in (ex.strip_salt(n) for n in own) if len(b) > 3} | {n for n in own if len(n) > 3} | {name}
            txt = pdf_text(pdf)
            blocks = S45.findall(txt)
            if not blocks:
                st["pdfs_no_section_4_5"] += 1; continue
            st["pdfs_with_4_5"] += 1
            seen = set()
            for b in blocks:
                for s in ex.sentences(clean(b)):
                    if s in seen:
                        continue
                    seen.add(s)
                    pats = [k for k, r in ex.NEG_RE.items() if r.search(s)]
                    if not pats:
                        continue
                    st["neg_sentences"] += 1
                    if ex.SPECULATIVE.search(s):
                        st["speculative_excluded"] += 1; continue
                    clauses, contrast = ex.negated_clauses(s)
                    found = set()
                    for c in clauses:
                        found |= lex.find(c)
                    own_base = {x for x in (ex.strip_salt(n) for n in own) if len(x) > 3}
                    partners = {p for p in found if lex.info[p]["in_rxcui"] not in own_in and not any(
                        len(ex.strip_salt(p)) > 3 and (ex.strip_salt(p) in o or o in ex.strip_salt(p)) for o in own_base)}
                    if not partners:
                        st["no_partner"] += 1; continue
                    st["sentences_with_partner"] += 1
                    sl = s.lower()
                    flags = {
                        "long_sentence": len(s) > ex.LONG,
                        "population_pk": bool(ex.POPPK.search(s)),
                        "table_like": bool(ex.TABLE_LIKE.search(s)) or len(re.findall(r"\d+(?:\.\d+)?", s)) >= 12,
                        "endogenous_context": bool(ex.ENDOGENOUS.search(s)),
                        "positive_cue": bool(ex.POSITIVE_CUE.search(s)),
                        "partial_parameter": bool(ex.PARTIAL_ONLY.search(s)) and not ex.FULL_PK.search(ex.PARTIAL_ONLY.sub(" ", s)),
                    }
                    own_m = any(re.search(r"\b" + re.escape(x) + r"\b", sl) for x in aliases)
                    for p in sorted(partners):
                        pn = {p, ex.strip_salt(p)} - {""}
                        rec = {"source": "EMA_SmPC_4.5", "slug": slug, "medicine": d.get("Name of medicine"),
                               "label_drugs": sorted(own), "label_in_rxcuis": sorted(own_in),
                               "partner": p, "partner_in_rxcui": lex.info[p]["in_rxcui"],
                               "patterns": pats, "contrast_filtered": contrast, "own_mentioned": own_m,
                               "regimen_partner": ex.regimen_partner(s, aliases, pn),
                               "direction_rule": ex.direction(" ".join(clauses), aliases, pn), **flags,
                               "sentence": s, "sentence_sha1": hashlib.sha1(s.encode()).hexdigest(),
                               "revision": d.get("Revision number"), "last_updated": d.get("Last updated date"),
                               "pdf_sha256": sha256(pdf)}
                        st["candidates"] += 1; st["direction_" + rec["direction_rule"]] += 1
                        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
    (a.out / "ema_stats.json").write_text(json.dumps({"script_version": VERSION, "stats": dict(st),
        "eu_to_us_names": EU_TO_US, "medicines_table_sha256": sha256(xl)}, indent=1))
    print(json.dumps(dict(st), indent=1))


if __name__ == "__main__":
    main()
