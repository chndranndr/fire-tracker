#!/usr/bin/env python3
"""Patch index.html with MERATUS v2 Wave 2 (#12, #13, #14, #15):
- #12: Unified ConcessionViewModel combining generic inventory & investigative dossiers without double-counting or proximity allegation transfer
- #13: Browse, search, filter, sort, and paginate all indexed concessions in a region with raw-vs-deduplicated count explanations
- #14: Contextual concession detail inspector with Summary / Map / Investigation tabs (Investigation strictly conditional on dossier link) and return-to-list state preservation
- #15: Minimal default map state, compact grouped layer control, explicit Burned Area unavailable warning, focused concession highlight bar, and clear legend
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


V2_WAVE2_CSS = r"""
    /* ==========================================================================
       MERATUS v2 Wave 2 (#12, #13, #14, #15): Unified Concessions & Minimal Map
       ========================================================================== */
    .concession-explorer-controls {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin: 6px 0;
    }
    .concession-explorer-controls label {
      display: flex;
      flex-direction: column;
      gap: 3px;
      font-family: var(--mono);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
    }
    .concession-explorer-controls select {
      background: var(--bg);
      color: var(--ink);
      border: 1px solid var(--line-2);
      border-radius: 3px;
      padding: 5px 6px;
      font-family: var(--sans);
      font-size: 12px;
    }
    .concession-count-breakdown {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 7px 9px;
      margin: 6px 0;
      font-size: 11px;
      line-height: 1.4;
      color: var(--muted);
    }
    .concession-count-breakdown strong {
      color: var(--ink);
    }
    .concession-caveat-note {
      margin-top: 4px;
      padding-top: 4px;
      border-top: 1px dashed var(--line);
      font-size: 10px;
      color: var(--muted);
    }
    .concession-pagination {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      padding: 6px 0;
      border-top: 1px solid var(--line);
      margin-top: 6px;
      font-family: var(--mono);
      font-size: 11px;
      color: var(--muted);
    }
    .concession-pagination button {
      background: var(--bg);
      color: var(--ink);
      border: 1px solid var(--line-2);
      border-radius: 3px;
      padding: 4px 8px;
      font-family: var(--mono);
      font-size: 10px;
      cursor: pointer;
    }
    .concession-pagination button:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    .concession-pagination button:not(:disabled):hover {
      border-color: var(--amber);
      color: var(--amber);
    }
    .vm-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 4px;
    }
    .vm-badge {
      display: inline-block;
      padding: 1px 5px;
      border-radius: 3px;
      font-family: var(--mono);
      font-size: 9px;
      font-weight: 600;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      border: 1px solid var(--line-2);
    }
    .vm-badge.official {
      color: #6fd08c;
      border-color: rgba(47, 158, 68, 0.45);
      background: rgba(47, 158, 68, 0.12);
    }
    .vm-badge.gfw {
      color: var(--amber);
      border-color: rgba(227, 160, 8, 0.45);
      background: rgba(227, 160, 8, 0.12);
    }
    .vm-badge.dossier-linked {
      color: #ff9b85;
      border-color: rgba(226, 58, 20, 0.55);
      background: rgba(226, 58, 20, 0.16);
    }
    .vm-badge.dossier-only {
      color: #ffd479;
      border-color: rgba(227, 160, 8, 0.65);
      background: rgba(227, 160, 8, 0.18);
    }
    .inspector-return-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--line);
    }
    .btn-return-list {
      background: var(--bg);
      color: var(--ink);
      border: 1px solid var(--line-2);
      border-radius: 3px;
      padding: 4px 9px;
      font-family: var(--mono);
      font-size: 11px;
      cursor: pointer;
    }
    .btn-return-list:hover,
    .btn-return-list:focus-visible {
      border-color: var(--amber);
      color: var(--amber);
      outline: none;
    }
    .inspector-tabs {
      display: flex;
      gap: 4px;
      margin: 8px 0 10px;
      border-bottom: 1px solid var(--line-2);
      padding-bottom: 6px;
    }
    .insp-tab-btn {
      background: transparent;
      color: var(--muted);
      border: 1px solid transparent;
      border-radius: 3px;
      padding: 5px 9px;
      font-family: var(--mono);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      cursor: pointer;
    }
    .insp-tab-btn:hover,
    .insp-tab-btn:focus-visible {
      color: var(--ink);
      border-color: var(--line-2);
      outline: none;
    }
    .insp-tab-btn.active {
      color: var(--bg);
      background: var(--amber);
      border-color: var(--amber);
      font-weight: 600;
    }
    .insp-action-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 8px 0;
    }
    .insp-action-btn {
      background: var(--bg);
      color: var(--ink);
      border: 1px solid var(--line-2);
      border-radius: 3px;
      padding: 5px 10px;
      font-family: var(--mono);
      font-size: 11px;
      cursor: pointer;
    }
    .insp-action-btn.primary {
      border-color: var(--amber);
      color: var(--amber);
    }
    .insp-action-btn:hover {
      background: rgba(227, 160, 8, 0.12);
    }
    /* Compact Map Layer Control (#15) */
    .map-layer-control {
      position: absolute;
      top: 12px;
      right: 12px;
      z-index: 520;
      background: rgba(15, 15, 16, 0.92);
      border: 1px solid var(--line-2);
      border-radius: 5px;
      padding: 8px 10px;
      min-width: 215px;
      max-width: 265px;
      font-size: 12px;
      backdrop-filter: blur(6px);
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
    }
    .map-layer-control-h {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-family: var(--mono);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 6px;
      padding-bottom: 4px;
      border-bottom: 1px solid var(--line);
    }
    .map-layer-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      padding: 3px 0;
      font-size: 12px;
      color: var(--ink);
    }
    .map-layer-row label {
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
    }
    .map-layer-warn {
      margin-top: 6px;
      padding: 5px 7px;
      border-radius: 3px;
      border-left: 2px solid var(--fire);
      background: rgba(226, 58, 20, 0.12);
      font-size: 11px;
      line-height: 1.35;
      color: var(--ink);
      display: none;
    }
    .map-layer-warn.visible {
      display: block;
    }
    .focused-concession-bar {
      position: absolute;
      bottom: 44px;
      left: 12px;
      z-index: 520;
      background: rgba(15, 15, 16, 0.94);
      border: 1px solid var(--amber);
      border-radius: 4px;
      padding: 6px 10px;
      display: none;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      max-width: calc(100% - 24px);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    }
    .focused-concession-bar.visible {
      display: flex;
      flex-wrap: wrap;
    }
    @media (max-width: 900px) {
      .map-layer-control {
        top: 56px;
        right: 8px;
        min-width: 185px;
        padding: 6px 8px;
      }
      .focused-concession-bar {
        bottom: 68px;
        left: 8px;
        right: 8px;
      }
    }
