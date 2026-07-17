#!/usr/bin/env python3
"""Parse a True Automation 'Certified Appraisal Roll' text report (Rev 3.01)
into DuckDB tables. Used by Wilson, Guadalupe, and Bandera CADs.

Usage: parse_ta_roll.py <county-name> <roll.txt>

Produces/updates in data/build/taxmap.duckdb:
  roll_props(county, prop_id, geo_id, owner, legal, situs, market, appraised,
             cap, assessed, exemption_codes)
  roll_entities(county, prop_id, entity_code, entity_name, assessed,
                exemptions, taxable)

The report is a line-printer layout: per-property header block (6-7 lines)
followed by an entity table; page headers/footers are interleaved and blocks
can span page breaks, so page furniture is filtered out first.
"""
import re
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "data" / "build"

# Page furniture to drop before block parsing.
FURNITURE = re.compile(
    r"^\s*$"
    r"|^\s+\d{4}\s*$"                      # bare year heading
    r"|Certified Appraisal Roll"
    r"|As of Supplement"
    r"|^\s+Title:"
    r"|Report Specifications|Sort Order:|Property Types:|Property Group Codes:"
    r"|Entities:|Alpha Range:|Geo Range:|Acreage Range:|Custom Query:"
    r"|^\s+Like:|^\s+From:"
    r"|^\s+County: \w+.*(AM|PM)\s*$"
    r"|^\s+Rev\. \d+\.\d+.*$"
    r"|^\s+Page \d+\s*$"
)

BLOCK_START = re.compile(r"^\s{0,6}(\d+)\s+(\d+)\s+([\d.]+)\s+([A-Z])\s+Geo:\s*(\S*)")
ENTITY_HEADER = re.compile(r"^\s+Entity\s+Description\s+Xref")
# code, name (2+ space gap), then the last 3 numeric columns
ENTITY_ROW = re.compile(
    r"^\s{4,12}(\S{1,8})\s+(.+?)\s{2,}([\d,]+)\s+([\d,]+)\s+([\d,-]+)\s*$"
)
NUM = lambda s: int(s.replace(",", "").replace("-", "0") or 0)

FIELD_PATTERNS = {
    "market": re.compile(r"Market:\s+([\d,]+)"),
    "appraised": re.compile(r"Appraised:\s+([\d,]+)"),
    "cap": re.compile(r"Cap:\s+([\d,]+)"),
    "assessed": re.compile(r"Assessed:\s+([\d,]+)"),
}


def parse(county: str, path: Path):
    props, entities = [], []
    cur = None
    in_entities = False
    with open(path, "r", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n").replace("\f", "")
            if FURNITURE.search(line):
                continue

            m = BLOCK_START.match(line)
            # An entity row can also start with digits; require Geo: to distinguish
            if m:
                if cur:
                    props.append(cur)
                cur = {
                    "prop_id": m.group(1), "geo_id": m.group(5), "owner": None,
                    "legal": None, "situs": "", "market": 0, "appraised": 0,
                    "cap": 0, "assessed": 0, "exemptions": "", "_line": 0,
                }
                in_entities = False
            if cur is None:
                continue
            cur["_line"] += 1

            for key, pat in FIELD_PATTERNS.items():
                fm = pat.search(line)
                if fm:
                    cur[key] = NUM(fm.group(1))
            if cur["_line"] == 2 and not in_entities:
                # owner name = first column of line 2 (ends at 2+ spaces)
                seg = line.strip().split("  ")[0].strip()
                cur["owner"] = seg or None
                rest = line.strip()[len(seg):].strip()
                cur["legal"] = rest.split("  ")[0].strip() or None
            sm = re.search(r"Situs:\s+(.*?)\s+(?:Mtg Cd:|$)", line)
            if sm:
                cur["situs"] = sm.group(1).strip()
            em = re.search(r"Exemptions:\s*(\S.*)?$", line)
            if em and "Entity" not in line:
                cur["exemptions"] = (em.group(1) or "").strip()

            if ENTITY_HEADER.match(line):
                in_entities = True
                continue
            if in_entities:
                rm = ENTITY_ROW.match(line)
                if rm and "Geo:" not in line:
                    entities.append((
                        county, cur["prop_id"], rm.group(1).strip(),
                        rm.group(2).strip(), NUM(rm.group(3)), NUM(rm.group(4)),
                        NUM(rm.group(5)),
                    ))
    if cur:
        props.append(cur)
    return props, entities


def main():
    county, roll = sys.argv[1], Path(sys.argv[2])
    props, entities = parse(county, roll)
    print(f"{county}: {len(props)} properties, {len(entities)} entity rows")

    con = duckdb.connect(str(BUILD / "taxmap.duckdb"))
    con.execute(
        """CREATE TABLE IF NOT EXISTS roll_props(
           county TEXT, prop_id TEXT, geo_id TEXT, owner TEXT, legal TEXT,
           situs TEXT, market BIGINT, appraised BIGINT, cap BIGINT,
           assessed BIGINT, exemption_codes TEXT)"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS roll_entities(
           county TEXT, prop_id TEXT, entity_code TEXT, entity_name TEXT,
           assessed BIGINT, exemptions BIGINT, taxable BIGINT)"""
    )
    con.execute("DELETE FROM roll_props WHERE county = ?", [county])
    con.execute("DELETE FROM roll_entities WHERE county = ?", [county])
    con.executemany(
        "INSERT INTO roll_props VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(county, p["prop_id"], p["geo_id"], p["owner"], p["legal"], p["situs"],
          p["market"], p["appraised"], p["cap"], p["assessed"], p["exemptions"])
         for p in props],
    )
    con.executemany("INSERT INTO roll_entities VALUES (?,?,?,?,?,?,?)", entities)

    # quick sanity report
    print(con.execute(
        """SELECT entity_code, any_value(entity_name), count(*)
           FROM roll_entities WHERE county = ? GROUP BY 1 ORDER BY 3 DESC LIMIT 15""",
        [county]).fetchall())


if __name__ == "__main__":
    main()
