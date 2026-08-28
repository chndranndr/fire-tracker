# Agent playbook — MERATUS

Instruksi untuk AI agent yang diminta **mengupdate atau melengkapi data** dashboard ini. Baca file ini dulu, lalu patuhi tanpa shortcut.

## Misi

Jaga agar data di `data/` akurat, bersumber, dan tidak menggabungkan empat lapisan bukti jadi satu klaim. UI (`index.html`) hanya diubah jika perlu skema/UX — default kerja agent = **data + docs**, bukan redesign.

## Baca wajib (urutan)

1. [`docs/methodology.md`](docs/methodology.md) — cara data dikumpulkan
2. [`docs/glossary.md`](docs/glossary.md) — istilah
3. [`docs/adr/001-evidence-layers.md`](docs/adr/001-evidence-layers.md)
4. [`docs/adr/002-campaign-framing.md`](docs/adr/002-campaign-framing.md)
5. [`docs/adr/005-build-time-frontend-composition.md`](docs/adr/005-build-time-frontend-composition.md)
6. [`docs/adr/006-runtime-data-publication.md`](docs/adr/006-runtime-data-publication.md)
7. [`data/README.txt`](data/README.txt) — skema file

## Artefak yang boleh kamu edit

| File | Kapan |
|------|--------|
| `data/hotspots/manifest.json` | Hanya jika memperbaiki kontrak shard; biasanya dihasilkan ingest |
| `data/hotspots/status.json` | Status pipeline FIRMS nasional |
| `data/hotspots/<region>/<date>.json` | Shard runtime FIRMS; jangan commit hourly ke `main` |
| `data/firms.json` | Legacy/bootstrap Kalimantan subset; bukan kontrak runtime produksi utama |
| `data/firms-status.json` | Legacy/bootstrap status Kalimantan; bukan status nasional utama |
| `data/kalimantan-indonesia.geojson` | Polygon filter administratif Indonesia untuk ingestion |
| `data/dossiers/kalimantan.json` | Dossier investigatif Kalimantan (utama) |
| `data/dossiers.json` | Salinan legacy; sinkronkan dari `kalimantan.json` bila mengubah dossier |
| `data/concessions/<region>/inventory/` | Inventaris konsesi generik nasional (hasil `ingest_concessions.py`) |
| `data/boundaries.geojson` | Legacy boundary Kalimantan dossier |
| `docs/methodology.md` | Jika prosedur pengumpulan berubah |
| `README.md` | Hanya jika alur pakai berubah material |

Jangan commit: `firms_sea_7d.csv`, `firms_kalimantan.json`, secret, API key.

**Publikasi produksi:** data runtime FIRMS segar dihasilkan di workspace CI, divalidasi, lalu dikemas ke artefak GitHub Pages. Jangan mengembalikan pola commit hourly `data/hotspots/**` ke `main` kecuali snapshot berkala yang disengaja.

## Empat lapisan — jangan dilipat

| Lapisan | Field / file | Dilarang mengklaim |
|---------|--------------|-------------------|
| Detection | `data/hotspots/<region>/<date>.json` | “Ini api PT X” |
| ConcessionClaim | `walhiHotspots`, `walhiSummary` | Sama dengan join FIRMS live × HGU |
| Control | `control`, `uboStatus` | Spekulasi grup tanpa URL |
| PoliticalTie | `politicalTies` | “Parpol membakar hutan” |

Hotspot di konsesi ≠ perusahaan menyulut api. Ikatan politik ≠ atribusi api.

## Tugas standar

### A. Refresh FIRMS

1. Jalankan `FIRMS_MAP_KEY=… python scripts/ingest_firms.py` atau workflow `Refresh FIRMS NRT`.
2. Pipeline mengambil VIIRS S-NPP, NOAA-20, dan NOAA-21 dari FIRMS Area API.
3. Filter spasial: bbox Indonesia + point-in-polygon terhadap `data/kalimantan-indonesia.geojson`, lalu klasifikasi ke 7 logical region (`sumatra`, `jawa`, `kalimantan`, `sulawesi`, `bali-nusra`, `maluku`, `papua`).
4. Output runtime utama:
   - `data/hotspots/manifest.json`
   - `data/hotspots/status.json`
   - `data/hotspots/<region>/<YYYY-MM-DD>.json`
