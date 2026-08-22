#!/usr/bin/env python3
"""Fetch, validate, normalize, and publish the MERATUS FIRMS dataset.

The script is deliberately dependency-free so it can run in GitHub Actions.
It fails closed: a failed or suspicious fetch updates only firms-status.json
and leaves the last known-good firms.json untouched.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_ROOT = "https://firms.modaps.eosdis.nasa.gov/api/area/"
AREA = "108.8,-4.5,119.3,4.4"
SOURCES = (
    ("VIIRS_SNPP_NRT", "S-NPP"),
    ("VIIRS_NOAA20_NRT", "NOAA-20"),
    ("VIIRS_NOAA21_NRT", "NOAA-21"),
)

# These are conservative filters for the static GitHub Pages pipeline. The
# country polygon is kept as a checked-in data artifact so a scheduled run
# does not depend on a second live boundary request.
KALIMANTAN_BBOX = (108.8, -4.5, 119.3, 4.4)
DEFAULT_BOUNDARY = Path(__file__).resolve().parent.parent / "data" / "kalimantan-indonesia.geojson"
EXPECTED_PLATFORMS = frozenset(platform for _, platform in SOURCES)
MIN_TOTAL_RETENTION = 0.25
MIN_SOURCE_RETENTION = 0.50
MAX_SOURCE_OBSERVATION_AGE_HOURS = 72


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, separators=(",", ":"))
        tmp.write("\n")
        temp_name = tmp.name
    Path(temp_name).replace(path)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def fetch_csv(url: str) -> list[dict[str, str]]:
    request = Request(url, headers={"User-Agent": "MERATUS FIRMS pipeline/2"})
    with urlopen(request, timeout=90) as response:
        body = response.read()
    text = body.decode("utf-8-sig")
    if not text.strip() or text.lstrip().startswith("<"):
        raise ValueError("FIRMS returned an empty or non-CSV response")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "latitude" not in reader.fieldnames or "longitude" not in reader.fieldnames:
        raise ValueError("FIRMS response is missing latitude/longitude columns")
    return list(reader)


def as_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key)
    if value in (None, "", "null", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_confidence(value: str | None) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"h", "high"}:
        return "high"
    if raw in {"l", "low"}:
        return "low"
    return "nominal"


def normalize_platform(value: str | None, fallback: str) -> str:
    raw = str(value or "").strip().upper().replace("_", "-")
    if raw in {"N", "SNPP", "S-NPP"}:
        return "S-NPP"
    if raw in {"N20", "NOAA20", "NOAA-20"}:
        return "NOAA-20"
    if raw in {"N21", "NOAA21", "NOAA-21"}:
        return "NOAA-21"
    return fallback


def in_box(lon: float, lat: float, box: tuple[float, float, float, float]) -> bool:
    west, south, east, north = box
    return west <= lon <= east and south <= lat <= north


def point_on_segment(lon: float, lat: float, start: list[float], end: list[float]) -> bool:
    x1, y1 = start
    x2, y2 = end
    cross = (lon - x1) * (y2 - y1) - (lat - y1) * (x2 - x1)
    if abs(cross) > 1e-9:
        return False
    return min(x1, x2) - 1e-9 <= lon <= max(x1, x2) + 1e-9 and min(y1, y2) - 1e-9 <= lat <= max(y1, y2) + 1e-9


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    for index, current in enumerate(ring):
        previous = ring[index - 1]
        if point_on_segment(lon, lat, previous, current):
            return True
        x1, y1 = previous
        x2, y2 = current
        if (y1 > lat) != (y2 > lat):
            crossing_lon = (x2 - x1) * (lat - y1) / (y2 - y1) + x1
            if lon < crossing_lon:
                inside = not inside
    return inside


def point_in_polygon(lon: float, lat: float, polygon: list[list[list[float]]]) -> bool:
    if not polygon or not point_in_ring(lon, lat, polygon[0]):
        return False
    return not any(point_in_ring(lon, lat, hole) for hole in polygon[1:])


def point_in_geometry(lon: float, lat: float, geometry: dict) -> bool:
    if not geometry:
        return False
    if geometry.get("type") == "Polygon":
        return point_in_polygon(lon, lat, geometry.get("coordinates", []))
    if geometry.get("type") == "MultiPolygon":
        return any(point_in_polygon(lon, lat, polygon) for polygon in geometry.get("coordinates", []))
    return False


def load_boundary_geometry(path: Path) -> tuple[dict, dict]:
    payload = load_json(path)
    features = payload.get("features", []) if isinstance(payload, dict) else []
    geometries = [feature.get("geometry") for feature in features if feature.get("geometry")]
    if not geometries:
        raise ValueError(f"boundary filter has no geometry: {path}")
    metadata = payload.get("metadata", {}) if isinstance(payload, dict) else {}
    return {"type": "GeometryCollection", "geometries": geometries}, metadata


def is_kalimantan_indonesia(lon: float, lat: float, boundary_geometry: dict) -> bool:
    if not in_box(lon, lat, KALIMANTAN_BBOX):
        return False
    return any(point_in_geometry(lon, lat, geometry) for geometry in boundary_geometry.get("geometries", []))


def observation_id(platform: str, date: str, time: str, lat: float, lon: float) -> str:
    return f"{platform}|{date}|{time.zfill(4)}|{lat:.5f}|{lon:.5f}"


def normalize_row(row: dict[str, str], fallback_platform: str, boundary_geometry: dict) -> dict | None:
    lat = as_float(row, "latitude")
    lon = as_float(row, "longitude")
    date = str(row.get("acq_date") or "").strip()
    time = str(row.get("acq_time") or "").strip().zfill(4)
    if lat is None or lon is None or not date or not is_kalimantan_indonesia(lon, lat, boundary_geometry):
        return None

    platform = normalize_platform(row.get("satellite"), fallback_platform)
    point = {
        "observationId": observation_id(platform, date, time, lat, lon),
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "b4": as_float(row, "bright_ti4"),
        "b5": as_float(row, "bright_ti5"),
        "frp": as_float(row, "frp"),
        "date": date,
        "time": time,
        "sat": str(row.get("satellite") or platform),
        "platform": platform,
        "conf": normalize_confidence(row.get("confidence")),
        "confidenceRaw": row.get("confidence"),
        "dn": str(row.get("daynight") or "").strip() or None,
        "scan": as_float(row, "scan"),
        "track": as_float(row, "track"),
        "version": row.get("version"),
    }
    return {key: value for key, value in point.items() if value is not None}


def detection_datetime(point: dict) -> datetime | None:
    try:
        return datetime.strptime(
            f"{point['date']} {str(point.get('time', '0000')).zfill(4)}", "%Y-%m-%d %H%M"
        ).replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None


def source_observation_summary(points: list[dict]) -> dict[str, dict]:
    summary: dict[str, dict] = {}
    for point in points:
        platform = point.get("platform")
        acquired = detection_datetime(point)
        if not platform or not acquired:
            continue
        entry = summary.setdefault(platform, {"count": 0, "newest": acquired, "oldest": acquired})
        entry["count"] += 1
        entry["newest"] = max(entry["newest"], acquired)
        entry["oldest"] = min(entry["oldest"], acquired)
    return summary


def validate(
    points: list[dict],
    previous_meta: dict,
    source_summary: dict[str, dict],
    boundary_geometry: dict,
    now: datetime,
) -> None:
    if not points:
        raise ValueError("validation rejected an empty Kalimantan dataset")
    previous_count = previous_meta.get("count")
    if previous_count and previous_count >= 100 and len(points) < max(100, int(previous_count * MIN_TOTAL_RETENTION)):
        raise ValueError(
            f"validation rejected suspicious aggregate count drop: {len(points)} vs previous {previous_count}"
        )
    missing_sources = sorted(EXPECTED_PLATFORMS - set(source_summary))
    if missing_sources:
        raise ValueError(f"validation rejected missing or empty satellite source(s): {', '.join(missing_sources)}")
    previous_source_counts = previous_meta.get("sourceCounts") or {}
    if isinstance(previous_source_counts, dict):
        for platform in EXPECTED_PLATFORMS:
            previous_count = previous_source_counts.get(platform)
            current_count = source_summary[platform]["count"]
            if previous_count and current_count < max(10, int(previous_count * MIN_SOURCE_RETENTION)):
                raise ValueError(
                    f"validation rejected suspicious {platform} count drop: {current_count} vs previous {previous_count}"
                )
    for platform, entry in source_summary.items():
        age_hours = (now - entry["newest"]).total_seconds() / 3600
        if age_hours > MAX_SOURCE_OBSERVATION_AGE_HOURS:
            raise ValueError(
                f"validation rejected stale {platform} observations: newest is {age_hours:.1f} hours old"
            )
    for point in points:
        lat, lon = point.get("lat"), point.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise ValueError("validation found a non-numeric coordinate")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("validation found an out-of-range coordinate")
        if not is_kalimantan_indonesia(lon, lat, boundary_geometry):
            raise ValueError("validation found a point outside the Kalimantan Indonesia filter")
        if point.get("platform") not in EXPECTED_PLATFORMS:
            raise ValueError(f"validation found an unknown platform: {point.get('platform')}")
        if detection_datetime(point) is None:
            raise ValueError("validation found an invalid acquisition timestamp")


def status_payload(previous_meta: dict, error: str) -> dict:
    return {
        "pipelineVersion": "3",
        "lastAttemptedSync": iso_utc(utc_now()),
        "lastSuccessfulSync": previous_meta.get("lastSuccessfulSync"),
        "pipelineStatus": "stale",
        "stale": True,
        "error": error,
        "previousDataPreserved": True,
    }


def healthy_status_payload(meta: dict) -> dict:
    return {
        "pipelineVersion": meta.get("pipelineVersion", "3"),
        "lastAttemptedSync": meta.get("lastSuccessfulSync"),
        "lastSuccessfulSync": meta.get("lastSuccessfulSync"),
        "pipelineStatus": "healthy",
        "stale": False,
        "previousDataPreserved": False,
    }


def run(args: argparse.Namespace) -> int:
    output_path = Path(args.output)
    status_path = Path(args.status)
    archive_dir = Path(args.archive_dir)
    boundary_path = Path(args.boundary)
    previous_payload = load_json(output_path)
    previous_meta = previous_payload.get("meta", {}) if isinstance(previous_payload, dict) else {}
    map_key = args.map_key or os.environ.get("FIRMS_MAP_KEY", "").strip()

    try:
        if not map_key:
            raise ValueError("FIRMS_MAP_KEY is not configured")
        boundary_geometry, boundary_metadata = load_boundary_geometry(boundary_path)

        all_points: list[dict] = []
        source_urls: dict[str, str] = {}
        for source, platform in SOURCES:
            url = f"{API_ROOT}csv/{map_key}/{source}/{AREA}/5"
            source_urls[platform] = API_ROOT
            rows = fetch_csv(url)
            if not rows:
                raise ValueError(f"FIRMS returned no records for {platform}")
            normalized = [point for row in rows if (point := normalize_row(row, platform, boundary_geometry)) is not None]
            if not normalized:
                raise ValueError(f"FIRMS returned no Kalimantan records for {platform}")
            all_points.extend(normalized)

        unique: dict[str, dict] = {}
        for point in all_points:
            unique.setdefault(point["observationId"], point)
        points = sorted(unique.values(), key=lambda point: (point["date"], point["time"], point["platform"], point["lat"], point["lon"]))
        now = utc_now()
        source_summary = source_observation_summary(points)
        validate(points, previous_meta, source_summary, boundary_geometry, now)

        acquired = [value for point in points if (value := detection_datetime(point)) is not None]
        source_observations = {
            platform: {
                "count": entry["count"],
                "newestDetectionUtc": iso_utc(entry["newest"]),
                "oldestDetectionUtc": iso_utc(entry["oldest"]),
            }
            for platform, entry in source_summary.items()
        }
        meta = {
            "source": "NASA FIRMS NRT VIIRS",
            "url": API_ROOT,
            "platforms": [platform for _, platform in SOURCES],
            "fetched": now.date().isoformat(),
            "lastSuccessfulSync": iso_utc(now),
            "newestDetectionUtc": iso_utc(max(acquired)),
            "oldestDetectionUtc": iso_utc(min(acquired)),
            "filter": "Kalimantan Indonesia broad bbox + Natural Earth Indonesia country polygon point-in-polygon",
            "filterBoundary": boundary_metadata,
            "area": AREA,
            "sourceCounts": {platform: entry["count"] for platform, entry in source_summary.items()},
            "sourceObservations": source_observations,
            "count": len(points),
            "pipelineVersion": "3",
            "pipelineStatus": "healthy",
            "stale": False,
        }
        payload = {"meta": meta, "points": points}
        archive_path = archive_dir / now.strftime("%Y") / now.strftime("%m") / f"{now.strftime('%d')}.json"
        write_json_atomic(archive_path, payload)
        # Publish the validated dataset only after the archive has been staged.
        # The status write comes last so a fetch/archive failure cannot mark a
        # still-old dataset as healthy.
        write_json_atomic(output_path, payload)
        write_json_atomic(status_path, healthy_status_payload(meta))
        print(json.dumps({"status": "healthy", "count": len(points), "sources": source_urls}, ensure_ascii=False))
        return 0
    except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
        status = status_payload(previous_meta, str(exc))
        write_json_atomic(status_path, status)
        print(json.dumps({"status": "stale", "error": str(exc), "previousDataPreserved": True}, ensure_ascii=False), file=sys.stderr)
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-key", help="NASA FIRMS MAP_KEY; otherwise FIRMS_MAP_KEY")
    parser.add_argument("--output", default="data/firms.json")
    parser.add_argument("--status", default="data/firms-status.json")
    parser.add_argument("--archive-dir", default="archive/firms")
    parser.add_argument("--boundary", default=str(DEFAULT_BOUNDARY))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
