# ADR 006 — Runtime data publication strategy

## Status

Accepted

## Konteks

Hourly FIRMS ingest previously committed refreshed JSON to `main`, bloating git history with runtime blobs while providing little source-control value.

## Keputusan

- Scheduled ingest writes runtime shards in the CI workspace only.
- GitHub Pages artifacts carry the fresh dataset to production.
- Source history keeps periodic or bootstrap snapshots for reproducibility, not hourly commits.
- Last-known-good semantics remain in `data/hotspots/status.json` when ingest fails.

## Konsekuensi

- `firms-nrt.yml` no longer pushes data commits on schedule.
- Production freshness depends on the hourly workflow artifact deploy.
- README and DATA_SOURCES.md document the split between code license and third-party data terms.
