#!/usr/bin/env python3
"""Inject the affiliated-land-holding display layer into the single-file dashboard.

The source dashboard intentionally keeps WALHI ConcessionClaim objects separate from
LandHolding/Control objects. This patch is applied before GitHub Pages packaging so
`index.html` does not need to duplicate land-holding records inside dossiers.json.

Usage:
  python scripts/patch_land_holdings_dashboard.py          # patch index.html
  python scripts/patch_land_holdings_dashboard.py --check  # validate patchability only
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
HOLDINGS = ROOT / "data" / "affiliated-land-holdings.json"
CENTERS = ROOT / "data" / "affiliated-land-display-centers.json"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 occurrence, found {count}")
    return text.replace(old, new, 1)


def validate_data() -> None:
    holdings = json.loads(HOLDINGS.read_text(encoding="utf-8"))
    centers = json.loads(CENTERS.read_text(encoding="utf-8"))

    records = holdings.get("holdings", [])
    center_map = centers.get("centers", {})
    ids = {row.get("id") for row in records}

    missing = sorted(row_id for row_id in ids if row_id not in center_map)
    extra = sorted(row_id for row_id in center_map if row_id not in ids)
    if missing:
        raise RuntimeError(f"missing display centers for: {', '.join(missing)}")
    if extra:
        raise RuntimeError(f"orphan display centers for: {', '.join(extra)}")

    for row in records:
        area = row.get("areaHa")
        if not isinstance(area, (int, float)) or area <= 0:
            raise RuntimeError(f"invalid areaHa for {row.get('id')}: {area!r}")

    for row_id, center in center_map.items():
        lat, lon = center.get("lat"), center.get("lon")
        if not isinstance(lat, (int, float)) or not -90 <= lat <= 90:
            raise RuntimeError(f"invalid latitude for {row_id}: {lat!r}")
        if not isinstance(lon, (int, float)) or not -180 <= lon <= 180:
            raise RuntimeError(f"invalid longitude for {row_id}: {lon!r}")
        if not center.get("precision") or not center.get("evidence"):
            raise RuntimeError(f"display center {row_id} lacks precision/evidence metadata")


def build_patched_index(source: str) -> str:
    if "function refreshEstimatedLandLayer()" in source:
        # Idempotent for local/deployment reruns.
        return source

    text = source

    text = replace_once(
        text,
        "    .legend .boundary-none { border: 1px dashed var(--warn); background: transparent; }",
        "    .legend .boundary-none { border: 1px dashed var(--warn); background: transparent; }\n"
        "    .legend .estimated-land { width: 12px; height: 12px; border: 2px dashed #6f9fc8; border-radius: 50%; background: rgba(111,159,200,0.08); }",
        "legend CSS",
    )

    text = replace_once(
        text,
        '          <div><span class="boundary-approx"></span>PERKIRAAN boundary</div>\n'
        '          <div><span class="boundary-none"></span>Location only / no boundary</div>',
        '          <div><span class="boundary-approx"></span>PERKIRAAN boundary</div>\n'
        '          <div><span class="estimated-land"></span>PERKIRAAN LUAS IZIN · bukan batas legal</div>\n'
        '          <div><span class="boundary-none"></span>Location only / no boundary</div>',
        "legend HTML",
    )

    text = replace_once(
        text,
        '      loadJson("data/boundaries.geojson").catch(function () {\n'
        '        return { type: "FeatureCollection", features: [] };\n'
        '      }),\n'
        '      loadJson("data/firms-status.json").catch(function () { return null; })\n'
        '    ]).then(function (pair) {\n'
        '      boot(pair[0], pair[1], pair[2], pair[3]);',
        '      loadJson("data/boundaries.geojson").catch(function () {\n'
        '        return { type: "FeatureCollection", features: [] };\n'
        '      }),\n'
        '      loadJson("data/firms-status.json").catch(function () { return null; }),\n'
        '      loadJson("data/affiliated-land-holdings.json").catch(function () { return { meta: {}, people: [], holdings: [] }; }),\n'
        '      loadJson("data/affiliated-land-display-centers.json").catch(function () { return { meta: {}, centers: {} }; })\n'
        '    ]).then(function (pair) {\n'
        '      boot(pair[0], pair[1], pair[2], pair[3], pair[4], pair[5]);',
        "dataset loading",
    )

    text = replace_once(
        text,
        "    function boot(firmsPayload, dossierPayload, boundariesGeo, pipelineStatusPayload) {\n"
        "    var firms = [];",
        "    function boot(firmsPayload, dossierPayload, boundariesGeo, pipelineStatusPayload, affiliatedPayload, holdingCentersPayload) {\n"
        "    var firms = [];",
        "boot signature",
    )

    text = replace_once(
        text,
        "    var walhi = dossierPayload.walhiSummary || null;\n"
        "    var boundaryById = {};",
        "    var walhi = dossierPayload.walhiSummary || null;\n"
        "    var landHoldings = affiliatedPayload && Array.isArray(affiliatedPayload.holdings) ? affiliatedPayload.holdings : [];\n"
        "    var landPeople = affiliatedPayload && Array.isArray(affiliatedPayload.people) ? affiliatedPayload.people : [];\n"
        "    var landPeopleById = {};\n"
        "    landPeople.forEach(function (p) { landPeopleById[p.id] = p; });\n"
        "    var holdingCenters = holdingCentersPayload && holdingCentersPayload.centers ? holdingCentersPayload.centers : {};\n"
        "    var boundaryById = {};",
        "land-holding variables",
    )

    text = replace_once(
        text,
        '      elHeaderStats.textContent = count.toLocaleString("id-ID") + " FIRMS detections · " + dossiers.length + " dossiers · " + mapped + "/" + dossiers.length + " boundaries mapped";',
        '      elHeaderStats.textContent = count.toLocaleString("id-ID") + " FIRMS detections · " + dossiers.length + " WALHI dossiers · " + landHoldings.length + " affiliated land holdings · " + mapped + "/" + dossiers.length + " boundaries mapped";',
        "header stats",
    )

    text = replace_once(
        text,
        "    var concessionLayer = L.layerGroup().addTo(map);\n"
        "    var regionLayer = L.layerGroup().addTo(map);",
        "    var concessionLayer = L.layerGroup().addTo(map);\n"
        "    var estimatedLandLayer = L.layerGroup().addTo(map);\n"
        "    var regionLayer = L.layerGroup().addTo(map);",
        "map layer",
    )

    marker = "    function refreshConcessionMarkers() {"
    if text.count(marker) != 1:
        raise RuntimeError(f"refreshConcessionMarkers marker mismatch: {text.count(marker)}")

    helpers = r'''
    function estimatedLandRadiusMeters(areaHa) {
      var hectares = Number(areaHa);
      if (!isFinite(hectares) || hectares <= 0) return 0;
      return Math.sqrt((hectares * 10000) / Math.PI);
    }

    function formatAreaHa(areaHa) {
      var value = Number(areaHa);
      return isFinite(value)
        ? value.toLocaleString("id-ID", { maximumFractionDigits: 2 }) + " ha"
        : "luas tidak tersedia";
    }

    function holdingCenter(h) {
      return h && h.id ? holdingCenters[h.id] : null;
    }

    function showLandHolding(h) {
      state.selectedId = h.id;
      state.selectedType = "landholding";
      var center = holdingCenter(h) || {};
      var control = h.control || {};
      var persons = (control.persons || []).map(function (link) {
        var p = landPeopleById[link.personId];
        var relation = p && p.relationToHajiIsam ? p.relationToHajiIsam + " · " : "";
        return '<div class="tie-card"><strong>' + escapeHtml(p ? p.name : link.personId) + '</strong><br/>' +
          '<span class="tie-meta">' + escapeHtml(relation + (link.role || "role tidak dinyatakan")) + '</span></div>';
      }).join("") || '<div class="insp-empty">Tidak ada person yang dikunci.</div>';

      var holdingSources = (h.sources || []).map(function (s) {
        return '<li><a href="' + escapeHtml(s.url) + '" target="_blank" rel="noopener">' +
          escapeHtml(s.label || s.type || "source") + '</a></li>';
      }).join("");
      var centerSources = (center.sources || []).map(function (url, idx) {
        return '<li><a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">Display-center source ' + (idx + 1) + '</a></li>';
      }).join("");
      var caves = (h.caveats || []).map(function (c) {
        return '<div class="caveat">' + escapeHtml(c) + '</div>';
      }).join("");
      var centerText = center.lat != null && center.lon != null
        ? Number(center.lat).toFixed(4) + ', ' + Number(center.lon).toFixed(4)
        : '—';

      elInsp.innerHTML =
        '<div class="insp-title">' + escapeHtml(h.company) + '</div>' +
        '<div class="insp-subtitle">' + escapeHtml(h.sector || '') + ' · ' + escapeHtml(h.province || '') + '</div>' +
        '<div class="insp-id">OBJ/' + escapeHtml(String(h.id || '').toUpperCase()) + ' · LandHolding / Control</div>' +
        '<div class="summary-grid">' +
          '<div class="summary-card"><span class="label">Reported permit area</span><strong>' + escapeHtml(formatAreaHa(h.areaHa)) + '</strong><small>' + escapeHtml(h.permitType || 'izin tidak dinyatakan') + '</small></div>' +
          '<div class="summary-card"><span class="label">Map geometry</span><strong>PERKIRAAN LUAS IZIN</strong><small>bukan batas legal konsesi</small></div>' +
          '<div class="summary-card"><span class="label">Control link</span><strong>' + escapeHtml(control.group || 'Tidak terpetakan') + '</strong><small>' + escapeHtml(control.relationshipType || 'relationship tidak dinyatakan') + ' · confidence ' + escapeHtml(control.confidence || '—') + '</small></div>' +
          '<div class="summary-card"><span class="label">Display center</span><strong>' + escapeHtml(center.precision || 'approximate') + '</strong><small>' + escapeHtml(center.label || centerText) + '</small></div>' +
        '</div>' +
        '<div class="caveat" style="border-color:#6f9fc8"><strong>SCHEMATIC EQUAL-AREA CIRCLE</strong><br/>' +
          'Radius dihitung dari luas izin yang dilaporkan. Bentuk lingkaran bukan bentuk HGU/PBPH sebenarnya. ' +
          'Titik pusat juga dapat berupa pendekatan wilayah operasi sesuai label precision.</div>' +
        '<details class="details-section" open><summary>Ownership / control</summary><div class="section-content">' + persons + '</div></details>' +
        '<details class="details-section" open><summary>Permit details</summary><div class="section-content"><dl class="kv">' +
          '<dt>Permit type</dt><dd>' + escapeHtml(h.permitType || '—') + '</dd>' +
          '<dt>Permit number</dt><dd>' + escapeHtml(h.permitNumber || '—') + '</dd>' +
          '<dt>Status</dt><dd>' + escapeHtml(h.permitStatus || '—') + '</dd>' +
          '<dt>Reported area</dt><dd>' + escapeHtml(formatAreaHa(h.areaHa)) + '</dd>' +
          '<dt>Display center</dt><dd>' + escapeHtml(centerText) + '</dd>' +
          '<dt>Center precision</dt><dd>' + escapeHtml(center.precision || '—') + '</dd>' +
          '</dl><p style="font-size:12px;color:var(--muted);line-height:1.4">' + escapeHtml(center.evidence || '') + '</p></div></details>' +
        '<details class="details-section"><summary>Sources</summary><div class="section-content"><strong>Holding evidence</strong><ul class="src-list">' + holdingSources + '</ul>' +
          '<strong>Display-center evidence</strong><ul class="src-list">' + centerSources + '</ul></div></details>' +
        '<details class="details-section"><summary>Caveats (' + (h.caveats || []).length + ')</summary><div class="section-content">' + caves + '</div></details>';

      openMobileInspector();
    }

    function refreshEstimatedLandLayer() {
      estimatedLandLayer.clearLayers();
      landHoldings.forEach(function (h) {
        var center = holdingCenter(h);
        if (!center || center.lat == null || center.lon == null) return;
        var radius = estimatedLandRadiusMeters(h.areaHa);
        if (!radius) return;

        var circle = L.circle([Number(center.lat), Number(center.lon)], {
          radius: radius,
          color: "#6f9fc8",
          weight: 2,
          opacity: 0.92,
          dashArray: "7 6",
          fillColor: "#6f9fc8",
          fillOpacity: 0.055
        });
        circle.bindTooltip(
          '<strong>' + escapeHtml(h.company) + '</strong><br/>' +
          'PERKIRAAN LUAS IZIN · ' + escapeHtml(formatAreaHa(h.areaHa)) + '<br/>' +
          '<span style="color:#9a968e">bukan batas legal · center: ' + escapeHtml(center.precision || 'approximate') + '</span>',
          { sticky: true, opacity: 0.96 }
        );
        circle.on("click", function () { showLandHolding(h); });
        estimatedLandLayer.addLayer(circle);
      });
    }

'''
    text = text.replace(marker, helpers + marker, 1)

    text = replace_once(
        text,
        "    renderList();\n"
        "    refreshConcessionMarkers();\n"
        "    refreshFirmsLayer();",
        "    renderList();\n"
        "    refreshConcessionMarkers();\n"
        "    refreshEstimatedLandLayer();\n"
        "    refreshFirmsLayer();",
        "initial layer render",
    )

    return text


def validate_patched(text: str) -> None:
    required = [
        'data/affiliated-land-holdings.json',
        'data/affiliated-land-display-centers.json',
        'PERKIRAAN LUAS IZIN · bukan batas legal',
        'function refreshEstimatedLandLayer()',
        'function showLandHolding(h)',
        'estimatedLandRadiusMeters',
        'LandHolding / Control',
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError("missing integration markers: " + ", ".join(missing))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate without writing index.html")
    args = parser.parse_args()

    validate_data()
    source = INDEX.read_text(encoding="utf-8")
    patched = build_patched_index(source)
    validate_patched(patched)

    if args.check:
        print("land-holding dashboard patch: OK")
        return

    if patched != source:
        INDEX.write_text(patched, encoding="utf-8")
        print("patched index.html with estimated land-holding circles")
    else:
        print("index.html already contains estimated land-holding circles")


if __name__ == "__main__":
    main()
