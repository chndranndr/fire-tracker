# Metodologi pengumpulan data — MERATUS

Dokumen ini menjelaskan **dari mana** setiap lapisan data di dashboard berasal, **bagaimana** data itu dikumpulkan dan disaring, **apa yang tidak diklaim**, dan **bagaimana memperbarui** data di masa depan.

Versi dashboard: artefak di repositori `fire-tracker` (vanilla HTML + JSON). Istilah teknis merujuk ke [`glossary.md`](glossary.md) dan ADR di [`adr/`](adr/).

---

## 1. Tujuan dan ruang lingkup

MERATUS adalah dashboard geospasial ringan untuk memantau hotspot karhutla **seluruh Indonesia**, dengan tiga lapisan yang harus dibedakan:

1. **Deteksi FIRMS nasional** — hotspot satelit di 7 logical region, dimuat per region × tanggal.
2. **Inventaris konsesi generik nasional** — katalog polygon izin/konsesi publik per region/sektor (BIG, GFW, dll.).
3. **Dossier investigatif Kalimantan** — 12 konsesi kurasi dengan klaim WALHI, kontrol korporasi, dan ikatan politik terdokumentasi.

Dashboard **bukan** sistem atribusi pidana, bukan sistem verifikasi lapangan, dan bukan join GIS resmi FIRMS × poligon HGU/IUP.

---

## 2. Empat lapisan bukti (wajib terpisah)

Setiap klaim di UI harus tetap berada di lapisannya. Lihat [`adr/001-evidence-layers.md`](adr/001-evidence-layers.md).

| Lapisan | Artefak data | Apa artinya | Apa yang *bukan* |
|--------|--------------|-------------|------------------|
| **Detection** | `data/hotspots/<region>/<date>.json`, `data/hotspots/manifest.json` | Anomali suhu satelit / ringkasan hotspot per region | Kebakaran terverifikasi lapangan; pelaku |
| **ConcessionClaim** | `data/dossiers/kalimantan.json` → `walhiHotspots`, `walhiSummary` | Klaim overlay WALHI (agregat periode Jan–Jul 2026, Kalimantan) | Join live titik FIRMS ke poligon konsesi |
| **Control** | `dossiers[].control`, `uboStatus` | Grup/UBO dari sumber publik bernama | Spekulasi pemilik tanpa kutipan |
| **PoliticalTie** | `dossiers[].politicalTies` | Jabatan partai, kampanye, kekerabatan, kabinet | “Parpol membakar hutan” |

Tepi graf di UI berlabel `KLAIM_OVERLAY` / `KONTROL` / `IKATAN` agar relasi tidak dibaca sebagai satu fakta tunggal. Framing lensa politik: [`adr/002-campaign-framing.md`](adr/002-campaign-framing.md).

---

## 3. Lapisan Detection — NASA FIRMS (nasional)

### 3.1 Sumber primer

- **Produk:** NASA FIRMS VIIRS near-real-time untuk **S-NPP, NOAA-20, dan NOAA-21**.
- **Endpoint:** FIRMS Area API `https://firms.modaps.eosdis.nasa.gov/api/area/` dengan `MAP_KEY` pada secret GitHub Actions.
- **Skrip:** `scripts/ingest_firms.py`.
- **Legacy/bootstrap:** `data/firms.json` dan `data/firms-status.json` tetap ada sebagai subset Kalimantan sementara transisi; **bukan** kontrak runtime produksi utama.

### 3.2 Pipeline pengumpulan (produksi)

