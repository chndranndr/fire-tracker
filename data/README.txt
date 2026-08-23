MERATUS data (pipeline NRT atau edit manual terkontrol, refresh browser)

firms.json
  { "meta": { "source", "url", "platforms", "fetched",
               "lastSuccessfulSync", "newestDetectionUtc", "count",
               "pipelineVersion", "pipelineStatus", ... },
    "points": [ { "observationId", "lat", "lon", "b4", "b5", "frp",
                  "date", "time", "sat", "platform", "conf", "dn", ... }, ... ] }

firms-status.json (opsional; dibuat oleh pipeline)
  Status operasional pipeline terpisah dari provenance dataset. Saat
  `pipelineStatus` = `stale`, dashboard mempertahankan firms.json sebelumnya
  dan menampilkan peringatan; status tidak boleh mengganti `meta.source`,
  `meta.platforms`, atau `meta.count` dari dataset yang sedang ditampilkan.

Pipeline
  `python scripts/ingest_firms.py` membutuhkan `FIRMS_MAP_KEY` NASA FIRMS.
  Sumber: VIIRS_SNPP_NRT, VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT.
  Filter spasial menggunakan bbox Kalimantan + point-in-polygon terhadap
  `kalimantan-indonesia.geojson`. Polygon tersebut berasal dari Natural Earth
  admin-0 countries 1:110m, dengan source/version/license dicatat di metadata.
  Rectangle Sarawak/Sabah tidak digunakan karena dapat membuang titik valid
  di wilayah Indonesia.

kalimantan-indonesia.geojson
  Polygon negara Indonesia yang dipakai hanya sebagai filter ingestion; bbox
  Kalimantan di pipeline membatasi hasil ke pulau Kalimantan. File ini bukan
  boundary konsesi dan tidak ditampilkan sebagai evidence perusahaan.

dossiers.json
  { "walhiSummary": { ... },
    "sipongiFallback": { ... },
    "dossiers": [ { "id", "name", "sector", "province", "walhiHotspots",
                    "centroid": [lat, lon], "uboStatus", "control",
                    "politicalTies", "caveats", "sources" }, ... ] }

affiliated-land-holdings.json
  Inventaris OSINT hak/izin lahan di Kalimantan yang memiliki hubungan korporasi
  terverifikasi dengan Haji Isam/Jhonlin atau anggota keluarga yang disebut sumber.
  File ini adalah lapisan Control tambahan, BUKAN ConcessionClaim WALHI dan BUKAN
  atribusi kebakaran.

  Struktur utama:
  { "meta": { "asOf", "recordCount", "geometryIncluded", "caveats" },
    "people": [ { "id", "name", "relationToHajiIsam", "sources" }, ... ],
    "holdings": [ { "id", "company", "sector", "permitType", "areaHa",
                    "province", "permitNumber", "permitStatus", "control",
                    "sources", "caveats" }, ... ] }

  Aturan evidence:
  - Setiap record holding harus punya sumber izin/luas dan sumber hubungan kontrol.
  - Hubungan keluarga, jabatan komisaris, dan kepemilikan saham dibedakan; jabatan
    komisaris tidak otomatis berarti pemilik.
  - Kepemilikan minoritas harus diberi label eksplisit dan tidak boleh ditulis
    sebagai kontrol penuh.
  - Teman/kerabat tanpa bukti hak lahan atau kontrol korporasi tidak dimasukkan.
  - Jangan menambahkan `walhiHotspots` ke file ini kecuali ada ConcessionClaim
    terpisah yang benar-benar menyebut konsesi tersebut.
  - `geometryIncluded: false` berarti luas izin tidak boleh divisualisasikan sebagai
    polygon buatan. Boundary baru tetap mengikuti aturan boundaries.geojson.

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
