#!/usr/bin/env python3
"""Pick the right appraisal-roll file per county and download it.

`find_rolls.py` lists every bulk file it found on each CAD site; most of those
are not the roll. CAD download pages are dominated by GIS shapefiles, map books,
annotation geodatabases and mineral/industrial value notices, all of which are
bigger than the roll itself — so "largest file" is exactly the wrong heuristic.
This scores candidates by what the roll is actually called, rejects the known
decoys, and prefers the most recent year.

    python pipeline/download_rolls.py --dry-run      # show the picks
    python pipeline/download_rolls.py --esd-only     # just the ESD-gap counties
    python pipeline/download_rolls.py --max-mb 800

Downloads land in data/raw/rolls/<county-slug>/ and are left compressed; the
existing parsers (parse_ta_roll.py / parse_ta_export.py) take it from there.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrub_cad_rates import SSL_CTX, UA, clean_url  # noqa: E402

SRC = ROOT / "data" / "build" / "roll-sources.json"
AUDIT = ROOT / "data" / "build" / "coverage-audit.json"
DEST = ROOT / "data" / "raw" / "rolls"
MANIFEST = ROOT / "data" / "build" / "roll-downloads.json"

# What the roll calls itself.
GOOD = [
    (12, r"certified\s+(appraisal\s+)?roll"),
    (11, r"appraisal\s+roll"),
    (10, r"certified\s+(data|export|records|full\s+roll)"),
    (9,  r"roll\s+export|data\s+export|export\s+file"),
    (7,  r"\bcert\w*\s+roll|tax\s+roll"),
    (4,  r"preliminary\s+(appraisal\s+)?roll"),
    (3,  r"all\s+propert|real\s+(and|&)\s+personal|all\s+entities"),
    (2,  r"\bcertified\b|\broll\b"),      # weak catch-all, still subject to BAD
]
# What is *not* the roll, however large and roll-adjacent it looks.
BAD = re.compile(
    r"\bgis\b|shape\s*file|shapefile|map\s*book|annotation|\.gdb|geodatabase"
    r"|mineral|industrial|notices?\b|unpaid|collector|abstract|subdivision"
    r"|survey|sketch|photo|image|appraisal\s+notice|arb\b|hearing"
    r"|layout|format|dictionary|readme", re.I)


def score(f):
    # Filenames use hyphens/underscores where prose uses spaces
    # ("2026-CERTIFIED-APPRAISAL-ROLL-ALL-ENTITIES.zip"), so flatten the
    # separators before matching or every \s+ in the patterns misses.
    blob = re.sub(r"[-_.+%20]+", " ", f"{f['label']} {f['url']}")
    if BAD.search(blob):
        return -1
    s = 0
    for pts, pat in GOOD:
        if re.search(pat, blob, re.I):
            s = max(s, pts)
    if not s:
        return -1
    if re.search(r"personal\s+propert|\bpp\b|bpp", blob, re.I):
        s -= 4                          # BPP-only export, not the real roll
    if re.search(r"\.zip($|\?)", f["url"], re.I):
        s += 1
    return s


def tax_year(f):
    """The year the data is FOR, not the year the CAD happened to upload it.

    A label year wins over a URL year: CAD sites live on WordPress, so a 2016
    roll re-posted in 2023 sits under /wp-content/uploads/2023/, and reading the
    path would rank it above the current roll.
    """
    label = re.sub(r"[-_.]+", " ", f["label"])
    years = [int(y) for y in re.findall(r"\b20(?:1\d|2\d)\b", label)]
    if not years:
        years = [int(y) for y in re.findall(r"\b20(?:1\d|2\d)\b", f["url"])]
    return max(years) if years else 0


def rank(files):
    """Candidate rolls, best first.

    Recency dominates deliberately — a 2016 roll would misstate both values and
    parcel coverage badly enough to be worse than not having one. How
    roll-shaped the name is only breaks ties within a year.
    """
    ranked = [(score(f), f) for f in files if f["usable"]]
    ranked = [(s, f) for s, f in ranked if s > 0]
    ranked.sort(key=lambda t: (-tax_year(t[1]), -t[0], -t[1]["bytes"]))
    return ranked


def pick(files, max_bytes=None):
    """Best candidate that fits the size budget, else the best one overall.

    Travis publishes its current roll only as a 3.5 GB JSON export; falling
    through to the next candidate gets us its 428 MB roll export instead of
    skipping the county entirely.
    """
    ranked = rank(files)
    if not ranked:
        return None, None, None
    if max_bytes is not None:
        for s, f in ranked:
            if f["bytes"] <= max_bytes:
                return s, f, None
        return None, None, ranked[0][1]      # everything oversized
    return ranked[0][0], ranked[0][1], None


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def download(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(clean_url(url), headers={"User-Agent": UA})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as r, \
            open(tmp, "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    tmp.rename(dest)
    return dest.stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--esd-only", action="store_true",
                    help="only counties where the map is missing an ESD")
    ap.add_argument("--max-mb", type=float, default=900,
                    help="skip any single file larger than this")
    ap.add_argument("--only")
    args = ap.parse_args()

    src = json.loads(SRC.read_text())
    audit = json.loads(AUDIT.read_text())
    if args.only:
        want = {s.strip().lower() for s in args.only.split(",")}
        src = {k: v for k, v in src.items() if k.lower() in want}
    elif args.esd_only:
        src = {k: v for k, v in src.items()
               if audit.get(k, {}).get("esd_count")}

    picks, skipped, toobig = [], [], []
    for county, rec in sorted(src.items()):
        s, f, oversized = pick(rec.get("files", []), args.max_mb * 1e6)
        if oversized is not None:
            toobig.append((county, oversized["bytes"] / 1e6, oversized))
            continue
        if not f:
            skipped.append(county)
            continue
        picks.append((county, s, f))

    print(f"{len(picks)} rolls to pull, {sum(f['bytes'] for _, _, f in picks) / 1e9:.2f} GB")
    for county, s, f in picks:
        print(f"  {county:16s} {f['bytes'] / 1e6:8.1f} MB  {tax_year(f) or '????'}  {f['label'][:50]}")
    if toobig:
        print(f"\nover --max-mb {args.max_mb:.0f}, not pulled:")
        for county, mb, f in toobig:
            print(f"  {county:16s} {mb:8.1f} MB  {f['label'][:52]}")
    if skipped:
        print(f"\nno roll-shaped file among their downloads: {', '.join(skipped)}")
    if args.dry_run:
        return

    done = []
    for county, s, f in picks:
        ext = re.search(r"\.(zip|txt|csv|xlsx?|gz)(?:$|\?)", f["url"], re.I)
        ext = f".{ext.group(1).lower()}" if ext else ".zip"
        dest = DEST / slug(county) / f"roll{ext}"
        if dest.exists():
            print(f"  {county}: already have {dest.name}")
            continue
        try:
            n = download(f["url"], dest)
            note = ""
            if ext == ".zip":
                try:
                    with zipfile.ZipFile(dest) as z:
                        names = z.namelist()
                    note = f"{len(names)} entries, e.g. {names[:3]}"
                except zipfile.BadZipFile:
                    note = "NOT A VALID ZIP"
            print(f"  {county}: {n / 1e6:.1f} MB  {note}", flush=True)
            done.append({"county": county, "url": f["url"], "label": f["label"],
                         "path": str(dest.relative_to(ROOT)), "bytes": n,
                         "score": s})
        except Exception as e:  # noqa: BLE001
            print(f"  {county}: FAILED {type(e).__name__}: {e}", flush=True)

    MANIFEST.write_text(json.dumps(done, indent=1))
    print(f"\ndownloaded {len(done)} rolls -> {MANIFEST}")


if __name__ == "__main__":
    main()