1. Ambil observasi VIIRS NRT untuk bbox Indonesia dari ketiga platform.
2. Parse deteksi (lat/lon, brightness, FRP, tanggal, waktu, satelit, confidence, day/night).
3. **Filter spasial Indonesia:** point-in-polygon terhadap `data/kalimantan-indonesia.geojson` (Natural Earth admin-0, bukan bbox Kalimantan saja).
4. Klasifikasikan setiap titik ke salah satu dari 7 logical region: `sumatra`, `jawa`, `kalimantan`, `sulawesi`, `bali-nusra`, `maluku`, `papua` (definisi di `data/regions.json`).
5. Deduplikasi deterministik (`observationId`) dan validasi schema, koordinat, timestamp, platform, recency, serta penurunan count yang mencurigakan.
6. Tulis shard runtime:
   - `data/hotspots/manifest.json` — index nasional per region/tanggal
   - `data/hotspots/status.json` — status pipeline (`healthy` / `stale`, timestamp sync)
   - `data/hotspots/<region>/<YYYY-MM-DD>.json` — titik untuk satu region × satu tanggal
7. Jika validasi gagal: pertahankan shard last-known-good; status ditandai `stale`.

### 3.3 Model publikasi (artifact-only)

- Workflow `Refresh FIRMS NRT` berjalan setiap jam di branch `main`.
- Shard runtime segar dihasilkan di workspace CI, divalidasi, lalu dikemas ke artefak GitHub Pages.
- **Hourly FIRMS runtime tidak di-commit ke source history** (lihat [`adr/006-runtime-data-publication.md`](adr/006-runtime-data-publication.md)).
- Repo source tetap menyimpan snapshot/bootstrap untuk reproducibility lokal dan regression tests.

### 3.4 Cara dibaca di UI

- Tampilan Indonesia memuat ringkasan dari `data/hotspots/manifest.json`.
- Browser mengunduh shard `region × date` hanya saat user memilih region dan tanggal.
- Titik digabung cluster (Leaflet.markercluster) karena volume besar.
- Scrubber waktu memfilter per `date`; filter confidence memotong `conf`.
- Klik titik → inspector Detection saja; kedekatan spasial ke boundary/centroid **bukan** atribusi kebakaran.

### 3.5 Batasan FIRMS

- Hotspot = kandidat termal; bisa api kecil, industri, atau false positive.
- Resolusi VIIRS (~375 m) tidak mencerminkan batas legal konsesi.
- Tiga platform polar-orbiting ≠ observasi kontinu setiap menit.
- Tidak ada koreksi asap/awan di sisi MERATUS.

### 3.6 Cara memperbarui

1. Set repository secret `FIRMS_MAP_KEY`.
2. Jalankan workflow `Refresh FIRMS NRT` (schedule hourly atau manual).
3. Workflow ingest → validate → `scripts/build_dashboard.py` → `scripts/validate_build.py` → upload Pages artifact.
4. Jika ingest gagal, shard last-known-good tetap dipublikasikan dengan status `stale`.

---

## 4. Lapisan konteks resmi — SIPONGI / Kemenhut (fallback & narasi gelombang)

### 4.1 Fungsi di produk

- **Narasi gelombang Agustus 2026** di panel Temuan (konteks Kalimantan, bukan pengganti shard FIRMS nasional).
- **Fallback kontekstual:** blok `sipongiFallback` di dossier Kalimantan menyediakan ringkasan high-confidence SIPONGI bila lapisan FIRMS regional tidak tersedia. Bukan lokasi satelit sebenarnya.

### 4.2 Sumber yang dikutip

Ringkasan di `data/dossiers/kalimantan.json` → `sipongiFallback` merangkum pemberitaan & rilis berbasis SIPONGI (NASA-MODIS/Terra-Aqua *high confidence* menurut Kemenhut), periode **17–19 Agustus 2026**:

| Agregat | Angka |
|---------|------:|
| Total high confidence (Kalbar+Kalteng+Kalsel) | 750 |
| Kalimantan Barat | 367 |
| Kalimantan Tengah | 343 |
| Kalimantan Selatan | 40 |
| Lonjakan 19 Agu (satu hari) | 518 |

Sumber URL tersimpan di `sipongiFallback.sources` (contoh: rilis Kemenhut operasi terpadu; Kompas 21 Agu 2026 tentang 750 hotspot).

