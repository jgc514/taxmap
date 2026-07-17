# Phase 0 Verification — 2026-07-16

## External spot-check: 10 parcels vs Bexar CAD's own records
(bexar.trueautomation.com/clientdb/Property.aspx?cid=110&prop_id=N — shows each
property's actual taxing entities and 2025 adopted rates; used as the oracle.)

| Property | Stack | Map rate | BCAD rate | Result |
|---|---|---|---|---|
| 404 King William, SA 78204 | SA + SAISD | 2.4405 | 2.440474 | ✅ exact |
| 122 Spyglass, Universal City | UC + Judson | 2.2533 | 2.253284 | ✅ exact |
| 14814 River Vista S, SA 78216 | SA + NEISD | 2.2675 | 2.267474 | ✅ exact |
| 10513 Bricewood Park, 78254 | Helotes + NISD | 2.0586 | 2.058584 | ✅ exact |
| 10255 Band Wagon, Converse | Converse + Judson | 2.1883 | 2.188284 | ✅ exact |
| 5936 Broadway, Alamo Heights | AH + AHISD | 2.0710 | 2.071031 | ✅ exact |
| 944 Austin Hwy, Terrell Hills | TH + AHISD | 2.0589 | 2.058878 | ✅ exact |
| 7300 W Loop 1604, Somerset | Somerset + Somerset ISD | 2.5635 | 2.663489 | ⚠️ −0.100 = ESD #5 |
| 25951 White Eagle Dr, 78260 | uninc + Comal ISD | 1.8185 | 1.886725 | ⚠️ −0.068 = ESD #3 |
| 1196 Stuart Rd, Adkins | uninc + East Central ISD | 1.6756 | 1.775584 | ⚠️ −0.100 = ESD #10 |

**7/10 exact to six decimals.** The 3 misses are low by *precisely* the Emergency
Services District rate BCAD lists for that property — the documented v0
limitation (no free ESD/MUD boundaries; fixed when the appraisal roll arrives
via the pending open-records request). City-of-SA parcels carry no ESD, so the
urban core is already exact; unincorporated and small-city parcels understate
by ~0.07–0.10 percentage points until Phase 2.

Also confirmed: PTAD's consolidated "Bexar 0.299999" = BCAD's County 0.276331
+ Road & Flood 0.023668, so the county base is exact.

## Browser verification
- ISD choropleth at metro zoom, layer handoff to parcels at z13 (0 ISD / 10,677
  parcels rendered at z13.1), parcel fabric crisp at z16.
- Click cards verified at district and parcel level (values, est. tax, stack).
- Tile archive: 85 MB PMTiles for 703,258 parcels + 23 ISD aggregates —
  well inside R2 free tier.

## Nominal vs effective reminder
BCAD's dollar estimate for 404 King William ($24,288) is below the map's
nominal estimate ($36,329) because of the current owner's exemptions — the
nominal/effective distinction the roll data will make explicit in Phase 2.

# Phase 1 Verification — 2026-07-16 (8-county metro)

- **Totals:** 1,065,028 parcels; per-county min/median/max all inside sanity
  bounds after the border-ISD fix (Blanco/Fredericksburg/Pearsall/Three Rivers
  ISDs added to rate lookups; only no-levy military ISDs and no-tax villages
  remain unmatched, correctly at 0).
- **Component decomposition:** one parcel per new county — base + city + ISD
  sums exact in all 7.
- **External checks:**
  - Guadalupe (CAD's own 2025 rate summary PDF): County 0.2784 + Lateral Road
    0.0520 = 0.3304 ✅ exact vs our PTAD base; City of Cibolo 0.5226 ✅ exact;
    SCUC ISD 1.0769 ✅ exact.
  - Comal & Guadalupe esearch portals: situs addresses match our parcels by
    property ID (join key confirmed); these portals don't publish per-property
    rate tables, so rate validation is component-level there.
  - Bexar oracle (trueautomation clientdb) remains the only per-property
    entity-table source found; new-county per-property tables arrive with the
    appraisal rolls (PIA requests).
- **Browser:** county → ISD → parcel drill-down verified; county and parcel
  click cards verified (Bexar County card; New Braunfels parcel card with
  correct Comal stack). Metro archive 148 MB.
