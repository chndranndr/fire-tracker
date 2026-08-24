#!/usr/bin/env python3
"""Build a public Kalimantan concession inventory for the MERATUS static map.

The inventory is separate from investigative dossiers. It records public
concession/licence polygons and source attributes; it does not infer fire
causation, illegality, political affiliation, or ownership beyond source data.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import ingest_firms  # noqa: E402

BIG_BASE = "https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/PERIZINAN_DAN_PERTANAHAN/MapServer"
GFW_BASE = "https://gis.bnpb.go.id/server/rest/services/InAWARE/Global_forest_watch2/MapServer"
KALIMANTAN_BBOX = (108.8, -4.5, 119.3, 4.4)
DEFAULT_BOUNDARY = ROOT / "data" / "kalimantan-indonesia.geojson"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "concessions" / "kalimantan" / "inventory"
DEFAULT_DOSSIERS = ROOT / "data" / "dossiers.json"
PAGE_SIZE = 1000
SIMPLIFY_TOLERANCE = 0.00035
PIPELINE_VERSION = "1"

SOURCE_SPECS = (
    {"id":"big-forestry-ha","layer":1,"base":BIG_BASE,"output":"forestry-ha.geojson","sector":"PBPH","subtype":"IUPHHK-HA","quality":"OFFICIAL","required":True,"normalizer":"forestry"},
    {"id":"big-forestry-hti","layer":2,"base":BIG_BASE,"output":"forestry-hti.geojson","sector":"PBPH","subtype":"IUPHHK-HTI","quality":"OFFICIAL","required":True,"normalizer":"forestry"},
    {"id":"big-forestry-re","layer":3,"base":BIG_BASE,"output":"forestry-re.geojson","sector":"PBPH","subtype":"IUPHHK-RE","quality":"OFFICIAL","required":True,"normalizer":"forestry"},
    {"id":"big-mining-wiup","layer":4,"base":BIG_BASE,"output":"mining.geojson","sector":"Tambang","subtype":"WIUP","quality":"OFFICIAL","required":True,"normalizer":"mining"},
    {"id":"big-oil-palm-kutai-barat","layer":36,"base":BIG_BASE,"output":"oil-palm-official.geojson","sector":"Sawit","subtype":"Izin Lokasi Sawit","quality":"OFFICIAL","required":False,"normalizer":"oil_palm_big"},
    {"id":"big-oil-palm-kutai-kartanegara","layer":37,"base":BIG_BASE,"output":"oil-palm-official.geojson","sector":"Sawit","subtype":"Izin Lokasi Sawit","quality":"OFFICIAL","required":False,"normalizer":"oil_palm_big"},
    {"id":"big-oil-palm-kutai-timur","layer":38,"base":BIG_BASE,"output":"oil-palm-official.geojson","sector":"Sawit","subtype":"Izin Lokasi Sawit","quality":"OFFICIAL","required":False,"normalizer":"oil_palm_big"},
    {"id":"big-oil-palm-paser","layer":39,"base":BIG_BASE,"output":"oil-palm-official.geojson","sector":"Sawit","subtype":"Izin Lokasi Sawit","quality":"OFFICIAL","required":False,"normalizer":"oil_palm_big"},
    {"id":"gfw-oil-palm","layer":6,"base":GFW_BASE,"output":"oil-palm-gfw.geojson","sector":"Sawit","subtype":"Oil palm concession","quality":"GFW","required":False,"normalizer":"oil_palm_gfw"},
)


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_utc(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json_atomic(path: Path, payload: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, separators=(",", ":"))
        tmp.write("\n")
        temp_name = tmp.name
    Path(temp_name).replace(path)


def read_json(path: Path, fallback=None):
    if not path.exists():
        return {} if fallback is None else fallback
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def fetch_bytes(url: str, retries: int = 3):
    last_error = None
    for attempt in range(retries):
        request = Request(url, headers={"User-Agent":"MERATUS concession inventory/1"})
        try:
            with urlopen(request, timeout=90) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    try:
        result = subprocess.run([
            "curl","--fail","--silent","--show-error","--location",
            "--connect-timeout","30","--max-time","180","--user-agent",
            "MERATUS concession inventory/1",url
        ], check=True, capture_output=True, timeout=190)
        return result.stdout
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if last_error is not None:
            raise last_error from exc
        raise


def fetch_json(url: str):
    payload = json.loads(fetch_bytes(url).decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}")
    if payload.get("error"):
        raise ValueError(f"ArcGIS error from {url}: {payload['error']}")
    return payload


def layer_url(spec):
    return f"{spec['base']}/{spec['layer']}"


def layer_metadata(spec):
    return fetch_json(layer_url(spec) + "?f=json")


def oid_field(metadata):
    value = metadata.get("objectIdField") or metadata.get("objectIdFieldName")
    if value:
        return str(value)
    for field in metadata.get("fields", []):
        if field.get("type") == "esriFieldTypeOID":
            return field.get("name")
    return None


def fetch_layer_features(spec, metadata=None):
    metadata = metadata or layer_metadata(spec)
    order_field = oid_field(metadata)
    features = []
    offset = 0
    while True:
        params = {
            "where":"1=1",
            "geometry":",".join(str(value) for value in KALIMANTAN_BBOX),
            "geometryType":"esriGeometryEnvelope",
            "inSR":"4326",
            "spatialRel":"esriSpatialRelIntersects",
            "outFields":"*",
            "returnGeometry":"true",
            "outSR":"4326",
            "geometryPrecision":"5",
            "resultOffset":str(offset),
            "resultRecordCount":str(PAGE_SIZE),
            "f":"geojson",
        }
        if order_field:
            params["orderByFields"] = order_field
        payload = fetch_json(layer_url(spec) + "/query?" + urlencode(params))
        page = payload.get("features", [])
        if not isinstance(page, list):
            raise ValueError(f"ArcGIS layer {spec['id']} returned invalid features")
        features.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        if offset > 200000:
            raise ValueError(f"pagination safety limit exceeded for {spec['id']}")
    return features


def all_coordinate_pairs(value: Any) -> Iterable[tuple[float, float]]:
    if not isinstance(value, list):
        return
    if len(value) >= 2 and isinstance(value[0], (int,float)) and isinstance(value[1], (int,float)):
        yield float(value[0]), float(value[1])
        return
    for item in value:
        yield from all_coordinate_pairs(item)


def geometry_in_region(geometry, region_geometry):
    coords = list(all_coordinate_pairs((geometry or {}).get("coordinates")))
    if not coords:
        return False
    for lon, lat in coords:
        if ingest_firms.point_in_geometry(lon, lat, region_geometry):
            return True
    min_lon = min(x for x,_ in coords); max_lon = max(x for x,_ in coords)
    min_lat = min(y for _,y in coords); max_lat = max(y for _,y in coords)
    candidates = (((min_lon+max_lon)/2,(min_lat+max_lat)/2),(min_lon,min_lat),(max_lon,max_lat))
    return any(ingest_firms.point_in_geometry(lon, lat, region_geometry) for lon,lat in candidates)


def perpendicular_distance(point, start, end):
    x,y = point[:2]; x1,y1 = start[:2]; x2,y2 = end[:2]
    if x1 == x2 and y1 == y2:
        return math.hypot(x-x1, y-y1)
    return abs((y2-y1)*x - (x2-x1)*y + x2*y1 - y2*x1) / math.hypot(y2-y1, x2-x1)


def rdp(points, tolerance):
    if len(points) <= 2:
        return points
    max_distance = -1.0; split_index = 0
    for index in range(1, len(points)-1):
        distance = perpendicular_distance(points[index], points[0], points[-1])
        if distance > max_distance:
            max_distance = distance; split_index = index
    if max_distance > tolerance:
        left = rdp(points[:split_index+1], tolerance)
        right = rdp(points[split_index:], tolerance)
        return left[:-1] + right
    return [points[0], points[-1]]


def simplify_ring(ring, tolerance=SIMPLIFY_TOLERANCE):
    if len(ring) < 5:
        return ring
    closed = ring[0][:2] == ring[-1][:2]
    core = ring[:-1] if closed else ring[:]
    simplified = rdp(core + [core[0]], tolerance) if len(core) >= 3 else core
    if simplified and simplified[-1][:2] == simplified[0][:2]:
        simplified = simplified[:-1]
    if len(simplified) < 3:
        simplified = core
    return simplified + [simplified[0]]


def simplify_geometry(geometry):
    if not geometry:
        return geometry
    kind = geometry.get("type"); coords = geometry.get("coordinates")
    if kind == "Polygon":
        return {"type":"Polygon","coordinates":[simplify_ring(ring) for ring in coords or []]}
    if kind == "MultiPolygon":
        return {"type":"MultiPolygon","coordinates":[[simplify_ring(ring) for ring in polygon] for polygon in coords or []]}
    return geometry


def first_nonempty(props, *names):
    for name in names:
        value = props.get(name)
        if value not in (None,""," "):
            return value
    return None


def clean_text(value):
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def as_float(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def arcgis_date(value):
    if value in (None,""):
        return None
    if isinstance(value,(int,float)):
        try:
            return datetime.fromtimestamp(float(value)/1000, tz=timezone.utc).date().isoformat()
        except (OverflowError,OSError,ValueError):
            return clean_text(value)
    return clean_text(value)


def normalize_company_key(value):
    text = (clean_text(value) or "").upper()
    text = re.sub(r"\b(PT|PERSERO|TBK)\b\.?", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def dossier_name_map(path):
    payload = read_json(path,{})
    result = {}
    for dossier in payload.get("dossiers",[]) if isinstance(payload,dict) else []:
        key = normalize_company_key(dossier.get("name")); dossier_id = dossier.get("id")
        if key and dossier_id:
            result[key] = dossier_id
    return result


def source_record_id(props, metadata):
    field = oid_field(metadata); value = props.get(field) if field else None
    if value is None:
        value = first_nonempty(props,"objectid","OBJECTID","objectid_1","OBJECTID_12","id")
    return str(value if value is not None else "unknown")


def base_properties(spec, props, metadata, retrieved_at):
    record_id = source_record_id(props,metadata)
    return {
        "inventoryId":f"{spec['id']}:{record_id}","sector":spec["sector"],"subtype":spec["subtype"],
        "quality":spec["quality"],"sourceDataset":spec["id"],"sourceRecordId":record_id,
        "source":"BIG Kebijakan Satu Peta" if spec["base"] == BIG_BASE else "Global Forest Watch via BNPB InAWARE",
        "sourceUrl":layer_url(spec),"retrievedAt":retrieved_at,
        "geometryProcessing":f"web display simplification tolerance {SIMPLIFY_TOLERANCE} degrees",
    }


def finish_props(out, name, dossiers):
    dossier_id = dossiers.get(normalize_company_key(name))
    if dossier_id:
        out["dossierId"] = dossier_id
    return {k:v for k,v in out.items() if v is not None}


def normalize_forestry(spec, props, metadata, retrieved_at, dossiers):
    out = base_properties(spec,props,metadata,retrieved_at)
    name = clean_text(first_nonempty(props,"namobj","name")) or f"Forestry concession {out['sourceRecordId']}"
    out.update({"name":name,"permitNumber":clean_text(first_nonempty(props,"no_sk","nosk")),
        "permitDate":arcgis_date(first_nonempty(props,"tgl_sk","tglsk")),"areaHa":as_float(first_nonempty(props,"lssk","area_ha")),
        "provinceCode":clean_text(first_nonempty(props,"kdprv","kodeprov")),"sourceRemark":clean_text(first_nonempty(props,"remark"))})
    return finish_props(out,name,dossiers)


def normalize_mining(spec, props, metadata, retrieved_at, dossiers):
    out = base_properties(spec,props,metadata,retrieved_at)
    name = clean_text(first_nonempty(props,"nmoprt","name")) or f"Mining concession {out['sourceRecordId']}"
    out.update({"name":name,"issuer":clean_text(first_nonempty(props,"issuer")),"province":clean_text(first_nonempty(props,"prov")),
        "district":clean_text(first_nonempty(props,"kab")),"permitNumber":clean_text(first_nonempty(props,"skblok")),
        "permitType":clean_text(first_nonempty(props,"tipopr")),"miningType":clean_text(first_nonempty(props,"tiptmb")),
        "commodity":clean_text(first_nonempty(props,"commdt")),"status":clean_text(first_nonempty(props,"status")),
        "validFrom":arcgis_date(first_nonempty(props,"datstr")),"validTo":arcgis_date(first_nonempty(props,"datend")),
        "areaHa":as_float(first_nonempty(props,"lublok")),"location":clean_text(first_nonempty(props,"locate")),
        "sourceRemark":clean_text(first_nonempty(props,"remark"))})
    return finish_props(out,name,dossiers)


def normalize_oil_palm_big(spec, props, metadata, retrieved_at, dossiers):
    out = base_properties(spec,props,metadata,retrieved_at)
    name = clean_text(first_nonempty(props,"nama_prsh","nama_perus","namobj","name")) or f"Oil-palm permit {out['sourceRecordId']}"
    out.update({"name":name,"group":clean_text(first_nonempty(props,"grp_usaha","group_usah")),
        "issuer":clean_text(first_nonempty(props,"penerbit","penerbit_i")),"permitNumber":clean_text(first_nonempty(props,"nmr_sk_il","sk_ilok")),
        "permitDate":arcgis_date(first_nonempty(props,"tgl_sk_il","tgl_ilok")),
        "areaHa":as_float(first_nonempty(props,"luas_sk_il","luassk_ilo","hectares","luas","l")),
        "village":clean_text(first_nonempty(props,"desa")),"subdistrict":clean_text(first_nonempty(props,"kecamatan")),
        "district":clean_text(first_nonempty(props,"kabupaten")),"status":clean_text(first_nonempty(props,"status")),
        "sourceRemark":clean_text(first_nonempty(props,"keterangan","remark")),
        "coverageCaveat":"BIG public plantation layer covers selected districts, not all Kalimantan plantations."})
    return finish_props(out,name,dossiers)


def normalize_oil_palm_gfw(spec, props, metadata, retrieved_at, dossiers):
    out = base_properties(spec,props,metadata,retrieved_at)
    name = clean_text(first_nonempty(props,"company","name")) or f"Oil-palm concession {out['sourceRecordId']}"
    out.update({"name":name,"group":clean_text(first_nonempty(props,"group_comp","subgroup")),"areaHa":as_float(first_nonempty(props,"area_ha")),
        "hguNumber":clean_text(first_nonempty(props,"po_hgu")),"hguAreaHa":as_float(first_nonempty(props,"po_area_hg")),
        "legalStatus":clean_text(first_nonempty(props,"po_legalst","po_legal_1")),"gfwId":clean_text(first_nonempty(props,"gfwid","globalid")),
        "upstreamSource":clean_text(first_nonempty(props,"source")),
        "coverageCaveat":"GFW compilation; source dates and completeness vary and may be older than current permits."})
    return finish_props(out,name,dossiers)

NORMALIZERS = {"forestry":normalize_forestry,"mining":normalize_mining,"oil_palm_big":normalize_oil_palm_big,"oil_palm_gfw":normalize_oil_palm_gfw}


def normalize_features(spec, features, metadata, kalimantan_geometry, retrieved_at, dossiers):
    normalizer = NORMALIZERS[spec["normalizer"]]; output = []
    for feature in features:
        geometry = feature.get("geometry") or {}; props = feature.get("properties") or {}
        if not geometry_in_region(geometry,kalimantan_geometry):
            continue
        output.append({"type":"Feature","properties":normalizer(spec,props,metadata,retrieved_at,dossiers),"geometry":simplify_geometry(geometry)})
    output.sort(key=lambda f:(str(f["properties"].get("name","")).upper(),str(f["properties"].get("inventoryId",""))))
    return output


def load_region_geometry(boundary_path):
    boundary,_ = ingest_firms.load_boundary_geometry(boundary_path)
    return ingest_firms.build_region_geometries(boundary)["kalimantan"]


def previous_output(output_dir, filename):
    path = output_dir / filename
    if not path.exists():
        return None
    try:
        payload = read_json(path)
    except (OSError,json.JSONDecodeError):
        return None
    return payload if isinstance(payload,dict) and payload.get("type") == "FeatureCollection" else None


def source_entry(spec,count,stale=False,error=None):
    entry = {"id":spec["id"],"layerId":spec["layer"],"sector":spec["sector"],"subtype":spec["subtype"],"quality":spec["quality"],"sourceUrl":layer_url(spec),"count":count,"stale":stale}
    if error: entry["error"] = error
    return entry


def run(args):
    output_dir = Path(args.output_dir); retrieved_at = iso_utc(utc_now())
    kalimantan_geometry = load_region_geometry(Path(args.boundary)); dossiers = dossier_name_map(Path(args.dossiers))
    grouped = {}; source_entries = []; optional_errors = []
    try:
        for spec in SOURCE_SPECS:
            try:
                metadata = layer_metadata(spec); raw = fetch_layer_features(spec,metadata)
                normalized = normalize_features(spec,raw,metadata,kalimantan_geometry,retrieved_at,dossiers)
                grouped.setdefault(spec["output"],[]).extend(normalized)
                source_entries.append(source_entry(spec,len(normalized)))
                print(f"{spec['id']}: {len(raw)} bbox features -> {len(normalized)} Kalimantan features")
            except (HTTPError,URLError,TimeoutError,OSError,ValueError,json.JSONDecodeError) as exc:
                if spec["required"]:
                    raise RuntimeError(f"required source {spec['id']} failed: {exc}") from exc
                optional_errors.append(f"{spec['id']}: {exc}")
                previous = previous_output(output_dir,spec["output"]); previous_features = (previous or {}).get("features",[])
                if previous_features and spec["output"] not in grouped:
                    grouped[spec["output"]] = previous_features
                source_entries.append(source_entry(spec,0,True,str(exc)))
        required_outputs = {spec["output"] for spec in SOURCE_SPECS if spec["required"]}
        missing = [name for name in required_outputs if not grouped.get(name)]
        if missing:
            raise RuntimeError("required concession output(s) empty: " + ", ".join(sorted(missing)))
        for filename,features in grouped.items():
            unique = {}
            for feature in features:
                iid = feature.get("properties",{}).get("inventoryId")
                unique[iid or f"anon-{len(unique)}"] = feature
            grouped[filename] = sorted(unique.values(),key=lambda f:(str(f["properties"].get("name","")).upper(),str(f["properties"].get("inventoryId",""))))
        layer_entries = []
        for filename in sorted(grouped):
            features = grouped[filename]
            sectors = sorted({f["properties"].get("sector") for f in features if f["properties"].get("sector")})
            qualities = sorted({f["properties"].get("quality") for f in features if f["properties"].get("quality")})
            write_json_atomic(output_dir/filename,{"type":"FeatureCollection","name":f"meratus-kalimantan-concession-inventory-{filename.removesuffix('.geojson')}",
                "metadata":{"coverageId":"kalimantan","generatedAt":retrieved_at,"pipelineVersion":PIPELINE_VERSION,"count":len(features),"sectors":sectors,"qualities":qualities,
                    "geometryNote":"Web-display geometry is simplified; consult source records for authoritative geometry.",
                    "evidenceNote":"A public concession record does not imply fire causation, illegality, or wrongdoing."},"features":features})
            layer_entries.append({"id":filename.removesuffix(".geojson"),"url":f"data/concessions/kalimantan/inventory/{filename}","count":len(features),"sectors":sectors,"qualities":qualities})
        manifest = {"version":1,"coverageId":"kalimantan","generatedAt":retrieved_at,"pipelineVersion":PIPELINE_VERSION,
            "pipelineStatus":"partial" if optional_errors else "healthy","count":sum(x["count"] for x in layer_entries),"layers":layer_entries,"sources":source_entries,
            "scope":"Public concession/licence inventory for Indonesian Kalimantan. Primary official coverage includes BIG forestry and mining layers; oil-palm coverage combines selected BIG district layers with a GFW compilation.",
            "limitations":["This is not a complete legal cadastre and upstream datasets differ in date and completeness.",
                "BIG public plantation layers cover selected districts rather than all Kalimantan plantation permits.",
                "GFW oil-palm data is supplementary and may be older than current permits.",
                "Geometry is simplified for browser display; use the source URL for authoritative records.",
                "Presence of hotspots within or near a concession is spatial context only, not attribution of fire cause."],
            "optionalErrors":optional_errors}
        write_json_atomic(output_dir/"manifest.json",manifest)
        write_json_atomic(output_dir/"status.json",{"coverageId":"kalimantan","pipelineVersion":PIPELINE_VERSION,"pipelineStatus":manifest["pipelineStatus"],"lastSuccessfulSync":retrieved_at,"count":manifest["count"],"optionalErrors":optional_errors})
        print(json.dumps({"status":manifest["pipelineStatus"],"count":manifest["count"],"layers":layer_entries},ensure_ascii=False))
        return 0
    except Exception as exc:
        write_json_atomic(output_dir/"status.json",{"coverageId":"kalimantan","pipelineVersion":PIPELINE_VERSION,"pipelineStatus":"stale","lastAttemptedSync":retrieved_at,"error":str(exc),"previousDataPreserved":True})
        print(json.dumps({"status":"stale","error":str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",default=str(DEFAULT_OUTPUT_DIR)); parser.add_argument("--boundary",default=str(DEFAULT_BOUNDARY)); parser.add_argument("--dossiers",default=str(DEFAULT_DOSSIERS))
    return parser.parse_args()

if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
