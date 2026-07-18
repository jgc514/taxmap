# Deploying taxmap to Cloudflare (free tier)

Two things you must do yourself (accounts + payment): everything else is
scripted/prepared. Total recurring cost: the domain (~$10/yr).

## One-time setup (you, ~20 minutes)

1. **Create a Cloudflare account** at dash.cloudflare.com (free plan).
2. **Register a domain** in Cloudflare → Domains (e.g. `sataxmap.com`, at cost,
   ~$10/yr) — or transfer one you already own.
3. **Create an R2 bucket** named `taxmap-tiles`:
   Dashboard → R2 → Create bucket (location: automatic).
   - Settings → Public access → **Connect custom domain** → `tiles.<yourdomain>`
     (do NOT use the r2.dev URL — it's rate-limited).
   - Settings → CORS policy:
     ```json
     [{ "AllowedOrigins": ["https://<yourdomain>", "http://localhost:5173"],
        "AllowedMethods": ["GET", "HEAD"],
        "AllowedHeaders": ["range", "if-match"],
        "ExposeHeaders": ["etag", "content-range", "accept-ranges"],
        "MaxAgeSeconds": 86400 }]
     ```
4. **Install + log in wrangler** (Cloudflare's CLI — I can run these once your
   account exists; the login opens a browser window for you to approve):
   ```
   npm install -g wrangler
   wrangler login
   ```

## Each deploy (I run these — or you can)

```bash
# 1. Upload tiles to R2 (versioned filename busts caches on annual refresh)
wrangler r2 object put taxmap-tiles/metro-2025.pmtiles \
  --file data/build/metro-2025.pmtiles --content-type application/octet-stream --remote

# 2. Build the app with the public tile URL
cd web
VITE_TILES_URL=https://tiles.<yourdomain> npm run build

# 3. Deploy to Cloudflare Pages
wrangler pages deploy dist --project-name taxmap
```

Then Pages → custom domain → `<yourdomain>` (first deploy only).

## Annual refresh runbook (each fall when new rates/rolls land)

1. Update year constants + source URLs in `pipeline/` for the new tax year.
2. `pipeline/download_phase0.sh` (+ county roll downloads)
3. `.venv/bin/python pipeline/build_metro.py && pipeline/build_tiles.sh`
4. Upload as `metro-<year>.pmtiles`, update `VITE_TILES_URL`/archive name, redeploy.

## Current deployment: GitHub Pages (live since 2026-07-17)

The map is live at https://jgc514.github.io/taxmap/ — gh-pages branch holds the
built site plus `tiles/` (8 archives, each under GitHub's 100MB/file limit;
region membership defined in `pipeline/build_region.py`).

Redeploy steps:
```bash
cd web && BASE_PATH=/taxmap/ npm run build
cp -R dist/. <scratch-ghpages-clone>/ && cd <scratch-ghpages-clone>
git add -A && git commit -m "Deploy" && git push -f origin gh-pages
# needs: git config http.postBuffer 524288000 (large first push)
```

**IMPORTANT — warm the CDN after every deploy:** GitHub's CDN answers range
requests with 200-full-file while its cache is cold, which breaks PMTiles
("Check that your storage backend supports HTTP Byte Serving"). One full GET
of each archive fixes it:
```bash
# warm every archive listed in web/src/archives.json — browser variants too
# (GitHub's CDN caches per Accept-Encoding, so warm the gzip variant browsers
# actually request):
for a in $(python3 -c "import json;print(' '.join(json.load(open('web/src/archives.json'))))"); do
  curl -so /dev/null "https://jgc514.github.io/taxmap/tiles/$a.pmtiles"
  curl -so /dev/null -H "Accept-Encoding: gzip, deflate, br, zstd" \
    "https://jgc514.github.io/taxmap/tiles/$a.pmtiles"
done
```
(The Cloudflare R2 path above remains the long-term home — no cold-cache issue,
single archive, custom domain.)
