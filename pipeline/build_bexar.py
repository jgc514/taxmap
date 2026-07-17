#!/usr/bin/env python3
"""Phase 0: Bexar County parcels -> nominal tax rate -> GeoJSONSeq for tippecanoe.

Jurisdiction assignment is the v0 spatial-join approximation:
  county-wide units (county + hospital + college + river authority) apply to
  every parcel; city and ISD come from point-in-polygon against TIGER
  boundaries. ESD/MUD/SID/PID special districts are NOT included until the
  CAD appraisal roll arrives (open-records request pending) — the map carries
  an "approximate" badge until then.

Outputs (data/build/):
  parcels.geojsonseq  — one feature per parcel: id, addr, mkt, rate, isd, cj
  isd.geojsonseq      — ISD polygons clipped to Bexar with median rate stats
  taxmap.duckdb       — parcels + taxing_units tables for later phases
  unmatched.txt       — any TIGER city/ISD name that found no PTAD rate
"""
import re
import sys
from pathlib import Path

import duckdb
import openpyxl

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BUILD = ROOT / "data" / "build"
BUILD.mkdir(parents=True, exist_ok=True)

TAX_YEAR = 2025
PARCELS_SHP = RAW / "stratmap_bexar/shp/stratmap25-landparcels_48029_bexar_202507.shp"
PLACE_SHP = RAW / "tiger_place/tl_2025_48_place.shp"
UNSD_SHP = RAW / "tiger_unsd/tl_2025_48_unsd.shp"
COUNTY_ZIP = RAW / "tl_2025_us_county.zip"
PTAD_XLSX = RAW / "ptad-2025-total-rates-levies.xlsx"

# PTAD county codes for the SA metro + bordering counties whose cities/ISDs
# reach into Bexar. Restricting candidates avoids same-name collisions from
# far-away corners of the state.
METRO_COUNTY_CODES = {"007", "010", "015", "046", "094", "130", "133", "163", "247"}

# Bexar county-wide units (apply to every parcel in the county).
COUNTYWIDE_UNIT_IDS = {
    "015-000-00",  # Bexar County (incl. road & flood in PTAD total)
    "015-201-11",  # University Health System
    "015-201-15",  # Alamo Community College District
    "015-201-27",  # San Antonio River Authority
}


def norm_city(name: str) -> str:
    n = name.strip().lower()
    n = re.sub(r"^(city|town|village) of ", "", n)
    return n


def norm_isd(name: str) -> str:
    n = name.strip().lower()
    n = n.replace("independent school district", "isd")
    n = re.sub(r"\s+", " ", n)
    return n


def load_taxing_units():
    ws = openpyxl.load_workbook(PTAD_XLSX, read_only=True)["Statewide"]
    units = []
    for row in ws.iter_rows(min_row=4, values_only=True):
        name, uid, rate = row[0], row[1], row[2]
        if not uid:
            continue
        name = name.strip().rstrip("*").strip()
        county, _, utype = uid.split("-")
        units.append((TAX_YEAR, uid, name, county, utype, float(rate or 0)))
    return units


