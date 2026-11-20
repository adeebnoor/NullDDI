"""NullDDI step 2, v1.1 (extractor A, deterministic rules).

Same task as v1.0: find FDA-label sentences that report a MEASURED absence of a
clinically significant drug-drug interaction, keeping provenance to the sentence.

Changes from v1.0 (17 Nov 2026), each fixing a defect seen in the v1.0 run:
  1. Lexicon = RxNorm ingredient names (TTY IN/PIN, RxNav allconcepts), restricted
     to ingredients that are the active ingredient of at least one label with a
     Clinical Pharmacology section (DailyMed SPL->RxNorm mapping, SCD/SBD/GPCK/BPCK).
     v1.0 used raw openfda.generic_name, which let 'oral', 'tablets', '400 mg' in.
     A short, published analyte stoplist removes lab analytes/physiological terms.
  2. A label's own active ingredients come from the DailyMed SPL->RxNorm mapping by
     set_id, unioned with openfda names; if both are empty (labels not yet in the
     mapping), from spl_product_data_elements, keeping only indexed ingredients that
     the label mentions >= 3 times in its clinical text (drops excipients). v1.0 skipped every label whose openfda
     block was empty (177,796 labels, 14,949 of them with negation sentences).
  3. Sentence handling: split also at numbered section headings ("7.5 Lorazepam");
     when a sentence has a contrast marker (however/but/whereas/except/...), only
     partners in the negated clause are kept; sentences still > 600 chars are kept
     but flagged long_sentence=true; bullets also split; population-PK sentences
     are kept but flagged population_pk=true (weaker, covariate-type evidence);
     flattened table text inside narrative sections is flagged table_like=true;
     sentences that never name the label's own drug (ingredient, brand) are flagged
     own_mentioned=false (e.g. a tinidazole label quoting metronidazole-phenytoin);
     endogenous-analyte contexts ("serum hormone levels") are flagged; sentences that
     also report a quantified change ("AUC increased by 50%", "2-fold") are flagged
     positive_cue=true because they may mix a real interaction with a null one.
  Flags never delete records; the CORE set is records with no flag raised. *_table sections are left to a dedicated
     numeric table extractor (they are flattened tables, not sentences).
  4. Every partner and own ingredient carries an RxCUI; PIN salts are mapped to the
     base IN when the salt-free name is an IN (warfarin sodium -> warfarin). The
     partner must differ from the label's own ingredients at IN level and must not
     be a name-substring of them (prodrug/moiety, e.g. fosaprepitant/aprepitant).

Usage:
  python 02_extract_null_statements_v1_1.py --raw data/raw/openfda_label \
      --rxnorm data/raw/rxnorm --out data/interim/v1_1
"""
import argparse, hashlib, json, re, zipfile
from collections import Counter, defaultdict
from pathlib import Path

VERSION = "1.1"
SECTIONS = ["drug_interactions", "clinical_pharmacology", "pharmacokinetics"]
DEFERRED_TABLE_SECTIONS = ["drug_interactions_table", "pharmacokinetics_table"]

NEG = {
    "P1": r"\bno clinically (?:significant|relevant|meaningful|important) (?:effect|effects|change|changes|difference|differences|interaction|interactions|alteration)",
    "P2": r"\b(?:did|does) not (?:significantly |meaningfully |substantially |appreciably )?(?:alter|affect|change|influence|increase|decrease|modify) the (?:pharmacokinetics|exposure|plasma concentrations?|auc|cmax|systemic exposure|bioavailability)",
    "P3": r"\bhad no (?:clinically (?:significant|relevant|meaningful) |significant |meaningful |apparent )?(?:effect|influence|impact) on the (?:pharmacokinetics|exposure|plasma concentrations?|auc|cmax)",
    "P4": r"\bno (?:significant |clinically (?:significant|relevant) )?pharmacokinetic interactions? (?:was|were|has been|have been) (?:observed|seen|found|detected|noted)",
    "P5": r"\bwere not (?:significantly |meaningfully )?(?:altered|affected|changed)\b",
}
NEG_RE = {k: re.compile(v, re.I) for k, v in NEG.items()}
SPECULATIVE = re.compile(
    r"\b(?:expected|predicted|predicts?|anticipated|in vitro|pbpk|physiologically[- ]based|simulat\w*|model(?:ing|led|ed)?|theoretical|unlikely|not studied|has not been (?:studied|evaluated))\b",
    re.I)
