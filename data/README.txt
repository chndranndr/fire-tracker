MERATUS data (pipeline NRT atau edit manual terkontrol, refresh browser)

firms.json
  { "meta": { "source", "url", "platforms", "fetched",
               "lastSuccessfulSync", "newestDetectionUtc", "count",
               "pipelineVersion", "pipelineStatus", ... },
    "points": [ { "observationId", "lat", "lon", "b4", "b5", "frp",
                  "date", "time", "sat", "platform", "conf", "dn", ... }, ... ] }

firms-status.json (opsional; dibuat oleh pipeline)
  Status pipeline terpisah dari dataset. Saat `pipelineStatus` = `stale`,
  dashboard mempertahankan firms.json sebelumnya dan menampilkan peringatan.

Pipeline
  `python scripts/ingest_firms.py` membutuhkan `FIRMS_MAP_KEY` NASA FIRMS.
  Sumber: VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT.
  Filter spasial saat ini menggunakan bbox Kalimantan + coarse exclusion
  boxes Sarawak/Sabah; jangan menyebut hasilnya sebagai batas administrasi
  presisi tanpa mengganti filter dengan polygon clip yang diverifikasi.

dossiers.json
  { "walhiSummary": { ... },
    "sipongiFallback": { ... },
    "dossiers": [ { "id", "name", "sector", "province", "walhiHotspots",
                    "centroid": [lat, lon], "uboStatus", "control",
                    "politicalTies", "caveats", "sources" }, ... ] }

boundaries.geojson  (region konsesi di peta)
  FeatureCollection. Setiap Feature:
    properties.dossierId  = id di dossiers.json  (wajib, contoh: "sum")
    properties.quality    = "OFFICIAL" | "GFW" | "PERKIRAAN"
    properties.source     = teks sumber
    properties.sourceUrl  = URL (wajib; dataset/query URL yang bisa diverifikasi)
    geometry              = Polygon atau MultiPolygon (WGS84 lon/lat)

  Contoh satu fitur:
  {
    "type": "Feature",
    "properties": {
      "dossierId": "sum",
      "name": "PT Sumatera Unggul Makmur",
      "quality": "OFFICIAL",
      "source": "HGU / peta izin yang kamu punya",
      "sourceUrl": "https://…"
    },
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[110.1, -0.4], [110.3, -0.4], [110.3, -0.2], [110.1, -0.2], [110.1, -0.4]]]
    }
  }

  Tanpa Feature untuk suatu id → di peta hanya centroid (belum ada region).

Serve with: python -m http.server 8765
Open: http://127.0.0.1:8765/index.html