"""


V2_EXPLORER_CONTROLS_HTML = """          <div class="concession-explorer-controls" id="concession-explorer-controls" aria-label="Filter dan urutan eksplorer konsesi terpadu">
            <label for="f-concession-source">Sumber / Kategori
              <select id="f-concession-source">
                <option value="">Semua (Inventaris + Dossier)</option>
                <option value="OFFICIAL">Resmi / OFFICIAL (BIG)</option>
                <option value="GFW">Indikatif / ESTIMATED (GFW)</option>
                <option value="DOSSIER">Memiliki Dossier Investigasi</option>
                <option value="UNMATCHED_DOSSIER">Dossier Independen Saja</option>
              </select>
            </label>
            <label for="f-concession-sort">Urutkan
              <select id="f-concession-sort">
                <option value="default">Dossier &amp; Luas Terbesar</option>
                <option value="name_asc">Nama Operator (A–Z)</option>
                <option value="area_desc">Luas Terbesar (ha)</option>
                <option value="area_asc">Luas Terkecil (ha)</option>
                <option value="sector_asc">Sektor &amp; Nama</option>
              </select>
            </label>
          </div>

          <div class="concession-count-breakdown" id="concession-count-breakdown" aria-live="polite">
            <div id="concession-count-headline">Memuat indeks konsesi terpadu…</div>
            <div class="concession-caveat-note" id="concession-inventory-caveat">
              Inventaris publik menggabungkan sumber berbeda (BIG/GFW), belum mencakup seluruh kadaster legal, dan dapat memuat tumpang-tindih izin. Klaim kepemilikan/politik pada dossier kurasi tidak pernah ditransfer otomatis ke izin di sekitarnya.
            </div>
          </div>"""


V2_MAP_LAYER_CONTROL_HTML = """        <div class="map-layer-control" id="map-layer-control" role="region" aria-label="Kontrol lapisan peta terpadu">
          <div class="map-layer-control-h">
            <span>Lapisan Peta (#15)</span>
            <span class="mono" id="map-layer-scope-tag">Minimal</span>
          </div>
          <div class="map-layer-row">
            <label><input type="checkbox" id="tog-map-firms" checked /> Hotspots (FIRMS)</label>
            <span class="avail-badge fresh">NRT</span>
          </div>
          <div class="map-layer-row">
            <label><input type="checkbox" id="tog-map-burned-area" /> Burned Area</label>
            <span class="avail-badge unavailable">UNAVAILABLE</span>
          </div>
          <div class="map-layer-row">
            <label><input type="checkbox" id="tog-map-concessions" /> Concessions</label>
            <span class="avail-badge official">ON-DEMAND</span>
          </div>
          <div class="map-layer-row">
            <label><input type="checkbox" id="tog-map-admin" checked /> Admin Boundaries</label>
            <span class="avail-badge official">7 WILAYAH</span>
          </div>
          <div class="map-layer-warn" id="burned-area-layer-warning" role="status">
            <strong>DATA UNAVAILABLE:</strong> Produk poligon area terbakar terverifikasi belum di-ingest (#20). Deteksi titik panas satelit FIRMS bukan poligon area terbakar.
          </div>
        </div>

        <div class="focused-concession-bar" id="focused-concession-bar" role="status" aria-live="polite">
          <span>Fokus Konsesi: <strong id="focused-concession-name">—</strong></span>
          <button type="button" class="filter-reset-btn" id="btn-focused-concession-zoom">Zoom Poligon</button>
          <button type="button" class="filter-reset-btn" id="btn-focused-concession-clear">Hapus Fokus ✕</button>
        </div>"""


V2_WAVE2_JS = r"""
    /* ==========================================================================
       MERATUS v2 Wave 2 (#12, #13, #14, #15): Unified ConcessionViewModel & Map
       ========================================================================== */
    var unifiedConcessionCache = {};
    var unifiedConcessionLoading = {};
    var featureByViewModelId = {};
    var viewModelById = {};

    function extractGeometryBboxAndCentroid(geometry) {
      if (!geometry || !geometry.coordinates) return { bbox: null, centroid: null };
      var lons = [];
      var lats = [];
      function walk(node) {
        if (!Array.isArray(node)) return;
        if (node.length >= 2 && typeof node[0] === "number" && typeof node[1] === "number") {
          lons.push(node[0]);
          lats.push(node[1]);
          return;
        }
        for (var i = 0; i < node.length; i++) walk(node[i]);
      }
      walk(geometry.coordinates);
      if (!lons.length || !lats.length) return { bbox: null, centroid: null };
      var minLon = Math.min.apply(null, lons);
      var maxLon = Math.max.apply(null, lons);
      var minLat = Math.min.apply(null, lats);
      var maxLat = Math.max.apply(null, lats);
      return {
        bbox: [
          Number(minLon.toFixed(5)),
          Number(minLat.toFixed(5)),
          Number(maxLon.toFixed(5)),
          Number(maxLat.toFixed(5))
        ],
        centroid: [
          Number(((minLat + maxLat) / 2).toFixed(5)),
          Number(((minLon + maxLon) / 2).toFixed(5))
        ]
      };
    }

    function buildUnifiedConcessionViewModels(inventoryFeatures, dossiersList, dossierBoundaryFeatures, regionId, allowedProvinces) {
      var dList = Array.isArray(dossiersList) ? dossiersList : [];
      var dossierById = {};
      dList.forEach(function (d) {
        if (d && d.id) dossierById[String(d.id)] = d;
      });

      var boundsByDossier = {};
      (Array.isArray(dossierBoundaryFeatures) ? dossierBoundaryFeatures : []).forEach(function (bf) {
        var bp = (bf && bf.properties) || {};
        var did = String(bp.dossierId || "").trim();
        if (did) {
          if (!boundsByDossier[did]) boundsByDossier[did] = [];
          boundsByDossier[did].push(bf);
        }
      });

      var dedupMap = {};
      var dedupOrder = [];
      var matchedDossierIds = {};
      var matchedInventoryKeys = {};
      var rawFeatures = Array.isArray(inventoryFeatures) ? inventoryFeatures : [];

      rawFeatures.forEach(function (feat) {
        if (!feat || typeof feat !== "object") return;
        var props = feat.properties || {};
        var key = String(props.sourceInventoryId || props.inventoryId || (props.sourceDataset + ":" + props.sourceRecordId));
        var vmId = "inv:" + key;
        var provs = parseRecordProvinces(props, allowedProvinces);
        var kabs = parseRecordKabupaten(props);
        var geomMeta = extractGeometryBboxAndCentroid(feat.geometry);
        var explicitDossierId = String(props.dossierId || "").trim();
        var linkedDossier = (explicitDossierId && dossierById[explicitDossierId]) ? dossierById[explicitDossierId] : null;
        var hasDossier = !!linkedDossier;

        if (hasDossier) {
          matchedDossierIds[explicitDossierId] = true;
          matchedInventoryKeys[key] = true;
        }

        if (!featureByViewModelId[vmId]) featureByViewModelId[vmId] = [];
        featureByViewModelId[vmId].push(feat);

        if (dedupMap[key]) {
          var existing = dedupMap[key];
          provs.forEach(function (p) { if (existing.provinces.indexOf(p) === -1) existing.provinces.push(p); });
          kabs.forEach(function (k) { if (existing.kabupaten.indexOf(k) === -1) existing.kabupaten.push(k); });
          if (geomMeta.bbox && existing.bbox) {
            existing.bbox = [
              Math.min(existing.bbox[0], geomMeta.bbox[0]),
              Math.min(existing.bbox[1], geomMeta.bbox[1]),
              Math.max(existing.bbox[2], geomMeta.bbox[2]),
              Math.max(existing.bbox[3], geomMeta.bbox[3])
            ];
          } else if (geomMeta.bbox && !existing.bbox) {
            existing.bbox = geomMeta.bbox;
            existing.centroid = geomMeta.centroid;
            existing.hasGeometry = true;
          }
          return;
        }

        var locParts = [props.location, props.subdistrict, props.district, props.province].map(function (s) {
          return String(s || "").trim();
        }).filter(function (s) { return s && s !== "-"; });
        var locationText = (provs.length || kabs.length)
          ? provs.concat(kabs).join(", ")
          : (locParts.length ? locParts.join(", ") : String(regionId || "indonesia"));

        var permitDate = String(props.permitDate || "").trim() ||
          ((props.validFrom || props.validTo) ? (String(props.validFrom || "—") + " s/d " + String(props.validTo || "—")) : null);
        var areaVal = (props.areaHa != null && isFinite(Number(props.areaHa))) ? Number(props.areaHa) : null;

        var row = {
          viewModelId: vmId,
          recordKind: hasDossier ? "inventory+dossier" : "inventory",
          inventoryId: String(props.inventoryId || key),
          linkedDossierId: hasDossier ? explicitDossierId : null,
          hasInvestigativeDossier: hasDossier,
          matchBasis: hasDossier ? "confirmed_dossier_id" : "none",
          region: String(props.region || regionId || "kalimantan"),
          name: String(props.name || "Tanpa Nama Operator"),
          operator: String((linkedDossier && linkedDossier.name) || props.name || "Tanpa Nama Operator"),
          sector: String(props.sector || (linkedDossier && linkedDossier.sector) || "Lainnya"),
          subtype: String(props.subtype || props.miningType || "Izin Konsesi"),
          quality: String(props.quality || "OFFICIAL").toUpperCase(),
          sourceDataset: String(props.sourceDataset || "inventory"),
          source: String(props.source || "Inventaris Publik"),
          sourceUrl: String(props.sourceUrl || ""),
          retrievedAt: props.retrievedAt ? String(props.retrievedAt) : null,
          permitNumber: props.permitNumber ? String(props.permitNumber).trim() : null,
          permitDate: permitDate,
          issuer: props.issuer ? String(props.issuer).trim() : null,
          commodity: props.commodity ? String(props.commodity).trim() : null,
          status: (props.status || props.legalStatus) ? String(props.status || props.legalStatus).trim() : null,
          group: (linkedDossier && linkedDossier.control && linkedDossier.control.group)
            ? String(linkedDossier.control.group)
            : (props.group ? String(props.group).trim() : null),
          areaHa: areaVal,
          hguAreaHa: (props.hguAreaHa != null && isFinite(Number(props.hguAreaHa))) ? Number(props.hguAreaHa) : null,
          provinces: provs,
          kabupaten: kabs,
          locationText: locationText,
          bbox: geomMeta.bbox,
          centroid: geomMeta.centroid,
          hasGeometry: !!geomMeta.bbox,
          geometryProcessing: props.geometryProcessing ? String(props.geometryProcessing) : null,
          coverageCaveat: props.coverageCaveat ? String(props.coverageCaveat) : null,
          walhiHotspots: (linkedDossier && linkedDossier.walhiHotspots != null) ? Number(linkedDossier.walhiHotspots) : null,
          uboStatus: linkedDossier ? String(linkedDossier.uboStatus || "UNKNOWN") : null
        };
        dedupMap[key] = row;
        dedupOrder.push(row);
        viewModelById[vmId] = row;
      });

      var unmatchedCount = 0;
      dList.forEach(function (d) {
        var did = String(d.id);
        if (matchedDossierIds[did]) return;
        unmatchedCount += 1;
        var vmId = "dossier:" + did;
        var dProvs = parseRecordProvinces(d, allowedProvinces);
        var dKabs = parseRecordKabupaten(d);
        var bFeats = boundsByDossier[did] || [];
        if (bFeats.length) {
          featureByViewModelId[vmId] = bFeats;
        }
        var dBbox = null;
        var dCentroid = null;
        var bQual = "NONE";
        var bSource = "WALHI Kalimantan & OSINT Bernama";
        var bUrl = "";
        bFeats.forEach(function (bf) {
          var gm = extractGeometryBboxAndCentroid(bf.geometry);
          var bp = bf.properties || {};
          if (bp.quality) bQual = String(bp.quality).toUpperCase();
          if (bp.source) bSource = String(bp.source);
          if (bp.sourceUrl) bUrl = String(bp.sourceUrl);
          if (gm.bbox) {
            if (!dBbox) {
              dBbox = gm.bbox;
              dCentroid = gm.centroid;
            } else {
              dBbox = [
                Math.min(dBbox[0], gm.bbox[0]),
                Math.min(dBbox[1], gm.bbox[1]),
                Math.max(dBbox[2], gm.bbox[2]),
                Math.max(dBbox[3], gm.bbox[3])
              ];
            }
          }
        });
        if (!dCentroid && Array.isArray(d.centroid) && d.centroid.length >= 2) {
          dCentroid = [Number(d.centroid[0]), Number(d.centroid[1])];
        }
        if (!bUrl && Array.isArray(d.sources) && d.sources.length) {
          bUrl = String(d.sources[0].url || "");
        }
        var dRow = {
          viewModelId: vmId,
          recordKind: "dossier-only",
          inventoryId: null,
          linkedDossierId: did,
          hasInvestigativeDossier: true,
          matchBasis: "unmatched_curated_dossier",
          region: String(regionId || "kalimantan"),
          name: String(d.name || did),
          operator: String(d.name || did),
          sector: String(d.sector || "Lainnya"),
          subtype: "Dossier Investigasi (Belum Terpetakan di Inventaris Standar)",
          quality: (bQual === "OFFICIAL" || bQual === "GFW" || bQual === "PERKIRAAN") ? bQual : "CURATED_DOSSIER",
          sourceDataset: "walhi-dossiers",
          source: bSource,
          sourceUrl: bUrl,
          retrievedAt: "2026-08-22T00:00:00Z",
          permitNumber: null,
          permitDate: null,
          issuer: null,
          commodity: null,
          status: "Dossier Kurasi Independen",
          group: (d.control && d.control.group) ? String(d.control.group) : null,
          areaHa: null,
          hguAreaHa: null,
          provinces: dProvs,
          kabupaten: dKabs,
          locationText: dProvs.length ? dProvs.join(", ") : String(d.province || regionId || "Kalimantan"),
          bbox: dBbox,
          centroid: dCentroid,
          hasGeometry: !!dBbox,
          geometryProcessing: dBbox ? "Batas poligon dossier kurasi terpisah dari shard inventaris" : "Fallback centroid lokasi kasar",
          coverageCaveat: "Dossier ini tidak memiliki kecocokan ID yang terverifikasi di shard inventaris publik BIG/GFW, sehingga dipertahankan sebagai entri independen tanpa penggabungan paksa.",
          walhiHotspots: d.walhiHotspots != null ? Number(d.walhiHotspots) : null,
          uboStatus: String(d.uboStatus || "UNKNOWN")
        };
        dedupOrder.push(dRow);
        viewModelById[vmId] = dRow;
      });

      var matchedDossierCount = Object.keys(matchedDossierIds).length;
      return {
        region: regionId,
        rows: dedupOrder,
        stats: {
          rawInventoryCount: rawFeatures.length,
          deduplicatedInventoryCount: Object.keys(dedupMap).length,
          matchedDossierCount: matchedDossierCount,
          matchedInventoryRowCount: Object.keys(matchedInventoryKeys).length,
          unmatchedDossierOnlyCount: unmatchedCount,
          totalDossierCount: matchedDossierCount + unmatchedCount,
          totalUnifiedCount: dedupOrder.length
        }
      };
    }

    function indexLoadedInventoryGeoJson(fc, layerUrl) {
      if (!fc || !Array.isArray(fc.features)) return;
      fc.features.forEach(function (feat) {
        if (!feat || typeof feat !== "object") return;
        var props = feat.properties || {};
        if (layerUrl && !props._sourceLayerUrl) props._sourceLayerUrl = layerUrl;
        var did = String(props.dossierId || "").trim();
        if (did && !props.sourceInventoryId && !props.inventoryId && !props.sourceDataset) {
          var dVmId = "dossier:" + did;
          if (!featureByViewModelId[dVmId]) featureByViewModelId[dVmId] = [];
          if (featureByViewModelId[dVmId].indexOf(feat) === -1) {
            featureByViewModelId[dVmId].push(feat);
          }
          return;
        }
        var key = String(props.sourceInventoryId || props.inventoryId || (props.sourceDataset + ":" + props.sourceRecordId));
        var vmId = "inv:" + key;
        if (!featureByViewModelId[vmId]) featureByViewModelId[vmId] = [];
        if (featureByViewModelId[vmId].indexOf(feat) === -1) {
          featureByViewModelId[vmId].push(feat);
        }
      });
    }

    function ensureConcessionGeometryForRow(row) {
      if (!row || !row.hasGeometry) return Promise.resolve([]);
      var existing = featureByViewModelId[row.viewModelId];
      if (existing && existing.length) return Promise.resolve(existing);
      if (row.linkedDossierId && boundaryById && boundaryById[row.linkedDossierId] && boundaryById[row.linkedDossierId].length) {
        featureByViewModelId[row.viewModelId] = boundaryById[row.linkedDossierId];
        return Promise.resolve(featureByViewModelId[row.viewModelId]);
      }
      var urls = Array.isArray(row.layerUrls) && row.layerUrls.length
        ? row.layerUrls
        : [];
      if (!urls.length && row.region && row.sourceDataset) {
        var dsMap = {
          "big-forestry-ha": "forestry-ha.geojson",
          "big-forestry-hti": "forestry-hti.geojson",
          "big-forestry-re": "forestry-re.geojson",
          "big-oil-palm-ihl": "oil-palm-ihl.geojson",
          "gfw-oil-palm": "oil-palm-gfw.geojson",
          "gfw-wood-fiber": "wood-fiber-gfw.geojson",
          "gfw-logging": "logging-gfw.geojson",
          "esdm-mining-wiup": "mining-wiup.geojson"
        };
        if (dsMap[row.sourceDataset]) {
          urls = ["data/concessions/" + row.region + "/inventory/" + dsMap[row.sourceDataset]];
        }
      }
      if (!urls.length) return Promise.resolve([]);
      return Promise.all(urls.map(function (u) {
        return loadConcessionInventoryData({ url: u }).then(function (fc) {
          indexLoadedInventoryGeoJson(fc, u);
          return fc;
        }).catch(function () { return null; });
      })).then(function () {
        return featureByViewModelId[row.viewModelId] || [];
      });
    }

    function ensureRegionalUnifiedConcessionIndex(regionId) {
      if (!regionId || regionId === "indonesia") return Promise.resolve(null);
      if (unifiedConcessionCache[regionId]) return Promise.resolve(unifiedConcessionCache[regionId]);
      if (unifiedConcessionLoading[regionId]) return unifiedConcessionLoading[regionId];

      var indexUrl = "data/concessions/" + regionId + "/inventory/index.json";
      var allowedProvs = (regionById[regionId] && regionById[regionId].provinces) || null;
      var p = loadJson(indexUrl).then(function (idxPayload) {
        if (idxPayload && Array.isArray(idxPayload.rows)) {
          idxPayload.rows.forEach(function (row) {
            if (row && row.viewModelId) {
              viewModelById[row.viewModelId] = row;
            }
          });
          idxPayload.geometryLoaded = false;
          unifiedConcessionCache[regionId] = idxPayload;
          delete unifiedConcessionLoading[regionId];
          return idxPayload;
        }
        throw new Error("Invalid regional concession metadata index payload");
      }).catch(function () {
        // Fallback when lightweight index.json is not present: build from manifest & layers
        return Promise.all([
          loadConcessionInventoryManifest(regionId),
          loadRegionStatic(regionId)
        ]).then(function (pair) {
          var invManifest = pair[0];
          var staticPayload = pair[1] || {};
          var layers = (invManifest && Array.isArray(invManifest.layers)) ? invManifest.layers : [];
          return Promise.all(layers.map(loadConcessionInventoryData)).then(function (layerPayloads) {
            var allFeatures = [];
            layerPayloads.forEach(function (fc) {
              if (fc && Array.isArray(fc.features)) {
                allFeatures = allFeatures.concat(fc.features);
              }
            });
            var dossiersList = (staticPayload.dossiers && Array.isArray(staticPayload.dossiers.dossiers))
              ? staticPayload.dossiers.dossiers
              : (staticPayload.dossier && Array.isArray(staticPayload.dossier.dossiers) ? staticPayload.dossier.dossiers : []);
            var bFeatures = (staticPayload.boundaries && Array.isArray(staticPayload.boundaries.features))
              ? staticPayload.boundaries.features
              : [];
            var built = buildUnifiedConcessionViewModels(
              allFeatures,
              dossiersList,
              bFeatures,
              regionId,
              allowedProvs
            );
            built.manifest = invManifest;
            built.geometryLoaded = true;
            unifiedConcessionCache[regionId] = built;
            delete unifiedConcessionLoading[regionId];
            return built;
          });
        });
      }).catch(function (err) {
        delete unifiedConcessionLoading[regionId];
        console.warn("Failed to build unified concession index for " + regionId, err);
        return null;
      });
      unifiedConcessionLoading[regionId] = p;
      return p;
    }

    function queryUnifiedConcessionViewModels(rows, opts) {
      opts = opts || {};
      var q = String(opts.search != null ? opts.search : (state.search || "")).trim().toLowerCase();
      var sec = String(opts.sector != null ? opts.sector : (state.sector || "")).trim();
      var qual = String(opts.sourceFilter != null ? opts.sourceFilter : (state.concessionSourceFilter || "")).trim().toUpperCase();
      var prov = String(opts.prov != null ? opts.prov : (state.prov || "")).trim();
      var kab = String(opts.kab != null ? opts.kab : (state.kab || "")).trim();
      var party = String(opts.party != null ? opts.party : (state.party || "")).trim();
      var boundary = String(opts.boundary != null ? opts.boundary : (state.boundary || "")).trim();
      var sortBy = String(opts.sortBy != null ? opts.sortBy : (state.concessionSort || "default"));
      var page = Math.max(1, parseInt(opts.page != null ? opts.page : (state.concessionPage || 1), 10) || 1);
      var pageSize = Math.max(1, parseInt(opts.pageSize != null ? opts.pageSize : (state.concessionPageSize || 50), 10) || 50);

      var normProv = prov ? (normalizeProvinceName(prov) || prov) : "";
      var normKab = kab ? (normalizeKabupatenName(kab) || kab) : "";
      var hierarchyMismatch = false;
      if (normProv && normKab && typeof resolveKabupatenProvinceJs === "function") {
        var authParentProv = resolveKabupatenProvinceJs(normKab);
        if (authParentProv && authParentProv !== normProv) {
          hierarchyMismatch = true;
        }
      }

      var filtered = hierarchyMismatch ? [] : (Array.isArray(rows) ? rows : []).filter(function (row) {
        if (sec && row.sector !== sec) return false;
        if (qual) {
          if (qual === "DOSSIER") {
            if (!row.hasInvestigativeDossier) return false;
          } else if (qual === "UNMATCHED_DOSSIER") {
            if (row.recordKind !== "dossier-only") return false;
          } else if (qual === "OFFICIAL") {
            if (String(row.quality || "").toUpperCase() !== "OFFICIAL") return false;
          } else if (qual === "GFW" || qual === "ESTIMATED") {
            var rq = String(row.quality || "").toUpperCase();
            if (rq !== "GFW" && rq !== "PERKIRAAN") return false;
          }
        }
        if (normProv) {
          var rProvs = row.provinces || [];
          if (rProvs.indexOf(normProv) === -1) return false;
        }
        if (normKab) {
          var rKabs = row.kabupaten || [];
          if (rKabs.indexOf(normKab) === -1) return false;
        }
        if (party) {
          if (!row.hasInvestigativeDossier || !row.linkedDossierId) return false;
          var dObj = dossiers.find(function (x) { return x.id === row.linkedDossierId; });
          if (!dObj || !matchesParty(dObj, party)) return false;
        }
        if (boundary) {
          if (boundary === "none") {
            if (row.hasGeometry) return false;
          } else if (String(row.quality || "").toUpperCase() !== boundary) {
            return false;
          }
        }
        if (q) {
          var blob = [
            row.name,
            row.operator,
            row.permitNumber,
            row.commodity,
            row.group,
            row.subtype,
            row.locationText,
            (row.provinces || []).join(" "),
            (row.kabupaten || []).join(" "),
            row.sourceDataset,
            row.linkedDossierId,
            row.viewModelId
          ].join(" ").toLowerCase();
          if (blob.indexOf(q) === -1) return false;
        }
        return true;
      });

      filtered.sort(function (a, b) {
        var nameA = String(a.name || "").toUpperCase();
        var nameB = String(b.name || "").toUpperCase();
        var areaA = (a.areaHa != null && isFinite(a.areaHa)) ? Number(a.areaHa) : null;
        var areaB = (b.areaHa != null && isFinite(b.areaHa)) ? Number(b.areaHa) : null;
        if (sortBy === "name_asc") {
          return nameA.localeCompare(nameB) || String(a.viewModelId).localeCompare(String(b.viewModelId));
        }
        if (sortBy === "area_desc") {
          if (areaA === null && areaB !== null) return 1;
          if (areaA !== null && areaB === null) return -1;
          if (areaA !== null && areaB !== null && areaB !== areaA) return areaB - areaA;
          return nameA.localeCompare(nameB);
        }
        if (sortBy === "area_asc") {
          if (areaA === null && areaB !== null) return 1;
          if (areaA !== null && areaB === null) return -1;
          if (areaA !== null && areaB !== null && areaA !== areaB) return areaA - areaB;
          return nameA.localeCompare(nameB);
        }
        if (sortBy === "sector_asc") {
          return String(a.sector || "").localeCompare(String(b.sector || "")) || nameA.localeCompare(nameB);
        }
        var dosA = a.hasInvestigativeDossier ? 0 : 1;
        var dosB = b.hasInvestigativeDossier ? 0 : 1;
        if (dosA !== dosB) return dosA - dosB;
        if (areaA === null && areaB !== null) return 1;
        if (areaA !== null && areaB === null) return -1;
        if (areaA !== null && areaB !== null && areaB !== areaA) return areaB - areaA;
        return nameA.localeCompare(nameB) || String(a.viewModelId).localeCompare(String(b.viewModelId));
      });

      var total = filtered.length;
      var totalPages = Math.max(1, Math.ceil(total / pageSize));
      var safePage = Math.min(Math.max(1, page), totalPages);
      var start = (safePage - 1) * pageSize;
      var end = start + pageSize;
      return {
        items: filtered.slice(start, end),
        allFiltered: filtered,
        totalFiltered: total,
        page: safePage,
        pageSize: pageSize,
        totalPages: totalPages,
        startIndex: total > 0 ? (start + 1) : 0,
        endIndex: Math.min(end, total)
      };
    }

    function activeUnifiedConcessionPool() {
      if (state.region !== "indonesia" && unifiedConcessionCache[state.region]) {
        return unifiedConcessionCache[state.region];
      }
      if (state.region === "indonesia" && unifiedConcessionCache["__indonesia__"]) {
        return unifiedConcessionCache["__indonesia__"];
      }
      var allowedProvs = (state.region !== "indonesia" && regionById[state.region])
        ? regionById[state.region].provinces
        : null;
      var fallbackBounds = [];
      Object.keys(boundaryById || {}).forEach(function (did) {
        fallbackBounds = fallbackBounds.concat(boundaryById[did] || []);
      });
      return buildUnifiedConcessionViewModels([], dossiers, fallbackBounds, state.region, allowedProvs);
    }

    function renderFocusedConcessionOnMap(row) {
      if (typeof focusedConcessionLayer !== "undefined" && focusedConcessionLayer) {
        focusedConcessionLayer.clearLayers();
      }
      var bar = document.getElementById("focused-concession-bar");
      var nameEl = document.getElementById("focused-concession-name");
      if (!row) {
        if (bar) bar.classList.remove("visible");
        return;
      }
      if (bar && nameEl) {
        nameEl.textContent = row.name + " (" + row.sector + ")";
        bar.classList.add("visible");
      }
      var feats = featureByViewModelId[row.viewModelId] ||
        (row.linkedDossierId ? (boundaryById[row.linkedDossierId] || []) : []);
      if (feats && feats.length && typeof focusedConcessionLayer !== "undefined" && focusedConcessionLayer) {
        var gj = L.geoJSON({ type: "FeatureCollection", features: feats }, {
          style: function () {
            return {
              color: "#ffffff",
              weight: 2.5,
              opacity: 1,
              fillColor: "#e3a008",
              fillOpacity: 0.30
            };
          }
        });
        focusedConcessionLayer.addLayer(gj);
      } else {
        if (row.centroid && typeof focusedConcessionLayer !== "undefined" && focusedConcessionLayer) {
          var cm = L.circleMarker(row.centroid, {
            radius: 9,
            color: "#ffffff",
            weight: 2,
            fillColor: "#e3a008",
            fillOpacity: 0.85
          });
          focusedConcessionLayer.addLayer(cm);
        }
        if (row.hasGeometry && (state.view === "map" || state.inspectorTab === "map")) {
          ensureConcessionGeometryForRow(row).then(function (loadedFeats) {
            if (state.selectedViewModelId === row.viewModelId && loadedFeats && loadedFeats.length && typeof focusedConcessionLayer !== "undefined" && focusedConcessionLayer) {
              focusedConcessionLayer.clearLayers();
              var gjLazy = L.geoJSON({ type: "FeatureCollection", features: loadedFeats }, {
                style: function () {
                  return {
                    color: "#ffffff",
                    weight: 2.5,
                    opacity: 1,
                    fillColor: "#e3a008",
                    fillOpacity: 0.30
                  };
                }
              });
              focusedConcessionLayer.addLayer(gjLazy);
            }
          });
        }
      }
    }

    function zoomToConcessionViewModel(row) {
      if (!row || !map) return;
      if (row.bbox && row.bbox.length === 4) {
        var b = L.latLngBounds([row.bbox[1], row.bbox[0]], [row.bbox[3], row.bbox[2]]);
        if (b.isValid()) {
          map.fitBounds(b.pad(0.18), { maxZoom: 12, animate: true });
          return;
        }
      }
      if (row.centroid && row.centroid.length >= 2) {
        map.flyTo(row.centroid, 9, { duration: 0.5 });
      }
    }

    function showUnifiedConcessionDetail(viewModelId, preferredTab) {
      var row = viewModelById[viewModelId];
      if (!row) return;
      state.selectedViewModelId = viewModelId;
      state.selectedId = row.linkedDossierId || row.inventoryId || viewModelId;
      state.selectedType = row.hasInvestigativeDossier ? "company" : "inventory";

      var linkedDossier = row.linkedDossierId
        ? (dossiers.find(function (x) { return x.id === row.linkedDossierId; }) || null)
        : null;
      var hasDossier = !!(row.hasInvestigativeDossier && linkedDossier);

      var activeTab = preferredTab || state.inspectorTab || "summary";
      if (activeTab === "investigation" && !hasDossier) {
        activeTab = "summary";
      }
      state.inspectorTab = activeTab;

      renderFocusedConcessionOnMap(row);
      renderList();

      var pool = activeUnifiedConcessionPool();
      var qRes = queryUnifiedConcessionViewModels(pool.rows);
      var returnLabel = "← Kembali ke Daftar (" + qRes.totalFiltered.toLocaleString("id-ID") + " konsesi · Hal. " + qRes.page + ")";

      var qualityBadgeClass = row.quality === "OFFICIAL" ? "official" : (row.recordKind === "dossier-only" ? "dossier-only" : "gfw");
      var qualityLabel = row.quality === "OFFICIAL" ? "OFFICIAL · BIG" : (row.recordKind === "dossier-only" ? "CURATED · INVESTIGATIVE" : "ESTIMATED · " + row.quality);
      var dossierBadgeHtml = hasDossier
        ? '<span class="vm-badge dossier-linked">' + (row.recordKind === "dossier-only" ? "DOSSIER INDEPENDEN (CURATED · INVESTIGATIVE)" : "DOSSIER INVESTIGASI TERSEDIA") + '</span>'
        : '<span class="vm-badge">INVENTARIS GENERIK · TANPA KLAIM ATRIBUSI</span>';

      var tabsHtml =
        '<div class="inspector-tabs" id="inspector-tabs" role="tablist" aria-label="Tab detail konsesi">' +
          '<button type="button" role="tab" class="insp-tab-btn' + (activeTab === "summary" ? " active" : "") + '" id="insp-tab-summary" data-insp-tab="summary" aria-selected="' + (activeTab === "summary" ? "true" : "false") + '">1 · Ringkasan</button>' +
          '<button type="button" role="tab" class="insp-tab-btn' + (activeTab === "map" ? " active" : "") + '" id="insp-tab-map" data-insp-tab="map" aria-selected="' + (activeTab === "map" ? "true" : "false") + '">2 · Peta &amp; Geometri</button>' +
          (hasDossier
            ? '<button type="button" role="tab" class="insp-tab-btn' + (activeTab === "investigation" ? " active" : "") + '" id="insp-tab-investigation" data-insp-tab="investigation" aria-selected="' + (activeTab === "investigation" ? "true" : "false") + '">3 · Investigasi &amp; Bukti</button>'
            : '') +
        '</div>';

      var paneHtml = "";
      if (activeTab === "summary") {
        var areaText = (row.areaHa != null && isFinite(row.areaHa))
          ? row.areaHa.toLocaleString("id-ID", { maximumFractionDigits: 2 }) + " ha"
          : "Luas geometri tidak tersedia di atribut sumber";
        var sourceLink = row.sourceUrl
          ? '<a href="' + escapeHtml(row.sourceUrl) + '" target="_blank" rel="noopener">' + escapeHtml(row.source) + ' ↗</a>'
          : escapeHtml(row.source || "Sumber tidak tercantum");

        paneHtml =
          '<div id="insp-pane-summary" role="tabpanel">' +
            '<div class="summary-grid">' +
              '<div class="summary-card"><span class="label">Sektor &amp; Jenis Izin</span><strong>' + escapeHtml(row.sector) + '</strong><small>' + escapeHtml(row.subtype) + '</small></div>' +
              '<div class="summary-card"><span class="label">Luas Tercantum</span><strong>' + escapeHtml(areaText) + '</strong><small>' + escapeHtml(qualityLabel) + '</small></div>' +
              '<div class="summary-card"><span class="label">Lokasi Administratif</span><strong>' + escapeHtml(row.locationText || row.region) + '</strong><small>Wilayah: ' + escapeHtml(row.region) + '</small></div>' +
              '<div class="summary-card"><span class="label">Status Bukti</span><strong>' + (hasDossier ? "Dossier Terhubung" : "Inventaris Publik") + '</strong><small>' + (hasDossier ? ("ID Dossier: " + escapeHtml(row.linkedDossierId)) : "Tanpa tuduhan otomatis") + '</small></div>' +
            '</div>' +
            '<details class="details-section" open><summary>Metadata Izin &amp; Provenance Sumber</summary><div class="section-content"><dl class="kv">' +
              '<dt>ID ViewModel</dt><dd class="mono">' + escapeHtml(row.viewModelId) + '</dd>' +
              '<dt>Operator / Nama</dt><dd>' + escapeHtml(row.operator || row.name) + '</dd>' +
              '<dt>Nomor Izin / SK</dt><dd>' + escapeHtml(row.permitNumber || "Tidak tercantum di sumber") + '</dd>' +
              '<dt>Tanggal / Masa Berlaku</dt><dd>' + escapeHtml(row.permitDate || "Tidak tercantum di sumber") + '</dd>' +
              '<dt>Penerbit Izin</dt><dd>' + escapeHtml(row.issuer || "Tidak tercantum di sumber") + '</dd>' +
              (row.commodity ? '<dt>Komoditas</dt><dd>' + escapeHtml(row.commodity) + '</dd>' : '') +
              (row.status ? '<dt>Status Izin</dt><dd>' + escapeHtml(row.status) + '</dd>' : '') +
              (row.group ? '<dt>Grup Tercantum</dt><dd>' + escapeHtml(row.group) + '</dd>' : '') +
              '<dt>Provinsi (Normalisasi)</dt><dd>' + escapeHtml((row.provinces || []).join(", ") || "Tidak dipetakan ke provinsi spesifik") + '</dd>' +
              '<dt>Kabupaten/Kota</dt><dd>' + escapeHtml((row.kabupaten || []).join(", ") || "Tidak dipetakan ke kabupaten spesifik") + '</dd>' +
              '<dt>Sumber Data</dt><dd>' + sourceLink + '</dd>' +
              '<dt>Diambil Pada (UTC)</dt><dd>' + escapeHtml(row.retrievedAt || "—") + '</dd>' +
            '</dl></div></details>' +
            (row.coverageCaveat ? '<div class="caveat">' + escapeHtml(row.coverageCaveat) + '</div>' : '') +
            '<div class="caveat"><strong>NO FIRE ATTRIBUTION · BATAS BUKTI</strong><br/>Kehadiran titik panas satelit NASA FIRMS di dalam atau di sekitar batas konsesi adalah konteks spasial semata, bukan bukti penyebab kebakaran atau pelanggaran hukum.</div>' +
          '</div>';
      } else if (activeTab === "map") {
        var featsForContext = featureByViewModelId[row.viewModelId] ||
          (row.linkedDossierId ? (boundaryById[row.linkedDossierId] || []) : []);
        if (row.hasGeometry && (!featsForContext || !featsForContext.length) && !row._geomLoading) {
          row._geomLoading = true;
          ensureConcessionGeometryForRow(row).then(function () {
            row._geomLoading = false;
            if (state.selectedViewModelId === viewModelId && state.inspectorTab === "map") {
              showUnifiedConcessionDetail(viewModelId, "map");
            }
          });
        }
        var insideCount = 0;
        var nearCount = 0;
        var activePts = firmsForView();
        if (featsForContext && featsForContext.length && activePts.length) {
          activePts.forEach(function (pt) {
            var isIn = featsForContext.some(function (f) { return pointInBoundaryGeometry(pt.lon, pt.lat, f.geometry); });
            if (isIn) {
              insideCount += 1;
            } else {
              var minDist = Infinity;
              featsForContext.forEach(function (f) {
                var dKm = boundaryGeometryDistanceKm(pt.lat, pt.lon, f.geometry);
                if (dKm < minDist) minDist = dKm;
              });
              if (minDist <= 5.0) nearCount += 1;
            }
          });
        }
        var geomExplain = row.hasGeometry
          ? ("Poligon tersedia (" + escapeHtml(row.geometryProcessing || "disederhanakan untuk tampilan web") + "). Bounding box: [" + row.bbox.join(", ") + "].")
          : "Geometri poligon TIDAK TERSEDIA untuk entri ini pada shard inventaris; peta menggunakan titik centroid lokasi kasar.";

        paneHtml =
          '<div id="insp-pane-map" role="tabpanel">' +
            '<div class="caveat" style="border-color:var(--amber)"><strong>Status Geometri: ' + (row.hasGeometry ? "POLIGON TERSEDIA" : "TANPA POLIGON (CENTROID FALLBACK)") + '</strong><br/>' + geomExplain + '</div>' +
            '<div class="insp-action-row">' +
              '<button type="button" class="insp-action-btn primary" id="btn-inspector-focus-map">Fokus &amp; Zoom Poligon di Peta</button>' +
              '<button type="button" class="insp-action-btn" id="btn-inspector-clear-focus">Hapus Fokus Peta</button>' +
            '</div>' +
            '<details class="details-section" open><summary>Konteks Spasial Observasi NASA FIRMS (' + escapeHtml(currentDate() || "tanggal terpilih") + ')</summary><div class="section-content">' +
              '<label style="display:flex;align-items:center;gap:6px;font-size:12px;margin-bottom:8px;cursor:pointer">' +
                '<input type="checkbox" id="tog-inspector-firms-context" ' + (state.showFirms ? "checked" : "") + ' /> Tampilkan overlay titik panas FIRMS pada peta untuk periode terpilih' +
              '</label>' +
              (row.hasGeometry
                ? ('<div class="summary-grid">' +
                    '<div class="summary-card"><span class="label">Di Dalam Poligon</span><strong>' + insideCount.toLocaleString("id-ID") + '</strong><small>titik panas (' + escapeHtml(currentDate() || "—") + ')</small></div>' +
                    '<div class="summary-card"><span class="label">Dekat Batas (≤5 km)</span><strong>' + nearCount.toLocaleString("id-ID") + '</strong><small>titik panas sekitar</small></div>' +
                  '</div>')
                : '<div class="insp-empty">Perhitungan irisan poligon memerlukan geometri batas (tidak dihitung dari centroid kasar).</div>') +
              '<p style="font-size:11px;color:var(--muted);margin:8px 0 0;line-height:1.4">Catatan netral: Irisan spasial menunjukkan lokasi pengamatan termal satelit pada tanggal terpilih dan tidak membuktikan asal api atau tanggung jawab hukum.</p>' +
            '</div></details>' +
          '</div>';
      } else if (activeTab === "investigation" && hasDossier) {
        var controls = linkedDossier.control || {};
        var personsData = controls.persons || [];
        var personById = {};
        personsData.forEach(function (p) { personById[p.id] = p; });
        var tiesData = linkedDossier.politicalTies || [];
        var uboLabel = linkedDossier.uboStatus === "UNKNOWN" ? "UBO UNKNOWN" : linkedDossier.uboStatus === "CAVEAT" ? "UBO CAVEAT" : "UBO TERKUNCI";
        var period = (walhi && walhi.period) ? walhi.period : "1 Jan – 27 Jul 2026";

        var personsHtml = personsData.map(function (p) {
          return '<div class="tie-card"><strong>' + escapeHtml(p.name) + '</strong><br/><span class="tie-meta">' + escapeHtml(p.role || "peran tidak dinyatakan") + '</span></div>';
        }).join("") || '<div class="insp-empty">Tidak ada person yang dikunci.</div>';

        var tiesHtml = tiesData.map(function (t) {
          var actor = personById[t.personId];
          var sourceHtml = renderSourceLinks(linkedDossier, t.sources);
          return '<div class="tie-card">' +
            '<strong>Actor</strong> · ' + escapeHtml(actor ? actor.name : (t.personId || "Tidak dinyatakan")) +
            '<div class="tie-meta">' + escapeHtml(t.type || "relationship tidak dinyatakan") + ' · Periode: ' + escapeHtml(t.period || "periode tidak dinyatakan") + ' · confidence ' + escapeHtml(t.confidence || "tidak dinyatakan") + '</div>' +
            '<div>' + escapeHtml(t.detail || "Tidak ada ringkasan detail.") + '</div>' +
            '<div class="tie-meta">Kutipan Sumber: ' + sourceHtml + '</div>' +
            '</div>';
        }).join("") || '<div class="insp-empty">Political tie: TIDAK TERPETAKAN.</div>';

        var cavesHtml = (linkedDossier.caveats || []).map(function (c) {
          return '<div class="caveat">' + escapeHtml(c) + '</div>';
        }).join("");

        paneHtml =
          '<div id="insp-pane-investigation" role="tabpanel">' +
            '<div class="summary-grid">' +
              '<div class="summary-card claim"><span class="label">Klaim WALHI (ConcessionClaim)</span><strong>' + linkedDossier.walhiHotspots.toLocaleString("id-ID") + '</strong><small>reported hotspots · ' + escapeHtml(period) + '</small></div>' +
              '<div class="summary-card"><span class="label">Kontrol &amp; UBO (Control)</span><strong>' + escapeHtml(controls.group || "Tidak terpetakan") + '</strong><small>' + escapeHtml(uboLabel) + '</small></div>' +
            '</div>' +
            '<div class="caveat" style="border-color:var(--amber)"><strong>Basis Pencocokan Dossier (#12):</strong> ' +
              (row.recordKind === "dossier-only"
                ? "Dossier kurasi independen (belum memiliki padanan ID terverifikasi pada shard inventaris BIG/GFW)."
                : ("Terhubung melalui ID terverifikasi ke rekor inventaris " + escapeHtml(row.inventoryId) + ".")) +
            '</div>' +
            '<details class="details-section" open><summary>Kontrol Korporasi &amp; UBO</summary><div class="section-content"><p style="margin:0 0 8px;font-size:13px;line-height:1.4">' + escapeHtml(controls.summary || "Ringkasan kontrol belum tersedia.") + '</p>' + personsHtml + '</div></details>' +
            '<details class="details-section" open><summary>Ikatan Politik Terdokumentasi (' + tiesData.length + ')</summary><div class="section-content">' + tiesHtml + '</div></details>' +
            '<details class="details-section" open><summary>Kutipan Sumber Bernama (' + (linkedDossier.sources || []).length + ')</summary><div class="section-content">' + renderSources(linkedDossier) + '</div></details>' +
            '<details class="details-section"><summary>Caveats Metodologi (' + (linkedDossier.caveats || []).length + ')</summary><div class="section-content">' + cavesHtml + '</div></details>' +
          '</div>';
      }

      elInsp.innerHTML =
        '<div class="inspector-return-bar" id="inspector-return-bar">' +
          '<button type="button" class="btn-return-list" id="btn-return-to-list">' + escapeHtml(returnLabel) + '</button>' +
        '</div>' +
        '<div class="insp-title">' + escapeHtml(row.name) + '</div>' +
        '<div class="insp-subtitle">' + escapeHtml(row.sector) + ' · ' + escapeHtml(row.locationText || row.region) + '</div>' +
        '<div class="vm-badges"><span class="vm-badge ' + qualityBadgeClass + '">' + escapeHtml(qualityLabel) + '</span>' + dossierBadgeHtml + '</div>' +
        tabsHtml +
        paneHtml;

      var returnBtn = document.getElementById("btn-return-to-list");
      if (returnBtn) {
        returnBtn.addEventListener("click", function () {
          closeMobileInspector();
          if (state.view !== "concessions" && state.view !== "map") {
            setView("concessions");
          }
          var searchEl = document.getElementById("search");
          if (searchEl) searchEl.focus();
        });
      }

      elInsp.querySelectorAll("button[data-insp-tab]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          showUnifiedConcessionDetail(viewModelId, btn.getAttribute("data-insp-tab"));
        });
      });

      var focusBtn = document.getElementById("btn-inspector-focus-map");
      if (focusBtn) {
        focusBtn.addEventListener("click", function () {
          if (state.view !== "map") setView("map");
          renderFocusedConcessionOnMap(row);
          zoomToConcessionViewModel(row);
        });
      }

      var clearBtn = document.getElementById("btn-inspector-clear-focus");
      if (clearBtn) {
        clearBtn.addEventListener("click", function () {
          renderFocusedConcessionOnMap(null);
        });
      }

      var firmsCtxToggle = document.getElementById("tog-inspector-firms-context");
      if (firmsCtxToggle) {
        firmsCtxToggle.addEventListener("change", function (e) {
          state.showFirms = !!e.target.checked;
          var mapFirmsTog = document.getElementById("tog-map-firms");
          if (mapFirmsTog) mapFirmsTog.checked = state.showFirms;
          refreshFirmsLayer();
        });
      }

      openMobileInspector();
    }
