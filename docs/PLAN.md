# SA Metro Property-Tax Heat Map — Implementation Plan

## Context

Jeremy Cobb (REALTOR, Magnolia Realty SA Hill Country) needs an interactive property-tax heat map that no off-the-shelf tool provides: drill down from county → city → school district → subdivision → **individual parcel**, colored by tax rate, with a per-jurisdiction rate breakdown on every property. Built entirely from **free public data** (county appraisal district rolls, adopted tax rates, parcel GIS) — no paid APIs. LandGlide (which he already pays for) is the accuracy cross-check, not a data source.

**Decisions locked in the interview:**

| Decision | Choice |
|---|---|
| Audience | Internal tool first; harden for clients later |
| Heat-map metric | Both **nominal rate** (sum of jurisdiction rates) and **effective rate** (actual levy ÷ market value), toggleable |
| V1 scope | Full 8-county SA metro: Bexar, Comal, Guadalupe, Medina, Wilson, Atascosa, Kendall, Bandera (Bexar built first to prove the pipeline) |
| Platform | Standalone web app, free hosting, embed-ready for HomeMatrix/website later |
| Neighborhood level | Platted **subdivisions** from CAD data (dissolved parcel boundaries) |
| Property click card | Jurisdiction-by-jurisdiction breakdown + value + estimated annual tax |
| Buyer mode | **In v1** — re-compute the bill at a hypothetical sale price with fresh homestead exemption |
| History | **Multi-year from the start** — backfill ~5 years where counties publish it; schema keyed by tax year |

Long-term: scale to all of Texas (statewide free parcel + rate data exists), eventually other states.

## Architecture

**Zero-recurring-cost stack.** All heavy computation happens locally on this Mac; the published artifact is static files.

```
TxGIO statewide parcels (uniform, CC0)   CAD appraisal rolls        Adopted tax rates
  geometry + values + PROP_ID        +   jurisdiction stack,    +   (PTAD statewide XLSX
  (one format for all 254 counties)      exemptions, taxable        + county truth-in-taxation
                                         values (per-CAD format)    pages for current year)
        │                                     │                          │
        └──────────────┬──────────────────────┴──────────────────────────┘
                       ▼
  Python pipeline (DuckDB + spatial)          ← runs locally, re-run each fall
    - per-county "recipe" adapter → common schema (join on PROP_ID)
    - compute nominal rate, effective rate, levy per parcel
    - dissolve parcels → subdivision / city / ISD / county aggregate polygons
                       │
                       ▼
  tippecanoe → single PMTiles archive per year (tile-join of all layers)
  + sharded static JSON for property-card details
                       │
                       ▼
  Static hosting: app shell on Cloudflare Pages, tiles/JSON on R2 (free tier)
                       │
                       ▼
  Web app: Vite + React + MapLibre GL JS + pmtiles protocol + OpenFreeMap basemap
```

Because TxGIO provides geometry/values in **one uniform format for every Texas county**, the per-county recipe shrinks to just the appraisal-roll adapter (jurisdiction stack + exemptions) — a big scaling win.

**Repo layout** (new repo, e.g. `~/taxmap`):
- `pipeline/` — Python: downloaders, per-county recipe modules, common-schema loaders, rate math, aggregation, tile build
- `pipeline/recipes/{bexar,comal,…}.py` — each county ≈ a small adapter (source URLs + column mapping); everything else shared
- `web/` — MapLibre frontend
- `data/` — raw downloads + built artifacts (gitignored)

**Common schema** (DuckDB, everything keyed by `tax_year`):
- `parcels(tax_year, county, prop_id, geom, situs_address, subdivision, market_value, assessed_value, homestead_flag, …)`
- `taxing_units(tax_year, unit_id, name, unit_type, rate_per_100)` — unit_type ∈ county / city / ISD / ESD / MUD / hospital / college / river authority / …
- `parcel_units(tax_year, county, prop_id, unit_id)` — the jurisdiction stack per parcel
- Derived per parcel: `nominal_rate` = Σ unit rates; `levy` and `effective_rate` from roll data; buyer estimate computed client-side from the unit stack + entered price

