#!/usr/bin/env python3
"""Audit, per county, which PTAD taxing units the app actually reflects.

The app's nominal rate for a parcel is
    county base (recipe `countywide` unit ids)
  + city  (spatial: parcels_all.city_name -> city_rate_map.unit_id)
  + ISD   (spatial: parcels_all.isd_name  -> isd_rate_map.unit_id)
  + special (TCEQ water-district polygon -> wd_rate_map.unit_id)
  [ overridden by roll_rated for counties whose appraisal roll we parsed ]

Anything in the PTAD workbook for that county that appears in none of those
sets is a jurisdiction the map silently drops. This script enumerates them.

Output: data/build/coverage-audit.json + a printed summary.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_region import HAND_CURATED  # noqa: E402
from recipes_statewide import STATEWIDE_COUNTIES  # noqa: E402
from roll_rates import ROLL_COUNTIES  # noqa: E402

DB = ROOT / "data" / "build" / "taxmap.duckdb"
OUT = ROOT / "data" / "build" / "coverage-audit.json"
TAX_YEAR = 2025

# PTAD unit-type codes (Comptroller "Unit Type" in the rates & levies workbook).
TYPE_LABEL = {
    "00": "county", "02": "school", "03": "city", "04": "MUD",
    "05": "utility district", "06": "groundwater district",
    "07": "levee improvement", "08": "drainage district", "09": "PID/SID",
    "10": "road district", "11": "hospital district", "12": "flood control",
    "13": "FWSD", "14": "public utility district", "15": "college",
    "18": "navigation/port", "19": "WCID", "20": "water supply district",
    "21": "water authority/watershed", "22": "irrigation district",
    "23": "conservation district", "24": "municipal water authority",
    "25": "municipal water district", "26": "water improvement district",
    "27": "misc special", "28": "reclamation district", "30": "limited district",
    "33": "county education/misc", "40": "emergency services district (ESD)",
    "48": "management district (MMD)", "50": "solid waste",
    "51": "development district", "52": "economic development",
}


def main():
    con = duckdb.connect(str(DB), read_only=True)

    units = con.execute(
        "SELECT unit_id, name, county_code, unit_type, rate_per_100 "
        "FROM taxing_units WHERE tax_year = ?", [TAX_YEAR]).fetchall()
    by_county = defaultdict(list)
    county_name_of = {}
    for uid, name, cc, ut, rate in units:
        by_county[cc].append((uid, name, ut, rate or 0.0))
        if ut == "00":
            county_name_of[cc] = name

    recipes = {}
    for name, c in HAND_CURATED.items():
        recipes[name] = c
    for name, c in STATEWIDE_COUNTIES.items():
        recipes.setdefault(name, c)

    # Unit ids the spatial joins actually attach, per county name.
    used = defaultdict(set)
    for table, col in (("city_rate_map", "unit_id"), ("isd_rate_map", "unit_id"),
                       ("wd_rate_map", "unit_id")):
        for county, uid in con.execute(
                f"SELECT DISTINCT county, {col} FROM {table} "
                f"WHERE {col} IS NOT NULL").fetchall():
            used[county].add(uid)

    # Roll counties get their exact per-parcel stack; treat every unit that
    # appears in a roll stack as covered there.
    roll_units = defaultdict(set)
    try:
        for county, stack in con.execute(
                "SELECT DISTINCT county, stack FROM roll_rated").fetchall():
            for part in (stack or "").split(";"):
                part = part.strip()
                if "=" in part:
                    roll_units[county].add(part.rsplit("=", 1)[0].strip())
    except duckdb.CatalogException:
        pass

    report, totals = {}, defaultdict(lambda: [0, 0.0])
    for county, cfg in sorted(recipes.items()):
        cc = cfg["ptad"]
        base = set(cfg.get("countywide", []))
        covered = base | used.get(county, set())
        is_roll = county in ROLL_COUNTIES
        missing = []
        for uid, name, ut, rate in sorted(by_county.get(cc, []),
                                          key=lambda r: -(r[3] or 0)):
            if uid in covered or rate <= 0:
                continue
            # school and city units are matched by name through the spatial
            # boundary layers; a miss there is a name-match bug, still report it
            missing.append({"unit_id": uid, "name": name, "type": ut,
                            "type_label": TYPE_LABEL.get(ut, ut),
                            "rate": round(rate, 6)})
            totals[ut][0] += 1
            totals[ut][1] += rate
        esd = [m for m in missing if m["type"] == "40"]
        esd_rates = {round(e["rate"], 6) for e in esd}
        report[county] = {
            "ptad": cc, "fips": cfg["fips"],
            "roll_verified": is_roll,
            "n_units_ptad": len([u for u in by_county.get(cc, []) if u[3] > 0]),
            "n_covered": len(covered),
            "missing": missing,
            "missing_rate_sum": round(sum(m["rate"] for m in missing), 6),
            "esd_count": len(esd),
            "esd_rate_uniform": (round(esd[0]["rate"], 6)
                                 if esd and len(esd_rates) == 1 else None),
            "esd_min": round(min((e["rate"] for e in esd), default=0), 6),
            "esd_max": round(max((e["rate"] for e in esd), default=0), 6),
        }

    OUT.write_text(json.dumps(report, indent=1, sort_keys=True))

    print(f"=== missing taxing units statewide ({TAX_YEAR}) ===")
    for ut, (n, tot) in sorted(totals.items(), key=lambda kv: -kv[1][1]):
        print(f"  {TYPE_LABEL.get(ut, ut):36s} {n:5d} units   "
              f"sum {tot:8.3f}   avg {tot / n:.4f}")

    esd_fix = [c for c, r in report.items()
               if r["esd_count"] and r["esd_rate_uniform"] is not None]
    esd_amb = [c for c, r in report.items()
               if r["esd_count"] and r["esd_rate_uniform"] is None]
    print(f"\nESD gaps: {len(esd_fix) + len(esd_amb)} counties")
    print(f"  unambiguous (one ESD, or all ESDs same rate): {len(esd_fix)}")
    print(f"  needs boundaries (ESD rates differ):          {len(esd_amb)}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
