# MERATUS Dashboard Improvement Roadmap

Status: proposed implementation plan  
Last updated: 2026-08-22

## Objective

Improve MERATUS so the dashboard is more informative and efficient without turning it into a generic BI dashboard. The product should remain an investigative map / intelligence console centered on three questions:

1. Where are recent satellite fire detections?
2. What verified concession boundary or concession claim is associated with the selected dossier?
3. What public ownership/control and political-affiliation evidence is available, while keeping those evidence layers separate from fire attribution?

The dashboard must continue to respect the project evidence model:

- Satellite detection is not field-verified fire.
- A hotspot inside or near a concession is not evidence that the concession holder caused the fire.
- Political affiliation is contextual public-record information, not fire attribution.
- Boundary provenance and quality must remain visible.

---

## Current assessment

The existing three-column layout is fundamentally good:

- left: search, filters, findings, dossier list;
- center: map / network graph;
- right: dossier inspector;
- bottom: time scrubber.

The main issue is information hierarchy, not lack of features. Too many controls and evidence sections are visible at the same visual priority, while some critical distinctions are not visually obvious enough.

The recommended direction is therefore to **reduce always-visible UI**, improve evidence-quality signaling, make the inspector summary-first, and improve mobile interaction.

---

# 1. UI / UX improvements

## P0 — Boundary quality must be visually explicit

### Problem

Boundary polygons currently look too similar even when provenance differs. An official BIG boundary and a legacy GFW boundary should not communicate the same evidentiary strength.

### Recommendation

Use the same amber visual family but vary line treatment and opacity:

| Boundary quality | Line | Fill | Meaning |
|---|---|---|---|
| `OFFICIAL` | solid | normal | verified official public boundary |
| `GFW` | dashed | lower opacity | sourced from GFW/WRI legacy concession dataset |
| `PERKIRAAN` | dotted / stronger dash | very low opacity | approximate only |
| no polygon | no polygon | none | centroid/location fallback only |

Do not introduce many unrelated colors. Reliability should be communicated mainly through line style, opacity, label, and provenance text.

### Acceptance criteria

- `OFFICIAL`, `GFW`, and `PERKIRAAN` are visually distinguishable without opening the inspector.
- Legend explains boundary quality in one compact block.
- Selected polygon may receive a white/high-contrast outline while keeping its provenance style visible.

---

## P0 — Hide centroid markers when a real polygon exists

### Problem

Centroid markers are useful as fallbacks, but once a verified polygon exists they add clutter and may imply that the hotspot number shown on the marker belongs to that exact point.

### Recommendation

Only show a centroid marker when the dossier has no polygon geometry.

Expected behavior:

- polygon exists -> show polygon, no centroid by default;
- polygon unavailable -> show centroid/location marker with explicit `BOUNDARY UNAVAILABLE` state;
- optional advanced layer control may allow all centroids to be displayed manually.

### Acceptance criteria

- No default centroid marker for dossiers with polygons.
- Fallback markers are visually different from concession boundaries.
- Clicking fallback markers still opens the dossier inspector.

---

## P0 — Fix mobile navigation instead of hiding core functionality

### Problem

The compact mobile layout currently hides several filters, layer controls, the findings box, and the dossier list. This reduces clutter but also removes the main exploration workflow.

### Recommendation

Use the map as the primary mobile surface and move dossiers into a bottom sheet.

Suggested mobile structure:

```text
+---------------------------+
| MERATUS     MAP | NETWORK |
+---------------------------+
|                           |
|            MAP            |
|                           |
+---------------------------+
| 12 DOSSIERS          ^    |
| KPC   3421   OFFICIAL     |
| AGM   1892   OFFICIAL     |
+---------------------------+
```

The bottom sheet should have three states:

1. collapsed: count + selected dossier summary;
2. half-height: searchable dossier list;
3. expanded: inspector / evidence details.

### Acceptance criteria

- Dossier list remains reachable on mobile in one interaction.
- Search remains available.
- Map remains visible while browsing dossiers.
- No horizontal overflow.

---

## P1 — Simplify the left sidebar

### Problem

The left sidebar currently has search, four filters, layer toggles, findings, and the full dossier list. This is too dense for a 280 px column.

### Recommendation

Default left panel:

```text
Search

[All sectors v] [Filter +]

12 CONCESSIONS
KPC                    3,421
Tambang · Kaltim   OFFICIAL

AGM                    1,892
Tambang · Kalsel   OFFICIAL
```

