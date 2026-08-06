// Minimal service worker: enables PWA install. No fetch handler on purpose —
// an interception layer (even pass-through) breaks PMTiles/basemap range
// requests in some browsers, and Chrome no longer requires one for install.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
