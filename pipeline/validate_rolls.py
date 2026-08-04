#!/usr/bin/env python3
"""Decide which ingested rolls are safe to switch on.

A roll only helps if three things hold, and each has failed before:

  1. JOIN — the roll's prop_id has to be the same account number StratMap
     carries as Prop_ID. Where a CAD renumbered or uses a formatted key
     ("12-3200-2002-20700-3"), the join silently produces almost nothing.
  2. MATCH — each roll entity name has to resolve to a PTAD taxing unit, or
     its rate is dropped and the parcel comes out UNDER-stated, which is worse
     than the spatial approximation it would replace.
  3. SANITY — the roll rate should agree with the spatial rate except for the
     special districts we know are missing. A roll rate *below* spatial, or a
     county-level shift, means the matcher grabbed the wrong units.

Counties passing all three are printed as a ready-to-paste ROLL_COUNTIES list;
the rest are reported with the reason so they can be fixed rather than
silently shipped.

    python pipeline/validate_rolls.py [--min-join 0.80] [--only Travis]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_region import HAND_CURATED  # noqa: E402
from recipes_statewide import STATEWIDE_COUNTIES  # noqa: E402
from roll_rates import SKIP_CODES, build_matcher  # noqa: E402

DB = ROOT / "data" / "build" / "taxmap.duckdb"
OUT = ROOT / "data" / "build" / "roll-validation.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-join", type=float, default=0.80,
                    help="minimum share of a county's parcels the roll reaches")
    ap.add_argument("--min-complete", type=float, default=0.85,
                    help="minimum share of roll parcels with a complete stack")
    ap.add_argument("--only")
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    # build_matcher's county-adjacency pool needs ST_Intersects; without it
    # every cross-county ISD, city and district silently fails to match.
    con.execute("INSTALL spatial; LOAD spatial;")
    ptad_code = {n: c["ptad"] for n, c in HAND_CURATED.items()}
    for n, c in STATEWIDE_COUNTIES.items():
        ptad_code.setdefault(n, c["ptad"])

    counties = [r[0] for r in con.execute(
        "SELECT DISTINCT county FROM roll_entities ORDER BY 1").fetchall()]
    if args.only:
        want = {s.strip().lower() for s in args.only.split(",")}
        counties = [c for c in counties if c.lower() in want]
    print(f"validating {len(counties)} ingested rolls\n")

    match = build_matcher(con, ptad_code)
    report, passed = {}, []
    for county in counties:
        code = ptad_code.get(county)
        if not code:
            report[county] = {"ok": False, "why": "county not in any recipe"}
            continue

        # 1. join — what share of the county's PARCELS does the roll reach?
        # Measuring the other direction is wrong: a roll also lists business
        # personal property, mineral and mobile-home accounts that have no land
        # parcel at all, so a healthy roll never fully "hits".
        # Travis (and others) export Prop_ID='0' for parcels with no account
        # number; those can never join and are excluded from the denominator.
        joined, parcels, roll_props = con.execute(
            """SELECT count(*) FILTER (WHERE r.prop_id IS NOT NULL),
                      count(*),
                      (SELECT count(DISTINCT prop_id) FROM roll_entities
                       WHERE county = ?)
               FROM (SELECT DISTINCT prop_id FROM parcels_all
                     WHERE county = ? AND prop_id IS NOT NULL
                       AND prop_id NOT IN ('0', '')) p
               LEFT JOIN (SELECT DISTINCT prop_id FROM roll_entities
                          WHERE county = ?) r ON r.prop_id = p.prop_id""",
            [county, county, county]).fetchone()
        join_rate = joined / parcels if parcels else 0

        # 2. match — every distinct entity name, once
        names = [r[0] for r in con.execute(
            "SELECT DISTINCT entity_name FROM roll_entities "
            "WHERE county = ? AND entity_code NOT IN ('CAD','APR')",
            [county]).fetchall()]
        hits = {n: match(code, n) for n in names}
        matched = sum(1 for v in hits.values() if v)
        match_rate = matched / len(names) if names else 0
        esd_units = sorted({v[0] for v in hits.values() if v and v[2] == "40"})
        unmatched = sorted(n for n, v in hits.items() if not v)[:12]

        # 3. sanity — roll rate vs the rate the map shows today
        rated = {}
        for pid, ecode, ename in con.execute(
                "SELECT prop_id, entity_code, entity_name FROM roll_entities "
                "WHERE county = ?", [county]).fetchall():
            if ecode in SKIP_CODES:
                continue
            hit = hits.get(ename)
            if hit:
                rated.setdefault(pid, {})[hit[0]] = (hit[1], hit[2])
        clean = {}
        bled = 0
        for pid, units in rated.items():
            # Same completeness rule roll_rates.py applies: exactly one school
            # district, at most one city, and the county unit present. Anything
            # else means a name failed to resolve and the total is short.
            if sum(1 for _, ut in units.values() if ut == "02") != 1 or \
               sum(1 for _, ut in units.values() if ut == "03") > 1 or \
               sum(1 for _, ut in units.values() if ut == "00") < 1:
                bled += 1
                continue
            clean[pid] = round(sum(r for r, _ in units.values()), 4)

        cur = dict(con.execute(
            "SELECT prop_id, round(nominal_rate, 4) FROM parcels_rated "
            "WHERE county = ?", [county]).fetchall())
        deltas = [clean[p] - cur[p] for p in clean if p in cur]
        deltas.sort()
        n = len(deltas)
        med = deltas[n // 2] if n else None
        lower = sum(1 for d in deltas if d < -0.0005) / n if n else 0

        # Unmatched NAMES are not themselves a problem: volunteer fire
        # departments, the CAD's own account and county road funds have no PTAD
        # rate and correctly contribute nothing. What matters is whether each
        # PARCEL ends up with a complete stack.
        complete = len(clean) / len(rated) if rated else 0
        ok = (join_rate >= args.min_join and complete >= args.min_complete
              and n > 0 and lower < 0.05)
        why = []
        if join_rate < args.min_join:
            why.append(f"roll covers only {join_rate:.0%} of parcels")
        if complete < args.min_complete:
            why.append(f"only {complete:.0%} of parcels get a complete stack")
        if not n:
            why.append("no parcels in common with the current build")
        elif lower >= 0.05:
            why.append(f"{lower:.0%} of parcels would go DOWN — suspect matching")

        report[county] = {
            "ok": ok, "why": "; ".join(why),
            "roll_properties": roll_props, "parcels_joined": joined,
            "join_rate": round(join_rate, 4), "joinable_parcels": parcels,
            "entity_names": len(names), "matched": matched,
            "match_rate": round(match_rate, 4),
            "unmatched_examples": unmatched,
            "esd_units_matched": esd_units,
            "complete_share": round(complete, 4),
            "comparable_parcels": n,
            "median_delta": round(med, 4) if med is not None else None,
            "share_lower": round(lower, 4),
            "parser_bleed_dropped": bled,
        }
        flag = "ok " if ok else "SKIP"
        print(f"  {flag} {county:14s} join {join_rate:5.1%}  complete {complete:5.1%}"
              f"  median {('%+.4f' % med) if med is not None else '   n/a'}"
              f"  ESD {len(esd_units)}  {report[county]['why']}")
        if ok:
            passed.append(county)

    OUT.write_text(json.dumps(report, indent=1, sort_keys=True))
    print(f"\n{len(passed)}/{len(counties)} rolls pass")
    print("ROLL_COUNTIES = [")
    for c in passed:
        print(f'    "{c}",')
    print("]")
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
