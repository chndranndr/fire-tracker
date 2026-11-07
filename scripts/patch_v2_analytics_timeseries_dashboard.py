#!/usr/bin/env python3
"""Patch index.html with MERATUS v2 Wave 3 (#16, #17, #18):
- #16: Durable FIRMS daily history consumption (`data/hotspots/history.json`) and 3-timestamp freshness disclosure (lastAttemptedSync, lastSuccessfulSync, newestDetectionUtc) + Git vs Pages runtime note
- #17: Daily hotspot trends, complete-day deltas, same-time-of-day (TOD) partial-day comparisons, UTC vs WIB (`Asia/Jakarta`) aggregation, and platform/confidence filtering
- #18: Reusable accessible time-series chart component (`renderReusableTimeSeriesChart`) supporting daily hotspot, daily burned area, hourly station PM2.5, and weekly ISPA series with truthful grain and gap preservation
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


V2_WAVE3_CSS = r"""
    /* ==========================================================================
       MERATUS v2 Wave 3 (#16, #17, #18): Reusable Time-Series Chart & Deltas
       ========================================================================== */
    .overview-widget.expanded {
      grid-column: 1 / -1;
    }
    .ts-controls-bar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
      margin-bottom: 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid var(--line);
    }
    .ts-control-group {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 110px;
    }
    .ts-control-group label {
      font-family: var(--mono);
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
    }
    .ts-control-group select {
      background: var(--bg);
      color: var(--ink);
      border: 1px solid var(--line-2);
      border-radius: 3px;
      padding: 4px 6px;
      font-family: var(--sans);
      font-size: 11px;
    }
    .ts-delta-strip {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
      gap: 6px;
      margin-bottom: 8px;
    }
    .ts-delta-pill {
      background: rgba(255, 255, 255, 0.02);
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 6px 8px;
      font-size: 11px;
      line-height: 1.35;
    }
    .ts-delta-pill .delta-label {
      display: block;
      font-family: var(--mono);
      font-size: 9px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin-bottom: 2px;
    }
    .ts-delta-pill .delta-val {
      font-family: var(--mono);
      font-weight: 600;
      font-size: 13px;
      color: var(--ink);
    }
    .ts-delta-pill .delta-val.up {
      color: #ff8b70;
    }
    .ts-delta-pill .delta-val.down {
      color: #6fd08c;
    }
    .ts-chart-tooltip {
      margin-top: 6px;
      padding: 7px 9px;
      border-radius: 4px;
      background: rgba(9, 9, 9, 0.92);
      border: 1px solid var(--line-2);
      font-family: var(--mono);
      font-size: 11px;
      line-height: 1.45;
      color: var(--ink);
      min-height: 38px;
    }
    .ts-bar-group:focus-visible {
      outline: 2px solid var(--amber);
      outline-offset: 2px;
    }
    @media (max-width: 480px) {
      .ts-controls-bar {
        gap: 4px;
      }
      .ts-control-group {
        min-width: calc(50% - 4px);
      }
    }
