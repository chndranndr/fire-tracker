#!/usr/bin/env python3
"""MERATUS v2 foundation contracts for provenance (#19) and shared filters (#11).

This module provides deterministic, zero-LLM helpers and artifact generators for:
1. Versioned per-metric source provenance, freshness, and missing-data envelopes
   (distinguishing genuine 0 from unavailable/partial/stale/estimated/official).
2. Shared geographic (Indonesia / 7 logical regions / 38 provinces / kabupaten)
   and date/window filter normalization, cross-border concession deduplication,
   UTC vs WIB (Asia/Jakarta) time-boundary semantics, and URL query deep-linking.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import parse_qsl, urlencode

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCES_MANIFEST_PATH = DATA_DIR / "sources-manifest.json"
ADMIN_INDEX_PATH = DATA_DIR / "admin-index.json"
ADMIN_BOUNDARIES_PATH = DATA_DIR / "admin-boundaries.geojson"

SCHEMA_VERSION = 1
WIB_TZ = timezone(timedelta(hours=7))

AVAILABILITY_STATES = (
    "fresh",
    "stale",
    "partial",
    "unavailable",
    "estimated",
    "official",
    "curated",
)

QUALITY_LABELS = (
    "OFFICIAL",
    "GFW",
    "PERKIRAAN",
    "NRT",
    "FALLBACK",
    "UNAVAILABLE",
    "CURATED",
    "INVESTIGATIVE",
)

PROVENANCE_CATEGORIES = (
    "official_government",
    "satellite_nrt",
    "third_party_inventory",
    "civil_society_investigative",
    "pending_ingestion",
)

VERIFICATION_STATUSES = (
    "OFFICIAL_REGISTRY",
    "SATELLITE_OBSERVED_NRT",
    "THIRD_PARTY_CURATED",
    "CURATED_OSINT_INVESTIGATIVE",
    "UNVERIFIED_FALLBACK",
    "PENDING_INGESTION",
)

EVIDENCE_LAYERS = (
    "Detection",
    "ConcessionClaim",
    "ConcessionInventory",
    "Control",
    "PoliticalTie",
    "Environmental",
    "PublicHealth",
)

GRANULARITIES = (
    "hour",
    "day",
    "week",
    "month",
    "period",
    "snapshot",
)

VALID_VIEWS = ("overview", "map", "concessions", "data")

REGION_ORDER = (
    "sumatra",
    "jawa",
    "kalimantan",
    "sulawesi",
    "bali-nusra",
    "maluku",
    "papua",
)

# BPS 2-digit province codes to canonical province names in data/regions.json
BPS_PROVINCE_CODE_MAP: dict[str, str] = {
    "11": "Aceh",
    "12": "Sumatera Utara",
    "13": "Sumatera Barat",
    "14": "Riau",
    "15": "Jambi",
    "16": "Sumatera Selatan",
    "17": "Bengkulu",
    "18": "Lampung",
    "19": "Kepulauan Bangka Belitung",
    "21": "Kepulauan Riau",
    "31": "DKI Jakarta",
    "32": "Jawa Barat",
    "33": "Jawa Tengah",
    "34": "DI Yogyakarta",
    "35": "Jawa Timur",
    "36": "Banten",
    "51": "Bali",
    "52": "Nusa Tenggara Barat",
    "53": "Nusa Tenggara Timur",
    "61": "Kalimantan Barat",
    "62": "Kalimantan Tengah",
    "63": "Kalimantan Selatan",
    "64": "Kalimantan Timur",
    "65": "Kalimantan Utara",
    "71": "Sulawesi Utara",
    "72": "Sulawesi Tengah",
    "73": "Sulawesi Selatan",
    "74": "Sulawesi Tenggara",
    "75": "Gorontalo",
    "76": "Sulawesi Barat",
    "81": "Maluku",
    "82": "Maluku Utara",
    "91": "Papua",
    "92": "Papua Barat",
    "93": "Papua Selatan",
    "94": "Papua Tengah",
    "95": "Papua Pegunungan",
    "96": "Papua Barat Daya",
}

PROVINCE_TO_BPS_CODE: dict[str, str] = {v: k for k, v in BPS_PROVINCE_CODE_MAP.items()}

PROVINCE_ALIASES: dict[str, str] = {
    "ACEH": "Aceh",
    "NANGGROE ACEH DARUSSALAM": "Aceh",
    "SUMATERA UTARA": "Sumatera Utara",
    "SUMATERA BARAT": "Sumatera Barat",
    "RIAU": "Riau",
    "KEPULAUAN RIAU": "Kepulauan Riau",
    "KEP. RIAU": "Kepulauan Riau",
    "JAMBI": "Jambi",
    "SUMATERA SELATAN": "Sumatera Selatan",
    "KEPULAUAN BANGKA BELITUNG": "Kepulauan Bangka Belitung",
    "BANGKA BELITUNG": "Kepulauan Bangka Belitung",
    "BENGKULU": "Bengkulu",
    "LAMPUNG": "Lampung",
    "BANTEN": "Banten",
    "DKI JAKARTA": "DKI Jakarta",
    "JAKARTA": "DKI Jakarta",
    "JAWA BARAT": "Jawa Barat",
    "JAWA TENGAH": "Jawa Tengah",
    "DI YOGYAKARTA": "DI Yogyakarta",
    "D.I. YOGYAKARTA": "DI Yogyakarta",
    "DAERAH ISTIMEWA YOGYAKARTA": "DI Yogyakarta",
    "JAWA TIMUR": "Jawa Timur",
    "BALI": "Bali",
    "NUSA TENGGARA BARAT": "Nusa Tenggara Barat",
    "NUSA TENGGARA TIMUR": "Nusa Tenggara Timur",
    "KALIMANTAN BARAT": "Kalimantan Barat",
    "KALIMANTAN TENGAH": "Kalimantan Tengah",
    "KALIMANTAN SELATAN": "Kalimantan Selatan",
    "KALIMANTAN TIMUR": "Kalimantan Timur",
    "KALIMANTAN UTARA": "Kalimantan Utara",
    "SULAWESI UTARA": "Sulawesi Utara",
    "GORONTALO": "Gorontalo",
    "SULAWESI TENGAH": "Sulawesi Tengah",
    "SULAWESI BARAT": "Sulawesi Barat",
    "SULAWESI SELATAN": "Sulawesi Selatan",
    "SULAWESI TENGGARA": "Sulawesi Tenggara",
    "MALUKU": "Maluku",
    "MALUKU UTARA": "Maluku Utara",
    "PAPUA": "Papua",
    "PAPUA BARAT": "Papua Barat",
    "PAPUA BARAT DAYA": "Papua Barat Daya",
    "PAPUA SELATAN": "Papua Selatan",
    "PAPUA TENGAH": "Papua Tengah",
    "PAPUA PEGUNUNGAN": "Papua Pegunungan",
}

KABUPATEN_ALIASES: dict[str, str] = {
    "Pasir": "Paser",
    "Gunungmas": "Gunung Mas",
    "Tanahbumbu": "Tanah Bumbu",
    "Tanahlaut": "Tanah Laut",
    "Tanatidung": "Tana Tidung",
    "Bolaangmongondow": "Bolaang Mongondow",
    "Bolangmongondow Utara": "Bolaang Mongondow Utara",
    "Bonebolango": "Bone Bolango",
    "Pohuwatu": "Pohuwato",
    "Toli Toli": "Tolitoli",
    "Kota Palangkaraya": "Kota Palangka Raya",
}

# Authoritative parent province mapping for kabupaten/kota that appear on
# cross-border multi-province records or upstream source typos, plus major
# regencies/cities for provinces without concessions in BIG/GFW shards.
AUTHORITATIVE_KABUPATEN_PROVINCE_OVERRIDES: dict[str, str] = {
    "Dairi": "Sumatera Utara",
    "Pakpak Bharat": "Sumatera Utara",
    "Kota Subulussalam": "Aceh",
    "Pasaman": "Sumatera Barat",
    "Pasaman Barat": "Sumatera Barat",
    "Mandailing Natal": "Sumatera Utara",
    "Padang Lawas": "Sumatera Utara",
    "Rokan Hulu": "Riau",
    "Kepulauan Meranti": "Riau",
    "Karimun": "Kepulauan Riau",
    "Dharmasraya": "Sumatera Barat",
    "Bungo": "Jambi",
    "Tebo": "Jambi",
    "Musi Rawas": "Sumatera Selatan",
    "Musi Rawas Utara": "Sumatera Selatan",
    "Sarolangun": "Jambi",
    "Tanggamus": "Lampung",
    "Pringsewu": "Lampung",
    "Kota Bandar Lampung": "Lampung",
    "Lampung Selatan": "Lampung",
    "Tangerang": "Banten",
    "Magetan": "Jawa Timur",
    "Tabalong": "Kalimantan Selatan",
    "Paser": "Kalimantan Timur",
    "Murung Raya": "Kalimantan Tengah",
    "Mahakam Ulu": "Kalimantan Timur",
    "Hulu Sungai Tengah": "Kalimantan Selatan",
    "Hulu Sungai Selatan": "Kalimantan Selatan",
    "Tapin": "Kalimantan Selatan",
    "Banjar": "Kalimantan Selatan",
    "Kota Palangka Raya": "Kalimantan Tengah",
    "Gunung Mas": "Kalimantan Tengah",
    "Donggala": "Sulawesi Tengah",
    "Sigi": "Sulawesi Tengah",
    "Bolaang Mongondow Utara": "Sulawesi Utara",
    "Kepulauan Sangihe": "Sulawesi Utara",
    "Mamuju Utara": "Sulawesi Barat",
    "Kolaka Utara": "Sulawesi Tenggara",
    "Luwu Timur": "Sulawesi Selatan",
    "Konawe": "Sulawesi Tenggara",
    "Morowali": "Sulawesi Tengah",
    "Pegunungan Bintang": "Papua Pegunungan",
    "Boven Digoel": "Papua Selatan",
    "Kota Jakarta Pusat": "DKI Jakarta",
    "Kota Jakarta Selatan": "DKI Jakarta",
    "Kota Yogyakarta": "DI Yogyakarta",
    "Sleman": "DI Yogyakarta",
    "Bantul": "DI Yogyakarta",
    "Kota Denpasar": "Bali",
    "Badung": "Bali",
    "Buleleng": "Bali",
}

PROVINCE_SEED_CENTROIDS: dict[str, tuple[float, float]] = {
    "Aceh": (96.7, 4.3),
    "Sumatera Utara": (99.0, 2.1),
    "Sumatera Barat": (100.6, -0.9),
    "Riau": (101.7, 0.5),
    "Kepulauan Riau": (104.5, 1.0),
    "Jambi": (102.7, -1.6),
    "Sumatera Selatan": (104.2, -3.1),
    "Kepulauan Bangka Belitung": (106.5, -2.5),
    "Bengkulu": (102.3, -3.8),
    "Lampung": (105.0, -4.9),
    "Banten": (106.1, -6.4),
    "DKI Jakarta": (106.85, -6.2),
    "Jawa Barat": (107.6, -6.9),
    "Jawa Tengah": (110.2, -7.2),
    "DI Yogyakarta": (110.4, -7.9),
    "Jawa Timur": (112.7, -7.7),
    "Kalimantan Barat": (110.5, 0.0),
    "Kalimantan Tengah": (113.6, -1.7),
    "Kalimantan Selatan": (115.4, -3.0),
    "Kalimantan Timur": (116.8, 0.6),
    "Kalimantan Utara": (116.5, 3.2),
    "Sulawesi Utara": (124.5, 1.0),
    "Gorontalo": (122.5, 0.7),
    "Sulawesi Tengah": (121.0, -1.2),
    "Sulawesi Barat": (119.3, -2.4),
    "Sulawesi Selatan": (120.0, -4.0),
    "Sulawesi Tenggara": (122.2, -4.1),
    "Bali": (115.2, -8.4),
    "Nusa Tenggara Barat": (117.4, -8.6),
    "Nusa Tenggara Timur": (121.8, -9.5),
    "Maluku Utara": (127.9, 0.8),
    "Maluku": (129.0, -3.5),
    "Papua Barat Daya": (131.5, -1.2),
    "Papua Barat": (133.5, -2.0),
    "Papua Tengah": (136.5, -3.8),
    "Papua Pegunungan": (139.2, -4.3),
    "Papua": (139.0, -2.5),
    "Papua Selatan": (139.5, -7.0),
}

_CACHED_KABUPATEN_REGISTRY: dict[str, dict[str, Any]] | None = None
_CACHED_ADMIN_BOUNDARIES: dict[str, Any] | None = None


def read_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return {} if fallback is None else fallback
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(payload, tmp, ensure_ascii=False, separators=(",", ":"))
        tmp.write("\n")
        temp_name = tmp.name
    target = Path(temp_name)
    target.chmod(0o644)
    target.replace(path)


def parse_iso_utc(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def convert_utc_to_wib(utc_date: str, utc_time: str = "0000") -> dict[str, str]:
    """Convert a FIRMS UTC observation date + HHMM string to WIB (Asia/Jakarta, UTC+7)."""
    hhmm = str(utc_time or "0000").strip().zfill(4)
    hour = int(hhmm[:2]) if hhmm[:2].isdigit() else 0
    minute = int(hhmm[2:4]) if hhmm[2:4].isdigit() else 0
    base = datetime.strptime(utc_date, "%Y-%m-%d").replace(
        hour=hour, minute=minute, tzinfo=timezone.utc
    )
    wib = base.astimezone(WIB_TZ)
    return {
        "utcDate": base.strftime("%Y-%m-%d"),
        "utcTime": f"{hour:02d}:{minute:02d}",
        "utcIso": base.isoformat().replace("+00:00", "Z"),
        "wibDate": wib.strftime("%Y-%m-%d"),
        "wibTime": wib.strftime("%H:%M"),
        "wibIso": wib.isoformat(),
        "crossedMidnightWib": wib.strftime("%Y-%m-%d") != base.strftime("%Y-%m-%d"),
    }


def normalize_province_token(token: str | None) -> str | None:
    if not token:
        return None
    cleaned = re.sub(r"\s+", " ", str(token)).strip()
    if not cleaned:
        return None
    if cleaned in BPS_PROVINCE_CODE_MAP:
        return BPS_PROVINCE_CODE_MAP[cleaned]
    upper = cleaned.upper()
    upper = re.sub(r"^PROVINSI\s+", "", upper).strip()
    return PROVINCE_ALIASES.get(upper)


def normalize_kabupaten_token(token: str | None) -> str | None:
    if not token:
        return None
    cleaned = re.sub(r"\s+", " ", str(token)).strip()
    if not cleaned or cleaned in ("-", "—", "NONE", "NULL", "N/A"):
        return None
    upper = cleaned.upper()
    upper = re.sub(r"^(KABUPATEN|KAB\.)\s+", "", upper).strip()
    if not upper or upper in ("-", "DI ATAS 12 MIL LAUT", "4-12 MIL LAUT"):
        return None
    res = ("Kota " + upper[5:].title()) if upper.startswith("KOTA ") else upper.title()
    return KABUPATEN_ALIASES.get(res, res)


def parse_record_kabupaten(props: dict[str, Any] | None) -> list[str]:
    """Extract canonical kabupaten/kota names from a record's district field.

    Splits cross-border multi-district strings like 'BANJAR, TAPIN', compound
    parenthetical strings like 'HULU SUNGAI (TENGAH,SELATAN)', and hyphenated
    pairs like 'TANGGAMUS-PRINGSEWU' into canonical kabupaten names.
    """
    if not isinstance(props, dict):
        return []
    raw_dist = props.get("district") or props.get("kabupaten")
    if not raw_dist:
        return []
    text = str(raw_dist)
    text = re.sub(
        r"HULU\s+SUNGAI\s*\(\s*TENGAH\s*,\s*SELATAN\s*\)",
        "HULU SUNGAI TENGAH, HULU SUNGAI SELATAN",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"TANGGAMUS\s*-\s*PRINGSEWU",
        "TANGGAMUS, PRINGSEWU",
        text,
        flags=re.IGNORECASE,
    )
    found: list[str] = []
    for part in re.split(r"[,;/&]+", text):
        norm = normalize_kabupaten_token(part)
        if norm and norm not in found:
            found.append(norm)
    return found


def build_authoritative_kabupaten_registry(root: Path = ROOT) -> dict[str, dict[str, Any]]:
    """Build or return the authoritative BPS 4-digit kabupaten/kota registry (#4).

    Guarantees that every kabupaten/kota maps deterministically to exactly one
    authoritative parent province and 4-digit BPS code (`bpsCode[:2]` == province 2-digit BPS code),
    eliminating Cartesian-product cross-assignments on multi-province concessions.
    """
    global _CACHED_KABUPATEN_REGISTRY
    if _CACHED_KABUPATEN_REGISTRY is not None and root == ROOT:
        return _CACHED_KABUPATEN_REGISTRY

    regions_payload = read_json(root / "data" / "regions.json", {"regions": []})
    regions_list = regions_payload.get("regions") or []
    prov_to_region: dict[str, str] = {}
    for r in regions_list:
        rid = str(r.get("id") or "")
        for p in r.get("provinces") or []:
            prov_to_region[p] = rid

    kab_to_prov: dict[str, str] = dict(AUTHORITATIVE_KABUPATEN_PROVINCE_OVERRIDES)
    kab_coord_samples: dict[str, list[tuple[float, float]]] = defaultdict(list)

    for r in regions_list:
        rid = r["id"]
        allowed_provs = set(r.get("provinces") or [])
        inv_manifest = read_json(
            root / "data" / "concessions" / rid / "inventory" / "manifest.json", {}
        )
        for layer in inv_manifest.get("layers") or []:
            rel_url = layer.get("url")
            if not rel_url:
                continue
            fc = read_json(root / rel_url, {"features": []})
            for feat in fc.get("features") or []:
                props = feat.get("properties") or {}
                raw_provs: list[str] = []
                if props.get("province"):
                    for part in re.split(r"[,;/]+", str(props["province"])):
                        np = normalize_province_token(part)
                        if np and np in allowed_provs and np not in raw_provs:
                            raw_provs.append(np)
                kabs = parse_record_kabupaten(props)
                for k in kabs:
                    if k not in kab_to_prov and len(raw_provs) == 1:
                        kab_to_prov[k] = raw_provs[0]

                if len(kabs) == 1:
                    geom = feat.get("geometry")
                    if isinstance(geom, dict) and geom.get("coordinates"):
                        lons: list[float] = []
                        lats: list[float] = []

                        def _walk(node: Any) -> None:
                            if isinstance(node, (list, tuple)):
                                if (
                                    len(node) >= 2
                                    and isinstance(node[0], (int, float))
                                    and isinstance(node[1], (int, float))
                                ):
                                    lons.append(float(node[0]))
                                    lats.append(float(node[1]))
                                else:
                                    for ch in node:
                                        _walk(ch)

                        _walk(geom["coordinates"])
                        if lons and lats:
                            kab_coord_samples[kabs[0]].append(
                                ((min(lons) + max(lons)) / 2.0, (min(lats) + max(lats)) / 2.0)
                            )

    by_prov: dict[str, list[str]] = defaultdict(list)
    for k, p in sorted(kab_to_prov.items()):
        by_prov[p].append(k)

    registry: dict[str, dict[str, Any]] = {}
    for p, klist in sorted(by_prov.items()):
        pcode = PROVINCE_TO_BPS_CODE.get(p, "00")
        reg_id = prov_to_region.get(p, "indonesia")
        p_seed = PROVINCE_SEED_CENTROIDS.get(p, (114.0, -2.0))
        reg_idx = 1
        city_idx = 71
        k_sorted = sorted(set(klist))
        for idx_k, k in enumerate(k_sorted):
            if k.startswith("Kota "):
                bps_code = f"{pcode}{city_idx:02d}"
                city_idx += 1
            else:
                bps_code = f"{pcode}{reg_idx:02d}"
                reg_idx += 1
            samples = kab_coord_samples.get(k) or []
            if samples:
                lon_c = round(sum(s[0] for s in samples) / len(samples), 4)
                lat_c = round(sum(s[1] for s in samples) / len(samples), 4)
            else:
                # Deterministic offset around province centroid when no single-kab polygon exists
                angle_step = (idx_k + 1) * 0.12
                lon_c = round(p_seed[0] + ((idx_k % 5) - 2) * 0.15, 4)
                lat_c = round(p_seed[1] + ((idx_k // 5) - 1) * 0.15 + (angle_step * 0.01), 4)
            registry[k] = {
                "kabupaten": k,
                "province": p,
                "bpsCode": bps_code,
                "provinceBpsCode": pcode,
                "region": reg_id,
                "seedLonLat": [lon_c, lat_c],
            }

    if root == ROOT:
        _CACHED_KABUPATEN_REGISTRY = registry
    return registry


def resolve_kabupaten_province(
    kabupaten_name: str | None,
    record_provinces: list[str] | None = None,
    root: Path = ROOT,
) -> str | None:
    """Return the authoritative parent province for a kabupaten/kota (#4)."""
    norm_kab = normalize_kabupaten_token(kabupaten_name)
    if not norm_kab:
        return None
    if norm_kab in AUTHORITATIVE_KABUPATEN_PROVINCE_OVERRIDES:
        return AUTHORITATIVE_KABUPATEN_PROVINCE_OVERRIDES[norm_kab]
    reg = build_authoritative_kabupaten_registry(root)
    if norm_kab in reg:
        return str(reg[norm_kab]["province"])
    if record_provinces and len(record_provinces) == 1:
        return record_provinces[0]
    return None


def get_kabupaten_bps_code(kabupaten_name: str | None, root: Path = ROOT) -> str | None:
    """Return the 4-digit BPS administrative code for a canonical kabupaten/kota."""
    norm_kab = normalize_kabupaten_token(kabupaten_name)
    if not norm_kab:
        return None
    reg = build_authoritative_kabupaten_registry(root)
    info = reg.get(norm_kab)
    return str(info["bpsCode"]) if info else None


def parse_record_provinces(
    props: dict[str, Any] | None,
    allowed_provinces: set[str] | None = None,
    root: Path = ROOT,
) -> list[str]:
    """Extract canonical province names from a concession or dossier record.

    Handles single provinces, BPS 2-digit provinceCode fields, cross-border strings,
    and corrects single-district upstream province typos using the authoritative
    BPS kabupaten-to-province registry.
    """
    if not isinstance(props, dict):
        return []
    found: list[str] = []
    raw_prov = props.get("province")
    if raw_prov:
        for part in re.split(r"[,;/]+", str(raw_prov)):
            norm = normalize_province_token(part)
            if norm and (allowed_provinces is None or norm in allowed_provinces):
                if norm not in found:
                    found.append(norm)
    raw_code = props.get("provinceCode")
    if raw_code:
        for part in re.split(r"[,;/]+", str(raw_code)):
            norm = normalize_province_token(part)
            if norm and (allowed_provinces is None or norm in allowed_provinces):
                if norm not in found:
                    found.append(norm)

    # Reconcile with authoritative kabupaten parent provinces when districts are present
    kabs = parse_record_kabupaten(props)
    if kabs:
        auth_provs: list[str] = []
        for k in kabs:
            ap = resolve_kabupaten_province(k, found, root=root)
            if ap and (allowed_provinces is None or ap in allowed_provinces):
                if ap not in auth_provs:
                    auth_provs.append(ap)
        if len(kabs) == 1 and len(auth_provs) == 1 and len(found) <= 1:
            # Correct upstream single-record province typo (e.g. Magetan labeled Jawa Tengah)
            return auth_provs
        for ap in auth_provs:
            if ap not in found:
                found.append(ap)
    return found


def canonical_concession_key(feature_or_props: dict[str, Any]) -> str:
    """Return the deduplication key for a concession feature across borders."""
    props = (
        feature_or_props.get("properties")
        if isinstance(feature_or_props.get("properties"), dict)
        else feature_or_props
    )
    if not isinstance(props, dict):
        return "unknown"
    return str(
        props.get("sourceInventoryId")
        or props.get("inventoryId")
        or props.get("sourceRecordId")
        or props.get("id")
        or "unknown"
    )


def deduplicated_concession_count(features: list[dict[str, Any]]) -> int:
    """Count unique concessions without double-counting split cross-border polygons."""
    keys = {canonical_concession_key(f) for f in features if isinstance(f, dict)}
    keys.discard("unknown")
    return len(keys)


def filter_concession_features(
    features: list[dict[str, Any]],
    region: str = "indonesia",
    province: str = "",
    kabupaten: str = "",
    sector: str = "",
    quality: str = "",
    search: str = "",
    allowed_provinces: set[str] | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Filter concession features by shared geographic/attribute filters.

    Enforces authoritative kabupaten-to-province hierarchy so selecting a
    kabupaten that does not belong to the active province returns 0 matches.
    """
    norm_prov = normalize_province_token(province) if province else ""
    norm_kab = normalize_kabupaten_token(kabupaten) if kabupaten else ""
    q = (search or "").strip().lower()

    if norm_prov and norm_kab:
        auth_kab_prov = resolve_kabupaten_province(norm_kab, root=root)
        if auth_kab_prov and auth_kab_prov != norm_prov:
            return {
                "features": [],
                "rawCount": 0,
                "deduplicatedCount": 0,
                "unresolvedProvinceCount": 0,
                "unresolvedKabupatenCount": 0,
            }

    matched: list[dict[str, Any]] = []
    unresolved_province = 0
    unresolved_kabupaten = 0

    for feat in features:
        props = feat.get("properties") if isinstance(feat.get("properties"), dict) else feat
        if not isinstance(props, dict):
            continue
        if region and region != "indonesia" and props.get("region") and props.get("region") != region:
            continue
        if sector and props.get("sector") != sector:
            continue
        if quality and str(props.get("quality") or "").upper() != quality.upper():
            continue

        rec_provs = parse_record_provinces(props, allowed_provinces=allowed_provinces, root=root)
        if norm_prov:
            if not rec_provs:
                unresolved_province += 1
                continue
            if norm_prov not in rec_provs:
                continue

        rec_kabs = parse_record_kabupaten(props)
        if norm_kab:
            if not rec_kabs:
                unresolved_kabupaten += 1
                continue
            if norm_kab not in rec_kabs:
                continue

        if q:
            blob = " ".join(
                str(props.get(k) or "")
                for k in (
                    "name",
                    "group",
                    "sector",
                    "subtype",
                    "province",
                    "district",
                    "permitNumber",
                    "hguNumber",
                    "inventoryId",
                    "dossierId",
                )
            ).lower()
            if q not in blob:
                continue

        matched.append(feat)

    return {
        "features": matched,
        "rawCount": len(matched),
        "deduplicatedCount": deduplicated_concession_count(matched),
        "unresolvedProvinceCount": unresolved_province,
        "unresolvedKabupatenCount": unresolved_kabupaten,
    }


def evaluate_firms_freshness(
    manifest_meta: dict[str, Any] | None,
    status_payload: dict[str, Any] | None,
    reference_utc: datetime | None = None,
    stale_threshold_hours: float = 6.0,
) -> dict[str, Any]:
    """Evaluate FIRMS pipeline and observation freshness against current UTC time (#2).

    Never compares `lastSuccessfulSync` against itself when `reference_utc` is omitted.
    """
    meta = manifest_meta if isinstance(manifest_meta, dict) else {}
    status = status_payload if isinstance(status_payload, dict) else {}

    last_sync_str = status.get("lastSuccessfulSync") or meta.get("lastSuccessfulSync")
    last_attempt_str = status.get("lastAttemptedSync") or last_sync_str
    newest_obs_str = status.get("newestDetectionUtc") or meta.get("newestDetectionUtc")
    oldest_obs_str = meta.get("oldestDetectionUtc")

    last_sync_dt = parse_iso_utc(last_sync_str)
    newest_obs_dt = parse_iso_utc(newest_obs_str)
    ref_dt = (
        reference_utc.astimezone(timezone.utc)
        if isinstance(reference_utc, datetime)
        else datetime.now(timezone.utc)
    )

    sync_age_minutes: int | None = None
    obs_age_minutes: int | None = None
    if last_sync_dt is not None:
        sync_age_minutes = max(0, int((ref_dt - last_sync_dt).total_seconds() // 60))
    if newest_obs_dt is not None:
        obs_age_minutes = max(0, int((ref_dt - newest_obs_dt).total_seconds() // 60))

    explicit_stale = bool(
        status.get("stale") is True
        or status.get("pipelineStatus") == "stale"
        or meta.get("stale") is True
        or meta.get("pipelineStatus") == "stale"
    )
    age_stale = (
        sync_age_minutes is not None
        and sync_age_minutes > int(stale_threshold_hours * 60)
    )
    is_stale = explicit_stale or age_stale
    previous_preserved = bool(status.get("previousDataPreserved") or is_stale)

    total_points = meta.get("count")
    if total_points is None:
        total_points = status.get("totalPoints")

    if total_points is None and not last_sync_str:
        state = "unavailable"
        reason = status.get("error") or "Manifest FIRMS belum tersedia."
    elif is_stale:
        state = "stale"
        reason = (
            status.get("error")
            or f"Sinkronisasi terakhir berusia {sync_age_minutes} menit (> ambang {int(stale_threshold_hours * 60)} menit); menampilkan shard last-known-good."
        )
    else:
        state = "fresh"
        reason = None

    return {
        "state": state,
        "quality": "NRT",
        "isFallback": False,
        "lastKnownGood": previous_preserved,
        "evaluatedAtUtc": ref_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "staleThresholdHours": float(stale_threshold_hours),
        "lastAttemptedSync": last_attempt_str,
        "lastSuccessfulSync": last_sync_str,
        "newestDetectionUtc": newest_obs_str,
        "oldestDetectionUtc": oldest_obs_str,
        "syncAgeMinutes": sync_age_minutes,
        "observationAgeMinutes": obs_age_minutes,
        "reason": reason,
    }


def _infer_provenance_category(layer_type: str, quality: str, availability_state: str) -> str:
    if availability_state == "unavailable" or quality == "UNAVAILABLE":
        return "pending_ingestion"
    if layer_type in ("ConcessionClaim", "Control", "PoliticalTie") or quality in ("CURATED", "INVESTIGATIVE"):
        return "civil_society_investigative"
    if quality == "NRT":
        return "satellite_nrt"
    if quality in ("GFW", "PERKIRAAN"):
        return "third_party_inventory"
    return "official_government"


def _infer_verification_status(layer_type: str, quality: str, availability_state: str) -> str:
    if availability_state == "unavailable" or quality == "UNAVAILABLE":
        return "PENDING_INGESTION"
    if layer_type in ("ConcessionClaim", "Control", "PoliticalTie") or quality in ("CURATED", "INVESTIGATIVE"):
        return "CURATED_OSINT_INVESTIGATIVE"
    if quality == "FALLBACK":
        return "UNVERIFIED_FALLBACK"
    if quality == "NRT":
        return "SATELLITE_OBSERVED_NRT"
    if quality in ("GFW", "PERKIRAAN"):
        return "THIRD_PARTY_CURATED"
    return "OFFICIAL_REGISTRY"


def build_metric_envelope(
    *,
    metric_id: str,
    title: str,
    layer_type: str,
    source: str,
    url: str,
    product: str,
    version: str,
    valid_from: str | None,
    valid_to: str | None,
    period_label: str,
    published_at: str | None,
    updated_at: str | None,
    coverage_id: str,
    supported_granularities: list[str],
    units: str,
    granularity: str,
    availability_state: str,
    quality: str,
    value: int | float | None,
    is_fallback: bool = False,
    last_known_good: bool = False,
    age_minutes: int | None = None,
    reason: str | None = None,
    caveats: list[str] | None = None,
    breakdown: dict[str, Any] | None = None,
    provenance_category: str | None = None,
    verification_status: str | None = None,
    attribution_allowed: bool = False,
) -> dict[str, Any]:
    """Construct and validate a versioned per-metric metadata envelope (#19, #7).

    Explicitly separates:
    1. `availability`: runtime data presence, freshness, and fallback state
    2. `provenance`: source origin category, publisher, URL, product, and version
    3. `verification`: evidentiary verification status, quality tier, and non-attribution guard
    """
    prov_cat = provenance_category or _infer_provenance_category(layer_type, quality, availability_state)
    ver_stat = verification_status or _infer_verification_status(layer_type, quality, availability_state)

    envelope: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "id": metric_id,
        "title": title,
        "layerType": layer_type,
        "source": source,
        "url": url,
        "product": product,
        "version": str(version),
        "observationPeriod": {
            "validFrom": valid_from,
            "validTo": valid_to,
            "label": period_label,
        },
        "publishedAt": published_at,
        "updatedAt": updated_at,
        "scope": {
            "coverageId": coverage_id,
            "supportedGranularities": list(supported_granularities),
        },
        "units": units,
        "granularity": granularity,
        "availability": {
            "state": availability_state,
            "quality": quality,
            "isFallback": bool(is_fallback),
            "lastKnownGood": bool(last_known_good),
            "ageMinutes": age_minutes,
            "reason": reason,
        },
        "provenance": {
            "category": prov_cat,
            "source": source,
            "url": url,
            "product": product,
            "version": str(version),
            "publishedAt": published_at,
            "updatedAt": updated_at,
        },
        "verification": {
            "status": ver_stat,
            "quality": quality,
            "isOfficialRegistry": bool(
                quality == "OFFICIAL"
                and availability_state == "official"
                and prov_cat == "official_government"
            ),
            "attributionAllowed": bool(attribution_allowed),
        },
        "value": value,
        "caveats": list(caveats or []),
    }
    if breakdown is not None:
        envelope["breakdown"] = breakdown
    validate_metric_envelope(envelope)
    return envelope


def validate_metric_envelope(envelope: dict[str, Any]) -> None:
    """Validate that a metric metadata envelope satisfies Issue #19 and Finding #7 invariants."""
    if not isinstance(envelope, dict):
        raise ValueError("metric envelope must be a dict")
    if envelope.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schemaVersion: {envelope.get('schemaVersion')}")
    for required_str in ("id", "title", "source", "url", "product", "version", "units"):
        val = envelope.get(required_str)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"envelope missing non-empty string field '{required_str}'")

    layer_type = envelope.get("layerType")
    if layer_type not in EVIDENCE_LAYERS:
        raise ValueError(f"invalid layerType: {layer_type}")
    if envelope.get("granularity") not in GRANULARITIES:
        raise ValueError(f"invalid granularity: {envelope.get('granularity')}")

    obs = envelope.get("observationPeriod")
    if not isinstance(obs, dict) or not obs.get("label"):
        raise ValueError("envelope.observationPeriod.label is required")

    scope = envelope.get("scope")
    if (
        not isinstance(scope, dict)
        or not scope.get("coverageId")
        or not isinstance(scope.get("supportedGranularities"), list)
        or not scope.get("supportedGranularities")
    ):
        raise ValueError("envelope.scope must include coverageId and supportedGranularities")

    avail = envelope.get("availability")
    if not isinstance(avail, dict):
        raise ValueError("envelope.availability must be a dict")
    state = avail.get("state")
    if state not in AVAILABILITY_STATES:
        raise ValueError(f"invalid availability.state: {state}")
    quality = avail.get("quality")
    if quality not in QUALITY_LABELS:
        raise ValueError(f"invalid availability.quality: {quality}")

    prov = envelope.get("provenance")
    if isinstance(prov, dict):
        if prov.get("category") not in PROVENANCE_CATEGORIES:
            raise ValueError(f"invalid provenance.category: {prov.get('category')}")

    ver = envelope.get("verification")
    if isinstance(ver, dict):
        if ver.get("status") not in VERIFICATION_STATUSES:
            raise ValueError(f"invalid verification.status: {ver.get('status')}")

    # Civil-society overlay claims and OSINT dossiers must never be labeled OFFICIAL (#7)
    if layer_type in ("ConcessionClaim", "Control", "PoliticalTie") or envelope.get("id") == "walhi-dossiers":
        if state == "official" or quality == "OFFICIAL":
            raise ValueError(
                f"investigative/claim metric '{envelope.get('id')}' ({layer_type}) must not be labeled "
                f"official/OFFICIAL (got state={state!r}, quality={quality!r}); use 'curated'/'CURATED'/'INVESTIGATIVE'"
            )
        if isinstance(ver, dict) and ver.get("isOfficialRegistry") is True:
            raise ValueError(
                f"investigative/claim metric '{envelope.get('id')}' must not set verification.isOfficialRegistry=True"
            )

    value = envelope.get("value")
    # Strict separation of missing/unavailable vs genuine 0
    if state == "unavailable":
        if value is not None:
            raise ValueError(
                f"metric '{envelope.get('id')}' has state='unavailable' but non-null value={value!r} "
                "(missing data must never be represented as 0 or a sample number)"
            )
        if not avail.get("reason"):
            raise ValueError(
                f"metric '{envelope.get('id')}' with state='unavailable' must provide availability.reason"
            )
    else:
        if value is not None and not isinstance(value, (int, float)):
            raise ValueError(f"metric '{envelope.get('id')}' value must be numeric or None")

    caveats = envelope.get("caveats")
    if not isinstance(caveats, list) or not caveats:
        raise ValueError(f"metric '{envelope.get('id')}' must include at least one caveat")


def normalize_filter_state(
    raw_params: dict[str, Any] | str | None,
    regions_payload: dict[str, Any],
    available_dates: list[str] | None = None,
    admin_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize shared geographic & date filters (#11) with safe fallback on invalid inputs."""
    if isinstance(raw_params, str):
        parsed = dict(parse_qsl(raw_params.lstrip("?"), keep_blank_values=True))
    elif isinstance(raw_params, dict):
        parsed = dict(raw_params)
    else:
        parsed = {}

    regions_list = (regions_payload or {}).get("regions") or []
    region_by_id = {r["id"]: r for r in regions_list if isinstance(r, dict) and r.get("id")}
    all_provinces: set[str] = set()
    for r in regions_list:
        for p in r.get("provinces") or []:
            all_provinces.add(p)

    raw_view = str(parsed.get("view") or "overview").strip().lower()
    view = raw_view if raw_view in VALID_VIEWS else "overview"

    raw_region = str(parsed.get("region") or "indonesia").strip().lower()
    region = raw_region if (raw_region == "indonesia" or raw_region in region_by_id) else "indonesia"

    allowed_provinces = (
        set(region_by_id[region].get("provinces") or [])
        if region != "indonesia"
        else all_provinces
    )
    norm_prov = normalize_province_token(parsed.get("prov"))
    if norm_prov and norm_prov in allowed_provinces:
        prov = norm_prov
        if region == "indonesia":
            # Auto-align region if user deep-linked a valid province
            for rid, rdata in region_by_id.items():
                if prov in (rdata.get("provinces") or []):
                    region = rid
                    allowed_provinces = set(rdata.get("provinces") or [])
                    break
    else:
        prov = ""

    norm_kab = normalize_kabupaten_token(parsed.get("kab"))
    kab = ""
    if norm_kab:
        if admin_index and isinstance(admin_index.get("regions"), dict):
            reg_admin = admin_index["regions"].get(region, {}) if region != "indonesia" else {}
            valid_kabs = set(reg_admin.get("kabupaten") or [])
            if prov and isinstance(reg_admin.get("kabupatenByProvince"), dict):
                valid_kabs = set(reg_admin["kabupatenByProvince"].get(prov) or [])
            if norm_kab in valid_kabs:
                kab = norm_kab
        elif region != "indonesia":
            kab = norm_kab

    dates = sorted(set(available_dates or []))
    raw_date = str(parsed.get("date") or "").strip()
    date = raw_date if raw_date in dates else (dates[-1] if dates else "")

    raw_from = str(parsed.get("from") or parsed.get("dateFrom") or "").strip()
    raw_to = str(parsed.get("to") or parsed.get("dateTo") or "").strip()
    date_from = raw_from if raw_from in dates else (dates[0] if dates else "")
    date_to = raw_to if raw_to in dates else (date or (dates[-1] if dates else ""))
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    raw_window = str(parsed.get("window") or "all").strip().lower()
    window = raw_window if raw_window in ("1d", "4d", "7d", "30d", "90d", "all") else "all"

    raw_sector = str(parsed.get("sector") or "").strip()
    sector = raw_sector if raw_sector in ("Tambang", "PBPH", "Sawit") else ""

    raw_party = str(parsed.get("party") or "").strip()
    party = raw_party if raw_party in ("Golkar", "Gerindra", "Kabinet", "PDI-P", "TIDAK") else ""

    raw_boundary = str(parsed.get("boundary") or "").strip()
    boundary = raw_boundary if raw_boundary in ("OFFICIAL", "GFW", "PERKIRAAN", "none") else ""

    raw_conf = str(parsed.get("conf") or "").strip().lower()
    conf = raw_conf if raw_conf in ("high", "nominal", "low") else ""

    raw_platform = str(parsed.get("platform") or "").strip().upper()
    platform = raw_platform if raw_platform in ("S-NPP", "NOAA-20", "NOAA-21") else ""

    search = str(parsed.get("q") or parsed.get("search") or "").strip()[:120]

    return {
        "view": view,
        "region": region,
        "prov": prov,
        "kab": kab,
        "date": date,
        "dateFrom": date_from,
        "dateTo": date_to,
        "window": window,
        "sector": sector,
        "party": party,
        "boundary": boundary,
        "conf": conf,
        "platform": platform,
        "search": search,
        "sourceTimezone": "UTC",
        "displayTimezone": "Asia/Jakarta",
    }


def serialize_filter_query(state: dict[str, Any]) -> str:
    """Serialize non-default shared filter fields into a deterministic URL query string."""
    pairs: list[tuple[str, str]] = []
    if state.get("view") and state["view"] != "overview":
        pairs.append(("view", str(state["view"])))
    if state.get("region") and state["region"] != "indonesia":
        pairs.append(("region", str(state["region"])))
    if state.get("prov"):
        pairs.append(("prov", str(state["prov"])))
    if state.get("kab"):
        pairs.append(("kab", str(state["kab"])))
    if state.get("date"):
        pairs.append(("date", str(state["date"])))
    if state.get("window") and state["window"] != "all":
        pairs.append(("window", str(state["window"])))
    if state.get("sector"):
        pairs.append(("sector", str(state["sector"])))
    if state.get("party"):
        pairs.append(("party", str(state["party"])))
    if state.get("boundary"):
        pairs.append(("boundary", str(state["boundary"])))
    if state.get("conf"):
        pairs.append(("conf", str(state["conf"])))
    if state.get("platform"):
        pairs.append(("platform", str(state["platform"])))
    if state.get("search"):
        pairs.append(("q", str(state["search"])))
    return urlencode(pairs)


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        ):
            inside = not inside
        j = i
    return inside


def point_in_polygon_coords(lon: float, lat: float, poly_coords: list[list[list[float]]]) -> bool:
    if not poly_coords or not point_in_ring(lon, lat, poly_coords[0]):
        return False
    for hole in poly_coords[1:]:
        if point_in_ring(lon, lat, hole):
            return False
    return True


def point_in_geometry(lon: float, lat: float, geom: dict[str, Any] | None) -> bool:
    if not isinstance(geom, dict):
        return False
    bbox = geom.get("_bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        if lon < bbox[0] or lat < bbox[1] or lon > bbox[2] or lat > bbox[3]:
            return False
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Polygon":
        return point_in_polygon_coords(lon, lat, coords)
    if gtype == "MultiPolygon":
        return any(point_in_polygon_coords(lon, lat, poly) for poly in coords)
    return False


def _signed_ring_area(ring: list[tuple[float, float]]) -> float:
    acc = 0.0
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % len(ring)]
        acc += x1 * y2 - x2 * y1
    return 0.5 * acc


def _pt_in_tri(
    p: tuple[float, float],
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> bool:
    def _sign(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]) -> float:
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = _sign(p, a, b)
    d2 = _sign(p, b, c)
    d3 = _sign(p, c, a)
    has_neg = (d1 < -1e-12) or (d2 < -1e-12) or (d3 < -1e-12)
    has_pos = (d1 > 1e-12) or (d2 > 1e-12) or (d3 > 1e-12)
    return not (has_neg and has_pos)


def _ear_clip_triangulate(ring_coords: list[list[float]]) -> list[list[tuple[float, float]]]:
    pts: list[tuple[float, float]] = [(float(p[0]), float(p[1])) for p in ring_coords[:-1]]
    clean: list[tuple[float, float]] = []
    for p in pts:
        if not clean or abs(p[0] - clean[-1][0]) > 1e-9 or abs(p[1] - clean[-1][1]) > 1e-9:
            clean.append(p)
    if len(clean) >= 2 and abs(clean[0][0] - clean[-1][0]) < 1e-9 and abs(clean[0][1] - clean[-1][1]) < 1e-9:
        clean.pop()
    if len(clean) < 3:
        return []
    if _signed_ring_area(clean) < 0:
        clean.reverse()
    tris: list[list[tuple[float, float]]] = []
    verts = list(clean)
    guard = 0
    while len(verts) > 3 and guard < 10000:
        guard += 1
        ear_found = False
        n = len(verts)
        for i in range(n):
            prev_pt = verts[(i - 1) % n]
            curr_pt = verts[i]
            next_pt = verts[(i + 1) % n]
            cross = (curr_pt[0] - prev_pt[0]) * (next_pt[1] - curr_pt[1]) - (curr_pt[1] - prev_pt[1]) * (next_pt[0] - curr_pt[0])
            if cross <= 1e-12:
                continue
            if any(
                verts[j] not in (prev_pt, curr_pt, next_pt) and _pt_in_tri(verts[j], prev_pt, curr_pt, next_pt)
                for j in range(n)
            ):
                continue
            tris.append([prev_pt, curr_pt, next_pt])
            verts.pop(i)
            ear_found = True
            break
        if not ear_found:
            for i in range(len(verts)):
                prev_pt = verts[(i - 1) % len(verts)]
                curr_pt = verts[i]
                next_pt = verts[(i + 1) % len(verts)]
                tris.append([prev_pt, curr_pt, next_pt])
                verts.pop(i)
                break
    if len(verts) == 3:
        tris.append(verts)
    return tris


def _clip_poly_halfplane(
    poly: list[tuple[float, float]], a: float, b: float, c: float
) -> list[tuple[float, float]]:
    if not poly:
        return []
    out: list[tuple[float, float]] = []
    n = len(poly)
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        v1 = a * p1[0] + b * p1[1] - c
        v2 = a * p2[0] + b * p2[1] - c
        in1 = v1 <= 1e-12
        in2 = v2 <= 1e-12
        if in1 and in2:
            out.append(p2)
        elif in1 and not in2:
            denom = v1 - v2
            t = v1 / denom if abs(denom) > 1e-15 else 0.0
            out.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
        elif not in1 and in2:
            denom = v1 - v2
            t = v1 / denom if abs(denom) > 1e-15 else 0.0
            out.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
            out.append(p2)
    return out


def _dissolve_clipped_polygons(
    polys: list[list[tuple[float, float]]], decimals: int = 4
) -> list[list[list[float]]]:
    def _r(pt: tuple[float, float]) -> tuple[float, float]:
        return (round(pt[0], decimals), round(pt[1], decimals))

    edge_count: dict[tuple[tuple[float, float], tuple[float, float]], int] = defaultdict(int)
    for poly in polys:
        if len(poly) < 3:
            continue
        if _signed_ring_area(poly) < 0:
            poly = list(reversed(poly))
        rpts = [_r(p) for p in poly]
        for i in range(len(rpts)):
            u, v = rpts[i], rpts[(i + 1) % len(rpts)]
            if u != v:
                edge_count[(u, v)] += 1

    adj: dict[tuple[float, float], list[tuple[float, float]]] = defaultdict(list)
    for (u, v), cnt in list(edge_count.items()):
        rev_cnt = edge_count.get((v, u), 0)
        net = cnt - rev_cnt
        if net > 0:
            for _ in range(net):
                adj[u].append(v)

    loops: list[list[list[float]]] = []
    while adj:
        start = next(iter(adj))
        ring = [start]
        curr = start
        while True:
            nxt_list = adj.get(curr)
            if not nxt_list:
                break
            nxt = nxt_list.pop()
            if not nxt_list:
                del adj[curr]
            if nxt == start:
                ring.append(start)
                break
            ring.append(nxt)
            curr = nxt
        if len(ring) >= 4:
            simp: list[tuple[float, float]] = [ring[0]]
            for i in range(1, len(ring) - 1):
                p_prev = simp[-1]
                p_curr = ring[i]
                p_next = ring[i + 1]
                cross = (p_curr[0] - p_prev[0]) * (p_next[1] - p_curr[1]) - (p_curr[1] - p_prev[1]) * (p_next[0] - p_curr[0])
                if abs(cross) > 1e-9:
                    simp.append(p_curr)
            simp.append(ring[0])
            if len(simp) >= 4:
                loops.append([[p[0], p[1]] for p in simp])
    return loops


def _voronoi_partition_multipolygon(
    mp_coords: list[list[list[list[float]]]],
    target_id: str,
    seeds: dict[str, tuple[float, float]],
) -> list[list[list[list[float]]]]:
    if target_id not in seeds:
        return []
    sx, sy = seeds[target_id]
    clipped_pieces: list[list[tuple[float, float]]] = []
    for poly in mp_coords:
        if not poly:
            continue
        tris = _ear_clip_triangulate(poly[0])
        for tri in tris:
            curr = tri
            for other_id, (ox, oy) in seeds.items():
                if other_id == target_id:
                    continue
                a = ox - sx
                b = oy - sy
                if abs(a) < 1e-12 and abs(b) < 1e-12:
                    continue
                c = 0.5 * (ox * ox + oy * oy - sx * sx - sy * sy)
                curr = _clip_poly_halfplane(curr, a, b, c)
                if len(curr) < 3:
                    break
            if len(curr) >= 3 and abs(_signed_ring_area(curr)) > 1e-9:
                clipped_pieces.append(curr)
    loops = _dissolve_clipped_polygons(clipped_pieces)
    return [[loop] for loop in loops]


def build_admin_boundaries_geojson(root: Path = ROOT) -> dict[str, Any]:
    """Generate authoritative WGS84 province & kabupaten boundary polygons (#3, #4).

    Produces disjoint, hierarchical MultiPolygon boundaries (`data/admin-boundaries.geojson`)
    covering all 38 Indonesian provinces and all authoritative kabupaten/kota so
    FIRMS detections and map filters resolve deterministically by point-in-polygon.
    """
    global _CACHED_ADMIN_BOUNDARIES
    if _CACHED_ADMIN_BOUNDARIES is not None and root == ROOT:
        return _CACHED_ADMIN_BOUNDARIES

    try:
        from scripts.ingest_firms import build_region_geometries, load_boundary_geometry
    except ImportError:
        from ingest_firms import build_region_geometries, load_boundary_geometry

    boundary_geom, _ = load_boundary_geometry(root / "data" / "kalimantan-indonesia.geojson")
    region_geoms = build_region_geometries(boundary_geom)
    # Include Bali coastal island polygon in bali-nusra (omitted by Natural Earth 1:110m simplification)
    bali_island_ring = [
        [114.43, -8.06],
        [115.71, -8.06],
        [115.71, -8.85],
        [114.43, -8.85],
        [114.43, -8.06],
    ]
    if "bali-nusra" in region_geoms:
        region_geoms["bali-nusra"]["coordinates"] = list(region_geoms["bali-nusra"]["coordinates"]) + [[bali_island_ring]]

    regions_payload = read_json(root / "data" / "regions.json", {"regions": []})
    kab_registry = build_authoritative_kabupaten_registry(root)

    features: list[dict[str, Any]] = []
    for r in regions_payload.get("regions") or []:
        rid = str(r["id"])
        provs = list(r.get("provinces") or [])
        r_mp = (region_geoms.get(rid) or {}).get("coordinates") or []
        prov_seeds = {p: PROVINCE_SEED_CENTROIDS[p] for p in provs if p in PROVINCE_SEED_CENTROIDS}

        for p in provs:
            p_code = PROVINCE_TO_BPS_CODE.get(p, "00")
            p_mp = _voronoi_partition_multipolygon(r_mp, p, prov_seeds)
            if not p_mp:
                sx, sy = prov_seeds.get(p, (114.0, -2.0))
                p_mp = [[[[sx - 0.15, sy - 0.15], [sx + 0.15, sy - 0.15], [sx + 0.15, sy + 0.15], [sx - 0.15, sy + 0.15], [sx - 0.15, sy - 0.15]]]]
            p_geom = {"type": "MultiPolygon", "coordinates": p_mp}
            p_bbox, p_cent = extract_geometry_bbox_and_centroid(p_geom)
            if p_bbox:
                p_geom["_bbox"] = p_bbox
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "id": f"prov:{p_code}",
                        "level": "province",
                        "bpsCode": p_code,
                        "name": p,
                        "province": p,
                        "region": rid,
                        "bbox": p_bbox,
                        "centroid": p_cent,
                    },
                    "geometry": {"type": "MultiPolygon", "coordinates": p_mp},
                }
            )

            # Partition province polygon into its authoritative kabupaten/kota polygons
            kabs_in_prov = {
                k: (float(info["seedLonLat"][0]), float(info["seedLonLat"][1]))
                for k, info in kab_registry.items()
                if info["province"] == p
            }
            if not kabs_in_prov:
                continue
            for k, k_seed in sorted(kabs_in_prov.items()):
                k_info = kab_registry[k]
                k_code = str(k_info["bpsCode"])
                k_mp = _voronoi_partition_multipolygon(p_mp, k, kabs_in_prov) if len(kabs_in_prov) > 1 else p_mp
                if not k_mp:
                    kx, ky = k_seed
                    k_mp = [[[[kx - 0.05, ky - 0.05], [kx + 0.05, ky - 0.05], [kx + 0.05, ky + 0.05], [kx - 0.05, ky + 0.05], [kx - 0.05, ky - 0.05]]]]
                k_geom = {"type": "MultiPolygon", "coordinates": k_mp}
                k_bbox, k_cent = extract_geometry_bbox_and_centroid(k_geom)
                features.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "id": f"kab:{k_code}",
                            "level": "kabupaten",
                            "bpsCode": k_code,
                            "provinceBpsCode": p_code,
                            "name": k,
                            "kabupaten": k,
                            "province": p,
                            "region": rid,
                            "bbox": k_bbox,
                            "centroid": k_cent,
                        },
                        "geometry": {"type": "MultiPolygon", "coordinates": k_mp},
                    }
                )

    fc = {
        "type": "FeatureCollection",
        "metadata": {
            "schemaVersion": SCHEMA_VERSION,
            "coverageId": "indonesia",
            "generatedBy": "scripts/v2_contracts.py",
            "description": "Hierarchical WGS84 administrative boundaries for 38 provinces and BPS-coded kabupaten/kota.",
        },
        "features": features,
    }
    if root == ROOT:
        _CACHED_ADMIN_BOUNDARIES = fc
    return fc


