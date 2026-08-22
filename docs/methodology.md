# Metodologi pengumpulan data — MERATUS

Dokumen ini menjelaskan **dari mana** setiap lapisan data di dashboard berasal, **bagaimana** data itu dikumpulkan dan disaring, **apa yang tidak diklaim**, dan **bagaimana memperbarui** data di masa depan.

Versi dashboard: artefak di repositori `fire-tracker` (vanilla HTML + JSON). Istilah teknis merujuk ke [`glossary.md`](glossary.md) dan ADR di [`adr/`](adr/).

---

## 1. Tujuan dan ruang lingkup

MERATUS memetakan gelombang karhutla di Kalimantan (Agustus 2026 dan konteks Jan–Jul 2026) dengan tiga pertanyaan navigasi:

1. Di mana deteksi termal satelit (hotspot) muncul?
2. Konsesi mana yang dilaporkan organisasi masyarakat sipil memiliki hotspot tinggi di dalamnya?
3. Siapa pengendali korporasi yang bisa dikutip dari sumber terbuka, dan apa ikatan politik publik yang terkait?

Dashboard **bukan** sistem atribusi pidana, bukan sistem verifikasi lapangan, dan bukan join GIS resmi FIRMS × poligon HGU/IUP.

---

## 2. Empat lapisan bukti (wajib terpisah)

Setiap klaim di UI harus tetap berada di lapisannya. Lihat [`adr/001-evidence-layers.md`](adr/001-evidence-layers.md).

| Lapisan | Artefak data | Apa artinya | Apa yang *bukan* |
|--------|--------------|-------------|------------------|
| **Detection** | `data/firms.json` (atau fallback SIPONGI) | Anomali suhu satelit / ringkasan hotspot resmi | Kebakaran terverifikasi lapangan; pelaku |
| **ConcessionClaim** | `data/dossiers.json` → `walhiHotspots`, `walhiSummary` | Klaim overlay WALHI (agregat periode Jan–Jul 2026) | Join live titik FIRMS 7 hari ke poligon konsesi |
| **Control** | `dossiers[].control`, `uboStatus` | Grup/UBO dari sumber publik bernama | Spekulasi pemilik tanpa kutipan |
| **PoliticalTie** | `dossiers[].politicalTies` | Jabatan partai, kampanye, kekerabatan, kabinet | “Parpol membakar hutan” |

Tepi graf di UI berlabel `KLAIM_OVERLAY` / `KONTROL` / `IKATAN` agar relasi tidak dibaca sebagai satu fakta tunggal. Framing lensa politik: [`adr/002-campaign-framing.md`](adr/002-campaign-framing.md).

---

## 3. Lapisan Detection — NASA FIRMS

### 3.1 Sumber primer

- **Produk target pipeline:** NASA FIRMS VIIRS near-real-time untuk **S-NPP, NOAA-20, dan NOAA-21**.
- **Endpoint pipeline:** FIRMS Area API `https://firms.modaps.eosdis.nasa.gov/api/area/` dengan `MAP_KEY` pada secret GitHub Actions.
- **Snapshot yang masih ada di repository:** Suomi-NPP VIIRS C2 SouthEast Asia 7-day. Snapshot tersebut tetap dapat dimuat sebagai known-good fallback sampai workflow NRT pertama berhasil.
- **Mengapa bukan Google Maps Embed:** lapisan api di peta Google umumnya bertumpu pada deteksi FIRMS/sejenis; Embed membutuhkan API key dan tidak cocok untuk alur OSINT/self-host. MERATUS memakai sumber FIRMS langsung.

### 3.2 Pipeline pengumpulan (snapshot yang di-commit)

