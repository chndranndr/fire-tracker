import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ingest_firms", ROOT / "scripts" / "ingest_firms.py")
ingest_firms = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ingest_firms)


BOUNDARY = {
    "type": "GeometryCollection",
    "geometries": [
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [109.0, -1.0],
                    [111.0, -1.0],
                    [111.0, 1.0],
                    [109.0, 1.0],
                    [109.0, -1.0],
                ]
            ],
        }
    ],
}

REGION_GEOMETRIES = {
    region: {"type": "MultiPolygon", "coordinates": []}
    for region in ingest_firms.REGION_ORDER
}
REGION_GEOMETRIES["kalimantan"] = {
    "type": "MultiPolygon",
    "coordinates": [
        [
            [
                [109.0, -1.0],
                [111.0, -1.0],
                [111.0, 1.0],
                [109.0, 1.0],
                [109.0, -1.0],
            ]
        ]
    ],
}


def point(platform: str) -> dict:
    return {
        "observationId": f"{platform}|2026-08-22|0900|0.50000|110.00000",
        "lat": 0.5,
        "lon": 110.0,
        "date": "2026-08-22",
        "time": "0900",
        "platform": platform,
        "conf": "nominal",
    }


class IngestFirmsTests(unittest.TestCase):
    def test_boundary_filter_keeps_indonesian_point(self):
        self.assertTrue(ingest_firms.is_indonesia(110.0, 0.5, BOUNDARY))
        self.assertFalse(ingest_firms.is_indonesia(112.0, 0.5, BOUNDARY))

    def test_component_classifier_covers_all_logical_regions(self):
        samples = {
            "sumatra": (101.0, -1.0),
            "jawa": (110.0, -7.0),
            "kalimantan": (114.0, -1.0),
            "sulawesi": (121.0, -2.0),
            "bali-nusra": (120.0, -9.0),
            "maluku": (128.0, -3.0),
            "papua": (137.0, -4.0),
        }
        for expected, (lon, lat) in samples.items():
            with self.subTest(expected=expected):
                self.assertEqual(ingest_firms.classify_component(lon, lat), expected)

    def test_validate_accepts_all_expected_platforms(self):
        points = [point(platform) for platform in sorted(ingest_firms.EXPECTED_PLATFORMS)]
        summary = ingest_firms.source_observation_summary(points)
        ingest_firms.validate(
            points,
            {},
            summary,
            BOUNDARY,
            REGION_GEOMETRIES,
            datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
        )

    def test_validate_rejects_missing_platform(self):
        points = [point("S-NPP"), point("NOAA-20")]
        summary = ingest_firms.source_observation_summary(points)
        with self.assertRaisesRegex(ValueError, "missing or empty satellite source"):
            ingest_firms.validate(
                points,
                {},
                summary,
                BOUNDARY,
                REGION_GEOMETRIES,
                datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
            )

    def test_previous_kalimantan_counts_do_not_trigger_national_retention_guard(self):
        points = [point(platform) for platform in sorted(ingest_firms.EXPECTED_PLATFORMS)]
        summary = ingest_firms.source_observation_summary(points)
        previous_meta = {
            "coverageId": "kalimantan",
            "count": 100000,
            "sourceCounts": {platform: 100000 for platform in ingest_firms.EXPECTED_PLATFORMS},
        }
        ingest_firms.validate(
            points,
            previous_meta,
            summary,
            BOUNDARY,
            REGION_GEOMETRIES,
            datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
        )

    def test_write_hotspot_shards_partitions_by_region_and_date(self):
        regions = [
            {"id": region, "label": region}
            for region in ingest_firms.REGION_ORDER
        ]
        points = []
        for region in ("sumatra", "kalimantan"):
            for date in ("2026-08-21", "2026-08-22"):
                sample = point("S-NPP")
                sample["observationId"] = f"{region}|{date}"
                sample["date"] = date
                sample["region"] = region
                points.append(sample)

        meta = {
            "lastSuccessfulSync": "2026-08-22T10:00:00Z",
            "newestDetectionUtc": "2026-08-22T09:00:00Z",
            "oldestDetectionUtc": "2026-08-21T09:00:00Z",
            "platforms": ["S-NPP"],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = ingest_firms.write_hotspot_shards(points, root, regions, meta)
            self.assertEqual(manifest["regions"]["sumatra"]["count"], 2)
            self.assertEqual(manifest["regions"]["kalimantan"]["count"], 2)
            self.assertTrue((root / "sumatra" / "2026-08-22.json").exists())
            payload = json.loads((root / "kalimantan" / "2026-08-21.json").read_text())
            self.assertEqual(payload["meta"]["region"], "kalimantan")
            self.assertEqual(len(payload["points"]), 1)

    def test_stale_status_does_not_overwrite_dataset_provenance(self):
        previous_meta = {
            "source": "legacy source",
            "platforms": ["S-NPP"],
            "count": 123,
            "lastSuccessfulSync": "2026-08-21T00:00:00Z",
        }
        status = ingest_firms.status_payload(previous_meta, "network unavailable")
        self.assertEqual(status["pipelineStatus"], "stale")
        self.assertEqual(status["lastSuccessfulSync"], previous_meta["lastSuccessfulSync"])
        self.assertEqual(status["coverageId"], "indonesia")
        self.assertNotIn("source", status)
        self.assertNotIn("platforms", status)
        self.assertNotIn("count", status)

    def test_merge_points_idempotent_deduplicates_exact_id_and_preserves_distinct_passes(self):
        existing = [
            {
                "observationId": "S-NPP|2026-08-22|0630|0.50000|110.00000",
                "lat": 0.5,
                "lon": 110.0,
                "date": "2026-08-22",
                "time": "0630",
                "platform": "S-NPP",
                "conf": "nominal",
                "frp": 12.5,
            }
        ]
        incoming = [
            # Exact duplicate observationId from overlapping NRT fetch
            {
                "observationId": "S-NPP|2026-08-22|0630|0.50000|110.00000",
                "lat": 0.5,
                "lon": 110.0,
                "date": "2026-08-22",
                "time": "0630",
                "platform": "S-NPP",
                "conf": "nominal",
                "frp": 12.5,
            },
            # Distinct satellite pass over same location 50 minutes later
            {
                "observationId": "NOAA-20|2026-08-22|0720|0.50000|110.00000",
                "lat": 0.5,
                "lon": 110.0,
                "date": "2026-08-22",
                "time": "0720",
                "platform": "NOAA-20",
                "conf": "high",
                "frp": 18.0,
            },
        ]
        merged = ingest_firms.merge_points_idempotent(existing, incoming)
        self.assertEqual(len(merged), 2)
        self.assertEqual(
            [p["platform"] for p in merged],
            ["S-NPP", "NOAA-20"],
        )

    def test_write_hotspot_shards_preserves_historical_dates_across_rolling_refreshes(self):
        regions = [{"id": region, "label": region} for region in ingest_firms.REGION_ORDER]
        batch_1 = [
            {
                "observationId": "S-NPP|2026-08-20|0600|0.50000|110.00000",
                "lat": 0.5,
                "lon": 110.0,
                "date": "2026-08-20",
                "time": "0600",
                "platform": "S-NPP",
                "conf": "nominal",
                "dn": "D",
                "frp": 10.0,
                "region": "kalimantan",
            },
            {
                "observationId": "S-NPP|2026-08-21|0600|0.50000|110.00000",
                "lat": 0.5,
                "lon": 110.0,
                "date": "2026-08-21",
                "time": "0600",
                "platform": "S-NPP",
                "conf": "high",
                "dn": "D",
                "frp": 20.0,
                "region": "kalimantan",
            },
        ]
        batch_2 = [
            # Duplicate of 2026-08-21 plus new 2026-08-22 (2026-08-20 aged out of rolling NRT fetch)
            {
                "observationId": "S-NPP|2026-08-21|0600|0.50000|110.00000",
                "lat": 0.5,
                "lon": 110.0,
                "date": "2026-08-21",
                "time": "0600",
                "platform": "S-NPP",
                "conf": "high",
                "dn": "D",
                "frp": 20.0,
                "region": "kalimantan",
            },
            {
                "observationId": "NOAA-21|2026-08-22|1800|0.50000|110.00000",
                "lat": 0.5,
                "lon": 110.0,
                "date": "2026-08-22",
                "time": "1800",
                "platform": "NOAA-21",
                "conf": "nominal",
                "dn": "N",
                "frp": 15.0,
                "region": "kalimantan",
            },
        ]
        meta = {
            "lastSuccessfulSync": "2026-08-22T19:00:00Z",
            "newestDetectionUtc": "2026-08-22T18:00:00Z",
            "oldestDetectionUtc": "2026-08-21T06:00:00Z",
            "platforms": ["S-NPP", "NOAA-21"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ingest_firms.write_hotspot_shards(batch_1, root, regions, meta, preserve_existing=True)
            manifest = ingest_firms.write_hotspot_shards(batch_2, root, regions, meta, preserve_existing=True)
            kal_days = manifest["regions"]["kalimantan"]["days"]
            self.assertEqual([d["date"] for d in kal_days], ["2026-08-22", "2026-08-21", "2026-08-20"])
            self.assertEqual(manifest["regions"]["kalimantan"]["count"], 3)
            self.assertTrue((root / "kalimantan" / "2026-08-20.json").exists())


if __name__ == "__main__":
    unittest.main()
