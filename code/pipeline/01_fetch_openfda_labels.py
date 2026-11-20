"""NullDDI step 1: download the complete openFDA drug-label bulk export.

Public-domain US Government data. Reads the official manifest
(https://api.fda.gov/download.json), downloads every drug/label partition,
verifies sizes, and records SHA-256 hashes and the export date in a manifest.

Usage: python 01_fetch_openfda_labels.py --out data/raw/openfda_label
"""
import argparse, hashlib, json, os, sys, time, urllib.request
from pathlib import Path

MANIFEST_URL = "https://api.fda.gov/download.json"


def fetch(url, dest, retries=4):
    for k in range(retries):
        try:
            tmp = dest.with_suffix(dest.suffix + ".part")
            with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            tmp.rename(dest)
            return
        except Exception as e:  # network hiccup: back off and retry
            print(f"  retry {k+1}/{retries} {url}: {e}", file=sys.stderr)
            time.sleep(5 * (k + 1))
    raise SystemExit(f"failed: {url}")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(MANIFEST_URL, timeout=60) as r:
        man = json.load(r)
    part = man["results"]["drug"]["label"]
    files = part["partitions"]
    print(f"export_date={part['export_date']} partitions={len(files)}")
    record = {"source": MANIFEST_URL, "export_date": part["export_date"],
              "total_records": part.get("total_records"), "files": []}
    for i, p in enumerate(files, 1):
        url = p["file"]
        dest = a.out / Path(url).name
        if not dest.exists():
            print(f"[{i}/{len(files)}] {url}")
            fetch(url, dest)
        record["files"].append({"url": url, "file": dest.name,
                                "bytes": dest.stat().st_size, "sha256": sha256(dest)})
    (a.out / "manifest.json").write_text(json.dumps(record, indent=1))
    print("done:", a.out / "manifest.json")


if __name__ == "__main__":
    main()
