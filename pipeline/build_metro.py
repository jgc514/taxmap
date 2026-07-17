#!/usr/bin/env python3
"""Phase 1: all 8 SA-metro counties -> nominal tax rate -> GeoJSONSeq layers.

Supersedes build_bexar.py (same v0 spatial-join approximation, now
config-driven per county). Per-county recipes below define the county-wide
taxing units; city + ISD come from TIGER point-in-polygon; ESD/MUD/WCID
special districts remain the documented v0 gap until appraisal rolls arrive.

Outputs (data/build/):
  parcels.geojsonseq  — all-county parcels: id, addr, mkt, rate, isd, cj, cty
  isd.geojsonseq      — ISD polygons clipped to the 8-county union, with stats
  county.geojsonseq   — 8 county polygons with stats
  taxmap.duckdb       — parcels_rated + taxing_units tables
  unmatched.txt       — TIGER city/ISD names with no PTAD rate match
"""
import glob
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
PLACE_SHP = RAW / "tiger_place/tl_2025_48_place.shp"
UNSD_SHP = RAW / "tiger_unsd/tl_2025_48_unsd.shp"
COUNTY_ZIP = RAW / "tl_2025_us_county.zip"
PTAD_XLSX = RAW / "ptad-2025-total-rates-levies.xlsx"

# Home-county PTAD codes whose city/ISD units can appear on metro parcels
# (the 8 metro counties + bordering counties whose ISDs/cities reach in:
# Blanco, Caldwell, Frio, Gillespie, Gonzales, Hays, Karnes, Kerr, Live Oak,
# Uvalde).
LOOKUP_COUNTY_CODES = {
    "007", "010", "015", "046", "094", "130", "133", "163", "247",
    "016", "028", "082", "086", "089", "105", "128", "149", "232",
}

# Per-county recipe: FIPS, PTAD code, county-wide taxing units.
# County-wide = applies to every parcel in that county (county government,
# hospital/college districts, river authorities, groundwater districts).
COUNTIES = {
    "Bexar": {
        "fips": "48029",
        "ptad": "015",
        "countywide": [
            "015-000-00",  # Bexar County (incl. road & flood)
            "015-201-11",  # University Health System
            "015-201-15",  # Alamo Community College District
            "015-201-27",  # San Antonio River Authority
        ],
    },
    "Comal": {
        "fips": "48091",
        "ptad": "046",
        "countywide": ["046-000-00"],
    },
    "Guadalupe": {
        "fips": "48187",
        "ptad": "094",
        "countywide": ["094-000-00"],
    },
    "Medina": {
        "fips": "48325",
        "ptad": "163",
        "countywide": [
            "163-000-00",
            "163-201-11",  # Medina County Hospital District
            "163-201-23",  # Medina County Underground WCD
        ],
    },
    "Wilson": {
        "fips": "48493",
        "ptad": "247",
        "countywide": [
            "247-000-00",
            "247-201-11",  # Wilson County Hospital District
            "015-201-27",  # San Antonio River Authority (taxes Wilson too)
        ],
    },
    "Atascosa": {
        "fips": "48013",
        "ptad": "007",
        "countywide": [
            "007-000-00",
            "007-201-06",  # Evergreen Underground WCD
        ],
    },
    "Kendall": {
        "fips": "48259",
        "ptad": "130",
        "countywide": [
            "130-000-00",
            "130-201-06",  # Cow Creek Groundwater Conservation
        ],
    },
    "Bandera": {
        "fips": "48019",
        "ptad": "010",
        "countywide": [
            "010-000-00",
            "010-201-27",  # Bandera River Authority
        ],
    },
}

METRO_BBOX = "ST_SetCRS(ST_MakeEnvelope(-99.65, 28.55, -97.55, 30.25), 'EPSG:4326')"


def norm_city(name: str) -> str:
    n = name.strip().lower()
    n = re.sub(r"^(city|town|village) of ", "", n)
    return n


def norm_isd(name: str) -> str:
    n = name.strip().lower()
    n = n.replace("independent school district", "isd")
    n = n.replace("consolidated isd", "cisd")
    return re.sub(r"\s+", " ", n)


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


def parcels_shp(fips: str) -> str:
    hits = glob.glob(str(RAW / f"stratmap_*/**/*{fips}*.shp"), recursive=True)
    if not hits:
        raise FileNotFoundError(f"no parcel shapefile for {fips}")
    return hits[0]