"""


def build_patched_index(source: str) -> str:
    use_crlf = "\r\n" in source
    text = source.replace("\r\n", "\n")

    if "function buildUnifiedConcessionViewModels(" in text:
        return source
    if "function setView(viewName, skipUrlSync)" not in text:
        raise RuntimeError(
            "patch_v2_concessions_map_dashboard.py must run after patch_v2_foundation_dashboard.py"
        )

    # 1. Inject Wave 2 CSS
    text = replace_once(text, "  </style>", V2_WAVE2_CSS + "\n  </style>", "v2 wave2 CSS")

    # 2. Update Browser panel header and inject Unified Explorer controls + pagination (#12, #13, #15)
    text = replace_once(
        text,
        '        <div class="panel-h" id="sheet-toggle" role="button" tabindex="0" aria-expanded="true">\n'
        '          <span>Browser · Dossier</span>\n'
        '          <span class="sheet-label">12 dossier</span>\n'
        '        </div>',
        '        <div class="panel-h" id="sheet-toggle" role="button" tabindex="0" aria-expanded="true">\n'
        '          <span id="explorer-title">Eksplorer Konsesi &amp; Dossier</span>\n'
        '          <span class="sheet-label" id="explorer-sheet-label">Memuat…</span>\n'
        '        </div>',
        "v2 explorer header",
    )

    text = replace_once(
        text,
        '          <input class="search" id="search" type="search" placeholder="Cari perusahaan, orang, partai, ID…" autocomplete="off" />',
        '          <input class="search" id="search" type="search" placeholder="Cari operator, nomor SK/izin, komoditas, kabupaten, ID…" autocomplete="off" />\n'
        + V2_EXPLORER_CONTROLS_HTML,
        "v2 explorer controls",
    )

    # Default #tog-regions to unchecked (#15 minimal default map) and add pagination below #obj-list
    old_toggles_and_list = (
        '          <div class="layer-toggles" aria-label="Lapisan peta">\n'
        '            <label><input type="checkbox" id="tog-regions" checked /> Boundary dossier</label>\n'
        '            <label><input type="checkbox" id="tog-inventory" /> Inventaris semua konsesi</label>\n'
        '            <label><input type="checkbox" id="tog-centroids" /> Tampilkan semua centroid</label>\n'
        '          </div>\n\n'
        '          <div class="dossier-count"><span>Filtered dossiers</span><strong id="dossier-count">—</strong></div>\n'
        '          <ul class="obj-list" id="obj-list"></ul>'
    )
    new_toggles_and_list = (
        '          <div class="layer-toggles" aria-label="Lapisan peta">\n'
        '            <label><input type="checkbox" id="tog-regions" /> Boundary dossier</label>\n'
        '            <label><input type="checkbox" id="tog-inventory" /> Inventaris semua konsesi</label>\n'
        '            <label><input type="checkbox" id="tog-centroids" /> Tampilkan semua centroid</label>\n'
        '          </div>\n\n'
        '          <div class="dossier-count"><span>Konsesi &amp; Dossier Terfilter</span><strong id="dossier-count">—</strong></div>\n'
        '          <ul class="obj-list" id="obj-list"></ul>\n'
        '          <div class="concession-pagination" id="concession-pagination" aria-label="Navigasi halaman konsesi">\n'
        '            <button type="button" id="btn-page-prev" disabled>← Sebelumnya</button>\n'
        '            <span id="concession-page-info">Hal. 1 / 1</span>\n'
        '            <button type="button" id="btn-page-next" disabled>Berikutnya →</button>\n'
        '          </div>'
    )
    text = replace_once(text, old_toggles_and_list, new_toggles_and_list, "v2 toggles and pagination")

    # 3. Inject Compact Map Layer Control, Focused Concession Bar, and updated Legend (#15)
    old_legend = (
        '        <div class="legend" id="map-legend">\n'
        '          <div><span class="fire-dot"></span>FIRMS satellite detection</div>\n'
        '          <div><span class="boundary-official"></span>OFFICIAL boundary</div>\n'
        '          <div><span class="boundary-gfw"></span>GFW boundary</div>\n'
        '          <div><span class="boundary-approx"></span>PERKIRAAN boundary</div>\n'
        '          <div><span class="estimated-land"></span>PERKIRAAN LUAS IZIN · bukan batas legal</div>\n'
        '          <div><span class="boundary-none"></span>Location only / no boundary</div>\n'
        '        </div>'
    )
    new_legend = (
        V2_MAP_LAYER_CONTROL_HTML
        + '\n        <div class="legend" id="map-legend">\n'
        '          <div><span class="fire-dot"></span>Deteksi panas satelit FIRMS (≠ area terbakar)</div>\n'
        '          <div><span class="boundary-official"></span>Poligon Konsesi OFFICIAL (BIG)</div>\n'
        '          <div><span class="boundary-gfw"></span>Poligon Indikatif ESTIMATED (GFW)</div>\n'
        '          <div><span class="boundary-approx"></span>Fokus Konsesi / Dossier Terpilih</div>\n'
        '          <div><span class="boundary-none"></span>Burned Area: DATA UNAVAILABLE</div>\n'
        '        </div>'
    )
    text = replace_once(text, old_legend, new_legend, "v2 map layer control and legend")

    # 4. Update state defaults (#15: showRegions: false, plus unified explorer & layer flags)
    text = replace_once(
        text,
        '      showRegions: true,\n      showCentroids: false,',
        '      showFirms: true,\n      showBurnedArea: false,\n      showAdminBoundaries: true,\n      showRegions: false,\n      showCentroids: false,\n      concessionSourceFilter: "",\n      concessionSort: "default",\n      concessionPage: 1,\n      concessionPageSize: 50,\n      selectedViewModelId: null,\n      inspectorTab: "summary",',
        "v2 state wave2 fields",
    )

    # 5. Add focusedConcessionLayer and adminBoundaryOutlineLayer to Leaflet map
    text = replace_once(
        text,
        "    var regionLayersById = {};",
        "    var regionLayersById = {};\n    var focusedConcessionLayer = L.layerGroup().addTo(map);\n    var adminBoundaryOutlineLayer = L.layerGroup().addTo(map);",
        "v2 focusedConcessionLayer",
    )

    # 6. Inject Wave 2 JS helpers before applyStaticPayload
    text = replace_once(
        text,
        "    function applyStaticPayload(payload) {",
        V2_WAVE2_JS + "\n    function applyStaticPayload(payload) {",
        "v2 wave2 JS helpers",
    )

    # 7. Upgrade renderList() to render the unified ConcessionViewModel explorer with pagination (#12, #13)
    old_render_list = (
        '    function renderList() {\n'
        '      var items = filteredDossiers();\n'
        '      elDossierCount.textContent = items.length + " / " + dossiers.length;\n'
        '      if (elSheetLabel) elSheetLabel.textContent = items.length + " dossier" + (items.length === 1 ? "" : "s");\n'
        '      elList.innerHTML = items.map(function (d) {\n'
        '        var sel = state.selectedId === d.id && state.selectedType === "company" ? " selected" : "";\n'
        '        var b = boundaryStatus(d);\n'
        '        return (\n'
        '          \'<li class="\' + sel + \'" data-id="\' + d.id + \'">\' +\n'
        '            \'<div><div class="name">\' + escapeHtml(d.name) + \'</div>\' +\n'
        '            \'<div class="meta">\' + escapeHtml(d.sector) + " · " + escapeHtml(d.province) +\n'
        '            \'<br/><span class="boundary-status \' + b.key + \'">\' + escapeHtml(b.label) + "</span>" +\n'
        '            "</div></div>" +\n'
        '            \'<div class="hot"><span class="claim-label">WALHI claim</span>\' + d.walhiHotspots.toLocaleString("id-ID") + "</div>" +\n'
        '          "</li>"\n'
        '        );\n'
        '      }).join("");\n'
        '    }'
    )
    new_render_list = r"""    function renderList() {
      var headlineEl = document.getElementById("concession-count-headline");
      var pageInfoEl = document.getElementById("concession-page-info");
      var prevBtn = document.getElementById("btn-page-prev");
      var nextBtn = document.getElementById("btn-page-next");

      if (state.region !== "indonesia" && !unifiedConcessionCache[state.region]) {
        if (headlineEl) {
          headlineEl.innerHTML = 'Memuat indeks konsesi wilayah <strong>' + escapeHtml((regionById[state.region] && regionById[state.region].label) || state.region) + '</strong>…';
        }
        ensureRegionalUnifiedConcessionIndex(state.region).then(function () {
          renderList();
        });
      }

      var pool = activeUnifiedConcessionPool();
      var qRes = queryUnifiedConcessionViewModels(pool.rows);
      state.concessionPage = qRes.page;

      elDossierCount.textContent = qRes.totalFiltered.toLocaleString("id-ID") + " / " + pool.stats.totalUnifiedCount.toLocaleString("id-ID");
      if (elSheetLabel) {
        elSheetLabel.textContent = qRes.totalFiltered.toLocaleString("id-ID") + " konsesi";
      }

      if (headlineEl) {
        if (state.region === "indonesia" && !unifiedConcessionCache["__indonesia__"]) {
          var natDedup = (adminIndex && adminIndex.nationalConcessions) ? adminIndex.nationalConcessions.deduplicatedCount : 7265;
          var natRaw = (adminIndex && adminIndex.nationalConcessions) ? adminIndex.nationalConcessions.rawCount : 7265;
          headlineEl.innerHTML =
            'Menampilkan <strong>' + qRes.totalFiltered.toLocaleString("id-ID") + '</strong> dossier kurasi nasional · ' +
            'Tersedia <strong>' + Number(natDedup).toLocaleString("id-ID") + '</strong> konsesi terdeduplikasi (' + Number(natRaw).toLocaleString("id-ID") + ' rekor sumber) di 7 wilayah. ' +
            '<button type="button" class="filter-reset-btn" id="btn-load-national-concessions" style="margin-top:4px">Muat Semua ' + Number(natDedup).toLocaleString("id-ID") + ' Konsesi Nasional</button>';
          var loadNatBtn = document.getElementById("btn-load-national-concessions");
          if (loadNatBtn) {
            loadNatBtn.addEventListener("click", function () {
              loadNatBtn.disabled = true;
              loadNatBtn.textContent = "Memuat 7 wilayah…";
              Promise.all(regions.map(function (r) { return ensureRegionalUnifiedConcessionIndex(r.id); })).then(function (results) {
                var combinedRows = [];
                var rawSum = 0;
                var dedupSum = 0;
                var matchedDos = 0;
                var unmatchedDos = 0;
                results.forEach(function (res) {
                  if (!res) return;
                  combinedRows = combinedRows.concat(res.rows || []);
                  rawSum += res.stats.rawInventoryCount || 0;
                  dedupSum += res.stats.deduplicatedInventoryCount || 0;
                  matchedDos += res.stats.matchedDossierCount || 0;
                  unmatchedDos += res.stats.unmatchedDossierOnlyCount || 0;
                });
                unifiedConcessionCache["__indonesia__"] = {
                  region: "indonesia",
                  rows: combinedRows,
                  stats: {
                    rawInventoryCount: rawSum,
                    deduplicatedInventoryCount: dedupSum,
                    matchedDossierCount: matchedDos,
                    unmatchedDossierOnlyCount: unmatchedDos,
                    totalUnifiedCount: combinedRows.length
                  }
                };
                state.concessionPage = 1;
                renderList();
              });
            });
          }
        } else {
          headlineEl.innerHTML =
            'Menampilkan <strong>' + qRes.startIndex.toLocaleString("id-ID") + '–' + qRes.endIndex.toLocaleString("id-ID") + '</strong> dari <strong>' + qRes.totalFiltered.toLocaleString("id-ID") + '</strong> konsesi terfilter · ' +
            'Total wilayah: <strong>' + pool.stats.deduplicatedInventoryCount.toLocaleString("id-ID") + '</strong> izin terdeduplikasi (dari ' + pool.stats.rawInventoryCount.toLocaleString("id-ID") + ' rekor sumber)' +
            (pool.stats.totalDossierCount
              ? (' + <strong>' + pool.stats.unmatchedDossierOnlyCount + '</strong> dossier independen (' + pool.stats.matchedDossierCount + ' dossier cocok dengan izin inventaris).')
              : '.');
        }
      }

      if (pageInfoEl) {
        pageInfoEl.textContent = "Hal. " + qRes.page + " / " + qRes.totalPages + " (" + qRes.totalFiltered.toLocaleString("id-ID") + ")";
      }
      if (prevBtn) prevBtn.disabled = qRes.page <= 1;
      if (nextBtn) nextBtn.disabled = qRes.page >= qRes.totalPages;

      if (!qRes.items.length) {
        elList.innerHTML = '<li class="insp-empty" style="cursor:default">Tidak ada konsesi atau dossier yang cocok dengan filter aktif. (0 hasil cocok ≠ 0 konsesi di lapangan).</li>';
        return;
      }

      elList.innerHTML = qRes.items.map(function (row) {
        var sel = (state.selectedViewModelId === row.viewModelId || (row.linkedDossierId && state.selectedId === row.linkedDossierId)) ? " selected" : "";
        var qBadge = row.quality === "OFFICIAL"
          ? '<span class="vm-badge official">OFFICIAL · BIG</span>'
          : (row.recordKind === "dossier-only"
              ? '<span class="vm-badge dossier-only">DOSSIER INDEPENDEN</span>'
              : '<span class="vm-badge gfw">ESTIMATED · ' + escapeHtml(row.quality) + '</span>');
        var dBadge = row.hasInvestigativeDossier
          ? (row.recordKind === "dossier-only"
              ? '<span class="vm-badge dossier-only">Investigative dossier available (Unmatched)</span>'
              : '<span class="vm-badge dossier-linked">Investigative dossier available</span>')
          : '';
        var areaMeta = (row.areaHa != null && isFinite(row.areaHa))
          ? " · " + row.areaHa.toLocaleString("id-ID", { maximumFractionDigits: 0 }) + " ha"
          : "";
        var rightMetric = row.hasInvestigativeDossier && row.walhiHotspots != null
          ? ('<div class="hot"><span class="claim-label">WALHI claim</span>' + row.walhiHotspots.toLocaleString("id-ID") + '</div>')
          : ('<div class="hot" style="color:var(--muted);font-size:11px"><span class="claim-label">' + escapeHtml(row.subtype) + '</span>' + (row.permitNumber ? escapeHtml(row.permitNumber.slice(0, 16)) : "Inventaris") + '</div>');

        return (
          '<li class="' + sel + '" data-vm-id="' + escapeHtml(row.viewModelId) + '"' + (row.linkedDossierId ? (' data-id="' + escapeHtml(row.linkedDossierId) + '"') : '') + '>' +
            '<div>' +
              '<div class="name">' + escapeHtml(row.name) + '</div>' +
              '<div class="meta">' + escapeHtml(row.sector) + ' · ' + escapeHtml(row.locationText || row.region) + escapeHtml(areaMeta) + '</div>' +
              '<div class="vm-badges">' + qBadge + dBadge + '</div>' +
            '</div>' +
            rightMetric +
          '</li>'
        );
      }).join("");
    }"""
    text = replace_once(text, old_render_list, new_render_list, "v2 unified renderList")

    # 8. Route showConcessionInventoryFeature and showCompany through showUnifiedConcessionDetail (#14)
    text = replace_once(
        text,
        "    function showConcessionInventoryFeature(feature) {\n      var p = feature.properties || {};",
        "    function showConcessionInventoryFeature(feature) {\n"
        "      var p = (feature && feature.properties) || {};\n"
        "      var key = String(p.sourceInventoryId || p.inventoryId || (p.sourceDataset + ':' + p.sourceRecordId));\n"
        "      var vmId = 'inv:' + key;\n"
        "      if (!viewModelById[vmId]) {\n"
        "        buildUnifiedConcessionViewModels([feature], dossiers, [], state.region, null);\n"
        "      }\n"
        "      if (viewModelById[vmId]) {\n"
        "        showUnifiedConcessionDetail(vmId, 'summary');\n"
        "        return;\n"
        "      }",
        "v2 route showConcessionInventoryFeature",
    )

    text = replace_once(
        text,
        "    function showCompany(d) {\n      state.selectedId = d.id;",
        "    function showCompany(d) {\n"
        "      if (d && d.id) {\n"
        "        var matchedVmId = Object.keys(viewModelById).find(function (k) {\n"
        "          return viewModelById[k] && viewModelById[k].linkedDossierId === d.id;\n"
        "        });\n"
        "        if (!matchedVmId) {\n"
        "          buildUnifiedConcessionViewModels([], dossiers, boundaryById[d.id] || [], state.region, null);\n"
        "          matchedVmId = 'dossier:' + d.id;\n"
        "        }\n"
        "        if (viewModelById[matchedVmId]) {\n"
        "          showUnifiedConcessionDetail(matchedVmId, 'investigation');\n"
        "          return;\n"
        "        }\n"
        "      }\n"
        "      state.selectedId = d.id;",
        "v2 route showCompany",
    )

    # 9. Respect state.showFirms and state.showAdminBoundaries in refreshFirmsLayer & renderAfterRegionLoad (#15)
    old_firms_refresh = (
        "    function refreshFirmsLayer() {\n"
        "      clusterGroup.clearLayers();\n"
        "      nationalSummaryLayer.clearLayers();\n"
        "      if (state.region === \"indonesia\") {"
    )
    new_firms_refresh = (
        "    function refreshFirmsLayer() {\n"
        "      clusterGroup.clearLayers();\n"
        "      nationalSummaryLayer.clearLayers();\n"
        "      if (!state.showFirms) {\n"
        "        elTimeLabel.textContent = (currentDate() || '—') + ' · Layer Hotspots FIRMS dinonaktifkan';\n"
        "        return;\n"
        "      }\n"
        "      if (state.region === \"indonesia\") {"
    )
    if "if (!state.showFirms)" not in text and "if (state.showFirms === false)" not in text:
        text = replace_once(text, old_firms_refresh, new_firms_refresh, "v2 refreshFirmsLayer showFirms guard")

    # 10. Update elList click listener and wire Wave 2 controls
    old_list_click = (
        '    elList.addEventListener("click", function (e) {\n'
        '      var li = e.target.closest("li[data-id]");\n'
        '      if (!li) return;\n'
        '      var d = dossiers.find(function (x) { return x.id === li.getAttribute("data-id"); });\n'
        '      if (d) showCompany(d);\n'
        '    });'
    )
    new_list_click = (
        '    elList.addEventListener("click", function (e) {\n'
        '      var li = e.target.closest("li[data-vm-id], li[data-id]");\n'
        '      if (!li) return;\n'
        '      var vmId = li.getAttribute("data-vm-id");\n'
        '      if (vmId && viewModelById[vmId]) {\n'
        '        showUnifiedConcessionDetail(vmId, "summary");\n'
        '        return;\n'
        '      }\n'
        '      var d = dossiers.find(function (x) { return x.id === li.getAttribute("data-id"); });\n'
        '      if (d) showCompany(d);\n'
        '    });'
    )
    text = replace_once(text, old_list_click, new_list_click, "v2 elList unified click handler")

    wave2_events = r"""
    /* ---------- v2 Wave 2 Events (#12, #13, #14, #15) ---------- */
    document.getElementById("f-concession-source").addEventListener("change", function (e) {
      state.concessionSourceFilter = e.target.value || "";
      state.concessionPage = 1;
      renderList();
    });

    document.getElementById("f-concession-sort").addEventListener("change", function (e) {
      state.concessionSort = e.target.value || "default";
      state.concessionPage = 1;
      renderList();
    });

    document.getElementById("btn-page-prev").addEventListener("click", function () {
      if (state.concessionPage > 1) {
        state.concessionPage -= 1;
        renderList();
      }
    });

    document.getElementById("btn-page-next").addEventListener("click", function () {
      state.concessionPage += 1;
      renderList();
    });

    document.getElementById("tog-map-firms").addEventListener("change", function (e) {
      state.showFirms = !!e.target.checked;
      refreshFirmsLayer();
    });

    document.getElementById("tog-map-burned-area").addEventListener("change", function (e) {
      state.showBurnedArea = !!e.target.checked;
      var warnEl = document.getElementById("burned-area-layer-warning");
      if (warnEl) {
        warnEl.classList.toggle("visible", state.showBurnedArea);
      }
    });

    document.getElementById("tog-map-concessions").addEventListener("change", function (e) {
      var enabled = !!e.target.checked;
      state.showRegions = enabled;
      var regTog = document.getElementById("tog-regions");
      var invTog = document.getElementById("tog-inventory");
      if (regTog) regTog.checked = enabled;
      if (invTog) invTog.checked = enabled;
      refreshConcessionMarkers();
      refreshConcessionInventoryLayer();
    });

    document.getElementById("tog-map-admin").addEventListener("change", function (e) {
      state.showAdminBoundaries = !!e.target.checked;
      var pane = map.getPane("overlayPane");
      if (pane) {
        pane.style.opacity = state.showAdminBoundaries ? "1" : "0.92";
      }
    });

    document.getElementById("btn-focused-concession-zoom").addEventListener("click", function () {
      if (state.selectedViewModelId && viewModelById[state.selectedViewModelId]) {
        zoomToConcessionViewModel(viewModelById[state.selectedViewModelId]);
      }
    });

    document.getElementById("btn-focused-concession-clear").addEventListener("click", function () {
      state.selectedViewModelId = null;
      renderFocusedConcessionOnMap(null);
      renderList();
    });
