#!/usr/bin/env python3
"""Bootstrap the sharded hotspot contract from legacy Kalimantan data.

This is only a deployment bridge for the first Pages deploy after the region-aware
frontend lands. Once the scheduled Indonesia FIRMS ingest has written
``data/hotspots/manifest.json``, this script is a no-op.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "data" / "firms.json"
REGIONS = ROOT / "data" / "regions.json"
SHARD_ROOT = ROOT / "data" / "hotspots"
MANIFEST = SHARD_ROOT / "manifest.json"
STATUS = SHARD_ROOT / "status.json"


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def build() -> tuple[dict, dict, dict[str, dict]]:
    legacy = load(LEGACY)
    regions_payload = load(REGIONS)
    points = legacy.get("points", []) if isinstance(legacy, dict) else []
    meta = legacy.get("meta", {}) if isinstance(legacy, dict) else {}
    if not points:
        raise RuntimeError("legacy FIRMS dataset is empty; cannot bootstrap hotspot shards")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for raw in points:
        point = dict(raw)
        point["region"] = "kalimantan"
        if not point.get("date"):
            raise RuntimeError("legacy FIRMS point is missing date")
        grouped[point["date"]].append(point)

    shards: dict[str, dict] = {}
    day_entries = []
    total = 0
    for date in sorted(grouped, reverse=True):
        day_points = sorted(
            grouped[date],
            key=lambda point: (
                str(point.get("time", "")),
                str(point.get("platform", point.get("sat", ""))),
                point.get("lat", 0),
                point.get("lon", 0),
            ),
        )
        payload = {
            "meta": {
                "coverageId": "kalimantan-bootstrap",
                "region": "kalimantan",
                "date": date,
                "count": len(day_points),
                "lastSuccessfulSync": meta.get("lastSuccessfulSync") or meta.get("fetched"),
                "pipelineVersion": "4-bootstrap",
                "bootstrap": True,
            },
            "points": day_points,
        }
        shards[date] = payload
        day_entries.append(
            {
                "date": date,
                "url": f"data/hotspots/kalimantan/{date}.json",
                "count": len(day_points),
            }
        )
        total += len(day_points)

    region_manifest = {}
    for region in regions_payload.get("regions", []):
        region_id = region["id"]
        region_manifest[region_id] = {
            "label": region["label"],
            "count": total if region_id == "kalimantan" else 0,
            "days": day_entries if region_id == "kalimantan" else [],
        }

    manifest = {
        "meta": {
            "coverageId": "kalimantan-bootstrap",
            "lastSuccessfulSync": meta.get("lastSuccessfulSync") or meta.get("fetched"),
            "newestDetectionUtc": meta.get("newestDetectionUtc"),
            "oldestDetectionUtc": meta.get("oldestDetectionUtc"),
            "platforms": meta.get("platforms", []),
            "count": total,
            "pipelineVersion": "4-bootstrap",
            "bootstrap": True,
        },
        "regions": region_manifest,
    }
    status = {
        "coverageId": "kalimantan-bootstrap",
        "pipelineVersion": "4-bootstrap",
        "lastAttemptedSync": meta.get("lastSuccessfulSync") or meta.get("fetched"),
        "lastSuccessfulSync": meta.get("lastSuccessfulSync") or meta.get("fetched"),
        "newestDetectionUtc": meta.get("newestDetectionUtc"),
        "totalPoints": total,
        "pipelineStatus": "bootstrap",
        "stale": bool(meta.get("stale", False)),
        "bootstrap": True,
        "previousDataPreserved": True,
    }
    return manifest, status, shards


def validate(manifest: dict, shards: dict[str, dict]) -> None:
    regions = manifest.get("regions", {})
    expected = {"sumatra", "jawa", "kalimantan", "sulawesi", "bali-nusra", "maluku", "papua"}
    if set(regions) != expected:
        raise RuntimeError("bootstrap manifest region set is incomplete")
    if not regions["kalimantan"]["days"]:
        raise RuntimeError("bootstrap manifest has no Kalimantan days")
    if not shards:
        raise RuntimeError("bootstrap generated no daily shards")
    manifest_count = regions["kalimantan"]["count"]
    shard_count = sum(payload["meta"]["count"] for payload in shards.values())
    if manifest_count != shard_count:
        raise RuntimeError(f"bootstrap count mismatch: {manifest_count} != {shard_count}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if MANIFEST.exists() and not args.force:
        print("hotspot shard manifest already exists; bootstrap skipped")
        return

    manifest, status, shards = build()
    validate(manifest, shards)
    if args.check:
        print("hotspot shard bootstrap: OK")
        return

    for date, payload in shards.items():
        write(SHARD_ROOT / "kalimantan" / f"{date}.json", payload)
    write(MANIFEST, manifest)
    write(STATUS, status)
    print(f"bootstrapped hotspot shards from legacy Kalimantan data: {manifest['meta']['count']} points")


if __name__ == "__main__":
    main()