def main():
    units = load_taxing_units()
    rate_by_id = {u[1]: u[5] for u in units}
    print(f"taxing units statewide: {len(units)}")

    for cname, cfg in COUNTIES.items():
        missing = [u for u in cfg["countywide"] if u not in rate_by_id]
        if missing:
            raise SystemExit(f"{cname}: unknown countywide unit ids {missing}")
        cfg["base"] = sum(rate_by_id[u] for u in cfg["countywide"])
        print(f"  {cname:10} base {cfg['base']:.6f} per $100")
        assert 0.25 < cfg["base"] < 0.9, f"{cname} base out of bounds"

    city_rates, isd_rates = {}, {}
    for _, uid, name, county, utype, rate in units:
        if county not in LOOKUP_COUNTY_CODES:
            continue
        if utype == "03":
            key = norm_city(name)
            if key not in city_rates or uid.split("-")[0] in {c["ptad"] for c in COUNTIES.values()}:
                city_rates[key] = (name, uid, rate)
        elif utype == "02":
            key = norm_isd(name)
            if key not in isd_rates or uid.split("-")[0] in {c["ptad"] for c in COUNTIES.values()}:
                isd_rates[key] = (name, uid, rate)

    rates_only = "--rates-only" in sys.argv  # reuse parcels_all; skip loads + spatial joins

    con = duckdb.connect(str(BUILD / "taxmap.duckdb"))
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("DROP TABLE IF EXISTS taxing_units")
    con.execute(
        """CREATE TABLE taxing_units(tax_year INT, unit_id TEXT, name TEXT,
           county_code TEXT, unit_type TEXT, rate_per_100 DOUBLE)"""
    )
    con.executemany("INSERT INTO taxing_units VALUES (?,?,?,?,?,?)", units)

    if rates_only:
        print("--rates-only: reusing existing parcels_all + boundary tables")
    else:
        print("loading TIGER boundaries (metro bbox) ...")
        _load_geodata(con)

    _load_side_attrs(con)
    _attach_rates_and_export(con, city_rates, isd_rates)
    print("done.")
    return 0


def _load_geodata(con):
    con.execute(
        f"""CREATE OR REPLACE TABLE places AS
        SELECT * FROM (
          SELECT NAME AS city_name,
                 ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
          FROM ST_Read('{PLACE_SHP}')
          WHERE LSAD != '57'  -- exclude CDPs: unincorporated, no city tax
        ) WHERE ST_Intersects(geom, {METRO_BBOX})"""
    )
    con.execute(
        f"""CREATE OR REPLACE TABLE isds AS
        SELECT * FROM (
          SELECT NAME AS isd_name,
                 ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
          FROM ST_Read('{UNSD_SHP}')
        ) WHERE ST_Intersects(geom, {METRO_BBOX})"""
    )
    fips_list = ",".join(f"'{c['fips']}'" for c in COUNTIES.values())
    con.execute(
        f"""CREATE OR REPLACE TABLE county_bounds AS
        SELECT GEOID AS fips, NAME AS county_name,
               ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
        FROM ST_Read('/vsizip/{COUNTY_ZIP}/tl_2025_us_county.shp')
        WHERE GEOID IN ({fips_list})"""
    )

    con.execute("DROP TABLE IF EXISTS parcels_all")
    con.execute(
        """CREATE TABLE parcels_all(prop_id TEXT, addr TEXT, mkt DOUBLE,
           county TEXT, base DOUBLE, city_name TEXT, isd_name TEXT, geom GEOMETRY)"""
    )
    for cname, cfg in COUNTIES.items():
        shp = parcels_shp(cfg["fips"])
        print(f"{cname}: {Path(shp).name}")
        con.execute(
            f"""INSERT INTO parcels_all
            SELECT prop_id, addr, mkt, county, base, c.city_name, i.isd_name, p.geom FROM (
              SELECT Prop_ID AS prop_id, SITUS_ADDR AS addr, MKT_VALUE AS mkt,
                     '{cname}' AS county, {cfg["base"]} AS base,
                     geom, ST_PointOnSurface(geom) AS pt
              FROM ST_Read('{shp}') WHERE geom IS NOT NULL
            ) p
            LEFT JOIN places c ON ST_Within(p.pt, c.geom)
            LEFT JOIN isds i ON ST_Within(p.pt, i.geom)"""
        )
    con.execute(
        """CREATE OR REPLACE TABLE parcels_all AS
        SELECT * EXCLUDE (rn) FROM (
          SELECT *, row_number() OVER (PARTITION BY county, prop_id, addr ORDER BY city_name, isd_name) rn
          FROM parcels_all) WHERE rn = 1"""
    )
    print("parcels total:", con.execute("SELECT count(*) FROM parcels_all").fetchone()[0])


def _load_side_attrs(con):
    """Owner + acreage per parcel (attribute-only read of the shapefiles;
    no spatial ops, so it's cheap to rebuild every run)."""
    con.execute(
        """CREATE OR REPLACE TABLE parcel_attrs(
           county TEXT, prop_id TEXT, owner TEXT, gis_area DOUBLE)"""
    )
    for cname, cfg in COUNTIES.items():
        shp = parcels_shp(cfg["fips"])
        con.execute(
            f"""INSERT INTO parcel_attrs
            SELECT '{cname}', Prop_ID, any_value(OWNER_NAME), any_value(GIS_AREA)
            FROM ST_Read('{shp}') GROUP BY Prop_ID"""
        )
    print("parcel_attrs:", con.execute("SELECT count(*) FROM parcel_attrs").fetchone()[0])


