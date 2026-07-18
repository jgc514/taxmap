#!/usr/bin/env python3
"""Phase 1x: 63-county region (Bexar + 4 adjacency rings) -> nominal tax rate
-> GeoJSONSeq layers.

Supersedes build_metro.py (same v0 spatial-join approximation, same schema).
County set = every Texas county within 4 adjacency rings of Bexar, computed by
pipeline/county_rings.py. Per-county recipes define county-wide taxing units
(county govt + hospital/college districts, GCDs, taxing river authorities that
demonstrably tax the whole county). City + ISD come from TIGER point-in-polygon
against PTAD rates. Partial districts (ESD/MUD/WCID/FWSD, road/drainage/
navigation districts, city-scoped hospital + college districts such as Austin
Community College, Del Mar, Laredo College, Central Texas College) remain the
documented v0 gap until appraisal rolls arrive.

PTAD county codes are NOT derivable from FIPS by formula: FIPS alphabetizes
Mc* as "Mac" while PTAD sorts literally, shifting Mason/Maverick/McCulloch/
McMullen (and McLennan/Matagorda in ring 5). Every code below is verified at
runtime against the county-unit name in the PTAD workbook.

Outputs (data/build/):
  parcels-<region>.geojsonseq — per-archive parcel exports (8 regions)
  isd.geojsonseq              — ISD polygons clipped to the 63-county union
  county.geojsonseq           — 63 county polygons with stats
  taxmap.duckdb               — parcels_rated + taxing_units tables
  unmatched.txt               — TIGER city/ISD names with no PTAD rate match
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

# Ring-5 counties: their ISDs/cities can reach into ring-4 counties, so their
# PTAD codes join the city/ISD rate lookup (resolved by name at runtime).
RING5_NAMES = [
    "Brazos", "Brown", "Burleson", "Calhoun", "Coleman", "Concho", "Coryell",
    "Crockett", "Falls", "Fort Bend", "Grimes", "Hamilton", "Hidalgo", "Irion",
    "Kenedy", "McLennan", "Matagorda", "Milam", "Mills", "Starr", "Terrell",
    "Tom Green", "Waller", "Wharton",
]

# Per-county recipe: FIPS, PTAD code, adjacency ring, tile-archive region,
# county-wide taxing units. Cross-county units (San Antonio River Authority,
# Evergreen UWCD) appear under every county they tax.
COUNTIES = {
    # ── ring 0-1: original 8-county SA metro ────────────────────────────
    "Bexar": {
        "fips": "48029", "ptad": "015", "ring": 0, "region": "bexar",
        "countywide": [
            "015-000-00",  # Bexar County (incl. road & flood)
            "015-201-11",  # University Health System
            "015-201-15",  # Alamo Community College District
            "015-201-27",  # San Antonio River Authority
        ],
    },
    "Comal": {
        "fips": "48091", "ptad": "046", "ring": 1, "region": "metro",
        "countywide": ["046-000-00"],
    },
    "Guadalupe": {
        "fips": "48187", "ptad": "094", "ring": 1, "region": "metro",
        "countywide": ["094-000-00"],
    },
    "Medina": {
        "fips": "48325", "ptad": "163", "ring": 1, "region": "metro",
        "countywide": [
            "163-000-00",
            "163-201-11",  # Medina County Hospital District
            "163-201-23",  # Medina County Underground WCD
        ],
    },
    "Wilson": {
        "fips": "48493", "ptad": "247", "ring": 1, "region": "metro",
        "countywide": [
            "247-000-00",
            "247-201-11",  # Wilson County Hospital District
            "015-201-27",  # San Antonio River Authority (taxes Wilson too)
            "007-201-06",  # Evergreen UWCD (per Wilson appraisal roll)
        ],
    },
    "Atascosa": {
        "fips": "48013", "ptad": "007", "ring": 1, "region": "metro",
        "countywide": [
            "007-000-00",
            "007-201-06",  # Evergreen Underground WCD
        ],
    },
    "Kendall": {
        "fips": "48259", "ptad": "130", "ring": 1, "region": "metro",
        "countywide": [
            "130-000-00",
            "130-201-06",  # Cow Creek Groundwater Conservation
        ],
    },
    "Bandera": {
        "fips": "48019", "ptad": "010", "ring": 1, "region": "metro",
        "countywide": [
            "010-000-00",
            "010-201-27",  # Bandera River Authority
        ],
    },
    # ── ring 2 ──────────────────────────────────────────────────────────
    "Blanco": {
        "fips": "48031", "ptad": "016", "ring": 2, "region": "central-south",
        "countywide": ["016-000-00", "016-201-06"],  # Blanco-Pedernales GCD
    },
    "Caldwell": {
        "fips": "48055", "ptad": "028", "ring": 2, "region": "central-south",
        "countywide": ["028-000-00", "028-202-06"],  # Plum Creek UWD (GCD)
    },
    "Frio": {
        "fips": "48163", "ptad": "082", "ring": 2, "region": "west",
        "countywide": [
            "082-000-00",
            "082-201-11",  # Frio Hospital District (rate 0 in 2025)
            "007-201-06",  # Evergreen UWCD (covers Frio)
        ],
    },
    "Gillespie": {
        "fips": "48171", "ptad": "086", "ring": 2, "region": "west",
        "countywide": ["086-000-00", "086-201-06"],  # Hill Country UWCD
    },
    "Gonzales": {
        "fips": "48177", "ptad": "089", "ring": 2, "region": "central-south",
        "countywide": [
            "089-000-00",
            "089-201-06",  # Gonzales County Underground WCD
            "089-201-11",  # Gonzales County Hospital District
        ],
    },
    "Hays": {
        "fips": "48209", "ptad": "105", "ring": 2, "region": "central-south",
        "countywide": ["105-000-00"],
    },
    "Karnes": {
        "fips": "48255", "ptad": "128", "ring": 2, "region": "south",
        "countywide": [
            "128-000-00",
            "128-201-11",  # Karnes County Hospital District
            "007-201-06",  # Evergreen UWCD (covers Karnes)
        ],
    },
    "Kerr": {
        "fips": "48265", "ptad": "133", "ring": 2, "region": "west",
        "countywide": [
            "133-000-00",
            "133-201-23",  # Headwaters Underground WCD
            "133-201-27",  # Upper Guadalupe River Authority
        ],
    },
    "La Salle": {
        "fips": "48283", "ptad": "142", "ring": 2, "region": "west",
        "countywide": ["142-000-00", "142-201-06"],  # Wintergarden UWD
    },
    "Live Oak": {
        "fips": "48297", "ptad": "149", "ring": 2, "region": "south",
        "countywide": ["149-000-00", "149-201-06"],  # Live Oak UWCD
    },
    "McMullen": {
        "fips": "48311", "ptad": "162", "ring": 2, "region": "south",
        "countywide": ["162-000-00", "162-201-06"],  # McMullen County GWD
    },
    "Real": {
        "fips": "48385", "ptad": "193", "ring": 2, "region": "west",
        "countywide": ["193-000-00", "193-201-28"],  # Real-Edwards C&RD
    },
    "Uvalde": {
        "fips": "48463", "ptad": "232", "ring": 2, "region": "west",
        "countywide": [
            "232-000-00",
            "232-201-06",  # Uvalde County Underground WCD
            "232-201-15",  # Southwest Texas Junior College (countywide)
        ],
    },
    "Zavala": {
        "fips": "48507", "ptad": "254", "ring": 2, "region": "west",
        "countywide": [
            "254-000-00",
            "232-201-15",  # SW Texas Junior College (per Comptroller directory)
            "142-201-06",  # Wintergarden UWD (per Comptroller directory)
        ],
    },
    # ── ring 3 ──────────────────────────────────────────────────────────
    "Bastrop": {
        "fips": "48021", "ptad": "011", "ring": 3, "region": "central-south",
        "countywide": ["011-000-00"],
    },
    "Bee": {
        "fips": "48025", "ptad": "013", "ring": 3, "region": "south",
        "countywide": ["013-000-00", "013-201-06"],  # Bee County Ground WCD
    },
    "Burnet": {
        "fips": "48053", "ptad": "027", "ring": 3, "region": "central-north",
        "countywide": ["027-000-00", "027-201-06"],  # Central Texas GCD
    },
    "DeWitt": {
        "fips": "48123", "ptad": "062", "ring": 3, "region": "central-south",
        "countywide": ["062-000-00", "062-201-06"],  # Pecan Valley GCD
    },
    "Dimmit": {
        "fips": "48127", "ptad": "064", "ring": 3, "region": "west",
        "countywide": [
            "064-000-00",
            "064-201-11",  # Dimmit Regional Hospital District
            "142-201-06",  # Wintergarden UWD (per Comptroller directory)
        ],
    },
    "Duval": {
        "fips": "48131", "ptad": "066", "ring": 3, "region": "south",
        "countywide": [
            "066-000-00",
            "066-201-23",  # Duval County GCD
            "066-201-33",  # Duval County Vocational District
        ],
    },
    "Edwards": {
        "fips": "48137", "ptad": "069", "ring": 3, "region": "west",
        "countywide": ["069-000-00"],
    },
    "Fayette": {
        "fips": "48149", "ptad": "075", "ring": 3, "region": "central-south",
        "countywide": ["075-000-00", "075-201-23"],  # Fayette County GWCD
    },
    "Goliad": {
        "fips": "48175", "ptad": "088", "ring": 3, "region": "coastal",
        "countywide": ["088-000-00", "088-201-06"],  # Goliad County Ground WCD
    },
    "Jim Wells": {
        "fips": "48249", "ptad": "125", "ring": 3, "region": "south",
        "countywide": ["125-000-00"],
    },
    "Kimble": {
        "fips": "48267", "ptad": "134", "ring": 3, "region": "central-north",
        "countywide": [
            "134-000-00",
            "134-201-06",  # Kimble County Ground WCD
            "134-201-11",  # Kimble County Hospital District
        ],
    },
    "Kinney": {
        "fips": "48271", "ptad": "136", "ring": 3, "region": "west",
        "countywide": ["136-000-00", "136-201-23"],  # Kinney County GCD
    },
    "Lavaca": {
        "fips": "48285", "ptad": "143", "ring": 3, "region": "central-south",
        "countywide": ["143-000-00"],  # hospital districts all partial
    },
    "Llano": {
        "fips": "48299", "ptad": "150", "ring": 3, "region": "central-north",
        "countywide": ["150-000-00"],
    },
    "Mason": {
        "fips": "48319", "ptad": "157", "ring": 3, "region": "central-north",
        "countywide": ["157-000-00"],
    },
    "Maverick": {
        "fips": "48323", "ptad": "159", "ring": 3, "region": "west",
        "countywide": ["159-000-00", "159-201-11"],  # Maverick County Hospital
    },
    "San Patricio": {
        "fips": "48409", "ptad": "205", "ring": 3, "region": "coastal",
        "countywide": ["205-000-00", "205-201-08"],  # SP County Drainage Dist
    },
    "Travis": {
        "fips": "48453", "ptad": "227", "ring": 3, "region": "travis",
        "countywide": [
            "227-000-00",
            "227-201-11",  # Travis County Healthcare District (Central Health)
            # ACC (227-201-15) is annexation-based, NOT countywide: v0 gap
        ],
    },
    "Webb": {
        "fips": "48479", "ptad": "240", "ring": 3, "region": "south",
        "countywide": ["240-000-00"],  # Laredo College is city-scoped
    },
    # ── ring 4 ──────────────────────────────────────────────────────────
    "Aransas": {
        "fips": "48007", "ptad": "004", "ring": 4, "region": "coastal",
        "countywide": ["004-000-00"],
    },
    "Austin": {
        "fips": "48015", "ptad": "008", "ring": 4, "region": "central-south",
        "countywide": ["008-000-00"],  # Bellville Hospital Dist is partial
    },
    "Bell": {
        "fips": "48027", "ptad": "014", "ring": 4, "region": "central-north",
        "countywide": ["014-000-00", "014-201-06"],  # Clearwater UWCD
    },
    "Brooks": {
        "fips": "48047", "ptad": "024", "ring": 4, "region": "south",
        "countywide": ["024-000-00", "024-201-23"],  # Brush Country GCD
    },
    "Colorado": {
        "fips": "48089", "ptad": "045", "ring": 4, "region": "central-south",
        "countywide": ["045-000-00", "045-201-23"],  # Colorado County CD
    },
    "Jackson": {
        "fips": "48239", "ptad": "120", "ring": 4, "region": "coastal",
        "countywide": [
            "120-000-00",
            "120-201-06",  # Texana GCD
            "120-202-11",  # Jackson County Hospital District
        ],
    },
    "Jim Hogg": {
        "fips": "48247", "ptad": "124", "ring": 4, "region": "south",
        "countywide": ["124-000-00"],
    },
    "Kleberg": {
        "fips": "48273", "ptad": "137", "ring": 4, "region": "south",
        "countywide": ["137-000-00"],
    },
    "Lampasas": {
        "fips": "48281", "ptad": "141", "ring": 4, "region": "central-north",
        "countywide": ["141-000-00"],
    },
    "Lee": {
        "fips": "48287", "ptad": "144", "ring": 4, "region": "central-south",
        "countywide": ["144-000-00"],
    },
    "McCulloch": {
        "fips": "48307", "ptad": "160", "ring": 4, "region": "central-north",
        "countywide": ["160-000-00", "160-201-11"],  # Heart of Texas Mem Hosp
    },
    "Menard": {
        "fips": "48327", "ptad": "164", "ring": 4, "region": "central-north",
        "countywide": [
            "164-000-00",
            "164-201-11",  # Menard County Hospital District
            # 164-201-23 Menard UWD (0.64/100) excluded pending verification:
            # rate is 20x typical for a GCD, suspected partial/anomalous
        ],
    },
    "Nueces": {
        "fips": "48355", "ptad": "178", "ring": 4, "region": "coastal",
        "countywide": [
            "178-000-00",
            "178-201-11",  # Nueces County Hospital District
            # Del Mar College (178-201-15) is city-scoped: v0 gap
        ],
    },
    "Refugio": {
        "fips": "48391", "ptad": "196", "ring": 4, "region": "coastal",
        "countywide": [
            "196-000-00",
            "196-201-06",  # Refugio Ground WCD
            "196-201-11",  # Refugio Co Memorial Hospital District
        ],
    },
    "San Saba": {
        "fips": "48411", "ptad": "206", "ring": 4, "region": "central-north",
        "countywide": ["206-000-00"],
    },
    "Schleicher": {
        "fips": "48413", "ptad": "207", "ring": 4, "region": "west",
        "countywide": [
            "207-000-00",
            "207-201-06",  # Plateau Underground Water District
            "207-201-11",  # Schleicher County Hospital District
        ],
    },
    "Sutton": {
        "fips": "48435", "ptad": "218", "ring": 4, "region": "west",
        "countywide": [
            "218-000-00",
            "218-201-11",  # Sutton County Hospital District
            "218-201-23",  # Sutton County Underground WCD
        ],
    },
    "Val Verde": {
        "fips": "48465", "ptad": "233", "ring": 4, "region": "west",
        "countywide": ["233-000-00", "233-201-11"],  # Val Verde Hospital Dist
    },
    "Victoria": {
        "fips": "48469", "ptad": "235", "ring": 4, "region": "coastal",
        "countywide": [
            "235-000-00",
            "235-203-06",  # Victoria County Ground WD
            "235-201-15",  # Victoria Junior College District (countywide)
        ],
    },
    "Washington": {
        "fips": "48477", "ptad": "239", "ring": 4, "region": "central-south",
        "countywide": [
            "239-000-00",
            "239-201-15",  # Blinn Junior College District (countywide)
        ],
    },
    "Williamson": {
        "fips": "48491", "ptad": "246", "ring": 4, "region": "central-north",
        "countywide": ["246-000-00"],
    },
    "Zapata": {
        "fips": "48505", "ptad": "253", "ring": 4, "region": "south",
        "countywide": ["253-000-00"],
    },
}

# Pristine hand-curated set, snapshotted before the statewide merge below —
# gen_recipes.py imports this to know which counties NOT to auto-generate.
HAND_CURATED = dict(COUNTIES)


def _load_statewide():
    """Merge auto-generated recipes (gen_recipes.py) for the rest of Texas,
    packing new counties into archive regions by a north-to-south geographic
    sweep with a parcel budget (oversized single counties get their own
    region; the tile script splits any oversized export into parts)."""
    try:
        from recipes_statewide import STATEWIDE_COUNTIES
    except ImportError:
        return
    import glob as _glob
    import struct as _struct

    budget = 550_000
    entries = []
    for cname, r in STATEWIDE_COUNTIES.items():
        hits = _glob.glob(str(RAW / f"stratmap_{r['fips']}/**/*.dbf"), recursive=True)
        # sum every part: multi-part counties (Harris) ship several dbfs
        n = sum(_struct.unpack("<I", Path(h).read_bytes()[4:8])[0] for h in hits)
        entries.append((cname, r, n))

    import duckdb as _duckdb
    con = _duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    cent = dict(
        con.execute(
            f"""SELECT GEOID, [ST_X(ST_Centroid(geom)), ST_Y(ST_Centroid(geom))]
            FROM ST_Read('/vsizip/{COUNTY_ZIP}/tl_2025_us_county.shp')
            WHERE STATEFP = '48'"""
        ).fetchall()
    )
    # Snake sweep: 1.5-degree latitude bands north->south, alternating east/west.
    def sweep_key(e):
        lon, lat = cent[e[1]["fips"]]
        band = -round(lat / 1.5)
        return (band, lon if band % 2 == 0 else -lon)

    entries.sort(key=sweep_key)
    region_i, acc = 0, 0
    for cname, r, n in entries:
        if acc > 0 and acc + n > budget:
            region_i += 1
            acc = 0
        acc += n
        COUNTIES[cname] = {
            "fips": r["fips"], "ptad": r["ptad"], "ring": None,
            "region": f"tx{region_i:02d}", "countywide": r["countywide"],
            "no_parcels": n == 0,
        }


_load_statewide()
REGIONS = sorted({c["region"] for c in COUNTIES.values() if not c.get("no_parcels")})


def norm_city(name: str) -> str:
    n = name.strip().lower()
    n = re.sub(r"^(city|town|village) of ", "", n)
    n = n.replace("-", " ")  # PTAD "Little-River Academy" vs TIGER "Little River-Academy"
    return re.sub(r"\s+", " ", n)


# TIGER vs PTAD school-name variants seen statewide (spelling drift).
ISD_ALIASES = {
    "culbersoncountyallamooreisd": "culbersoncountyallamoreisd",
    "lapoynerisd": "lapoynorisd",
}


def norm_isd(name: str) -> str:
    n = name.strip().lower()
    n = n.replace("independent school district", "isd")
    n = n.replace("municipal school district", "msd")   # Stafford MSD
    n = n.replace("consolidated common school district", "ccsd")
    n = n.replace("common school district", "csd")
    n = n.replace("consolidated isd", "cisd")
    n = n.replace(" county isd", " isd")  # PTAD "Schleicher County ISD" vs TIGER "Schleicher ISD"
    n = n.replace(" collegiate ", " ")    # TIGER P-TECH rebrands (Floydada Collegiate ISD)
    n = re.sub(r"\bcisd\b", "isd", n)     # PTAD "Clyde ISD" vs TIGER "Clyde Consolidated ISD"
    key = re.sub(r"[^a-z0-9]", "", n)     # punctuation/space-insensitive (LaPoyner, County-Allamoore)
    return ISD_ALIASES.get(key, key)


def norm_county(name: str) -> str:
    return re.sub(r"[^a-z]", "", name.lower())


def load_taxing_units():
    """Returns (units, county_names) where county_names maps PTAD county
    code -> county name (from the XXX-000-00 unit rows)."""
    ws = openpyxl.load_workbook(PTAD_XLSX, read_only=True)["Statewide"]
    units, county_names = [], {}
    for row in ws.iter_rows(min_row=4, values_only=True):
        name, uid, rate = row[0], row[1], row[2]
        if not uid:
            continue
        name = name.strip().rstrip("*").strip()
        county, num, utype = uid.split("-")
        if num == "000":
            county_names[county] = name
        units.append((TAX_YEAR, uid, name, county, utype, float(rate or 0)))
    return units, county_names


def verify_ptad_codes(county_names):
    """FIPS and PTAD alphabetize Mc* differently — never trust a formula."""
    for cname, cfg in COUNTIES.items():
        ptad_name = county_names.get(cfg["ptad"], "")
        if norm_county(ptad_name) != norm_county(cname):
            raise SystemExit(
                f"PTAD code mismatch: {cname} configured as {cfg['ptad']} "
                f"but that code is named {ptad_name!r}"
            )


def resolve_ring5_codes(county_names):
    by_name = {norm_county(n): c for c, n in county_names.items()}
    codes = set()
    for n in RING5_NAMES:
        code = by_name.get(norm_county(n))
        if not code:
            raise SystemExit(f"ring-5 county {n!r} not found in PTAD workbook")
        codes.add(code)
    return codes


def parcels_shps(fips: str) -> list:
    """ALL shapefiles for a county — huge counties ship multi-part (Harris
    is harris_east + harris_west; loading only the first part silently
    drops half the county)."""
    hits = sorted(glob.glob(str(RAW / f"stratmap_*/**/*{fips}*.shp"), recursive=True))
    if not hits:
        raise FileNotFoundError(f"no parcel shapefile for {fips}")
    return hits


def parcels_geom_sql(shp: str) -> str:
    """StratMap vintages are inconsistent: most counties ship EPSG:4326 but
    the 2025-05 refresh ships Web Mercator, which silently breaks every
    spatial join and puts the county in the wrong place. Read the .prj and
    transform when needed; refuse unknown projections."""
    prj = Path(shp).with_suffix(".prj").read_text()
    if prj.startswith("GEOGCS"):
        return "geom"
    if "Web_Mercator" in prj:
        return "ST_Transform(geom, 'EPSG:3857', 'EPSG:4326', always_xy := true)"
    raise SystemExit(f"unrecognized CRS in {shp}: {prj[:80]}")


def main():
    units, county_names = load_taxing_units()
    verify_ptad_codes(county_names)
    rate_by_id = {u[1]: u[5] for u in units}
    print(f"taxing units statewide: {len(units)}")

    for cname, cfg in COUNTIES.items():
        missing = [u for u in cfg["countywide"] if u not in rate_by_id]
        if missing:
            raise SystemExit(f"{cname}: unknown countywide unit ids {missing}")
        cfg["base"] = sum(rate_by_id[u] for u in cfg["countywide"])
        print(f"  {cname:14} ring {cfg['ring']}  base {cfg['base']:.6f} per $100")
        # PTAD has real zero/near-zero reports (Culberson unreported, Reagan
        # 0.0152) — warn on the low side, hard-fail only on absurd highs.
        assert 0 <= cfg["base"] < 1.8, f"{cname} base out of bounds"
        if cfg["base"] < 0.15:
            print(f"    WARNING: {cname} base {cfg['base']:.4f} — PTAD reporting gap?")

    # Statewide, city/ISD names collide (two "Reno"s, two "Lakeside"s, ...):
    # keep every candidate and resolve per parcel county — prefer the unit
    # listed in the parcel's county, then one in an adjacent county (cities
    # and ISDs straddle county lines), else a sole statewide candidate.
    city_rates, isd_rates = {}, {}
    for _, uid, name, county, utype, rate in units:
        if utype == "03":
            city_rates.setdefault(norm_city(name), []).append((name, uid, rate, county))
        elif utype == "02":
            isd_rates.setdefault(norm_isd(name), []).append((name, uid, rate, county))

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
        print("loading TIGER boundaries (63-county region) ...")
        _load_geodata(con)

    _load_side_attrs(con)
    _attach_rates_and_export(con, city_rates, isd_rates)
    print("done.")
    return 0


def _load_geodata(con):
    fips_list = ",".join(f"'{c['fips']}'" for c in COUNTIES.values())
    con.execute(
        f"""CREATE OR REPLACE TABLE county_bounds AS
        SELECT GEOID AS fips, NAME AS county_name,
               ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
        FROM ST_Read('/vsizip/{COUNTY_ZIP}/tl_2025_us_county.shp')
        WHERE GEOID IN ({fips_list})"""
    )
    n = con.execute("SELECT count(*) FROM county_bounds").fetchone()[0]
    assert n == len(COUNTIES), f"county_bounds has {n} rows, expected {len(COUNTIES)}"
    # Region envelope (+0.1 deg) filters the statewide TIGER layers.
    xmin, ymin, xmax, ymax = con.execute(
        """SELECT min(ST_XMin(geom)) - 0.1, min(ST_YMin(geom)) - 0.1,
                  max(ST_XMax(geom)) + 0.1, max(ST_YMax(geom)) + 0.1
        FROM county_bounds"""
    ).fetchone()
    bbox = f"ST_SetCRS(ST_MakeEnvelope({xmin}, {ymin}, {xmax}, {ymax}), 'EPSG:4326')"
    print(f"  region bbox: {xmin:.2f},{ymin:.2f} -> {xmax:.2f},{ymax:.2f}")

    con.execute(
        f"""CREATE OR REPLACE TABLE places AS
        SELECT * FROM (
          SELECT NAME AS city_name,
                 ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
          FROM ST_Read('{PLACE_SHP}')
          WHERE LSAD != '57'  -- exclude CDPs: unincorporated, no city tax
        ) WHERE ST_Intersects(geom, {bbox})"""
    )
    con.execute(
        f"""CREATE OR REPLACE TABLE isds AS
        SELECT * FROM (
          SELECT NAME AS isd_name,
                 ST_Transform(geom, 'EPSG:4269', 'EPSG:4326', always_xy := true) AS geom
          FROM ST_Read('{UNSD_SHP}')
        ) WHERE ST_Intersects(geom, {bbox})"""
    )

    con.execute("DROP TABLE IF EXISTS parcels_all")
    con.execute(
        """CREATE TABLE parcels_all(prop_id TEXT, addr TEXT, mkt DOUBLE,
           county TEXT, base DOUBLE, city_name TEXT, isd_name TEXT, geom GEOMETRY)"""
    )
    for cname, cfg in COUNTIES.items():
        if cfg.get("no_parcels"):
            print(f"{cname}: NO PARCEL DATA (boundary-only county)")
            continue
        # multi-part counties (Harris = east + west): load every shapefile
        for shp in parcels_shps(cfg["fips"]):
            gsql = parcels_geom_sql(shp)
            print(f"{cname}: {Path(shp).name}" + (" [3857->4326]" if "Transform" in gsql else ""))
            con.execute(
                f"""INSERT INTO parcels_all
                SELECT prop_id, addr, mkt, county, base, c.city_name, i.isd_name, p.geom FROM (
                  SELECT Prop_ID AS prop_id, SITUS_ADDR AS addr,
                         -- some CADs export values as text ("$ 117,596"): strip
                         -- and TRY_CAST so one bad row can't abort the build
                         TRY_CAST(regexp_replace(CAST(MKT_VALUE AS VARCHAR), '[^0-9.]', '', 'g') AS DOUBLE) AS mkt,
                         '{cname}' AS county, {cfg["base"]} AS base,
                         {gsql} AS geom, ST_PointOnSurface({gsql}) AS pt
                  FROM ST_Read('{shp}') WHERE geom IS NOT NULL
                ) p
                LEFT JOIN places c ON ST_Within(p.pt, c.geom)
                LEFT JOIN isds i ON ST_Within(p.pt, i.geom)"""
            )
    # Dedup stacked/duplicated rows sharing a real prop_id. Some CADs (Travis)
    # export Prop_ID='0' for a large share of parcels — those are distinct
    # properties, never collapse them.
    con.execute(
        """CREATE OR REPLACE TABLE parcels_all AS
        SELECT * EXCLUDE (rn) FROM (
          SELECT *, CASE WHEN prop_id IS NULL OR trim(prop_id) IN ('', '0') THEN 1
                         ELSE row_number() OVER (PARTITION BY county, prop_id, addr
                                                 ORDER BY city_name, isd_name) END rn
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
        if cfg.get("no_parcels"):
            continue
        for shp in parcels_shps(cfg["fips"]):
            # CAST: some counties store Prop_ID as BIGINT; anti-join keeps a
            # multi-part county's boundary-straddling ids from duplicating
            # (NULL-safe: null ids carry no joinable attrs, drop them here)
            con.execute(
                f"""INSERT INTO parcel_attrs
                SELECT '{cname}', CAST(Prop_ID AS VARCHAR), any_value(OWNER_NAME),
                       any_value(TRY_CAST(regexp_replace(CAST(GIS_AREA AS VARCHAR), '[^0-9.]', '', 'g') AS DOUBLE))
                FROM ST_Read('{shp}')
                WHERE Prop_ID IS NOT NULL
                  AND CAST(Prop_ID AS VARCHAR) NOT IN (
                    SELECT prop_id FROM parcel_attrs
                    WHERE county = '{cname}' AND prop_id IS NOT NULL)
                GROUP BY Prop_ID"""
            )
    print("parcel_attrs:", con.execute("SELECT count(*) FROM parcel_attrs").fetchone()[0])


def _adjacency_by_ptad(con):
    """PTAD-code adjacency between loaded counties (shared boundary)."""
    ptad_by_fips = {c["fips"]: c["ptad"] for c in COUNTIES.values()}
    adj = {}
    for a, b in con.execute(
        """SELECT a.fips, b.fips FROM county_bounds a JOIN county_bounds b
        ON a.fips < b.fips AND ST_Intersects(a.geom, b.geom)"""
    ).fetchall():
        pa, pb = ptad_by_fips[a], ptad_by_fips[b]
        adj.setdefault(pa, set()).add(pb)
        adj.setdefault(pb, set()).add(pa)
    return adj


def _attach_rates_and_export(con, city_rates, isd_rates):
    unmatched = set()
    adj = _adjacency_by_ptad(con)
    ptad_of = {n: c["ptad"] for n, c in COUNTIES.items()}

    def resolve(cands, county):
        code = ptad_of[county]
        if not cands:
            return None
        own = [c for c in cands if c[3] == code]
        if own:
            return own[0]
        near = [c for c in cands if c[3] in adj.get(code, ())]
        if near:
            return near[0]
        return cands[0] if len(cands) == 1 else None

    city_map, isd_map = [], []
    for county, cn in con.execute(
        "SELECT DISTINCT county, city_name FROM parcels_all WHERE city_name IS NOT NULL"
    ).fetchall():
        hit = resolve(city_rates.get(norm_city(cn)), county)
        city_map.append((county, cn, hit[0] if hit else None, hit[1] if hit else None, hit[2] if hit else 0.0))
        if not hit:
            unmatched.add(f"CITY\t{cn}\t({county})")
    for county, iname in con.execute(
        "SELECT DISTINCT county, isd_name FROM parcels_all WHERE isd_name IS NOT NULL"
    ).fetchall():
        hit = resolve(isd_rates.get(norm_isd(iname)), county)
        isd_map.append((county, iname, hit[0] if hit else None, hit[1] if hit else None, hit[2] if hit else 0.0))
        if not hit:
            unmatched.add(f"ISD\t{iname}\t({county})")
    con.execute(
        """CREATE OR REPLACE TABLE city_rate_map(
           county TEXT, city_name TEXT, unit_name TEXT, unit_id TEXT, rate DOUBLE)"""
    )
    con.executemany("INSERT INTO city_rate_map VALUES (?,?,?,?,?)", city_map)
    con.execute(
        """CREATE OR REPLACE TABLE isd_rate_map(
           county TEXT, isd_name TEXT, unit_name TEXT, unit_id TEXT, rate DOUBLE)"""
    )
    con.executemany("INSERT INTO isd_rate_map VALUES (?,?,?,?,?)", isd_map)
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
        LEFT JOIN city_rate_map c ON c.county = p.county AND c.city_name = p.city_name
        LEFT JOIN isd_rate_map i ON i.county = p.county AND i.isd_name = p.isd_name"""
    )
    for row in con.execute(
        """SELECT county, count(*), round(min(nominal_rate),4), round(median(nominal_rate),4),
           round(max(nominal_rate),4) FROM parcels_rated GROUP BY county ORDER BY 2 DESC"""
    ).fetchall():
        print(f"  {row[0]:14} n={row[1]:>7}  min/med/max {row[2]}/{row[3]}/{row[4]}")

    region_of = {n: c["region"] for n, c in COUNTIES.items()}
    con.execute("CREATE OR REPLACE TABLE county_region(county TEXT, region TEXT)")
    con.executemany("INSERT INTO county_region VALUES (?,?)", list(region_of.items()))
    for region in REGIONS:
        out = BUILD / f"parcels-{region}.geojsonseq"
        print(f"writing {out.name} ...")
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
              JOIN county_region r ON r.county = p.county AND r.region = '{region}'
              LEFT JOIN isd_rate_map i ON i.county = p.county AND i.isd_name = p.isd_name
              LEFT JOIN parcel_attrs a ON a.county = p.county AND a.prop_id = p.prop_id
            ) TO '{out}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')"""
        )

    print("writing isd.geojsonseq ...")
    con.execute("CREATE OR REPLACE TABLE region_union AS SELECT ST_Union_Agg(geom) AS geom FROM county_bounds")
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
          CROSS JOIN region_union m
        ) TO '{BUILD / "isd.geojsonseq"}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')"""
    )

    print("writing county.geojsonseq ...")
    con.execute("CREATE OR REPLACE TABLE fips_names(fips TEXT, county TEXT, base DOUBLE)")
    con.executemany(
        "INSERT INTO fips_names VALUES (?,?,?)",
        [(c["fips"], n, c["base"]) for n, c in COUNTIES.items()],
    )
    # LEFT JOIN + coalesce: a boundary-only county (no parcel data shared,
    # e.g. Donley) still shows its county-wide base rate on the choropleth.
    con.execute(
        f"""COPY (
          SELECT b.county_name AS name, coalesce(s.rate, round(f.base, 4)) AS rate,
                 coalesce(s.parcels, 0) AS parcels, s.med_value, b.geom
          FROM county_bounds b
          JOIN fips_names f USING (fips)
          LEFT JOIN (
            SELECT county, round(median(nominal_rate),4) AS rate, count(*) AS parcels,
                   round(median(mkt),0)::BIGINT AS med_value
            FROM parcels_rated GROUP BY county
          ) s ON s.county = f.county
        ) TO '{BUILD / "county.geojsonseq"}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')"""
    )


if __name__ == "__main__":
    sys.exit(main())
