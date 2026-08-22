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

## Data (edit manual)

| File | Isi |
|------|-----|
| `data/firms.json` | Titik FIRMS (`meta` + `points`) |
| `data/dossiers.json` | 12 dossier + ringkasan WALHI + fallback SIPONGI |
| `data/boundaries.geojson` | Poligon batas konsesi (`properties.dossierId`) |

Lihat `data/README.txt` untuk skema.

## Catatan bukti

Deteksi satelit ≠ kebakaran terverifikasi. Hotspot di konsesi (klaim WALHI) ≠ tuduhan pembakaran. Ikatan politik = sumber publik (jabatan/kampanye/kekerabatan), bukan atribusi api.
