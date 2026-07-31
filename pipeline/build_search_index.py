#!/usr/bin/env python3
"""Statewide search index: 13.8M parcels -> prefix-sharded, pre-gzipped TSV.

Three indexes under data/search/, one directory each:
  owner/<PRE>.tsv.gz  cols: prop_id, cty_idx, addr, owner, lat, lng
  addr/<PRE>.tsv.gz   cols: prop_id, cty_idx, addr, lat, lng
  id/<PRE>.tsv.gz     cols: prop_id, cty_idx, addr, lat, lng

Shard key (must mirror the JS in web/src/App.jsx exactly):
  norm(s)  = upper(s), [^A-Z0-9]+ -> single space, trim
  owner: first 3 chars of norm(owner)            (whole key when shorter)
  addr:  house-number route — first token of norm(addr) when numeric:
         first 3 digits (whole number when shorter); otherwise token route:
         't_' + first 3 chars of the first token (no-house-number parcels
         like 'CR 405' — Photon covers road-level queries for the rest)
  id:    first 3 chars of norm(prop_id) minus spaces

Spaces inside a prefix map to '_' in filenames. Rows are sorted by full key
within each shard (adjacent near-duplicates make gzip ~5x). Each index dir
gets manifest.json {prefix: rowcount}; data/search/meta.json carries the
county list that cty_idx points into.

Hosted on GitHub Pages (jgc514/taxmap-search) next to the tiles; the app
fetches the one shard a query maps to and inflates it with
DecompressionStream. No server anywhere.
"""
import gzip
import json
import sys
import time
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "build" / "taxmap.duckdb"
OUT = ROOT / "data" / "search"

NORM = "trim(regexp_replace(upper({col}), '[^A-Z0-9]+', ' ', 'g'))"


def shard_fname(prefix: str) -> str:
    return prefix.replace(" ", "_") + ".tsv.gz"