def _attach_rates_and_export(con, city_rates, isd_rates):
    unmatched = set()
    city_map, isd_map = [], []
    for (cn,) in con.execute("SELECT DISTINCT city_name FROM parcels_all WHERE city_name IS NOT NULL").fetchall():
        hit = city_rates.get(norm_city(cn))
        city_map.append((cn, hit[0] if hit else None, hit[1] if hit else None, hit[2] if hit else 0.0))
        if not hit:
            unmatched.add(f"CITY\t{cn}")
    for (iname,) in con.execute("SELECT DISTINCT isd_name FROM parcels_all WHERE isd_name IS NOT NULL").fetchall():
        hit = isd_rates.get(norm_isd(iname))
        isd_map.append((iname, hit[0] if hit else None, hit[1] if hit else None, hit[2] if hit else 0.0))
        if not hit:
            unmatched.add(f"ISD\t{iname}")
    con.execute("CREATE OR REPLACE TABLE city_rate_map(city_name TEXT, unit_name TEXT, unit_id TEXT, rate DOUBLE)")
    con.executemany("INSERT INTO city_rate_map VALUES (?,?,?,?)", city_map)
    con.execute("CREATE OR REPLACE TABLE isd_rate_map(isd_name TEXT, unit_name TEXT, unit_id TEXT, rate DOUBLE)")
    con.executemany("INSERT INTO isd_rate_map VALUES (?,?,?,?)", isd_map)
    (BUILD / "unmatched.txt").write_text("\n".join(sorted(unmatched)) or "none\n")
    print(f"unmatched boundary names: {len(unmatched)}")
    for u in sorted(unmatched):
        print("  ", u.replace("\t", " "))

    con.execute(
        """CREATE OR REPLACE TABLE parcels_rated AS
        SELECT p.prop_id, p.addr, p.mkt, p.county, p.city_name, p.isd_name,
               p.base + coalesce(c.rate, 0) + coalesce(i.rate, 0) AS nominal_rate,
               p.geom
        FROM parcels_all p
        LEFT JOIN city_rate_map c USING (city_name)
        LEFT JOIN isd_rate_map i USING (isd_name)"""
    )
    for row in con.execute(
        """SELECT county, count(*), round(min(nominal_rate),4), round(median(nominal_rate),4),
           round(max(nominal_rate),4) FROM parcels_rated GROUP BY county ORDER BY 2 DESC"""
    ).fetchall():
        print(f"  {row[0]:10} n={row[1]:>7}  min/med/max {row[2]}/{row[3]}/{row[4]}")

    print("writing parcels.geojsonseq ...")
    con.execute(
        f"""COPY (
          SELECT p.prop_id AS id, p.addr, p.mkt::BIGINT AS mkt, round(p.nominal_rate, 4) AS rate,
                 round(coalesce(i.rate, 0), 4) AS isdr,
                 p.isd_name AS isd, p.city_name AS cj, p.county AS cty,
                 a.owner AS own,
                 round(CASE WHEN coalesce(a.gis_area, 0) > 0 THEN a.gis_area
                       ELSE ST_Area_Spheroid(p.geom) / 4046.8564 END, 3) AS ac,
                 p.geom
          FROM parcels_rated p
          LEFT JOIN isd_rate_map i USING (isd_name)
          LEFT JOIN parcel_attrs a ON a.county = p.county AND a.prop_id = p.prop_id
        ) TO '{BUILD / "parcels.geojsonseq"}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')"""
    )

    print("writing isd.geojsonseq ...")
    con.execute("CREATE OR REPLACE TABLE metro_union AS SELECT ST_Union_Agg(geom) AS geom FROM county_bounds")
    con.execute(
        f"""COPY (
          SELECT i.isd_name AS name, s.rate, s.parcels, s.med_value,
                 ST_Intersection(i.geom, m.geom) AS geom
          FROM isds i
          JOIN (
            SELECT isd_name, round(median(nominal_rate),4) AS rate, count(*) AS parcels,
                   round(median(mkt),0)::BIGINT AS med_value
            FROM parcels_rated WHERE isd_name IS NOT NULL GROUP BY isd_name
          ) s USING (isd_name)
          CROSS JOIN metro_union m
        ) TO '{BUILD / "isd.geojsonseq"}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')"""
    )

    print("writing county.geojsonseq ...")
    name_by_fips = {c["fips"]: n for n, c in COUNTIES.items()}
    con.execute("CREATE OR REPLACE TABLE fips_names(fips TEXT, county TEXT)")
    con.executemany("INSERT INTO fips_names VALUES (?,?)", list(name_by_fips.items()))
    con.execute(
        f"""COPY (
          SELECT b.county_name AS name, s.rate, s.parcels, s.med_value, b.geom
          FROM county_bounds b
          JOIN fips_names f USING (fips)
          JOIN (
            SELECT county, round(median(nominal_rate),4) AS rate, count(*) AS parcels,
                   round(median(mkt),0)::BIGINT AS med_value
            FROM parcels_rated GROUP BY county
          ) s ON s.county = f.county
        ) TO '{BUILD / "county.geojsonseq"}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')"""
    )


if __name__ == "__main__":
    sys.exit(main())
