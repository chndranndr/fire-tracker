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

SCHEMA_VERSION = 1
WIB_TZ = timezone(timedelta(hours=7))

AVAILABILITY_STATES = (
    "fresh",
    "stale",
    "partial",
    "unavailable",
    "estimated",
    "official",
)

QUALITY_LABELS = (
    "OFFICIAL",
    "GFW",
    "PERKIRAAN",
    "NRT",
    "FALLBACK",
    "UNAVAILABLE",
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


def parse_record_provinces(
    props: dict[str, Any] | None,
    allowed_provinces: set[str] | None = None,
) -> list[str]:
    """Extract canonical province names from a concession or dossier record.

    Handles both single provinces, BPS 2-digit provinceCode fields, and
    cross-border strings such as 'KALIMANTAN SELATAN, KALIMANTAN TIMUR'.
    Island-wide labels like 'Kalimantan' or marine labels like
    'DI ATAS 12 MIL LAUT' return [] so island totals are never silently
    substituted for province-level filters.
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
    return found


def normalize_kabupaten_token(token: str | None) -> str | None:
    if not token:
        return None
    cleaned = re.sub(r"\s+", " ", str(token)).strip()
    if not cleaned or cleaned in ("-", "—", "NONE", "NULL", "N/A"):
        return None
    upper = cleaned.upper()
    upper = re.sub(r"^(KABUPATEN|KAB\.)\s+", "", upper).strip()
    if not upper or upper in ("-", "DI ATAS 12 MIL LAUT"):
        return None
    if upper.startswith("KOTA "):
        return "Kota " + upper[5:].title()
    return upper.title()


def parse_record_kabupaten(props: dict[str, Any] | None) -> list[str]:
    """Extract canonical kabupaten/kota names from a record's district field.

    Splits cross-border multi-district strings like 'BANJAR, TAPIN' into
    ['Banjar', 'Tapin'].
    """
    if not isinstance(props, dict):
        return []
    raw_dist = props.get("district") or props.get("kabupaten")
    if not raw_dist:
        return []
    found: list[str] = []
    for part in re.split(r"[,;/]+", str(raw_dist)):
        norm = normalize_kabupaten_token(part)
        if norm and norm not in found:
            found.append(norm)
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
) -> dict[str, Any]:
    """Filter concession features by shared geographic/attribute filters.

    Returns both raw matched features, deduplicated count, and counts of records
    that lacked province or kabupaten resolution so the UI never conflates
    missing administrative resolution with 0.
    """
    norm_prov = normalize_province_token(province) if province else ""
    norm_kab = normalize_kabupaten_token(kabupaten) if kabupaten else ""
    q = (search or "").strip().lower()

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

        rec_provs = parse_record_provinces(props, allowed_provinces=allowed_provinces)
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
    """Evaluate FIRMS pipeline and observation freshness without silent fallback."""
    meta = manifest_meta if isinstance(manifest_meta, dict) else {}
    status = status_payload if isinstance(status_payload, dict) else {}

    last_sync_str = status.get("lastSuccessfulSync") or meta.get("lastSuccessfulSync")
    last_attempt_str = status.get("lastAttemptedSync") or last_sync_str
    newest_obs_str = status.get("newestDetectionUtc") or meta.get("newestDetectionUtc")
    oldest_obs_str = meta.get("oldestDetectionUtc")

    last_sync_dt = parse_iso_utc(last_sync_str)
    newest_obs_dt = parse_iso_utc(newest_obs_str)
    ref_dt = reference_utc or last_sync_dt or newest_obs_dt

    sync_age_minutes: int | None = None
    obs_age_minutes: int | None = None
    if ref_dt and last_sync_dt:
        sync_age_minutes = max(0, int((ref_dt - last_sync_dt).total_seconds() // 60))
    if ref_dt and newest_obs_dt:
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
            or "Sinkronisasi melampaui ambang kesegaran; menampilkan shard last-known-good."
        )
    else:
        state = "fresh"
        reason = None

    return {
        "state": state,
        "quality": "NRT",
        "isFallback": False,
        "lastKnownGood": previous_preserved,
        "lastAttemptedSync": last_attempt_str,
        "lastSuccessfulSync": last_sync_str,
        "newestDetectionUtc": newest_obs_str,
        "oldestDetectionUtc": oldest_obs_str,
        "syncAgeMinutes": sync_age_minutes,
        "observationAgeMinutes": obs_age_minutes,
        "reason": reason,
    }


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
) -> dict[str, Any]:
    """Construct and validate a versioned per-metric metadata envelope (#19)."""
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
        "value": value,
        "caveats": list(caveats or []),
    }
    if breakdown is not None:
        envelope["breakdown"] = breakdown
    validate_metric_envelope(envelope)
    return envelope


def validate_metric_envelope(envelope: dict[str, Any]) -> None:
    """Validate that a metric metadata envelope satisfies Issue #19 invariants."""
    if not isinstance(envelope, dict):
        raise ValueError("metric envelope must be a dict")
    if envelope.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schemaVersion: {envelope.get('schemaVersion')}")
    for required_str in ("id", "title", "source", "url", "product", "version", "units"):
        val = envelope.get(required_str)
        if not isinstance(val, str) or not val.strip():
            raise ValueError(f"envelope missing non-empty string field '{required_str}'")

    if envelope.get("layerType") not in EVIDENCE_LAYERS:
        raise ValueError(f"invalid layerType: {envelope.get('layerType')}")
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


def build_admin_index(root: Path = ROOT) -> dict[str, Any]:
    """Build a compact precomputed administrative & concession index per region (#11).

    Allows the frontend to populate province/kabupaten selectors and show exact
    deduplicated counts and missing-resolution caveats without downloading all
    regional GeoJSON files on first load.
    """
    regions_payload = read_json(root / "data" / "regions.json", {"regions": []})
    regions_list = regions_payload.get("regions") or []

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

            provs = parse_record_provinces(props, allowed_provinces=allowed_provs)
            if not provs:
                unmapped_prov_keys.add(key)
            else:
                if len(provs) > 1:
                    cross_border_prov_keys.add(key)
                for p in provs:
                    by_prov_keys.setdefault(p, set()).add(key)

            kabs = parse_record_kabupaten(props)
            if not kabs:
                unmapped_kab_keys.add(key)
            else:
                if len(kabs) > 1:
                    cross_border_kab_keys.add(key)
                for k in kabs:
                    by_kab_keys[k].add(key)
                    for p in provs:
                        kab_by_prov.setdefault(p, set()).add(k)

        index_regions[rid] = {
            "id": rid,
            "label": r.get("label") or rid,
            "provinces": list(r.get("provinces") or []),
            "kabupaten": sorted(by_kab_keys.keys()),
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
                "byKabupaten": {k: len(ks) for k, ks in sorted(by_kab_keys.items())},
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
        "bpsProvinceCodes": BPS_PROVINCE_CODE_MAP,
        "nationalConcessions": {
            "rawCount": national_raw,
            "deduplicatedCount": len(national_unique_keys),
            "officialCount": len(national_official_keys),
            "gfwCount": len(national_gfw_keys),
        },
        "regions": index_regions,
    }


def build_sources_manifest(root: Path = ROOT) -> dict[str, Any]:
    """Generate data/sources-manifest.json with standardized metadata envelopes (#19)."""
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
        supported_granularities=["national", "region", "point"],
        units="detections",
        granularity="day",
        availability_state=firms_eval["state"],
        quality="NRT",
        value=int(h_meta.get("count") or 0) if firms_eval["state"] != "unavailable" else None,
        is_fallback=False,
        last_known_good=firms_eval["lastKnownGood"],
        age_minutes=firms_eval["observationAgeMinutes"],
        reason=firms_eval["reason"],
        caveats=[
            "Titik panas satelit (anomali termal ~375 m) bukan kejadian kebakaran terverifikasi lapangan.",
            "Jumlah titik FIRMS tidak dapat dikalikan ukuran piksel menjadi luas area terbakar (hektar).",
            "Shard runtime dikelompokkan per 7 wilayah logis (pulau/kepulauan); filter provinsi/kabupaten memerlukan batas poligon admin-1/admin-2 sehingga tidak disubstitusi diam-diam dengan total pulau.",
        ],
        breakdown={
            "platforms": h_meta.get("platforms") or ["S-NPP", "NOAA-20", "NOAA-21"],
            "sourceCounts": hotspots_status.get("sourceCounts") or {},
            "days": sorted_dates,
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
        reason=(
            "Layer resmi BIG (kehutanan & tambang) aktif nasional; layer izin sawit BIG hanya mencakup kabupaten terpilih dan layer suplemen GFW berstatus partial/cached."
        ),
        caveats=[
            "Inventaris ini bukan kadaster legal lengkap; tanggal dan kelengkapan antar-sumber berbeda.",
            "Poligon lintas batas provinsi/kabupaten dipetakan dengan aturan interseksi dan dihitung secara terdeduplikasi berdasarkan ID sumber.",
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
        source="WALHI Kalimantan (Kompas.id / Detik) & OSINT Korporasi/Politik Bername",
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
        availability_state="official",
        quality="OFFICIAL",
        value=len(dossiers_list),
        is_fallback=False,
        last_known_good=False,
        reason="Tersedia khusus untuk 12 konsesi kurasi di Kalimantan; wilayah lain belum memiliki dossier investigatif.",
        caveats=[
            "Angka klaim WALHI (Jan–Jul 2026) adalah laporan terikat periode, bukan hasil join langsung dengan titik FIRMS 7 hari terakhir.",
            " Kepemilikan grup (Control) dan ikatan politik (PoliticalTie) dikutip dari sumber publik bernama dan tidak membuktikan kesalahan hukum atau pembakaran.",
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
) -> dict[str, Any]:
    """Build unified presentation-level ConcessionViewModel rows (#12, #13, #14).

    Respects ADR-007:
    - Keeps generic inventory and curated dossier JSON separate on disk.
    - Matches dossier entries to inventory records ONLY when a verifiable
      dossierId link exists (`matchBasis == 'confirmed_dossier_id'`).
    - Never transfers ownership/political claims to generic inventory records by proximity.
    - Keeps unmatched curated dossiers as independent `dossier-only` entries so
      all 12 Kalimantan dossiers remain accessible without double-counting confirmed matches.
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
        provs = parse_record_provinces(props, allowed_provinces=allowed_provinces)
        kabs = parse_record_kabupaten(props)
        bbox, centroid = extract_geometry_bbox_and_centroid(feat.get("geometry"))

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
        d_provs = parse_record_provinces(d, allowed_provinces=allowed_provinces)
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
                "quality": b_qual if b_qual in ("OFFICIAL", "GFW", "PERKIRAAN") else "CURATED_DOSSIER",
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
    for layer in inv_manifest.get("layers") or []:
        rel_url = layer.get("url")
        if rel_url:
            fc = read_json(root / rel_url, {"features": []})
            features.extend(fc.get("features") or [])

    conc_manifest = read_json(root / "data" / "concessions" / "manifest.json", {})
    reg_conc_meta = ((conc_manifest.get("regions") or {}).get(region_id)) or {}
    dossiers_list: list[dict[str, Any]] = []
    if reg_conc_meta.get("dossiers"):
        d_payload = read_json(root / reg_conc_meta["dossiers"], {})
        dossiers_list = d_payload.get("dossiers") or []
    dossier_bounds: list[dict[str, Any]] = []
    if reg_conc_meta.get("boundaries"):
        b_payload = read_json(root / reg_conc_meta["boundaries"], {})
        dossier_bounds = b_payload.get("features") or []

    return build_concession_view_models(
        inventory_features=features,
        dossiers=dossiers_list,
        dossier_boundaries=dossier_bounds,
        region_id=region_id,
        allowed_provinces=allowed_provs or None,
    )


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
) -> dict[str, Any]:
    """Filter, sort, and paginate unified ConcessionViewModel rows (#13)."""
    q = str(search or "").strip().lower()
    sec = str(sector or "").strip()
    qual = str(quality or "").strip().upper()
    norm_prov = normalize_province_token(prov) if prov else ""
    norm_kab = normalize_kabupaten_token(kab) if kab else ""

    filtered: list[dict[str, Any]] = []
    for row in rows or []:
        if sec and row.get("sector") != sec:
            continue
        if dossier_only and not row.get("hasInvestigativeDossier"):
            continue
        if qual:
            if qual == "DOSSIER":
                if not row.get("hasInvestigativeDossier"):
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


def generate_v2_Foundation_artifacts(root: Path = ROOT, check_only: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    admin_index = build_admin_index(root)
    sources_manifest = build_sources_manifest(root)
    for env in sources_manifest["metrics"].values():
        validate_metric_envelope(env)
    if not check_only:
        write_json_atomic(root / "data" / "admin-index.json", admin_index)
        write_json_atomic(root / "data" / "sources-manifest.json", sources_manifest)
    return admin_index, sources_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without writing files")
    args = parser.parse_args()
    admin_index, sources_manifest = generate_v2_Foundation_artifacts(ROOT, check_only=args.check)
    kal_vm = build_region_concession_view_models("kalimantan", ROOT)
    print(
        f"v2_contracts: validated {len(sources_manifest['metrics'])} metric envelopes, "
        f"{len(admin_index['regions'])} regional admin indexes "
        f"({admin_index['nationalConcessions']['deduplicatedCount']} deduplicated concessions), "
        f"and Kalimantan unified ConcessionViewModel ({kal_vm['stats']['totalUnifiedCount']} rows, "
        f"{kal_vm['stats']['matchedDossierCount']} matched dossiers + "
        f"{kal_vm['stats']['unmatchedDossierOnlyCount']} dossier-only)"
    )


if __name__ == "__main__":
    main()

