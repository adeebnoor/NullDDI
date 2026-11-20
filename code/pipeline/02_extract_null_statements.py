"""NullDDI step 2 (extractor A, deterministic rules): find sentences in FDA labels
that report a MEASURED absence of a clinically significant drug-drug interaction.

Input : openFDA drug/label bulk JSON zips (step 1).
Output: candidates.jsonl, one record per (label, sentence, partner drug), with full
        provenance (set_id, label id, version, effective_time, section, pattern id).

Design rules (no human review anywhere):
  * a sentence must contain a NEGATION pattern (P1-P5) and a partner drug name
    from the open lexicon built from openfda.generic_name over the same export;
  * sentences that are speculative or model-based (expected/predicted/in vitro/
    PBPK/simulation) are excluded, so only observed results remain;
  * the partner must differ from the label's own active ingredients.

Usage: python 02_extract_null_statements.py --raw data/raw/openfda_label --out data/interim
"""
import argparse, json, re, zipfile
from collections import Counter
from pathlib import Path

SECTIONS = ["drug_interactions", "clinical_pharmacology", "pharmacokinetics",
            "drug_interactions_table", "pharmacokinetics_table"]

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
TOKEN = re.compile(r"[a-z0-9][a-z0-9\-]*")


SALTS = re.compile(
    r"\b(?:sodium|potassium|calcium|magnesium|hydrochloride|hcl|dihydrochloride|hydrobromide|sulfate|sulphate|"
    r"mesylate|maleate|fumarate|tartrate|bitartrate|citrate|acetate|succinate|phosphate|besylate|tosylate|"
    r"monohydrate|dihydrate|trihydrate|hemihydrate|anhydrous|disodium|dipropionate|propionate|bromide|"
    r"chloride|lactate|gluconate|carbonate|hyclate|malate|oxalate|valerate|nitrate)\b", re.I)


def variants(name):
    """name plus its salt-free base, e.g. 'warfarin sodium' -> {'warfarin sodium', 'warfarin'}."""
    base = re.sub(r"\s+", " ", SALTS.sub(" ", name)).strip()
    return {name} | ({base} if len(base) > 3 else set())


def iter_labels(raw):
    for z in sorted(Path(raw).glob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                with zf.open(n) as f:
                    for rec in json.load(f).get("results", []):
                        yield z.name, rec


def own_names(rec):
    o = rec.get("openfda", {})
    names = set()
    for k in ("generic_name", "substance_name", "brand_name"):
        for v in o.get(k, []):
            for part in re.split(r"\s+and\s+|,|/", v.lower()):
                part = part.strip()
                if len(part) > 2:
                    names |= variants(part)
    return names


def build_lexicon(raw):
    lex = Counter()
    for _, rec in iter_labels(raw):
        for v in rec.get("openfda", {}).get("substance_name", []) + rec.get("openfda", {}).get("generic_name", []):
            for part in re.split(r"\s+and\s+|,|/", v.lower()):
                part = part.strip()
                if 3 < len(part) < 60 and not part.isdigit():
                    for v in variants(part):
                        lex[v] += 1
    # keep names seen on >= 1 label; index by first token for fast n-gram lookup
    idx = {}
    for name in lex:
        toks = TOKEN.findall(name)
        if toks:
            idx.setdefault(toks[0], []).append((toks, name))
    for k in idx:
        idx[k].sort(key=lambda t: -len(t[0]))  # longest match first
    return idx


def find_drugs(sentence, idx):
    toks = TOKEN.findall(sentence.lower())
    found, i = set(), 0
    while i < len(toks):
        hit = None
        for cand, name in idx.get(toks[i], []):
            if toks[i:i + len(cand)] == cand:
                hit = (len(cand), name)
                break
        if hit:
            found.add(hit[1])
            i += hit[0]
        else:
            i += 1
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    idx = build_lexicon(a.raw)
    stats = Counter()
    with open(a.out / "candidates.jsonl", "w") as out:
        for zname, rec in iter_labels(a.raw):
            stats["labels"] += 1
            own = own_names(rec)
            if not own:
                stats["labels_no_openfda"] += 1
                continue
            for sec in SECTIONS:
                for block in rec.get(sec, []):
                    for s in SENT_SPLIT.split(re.sub(r"\s+", " ", block)):
                        pats = [k for k, r in NEG_RE.items() if r.search(s)]
                        if not pats:
                            continue
                        stats["neg_sentences"] += 1
                        if SPECULATIVE.search(s):
                            stats["speculative_excluded"] += 1
                            continue
                        partners = {d for d in find_drugs(s, idx) if d not in own and not any(d in o or o in d for o in own)}
                        if not partners:
                            stats["no_partner"] += 1
                            continue
                        for p in sorted(partners):
                            stats["candidates"] += 1
                            out.write(json.dumps({
                                "label_drugs": sorted(own), "partner": p, "section": sec,
                                "patterns": pats, "sentence": s,
                                "set_id": rec.get("set_id"), "label_id": rec.get("id"),
                                "version": rec.get("version"), "effective_time": rec.get("effective_time"),
                                "source_file": zname}) + "\n")
    (a.out / "extract_stats.json").write_text(json.dumps(stats, indent=1))
    print(dict(stats))


if __name__ == "__main__":
    main()
