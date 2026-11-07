#!/usr/bin/env python3
"""Single entry point for the production MERATUS dashboard build."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def bootstrap_hotspots(force: bool = False) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / "bootstrap_hotspot_shards.py")]
    if force:
        cmd.append("--force")
    subprocess.run(cmd, check=True, cwd=ROOT)


def build_v2_contracts(check_only: bool = False) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / "v2_contracts.py")]
    if check_only:
        cmd.append("--check")
    subprocess.run(cmd, check=True, cwd=ROOT)


def build_patched_html(source: str) -> str:
    land = load_module(
        "patch_land_holdings_dashboard",
        ROOT / "scripts" / "patch_land_holdings_dashboard.py",
    )
    region = load_module(
        "patch_region_dashboard",
        ROOT / "scripts" / "patch_region_dashboard.py",
    )
    inventory = load_module(
        "patch_concession_inventory_dashboard",
        ROOT / "scripts" / "patch_concession_inventory_dashboard.py",
    )
    v2_foundation = load_module(
        "patch_v2_foundation_dashboard",
        ROOT / "scripts" / "patch_v2_foundation_dashboard.py",
    )
    v2_concessions_map = load_module(
        "patch_v2_concessions_map_dashboard",
        ROOT / "scripts" / "patch_v2_concessions_map_dashboard.py",
    )
    html = land.build_patched_index(source)
    html = region.build_patched_index(html)
    html = inventory.build_patched_index(html)
    inventory.validate_patched(html)
    html = v2_foundation.build_patched_index(html)
    v2_foundation.validate_patched(html)
    html = v2_concessions_map.build_patched_index(html)
    v2_concessions_map.validate_patched(html)
    return html


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the production MERATUS dashboard")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate patchability without writing index.html",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Skip hotspot shard bootstrap (use when manifest already present)",
    )
    parser.add_argument(
        "--force-bootstrap",
        action="store_true",
        help="Pass --force to bootstrap_hotspot_shards.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=INDEX,
        help="Write patched HTML here (default: index.html)",
    )
    args = parser.parse_args()

    if not args.skip_bootstrap:
        bootstrap_hotspots(force=args.force_bootstrap)

    build_v2_contracts(check_only=args.check)

    use_crlf = b"\r\n" in INDEX.read_bytes()
    source = INDEX.read_text(encoding="utf-8")
    patched = build_patched_html(source)

    if args.check:
        print("Dashboard build check passed.")
        return

    with args.output.open("w", encoding="utf-8", newline="\r\n" if use_crlf else "\n") as handle:
        handle.write(patched)
    print(f"Wrote patched dashboard to {args.output}")


if __name__ == "__main__":
    main()
