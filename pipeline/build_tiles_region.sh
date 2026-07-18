#!/bin/bash
# GeoJSONSeq -> PMTiles for the 63-county region, split into 8 archives so
# every file stays under GitHub's 100MB limit:
#   metro-rest-2025      county(z4-6) + isd(z7-12) + ring-1 metro parcels(z13-15)
#   bexar-parcels-2025   Bexar parcels (z13-14, -d15 extra detail for overzoom)
#   travis-a/b-2025      Travis parcels, interleaved halves (z13-14, -d15) —
#                        Travis alone would exceed 100MB, so alternate features
#                        go to each archive and the app renders both
#   <region>-2025        central-north / central-south / west / south / coastal
#                        parcels (z13-14, -d15)
# Supersedes build_tiles.sh (single-archive). Region membership is defined in
# pipeline/build_region.py, which writes one parcels-<region>.geojsonseq each.
set -euo pipefail
BUILD="$(cd "$(dirname "$0")/.." && pwd)/data/build"
WEB_TILES="$(cd "$(dirname "$0")/.." && pwd)/web/public/tiles"
mkdir -p "$WEB_TILES"

echo "== county layer =="
tippecanoe -f -o "$BUILD/county.pmtiles" -l county \
  -Z4 -z6 --generate-ids -P "$BUILD/county.geojsonseq"

echo "== isd layer =="
tippecanoe -f -o "$BUILD/isd.pmtiles" -l isd \
  -Z7 -z12 --coalesce-densest-as-needed --generate-ids -P "$BUILD/isd.geojsonseq"

parcel_tiles() {  # parcel_tiles <in.geojsonseq> <out.pmtiles> <extra tippecanoe args...>
  local in="$1" out="$2"; shift 2
  tippecanoe -f -o "$out" -l parcels \
    "$@" \
    --drop-densest-as-needed \
    --coalesce-densest-as-needed \
    --extend-zooms-if-still-dropping \
    --no-simplification-of-shared-nodes \
    --generate-ids \
    -P "$in"
}

echo "== metro parcels (ring-1, z13-15) =="
parcel_tiles "$BUILD/parcels-metro.geojsonseq" "$BUILD/parcels-metro.pmtiles" -Z13 -z15

echo "== merge metro-rest =="
tile-join -f -o "$BUILD/metro-rest-2025.pmtiles" --no-tile-size-limit \
  "$BUILD/county.pmtiles" "$BUILD/isd.pmtiles" "$BUILD/parcels-metro.pmtiles"

echo "== split travis into interleaved halves =="
awk 'NR % 2 == 1' "$BUILD/parcels-travis.geojsonseq" > "$BUILD/parcels-travis-a.geojsonseq"
awk 'NR % 2 == 0' "$BUILD/parcels-travis.geojsonseq" > "$BUILD/parcels-travis-b.geojsonseq"

for region in bexar travis-a travis-b central-north central-south west south coastal; do
  case "$region" in
    bexar)    out="bexar-parcels-2025" ;;
    travis-*) out="${region}-2025" ;;
    *)        out="${region}-2025" ;;
  esac
  echo "== $region parcels (z13-14 -d15) -> $out =="
  parcel_tiles "$BUILD/parcels-${region}.geojsonseq" "$BUILD/${out}.pmtiles" -Z13 -z14 -d15
done

echo "== copy to web/public/tiles =="
rm -f "$WEB_TILES"/*.pmtiles
for a in metro-rest-2025 bexar-parcels-2025 travis-a-2025 travis-b-2025 \
         central-north-2025 central-south-2025 west-2025 south-2025 coastal-2025; do
  cp "$BUILD/$a.pmtiles" "$WEB_TILES/$a.pmtiles"
done

echo "== archive sizes (GitHub hard limit: 100MB/file) =="
over=0
for f in "$WEB_TILES"/*.pmtiles; do
  bytes=$(stat -f%z "$f")
  printf "  %-28s %5.1f MB\n" "$(basename "$f")" "$(echo "$bytes / 1048576" | bc -l)"
  if [ "$bytes" -ge 99614720 ]; then echo "  ^^ OVER 95MB SAFETY MARGIN"; over=1; fi
done
[ "$over" = 0 ] && echo "== done: all archives within limits ==" || { echo "== FAIL: archive too big =="; exit 1; }