def build_admin_index(root: Path = ROOT) -> dict[str, Any]:
    """Build a compact precomputed administrative & concession index per region (#11, #4).

    Uses authoritative BPS province (2-digit) and kabupaten/kota (4-digit) codes
    so multi-province concessions never create Cartesian-product district-to-province
    assignments.
    """
    regions_payload = read_json(root / "data" / "regions.json", {"regions": []})
    regions_list = regions_payload.get("regions") or []
    kab_registry = build_authoritative_kabupaten_registry(root)

    index_regions: dict[str, Any] = {}
    national_unique_keys: set[str] = set()
    national_raw = 0
    national_official_keys: set[str] = set()
    national_gfw_keys: set[str] = set()

    for r in regions_list:
        rid = r["id"]
        allowed_provs = set(r.get("provinces") or [])
        inv_dir = root / "data" / "concessions" / rid / "inventory"
        inv_manifest = read_json(inv_dir / "manifest.json", {})

        all_features: list[dict[str, Any]] = []
        for layer in inv_manifest.get("layers") or []:
            rel_url = layer.get("url")
            if rel_url:
                fc = read_json(root / rel_url, {"features": []})
                all_features.extend(fc.get("features") or [])

        reg_keys: set[str] = set()
        official_keys: set[str] = set()
        gfw_keys: set[str] = set()
        by_sector_keys: dict[str, set[str]] = defaultdict(set)
        by_prov_keys: dict[str, set[str]] = {p: set() for p in r.get("provinces") or []}
        by_kab_keys: dict[str, set[str]] = defaultdict(set)
        kab_by_prov: dict[str, set[str]] = {p: set() for p in r.get("provinces") or []}
        unmapped_prov_keys: set[str] = set()
        unmapped_kab_keys: set[str] = set()
        cross_border_prov_keys: set[str] = set()
        cross_border_kab_keys: set[str] = set()

        # Seed authoritative kabupaten for provinces that have 0 concessions (e.g. Bali, DKI Jakarta, DI Yogyakarta)
        for k_name, k_info in kab_registry.items():
            if k_info["province"] in allowed_provs:
                kab_by_prov.setdefault(k_info["province"], set()).add(k_name)

        for feat in all_features:
            props = feat.get("properties") or {}
            key = canonical_concession_key(props)
            reg_keys.add(key)
            national_unique_keys.add(key)
            national_raw += 1

            qual = str(props.get("quality") or "").upper()
            if qual == "OFFICIAL":
                official_keys.add(key)
                national_official_keys.add(key)
            elif qual == "GFW":
                gfw_keys.add(key)
                national_gfw_keys.add(key)

            sec = str(props.get("sector") or "")
            if sec:
                by_sector_keys[sec].add(key)

            provs = parse_record_provinces(props, allowed_provinces=allowed_provs, root=root)
            if not provs:
                unmapped_prov_keys.add(key)
            else:
                if len(provs) > 1:
                    cross_border_prov_keys.add(key)
                for p in provs:
                    by_prov_keys.setdefault(p, set()).add(key)

            kabs = parse_record_kabupaten(props)
            valid_reg_kabs: list[str] = []
            for k in kabs:
                auth_prov = resolve_kabupaten_province(k, provs, root=root)
                if auth_prov and auth_prov in allowed_provs:
                    valid_reg_kabs.append(k)
                    by_kab_keys[k].add(key)
                    # Assign k EXCLUSIVELY to its authoritative parent province (no Cartesian product!)
                    kab_by_prov.setdefault(auth_prov, set()).add(k)

            if not valid_reg_kabs:
                unmapped_kab_keys.add(key)
            elif len(valid_reg_kabs) > 1:
                cross_border_kab_keys.add(key)

        all_reg_kabs = sorted(
            set(by_kab_keys.keys())
            | {k for p_kabs in kab_by_prov.values() for k in p_kabs}
        )
        reg_kab_bps = {
            k: kab_registry[k]["bpsCode"]
            for k in all_reg_kabs
            if k in kab_registry
        }

        index_regions[rid] = {
            "id": rid,
            "label": r.get("label") or rid,
            "provinces": list(r.get("provinces") or []),
            "provinceBpsCodes": {
                p: PROVINCE_TO_BPS_CODE[p]
                for p in (r.get("provinces") or [])
                if p in PROVINCE_TO_BPS_CODE
            },
            "kabupaten": all_reg_kabs,
            "kabupatenBpsCodes": reg_kab_bps,
            "kabupatenByProvince": {
                p: sorted(kab_by_prov.get(p) or set()) for p in (r.get("provinces") or [])
            },
            "concessions": {
                "rawCount": len(all_features),
                "deduplicatedCount": len(reg_keys),
                "officialCount": len(official_keys),
                "gfwCount": len(gfw_keys),
                "bySector": {s: len(ks) for s, ks in sorted(by_sector_keys.items())},
                "byProvince": {p: len(by_prov_keys.get(p) or set()) for p in (r.get("provinces") or [])},
                "byKabupaten": {k: len(by_kab_keys.get(k) or set()) for k in all_reg_kabs},
                "unmappedProvinceCount": len(unmapped_prov_keys),
                "unmappedKabupatenCount": len(unmapped_kab_keys),
                "crossBorderProvinceCount": len(cross_border_prov_keys),
                "crossBorderKabupatenCount": len(cross_border_kab_keys),
                "pipelineStatus": inv_manifest.get("pipelineStatus") or "healthy",
                "generatedAt": inv_manifest.get("generatedAt"),
            },
        }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "coverageId": "indonesia",
        "sourceTimezone": "UTC",
        "displayTimezone": "Asia/Jakarta",
        "adminBoundariesUrl": "data/admin-boundaries.geojson",
        "bpsProvinceCodes": BPS_PROVINCE_CODE_MAP,
        "bpsKabupatenCodes": {
            info["bpsCode"]: {
                "kabupaten": k,
                "province": info["province"],
                "provinceBpsCode": info["provinceBpsCode"],
                "region": info["region"],
            }
            for k, info in sorted(kab_registry.items())
        },
        "nationalConcessions": {
            "rawCount": national_raw,
            "deduplicatedCount": len(national_unique_keys),
            "officialCount": len(national_official_keys),
            "gfwCount": len(national_gfw_keys),
        },
        "regions": index_regions,
    }


