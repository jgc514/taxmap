import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";
import "maplibre-gl/dist/maplibre-gl.css";

// Sequential blue ramp (validated reference palette, steps 100->700).
// Domain: SA-metro nominal rates, % of value per year.
const RATE_STOPS = [
  [1.3, "#cde2fb"],
  [1.52, "#9ec5f4"],
  [1.73, "#6da7ec"],
  [1.95, "#3987e5"],
  [2.17, "#256abf"],
  [2.38, "#184f95"],
  [2.6, "#0d366b"],
];
const rateColor = ["interpolate", ["linear"], ["get", "rate"], ...RATE_STOPS.flat()];

const fmtUSD = (n) =>
  n?.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }) ?? "—";

// Tiles served from <base>/tiles by default; set VITE_TILES_URL to an external
// host (e.g. R2 custom domain) to serve them elsewhere.
const TILES_BASE =
  import.meta.env.VITE_TILES_URL || `${location.origin}${import.meta.env.BASE_URL}tiles`;

// TX general school homestead exemption (2025): $140,000.
const SCHOOL_HS_EXEMPTION = 140000;

const buyerEstimate = (price, rate, isdRate) => {
  if (!price || price <= 0) return null;
  const nonSchool = (price * (rate - isdRate)) / 100;
  const school = (Math.max(price - SCHOOL_HS_EXEMPTION, 0) * isdRate) / 100;
  return nonSchool + school;
};

const initialView = () => {
  const q = new URLSearchParams(location.search);
  const lat = parseFloat(q.get("lat")), lng = parseFloat(q.get("lng")), z = parseFloat(q.get("z"));
  if (Number.isFinite(lat) && Number.isFinite(lng)) {
    return { center: [lng, lat], zoom: Number.isFinite(z) ? z : 15 };
  }
  return { center: [-98.6, 29.42], zoom: 8.1 };
};

