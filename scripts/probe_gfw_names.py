"""Probe public GFW-style layers for dossier company name matches."""
import json
import urllib.parse
import urllib.request

ENDPOINTS = [
    # BNPB mirror of Indonesia oil palm concessions
    "https://gis.bnpb.go.id/server/rest/services/InAWARE/Global_forest_watch2/MapServer/6/query",
]

NEEDLES = [
    "SUMATERA UNGGUL",
    "SUMATRA UNGGUL",
    "BAGUS SENTOSA",
    "LESTARI ALAM",
    "TRI H",
    "KIDECO",
    "ADARO",
    "KALTIM PRIMA",
    "ANTANG GUNUNG",
    "BHUMI RANTAU",
    "DWIMA",
    "KIANI",
]


def query(base: str, where: str) -> list:
    params = {
        "where": where,
        "outFields": "name,company,group_comp,area_ha,type",
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": "8",
    }
    url = base + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        data = json.loads(r.read().decode())
    return data.get("features") or []


def main() -> None:
    for base in ENDPOINTS:
        print("ENDPOINT", base)
        for n in NEEDLES:
            where = (
                f"UPPER(company) LIKE '%{n}%' OR UPPER(name) LIKE '%{n}%'"
            )
            try:
                feats = query(base, where)
                print(f"  {n}: {len(feats)}")
                for f in feats[:3]:
                    print("   ", f.get("attributes"))
            except Exception as e:
                print(f"  {n}: ERR {e}")


if __name__ == "__main__":
    main()
