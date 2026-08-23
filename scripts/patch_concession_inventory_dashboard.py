#!/usr/bin/env python3
"""Patch the composed MERATUS dashboard with the generic concession inventory.

Run after patch_land_holdings_dashboard.py and patch_region_dashboard.py. The
inventory remains distinct from investigative dossiers: it is a broad spatial
catalog of public concession/licence records, loaded on demand by region/sector.
"""
from __future__ import annotations
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 occurrence, found {count}")
    return text.replace(old, new, 1)


def build_patched_index(source: str) -> str:
    if "function refreshConcessionInventoryLayer()" in source:
        return source
    if "function selectRegion(regionId, preferredDate)" not in source:
        raise RuntimeError("concession inventory patch must run after patch_region_dashboard.py")
    text = source
    text = replace_once(
        text,
        '            <label><input type="checkbox" id="tog-regions" checked /> Boundary dossier</label>\n'
        '            <label><input type="checkbox" id="tog-centroids" /> Tampilkan semua centroid</label>',
        '            <label><input type="checkbox" id="tog-regions" checked /> Boundary dossier</label>\n'
        '            <label><input type="checkbox" id="tog-inventory" /> Inventaris semua konsesi</label>\n'
        '            <label><input type="checkbox" id="tog-centroids" /> Tampilkan semua centroid</label>',
        "inventory layer toggle",
    )
    text = replace_once(
        text,
        "    var hotspotCache = {};\n    var staticRegionCache = {};\n    var regionRequest = 0;",
        "    var hotspotCache = {};\n    var staticRegionCache = {};\n    var concessionInventoryManifestCache = {};\n    var concessionInventoryDataCache = {};\n    var currentConcessionInventoryManifest = null;\n    var concessionInventoryRequest = 0;\n    var regionRequest = 0;",
        "inventory cache variables",
    )
    helpers = r'''
    function loadConcessionInventoryManifest(regionId) {
      if (regionId === "indonesia") return Promise.resolve(null);
      var concessionEntry = concessionManifest && concessionManifest.regions ? concessionManifest.regions[regionId] : null;
      var url = concessionEntry && concessionEntry.inventory;
      if (!url) return Promise.resolve(null);
      if (!concessionInventoryManifestCache[url]) {
        concessionInventoryManifestCache[url] = loadJson(url).catch(function (err) {
          delete concessionInventoryManifestCache[url];
          console.warn("Concession inventory manifest unavailable", regionId, err);
          return null;
        });
      }
      return concessionInventoryManifestCache[url];
    }

    function loadConcessionInventoryData(entry) {
      if (!entry || !entry.url) return Promise.resolve({ type: "FeatureCollection", features: [] });
      if (!concessionInventoryDataCache[entry.url]) {
        concessionInventoryDataCache[entry.url] = loadJson(entry.url).catch(function (err) {
          delete concessionInventoryDataCache[entry.url];
          throw err;
        });
      }
      return concessionInventoryDataCache[entry.url];
    }

    function inventoryEntriesForView() {
      var layers = currentConcessionInventoryManifest && Array.isArray(currentConcessionInventoryManifest.layers)
        ? currentConcessionInventoryManifest.layers : [];
      if (!state.sector) return layers;
      return layers.filter(function (entry) { return (entry.sectors || []).indexOf(state.sector) !== -1; });
    }

    function inventoryStyle(feature) {
      var p = feature.properties || {};
      var sector = p.sector || "";
      var color = sector === "Tambang" ? "#9c7ad6" : sector === "Sawit" ? "#c38b42" : "#6d9b76";
      return { color: color, weight: p.quality === "OFFICIAL" ? 1.2 : 1, opacity: 0.82,
        fillColor: color, fillOpacity: 0.075, dashArray: p.quality === "GFW" ? "6 5" : null };
    }

    function inventoryValue(value, suffix) {
      if (value == null || value === "") return "—";
      if (typeof value === "number") return value.toLocaleString("id-ID", { maximumFractionDigits: 2 }) + (suffix || "");
      return escapeHtml(value) + (suffix || "");
    }

    function showConcessionInventoryFeature(feature) {
      var p = feature.properties || {};
      state.selectedId = p.inventoryId || p.sourceRecordId || p.name || "inventory";
      state.selectedType = "inventory";
      var source = p.sourceUrl
        ? '<a href="' + escapeHtml(p.sourceUrl) + '" target="_blank" rel="noopener">' + escapeHtml(p.source || "Source record") + ' ↗</a>'
        : escapeHtml(p.source || "Source tidak tersedia");
      var caveat = p.coverageCaveat ? '<div class="caveat">' + escapeHtml(p.coverageCaveat) + '</div>' : '';
      var dossierLink = p.dossierId
        ? '<div class="caveat" style="border-color:var(--amber)"><strong>INVESTIGATIVE DOSSIER MATCH</strong><br/>Nama operator cocok dengan dossier MERATUS <span class="mono">' + escapeHtml(p.dossierId) + '</span>. Ini hanya cross-link nama, bukan inferensi kepemilikan tambahan.</div>'
        : '';
      elInsp.innerHTML =
        '<div class="insp-title">' + escapeHtml(p.name || "Concession record") + '</div>' +
        '<div class="insp-subtitle">Inventaris konsesi · ' + escapeHtml(p.sector || "sektor tidak dinyatakan") + ' · ' + escapeHtml(p.subtype || "tipe tidak dinyatakan") + '</div>' +
        '<div class="insp-id">CONCESSION/' + escapeHtml(String(p.inventoryId || p.sourceRecordId || "UNKNOWN")) + '</div>' +
        '<div class="summary-grid">' +
          '<div class="summary-card"><span class="label">Source quality</span><strong>' + escapeHtml(p.quality || "—") + '</strong><small>' + escapeHtml(p.sourceDataset || "") + '</small></div>' +
          '<div class="summary-card"><span class="label">Reported area</span><strong>' + inventoryValue(p.areaHa, ' ha') + '</strong><small>upstream attribute bila tersedia</small></div>' +
          '<div class="summary-card"><span class="label">Permit / HGU</span><strong>' + escapeHtml(p.permitNumber || p.hguNumber || "—") + '</strong><small>' + escapeHtml(p.permitDate || p.validFrom || "tanggal tidak tersedia") + '</small></div>' +
          '<div class="summary-card"><span class="label">Status</span><strong>' + escapeHtml(p.status || p.legalStatus || "—") + '</strong><small>' + escapeHtml(p.commodity || p.miningType || p.group || "") + '</small></div>' +
        '</div>' +
        '<details class="details-section" open><summary>Source attributes</summary><div class="section-content"><dl class="kv">' +
          '<dt>Operator / company</dt><dd>' + escapeHtml(p.name || "—") + '</dd>' +
          '<dt>Group</dt><dd>' + escapeHtml(p.group || "—") + '</dd>' +
          '<dt>Province</dt><dd>' + escapeHtml(p.province || p.provinceCode || "—") + '</dd>' +
          '<dt>District</dt><dd>' + escapeHtml(p.district || "—") + '</dd>' +
          '<dt>Commodity</dt><dd>' + escapeHtml(p.commodity || "—") + '</dd>' +
          '<dt>Permit type</dt><dd>' + escapeHtml(p.permitType || p.subtype || "—") + '</dd>' +
          '<dt>Valid to</dt><dd>' + escapeHtml(p.validTo || "—") + '</dd>' +
          '<dt>Source record</dt><dd>' + escapeHtml(p.sourceRecordId || "—") + '</dd>' +
        '</dl></div></details>' +
        '<details class="details-section" open><summary>Provenance</summary><div class="section-content"><p style="font-size:13px;line-height:1.4">' + source + '</p>' +
          '<p style="font-size:12px;color:var(--muted)">Geometry disederhanakan untuk tampilan web. Untuk batas/izin otoritatif, periksa record sumber.</p></div></details>' +
        dossierLink + caveat +
        '<div class="caveat"><strong>NO FIRE ATTRIBUTION</strong><br/>Keberadaan hotspot di dalam atau dekat polygon konsesi adalah konteks spasial saja. Dataset ini tidak menyatakan operator menyebabkan kebakaran, melakukan pelanggaran, atau memiliki afiliasi politik tertentu.</div>';
      openMobileInspector();
    }

    function refreshConcessionInventoryLayer() {
      concessionInventoryLayer.clearLayers();
      var enabled = document.getElementById("tog-inventory");
      if (!enabled || !enabled.checked || state.region === "indonesia" || !currentConcessionInventoryManifest) return;
      var entries = inventoryEntriesForView();
      if (!entries.length) return;
      var token = ++concessionInventoryRequest;
      Promise.all(entries.map(loadConcessionInventoryData)).then(function (payloads) {
        if (token !== concessionInventoryRequest) return;
        payloads.forEach(function (payload) {
          var gj = L.geoJSON(payload || { type: "FeatureCollection", features: [] }, {
            style: inventoryStyle,
            onEachFeature: function (feature, layer) {
              var p = feature.properties || {};
              layer.bindTooltip('<strong>' + escapeHtml(p.name || "Concession record") + '</strong><br/>' +
                escapeHtml(p.sector || "") + ' · ' + escapeHtml(p.subtype || "") + ' · ' + escapeHtml(p.quality || ""),
                { sticky: true, opacity: 0.94 });
              layer.on("click", function () { showConcessionInventoryFeature(feature); });
            }
          });
          concessionInventoryLayer.addLayer(gj);
        });
      }).catch(function (err) {
        if (token !== concessionInventoryRequest) return;
        console.warn("Failed to load concession inventory", err);
        elStamp.dataset.status = "stale";
        elStamp.title = "Sebagian inventaris konsesi gagal dimuat: " + String(err && err.message ? err.message : err);
      });
    }

'''
    text = replace_once(text, "    function applyStaticPayload(payload) {", helpers + "    function applyStaticPayload(payload) {", "inventory loader helpers")
    text = replace_once(text,
        "    var nationalSummaryLayer = L.layerGroup().addTo(map);\n    var concessionLayer = L.layerGroup().addTo(map);",
        "    var nationalSummaryLayer = L.layerGroup().addTo(map);\n    var concessionInventoryLayer = L.layerGroup().addTo(map);\n    var concessionLayer = L.layerGroup().addTo(map);",
        "inventory map layer")
    text = replace_once(text,
        '      var holdingCount = state.region === "kalimantan" ? landHoldings.length : 0;\n'
        '      elHeaderStats.textContent = count.toLocaleString("id-ID") + " FIRMS detections · " + scopeLabel + " · " + dossiers.length + " dossiers · " + holdingCount + " affiliated land holdings · " + mapped + "/" + dossiers.length + " boundaries mapped";',
        '      var holdingCount = state.region === "kalimantan" ? landHoldings.length : 0;\n'
        '      var inventoryCount = currentConcessionInventoryManifest && currentConcessionInventoryManifest.count != null ? Number(currentConcessionInventoryManifest.count) : 0;\n'
        '      elHeaderStats.textContent = count.toLocaleString("id-ID") + " FIRMS detections · " + scopeLabel + " · " + inventoryCount.toLocaleString("id-ID") + " concession records · " + dossiers.length + " dossiers · " + holdingCount + " affiliated land holdings · " + mapped + "/" + dossiers.length + " boundaries mapped";',
        "inventory header count")
    text = replace_once(text,
        "      renderList();\n      refreshConcessionMarkers();\n      refreshEstimatedLandLayer();\n      refreshFirmsLayer();",
        "      renderList();\n      refreshConcessionMarkers();\n      refreshConcessionInventoryLayer();\n      refreshEstimatedLandLayer();\n      refreshFirmsLayer();",
        "region render inventory")
    text = replace_once(text,
        "      return Promise.all([loadHotspotDay(regionId, date), loadRegionStatic(regionId)]).then(function (pair) {\n"
        "        if (token !== regionRequest) return;\n"
        "        applyStaticPayload(pair[1]);\n"
        "        applyHotspotPayload(pair[0]);",
        "      return Promise.all([loadHotspotDay(regionId, date), loadRegionStatic(regionId), loadConcessionInventoryManifest(regionId)]).then(function (pair) {\n"
        "        if (token !== regionRequest) return;\n"
        "        applyStaticPayload(pair[1]);\n"
        "        currentConcessionInventoryManifest = pair[2];\n"
        "        applyHotspotPayload(pair[0]);",
        "region selection inventory manifest")
    text = replace_once(text,
        "        renderList();\n        refreshConcessionMarkers();\n        refreshFirmsLayer();",
        "        renderList();\n        refreshConcessionMarkers();\n        refreshConcessionInventoryLayer();\n        refreshFirmsLayer();",
        "sector/filter inventory refresh")
    text = replace_once(text,
        '    document.getElementById("tog-centroids").addEventListener("change", function (e) {\n'
        '      state.showCentroids = !!e.target.checked;\n'
        '      refreshConcessionMarkers();\n'
        '    });',
        '    document.getElementById("tog-inventory").addEventListener("change", function () {\n'
        '      refreshConcessionInventoryLayer();\n'
        '    });\n'
        '    document.getElementById("tog-centroids").addEventListener("change", function (e) {\n'
        '      state.showCentroids = !!e.target.checked;\n'
        '      refreshConcessionMarkers();\n'
        '    });',
        "inventory toggle event")
    return text


def validate_patched(text: str) -> None:
    required = ['id="tog-inventory"',"function loadConcessionInventoryManifest(regionId)",
        "function refreshConcessionInventoryLayer()","function showConcessionInventoryFeature(feature)",
        "concessionInventoryLayer = L.layerGroup().addTo(map)","currentConcessionInventoryManifest = pair[2]",
        "concession records","NO FIRE ATTRIBUTION"]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError("missing concession inventory integration markers: " + ", ".join(missing))


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--check",action="store_true",help="validate without writing index.html"); args = parser.parse_args()
    source = INDEX.read_text(encoding="utf-8"); patched = build_patched_index(source); validate_patched(patched)
    if args.check:
        print("concession inventory dashboard patch: OK"); return
    if patched != source:
        INDEX.write_text(patched,encoding="utf-8"); print("patched index.html with generic concession inventory")
    else:
        print("index.html already contains generic concession inventory")

if __name__ == "__main__":
    main()
