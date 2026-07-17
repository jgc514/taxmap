#!/bin/bash
# Phase 0 source data: Bexar County (FIPS 48029), tax year 2025.
# TxGIO's CDN rejects curl's default user-agent, hence the browser UA.
set -u
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
RAW="$(cd "$(dirname "$0")/.." && pwd)/data/raw"
mkdir -p "$RAW"

fetch() {  # fetch <url> <dest-relative-to-RAW>
  local url="$1" dest="$RAW/$2"
  if [ -s "$dest" ]; then echo "SKIP (exists): $2"; return 0; fi
  echo "GET $2"
  curl -fSL --retry 3 -A "$UA" -o "$dest.part" "$url" && mv "$dest.part" "$dest" \
    && echo "OK: $2 ($(du -h "$dest" | cut -f1))" \
    || { rm -f "$dest.part"; echo "FAIL: $2 <- $url"; return 1; }
}

fail=0
fetch "https://data.geographic.texas.gov/0fa04328-872e-481c-b453-126a74777593/resources/stratmap25-landparcels_48029_lp.zip" "stratmap25-landparcels_48029_lp.zip" || fail=1
fetch "https://www2.census.gov/geo/tiger/TIGER2025/PLACE/tl_2025_48_place.zip" "tl_2025_48_place.zip" \
  || fetch "https://www2.census.gov/geo/tiger/TIGER2024/PLACE/tl_2024_48_place.zip" "tl_2024_48_place.zip" || fail=1
fetch "https://www2.census.gov/geo/tiger/TIGER2025/UNSD/tl_2025_48_unsd.zip" "tl_2025_48_unsd.zip" \
  || fetch "https://www2.census.gov/geo/tiger/TIGER2024/UNSD/tl_2024_48_unsd.zip" "tl_2024_48_unsd.zip" || fail=1
fetch "https://www2.census.gov/geo/tiger/TIGER2025/COUNTY/tl_2025_us_county.zip" "tl_2025_us_county.zip" \
  || fetch "https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip" "tl_2024_us_county.zip" || fail=1
fetch "https://comptroller.texas.gov/taxes/property-tax/docs/2025-total-rates-levies.xlsx" "ptad-2025-total-rates-levies.xlsx" \
  || fetch "https://comptroller.texas.gov/taxes/property-tax/docs/2024-total-rates-levies.xlsx" "ptad-2024-total-rates-levies.xlsx" || fail=1
fetch "https://bcad.org/wp-content/uploads/2025/12/TAX-RATE-CHART-2025.pdf" "bcad-tax-rate-chart-2025.pdf" || fail=1

echo "=== DOWNLOADS DONE (fail=$fail) ==="
ls -lh "$RAW"
exit $fail
