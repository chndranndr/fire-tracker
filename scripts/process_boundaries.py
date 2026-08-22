import json
from pathlib import Path
from collections import Counter, defaultdict
from shapely.geometry import shape
from shapely.validation import explain_validity

ROOT = Path('research-output')
RAW = ROOT / 'big_matches.geojson'
OUT = ROOT / 'final_boundaries.geojson'
REPORT = ROOT / 'validation_report.json'

INCLUDE = {'kpc', 'agm', 'bre', 'dwima', 'kiani'}
NAMES = {
    'kpc': 'PT Kaltim Prima Coal',
    'agm': 'PT Antang Gunung Meratus',
    'bre': 'PT Bhumi Rantau Energi',
    'dwima': 'PT Dwima Intiga',
    'kiani': 'PT Kiani Lestari',
}
EXPECTED_SOURCE_NAMES = {
    'kpc': 'KALTIM PRIMA COAL',
    'agm': 'ANTANG GUNUNG MERATUS',
    'bre': 'BHUMI RANTAU ENERGI',
    'dwima': 'PT DWIMA INTIGA',
    'kiani': 'PT KIANI LESTARI',
}
LAYER_URL = {
    1: 'https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/PERIZINAN_DAN_PERTANAHAN/MapServer/1',
    2: 'https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/PERIZINAN_DAN_PERTANAHAN/MapServer/2',
    4: 'https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/PERIZINAN_DAN_PERTANAHAN/MapServer/4',
}
LAYER_LABEL = {
    1: 'Peta IUPHHK-HA / izin pemanfaatan hutan alam',
    2: 'Peta IUPHHK-HTI / izin hutan tanaman industri',
    4: 'Peta Wilayah Izin Usaha Pertambangan (WIUP)',
}
# Broad Indonesian Kalimantan screening envelope. This deliberately rejects obvious
# points in Malaysia/open sea; it is not used to create or alter geometry.
KALIMANTAN_ID_BBOX = (108.0, -4.6, 119.5, 1.85)


def clean_coords(node):
    # ArcGIS sometimes serializes XYZM positions such as [lon, lat, 0, null].
    # GeoJSON here is normalized to the first two coordinates only; vertices are unchanged.
    if isinstance(node, list):
        if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            return [float(node[0]), float(node[1])]
        return [clean_coords(v) for v in node]
    raise TypeError(f'Unexpected coordinate node: {type(node).__name__}')


def source_name(props):
    return (props.get('nmoprt') or props.get('namobj') or '').strip()


def source_record_id(props):
    return props.get('objectid_1', props.get('objectid'))


def permit_no(props):
    return str(props.get('skblok') or props.get('no_sk') or '').strip()


def source_area(props):
    return props.get('lublok', props.get('lssk'))


def make_source(did, layer_id, props):
    record = source_record_id(props)
    operator = source_name(props)
    permit = permit_no(props)
    area = source_area(props)
    parts = [
        'Badan Informasi Geospasial (BIG), Kebijakan Satu Peta',
        LAYER_LABEL[layer_id],
        f'operator={operator}',
    ]
    if permit:
        parts.append(f'izin/SK={permit}')
    if area not in (None, ''):
        parts.append(f'luas_sumber_ha={area}')
    if record not in (None, ''):
        parts.append(f'record={record}')
    return '; '.join(parts)


raw = json.loads(RAW.read_text(encoding='utf-8'))
features = []
validation = []
excluded = []

for raw_feature in raw.get('features', []):
    research = raw_feature.get('_research') or {}
    did = research.get('dossierId')
    props = raw_feature.get('properties') or {}
    layer_id = research.get('layerId')

    if did not in INCLUDE:
        if did in {'kideco', 'adaro'}:
            excluded.append({
                'dossierId': did,
                'reason': 'official BIG record is historical/expired; excluded from current dashboard boundary',
                'operator': source_name(props),
                'permit': permit_no(props),
                'sourceEndEpochMs': props.get('datend'),
                'sourceAreaHa': source_area(props),
                'sourceRecordId': source_record_id(props),
            })
        continue

    actual = source_name(props)
    expected = EXPECTED_SOURCE_NAMES[did]
    if actual.upper() != expected.upper():
        raise ValueError(f'{did}: source operator mismatch: {actual!r} != {expected!r}')

    geometry = {
        'type': raw_feature['geometry']['type'],
        'coordinates': clean_coords(raw_feature['geometry']['coordinates']),
    }
    if geometry['type'] not in {'Polygon', 'MultiPolygon'}:
        raise ValueError(f'{did}: unsupported geometry {geometry["type"]}')

    geom = shape(geometry)
    minx, miny, maxx, maxy = geom.bounds
    env = KALIMANTAN_ID_BBOX
    bbox_ok = minx >= env[0] and miny >= env[1] and maxx <= env[2] and maxy <= env[3]
    topo_ok = geom.is_valid and not geom.is_empty and geom.area > 0
    if not bbox_ok or not topo_ok:
        raise ValueError(
            f'{did}: invalid source geometry: bbox={geom.bounds}, '
            f'bbox_ok={bbox_ok}, validity={explain_validity(geom)}'
        )

    source_url = LAYER_URL[layer_id]
    feature = {
        'type': 'Feature',
        'properties': {
            'dossierId': did,
            'name': NAMES[did],
            'quality': 'OFFICIAL',
            'source': make_source(did, layer_id, props),
            'sourceUrl': source_url,
        },
        'geometry': geometry,
    }
    features.append(feature)
    validation.append({
        'dossierId': did,
        'name': NAMES[did],
        'sourceOperator': actual,
        'layerId': layer_id,
        'sourceRecordId': source_record_id(props),
        'permit': permit_no(props),
        'sourceAreaHa': source_area(props),
        'geometryType': geometry['type'],
        'bounds': [minx, miny, maxx, maxy],
        'isValid': geom.is_valid,
        'validity': explain_validity(geom),
        'isEmpty': geom.is_empty,
        'bboxWithinIndonesianKalimantanScreen': bbox_ok,
        'coordinateDimensions': 2,
    })

final = {
    'type': 'FeatureCollection',
    'name': 'meratus-concession-boundaries',
    'crs': {
        'type': 'name',
        'properties': {'name': 'urn:ogc:def:crs:OGC:1.3:CRS84'},
    },
    'features': features,
}
OUT.write_text(json.dumps(final, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

counts = Counter(f['properties']['dossierId'] for f in features)
report = {
    'ok': True,
    'featureCount': len(features),
    'counts': dict(sorted(counts.items())),
    'includedDossierIds': sorted(counts),
    'excludedHistoricalOfficialRecords': excluded,
    'validation': validation,
}
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
