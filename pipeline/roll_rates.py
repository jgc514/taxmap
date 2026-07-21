#!/usr/bin/env python3
"""Phase 2: compute EXACT per-parcel tax rates from parsed CAD appraisal rolls.

For counties whose appraisal roll is ingested (roll_entities table, produced by
parse_ta_roll.py), each parcel's authoritative taxing-unit stack is known — so
its nominal rate is the sum of its actual entities' PTAD rates. This captures
ESDs, PIDs, MUDs, and every other special district EXACTLY (no spatial
approximation) and supersedes the boundary-join rate for that county.

build_region.py imports build_roll_rated(con) to populate:
  roll_rated(county, prop_id, nominal_rate, isd_rate, stack)
where `stack` is a "Name=rate; …" itemization for the popup breakdown.

Entity → PTAD-unit matching: normalized-name exact, then ESD-by-number, then a
>=0.9 fuzzy fallback, over a candidate pool of the parcel county + adjacent
counties (districts/ISDs/cities legitimately span county lines). Only PTAD
units with rate>0 are eligible, so non-taxing roll entities (the CAD itself,
volunteer fire departments, county-bundled road accounts) correctly add
nothing. `CAD`/`APR` placeholder codes are always skipped.
"""
import re
from difflib import SequenceMatcher

STOP = {"city", "of", "the", "county", "area", "number", "no", "district",
        "underground", "conservation", "co", "dist", "ranch"}
SKIP_CODES = {"CAD", "APR"}


def _norm(s):
    s = (s or "").lower()
    s = re.sub(r"\s+\d{4,}\s*$", "", s)  # trailing levy/geo code on roll names
    s = s.replace("independent school district", "isd").replace("i.s.d.", "isd")
    s = s.replace("consolidated isd", "isd").replace("cisd", "isd")
    s = s.replace("municipal utility district", "mud")
    s = s.replace("water control and improvement district", "wcid")
    s = s.replace("water improvement district", "wcid").replace("water district", "wcid")
    s = s.replace("emergency services district", "esd").replace("emergency service district", "esd")
    s = s.replace("public utility district", "pud").replace("p.u.d.", "pud")
    s = s.replace("hospital", "hosp").replace("hosp", "hosp")
    s = s.replace("u.c.", "universalcity").replace("universal city", "universalcity")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return "".join(t for t in s.split() if t not in STOP)


def _esd_key(s):
    m = re.search(r"esd\s*#?\s*(\d+)", (s or "").lower())
    return f"esd{m.group(1)}" if m else None


def build_matcher(con, ptad_code):
    """Return match(county, entity_name) -> (unit_name, rate) or None."""
    ptad = {}
    for cc, name, rate, ut in con.execute(
        "SELECT county_code,name,rate_per_100,unit_type FROM taxing_units"
    ).fetchall():
        ptad.setdefault(cc, []).append((name, float(rate), ut))
    # PTAD-code adjacency from county geometry (county_bounds must be loaded):
    # a roll entity's rate can live under a neighboring county's PTAD code when
    # the district/ISD/city straddles the line, so the candidate pool spans them.
    adj = {}
    try:
        fips_code = {
            fips: ptad_code[cn]
            for fips, cn in con.execute("SELECT fips, county_name FROM county_bounds").fetchall()
            if cn in ptad_code
        }
        for a, b in con.execute(
            """SELECT a.fips,b.fips FROM county_bounds a JOIN county_bounds b
            ON a.fips<b.fips AND ST_Intersects(a.geom,b.geom)"""
        ).fetchall():
            ca, cb = fips_code.get(a), fips_code.get(b)
            if ca and cb:
                adj.setdefault(ca, set()).add(cb)
                adj.setdefault(cb, set()).add(ca)
    except Exception:
        adj = {}

    norm_cache = {}

    def nc(x):
        v = norm_cache.get(x)
        if v is None:
            v = _norm(x)
            norm_cache[x] = v
        return v

    def match(county_code, entity_name):
        """Return (unit_name, rate, unit_type) or None."""
        pool_codes = {county_code} | adj.get(county_code, set())
        cands = [(un, ur, ut) for cc in pool_codes for (un, ur, ut) in ptad.get(cc, []) if ur > 0]
        nn = nc(entity_name)
        for un, ur, ut in cands:
            if nc(un) == nn:
                return (un, ur, ut)
        ek = _esd_key(entity_name)
        if ek:
            for un, ur, ut in cands:
                if _esd_key(un) == ek:
                    return (un, ur, ut)
        best = None
        for un, ur, ut in cands:
            r = SequenceMatcher(None, nn, nc(un)).ratio()
            if r >= 0.9 and (best is None or r > best[3]):
                best = (un, ur, ut, r)
        return (best[0], best[1], best[2]) if best else None

    return match


# Counties whose rolls are ingested into roll_entities.
ROLL_COUNTIES = ["Wilson", "Bandera", "Guadalupe"]


def build_roll_rated(con, ptad_code):
    """Populate roll_rated(county, prop_id, nominal_rate, isd_rate, stack)."""
    have = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name='roll_entities'"
    ).fetchone()[0]
    con.execute(
        """CREATE OR REPLACE TABLE roll_rated(
           county TEXT, prop_id TEXT, nominal_rate DOUBLE, isd_rate DOUBLE, stack TEXT)"""
    )
    if not have:
        print("roll rates: no roll_entities table")
        return
    match = build_matcher(con, ptad_code)
    rows = []
    for county in ROLL_COUNTIES:
        code = ptad_code.get(county)
        if not code:
            continue
        ent = con.execute(
            "SELECT prop_id, entity_code, entity_name FROM roll_entities WHERE county=?",
            [county],
        ).fetchall()
        # resolve distinct entity names once → {unit_name: (rate, utype)} per parcel
        by_prop = {}
        name_hit = {}
        for pid, ecode, ename in ent:
            if ecode in SKIP_CODES:
                continue
            if ename not in name_hit:
                name_hit[ename] = match(code, ename)
            hit = name_hit[ename]
            if not hit:
                continue
            by_prop.setdefault(pid, {})[hit[0]] = (hit[1], hit[2])  # dedupe by unit name
        matched_units = sum(1 for v in name_hit.values() if v)
        kept = dropped = 0
        for pid, units in by_prop.items():
            n_isd = sum(1 for r, ut in units.values() if ut == "02")
            n_city = sum(1 for r, ut in units.values() if ut == "03")
            # >1 ISD or >1 city is physically impossible → parser bled entities
            # across a page break; fall back to the spatial rate for this parcel.
            if n_isd > 1 or n_city > 1:
                dropped += 1
                continue
            kept += 1
            total = round(sum(r for r, _ in units.values()), 4)
            isd = round(sum(r for r, ut in units.values() if ut == "02"), 4)
            stack = "; ".join(f"{n}={r}" for n, (r, _) in sorted(units.items()))
            rows.append((county, pid, total, isd, stack))
        print(f"roll rates {county}: {len(name_hit)} entity names, {matched_units} matched; "
              f"{kept} parcels rated, {dropped} dropped (parser bleed)")
    con.executemany("INSERT INTO roll_rated VALUES (?,?,?,?,?)", rows)
    print(f"roll rates: {len(rows)} clean parcels across {len(ROLL_COUNTIES)} counties")