**Drill-down rendering** (validated by research — see below): pre-aggregated static tile layers per zoom band, each built separately with tippecanoe and merged into **one PMTiles archive** via `tile-join` — county polygons (Z4–8) → city & ISD (Z8–11) → subdivision (Z11–13) → individual parcels (Z13–15). Because Texas cities, ISDs, and counties **overlap rather than nest**, mid-zoom gets a "view by: city / ISD" toggle showing one aggregation layer at a time. Choropleth color from the selected metric; parcel click fetches full jurisdiction detail from sharded static JSON by prop_id (tiles carry only id + the render-driving numbers — the production pattern used by NYC's ZoLa for its ~860k tax lots).

**Buyer mode:** user enters a hypothetical price on any parcel → client recomputes each jurisdiction's dollar amount at that price with a fresh general homestead exemption (per-unit exemption amounts, e.g. $100k school HS exemption, ship with the taxing-unit data) → shows "current owner pays X / a buyer would pay ~Y."

## Rendering stack — VERIFIED ✅

Research agent confirmed every component is proven at or beyond our scale in production:

- **Scale:** tippecanoe routinely handles millions of polygons; a published walkthrough tiles 655k Texas polygons (exactly Bexar's parcel count) into PMTiles + MapLibre. Bexar archive ≈ **1–3 GB**; even statewide Texas (~13–20M parcels, 15–40 GB) would cost well under $1/month on R2. A production site (Pinball Map) serves a 111 GB PMTiles archive from R2 with **no tile server** for ~$1.67/mo.
- **Key tippecanoe settings:** `--drop-densest-as-needed --coalesce-densest-as-needed --no-simplification-of-shared-nodes` (prevents cracks between adjacent parcels), `--generate-ids` (needed for hover/click styling), attribute whitelist via `-y`, keep default 500KB tile budget, cap parcel maxzoom at ~15 (biggest size lever).
- **Hosting corrections found:** the PMTiles file must live on **R2, not Pages** (Pages has a 25 MiB per-file cap — app shell on Pages, tiles on R2). R2 needs a **custom domain** (the `r2.dev` dev URL is rate-limited) — a domain on Cloudflare (~$10/yr) is the *only unavoidable cost* in the whole project. Set a CORS policy on the R2 bucket (the #1 reported failure mode). R2 free tier: 10 GB storage, egress always $0, 10M reads/mo ≈ 30–50k map sessions/mo — far beyond internal use.
- **Basemap:** **OpenFreeMap** — free vector OSM basemap, no API key, no request limits, production use explicitly welcomed, MapLibre-native. Kept swappable (fallback: self-host a Texas Protomaps extract in the same R2 bucket).
- **Prior-art lesson** (California's ca-property-tax project, NYC ZoLa, Cook County's ptaxsim): the map is the easy half — **per-county data wrangling is where the real effort goes**, which is exactly why the per-county recipe pattern and Bexar-first sequencing matter. Cook County's open-source `ptaxsim` is the reference for modeling overlapping-jurisdiction bill decomposition.

## Statewide data backbone — VERIFIED ✅ (better than hoped)

Research agent confirmed two free statewide datasets that carry most of the load:

**TxGIO StratMap Land Parcels** (Texas Geographic Information Office, data.geographic.texas.gov):
- **All 254 Texas counties**, public domain (CC0), no signup/API key. 2025 vintage published Sep 2025; vintages back to 2021 (≈251–252 counties each) → multi-year history comes largely from these snapshots.
- Per-county zipped shapefiles/geodatabases (1.3–67 MB each), also a programmatic API listing direct download URLs.
- Attributes include **PROP_ID (the CAD's own property ID — the documented join key to appraisal rolls)**, plus **market/land/improvement values, situs address, owner name, legal description, and state land-use category** already baked in. Schema spec: cdn.tnris.org/documents/tnris-land-parcel-schema.pdf.

**Texas Comptroller (PTAD) adopted tax rates**, statewide, 2021–2025:
- Direct XLSX downloads per year (consolidated + school/city/county/special-district files) at comptroller.texas.gov/taxes/property-tax/rates/ — every taxing unit's adopted rate keyed by the state's 8-digit taxing-unit ID.
- Known lag: certified statewide rates for tax year N finalize by Aug of N+1. Mitigation: for the current year, pull adopted rates directly from county tax-office truth-in-taxation pages (Bexar's publishes each fall).

**What this changes:** parcel geometry, values, addresses, and rates for the *entire state* are already free and uniform. The per-county CAD rolls are still needed for the three things TxGIO doesn't carry — **the jurisdiction stack per parcel** (which taxing units apply to each property — the heart of the nominal-rate map), **exemptions**, and **taxable value per unit** (for effective rate + buyer mode). Statewide scaling later = same recipe, uniform inputs.

**National scaling note (for the long game):** no free national parcel source exists; roughly a third to half of states run free statewide programs like Texas's (WI, NJ, FL, NC, MT, MD…), the rest are county-by-county or paid aggregators (Regrid/ATTOM). The architecture (recipe adapters → common schema) is exactly the right shape for that reality.

## 8-county CAD audit — VERIFIED ✅ (one wrinkle, with workaround)

All 8 counties checked live (July 2026). Parcel GIS is free everywhere via TxGIO; adopted tax rates are free everywhere (True Prodigy truth-in-taxation portals for all 8 — `bexar.trueprodigy-taxtransparency.com`, `{county}.countytaxrates.com` — plus simple all-units rate PDFs from most CADs, e.g. BCAD's annual TAX-RATE-CHART PDF). The wrinkle is the **bulk appraisal roll**:

| County | Bulk appraisal roll | Notes |
|---|---|---|
| Guadalupe | ✅ FREE download | guadalupead.org/certified-appraisal-roll/ — ~71 MB ZIPs, 2024–25 |
| Wilson | ✅ FREE download | wilson-cad.org/reports/ — back to 2019; format verified: fixed-layout text report with per-entity (jurisdiction) value table per property — exactly what we need |
| Bandera | ✅ FREE download | bancad.org downloads page — certified rolls back to 2021 |
| **Bexar** | ⚠️ Open-records request | Not posted publicly; BCAD's own PIA form says the appraisal-data export is offered via their FTP server on request; electronic-data cost quoted case-by-case (written estimate required if >$40) |
| Comal, Medina, Atascosa, Kendall | ⚠️ Open-records request | Rolls are public under the TX Public Information Act; one-time email request each; no posted fee schedules |

**Why this doesn't block anything:**
1. TxGIO parcels already carry values for all 8 counties, and jurisdiction stacks can be **approximated by spatial join** against free boundary layers (county/city/ISD boundaries are all free downloads) — good enough for a v0 nominal-rate map, flagged as "approximate" until rolls land. Special districts (ESD/MUD) are the fuzzy part until rolls arrive.
2. The 3 free rolls appear to share one vendor's report format (Wilson's verified) → **one custom parser** likely covers all three. No CAD posts a data dictionary, so budget parser time.
3. PIA request emails to the 5 remaining CADs are a **day-one action** (drafts prepared for Jeremy to send from his email); rolls integrate per-county as they arrive, Bexar prioritized. These are one-time-per-year requests, not subscriptions — consistent with the "no paid API" constraint, though Bexar *may* quote a modest one-time media/programming fee (estimate required in writing first, so no surprises).
4. Buyer mode doesn't need the rolls at all — it computes from adopted rates + published exemption schedules + a hypothetical price. Only *current-owner* bills (their exemptions and homestead cap) need roll data.

**Scraping notes:** TxGIO CDN 403s curl's default user-agent — send a browser User-Agent (verified working). True Prodigy portals are JS apps — pull their underlying JSON APIs, or use the CADs' static rate PDFs.

## Build phases (sequenced around data availability)

**Phase 0 — Pipeline proof on Bexar + PIA requests out the door.**
Scaffold repo (`~/taxmap`, new git repo). Download TxGIO Bexar parcels (311 MB) + 2025 adopted rates (BCAD rate chart + True Prodigy). Build jurisdiction assignment v0 by spatial join (county/city/ISD boundary layers). Compute nominal rate per parcel → DuckDB → tippecanoe → first PMTiles → minimal MapLibre page. **Also: draft the 5 open-records emails (Bexar, Comal, Medina, Atascosa, Kendall) for Jeremy to send day one — roll delivery time is the long pole, so it starts now.**
*Exit criteria: zoom from metro level down to Jeremy's own listings in a browser and see plausible nominal rates.*

**Phase 1 — Metro fan-out + full drill-down UX.**
Run the other 7 TxGIO county files through the same pipeline (uniform format — cheap). Aggregate dissolves (county/city/ISD/subdivision from CAD subdivision attributes where present), zoom-banded layer handoffs, legend, nominal/effective toggle (effective-rate layer appears per-county as roll data lands), click card v1, address/subdivision search. "Approximate jurisdictions" badge until rolls integrate.

**Phase 2 — Authoritative rolls + buyer mode.**
Parser for the CAD vendor text-report format → ingest the 3 free rolls (Guadalupe, Wilson, Bandera). Integrate PIA rolls as they arrive (Bexar first priority). Upgrades per county: exact jurisdiction stacks (incl. ESD/MUD/special districts), exemptions, taxable value per unit → true effective rate + current-owner bill. Buyer-mode calculator on the card (rates + exemption schedules + entered price — ships even before all rolls arrive).

**Phase 3 — Multi-year history.**
Backfill TxGIO parcel vintages 2021–2025 + PTAD statewide rate files 2021–2025 + CAD roll back-years where posted (Wilson to 2019, Bandera to 2021). Year selector; per-parcel rate/value trend sparkline on the card.

**Phase 4 — Deploy + runbook.**
Cloudflare Pages (app) + R2 with custom domain (tiles/JSON), CORS config, clean URL, embed-ready iframe mode. Written annual-refresh runbook (each fall: new rates + rolls + TxGIO vintage → re-run pipeline → upload new year's archive).

**Post-v1 (not in this plan):** client-facing polish + Magnolia branding + disclaimers; statewide Texas (same TxGIO/PTAD inputs, uniform); multi-state via per-state recipe adapters.

## Verification

- **Data accuracy:** spot-check ≥10 known properties per county against three independent sources: the CAD's own property search, the county's True Prodigy truth-in-taxation portal (shows each property's actual taxing units and rates — the perfect oracle for our jurisdiction stacks), and LandGlide. Market value, jurisdiction list, total rate, and levy must match. Sanity bounds: SA-area total rates ≈ 1.5%–3.4%; anything outside gets investigated.
- **Spatial-join quality (Phase 0–1):** measure what % of parcels' spatially-derived jurisdiction stacks match the roll-derived truth once rolls arrive — quantifies how much the "approximate" badge mattered.
- **Buyer-mode math:** validate against the True Prodigy portals' estimator output for a handful of Bexar properties.
- **App:** browser-preview verification at each phase — zoom through every drill level, click parcels, confirm card math, test metric toggle and year selector; screenshot proof shared at each milestone.
- **Performance:** map must stay smooth on a normal laptop at parcel zoom; keep tippecanoe's default 500KB/tile budget.