1. Ambil lima hari terakhir untuk setiap sumber VIIRS NRT.
2. Parse baris deteksi (latitude, longitude, bright_ti4/ti5, FRP, tanggal, waktu, satelit, confidence, day/night, dan atribut sensor lain yang tersedia).
3. **Filter spasial Kalimantan Indonesia:** bbox kasar + point-in-polygon terhadap `data/kalimantan-indonesia.geojson`, yang bersumber dari Natural Earth admin-0 countries 1:110m. Rectangle Sarawak/Sabah tidak digunakan karena mencakup wilayah Indonesia di perbatasan.
4. Normalisasi platform dan confidence ke label UI: `low` / `nominal` / `high`.
5. Tambahkan `observationId` deterministik dari platform + tanggal/waktu akuisisi + koordinat, lalu hapus hanya record exact-duplicate.
6. Validasi schema, koordinat, timestamp, platform, non-empty result, recency per platform, serta penurunan count aggregate dan per platform yang mencurigakan.
7. Tulis `data/firms.json` dan `data/firms-status.json` hanya jika dataset baru lolos validasi:

```json
{
  "meta": {
    "source": "NASA FIRMS NRT VIIRS",
    "platforms": ["S-NPP", "NOAA-20", "NOAA-21"],
    "url": "…",
    "fetched": "YYYY-MM-DD",
    "lastSuccessfulSync": "YYYY-MM-DDTHH:MM:SSZ",
    "newestDetectionUtc": "YYYY-MM-DDTHH:MM:SSZ",
    "sourceCounts": {"S-NPP": 1234, "NOAA-20": 1234, "NOAA-21": 1234},
    "sourceObservations": {"S-NPP": {"newestDetectionUtc": "YYYY-MM-DDTHH:MM:SSZ"}},
    "pipelineVersion": "3",
    "pipelineStatus": "healthy",
    "count": 20500
  },
  "points": [
    {
      "lat": -2.19013,
      "lon": 112.68287,
      "b4": 344.34,
      "b5": 293.47,
      "frp": 4.04,
      "date": "2026-08-14",
      "time": "0642",
      "sat": "N",
      "conf": "nominal",
      "dn": "D"
    }
  ]
}
```

### 3.3 Snapshot yang dipakai di dashboard awal

| Metrik | Nilai (meta repositori) |
|--------|-------------------------|
| Tanggal fetch | 2026-08-21 |
| Jumlah titik setelah filter | 20.500 |
| Confidence | high 905 · nominal 18.915 · low 680 |
| Rentang tanggal di file | ~2026-08-14 … 2026-08-20 |

Angka ini **bukan** sama dengan 750 hotspot high-confidence SIPONGI 17–19 Agustus (produk & ambang berbeda — lihat §4).

### 3.4 Cara dibaca di UI

- Titik digabung cluster (Leaflet.markercluster) karena volume besar.
- Scrubber waktu memfilter per `date`.
- Filter `Keyakinan FIRMS` memotong `conf`.
- Klik titik → inspector Detection saja; asosiasi spasial memakai urutan **point-in-polygon boundary**, jarak ke **tepi polygon terdekat**, lalu **centroid fallback** hanya untuk dossier tanpa boundary. Kedekatan atau overlap tetap **bukan atribusi kebakaran**.

### 3.5 Batasan FIRMS

- Hotspot = kandidat termal; bisa jadi api kecil, industri, atau false positive.
- Resolusi VIIRS (~375 m) tidak mencerminkan batas legal konsesi.
- FIRMS mendistribusikan data near-real-time, bukan continuous live imagery. Dashboard menampilkan snapshot terakhir yang berhasil di-ingest.
- Tidak ada koreksi asap/awan di sisi MERATUS.
- S-NPP, NOAA-20, dan NOAA-21 tetap satelit polar-orbiting; tiga platform tidak berarti observasi kontinu setiap menit.

### 3.6 Cara memperbarui

1. Set repository secret `FIRMS_MAP_KEY`.
2. Jalankan workflow `Refresh FIRMS NRT` secara manual atau tunggu cron hourly.
3. Workflow melakukan safe publish ke `data/firms.json`, menulis archive harian, memperbarui metadata freshness, lalu men-deploy Pages dari workspace yang sama.
4. Jika fetch atau validasi gagal, workflow menulis `pipelineStatus: stale` ke `data/firms-status.json` dan mempertahankan dataset terakhir yang valid.

