MERATUS data (edit manual, refresh browser)

firms.json
  { "meta": { "source", "url", "fetched", "count", ... },
    "points": [ { "lat", "lon", "b4", "b5", "frp", "date", "time", "sat", "conf", "dn" }, ... ] }

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
    properties.sourceUrl  = URL (opsional)
    geometry              = Polygon atau MultiPolygon (WGS84 lon/lat)

  Contoh satu fitur:
  {
    "type": "Feature",
    "properties": {
      "dossierId": "sum",
      "name": "PT Sumatera Unggul Makmur",
      "quality": "OFFICIAL",
      "source": "HGU / peta izin yang kamu punya",
      "sourceUrl": ""
    },
    "geometry": {
      "type": "Polygon",
      "coordinates": [[[110.1, -0.4], [110.3, -0.4], [110.3, -0.2], [110.1, -0.2], [110.1, -0.4]]]
    }
  }

  Tanpa Feature untuk suatu id → di peta hanya centroid (belum ada region).

Serve with: python -m http.server 8765
Open: http://127.0.0.1:8765/index.html
