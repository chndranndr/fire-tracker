import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_v2_contracts():
    path = ROOT / "scripts" / "v2_contracts.py"
    spec = importlib.util.spec_from_file_location("v2_contracts", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader is not None
    spec.loader.exec_module(module)
    return module


v2 = load_v2_contracts()


class V2FoundationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.regions_payload = v2.read_json(ROOT / "data" / "regions.json")
        cls.admin_index = v2.read_json(ROOT / "data" / "admin-index.json")
        cls.sources_manifest = v2.read_json(ROOT / "data" / "sources-manifest.json")

    def test_all_sources_manifest_envelopes_are_valid(self):
        metrics = self.sources_manifest.get("metrics") or {}
        expected_ids = {
            "firms-hotspots",
            "concession-inventory",
            "walhi-dossiers",
            "sipongi-fallback",
            "burned-area",
            "air-quality-pm25",
            "bmkg-weather",
            "kemenkes-ispa",
        }
        self.assertEqual(set(metrics.keys()), expected_ids)
        for env in metrics.values():
            v2.validate_metric_envelope(env)

    def test_unavailable_metrics_never_use_zero_or_sample_values(self):
        metrics = self.sources_manifest["metrics"]
        for mid in ("burned-area", "air-quality-pm25", "bmkg-weather", "kemenkes-ispa"):
            env = metrics[mid]
            self.assertEqual(env["availability"]["state"], "unavailable")
            self.assertIsNone(env["value"])
            self.assertTrue(env["availability"]["reason"])

        with self.assertRaises(ValueError):
            v2.build_metric_envelope(
                metric_id="bad-zero-unavailable",
                title="Invalid Zero Unavailable",
                layer_type="Environmental",
                source="Test",
                url="https://example.com",
                product="Test",
                version="1",
                valid_from=None,
                valid_to=None,
                period_label="N/A",
                published_at=None,
                updated_at=None,
                coverage_id="indonesia",
                supported_granularities=["national"],
                units="ha",
                granularity="day",
                availability_state="unavailable",
                quality="UNAVAILABLE",
                value=0,
                reason="Missing",
                caveats=["Caveat"],
            )

    def test_genuine_zero_is_distinct_from_unavailable(self):
        env = v2.build_metric_envelope(
            metric_id="genuine-zero-hotspots",
            title="Genuine Zero Detections",
            layer_type="Detection",
            source="NASA FIRMS",
            url="https://firms.modaps.eosdis.nasa.gov/",
            product="VIIRS",
            version="4",
            valid_from="2026-08-27",
            valid_to="2026-08-27",
            period_label="2026-08-27 (UTC)",
            published_at="2026-08-28T00:00:00Z",
            updated_at="2026-08-28T00:00:00Z",
            coverage_id="maluku",
            supported_granularities=["region"],
            units="detections",
            granularity="day",
            availability_state="fresh",
            quality="NRT",
            value=0,
            caveats=["Observed zero satellite detections."],
        )
        self.assertEqual(env["availability"]["state"], "fresh")
        self.assertEqual(env["value"], 0)

    def test_firms_freshness_distinguishes_fresh_stale_and_unavailable(self):
        meta = {
            "count": 67478,
            "lastSuccessfulSync": "2026-08-28T05:00:00Z",
            "newestDetectionUtc": "2026-08-28T04:00:00Z",
        }
        ref_fresh = datetime(2026, 8, 28, 6, 0, tzinfo=timezone.utc)
        fresh = v2.evaluate_firms_freshness(meta, {"stale": False}, reference_utc=ref_fresh)
        self.assertEqual(fresh["state"], "fresh")
        self.assertFalse(fresh["lastKnownGood"])
        self.assertEqual(fresh["syncAgeMinutes"], 60)

        ref_old = datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc)
        stale_by_age = v2.evaluate_firms_freshness(meta, {"stale": False}, reference_utc=ref_old)
        self.assertEqual(stale_by_age["state"], "stale")
        self.assertTrue(stale_by_age["lastKnownGood"])

        stale_by_flag = v2.evaluate_firms_freshness(
            meta,
            {"stale": True, "previousDataPreserved": True, "error": "Upstream timeout"},
            reference_utc=ref_fresh,
        )
        self.assertEqual(stale_by_flag["state"], "stale")
        self.assertTrue(stale_by_flag["lastKnownGood"])
        self.assertIn("Upstream timeout", stale_by_flag["reason"])

        unavail = v2.evaluate_firms_freshness({}, {})
        self.assertEqual(unavail["state"], "unavailable")

    def test_sipongi_and_firms_remain_separate_sources(self):
        metrics = self.sources_manifest["metrics"]
        firms = metrics["firms-hotspots"]
        sipongi = metrics["sipongi-fallback"]
        self.assertFalse(firms["availability"]["isFallback"])
        self.assertTrue(sipongi["availability"]["isFallback"])
        self.assertEqual(firms["granularity"], "day")
        self.assertEqual(sipongi["granularity"], "period")
        self.assertNotEqual(firms["source"], sipongi["source"])

    def test_province_and_kabupaten_normalization_and_cross_border_deduplication(self):
        # BPS code -> canonical province
        self.assertEqual(
            v2.parse_record_provinces({"provinceCode": "64"}),
            ["Kalimantan Timur"],
        )
        # Cross-border multi-province string -> both provinces
        self.assertEqual(
            v2.parse_record_provinces({"province": "KALIMANTAN SELATAN, KALIMANTAN TIMUR"}),
            ["Kalimantan Selatan", "Kalimantan Timur"],
        )
        # Island-wide label 'Kalimantan' -> [] (never substitutes for a province)
        self.assertEqual(
            v2.parse_record_provinces({"province": "Kalimantan"}),
            [],
        )
        # Cross-border kabupaten string -> both kabupaten
        self.assertEqual(
            v2.parse_record_kabupaten({"district": "BANJAR, TAPIN"}),
            ["Banjar", "Tapin"],
        )

        # Deduplication across split cross-border polygons
        features = [
            {
                "properties": {
                    "inventoryId": "big-mining-wiup:100:kalimantan",
                    "sourceInventoryId": "big-mining-wiup:100",
                    "sector": "Tambang",
                    "quality": "OFFICIAL",
                    "province": "KALIMANTAN SELATAN, KALIMANTAN TIMUR",
                    "district": "TABALONG, PASER",
                }
            },
            {
                "properties": {
                    "inventoryId": "big-mining-wiup:100:kalimantan-2",
                    "sourceInventoryId": "big-mining-wiup:100",
                    "sector": "Tambang",
                    "quality": "OFFICIAL",
                    "province": "KALIMANTAN TIMUR",
                    "district": "PASER",
                }
            },
            {
                "properties": {
                    "inventoryId": "gfw-oil-palm:200",
                    "sector": "Sawit",
                    "quality": "GFW",
                    "province": "Kalimantan",
                }
            },
        ]
        self.assertEqual(v2.deduplicated_concession_count(features), 2)

        filtered_kaltim = v2.filter_concession_features(
            features, region="kalimantan", province="Kalimantan Timur"
        )
        self.assertEqual(filtered_kaltim["rawCount"], 2)
        self.assertEqual(filtered_kaltim["deduplicatedCount"], 1)
        self.assertEqual(filtered_kaltim["unresolvedProvinceCount"], 1)

        filtered_paser = v2.filter_concession_features(
            features, region="kalimantan", province="Kalimantan Timur", kabupaten="Paser"
        )
        self.assertEqual(filtered_paser["deduplicatedCount"], 1)

    def test_utc_to_wib_time_boundary_conversion(self):
        before_midnight = v2.convert_utc_to_wib("2026-08-27", "1630")
        self.assertEqual(before_midnight["wibDate"], "2026-08-27")
        self.assertEqual(before_midnight["wibTime"], "23:30")
        self.assertFalse(before_midnight["crossedMidnightWib"])

        after_midnight = v2.convert_utc_to_wib("2026-08-27", "1730")
        self.assertEqual(after_midnight["wibDate"], "2026-08-28")
        self.assertEqual(after_midnight["wibTime"], "00:30")
        self.assertTrue(after_midnight["crossedMidnightWib"])

    def test_url_filter_normalization_and_safe_fallback(self):
        dates = ["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27"]
        # Valid query with province auto-aligning region
        state = v2.normalize_filter_state(
            "?view=concessions&prov=Kalimantan+Timur&kab=Kutai+Timur&date=2026-08-26&window=4d&sector=Tambang",
            self.regions_payload,
            available_dates=dates,
            admin_index=self.admin_index,
        )
        self.assertEqual(state["view"], "concessions")
        self.assertEqual(state["region"], "kalimantan")
        self.assertEqual(state["prov"], "Kalimantan Timur")
        self.assertEqual(state["kab"], "Kutai Timur")
        self.assertEqual(state["date"], "2026-08-26")
        self.assertEqual(state["window"], "4d")
        self.assertEqual(state["sector"], "Tambang")

        qs = v2.serialize_filter_query(state)
        round_trip = v2.normalize_filter_state(
            qs,
            self.regions_payload,
            available_dates=dates,
            admin_index=self.admin_index,
        )
        self.assertEqual(round_trip, state)

        # Invalid parameters fall back safely
        fallback = v2.normalize_filter_state(
            "?view=invalid&region=atlantis&prov=FakeProv&kab=FakeKab&date=1999-01-01&window=999d&sector=Unknown",
            self.regions_payload,
            available_dates=dates,
            admin_index=self.admin_index,
        )
        self.assertEqual(fallback["view"], "overview")
        self.assertEqual(fallback["region"], "indonesia")
        self.assertEqual(fallback["prov"], "")
        self.assertEqual(fallback["kab"], "")
        self.assertEqual(fallback["date"], "2026-08-27")
        self.assertEqual(fallback["window"], "all")
        self.assertEqual(fallback["sector"], "")

    def test_unified_concession_viewmodel_matches_and_unmatched_dossiers(self):
        kal = v2.build_region_concession_view_models("kalimantan", ROOT)
        stats = kal["stats"]
        self.assertEqual(stats["rawInventoryCount"], 3053)
        self.assertEqual(stats["deduplicatedInventoryCount"], 3053)
        self.assertEqual(stats["matchedDossierCount"], 9)
        self.assertEqual(stats["matchedInventoryRowCount"], 10)
        self.assertEqual(stats["unmatchedDossierOnlyCount"], 3)
        self.assertEqual(stats["totalDossierCount"], 12)
        self.assertEqual(stats["totalUnifiedCount"], 3056)

        rows = kal["rows"]
        accessible_dossiers = {
            r["linkedDossierId"] for r in rows if r.get("hasInvestigativeDossier")
        }
        self.assertEqual(
            accessible_dossiers,
            {
                "kideco",
                "kpc",
                "agm",
                "bre",
                "adaro",
                "dwima",
                "kiani",
                "bsg",
                "lar",
                "thm1",
                "thm2",
                "sum",
            },
        )

        # Unmatched dossiers stay independent as dossier-only records
        dossier_only = [r for r in rows if r["recordKind"] == "dossier-only"]
        self.assertEqual({r["linkedDossierId"] for r in dossier_only}, {"thm1", "thm2", "sum"})
        for r in dossier_only:
            self.assertEqual(r["matchBasis"], "unmatched_curated_dossier")
            self.assertTrue(r["hasInvestigativeDossier"])

        # Generic inventory rows never inherit WALHI claims or UBO status by proximity
        generic_rows = [r for r in rows if r["recordKind"] == "inventory"]
        self.assertEqual(len(generic_rows), 3043)
        for r in generic_rows:
            self.assertFalse(r["hasInvestigativeDossier"])
            self.assertIsNone(r["linkedDossierId"])
            self.assertIsNone(r["walhiHotspots"])
            self.assertIsNone(r["uboStatus"])

    def test_concession_search_filter_sort_pagination_and_large_fixture(self):
        kal = v2.build_region_concession_view_models("kalimantan", ROOT)
        rows = kal["rows"]

        # Default page 1 of 50
        p1 = v2.query_concession_view_models(rows, page=1, page_size=50)
        self.assertEqual(p1["totalFiltered"], 3056)
        self.assertEqual(len(p1["items"]), 50)
        self.assertEqual(p1["totalPages"], 62)
        # First items in default sort have investigative dossiers
        self.assertTrue(p1["items"][0]["hasInvestigativeDossier"])

        # Filter by Kalimantan Timur + Tambang + OFFICIAL
        kaltim_mining = v2.query_concession_view_models(
            rows,
            sector="Tambang",
            quality="OFFICIAL",
            prov="Kalimantan Timur",
            sort_by="area_desc",
        )
        self.assertGreater(kaltim_mining["totalFiltered"], 100)
        for r in kaltim_mining["items"]:
            self.assertEqual(r["sector"], "Tambang")
            self.assertEqual(r["quality"], "OFFICIAL")
            self.assertIn("Kalimantan Timur", r["provinces"])

        # Search by specific operator
        kideco_q = v2.query_concession_view_models(rows, search="KIDECO JAYA AGUNG")
        self.assertEqual(kideco_q["totalFiltered"], 1)
        self.assertEqual(kideco_q["items"][0]["linkedDossierId"], "kideco")

        # Large generated fixture (5,000 records) pagination test
        large_fixture = [
            {
                "viewModelId": f"inv:test:{i}",
                "recordKind": "inventory",
                "name": f"PT CONCESSION {i:04d}",
                "operator": f"PT CONCESSION {i:04d}",
                "sector": "Sawit" if i % 2 == 0 else "PBPH",
                "subtype": "HGU",
                "quality": "OFFICIAL",
                "hasInvestigativeDossier": False,
                "areaHa": float(i * 10),
                "provinces": ["Kalimantan Barat"],
                "kabupaten": ["Ketapang"],
                "locationText": "Kalimantan Barat, Ketapang",
            }
            for i in range(5000)
        ]
        page_last = v2.query_concession_view_models(
            large_fixture, sector="Sawit", sort_by="area_asc", page=50, page_size=50
        )
        self.assertEqual(page_last["totalFiltered"], 2500)
        self.assertEqual(page_last["totalPages"], 50)
        self.assertEqual(len(page_last["items"]), 50)
        self.assertEqual(page_last["startIndex"], 2451)
        self.assertEqual(page_last["endIndex"], 2500)

    def test_contextual_concession_inspector_tabs_and_evidence_separation(self):
        kal = v2.build_region_concession_view_models("kalimantan", ROOT)
        rows = kal["rows"]
        dossiers_payload = v2.read_json(ROOT / "data" / "dossiers" / "kalimantan.json", {})
        dossier_by_id = {d["id"]: d for d in (dossiers_payload.get("dossiers") or [])}

        generic_row = next(r for r in rows if not r["hasInvestigativeDossier"])
        generic_insp = v2.build_concession_inspector_model(generic_row, None)
        self.assertEqual(generic_insp["tabs"], ["summary", "map"])
        self.assertIsNone(generic_insp["investigation"])

        matched_row = next(r for r in rows if r["linkedDossierId"] == "kideco")
        matched_insp = v2.build_concession_inspector_model(
            matched_row, dossier_by_id["kideco"]
        )
        self.assertEqual(matched_insp["tabs"], ["summary", "map", "investigation"])
        self.assertIsNotNone(matched_insp["investigation"])
        self.assertEqual(matched_insp["investigation"]["dossierId"], "kideco")
        self.assertTrue(len(matched_insp["investigation"]["sources"]) > 0)


if __name__ == "__main__":
    unittest.main()