### 4.3 Mengapa dua angka (FIRMS 7d vs SIPONGI 3 hari) tidak digabung

- Sensor/produk berbeda (VIIRS NRT CSV vs pelaporan SIPONGI berbasis MODIS high confidence).
- Ambang confidence dan jendela waktu berbeda.
- MERATUS menampilkan keduanya sebagai konteks, **tidak** merekonsiliasi menjadi satu time series resmi.

---

## 5. Lapisan ConcessionClaim — WALHI (Jan–Jul 2026)

### 5.1 Sumber primer

Analisis spasial **Wahana Lingkungan Hidup Indonesia (WALHI)** yang dilaporkan media, periode pantauan **1 Januari – 27 Juli 2026** (agregat pulau Kalimantan). Kutipan utama yang dipakai di `walhiSummary.sources`:

- Kompas.id — ~74% hotspot di kawasan konsesi.
- Detik / liputan daerah — ranking perusahaan per sektor.

Angka ringkas yang di-embed:

| Metrik | Nilai |
|--------|------:|
| Hotspot Kalimantan | 34.262 |
| Di dalam konsesi | 25.524 (~74%) |
| Di HGU sawit | 10.739 |
| Di konsesi tambang | 7.880 |
| Di PBPH | 6.905 |

### 5.2 Seleksi 12 dossier

Dashboard **tidak** mengimpor 34 ribu titik WALHI. Yang diambil adalah **12 konsesi dengan hotspot tertinggi** yang disebut berulang di liputan WALHI, dibagi sektor:

**Tambang**

| ID | Perusahaan | Hotspot (klaim WALHI) |
|----|------------|----------------------:|
| `kideco` | PT Kideco Jaya Agung | 1.116 |
| `kpc` | PT Kaltim Prima Coal | 863 |
| `agm` | PT Antang Gunung Meratus | 840 |
| `bre` | PT Bhumi Rantau Energi | 618 |
| `adaro` | PT Adaro Indonesia | 355 |

**PBPH**

| ID | Perusahaan | Hotspot |
|----|------------|--------:|
| `dwima` | PT Dwima Intiga | 866 |
| `kiani` | PT Kiani Lestari | 707 |

**Sawit (HGU)**

| ID | Perusahaan | Hotspot |
|----|------------|--------:|
| `bsg` | PT Bagus Sentosa Gemilang | 637 |
| `thm1` | PT Tri H.M 1 | 573 |
| `thm2` | PT Tri H.M 2 | 573 |
| `lar` | PT Lestari Alam Raya | 469 |
| `sum` | PT Sumatera Unggul Makmur | 280 |

### 5.3 Centroid lokasi

Setiap dossier punya `centroid: [lat, lon]` untuk navigasi peta/marker. Centroid disusun dari **lokasi operasi yang dipublikasikan** (situs perusahaan, GEM Wiki, pemberitaan lokasi tambang/HTI), **bukan** dari centroid poligon HGU resmi.

Caveat di UI: centroid tetap kasar untuk navigasi; jika suatu dossier belum memiliki Feature, peta hanya menampilkan centroid dan bukan batas legal.

### 5.4 Apa yang tidak dilakukan

- Tidak ada unduhan shapefile HGU/IUP resmi ke dalam repo pada rilis awal.
- Tidak ada intersect FIRMS 7 hari × poligon konsesi.
- Angka `walhiHotspots` **tidak** dihitung ulang dari shard FIRMS; angka itu milik klaim WALHI Jan–Jul.

### 5.5 Inventaris konsesi generik (nasional)

Selain dossier investigatif Kalimantan, MERATUS memuat **inventaris konsesi generik** untuk seluruh Indonesia:

