#!/bin/bash
# Statewide: StratMap 2025 parcels for every Texas county not already on disk.
# Texas county FIPS are the odd numbers 48001..48507. Resume-capable: skips
# any county whose extracted shapefile already exists. Harris/Dallas/Tarrant
# zips are multi-GB — expect this to run for a while.
set -u
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
BASE="https://data.geographic.texas.gov/0fa04328-872e-481c-b453-126a74777593/resources"
RAW="$(cd "$(dirname "$0")/.." && pwd)/data/raw"
mkdir -p "$RAW"

fail=0
for n in $(seq 1 2 507); do
  f=$(printf "48%03d" "$n")
  zip="$RAW/stratmap25-landparcels_${f}_lp.zip"
  dir="$RAW/stratmap_${f}"
  # Bexar's original extract lives in stratmap_bexar
  if [ "$f" = "48029" ]; then dir="$RAW/stratmap_bexar"; fi
  if [ -d "$dir" ] && ls "$dir"/*.shp >/dev/null 2>&1; then
    continue
  fi
  if [ ! -s "$zip" ]; then
    echo "GET $f"
    curl -fSL --retry 3 -C - -A "$UA" -o "$zip.part" "$BASE/stratmap25-landparcels_${f}_lp.zip" \
      && mv "$zip.part" "$zip" \
      || { echo "FAIL: $f"; fail=1; continue; }
  fi
  mkdir -p "$dir"
  unzip -oq "$zip" -d "$dir" || { echo "UNZIP FAIL: $f"; fail=1; continue; }
  echo "OK: $f ($(du -h "$zip" | cut -f1))"
done
echo "=== STATEWIDE DOWNLOADS DONE (fail=$fail) ==="
ls -d "$RAW"/stratmap_* | wc -l
exit $fail
