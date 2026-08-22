# ADR 003 — Single-file delivery

## Status

Accepted

## Konteks

Target distribusi: satu artefak yang bisa dibuka offline/lokal tanpa backend, npm app, atau multi-page. Data FIRMS dan dossier harus ikut tersemat.

## Keputusan

- **`index.html`** (CSS + JS) tetap vanilla; data **tidak** di-embed di HTML.
- Sumber data runtime: `data/firms.json` + `data/dossiers.json` via `fetch()` (cache: no-store).
- Tidak ada backend, framework, atau API key Google Maps.
- Update data = edit JSON manual, lalu refresh browser (HTTP server lokal wajib — `file://` memblokir fetch).
- Skema:
  - `data/firms.json` → `{ "meta": {...}, "points": [ { lat, lon, b4, b5, frp, date, time, sat, conf, dn }, ... ] }`
  - `data/dossiers.json` → `{ "walhiSummary": {...}, "sipongiFallback": {...}, "dossiers": [ ...12 konsesi ] }`
- Jika `firms.json` gagal/kosong: UI memakai `sipongiFallback` dari `dossiers.json`.
- Peta: Leaflet via CDN; graf: SVG/canvas tanpa framework.

## Konsekuensi

- Ukuran `firms.json` besar → cluster di peta wajib.
- Harus dibuka lewat HTTP (`python -m http.server`), bukan double-click file.
- Tidak ada auth, persistence server, atau join GIS berat.