---

## 4. Lapisan konteks resmi — SIPONGI / Kemenhut (fallback & narasi gelombang)

### 4.1 Fungsi di produk

- **Narasi gelombang Agustus 2026** di panel Temuan / stempel (bukan pengganti peta titik kecuali fallback).
- **Fallback UI:** jika `data/firms.json` gagal dimuat atau `points` kosong, UI mensintesis titik sebaran kasar dari `sipongiFallback.daily` (bukan lokasi satelit sebenarnya).

### 4.2 Sumber yang dikutip

Ringkasan di `dossiers.json` → `sipongiFallback` merangkum pemberitaan & rilis berbasis SIPONGI (NASA-MODIS/Terra-Aqua *high confidence* menurut Kemenhut), periode **17–19 Agustus 2026**:

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
- Angka `walhiHotspots` **tidak** dihitung ulang dari `firms.json`; angka itu milik klaim WALHI Jan–Jul.

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

Lihat [`adr/003-single-html.md`](adr/003-single-html.md).

| File | Peran |
|------|--------|
| `index.html` | UI Palantir-style; `fetch` JSON |
| `data/firms.json` | Detection |
| `data/dossiers.json` | WALHI summary, SIPONGI fallback, 12 dossier |
| `data/boundaries.geojson` | Region konsesi (opsional) |
| `data/README.txt` | Skema singkat untuk editor data |

Alur runtime:

1. Browser memuat `index.html` lewat HTTP (lokal atau GitHub Pages).
2. `fetch("data/firms.json")`, `fetch("data/dossiers.json")`, `fetch("data/boundaries.geojson")` dengan `cache: "no-store"`.
3. Jika FIRMS gagal → sintesis fallback SIPONGI.
4. Jika boundaries kosong → hanya centroid.

Tidak ada backend, database, atau API key Google pada rilis ini.

---

## 9. Kontrol kualitas dan anti-klaim berlebih

Checklist sebelum menambah klaim baru ke `dossiers.json`:

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
5. **Fallback SIPONGI** menyebar titik secara sintetis di sekitar pusat provinsi — hanya untuk menjaga kanvas hidup, bukan lokasi akurat.
6. **Lisensi data pihak ketiga** (FIRMS, liputan media, kelak GFW/HGU) harus dihormati saat redistribusi massal.

---

## 11. Cara mereplikasi pengumpulan (ringkas)

```text
A. FIRMS
   unduh CSV SEA 7d → filter bbox Kalimantan ID → buang MY → tulis data/firms.json

B. WALHI dossier
   baca liputan WALHI Jan–Jul 2026 → ambil 12 nama + angka hotspot → isi dossiers[]

C. Control / politik
   IDX / annual report / investigasi bernama → isi control + politicalTies atau UNKNOWN

D. SIPONGI konteks
   rilis Kemenhut + liputan 17–19 Agu → isi sipongiFallback

E. Boundaries
   pertahankan Feature yang provenance-nya valid; cari sumber terbuka baru → properties.dossierId → data/boundaries.geojson
```

---

## 12. Referensi internal

- [`glossary.md`](glossary.md) — istilah domain
- [`adr/001-evidence-layers.md`](adr/001-evidence-layers.md) — empat lapisan
- [`adr/002-campaign-framing.md`](adr/002-campaign-framing.md) — lensa politik
- [`adr/003-single-html.md`](adr/003-single-html.md) — distribusi JSON
- [`../data/README.txt`](../data/README.txt) — skema file data

---

*Dokumen ini mendeskripsikan metodologi yang dipakai membangun dataset awal MERATUS. Pembaruan data di masa depan harus mengikuti lapisan bukti yang sama; jika metodologi berubah, revisi file ini dan catat tanggal di commit.*
