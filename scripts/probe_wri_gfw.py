"""Query WRI GFW commodities oil palm layer for dossier matches; write sample GeoJSON if found."""
import json
import pathlib
import urllib.parse
import urllib.request

BASE = "https://gis-gfw.wri.org/arcgis/rest/services/commodities/MapServer/25/query"
UA = {"User-Agent": "MERATUS-fire-tracker/1.0 (research; open-source OSINT)"}

# Map search needles -> dossier ids (from dossiers.json)
SEARCH = [
    ("sum", ["SUMATERA UNGGUL", "SUMATRA UNGGUL"]),
    ("bsg", ["BAGUS SENTOSA"]),
    ("lar", ["LESTARI ALAM RAYA", "LESTARI ALAM"]),
    ("thm1", ["TRI H.M", "TRI HM", "TRI H M"]),
    ("thm2", ["TRI H.M", "TRI HM"]),
    ("kideco", ["KIDECO"]),
    ("adaro", ["ADARO"]),
    ("kpc", ["KALTIM PRIMA", "KPC"]),
    ("agm", ["ANTANG GUNUNG"]),
    ("bre", ["BHUMI RANTAU"]),
    ("dwima", ["DWIMA"]),
    ("kiani", ["KIANI"]),
]


def fetch(where: str, geometry: bool = False, count: int = 20) -> dict:
    params = {
        "where": where,
        "outFields": "*",
        "returnGeometry": "true" if geometry else "false",
        "outSR": "4326",
        "f": "geojson" if geometry else "json",
        "resultRecordCount": str(count),
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def main() -> None:
    # Discover field names
    meta = fetch("1=1", geometry=False, count=1)
    feats = meta.get("features") or []
    if feats:
        print("ATTR KEYS", sorted((feats[0].get("attributes") or {}).keys()))
        print("SAMPLE", feats[0].get("attributes"))
    else:
        print("NO SAMPLE", meta.keys(), list(meta.keys()))
        # try geojson mode for sample
        g = fetch("1=1", geometry=True, count=1)
        print("GEOJSON keys", g.keys(), "n", len(g.get("features") or []))
        if g.get("features"):
            print("props", g["features"][0].get("properties"))


if __name__ == "__main__":
    main()