Move secondary controls behind `Filter +`:

- province;
- political tie;
- FIRMS confidence;
- optional boundary quality.

Separate FIRMS-specific controls from dossier filters visually.

### Acceptance criteria

- Only search and one primary filter are always visible.
- Secondary filters are available in a compact popover / disclosure panel.
- Dossier rows show boundary state (`OFFICIAL`, `GFW`, `NO BOUNDARY`).
- Dossiers remain sortable by WALHI hotspot claim count by default.

---

## P1 — Make the inspector summary-first

### Problem

The inspector currently exposes many evidence sections at once: boundary, control/UBO, political ties, caveats, named sources, and layer notes. The most important answer is therefore buried inside evidence detail.

### Recommendation

The inspector header should answer the core questions immediately.

Example:

```text
PT KALTIM PRIMA COAL
Tambang · Kalimantan Timur

3,421
HOTSPOT — WALHI CLAIM

BOUNDARY   OFFICIAL
CONTROL    Bumi Resources / Bakrie
POLITICAL  Golkar
```

Default-open sections:

1. Boundary
2. Ownership / Control
3. Political ties

Collapsed by default:

- Sources (n)
- Caveats (n)
- Technical details
- Methodology / evidence-layer explanation

### Acceptance criteria

A user should understand the dossier's core state within roughly 2-3 seconds without scrolling.

---

## P1 — Separate WALHI claims from FIRMS detections more explicitly

### Problem

The dashboard displays both WALHI hotspot counts and FIRMS satellite detections. Even with caveats, users may assume both numbers are the same dataset or that MERATUS itself has spatially joined every FIRMS detection to a concession polygon.

### Recommendation

Never label both simply as `hotspot` without the source.

Use explicit labels:

```text
WALHI CLAIM
3,421 hotspots
```

versus:

```text
FIRMS
12,442 satellite detections shown
```

### Acceptance criteria

- Source is visible beside every aggregate count.
- FIRMS points are consistently labeled `satellite detections`.
- WALHI numbers are consistently labeled `WALHI claim` / `WALHI-reported hotspots`.
- No UI text implies a new FIRMS x concession attribution unless such analysis is explicitly added and documented later.

---

## P1 — Move aggregate findings out of the crowded sidebar

### Problem

The `Temuan` card consumes substantial sidebar space and mixes aggregate WALHI numbers with specific political-network examples.

### Recommendation

Move the aggregate statement into a compact banner above or over the map:

```text
WALHI · Jan-Jul 2026
74% of reported hotspots were stated to be within concessions
25,524 / 34,262
[Methodology]
```

Do not make specific political links the default top-level headline. Political-network context is better exposed after selecting a dossier or entering network mode.

### Acceptance criteria

- Aggregate claim remains visible.
- Source and reporting period are visible.
- Political ties are not visually presented as causal fire findings.

---

## P1 — Rename `GRAF` to `JARINGAN`

`PETA | JARINGAN` communicates the user intent more clearly than `PETA | GRAF`.

Network mode should focus on the selected dossier neighborhood by default rather than rendering an unnecessarily large graph.

Suggested relationship view:

```text
KPC
 |
Bumi Resources
 |
Bakrie
 |
Golkar
```

Every edge should retain a relationship type such as ownership, control, office, campaign, kinship, cabinet, or other documented relation.

---

## P2 — Add compact dataset-state indicators to the header

Recommended header:

```text
MERATUS
20,500 FIRMS detections · 12 dossiers · 8/12 verified boundaries

                         PETA | JARINGAN
```

These values must be computed from loaded data rather than hard-coded.

Useful state indicators:

- FIRMS detection count;
- dossier count;
- number of dossiers with polygon boundaries;
- last successful FIRMS sync;
- newest detection timestamp.

---

## Features NOT recommended

Avoid adding the following unless a future analytical requirement clearly justifies them:

- multiple KPI cards;
- pie charts;
- generic bar-chart dashboards;
- decorative dashboards unrelated to spatial investigation;
- large default network graphs;
- excessive color coding.

MERATUS is more useful as an investigative geospatial console than as a conventional BI dashboard.

---

# 2. Data freshness upgrade

## Current state

The current FIRMS file is a static snapshot sourced from:

- NASA FIRMS
- Suomi-NPP VIIRS Collection 2
- Southeast Asia 7-day CSV

