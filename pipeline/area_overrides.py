#!/usr/bin/env python3
"""Turn proven CAD area totals into per-area rate corrections for the build.

`compare_cad_rates.py` decomposes each combined rate a CAD publishes back into
the exact units that sum to it, and reports which of those units the map is
missing for parcels in that area. Where the decomposition is unique, that is a
citable fact about a specific (county, city, school district) area — not a
guess — so it can be applied directly.

This writes `area_extra`: for a (county, city boundary name, ISD boundary name)
area, the extra rate the map should be adding and the units it comes from.
`build_region.py` picks it up the same way it picks up `parcel_special`.

Only corrections that satisfy all of the following are emitted:
  * the published total decomposed to exactly one unit set
  * every extra unit in that set is one `audit_coverage.py` flags as missing
  * the gap between the published total and the map's rate for that same area
    equals the sum of those missing units (so nothing else is going on)

Output: data/build/area-overrides.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "build" / "taxmap.duckdb"
CAD = ROOT / "data" / "build" / "cad-vs-app.json"
OUT = ROOT / "data" / "build" / "area-overrides.json"
TOL = 0.0006


def build(write_table=True):
    report = json.loads(CAD.read_text())
    con = duckdb.connect(str(DB), read_only=not write_table)

    city_by_unit, isd_by_unit = {}, {}
    for county, cn, uid in con.execute(
            "SELECT county, city_name, unit_id FROM city_rate_map "
            "WHERE unit_id IS NOT NULL").fetchall():
        city_by_unit.setdefault((county, uid), []).append(cn)
    for county, inm, uid in con.execute(
            "SELECT county, isd_name, unit_id FROM isd_rate_map "
            "WHERE unit_id IS NOT NULL").fetchall():
        isd_by_unit.setdefault((county, uid), []).append(inm)

    rows, skipped, optional, untrusted = [], 0, 0, []
    for county, r in sorted(report.items()):
        missing = {m["unit_id"]: m for m in r["missing_jurisdictions"]}

        # Guard against the wrong document. Several CADs publish a multi-year
        # rate history; a stale row can still happen to decompose cleanly, so
        # require that the chosen table's per-unit rates agree with PTAD and
        # that most of its published totals resolve at all.
        recon = r["reconciliation"]
        solved_frac = (sum(1 for rc in recon if rc.get("solved")) / len(recon)
                       if recon else 0)
        if recon and (r.get("cad_table_trust", 0) < 0.6 or solved_frac < 0.6):
            untrusted.append(county)
            continue

        # A county that publishes both "GKE/SBN/WCC" and "GKE/SBN/WCC/MCD" is
        # telling us the MUD applies to *part* of that school district's area,
        # not all of it. Only areas with a single published total are safe to
        # key off (city, ISD) alone — anything else needs the district's real
        # boundary, so it is reported but not applied.
        per_area = {}
        for rc in r["reconciliation"]:
            if rc.get("solved"):
                per_area.setdefault((rc.get("isd_unit"), rc.get("city_unit")),
                                    []).append(rc)

        for rc in r["reconciliation"]:
            if rc.get("ok") or not rc.get("solved") or rc.get("delta") is None:
                continue
            if len(per_area.get((rc.get("isd_unit"), rc.get("city_unit")), [])) > 1:
                optional += 1
                continue
            extras = rc.get("extras") or []
            gap = rc["delta"]
            # every extra must be a unit we know is missing, and they must
            # account for the whole gap
            by_name = {e["name"]: e for e in extras}
            cand = [e for e in extras
                    if any(m["name"] == e["name"] for m in missing.values())]
            if not cand or abs(sum(e["rate"] for e in cand) - gap) > TOL:
                skipped += 1
                continue
            unit_ids = [uid for uid, m in missing.items() if m["name"] in by_name]
            # Same-rate districts are interchangeable in a total, so record the
            # alternatives rather than pretending we know which one it is.
            alts = {}
            for uid in unit_ids:
                same = [m["name"] for u2, m in missing.items()
                        if u2 != uid and abs(m["rate"] - missing[uid]["rate"]) < 1e-9
                        and m["type"] == missing[uid]["type"]]
                if same:
                    alts[missing[uid]["name"]] = same
            rows.append({
                "same_rate_alternatives": alts,
                "county": county, "ptad": r["ptad"], "fips": r["fips"],
                "area": rc["published"],
                # The StratMap boundary names the build actually keys on — a
                # PTAD unit can be reached from several of them.
                "isd_names": isd_by_unit.get((county, rc.get("isd_unit"))) or [],
                "city_names": (city_by_unit.get((county, rc.get("city_unit")))
                               if rc.get("city_unit") else [None]) or [None],
                "isd": rc.get("isd"), "city": rc.get("city"),
                "extra_rate": round(gap, 6),
                "units": [{"unit_id": u, "name": missing[u]["name"],
                           "type": missing[u]["type_label"],
                           "rate": missing[u]["rate"]} for u in unit_ids],
                "published_total": rc["published_rate"],
                "map_total_before": rc["app_rate"],
                "parcels": rc["app_parcels"],
                "src": rc["src"],
            })

    OUT.write_text(json.dumps(rows, indent=1))
    counties = sorted({r["county"] for r in rows})
    parcels = sum(r["parcels"] or 0 for r in rows)
    print(f"{len(rows)} proven area corrections across {len(counties)} counties")
    print(f"  parcels affected: {parcels:,}")
    print(f"  skipped (gap not fully explained): {skipped}")
    print(f"  skipped (district covers only part of the area): {optional}")
    print(f"  skipped (rate sheet not trustworthy / wrong year): {len(untrusted)}" + (f" — {', '.join(sorted(untrusted))}" if untrusted else ""))
    for c in counties:
        cr = [r for r in rows if r["county"] == c]
        print(f"  {c:14s} {len(cr)} areas  +{max(r['extra_rate'] for r in cr):.4f} max")
    print(f"-> {OUT}")
    return rows


if __name__ == "__main__":
    sys.exit(0 if build() is not None else 1)
