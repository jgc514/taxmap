#!/usr/bin/env python3
"""Emit web/src/rate-breakdown.json — the per-county jurisdiction rate
components the popup reconstructs a breakdown from, WITHOUT re-tiling.

For each county:
  base_units: [{name, rate}]  the itemized county-wide stack (county govt +
              hospital/college/GCD/etc — the same unit ids the pipeline sums
              into `base`)
  cities:     {normalized_city_name: {name, rate}}  city rate by TIGER name

The ISD line comes from the tile itself (`isd` name + `isdr` rate already on
every parcel), so total = sum(base_units) + city + isdr, matching the tile's
`rate` field exactly. Nothing here needs the geometry or a rebuild.
"""
import json
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_region import COUNTIES, PTAD_XLSX, norm_city  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "web" / "src" / "rate-breakdown.json"


def main():
    ws = openpyxl.load_workbook(PTAD_XLSX, read_only=True)["Statewide"]
    name_by_id, rate_by_id = {}, {}
    city_units = {}  # ptad county code -> {norm name: (name, rate)}
    for row in ws.iter_rows(min_row=4, values_only=True):
        name, uid, rate = row[0], row[1], row[2]
        if not uid:
            continue
        name = name.strip().rstrip("*").strip()
        code, _, utype = uid.split("-")
        name_by_id[uid] = name
        rate_by_id[uid] = float(rate or 0)
        if utype == "03":
            city_units.setdefault(code, {})[norm_city(name)] = (name, float(rate or 0))

    out = {}
    for cname, cfg in COUNTIES.items():
        base_units = [
            {"name": name_by_id[u], "rate": round(rate_by_id[u], 6)}
            for u in cfg["countywide"]
            if rate_by_id.get(u, 0) > 0
        ]
        # cities that can appear on this county's parcels: its own + adjacent
        # (parcels near a county line may sit in a neighboring city). Keep it
        # simple + correct: include the county's own PTAD-code cities; the
        # client falls back to "City (see total)" if a name isn't found.
        cities = {
            k: {"name": n, "rate": round(r, 6)}
            for k, (n, r) in city_units.get(cfg["ptad"], {}).items()
        }
        out[cname] = {"base_units": base_units, "cities": cities}

    OUT.write_text(json.dumps(out, separators=(",", ":")))
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.name}: {len(out)} counties, {kb:.0f} KB")


if __name__ == "__main__":
    main()