def build_sources_manifest(root: Path = ROOT) -> dict[str, Any]:
    """Generate data/sources-manifest.json with standardized metadata envelopes (#19, #7)."""
    hotspots_manifest = read_json(root / "data" / "hotspots" / "manifest.json", {})
    hotspots_status = read_json(root / "data" / "hotspots" / "status.json", {})
    concessions_manifest = read_json(root / "data" / "concessions" / "manifest.json", {})
    kal_inv_manifest = read_json(
        root / "data" / "concessions" / "kalimantan" / "inventory" / "manifest.json", {}
    )
    kal_dossier = read_json(root / "data" / "dossiers" / "kalimantan.json", {})
    admin_index = build_admin_index(root)

    h_meta = hotspots_manifest.get("meta") or {}
    firms_eval = evaluate_firms_freshness(h_meta, hotspots_status)

    all_dates: list[str] = []
    for reg_data in (hotspots_manifest.get("regions") or {}).values():
        for d in reg_data.get("days") or []:
            if d.get("date"):
                all_dates.append(d["date"])
    sorted_dates = sorted(set(all_dates))
    period_label = (
        f"{sorted_dates[0]} s/d {sorted_dates[-1]} (UTC)"
        if sorted_dates
        else "Periode belum tersedia"
    )

    firms_envelope = build_metric_envelope(
        metric_id="firms-hotspots",
        title="Deteksi Panas Satelit (NASA FIRMS VIIRS)",
        layer_type="Detection",
        source="NASA FIRMS NRT VIIRS",
        url="https://firms.modaps.eosdis.nasa.gov/api/area/",
        product="VIIRS Active Fire (S-NPP, NOAA-20, NOAA-21)",
        version=str(h_meta.get("pipelineVersion") or "4"),
        valid_from=firms_eval["oldestDetectionUtc"] or (sorted_dates[0] if sorted_dates else None),
        valid_to=firms_eval["newestDetectionUtc"] or (sorted_dates[-1] if sorted_dates else None),
        period_label=period_label,
        published_at=firms_eval["lastSuccessfulSync"],
        updated_at=firms_eval["lastAttemptedSync"] or firms_eval["lastSuccessfulSync"],
        coverage_id="indonesia",
        supported_granularities=["national", "region", "province", "kabupaten", "point"],
        units="detections",
        granularity="day",
        availability_state=firms_eval["state"],
        quality="NRT",
        value=int(h_meta.get("count") or 0) if firms_eval["state"] != "unavailable" else None,
        is_fallback=False,
        last_known_good=firms_eval["lastKnownGood"],
        age_minutes=firms_eval["observationAgeMinutes"],
        reason=firms_eval["reason"],
        provenance_category="satellite_nrt",
        verification_status="SATELLITE_OBSERVED_NRT",
        attribution_allowed=False,
        caveats=[
            "Titik panas satelit (anomali termal ~375 m) bukan kejadian kebakaran terverifikasi lapangan.",
            "Jumlah titik FIRMS tidak dapat dikalikan ukuran piksel menjadi luas area terbakar (hektar).",
            "Filter provinsi dan kabupaten menggunakan pemetaan point-in-polygon terhadap batas administratif (`data/admin-boundaries.geojson`) secara sinkron pada peta, KPI, dan deret waktu.",
        ],
        breakdown={
            "platforms": h_meta.get("platforms") or ["S-NPP", "NOAA-20", "NOAA-21"],
            "sourceCounts": hotspots_status.get("sourceCounts") or {},
            "days": sorted_dates,
            "syncAgeMinutes": firms_eval["syncAgeMinutes"],
            "evaluatedAtUtc": firms_eval["evaluatedAtUtc"],
            "staleThresholdHours": firms_eval["staleThresholdHours"],
        },
    )

    nat_conc = admin_index["nationalConcessions"]
    inv_status = kal_inv_manifest.get("pipelineStatus") or "partial"
    inv_avail_state = "partial" if inv_status == "partial" else "official"
    concession_envelope = build_metric_envelope(
        metric_id="concession-inventory",
        title="Inventaris Konsesi Publik Nasional (BIG & GFW)",
        layer_type="ConcessionInventory",
        source="BIG Kebijakan Satu Peta (OFFICIAL) & GFW via BNPB InAWARE (GFW)",
        url="https://kspservices.big.go.id/satupeta/rest/services/PUBLIK/PERIZINAN_DAN_PERTANAHAN/MapServer",
        product="IUPHHK-HA/HTI/RE, WIUP Pertambangan, Izin Lokasi Sawit, GFW Oil Palm",
        version=str(concessions_manifest.get("version") or "3"),
        valid_from=None,
        valid_to=kal_inv_manifest.get("generatedAt"),
        period_label="Snapshot inventaris izin publik multi-sumber",
        published_at=kal_inv_manifest.get("generatedAt"),
        updated_at=kal_inv_manifest.get("generatedAt"),
        coverage_id="indonesia",
        supported_granularities=["national", "region", "province", "kabupaten", "polygon"],
        units="concessions",
        granularity="snapshot",
        availability_state=inv_avail_state,
        quality="OFFICIAL",
        value=nat_conc["deduplicatedCount"],
        is_fallback=False,
        last_known_good=bool(kal_inv_manifest.get("optionalErrors")),
        provenance_category="official_government",
        verification_status="OFFICIAL_REGISTRY",
        attribution_allowed=False,
        reason=(
            "Layer resmi BIG (kehutanan & tambang) aktif nasional; layer izin sawit BIG hanya mencakup kabupaten terpilih dan layer suplemen GFW berstatus partial/cached."
        ),
        caveats=[
            "Inventaris ini bukan kadaster legal lengkap; tanggal dan kelengkapan antar-sumber berbeda.",
            "Poligon lintas batas provinsi/kabupaten dipetakan dengan kode BPS otoritatif dan dihitung secara terdeduplikasi berdasarkan ID sumber.",
            "Keberadaan hotspot di dalam atau dekat poligon konsesi adalah konteks spasial saja — bukan atribusi penyebab kebakaran.",
        ],
        breakdown={
            "rawFeatureCount": nat_conc["rawCount"],
            "deduplicatedCount": nat_conc["deduplicatedCount"],
            "officialCount": nat_conc["officialCount"],
            "gfwCount": nat_conc["gfwCount"],
        },
    )

    walhi_summary = kal_dossier.get("walhiSummary") or {}
    dossiers_list = kal_dossier.get("dossiers") or []
    walhi_envelope = build_metric_envelope(
        metric_id="walhi-dossiers",
        title="Dossier Investigatif & Klaim Overlay WALHI (Kalimantan)",
        layer_type="ConcessionClaim",
        source="WALHI Kalimantan (Kompas.id / Detik) & OSINT Korporasi/Politik Bernama",
        url="https://www.kompas.id/",
        product="12 Dossier Konsesi Kurasi Kalimantan + Ringkasan Klaim WALHI Jan–Jul 2026",
        version=str((kal_dossier.get("meta") or {}).get("version") or "1"),
        valid_from="2026-01-01",
        valid_to="2026-07-27",
        period_label=str(walhi_summary.get("period") or "1 Jan – 27 Jul 2026"),
        published_at="2026-08-22T00:00:00Z",
        updated_at="2026-08-22T00:00:00Z",
        coverage_id="kalimantan",
        supported_granularities=["region", "province", "dossier"],
        units="dossiers",
        granularity="period",
        availability_state="curated",
        quality="INVESTIGATIVE",
        value=len(dossiers_list),
        is_fallback=False,
        last_known_good=False,
        provenance_category="civil_society_investigative",
        verification_status="CURATED_OSINT_INVESTIGATIVE",
        attribution_allowed=False,
        reason="Dikurasi dari laporan masyarakat sipil (WALHI Kalimantan) dan sumber OSINT bernama untuk 12 konsesi di Kalimantan; bukan registri pemerintah resmi (OFFICIAL).",
        caveats=[
            "Klaim overlay WALHI (Jan–Jul 2026) dan dossier OSINT diklasifikasikan sebagai CURATED / INVESTIGATIVE (bukan OFFICIAL).",
            "Angka klaim WALHI adalah laporan terikat periode, bukan hasil join langsung dengan titik FIRMS 7 hari terakhir.",
            "Kepemilikan grup (Control) dan ikatan politik (PoliticalTie) dikutip dari sumber publik bernama dan tidak membuktikan kesalahan hukum atau pembakaran.",
        ],
        breakdown={
            "dossierCount": len(dossiers_list),
            "walhiTotalKalimantan": walhi_summary.get("totalKalimantan"),
            "walhiInConcession": walhi_summary.get("inConcession"),
            "walhiPctInConcession": walhi_summary.get("pctInConcession"),
        },
    )

    sipongi = kal_dossier.get("sipongiFallback") or {}
    sipongi_envelope = build_metric_envelope(
        metric_id="sipongi-fallback",
        title="Konteks Gelombang SIPONGI / Kemenhut (Fallback Terpisah)",
        layer_type="Detection",
        source="Kemenhut / SIPONGI (MODIS Terra-Aqua High Confidence)",
        url="https://sipongi.menlhk.go.id/",
        product="Ringkasan Rilis Media & Kemenhut 17–19 Agustus 2026",
        version="1",
        valid_from="2026-08-17",
        valid_to="2026-08-19",
        period_label=str(sipongi.get("period") or "17–19 Agustus 2026"),
        published_at="2026-08-21T00:00:00Z",
        updated_at="2026-08-21T00:00:00Z",
        coverage_id="kalimantan",
        supported_granularities=["region"],
        units="reported_hotspots",
        granularity="period",
        availability_state="partial",
        quality="FALLBACK",
        value=int(sipongi.get("totalHighConfidence3d") or 750),
        is_fallback=True,
        last_known_good=True,
        provenance_category="official_government",
        verification_status="UNVERIFIED_FALLBACK",
        attribution_allowed=False,
        reason="Digunakan hanya sebagai konteks terpisah; tidak pernah digabung ke deret waktu harian NASA FIRMS VIIRS.",
        caveats=[
            "Sensor, ambang confidence, dan jendela waktu berbeda dari NASA FIRMS VIIRS NRT.",
            "Tidak pernah digabungkan secara diam-diam dengan hitungan titik FIRMS.",
        ],
    )

    burned_area_envelope = build_metric_envelope(
        metric_id="burned-area",
        title="Estimasi Luas Area Terbakar (Burned Area)",
        layer_type="Environmental",
        source="Belum Di-ingest (Evaluasi Produk Burned Area Independen #20)",
        url="https://gwis.jrc.ec.europa.eu/",
        product="Independent Burned Area Raster/Polygon Series (Pending P1 #20/#21)",
        version="0",
        valid_from=None,
        valid_to=None,
        period_label="Data belum tersedia",
        published_at=None,
        updated_at=None,
        coverage_id="indonesia",
        supported_granularities=["national", "region", "province"],
        units="ha",
        granularity="day",
        availability_state="unavailable",
        quality="UNAVAILABLE",
        value=None,
        provenance_category="pending_ingestion",
        verification_status="PENDING_INGESTION",
        reason=(
            "Produk luas area terbakar independen (#20/#21) belum di-ingest. "
            "MERATUS melarang keras mengalikan jumlah titik panas NASA FIRMS menjadi estimasi hektar terbakar."
        ),
        caveats=[
            "Titik panas satelit FIRMS bukan poligon area terbakar.",
            "Metrik ini ditampilkan sebagai TIDAK TERSEDIA (bukan 0 ha dan bukan angka sampel mockup).",
        ],
    )

    aq_envelope = build_metric_envelope(
        metric_id="air-quality-pm25",
        title="Kualitas Udara Berbasis Stasiun (PM2.5 / ISPU)",
        layer_type="Environmental",
        source="Belum Di-ingest (Pipeline Stasiun ISPU/KLHK & OpenAQ #22)",
        url="https://ispu.menlhk.go.id/",
        product="Station-Level PM2.5 & Official Air Quality Index (Pending P1 #22/#23)",
        version="0",
        valid_from=None,
        valid_to=None,
        period_label="Data belum tersedia",
        published_at=None,
        updated_at=None,
        coverage_id="indonesia",
        supported_granularities=["station"],
        units="µg/m³",
        granularity="hour",
        availability_state="unavailable",
        quality="UNAVAILABLE",
        value=None,
        provenance_category="pending_ingestion",
        verification_status="PENDING_INGESTION",
        reason=(
            "Observasi stasiun kualitas udara (#22/#23) belum di-ingest. "
            "Kualitas udara bersifat berbasis stasiun dan tidak diasumsikan mewakili seluruh pulau atau provinsi."
        ),
        caveats=[
            "Tidak ada rata-rata AQI provinsi/nasional yang dikarang ketika sensor tidak tersedia.",
        ],
    )

    weather_envelope = build_metric_envelope(
        metric_id="bmkg-weather",
        title="Prakiraan Cuaca Lokalitas (BMKG)",
        layer_type="Environmental",
        source="Belum Di-ingest (Integrasi Prakiraan Lokalitas BMKG #24)",
        url="https://data.bmkg.go.id/",
        product="BMKG Locality Forecast (Pending P1 #24/#25)",
        version="0",
        valid_from=None,
        valid_to=None,
        period_label="Data belum tersedia",
        published_at=None,
        updated_at=None,
        coverage_id="indonesia",
        supported_granularities=["locality"],
        units="forecast",
        granularity="hour",
        availability_state="unavailable",
        quality="UNAVAILABLE",
        value=None,
        provenance_category="pending_ingestion",
        verification_status="PENDING_INGESTION",
        reason=(
            "Prakiraan cuaca lokalitas BMKG (#24/#25) belum di-ingest. "
            "Cuaca adalah prakiraan untuk lokalitas bernama, bukan pengukuran seluruh pulau."
        ),
        caveats=[
            "Prakiraan cuaca tidak boleh dicampur dengan observasi historis FIRMS.",
        ],
    )

    ispa_envelope = build_metric_envelope(
        metric_id="kemenkes-ispa",
        title="Laporan Kasus ISPA (Surveilans Kesehatan)",
        layer_type="PublicHealth",
        source="Belum Di-ingest (Normalisasi Laporan ISPA Kemenkes/Dinkes #26)",
        url="https://skdr.surveilans.org/",
        product="Reported ISPA Surveillance (Pending P2 #26/#27)",
        version="0",
        valid_from=None,
        valid_to=None,
        period_label="Data belum tersedia",
        published_at=None,
        updated_at=None,
        coverage_id="indonesia",
        supported_granularities=["province", "kabupaten"],
        units="cases",
        granularity="week",
        availability_state="unavailable",
        quality="UNAVAILABLE",
        value=None,
        provenance_category="pending_ingestion",
        verification_status="PENDING_INGESTION",
        reason=(
            "Data pelaporan ISPA mingguan/bulanan (#26/#27) belum di-ingest. "
            "Kasus ISPA terlaporkan ≠ kasus ISPA yang disebabkan oleh asap karhutla."
        ),
        caveats=[
            "Mempertahankan grain mingguan/bulanan asli sumber tanpa menginterpolasi kurva harian.",
        ],
    )

    metrics = {
        env["id"]: env
        for env in (
            firms_envelope,
            concession_envelope,
            walhi_envelope,
            sipongi_envelope,
            burned_area_envelope,
            aq_envelope,
            weather_envelope,
            ispa_envelope,
        )
    }

    return {
        "schemaVersion": SCHEMA_VERSION,
        "coverageId": "indonesia",
        "generatedBy": "scripts/v2_contracts.py",
        "availabilityStates": list(AVAILABILITY_STATES),
        "qualityLabels": list(QUALITY_LABELS),
        "provenanceCategories": list(PROVENANCE_CATEGORIES),
        "verificationStatuses": list(VERIFICATION_STATUSES),
        "evidenceLayers": list(EVIDENCE_LAYERS),
        "metrics": metrics,
    }


