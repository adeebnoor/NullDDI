"""NullDDI step 8a: name the EMA product-information PDFs downloaded by the browser.

The desktop browser saves downloads under random names (*.tmp). Each EMA PI PDF starts with
"1. NAME OF THE MEDICINAL PRODUCT" followed by the product name, which is matched to the
EMA medicines table (longest name first). Identified files are moved to
data/raw/ema/pi_pdf/<slug>.pdf; duplicates and unidentified files are left in place and listed.

Usage: python 08a_ema_identify_pdfs.py --downloads D:/Downloads --ema D:/Downloads/NullDDI/data/raw/ema
"""
import argparse, glob, json, os, re, subprocess
from pathlib import Path

import openpyxl


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--downloads", required=True); ap.add_argument("--ema", required=True)
    a = ap.parse_args()
    ema = Path(a.ema); (ema / "pi_pdf").mkdir(exist_ok=True)
    ws = openpyxl.load_workbook(next(ema.glob("medicines-output-medicines-report_en_*.xlsx")), read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True)); h = rows[8]
    slugs = set(json.loads((ema / "ema_slugs_originators_20261118.json").read_text()))
    name2slug = {}
    for r in rows[9:]:
        d = dict(zip(h, r))
        if d.get("Medicine URL"):
            s = d["Medicine URL"].rstrip("/").split("/")[-1]
            if s in slugs:
                name2slug[re.sub(r"\s*\(previously.*", "", d["Name of medicine"]).lower()] = s
    names = sorted(name2slug, key=len, reverse=True)
    res = {"identified": 0, "duplicate": [], "unidentified": [], "not_pdf": []}
    for f in sorted(glob.glob(os.path.join(a.downloads, "*.tmp")) + glob.glob(os.path.join(a.downloads, "emapi__*.pdf"))):
        with open(f, "rb") as fh:
            if fh.read(5) != b"%PDF-":
                res["not_pdf"].append(os.path.basename(f)); continue
        t = subprocess.run(["pdftotext", "-l", "3", f, "-"], capture_output=True, text=True).stdout
        m = re.search(r"NAME OF THE MEDICINAL PRODUCT\s*\n+\s*(.+)", t)
        first = (m.group(1) if m else "").strip().lower()
        hit = next((name2slug[n] for n in names if re.match(re.escape(n) + r"\b", first)), None)
        if not hit:
            res["unidentified"].append([os.path.basename(f), first[:80]]); continue
        dst = ema / "pi_pdf" / f"{hit}.pdf"
        if dst.exists():
            res["duplicate"].append([os.path.basename(f), hit]); continue
        os.replace(f, dst); res["identified"] += 1
    have = {p.stem for p in (ema / "pi_pdf").glob("*.pdf")}
    res["have"] = len(have); res["missing"] = sorted(slugs - have)
    (ema / "pi_pdf_identification.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: (v if isinstance(v, int) else len(v)) for k, v in res.items()}))


if __name__ == "__main__":
    main()
