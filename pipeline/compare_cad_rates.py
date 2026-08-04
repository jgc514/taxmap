#!/usr/bin/env python3
"""Compare what the map shows against what county appraisal districts publish.

Three independent checks per county:

  A. JURISDICTION COVERAGE — every PTAD taxing unit with a rate that the app
     attaches to no parcel (from audit_coverage.py), cross-referenced against
     the same entity appearing on the CAD's own published rate sheet.

  B. RATE ACCURACY — for units the app does use, does the rate we carry (PTAD
     2025) equal the rate the CAD publishes? Flags anything off by >0.0005.

  C. TOTAL-RATE RECONCILIATION — the strongest check. Most CADs publish a
     "totaled tax rates" block enumerating every valid jurisdiction combination
     in the county ("Blanco out of the City  1.349408"). Those totals are
     exactly what a parcel's rate should be. We match each published total to
     the nearest distinct rate the app actually renders in that county and
     report the gap.

Inputs : data/build/cad-rates.json, data/build/coverage-audit.json, taxmap.duckdb
Output : data/build/cad-vs-app.json  +  docs/RATE-AUDIT.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "build" / "taxmap.duckdb"
CAD = ROOT / "data" / "build" / "cad-rates.json"
AUDIT = ROOT / "data" / "build" / "coverage-audit.json"
OUT = ROOT / "data" / "build" / "cad-vs-app.json"
MD = ROOT / "docs" / "RATE-AUDIT.md"
TAX_YEAR = 2025

TOL = 0.0005          # rate equality tolerance, per $100
BUCKET_TOL = 0.0002   # total-vs-bucket equality tolerance
EPS_SOLVE = 0.0002    # subset-sum tolerance when decomposing a published total

ABBREV = [
    (r"\bindependent school district\b", "isd"),
    (r"\bconsolidated independent school dist(rict)?\b", "isd"),
    (r"\bschool district\b", "isd"),
    (r"\bemergency services? district\b", "esd"),
    (r"\bemerg(ency)? serv(ice)?s? dist\b", "esd"),
    (r"\bmunicipal utility district\b", "mud"),
    (r"\bwater control (and|&) improvement district\b", "wcid"),
    (r"\bfresh water supply district\b", "fwsd"),
    (r"\bgroundwater conservation district\b", "gcd"),
    (r"\bground water conservation district\b", "gcd"),
    (r"\bunderground water conservation district\b", "uwcd"),
    (r"\bpublic improvement district\b", "pid"),
    (r"\bmanagement district\b", "mmd"),
    (r"\bhospital district\b", "hosp"),
    (r"\bjunior college( district)?\b", "college"),
    (r"\bcommunity college( district)?\b", "college"),
    (r"\bcounty\b", "co"),
    (r"\bcity of\b", ""),
    (r"\btown of\b", ""),
    (r"\bnumber\b", ""),
]


def norm(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"\b(20\d\d|tax year|adopted|rate|total)\b", " ", s)
    for pat, rep in ABBREV:
        s = re.sub(pat, rep, s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


COMBO_HINT = re.compile(r"\b(in|out|outside|inside|within)\b.*\b(city|limits?)\b"
                        r"|/|\+|combined|total", re.I)

# CAD sheets label entities loosely ("Blanco County GBL", "City of Blanco CBL").
# A type hint read off the label is what separates a county unit from the
# identically-named city unit.
TYPE_HINTS = [
    ("02", r"\bisd\b|\bcisd\b|school"),
    ("40", r"\besd\b|emergency\s*serv"),
    ("04", r"\bmud\b|municipal\s*utility"),
    ("19", r"\bwcid\b|water\s*control"),
    ("13", r"\bfwsd\b|fresh\s*water"),
    ("11", r"\bhospital\b|memorial|medical"),
    ("15", r"\bcollege\b"),
    ("09", r"\bpid\b|\bsid\b|public\s*improvement"),
    ("08", r"\bdrainage\b"),
    ("18", r"\bnavigation\b|\bport\b"),
    ("06", r"groundwater|ground\s*water|\bgcd\b|\buwcd\b|\bwcd\b"),
    ("03", r"^\s*(city|town|village)\s+of\b|\bcity\s+of\b"),
    ("00", r"\bcounty\b"),
]


def type_hint(name: str) -> str | None:
    for code, pat in TYPE_HINTS:
        if re.search(pat, name, re.I):
            return code
    return None


def match_unit(cad_name: str, candidates: list[tuple]) -> tuple | None:
    """Best PTAD unit for a CAD label, or None if nothing matches confidently.

    `candidates` are (norm_name, unit_id, ptad_name, unit_type, rate). CAD
    labels routinely carry the district's internal entity code as a suffix
    ("Blanco ISD SBL"), so exact equality alone matches almost nothing --
    containment, scaled by how much of the longer string is explained, plus the
    type hint, is what actually discriminates.
    """
    cn = norm(cad_name)
    if not cn:
        return None
    hint = type_hint(cad_name)
    best, best_score = None, 0.0
    for pn, uid, pname, ut, rate in candidates:
        if not pn:
            continue
        if pn == cn:
            s = 3.0
        elif cn.startswith(pn) or pn.startswith(cn):
            s = 2.0 * len(min(pn, cn, key=len)) / len(max(pn, cn, key=len))
        elif pn in cn or cn in pn:
            s = 1.5 * len(min(pn, cn, key=len)) / len(max(pn, cn, key=len))
        else:
            continue
        if hint:
            s += 0.8 if ut == hint else -0.8
        if s > best_score:
            best, best_score = (uid, pname, ut, rate), s
    return best if best_score >= 1.4 else None


def is_combo(name: str, rate: float, matched: bool) -> bool:
    """A published *total* for an area, not a single jurisdiction's rate."""
    if COMBO_HINT.search(name):
        return True
    if matched:
        return False
    # Bare code stacks like "GKE/SBN/WCC" or totals well above any single unit.
    return rate >= 1.15 and not re.search(r"\bisd\b|school", name, re.I)