5. Validasi wajib: schema, koordinat, timestamp, platform, count non-zero per platform, recency, dan penurunan count yang mencurigakan.
6. Jika fetch/validasi gagal: pertahankan shard last-known-good dan tulis status `stale` ke `data/hotspots/status.json`.
7. `data/firms.json` / `data/firms-status.json` hanya legacy/bootstrap Kalimantan; jangan anggap itu kontrak runtime nasional.
8. Jangan mengubah `walhiHotspots` hanya karena FIRMS berubah (periode & produk beda).

### B. Lengkapi / revisi dossier

1. Edit `data/dossiers/kalimantan.json`; sinkronkan `data/dossiers.json` jika masih dipakai.
2. Pertahankan `id` yang ada kecuali user minta rename + update boundary/UI refs.
3. Setiap klaim Control atau PoliticalTie **wajib** punya sumber URL spesifik di `sources` atau `politicalTies[].sources`.
4. Setiap edge bukti butuh sumber independen; jangan pakai satu artikel untuk dua klaim berbeda.
5. `confidence` ikatan: `tinggi` | `sedang` | `rendah` (jujur).
6. Jika tidak ketemu bukti:
   - `uboStatus: "UNKNOWN"`
   - `politicalTies: []` dan/atau `politicalStatus: "TIDAK TERPETAKAN"`
7. **Kiani Lestari (`kiani`)**: jangan hapus caveat The Gecko Project / status operasional meragukan.
8. Centroid hanya dari lokasi operasi publik; label sebagai navigasi kasar di `caveats` bila perlu.

### C. Inventaris konsesi nasional

1. Jalankan `python scripts/ingest_concessions.py` untuk refresh inventaris generik per region.
2. Output: `data/concessions/<region>/inventory/*.geojson` + manifest/status.
3. Inventaris generik ≠ dossier investigatif Kalimantan; jangan mencampur provenance atau klaim politik ke layer inventaris.

### D. Isi boundaries dossier

1. Hanya jika ada geometri dari sumber terbuka yang **berhasil diunduh** dan diverifikasi.
2. `properties.dossierId` = `dossiers[].id` (contoh `sum`, `kideco`).
3. `quality`: `OFFICIAL` | `GFW` | `PERKIRAAN` — jangan `OFFICIAL` kalau perkiraan.
4. CRS WGS84 (lon, lat). Polygon atau MultiPolygon.
5. **Dilarang** menggambar kotak dummy di sekitar centroid agar “terlihat lengkap”.

### E. SIPONGI / WALHI angka agregat

- Update `walhiSummary` / `sipongiFallback` hanya dari rilis/pemberitaan baru dengan URL di `sources`.
- Jangan merekonsiliasi angka SIPONGI dengan count FIRMS menjadi satu time series palsu.

## Checklist sebelum selesai

- [ ] JSON valid (`hotspots/manifest.json`, dossier, boundaries bila diubah)
- [ ] Tidak ada UBO/parpol baru tanpa URL spesifik
- [ ] Tidak ada poligon tanpa `quality` + `source`
- [ ] Empat lapisan tidak dicampur di copy `caveats` / commit message
- [ ] Shard manifest/count konsisten dengan isi shard (jika FIRMS diubah lokal)
- [ ] `python scripts/validate_build.py` lulus
- [ ] Uji cepat: `python scripts/build_dashboard.py`, serve HTTP, buka `index.html`
- [ ] Laporkan ke user: **apa yang diisi**, **apa yang tetap UNKNOWN**, **sumber yang dipakai**

## Commit (hanya jika user minta)

- Pesan fokus *mengapa* (mis. “Fix dossier citation” / “Refresh concession inventory”).
- Jangan push kecuali user minta.
- Jangan commit hourly runtime FIRMS shards ke `main` tanpa kebijakan snapshot eksplisit.
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
Tugas: <refresh FIRMS | lengkapi dossier X | refresh concession inventory>
```

## Verifikasi lokal

```bash
python scripts/build_dashboard.py
python scripts/validate_build.py
python -m http.server 8765
```

Buka http://127.0.0.1:8765/index.html — pilih region untuk memuat shard dan dossier yang tersedia.
