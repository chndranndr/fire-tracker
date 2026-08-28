# ADR 007 — Investigative dossier vs generic concession inventory

## Status

Accepted

## Konteks

MERATUS serves two different concession-related surfaces: a broad public inventory (GFW, BIG-derived layers) and a curated Kalimantan investigative dossier with OSINT citations, control graph, and political ties. Mixing them would blur provenance and inflate sensitive claims.

## Keputusan

- **Generic concession inventory** — `data/concessions/<region>/inventory/` loaded on demand; nationwide catalog, no political graph.
- **Investigative dossier** — `data/dossiers/<region>.json` with explicit evidence layers, caveats, and NamedSource citations.
- Kalimantan is the only region with a full dossier today; other regions may show hotspots and inventory without dossier polygons.
- UI toggles and copy keep inventory and dossier boundaries visually and semantically distinct.

## Konsekuensi

- `patch_concession_inventory_dashboard.py` runs after region patch; inventory toggle is separate from dossier boundary layer.
- Sensitive citation audit applies to dossier/political tie sources, not to every inventory polygon.
- Nationwide scope in README must not imply nationwide investigative completeness.
