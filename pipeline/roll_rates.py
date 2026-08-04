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
    # Freeport / property-type qualifiers a CAD appends to its own entity names
    # ("LUFKIN ISD (FP)", "ANGELINA COUNTY (FP)") are not part of the unit.
    s = re.sub(r"\((?:fp|rp|pp|mn|bpp)\)", " ", s)
    s = s.replace("independent school district", "isd").replace("i.s.d.", "isd")
    s = s.replace("consolidated isd", "isd").replace("cisd", "isd")
    # Some rolls spell school districts out in full ("Bells School District"),
    # and "district" is a stop word, so without this they normalise to
    # "bellsschool" and never reach "Bells ISD".
    s = s.replace("school district", "isd").replace("school dist", "isd")
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


# A county and its seat routinely share a name — PTAD carries both "Kaufman"
# (county, type 00) and "Kaufman" (city, type 03) — and `_norm` strips the very
# word that tells them apart. Without a type hint, "KAUFMAN COUNTY" matches
# whichever happens to come first, which silently swapped the county rate for
# the city rate on every parcel in the county.
_TYPE_HINTS = [
    ("02", r"\bisd\b|\bcisd\b|school"),
    ("40", r"\besd\b|emerg\w*\s+serv"),
    ("04", r"\bmud\b|municipal\s+utility"),
    ("19", r"\bwcid\b|water\s+control"),
    ("13", r"\bfwsd\b|fresh\s*water|\bfwd\b"),
    ("11", r"\bhospital\b|memorial"),
    ("15", r"\bcollege\b"),
    ("09", r"\bpid\b|public\s+improve"),
    ("06", r"groundwater|ground\s+water|\bgcd\b|\bwcd\b"),
    ("03", r"^\s*(city|town|village)\s+of\b|\bcity\s+of\b"),
    ("00", r"\bcount(y|ies)\b|\bco\b"),
]


def _type_hint(name):
    for code, pat in _TYPE_HINTS:
        if re.search(pat, name or "", re.I):
            return code
    return None


def build_matcher(con, ptad_code):
    """Return match(county_code, entity_name) -> (unit_name, rate, type) or None."""
    name_of_code = {c: n for n, c in ptad_code.items()}
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
    except Exception as e:  # noqa: BLE001
        # Without adjacency, every district/ISD/city that straddles a county
        # line stops matching and the parcels carrying it come out short. That
        # is far too damaging to swallow quietly — the usual cause is the
        # spatial extension not being loaded on this connection.
        print(f"  WARNING: county adjacency unavailable ({type(e).__name__}: "
              f"{e}); cross-county entities will NOT match")
        adj = {}

    norm_cache = {}

    def nc(x):
        v = norm_cache.get(x)
        if v is None:
            v = _norm(x)
            norm_cache[x] = v
        return v

    def match(county_code, entity_name, _retry=False):
        """Return (unit_name, rate, unit_type) or None. Resolve within the
        parcel's OWN county first (exact → ESD-number → fuzzy), only then fall
        back to adjacent counties — otherwise a numbered ESD/WCID would match
        a same-numbered district in a neighboring county (e.g. Wilson's 'ESD 1'
        wrongly hitting Atascosa ESD #1)."""
        own = [(un, ur, ut) for (un, ur, ut) in ptad.get(county_code, []) if ur > 0]
        near = [(un, ur, ut) for cc in adj.get(county_code, set())
                for (un, ur, ut) in ptad.get(cc, []) if ur > 0]
        nn = nc(entity_name)
        ek = _esd_key(entity_name)
        hint = _type_hint(entity_name)
        for cands in (own, near):
            # Within each stage, a candidate whose PTAD unit type agrees with
            # the hint read off the roll name wins over one that merely has the
            # same normalised text.
            exact = [(un, ur, ut) for un, ur, ut in cands if nc(un) == nn]
            if exact:
                if hint:
                    typed = [c for c in exact if c[2] == hint]
                    if typed:
                        return typed[0]
                    # An exact-text match of the WRONG type is the county/city
                    # trap; keep looking rather than returning it.
                    if any(c[2] in ("00", "03") for c in exact) and \
                            hint in ("00", "03"):
                        continue
                return exact[0]
            if ek:
                for un, ur, ut in cands:
                    if _esd_key(un) == ek:
                        return (un, ur, ut)
            # A type hint PREFERS a candidate, it never excludes one. The hints
            # are read off free text and are routinely wrong about which PTAD
            # type a district is filed under (a "WCD" may be filed as a
            # conservation district, not a groundwater one), so filtering on
            # them drops matches that the plain fuzzy pass used to find.
            best = None
            for un, ur, ut in cands:
                r = SequenceMatcher(None, nn, nc(un)).ratio()
                if r < 0.88:
                    continue
                agree = hint is not None and ut == hint
                if not agree and r < 0.9:
                    continue
                score = r + (0.05 if agree else 0.0)
                if best is None or score > best[3]:
                    best = (un, ur, ut, score)
            if best:
                return (best[0], best[1], best[2])

        # Rolls often name their own county's districts without the county
        # prefix PTAD uses — Victoria's roll says "Navigation District" where
        # PTAD says "Victoria County Navigation District". Retry once with the
        # prefix supplied.
        cname = name_of_code.get(county_code)
        if cname and not _retry and not re.search(
                rf"\b{re.escape(cname.lower())}\b", (entity_name or "").lower()):
            return match(county_code, f"{cname} County {entity_name}", True)
        return None

    return match


