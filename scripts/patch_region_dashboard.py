#!/usr/bin/env python3
"""Patch the single-file dashboard with region/date lazy loading.

The repository intentionally keeps ``index.html`` as the stable source template.
Deployment first applies ``patch_land_holdings_dashboard.py`` and then this patch.
The resulting Pages artifact loads FIRMS, dossiers, and concession polygons by
logical Indonesian region instead of bulk-loading the legacy Kalimantan files.
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
    if "function selectRegion(regionId, preferredDate)" in source:
        return source
    if "function refreshEstimatedLandLayer()" not in source:
        raise RuntimeError(
            "region dashboard patch must run after patch_land_holdings_dashboard.py"
        )

    text = source

    text = replace_once(
        text,
        "<title>MERATUS — Intel Karhutla Kalimantan</title>",
        "<title>MERATUS — Intel Karhutla Indonesia</title>",
        "document title",
    )
    text = replace_once(
        text,
        '<div class="stamp"><strong>SUMBER TERBUKA</strong> · Karhutla Kalimantan</div>',
        '<div class="stamp"><strong>SUMBER TERBUKA</strong> · Karhutla Indonesia</div>',
        "header scope",
    )

    text = replace_once(
        text,
        '          <div class="filter-primary">\n'
        '            <label>Sektor utama\n',
        '          <div class="filter-primary">\n'
        '            <label>Wilayah\n'
        '              <select id="f-region">\n'
        '                <option value="indonesia">Indonesia · ringkasan</option>\n'
        '              </select>\n'
        '            </label>\n'
        '          </div>\n\n'
        '          <div class="filter-primary">\n'
        '            <label>Sektor utama\n',
        "region selector",
    )

    text = replace_once(
        text,
        '    /* Data dinamis: edit data/firms.json + data/dossiers.json lalu refresh.\n'
        '       Butuh http server lokal (file:// diblokir CORS fetch). */',
        '    /* Data dinamis: manifest + shard per region/tanggal.\n'
        '       Butuh http server lokal (file:// diblokir CORS fetch). */',
        "data comment",
    )

    text = replace_once(
        text,
        "    elHeaderStats.textContent = \"MEMUAT data/*.json …\";\n"
        "    elStamp.textContent = \"memuat status…\";\n"
        "    elInsp.innerHTML = '<div class=\"insp-empty\">Memuat <span class=\"mono\">data/firms.json</span>, <span class=\"mono\">data/dossiers.json</span> &amp; <span class=\"mono\">data/boundaries.geojson</span>…</div>';",
        "    elHeaderStats.textContent = \"MEMUAT manifest Indonesia …\";\n"
        "    elStamp.textContent = \"memuat status…\";\n"
        "    elInsp.innerHTML = '<div class=\"insp-empty\">Memuat manifest hotspot, dossier, dan konsesi per wilayah…</div>';",
        "loading copy",
    )

    old_loader = '''    Promise.all([\n      loadJson("data/firms.json").catch(function (err) {\n        return { __error: err, meta: null, points: [] };\n      }),\n      loadJson("data/dossiers.json"),\n      loadJson("data/boundaries.geojson").catch(function () {\n        return { type: "FeatureCollection", features: [] };\n      }),\n      loadJson("data/firms-status.json").catch(function () { return null; }),\n      loadJson("data/affiliated-land-holdings.json").catch(function () { return { meta: {}, people: [], holdings: [] }; }),\n      loadJson("data/affiliated-land-display-centers.json").catch(function () { return { meta: {}, centers: {} }; })\n    ]).then(function (pair) {\n      boot(pair[0], pair[1], pair[2], pair[3], pair[4], pair[5]);'''
    new_loader = '''    Promise.all([\n      loadJson("data/regions.json"),\n      loadJson("data/hotspots/manifest.json"),\n      loadJson("data/hotspots/status.json").catch(function () { return null; }),\n      loadJson("data/dossiers/manifest.json").catch(function () { return { regions: {} }; }),\n      loadJson("data/concessions/manifest.json").catch(function () { return { regions: {} }; }),\n      loadJson("data/affiliated-land-holdings.json").catch(function () { return { meta: {}, people: [], holdings: [] }; }),\n      loadJson("data/affiliated-land-display-centers.json").catch(function () { return { meta: {}, centers: {} }; })\n    ]).then(function (pair) {\n      boot(pair[0], pair[1], pair[2], pair[3], pair[4], pair[5], pair[6]);'''
    text = replace_once(text, old_loader, new_loader, "manifest loader")

    old_boot = '''    function boot(firmsPayload, dossierPayload, boundariesGeo, pipelineStatusPayload, affiliatedPayload, holdingCentersPayload) {\n    var firms = [];\n    var firmsMeta = null;\n    var pipelineStatus = (pipelineStatusPayload && typeof pipelineStatusPayload === "object") ? pipelineStatusPayload : null;\n    var usingFallback = false;\n    var sipongi = dossierPayload.sipongiFallback || null;\n    var dossiers = dossierPayload.dossiers || [];\n    var walhi = dossierPayload.walhiSummary || null;\n    var landHoldings = affiliatedPayload && Array.isArray(affiliatedPayload.holdings) ? affiliatedPayload.holdings : [];\n    var landPeople = affiliatedPayload && Array.isArray(affiliatedPayload.people) ? affiliatedPayload.people : [];\n    var landPeopleById = {};\n    landPeople.forEach(function (p) { landPeopleById[p.id] = p; });\n    var holdingCenters = holdingCentersPayload && holdingCentersPayload.centers ? holdingCentersPayload.centers : {};\n    var boundaryById = {};\n    (boundariesGeo && boundariesGeo.features ? boundariesGeo.features : []).forEach(function (f) {\n      var id = f.properties && f.properties.dossierId;\n      if (!id || !f.geometry) return;\n      if (!boundaryById[id]) boundaryById[id] = [];\n      boundaryById[id].push(f);\n    });'''
    new_boot = '''    function boot(regionsPayload, hotspotsManifest, pipelineStatusPayload, dossierManifest, concessionManifest, affiliatedPayload, holdingCentersPayload) {\n    var firms = [];\n    var firmsMeta = hotspotsManifest && hotspotsManifest.meta ? hotspotsManifest.meta : null;\n    var pipelineStatus = (pipelineStatusPayload && typeof pipelineStatusPayload === "object") ? pipelineStatusPayload : null;\n    var usingFallback = false;\n    var sipongi = null;\n    var dossiers = [];\n    var walhi = null;\n    var regions = regionsPayload && Array.isArray(regionsPayload.regions) ? regionsPayload.regions : [];\n    var regionById = {};\n    regions.forEach(function (region) { regionById[region.id] = region; });\n    var hotspotCache = {};\n    var staticRegionCache = {};\n    var regionRequest = 0;\n    var hotspotRequest = 0;\n    var landHoldings = affiliatedPayload && Array.isArray(affiliatedPayload.holdings) ? affiliatedPayload.holdings : [];\n    var landPeople = affiliatedPayload && Array.isArray(affiliatedPayload.people) ? affiliatedPayload.people : [];\n    var landPeopleById = {};\n    landPeople.forEach(function (p) { landPeopleById[p.id] = p; });\n    var holdingCenters = holdingCentersPayload && holdingCentersPayload.centers ? holdingCentersPayload.centers : {};\n    var boundaryById = {};\n\n    function rebuildBoundaryIndex(boundariesGeo) {\n      boundaryById = {};\n      (boundariesGeo && boundariesGeo.features ? boundariesGeo.features : []).forEach(function (f) {\n        var id = f.properties && f.properties.dossierId;\n        if (!id || !f.geometry) return;\n        if (!boundaryById[id]) boundaryById[id] = [];\n        boundaryById[id].push(f);\n      });\n    }'''
    text = replace_once(text, old_boot, new_boot, "boot initialization")

    old_payload_init = '''    if (firmsPayload && !firmsPayload.__error) {\n      firms = Array.isArray(firmsPayload)\n        ? firmsPayload\n        : (firmsPayload.points || []);\n      firmsMeta = Array.isArray(firmsPayload) ? null : (firmsPayload.meta || null);\n    }\n\n    if (!firms.length) {\n      usingFallback = true;\n      firms = synthesizeSipongiPoints(sipongi);\n      firmsMeta = {\n        source: "SIPONGI/Kemenhut fallback (17–19 Agu 2026)",\n        count: firms.length,\n        fallback: true,\n        loadError: firmsPayload && firmsPayload.__error\n          ? String(firmsPayload.__error.message || firmsPayload.__error)\n          : null\n      };\n    }\n\n'''
    text = replace_once(text, old_payload_init, "", "remove legacy payload initialization")

    text = replace_once(
        text,
        '      selectedType: null,\n      prov: "",',
        '      selectedType: null,\n      region: "indonesia",\n      prov: "",',
        "state region",
    )

    old_dates = '''    var dates = Array.from(new Set(firms.map(function (f) { return f.date; }))).sort();\n    state.dates = dates;\n    state.dateIdx = dates.length ? dates.length - 1 : 0;\n\n    renderDatasetState();\n'''
    helpers = r'''    function regionManifestEntry(regionId) {
      return hotspotsManifest && hotspotsManifest.regions
        ? (hotspotsManifest.regions[regionId] || null)
        : null;
    }

    function manifestDayEntry(regionId, date) {
      var entry = regionManifestEntry(regionId);
      if (!entry) return null;
      return (entry.days || []).find(function (day) { return day.date === date; }) || null;
    }

    function nationalCountForDate(date) {
      if (!date || !hotspotsManifest || !hotspotsManifest.regions) return 0;
      return Object.keys(hotspotsManifest.regions).reduce(function (sum, regionId) {
        var day = manifestDayEntry(regionId, date);
        return sum + (day ? Number(day.count || 0) : 0);
      }, 0);
    }

    function regionCountForDate(regionId, date) {
      if (regionId === "indonesia") return nationalCountForDate(date);
      var day = manifestDayEntry(regionId, date);
      return day ? Number(day.count || 0) : 0;
    }

    function availableDates(regionId) {
      var values = [];
      if (regionId === "indonesia") {
        Object.keys((hotspotsManifest && hotspotsManifest.regions) || {}).forEach(function (id) {
          ((hotspotsManifest.regions[id] || {}).days || []).forEach(function (day) { values.push(day.date); });
        });
      } else {
        var entry = regionManifestEntry(regionId);
        ((entry && entry.days) || []).forEach(function (day) { values.push(day.date); });
      }
      return Array.from(new Set(values)).sort();
    }

    function configureDates(regionId, preferredDate) {
      var dates = availableDates(regionId);
      state.dates = dates;
      var preferredIndex = preferredDate ? dates.indexOf(preferredDate) : -1;
      state.dateIdx = preferredIndex >= 0 ? preferredIndex : (dates.length ? dates.length - 1 : 0);
      elTime.min = 0;
      elTime.max = Math.max(0, dates.length - 1);
      elTime.value = state.dateIdx;
      elTime.disabled = !dates.length;
    }

    function updateProvinceOptions(regionId) {
      var select = document.getElementById("f-prov");
      var selected = state.prov;
      var provinces = [];
      if (regionId === "indonesia") {
        regions.forEach(function (region) { provinces = provinces.concat(region.provinces || []); });
      } else if (regionById[regionId]) {
        provinces = regionById[regionId].provinces || [];
      }
      select.innerHTML = '<option value="">Semua</option>' + provinces.map(function (province) {
        return '<option>' + escapeHtml(province) + '</option>';
      }).join("");
      state.prov = provinces.indexOf(selected) >= 0 ? selected : "";
      select.value = state.prov;
    }

    function populateRegionSelector() {
      var select = document.getElementById("f-region");
      select.innerHTML = '<option value="indonesia">Indonesia · ringkasan</option>' + regions.map(function (region) {
        return '<option value="' + escapeHtml(region.id) + '">' + escapeHtml(region.label) + '</option>';
      }).join("");
      select.value = state.region;
    }

    function virtualNationalPayload(date) {
      return {
        meta: {
          coverageId: (hotspotsManifest.meta && hotspotsManifest.meta.coverageId) || "indonesia",
          region: "indonesia",
          date: date,
          count: nationalCountForDate(date),
          source: "NASA FIRMS NRT VIIRS",
          lastSuccessfulSync: hotspotsManifest.meta && hotspotsManifest.meta.lastSuccessfulSync,
          newestDetectionUtc: hotspotsManifest.meta && hotspotsManifest.meta.newestDetectionUtc,
          pipelineVersion: hotspotsManifest.meta && hotspotsManifest.meta.pipelineVersion
        },
        points: []
      };
    }

    function loadHotspotDay(regionId, date) {
      if (regionId === "indonesia") return Promise.resolve(virtualNationalPayload(date));
      var entry = manifestDayEntry(regionId, date);
      if (!entry || !entry.url) {
        return Promise.resolve({
          meta: {
            coverageId: "indonesia",
            region: regionId,
            date: date,
            count: 0,
            source: "NASA FIRMS NRT VIIRS",
            lastSuccessfulSync: hotspotsManifest.meta && hotspotsManifest.meta.lastSuccessfulSync
          },
          points: []
        });
      }
      var key = regionId + "|" + date;
      if (!hotspotCache[key]) {
        hotspotCache[key] = loadJson(entry.url).catch(function (err) {
          delete hotspotCache[key];
          throw err;
        });
      }
      return hotspotCache[key];
    }

    function loadRegionStatic(regionId) {
      if (regionId === "indonesia") {
        return Promise.resolve({
          dossier: { dossiers: [], walhiSummary: null, sipongiFallback: null },
          boundaries: { type: "FeatureCollection", features: [] }
        });
      }
      if (staticRegionCache[regionId]) return staticRegionCache[regionId];
      var dossierEntry = dossierManifest && dossierManifest.regions ? dossierManifest.regions[regionId] : null;
      var concessionEntry = concessionManifest && concessionManifest.regions ? concessionManifest.regions[regionId] : null;
      var dossierUrl = dossierEntry && dossierEntry.available ? dossierEntry.url : null;
      if (!dossierUrl && concessionEntry && concessionEntry.available) dossierUrl = concessionEntry.dossiers;
      var boundaryUrl = concessionEntry && concessionEntry.available ? concessionEntry.boundaries : null;
      staticRegionCache[regionId] = Promise.all([
        dossierUrl ? loadJson(dossierUrl) : Promise.resolve({ dossiers: [], walhiSummary: null, sipongiFallback: null }),
        boundaryUrl ? loadJson(boundaryUrl) : Promise.resolve({ type: "FeatureCollection", features: [] })
      ]).then(function (pair) {
        return { dossier: pair[0], boundaries: pair[1] };
      }).catch(function (err) {
        delete staticRegionCache[regionId];
        throw err;
      });
      return staticRegionCache[regionId];
    }

    function applyHotspotPayload(payload) {
      firms = payload && Array.isArray(payload.points) ? payload.points : [];
      firmsMeta = payload && payload.meta ? payload.meta : null;
      usingFallback = false;
      if (!firms.length && state.region === "kalimantan" && sipongi) {
        var fallback = synthesizeSipongiPoints(sipongi).filter(function (point) {
          return !currentDate() || point.date === currentDate();
        });
        if (fallback.length) {
          firms = fallback;
          usingFallback = true;
          firmsMeta = {
            source: "SIPONGI/Kemenhut fallback",
            count: fallback.length,
            fallback: true,
            date: currentDate(),
            lastSuccessfulSync: pipelineStatus && pipelineStatus.lastSuccessfulSync
          };
        }
      }
    }

    function applyStaticPayload(payload) {
      var dossierPayload = payload && payload.dossier ? payload.dossier : {};
      dossiers = Array.isArray(dossierPayload.dossiers) ? dossierPayload.dossiers : [];
      walhi = dossierPayload.walhiSummary || null;
      sipongi = dossierPayload.sipongiFallback || null;
      rebuildBoundaryIndex(payload && payload.boundaries ? payload.boundaries : null);
    }

    function focusRegion(regionId) {
      if (regionId === "indonesia") {
        map.fitBounds([[-11.5, 94.5], [6.5, 141.5]], { padding: [12, 12], animate: false });
        return;
      }
      var region = regionById[regionId];
      if (region && region.center) map.setView(region.center, region.zoom || 5, { animate: false });
    }

    function renderAfterRegionLoad() {
      state.selectedId = null;
      state.selectedType = null;
      elInsp.innerHTML = '<div class="insp-empty">Pilih cluster api, konsesi, atau node graf. Coverage aktif: ' + escapeHtml(state.region === "indonesia" ? "Indonesia" : ((regionById[state.region] || {}).label || state.region)) + '.</div>';
      renderDatasetState();
      renderList();
      refreshConcessionMarkers();
      refreshEstimatedLandLayer();
      refreshFirmsLayer();
      if (state.mode === "graph") drawGraph(null);
    }

    function selectRegion(regionId, preferredDate) {
      if (regionId !== "indonesia" && !regionById[regionId]) return Promise.resolve();
      var token = ++regionRequest;
      ++hotspotRequest;
      state.region = regionId;
      document.getElementById("f-region").value = regionId;
      configureDates(regionId, preferredDate || currentDate());
      updateProvinceOptions(regionId);
      elTimeLabel.textContent = "memuat " + (regionId === "indonesia" ? "Indonesia" : ((regionById[regionId] || {}).label || regionId)) + "…";
      var date = currentDate();
      return Promise.all([loadHotspotDay(regionId, date), loadRegionStatic(regionId)]).then(function (pair) {
        if (token !== regionRequest) return;
        applyStaticPayload(pair[1]);
        applyHotspotPayload(pair[0]);
        focusRegion(regionId);
        renderAfterRegionLoad();
      }).catch(function (err) {
        if (token !== regionRequest) return;
        elHeaderStats.textContent = "REGION DATA ERROR";
        elTimeLabel.textContent = "gagal memuat wilayah";
        elInsp.innerHTML = '<div class="insp-empty">Gagal memuat data wilayah.<br/><br/><span class="mono">' + escapeHtml(err && err.message ? err.message : err) + '</span></div>';
      });
    }

    function loadSelectedDate() {
      var token = ++hotspotRequest;
      var regionId = state.region;
      var date = currentDate();
      elTimeLabel.textContent = "memuat " + (date || "tanggal") + "…";
      return loadHotspotDay(regionId, date).then(function (payload) {
        if (token !== hotspotRequest || regionId !== state.region) return;
        applyHotspotPayload(payload);
        renderDatasetState();
        refreshFirmsLayer();
      }).catch(function (err) {
        if (token !== hotspotRequest) return;
        elTimeLabel.textContent = "gagal memuat " + (date || "tanggal");
        elStamp.dataset.status = "stale";
        elStamp.title = String(err && err.message ? err.message : err);
      });
    }

'''
    text = replace_once(text, old_dates, helpers, "region/date helpers")

    text = replace_once(
        text,
        '      var count = firmsMeta && firmsMeta.count != null ? firmsMeta.count : firms.length;\n'
        '      var mapped = dossiers.filter(function (d) { return (boundaryById[d.id] || []).length > 0; }).length;\n'
        '      elHeaderStats.textContent = count.toLocaleString("id-ID") + " FIRMS detections · " + dossiers.length + " WALHI dossiers · " + landHoldings.length + " affiliated land holdings · " + mapped + "/" + dossiers.length + " boundaries mapped";',
        '      var count = firmsMeta && firmsMeta.count != null ? firmsMeta.count : firms.length;\n'
        '      var mapped = dossiers.filter(function (d) { return (boundaryById[d.id] || []).length > 0; }).length;\n'
        '      var scopeLabel = state.region === "indonesia" ? "Indonesia" : ((regionById[state.region] || {}).label || state.region);\n'
        '      var holdingCount = state.region === "kalimantan" ? landHoldings.length : 0;\n'
        '      elHeaderStats.textContent = count.toLocaleString("id-ID") + " FIRMS detections · " + scopeLabel + " · " + dossiers.length + " dossiers · " + holdingCount + " affiliated land holdings · " + mapped + "/" + dossiers.length + " boundaries mapped";',
        "regional header stats",
    )

    text = replace_once(
        text,
        '      var sourceName = usingFallback ? "SIPONGI fallback" : (/NRT/i.test((firmsMeta && firmsMeta.source) || "") ? "NASA FIRMS NRT" : "NASA FIRMS snapshot");',
        '      var sourceName = usingFallback ? "SIPONGI fallback" : ((hotspotsManifest.meta && hotspotsManifest.meta.bootstrap) ? "FIRMS bootstrap" : "NASA FIRMS NRT");',
        "source label",
    )

    old_walhi = '''      if (walhi) {\n        if (periodEl) periodEl.textContent = walhi.period || "periode tidak dinyatakan";\n        if (statEl) statEl.textContent = (walhi.pctInConcession != null ? walhi.pctInConcession + "%" : "WALHI CLAIM");\n        if (copyEl) copyEl.textContent = (walhi.inConcession != null && walhi.totalKalimantan != null\n          ? walhi.inConcession.toLocaleString("id-ID") + " / " + walhi.totalKalimantan.toLocaleString("id-ID") + " reported hotspots berada di wilayah konsesi"\n          : "reported hotspots berada di wilayah konsesi");\n      }'''
    new_walhi = '''      if (walhi) {\n        if (periodEl) periodEl.textContent = walhi.period || "periode tidak dinyatakan";\n        if (statEl) statEl.textContent = (walhi.pctInConcession != null ? walhi.pctInConcession + "%" : "WALHI CLAIM");\n        if (copyEl) copyEl.textContent = (walhi.inConcession != null && walhi.totalKalimantan != null\n          ? walhi.inConcession.toLocaleString("id-ID") + " / " + walhi.totalKalimantan.toLocaleString("id-ID") + " reported hotspots berada di wilayah konsesi"\n          : "reported hotspots berada di wilayah konsesi");\n      } else {\n        if (periodEl) periodEl.textContent = state.region === "indonesia" ? "coverage nasional" : "coverage regional";\n        if (statEl) statEl.textContent = state.region === "indonesia" ? "7 REGION" : "—";\n        if (copyEl) copyEl.textContent = state.region === "indonesia"\n          ? "Pilih wilayah untuk memuat hotspot mentah, dossier, dan polygon konsesi secara lazy."\n          : "Dossier / konsesi belum tersedia untuk wilayah ini; hotspot FIRMS tetap tersedia.";\n      }'''
    text = replace_once(text, old_walhi, new_walhi, "regional evidence banner")

    text = replace_once(
        text,
        '    var map = L.map("map", { zoomControl: true, attributionControl: true }).setView([-1.5, 114.5], 6);',
        '    var map = L.map("map", { zoomControl: true, attributionControl: true }).setView([-2.5, 118], 5);',
        "national map viewport",
    )
    text = replace_once(
        text,
        '''    var clusterGroup = L.markerClusterGroup({\n      showCoverageOnHover: false,\n      maxClusterRadius: 45,\n      spiderfyOnMaxZoom: true\n    });''',
        '''    var clusterGroup = L.markerClusterGroup({\n      showCoverageOnHover: false,\n      maxClusterRadius: 45,\n      spiderfyOnMaxZoom: true,\n      removeOutsideVisibleBounds: true,\n      chunkedLoading: true,\n      chunkInterval: 100,\n      chunkDelay: 20\n    });''',
        "chunked clustering",
    )
    text = replace_once(
        text,
        "    var concessionLayer = L.layerGroup().addTo(map);\n    var estimatedLandLayer = L.layerGroup().addTo(map);",
        "    var nationalSummaryLayer = L.layerGroup().addTo(map);\n    var concessionLayer = L.layerGroup().addTo(map);\n    var estimatedLandLayer = L.layerGroup().addTo(map);",
        "national summary layer",
    )

    old_refresh = '''    function refreshFirmsLayer() {\n      clusterGroup.clearLayers();\n      var pts = firmsForView();\n      var markers = [];\n      for (var i = 0; i < pts.length; i++) {\n        (function (p) {\n          var m = L.marker([p.lat, p.lon], { icon: fireIcon(p.conf) });\n          m.on("click", function () {\n            showFirmsPoint(p, nearestConcession(p.lat, p.lon));\n          });\n          markers.push(m);\n        })(pts[i]);\n      }\n      clusterGroup.addLayers(markers);\n      elTimeLabel.textContent = (currentDate() || "—") + " · " + pts.length.toLocaleString("id-ID") + " satellite detections" +\n        (state.conf ? " · " + state.conf : "") + (state.platform ? " · " + state.platform : "");\n    }'''
    new_refresh = r'''    function refreshNationalSummary() {
      nationalSummaryLayer.clearLayers();
      var date = currentDate();
      regions.forEach(function (region) {
        var count = regionCountForDate(region.id, date);
        if (!count || !region.center) return;
        var radius = Math.max(7, Math.min(20, 6 + Math.log10(count + 1) * 4));
        var marker = L.circleMarker(region.center, {
          radius: radius,
          color: "#e23a14",
          weight: 1,
          opacity: 0.9,
          fillColor: "#e23a14",
          fillOpacity: 0.28
        });
        marker.bindTooltip(
          '<strong>' + escapeHtml(region.label) + '</strong><br/>' +
          count.toLocaleString("id-ID") + ' FIRMS detections · ' + escapeHtml(date || "—") +
          '<br/><span style="color:#9a968e">klik untuk memuat region</span>',
          { sticky: true, opacity: 0.96 }
        );
        marker.on("click", function () { selectRegion(region.id, date); });
        nationalSummaryLayer.addLayer(marker);
      });
    }

    function refreshFirmsLayer() {
      clusterGroup.clearLayers();
      nationalSummaryLayer.clearLayers();
      if (state.region === "indonesia") {
        refreshNationalSummary();
        var nationalCount = nationalCountForDate(currentDate());
        elTimeLabel.textContent = (currentDate() || "—") + " · " + nationalCount.toLocaleString("id-ID") + " detections · ringkasan 7 region";
        return;
      }
      var pts = firmsForView();
      var markers = [];
      for (var i = 0; i < pts.length; i++) {
        (function (p) {
          var m = L.marker([p.lat, p.lon], { icon: fireIcon(p.conf) });
          m.on("click", function () {
            showFirmsPoint(p, nearestConcession(p.lat, p.lon));
          });
          markers.push(m);
        })(pts[i]);
      }
      clusterGroup.addLayers(markers);
      var scope = (regionById[state.region] || {}).label || state.region;
      elTimeLabel.textContent = (currentDate() || "—") + " · " + pts.length.toLocaleString("id-ID") + " satellite detections · " + scope +
        (state.conf ? " · " + state.conf : "") + (state.platform ? " · " + state.platform : "");
    }'''
    text = replace_once(text, old_refresh, new_refresh, "lazy FIRMS rendering")

    text = replace_once(
        text,
        "    function refreshEstimatedLandLayer() {\n      estimatedLandLayer.clearLayers();",
        "    function refreshEstimatedLandLayer() {\n      estimatedLandLayer.clearLayers();\n      if (state.region !== \"kalimantan\") return;",
        "regional land holdings",
    )

    event_marker = '    /* ---------- Events ---------- */\n'
    region_event = '''    document.getElementById("f-region").addEventListener("change", function (e) {\n      selectRegion(e.target.value, currentDate());\n    });\n\n'''
    text = replace_once(text, event_marker, event_marker + region_event, "region change event")

    old_time = '''    elTime.min = 0;\n    elTime.max = Math.max(0, dates.length - 1);\n    elTime.value = state.dateIdx;\n    elTime.addEventListener("input", function (e) {\n      state.dateIdx = parseInt(e.target.value, 10) || 0;\n      refreshFirmsLayer();\n    });'''
    new_time = '''    elTime.addEventListener("input", function (e) {\n      state.dateIdx = parseInt(e.target.value, 10) || 0;\n      loadSelectedDate();\n    });'''
    text = replace_once(text, old_time, new_time, "date shard event")

    old_init = '''    renderList();\n    refreshConcessionMarkers();\n    refreshEstimatedLandLayer();\n    refreshFirmsLayer();'''
    new_init = '''    populateRegionSelector();\n    configureDates("indonesia", null);\n    updateProvinceOptions("indonesia");\n    selectRegion("indonesia", currentDate());'''
    text = replace_once(text, old_init, new_init, "region-aware init")

    return text


def validate_patched(text: str) -> None:
    required = [
        'id="f-region"',
        'data/hotspots/manifest.json',
        'data/dossiers/manifest.json',
        'data/concessions/manifest.json',
        'function selectRegion(regionId, preferredDate)',
        'function loadHotspotDay(regionId, date)',
        'function refreshNationalSummary()',
        'chunkedLoading: true',
        'state.region !== "kalimantan"',
        'Indonesia · ringkasan',
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError("missing region integration markers: " + ", ".join(missing))
    forbidden = [
        'loadJson("data/firms.json")',
        'loadJson("data/dossiers.json")',
        'loadJson("data/boundaries.geojson")',
    ]
    present = [marker for marker in forbidden if marker in text]
    if present:
        raise RuntimeError("legacy bulk frontend loads remain: " + ", ".join(present))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="validate without writing index.html")
    args = parser.parse_args()

    source = INDEX.read_text(encoding="utf-8")
    patched = build_patched_index(source)
    validate_patched(patched)

    if args.check:
        print("region-aware dashboard patch: OK")
        return

    if patched != source:
        INDEX.write_text(patched, encoding="utf-8")
        print("patched index.html with Indonesia region/date lazy loading")
    else:
        print("index.html already contains Indonesia region/date lazy loading")


if __name__ == "__main__":
    main()