- **Skrip:** `scripts/ingest_concessions.py`
- **Output:** `data/concessions/<region>/inventory/*.geojson` + manifest/status per region
- **Sumber:** layer BIG (mining, forestry, oil palm resmi) dan GFW/WRI (oil palm, forestry) yang tersedia
- **Fungsi UI:** toggle “Inventaris semua konsesi” — katalog spasial luas, tanpa graf politik atau klaim WALHI

Inventaris generik **bukan** ConcessionClaim WALHI dan **bukan** boundary dossier investigatif.

---

## 6. Lapisan Control (UBO / grup) dan PoliticalTie

### 6.1 Metode OSINT

Untuk tiap dari 12 perusahaan:

1. Mulai dari nama konsesi di liputan WALHI.
2. Cari **pemegang saham / grup induk** di laporan keuangan, keterbukaan IDX, situs perusahaan, atau investigasi jurnalistik bernama.
3. Catat orang kunci (direksi, keluarga pengendali) hanya jika muncul di sumber.
4. Cari **ikatan politik yang bisa dikutip**: jabatan partai, peran kampanye resmi, kekerabatan elite yang diliput, peran kabinet — bukan rumor forum.
5. Setiap ikatan mendapat `confidence` (`tinggi` / `sedang` / …) dan `sources[]`.
6. Jika tidak terkunci → status eksplisit:
   - `uboStatus: "UNKNOWN"`
   - `politicalStatus: "TIDAK TERPETAKAN"`
   - Jangan mengarang grup atau partai.

### 6.2 Ringkasan status bukti (rilis awal)

| Status | Konsesi |
|--------|---------|
| UBO `KNOWN` + ada ikatan politik dikutip | Kideco (Indika / Lasmono–Arsjad), KPC (Bakrie / Golkar), Adaro (Thohir / ikatan kabinet) |
| UBO `KNOWN`, parpol `TIDAK TERPETAKAN` | Antang Gunung Meratus (BSSR / Wahana Sentosa; UBO Ghan Djoe Hiang), Bhumi Rantau Energi (sumber grup masih longgar), Dwima Intiga (Dwima Group) |
| UBO `CAVEAT` + ikatan Gerindra/historis | Kiani Lestari — pembelian historis terkait Prabowo (JK 2024) **dan** caveat The Gecko Project (2024) bahwa operasional izin bisa tidak dipegang entitas yang sama |
| UBO `UNKNOWN` + parpol tidak terpetakan | Bagus Sentosa Gemilang, Tri H.M 1/2, Lestari Alam Raya, Sumatera Unggul Makmur |

Jenis ikatan yang diizinkan di data: `kekerabatan`, `jabatan_partai`, `peran_kampanye`, `kabinet` / koalisi — sesuai field `politicalTies[].type`.

### 6.3 Framing (ADR 002)

Ikatan politik adalah **lensa navigasi** (filter partai, hub graf, panel Temuan), bukan bukti penyebab api. Copy UI wajib memuat disclaimer bahwa hotspot di konsesi ≠ perusahaan menyulut api.

---

## 7. Lapisan batas lahan — `boundaries.geojson`

### 7.1 Status saat dokumentasi ini ditulis

Per 22 Agustus 2026, `data/boundaries.geojson` berisi **13 Feature untuk seluruh 12 dossier**. Delapan Feature berasal dari layer resmi BIG/Satu Peta (IUP dan PBPH), sedangkan lima Feature berasal dari layer GFW/WRI oil-palm yang bersifat legacy/incomplete. Satu dossier dapat memiliki lebih dari satu Feature karena izin dapat terpecah (mis. `agm`).

Coverage saat ini: `kideco`, `kpc`, `agm`, `bre`, `adaro`, `dwima`, `kiani` memakai geometri BIG; `bsg`, `thm1`, `thm2`, `lar`, `sum` memakai geometri GFW/WRI. Semua Feature dikueri/diperoleh sebagai WGS84 (`EPSG:4326`/`CRS84`) dan memiliki `source`, `sourceUrl`, `quality`, serta catatan matching di `properties`.

