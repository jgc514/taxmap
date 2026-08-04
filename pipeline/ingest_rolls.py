#!/usr/bin/env python3
"""Load every downloaded appraisal roll into `roll_entities`.

The downloads are almost all True Automation PACS "Appraisal Export" bundles,
whose APPRAISAL_ENTITY_INFO.TXT is one fixed-width row per (property, taxing
entity) — exactly the per-parcel jurisdiction stack the map is missing. This
finds that member inside each archive, parses it with the existing 8.0.30
layout, and reports what turned up per county.

The roll's tax year does not have to match the map's: we take only *which*
units bill each account from the roll, and the rate for each unit still comes
from the PTAD workbook (`roll_rates.py`), so a 2026 roll is fine for fixing
2025 coverage.

    python pipeline/ingest_rolls.py --dry-run    # what's parsable
    python pipeline/ingest_rolls.py --only Hays
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import duckdb
import pyarrow as pa

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_ta_export import cut, num  # noqa: E402

ROLLS = ROOT / "data" / "raw" / "rolls"
DB = ROOT / "data" / "build" / "taxmap.duckdb"
REPORT = ROOT / "data" / "build" / "roll-ingest.json"

# The per-(property, entity) member of a PACS export. Counties ship it under
# either the long name or the abbreviated one — Travis uses PROP_ENT.TXT, with
# wider records but the same leading field layout.
MEMBER = re.compile(r"(APPRAISAL_ENTITY_INFO|PROP_ENT)\.TXT$", re.I)
MIN_LINE = 178


def entity_stream(path: Path, depth=0):
    """(name, byte stream) of the entity-info member, or None.

    Recurses one level into nested archives: several CADs wrap the vendor
    export in an outer zip alongside per-table zips (Orange, for one).
    """
    if path.suffix.lower() == ".zip":
        try:
            z = zipfile.ZipFile(path)
        except zipfile.BadZipFile:
            return None
        hits = [n for n in z.namelist() if MEMBER.search(n)]
        if hits:
            return hits[0], z.open(hits[0])
        if depth < 2:
            for inner in z.namelist():
                if not inner.lower().endswith(".zip"):
                    continue
                try:
                    buf = io.BytesIO(z.read(inner))
                    iz = zipfile.ZipFile(buf)
                except (zipfile.BadZipFile, KeyError):
                    continue
                ihits = [n for n in iz.namelist() if MEMBER.search(n)]
                if ihits:
                    return f"{inner}!{ihits[0]}", iz.open(ihits[0])
        return None
    if MEMBER.search(path.name):
        return path.name, open(path, "rb")
    return None


def parse(county, stream):
    rows, bad = [], 0
    for raw in io.TextIOWrapper(stream, errors="replace"):
        line = raw.rstrip("\n")
        if len(line) < MIN_LINE:
            bad += 1
            continue
        code = cut(line, "entity_cd").strip()
        name = cut(line, "entity_name").strip()
        if not code:
            bad += 1
            continue
        rows.append((county, str(num(cut(line, "prop_id"))), code, name,
                     num(cut(line, "assessed_val")),
                     num(cut(line, "ex_amt")) if len(line) >= 373 else 0,
                     num(cut(line, "taxable_val"))))
    return rows, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only")
    args = ap.parse_args()

    dirs = sorted(d for d in ROLLS.iterdir() if d.is_dir())
    if args.only:
        want = {re.sub(r"[^a-z0-9]+", "-", s.strip().lower())
                for s in args.only.split(",")}
        dirs = [d for d in dirs if d.name in want]

    con = None if args.dry_run else duckdb.connect(str(DB))
    if con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS roll_entities(
               county TEXT, prop_id TEXT, entity_code TEXT, entity_name TEXT,
               assessed BIGINT, exemptions BIGINT, taxable BIGINT)""")
        # Each county re-ingest starts with DELETE ... WHERE county = ?, and
        # this table reaches ~15M rows across the state. Without an index that
        # is a full scan per county and the run gets slower the more counties
        # it has already loaded.
        con.execute("CREATE INDEX IF NOT EXISTS roll_entities_county "
                    "ON roll_entities(county)")

    report, ok, skipped = {}, 0, []
    for d in dirs:
        county = d.name.replace("-", " ").title()
        files = [p for p in sorted(d.iterdir()) if p.is_file()]
        # An already-extracted export (Bandera, Guadalupe) has the entity file
        # sitting loose in the directory — look for it by name before falling
        # back to whichever archive happens to sort first.
        src = next((p for p in files if MEMBER.search(p.name)), None) or \
            next((p for p in files if p.suffix.lower() in (".zip", ".txt")), None)
        if not src:
            skipped.append((county, "no archive"))
            continue
        got = entity_stream(src)
        if not got:
            skipped.append((county, f"no APPRAISAL_ENTITY_INFO in {src.name}"))
            continue
        member, stream = got
        rows, bad = parse(county, stream)
        stream.close()
        if not rows:
            skipped.append((county, "entity file parsed to 0 rows"))
            continue

        codes = {}
        for r in rows:
            codes.setdefault(r[2], r[3])
        props = len({r[1] for r in rows})
        # ESD rows are the point of the exercise — surface them per county.
        # Diagnostic only — roll_rates.py does the real entity→PTAD matching by
        # name. Codes are county-invented ("CESD2", "F01", "E2"), so the name
        # is the only reliable signal here.
        esd = {c: n for c, n in codes.items()
               if re.search(r"\besd\b|emerg\w*\s+serv|fire", n, re.I)}
        report[county] = {"file": str(src.relative_to(ROOT)), "member": member,
                          "rows": len(rows), "properties": props,
                          "unparsed_lines": bad, "entity_codes": len(codes),
                          "esd_codes": esd}
        print(f"  {county:16s} {props:>8,} props  {len(rows):>9,} entity rows  "
              f"{len(codes):>3} units  ESD: {list(esd)[:4]}", flush=True)

        if con:
            con.execute("DELETE FROM roll_entities WHERE county = ?", [county])
            # Bulk-insert through Arrow. con.executemany() binds one row at a
            # time: on this data it managed ~25k rows/minute, so a statewide
            # ~15M-row load ran for hours. Handing DuckDB a columnar batch
            # turns the same work into seconds.
            batch = pa.table({
                "county": pa.array([r[0] for r in rows], pa.string()),
                "prop_id": pa.array([r[1] for r in rows], pa.string()),
                "entity_code": pa.array([r[2] for r in rows], pa.string()),
                "entity_name": pa.array([r[3] for r in rows], pa.string()),
                "assessed": pa.array([r[4] for r in rows], pa.int64()),
                "exemptions": pa.array([r[5] for r in rows], pa.int64()),
                "taxable": pa.array([r[6] for r in rows], pa.int64()),
            })
            con.register("roll_batch", batch)
            con.execute("INSERT INTO roll_entities SELECT * FROM roll_batch")
            con.unregister("roll_batch")
        ok += 1

    REPORT.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(f"\n{ok} counties ingested"
          f"{' (dry run, nothing written)' if args.dry_run else ''}")
    if skipped:
        print(f"{len(skipped)} not usable as a PACS export:")
        for county, why in skipped:
            print(f"  {county:16s} {why}")
    print(f"-> {REPORT}")


if __name__ == "__main__":
    main()
