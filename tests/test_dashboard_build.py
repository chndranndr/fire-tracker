import importlib.util
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


land_patch = load_module(
    "patch_land_holdings_dashboard",
    ROOT / "scripts" / "patch_land_holdings_dashboard.py",
)
region_patch = load_module(
    "patch_region_dashboard",
    ROOT / "scripts" / "patch_region_dashboard.py",
)
inventory_patch = load_module(
    "patch_concession_inventory_dashboard",
    ROOT / "scripts" / "patch_concession_inventory_dashboard.py",
)


class DashboardBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.html = inventory_patch.build_patched_index(
            region_patch.build_patched_index(
                land_patch.build_patched_index(source)
            )
        )

    def test_region_patch_removes_legacy_bulk_frontend_loads(self):
        self.assertIn('id="f-region"', self.html)
        self.assertIn('data/hotspots/manifest.json', self.html)
        self.assertIn('function selectRegion(regionId, preferredDate)', self.html)
        self.assertIn('function refreshNationalSummary()', self.html)
        self.assertNotIn('loadJson("data/firms.json")', self.html)
        self.assertNotIn('loadJson("data/dossiers.json")', self.html)
        self.assertNotIn('loadJson("data/boundaries.geojson")', self.html)
        self.assertIn('id="tog-inventory"', self.html)
        self.assertIn("function refreshConcessionInventoryLayer()", self.html)

    def test_patched_inline_javascript_parses(self):
        scripts = re.findall(r"<script>(.*?)</script>", self.html, flags=re.DOTALL)
        self.assertTrue(scripts, "patched dashboard has no inline JavaScript")
        for index, script in enumerate(scripts):
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", suffix=f"-{index}.js", delete=False
            ) as handle:
                handle.write(script)
                path = Path(handle.name)
            try:
                result = subprocess.run(
                    ["node", "--check", str(path)],
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=f"node --check failed:\n{result.stdout}\n{result.stderr}",
                )
            finally:
                path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
