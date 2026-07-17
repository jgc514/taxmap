# taxmap — SA Metro Property-Tax Heat Map

Interactive drill-down heat map of property tax rates: county → city / school
district → subdivision → individual parcel. Built entirely from free public
data (TxGIO statewide parcels, Comptroller PTAD rates, CAD appraisal rolls).

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
pipeline/download_phase0.sh                  # + county zips (see build_metro.py)
.venv/bin/python pipeline/build_metro.py     # all 8 counties → geojsonseq layers
pipeline/build_tiles.sh                      # → data/build/metro-2025.pmtiles
cd web && npm install && npm run dev
```

## Tax years & data vintages
Everything is keyed by `tax_year`. Current build: 2025 certified data
(TxGIO 2025 parcel vintage, PTAD 2025 adopted rates).
