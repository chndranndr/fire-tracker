# ADR 004 — Region and date hotspot sharding

## Status

Accepted

## Konteks

Legacy `data/firms.json` shipped the entire Kalimantan FIRMS window in one file. Nationwide coverage would make initial payload too large for static hosting and slow marker clustering in the browser.

## Keputusan

- Hotspots are stored as `data/hotspots/<region>/<YYYY-MM-DD>.json`.
- `data/hotspots/manifest.json` indexes regions, dates, counts, and URLs.
- The frontend loads national summary from the manifest and fetches a shard only when the user selects region and date.
- Seven logical Indonesia regions are defined in `data/regions.json` and used during ingest classification.

## Konsekuensi

- `data/firms.json` remains a compatibility subset during transition.
- Ingest must update manifest metadata (`lastSuccessfulSync`, platform list, counts).
- Tests assert the patched dashboard no longer bulk-loads legacy JSON paths.