SENT_SPLIT = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")
HEADING_SPLIT = re.compile(r"\s+(?=\d{1,2}\.\d{1,2}\s+[A-Z])|\s*[\u2022\u25cf\u25aa]\s*")
TABLE_LIKE = re.compile(r"\(N\s*=|\bratio of (?:auc|c ?max)\b|\bchange in (?:auc|c ?max)\b|\b90% ci\b", re.I)
ENDOGENOUS = re.compile(r"\b(?:serum|plasma) (?:hormone )?levels\b|\bhormone levels\b|\bendogenous\b", re.I)
POSITIVE_CUE = re.compile(r"\b(?:increased|decreased|reduced|elevated|lowered)\b[^.;]{0,80}?\bby (?:approximately |about |up to )?\d+(?:\.\d+)?\s*(?:%|-?fold)|\b\d+(?:\.\d+)?\s*-?fold (?:increase|decrease|higher|lower)", re.I)
POPPK = re.compile(r"\bpopulation (?:pharmacokinetic|pk)\b", re.I)
CONTRAST = re.compile(r",?\s*\b(?:however|but|whereas|although|except|in contrast|on the other hand)\b|;", re.I)
TOKEN = re.compile(r"[a-z0-9][a-z0-9\-]*")
LONG = 600
OWN_TTY = {"SCD", "SBD", "GPCK", "BPCK"}

# Lab analytes / physiological terms that are RxNorm ingredients but, inside a PK
# sentence, almost always name a measurement, not a co-administered drug.
ANALYTE_STOP = {"glucose", "creatinine", "urea", "prothrombin", "water", "oxygen", "air",
                "sodium", "potassium", "chloride", "bicarbonate", "albumin", "hemoglobin",
                "cholesterol", "bilirubin", "insulin human", "placebo"}

SALTS = re.compile(
    r"\b(?:sodium|potassium|calcium|magnesium|hydrochloride|hcl|dihydrochloride|hydrobromide|sulfate|sulphate|"
    r"mesylate|maleate|fumarate|tartrate|bitartrate|citrate|acetate|succinate|phosphate|besylate|tosylate|"
    r"monohydrate|dihydrate|trihydrate|hemihydrate|anhydrous|disodium|dipropionate|propionate|bromide|"
    r"chloride|lactate|gluconate|carbonate|hyclate|malate|oxalate|valerate|nitrate)\b", re.I)


