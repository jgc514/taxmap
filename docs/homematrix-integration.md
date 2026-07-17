# Wiring taxmap into HomeMatrix (Lovable)

Prereq: taxmap deployed publicly (see DEPLOY.md). Replace `<yourdomain>` below.

## Tier 1 — "View Tax Map" button / embed (do this first)

The map supports deep links: `https://<yourdomain>/?lat=29.4126&lng=-98.4924&z=16`
opens centered on any property (it also keeps the URL updated as you pan, so
any view is shareable/bookmarkable).

Paste this prompt into Lovable:

> On each listing detail page, add a "View Tax Map" button next to the listing
> address. Link it to `https://<yourdomain>/?lat={listing.latitude}&lng={listing.longitude}&z=16`
> and open in a new tab. Also add an optional embedded map section: an iframe
> with src set to the same URL, full width, 480px tall, rounded corners,
> lazy-loaded.

## Tier 2 — native map component inside HomeMatrix (optional, later)

Lovable can install npm packages. Prompt it to add `maplibre-gl` and `pmtiles`,
then render a MapLibre map using vector source
`pmtiles://https://tiles.<yourdomain>/metro-2025.pmtiles` with a fill layer on
source-layer `parcels` (minzoom 13) colored by the `rate` property, plus `isd`
(z7.5–13) and `county` (below z7.5) layers. Copy the layer definitions and the
color ramp from `web/src/App.jsx` in this repo.

## Tier 3 — tax data in HomeMatrix PDF reports (after Phase 2 JSON API)

Phase 2 publishes static per-property JSON at
`https://tiles.<yourdomain>/detail/{tax-year}/{county}/{prop_id}.json` with the
full jurisdiction breakdown + exemption data. HomeMatrix's report generator
(jsPDF) fetches that for the listing's property ID and renders a "Property Tax
Analysis" page: current owner's bill, and the buyer estimate at the listing
price. (Property-ID lookup by address will also be provided.)
