"""Rate distribution stats for the diverging choropleth → web/src/rate-stats.json.

The map colors a feature by how far its rate sits from a *median anchor*, in
standard deviations, rather than by an absolute rate. Which median is the right
anchor depends on the layer:

  parcels  — the parcel's own county. Within-county variation (city vs
             unincorporated, MUD vs no MUD) is the story at parcel zoom;
             against a statewide anchor a high-tax county paints uniformly dark
             and says nothing.
  isd      — the statewide distribution of ISD median rates. ISDs cross county
             lines, so a county anchor is undefined for them.
  county   — the statewide distribution of county median rates. Anchoring a
             county against itself would flatten the statewide view entirely.

Counties whose parcels are effectively one rate (σ ≈ 0 — a handful of rural
counties with no city or special district) would blow up the z-score, so they
fall back to the statewide parcel σ.

Run: .venv/bin/python pipeline/gen_rate_stats.py
"""

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "build" / "taxmap.duckdb"
OUT = ROOT / "web" / "src" / "rate-stats.json"

# Below this the county's rates carry no signal of their own.
MIN_SIGMA = 0.02


def main() -> None:
    con = duckdb.connect(str(DB), read_only=True)

    state_med, state_sd = con.execute(
        "SELECT median(nominal_rate), stddev_samp(nominal_rate) FROM parcels_rated"
    ).fetchone()

    county_med, county_sd = con.execute(
        """SELECT median(r), stddev_samp(r) FROM (
             SELECT median(nominal_rate) r FROM parcels_rated GROUP BY county)"""
    ).fetchone()

    isd_med, isd_sd = con.execute(
        """SELECT median(r), stddev_samp(r) FROM (
             SELECT median(nominal_rate) r FROM parcels_rated
             WHERE isd_name IS NOT NULL GROUP BY isd_name)"""
    ).fetchone()

    counties = {}
    fallbacks = []
    for name, n, med, sd in con.execute(
        """SELECT county, count(*), median(nominal_rate), stddev_samp(nominal_rate)
           FROM parcels_rated GROUP BY county ORDER BY county"""
    ).fetchall():
        if sd is None or sd < MIN_SIGMA:
            fallbacks.append(name)
            sd = state_sd
        counties[name] = [round(med, 4), round(sd, 4), n]

    stats = {
        "parcel": {"median": round(state_med, 4), "sd": round(state_sd, 4)},
        "county": {"median": round(county_med, 4), "sd": round(county_sd, 4)},
        "isd": {"median": round(isd_med, 4), "sd": round(isd_sd, 4)},
        # name -> [median, sd, parcel_count]
        "counties": counties,
    }
    OUT.write_text(json.dumps(stats, separators=(",", ":")) + "\n")

    print(f"wrote {OUT.relative_to(ROOT)} — {len(counties)} counties")
    print(f"  parcel  median {stats['parcel']['median']}  sd {stats['parcel']['sd']}")
    print(f"  county  median {stats['county']['median']}  sd {stats['county']['sd']}")
    print(f"  isd     median {stats['isd']['median']}  sd {stats['isd']['sd']}")
    if fallbacks:
        print(f"  sigma fallback (flat-rate counties): {', '.join(fallbacks)}")


if __name__ == "__main__":
    main()