### 7.2 Metode yang direncanakan untuk mengisi

1. Ekspor poligon dari GIS (QGIS) / shapefile HGU–IUP–PBPH / GeoJSON pihak ketiga berlisensi jelas.
2. Pastikan CRS **WGS84** (lon, lat).
3. Setiap Feature:

```json
{
  "type": "Feature",
  "properties": {
    "dossierId": "sum",
    "name": "PT Sumatera Unggul Makmur",
    "quality": "OFFICIAL",
    "source": "uraian sumber",
    "sourceUrl": "https://…"
  },
  "geometry": { "type": "Polygon", "coordinates": [ … ] }
}
```

4. `dossierId` harus cocok dengan `dossiers[].id`.
5. `quality`: `OFFICIAL` | `GFW` | `PERKIRAAN` (UI memakai gaya garis putus untuk perkiraan).

### 7.2.1 Matching yang dipakai pada coverage lengkap

- BIG mencocokkan operator exact setelah normalisasi awalan `PT`: `KIDECO JAYA AGUNG` → `kideco` dan `ADARO INDONESIA` → `adaro`.
- GFW/WRI memiliki record terpisah bernama `PT. Tri H.M 1` dan `PT. Tri H.M 2`; masing-masing dipetakan ke `thm1` dan `thm2` berdasarkan `name` dan `gfwid` exact.
- Record yang hanya menyebut grup, centroid, atau nama yang ambigu tidak dipakai untuk mengisi Feature.

### 7.3 Percobaan otomatis yang gagal / tidak dipakai

- Probe mirror BNPB GFW oil palm dengan parameter `outFields` sempit → HTTP 403; query full-field manual dapat merespons 200 untuk sebagian nama, tetapi tidak menemukan Kideco/Adaro.
- Query WRI ArcGIS commodities → timeout.
- WFS Nusantara Atlas tersedia, tetapi record `Tri H.M` di sana tergabung menjadi satu nama tanpa pemisahan `1`/`2`; record itu tidak dipakai untuk menghindari assignment ambigu.
- Coverage yang dipakai berasal dari query BIG yang berhasil dan layer GFW/WRI yang berhasil diunduh dengan `outSR=4326`; layer GFW tetap diberi caveat legacy/incomplete.

Jangan mengisi poligon “dummy” yang tampak resmi.

---

## 8. Arsitektur penyajian data

Lihat [`adr/005-build-time-frontend-composition.md`](adr/005-build-time-frontend-composition.md) dan [`adr/004-region-date-sharding.md`](adr/004-region-date-sharding.md).

| File / path | Peran |
|-------------|--------|
| `index.html` | Template UI; dipatch saat build |
| `data/hotspots/manifest.json` | Index nasional Detection |
| `data/hotspots/status.json` | Status pipeline FIRMS |
| `data/hotspots/<region>/<date>.json` | Shard Detection per region × tanggal |
| `data/concessions/<region>/inventory/` | Inventaris konsesi generik nasional |
| `data/dossiers/manifest.json` | Availability dossier per region |
| `data/dossiers/kalimantan.json` | WALHI summary, SIPONGI fallback, 12 dossier investigatif |
| `data/concessions/kalimantan/boundaries.geojson` | Boundary dossier Kalimantan |
| `data/firms.json` | Legacy/bootstrap Kalimantan (bukan runtime utama) |

Alur produksi:

1. `scripts/ingest_firms.py` menghasilkan shard runtime di workspace CI.
2. `scripts/build_dashboard.py` menerapkan patch frontend berurutan.
3. `scripts/validate_build.py` menjadi regression gate PR dan deploy.
4. Artefak GitHub Pages memuat shard segar + build dashboard.
5. Browser memuat manifest nasional, lalu lazy-load shard/dossier/inventaris per region.

Tidak ada backend, database, atau API key Google.

---

## 9. Kontrol kualitas dan anti-klaim berlebih

