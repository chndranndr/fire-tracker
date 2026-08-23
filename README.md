# MERATUS

Intel dashboard (vanilla HTML/CSS/JS) untuk hotspot karhutla Indonesia, dengan layer dossier/konsesi dan jaringan afiliasi publik yang dimuat per wilayah ketika tersedia.

## Jalankan lokal

Siapkan kontrak shard dan dashboard hasil patch terlebih dulu:

```bash
python scripts/bootstrap_hotspot_shards.py
python scripts/patch_land_holdings_dashboard.py
python scripts/patch_region_dashboard.py
```

Lalu jalankan HTTP server:

```bash
python -m http.server 8765
```

Buka http://127.0.0.1:8765/index.html.

Untuk file besar, gunakan server threaded:

```bash
python -c "from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler; ThreadingHTTPServer(('127.0.0.1', 8765), SimpleHTTPRequestHandler).serve_forever()"
```

## Data

### Hotspot FIRMS

| File | Isi |
|------|-----|
| `data/regions.json` | Definisi 7 logical region Indonesia, center map, dan daftar provinsi |
| `data/hotspots/manifest.json` | Index nasional hotspot per region dan tanggal |
| `data/hotspots/<region>/<YYYY-MM-DD>.json` | Titik FIRMS hanya untuk satu region dan satu tanggal |
| `data/hotspots/status.json` | Status pipeline FIRMS nasional |
| `data/firms.json` | Compatibility subset Kalimantan sementara selama transisi |
| `data/firms-status.json` | Compatibility status Kalimantan sementara |

Logical region yang digunakan: `sumatra`, `jawa`, `kalimantan`, `sulawesi`, `bali-nusra`, `maluku`, dan `papua`.

Frontend membaca `manifest.json` terlebih dulu. Pada tampilan Indonesia, browser hanya menampilkan agregasi per region dari manifest. Raw hotspot baru diunduh ketika user memilih region dan tanggal tertentu.

### Dossier dan konsesi

| File | Isi |
|------|-----|
| `data/dossiers/manifest.json` | Availability dan URL dossier per region |
| `data/dossiers/<region>.json` | Dossier untuk satu region |
| `data/concessions/manifest.json` | Availability dan URL boundary per region |
| `data/concessions/<region>/boundaries.geojson` | Polygon konsesi untuk satu region |

Saat ini dataset dossier/konsesi yang terisi adalah Kalimantan. Region lain tetap dapat menampilkan hotspot FIRMS walaupun dossier atau polygon konsesinya belum tersedia.

Lihat `data/README.txt` untuk skema legacy/detail tambahan.

## Refresh FIRMS NRT

GitHub Actions menjalankan [`firms-nrt.yml`](.github/workflows/firms-nrt.yml) setiap jam. Workflow membutuhkan repository secret `FIRMS_MAP_KEY` dari NASA FIRMS, mengambil VIIRS S-NPP, NOAA-20, dan NOAA-21 untuk bbox Indonesia, memfilter titik memakai polygon Indonesia, mendeduplikasi observation, mengklasifikasikan titik ke logical region, lalu menulis shard `region × date`.

Jika fetch gagal, salah satu platform kosong, data stale, atau jumlah observation turun secara mencurigakan, dataset last-known-good dipertahankan dan status ditandai stale.

Pada deploy pertama sebelum national manifest tersedia, [`bootstrap_hotspot_shards.py`](scripts/bootstrap_hotspot_shards.py) dapat membuat manifest Kalimantan sementara dari legacy `data/firms.json`. Setelah scheduled national ingest berhasil, manifest bootstrap otomatis tergantikan oleh shard nasional.

Frontend Pages dibangun dengan dua patch berurutan: [`patch_land_holdings_dashboard.py`](scripts/patch_land_holdings_dashboard.py), lalu [`patch_region_dashboard.py`](scripts/patch_region_dashboard.py). Patch kedua mengaktifkan region selector, national summary, lazy loading per region/tanggal, regional dossier/polygon loading, dan chunked MarkerCluster rendering.

## Catatan bukti

Deteksi satelit ≠ kebakaran terverifikasi. Hotspot di konsesi (klaim WALHI) ≠ tuduhan pembakaran. Ikatan politik = sumber publik (jabatan/kampanye/kekerabatan), bukan atribusi api.

Metodologi lengkap pengumpulan data: [`docs/methodology.md`](docs/methodology.md).

Instruksi untuk AI agent (update/lengkapi data): [`agent.md`](agent.md).