def subset_index(extras, max_extra=15):
    """sum → the special-district subsets adding up to it, keyed to 4 decimals."""
    idx = defaultdict(list)
    extras = extras[:max_extra]
    for k in range(0, len(extras) + 1):
        for combo in combinations(extras, k):
            idx[round(sum(e[1] for e in combo), 4)].append(combo)
    return idx


def solve(total, county_rate, isds, cities, idx):
    """Every (isd, city, specials) combination of units summing to `total`.

    Constraints that hold for any Texas parcel: the county unit always applies,
    exactly one school district applies, at most one city applies, and any
    number of special districts may. Solutions that differ only in *which*
    equal-rate district was picked (a county's two 10¢ ESDs, say) are the same
    answer as far as the total goes, so they are collapsed before deciding
    whether the decomposition is unique.
    """
    sols, seen = [], set()
    for isd in isds:
        for city in [None] + cities:
            base = county_rate + isd[1] + (city[1] if city else 0.0)
            need = round(total - base, 4)
            if need < -EPS_SOLVE:
                continue
            for combo in idx.get(need, ()):
                key = (isd[0][0], city[0][0] if city else None,
                       tuple(sorted(round(e[1], 6) for e in combo)))
                if key in seen:
                    continue
                seen.add(key)
                sols.append((isd, city, combo))
    return sols


def group_rate(groups, county, city_names, isd_names):
    """The rate the map shows for parcels in this (city, ISD) area."""
    tally = defaultdict(int)
    for cn in (city_names or [None]):
        for inm in (isd_names or []):
            for rate, n in groups.get((county, cn, inm), {}).items():
                tally[rate] += n
    if not tally:
        return None, 0
    rate = max(tally, key=tally.get)
    return rate, tally[rate]