"""


V2_TREND_CARD_CONTROLS_HTML = """              <div class="overview-widget-h">
                <span id="trend-widget-title">Analitik Deret Waktu &amp; Tren Harian (#17, #18)</span>
                <div style="display:flex;gap:6px;align-items:center">
                  <button type="button" class="filter-reset-btn" id="btn-expand-trend-chart" aria-expanded="false">Perluas ⤢</button>
                  <button type="button" class="kpi-cite-btn" id="btn-trend-provenance" data-metric-id="firms-hotspots">Provenance ⓘ</button>
                </div>
              </div>
              <div class="ts-controls-bar" id="ts-controls-bar" role="group" aria-label="Kontrol grafik deret waktu">
                <div class="ts-control-group">
                  <label for="ts-metric-select">Metrik Deret Waktu</label>
                  <select id="ts-metric-select">
                    <option value="firms-hotspots">Deteksi Panas (FIRMS · Harian)</option>
                    <option value="burned-area">Area Terbakar (Burned Area · Harian)</option>
                    <option value="air-quality-pm25">PM2.5 Stasiun (ISPU · Per Jam)</option>
                    <option value="kemenkes-ispa">Kasus ISPA (Surveilans · Mingguan)</option>
                  </select>
                </div>
                <div class="ts-control-group">
                  <label for="ts-agg-select">Mode Seri</label>
                  <select id="ts-agg-select">
                    <option value="incremental">Inkremental (Per Interval)</option>
                    <option value="cumulative">Kumulatif Periode</option>
                  </select>
                </div>
                <div class="ts-control-group">
                  <label for="ts-tz-select">Zona Waktu</label>
                  <select id="ts-tz-select">
                    <option value="UTC">UTC (Asli Satelit)</option>
                    <option value="Asia/Jakarta">WIB (Asia/Jakarta UTC+7)</option>
                  </select>
                </div>
              </div>
              <div class="ts-delta-strip" id="ts-delta-strip" aria-live="polite"></div>
              <div class="trend-svg-wrap" id="overview-trend-svg"></div>
              <div class="ts-chart-tooltip" id="ts-chart-tooltip" role="status" aria-live="polite">
                Arahkan kursor, sentuh, atau tekan Tab pada batang grafik untuk melihat detail tanggal, nilai, perubahan harian, dan sumber data.
              </div>"""


V2_WAVE3_JS = r"""
    /* ==========================================================================
       MERATUS v2 Wave 3 (#16, #17, #18): Durable History, Deltas & Reusable Chart
       ========================================================================== */
    var hotspotHistory = null;

    function computeDeltaMetricsJs(currVal, prevVal) {
      if (currVal == null || prevVal == null || !isFinite(currVal) || !isFinite(prevVal)) {
        return {
          current: currVal,
          previous: prevVal,
          deltaAbs: null,
          deltaPct: null,
          denominatorZero: false,
          comparable: false,
          reason: "missing_comparison_period"
        };
      }
      var deltaAbs = currVal - prevVal;
      if (prevVal === 0) {
        return {
          current: currVal,
          previous: prevVal,
          deltaAbs: deltaAbs,
          deltaPct: null,
          denominatorZero: true,
          comparable: true,
          reason: "denominator_zero"
        };
      }
      var deltaPct = Number(((deltaAbs / prevVal) * 100).toFixed(2));
      return {
        current: currVal,
        previous: prevVal,
        deltaAbs: deltaAbs,
        deltaPct: deltaPct,
        denominatorZero: false,
        comparable: true,
        reason: "ok"
      };
    }

    function extractBucketFilteredCountJs(bucket, platform, conf, useSameTod) {
      if (!bucket) return 0;
      if (useSameTod && !platform && !conf) {
        return Number(bucket.sameTodCount != null ? bucket.sameTodCount : (bucket.count || 0));
      }
      var plat = String(platform || "").trim().toUpperCase();
      var cf = String(conf || "").trim().toLowerCase();
      if (plat && cf && bucket.byPlatformConfidence) {
        return Number(bucket.byPlatformConfidence[plat + "|" + cf] || 0);
      }
      if (plat && bucket.byPlatform) {
        return Number(bucket.byPlatform[plat] || 0);
      }
      if (cf && bucket.byConfidence) {
        return Number(bucket.byConfidence[cf] || 0);
      }
      return Number(bucket.count || 0);
    }

    function getActiveScopeLabel() {
      var parts = [
        state.region === "indonesia"
          ? "Indonesia"
          : ((regionById[state.region] || {}).label || state.region)
      ];
      if (state.prov) parts.push(state.prov);
      if (state.kab) parts.push(state.kab);
      return parts.join(" · ");
    }

    function buildTypedTimeSeriesForView(metricId, opts) {
      opts = opts || {};
      var mId = String(metricId || state.tsMetric || "firms-hotspots");
      var aggMode = String(opts.aggregationMode || state.tsAggMode || "incremental") === "cumulative" ? "cumulative" : "incremental";
      var tzMode = String(opts.timezone || state.tsTimezone || "UTC") === "Asia/Jakarta" ? "Asia/Jakarta" : "UTC";
      var reg = opts.region != null ? opts.region : state.region;
      var prov = opts.prov != null ? opts.prov : state.prov;
      var kab = opts.kab != null ? opts.kab : state.kab;
      var win = opts.window != null ? opts.window : (state.window || "all");
      var plat = opts.platform != null ? opts.platform : (state.platform || "");
      var conf = opts.conf != null ? opts.conf : (state.conf || "");
      var scopeLabel = getActiveScopeLabel();

      if (mId !== "firms-hotspots") {
        var specs = {
          "burned-area": {
            title: "Estimasi Luas Area Terbakar Harian (Burned Area)",
            sourceName: "Produk Burned Area Independen (Pending #20)",
            units: "ha",
            granularity: "day",
            reason: "Produk poligon/raster area terbakar independen (#20/#21) belum di-ingest. Titik panas FIRMS tidak pernah dikonversi menjadi hektar terbakar."
          },
          "air-quality-pm25": {
            title: "Konsentrasi PM2.5 Berbasis Stasiun (ISPU / OpenAQ)",
            sourceName: "Stasiun Kualitas Udara ISPU/KLHK & OpenAQ (Pending #22)",
            units: "µg/m³",
            granularity: "hour",
            reason: "Observasi PM2.5 berbasis stasiun (#22/#23) belum di-ingest. Kualitas udara terikat pada titik stasiun pengukuran, bukan rata-rata pulau."
          },
          "kemenkes-ispa": {
            title: "Laporan Kasus ISPA Mingguan (Surveilans Kesehatan)",
            sourceName: "Surveilans ISPA Kemenkes/Dinkes (Pending #26)",
            units: "cases",
            granularity: "week",
            reason: "Data surveilans ISPA mingguan/bulanan (#26/#27) belum di-ingest. Frekuensi mingguan asli sumber dipertahankan tanpa interpolasi kurva harian."
          }
        };
        var sp = specs[mId] || specs["burned-area"];
        return {
          seriesId: mId + ":" + reg + ":" + win + ":" + aggMode,
          metricId: mId,
          title: sp.title,
          sourceId: mId,
          sourceName: sp.sourceName,
          units: sp.units,
          granularity: sp.granularity,
          aggregationMode: aggMode,
          timezone: tzMode,
          updatedAt: null,
          newestObservationAt: null,
          coverage: {
            scopeId: kab || prov || reg,
            scopeLabel: scopeLabel,
            requestedWindow: win,
            completeness: "unavailable",
            reason: sp.reason
          },
          points: []
        };
      }

      if (prov || kab) {
        return {
          seriesId: "firms-hotspots:" + reg + ":" + prov + ":" + kab,
          metricId: "firms-hotspots",
          title: "Tren Harian Deteksi Panas Satelit (NASA FIRMS VIIRS)",
          sourceId: "firms-hotspots",
          sourceName: "NASA FIRMS NRT VIIRS (S-NPP, NOAA-20, NOAA-21)",
          units: "detections",
          granularity: "day",
          aggregationMode: aggMode,
          timezone: tzMode,
          updatedAt: (firmsMeta && firmsMeta.lastSuccessfulSync) || null,
          newestObservationAt: (firmsMeta && firmsMeta.newestDetectionUtc) || null,
          coverage: {
            scopeId: kab || prov,
            scopeLabel: scopeLabel,
            requestedWindow: win,
            completeness: "unavailable",
            reason: "Shard observasi NASA FIRMS dikelompokkan per 7 wilayah logis (pulau/kepulauan) tanpa poligon batas provinsi/kabupaten. Total pulau tidak pernah disubstitusikan untuk filter sub-pulau."
          },
          points: []
        };
      }

      var rawDaily = [];
      if (hotspotHistory) {
        rawDaily = (tzMode === "Asia/Jakarta" ? hotspotHistory.wibDaily : hotspotHistory.utcDaily) || [];
      } else if (hotspotsManifest && hotspotsManifest.regions) {
        var dateSet = {};
        Object.keys(hotspotsManifest.regions).forEach(function (rKey) {
          ((hotspotsManifest.regions[rKey] && hotspotsManifest.regions[rKey].days) || []).forEach(function (d) {
            if (d && d.date) dateSet[d.date] = true;
          });
        });
        rawDaily = Object.keys(dateSet).sort().map(function (dStr) {
          var regBuckets = {};
          var natCount = 0;
          Object.keys(hotspotsManifest.regions).forEach(function (rKey) {
            var c = regionCountForDate(rKey, dStr);
            regBuckets[rKey] = { count: c, sameTodCount: c };
            natCount += c;
          });
          return {
            date: dStr,
            completeness: "complete",
            todCutoff: "2359",
            national: { count: natCount, sameTodCount: natCount },
            regions: regBuckets
          };
        });
      }

      if (!rawDaily.length) {
        return {
          seriesId: "firms-hotspots:empty",
          metricId: "firms-hotspots",
          title: "Tren Harian Deteksi Panas Satelit (NASA FIRMS VIIRS)",
          sourceId: "firms-hotspots",
          sourceName: "NASA FIRMS NRT VIIRS",
          units: "detections",
          granularity: "day",
          aggregationMode: aggMode,
          timezone: tzMode,
          updatedAt: null,
          newestObservationAt: null,
          coverage: {
            scopeId: reg,
            scopeLabel: scopeLabel,
            requestedWindow: win,
            completeness: "unavailable",
            reason: "Tidak ada riwayat harian FIRMS yang tersedia."
          },
          points: []
        };
      }

      var byDate = {};
      rawDaily.forEach(function (item) {
        if (item && item.date) byDate[item.date] = item;
      });
      var sortedDates = Object.keys(byDate).sort();
      var minDate = new Date(sortedDates[0] + "T00:00:00Z");
      var maxDate = new Date(sortedDates[sortedDates.length - 1] + "T00:00:00Z");
      var continuous = [];
      for (var cur = new Date(minDate.getTime()); cur <= maxDate; cur.setUTCDate(cur.getUTCDate() + 1)) {
        var dIso = cur.toISOString().slice(0, 10);
        var dayObj = byDate[dIso];
        if (!dayObj) {
          continuous.push({
            label: dIso,
            date: dIso,
            observedAt: dIso,
            validFrom: dIso + "T00:00:00",
            validTo: dIso + "T23:59:59",
            rawVal: null,
            sameTodValue: null,
            status: "gap"
          });
        } else {
          var bkt = reg === "indonesia" ? dayObj.national : (dayObj.regions && dayObj.regions[reg]);
          var val = extractBucketFilteredCountJs(bkt, plat, conf, false);
          var todVal = extractBucketFilteredCountJs(bkt, plat, conf, true);
          var st = String(dayObj.completeness || "complete");
          continuous.push({
            label: dIso,
            date: dIso,
            observedAt: (bkt && bkt.newestUtc) || dIso,
            validFrom: dIso + "T00:00:00",
            validTo: dIso + (st === "partial" ? ("T" + String(dayObj.todCutoff || "2359").slice(0, 2) + ":" + String(dayObj.todCutoff || "2359").slice(2, 4) + ":00") : "T23:59:59"),
            rawVal: val,
            sameTodValue: todVal,
            status: st
          });
        }
      }

      for (var i = 0; i < continuous.length; i++) {
        var p = continuous[i];
        if (i === 0 || p.status === "gap" || continuous[i - 1].status === "gap") {
          p.deltaAbs = null;
          p.deltaPct = null;
          p.deltaComparable = false;
        } else if (p.status === "complete" && continuous[i - 1].status === "complete") {
          var dm = computeDeltaMetricsJs(p.rawVal, continuous[i - 1].rawVal);
          p.deltaAbs = dm.deltaAbs;
          p.deltaPct = dm.deltaPct;
          p.deltaComparable = dm.comparable;
        } else {
          p.deltaAbs = null;
          p.deltaPct = null;
          p.deltaComparable = false;
        }
      }

      var completeDays = continuous.filter(function (x) { return x.status === "complete" && x.rawVal != null; });
      var completeDod = null;
      if (completeDays.length >= 2) {
        var cCurr = completeDays[completeDays.length - 1];
        var cPrev = completeDays[completeDays.length - 2];
        var cdm = computeDeltaMetricsJs(cCurr.rawVal, cPrev.rawVal);
        completeDod = {
          currentDate: cCurr.date,
          previousDate: cPrev.date,
          current: cdm.current,
          previous: cdm.previous,
          deltaAbs: cdm.deltaAbs,
          deltaPct: cdm.deltaPct,
          denominatorZero: cdm.denominatorZero,
          comparable: cdm.comparable
        };
      }

      var sameTodComp = null;
      if (continuous.length >= 2 && !plat && !conf) {
        var lPt = continuous[continuous.length - 1];
        var pPt = continuous[continuous.length - 2];
        if (lPt.status !== "gap" && pPt.status !== "gap") {
          var cutoffRaw = (hotspotHistory && (tzMode === "Asia/Jakarta" ? hotspotHistory.wibTodCutoff : hotspotHistory.utcTodCutoff)) || "2359";
          var sdm = computeDeltaMetricsJs(lPt.sameTodValue, pPt.sameTodValue);
          sameTodComp = {
            currentDate: lPt.date,
            previousDate: pPt.date,
            cutoffTime: String(cutoffRaw).slice(0, 2) + ":" + String(cutoffRaw).slice(2, 4) + " " + tzMode,
            latestDayStatus: lPt.status,
            current: sdm.current,
            previous: sdm.previous,
            deltaAbs: sdm.deltaAbs,
            deltaPct: sdm.deltaPct,
            denominatorZero: sdm.denominatorZero,
            comparable: sdm.comparable
          };
        }
      }

      var reqMap = { "1d": 1, "24h": 1, "4d": 4, "7d": 7, "30d": 30, "90d": 90 };
      var reqDays = reqMap[String(win).toLowerCase()] || null;
      var sliced = reqDays ? continuous.slice(-reqDays) : continuous;
      var hasEnough = !reqDays || (continuous.length >= reqDays && sliced.every(function (x) { return x.status !== "gap"; }));
      var allComp = hasEnough && sliced.every(function (x) { return x.status === "complete"; });
      var completeness = allComp ? "complete" : "partial";

      var running = 0;
      var finalPoints = sliced.map(function (pt) {
        if (pt.status === "gap" || pt.rawVal == null) {
          return {
            label: pt.label,
            observedAt: pt.observedAt,
            validFrom: pt.validFrom,
            validTo: pt.validTo,
            value: null,
            incrementalValue: null,
            sameTodValue: null,
            status: "gap",
            deltaAbs: null,
            deltaPct: null
          };
        }
        running += Number(pt.rawVal);
        return {
          label: pt.label,
          observedAt: pt.observedAt,
          validFrom: pt.validFrom,
          validTo: pt.validTo,
          value: aggMode === "cumulative" ? running : Number(pt.rawVal),
          incrementalValue: Number(pt.rawVal),
          sameTodValue: pt.sameTodValue,
          status: pt.status,
          deltaAbs: pt.deltaAbs,
          deltaPct: pt.deltaPct
        };
      });

      var freshnessMeta = (hotspotHistory && hotspotHistory.freshness) || {};
      return {
        seriesId: "firms-hotspots:" + reg + ":" + win + ":" + tzMode + ":" + aggMode,
        metricId: "firms-hotspots",
        title: aggMode === "cumulative"
          ? "Kumulatif Deteksi Panas Satelit (NASA FIRMS VIIRS)"
          : "Tren Harian Deteksi Panas Satelit (NASA FIRMS VIIRS)",
        sourceId: "firms-hotspots",
        sourceName: "NASA FIRMS NRT VIIRS (S-NPP, NOAA-20, NOAA-21)",
        units: "detections",
        granularity: "day",
        aggregationMode: aggMode,
        timezone: tzMode,
        updatedAt: freshnessMeta.lastSuccessfulSync || (firmsMeta && firmsMeta.lastSuccessfulSync) || null,
        lastAttemptedSync: freshnessMeta.lastAttemptedSync || (pipelineStatus && pipelineStatus.lastAttemptedSync) || null,
        newestObservationAt: freshnessMeta.newestDetectionUtc || (firmsMeta && firmsMeta.newestDetectionUtc) || null,
        coverage: {
          scopeId: reg,
          scopeLabel: scopeLabel,
          requestedWindow: win,
          requestedDays: reqDays,
          availableDays: continuous.filter(function (x) { return x.status !== "gap"; }).length,
          completeness: completeness,
          reason: freshnessMeta.reason || null
        },
        completeDayOverDay: completeDod,
        sameTimeOfDayComparison: sameTodComp,
        points: finalPoints
      };
    }

    function formatDeltaBadgeText(deltaObj) {
      if (!deltaObj || !deltaObj.comparable) return "Delta tidak sebanding (interval parsial/kurang)";
      var sign = deltaObj.deltaAbs > 0 ? "+" : "";
      var absStr = sign + Number(deltaObj.deltaAbs).toLocaleString("id-ID");
      if (deltaObj.denominatorZero) {
        return absStr + " (hari sebelumnya 0)";
      }
      var pctSign = deltaObj.deltaPct > 0 ? "+" : "";
      return absStr + " (" + pctSign + deltaObj.deltaPct + "%)";
    }

    function renderReusableTimeSeriesChart(containerEl, seriesEnvelope, opts) {
      if (!containerEl || !seriesEnvelope) return;
      opts = opts || {};
      var deltaStripEl = opts.deltaStripEl || document.getElementById("ts-delta-strip");
      var tooltipEl = opts.tooltipEl || document.getElementById("ts-chart-tooltip");
      var cov = seriesEnvelope.coverage || {};
      var grainLabels = {
        hour: "Per Jam",
        day: "Harian",
        week: "Mingguan (Tanpa Interpolasi Harian)",
        month: "Bulanan"
      };
      var grainText = grainLabels[seriesEnvelope.granularity] || seriesEnvelope.granularity;

      if (deltaStripEl) {
        if (cov.completeness === "unavailable") {
          deltaStripEl.innerHTML =
            '<div class="ts-delta-pill"><span class="delta-label">Status Seri &amp; Grain</span><span class="delta-val" style="color:var(--muted)">DATA UNAVAILABLE · ' + escapeHtml(grainText) + '</span></div>' +
            '<div class="ts-delta-pill"><span class="delta-label">Cakupan Geografi</span><span class="delta-val">' + escapeHtml(cov.scopeLabel || cov.scopeId || "—") + '</span></div>';
        } else {
          var dod = seriesEnvelope.completeDayOverDay;
          var tod = seriesEnvelope.sameTimeOfDayComparison;
          var dodClass = dod && dod.deltaAbs > 0 ? " up" : (dod && dod.deltaAbs < 0 ? " down" : "");
          var todClass = tod && tod.deltaAbs > 0 ? " up" : (tod && tod.deltaAbs < 0 ? " down" : "");
          var dodHtml = dod
            ? ('<div class="ts-delta-pill"><span class="delta-label">Perubahan Hari Penuh (' + escapeHtml(dod.currentDate + " vs " + dod.previousDate) + ')</span>' +
               '<span class="delta-val' + dodClass + '">' + escapeHtml(formatDeltaBadgeText(dod)) + '</span>' +
               '<div style="font-size:10px;color:var(--muted)">' + Number(dod.current).toLocaleString("id-ID") + ' vs ' + Number(dod.previous).toLocaleString("id-ID") + ' ' + escapeHtml(seriesEnvelope.units) + '</div></div>')
            : '<div class="ts-delta-pill"><span class="delta-label">Perubahan Hari Penuh</span><span class="delta-val">Membutuhkan ≥2 hari penuh</span></div>';

          var todHtml = tod
            ? ('<div class="ts-delta-pill"><span class="delta-label">Jam-yang-Sama s/d ' + escapeHtml(tod.cutoffTime) + ' (' + escapeHtml(tod.currentDate + " vs " + tod.previousDate) + ')</span>' +
               '<span class="delta-val' + todClass + '">' + escapeHtml(formatDeltaBadgeText(tod)) + '</span>' +
               '<div style="font-size:10px;color:var(--muted)">' + Number(tod.current).toLocaleString("id-ID") + ' vs ' + Number(tod.previous).toLocaleString("id-ID") + ' · Status hari terbaru: ' + escapeHtml(String(tod.latestDayStatus || "").toUpperCase()) + '</div></div>')
            : '';

          var syncHtml =
            '<div class="ts-delta-pill"><span class="delta-label">Kesegaran &amp; Cakupan (' + escapeHtml(seriesEnvelope.timezone || "UTC") + ')</span>' +
            '<span class="delta-val">' + escapeHtml(String(cov.completeness || "complete").toUpperCase()) + ' · ' + escapeHtml(grainText) + '</span>' +
            '<div style="font-size:10px;color:var(--muted)">Obs terbaru: ' + escapeHtml(seriesEnvelope.newestObservationAt || "—") + ' · Sync: ' + escapeHtml(seriesEnvelope.updatedAt || "—") + '</div></div>';

          deltaStripEl.innerHTML = dodHtml + todHtml + syncHtml;
        }
      }

      if (cov.completeness === "unavailable" || !Array.isArray(seriesEnvelope.points) || !seriesEnvelope.points.length) {
        containerEl.innerHTML =
          '<div style="padding:18px 12px;color:var(--muted);font-family:var(--mono);font-size:12px;border:1px dashed var(--line-2);border-radius:4px">' +
            '<strong style="color:var(--ink)">DATA UNAVAILABLE · ' + escapeHtml(seriesEnvelope.title) + '</strong><br/>' +
            escapeHtml(cov.reason || "Deret waktu belum tersedia untuk cakupan/metrik ini.") +
            '<br/><span style="font-size:10px">Grain sumber: ' + escapeHtml(grainText) + ' · Unit: ' + escapeHtml(seriesEnvelope.units) + ' · Tidak ada kurva harian hasil interpolasi/fabrikasi.</span>' +
          '</div>';
        if (tooltipEl) {
          tooltipEl.innerHTML =
            '<strong>' + escapeHtml(seriesEnvelope.sourceName) + '</strong> · Scope: ' + escapeHtml(cov.scopeLabel || cov.scopeId || "—") +
            ' · Grain: ' + escapeHtml(grainText) + ' · Status: DATA UNAVAILABLE';
        }
        return;
      }

      var pts = seriesEnvelope.points;
      var validVals = pts.filter(function (p) { return p.value != null && isFinite(p.value); }).map(function (p) { return Number(p.value); });
      var maxVal = Math.max.apply(null, validVals.concat([1]));
      var w = 540;
      var h = 152;
      var padL = 46;
      var padR = 14;
      var padT = 18;
      var padB = 30;
      var plotW = w - padL - padR;
      var plotH = h - padT - padB;
      var slotW = plotW / Math.max(pts.length, 1);
      var barW = Math.min(48, Math.max(8, slotW * 0.62));

      var barsSvg = pts.map(function (pt, idx) {
        var x = padL + idx * slotW + (slotW - barW) / 2;
        var shortLabel = String(pt.label || "").slice(5);
        if (pt.status === "gap" || pt.value == null) {
          return (
            '<g class="ts-bar-group" tabindex="0" role="graphics-symbol" data-pt-idx="' + idx + '" aria-label="' + escapeHtml(pt.label + ': GAP / data tidak tersedia') + '" style="cursor:pointer">' +
              '<rect x="' + x.toFixed(1) + '" y="' + padT + '" width="' + barW.toFixed(1) + '" height="' + plotH + '" fill="none" stroke="#5a564f" stroke-dasharray="3 3" rx="2" />' +
              '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + (padT + plotH / 2).toFixed(1) + '" text-anchor="middle" fill="#7a756c" font-family="IBM Plex Mono" font-size="8">GAP</text>' +
              '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + (h - 8) + '" text-anchor="middle" fill="#9a968e" font-family="IBM Plex Mono" font-size="9">' + escapeHtml(shortLabel) + '</text>' +
            '</g>'
          );
        }
        var ratio = Number(pt.value) / maxVal;
        var barH = Math.max(3, Math.round(ratio * plotH));
        var y = padT + (plotH - barH);
        var isSelected = pt.label === currentDate();
        var isPartial = pt.status === "partial";
        var fill = isSelected ? "#e23a14" : (isPartial ? "#d97706" : "#c45c2a");
        var valStr = Number(pt.value).toLocaleString("id-ID");
        var deltaDesc = pt.deltaAbs != null
          ? (" · DoD: " + (pt.deltaAbs > 0 ? "+" : "") + pt.deltaAbs.toLocaleString("id-ID") + (pt.deltaPct != null ? (" (" + (pt.deltaPct > 0 ? "+" : "") + pt.deltaPct + "%)") : ""))
          : (isPartial ? " · PARTIAL DAY" : "");

        return (
          '<g class="ts-bar-group" tabindex="0" role="graphics-symbol" data-pt-idx="' + idx + '" data-date="' + escapeHtml(pt.label) + '" ' +
             'aria-label="' + escapeHtml(pt.label + ': ' + valStr + ' ' + seriesEnvelope.units + deltaDesc) + '" style="cursor:pointer">' +
            '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + barW.toFixed(1) + '" height="' + barH.toFixed(1) + '" fill="' + fill + '" rx="2" ' +
              (isPartial ? 'stroke="#ffffff" stroke-dasharray="2 2" stroke-width="1"' : '') + ' />' +
            (pts.length <= 14
              ? '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + Math.max(11, y - 4).toFixed(1) + '" text-anchor="middle" fill="#ece8df" font-family="IBM Plex Mono" font-size="9">' + escapeHtml(valStr) + '</text>'
              : '') +
            '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + (h - 8) + '" text-anchor="middle" fill="' + (isSelected ? "#e3a008" : "#9a968e") + '" font-family="IBM Plex Mono" font-size="9">' + escapeHtml(shortLabel + (isPartial ? "*" : "")) + '</text>' +
          '</g>'
        );
      }).join("");

      containerEl.innerHTML =
        '<svg viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="' + escapeHtml(seriesEnvelope.title) + '">' +
          '<line x1="' + padL + '" y1="' + padT + '" x2="' + (w - padR) + '" y2="' + padT + '" stroke="#232325" stroke-dasharray="2 3" />' +
          '<line x1="' + padL + '" y1="' + (padT + plotH) + '" x2="' + (w - padR) + '" y2="' + (padT + plotH) + '" stroke="#2f2f33" />' +
          '<text x="4" y="' + (padT + 8) + '" fill="#9a968e" font-family="IBM Plex Mono" font-size="9">' + maxVal.toLocaleString("id-ID") + '</text>' +
          '<text x="4" y="' + (padT + plotH) + '" fill="#9a968e" font-family="IBM Plex Mono" font-size="9">0</text>' +
          barsSvg +
        '</svg>';

      function showPointTooltip(idx) {
        if (!tooltipEl) return;
        var pt = pts[idx];
        if (!pt) return;
        if (pt.status === "gap" || pt.value == null) {
          tooltipEl.innerHTML =
            '<strong>' + escapeHtml(pt.label) + '</strong> · Status: <strong>GAP (Interval Hilang — Bukan 0)</strong><br/>' +
            'Sumber: ' + escapeHtml(seriesEnvelope.sourceName) + ' · Scope: ' + escapeHtml(cov.scopeLabel || cov.scopeId || "—") +
            ' · Grain: ' + escapeHtml(grainText) + ' (' + escapeHtml(seriesEnvelope.timezone || "UTC") + ')';
          return;
        }
        var dInfo = pt.deltaAbs != null
          ? ('Perubahan Hari Penuh: <strong>' + (pt.deltaAbs > 0 ? "+" : "") + pt.deltaAbs.toLocaleString("id-ID") +
             (pt.deltaPct != null ? (' (' + (pt.deltaPct > 0 ? "+" : "") + pt.deltaPct + '%)') : '') + '</strong>')
          : (pt.status === "partial" ? "Status: <strong>PARTIAL DAY (Hari berjalan/belum 24 jam penuh)</strong>" : "Hari pertama pada jendela terpilih");
        tooltipEl.innerHTML =
          '<strong>' + escapeHtml(pt.label) + '</strong> (' + escapeHtml(pt.validFrom + ' s/d ' + pt.validTo + ' ' + (seriesEnvelope.timezone || "UTC")) + ') · ' +
          'Nilai: <strong>' + Number(pt.value).toLocaleString("id-ID") + ' ' + escapeHtml(seriesEnvelope.units) + '</strong> (' + escapeHtml(seriesEnvelope.aggregationMode) + ') · ' + dInfo + '<br/>' +
          'Sumber: ' + escapeHtml(seriesEnvelope.sourceName) + ' · Scope: ' + escapeHtml(cov.scopeLabel || cov.scopeId || "—") +
          ' · Grain: ' + escapeHtml(grainText) + ' · Update: ' + escapeHtml(seriesEnvelope.updatedAt || "—");
      }

      showPointTooltip(pts.length - 1);

      containerEl.querySelectorAll(".ts-bar-group").forEach(function (g) {
        var idx = parseInt(g.getAttribute("data-pt-idx"), 10);
        g.addEventListener("mouseenter", function () { showPointTooltip(idx); });
        g.addEventListener("focus", function () { showPointTooltip(idx); });
        g.addEventListener("click", function () {
          showPointTooltip(idx);
          var dt = g.getAttribute("data-date");
          if (dt && seriesEnvelope.metricId === "firms-hotspots") {
            var dIdx = (state.dates || []).indexOf(dt);
            if (dIdx >= 0) {
              state.dateIdx = dIdx;
              elTime.value = dIdx;
              loadSelectedDate();
            }
          }
        });
      });
    }
"""


def build_patched_index(source: str) -> str:
    use_crlf = "\r\n" in source
    text = source.replace("\r\n", "\n")

    if "function renderReusableTimeSeriesChart(" in text:
        return source
    if "function buildUnifiedConcessionViewModels(" not in text:
        raise RuntimeError(
            "patch_v2_analytics_timeseries_dashboard.py must run after patch_v2_concessions_map_dashboard.py"
        )

    # 1. Inject Wave 3 CSS
    text = replace_once(text, "  </style>", V2_WAVE3_CSS + "\n  </style>", "v2 wave3 CSS")

    # 2. Upgrade #overview-trend-card with metric switcher, aggregation mode, timezone switcher, delta strip & tooltip (#17, #18)
    old_trend_card_inner = (
        '              <div class="overview-widget-h">\n'
        '                <span id="trend-widget-title">Tren Harian Deteksi Panas (NASA FIRMS)</span>\n'
        '                <button type="button" class="kpi-cite-btn" data-metric-id="firms-hotspots">Sumber: VIIRS UTC ⓘ</button>\n'
        '              </div>\n'
        '              <div class="trend-svg-wrap" id="overview-trend-svg"></div>\n'
        '              <div class="kpi-card-meta" id="overview-trend-caption">Frekuensi harian asli sumber; tidak digabung dengan ringkasan SIPONGI.</div>'
    )
    new_trend_card_inner = (
        V2_TREND_CARD_CONTROLS_HTML
        + '\n              <div class="kpi-card-meta" id="overview-trend-caption">Frekuensi asli sumber dipertahankan; tidak digabung dengan SIPONGI dan tidak dikonversi menjadi hektar terbakar.</div>'
    )
    text = replace_once(text, old_trend_card_inner, new_trend_card_inner, "v2 wave3 trend card controls")

    # 3. Load data/hotspots/history.json in Promise.all
    old_promise_all = (
        '      loadJson("data/admin-index.json").catch(function () { return null; }),\n'
        '      loadJson("data/sources-manifest.json").catch(function () { return null; })\n'
        '    ]).then(function (pair) {\n'
        '      boot(pair[0], pair[1], pair[2], pair[3], pair[4], pair[5], pair[6], pair[7], pair[8]);'
    )
    new_promise_all = (
        '      loadJson("data/admin-index.json").catch(function () { return null; }),\n'
        '      loadJson("data/sources-manifest.json").catch(function () { return null; }),\n'
        '      loadJson("data/hotspots/history.json").catch(function () { return null; })\n'
        '    ]).then(function (pair) {\n'
        '      boot(pair[0], pair[1], pair[2], pair[3], pair[4], pair[5], pair[6], pair[7], pair[8], pair[9]);'
    )
    text = replace_once(text, old_promise_all, new_promise_all, "v2 wave3 load history.json")

    text = replace_once(
        text,
        "    function boot(regionsPayload, hotspotsManifest, pipelineStatusPayload, dossierManifest, concessionManifest, affiliatedPayload, holdingCentersPayload, adminIndexPayload, sourcesManifestPayload) {",
        "    function boot(regionsPayload, hotspotsManifest, pipelineStatusPayload, dossierManifest, concessionManifest, affiliatedPayload, holdingCentersPayload, adminIndexPayload, sourcesManifestPayload, hotspotHistoryPayload) {",
        "v2 wave3 boot signature",
    )

    text = replace_once(
        text,
        "    adminIndex = adminIndexPayload;\n    sourcesManifest = sourcesManifestPayload;",
        "    adminIndex = adminIndexPayload;\n    sourcesManifest = sourcesManifestPayload;\n"
        + V2_WAVE3_JS
        + "\n    hotspotHistory = hotspotHistoryPayload;",
        "v2 wave3 JS helpers",
    )

    # 4. Extend state with tsMetric, tsAggMode, tsTimezone
    text = replace_once(
        text,
        '      inspectorTab: "summary",',
        '      inspectorTab: "summary",\n      tsMetric: "firms-hotspots",\n      tsAggMode: "incremental",\n      tsTimezone: "UTC",',
        "v2 wave3 state fields",
    )

    # 5. Upgrade renderOverviewTrendChart() to delegate to buildTypedTimeSeriesForView + renderReusableTimeSeriesChart
    old_render_trend = (
        "    function renderOverviewTrendChart() {\n"
        "      var wrap = document.getElementById(\"overview-trend-svg\");\n"
        "      var cap = document.getElementById(\"overview-trend-caption\");\n"
        "      var titleEl = document.getElementById(\"trend-widget-title\");\n"
        "      if (!wrap) return;"
    )
    new_render_trend = (
        "    function renderOverviewTrendChart() {\n"
        "      var wrap = document.getElementById(\"overview-trend-svg\");\n"
        "      var cap = document.getElementById(\"overview-trend-caption\");\n"
        "      var titleEl = document.getElementById(\"trend-widget-title\");\n"
        "      if (!wrap) return;\n"
        "      var seriesEnv = buildTypedTimeSeriesForView(state.tsMetric || 'firms-hotspots');\n"
        "      if (titleEl) titleEl.textContent = seriesEnv.title + ' · ' + ((seriesEnv.coverage && seriesEnv.coverage.scopeLabel) || 'Indonesia');\n"
        "      renderReusableTimeSeriesChart(wrap, seriesEnv);\n"
        "      var provBtn = document.getElementById('btn-trend-provenance');\n"
        "      if (provBtn) provBtn.setAttribute('data-metric-id', seriesEnv.metricId);\n"
        "      if (cap) {\n"
        "        var fMeta = (hotspotHistory && hotspotHistory.freshness) || {};\n"
        "        cap.textContent = 'Percobaan sync: ' + (fMeta.lastAttemptedSync || '—') + ' · Sync berhasil: ' + (fMeta.lastSuccessfulSync || '—') + ' · Obs satelit terbaru: ' + (fMeta.newestDetectionUtc || '—') + ' (Snapshot Git dapat lebih lama dari artefak runtime GitHub Pages per jam).';\n"
        "      }\n"
        "      return;"
    )
    text = replace_once(text, old_render_trend, new_render_trend, "v2 wave3 renderOverviewTrendChart delegation")

    # 6. Wire Wave 3 UI controls
    wave3_events = r"""
    /* ---------- v2 Wave 3 Events (#16, #17, #18) ---------- */
    document.getElementById("ts-metric-select").addEventListener("change", function (e) {
      state.tsMetric = e.target.value || "firms-hotspots";
      renderOverviewTrendChart();
    });

    document.getElementById("ts-agg-select").addEventListener("change", function (e) {
      state.tsAggMode = e.target.value || "incremental";
      renderOverviewTrendChart();
    });

    document.getElementById("ts-tz-select").addEventListener("change", function (e) {
      state.tsTimezone = e.target.value || "UTC";
      renderOverviewTrendChart();
    });

    document.getElementById("btn-expand-trend-chart").addEventListener("click", function (e) {
      var card = document.getElementById("overview-trend-card");
      if (!card) return;
      var exp = card.classList.toggle("expanded");
      e.target.setAttribute("aria-expanded", exp ? "true" : "false");
      e.target.textContent = exp ? "Perkecil ⤡" : "Perluas ⤢";
    });
"""
    text = replace_once(
        text,
        "    /* ---------- Init ---------- */",
        wave3_events + "\n    /* ---------- Init ---------- */",
        "v2 wave3 events",
    )

    if use_crlf:
        text = text.replace("\n", "\r\n")
    return text


def validate_patched(text: str) -> None:
    required = [
        'id="ts-controls-bar"',
        'id="ts-metric-select"',
        'id="ts-agg-select"',
        'id="ts-tz-select"',
        'id="ts-delta-strip"',
        'id="ts-chart-tooltip"',
        'id="btn-expand-trend-chart"',
        'data/hotspots/history.json',
        'function buildTypedTimeSeriesForView(',
        'function renderReusableTimeSeriesChart(',
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(
            "missing v2 wave 3 integration markers: " + ", ".join(missing)
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
        print("v2 wave 3 analytics & time-series patch: OK")
        return
    if patched != source:
        INDEX.write_text(patched, encoding="utf-8")
        print("patched index.html with MERATUS v2 Wave 3 durable history, deltas, and reusable time-series chart")
    else:
        print("index.html already contains MERATUS v2 Wave 3 patch")


if __name__ == "__main__":
    main()
