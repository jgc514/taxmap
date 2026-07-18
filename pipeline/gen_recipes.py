#!/usr/bin/env python3
"""Generate v0 county recipes for every Texas county not hand-curated in
build_region.py, writing pipeline/recipes_statewide.py + a review report.

Inclusion heuristics (validated on the 63 hand-curated counties):
  - county unit (XXX-000-00): always
  - hospital districts (type 11): only when named after the county
    ("<County> County Hospital District", "<County> Co Memorial ...",
    "<County> Regional ..."), i.e. name starts with the county name
  - groundwater districts (types 06/23): only when name starts with the
    county name (multi-county GCDs stay in their PTAD listing county)
  - misc county-wide (type 33, e.g. county education/vocational): only when
    name starts with the county name
  - college districts (type 15): NEVER by heuristic — only an explicit
    allowlist of districts verified county-coextensive
  - famous county-wide specials (Harris FCD, Port of Houston, HCDE, Tarrant
    Regional WD): explicit allowlist
  - everything else (MUD/ESD/WCID/drainage/road/PID/...): excluded, and any
    exclusion with rate >= 0.05 is logged for manual review

Output recipes carry {"fips", "ptad", "ring": None, "region": None,
"countywide": [...]}; region packing happens in build_region.py.
"""
import glob
import re
import struct
import sys
from pathlib import Path

import duckdb
import openpyxl

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = Path(__file__).resolve().parent / "recipes_statewide.py"
REPORT = ROOT / "data" / "build" / "recipe-review.txt"
PTAD_XLSX = RAW / "ptad-2025-total-rates-levies.xlsx"
COUNTY_ZIP = RAW / "tl_2025_us_county.zip"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_region import HAND_CURATED  # noqa: E402


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


# College districts verified county-coextensive (PTAD-name substring, lowered).
COLLEGE_ALLOWLIST = [
    "dallas county community college", "dallas college",
    "tarrant county college", "tarrant county junior college",
    "collin county community college", "collin college",
    "collin county junior college",
    "el paso community college", "el paso county community college",
    "el paso county junior college",
    "grayson county junior college", "grayson college",
    "midland college", "midland county junior college",
    "odessa college", "ector county junior college",
    "weatherford college", "parker county junior college",
    "mclennan community college", "mclennan county junior college",
    "wharton county junior college",
    "clarendon college",
    "panola county college",
    "western texas college",
    "howard county junior college",
    "vernon college",
    "south texas college",           # Hidalgo listing (county-coextensive)
    "south texas community college", # Starr listing of the same district
]

# Hand-verified county-wide specials that the name heuristics can't catch.
SPECIAL_ALLOWLIST = [
    "harris county fcd",             # Harris County Flood Control District
    "harris county flood control",
    "port of houston authority",
    "harris county department of education",
    "harris co department of education",
    "harris county dept of education",
    "tarrant regional water district",
    "r. e. thomason",                # UMC El Paso's legal name (countywide)
]

HOSPITAL_TYPES = {"11"}
GCD_TYPES = {"06", "23"}
MISC_TYPES = {"33"}
COLLEGE_TYPES = {"15"}


def main():
    ws = openpyxl.load_workbook(PTAD_XLSX, read_only=True)["Statewide"]
    county_names, units = {}, []
    for row in ws.iter_rows(min_row=4, values_only=True):
        name, uid, rate = row[0], row[1], row[2]
        if not uid:
            continue
        name = name.strip().rstrip("*").strip()
        code, num, utype = uid.split("-")
        if num == "000":
            county_names[code] = name
        units.append((uid, name, code, utype, float(rate or 0)))

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    fips_by_name = {
        norm(n): f
        for f, n in con.execute(
            f"""SELECT GEOID, NAME FROM ST_Read('/vsizip/{COUNTY_ZIP}/tl_2025_us_county.shp')
            WHERE STATEFP = '48'"""
        ).fetchall()
    }

    curated_codes = {c["ptad"] for c in HAND_CURATED.values()}
    report, recipes = [], {}
    for code, cname in sorted(county_names.items(), key=lambda kv: kv[1]):
        if code in curated_codes:
            continue
        fips = fips_by_name.get(norm(cname))
        if not fips:
            report.append(f"!! no FIPS match for PTAD county {code} {cname!r}")
            continue
        cw = [f"{code}-000-00"]
        ncounty = norm(cname)
        for uid, name, ucode, utype, rate in units:
            if ucode != code or uid.endswith("-000-00"):
                continue
            nl, nn = name.lower(), norm(name)
            included = False
            if utype in HOSPITAL_TYPES | GCD_TYPES | MISC_TYPES and nn.startswith(ncounty):
                included = True
            elif utype in COLLEGE_TYPES and any(a in nl for a in (x for x in COLLEGE_ALLOWLIST)):
                included = True
            elif any(a in nl for a in SPECIAL_ALLOWLIST):
                included = True
            if included:
                cw.append(uid)
                report.append(f"   {cname}: INCLUDE {uid} {name} ({rate})")
            elif rate >= 0.05 and utype in HOSPITAL_TYPES | GCD_TYPES | MISC_TYPES | COLLEGE_TYPES | {"27", "28", "18", "12"}:
                report.append(f"   {cname}: review-excluded {uid} [{utype}] {name} ({rate})")
        recipes[cname] = {"fips": fips, "ptad": code, "countywide": cw}

    lines = [
        '"""Auto-generated by gen_recipes.py — v0 recipes for counties beyond',
        'the hand-curated set in build_region.py. Regenerate, never hand-edit;',
        'promote corrections into build_region.py COUNTIES instead."""',
        "",
        "STATEWIDE_COUNTIES = {",
    ]
    for cname, r in recipes.items():
        lines.append(
            f'    "{cname}": {{"fips": "{r["fips"]}", "ptad": "{r["ptad"]}", '
            f'"countywide": {r["countywide"]!r}}},'
        )
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n")
    REPORT.write_text("\n".join(report) + "\n")
    print(f"generated {len(recipes)} recipes -> {OUT.name}")
    print(f"review report: {REPORT} ({sum(1 for l in report if 'review-excluded' in l)} exclusions to eyeball)")

    # Parcel-count inventory from DBF headers (for archive packing + splits).
    counts = {}
    for cname, r in recipes.items():
        pat = str(RAW / f"stratmap_{r['fips']}/**/*.dbf")
        hits = glob.glob(pat, recursive=True)
        if not hits:
            counts[cname] = 0
            continue
        counts[cname] = struct.unpack("<I", Path(hits[0]).read_bytes()[4:8])[0]
    big = sorted(counts.items(), key=lambda kv: -kv[1])[:12]
    print("largest new counties:", ", ".join(f"{n} {c:,}" for n, c in big))
    print("new parcels total:", f"{sum(counts.values()):,}")


if __name__ == "__main__":
    main()
