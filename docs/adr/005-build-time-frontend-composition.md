# ADR 005 — Build-time frontend composition

## Status

Accepted

## Konteks

Production dashboard features (land-holding overlay, region lazy loading, concession inventory layer) are implemented as ordered patches on a stable `index.html` template. Patch order was duplicated across README and multiple workflows, which invited drift.

## Keputusan

- Keep `index.html` as the vanilla source template; do not merge patch logic into one giant file.
- Apply patches in this order at build time:
  1. `patch_land_holdings_dashboard.py`
  2. `patch_region_dashboard.py`
  3. `patch_concession_inventory_dashboard.py`
- `scripts/build_dashboard.py` is the single documented build entry point.
- `scripts/validate_build.py` validates patched invariants and `node --check` on inline JavaScript.

## Konsekuensi

- Local developers and CI call the same build command.
- Patch scripts remain independently testable.
- ADR 003 (single-file delivery) is superseded for runtime data loading but the static HTML delivery model remains.
