#!/bin/bash
# Ring 2-4 expansion: StratMap 2025 parcels for the 55 counties beyond the
# original 8-county metro (all counties within 4 adjacency rings of Bexar —
# see pipeline/county_rings.py). Downloads + extracts each into data/raw.
set -u
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
BASE="https://data.geographic.texas.gov/0fa04328-872e-481c-b453-126a74777593/resources"
RAW="$(cd "$(dirname "$0")/.." && pwd)/data/raw"
mkdir -p "$RAW"

FIPS_NEW="48007 48015 48021 48025 48027 48031 48047 48053 48055 48089 \
48123 48127 48131 48137 48149 48163 48171 48175 48177 48209 48239 48247 \
48249 48255 48265 48267 48271 48273 48281 48283 48285 48287 48297 48299 \
48307 48311 48319 48323 48327 48355 48385 48391 48409 48411 48413 48435 \
48453 48463 48465 48469 48477 48479 48491 48505 48507"

fail=0
for f in $FIPS_NEW; do
  zip="$RAW/stratmap25-landparcels_${f}_lp.zip"
  dir="$RAW/stratmap_${f}"
  if [ -d "$dir" ] && ls "$dir"/*.shp >/dev/null 2>&1; then
    echo "SKIP (extracted): $f"; continue
  fi
  if [ ! -s "$zip" ]; then
    echo "GET $f"
    curl -fSL --retry 3 -A "$UA" -o "$zip.part" "$BASE/stratmap25-landparcels_${f}_lp.zip" \
      && mv "$zip.part" "$zip" \
      || { rm -f "$zip.part"; echo "FAIL: $f"; fail=1; continue; }
  fi
  mkdir -p "$dir"
  unzip -oq "$zip" -d "$dir" || { echo "UNZIP FAIL: $f"; fail=1; continue; }
  echo "OK: $f ($(du -h "$zip" | cut -f1))"
done
echo "=== RING4 DOWNLOADS DONE (fail=$fail) ==="
exit $fail
