# Launch checklist — statewide web + phone apps

Everything here that says **(you)** requires an account or payment only you
can set up; every step marked (scripted) is automated and ready to run the
moment the account exists.

## 1. Statewide tile hosting — Cloudflare R2 (~20 min, **you**)

GitHub Pages caps a site at 1GB; statewide tiles are ~1.5GB, so they move to
Cloudflare R2 (free tier: 10GB storage, zero egress fees).

1. **(you)** Create a Cloudflare account: dash.cloudflare.com (free plan).
2. **(you)** Register a domain in Cloudflare → Domains (~$10/yr) — e.g.
   `txtaxmap.com`.
3. **(you)** R2 → Create bucket `taxmap-tiles` → Settings → Public access →
   Connect custom domain `tiles.<yourdomain>` (NOT the rate-limited r2.dev
   URL). CORS policy: see docs/DEPLOY.md §One-time setup.
4. **(you)** `npm install -g wrangler && wrangler login` (browser approval).
5. (scripted) `pipeline/deploy_r2.sh` uploads every archive and prints the
   VITE_TILES_URL build command. App + site then deploy to Pages/gh-pages as
   today — only the tiles move.

Until R2 exists, the live site keeps the 63-county coverage (its 469MB fits
GitHub Pages); statewide tiles are built and waiting locally.

## 2. iPhone app — Apple (**you**, then scripted)

1. **(you)** Enroll in the Apple Developer Program ($99/yr) at
   developer.apple.com — enrollment approval typically takes 1–3 days, so
   START THIS FIRST.
2. **(you)** Install Xcode from the App Store (large download).
3. (scripted) `cd web && npx cap add ios && npx cap sync ios` then open
   `ios/App/App.xcworkspace`, set your signing team, archive, and upload
   via Xcode's Organizer.
4. App Store review: typically 1–3 days once submitted; first submissions
   sometimes get questions about data sources — the answer is "public
   government records (TxGIO parcels, Comptroller tax rates)".

**Available TODAY without Apple:** the site is an installable PWA — on
iPhone: Share → Add to Home Screen. Full-screen, has an icon, works now.

## 3. Android app — Google (**you**, then scripted)

1. **(you)** Google Play Console account: play.google.com/console ($25
   one-time). Identity verification can take a day or two.
2. (scripted) `cd web && npx cap add android && npx cap sync android`,
   then `cd android && ./gradlew bundleRelease`; sign with the keystore the
   script generates and upload the .aab in Play Console.
3. Play review for new developer accounts includes a 14-day closed-testing
   requirement (20 testers) before production — plan for that; the PWA and
   direct-install APK cover Android users meanwhile.

**Available TODAY without Google:** Chrome on Android offers "Install app"
(the PWA) automatically.

## 4. What's already done (no action needed)

- 254-county statewide pipeline: recipes generated + verified, data built,
  tiles auto-packed under GitHub's limits (`pipeline/build_tiles_region.sh`)
- Map features: red hover boundary, lot dimensions, exemption calculator,
  FEMA flood overlay, satellite/topo basemaps, measure tool
- Annual data watcher: `.github/workflows/data-watch.yml` opens a tracking
  issue when next year's PTAD rates or StratMap vintage appear

## 5. One-click step: enable the annual data watcher (**you**, 2 min)

My GitHub token can't push workflow files (OAuth `workflow` scope). The
watcher lives at `docs/workflows/data-watch.yml` — either:
- on github.com: Add file → create `.github/workflows/data-watch.yml`,
  paste that file's contents, commit; or
- locally: `git mv docs/workflows/data-watch.yml .github/workflows/ && git push`
