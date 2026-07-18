#!/bin/bash
# GeoJSONSeq -> PMTiles for all regions, dynamically:
#   - every data/build/parcels-<region>.geojsonseq becomes one archive
#     (z13-14, -d15 detail for overzoom), EXCEPT:
#   - metro keeps z15 and is merged with county(z4-6) + isd(z7-12) layers
#     into metro-rest-2025 (stable name, HomeMatrix depends on it)
#   - bexar keeps its stable archive name bexar-parcels-2025
#   - any export over SPLIT_BYTES is split into interleaved parts
#     (<region>-a/-b/... [-2025]) so every file stays under GitHub's 100MB
# Writes web/src/archives.json — the app renders whatever is listed there.
set -euo pipefail
BUILD="$(cd "$(dirname "$0")/.." && pwd)/data/build"
WEB="$(cd "$(dirname "$0")/.." && pwd)/web"
WEB_TILES="$WEB/public/tiles"
mkdir -p "$WEB_TILES"
SPLIT_BYTES=$((500 * 1024 * 1024))
PART_BYTES=$((450 * 1024 * 1024))

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

ARCHIVES=("metro-rest-2025")
letters=(a b c d e f)

for src in "$BUILD"/parcels-*.geojsonseq; do
  region="$(basename "$src" .geojsonseq)"; region="${region#parcels-}"
  case "$region" in
    metro|*-a|*-b|*-c|*-d|*-e|*-f) continue ;;  # metro done; skip old part files
  esac
  bytes=$(stat -f%z "$src")
  if [ "$bytes" -gt "$SPLIT_BYTES" ]; then
    parts=$(( (bytes + PART_BYTES - 1) / PART_BYTES ))
    echo "== $region: $((bytes / 1048576))MB -> $parts interleaved parts =="
    for ((k = 0; k < parts; k++)); do
      part="$BUILD/parcels-${region}-${letters[$k]}.geojsonseq"
      awk -v n="$parts" -v k="$k" 'NR % n == k' "$src" > "$part"
      out="${region}-${letters[$k]}-2025"
      echo "== $region part ${letters[$k]} -> $out =="
      parcel_tiles "$part" "$BUILD/${out}.pmtiles" -Z13 -z14 -d15
      ARCHIVES+=("$out")
    done
  else
    out="${region}-2025"
    [ "$region" = "bexar" ] && out="bexar-parcels-2025"
    echo "== $region -> $out =="
    parcel_tiles "$src" "$BUILD/${out}.pmtiles" -Z13 -z14 -d15
    ARCHIVES+=("$out")
  fi
done

echo "== copy to web/public/tiles + write archives.json =="
rm -f "$WEB_TILES"/*.pmtiles
{
  echo "["
  for i in "${!ARCHIVES[@]}"; do
    a="${ARCHIVES[$i]}"
    cp "$BUILD/$a.pmtiles" "$WEB_TILES/$a.pmtiles"
    sep=","; [ "$i" = "$((${#ARCHIVES[@]} - 1))" ] && sep=""
    echo "  \"$a\"$sep"
  done
  echo "]"
} > "$WEB/src/archives.json"

echo "== archive sizes (GitHub hard limit: 100MB/file) =="
over=0; total=0
for f in "$WEB_TILES"/*.pmtiles; do
  bytes=$(stat -f%z "$f"); total=$((total + bytes))
  printf "  %-28s %5.1f MB\n" "$(basename "$f")" "$(echo "$bytes / 1048576" | bc -l)"
  # GitHub hard-rejects >=100MB. Fail at 99MB; warn from 93MB up.
  # (metro-rest runs hot because it carries the statewide county+ISD overview
  # layers — split those into their own archive at the next annual refresh.)
  if [ "$bytes" -ge 103809024 ]; then
    echo "  ^^ FAIL: within 1MB of GitHub's 100MB limit"; over=1
  elif [ "$bytes" -ge 97517568 ]; then
    echo "  ^^ warning: close to GitHub's 100MB limit"
  fi
done
printf "  TOTAL: %.2f GB across %d archives\n" "$(echo "$total / 1073741824" | bc -l)" "${#ARCHIVES[@]}"
[ "$over" = 0 ] && echo "== done ==" || { echo "== FAIL: archive too big =="; exit 1; }