def main():
    cad = json.loads(CAD.read_text())
    audit = json.loads(AUDIT.read_text())
    con = duckdb.connect(str(DB), read_only=True)

    units = con.execute(
        "SELECT unit_id, name, county_code, unit_type, rate_per_100 "
        "FROM taxing_units WHERE tax_year = ?", [TAX_YEAR]).fetchall()
    ptad = defaultdict(dict)
    ptad_units = defaultdict(list)
    for uid, name, cc, ut, rate in units:
        ptad[cc][norm(name)] = (uid, name, ut, rate or 0.0)
        if (rate or 0) > 0:
            ptad_units[cc].append((uid, name, ut, rate))

    print("reading app rate buckets ...", flush=True)
    buckets = defaultdict(list)
    for county, rate, n in con.execute(
            """SELECT county, round(nominal_rate, 6) AS r, count(*) AS n
               FROM parcels_rated GROUP BY county, r
               HAVING n >= 5 ORDER BY county, n DESC""").fetchall():
        buckets[county].append((rate, n))

    # Rates the map renders per (county, city boundary, ISD boundary) area --
    # the granularity a CAD's published area total is comparable against.
    groups = defaultdict(dict)
    for county, cn, inm, rate, n in con.execute(
            """SELECT county, city_name, isd_name, round(nominal_rate, 6) AS r,
                      count(*) AS n
               FROM parcels_rated GROUP BY county, city_name, isd_name, r""").fetchall():
        groups[(county, cn, inm)][rate] = n

    # A PTAD unit can be reached from several StratMap boundary names.
    city_by_unit, isd_by_unit = defaultdict(list), defaultdict(list)
    for county, cn, uid in con.execute(
            "SELECT county, city_name, unit_id FROM city_rate_map "
            "WHERE unit_id IS NOT NULL").fetchall():
        city_by_unit[(county, uid)].append(cn)
    for county, inm, uid in con.execute(
            "SELECT county, isd_name, unit_id FROM isd_rate_map "
            "WHERE unit_id IS NOT NULL").fetchall():
        isd_by_unit[(county, uid)].append(inm)

    report = {}
    for county, rec in sorted(cad.items()):
        cc = rec.get("ptad")
        a = audit.get(county, {})
        cands = [(k, *v) for k, v in ptad.get(cc, {}).items()]

        # Pick the single most trustworthy table rather than pooling all of
        # them: CAD sites routinely also publish 5-year rate histories and
        # M&O/I&S breakouts, and pooling those manufactures fake disagreements.
        best_table, best_score, trust, best_rows = None, -1.0, 0.0, []
        for t in rec.get("tables", []):
            rows, counts = [], defaultdict(int)
            for nm, rt in t["pairs"]:
                hit = match_unit(nm, cands)
                rows.append((nm, rt, hit))
                if hit:
                    counts[hit[0]] += 1
            hits = [r for r in rows if r[2]]
            if not hits:
                continue
            # rows repeated for a unit ⇒ multi-year history ⇒ untrustworthy
            dupe = sum(1 for r in hits if counts[r[2][0]] > 1) / len(hits)
            agree = sum(1 for r in hits if abs(r[2][3] - r[1]) <= TOL) / len(hits)
            score = len(set(r[2][0] for r in hits)) * agree * (1 - dupe)
            if score > best_score:
                best_table, best_score, trust, best_rows = t, score, agree, rows

        singles, combos = [], []
        seen_unit = set()
        for nm, rt, hit in best_rows:
            row = {"name": nm, "rate": rt, "src": best_table["url"],
                   "unit": hit}
            if is_combo(nm, rt, bool(hit)):
                combos.append(row)
            elif hit and hit[0] not in seen_unit:
                seen_unit.add(hit[0])
                singles.append(row)
            elif not hit:
                singles.append(row)

        # -- B. rate accuracy: CAD single-unit rate vs the PTAD rate we carry.
        # Only asserted when the chosen table mostly agrees with PTAD already;
        # otherwise we flag the county for manual review instead of emitting
        # dozens of parse artefacts as findings.
        mismatches, matched = [], 0
        for s in singles:
            hit = s["unit"]
            if not hit:
                continue
            matched += 1
            if abs(hit[3] - s["rate"]) > TOL and trust >= 0.6:
                mismatches.append({"unit_id": hit[0], "ptad_name": hit[1],
                                   "ptad_rate": round(hit[3], 6),
                                   "cad_name": s["name"], "cad_rate": s["rate"],
                                   "delta": round(s["rate"] - hit[3], 6),
                                   "src": s["src"]})

        # -- A. missing jurisdictions, annotated with CAD confirmation
        cad_by_unit = {s["unit"][0]: s for s in singles if s["unit"]}
        missing = []
        for m in a.get("missing", []):
            conf = cad_by_unit.get(m["unit_id"])
            missing.append({**m, "on_cad_site": bool(conf),
                            "cad_rate": conf["rate"] if conf else None,
                            "src": conf["src"] if conf else None})

        # -- C. published area totals vs the rates the app actually renders.
        # Each published total is solved back into the exact set of units that
        # sums to it (county + one ISD + at most one city + specials). The
        # solved ISD/city identify WHICH parcels the total applies to, so the
        # comparison is like-for-like instead of nearest-number-wins.
        units_here = [(u, u[3]) for u in ptad_units.get(cc, [])]
        county_rate = next((r for u, r in units_here if u[2] == "00"), None)
        isds = [(u, r) for u, r in units_here if u[2] == "02"]
        cities = [(u, r) for u, r in units_here if u[2] == "03"]
        extras = sorted(((u, r) for u, r in units_here
                         if u[2] not in ("00", "02", "03")), key=lambda t: -t[1])
        idx = subset_index(extras)
        all_b = buckets.get(county, [])
        recon = []
        for c in combos:
            if not (0.4 <= c["rate"] <= 4.0) or county_rate is None or not isds:
                continue
            in_app = any(abs(b[0] - c["rate"]) <= BUCKET_TOL for b in all_b)
            sols = solve(c["rate"], county_rate, isds, cities, idx)
            row = {"published": c["name"], "published_rate": c["rate"],
                   "in_app": in_app, "ok": in_app, "src": c["src"],
                   "solved": len(sols) == 1}
            if len(sols) == 1:
                isd, city, ex = sols[0]
                cn = city_by_unit.get((county, city[0][0])) if city else [None]
                inm = isd_by_unit.get((county, isd[0][0]), [])
                app_rate, app_n = group_rate(groups, county, cn, inm)
                row.update({
                    "isd": isd[0][1], "isd_unit": isd[0][0],
                    "city": city[0][1] if city else None,
                    "city_unit": city[0][0] if city else None,
                    "isd_names": inm, "city_names": cn,
                    "extras": [{"name": e[0][1], "type": e[0][2], "rate": e[1]}
                               for e in ex],
                    "app_rate": app_rate, "app_parcels": app_n,
                    "delta": round(c["rate"] - app_rate, 6) if app_rate else None,
                })
                if app_rate is not None:
                    row["ok"] = abs(c["rate"] - app_rate) <= BUCKET_TOL
                    missing_ids = {m["unit_id"] for m in a.get("missing", [])}
                    row["likely_cause"] = ", ".join(
                        e[0][1] for e in ex if e[0][0] in missing_ids) or None
            recon.append(row)
        recon.sort(key=lambda r: (r["ok"], -abs(r.get("delta") or 0)))

        # Does an ESD appear in EVERY area the CAD publishes? That, not a
        # uniform rate, is what licenses adding the ESD county-wide.
        solved = [r for r in recon if r.get("solved") and "extras" in r]
        n_esd_units = sum(1 for u, _ in units_here if u[2] == "40")
        # A sheet whose per-unit rates disagree with PTAD is usually a rate
        # *history*; a stale row can still decompose cleanly, so don't let it
        # vouch for coverage.
        if trust < 0.6 or (recon and len(solved) / len(recon) < 0.6):
            solved = []
        if not n_esd_units:
            esd_cov = "none"
        elif not solved:
            esd_cov = "unknown"
        else:
            has = [any(e["type"] == "40" for e in r["extras"]) for r in solved]
            esd_cov = "countywide" if all(has) else (
                "partial" if any(has) else "not-in-published-areas")

        report[county] = {
            "fips": a.get("fips"), "ptad": cc,
            "cad_docs": rec.get("docs", 0),
            "cad_units_parsed": len(singles),
            "cad_units_matched_to_ptad": matched,
            "cad_table": best_table["url"] if best_table else None,
            "cad_table_trust": round(trust, 3),
            "rate_mismatches": mismatches,
            "missing_jurisdictions": missing,
            "missing_rate_sum": a.get("missing_rate_sum", 0),
            "esd_count": a.get("esd_count", 0),
            "esd_rate_uniform": a.get("esd_rate_uniform"),
            "esd_coverage": esd_cov,
            "areas_solved": len(solved),
            "reconciliation": recon,
            "recon_bad": sum(1 for r in recon if not r["ok"]),
            "roll_verified": a.get("roll_verified", False),
        }

    OUT.write_text(json.dumps(report, indent=1, sort_keys=True))
    write_markdown(report)

    scraped = sum(1 for r in report.values() if r["cad_units_parsed"] >= 3)
    with_recon = sum(1 for r in report.values() if r["reconciliation"])
    bad = sum(1 for r in report.values() if r["recon_bad"])
    mism = sum(len(r["rate_mismatches"]) for r in report.values())
    print(f"\ncounties with parsed CAD rate sheet : {scraped}/{len(report)}")
    print(f"counties with published area totals : {with_recon}")
    print(f"  of those, totals the app misses   : {bad}")
    print(f"PTAD-vs-CAD rate mismatches         : {mism}")
    print(f"-> {OUT}\n-> {MD}")


