#!/usr/bin/env python3
"""Build region-sharded public concession inventories for MERATUS.

One run fetches each national upstream layer once, normalizes the records, then
partitions polygon components into the seven logical Indonesian regions used by
the hotspot pipeline. The generic inventory stays separate from investigative
dossiers and does not infer fire causation, illegality, political affiliation,
or beneficial ownership beyond explicit source attributes.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from collections import defaultdict
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
INDONESIA_BBOX = ingest_firms.INDONESIA_BBOX
REGION_ORDER = ingest_firms.REGION_ORDER
DEFAULT_BOUNDARY = ROOT / "data" / "kalimantan-indonesia.geojson"
DEFAULT_OUTPUT_ROOT = ROOT / "data" / "concessions"
DEFAULT_CONCESSION_MANIFEST = DEFAULT_OUTPUT_ROOT / "manifest.json"
DEFAULT_DOSSIERS = ROOT / "data" / "dossiers.json"
PAGE_SIZE = 1000
SIMPLIFY_TOLERANCE = 0.00035
PIPELINE_VERSION = "2"
MAX_REGION_SAMPLE_POINTS = 400

SOURCE_SPECS = (
    {"id":"big-forestry-ha","layer":1,"base":BIG_BASE,"output":"forestry-ha.geojson","sector":"PBPH","subtype":"IUPHHK-HA","quality":"OFFICIAL","required":True,"normalizer":"forestry"},
    {"id":"big-forestry-hti","layer":2,"base":BIG_BASE,"output":"forestry-hti.geojson","sector":"PBPH","subtype":"IUPHHK-HTI","quality":"OFFICIAL","required":True,"normalizer":"forestry"},
    {"id":"big-forestry-re","layer":3,"base":BIG_BASE,"output":"forestry-re.geojson","sector":"PBPH","subtype":"IUPHHK-RE","quality":"OFFICIAL","required":True,"normalizer":"forestry"},
    {"id":"big-mining-wiup","layer":4,"base":BIG_BASE,"output":"mining.geojson","sector":"Tambang","subtype":"WIUP","quality":"OFFICIAL","required":True,"normalizer":"mining"},
    {"id":"big-oil-palm-kutai-barat","layer":36,"base":BIG_BASE,"output":"oil-palm-official.geojson","sector":"Sawit","subtype":"Izin Lokasi Sawit","quality":"OFFICIAL","required":False,"normalizer":"oil_palm_big","region_hint":"kalimantan"},
    {"id":"big-oil-palm-kutai-kartanegara","layer":37,"base":BIG_BASE,"output":"oil-palm-official.geojson","sector":"Sawit","subtype":"Izin Lokasi Sawit","quality":"OFFICIAL","required":False,"normalizer":"oil_palm_big","region_hint":"kalimantan"},
    {"id":"big-oil-palm-kutai-timur","layer":38,"base":BIG_BASE,"output":"oil-palm-official.geojson","sector":"Sawit","subtype":"Izin Lokasi Sawit","quality":"OFFICIAL","required":False,"normalizer":"oil_palm_big","region_hint":"kalimantan"},
    {"id":"big-oil-palm-paser","layer":39,"base":BIG_BASE,"output":"oil-palm-official.geojson","sector":"Sawit","subtype":"Izin Lokasi Sawit","quality":"OFFICIAL","required":False,"normalizer":"oil_palm_big","region_hint":"kalimantan"},
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
        request = Request(url, headers={"User-Agent":"MERATUS concession inventory/2"})
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
            "MERATUS concession inventory/2",url
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
    """Fetch one upstream source once for the Indonesia envelope."""
    metadata = metadata or layer_metadata(spec)
    order_field = oid_field(metadata)
    features = []
    offset = 0
    while True:
        params = {
            "where":"1=1",
            "geometry":",".join(str(value) for value in INDONESIA_BBOX),
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
        if offset > 250000:
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


def polygon_parts(geometry):
    if not geometry:
        return []
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "Polygon":
        return [coordinates]
    if kind == "MultiPolygon":
        return list(coordinates)
    return []


def sampled_points(polygon):
    coords = list(all_coordinate_pairs(polygon))
    if len(coords) <= MAX_REGION_SAMPLE_POINTS:
        return coords
    step = max(1, len(coords) // MAX_REGION_SAMPLE_POINTS)
    return coords[::step]


def region_for_polygon(polygon, region_geometries, indonesia_boundary, allow_indonesia_heuristic=False):
    """Assign one polygon component to one logical region.

    Membership against the checked-in country/region polygons wins. For BIG
    national layers, a centroid heuristic is allowed only as a last fallback for
    small islands omitted by the coarse Natural Earth mask. Supplementary GFW
    data does not use that fallback, avoiding neighbouring-country concessions.
    """
    points = sampled_points(polygon)
    if not points:
        return None
    scores = {region: 0 for region in REGION_ORDER}
    for lon, lat in points:
        for region in REGION_ORDER:
            if ingest_firms.point_in_geometry(lon, lat, region_geometries[region]):
                scores[region] += 1
                break
    best_region = max(REGION_ORDER, key=lambda region: scores[region])
    if scores[best_region] > 0:
        return best_region

    min_lon = min(lon for lon,_ in points); max_lon = max(lon for lon,_ in points)
    min_lat = min(lat for _,lat in points); max_lat = max(lat for _,lat in points)
    center_lon = (min_lon + max_lon) / 2
    center_lat = (min_lat + max_lat) / 2
    direct = ingest_firms.region_for_point(center_lon, center_lat, region_geometries)
    if direct:
        return direct
    if ingest_firms.is_indonesia(center_lon, center_lat, indonesia_boundary):
        return ingest_firms.classify_component(center_lon, center_lat)
    if allow_indonesia_heuristic and ingest_firms.in_box(center_lon, center_lat, INDONESIA_BBOX):
        return ingest_firms.classify_component(center_lon, center_lat)
    return None


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
        "coverageCaveat":"BIG public plantation location layer covers selected districts only; it is not complete Indonesia-wide plantation coverage."})
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


def group_geometry_by_region(geometry, region_geometries, indonesia_boundary, allow_indonesia_heuristic=False):
    grouped = defaultdict(list)
    for polygon in polygon_parts(geometry):
        region = region_for_polygon(polygon, region_geometries, indonesia_boundary, allow_indonesia_heuristic)
        if region:
            grouped[region].append(polygon)
    return grouped


def normalize_features_by_region(spec, features, metadata, region_geometries, indonesia_boundary, retrieved_at, dossiers):
    normalizer = NORMALIZERS[spec["normalizer"]]
    output = {region: [] for region in REGION_ORDER}
    unassigned = 0
    for feature in features:
        geometry = feature.get("geometry") or {}
        props = feature.get("properties") or {}
        forced_region = spec.get("region_hint")
        if forced_region:
            polygons = polygon_parts(geometry)
            parts = {forced_region: polygons} if polygons else {}
        else:
            parts = group_geometry_by_region(
                geometry,
                region_geometries,
                indonesia_boundary,
                allow_indonesia_heuristic=(spec["base"] == BIG_BASE),
            )
        if not parts:
            unassigned += 1
            continue
        normalized_props = normalizer(spec,props,metadata,retrieved_at,dossiers)
        base_inventory_id = normalized_props.get("inventoryId")
        multi_region = len(parts) > 1
        for region, polygons in parts.items():
            region_props = dict(normalized_props)
            region_props["region"] = region
            if region != "kalimantan":
                region_props.pop("dossierId", None)
            if multi_region and base_inventory_id:
                region_props["sourceInventoryId"] = base_inventory_id
                region_props["inventoryId"] = f"{base_inventory_id}:{region}"
            region_geometry = (
                {"type":"Polygon","coordinates":polygons[0]}
                if len(polygons) == 1
                else {"type":"MultiPolygon","coordinates":polygons}
            )
            output[region].append({"type":"Feature","properties":region_props,"geometry":simplify_geometry(region_geometry)})
    for region in REGION_ORDER:
        output[region].sort(key=lambda f:(str(f["properties"].get("name","")).upper(),str(f["properties"].get("inventoryId",""))))
    return output, unassigned


def load_region_geometries(boundary_path):
    boundary,_ = ingest_firms.load_boundary_geometry(boundary_path)
    return boundary, ingest_firms.build_region_geometries(boundary)


def inventory_dir(output_root, region):
    return output_root / region / "inventory"


def previous_source_features(output_root, region, filename, source_id):
    path = inventory_dir(output_root,region) / filename
    if not path.exists():
        return []
    try:
        payload = read_json(path)
    except (OSError,json.JSONDecodeError):
        return []
    if not isinstance(payload,dict) or payload.get("type") != "FeatureCollection":
        return []
    return [
        feature for feature in payload.get("features",[])
        if (feature.get("properties") or {}).get("sourceDataset") == source_id
    ]


def source_entry(spec,count,region_counts,stale=False,error=None,unassigned=0):
    entry = {
        "id":spec["id"],"layerId":spec["layer"],"sector":spec["sector"],"subtype":spec["subtype"],
        "quality":spec["quality"],"sourceUrl":layer_url(spec),"count":count,
        "regions":region_counts,"unassigned":unassigned,"stale":stale,
    }
    if error:
        entry["error"] = error
    return entry


def dedupe_features(features):
    unique = {}
    for feature in features:
        iid = (feature.get("properties") or {}).get("inventoryId")
        unique[iid or f"anon-{len(unique)}"] = feature
    return sorted(unique.values(),key=lambda f:(str(f["properties"].get("name","")).upper(),str(f["properties"].get("inventoryId",""))))


def write_region_inventory(output_root, region, grouped, source_entries, retrieved_at, optional_errors):
    region_dir = inventory_dir(output_root,region)
    layer_entries = []
    known_outputs = sorted({spec["output"] for spec in SOURCE_SPECS})
    for filename in known_outputs:
        features = dedupe_features(grouped.get(filename,[]))
        path = region_dir / filename
        if not features:
            if path.exists():
                path.unlink()
            continue
        sectors = sorted({f["properties"].get("sector") for f in features if f["properties"].get("sector")})
        qualities = sorted({f["properties"].get("quality") for f in features if f["properties"].get("quality")})
        write_json_atomic(path,{
            "type":"FeatureCollection",
            "name":f"meratus-{region}-concession-inventory-{filename.removesuffix('.geojson')}",
            "metadata":{
                "coverageId":region,"parentCoverageId":"indonesia","generatedAt":retrieved_at,
                "pipelineVersion":PIPELINE_VERSION,"count":len(features),"sectors":sectors,"qualities":qualities,
                "geometryNote":"Web-display geometry is simplified; consult source records for authoritative geometry.",
                "evidenceNote":"A public concession record does not imply fire causation, illegality, or wrongdoing.",
            },
            "features":features,
        })
        layer_entries.append({
            "id":filename.removesuffix(".geojson"),
            "url":f"data/concessions/{region}/inventory/{filename}",
            "count":len(features),"sectors":sectors,"qualities":qualities,
        })
    region_sources = []
    for entry in source_entries:
        copy = dict(entry)
        copy["count"] = entry.get("regions",{}).get(region,0)
        copy.pop("regions",None)
        region_sources.append(copy)
    count = sum(entry["count"] for entry in layer_entries)
    manifest = {
        "version":2,"coverageId":region,"parentCoverageId":"indonesia","generatedAt":retrieved_at,
        "pipelineVersion":PIPELINE_VERSION,"pipelineStatus":"partial" if optional_errors else "healthy",
        "count":count,"layers":layer_entries,"sources":region_sources,
        "scope":f"Public concession/licence inventory for the MERATUS logical region '{region}', generated from one Indonesia-wide upstream fetch per source.",
        "limitations":[
            "This is not a complete legal cadastre and upstream datasets differ in date and completeness.",
            "BIG forestry and mining layers are the official national baseline used here.",
            "BIG public plantation-location layers currently cover selected districts rather than all Indonesia plantation permits.",
            "GFW oil-palm data is supplementary and may be older than current permits.",
            "The checked-in Natural Earth country mask is coarse and may omit very small islands.",
            "Geometry is simplified for browser display; use the source URL for authoritative records.",
            "Presence of hotspots within or near a concession is spatial context only, not attribution of fire cause.",
        ],
        "optionalErrors":optional_errors,
    }
    write_json_atomic(region_dir/"manifest.json",manifest)
    write_json_atomic(region_dir/"status.json",{
        "coverageId":region,"parentCoverageId":"indonesia","pipelineVersion":PIPELINE_VERSION,
        "pipelineStatus":manifest["pipelineStatus"],"lastSuccessfulSync":retrieved_at,
        "count":count,"optionalErrors":optional_errors,
    })
    return manifest


def update_concession_manifest(path, region_manifests):
    payload = read_json(path,{"version":3,"coverageId":"indonesia","regions":{}})
    if not isinstance(payload,dict):
        payload = {"version":3,"coverageId":"indonesia","regions":{}}
    payload["version"] = max(3,int(payload.get("version") or 0))
    payload["coverageId"] = "indonesia"
    regions = payload.setdefault("regions",{})
    for region in REGION_ORDER:
        entry = regions.setdefault(region,{"available":False,"dossiers":None,"boundaries":None})
        entry["inventory"] = f"data/concessions/{region}/inventory/manifest.json"
        entry["inventoryAvailable"] = bool(region_manifests[region]["count"])
        entry["inventoryCount"] = region_manifests[region]["count"]
    write_json_atomic(path,payload)
    return payload


def run(args):
    output_root = Path(args.output_root)
    retrieved_at = iso_utc(utc_now())
    status_path = output_root / "inventory-status.json"
    try:
        indonesia_boundary, region_geometries = load_region_geometries(Path(args.boundary))
        dossiers = dossier_name_map(Path(args.dossiers))
        grouped = {region: defaultdict(list) for region in REGION_ORDER}
        source_entries = []
        optional_errors = []

        for spec in SOURCE_SPECS:
            try:
                metadata = layer_metadata(spec)
                raw = fetch_layer_features(spec,metadata)
                by_region, unassigned = normalize_features_by_region(
                    spec,raw,metadata,region_geometries,indonesia_boundary,retrieved_at,dossiers
                )
                region_counts = {}
                total = 0
                for region in REGION_ORDER:
                    features = by_region[region]
                    grouped[region][spec["output"]].extend(features)
                    region_counts[region] = len(features)
                    total += len(features)
                if spec["required"] and total == 0:
                    raise ValueError("required national source produced zero Indonesia region records")
                source_entries.append(source_entry(spec,total,region_counts,unassigned=unassigned))
                print(
                    f"{spec['id']}: {len(raw)} Indonesia-bbox features -> {total} region records; "
                    f"unassigned={unassigned}; regions={json.dumps(region_counts, ensure_ascii=False, sort_keys=True)}"
                )
            except (HTTPError,URLError,TimeoutError,OSError,ValueError,json.JSONDecodeError) as exc:
                if spec["required"]:
                    raise RuntimeError(f"required source {spec['id']} failed: {exc}") from exc
                error_text = f"{spec['id']}: {exc}"
                optional_errors.append(error_text)
                region_counts = {}
                carried = 0
                for region in REGION_ORDER:
                    previous = previous_source_features(output_root,region,spec["output"],spec["id"])
                    grouped[region][spec["output"]].extend(previous)
                    region_counts[region] = len(previous)
                    carried += len(previous)
                source_entries.append(source_entry(spec,carried,region_counts,True,str(exc)))
                print(f"optional source stale: {error_text}; preserved={carried}",file=sys.stderr)

        required_source_ids = {spec["id"] for spec in SOURCE_SPECS if spec["required"]}
        successful_required = {
            entry["id"] for entry in source_entries
            if entry["id"] in required_source_ids and not entry.get("stale") and entry.get("count",0) > 0
        }
        missing_required = sorted(required_source_ids - successful_required)
        if missing_required:
            raise RuntimeError("required national concession source(s) unavailable: " + ", ".join(missing_required))

        region_manifests = {}
        for region in REGION_ORDER:
            region_manifests[region] = write_region_inventory(
                output_root,region,grouped[region],source_entries,retrieved_at,optional_errors
            )

        update_concession_manifest(Path(args.concession_manifest),region_manifests)
        region_counts = {region:region_manifests[region]["count"] for region in REGION_ORDER}
        total_count = sum(region_counts.values())
        national_manifest = {
            "version":1,"coverageId":"indonesia","generatedAt":retrieved_at,
            "pipelineVersion":PIPELINE_VERSION,"pipelineStatus":"partial" if optional_errors else "healthy",
            "count":total_count,"regions":{
                region:{
                    "count":region_manifests[region]["count"],
                    "manifest":f"data/concessions/{region}/inventory/manifest.json",
                    "layers":region_manifests[region]["layers"],
                } for region in REGION_ORDER
            },
            "sources":source_entries,
            "optionalErrors":optional_errors,
            "scope":"Indonesia public concession/licence inventory. Each upstream source is fetched once per run and then sharded into the seven MERATUS logical regions.",
            "limitations":[
                "This is not a complete legal cadastre.",
                "Official BIG forestry and mining layers are national; public BIG plantation-location coverage is incomplete.",
                "GFW oil-palm data is supplementary and may be older than current permits.",
                "Very small islands may be omitted by the coarse checked-in country mask.",
            ],
        }
        write_json_atomic(output_root/"inventory-manifest.json",national_manifest)
        write_json_atomic(status_path,{
            "coverageId":"indonesia","pipelineVersion":PIPELINE_VERSION,
            "pipelineStatus":national_manifest["pipelineStatus"],"lastSuccessfulSync":retrieved_at,
            "count":total_count,"regionCounts":region_counts,"optionalErrors":optional_errors,
        })
        print(json.dumps({
            "status":national_manifest["pipelineStatus"],"count":total_count,
            "regions":region_counts,
            "sources":{entry["id"]:entry["count"] for entry in source_entries},
        },ensure_ascii=False))
        return 0
    except Exception as exc:
        write_json_atomic(status_path,{
            "coverageId":"indonesia","pipelineVersion":PIPELINE_VERSION,
            "pipelineStatus":"stale","lastAttemptedSync":retrieved_at,
            "error":str(exc),"previousDataPreserved":True,
        })
        print(json.dumps({"status":"stale","error":str(exc),"previousDataPreserved":True},ensure_ascii=False),file=sys.stderr)
        return 2


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root",default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--concession-manifest",default=str(DEFAULT_CONCESSION_MANIFEST))
    parser.add_argument("--boundary",default=str(DEFAULT_BOUNDARY))
    parser.add_argument("--dossiers",default=str(DEFAULT_DOSSIERS))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