def main():
    units = load_taxing_units()
    print(f"taxing units statewide: {len(units)}")

    county_base = sum(u[5] for u in units if u[1] in COUNTYWIDE_UNIT_IDS)
    assert 0.6 < county_base < 0.9, f"county base rate looks wrong: {county_base}"
    print(f"Bexar county-wide base rate: {county_base:.6f} per $100")

    # Rate lookups by normalized name, restricted to metro-area counties.
    city_rates, isd_rates = {}, {}
    for _, uid, name, county, utype, rate in units:
        if county not in METRO_COUNTY_CODES:
            continue
        if utype == "03":
            key = norm_city(name)
            # prefer the Bexar-county unit on any collision
            if key not in city_rates or uid.startswith("015-"):
                city_rates[key] = (name, uid, rate)
        elif utype == "02":
            key = norm_isd(name)
            if key not in isd_rates or uid.startswith("015-"):
                isd_rates[key] = (name, uid, rate)

    con = duckdb.connect(str(BUILD / "taxmap.duckdb"))
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("DROP TABLE IF EXISTS taxing_units")
    con.execute(
        """CREATE TABLE taxing_units(tax_year INT, unit_id TEXT, name TEXT,
           county_code TEXT, unit_type TEXT, rate_per_100 DOUBLE)"""
    )
    con.executemany("INSERT INTO taxing_units VALUES (?,?,?,?,?,?)", units)

    print("loading parcels + boundaries ...")
    con.execute(
        f"""CREATE OR REPLACE TABLE parcels_raw AS
        SELECT Prop_ID AS prop_id, SITUS_ADDR AS addr, SITUS_CITY AS situs_city,
               MKT_VALUE AS mkt, STAT_LAND_ AS land_use, YEAR_BUILT AS year_built,
               LEGAL_DESC AS legal_desc, geom,
               ST_PointOnSurface(geom) AS pt
        FROM ST_Read('{PARCELS_SHP}')
        WHERE geom IS NOT NULL"""
    )
    # TIGER ships NAD83 (EPSG:4269); parcels are WGS84 (EPSG:4326).
    con.execute(
        f"""CREATE OR REPLACE TABLE places AS
        SELECT * FROM (
          SELECT NAME AS city_name,
                 ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
          FROM ST_Read('{PLACE_SHP}')
          WHERE LSAD != '57'  -- exclude CDPs: unincorporated, levy no city tax
        ) WHERE ST_Intersects(geom, ST_SetCRS(ST_MakeEnvelope(-98.81, 29.11, -98.12, 29.76), 'EPSG:4326'))"""
    )
    con.execute(
        f"""CREATE OR REPLACE TABLE isds AS
        SELECT * FROM (
          SELECT NAME AS isd_name,
                 ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
          FROM ST_Read('{UNSD_SHP}')
        ) WHERE ST_Intersects(geom, ST_SetCRS(ST_MakeEnvelope(-98.81, 29.11, -98.12, 29.76), 'EPSG:4326'))"""
    )
    n = con.execute("SELECT count(*) FROM parcels_raw").fetchone()[0]
    print(f"parcels: {n}, places: {con.execute('SELECT count(*) FROM places').fetchone()[0]}, "
          f"isds: {con.execute('SELECT count(*) FROM isds').fetchone()[0]}")

    print("spatial joins (city, ISD) ...")
    con.execute(
        """CREATE OR REPLACE TABLE parcels AS
        SELECT p.* EXCLUDE (pt), c.city_name, i.isd_name
        FROM parcels_raw p
        LEFT JOIN places c ON ST_Within(p.pt, c.geom)
        LEFT JOIN isds i ON ST_Within(p.pt, i.geom)"""
    )
    # A parcel straddling two polygons can join twice; keep one row per prop_id+geom.
    con.execute(
        """CREATE OR REPLACE TABLE parcels AS
        SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY prop_id, legal_desc, addr ORDER BY city_name, isd_name) rn
        FROM parcels) WHERE rn = 1"""
    )

    # Attach rates in Python (small lookup), write back as a table.
    unmatched = set()
    city_rows = con.execute("SELECT DISTINCT city_name FROM parcels WHERE city_name IS NOT NULL").fetchall()
    isd_rows = con.execute("SELECT DISTINCT isd_name FROM parcels WHERE isd_name IS NOT NULL").fetchall()
    city_map, isd_map = [], []
    for (cn,) in city_rows:
        hit = city_rates.get(norm_city(cn))
        if hit:
            city_map.append((cn, hit[0], hit[1], hit[2]))
        else:
            unmatched.add(f"CITY\t{cn}")
            city_map.append((cn, None, None, 0.0))
    for (iname,) in isd_rows:
        hit = isd_rates.get(norm_isd(iname))
        if hit:
            isd_map.append((iname, hit[0], hit[1], hit[2]))
        else:
            unmatched.add(f"ISD\t{iname}")
            isd_map.append((iname, None, None, 0.0))
    con.execute("CREATE OR REPLACE TABLE city_rate_map(city_name TEXT, unit_name TEXT, unit_id TEXT, rate DOUBLE)")
    con.executemany("INSERT INTO city_rate_map VALUES (?,?,?,?)", city_map)
    con.execute("CREATE OR REPLACE TABLE isd_rate_map(isd_name TEXT, unit_name TEXT, unit_id TEXT, rate DOUBLE)")
    con.executemany("INSERT INTO isd_rate_map VALUES (?,?,?,?)", isd_map)
    (BUILD / "unmatched.txt").write_text("\n".join(sorted(unmatched)) or "none\n")
    print(f"unmatched boundary names: {len(unmatched)} (see data/build/unmatched.txt)")

    con.execute(
        f"""CREATE OR REPLACE TABLE parcels_rated AS
        SELECT p.prop_id, p.addr, p.situs_city, p.mkt, p.land_use, p.year_built,
               p.city_name, p.isd_name,
               {county_base} + coalesce(c.rate, 0) + coalesce(i.rate, 0) AS nominal_rate,
               c.rate AS city_rate, i.rate AS isd_rate, p.geom
        FROM parcels p
        LEFT JOIN city_rate_map c USING (city_name)
        LEFT JOIN isd_rate_map i USING (isd_name)"""
    )
    stats = con.execute(
        """SELECT count(*), round(min(nominal_rate),4), round(median(nominal_rate),4),
           round(max(nominal_rate),4), count(*) FILTER (isd_name IS NULL) FROM parcels_rated"""
    ).fetchone()
    print(f"rated parcels: {stats[0]}  rate min/med/max: {stats[1]}/{stats[2]}/{stats[3]}  no-ISD: {stats[4]}")

    print("writing parcels.geojsonseq ...")
    con.execute(
        f"""COPY (
          SELECT prop_id AS id, addr, mkt::BIGINT AS mkt,
                 round(nominal_rate, 4) AS rate,
                 isd_name AS isd, city_name AS cj, geom
          FROM parcels_rated
        ) TO '{BUILD / "parcels.geojsonseq"}'
        WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')"""
    )

    print("writing isd.geojsonseq (ISD polygons clipped to Bexar, with stats) ...")
    con.execute(
        f"""CREATE OR REPLACE TABLE bexar_boundary AS
        SELECT ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
        FROM ST_Read('/vsizip/{COUNTY_ZIP}/tl_2025_us_county.shp')
        WHERE GEOID = '48029'"""
    )
    con.execute(
        f"""COPY (
          SELECT s.isd_name AS name,
                 round(median(p.nominal_rate), 4) AS rate,
                 count(*) AS parcels,
                 round(median(p.mkt), 0)::BIGINT AS med_value,
                 any_value(ST_Intersection(i.geom, b.geom)) AS geom
          FROM parcels_rated p
          JOIN (SELECT isd_name, geom FROM isds) i ON p.isd_name = i.isd_name
          JOIN isds s ON s.isd_name = i.isd_name
          CROSS JOIN bexar_boundary b
          GROUP BY s.isd_name
        ) TO '{BUILD / "isd.geojsonseq"}'
        WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')"""
    )
    print("done.")


if __name__ == "__main__":
    sys.exit(main())