export default function App() {
  const mapDiv = useRef(null);
  const [status, setStatus] = useState("loading map…");

  useEffect(() => {
    const protocol = new Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);
    const view = initialView();
    const map = new maplibregl.Map({
      container: mapDiv.current,
      style: "https://tiles.openfreemap.org/styles/positron",
      center: view.center,
      zoom: view.zoom,
      attributionControl: { compact: true },
    });
    map.on("moveend", () => {
      const c = map.getCenter();
      const p = new URLSearchParams(location.search);
      p.set("lat", c.lat.toFixed(5));
      p.set("lng", c.lng.toFixed(5));
      p.set("z", map.getZoom().toFixed(2));
      history.replaceState(null, "", `?${p}`);
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    window.__map = map;

    map.on("load", () => {
      // Two archives so each stays under GitHub's 100MB file limit:
      // county + ISD + non-Bexar parcels in one, Bexar parcels in the other.
      map.addSource("taxes", {
        type: "vector",
        url: `pmtiles://${TILES_BASE}/metro-rest-2025.pmtiles`,
      });
      map.addSource("taxes-bx", {
        type: "vector",
        url: `pmtiles://${TILES_BASE}/bexar-parcels-2025.pmtiles`,
      });

      // Insert beneath the basemap's first symbol layer so street/city labels
      // stay readable above the choropleth.
      const firstSymbol = map.getStyle().layers.find((l) => l.type === "symbol")?.id;

      map.addLayer(
        {
          id: "county-fill",
          type: "fill",
          source: "taxes",
          "source-layer": "county",
          maxzoom: 7.5,
          paint: { "fill-color": rateColor, "fill-opacity": 0.6 },
        },
        firstSymbol
      );
      map.addLayer(
        {
          id: "county-line",
          type: "line",
          source: "taxes",
          "source-layer": "county",
          maxzoom: 7.5,
          paint: { "line-color": "#fcfcfb", "line-width": 1.5 },
        },
        firstSymbol
      );
      map.addLayer(
        {
          id: "isd-fill",
          type: "fill",
          source: "taxes",
          "source-layer": "isd",
          minzoom: 7.5,
          maxzoom: 13,
          paint: { "fill-color": rateColor, "fill-opacity": 0.6 },
        },
        firstSymbol
      );
      map.addLayer(
        {
          id: "isd-line",
          type: "line",
          source: "taxes",
          "source-layer": "isd",
          minzoom: 7.5,
          maxzoom: 13,
          paint: { "line-color": "#fcfcfb", "line-width": 1.2 },
        },
        firstSymbol
      );
      for (const [suffix, src] of [["", "taxes"], ["-bx", "taxes-bx"]]) {
        map.addLayer(
          {
            id: `parcel-fill${suffix}`,
            type: "fill",
            source: src,
            "source-layer": "parcels",
            minzoom: 13,
            paint: { "fill-color": rateColor, "fill-opacity": 0.7 },
          },
          firstSymbol
        );
        map.addLayer(
          {
            id: `parcel-line${suffix}`,
            type: "line",
            source: src,
            "source-layer": "parcels",
            minzoom: 14.5,
            paint: { "line-color": "#fcfcfb", "line-width": 0.5 },
          },
          firstSymbol
        );
      }

      const onParcelClick = (e) => {
        const p = e.features[0].properties;
        const est = p.mkt > 0 ? (p.mkt * p.rate) / 100 : null;
        const defaultPrice = p.mkt > 0 ? p.mkt : 300000;
        const popup = new maplibregl.Popup({ maxWidth: "340px" })
          .setLngLat(e.lngLat)
          .setHTML(
            `<div class="card">
              <div class="card-addr">${p.addr || "(no situs address)"}</div>
              <div class="card-rate">${Number(p.rate).toFixed(4)}%<span> nominal rate</span></div>
              <table>
                <tr><td>Market value</td><td>${fmtUSD(p.mkt)}</td></tr>
                <tr><td>Est. annual tax</td><td>${est ? fmtUSD(est) : "—"}</td></tr>
                <tr><td>School district</td><td>${p.isd || "—"}</td></tr>
                <tr><td>City</td><td>${p.cj || "Unincorporated"}</td></tr>
                <tr><td>County</td><td>${p.cty}</td></tr>
                <tr><td>Property ID</td><td>${p.id}</td></tr>
              </table>
              <div class="buyer">
                <div class="buyer-title">Buyer estimate</div>
                <label>If purchased at $<input type="text" inputmode="numeric" class="buyer-price" value="${defaultPrice.toLocaleString("en-US")}"></label>
                <div class="buyer-result"></div>
                <div class="card-note">Assumes general homestead ($140k school exemption); optional county/city exemptions vary</div>
              </div>
              <div class="card-note">v0: county-wide + city + ISD units; special districts pending roll data</div>
            </div>`
          )
          .addTo(map);
        const el = popup.getElement();
        const input = el.querySelector(".buyer-price");
        const result = el.querySelector(".buyer-result");
        const update = () => {
          const price = Number(input.value.replace(/[^0-9]/g, ""));
          const b = buyerEstimate(price, Number(p.rate), Number(p.isdr ?? 0));
          result.textContent = b != null ? `≈ ${fmtUSD(b)} / year (${fmtUSD(b / 12)}/mo)` : "—";
        };
        input.addEventListener("input", update);
        update();
      };
      map.on("click", "parcel-fill", onParcelClick);
      map.on("click", "parcel-fill-bx", onParcelClick);
      const aggregateCard = (label) => (e) => {
        const p = e.features[0].properties;
        new maplibregl.Popup({ maxWidth: "300px" })
          .setLngLat(e.lngLat)
          .setHTML(
            `<div class="card">
              <div class="card-addr">${p.name}${label}</div>
              <div class="card-rate">${Number(p.rate).toFixed(4)}%<span> median rate</span></div>
              <table>
                <tr><td>Parcels</td><td>${Number(p.parcels).toLocaleString()}</td></tr>
                <tr><td>Median value</td><td>${fmtUSD(p.med_value)}</td></tr>
              </table>
            </div>`
          )
          .addTo(map);
      };
      map.on("click", "isd-fill", (e) => {
        if (map.getZoom() >= 13) return;
        aggregateCard("")(e);
      });
      map.on("click", "county-fill", aggregateCard(" County"));
      for (const id of ["parcel-fill", "parcel-fill-bx", "isd-fill", "county-fill"]) {
        map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
      }
      setStatus(null);
    });
    map.on("error", (e) => {
      console.error("map error", e?.error || e);
    });
    return () => {
      map.remove();
      maplibregl.removeProtocol("pmtiles");
    };
  }, []);

  return (
    <div className="app">
      <div ref={mapDiv} className="map" />
      <header className="topbar">
        <h1>SA Metro Property Tax Map</h1>
        <span className="badge">v0 · 8-county SA metro · 2025 · jurisdictions approximate</span>
      </header>
      <div className="legend">
        <div className="legend-title">Nominal tax rate (% of value)</div>
        <div
          className="legend-bar"
          style={{ background: `linear-gradient(to right, ${RATE_STOPS.map(([, c]) => c).join(",")})` }}
        />
        <div className="legend-labels">
          <span>{RATE_STOPS[0][0]}%</span>
          <span>{RATE_STOPS[RATE_STOPS.length - 1][0]}%</span>
        </div>
        <div className="legend-hint">Zoom in past the district level to see individual parcels</div>
      </div>
      {status && <div className="status">{status}</div>}
    </div>
  );
}
