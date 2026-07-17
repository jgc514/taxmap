import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";

// PMTiles needs HTTP range requests; Vite's static middleware doesn't provide
// them, so serve public/tiles/*.pmtiles ourselves.
function pmtilesRange() {
  return {
    name: "pmtiles-range",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (!req.url?.startsWith("/tiles/") || !req.url.includes(".pmtiles")) return next();
        const file = path.join(server.config.root, "public", decodeURIComponent(req.url.split("?")[0]));
        if (!fs.existsSync(file)) { res.statusCode = 404; return res.end("not found"); }
        const { size } = fs.statSync(file);
        const range = req.headers.range;
        res.setHeader("Accept-Ranges", "bytes");
        if (!range) {
          res.setHeader("Content-Length", size);
          return fs.createReadStream(file).pipe(res);
        }
        const m = /bytes=(\d+)-(\d*)/.exec(range);
        const start = Number(m[1]);
        const end = m[2] ? Math.min(Number(m[2]), size - 1) : size - 1;
        res.statusCode = 206;
        res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`);
        res.setHeader("Content-Length", end - start + 1);
        fs.createReadStream(file, { start, end }).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), pmtilesRange()],
  server: { port: Number(process.env.PORT) || 5173 },
});
