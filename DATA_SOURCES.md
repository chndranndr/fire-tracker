# MERATUS data sources and licensing

This document describes third-party datasets and citations used by MERATUS. It does **not** grant rights to redistribute those datasets. Only the MERATUS source code is covered by the repository `LICENSE` (MIT). Each dataset remains subject to its provider's terms.

## NASA FIRMS (VIIRS active fire)

| Field | Value |
| --- | --- |
| Source | NASA Fire Information for Resource Management System (FIRMS) |
| URL | https://firms.modaps.eosdis.nasa.gov/ |
| Role in MERATUS | Near-real-time hotspot detections (S-NPP, NOAA-20, NOAA-21) |
| Retrieval | Hourly GitHub Actions ingest via NASA MAP key; filtered to Indonesia bbox and logical regions |
| Quality label | Satellite thermal detection; not ground-verified fire |
| Licensing / terms | NASA open data policy; MAP key required for automated access |
| Caveats | Detections ≠ confirmed wildfire; cloud, industrial heat, and sensor artifacts possible |

## BIG / Kebijakan Satu Peta (public concession boundaries)

| Field | Value |
| --- | --- |
| Source | Badan Informasi Geospasial (BIG) — Satu Peta / open concession layers |
| URL | https://tanahair.indonesia.go.id/ |
| Role in MERATUS | Nationwide generic concession inventory polygons (mining, forestry, oil palm where available) |
| Retrieval | `scripts/ingest_concessions.py` fetches BIG/GFW sources, normalizes features, and writes region-sharded GeoJSON under `data/concessions/<region>/inventory/` |
| Quality label | Official administrative geometry where sourced from BIG; GFW-derived layers tagged separately |
| Licensing / terms | Indonesian government open-data terms; verify before republication |
| Caveats | Inventory catalog ≠ investigative dossier boundaries; geometry ≠ operational status |

## Global Forest Watch (GFW)

| Field | Value |
| --- | --- |
| Source | World Resources Institute — Global Forest Watch |
| URL | https://www.globalforestwatch.org/ |
| Role in MERATUS | Oil-palm and forestry concession inventory layers (`oil-palm-gfw`, forestry variants) |
| Retrieval | Ingest scripts probe and normalize GFW-derived GeoJSON per region |
| Quality label | Third-party spatial inventory; provenance tagged per feature |
| Licensing / terms | GFW data policy — https://www.globalforestwatch.org/terms-of-use |
| Caveats | Broad inventory layer; not the same as WALHI investigative overlay claims |

## Natural Earth

| Field | Value |
| --- | --- |
| Source | Natural Earth |
| URL | https://www.naturalearthdata.com/ |
| Role in MERATUS | Basemap context / country outlines where referenced |
| Retrieval | Static reference data |
| Quality label | Cartographic generalization |
| Licensing / terms | Public domain |
| Caveats | Not used for legal boundary adjudication |

## WALHI-derived claims and media citations

| Field | Value |
| --- | --- |
| Source | WALHI press/analysis as reported by Kompas.id, Detik, IniBalikpapan, and related outlets |
| URL | See `data/dossiers/kalimantan.json` source entries |
| Role in MERATUS | ConcessionClaim overlay counts (Jan–Jul 2026 Kalimantan context) |
| Retrieval | Human-curated dossier JSON with NamedSource IDs |
| Quality label | Investigative/media claim — separate evidence layer from FIRMS detections |
| Licensing / terms | Original articles retain publisher copyright; cite URLs directly |
| Caveats | Hotspot-in-concession ≠ fire attribution; not a live GIS join |

## SIPONGI / Kemenhut

| Field | Value |
| --- | --- |
| Source | Kementerian Kehutanan — SIPONGI / operasi terpadu karhutla |
| URL | https://www.menlhk.go.id/ ; SIPONGI portal |
| Role in MERATUS | High-confidence fallback hotspot counts when FIRMS layer unavailable |
| Retrieval | Curated fallback block in dossier JSON |
| Quality label | Government operational reporting |
| Licensing / terms | Government publication terms |
| Caveats | Fallback only; periods and provinces are explicitly scoped in data |

## Corporate, IDX, media, and OSINT sources

| Field | Value |
| --- | --- |
| Source | Company sites, IDX filings, ANTARA, CNN Indonesia, The Gecko Project, Tirto, Golkar.or.id, etc. |
| URL | Per-entry in `data/dossiers/kalimantan.json` |
| Role in MERATUS | Control and PoliticalTie evidence with NamedSource citations |
| Retrieval | Human verification; homepage-only citations rejected for sensitive claims |
| Quality label | Varies (`tinggi` / `sedang` / `UNKNOWN` / `TIDAK TERPETAKAN`) |
| Licensing / terms | Each publisher's terms apply |
| Caveats | Political ties on individuals ≠ company fire guilt; UBO gaps stay explicit |

## Generated runtime shards

| Field | Value |
| --- | --- |
| Source | Produced by `scripts/ingest_firms.py` from NASA FIRMS |
| Path | `data/hotspots/<region>/<date>.json`, `data/hotspots/manifest.json` |
| Role in MERATUS | Production dashboard lazy-load contract |
| Retrieval | CI artifact on hourly schedule; not committed every hour to source history |
| Quality label | Validated ingest with last-known-good fallback |
| Licensing / terms | Derived from NASA FIRMS; same caveats as above |
| Caveats | Timestamped counts in manifest; see `data/hotspots/status.json` |