"""

    text = replace_once(
        text,
        "    /* ---------- Init ---------- */",
        wave2_events + "\n    /* ---------- Init ---------- */",
        "v2 wave2 events",
    )

    if use_crlf:
        text = text.replace("\n", "\r\n")
    return text


def validate_patched(text: str) -> None:
    required = [
        'id="concession-explorer-controls"',
        'id="f-concession-source"',
        'id="f-concession-sort"',
        'id="concession-count-breakdown"',
        'id="concession-pagination"',
        'id="btn-page-prev"',
        'id="btn-page-next"',
        'id="map-layer-control"',
        'id="tog-map-firms"',
        'id="tog-map-burned-area"',
        'id="tog-map-concessions"',
        'id="tog-map-admin"',
        'id="burned-area-layer-warning"',
        'id="focused-concession-bar"',
        'function buildUnifiedConcessionViewModels(',
        'function ensureConcessionGeometryForRow(',
        '/inventory/index.json',
        'function queryUnifiedConcessionViewModels(',
        'function showUnifiedConcessionDetail(',
        'Investigative dossier available',
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(
            "missing v2 wave 2 integration markers: " + ", ".join(missing)
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="validate without writing index.html"
    )
    args = parser.parse_args()
    source = INDEX.read_text(encoding="utf-8")
    patched = build_patched_index(source)
    validate_patched(patched)
    if args.check:
        print("v2 wave 2 concessions & map patch: OK")
        return
    if patched != source:
        INDEX.write_text(patched, encoding="utf-8")
        print("patched index.html with MERATUS v2 Wave 2 concessions explorer, inspector, and map controls")
    else:
        print("index.html already contains MERATUS v2 Wave 2 patch")


if __name__ == "__main__":
    main()
