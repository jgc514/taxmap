#!/usr/bin/env python3
"""Parse True Automation PACS 'Appraisal Export' fixed-width files (8.0.x)
into DuckDB. This is the machine-readable bulk format most TA/PACS counties
deliver (Bandera + Guadalupe post it publicly; the PIA counties are expected
to deliver the same). Layout: Appraisal-Export-Layout-8.0.30.pdf (data/raw/).

Usage: parse_ta_export.py <county-name> <APPRAISAL_ENTITY_INFO.TXT>

Loads roll_entities (same table the report parser fills) plus per-entity
exemption amounts in roll_entity_exemptions.
"""
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "data" / "build"

# (start, end) are 1-based inclusive per the spec.
F = {
    "prop_id": (1, 12), "yr": (13, 17), "sup_num": (18, 29),
    "owner_id": (30, 41), "entity_id": (42, 53), "entity_cd": (54, 63),
    "entity_name": (64, 113),
    "assessed_val": (149, 163), "taxable_val": (164, 178),
    "hs_amt": (299, 313), "ov65_amt": (314, 328),
    "dp_amt": (329, 343), "dv_amt": (344, 358), "ex_amt": (359, 373),
}


def cut(line, key):
    s, e = F[key]
    return line[s - 1:e]


def num(s):
    s = s.strip()
    return int(s) if s and s.strip("0") else (0 if s else 0)


def main():
    county, path = sys.argv[1], Path(sys.argv[2])
    rows = []
    with open(path, "r", errors="replace") as f:
        for line in f:
            if len(line) < 178:
                continue
            if num(cut(line, "yr")) != 2025 or num(cut(line, "sup_num")) != 0:
                # keep only certified 2025 records
                pass  # some counties export a single year; keep all, filter later
            rows.append((
                county,
                str(num(cut(line, "prop_id"))),
                cut(line, "entity_cd").strip(),
                cut(line, "entity_name").strip(),
                num(cut(line, "assessed_val")),
                num(cut(line, "ex_amt")) if len(line) >= 373 else 0,
                num(cut(line, "taxable_val")),
                num(cut(line, "hs_amt")) if len(line) >= 313 else 0,
                num(cut(line, "ov65_amt")) if len(line) >= 328 else 0,
                num(cut(line, "yr")),
            ))
    print(f"{county}: {len(rows)} entity rows")

    con = duckdb.connect(str(BUILD / "taxmap.duckdb"))
    con.execute(
        """CREATE TABLE IF NOT EXISTS roll_entities(
           county TEXT, prop_id TEXT, entity_code TEXT, entity_name TEXT,
           assessed BIGINT, exemptions BIGINT, taxable BIGINT)"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS roll_entity_exemptions(
           county TEXT, prop_id TEXT, entity_code TEXT,
           hs_amt BIGINT, ov65_amt BIGINT, tax_year INT)"""
    )
    con.execute("DELETE FROM roll_entities WHERE county = ?", [county])
    con.execute("DELETE FROM roll_entity_exemptions WHERE county = ?", [county])
    con.executemany(
        "INSERT INTO roll_entities VALUES (?,?,?,?,?,?,?)",
        [(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows],
    )
    con.executemany(
        "INSERT INTO roll_entity_exemptions VALUES (?,?,?,?,?,?)",
        [(r[0], r[1], r[2], r[7], r[8], r[9]) for r in rows],
    )
    print(con.execute(
        """SELECT entity_code, any_value(entity_name), count(*)
           FROM roll_entities WHERE county = ? GROUP BY 1 ORDER BY 3 DESC LIMIT 12""",
        [county]).fetchall())


if __name__ == "__main__":
    main()
