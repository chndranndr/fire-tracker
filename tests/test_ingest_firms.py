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

    def test_durable_store_restores_and_persists_history_across_ephemeral_workspaces(self):
        regions = [{"id": region, "label": region} for region in ingest_firms.REGION_ORDER]
        batch_day_1 = [
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
        batch_day_2 = [
            # Overlapping 2026-08-21 observation + new 2026-08-22 observation (2026-08-20 aged out of API window)
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
        meta_1 = {
            "lastSuccessfulSync": "2026-08-21T07:00:00Z",
            "newestDetectionUtc": "2026-08-21T06:00:00Z",
            "oldestDetectionUtc": "2026-08-20T06:00:00Z",
            "platforms": ["S-NPP"],
        }
        meta_2 = {
            "lastSuccessfulSync": "2026-08-22T19:00:00Z",
            "newestDetectionUtc": "2026-08-22T18:00:00Z",
            "oldestDetectionUtc": "2026-08-21T06:00:00Z",
            "platforms": ["S-NPP", "NOAA-21"],
        }
        with tempfile.TemporaryDirectory() as durable_tmp, \
             tempfile.TemporaryDirectory() as ephemeral_run_1, \
             tempfile.TemporaryDirectory() as ephemeral_run_2:
            durable_dir = Path(durable_tmp) / "hotspots"
            ws_1 = Path(ephemeral_run_1) / "hotspots"
            ws_2 = Path(ephemeral_run_2) / "hotspots"

            # Ephemeral CI run #1 writes shards and persists them to durable_dir
            ingest_firms.write_hotspot_shards(
                batch_day_1,
                ws_1,
                regions,
                meta_1,
                preserve_existing=True,
                durable_store_dir=durable_dir,
            )
            self.assertTrue((durable_dir / "manifest.json").exists())
            self.assertTrue((durable_dir / "kalimantan" / "2026-08-20.json").exists())

            # Ephemeral CI run #2 starts with a completely empty local workspace (ws_2)
            self.assertFalse((ws_2 / "kalimantan" / "2026-08-20.json").exists())
            manifest_2 = ingest_firms.write_hotspot_shards(
                batch_day_2,
                ws_2,
                regions,
                meta_2,
                preserve_existing=True,
                durable_store_dir=durable_dir,
            )
            kal_days = manifest_2["regions"]["kalimantan"]["days"]
            self.assertEqual([d["date"] for d in kal_days], ["2026-08-22", "2026-08-21", "2026-08-20"])
            self.assertEqual(manifest_2["regions"]["kalimantan"]["count"], 3)
            self.assertEqual(manifest_2["meta"]["oldestDetectionUtc"], "2026-08-20T06:00:00Z")
            self.assertTrue((ws_2 / "kalimantan" / "2026-08-20.json").exists())
            self.assertTrue((durable_dir / "kalimantan" / "2026-08-22.json").exists())

    def test_validate_separates_rolling_window_from_historical_totals(self):
        # Issue #2: A 5-day ingest batch (~180 points) must NOT be compared against cumulative historical count (67,478)
        pts = (
            [point("S-NPP") for _ in range(60)]
            + [point("NOAA-20") for _ in range(60)]
            + [point("NOAA-21") for _ in range(60)]
        )
        summary = {
            p: {
                "count": 60,
                "newest": datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
                "oldest": datetime(2026, 8, 22, 1, 0, tzinfo=timezone.utc),
            }
            for p in ("S-NPP", "NOAA-20", "NOAA-21")
        }
        previous_meta_with_history = {
            "coverageId": "indonesia",
            "count": 67478,
            "historicalCount": 67478,
            "rollingWindowCount": 200,
            "historyPreserved": True,
            "sourceCounts": {"S-NPP": 25000, "NOAA-20": 25000, "NOAA-21": 17478},
            "rollingWindowSourceCounts": {"S-NPP": 70, "NOAA-20": 70, "NOAA-21": 60},
        }
        now = datetime(2026, 8, 22, 11, 0, tzinfo=timezone.utc)
        # 180 is >= 200 * 0.75 (150), so this must NOT fail!
        ingest_firms.validate(
            pts, previous_meta_with_history, summary, BOUNDARY, REGION_GEOMETRIES, now
        )

        # But if the current batch drops below the retention threshold of the rolling window (e.g. 50 < 100), it rejects
        dropped_pts = (
            [point("S-NPP") for _ in range(15)]
            + [point("NOAA-20") for _ in range(15)]
            + [point("NOAA-21") for _ in range(20)]
        )
        dropped_summary = {
            p: {
                "count": len([pt for pt in dropped_pts if pt.get("platform") == p]),
                "newest": datetime(2026, 8, 22, 10, 0, tzinfo=timezone.utc),
                "oldest": datetime(2026, 8, 22, 1, 0, tzinfo=timezone.utc),
            }
            for p in ("S-NPP", "NOAA-20", "NOAA-21")
        }
        with self.assertRaises(ValueError) as ctx:
            ingest_firms.validate(
                dropped_pts, previous_meta_with_history, dropped_summary, BOUNDARY, REGION_GEOMETRIES, now
            )
        self.assertIn("previous rolling window", str(ctx.exception))

    def test_summarize_day_points_evaluates_true_day_boundaries(self):
        # Issue #4: Day completeness evaluates actual calendar day boundaries, never an arbitrary 21:00 cutoff
        day_points = [
            {
                "observationId": "S-NPP|2026-08-22|2130|0.5|110.0",
                "lat": 0.5,
                "lon": 110.0,
                "date": "2026-08-22",
                "time": "2130",
                "platform": "S-NPP",
                "conf": "nominal",
            }
        ]
        # Current time is 2026-08-22 22:00 UTC (day is still ongoing, even though time is > 21:00)
        during_day = datetime(2026, 8, 22, 22, 0, tzinfo=timezone.utc)
        summary_ongoing = ingest_firms.summarize_day_points(
            day_points, is_latest_global_date=True, has_subsequent_date=False, now_utc=during_day
        )
        self.assertEqual(summary_ongoing["completeness"], "partial")

        # After day concludes and subsequent date exists -> complete
        after_day = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
        summary_concluded = ingest_firms.summarize_day_points(
            day_points, is_latest_global_date=False, has_subsequent_date=True, now_utc=after_day
        )
        self.assertEqual(summary_concluded["completeness"], "complete")

    def test_real_actions_worktree_persistence_sequence_e2e(self):
        # Review finding #4: Production FIRMS history persistence verified against real git execution
        # Simulates consecutive GitHub Actions container executions with ephemeral workspaces
        import shutil
        import subprocess

        regions = [{"id": region, "label": region} for region in ingest_firms.REGION_ORDER]

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bare = root / "remote-origin.git"
            subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(bare)], check=True, capture_output=True)

            # Ephemeral Runner 1 (Initial run: firms-history-data does not exist on remote yet)
            runner_1 = root / "runner_1"
            subprocess.run(["git", "clone", str(bare), str(runner_1)], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "test-bot"], cwd=runner_1, check=True)
            subprocess.run(["git", "config", "user.email", "bot@test.com"], cwd=runner_1, check=True)
            (runner_1 / "README.md").write_text("seed", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=runner_1, check=True)
            subprocess.run(["git", "commit", "-m", "init main"], cwd=runner_1, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=runner_1, check=True)

            # Exact restore step from firms-nrt.yml
            store_1 = root / "store_1"
            store_1.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "fetch", "origin", "firms-history-data:refs/remotes/origin/firms-history-data"], cwd=runner_1, capture_output=True)
            chk = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/remotes/origin/firms-history-data"], cwd=runner_1)
            self.assertNotEqual(chk.returncode, 0, "remote branch must not exist on first run")
            subprocess.run(["git", "worktree", "add", "--detach", str(store_1)], cwd=runner_1, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "--orphan", "firms-history-data"], cwd=store_1, check=True, capture_output=True)
            subprocess.run(["git", "rm", "-rf", "."], cwd=store_1, check=True, capture_output=True)

            batch_day_1 = [
                {
                    "observationId": "S-NPP|2026-08-20|0600|0.50000|110.00000",
                    "lat": 0.5, "lon": 110.0, "date": "2026-08-20", "time": "0600",
                    "platform": "S-NPP", "conf": "nominal", "dn": "D", "frp": 10.0, "region": "kalimantan",
                }
            ]
            meta_1 = {"lastSuccessfulSync": "2026-08-20T07:00:00Z", "newestDetectionUtc": "2026-08-20T06:00:00Z", "oldestDetectionUtc": "2026-08-20T06:00:00Z", "platforms": ["S-NPP"]}
            ingest_firms.write_hotspot_shards(batch_day_1, runner_1 / "data" / "hotspots", regions, meta_1, preserve_existing=True, durable_store_dir=store_1)

            # Exact persist step from firms-nrt.yml
            (store_1 / "hotspots").mkdir(parents=True, exist_ok=True)
            for item in (runner_1 / "data" / "hotspots").iterdir():
                dest = store_1 / "hotspots" / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=store_1, check=True)
            subprocess.run(["git", "config", "user.email", "bot@users.noreply.github.com"], cwd=store_1, check=True)
            subprocess.run(["git", "add", "-A"], cwd=store_1, check=True)
            subprocess.run(["git", "commit", "-m", "chore(firms): persist durable multi-day hotspot history"], cwd=store_1, check=True, capture_output=True)
            subprocess.run(["git", "push", "origin", "firms-history-data"], cwd=store_1, check=True, capture_output=True)

            # Ephemeral Runner 2 (Next scheduled Actions run: brand new container workspace)
            runner_2 = root / "runner_2"
            subprocess.run(["git", "clone", str(bare), str(runner_2)], check=True, capture_output=True)
            self.assertFalse((runner_2 / "data" / "hotspots").exists())

            # Exact restore step from firms-nrt.yml
            store_2 = root / "store_2"
            store_2.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "fetch", "origin", "firms-history-data:refs/remotes/origin/firms-history-data"], cwd=runner_2, check=True, capture_output=True)
            chk2 = subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/remotes/origin/firms-history-data"], cwd=runner_2)
            self.assertEqual(chk2.returncode, 0, "remote branch must exist on runner 2")
            subprocess.run(["git", "worktree", "add", "-B", "firms-history-data", str(store_2), "origin/firms-history-data"], cwd=runner_2, check=True, capture_output=True)

            # Day 2 ingest batch (2026-08-20 aged out of FIRMS API window)
            batch_day_2 = [
                {
                    "observationId": "NOAA-20|2026-08-21|0600|0.50000|110.00000",
                    "lat": 0.5, "lon": 110.0, "date": "2026-08-21", "time": "0600",
                    "platform": "NOAA-20", "conf": "high", "dn": "D", "frp": 25.0, "region": "kalimantan",
                }
            ]
            meta_2 = {"lastSuccessfulSync": "2026-08-21T07:00:00Z", "newestDetectionUtc": "2026-08-21T06:00:00Z", "oldestDetectionUtc": "2026-08-21T06:00:00Z", "platforms": ["NOAA-20"]}
            manifest_2 = ingest_firms.write_hotspot_shards(batch_day_2, runner_2 / "data" / "hotspots", regions, meta_2, preserve_existing=True, durable_store_dir=store_2)

            # Assert history from day 1 was successfully restored into runner_2!
            self.assertTrue((runner_2 / "data" / "hotspots" / "kalimantan" / "2026-08-20.json").exists())
            self.assertTrue((runner_2 / "data" / "hotspots" / "kalimantan" / "2026-08-21.json").exists())
            dates_in_manifest = [d["date"] for d in manifest_2["regions"]["kalimantan"]["days"]]
            self.assertEqual(dates_in_manifest, ["2026-08-21", "2026-08-20"])
            self.assertEqual(manifest_2["meta"]["oldestDetectionUtc"], "2026-08-20T06:00:00Z")


if __name__ == "__main__":
    unittest.main()