At the time of this roadmap, `data/firms.json` reports:

- `fetched`: `2026-08-21`
- source: `NASA FIRMS Suomi-NPP VIIRS C2 SouthEast Asia 7-day CSV`
- Kalimantan filter with Sarawak/Sabah excluded
- 20,500 stored detections

This means the dashboard is only as fresh as the latest committed snapshot even though NASA FIRMS itself publishes near-real-time active-fire data much more frequently.

Google's wildfire products also use multiple satellite sources and automated fire-boundary processing, so MERATUS should not claim to be more real-time than Google Maps unless measured evidence supports that statement.

MERATUS should instead optimize for:

1. fast ingestion of authoritative active-fire detections;
2. transparent source metadata;
3. reproducible history;
4. concession/context overlays Google Maps does not provide.

---

## P0 — Move from manual/static FIRMS snapshot to scheduled NRT ingestion

### Target architecture

```text
NASA FIRMS NRT
├── VIIRS S-NPP
├── VIIRS NOAA-20
└── VIIRS NOAA-21
        |
        v
scheduled ingest
        |
        v
validate + normalize + Kalimantan filter
        |
        v
dedupe
        |
        +--> latest dataset
        |
        +--> historical archive
        |
        v
MERATUS dashboard
```

### Why multiple VIIRS platforms

The current dashboard uses only Suomi-NPP. Adding NOAA-20 and NOAA-21 improves observation opportunities and reduces reliance on a single satellite/platform.

This does not make VIIRS continuous real-time imagery; all three remain polar-orbiting satellites. The goal is to reduce time-to-ingest after new observations become available.

---

## P0 — Refresh every 30-60 minutes

Recommended initial cadence: **hourly**.

Rationale:

- sufficient for a static GitHub Pages architecture;
- avoids pretending the satellite itself observes every 30 minutes;
- quickly picks up new FIRMS records after publication;
- compatible with GitHub Actions scheduling constraints.

If the pipeline later moves off GitHub Pages and operational requirements justify it, a shorter cadence may be evaluated.

### Required behavior

Each run should:

1. fetch source datasets;
2. reject malformed responses;
3. filter to the intended Indonesian Kalimantan extent;
4. normalize sensor/platform fields;
5. deduplicate records;
6. preserve acquisition timestamp;
7. write a compact current dataset;
8. record pipeline metadata;
9. fail closed if the new dataset is obviously incomplete or corrupt.

Do **not** replace a healthy current file with an empty or suspicious fetch result.

---

## P0 — Add explicit freshness metadata

Recommended `meta` fields:

```json
{
  "source": "NASA FIRMS NRT",
  "platforms": ["S-NPP", "NOAA-20", "NOAA-21"],
  "lastSuccessfulSync": "2026-08-22T12:42:00+07:00",
  "newestDetectionUtc": "2026-08-22T05:58:00Z",
  "oldestDetectionUtc": "...",
  "count": 12345,
  "pipelineVersion": "2",
  "stale": false
}
```

The UI should display both:

- last successful sync;
- age of newest satellite detection.

These are different concepts.

---

## P0 — Add a visible data freshness indicator

Normal state:

```text
FIRMS NRT
Updated 12:42 WIB
Newest detection 11:58 WIB
Data age 44m
```

Potential stale state:

```text
DATA STALE
Last successful sync 8h ago
```

Avoid calling the product `LIVE` unless the actual latency and observation model justify that wording. `Near-real-time` or `NRT` is more accurate.

Suggested status thresholds can initially be conservative and configurable, for example:

- healthy: sync completed within 2 hours;
- delayed: 2-6 hours;
- stale: >6 hours;

A stale satellite observation does not necessarily mean pipeline failure, because satellite overpass timing and cloud cover can affect detections. Therefore distinguish:

- `pipeline stale`;
- `newest observation age`.

---

## P1 — Separate current view from history

Instead of keeping one large rolling file indefinitely, use two concepts:

```text
data/firms-latest.json
archive/firms/YYYY/MM/DD.json
```

or an equivalent generated structure.

For GitHub Pages, keep the current client payload bounded so map rendering stays fast.

Possible default window:

- latest 24h / 48h for initial map;
- 7-day history loaded on demand.

Keep the exact retention choice configurable after measuring file size and rendering performance.

---

## P1 — Deduplicate multi-platform detections carefully

