# Agent playbook — MERATUS

Instruksi untuk AI agent yang diminta **mengupdate atau melengkapi data** dashboard ini. Baca file ini dulu, lalu patuhi tanpa shortcut.

## Misi

Jaga agar data di `data/` akurat, bersumber, dan tidak menggabungkan empat lapisan bukti jadi satu klaim. UI (`index.html`) hanya diubah jika perlu skema/UX — default kerja agent = **data + docs**, bukan redesign.

## Baca wajib (urutan)

1. [`docs/methodology.md`](docs/methodology.md) — cara data dikumpulkan
2. [`docs/glossary.md`](docs/glossary.md) — istilah
3. [`docs/adr/001-evidence-layers.md`](docs/adr/001-evidence-layers.md)
4. [`docs/adr/002-campaign-framing.md`](docs/adr/002-campaign-framing.md)
5. [`docs/adr/003-single-html.md`](docs/adr/003-single-html.md)
6. [`data/README.txt`](data/README.txt) — skema file

## Artefak yang boleh kamu edit

| File | Kapan |
|------|--------|
| `data/firms.json` | Refresh deteksi FIRMS |
| `data/dossiers.json` | Dossier, WALHI summary, SIPONGI fallback |
| `data/boundaries.geojson` | Poligon konsesi (hanya geometri berlisensi/sumber jelas) |
| `docs/methodology.md` | Jika prosedur pengumpulan berubah |
| `README.md` | Hanya jika alur pakai berubah material |

Jangan commit: `firms_sea_7d.csv`, `firms_kalimantan.json`, secret, API key.

## Empat lapisan — jangan dilipat

| Lapisan | Field / file | Dilarang mengklaim |
|---------|--------------|-------------------|
| Detection | `firms.json` points | “Ini api PT X” |
| ConcessionClaim | `walhiHotspots`, `walhiSummary` | Sama dengan join FIRMS 7d × HGU |
| Control | `control`, `uboStatus` | Spekulasi grup tanpa URL |
| PoliticalTie | `politicalTies` | “Parpol membakar hutan” |

Hotspot di konsesi ≠ perusahaan menyulut api. Ikatan politik ≠ atribusi api.

## Tugas standar

### A. Refresh FIRMS

1. Unduh:  
   `https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_SouthEast_Asia_7d.csv`
2. Filter Kalimantan Indonesia; **keluarkan** Sarawak/Sabah.
3. Tulis `data/firms.json` dengan `meta` (`source`, `url`, `fetched`, `filter`, `count`) + `points`.
4. Field point: `lat`, `lon`, `b4`, `b5`, `frp`, `date`, `time`, `sat`, `conf` (`low`|`nominal`|`high`), `dn`.
5. Jangan mengubah `walhiHotspots` hanya karena FIRMS berubah (periode & produk beda).

### B. Lengkapi / revisi dossier

1. Pertahankan `id` yang ada kecuali user minta rename + update `boundaries`/`UI` refs.
2. Setiap klaim Control atau PoliticalTie **wajib** punya sumber URL di `sources` atau `politicalTies[].sources`.
3. `confidence` ikatan: `tinggi` | `sedang` | `rendah` (jujur).
4. Jika tidak ketemu bukti:
   - `uboStatus: "UNKNOWN"`
   - `politicalTies: []` dan/atau `politicalStatus: "TIDAK TERPETAKAN"`
5. **Kiani Lestari (`kiani`)**: jangan hapus caveat The Gecko Project / status operasional meragukan.
6. Centroid hanya dari lokasi operasi publik; label sebagai navigasi kasar di `caveats` bila perlu.

### C. Isi boundaries

1. Hanya jika ada geometri dari user, shapefile/KML/GeoJSON berlisensi, atau sumber terbuka yang **berhasil diunduh** dan diverifikasi.
2. `properties.dossierId` = `dossiers[].id` (contoh `sum`, `kideco`).
3. `quality`: `OFFICIAL` | `GFW` | `PERKIRAAN` — jangan `OFFICIAL` kalau perkiraan.
4. CRS WGS84 (lon, lat). Polygon atau MultiPolygon.
5. **Dilarang** menggambar kotak dummy di sekitar centroid agar “terlihat lengkap”.
6. Jika GFW/API 403/timeout → laporkan gagal; biarkan `features` kosong untuk id itu.

### D. SIPONGI / WALHI angka agregat

- Update `walhiSummary` / `sipongiFallback` hanya dari rilis/pemberitaan baru dengan URL di `sources`.
- Jangan merekonsiliasi angka SIPONGI dengan count FIRMS menjadi satu time series palsu.

## Checklist sebelum selesai

- [ ] JSON valid (`firms.json`, `dossiers.json`, `boundaries.geojson`)
- [ ] Tidak ada UBO/parpol baru tanpa URL
- [ ] Tidak ada poligon tanpa `quality` + `source`
- [ ] Empat lapisan tidak dicampur di copy `caveats` / commit message
- [ ] `meta.count` / `meta.fetched` cocok dengan isi `points` (jika FIRMS diubah)
- [ ] Uji cepat: serve HTTP, buka `index.html`, pastikan fetch 200
- [ ] Laporkan ke user: **apa yang diisi**, **apa yang tetap UNKNOWN**, **sumber yang dipakai**

## Commit (hanya jika user minta)

- Pesan fokus *mengapa* (mis. “Refresh FIRMS 7d snapshot” / “Add HGU polygon for kideco”).
- Jangan push kecuali user minta.
- Jangan force-push `main`.

## Anti-goals

- Mengarang pemilik sawit atau partai “supaya graf penuh”.
- Join live FIRMS × konsesi tanpa poligon resmi dan tanpa permintaan eksplisit + metodologi baru.
- Menambah backend/React/npm “supaya lebih mudah”.
- Menghapus disclaimer / ADR framing politik.
- Memakai Google Maps Embed sebagai pengganti FIRMS tanpa keputusan produk baru.

## Prompt starter (untuk manusia)

Salin ke agent baru:

```text
Kerjakan update data MERATUS sesuai agent.md dan docs/methodology.md.
Jangan mengarang UBO, parpol, atau poligon. Laporkan yang diisi vs yang tetap UNKNOWN.
Tugas: <refresh FIRMS | lengkapi dossier X | import boundaries dari file …>
```

## Verifikasi lokal

```bash
# dari root repo
python -c "from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler; ThreadingHTTPServer(('127.0.0.1', 8765), SimpleHTTPRequestHandler).serve_forever()"
```

Buka http://127.0.0.1:8765/index.html — stempel harus menampilkan count FIRMS dan `region N/12`.
