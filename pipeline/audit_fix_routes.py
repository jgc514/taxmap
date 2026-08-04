#!/usr/bin/env python3
"""Where the data needed to close each ESD gap can actually be obtained.

The audit says which jurisdictions the map drops; this says, county by county,
which of the four possible sources can supply the missing *coverage* (the rates
themselves are already in the PTAD workbook):

  1. CAD published area totals — the county prints the combined rate for each
     area, so the stack can be solved exactly (`area_overrides.py`).
  2. Appraisal roll / data export — the CAD publishes the certified roll, which
     lists every taxing unit per account. This is the exact per-parcel answer
     and reuses `parse_ta_roll.py` / `parse_ta_export.py` / `roll_rates.py`,
     already proven on Wilson, Bandera and Guadalupe.
  3. A published ESD boundary layer on ArcGIS (`probe_esd_layers.py`).
  4. Nothing found — needs a public-information request.

Output: docs/RATE-FIX-ROUTES.md
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "cad-rates"
SOURCES = ROOT / "data" / "build" / "cad-sources.json"
CAD = ROOT / "data" / "build" / "cad-vs-app.json"
AUDIT = ROOT / "data" / "build" / "coverage-audit.json"
LAYERS = ROOT / "data" / "build" / "esd-layer-candidates.json"
OVERRIDES = ROOT / "data" / "build" / "area-overrides.json"
MD = ROOT / "docs" / "RATE-FIX-ROUTES.md"

ROLL_HINT = re.compile(
    r"(appraisal (export|roll)|certified roll|data (download|export)"
    r"|export data|public data|open records data)", re.I)


def roll_mentions(fips):
    d = CACHE / fips
    hits = set()
    for f in sorted(d.glob("*.txt")):
        for m in ROLL_HINT.finditer(f.read_text(errors="replace")):
            hits.add(m.group(0).lower())
    return sorted(hits)


def layer_for(county, layers):
    """ArcGIS services whose title or owner names this county."""
    key = county.lower().replace(" ", "")
    out = []
    for h in layers:
        blob = f"{h['item']} {h.get('owner') or ''}".lower().replace(" ", "")
        if key in blob:
            out.append((h["item"], h["url"], [x["name"] for x in h["hits"]]))
    return out


def main():
    sources = json.loads(SOURCES.read_text())
    audit = json.loads(AUDIT.read_text())
    cad = json.loads(CAD.read_text())
    layers = json.loads(LAYERS.read_text())["hits"] if LAYERS.exists() else []
    overrides = json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else []
    solved_counties = {r["county"] for r in overrides}

    gaps = sorted(((c, r) for c, r in audit.items() if r["esd_count"]),
                  key=lambda kv: -kv[1]["esd_max"])

    lines = [
        "# Closing the ESD gap — what data exists, county by county",
        "",
        "Every ESD's *rate* is already in the Comptroller workbook we build from.",
        "What is missing is *coverage*: which parcels are inside which district.",
        "These are the routes to that, ranked by how exact they are.",
        "",
        "| County | ESDs | max rate | route 1: CAD area totals | route 2: roll/data export | route 3: ArcGIS ESD layer |",
        "|---|---:|---:|---|---|---|",
    ]
    counts = {"area": 0, "roll": 0, "layer": 0, "none": 0}
    for county, r in gaps:
        fips = r["fips"]
        area = ("solved" if county in solved_counties
                else cad.get(county, {}).get("esd_coverage", "unknown"))
        roll = roll_mentions(fips)
        lyr = layer_for(county, layers)
        if area in ("solved", "countywide"):
            counts["area"] += 1
        elif roll:
            counts["roll"] += 1
        elif lyr:
            counts["layer"] += 1
        else:
            counts["none"] += 1
        lines.append(
            f"| [{county}]({sources[county].get('cad','')}) | {r['esd_count']} "
            f"| {r['esd_max']:.4f} | {area} | {', '.join(roll) or '—'} "
            f"| {lyr[0][0] if lyr else '—'} |")

    lines[6:6] = [
        f"* **{counts['area']}** counties can be fixed from the CAD's own "
        "published area totals today.",
        f"* **{counts['roll']}** more advertise a downloadable appraisal roll or "
        "data export — the exact per-parcel unit stack, through the parser that "
        "already handles Wilson/Bandera/Guadalupe.",
        f"* **{counts['layer']}** more have a published ESD/fire-district boundary "
        "layer on ArcGIS.",
        f"* **{counts['none']}** have none of the three and need a public-"
        "information request.",
        "",
    ]

    if layers:
        lines += ["", "## ArcGIS ESD / fire-district layers found", "",
                  "| service | owner | layers | url |", "|---|---|---|---|"]
        for h in sorted(layers, key=lambda x: x["item"]):
            lines.append(f"| {h['item'][:44]} | {h.get('owner','')} | "
                         f"{', '.join(l['name'] for l in h['hits'])[:60]} | "
                         f"{h['url']} |")

    MD.write_text("\n".join(lines) + "\n")
    print(f"{len(gaps)} counties with an ESD gap")
    for k, v in counts.items():
        print(f"  route {k}: {v}")
    print(f"-> {MD}")


if __name__ == "__main__":
    main()
