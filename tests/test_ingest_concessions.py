import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location("ingest_concessions", SCRIPTS / "ingest_concessions.py")
ingest = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ingest)


class ConcessionIngestTests(unittest.TestCase):
    def setUp(self):
        self.square = {
            "type": "MultiPolygon",
            "coordinates": [[[[110.0, -2.0], [116.0, -2.0], [116.0, 2.0], [110.0, 2.0], [110.0, -2.0]]]],
        }

    def test_national_bbox_matches_firms_pipeline(self):
        self.assertEqual(ingest.INDONESIA_BBOX, (94.5, -11.5, 141.5, 6.5))
        self.assertEqual(tuple(ingest.REGION_ORDER), (
            "sumatra", "jawa", "kalimantan", "sulawesi", "bali-nusra", "maluku", "papua"
        ))

    def test_geometry_in_region_accepts_inside_polygon(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [[[111.0, -1.0], [112.0, -1.0], [112.0, 0.0], [111.0, 0.0], [111.0, -1.0]]],
        }
        self.assertTrue(ingest.geometry_in_region(geometry, self.square))

    def test_geometry_in_region_rejects_outside_polygon(self):
        geometry = {
            "type": "Polygon",
            "coordinates": [[[120.0, -1.0], [121.0, -1.0], [121.0, 0.0], [120.0, 0.0], [120.0, -1.0]]],
        }
        self.assertFalse(ingest.geometry_in_region(geometry, self.square))

    def test_multi_polygon_is_split_by_region_without_duplicate_source_fetch(self):
        region_geometries = {
            region: {"type": "MultiPolygon", "coordinates": []}
            for region in ingest.REGION_ORDER
        }
        region_geometries["sumatra"] = {
            "type": "Polygon",
            "coordinates": [[[99.0, -1.0], [101.0, -1.0], [101.0, 1.0], [99.0, 1.0], [99.0, -1.0]]],
        }
        region_geometries["kalimantan"] = {
            "type": "Polygon",
            "coordinates": [[[112.0, -1.0], [114.0, -1.0], [114.0, 1.0], [112.0, 1.0], [112.0, -1.0]]],
        }
        indonesia_boundary = {
            "type": "GeometryCollection",
            "geometries": [region_geometries["sumatra"], region_geometries["kalimantan"]],
        }
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[99.2, -0.8], [100.8, -0.8], [100.8, 0.8], [99.2, 0.8], [99.2, -0.8]]],
                [[[112.2, -0.8], [113.8, -0.8], [113.8, 0.8], [112.2, 0.8], [112.2, -0.8]]],
            ],
        }
        grouped = ingest.group_geometry_by_region(geometry, region_geometries, indonesia_boundary)
        self.assertEqual(set(grouped), {"sumatra", "kalimantan"})
        self.assertEqual(len(grouped["sumatra"]), 1)
        self.assertEqual(len(grouped["kalimantan"]), 1)

    def test_gfw_polygon_outside_indonesia_mask_has_no_heuristic_region(self):
        region_geometries = {
            region: {"type": "MultiPolygon", "coordinates": []}
            for region in ingest.REGION_ORDER
        }
        indonesia_boundary = {"type": "GeometryCollection", "geometries": []}
        polygon = [[[117.0, 5.0], [118.0, 5.0], [118.0, 5.5], [117.0, 5.5], [117.0, 5.0]]]
        self.assertIsNone(
            ingest.region_for_polygon(polygon, region_geometries, indonesia_boundary, allow_indonesia_heuristic=False)
        )

    def test_big_polygon_can_use_indonesia_only_fallback(self):
        region_geometries = {
            region: {"type": "MultiPolygon", "coordinates": []}
            for region in ingest.REGION_ORDER
        }
        indonesia_boundary = {"type": "GeometryCollection", "geometries": []}
        polygon = [[[112.0, -1.0], [113.0, -1.0], [113.0, 0.0], [112.0, 0.0], [112.0, -1.0]]]
        self.assertEqual(
            ingest.region_for_polygon(polygon, region_geometries, indonesia_boundary, allow_indonesia_heuristic=True),
            "kalimantan",
        )

    def test_simplify_ring_preserves_closed_ring(self):
        ring = [
            [110.0, 0.0], [110.1, 0.0], [110.2, 0.0],
            [110.2, 0.1], [110.2, 0.2],
            [110.1, 0.2], [110.0, 0.2],
            [110.0, 0.1], [110.0, 0.0],
        ]
        simplified = ingest.simplify_ring(ring, tolerance=0.01)
        self.assertEqual(simplified[0][:2], simplified[-1][:2])
        self.assertLess(len(simplified), len(ring))
        self.assertGreaterEqual(len(simplified), 4)

    def test_forestry_normalization_keeps_source_and_links_existing_dossier(self):
        spec_data = next(row for row in ingest.SOURCE_SPECS if row["id"] == "big-forestry-ha")
        metadata = {"objectIdField": "OBJECTID"}
        props = {
            "OBJECTID": 12,
            "namobj": "PT Kaltim Prima Coal",
            "no_sk": "SK-1",
            "tgl_sk": 1704067200000,
            "lssk": 1234.5,
            "kdprv": "64",
        }
        result = ingest.normalize_forestry(
            spec_data,
            props,
            metadata,
            "2026-08-24T00:00:00Z",
            {ingest.normalize_company_key("PT Kaltim Prima Coal"): "kpc"},
        )
        self.assertEqual(result["quality"], "OFFICIAL")
        self.assertEqual(result["name"], "PT Kaltim Prima Coal")
        self.assertEqual(result["permitNumber"], "SK-1")
        self.assertEqual(result["dossierId"], "kpc")
        self.assertTrue(result["sourceUrl"].endswith("/1"))

    def test_mining_normalization_keeps_operator_and_commodity(self):
        spec_data = next(row for row in ingest.SOURCE_SPECS if row["id"] == "big-mining-wiup")
        metadata = {"objectIdField": "OBJECTID"}
        props = {
            "OBJECTID": 99,
            "nmoprt": "PT Example Mining",
            "prov": "Kalimantan Timur",
            "kab": "Kutai Timur",
            "skblok": "90/1/IUP/PMA/2021",
            "commdt": "Batubara",
            "lublok": 1000,
            "status": "Operasi Produksi",
        }
        result = ingest.normalize_mining(spec_data, props, metadata, "2026-08-24T00:00:00Z", {})
        self.assertEqual(result["sector"], "Tambang")
        self.assertEqual(result["name"], "PT Example Mining")
        self.assertEqual(result["commodity"], "Batubara")
        self.assertEqual(result["areaHa"], 1000.0)
        self.assertEqual(result["quality"], "OFFICIAL")

    def test_gfw_oil_palm_is_never_labelled_official(self):
        spec_data = next(row for row in ingest.SOURCE_SPECS if row["id"] == "gfw-oil-palm")
        metadata = {"objectIdField": "OBJECTID"}
        result = ingest.normalize_oil_palm_gfw(
            spec_data,
            {"OBJECTID": 7, "company": "PT Example Palm", "group_comp": "Example Group", "area_ha": 2500},
            metadata,
            "2026-08-24T00:00:00Z",
            {},
        )
        self.assertEqual(result["quality"], "GFW")
        self.assertNotEqual(result["quality"], "OFFICIAL")
        self.assertIn("older", result["coverageCaveat"])

    def test_required_sources_are_official_forestry_and_mining_only(self):
        required = [row for row in ingest.SOURCE_SPECS if row["required"]]
        self.assertEqual(
            {row["id"] for row in required},
            {"big-forestry-ha", "big-forestry-hti", "big-forestry-re", "big-mining-wiup"},
        )
        self.assertTrue(all(row["quality"] == "OFFICIAL" for row in required))


if __name__ == "__main__":
    unittest.main()