# Counties whose ingested roll passes validate_rolls.py: the roll reaches
# >=80% of the county's parcels, >=85% of those get a complete unit stack, and
# <5% come out below the spatial estimate they replace. Regenerate with
# `python pipeline/validate_rolls.py` after ingesting new rolls.
ROLL_COUNTIES = [
    "Angelina", "Brown", "Caldwell", "Camp", "Grayson", "Gregg", "Guadalupe",
    "Hardin", "Hill", "Hockley", "Lavaca", "Milam", "Nueces", "San Jacinto",
    "Shackelford", "Shelby", "Taylor", "Travis", "Wise", "Yoakum",
    # Two exceptions, both already live before this list was validated:
    # Bandera fails only the "goes down" check, and that drop is a FIX — its
    #   roll says "BANDERA COUNTY", which used to match PTAD's identically
    #   named CITY of Bandera (0.569939) instead of the county (0.5304), so
    #   every parcel in the county was overstated by exactly 0.0395.
    # Wilson sits at 77% complete because its line-printer roll parses noisily;
    #   its median delta is 0.0000, and the incomplete parcels now fall back to
    #   the spatial rate rather than shipping short.
    "Bandera", "Wilson",
]


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
            n_county = sum(1 for r, ut in units.values() if ut == "00")
            # >1 ISD or >1 city is physically impossible → parser bled entities
            # across a page break; fall back to the spatial rate for this parcel.
            # ZERO ISD or zero county means an entity name failed to resolve, so
            # the sum is missing a real unit — that understates the parcel, which
            # is worse than the spatial estimate it would replace. Fall back too.
            if n_isd != 1 or n_city > 1 or n_county < 1:
                dropped += 1
                continue
            kept += 1
            total = round(sum(r for r, _ in units.values()), 4)
            isd = round(sum(r for r, ut in units.values() if ut == "02"), 4)
            stack = "; ".join(f"{n}={r}" for n, (r, _) in sorted(units.items()))
            rows.append((county, pid, total, isd, stack))
        print(f"roll rates {county}: {len(name_hit)} entity names, {matched_units} matched; "
              f"{kept} parcels rated, {dropped} dropped (parser bleed)")
    if rows:
        # Columnar insert, not executemany — binding these row by row takes
        # hours at this volume (see ingest_rolls.py for the same fix).
        import pyarrow as pa
        con.register("roll_rated_batch", pa.table({
            "county": pa.array([r[0] for r in rows], pa.string()),
            "prop_id": pa.array([r[1] for r in rows], pa.string()),
            "nominal_rate": pa.array([r[2] for r in rows], pa.float64()),
            "isd_rate": pa.array([r[3] for r in rows], pa.float64()),
            "stack": pa.array([r[4] for r in rows], pa.string()),
        }))
        con.execute("INSERT INTO roll_rated SELECT * FROM roll_rated_batch")
        con.unregister("roll_rated_batch")
    print(f"roll rates: {len(rows)} clean parcels across {len(ROLL_COUNTIES)} counties")
