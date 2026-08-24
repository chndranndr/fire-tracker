# Indonesia concession inventory

MERATUS keeps two concession concepts separate:

1. **Investigative dossier boundaries** — curated polygons linked to researched company/control dossiers.
2. **Generic concession inventory** — broad public licence/concession polygons used for map exploration and spatial context.

The generic inventory does **not** imply fire causation, illegality, wrongdoing, political affiliation, or beneficial ownership beyond attributes explicitly present in the cited source.

## One-run ingestion

`scripts/ingest_concessions.py` performs one Indonesia-wide run. Each upstream layer is fetched once using the same Indonesia bbox as the FIRMS pipeline, normalized, and then partitioned into the seven logical MERATUS regions:

- `sumatra`
- `jawa`
- `kalimantan`
- `sulawesi`
- `bali-nusra`
- `maluku`
- `papua`

There is no seven-region request matrix.

Generated files follow this layout:

```text
data/concessions/
├── inventory-manifest.json
├── inventory-status.json
├── manifest.json
└── <region>/
    └── inventory/
        ├── manifest.json
        ├── status.json
        ├── forestry-ha.geojson
        ├── forestry-hti.geojson
        ├── forestry-re.geojson
        ├── mining.geojson
        ├── oil-palm-official.geojson
        └── oil-palm-gfw.geojson
```

Only shards with records are written for a region.

## Provenance and quality

The official national baseline is fetched from BIG Kebijakan Satu Peta:

- IUPHHK-HA
- IUPHHK-HTI
- IUPHHK-RE
- WIUP

Selected BIG plantation-location layers are marked `OFFICIAL`, but their public coverage is incomplete nationally. The GFW oil-palm compilation is supplementary and remains marked `GFW`; it must not be presented as equivalent to an authoritative current cadastral record.

Every feature keeps source dataset identifiers, source URL, retrieval timestamp, and quality label. Geometry is simplified for browser display, so authoritative boundary checks should use the upstream source.

## Region assignment

National forestry/mining and GFW features are assigned primarily by polygon membership against the checked-in Indonesia/region mask. BIG national records may use an Indonesia-only fallback for tiny components omitted by the coarse Natural Earth geometry. GFW does not use that broad-bbox fallback.

The four currently exposed BIG plantation layers are district-specific to Kutai Barat, Kutai Kartanegara, Kutai Timur, and Paser, so they are explicitly pinned to `kalimantan` rather than allowing tiny/offshore geometry components to be guessed into another logical region.

## Refresh behavior

`.github/workflows/concessions.yml` refreshes the whole Indonesia inventory in one job on its schedule or manual run. Required BIG forestry/mining source failures fail closed and preserve the previous inventory. Optional-source failures preserve only last-known-good records belonging to the failed `sourceDataset`.

Generated data paths do not trigger another live refresh, and superseded refresh runs are cancelled so an older branch SHA cannot race newer code.