Checklist sebelum menambah klaim baru ke `data/dossiers/kalimantan.json`:

1. Ada **URL sumber bernama** di `sources` atau `politicalTies[].sources`?
2. Apakah klaim masuk lapis yang benar (Detection vs ConcessionClaim vs Control vs PoliticalTie)?
3. Apakah UI/copy masih menghindari vonis pidana?
4. Untuk Kiani: caveat Gecko masih ada?
5. Untuk sawit tanpa UBO: tetap `UNKNOWN`, jangan isi grup dari tebakan nama PT?
6. Untuk geometri: `quality` dan `source` diisi jujur?

---

## 10. Keterbatasan keseluruhan

1. **Dua periode berbeda:** FIRMS snapshot ~7 hari Agustus vs WALHI Jan–Jul — tidak di-overlay sebagai bukti spasial yang sama.
2. **Kualitas dan vintage poligon tidak seragam:** delapan Feature berasal dari BIG, sementara lima Feature GFW/WRI berasal dari dataset lama yang diketahui incomplete; coverage ini tidak membuktikan status HGU/IUP aktif pada 2026 dan tidak dipakai untuk densitas hotspot baru.
3. **Dossier curated 12 PT** → bukan sensus seluruh pemegang izin Kalimantan.
4. **OSINT politik selektif** → banyak tautan elite tidak masuk karena tidak ada sumber yang memenuhi ambang.
5. **Fallback SIPONGI** di dossier Kalimantan adalah konteks gelombang, bukan shard FIRMS nasional.
6. **Lisensi data pihak ketiga** (FIRMS, liputan media, kelak GFW/HGU) harus dihormati saat redistribusi massal.

---

## 11. Cara mereplikasi pengumpulan (ringkas)

```text
A. FIRMS nasional
   FIRMS_MAP_KEY → scripts/ingest_firms.py
   → filter Indonesia → 7 logical regions
   → tulis data/hotspots/manifest.json + status.json + <region>/<date>.json
   → publish via GitHub Pages artifact (bukan commit hourly ke main)

B. Inventaris konsesi nasional
   scripts/ingest_concessions.py
   → fetch BIG/GFW sources → shard per region
   → tulis data/concessions/<region>/inventory/

C. WALHI dossier (Kalimantan)
   baca liputan WALHI Jan–Jul 2026 → isi data/dossiers/kalimantan.json

D. Control / politik
   sumber bernama (IDX, KPU, media, investigasi) → control + politicalTies atau UNKNOWN
   setiap edge bukti butuh kutipan independen

E. SIPONGI konteks
   rilis Kemenhut + liputan 17–19 Agu → isi sipongiFallback di dossier Kalimantan

F. Build & deploy
   scripts/build_dashboard.py → scripts/validate_build.py → GitHub Pages
```

---

## 12. Referensi internal

- [`glossary.md`](glossary.md) — istilah domain
- [`adr/001-evidence-layers.md`](adr/001-evidence-layers.md) — empat lapisan
- [`adr/002-campaign-framing.md`](adr/002-campaign-framing.md) — lensa politik
- [`adr/004-region-date-sharding.md`](adr/004-region-date-sharding.md) — shard hotspot nasional
- [`adr/005-build-time-frontend-composition.md`](adr/005-build-time-frontend-composition.md) — build dashboard
- [`adr/006-runtime-data-publication.md`](adr/006-runtime-data-publication.md) — publikasi artifact-only
- [`adr/007-dossier-inventory-separation.md`](adr/007-dossier-inventory-separation.md) — dossier vs inventaris
- [`../data/README.txt`](../data/README.txt) — skema file data

---

*Dokumen ini mendeskripsikan metodologi yang dipakai membangun dataset awal MERATUS. Pembaruan data di masa depan harus mengikuti lapisan bukti yang sama; jika metodologi berubah, revisi file ini dan catat tanggal di commit.*