Adding three VIIRS platforms will introduce observations of the same fire at different times and potentially nearby coordinates.

Do not aggressively collapse observations simply because they are geographically close.

Recommended model:

- preserve raw observations as separate records;
- assign a deterministic observation ID from platform + acquisition date/time + coordinates;
- only remove exact or clearly duplicated upstream records;
- treat clustering as a visualization concern rather than destructive data processing.

---

## P1 — Preserve sensor provenance in the UI

Each detection inspector should show at least:

- platform / satellite;
- acquisition date/time;
- confidence;
- FRP;
- brightness fields when available;
- source `NASA FIRMS`.

The dashboard should be able to filter by platform if needed, but this should remain an advanced control rather than a permanent primary filter.

---

## P1 — Add ingestion validation and rollback protection

Before publishing a newly fetched dataset, validate:

- JSON/schema validity;
- point count is non-zero;
- coordinates fall within expected broad Kalimantan bounds;
- lat/lon order is correct;
- acquisition times parse correctly;
- platforms are recognized;
- record-count movement is not implausibly catastrophic without explanation.

If validation fails:

- keep the previous known-good file;
- write failure metadata/logs;
- expose a stale warning in the dashboard.

---

## P2 — Consider a second near-real-time fire-extent layer later

VIIRS detections provide precise thermal-detection points but are constrained by polar-orbit revisit timing.

A future version could evaluate a separate derived fire-extent / geostationary-satellite layer with higher temporal frequency.

This should be a separate evidence layer, not a replacement for VIIRS points.

Do not implement this until a source has:

- clear public access;
- acceptable licensing;
- stable API/download behavior;
- documented latency and spatial resolution;
- defensible methodology.

---

# 3. Proposed implementation phases

## Phase 1 — Clarity and evidence quality

Priority: P0 UI work.

- boundary styling by quality;
- centroid fallback only;
- explicit WALHI vs FIRMS terminology;
- mobile dossier bottom sheet;
- compact legend;
- basic header data-state counts.

Outcome: dashboard becomes easier to understand without changing the evidence model.

## Phase 2 — Near-real-time ingestion

Priority: P0 data work.

- scheduled FIRMS ingestion;
- S-NPP + NOAA-20 + NOAA-21;
- normalization and dedupe;
- validation and previous-good rollback;
- freshness metadata;
- UI freshness indicator.

Outcome: MERATUS no longer depends on manually refreshed FIRMS snapshots.

## Phase 3 — Information hierarchy

- compact sidebar + secondary filter disclosure;
- summary-first inspector;
- collapsible evidence/source sections;
- `PETA | JARINGAN` terminology;
- selected-dossier network neighborhood.

Outcome: faster investigation with less visual noise.

## Phase 4 — Performance and history

- bounded latest payload;
- archive / history loading strategy;
- lazy-load historical detections;
- optimize marker clustering and GeoJSON rendering;
- measure mobile performance.

---

# 4. Success criteria

The redesign should be considered successful when:

1. A first-time user can identify what the red points represent without reading methodology documentation.
2. `OFFICIAL`, `GFW`, and missing-boundary states are immediately distinguishable.
3. A selected dossier reveals company, WALHI claim count, boundary quality, ownership/control, and political tie status without scrolling on a normal desktop viewport.
4. Mobile users can search and browse all dossiers without losing the map.
5. The dashboard exposes last sync time and newest FIRMS observation age.
6. A failed ingestion cannot silently replace a valid dataset with bad data.
7. No UI text converts correlation, proximity, political affiliation, or concession overlap into a causal allegation.
8. The interface remains a map-first investigative tool rather than a generic BI dashboard.

---

# 5. Reference sources for freshness design

- NASA FIRMS active-fire data and API: https://firms.modaps.eosdis.nasa.gov/
- NASA FIRMS Area API: https://firms.modaps.eosdis.nasa.gov/api/area/
- NASA FIRMS VIIRS active-fire description: https://firms.modaps.eosdis.nasa.gov/content/descriptions/FIRMS_VIIRS_Firehotspots.html
- Google Maps wildfire information: https://support.google.com/maps/answer/9985621
- Google Research, real-time wildfire-boundary tracking: https://research.google/blog/real-time-tracking-of-wildfire-boundaries-using-satellite-imagery/

These external systems are reference points for latency and product design only. MERATUS should state its own measured data timestamps rather than claiming parity or superiority without evidence.
