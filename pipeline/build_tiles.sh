#!/bin/bash
# GeoJSONSeq -> PMTiles: county z4-6, ISD z7-12, parcels z13-15, merged into
# one archive with three named layers, copied into web/public for the dev server.
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

echo "== parcels layer =="
tippecanoe -f -o "$BUILD/parcels.pmtiles" -l parcels \
  -Z13 -z15 \
  --drop-densest-as-needed \
  --coalesce-densest-as-needed \
  --extend-zooms-if-still-dropping \
  --no-simplification-of-shared-nodes \
  --generate-ids \
  -P "$BUILD/parcels.geojsonseq"

echo "== merge =="
tile-join -f -o "$BUILD/metro-2025.pmtiles" --no-tile-size-limit \
  "$BUILD/county.pmtiles" "$BUILD/isd.pmtiles" "$BUILD/parcels.pmtiles"

cp "$BUILD/metro-2025.pmtiles" "$WEB_TILES/metro-2025.pmtiles"
rm -f "$WEB_TILES/bexar-2025.pmtiles"
ls -lh "$BUILD"/*.pmtiles
echo "== done: metro tiles copied to web/public/tiles =="
