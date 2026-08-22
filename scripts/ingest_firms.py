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

# These are conservative filters for the static GitHub Pages pipeline. They
# retain the existing project's broad Kalimantan scope and remove the coarse
# Sarawak/Sabah envelopes. A future polygon clip can replace these constants.
KALIMANTAN_BBOX = (108.8, -4.5, 119.3, 4.4)
MALAYSIA_EXCLUSION_BOXES = (
    (109.4, 0.8, 115.5, 5.0),  # Sarawak, coarse envelope
    (115.5, 4.0, 119.3, 7.5),  # Sabah, coarse envelope
)


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


def is_kalimantan_indonesia(lon: float, lat: float) -> bool:
    if not in_box(lon, lat, KALIMANTAN_BBOX):
        return False
    return not any(in_box(lon, lat, box) for box in MALAYSIA_EXCLUSION_BOXES)


def observation_id(platform: str, date: str, time: str, lat: float, lon: float) -> str:
    return f"{platform}|{date}|{time.zfill(4)}|{lat:.5f}|{lon:.5f}"


def normalize_row(row: dict[str, str], fallback_platform: str) -> dict | None:
    lat = as_float(row, "latitude")
    lon = as_float(row, "longitude")
    date = str(row.get("acq_date") or "").strip()
    time = str(row.get("acq_time") or "").strip().zfill(4)
    if lat is None or lon is None or not date or not is_kalimantan_indonesia(lon, lat):
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


def validate(points: list[dict], previous_count: int | None) -> None:
    if not points:
        raise ValueError("validation rejected an empty Kalimantan dataset")
    if previous_count and previous_count >= 100 and len(points) < max(10, int(previous_count * 0.05)):
        raise ValueError(
            f"validation rejected suspicious count drop: {len(points)} vs previous {previous_count}"
        )
    for point in points:
        lat, lon = point.get("lat"), point.get("lon")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise ValueError("validation found a non-numeric coordinate")
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("validation found an out-of-range coordinate")
        if not is_kalimantan_indonesia(lon, lat):
            raise ValueError("validation found a point outside the Kalimantan Indonesia filter")
        if point.get("platform") not in {platform for _, platform in SOURCES}:
            raise ValueError(f"validation found an unknown platform: {point.get('platform')}")
        if detection_datetime(point) is None:
            raise ValueError("validation found an invalid acquisition timestamp")


def status_payload(previous_meta: dict, error: str) -> dict:
    return {
        "source": "NASA FIRMS NRT",
        "platforms": [platform for _, platform in SOURCES],
        "lastSuccessfulSync": previous_meta.get("lastSuccessfulSync"),
        "newestDetectionUtc": previous_meta.get("newestDetectionUtc"),
        "oldestDetectionUtc": previous_meta.get("oldestDetectionUtc"),
        "count": previous_meta.get("count"),
        "pipelineVersion": "2",
        "pipelineStatus": "stale",
        "stale": True,
        "error": error,
        "previousDataPreserved": True,
    }


def run(args: argparse.Namespace) -> int:
    output_path = Path(args.output)
    status_path = Path(args.status)
    archive_dir = Path(args.archive_dir)
    previous_payload = load_json(output_path)
    previous_meta = previous_payload.get("meta", {}) if isinstance(previous_payload, dict) else {}
    map_key = args.map_key or os.environ.get("FIRMS_MAP_KEY", "").strip()

    try:
        if not map_key:
            raise ValueError("FIRMS_MAP_KEY is not configured")

        all_points: list[dict] = []
        source_counts: dict[str, int] = {}
        source_urls: dict[str, str] = {}
        for source, platform in SOURCES:
            url = f"{API_ROOT}csv/{map_key}/{source}/{AREA}/5"
            source_urls[platform] = API_ROOT
            rows = fetch_csv(url)
            normalized = [point for row in rows if (point := normalize_row(row, platform)) is not None]
            source_counts[platform] = len(normalized)
            all_points.extend(normalized)

        unique: dict[str, dict] = {}
        for point in all_points:
            unique.setdefault(point["observationId"], point)
        points = sorted(unique.values(), key=lambda point: (point["date"], point["time"], point["platform"], point["lat"], point["lon"]))
        previous_count = previous_meta.get("count")
        validate(points, int(previous_count) if previous_count is not None else None)

        acquired = [value for point in points if (value := detection_datetime(point)) is not None]
        now = utc_now()
        meta = {
            "source": "NASA FIRMS NRT VIIRS",
            "url": API_ROOT,
            "platforms": [platform for _, platform in SOURCES],
            "fetched": now.date().isoformat(),
            "lastSuccessfulSync": iso_utc(now),
            "newestDetectionUtc": iso_utc(max(acquired)),
            "oldestDetectionUtc": iso_utc(min(acquired)),
            "filter": "Kalimantan Indonesia broad bbox; coarse Sarawak/Sabah exclusion boxes",
            "area": AREA,
            "sourceCounts": source_counts,
            "count": len(points),
            "pipelineVersion": "2",
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
        write_json_atomic(status_path, meta)
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
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
