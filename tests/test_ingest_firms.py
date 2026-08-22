import importlib.util
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
        self.assertTrue(ingest_firms.is_kalimantan_indonesia(110.0, 0.5, BOUNDARY))
        self.assertFalse(ingest_firms.is_kalimantan_indonesia(112.0, 0.5, BOUNDARY))

    def test_validate_accepts_all_expected_platforms(self):
        points = [point(platform) for platform in sorted(ingest_firms.EXPECTED_PLATFORMS)]
        summary = ingest_firms.source_observation_summary(points)
        ingest_firms.validate(
            points,
            {},
            summary,
            BOUNDARY,
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
                datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
            )

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
        self.assertNotIn("source", status)
        self.assertNotIn("platforms", status)
        self.assertNotIn("count", status)


if __name__ == "__main__":
    unittest.main()
