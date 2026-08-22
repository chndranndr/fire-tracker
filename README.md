# MERATUS

Intel dashboard (vanilla HTML/CSS/JS) untuk hotspot karhutla Kalimantan, klaim konsesi WALHI, dan jaringan afiliasi publik.

## Jalankan lokal

```bash
python -m http.server 8765
```

Buka http://127.0.0.1:8765/index.html

Lebih aman untuk file besar: server threaded

```bash
python -c "from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler; ThreadingHTTPServer(('127.0.0.1', 8765), SimpleHTTPRequestHandler).serve_forever()"
```

## Data

| File | Isi |
|------|-----|
| `data/firms.json` | Titik FIRMS (`meta` + `points`) |
| `data/firms-status.json` | Status pipeline NRT; dataset lama dipertahankan jika ingest gagal |
| `data/dossiers.json` | 12 dossier + ringkasan WALHI + fallback SIPONGI |
| `data/boundaries.geojson` | Poligon batas konsesi (`properties.dossierId`) |

Lihat `data/README.txt` untuk skema.

### Refresh FIRMS NRT

GitHub Actions menjalankan [`firms-nrt.yml`](.github/workflows/firms-nrt.yml) setiap jam. Workflow membutuhkan repository secret `FIRMS_MAP_KEY` dari NASA FIRMS, mengambil VIIRS S-NPP, NOAA-20, dan NOAA-21, lalu memvalidasi dan mendeduplikasi observation secara deterministik.

Jika fetch gagal atau jumlah titik turun secara mencurigakan, workflow hanya memperbarui `data/firms-status.json` dengan status `stale`; `data/firms.json` terakhir yang valid tidak ditimpa.

## Catatan bukti

Deteksi satelit ≠ kebakaran terverifikasi. Hotspot di konsesi (klaim WALHI) ≠ tuduhan pembakaran. Ikatan politik = sumber publik (jabatan/kampanye/kekerabatan), bukan atribusi api.

Metodologi lengkap pengumpulan data: [`docs/methodology.md`](docs/methodology.md).

Instruksi untuk AI agent (update/lengkapi data): [`agent.md`](agent.md).