def export(con, name: str, sql: str) -> dict:
    """Stream (shard, k, line) ordered by shard,k into rolling gz files."""
    outdir = OUT / name
    outdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    reader = con.execute(sql).fetch_record_batch(200_000)
    manifest: dict[str, int] = {}
    cur, fh = None, None
    rows = 0
    for batch in reader:
        shards = batch.column(0).to_pylist()
        lines = batch.column(1).to_pylist()
        for shard, line in zip(shards, lines):
            if shard != cur:
                if fh:
                    fh.close()
                cur = shard
                fh = gzip.open(outdir / shard_fname(shard), "wb", compresslevel=6)
                manifest[shard] = 0
            fh.write(line.encode() + b"\n")
            manifest[shard] += 1
            rows += 1
    if fh:
        fh.close()
    (outdir / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")))
    size = sum(f.stat().st_size for f in outdir.glob("*.tsv.gz"))
    print(
        f"{name}: {rows:,} rows, {len(manifest):,} shards, "
        f"{size / 1e6:,.0f}MB gz, {time.time() - t0:,.0f}s",
        flush=True,
    )
    return {"rows": rows, "shards": len(manifest), "bytes": size}


def main():
    con = duckdb.connect(str(DB), read_only=True)
    con.execute("INSTALL spatial; LOAD spatial")
    con.execute("PRAGMA threads=8")

    counties = [r[0] for r in con.execute(
        "SELECT DISTINCT county FROM parcels_rated ORDER BY 1").fetchall()]
    cidx = {c: i for i, c in enumerate(counties)}
    con.execute("CREATE TEMP TABLE cty_map(county TEXT, idx INT)")
    con.executemany("INSERT INTO cty_map VALUES (?, ?)", list(cidx.items()))

    # Shared base: one centroid per parcel, exact-duplicate rows collapsed,
    # control chars scrubbed so they can't break TSV lines. Materialized —
    # three exports read it. prop_id '0' (Travis CAD withheld ids) would fan
    # the owner join across ~430k parcels, so owner attaches only to real ids.
    con.execute("""
        CREATE TEMP TABLE base AS
        WITH attrs AS (
          SELECT county, prop_id, any_value(owner) AS owner
          FROM parcel_attrs
          WHERE owner IS NOT NULL AND owner <> '' AND prop_id <> '0'
          GROUP BY 1, 2
        ),
        pts AS (
          SELECT p.county, p.prop_id,
                 regexp_replace(coalesce(p.addr, ''), '[\\t\\n\\r]+', ' ', 'g') AS addr,
                 regexp_replace(a.owner, '[\\t\\n\\r]+', ' ', 'g') AS owner,
                 ST_Centroid(p.geom) AS c
          FROM parcels_rated p
          LEFT JOIN attrs a ON a.county = p.county AND a.prop_id = p.prop_id
        )
        SELECT county, prop_id, addr, any_value(owner) AS owner,
               round(any_value(ST_Y(c)), 5) AS lat,
               round(any_value(ST_X(c)), 5) AS lng
        FROM pts GROUP BY 1, 2, 3
    """)

    stats = {}
    ok = NORM.format(col="b.owner")
    stats["owner"] = export(con, "owner", f"""
        WITH keyed AS (
          SELECT {ok} AS k, b.prop_id, m.idx, b.addr, b.owner, b.lat, b.lng
          FROM base b JOIN cty_map m ON m.county = b.county
          WHERE b.owner IS NOT NULL AND b.lat IS NOT NULL
        )
        SELECT CASE WHEN length(k) >= 3 THEN substr(k, 1, 3) ELSE k END AS shard,
               concat_ws(chr(9), prop_id, idx, addr, owner, lat, lng) AS line
        FROM keyed WHERE k <> ''
        ORDER BY shard, k
    """)

    ak = NORM.format(col="b.addr")
    stats["addr"] = export(con, "addr", f"""
        WITH keyed AS (
          SELECT {ak} AS k, split_part({ak}, ' ', 1) AS tok0,
                 b.prop_id, m.idx, b.addr, b.lat, b.lng
          FROM base b JOIN cty_map m ON m.county = b.county
          WHERE b.addr <> '' AND b.lat IS NOT NULL
        )
        SELECT CASE
                 WHEN regexp_matches(tok0, '^[0-9]+$')
                   THEN CASE WHEN length(tok0) >= 3 THEN substr(tok0, 1, 3) ELSE tok0 END
                 ELSE 't_' || CASE WHEN length(tok0) >= 3 THEN substr(tok0, 1, 3) ELSE tok0 END
               END AS shard,
               concat_ws(chr(9), prop_id, idx, addr, lat, lng) AS line
        FROM keyed WHERE tok0 <> ''
        ORDER BY shard, k
    """)

    stats["id"] = export(con, "id", """
        WITH keyed AS (
          SELECT regexp_replace(upper(b.prop_id), '[^A-Z0-9]', '', 'g') AS k,
                 b.prop_id, m.idx, b.addr, b.lat, b.lng
          FROM base b JOIN cty_map m ON m.county = b.county
          WHERE b.prop_id <> '0' AND b.lat IS NOT NULL
        )
        SELECT CASE WHEN length(k) >= 3 THEN substr(k, 1, 3) ELSE k END AS shard,
               concat_ws(chr(9), prop_id, idx, addr, lat, lng) AS line
        FROM keyed WHERE k <> '' AND k <> '0'
        ORDER BY shard, k
    """)

    (OUT / "meta.json").write_text(json.dumps(
        {"built": date.today().isoformat(), "counties": counties,
         "stats": stats}, separators=(",", ":")))
    total = sum(s["bytes"] for s in stats.values())
    print(f"total: {total / 1e6:,.0f}MB gz across "
          f"{sum(s['shards'] for s in stats.values()):,} shards", flush=True)


if __name__ == "__main__":
    sys.exit(main())
