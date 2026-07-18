#!/usr/bin/env python3
"""Compute Texas counties within N adjacency rings of Bexar (48029).

Adjacency = shared boundary (ST_Intersects on TIGER county polygons, which
also catches corner-touch pairs). Prints ring assignments + FIPS list.
"""
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
COUNTY_ZIP = ROOT / "data" / "raw" / "tl_2025_us_county.zip"
MAX_RING = int(sys.argv[1]) if len(sys.argv) > 1 else 4

con = duckdb.connect()
con.execute("INSTALL spatial; LOAD spatial;")
con.execute(
    f"""CREATE TABLE tx AS
    SELECT GEOID AS fips, NAME AS name, geom
    FROM ST_Read('/vsizip/{COUNTY_ZIP}/tl_2025_us_county.shp')
    WHERE STATEFP = '48'"""
)
pairs = con.execute(
    """SELECT a.fips, b.fips FROM tx a JOIN tx b
    ON a.fips < b.fips AND ST_Intersects(a.geom, b.geom)"""
).fetchall()
adj = {}
for a, b in pairs:
    adj.setdefault(a, set()).add(b)
    adj.setdefault(b, set()).add(a)

names = dict(con.execute("SELECT fips, name FROM tx").fetchall())
ring = {"48029": 0}
frontier = {"48029"}
for r in range(1, MAX_RING + 1):
    frontier = {n for f in frontier for n in adj[f] if n not in ring}
    for f in frontier:
        ring[f] = r

for r in range(MAX_RING + 1):
    members = sorted(f for f, rr in ring.items() if rr == r)
    print(f"ring {r} ({len(members)}): " + ", ".join(f"{names[f]} {f}" for f in members))
print(f"total: {len(ring)}")
print(",".join(sorted(ring)))
