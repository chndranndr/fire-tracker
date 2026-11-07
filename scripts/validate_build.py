#!/usr/bin/env python3
"""Regression gate shared by PR validation and production Pages deploy."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], label: str) -> None:
    print(f"validate: {label}")
    subprocess.run(cmd, check=True, cwd=ROOT)


def load_ingest_firms():
    spec = importlib.util.spec_from_file_location(
        "ingest_firms", ROOT / "scripts" / "ingest_firms.py"
    )
    ingest_firms = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(ingest_firms)
    return ingest_firms


def validate_json_contracts() -> None:
    for path in (
        ROOT / "data/firms.json",
        ROOT / "data/dossiers.json",
        ROOT / "data/boundaries.geojson",
        ROOT / "data/kalimantan-indonesia.geojson",
        ROOT / "data/regions.json",
        ROOT / "data/dossiers/manifest.json",
        ROOT / "data/concessions/manifest.json",
        ROOT / "data/concessions/kalimantan/inventory/manifest.json",
        ROOT / "data/affiliated-land-holdings.json",
        ROOT / "data/affiliated-land-display-centers.json",
        ROOT / "data/admin-index.json",
        ROOT / "data/sources-manifest.json",
    ):
        with path.open(encoding="utf-8") as handle:
            json.load(handle)
        print(f"validated {path.relative_to(ROOT)}")


def validate_region_geometry() -> None:
    ingest_firms = load_ingest_firms()
    boundary, _ = ingest_firms.load_boundary_geometry(
        ROOT / "data/kalimantan-indonesia.geojson"
    )
    region_geometries = ingest_firms.build_region_geometries(boundary)
    assert tuple(region_geometries) == ingest_firms.REGION_ORDER
    assert all(
        region_geometries[region]["coordinates"] for region in ingest_firms.REGION_ORDER
    )
    print("validated Indonesia boundary split into 7 logical regions")


def validate_patched_html(html: str) -> Path:
    assert 'boundary.qualities.indexOf(state.boundary)' in html
    assert 'boundaryStatus(d).key !== state.boundary' not in html
    assert "pointInBoundaryGeometry" in html
    assert "boundaryGeometryDistanceKm" in html
    assert "jarak centroid kasar" not in html
    assert 'id="f-region"' in html
    assert "data/hotspots/manifest.json" in html
    assert "function selectRegion(regionId, preferredDate)" in html
    assert "function refreshNationalSummary()" in html
    assert "chunkedLoading: true" in html
    assert 'loadJson("data/firms.json")' not in html
    assert 'loadJson("data/dossiers.json")' not in html
    assert 'loadJson("data/boundaries.geojson")' not in html
    assert 'id="tog-inventory"' in html
    assert "function refreshConcessionInventoryLayer()" in html
    assert "NO FIRE ATTRIBUTION" in html
    assert 'id="primary-nav"' in html
    assert 'id="shared-filter-bar"' in html
    assert 'id="kpi-grid"' in html
    assert 'id="provenance-drawer"' in html
    assert "data/admin-index.json" in html
    assert "data/sources-manifest.json" in html
    assert "function setView(viewName, skipUrlSync)" in html
    assert "DATA UNAVAILABLE" in html

    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", html, flags=re.S | re.I)
    inline = "\n".join(script for script in scripts if script.strip())
    js_path = Path(tempfile.gettempdir()) / "meratus-inline.js"
    js_path.write_text(inline, encoding="utf-8")
    subprocess.run(["node", "--check", str(js_path)], check=True, cwd=ROOT)
    print("validated region/date lazy loading, concession inventory, v2 foundation shell, and inline JS syntax")
    return js_path


def main() -> None:
    scripts = sorted(str(path) for path in (ROOT / "scripts").glob("*.py"))
    run([sys.executable, "-m", "py_compile", *scripts], "python syntax")
    run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
        "python unit tests",
    )
    run(["node", str(ROOT / "tests/test_spatial_proximity.js")], "spatial proximity")
    run(["node", str(ROOT / "tests/test_v2_frontend_runtime.js")], "v2 frontend runtime")

    validate_json_contracts()
    validate_region_geometry()

    run(
        [sys.executable, str(ROOT / "scripts/bootstrap_hotspot_shards.py"), "--check", "--force"],
        "hotspot shard contract",
    )
    run(
        [sys.executable, str(ROOT / "scripts/v2_contracts.py"), "--check"],
        "v2 provenance & shared filter contracts",
    )

    build_dashboard = importlib.util.spec_from_file_location(
        "build_dashboard", ROOT / "scripts" / "build_dashboard.py"
    )
    assert build_dashboard and build_dashboard.loader
    module = importlib.util.module_from_spec(build_dashboard)
    build_dashboard.loader.exec_module(module)

    source = (ROOT / "index.html").read_text(encoding="utf-8")
    patched = module.build_patched_html(source)
    validate_patched_html(patched)
    print("validate_build: all checks passed")


if __name__ == "__main__":
    main()
