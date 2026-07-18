# taxmap — South-Central Texas Property-Tax Heat Map

Interactive drill-down heat map of property tax rates: county → city / school
district → subdivision → individual parcel. Built entirely from free public
data (TxGIO statewide parcels, Comptroller PTAD rates, CAD appraisal rolls).

Coverage: 63 counties — Bexar plus every county within 4 adjacency rings
(San Antonio, Austin metro, Corpus Christi, Laredo, Del Rio, Victoria;
computed by `pipeline/county_rings.py`). ~3.7M parcels, tax year 2025.

Full plan: see `docs/PLAN.md`.

## Layout
- `pipeline/` — Python + DuckDB data pipeline (run locally, refresh each fall)
  - `download_phase0.sh` — fetch raw source data into `data/raw/`
  - `recipes/` — per-county appraisal-roll adapters
- `web/` — MapLibre GL JS frontend (Vite + React)
- `data/` — raw downloads and built artifacts (gitignored)
- `docs/pia/` — open-records request drafts for CADs that don't post bulk rolls

## Pipeline quickstart
```
python3 -m venv .venv && .venv/bin/pip install duckdb openpyxl pdfplumber
pipeline/download_phase0.sh                  # shared boundary/rate sources
pipeline/download_ring4.sh                   # ring 2-4 county parcel zips
.venv/bin/python pipeline/build_region.py    # all 63 counties → geojsonseq layers
pipeline/build_tiles_region.sh               # → 8 pmtiles archives (<100MB each)
cd web && npm install && npm run dev
```
(`build_metro.py`/`build_tiles.sh` are the superseded 8-county versions.)

## Tax years & data vintages
Everything is keyed by `tax_year`. Current build: 2025 certified data
(TxGIO 2025 parcel vintage, PTAD 2025 adopted rates).