def strip_salt(name):
    return re.sub(r"\s+", " ", SALTS.sub(" ", name)).strip()


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def iter_labels(raw):
    for z in sorted(Path(raw).glob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                with zf.open(n) as f:
                    for rec in json.load(f).get("results", []):
                        yield z.name, rec


class Lexicon:
    """RxNorm IN/PIN names -> (rxcui, tty, base IN rxcui), indexed by first token."""

    def __init__(self, concepts):
        self.info = {}
        ins = {c["name"].lower(): c["rxcui"] for c in concepts if c["tty"] == "IN"}
        for c in concepts:
            if c["tty"] not in ("IN", "PIN"):
                continue
            n = c["name"].lower()
            base = ins.get(n) if c["tty"] == "IN" else ins.get(strip_salt(n), c["rxcui"])
            self.info[n] = {"rxcui": c["rxcui"], "tty": c["tty"], "in_rxcui": base}
        self.idx = {}

    def build_index(self, allowed_in):
        self.idx = {}
        for n, v in self.info.items():
            if v["in_rxcui"] not in allowed_in or n in ANALYTE_STOP or len(n) < 4:
                continue
            toks = TOKEN.findall(n)
            if toks:
                self.idx.setdefault(toks[0], []).append((toks, n))
        for k in self.idx:
            self.idx[k].sort(key=lambda t: -len(t[0]))

    def find(self, text, idx=None):
        idx = self.idx if idx is None else idx
        toks = TOKEN.findall(text.lower())
        found, i = set(), 0
        while i < len(toks):
            hit = None
            for cand, name in idx.get(toks[i], []):
                if toks[i:i + len(cand)] == cand:
                    hit = (len(cand), name)
                    break
            if hit:
                found.add(hit[1]); i += hit[0]
            else:
                i += 1
        return found


def load_setid_ingredients(rxdir, lex):
    """set_id -> set of IN rxcuis and names, from DailyMed SCD/SBD/GPCK/BPCK strings."""
    full_idx = {}
    for n in lex.info:
        toks = TOKEN.findall(n)
        if toks:
            full_idx.setdefault(toks[0], []).append((toks, n))
    for k in full_idx:
        full_idx[k].sort(key=lambda t: -len(t[0]))
    z = next(Path(rxdir).glob("dailymed_rxnorm_mappings_*.zip"))
    with zipfile.ZipFile(z) as zf:
        txt = zf.read(zf.namelist()[0]).decode("utf-8", "replace")
    out = defaultdict(set)
    for line in txt.splitlines()[1:]:
        p = line.split("|")
        if len(p) < 5 or p[4] not in OWN_TTY:
            continue
        s = re.sub(r"\[[^\]]*\]", " ", p[3])
        for n in lex.find(s, full_idx):
            out[p[0]].add(n)
    return out, z


def own_from_openfda(rec, lex):
    o = rec.get("openfda", {}) or {}
    names = set()
    for k in ("generic_name", "substance_name"):
        for v in o.get(k, []):
            for part in re.split(r"\s+and\s+|,|/", v.lower()):
                part = part.strip()
                for cand in (part, strip_salt(part)):
                    if cand in lex.info:
                        names.add(cand)
    return names


def own_from_spl_elements(rec, lex):
    """Fallback for labels absent from the DailyMed RxNorm mapping and without openfda
    names: indexed (allowed, non-excipient) ingredients listed in spl_product_data_elements
    that the label itself mentions >= 3 times in its clinical sections."""
    elems = " ".join(rec.get("spl_product_data_elements", []))
    if not elems:
        return set()
    cands = lex.find(elems)
    body = " ".join(b for sec in SECTIONS + ["description", "indications_and_usage"]
                    for b in rec.get(sec, [])).lower()
    cnt = {n: len(re.findall(r"\b" + re.escape(n) + r"\b", body)) for n in cands}
    top = max(cnt.values(), default=0)
    # keep the label's dominant ingredient(s); excipients (e.g. gelatin) fall far below it
    return {n for n, k in cnt.items() if k >= 3 and k >= 0.25 * top}


def own_aliases(rec, own):
    """Words that name the label's own product in its text: ingredient base names,
    openfda brand names, and the leading product-name token of spl_product_data_elements."""
    al = {b for b in (strip_salt(n) for n in own) if len(b) > 3} | {n for n in own if len(n) > 3}
    for v in (rec.get("openfda", {}) or {}).get("brand_name", []):
        if len(v) > 3:
            al.add(v.lower())
    el = rec.get("spl_product_data_elements", [])
    if el and el[0].split():
        t = el[0].split()[0].lower()
        if len(t) > 3:
            al.add(t)
    return al


def sentences(block):
    text = re.sub(r"\s+", " ", block)
    for chunk in HEADING_SPLIT.split(text):
        for s in SENT_SPLIT.split(chunk):
            if s:
                yield s


def negated_clauses(s):
    parts = [c for c in CONTRAST.split(s) if c and c.strip()]
    if len(parts) <= 1:
        return [s], False
    return [c for c in parts if any(r.search(c) for r in NEG_RE.values())], True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--rxnorm", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    lexf = next(Path(a.rxnorm).glob("rxnorm_ingredients_*.json"))
    lexj = json.loads(lexf.read_text(encoding="utf-8"))
    lex = Lexicon(lexj["concepts"])
    setid_names, mapf = load_setid_ingredients(a.rxnorm, lex)

    # pass 1: allowed partner ingredients = actives of labels that have Clinical Pharmacology
    allowed, per_file = set(), Counter()
    for zname, rec in iter_labels(a.raw):
        per_file[zname] += 1
        if rec.get("clinical_pharmacology"):
            for n in setid_names.get(rec.get("set_id"), ()):
                allowed.add(lex.info[n]["in_rxcui"])
    lex.build_index(allowed)

    stats = Counter()
    stats["lexicon_in_pin_names"] = len(lex.info)
    stats["allowed_partner_ingredients_in"] = len(allowed)
    stats["indexed_partner_names"] = sum(len(v) for v in lex.idx.values())
    with open(a.out / "candidates.jsonl", "w", encoding="utf-8") as out:
        for zname, rec in iter_labels(a.raw):
            stats["labels"] += 1
            sid = rec.get("set_id")
            m_names = setid_names.get(sid, set())
            o_names = own_from_openfda(rec, lex)
            own = m_names | o_names
            e_names = set() if own else own_from_spl_elements(rec, lex)
            own |= e_names
            if not own:
                stats["labels_no_own_ingredient"] += 1
                if any(r.search(b) for sec in SECTIONS for b in rec.get(sec, []) for r in NEG_RE.values()):
                    stats["labels_no_own_ingredient_with_negation"] += 1
                continue
            src = ("spl_elements" if e_names else
                   "both" if m_names and o_names else ("rxnorm_map" if m_names else "openfda"))
            stats["labels_own_from_" + src] += 1
            own_in = {lex.info[n]["in_rxcui"] for n in own}
            aliases = own_aliases(rec, own)
            for sec in DEFERRED_TABLE_SECTIONS:
                for block in rec.get(sec, []):
                    if any(r.search(block) for r in NEG_RE.values()):
                        stats["deferred_table_blocks_with_negation"] += 1
            for sec in SECTIONS:
                for block in rec.get(sec, []):
                    for s in sentences(block):
                        pats = [k for k, r in NEG_RE.items() if r.search(s)]
                        if not pats:
                            continue
                        stats["neg_sentences"] += 1
                        if SPECULATIVE.search(s):
                            stats["speculative_excluded"] += 1
                            continue
                        clauses, contrast = negated_clauses(s)
                        found = set()
                        for c in clauses:
                            found |= lex.find(c)
                        own_base = {b for b in (strip_salt(n) for n in own) if len(b) > 3}
                        partners = {d for d in found if lex.info[d]["in_rxcui"] not in own_in
                                    and not any(len(strip_salt(d)) > 3 and (strip_salt(d) in o or o in strip_salt(d))
                                                for o in own_base)}
                        if not partners:
                            stats["no_partner"] += 1
                            continue
                        stats["sentences_with_partner"] += 1
                        if contrast:
                            stats["sentences_contrast_clause_filtered"] += 1
                        long_s = len(s) > LONG
                        stats["long_sentences_flagged"] += long_s
                        pop = bool(POPPK.search(s))
                        tbl = bool(TABLE_LIKE.search(s)) or len(re.findall(r"\d+(?:\.\d+)?", s)) >= 12
                        stats["table_like_sentences_flagged"] += tbl
                        sl = s.lower()
                        own_m = any(re.search(r"\b" + re.escape(x) + r"\b", sl) for x in aliases)
                        stats["own_not_mentioned_flagged"] += not own_m
                        endo = bool(ENDOGENOUS.search(s))
                        pos = bool(POSITIVE_CUE.search(s))
                        stats["positive_cue_flagged"] += pos
                        stats["endogenous_context_flagged"] += endo
                        stats["poppk_sentences_flagged"] += pop
                        for p in sorted(partners):
                            pi = lex.info[p]
                            stats["candidates"] += 1
                            out.write(json.dumps({
                                "label_drugs": sorted(own), "label_in_rxcuis": sorted(own_in),
                                "own_source": src,
                                "partner": p, "partner_rxcui": pi["rxcui"], "partner_tty": pi["tty"],
                                "partner_in_rxcui": pi["in_rxcui"],
                                "section": sec, "patterns": pats, "contrast_filtered": contrast,
                                "long_sentence": long_s, "population_pk": pop, "table_like": tbl,
                                "own_mentioned": own_m, "endogenous_context": endo,
                                "positive_cue": pos, "sentence": s,
                                "sentence_sha1": hashlib.sha1(s.encode()).hexdigest(),
                                "set_id": sid, "label_id": rec.get("id"),
                                "version": rec.get("version"), "effective_time": rec.get("effective_time"),
                                "source_file": zname}, ensure_ascii=False) + "\n")
    meta = {"script_version": VERSION, "stats": dict(stats), "records_per_file": dict(per_file),
            "inputs": {"lexicon": {"file": lexf.name, "sha256": sha256(lexf),
                                   "rxnav_version": lexj.get("rxnav_version")},
                       "dailymed_mapping": {"file": mapf.name, "sha256": sha256(mapf)}},
            "analyte_stoplist": sorted(ANALYTE_STOP),
            "deferred_sections": DEFERRED_TABLE_SECTIONS}
    (a.out / "extract_stats.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