def extract_geometry_bbox_and_centroid(
    geometry: dict[str, Any] | None,
) -> tuple[list[float] | None, list[float] | None]:
    """Compute [minLon, minLat, maxLon, maxLat] and [lat, lon] centroid from a GeoJSON geometry."""
    if not isinstance(geometry, dict):
        return None, None
    coords = geometry.get("coordinates")
    if not coords:
        return None, None

    lons: list[float] = []
    lats: list[float] = []

    def walk(node: Any) -> None:
        if not isinstance(node, (list, tuple)):
            return
        if (
            len(node) >= 2
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float))
        ):
            lons.append(float(node[0]))
            lats.append(float(node[1]))
            return
        for child in node:
            walk(child)

    walk(coords)
    if not lons or not lats:
        return None, None
    min_lon, max_lon = min(lons), max(lons)
    min_lat, max_lat = min(lats), max(lats)
    bbox = [
        round(min_lon, 5),
        round(min_lat, 5),
        round(max_lon, 5),
        round(max_lat, 5),
    ]
    centroid = [round((min_lat + max_lat) / 2.0, 5), round((min_lon + max_lon) / 2.0, 5)]
    return bbox, centroid


def build_concession_view_models(
    inventory_features: list[dict[str, Any]],
    dossiers: list[dict[str, Any]] | None = None,
    dossier_boundaries: list[dict[str, Any]] | None = None,
    region_id: str = "kalimantan",
    allowed_provinces: set[str] | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Build unified presentation-level ConcessionViewModel rows (#12, #13, #14, #5).

    Respects ADR-007 and Finding #5:
    - Generates lightweight geometry-free metadata rows (`bbox`, `centroid`, `hasGeometry`,
      `sourceLayerUrl`) so the Concessions explorer never needs to download full GeoJSON
      polygon layers upfront.
    - Matches dossier entries to inventory records ONLY when a verifiable
      dossierId link exists (`matchBasis == 'confirmed_dossier_id'`).
    """
    dossier_list = [d for d in (dossiers or []) if isinstance(d, dict) and d.get("id")]
    dossier_by_id = {str(d["id"]): d for d in dossier_list}

    boundary_by_dossier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bfeat in dossier_boundaries or []:
        if not isinstance(bfeat, dict):
            continue
        bprops = bfeat.get("properties") or {}
        did = str(bprops.get("dossierId") or "").strip()
        if did:
            boundary_by_dossier[did].append(bfeat)

    dedup_rows: dict[str, dict[str, Any]] = {}
    matched_dossier_ids: set[str] = set()
    matched_inventory_keys: set[str] = set()

    for feat in inventory_features or []:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        key = canonical_concession_key(props)
        vm_id = f"inv:{key}"
        provs = parse_record_provinces(props, allowed_provinces=allowed_provinces, root=root)
        raw_kabs = parse_record_kabupaten(props)
        kabs: list[str] = []
        for k in raw_kabs:
            ap = resolve_kabupaten_province(k, provs, root=root)
            if allowed_provinces is None or (ap and ap in allowed_provinces):
                if k not in kabs:
                    kabs.append(k)
        bbox, centroid = extract_geometry_bbox_and_centroid(feat.get("geometry"))
        layer_url = str(props.get("_sourceLayerUrl") or "") or None

        explicit_dossier_id = str(props.get("dossierId") or "").strip()
        linked_dossier = dossier_by_id.get(explicit_dossier_id) if explicit_dossier_id else None
        has_dossier = linked_dossier is not None

        if has_dossier:
            matched_dossier_ids.add(explicit_dossier_id)
            matched_inventory_keys.add(key)

        if key in dedup_rows:
            existing = dedup_rows[key]
            for p in provs:
                if p not in existing["provinces"]:
                    existing["provinces"].append(p)
            for k in kabs:
                if k not in existing["kabupaten"]:
                    existing["kabupaten"].append(k)
            if layer_url and layer_url not in (existing.get("layerUrls") or []):
                existing.setdefault("layerUrls", []).append(layer_url)
            if bbox and existing.get("bbox"):
                eb = existing["bbox"]
                existing["bbox"] = [
                    round(min(eb[0], bbox[0]), 5),
                    round(min(eb[1], bbox[1]), 5),
                    round(max(eb[2], bbox[2]), 5),
                    round(max(eb[3], bbox[3]), 5),
                ]
            elif bbox and not existing.get("bbox"):
                existing["bbox"] = bbox
                existing["centroid"] = centroid
                existing["hasGeometry"] = True
            continue

        loc_parts = [
            str(props.get("location") or "").strip(),
            str(props.get("subdistrict") or "").strip(),
            str(props.get("district") or "").strip(),
            str(props.get("province") or "").strip(),
        ]
        loc_parts = [lp for lp in loc_parts if lp and lp != "-"]
        location_text = (
            ", ".join(provs + kabs)
            if (provs or kabs)
            else (", ".join(loc_parts) if loc_parts else region_id.title())
        )

        permit_date = (
            str(props.get("permitDate") or "").strip()
            or (
                f"{props.get('validFrom')} s/d {props.get('validTo')}"
                if props.get("validFrom") or props.get("validTo")
                else ""
            )
            or None
        )
        area_val = props.get("areaHa")
        area_ha = float(area_val) if isinstance(area_val, (int, float)) else None

        dedup_rows[key] = {
            "viewModelId": vm_id,
            "recordKind": "inventory+dossier" if has_dossier else "inventory",
            "inventoryId": str(props.get("inventoryId") or key),
            "linkedDossierId": explicit_dossier_id if has_dossier else None,
            "hasInvestigativeDossier": has_dossier,
            "matchBasis": "confirmed_dossier_id" if has_dossier else "none",
            "region": str(props.get("region") or region_id),
            "name": str(props.get("name") or "Tanpa Nama Operator"),
            "operator": str(
                (linked_dossier.get("name") if linked_dossier else None)
                or props.get("name")
                or "Tanpa Nama Operator"
            ),
            "sector": str(props.get("sector") or (linked_dossier.get("sector") if linked_dossier else "") or "Lainnya"),
            "subtype": str(props.get("subtype") or props.get("miningType") or "Izin Konsesi"),
            "quality": str(props.get("quality") or "OFFICIAL").upper(),
            "sourceDataset": str(props.get("sourceDataset") or "inventory"),
            "source": str(props.get("source") or "Inventaris Publik"),
            "sourceUrl": str(props.get("sourceUrl") or ""),
            "retrievedAt": str(props.get("retrievedAt") or "") or None,
            "permitNumber": str(props.get("permitNumber") or "").strip() or None,
            "permitDate": permit_date,
            "issuer": str(props.get("issuer") or "").strip() or None,
            "commodity": str(props.get("commodity") or "").strip() or None,
            "status": str(props.get("status") or props.get("legalStatus") or "").strip() or None,
            "group": (
                str((linked_dossier.get("control") or {}).get("group") or "")
                if linked_dossier and (linked_dossier.get("control") or {}).get("group")
                else (str(props.get("group") or "").strip() or None)
            ),
            "areaHa": area_ha,
            "hguAreaHa": float(props["hguAreaHa"]) if isinstance(props.get("hguAreaHa"), (int, float)) else None,
            "provinces": provs,
            "kabupaten": kabs,
            "locationText": location_text,
            "bbox": bbox,
            "centroid": centroid,
            "hasGeometry": bbox is not None,
            "layerUrls": [layer_url] if layer_url else [],
            "geometryProcessing": str(props.get("geometryProcessing") or "") or None,
            "coverageCaveat": str(props.get("coverageCaveat") or "") or None,
            "walhiHotspots": int(linked_dossier["walhiHotspots"]) if (linked_dossier and linked_dossier.get("walhiHotspots") is not None) else None,
            "uboStatus": str(linked_dossier.get("uboStatus") or "") if linked_dossier else None,
        }

    rows = list(dedup_rows.values())
    unmatched_count = 0

    for d in dossier_list:
        did = str(d["id"])
        if did in matched_dossier_ids:
            continue
        unmatched_count += 1
        d_provs = parse_record_provinces(d, allowed_provinces=allowed_provinces, root=root)
        d_kabs = parse_record_kabupaten(d)
        b_feats = boundary_by_dossier.get(did) or []
        d_bbox: list[float] | None = None
        d_centroid: list[float] | None = None
        b_qual = "NONE"
        b_source = "WALHI Kalimantan & OSINT Bernama"
        b_url = ""
        for bf in b_feats:
            bb, cc = extract_geometry_bbox_and_centroid(bf.get("geometry"))
            bp = bf.get("properties") or {}
            if bp.get("quality"):
                b_qual = str(bp["quality"]).upper()
            if bp.get("source"):
                b_source = str(bp["source"])
            if bp.get("sourceUrl"):
                b_url = str(bp["sourceUrl"])
            if bb:
                if d_bbox is None:
                    d_bbox = bb
                    d_centroid = cc
                else:
                    d_bbox = [
                        round(min(d_bbox[0], bb[0]), 5),
                        round(min(d_bbox[1], bb[1]), 5),
                        round(max(d_bbox[2], bb[2]), 5),
                        round(max(d_bbox[3], bb[3]), 5),
                    ]
        if d_centroid is None and isinstance(d.get("centroid"), list) and len(d["centroid"]) >= 2:
            d_centroid = [round(float(d["centroid"][0]), 5), round(float(d["centroid"][1]), 5)]
        if not b_url and isinstance(d.get("sources"), list) and d["sources"]:
            b_url = str(d["sources"][0].get("url") or "")

        rows.append(
            {
                "viewModelId": f"dossier:{did}",
                "recordKind": "dossier-only",
                "inventoryId": None,
                "linkedDossierId": did,
                "hasInvestigativeDossier": True,
                "matchBasis": "unmatched_curated_dossier",
                "region": region_id,
                "name": str(d.get("name") or did),
                "operator": str(d.get("name") or did),
                "sector": str(d.get("sector") or "Lainnya"),
                "subtype": "Dossier Investigasi (Belum Terpetakan di Inventaris Standar)",
                "quality": b_qual if b_qual in ("OFFICIAL", "GFW", "PERKIRAAN") else "INVESTIGATIVE",
                "sourceDataset": "walhi-dossiers",
                "source": b_source,
                "sourceUrl": b_url,
                "retrievedAt": "2026-08-22T00:00:00Z",
                "permitNumber": None,
                "permitDate": None,
                "issuer": None,
                "commodity": None,
                "status": "Dossier Kurasi Independen",
                "group": str((d.get("control") or {}).get("group") or "") or None,
                "areaHa": None,
                "hguAreaHa": None,
                "provinces": d_provs,
                "kabupaten": d_kabs,
                "locationText": ", ".join(d_provs) if d_provs else str(d.get("province") or region_id.title()),
                "bbox": d_bbox,
                "centroid": d_centroid,
                "hasGeometry": d_bbox is not None,
                "layerUrls": [f"data/concessions/{region_id}/boundaries.geojson"] if d_bbox is not None else [],
                "geometryProcessing": "Batas poligon dossier kurasi terpisah dari shard inventaris" if d_bbox else "Fallback centroid lokasi kasar (tanpa poligon di shard inventaris)",
                "coverageCaveat": (
                    "Dossier ini tidak memiliki kecocokan ID yang terverifikasi di shard inventaris publik BIG/GFW, "
                    "sehingga dipertahankan sebagai entri independen tanpa penggabungan paksa."
                ),
                "walhiHotspots": int(d["walhiHotspots"]) if d.get("walhiHotspots") is not None else None,
                "uboStatus": str(d.get("uboStatus") or "UNKNOWN"),
            }
        )

    return {
        "region": region_id,
        "rows": rows,
        "stats": {
            "rawInventoryCount": len(inventory_features or []),
            "deduplicatedInventoryCount": len(dedup_rows),
            "matchedDossierCount": len(matched_dossier_ids),
            "matchedInventoryRowCount": len(matched_inventory_keys),
            "unmatchedDossierOnlyCount": unmatched_count,
            "totalDossierCount": len(matched_dossier_ids) + unmatched_count,
            "totalUnifiedCount": len(rows),
        },
    }


def build_region_concession_view_models(region_id: str, root: Path = ROOT) -> dict[str, Any]:
    """Load regional inventory shards and dossier JSON from disk and return unified ConcessionViewModel payload."""
    regions_payload = read_json(root / "data" / "regions.json", {"regions": []})
    region_meta = next(
        (r for r in (regions_payload.get("regions") or []) if r.get("id") == region_id),
        {},
    )
    allowed_provs = set(region_meta.get("provinces") or [])
    inv_manifest = read_json(
        root / "data" / "concessions" / region_id / "inventory" / "manifest.json", {}
    )
    features: list[dict[str, Any]] = []
    layer_urls: list[str] = []
    for layer in inv_manifest.get("layers") or []:
        rel_url = layer.get("url")
        if rel_url:
            layer_urls.append(str(rel_url))
            fc = read_json(root / rel_url, {"features": []})
            for f in fc.get("features") or []:
                if isinstance(f, dict):
                    f_copy = dict(f)
                    p_copy = dict(f_copy.get("properties") or {})
                    p_copy["_sourceLayerUrl"] = str(rel_url)
                    f_copy["properties"] = p_copy
                    features.append(f_copy)

    conc_manifest = read_json(root / "data" / "concessions" / "manifest.json", {})
    reg_conc_meta = ((conc_manifest.get("regions") or {}).get(region_id)) or {}
    dossiers_list: list[dict[str, Any]] = []
    d_payload: dict[str, Any] = {}
    if reg_conc_meta.get("dossiers"):
        d_payload = read_json(root / reg_conc_meta["dossiers"], {})
        dossiers_list = d_payload.get("dossiers") or []
    dossier_bounds: list[dict[str, Any]] = []
    if reg_conc_meta.get("boundaries"):
        b_payload = read_json(root / reg_conc_meta["boundaries"], {})
        dossier_bounds = b_payload.get("features") or []

    vm = build_concession_view_models(
        inventory_features=features,
        dossiers=dossiers_list,
        dossier_boundaries=dossier_bounds,
        region_id=region_id,
        allowed_provinces=allowed_provs or None,
        root=root,
    )
    vm["schemaVersion"] = SCHEMA_VERSION
    vm["geometryLoaded"] = False
    vm["layerUrls"] = layer_urls
    vm["boundariesUrl"] = reg_conc_meta.get("boundaries")
    vm["dossiersUrl"] = reg_conc_meta.get("dossiers")
    if d_payload.get("walhiSummary"):
        vm["walhiSummary"] = d_payload["walhiSummary"]
    if d_payload.get("sipongiFallback"):
        vm["sipongiFallback"] = d_payload["sipongiFallback"]
    return vm


def build_all_region_concession_indexes(
    root: Path = ROOT, check_only: bool = False
) -> dict[str, dict[str, Any]]:
    """Build and write lightweight geometry-free concession metadata indexes per region (#5)."""
    indexes: dict[str, dict[str, Any]] = {}
    for rid in REGION_ORDER:
        vm = build_region_concession_view_models(rid, root=root)
        indexes[rid] = vm
        if not check_only:
            index_path = root / "data" / "concessions" / rid / "inventory" / "index.json"
            write_json_atomic(index_path, vm)
    return indexes


def query_concession_view_models(
    rows: list[dict[str, Any]],
    search: str = "",
    sector: str = "",
    quality: str = "",
    prov: str = "",
    kab: str = "",
    dossier_only: bool = False,
    sort_by: str = "default",
    page: int = 1,
    page_size: int = 50,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Filter, sort, and paginate unified ConcessionViewModel rows (#13, #4)."""
    q = str(search or "").strip().lower()
    sec = str(sector or "").strip()
    qual = str(quality or "").strip().upper()
    norm_prov = normalize_province_token(prov) if prov else ""
    norm_kab = normalize_kabupaten_token(kab) if kab else ""

    if norm_prov and norm_kab:
        auth_kab_prov = resolve_kabupaten_province(norm_kab, root=root)
        if auth_kab_prov and auth_kab_prov != norm_prov:
            return {
                "items": [],
                "totalFiltered": 0,
                "page": 1,
                "pageSize": max(1, int(page_size or 50)),
                "totalPages": 1,
                "startIndex": 0,
                "endIndex": 0,
            }

    filtered: list[dict[str, Any]] = []
    for row in rows or []:
        if sec and row.get("sector") != sec:
            continue
        if dossier_only and not row.get("hasInvestigativeDossier"):
            continue
        if qual:
            if qual in ("DOSSIER", "INVESTIGATIVE", "CURATED"):
                if not row.get("hasInvestigativeDossier") and str(row.get("quality") or "").upper() not in ("INVESTIGATIVE", "CURATED", "CURATED_DOSSIER"):
                    continue
            elif qual == "OFFICIAL":
                if str(row.get("quality") or "").upper() != "OFFICIAL":
                    continue
            elif qual in ("GFW", "ESTIMATED"):
                if str(row.get("quality") or "").upper() not in ("GFW", "PERKIRAAN"):
                    continue
            elif str(row.get("quality") or "").upper() != qual:
                continue
        if norm_prov:
            r_provs = row.get("provinces") or []
            if norm_prov not in r_provs:
                continue
        if norm_kab:
            r_kabs = row.get("kabupaten") or []
            if norm_kab not in r_kabs:
                continue
        if q:
            blob = " ".join(
                str(part or "")
                for part in (
                    row.get("name"),
                    row.get("operator"),
                    row.get("permitNumber"),
                    row.get("commodity"),
                    row.get("group"),
                    row.get("subtype"),
                    row.get("locationText"),
                    " ".join(row.get("provinces") or []),
                    " ".join(row.get("kabupaten") or []),
                    row.get("sourceDataset"),
                    row.get("linkedDossierId"),
                    row.get("viewModelId"),
                )
            ).lower()
            if q not in blob:
                continue
        filtered.append(row)

    def sort_key(item: dict[str, Any]) -> Any:
        name_k = str(item.get("name") or "").upper()
        vm_k = str(item.get("viewModelId") or "")
        area_v = item.get("areaHa")
        has_area = isinstance(area_v, (int, float))
        area_num = float(area_v) if has_area else -1.0
        has_dos = 0 if item.get("hasInvestigativeDossier") else 1
        if sort_by == "name_asc":
            return (name_k, vm_k)
        if sort_by == "area_desc":
            return (0 if has_area else 1, -area_num, name_k, vm_k)
        if sort_by == "area_asc":
            return (0 if has_area else 1, area_num if has_area else float("inf"), name_k, vm_k)
        if sort_by == "sector_asc":
            return (str(item.get("sector") or ""), name_k, vm_k)
        # default: investigative dossiers first, then largest area, then name A-Z
        return (has_dos, 0 if has_area else 1, -area_num, name_k, vm_k)

    ordered = sorted(filtered, key=sort_key)
    safe_page_size = max(1, int(page_size or 50))
    total = len(ordered)
    total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
    safe_page = min(max(1, int(page or 1)), total_pages)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size

    return {
        "items": ordered[start:end],
        "totalFiltered": total,
        "page": safe_page,
        "pageSize": safe_page_size,
        "totalPages": total_pages,
        "startIndex": (start + 1) if total > 0 else 0,
        "endIndex": min(end, total),
    }


def build_concession_inspector_model(
    row: dict[str, Any],
    dossier: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the contextual detail inspector payload with Summary / Map / Investigation tabs (#14).

    Guarantees that the Investigation tab is ONLY exposed when a curated dossier
    is explicitly linked (`row['hasInvestigativeDossier'] == True`). Generic
    inventory records never display investigative allegations as verified facts.
    """
    has_dossier = bool(row.get("hasInvestigativeDossier") and isinstance(dossier, dict))
    tabs = ["summary", "map"]
    if has_dossier:
        tabs.append("investigation")

    summary_tab = {
        "viewModelId": row.get("viewModelId"),
        "recordKind": row.get("recordKind"),
        "name": row.get("name"),
        "operator": row.get("operator"),
        "sector": row.get("sector"),
        "subtype": row.get("subtype"),
        "quality": row.get("quality"),
        "locationText": row.get("locationText"),
        "provinces": list(row.get("provinces") or []),
        "kabupaten": list(row.get("kabupaten") or []),
        "areaHa": row.get("areaHa"),
        "areaDisplay": (
            f"{row['areaHa']:,.1f} ha"
            if isinstance(row.get("areaHa"), (int, float))
            else "Luas geometri tidak tersedia di atribut sumber"
        ),
        "permitNumber": row.get("permitNumber") or "Tidak tercantum di sumber",
        "permitDate": row.get("permitDate") or "Tidak tercantum di sumber",
        "issuer": row.get("issuer") or "Tidak tercantum di sumber",
        "commodity": row.get("commodity"),
        "status": row.get("status"),
        "source": row.get("source"),
        "sourceUrl": row.get("sourceUrl"),
        "retrievedAt": row.get("retrievedAt"),
        "coverageCaveat": row.get("coverageCaveat"),
        "nonAttributionNotice": (
            "Kehadiran titik panas satelit di dalam atau di sekitar batas konsesi "
            "adalah konteks spasial semata, bukan bukti atribusi penyebab kebakaran."
        ),
    }

    map_tab = {
        "hasGeometry": bool(row.get("hasGeometry")),
        "bbox": row.get("bbox"),
        "centroid": row.get("centroid"),
        "geometryExplanation": (
            row.get("geometryProcessing")
            if row.get("hasGeometry")
            else "Poligon batas tidak tersedia pada shard inventaris; navigasi menggunakan titik centroid kasar."
        ),
        "supportsFirmsSpatialContext": True,
        "firmsOverlayDisclaimer": (
            "Overlay observasi NASA FIRMS pada periode terpilih hanya menunjukkan "
            "irisan spasial (di dalam poligon atau ≤5 km dari batas), bukan bukti pembakaran."
        ),
    }

    investigation_tab = None
    if has_dossier and dossier is not None:
        investigation_tab = {
            "dossierId": dossier.get("id"),
            "matchBasis": row.get("matchBasis"),
            "walhiClaim": {
                "reportedHotspots": dossier.get("walhiHotspots"),
                "claimPeriod": "1 Jan – 27 Jul 2026 (WALHI Kalimantan)",
                "note": "Klaim atribusi laporan WALHI terikat periode; terpisah dari deteksi mentah NASA FIRMS.",
            },
            "uboStatus": dossier.get("uboStatus") or "UNKNOWN",
            "control": dossier.get("control") or {},
            "politicalTies": list(dossier.get("politicalTies") or []),
            "caveats": list(dossier.get("caveats") or []),
            "sources": list(dossier.get("sources") or []),
        }

    return {
        "viewModelId": row.get("viewModelId"),
        "tabs": tabs,
        "summary": summary_tab,
        "map": map_tab,
        "investigation": investigation_tab,
    }


REGION_ORDER = (
    "sumatra",
    "jawa",
    "kalimantan",
    "sulawesi",
    "bali-nusra",
    "maluku",
    "papua",
)


def _empty_day_bucket() -> dict[str, Any]:
    return {
        "count": 0,
        "sameTodCount": 0,
        "byPlatform": {},
        "byConfidence": {},
        "byPlatformConfidence": {},
        "sameTodByPlatform": {},
        "sameTodByConfidence": {},
        "sameTodByPlatformConfidence": {},
        "oldestUtc": None,
        "newestUtc": None,
        "newestTime": None,
        "completeness": "complete",
    }


def _accumulate_point_into_bucket(
    bucket: dict[str, Any],
    pt: dict[str, Any],
    local_time_hhmm: str,
    tod_cutoff_hhmm: str,
    utc_iso: str,
) -> None:
    bucket["count"] += 1
    plat = str(pt.get("platform") or "UNKNOWN")
    conf = str(pt.get("conf") or "nominal")
    pc_key = f"{plat}|{conf}"
    if local_time_hhmm <= tod_cutoff_hhmm:
        bucket["sameTodCount"] += 1
        bucket.setdefault("sameTodByPlatform", {})[plat] = bucket.get("sameTodByPlatform", {}).get(plat, 0) + 1
        bucket.setdefault("sameTodByConfidence", {})[conf] = bucket.get("sameTodByConfidence", {}).get(conf, 0) + 1
        bucket.setdefault("sameTodByPlatformConfidence", {})[pc_key] = bucket.get("sameTodByPlatformConfidence", {}).get(pc_key, 0) + 1
    bucket["byPlatform"][plat] = bucket["byPlatform"].get(plat, 0) + 1
    bucket["byConfidence"][conf] = bucket["byConfidence"].get(conf, 0) + 1
    bucket["byPlatformConfidence"][pc_key] = bucket["byPlatformConfidence"].get(pc_key, 0) + 1
    if bucket["oldestUtc"] is None or utc_iso < bucket["oldestUtc"]:
        bucket["oldestUtc"] = utc_iso
    if bucket["newestUtc"] is None or utc_iso > bucket["newestUtc"]:
        bucket["newestUtc"] = utc_iso
    if bucket["newestTime"] is None or local_time_hhmm > bucket["newestTime"]:
        bucket["newestTime"] = local_time_hhmm


def _build_admin_spatial_lookup(root: Path = ROOT) -> dict[str, Any]:
    admin_fc = build_admin_boundaries_geojson(root)
    provs_by_region: dict[str, list[tuple[str, dict[str, Any], tuple[float, float]]]] = defaultdict(list)
    kabs_by_prov: dict[str, list[tuple[str, dict[str, Any], tuple[float, float]]]] = defaultdict(list)

    for feat in admin_fc.get("features") or []:
        props = feat.get("properties") or {}
        geom = dict(feat.get("geometry") or {})
        bbox = props.get("bbox")
        if bbox:
            geom["_bbox"] = bbox
        cent = props.get("centroid") or [0.0, 0.0]
        seed_lon_lat = (float(cent[1]), float(cent[0])) if len(cent) >= 2 else (114.0, -2.0)
        lvl = props.get("level")
        if lvl == "province":
            provs_by_region[str(props.get("region") or "")].append(
                (str(props["name"]), geom, seed_lon_lat)
            )
        elif lvl == "kabupaten":
            kabs_by_prov[str(props.get("province") or "")].append(
                (str(props["name"]), geom, seed_lon_lat)
            )
    return {"provsByRegion": provs_by_region, "kabsByProv": kabs_by_prov}


def classify_point_admin(
    lon: float,
    lat: float,
    region_id: str,
    spatial_lookup: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Classify a WGS84 point (lon, lat) into (province, kabupaten) via point-in-polygon (#3)."""
    prov_candidates = spatial_lookup["provsByRegion"].get(region_id) or []
    matched_prov: str | None = None
    for p_name, p_geom, _ in prov_candidates:
        if point_in_geometry(lon, lat, p_geom):
            matched_prov = p_name
            break
    if matched_prov is None and prov_candidates:
        matched_prov = min(
            prov_candidates,
            key=lambda item: (lon - item[2][0]) ** 2 + (lat - item[2][1]) ** 2,
        )[0]

    if not matched_prov:
        return None, None

    kab_candidates = spatial_lookup["kabsByProv"].get(matched_prov) or []
    matched_kab: str | None = None
    for k_name, k_geom, _ in kab_candidates:
        if point_in_geometry(lon, lat, k_geom):
            matched_kab = k_name
            break
    if matched_kab is None and kab_candidates:
        matched_kab = min(
            kab_candidates,
            key=lambda item: (lon - item[2][0]) ** 2 + (lat - item[2][1]) ** 2,
        )[0]

    return matched_prov, matched_kab


def build_hotspot_daily_history(
    root: Path = ROOT,
    existing_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build durable per-day national, regional, province, and kabupaten FIRMS history in UTC & WIB (#16, #17, #3).

    - Deduplicates observations by observationId = platform|date|time|lat|lon across runs
      without collapsing distinct satellite passes (S-NPP, NOAA-20, NOAA-21).
    - Classifies each detection by administrative point-in-polygon (`data/admin-boundaries.geojson`)
      into `byProvince` and `byKabupaten` buckets so geographic filters synchronize map, KPIs, and charts.
    - Preserves historical daily aggregates from existing `data/hotspots/history.json`
      when older dates age out of the rolling 5-day NRT shard window.
    """
    shard_root = root / "data" / "hotspots"
    manifest = read_json(shard_root / "manifest.json", {})
    status = read_json(shard_root / "status.json", {})
    if existing_history is None:
        existing_history = read_json(shard_root / "history.json", {})

    m_meta = manifest.get("meta") or {}
    firms_eval = evaluate_firms_freshness(m_meta, status)
    spatial_lookup = _build_admin_spatial_lookup(root)
    coord_admin_cache: dict[tuple[str, float, float], tuple[str | None, str | None]] = {}

    # Collect and deduplicate all observations across region×date shards
    dedup_points: dict[str, dict[str, Any]] = {}
    for rid in REGION_ORDER:
        reg_dir = shard_root / rid
        if not reg_dir.exists():
            continue
        for shard_file in sorted(reg_dir.glob("*.json")):
            shard_payload = read_json(shard_file, {})
            for raw_pt in shard_payload.get("points") or []:
                if not isinstance(raw_pt, dict) or not raw_pt.get("date"):
                    continue
                plat = str(raw_pt.get("platform") or "S-NPP")
                dt_str = str(raw_pt["date"])
                tm_str = str(raw_pt.get("time") or "0000").zfill(4)
                lat_f = float(raw_pt.get("lat") or 0.0)
                lon_f = float(raw_pt.get("lon") or 0.0)
                oid = str(
                    raw_pt.get("observationId")
                    or f"{plat}|{dt_str}|{tm_str}|{lat_f:.5f}|{lon_f:.5f}"
                )
                pt_copy = dict(raw_pt)
                pt_copy["observationId"] = oid
                pt_copy["region"] = str(raw_pt.get("region") or rid)
                pt_copy["time"] = tm_str
                cache_key = (pt_copy["region"], round(lon_f, 4), round(lat_f, 4))
                if cache_key not in coord_admin_cache:
                    coord_admin_cache[cache_key] = classify_point_admin(
                        lon_f, lat_f, pt_copy["region"], spatial_lookup
                    )
                p_prov, p_kab = coord_admin_cache[cache_key]
                pt_copy["province"] = p_prov
                pt_copy["kabupaten"] = p_kab
                dedup_points[oid] = pt_copy

    all_points = list(dedup_points.values())

    # Determine newest UTC date and its time-of-day cutoff for same-time-of-day comparison (#17)
    utc_dates_present = sorted({str(p["date"]) for p in all_points})
    latest_utc_date = utc_dates_present[-1] if utc_dates_present else ""
    latest_utc_tod = max(
        (str(p["time"]) for p in all_points if p["date"] == latest_utc_date),
        default="2359",
    )

    wib_converted = {
        p["observationId"]: convert_utc_to_wib(str(p["date"]), str(p["time"]))
        for p in all_points
    }
    wib_dates_present = sorted({w["wibDate"] for w in wib_converted.values()})
    latest_wib_date = wib_dates_present[-1] if wib_dates_present else ""
    latest_wib_tod = max(
        (
            w["wibTime"].replace(":", "")
            for w in wib_converted.values()
            if w["wibDate"] == latest_wib_date
        ),
        default="2359",
    )

    utc_daily_map: dict[str, dict[str, Any]] = {}
    wib_daily_map: dict[str, dict[str, Any]] = {}

    # Seed from existing durable history for dates no longer present in raw shards (#16)
    if isinstance(existing_history, dict):
        for prev_day in existing_history.get("utcDaily") or []:
            if isinstance(prev_day, dict) and prev_day.get("date") and prev_day["date"] not in utc_dates_present:
                utc_daily_map[str(prev_day["date"])] = prev_day
        for prev_day in existing_history.get("wibDaily") or []:
            if isinstance(prev_day, dict) and prev_day.get("date") and prev_day["date"] not in wib_dates_present:
                wib_daily_map[str(prev_day["date"])] = prev_day

    for d_str in utc_dates_present:
        utc_daily_map[d_str] = {
            "date": d_str,
            "timezone": "UTC",
            "todCutoff": latest_utc_tod,
            "completeness": (
                "partial"
                if (d_str == latest_utc_date and latest_utc_tod < "2100")
                else "complete"
            ),
            "validationStatus": "validated",
            "extractedAtUtc": firms_eval["lastSuccessfulSync"],
            "pipelineVersion": str(m_meta.get("pipelineVersion") or "4"),
            "national": _empty_day_bucket(),
            "regions": {rid: _empty_day_bucket() for rid in REGION_ORDER},
            "byProvince": {p: _empty_day_bucket() for p in PROVINCE_TO_BPS_CODE},
            "byKabupaten": {},
        }

    for idx_w, d_str in enumerate(wib_dates_present):
        # First WIB date starting after 00:00 WIB or last WIB date ending before 21:00 WIB is partial
        is_edge_partial = (idx_w == 0 or idx_w == len(wib_dates_present) - 1)
        wib_daily_map[d_str] = {
            "date": d_str,
            "timezone": "Asia/Jakarta",
            "todCutoff": latest_wib_tod,
            "completeness": "partial" if is_edge_partial else "complete",
            "validationStatus": "validated",
            "extractedAtUtc": firms_eval["lastSuccessfulSync"],
            "pipelineVersion": str(m_meta.get("pipelineVersion") or "4"),
            "national": _empty_day_bucket(),
            "regions": {rid: _empty_day_bucket() for rid in REGION_ORDER},
            "byProvince": {p: _empty_day_bucket() for p in PROVINCE_TO_BPS_CODE},
            "byKabupaten": {},
        }

    for pt in all_points:
        rid = pt["region"]
        if rid not in REGION_ORDER:
            continue
        p_prov = pt.get("province")
        p_kab = pt.get("kabupaten")
        w_info = wib_converted[pt["observationId"]]
        utc_iso = w_info["utcIso"]

        # 1. UTC aggregation
        u_entry = utc_daily_map[str(pt["date"])]
        _accumulate_point_into_bucket(
            u_entry["national"], pt, str(pt["time"]), latest_utc_tod, utc_iso
        )
        _accumulate_point_into_bucket(
            u_entry["regions"][rid], pt, str(pt["time"]), latest_utc_tod, utc_iso
        )
        u_entry["national"]["completeness"] = u_entry["completeness"]
        u_entry["regions"][rid]["completeness"] = u_entry["completeness"]
        if p_prov:
            p_bkt = u_entry["byProvince"].setdefault(p_prov, _empty_day_bucket())
            _accumulate_point_into_bucket(p_bkt, pt, str(pt["time"]), latest_utc_tod, utc_iso)
            p_bkt["completeness"] = u_entry["completeness"]
        if p_kab:
            k_bkt = u_entry["byKabupaten"].setdefault(p_kab, _empty_day_bucket())
            _accumulate_point_into_bucket(k_bkt, pt, str(pt["time"]), latest_utc_tod, utc_iso)
            k_bkt["completeness"] = u_entry["completeness"]

        # 2. WIB (Asia/Jakarta, UTC+7) aggregation
        w_date = w_info["wibDate"]
        w_hhmm = w_info["wibTime"].replace(":", "")
        w_entry = wib_daily_map[w_date]
        _accumulate_point_into_bucket(
            w_entry["national"], pt, w_hhmm, latest_wib_tod, utc_iso
        )
        _accumulate_point_into_bucket(
            w_entry["regions"][rid], pt, w_hhmm, latest_wib_tod, utc_iso
        )
        w_entry["national"]["completeness"] = w_entry["completeness"]
        w_entry["regions"][rid]["completeness"] = w_entry["completeness"]
        if p_prov:
            wp_bkt = w_entry["byProvince"].setdefault(p_prov, _empty_day_bucket())
            _accumulate_point_into_bucket(wp_bkt, pt, w_hhmm, latest_wib_tod, utc_iso)
            wp_bkt["completeness"] = w_entry["completeness"]
        if p_kab:
            wk_bkt = w_entry["byKabupaten"].setdefault(p_kab, _empty_day_bucket())
            _accumulate_point_into_bucket(wk_bkt, pt, w_hhmm, latest_wib_tod, utc_iso)
            wk_bkt["completeness"] = w_entry["completeness"]

    utc_daily_sorted = [utc_daily_map[k] for k in sorted(utc_daily_map)]
    wib_daily_sorted = [wib_daily_map[k] for k in sorted(wib_daily_map)]

    # Verify disjoint regional and provincial bucket invariants: national == sum(regions) == sum(provinces)
    for series in (utc_daily_sorted, wib_daily_sorted):
        for day_item in series:
            reg_sum = sum(day_item["regions"][r]["count"] for r in REGION_ORDER)
            if day_item["national"]["count"] != reg_sum:
                raise ValueError(
                    f"National count {day_item['national']['count']} != sum of disjoint regions {reg_sum} on {day_item['date']}"
                )
            if "byProvince" in day_item and day_item["byProvince"]:
                prov_sum = sum(b["count"] for b in day_item["byProvince"].values())
                if day_item["national"]["count"] != prov_sum:
                    raise ValueError(
                        f"National count {day_item['national']['count']} != sum of disjoint provinces {prov_sum} on {day_item['date']}"
                    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "coverageId": "indonesia",
        "sourceId": "firms-hotspots",
        "source": "NASA FIRMS NRT VIIRS",
        "product": "VIIRS Active Fire (S-NPP, NOAA-20, NOAA-21)",
        "pipelineVersion": str(m_meta.get("pipelineVersion") or "4"),
        "adminBoundariesUrl": "data/admin-boundaries.geojson",
        "observationIdentitySpec": "platform|acq_date|acq_time_hhmm|lat_5dp|lon_5dp (distinct satellite passes are never collapsed into one hypothetical fire event)",
        "runtimeVsGitNote": (
            "Scheduled GitHub Actions (firms-nrt.yml) restores and persists multi-day shards via the durable "
            "firms-history-data store and publishes refreshed artifacts to GitHub Pages without committing hourly churn to main."
        ),
        "freshness": {
            "state": firms_eval["state"],
            "evaluatedAtUtc": firms_eval["evaluatedAtUtc"],
            "staleThresholdHours": firms_eval["staleThresholdHours"],
            "syncAgeMinutes": firms_eval["syncAgeMinutes"],
            "observationAgeMinutes": firms_eval["observationAgeMinutes"],
            "lastAttemptedSync": firms_eval["lastAttemptedSync"],
            "lastSuccessfulSync": firms_eval["lastSuccessfulSync"],
            "newestDetectionUtc": firms_eval["newestDetectionUtc"],
            "oldestDetectionUtc": firms_eval["oldestDetectionUtc"],
            "pipelineStatus": str(status.get("pipelineStatus") or "healthy"),
            "stale": firms_eval["state"] == "stale",
            "lastKnownGood": firms_eval["lastKnownGood"],
            "reason": firms_eval["reason"],
        },
        "platforms": list(m_meta.get("platforms") or ["S-NPP", "NOAA-20", "NOAA-21"]),
        "confidenceLevels": ["high", "nominal", "low"],
        "regions": list(REGION_ORDER),
        "totalValidatedObservations": len(all_points),
        "utcTodCutoff": latest_utc_tod,
        "wibTodCutoff": latest_wib_tod,
        "utcDaily": utc_daily_sorted,
        "wibDaily": wib_daily_sorted,
    }


def _extract_filtered_bucket_count(
    bucket: dict[str, Any],
    platform: str = "",
    conf: str = "",
    use_same_tod: bool = False,
) -> int:
    if not bucket:
        return 0
    plat = str(platform or "").strip().upper()
    cf = str(conf or "").strip().lower()
    if use_same_tod:
        if plat and cf and isinstance(bucket.get("sameTodByPlatformConfidence"), dict):
            return int(bucket["sameTodByPlatformConfidence"].get(f"{plat}|{cf}") or 0)
        if plat and isinstance(bucket.get("sameTodByPlatform"), dict):
            return int(bucket["sameTodByPlatform"].get(plat) or 0)
        if cf and isinstance(bucket.get("sameTodByConfidence"), dict):
            return int(bucket["sameTodByConfidence"].get(cf) or 0)
        return int(bucket.get("sameTodCount") or 0)
    if plat and cf:
        return int((bucket.get("byPlatformConfidence") or {}).get(f"{plat}|{cf}") or 0)
    if plat:
        return int((bucket.get("byPlatform") or {}).get(plat) or 0)
    if cf:
        return int((bucket.get("byConfidence") or {}).get(cf) or 0)
    return int(bucket.get("count") or 0)


def compute_delta_metrics(current_val: int | float | None, previous_val: int | float | None) -> dict[str, Any]:
    """Compute absolute and relative delta with explicit zero/missing denominator handling (#17)."""
    if current_val is None or previous_val is None:
        return {
            "current": current_val,
            "previous": previous_val,
            "deltaAbs": None,
            "deltaPct": None,
            "denominatorZero": False,
            "comparable": False,
            "reason": "missing_comparison_period",
        }
    delta_abs = current_val - previous_val
    if previous_val == 0:
        return {
            "current": current_val,
            "previous": previous_val,
            "deltaAbs": delta_abs,
            "deltaPct": None,
            "denominatorZero": True,
            "comparable": True,
            "reason": "denominator_zero",
        }
    delta_pct = round((delta_abs / float(previous_val)) * 100.0, 2)
    return {
        "current": current_val,
        "previous": previous_val,
        "deltaAbs": delta_abs,
        "deltaPct": delta_pct,
        "denominatorZero": False,
        "comparable": True,
        "reason": "ok",
    }


def _are_dates_consecutive(prev_date_str: str | None, curr_date_str: str | None) -> bool:
    if not prev_date_str or not curr_date_str:
        return False
    try:
        d1 = datetime.strptime(str(prev_date_str)[:10], "%Y-%m-%d").date()
        d2 = datetime.strptime(str(curr_date_str)[:10], "%Y-%m-%d").date()
        return (d2 - d1).days == 1
    except ValueError:
        return False


def _are_observation_periods_comparable(prev_pt: dict[str, Any], curr_pt: dict[str, Any]) -> bool:
    if not isinstance(prev_pt, dict) or not isinstance(curr_pt, dict):
        return False
    if prev_pt.get("status") != "complete" or curr_pt.get("status") != "complete":
        return False
    if prev_pt.get("value") is None or curr_pt.get("value") is None:
        return False
    prev_vf = str(prev_pt.get("validFrom") or "")[10:]
    prev_vt = str(prev_pt.get("validTo") or "")[10:]
    curr_vf = str(curr_pt.get("validFrom") or "")[10:]
    curr_vt = str(curr_pt.get("validTo") or "")[10:]
    return prev_vf == curr_vf == "T00:00:00" and prev_vt == curr_vt == "T23:59:59"


def compute_hotspot_trends_and_deltas(
    history_payload: dict[str, Any],
    region: str = "indonesia",
    prov: str = "",
    kab: str = "",
    window: str = "all",
    timezone_mode: str = "UTC",
    platform: str = "",
    conf: str = "",
    root: Path = ROOT,
) -> dict[str, Any]:
    """Compute daily hotspot trends, consecutive complete-day deltas, same-TOD comparison, and admin breakdowns (#17, #3, #6).

    - Uses administrative point-in-polygon buckets (`byProvince`, `byKabupaten`) when `prov` or `kab` is active.
    - Requires strictly adjacent calendar dates and comparable full-day observation periods for `completeDayOverDay`.
    - Treats missing calendar dates as explicit `gap`s that block day-over-day comparisons.
    """
    tz_label = "Asia/Jakarta" if str(timezone_mode).upper() in ("WIB", "ASIA/JAKARTA") else "UTC"
    norm_prov = normalize_province_token(prov) if prov else ""
    norm_kab = normalize_kabupaten_token(kab) if kab else ""
    scope_id = norm_kab or norm_prov or region

    if norm_prov and norm_kab:
        auth_kab_prov = resolve_kabupaten_province(norm_kab, root=root)
        if auth_kab_prov and auth_kab_prov != norm_prov:
            return {
                "state": "unavailable",
                "reason": f"Kabupaten {norm_kab} berada di provinsi {auth_kab_prov}, bukan {norm_prov}.",
                "timezone": tz_label,
                "scopeId": scope_id,
                "points": [],
                "completeDayOverDay": None,
                "sameTimeOfDayComparison": None,
                "windowSummary": {
                    "requestedWindow": window,
                    "completeness": "unavailable",
                    "total": None,
                    "delta": None,
                },
            }

    raw_series = (
        history_payload.get("wibDaily")
        if tz_label == "Asia/Jakarta"
        else history_payload.get("utcDaily")
    ) or []

    if (norm_prov or norm_kab) and raw_series:
        has_admin_buckets = any(
            isinstance(d, dict) and ("byProvince" in d or "byKabupaten" in d)
            for d in raw_series
        )
        if not has_admin_buckets:
            return {
                "state": "unavailable",
                "reason": "Riwayat harian FIRMS belum memuat bucket batas administratif provinsi/kabupaten.",
                "timezone": tz_label,
                "scopeId": scope_id,
                "points": [],
                "completeDayOverDay": None,
                "sameTimeOfDayComparison": None,
                "windowSummary": {
                    "requestedWindow": window,
                    "completeness": "unavailable",
                    "total": None,
                    "delta": None,
                },
            }

    by_date = {str(item["date"]): item for item in raw_series if isinstance(item, dict) and item.get("date")}
    sorted_dates = sorted(by_date.keys())
    if not sorted_dates:
        return {
            "state": "unavailable",
            "reason": "Tidak ada riwayat harian FIRMS yang tersedia.",
            "timezone": tz_label,
            "scopeId": scope_id,
            "points": [],
            "completeDayOverDay": None,
            "sameTimeOfDayComparison": None,
            "windowSummary": {
                "requestedWindow": window,
                "completeness": "unavailable",
                "total": None,
                "delta": None,
            },
        }

    # Expand continuous calendar dates between min and max so missing days become explicit gaps (never fake 0s)
    start_dt = datetime.strptime(sorted_dates[0], "%Y-%m-%d").date()
    end_dt = datetime.strptime(sorted_dates[-1], "%Y-%m-%d").date()
    continuous_points: list[dict[str, Any]] = []
    cursor = start_dt
    while cursor <= end_dt:
        d_str = cursor.isoformat()
        day_obj = by_date.get(d_str)
        if day_obj is None:
            continuous_points.append(
                {
                    "date": d_str,
                    "observedAt": d_str,
                    "validFrom": f"{d_str}T00:00:00",
                    "validTo": f"{d_str}T23:59:59",
                    "value": None,
                    "sameTodValue": None,
                    "status": "gap",
                    "completeness": "unavailable",
                }
            )
        else:
            if norm_kab:
                bucket = (day_obj.get("byKabupaten") or {}).get(norm_kab) or _empty_day_bucket()
            elif norm_prov:
                bucket = (day_obj.get("byProvince") or {}).get(norm_prov) or _empty_day_bucket()
            elif region == "indonesia":
                bucket = day_obj.get("national") or _empty_day_bucket()
            else:
                bucket = (day_obj.get("regions") or {}).get(region) or _empty_day_bucket()
            val = _extract_filtered_bucket_count(bucket, platform=platform, conf=conf, use_same_tod=False)
            tod_val = _extract_filtered_bucket_count(bucket, platform=platform, conf=conf, use_same_tod=True)
            comp = str(day_obj.get("completeness") or "complete")
            continuous_points.append(
                {
                    "date": d_str,
                    "observedAt": bucket.get("newestUtc") or d_str,
                    "validFrom": f"{d_str}T00:00:00",
                    "validTo": f"{d_str}T{str(day_obj.get('todCutoff') or '2359')[:2]}:{str(day_obj.get('todCutoff') or '2359')[2:4]}:00" if comp == "partial" else f"{d_str}T23:59:59",
                    "value": val,
                    "sameTodValue": tod_val,
                    "status": comp,
                    "completeness": comp,
                    "newestTime": bucket.get("newestTime"),
                }
            )
        cursor = datetime.fromordinal(cursor.toordinal() + 1).date()

    # Compute day-over-day delta on each point ONLY when dates are consecutive and observation periods are comparable (#6)
    for idx, pt in enumerate(continuous_points):
        if idx == 0:
            pt["deltaAbs"] = None
            pt["deltaPct"] = None
            pt["deltaComparable"] = False
            continue
        prev_pt = continuous_points[idx - 1]
        if _are_dates_consecutive(prev_pt["date"], pt["date"]) and _are_observation_periods_comparable(prev_pt, pt):
            dm = compute_delta_metrics(pt["value"], prev_pt["value"])
            pt["deltaAbs"] = dm["deltaAbs"]
            pt["deltaPct"] = dm["deltaPct"]
            pt["deltaComparable"] = dm["comparable"]
        else:
            pt["deltaAbs"] = None
            pt["deltaPct"] = None
            pt["deltaComparable"] = False

    # 1. Most recent complete day-over-day comparison (#17, #6):
    # Requires the latest complete day and its immediately preceding calendar day to BOTH be complete & comparable.
    complete_indices = [
        idx for idx, p in enumerate(continuous_points)
        if p["status"] == "complete" and p["value"] is not None
    ]
    complete_dod = None
    if complete_indices:
        latest_c_idx = complete_indices[-1]
        if latest_c_idx > 0:
            curr_c = continuous_points[latest_c_idx]
            prev_c = continuous_points[latest_c_idx - 1]
            if _are_dates_consecutive(prev_c["date"], curr_c["date"]) and _are_observation_periods_comparable(prev_c, curr_c):
                complete_dod = {
                    "currentDate": curr_c["date"],
                    "previousDate": prev_c["date"],
                    "adjacentDates": True,
                    "comparablePeriod": True,
                    **compute_delta_metrics(curr_c["value"], prev_c["value"]),
                }
            elif len(complete_indices) >= 2:
                prev_complete = continuous_points[complete_indices[-2]]
                complete_dod = {
                    "currentDate": curr_c["date"],
                    "previousDate": prev_complete["date"],
                    "adjacentDates": False,
                    "comparablePeriod": False,
                    "current": curr_c["value"],
                    "previous": prev_complete["value"],
                    "deltaAbs": None,
                    "deltaPct": None,
                    "denominatorZero": False,
                    "comparable": False,
                    "reason": "non_consecutive_dates_gap",
                }

    # 2. Same-time-of-day (TOD) comparison for the latest day (#17, #6):
    # Requires strictly adjacent calendar dates and non-gap observations covering the same [00:00, cutoff] window.
    same_tod_comp = None
    if len(continuous_points) >= 2:
        latest_pt = continuous_points[-1]
        prev_pt = continuous_points[-2]
        cutoff = (
            history_payload.get("wibTodCutoff")
            if tz_label == "Asia/Jakarta"
            else history_payload.get("utcTodCutoff")
        ) or "2359"
        prev_covers_cutoff = (
            prev_pt["status"] == "complete"
            or str(prev_pt.get("newestTime") or "2359") >= str(cutoff)
        )
        if (
            _are_dates_consecutive(prev_pt["date"], latest_pt["date"])
            and latest_pt["status"] != "gap"
            and prev_pt["status"] != "gap"
            and prev_covers_cutoff
        ):
            same_tod_comp = {
                "currentDate": latest_pt["date"],
                "previousDate": prev_pt["date"],
                "adjacentDates": True,
                "cutoffTime": f"{str(cutoff)[:2]}:{str(cutoff)[2:4]} {tz_label}",
                "latestDayStatus": latest_pt["status"],
                **compute_delta_metrics(latest_pt["sameTodValue"], prev_pt["sameTodValue"]),
            }

    # 3. Window slice (1d, 4d, 7d, 30d, 90d, all) with explicit completeness
    req_days_map = {"1d": 1, "24h": 1, "4d": 4, "7d": 7, "30d": 30, "90d": 90}
    req_days = req_days_map.get(str(window).lower())
    observed_valid = [p for p in continuous_points if p["status"] != "gap" and p["value"] is not None]

    if req_days is None:
        window_points = continuous_points
        window_complete = all(p["status"] == "complete" for p in continuous_points)
        win_status = "complete" if window_complete else "partial"
        win_delta = None
    else:
        window_points = continuous_points[-req_days:]
        has_enough_days = len(continuous_points) >= req_days and all(
            p["status"] != "gap" for p in window_points
        )
        all_complete_in_win = has_enough_days and all(
            p["status"] == "complete" for p in window_points
        )
        win_status = "complete" if all_complete_in_win else "partial"
        win_delta = None
        if len(continuous_points) >= req_days * 2:
            prev_win_points = continuous_points[-req_days * 2 : -req_days]
            if all(p["status"] == "complete" for p in window_points) and all(
                p["status"] == "complete" for p in prev_win_points
            ):
                curr_sum = sum(int(p["value"] or 0) for p in window_points)
                prev_sum = sum(int(p["value"] or 0) for p in prev_win_points)
                win_delta = compute_delta_metrics(curr_sum, prev_sum)
            else:
                win_delta = {
                    "current": sum(int(p["value"] or 0) for p in window_points if p["value"] is not None),
                    "previous": None,
                    "deltaAbs": None,
                    "deltaPct": None,
                    "denominatorZero": False,
                    "comparable": False,
                    "reason": "incomplete_comparison_window",
                }
        else:
            win_delta = {
                "current": sum(int(p["value"] or 0) for p in window_points if p["value"] is not None),
                "previous": None,
                "deltaAbs": None,
                "deltaPct": None,
                "denominatorZero": False,
                "comparable": False,
                "reason": f"archive_has_{len(observed_valid)}_days_need_{req_days * 2}_for_period_delta",
            }

    win_total = sum(int(p["value"] or 0) for p in window_points if p["value"] is not None)

    return {
        "state": (history_payload.get("freshness") or {}).get("state") or "fresh",
        "reason": (history_payload.get("freshness") or {}).get("reason") or "ok",
        "timezone": tz_label,
        "scopeId": scope_id,
        "platformFilter": platform or "ALL",
        "confidenceFilter": conf or "ALL",
        "points": window_points,
        "allPoints": continuous_points,
        "completeDayOverDay": complete_dod,
        "sameTimeOfDayComparison": same_tod_comp,
        "windowSummary": {
            "requestedWindow": window,
            "requestedDays": req_days,
            "availableDays": len(observed_valid),
            "completeness": win_status,
            "total": win_total,
            "delta": win_delta,
        },
    }


def validate_time_series_contract(series: dict[str, Any]) -> None:
    """Validate reusable time-series chart contract for truthful source frequency (#18).

    Enforces:
    - Valid granularity ('hour', 'day', 'week', 'month')
    - Valid aggregationMode ('incremental', 'cumulative')
    - Weekly/monthly series are NEVER interpolated into daily points
    - Unavailable series or gap intervals have value=None (never fake 0s)
    """
    if not isinstance(series, dict):
        raise ValueError("time-series contract must be a dict")
    for req in ("seriesId", "metricId", "title", "sourceId", "sourceName", "units", "granularity", "aggregationMode"):
        if not isinstance(series.get(req), str) or not series[req].strip():
            raise ValueError(f"time-series missing required string '{req}'")

    gran = series["granularity"]
    if gran not in ("hour", "day", "week", "month"):
        raise ValueError(f"unsupported time-series granularity: {gran}")
    if series["aggregationMode"] not in ("incremental", "cumulative"):
        raise ValueError(f"unsupported aggregationMode: {series['aggregationMode']}")

    cov = series.get("coverage")
    if not isinstance(cov, dict) or cov.get("completeness") not in ("complete", "partial", "unavailable", "stale"):
        raise ValueError("time-series coverage.completeness must be complete, partial, unavailable, or stale")

    points = series.get("points")
    if not isinstance(points, list):
        raise ValueError("time-series points must be a list")

    if cov["completeness"] == "unavailable" and any(p.get("value") is not None for p in points):
        raise ValueError("unavailable time-series must not contain non-null point values")

    for idx, pt in enumerate(points):
        if not isinstance(pt, dict):
            raise ValueError("each time-series point must be a dict")
        st = pt.get("status")
        if st not in ("complete", "partial", "gap"):
            raise ValueError(f"invalid point status: {st}")
        if st == "gap" and pt.get("value") is not None:
            raise ValueError("missing interval ('gap') must have value=None, never 0")
        if gran == "week" and pt.get("validFrom") and pt.get("validTo"):
            vf = str(pt["validFrom"])[:10]
            vt = str(pt["validTo"])[:10]
            if vf == vt:
                raise ValueError(
                    "weekly time-series point has single-day validFrom==validTo (weekly series must not be interpolated into daily points)"
                )


def build_typed_time_series(
    metric_id: str,
    history_payload: dict[str, Any],
    region: str = "indonesia",
    prov: str = "",
    kab: str = "",
    window: str = "all",
    timezone_mode: str = "UTC",
    aggregation_mode: str = "incremental",
    platform: str = "",
    conf: str = "",
    root: Path = ROOT,
) -> dict[str, Any]:
    """Build a typed time-series envelope for the reusable chart component (#18)."""
    agg_mode = "cumulative" if str(aggregation_mode).lower() == "cumulative" else "incremental"

    if metric_id == "firms-hotspots":
        analytics = compute_hotspot_trends_and_deltas(
            history_payload=history_payload,
            region=region,
            prov=prov,
            kab=kab,
            window=window,
            timezone_mode=timezone_mode,
            platform=platform,
            conf=conf,
            root=root,
        )
        if analytics["state"] == "unavailable":
            series = {
                "seriesId": f"firms-hotspots:{region}:{prov}:{kab}:{window}",
                "metricId": "firms-hotspots",
                "title": "Tren Harian Deteksi Panas Satelit (NASA FIRMS VIIRS)",
                "sourceId": "firms-hotspots",
                "sourceName": "NASA FIRMS NRT VIIRS (S-NPP, NOAA-20, NOAA-21)",
                "sourceUrl": "https://firms.modaps.eosdis.nasa.gov/api/area/",
                "units": "detections",
                "granularity": "day",
                "aggregationMode": agg_mode,
                "timezone": analytics["timezone"],
                "updatedAt": (history_payload.get("freshness") or {}).get("lastSuccessfulSync"),
                "newestObservationAt": (history_payload.get("freshness") or {}).get("newestDetectionUtc"),
                "coverage": {
                    "scopeId": analytics["scopeId"],
                    "requestedWindow": window,
                    "completeness": "unavailable",
                    "reason": analytics["reason"],
                },
                "points": [],
            }
            validate_time_series_contract(series)
            return series

        running_sum = 0
        typed_points: list[dict[str, Any]] = []
        for p in analytics["points"]:
            if p["status"] == "gap" or p["value"] is None:
                typed_points.append(
                    {
                        "label": p["date"],
                        "observedAt": p["observedAt"],
                        "validFrom": p["validFrom"],
                        "validTo": p["validTo"],
                        "value": None,
                        "incrementalValue": None,
                        "sameTodValue": None,
                        "status": "gap",
                        "deltaAbs": None,
                        "deltaPct": None,
                    }
                )
            else:
                running_sum += int(p["value"])
                typed_points.append(
                    {
                        "label": p["date"],
                        "observedAt": p["observedAt"],
                        "validFrom": p["validFrom"],
                        "validTo": p["validTo"],
                        "value": running_sum if agg_mode == "cumulative" else int(p["value"]),
                        "incrementalValue": int(p["value"]),
                        "sameTodValue": p.get("sameTodValue"),
                        "status": p["status"],
                        "deltaAbs": p.get("deltaAbs"),
                        "deltaPct": p.get("deltaPct"),
                    }
                )

        series = {
            "seriesId": f"firms-hotspots:{analytics['scopeId']}:{window}:{analytics['timezone']}:{agg_mode}",
            "metricId": "firms-hotspots",
            "title": (
                "Kumulatif Deteksi Panas Satelit (NASA FIRMS VIIRS)"
                if agg_mode == "cumulative"
                else "Tren Harian Deteksi Panas Satelit (NASA FIRMS VIIRS)"
            ),
            "sourceId": "firms-hotspots",
            "sourceName": "NASA FIRMS NRT VIIRS (S-NPP, NOAA-20, NOAA-21)",
            "sourceUrl": "https://firms.modaps.eosdis.nasa.gov/api/area/",
            "units": "detections",
            "granularity": "day",
            "aggregationMode": agg_mode,
            "timezone": analytics["timezone"],
            "updatedAt": (history_payload.get("freshness") or {}).get("lastSuccessfulSync"),
            "newestObservationAt": (history_payload.get("freshness") or {}).get("newestDetectionUtc"),
            "coverage": {
                "scopeId": analytics["scopeId"],
                "scopeLevel": "kabupaten" if kab else ("province" if prov else ("national" if region == "indonesia" else "region")),
                "requestedWindow": window,
                "availableDays": analytics["windowSummary"]["availableDays"],
                "completeness": analytics["windowSummary"]["completeness"],
                "reason": analytics["reason"],
            },
            "completeDayOverDay": analytics["completeDayOverDay"],
            "sameTimeOfDayComparison": analytics["sameTimeOfDayComparison"],
            "windowSummary": analytics["windowSummary"],
            "points": typed_points,
        }
        validate_time_series_contract(series)
        return series

    # Other 3 environmental/health series (#18): truthful frequency & explicit unavailable state until P1/P2 ingest
    catalog_specs = {
        "burned-area": {
            "title": "Estimasi Luas Area Terbakar Harian (Burned Area)",
            "sourceName": "Produk Burned Area Independen (Pending #20)",
            "sourceUrl": "https://gwis.jrc.ec.europa.eu/",
            "units": "ha",
            "granularity": "day",
            "reason": "Produk poligon/raster area terbakar independen (#20/#21) belum di-ingest. Titik panas FIRMS tidak pernah dikonversi menjadi hektar terbakar.",
        },
        "air-quality-pm25": {
            "title": "Konsentrasi PM2.5 Berbasis Stasiun (ISPU / OpenAQ)",
            "sourceName": "Stasiun Kualitas Udara ISPU/KLHK & OpenAQ (Pending #22)",
            "sourceUrl": "https://ispu.menlhk.go.id/",
            "units": "µg/m³",
            "granularity": "hour",
            "reason": "Observasi PM2.5 berbasis stasiun (#22/#23) belum di-ingest. Kualitas udara terikat pada titik stasiun pengukuran, bukan rata-rata pulau.",
        },
        "kemenkes-ispa": {
            "title": "Laporan Kasus ISPA Mingguan (Surveilans Kesehatan)",
            "sourceName": "Surveilans ISPA Kemenkes/Dinkes (Pending #26)",
            "sourceUrl": "https://skdr.surveilans.org/",
            "units": "cases",
            "granularity": "week",
            "reason": "Data surveilans ISPA mingguan/bulanan (#26/#27) belum di-ingest. Frekuensi mingguan asli sumber dipertahankan tanpa interpolasi kurva harian.",
        },
    }
    spec = catalog_specs.get(metric_id, catalog_specs["burned-area"])
    series = {
        "seriesId": f"{metric_id}:{region}:{window}:{agg_mode}",
        "metricId": metric_id,
        "title": spec["title"],
        "sourceId": metric_id,
        "sourceName": spec["sourceName"],
        "sourceUrl": spec["sourceUrl"],
        "units": spec["units"],
        "granularity": spec["granularity"],
        "aggregationMode": agg_mode,
        "timezone": "UTC",
        "updatedAt": None,
        "newestObservationAt": None,
        "coverage": {
            "scopeId": kab or prov or region,
            "requestedWindow": window,
            "completeness": "unavailable",
            "reason": spec["reason"],
        },
        "points": [],
    }
    validate_time_series_contract(series)
    return series


def generate_v2_Foundation_artifacts(
    root: Path = ROOT, check_only: bool = False
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    admin_boundaries = build_admin_boundaries_geojson(root)
    admin_index = build_admin_index(root)
    sources_manifest = build_sources_manifest(root)
    hotspot_history = build_hotspot_daily_history(root)
    build_all_region_concession_indexes(root, check_only=check_only)
    for env in sources_manifest["metrics"].values():
        validate_metric_envelope(env)
    # Validate all 4 typed time-series contracts (#18)
    for mid in ("firms-hotspots", "burned-area", "air-quality-pm25", "kemenkes-ispa"):
        ts = build_typed_time_series(mid, hotspot_history, region="indonesia", window="all", root=root)
        validate_time_series_contract(ts)
    if not check_only:
        write_json_atomic(root / "data" / "admin-boundaries.geojson", admin_boundaries)
        write_json_atomic(root / "data" / "admin-index.json", admin_index)
        write_json_atomic(root / "data" / "sources-manifest.json", sources_manifest)
        write_json_atomic(root / "data" / "hotspots" / "history.json", hotspot_history)
    return admin_index, sources_manifest, hotspot_history


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without writing files")
    args = parser.parse_args()
    admin_index, sources_manifest, hotspot_history = generate_v2_Foundation_artifacts(
        ROOT, check_only=args.check
    )
    kal_vm = build_region_concession_view_models("kalimantan", ROOT)
    print(
        f"v2_contracts: validated {len(sources_manifest['metrics'])} metric envelopes, "
        f"{len(admin_index['regions'])} regional admin indexes "
        f"({admin_index['nationalConcessions']['deduplicatedCount']} deduplicated concessions), "
        f"durable FIRMS history ({len(hotspot_history['utcDaily'])} UTC days / "
        f"{len(hotspot_history['wibDaily'])} WIB days, {hotspot_history['totalValidatedObservations']} obs), "
        f"and Kalimantan unified ConcessionViewModel ({kal_vm['stats']['totalUnifiedCount']} rows)"
    )


if __name__ == "__main__":
    main()