def write_markdown(report):
    esd_counties = sorted(
        ((c, r) for c, r in report.items() if r["esd_count"]),
        key=lambda kv: -sum(m["rate"] for m in kv[1]["missing_jurisdictions"]
                            if m["type"] == "40"))
    n_esd_units = sum(r["esd_count"] for _, r in esd_counties)
    proven = [c for c, r in report.items() if r["esd_coverage"] == "countywide"]
    partial = [c for c, r in report.items() if r["esd_coverage"] == "partial"]

    lines = [
        "# Tax-rate audit — map vs. county appraisal districts",
        "",
        f"Sources: the {TAX_YEAR} Comptroller PTAD rates-and-levies workbook, the",
        "rate sheets published on all 254 CAD websites (`scrub_cad_rates.py`),",
        "and the rates the map itself renders (`parcels_rated`).",
        "",
        "## Summary",
        "",
        f"* **{n_esd_units} emergency services districts across "
        f"{len(esd_counties)} counties are missing from every parcel rate.**",
        "  The Comptroller workbook already carries each one's adopted rate — the",
        "  map drops them because `gen_recipes.py` only adds a special district to",
        "  a county's base stack when it can prove the district covers the whole",
        "  county, and ESD boundaries are not published statewide.",
        f"* {len(proven)} "
        + ("county's" if len(proven) == 1 else "counties'")
        + " own published area totals include an ESD in"
        " **every** area, which proves county-wide coverage"
        + (": " + ", ".join(sorted(proven)) if proven else "") + ".",
        f"* {len(partial)} counties publish areas both with and without an ESD, so"
        " those need real boundaries"
        + (": " + ", ".join(sorted(partial)) if partial else "") + ".",
        "* The remaining counties publish no area totals we could parse; see"
        " `RATE-FIX-ROUTES.md` for where their coverage data can be obtained.",
        "",
        "## 1. Counties where the map omits an ESD",
        "",
        "`coverage` is read off the CAD's own published area totals, not guessed:",
        "*countywide* = every published area includes an ESD; *partial* = some do",
        "not; *unknown* = that CAD publishes no area totals we could parse.",
        "",
        "| County | ESDs | rate range | coverage | on CAD site | map understates by |",
        "|---|---:|---|---|---:|---:|",
    ]
    for county, r in esd_counties:
        esds = [m for m in r["missing_jurisdictions"] if m["type"] == "40"]
        if not esds:
            continue
        conf = sum(1 for m in esds if m["on_cad_site"])
        lo = min(m["rate"] for m in esds)
        hi = max(m["rate"] for m in esds)
        gap = max((abs(rc.get("delta") or 0) for rc in r["reconciliation"]
                   if not rc["ok"]), default=None)
        lines.append(f"| {county} | {len(esds)} | {lo:.4f}–{hi:.4f} | "
                     f"{r['esd_coverage']} | {conf}/{len(esds)} | "
                     f"{('%.4f' % gap) if gap else ''} |")

    lines += ["", "## 2. Published area totals the map does not reproduce", "",
              "Each row is a combined rate the county publishes for a specific",
              "area, decomposed back into the exact units that sum to it, then",
              "compared with what the map shows for parcels in that same",
              "city/school-district area.",
              "",
              "| County | published area | CAD total | map shows | gap | missing unit |",
              "|---|---|---:|---:|---:|---|"]
    rows = []
    for county, r in report.items():
        for rc in r["reconciliation"]:
            if not rc["ok"] and abs(rc.get("delta") or 0) >= 0.005:
                rows.append((abs(rc["delta"]), county, rc))
    for _, county, rc in sorted(rows, key=lambda t: (-t[0], t[1]))[:200]:
        lines.append(f"| {county} | {rc['published'][:44]} | {rc['published_rate']:.6f} "
                     f"| {rc.get('app_rate')} | {(rc.get('delta') or 0):+.6f} "
                     f"| {rc.get('likely_cause') or ''} |")

    lines += ["", "## 3. PTAD rate disagrees with the CAD's published rate", "",
              "Only counties whose scraped sheet otherwise agrees with PTAD are",
              "listed. These still need eyeballing before acting on them: a CAD",
              "page that breaks a rate into M&O and I&S, or that shows several",
              "tax years, can produce a row here that is not really a conflict.",
              "The Comptroller workbook is the authority unless the CAD's own",
              "adopted-rate sheet for 2025 says otherwise.",
              "",
              "| County | unit | PTAD | CAD | delta |", "|---|---|---:|---:|---:|"]
    for county, r in sorted(report.items()):
        for m in r["rate_mismatches"]:
            lines.append(f"| {county} | {m['ptad_name'][:40]} | {m['ptad_rate']:.6f} "
                         f"| {m['cad_rate']:.6f} | {m['delta']:+.6f} |")

    lines += ["", "## 4. Counties with no machine-readable rate sheet", "",
              "The crawler reached the site but found no parsable table of",
              "jurisdictions — mostly JavaScript-rendered county portals. These",
              "need the Truth-in-Taxation vendor APIs or a manual pass.", ""]
    none = [c for c, r in sorted(report.items()) if r["cad_units_parsed"] < 3]
    lines.append(", ".join(none))

    MD.parent.mkdir(parents=True, exist_ok=True)
    MD.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
