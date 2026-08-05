#!/bin/bash
# Warm the GitHub Pages CDN for every archive in web/src/archives.json.
#
# A force-push cold-starts the edge cache, and GitHub caches each
# Accept-Encoding variant SEPARATELY -- warming only the default encoding
# leaves gzip clients (which is most browsers) hitting a cold origin and
# waiting seconds for the first range request of every archive.
#
# PMTiles only ever issues range requests, so a 206 on a small range is both
# the correct warm-up and the correct health check.
#
# Usage: pipeline/warm_tiles.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE_DEFAULT="https://jgc514.github.io/taxmap/tiles"

urls=$(python3 - "$ROOT/web/src/archives.json" "$BASE_DEFAULT" <<'PY'
import json, sys
entries = json.load(open(sys.argv[1]))
for e in entries:
    if isinstance(e, str):
        print(f"{sys.argv[2]}/{e}.pmtiles")
    else:
        print(e["url"])
PY
)

total=0; ok=0; bad=0
for u in $urls; do
  for enc in "identity" "gzip"; do
    code=$(curl -s -o /dev/null -m 60 \
      -H "Accept-Encoding: $enc" -H "Range: bytes=0-16383" \
      -A "Mozilla/5.0" -w "%{http_code}" "$u")
    total=$((total + 1))
    if [ "$code" = "206" ] || [ "$code" = "200" ]; then
      ok=$((ok + 1))
    else
      bad=$((bad + 1))
      printf "  FAIL %s  [%s]  %s\n" "$code" "$enc" "$u"
    fi
  done
  printf "  warmed %s\n" "$(basename "$u")"
done

echo
echo "warmed $ok/$total variant requests ($bad failed)"
[ "$bad" -eq 0 ] || exit 1
