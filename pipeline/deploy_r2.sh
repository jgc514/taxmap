#!/bin/bash
# Upload every built tile archive to Cloudflare R2 (bucket: taxmap-tiles).
# Prereqs (one-time, see docs/LAUNCH-CHECKLIST.md): Cloudflare account,
# bucket with public custom domain, `wrangler login`.
# Usage: pipeline/deploy_r2.sh [tiles-domain]   e.g. tiles.txtaxmap.com
set -euo pipefail
WEB_TILES="$(cd "$(dirname "$0")/.." && pwd)/web/public/tiles"
DOMAIN="${1:-tiles.example.com}"

command -v wrangler >/dev/null || { echo "wrangler not installed (npm i -g wrangler)"; exit 1; }

for f in "$WEB_TILES"/*.pmtiles; do
  name="$(basename "$f")"
  echo "== uploading $name ($(du -h "$f" | cut -f1)) =="
  wrangler r2 object put "taxmap-tiles/$name" \
    --file "$f" --content-type application/octet-stream --remote
done

echo
echo "Done. Build + deploy the app pointed at R2:"
echo "  cd web && VITE_TILES_URL=https://$DOMAIN BASE_PATH=/taxmap/ npm run build"
echo "then push dist to gh-pages WITHOUT the tiles/ directory (they live on R2 now)."
