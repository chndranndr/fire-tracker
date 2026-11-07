#!/usr/bin/env python3
"""Patch the composed MERATUS dashboard with the v2 P0 foundation (#10, #11, #19).

Run after patch_land_holdings_dashboard.py, patch_region_dashboard.py, and
patch_concession_inventory_dashboard.py. Adds:
- Issue #10: Minimalist responsive dashboard shell with Overview / Map /
  Concessions / Data navigation, 4 primary KPIs, 1 daily trend chart, concise
  7-region comparison summary, and 360px mobile-first layout.
- Issue #11: Shared geographic (Indonesia / region / province / kabupaten) and
  date/window filter state across all views, cross-border concession
  deduplication, UTC vs WIB time semantics, and URL query deep-linking.
- Issue #19: Versioned per-metric source provenance, freshness, and
  missing-data states (fresh / stale / partial / unavailable / estimated /
  official) with a dedicated Provenance & Methodology Drawer.
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


V2_CSS = r"""
    /* === MERATUS v2 Foundation Shell, Shared Filters & Provenance (#10, #11, #19) === */
    html, body { max-width: 100vw; overflow-x: hidden; }
    .app {
      display: grid;
      grid-template-rows: auto auto minmax(0, 1fr) 46px;
      height: 100vh;
      min-height: 100vh;
      max-width: 100vw;
      overflow: hidden;
    }
    .topbar {
      flex-wrap: wrap;
      min-height: 48px;
      padding: 6px 12px;
      gap: 10px;
      z-index: 800;
    }
    .primary-nav {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      background: #0d0d0d;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 2px;
    }
    .primary-nav button {
      background: transparent;
      border: 0;
      padding: 5px 11px;
      cursor: pointer;
      font-weight: 600;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      border-radius: var(--radius);
    }
    .primary-nav button:hover { color: var(--text); }
    .primary-nav button.active {
      background: #1c1a14;
      color: var(--amber);
      box-shadow: inset 0 -2px 0 var(--amber);
    }
    .primary-nav button:focus-visible,
    .mode-toggle button:focus-visible,
    .provenance-btn:focus-visible,
    .filter-reset-btn:focus-visible,
    .shared-filter-bar select:focus-visible,
    .shared-filter-bar input:focus-visible {
      outline: 2px solid var(--amber);
      outline-offset: 1px;
    }
    .provenance-btn {
      background: #141414;
      border: 1px solid var(--line);
      color: var(--text);
      padding: 4px 8px;
      font-family: var(--font-mono);
      font-size: 11px;
      cursor: pointer;
      border-radius: var(--radius);
      white-space: nowrap;
    }
    .provenance-btn:hover { border-color: var(--amber); color: var(--amber); }

    /* Shared Geographic & Date Filter Bar (#11) */
    .shared-filter-bar {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      padding: 6px 12px;
      background: #0e0e0e;
      border-bottom: 1px solid var(--line);
      font-size: 12px;
      z-index: 750;
      min-width: 0;
    }
    .shared-filter-group {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      min-width: 0;
    }
    .shared-filter-group label {
      font-size: 10px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      white-space: nowrap;
    }
    .shared-filter-group select,
    .shared-filter-group input[type="search"] {
      background: #080808;
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 4px 7px;
      font-size: 12px;
      color: var(--text);
      max-width: 170px;
      min-width: 0;
    }
    .tz-badge {
      font-family: var(--font-mono);
      font-size: 10px;
      color: var(--muted);
      padding: 3px 6px;
      border: 1px solid #222;
      background: #0a0a0a;
      white-space: nowrap;
    }
    .filter-scope-pill {
      font-family: var(--font-mono);
      font-size: 11px;
      color: var(--amber);
      background: rgba(227, 160, 8, 0.08);
      border: 1px solid rgba(227, 160, 8, 0.35);
      padding: 2px 7px;
      border-radius: var(--radius);
      max-width: 260px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .filter-reset-btn {
      background: transparent;
      border: 1px solid var(--line);
      color: var(--muted);
      padding: 4px 8px;
      font-size: 11px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      cursor: pointer;
      border-radius: var(--radius);
    }
    .filter-reset-btn:hover { color: var(--text); border-color: var(--amber); }

    /* Availability & Provenance Badges (#19) */
    .avail-badge {
      display: inline-block;
      padding: 1px 5px;
      font-family: var(--font-mono);
      font-size: 9px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      border: 1px solid var(--line);
      border-radius: var(--radius);
    }
    .avail-badge.fresh, .avail-badge.official {
      color: #8ec094;
      border-color: rgba(107, 143, 113, 0.6);
      background: rgba(107, 143, 113, 0.12);
    }
    .avail-badge.curated, .avail-badge.investigative {
      color: #d8b4fe;
      border-color: rgba(192, 132, 252, 0.55);
      background: rgba(192, 132, 252, 0.12);
    }
    .avail-badge.partial, .avail-badge.estimated {
      color: var(--amber);
      border-color: rgba(227, 160, 8, 0.5);
      background: rgba(227, 160, 8, 0.1);
    }
    .avail-badge.stale {
      color: #e07b52;
      border-color: var(--warn);
      background: rgba(184, 92, 56, 0.15);
    }
    .avail-badge.unavailable {
      color: var(--muted);
      border-color: #333;
      background: #141414;
    }

    /* Overview Strip: 4 KPIs + Trend + Regional Comparison (#10) */
    .overview-strip {
      position: absolute;
      top: 8px;
      left: 8px;
      right: 8px;
      z-index: 520;
      display: grid;
      gap: 8px;
      pointer-events: none;
      max-height: calc(100% - 16px);
      overflow-y: auto;
    }
    .overview-strip > * { pointer-events: auto; }
    .app[data-view="map"] .overview-strip,
    .app[data-view="concessions"] .overview-strip,
    .app[data-view="data"] .overview-strip {
      display: none !important;
    }
    .app[data-view="overview"] .findings-banner {
      display: none !important;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }
    .kpi-card {
      background: rgba(14, 14, 14, 0.94);
      border: 1px solid var(--line);
      padding: 8px 10px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-width: 0;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
    }
    .kpi-card-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      margin-bottom: 4px;
    }
    .kpi-card-title {
      font-size: 10px;
      letter-spacing: 0.09em;
      text-transform: uppercase;
      color: var(--muted);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .kpi-card-value {
      font-family: var(--font-mono);
      font-size: 18px;
      font-weight: 500;
      color: var(--text);
      line-height: 1.2;
      overflow-wrap: anywhere;
    }
    .kpi-card-value.fire { color: var(--fire); }
    .kpi-card-value.unavailable {
      font-size: 12px;
      color: var(--muted);
      letter-spacing: 0.05em;
    }
    .kpi-card-meta {
      margin-top: 4px;
      font-size: 11px;
      color: var(--muted);
      line-height: 1.3;
    }
    .kpi-card-foot {
      margin-top: 6px;
      padding-top: 5px;
      border-top: 1px solid #1e1e1e;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      font-family: var(--font-mono);
      font-size: 10px;
      color: var(--muted);
    }
    .kpi-cite-btn {
      background: none;
      border: 0;
      color: var(--amber);
      padding: 0;
      font-family: var(--font-mono);
      font-size: 10px;
      cursor: pointer;
      text-decoration: underline;
      text-underline-offset: 2px;
    }

    .overview-widgets {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
      gap: 8px;
      max-width: 760px;
    }
    .overview-widget {
      background: rgba(14, 14, 14, 0.94);
      border: 1px solid var(--line);
      padding: 8px 10px;
      min-width: 0;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
    }
    .overview-widget-h {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 6px;
      margin-bottom: 6px;
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .trend-svg-wrap {
      width: 100%;
      height: 76px;
    }
    .trend-svg-wrap svg {
      width: 100%;
      height: 100%;
      display: block;
    }
    .regional-mini-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 11px;
    }
    .regional-mini-table th,
    .regional-mini-table td {
      padding: 3px 4px;
      text-align: left;
      border-bottom: 1px solid #1c1c1c;
      white-space: nowrap;
    }
    .regional-mini-table th {
      color: var(--muted);
      font-weight: 500;
      font-size: 10px;
      text-transform: uppercase;
    }
    .regional-mini-table td.num,
    .regional-mini-table th.num {
      text-align: right;
      font-family: var(--font-mono);
    }
    .regional-mini-table tr.region-row { cursor: pointer; }
    .regional-mini-table tr.region-row:hover,
    .regional-mini-table tr.region-row.active {
      background: #1b1914;
      color: var(--amber);
    }

    /* Concessions & Data dedicated view layouts (#10, #19) */
    .app[data-view="concessions"] .main {
      grid-template-columns: minmax(320px, 440px) minmax(0, 1fr) 360px;
    }
    .data-view-panel {
      display: none;
      position: absolute;
      inset: 0;
      z-index: 650;
      background: var(--bg);
      overflow-y: auto;
      padding: 16px;
    }
    .app[data-view="data"] .data-view-panel {
      display: block;
    }
    .data-view-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }
    .env-card {
      background: var(--panel);
      border: 1px solid var(--line);
      padding: 12px;
    }
    .env-card h3 {
      margin: 0 0 4px;
      font-size: 15px;
      color: var(--text);
    }

    /* Provenance Drawer (#19) */
    .provenance-drawer {
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: min(440px, 100vw);
      background: #111;
      border-left: 1px solid var(--line);
      z-index: 1200;
      transform: translateX(102%);
      transition: transform 180ms ease;
      display: flex;
      flex-direction: column;
      box-shadow: -8px 0 28px rgba(0, 0, 0, 0.55);
    }
    .provenance-drawer.open { transform: translateX(0); }
    .provenance-drawer-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 12px;
      color: var(--amber);
    }
    .provenance-drawer-body {
      flex: 1;
      overflow-y: auto;
      padding: 12px 14px 20px;
      font-size: 13px;
      line-height: 1.45;
    }

    @media (max-width: 1100px) {
      .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .overview-widgets { grid-template-columns: 1fr; max-width: 100%; }
    }

    @media (max-width: 960px) {
      .app {
        grid-template-rows: auto auto minmax(0, 1fr) 42px;
        height: 100dvh;
      }
      .shared-filter-bar {
        gap: 6px;
        padding: 5px 8px;
        overflow-x: auto;
        flex-wrap: nowrap;
      }
      .shared-filter-group select { max-width: 125px; }
      .overview-strip {
        position: relative;
        top: 0;
        left: 0;
        right: 0;
        padding: 6px 8px;
        background: rgba(9, 9, 9, 0.92);
        border-bottom: 1px solid var(--line);
        max-height: 44vh;
      }
      .kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px;
      }
    }

    @media (max-width: 420px) {
      .topbar { padding: 4px 8px; gap: 6px; }
      .primary-nav button { padding: 4px 7px; font-size: 11px; }
      .kpi-grid { grid-template-columns: 1fr 1fr; gap: 5px; }
      .kpi-card { padding: 6px 8px; }
      .kpi-card-value { font-size: 15px; }
      .shared-filter-bar { flex-wrap: wrap; overflow-x: hidden; }
      .shared-filter-group { flex: 1 1 calc(50% - 6px); }
      .shared-filter-group select { width: 100%; max-width: none; }
    }
"""


V2_TOPBAR_HTML = r"""      <nav class="primary-nav" id="primary-nav" aria-label="Navigasi tampilan utama">
        <button type="button" id="nav-overview" data-view="overview" class="active">Overview</button>
        <button type="button" id="nav-map" data-view="map">Map</button>
        <button type="button" id="nav-concessions" data-view="concessions">Concessions</button>
        <button type="button" id="nav-data" data-view="data">Data</button>
      </nav>
      <button type="button" class="provenance-btn" id="btn-provenance-drawer" aria-haspopup="dialog" aria-controls="provenance-drawer">Sumber &amp; Status ⓘ</button>
      <div class="mode-toggle" role="group" aria-label="Mode kanvas">"""


V2_SHARED_FILTER_BAR_HTML = r"""    <section class="shared-filter-bar" id="shared-filter-bar" aria-label="Filter geografi dan waktu bersama">
      <div class="shared-filter-group">
        <label for="f-region-shared">Wilayah</label>
        <select id="f-region-shared">
          <option value="indonesia">Indonesia · semua wilayah</option>
        </select>
      </div>
      <div class="shared-filter-group">
        <label for="f-prov-shared">Provinsi</label>
        <select id="f-prov-shared">
          <option value="">Semua provinsi</option>
        </select>
      </div>
      <div class="shared-filter-group">
        <label for="f-kab">Kabupaten/Kota</label>
        <select id="f-kab">
          <option value="">Semua kabupaten/kota</option>
        </select>
      </div>
      <div class="shared-filter-group">
        <label for="f-window">Periode</label>
        <select id="f-window">
          <option value="all">Semua tanggal shard</option>
          <option value="1d">1 hari (tanggal aktif)</option>
          <option value="4d">4 hari terakhir</option>
          <option value="7d">7 hari terakhir</option>
        </select>
      </div>
      <div class="shared-filter-group">
        <label for="f-date-select">Tanggal (UTC)</label>
        <select id="f-date-select">
          <option value="">Memuat…</option>
        </select>
      </div>
      <span class="filter-scope-pill" id="active-scope-pill">Cakupan: Indonesia</span>
      <span class="tz-badge" title="Observasi satelit memakai tanggal UTC; waktu tampil di UI dikonversi ke WIB (Asia/Jakarta, UTC+7)">UTC → WIB (UTC+7)</span>
      <button type="button" class="filter-reset-btn" id="btn-reset-filters">Reset Filter</button>
    </section>"""


V2_OVERVIEW_AND_DRAWER_HTML = r"""        <div class="overview-strip" id="overview-strip" aria-label="Ringkasan utama MERATUS v2">
          <div class="kpi-grid" id="kpi-grid">
            <article class="kpi-card" id="kpi-card-hotspots">
              <div class="kpi-card-head">
                <span class="kpi-card-title">1 · Deteksi Panas (FIRMS)</span>
                <span class="avail-badge fresh" id="kpi-hotspots-badge">FRESH</span>
              </div>
              <div class="kpi-card-value fire" id="kpi-hotspots-val">—</div>
              <div class="kpi-card-meta" id="kpi-hotspots-meta">Memuat observasi VIIRS…</div>
              <div class="kpi-card-foot">
                <span id="kpi-hotspots-period">NASA FIRMS VIIRS</span>
                <button type="button" class="kpi-cite-btn" data-metric-id="firms-hotspots">Provenance ⓘ</button>
              </div>
            </article>

            <article class="kpi-card" id="kpi-card-concessions">
              <div class="kpi-card-head">
                <span class="kpi-card-title">2 · Konsesi Terindeks</span>
                <span class="avail-badge official" id="kpi-concessions-badge">OFFICIAL+GFW</span>
              </div>
              <div class="kpi-card-value" id="kpi-concessions-val">—</div>
              <div class="kpi-card-meta" id="kpi-concessions-meta">Memuat inventaris izin publik…</div>
              <div class="kpi-card-foot">
                <span id="kpi-concessions-period">BIG Satu Peta &amp; GFW</span>
                <button type="button" class="kpi-cite-btn" data-metric-id="concession-inventory">Provenance ⓘ</button>
              </div>
            </article>

            <article class="kpi-card" id="kpi-card-dossiers">
              <div class="kpi-card-head">
                <span class="kpi-card-title">3 · Dossier &amp; Klaim WALHI</span>
                <span class="avail-badge curated" id="kpi-dossiers-badge">CURATED · INVESTIGATIVE</span>
              </div>
              <div class="kpi-card-value" id="kpi-dossiers-val">—</div>
              <div class="kpi-card-meta" id="kpi-dossiers-meta">Memuat cakupan dossier…</div>
              <div class="kpi-card-foot">
                <span id="kpi-dossiers-period">Jan–Jul 2026</span>
                <button type="button" class="kpi-cite-btn" data-metric-id="walhi-dossiers">Provenance ⓘ</button>
              </div>
            </article>

            <article class="kpi-card" id="kpi-card-environmental">
              <div class="kpi-card-head">
                <span class="kpi-card-title">4 · Area Terbakar / Udara / Cuaca</span>
                <span class="avail-badge unavailable" id="kpi-env-badge">UNAVAILABLE</span>
              </div>
              <div class="kpi-card-value unavailable" id="kpi-env-val">DATA UNAVAILABLE</div>
              <div class="kpi-card-meta" id="kpi-env-meta">Titik FIRMS ≠ hektar terbakar. Produk area terbakar (#20), PM2.5 stasiun (#22), &amp; BMKG (#24) belum di-ingest.</div>
              <div class="kpi-card-foot">
                <span>Tanpa angka sampel/estimasi palsu</span>
                <button type="button" class="kpi-cite-btn" data-metric-id="burned-area">Provenance ⓘ</button>
              </div>
            </article>
          </div>

          <div class="overview-widgets">
            <div class="overview-widget" id="overview-trend-card">
              <div class="overview-widget-h">
                <span id="trend-widget-title">Tren Harian Deteksi Panas (NASA FIRMS)</span>
                <button type="button" class="kpi-cite-btn" data-metric-id="firms-hotspots">Sumber: VIIRS UTC ⓘ</button>
              </div>
              <div class="trend-svg-wrap" id="overview-trend-svg"></div>
              <div class="kpi-card-meta" id="overview-trend-caption">Frekuensi harian asli sumber; tidak digabung dengan ringkasan SIPONGI.</div>
            </div>

            <div class="overview-widget" id="overview-regional-card">
              <div class="overview-widget-h">
                <span>Ringkasan 7 Wilayah Logis</span>
                <span class="mono" style="font-size:10px">Klik baris → fokus wilayah</span>
              </div>
              <div id="overview-regional-table-wrap"></div>
            </div>
          </div>
        </div>

        <div class="data-view-panel" id="data-view-panel" aria-label="Katalog sumber data, kesegaran, dan batasan metodologi">
          <div style="max-width:1100px;margin:0 auto">
            <h2 style="margin:0 0 6px;font-size:20px;color:var(--amber);letter-spacing:0.06em;text-transform:uppercase">Katalog Provenance, Kesegaran &amp; Status Data (Kontrak v2 #19)</h2>
            <p style="margin:0 0 12px;color:var(--muted);font-size:14px;line-height:1.45">
              Setiap metrik dan lapisan peta di MERATUS memiliki amplop metadata terstandar dengan pemisahan eksplisit antara <strong>Ketersediaan (Availability)</strong>, <strong>Asal Sumber (Provenance)</strong>, dan <strong>Status Verifikasi</strong>. Nilai <strong>0 teramati</strong> dibedakan secara ketat dari <strong>DATA UNAVAILABLE</strong>.
            </p>
            <div class="data-view-grid" id="data-view-grid"></div>
          </div>
        </div>"""


V2_DRAWER_ASIDE_HTML = r"""    <aside class="provenance-drawer" id="provenance-drawer" role="dialog" aria-modal="false" aria-labelledby="provenance-drawer-title">
      <div class="provenance-drawer-head">
        <span id="provenance-drawer-title">Sumber, Kesegaran &amp; Metodologi</span>
        <button type="button" class="filter-reset-btn" id="btn-close-provenance">Tutup ✕</button>
      </div>
      <div class="provenance-drawer-body" id="provenance-drawer-body"></div>
    </aside>"""


V2_JS_HELPERS = r"""
    /* === MERATUS v2 Foundation Helpers (#10, #11, #19) === */
    var adminIndex = null;
    var sourcesManifest = null;
    var adminBoundariesGeoJson = null;
    var adminBoundaryByProv = {};
    var adminBoundaryByKab = {};
    var adminBoundaryLayer = null;

    var BPS_PROVINCE_MAP = {
      "11": "Aceh", "12": "Sumatera Utara", "13": "Sumatera Barat", "14": "Riau",
      "15": "Jambi", "16": "Sumatera Selatan", "17": "Bengkulu", "18": "Lampung",
      "19": "Kepulauan Bangka Belitung", "21": "Kepulauan Riau", "31": "DKI Jakarta",
      "32": "Jawa Barat", "33": "Jawa Tengah", "34": "DI Yogyakarta", "35": "Jawa Timur",
      "36": "Banten", "51": "Bali", "52": "Nusa Tenggara Barat", "53": "Nusa Tenggara Timur",
      "61": "Kalimantan Barat", "62": "Kalimantan Tengah", "63": "Kalimantan Selatan",
      "64": "Kalimantan Timur", "65": "Kalimantan Utara", "71": "Sulawesi Utara",
      "72": "Sulawesi Tengah", "73": "Sulawesi Selatan", "74": "Sulawesi Tenggara",
      "75": "Gorontalo", "76": "Sulawesi Barat", "81": "Maluku", "82": "Maluku Utara",
      "91": "Papua", "92": "Papua Barat", "93": "Papua Selatan", "94": "Papua Tengah",
      "95": "Papua Pegunungan", "96": "Papua Barat Daya"
    };

    var PROVINCE_LOOKUP = {};
    Object.keys(BPS_PROVINCE_MAP).forEach(function (code) {
      var canonical = BPS_PROVINCE_MAP[code];
      PROVINCE_LOOKUP[code] = canonical;
      PROVINCE_LOOKUP[canonical.toUpperCase()] = canonical;
    });
    PROVINCE_LOOKUP["DAERAH ISTIMEWA YOGYAKARTA"] = "DI Yogyakarta";
    PROVINCE_LOOKUP["D.I. YOGYAKARTA"] = "DI Yogyakarta";
    PROVINCE_LOOKUP["DKI JAKARTA"] = "DKI Jakarta";
    PROVINCE_LOOKUP["BANGKA BELITUNG"] = "Kepulauan Bangka Belitung";

    var KABUPATEN_ALIASES = {
      "PASIR": "Paser",
      "GUNUNGMAS": "Gunung Mas",
      "TANAHBUMBU": "Tanah Bumbu",
      "TANAHLAUT": "Tanah Laut",
      "TANATIDUNG": "Tana Tidung",
      "BOLAANGMONGONDOW": "Bolaang Mongondow",
      "BOLANGMONGONDOW UTARA": "Bolaang Mongondow Utara",
      "BONEBOLANGO": "Bone Bolango",
      "POHUWATU": "Pohuwato",
      "TOLI TOLI": "Tolitoli",
      "KOTA PALANGKARAYA": "Kota Palangka Raya",
      "PALANGKARAYA": "Kota Palangka Raya",
      "PALANGKA RAYA": "Kota Palangka Raya"
    };

    function normalizeProvinceName(token) {
      if (!token) return null;
      var cleaned = String(token).replace(/\s+/g, " ").trim();
      if (!cleaned) return null;
      if (PROVINCE_LOOKUP[cleaned]) return PROVINCE_LOOKUP[cleaned];
      var upper = cleaned.toUpperCase().replace(/^PROVINSI\s+/, "").trim();
      return PROVINCE_LOOKUP[upper] || null;
    }

    function parseRecordProvinces(props, allowedProvinces) {
      if (!props || typeof props !== "object") return [];
      var out = [];
      function collect(raw) {
        if (!raw) return;
        String(raw).split(/[,;/]+/).forEach(function (part) {
          var norm = normalizeProvinceName(part);
          if (norm && (!allowedProvinces || allowedProvinces.indexOf(norm) !== -1)) {
            if (out.indexOf(norm) === -1) out.push(norm);
          }
        });
      }
      collect(props.province);
      collect(props.provinceCode);
      return out;
    }

    function normalizeKabupatenName(token) {
      if (!token) return null;
      var cleaned = String(token).replace(/\s+/g, " ").trim();
      if (!cleaned || cleaned === "-" || cleaned === "—") return null;
      var upper = cleaned.toUpperCase().replace(/^(KABUPATEN|KAB\.)\s+/, "").trim();
      if (!upper || upper === "-" || upper === "DI ATAS 12 MIL LAUT" || upper === "4-12 MIL LAUT") return null;
      if (KABUPATEN_ALIASES[upper]) return KABUPATEN_ALIASES[upper];
      var words = upper.toLowerCase().split(" ").map(function (w) {
        return w ? w.charAt(0).toUpperCase() + w.slice(1) : "";
      }).join(" ");
      return KABUPATEN_ALIASES[words.toUpperCase()] || words;
    }

    function parseRecordKabupaten(props) {
      if (!props || typeof props !== "object") return [];
      var raw = props.district || props.kabupaten;
      if (!raw) return [];
      var text = String(raw)
        .replace(/HULU\s+SUNGAI\s*\(\s*TENGAH\s*,\s*SELATAN\s*\)/gi, "HULU SUNGAI TENGAH, HULU SUNGAI SELATAN")
        .replace(/TANGGAMUS\s*-\s*PRINGSEWU/gi, "TANGGAMUS, PRINGSEWU");
      var out = [];
      text.split(/[,;/&]+/).forEach(function (part) {
        var norm = normalizeKabupatenName(part);
        if (norm && out.indexOf(norm) === -1) out.push(norm);
      });
      return out;
    }

    function resolveKabupatenProvinceJs(kabName) {
      if (!kabName) return null;
      var norm = normalizeKabupatenName(kabName) || kabName;
      if (adminBoundaryByKab[norm] && adminBoundaryByKab[norm].province) {
        return adminBoundaryByKab[norm].province;
      }
      if (adminIndex && adminIndex.kabupatenParentProvince && adminIndex.kabupatenParentProvince[norm]) {
        return adminIndex.kabupatenParentProvince[norm];
      }
      if (adminIndex && adminIndex.regions) {
        var rids = Object.keys(adminIndex.regions);
        for (var i = 0; i < rids.length; i++) {
          var reg = adminIndex.regions[rids[i]];
          var byProv = (reg && reg.kabupatenByProvince) || {};
          var pNames = Object.keys(byProv);
          for (var j = 0; j < pNames.length; j++) {
            var pName = pNames[j];
            if ((byProv[pName] || []).indexOf(norm) !== -1) return pName;
          }
        }
      }
      return null;
    }

    function resolveProvinceRegionJs(provName) {
      var norm = normalizeProvinceName(provName) || provName;
      if (!norm) return null;
      if (adminBoundaryByProv[norm] && adminBoundaryByProv[norm].region) {
        return adminBoundaryByProv[norm].region;
      }
      for (var i = 0; i < regions.length; i++) {
        if ((regions[i].provinces || []).indexOf(norm) !== -1) return regions[i].id;
      }
      return null;
    }

    function computeGeometryBboxJs(geom) {
      if (!geom || !geom.coordinates) return null;
      var minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
      function walk(node) {
        if (!Array.isArray(node)) return;
        if (node.length >= 2 && typeof node[0] === "number" && typeof node[1] === "number") {
          var x = Number(node[0]), y = Number(node[1]);
          if (isFinite(x) && isFinite(y)) {
            if (x < minLon) minLon = x;
            if (x > maxLon) maxLon = x;
            if (y < minLat) minLat = y;
            if (y > maxLat) maxLat = y;
          }
          return;
        }
        for (var i = 0; i < node.length; i++) walk(node[i]);
      }
      walk(geom.coordinates);
      if (!isFinite(minLon)) return null;
      return [minLon, minLat, maxLon, maxLat];
    }

    function indexAdminBoundaries(fc) {
      adminBoundariesGeoJson = fc;
      adminBoundaryByProv = {};
      adminBoundaryByKab = {};
      if (!fc || !Array.isArray(fc.features)) return;
      fc.features.forEach(function (feat) {
        if (!feat || !feat.geometry) return;
        var props = feat.properties || {};
        var bbox = Array.isArray(props.bbox) && props.bbox.length === 4
          ? props.bbox
          : computeGeometryBboxJs(feat.geometry);
        var lvl = props.level || props.adminLevel;
        var pName = props.province || (lvl === "province" ? props.name : null);
        var kName = props.kabupaten || (lvl === "kabupaten" ? props.name : null);
        if (lvl === "province" && pName) {
          adminBoundaryByProv[pName] = {
            name: pName,
            bpsCode: props.bpsCode || null,
            region: props.region || null,
            geometry: feat.geometry,
            feature: feat,
            bbox: bbox
          };
        } else if (lvl === "kabupaten" && kName) {
          adminBoundaryByKab[kName] = {
            name: kName,
            province: props.province || null,
            bpsCode: props.bpsCode || null,
            parentBpsCode: props.parentBpsCode || props.provinceBpsCode || null,
            region: props.region || null,
            geometry: feat.geometry,
            feature: feat,
            bbox: bbox
          };
        }
      });
    }

    function pointInRingJs(lon, lat, ring) {
      if (!Array.isArray(ring) || ring.length < 3) return false;
      var inside = false;
      for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        var xi = Number(ring[i][0]), yi = Number(ring[i][1]);
        var xj = Number(ring[j][0]), yj = Number(ring[j][1]);
        var dy = yj - yi;
        if (Math.abs(dy) < 1e-12) continue;
        var intersect = ((yi > lat) !== (yj > lat)) &&
          (lon <= ((xj - xi) * (lat - yi)) / dy + xi + 1e-9);
        if (intersect) inside = !inside;
      }
      return inside;
    }

    function pointInPolygonCoordsJs(lon, lat, rings) {
      if (!Array.isArray(rings) || !rings.length) return false;
      if (!pointInRingJs(lon, lat, rings[0])) return false;
      for (var h = 1; h < rings.length; h++) {
        if (pointInRingJs(lon, lat, rings[h])) return false;
      }
      return true;
    }

    function pointInBoundaryGeometry(lon, lat, entryOrGeom) {
      if (!entryOrGeom) return false;
      var geom = entryOrGeom.geometry ? entryOrGeom.geometry : entryOrGeom;
      if (!geom || !geom.type) return false;
      var x = Number(lon), y = Number(lat);
      if (!isFinite(x) || !isFinite(y)) return false;
      var bbox = entryOrGeom.bbox || geom.bbox;
      if (Array.isArray(bbox) && bbox.length === 4) {
        if (x < bbox[0] - 1e-6 || x > bbox[2] + 1e-6 ||
            y < bbox[1] - 1e-6 || y > bbox[3] + 1e-6) {
          return false;
        }
      }
      var coords = geom.coordinates || [];
      if (geom.type === "Polygon") {
        return pointInPolygonCoordsJs(x, y, coords);
      }
      if (geom.type === "MultiPolygon") {
        for (var i = 0; i < coords.length; i++) {
          if (pointInPolygonCoordsJs(x, y, coords[i])) return true;
        }
      }
      return false;
    }

    function resolvePointAdmin(p) {
      if (!p || typeof p !== "object") return { province: null, kabupaten: null };
      if (p.province || p.kabupaten) {
        var pNorm = normalizeProvinceName(p.province) || p.province || null;
        var kNorm = normalizeKabupatenName(p.kabupaten) || p.kabupaten || null;
        if (!pNorm && kNorm) pNorm = resolveKabupatenProvinceJs(kNorm);
        return { province: pNorm, kabupaten: kNorm };
      }
      if (p._adminResolved && Object.keys(adminBoundaryByProv).length > 0) {
        return { province: p._adminProv || null, kabupaten: p._adminKab || null };
      }
      var lon = Number(p.lon), lat = Number(p.lat);
      var matchedProv = null;
      var matchedKab = null;
      var provNames = Object.keys(adminBoundaryByProv);
      for (var i = 0; i < provNames.length; i++) {
        var pName = provNames[i];
        if (pointInBoundaryGeometry(lon, lat, adminBoundaryByProv[pName])) {
          matchedProv = pName;
          break;
        }
      }
      var kabNames = Object.keys(adminBoundaryByKab);
      for (var j = 0; j < kabNames.length; j++) {
        var kName = kabNames[j];
        var kEntry = adminBoundaryByKab[kName];
        if (matchedProv && kEntry.province && kEntry.province !== matchedProv) continue;
        if (pointInBoundaryGeometry(lon, lat, kEntry)) {
          matchedKab = kName;
          if (!matchedProv && kEntry.province) matchedProv = kEntry.province;
          break;
        }
      }
      if (provNames.length > 0) {
        p._adminResolved = true;
        p._adminProv = matchedProv;
        p._adminKab = matchedKab;
      }
      return { province: matchedProv, kabupaten: matchedKab };
    }

    function pointMatchesProvince(p, provName) {
      if (!provName) return true;
      var normProv = normalizeProvinceName(provName) || provName;
      if (p && p.province && (normalizeProvinceName(p.province) || p.province) === normProv) return true;
      if (p && p.kabupaten) {
        var kParent = resolveKabupatenProvinceJs(p.kabupaten);
        if (kParent) return kParent === normProv;
      }
      var pEntry = adminBoundaryByProv[normProv];
      if (pEntry) {
        return pointInBoundaryGeometry(p.lon, p.lat, pEntry);
      }
      var resolved = resolvePointAdmin(p);
      return resolved.province === normProv;
    }

    function pointMatchesKabupaten(p, kabName, activeProvName) {
      if (!kabName) return true;
      var normKab = normalizeKabupatenName(kabName) || kabName;
      var kEntry = adminBoundaryByKab[normKab];
      if (activeProvName) {
        var normProv = normalizeProvinceName(activeProvName) || activeProvName;
        var authParent = (kEntry && kEntry.province) || resolveKabupatenProvinceJs(normKab);
        if (authParent && authParent !== normProv) return false;
      }
      if (p && p.kabupaten && (normalizeKabupatenName(p.kabupaten) || p.kabupaten) === normKab) return true;
      if (kEntry) {
        return pointInBoundaryGeometry(p.lon, p.lat, kEntry);
      }
      var resolved = resolvePointAdmin(p);
      return resolved.kabupaten === normKab;
    }

    var _runtimeFreshnessOverrideMs = null;

    function evaluateFirmsFreshnessRuntime(nowMs) {
      if (nowMs != null && isFinite(Number(nowMs))) {
        _runtimeFreshnessOverrideMs = Number(nowMs);
      }
      var refMs = _runtimeFreshnessOverrideMs != null ? _runtimeFreshnessOverrideMs : Date.now();
      var env = (sourcesManifest && sourcesManifest.metrics && sourcesManifest.metrics["firms-hotspots"]) || null;
      var avail = (env && env.availability) || {};
      var lastSync = (pipelineStatus && pipelineStatus.lastSuccessfulSync) ||
                     (firmsMeta && (firmsMeta.lastSuccessfulSync || firmsMeta.retrievedAt)) ||
                     (env && env.updatedAt) ||
                     avail.lastSuccessfulSync ||
                     null;
      var latestObs = (pipelineStatus && pipelineStatus.latestObservationUtc) ||
                      (firmsMeta && (firmsMeta.latestObservationUtc || firmsMeta.newestDetectionUtc)) ||
                      (window.hotspotHistory && window.hotspotHistory.freshness && window.hotspotHistory.freshness.newestDetectionUtc) ||
                      avail.latestObservationUtc ||
                      null;
      var thresholdHours = Number(
        (pipelineStatus && pipelineStatus.staleAfterHours) ||
        avail.staleThresholdHours ||
        6
      );
      if (!isFinite(thresholdHours) || thresholdHours <= 0) thresholdHours = 6;
      var thresholdMinutes = thresholdHours * 60;

      var syncMs = lastSync ? Date.parse(lastSync) : NaN;
      var obsMs = latestObs ? Date.parse(latestObs) : NaN;
      var syncAgeMinutes = isFinite(syncMs) ? Math.max(0, Math.round((refMs - syncMs) / 60000)) : null;
      var observationAgeMinutes = isFinite(obsMs) ? Math.max(0, Math.round((refMs - obsMs) / 60000)) : null;

      var explicitStale = Boolean(
        (pipelineStatus && pipelineStatus.pipelineStatus === "stale") ||
        (firmsMeta && firmsMeta.pipelineStatus === "stale")
      );
      var isStale = explicitStale || syncAgeMinutes === null || syncAgeMinutes > thresholdMinutes;
      var stateStr = usingFallback ? "partial" : (isStale ? "stale" : "fresh");
      var evaluatedIso = new Date(refMs).toISOString();

      var reason = usingFallback
        ? "Menampilkan fallback SIPONGI karena shard FIRMS kosong."
        : (isStale
          ? ("Sinkronisasi FIRMS melewati ambang kesegaran runtime (" +
             (syncAgeMinutes != null ? (syncAgeMinutes + " menit > " + thresholdMinutes + " menit") : "waktu sinkronisasi tidak diketahui") +
             "); menampilkan shard LKG terakhir.")
          : ("Sinkronisasi FIRMS sehat (" + syncAgeMinutes + " menit lalu, ambang " + thresholdMinutes + " menit)."));

      if (pipelineStatus && typeof pipelineStatus === "object") {
        pipelineStatus.stale = isStale;
        pipelineStatus.syncAgeMinutes = syncAgeMinutes;
        pipelineStatus.observationAgeMinutes = observationAgeMinutes;
        pipelineStatus.evaluatedAtUtc = evaluatedIso;
      }
      if (env && env.availability) {
        env.availability.state = stateStr;
        env.availability.fresh = (stateStr === "fresh");
        env.availability.stale = isStale;
        env.availability.lastKnownGood = isStale;
        env.availability.syncAgeMinutes = syncAgeMinutes;
        env.availability.observationAgeMinutes = observationAgeMinutes;
        env.availability.staleThresholdHours = thresholdHours;
        env.availability.evaluatedAtUtc = evaluatedIso;
        env.availability.reason = reason;
      }
      if (window.hotspotHistory && window.hotspotHistory.freshness) {
        window.hotspotHistory.freshness.state = stateStr;
        window.hotspotHistory.freshness.fresh = (stateStr === "fresh");
        window.hotspotHistory.freshness.stale = isStale;
        window.hotspotHistory.freshness.lastKnownGood = isStale;
        window.hotspotHistory.freshness.syncAgeMinutes = syncAgeMinutes;
        window.hotspotHistory.freshness.observationAgeMinutes = observationAgeMinutes;
        window.hotspotHistory.freshness.evaluatedAtUtc = evaluatedIso;
        window.hotspotHistory.freshness.reason = reason;
      }
      return {
        state: stateStr,
        fresh: stateStr === "fresh",
        stale: isStale,
        lastKnownGood: isStale,
        syncAgeMinutes: syncAgeMinutes,
        observationAgeMinutes: observationAgeMinutes,
        staleThresholdHours: thresholdHours,
        lastSuccessfulSync: lastSync,
        latestObservationUtc: latestObs,
        evaluatedAtUtc: evaluatedIso,
        reason: reason
      };
    }

    function scopeHotspotCountForDate(date) {
      if (!date) return 0;
      if (state.kab || state.prov) {
        if (state.kab && state.prov) {
          var authProv = resolveKabupatenProvinceJs(state.kab);
          if (authProv && authProv !== state.prov) return 0;
        }
        var hh = (typeof hotspotHistory !== "undefined" && hotspotHistory) ? hotspotHistory : window.hotspotHistory;
        if (date === currentDate() && Array.isArray(firms) && firms.length > 0 && (state.conf || state.platform || !hh)) {
          return firmsForView().length;
        }
        if (hh && Array.isArray(hh.utcDaily)) {
          for (var i = 0; i < hh.utcDaily.length; i++) {
            var dayEntry = hh.utcDaily[i];
            if (dayEntry && dayEntry.date === date) {
              if (state.kab) {
                var kBucket = dayEntry.byKabupaten && dayEntry.byKabupaten[state.kab];
                if (kBucket) {
                  if (state.conf && kBucket.byConfidence) return Number(kBucket.byConfidence[state.conf] || 0);
                  if (state.platform && kBucket.byPlatform) return Number(kBucket.byPlatform[state.platform] || 0);
                  return Number(kBucket.count || 0);
                }
                return 0;
              }
              if (state.prov) {
                var pBucket = dayEntry.byProvince && dayEntry.byProvince[state.prov];
                if (pBucket) {
                  if (state.conf && pBucket.byConfidence) return Number(pBucket.byConfidence[state.conf] || 0);
                  if (state.platform && pBucket.byPlatform) return Number(pBucket.byPlatform[state.platform] || 0);
                  return Number(pBucket.count || 0);
                }
                return 0;
              }
            }
          }
        }
        if (date === currentDate() && Array.isArray(firms) && firms.length > 0) {
          return firmsForView().length;
        }
        return 0;
      }
      if (date === currentDate() && Array.isArray(firms) && firms.length > 0 && (state.conf || state.platform)) {
        return firmsForView().length;
      }
      return state.region === "indonesia" ? nationalCountForDate(date) : regionCountForDate(state.region, date);
    }

    function updateKabupatenOptions(regionId, provName) {
      var select = document.getElementById("f-kab");
      if (!select) return;
      var kabs = [];
      if (adminIndex && adminIndex.regions) {
        if (regionId === "indonesia") {
          Object.keys(adminIndex.regions).forEach(function (rid) {
            var r = adminIndex.regions[rid];
            if (provName && r.kabupatenByProvince && r.kabupatenByProvince[provName]) {
              kabs = kabs.concat(r.kabupatenByProvince[provName]);
            } else if (!provName && Array.isArray(r.kabupaten)) {
              kabs = kabs.concat(r.kabupaten);
            }
          });
        } else if (adminIndex.regions[regionId]) {
          var regEntry = adminIndex.regions[regionId];
          if (provName && regEntry.kabupatenByProvince && regEntry.kabupatenByProvince[provName]) {
            kabs = regEntry.kabupatenByProvince[provName] || [];
          } else if (!provName) {
            kabs = regEntry.kabupaten || [];
          }
        }
      }
      kabs = Array.from(new Set(kabs)).sort();
      var currentKab = state.kab || "";
      select.innerHTML = '<option value="">Semua kabupaten/kota (' + kabs.length + ')</option>' +
        kabs.map(function (k) {
          return '<option value="' + escapeHtml(k) + '">' + escapeHtml(k) + '</option>';
        }).join("");
      state.kab = kabs.indexOf(currentKab) !== -1 ? currentKab : "";
      select.value = state.kab;
    }

    function syncSharedFilterControls() {
      var regShared = document.getElementById("f-region-shared");
      var regSidebar = document.getElementById("f-region");
      if (regShared && regSidebar) {
        regShared.innerHTML = regSidebar.innerHTML;
        regShared.value = state.region;
      }
      var provShared = document.getElementById("f-prov-shared");
      var provSidebar = document.getElementById("f-prov");
      if (provShared && provSidebar) {
        provShared.innerHTML = provSidebar.innerHTML;
        provShared.value = state.prov;
      }
      updateKabupatenOptions(state.region, state.prov);

      var dateSelect = document.getElementById("f-date-select");
      if (dateSelect) {
        var dates = state.dates || [];
        var cur = currentDate() || "";
        dateSelect.innerHTML = dates.length
          ? dates.slice().reverse().map(function (d) {
              return '<option value="' + escapeHtml(d) + '">' + escapeHtml(d) + '</option>';
            }).join("")
          : '<option value="">Tidak ada tanggal</option>';
        dateSelect.value = cur;
      }

      var winSelect = document.getElementById("f-window");
      if (winSelect) winSelect.value = state.window || "all";

      var pill = document.getElementById("active-scope-pill");
      if (pill) {
        var parts = [
          state.region === "indonesia" ? "Indonesia" : ((regionById[state.region] || {}).label || state.region)
        ];
        if (state.prov) parts.push(state.prov);
        if (state.kab) parts.push(state.kab);
        if (state.sector) parts.push(state.sector);
        if (currentDate()) parts.push(currentDate());
        pill.textContent = "Cakupan: " + parts.join(" · ");
      }
    }

    function syncUrlQuery() {
      if (!window.history || !window.history.replaceState) return;
      var params = new URLSearchParams();
      if (state.view && state.view !== "overview") params.set("view", state.view);
      if (state.region && state.region !== "indonesia") params.set("region", state.region);
      if (state.prov) params.set("prov", state.prov);
      if (state.kab) params.set("kab", state.kab);
      if (currentDate()) params.set("date", currentDate());
      if (state.window && state.window !== "all") params.set("window", state.window);
      if (state.sector) params.set("sector", state.sector);
      if (state.party) params.set("party", state.party);
      if (state.boundary) params.set("boundary", state.boundary);
      if (state.conf) params.set("conf", state.conf);
      if (state.platform) params.set("platform", state.platform);
      if (state.search) params.set("q", state.search);
      var qs = params.toString();
      var nextUrl = window.location.pathname + (qs ? "?" + qs : "") + (window.location.hash || "");
      window.history.replaceState(null, "", nextUrl);
    }

    function applyInitialUrlFilters() {
      var params = new URLSearchParams(window.location.search || "");
      var rawView = (params.get("view") || "overview").toLowerCase();
      state.view = ["overview", "map", "concessions", "data"].indexOf(rawView) !== -1 ? rawView : "overview";

      var rawReg = (params.get("region") || "indonesia").toLowerCase();
      if (rawReg === "indonesia" || regionById[rawReg]) {
        state.region = rawReg;
      } else {
        state.region = "indonesia";
      }

      var rawProv = normalizeProvinceName(params.get("prov"));
      if (rawProv) {
        if (state.region === "indonesia") {
          var pReg = resolveProvinceRegionJs(rawProv);
          if (pReg) state.region = pReg;
        }
        var allowed = state.region === "indonesia"
          ? []
          : ((regionById[state.region] && regionById[state.region].provinces) || []);
        if (!allowed.length || allowed.indexOf(rawProv) !== -1) {
          state.prov = rawProv;
        }
      }

      var rawKab = normalizeKabupatenName(params.get("kab"));
      if (rawKab) {
        var authParentProv = resolveKabupatenProvinceJs(rawKab);
        if (authParentProv && (!state.prov || state.prov === authParentProv)) {
          state.kab = rawKab;
          if (!state.prov) state.prov = authParentProv;
          if (state.region === "indonesia") {
            var kReg = resolveProvinceRegionJs(authParentProv);
            if (kReg) state.region = kReg;
          }
        } else if (!authParentProv) {
          state.kab = rawKab;
        }
      }

      var rawWin = (params.get("window") || "all").toLowerCase();
      state.window = ["1d", "4d", "7d", "all"].indexOf(rawWin) !== -1 ? rawWin : "all";

      var rawSector = params.get("sector") || "";
      if (["Tambang", "PBPH", "Sawit"].indexOf(rawSector) !== -1) {
        state.sector = rawSector;
        var secEl = document.getElementById("f-sector");
        if (secEl) secEl.value = rawSector;
      }
      var rawParty = params.get("party") || "";
      if (["Golkar", "Gerindra", "Kabinet", "PDI-P", "TIDAK"].indexOf(rawParty) !== -1) {
        state.party = rawParty;
        var pEl = document.getElementById("f-party");
        if (pEl) pEl.value = rawParty;
      }
      var rawBound = params.get("boundary") || "";
      if (["OFFICIAL", "GFW", "PERKIRAAN", "none"].indexOf(rawBound) !== -1) {
        state.boundary = rawBound;
        var bEl = document.getElementById("f-boundary");
        if (bEl) bEl.value = rawBound;
      }
      var rawConf = (params.get("conf") || "").toLowerCase();
      if (["high", "nominal", "low"].indexOf(rawConf) !== -1) {
        state.conf = rawConf;
        var cEl = document.getElementById("f-conf");
        if (cEl) cEl.value = rawConf;
      }
      var rawPlat = (params.get("platform") || "").toUpperCase();
      if (["S-NPP", "NOAA-20", "NOAA-21"].indexOf(rawPlat) !== -1) {
        state.platform = rawPlat;
        var plEl = document.getElementById("f-platform");
        if (plEl) plEl.value = rawPlat;
      }
      var rawQ = (params.get("q") || params.get("search") || "").trim();
      if (rawQ) {
        state.search = rawQ.slice(0, 120);
        if (elSearch) elSearch.value = state.search;
      }
      return params.get("date") || null;
    }

    function setView(viewName, skipUrlSync) {
      var valid = ["overview", "map", "concessions", "data"];
      var next = valid.indexOf(viewName) !== -1 ? viewName : "overview";
      state.view = next;
      var appEl = document.querySelector(".app");
      if (appEl) appEl.setAttribute("data-view", next);
      document.querySelectorAll("#primary-nav button[data-view]").forEach(function (btn) {
        var active = btn.getAttribute("data-view") === next;
        btn.classList.toggle("active", active);
        btn.setAttribute("aria-current", active ? "page" : "false");
      });
      if (next === "data") {
        renderDataCatalogView();
      }
      if (state.mode === "map" && typeof map !== "undefined" && map) {
        setTimeout(function () { map.invalidateSize(); }, 60);
      }
      if (!skipUrlSync) syncUrlQuery();
    }

    function activeDatesForWindow() {
      var all = (state.dates || []).slice().sort();
      if (!all.length) return [];
      var cur = currentDate() || all[all.length - 1];
      var curIdx = all.indexOf(cur);
      if (curIdx === -1) curIdx = all.length - 1;
      if (state.window === "1d") return [all[curIdx]];
      var count = state.window === "4d" ? 4 : state.window === "7d" ? 7 : all.length;
      var start = Math.max(0, curIdx - count + 1);
      return all.slice(start, curIdx + 1);
    }

    function computeConcessionSummaryForScope() {
      if (!adminIndex || !adminIndex.regions) {
        return { state: "unavailable", count: null, meta: "Indeks konsesi belum dimuat." };
      }
      if (state.region === "indonesia" && !state.prov && !state.kab) {
        var nat = adminIndex.nationalConcessions || {};
        return {
          state: "partial",
          badge: "OFFICIAL+GFW",
          count: nat.deduplicatedCount || 0,
          meta: (nat.officialCount || 0).toLocaleString("id-ID") + " OFFICIAL (BIG) · " +
                (nat.gfwCount || 0).toLocaleString("id-ID") + " GFW suplemen · terdeduplikasi lintas batas",
          period: "7 wilayah · " + (nat.rawCount || 0).toLocaleString("id-ID") + " poligon sumber"
        };
      }
      var regEntry = adminIndex.regions[state.region];
      if (!regEntry && state.prov) {
        var resolvedReg = resolveProvinceRegionJs(state.prov);
        if (resolvedReg) regEntry = adminIndex.regions[resolvedReg];
      }
      if (!regEntry || !regEntry.concessions) {
        return { state: "unavailable", badge: "UNAVAILABLE", count: null, meta: "Inventaris wilayah tidak tersedia.", period: "—" };
      }
      var c = regEntry.concessions;
      if (state.kab) {
        var authParent = resolveKabupatenProvinceJs(state.kab);
        if (state.prov && authParent && authParent !== state.prov) {
          return {
            state: "unavailable",
            badge: "HIERARCHY MISMATCH",
            count: 0,
            meta: "Kab. " + state.kab + " berada di Prov. " + authParent + ", bukan " + state.prov + ".",
            period: regEntry.label
          };
        }
        var kabCount = (c.byKabupaten && c.byKabupaten[state.kab] != null) ? Number(c.byKabupaten[state.kab]) : 0;
        return {
          state: "partial",
          badge: "PARTIAL (KAB)",
          count: kabCount,
          meta: "Kab. " + state.kab + " · " + (c.unmappedKabupatenCount || 0).toLocaleString("id-ID") +
                " record kehutanan/GFW di wilayah ini tidak memiliki atribut kabupaten",
          period: regEntry.label + " · kode BPS otoritatif"
        };
      }
      if (state.prov) {
        var provCount = (c.byProvince && c.byProvince[state.prov] != null) ? Number(c.byProvince[state.prov]) : 0;
        return {
          state: c.unmappedProvinceCount ? "partial" : "official",
          badge: c.unmappedProvinceCount ? "PARTIAL (PROV)" : "OFFICIAL+GFW",
          count: provCount,
          meta: "Prov. " + state.prov + " · " + (c.crossBorderProvinceCount || 0) +
                " poligon lintas provinsi dihitung terdeduplikasi" +
                (c.unmappedProvinceCount ? " · " + c.unmappedProvinceCount + " tanpa atribut provinsi" : ""),
          period: regEntry.label + " · " + (c.officialCount || 0).toLocaleString("id-ID") + " OFFICIAL"
        };
      }
      return {
        state: c.pipelineStatus === "partial" ? "partial" : "official",
        badge: c.pipelineStatus === "partial" ? "PARTIAL" : "OFFICIAL",
        count: c.deduplicatedCount || 0,
        meta: (c.officialCount || 0).toLocaleString("id-ID") + " OFFICIAL (BIG) · " +
              (c.gfwCount || 0).toLocaleString("id-ID") + " GFW suplemen",
        period: regEntry.label + " · " + (c.rawCount || 0).toLocaleString("id-ID") + " fitur"
      };
    }

    function renderOverviewKpisAndWidgets() {
      var hValEl = document.getElementById("kpi-hotspots-val");
      var hMetaEl = document.getElementById("kpi-hotspots-meta");
      var hBadgeEl = document.getElementById("kpi-hotspots-badge");
      var hPeriodEl = document.getElementById("kpi-hotspots-period");

      var curDate = currentDate();
      var winDates = activeDatesForWindow();
      var freshness = evaluateFirmsFreshnessRuntime();
      var isStale = freshness.stale;

      var dayCount = scopeHotspotCountForDate(curDate);
      var windowTotal = winDates.reduce(function (acc, d) {
        return acc + scopeHotspotCountForDate(d);
      }, 0);
      var allDates = (state.dates || []).slice().sort();
      var curIdx = allDates.indexOf(curDate);
      var prevDate = curIdx > 0 ? allDates[curIdx - 1] : null;
      var isConsecutivePrev = false;
      if (prevDate && curDate) {
        var d1 = Date.parse(prevDate + "T00:00:00Z");
        var d2 = Date.parse(curDate + "T00:00:00Z");
        isConsecutivePrev = isFinite(d1) && isFinite(d2) && Math.round((d2 - d1) / 86400000) === 1;
      }
      var prevCount = isConsecutivePrev ? scopeHotspotCountForDate(prevDate) : null;
      var deltaText = "";
      if (prevCount != null && prevCount > 0) {
        var diff = dayCount - prevCount;
        var pct = ((diff / prevCount) * 100).toFixed(1);
        deltaText = " · " + (diff >= 0 ? "+" : "") + diff.toLocaleString("id-ID") + " (" + (diff >= 0 ? "+" : "") + pct + "% vs " + prevDate + ")";
      } else if (prevDate && !isConsecutivePrev) {
        deltaText = " · jeda tanggal sebelum " + curDate;
      }
      if (hValEl) {
        hValEl.textContent = (state.window === "1d" ? dayCount : windowTotal).toLocaleString("id-ID") + " deteksi";
        hValEl.className = "kpi-card-value fire";
      }
      if (hBadgeEl) {
        var badgeState = usingFallback ? "partial" : (isStale ? "stale" : "fresh");
        var scopeSuffix = state.kab ? " · KAB" : (state.prov ? " · PROV" : "");
        hBadgeEl.textContent = usingFallback
          ? "FALLBACK SIPONGI"
          : (isStale ? ("STALE (LKG)" + scopeSuffix) : (dayCount === 0 ? ("OBSERVED 0" + scopeSuffix) : ("FRESH · NRT" + scopeSuffix)));
        hBadgeEl.className = "avail-badge " + badgeState;
      }
      if (hMetaEl) {
        var scopeLabel = state.kab ? ("Kab. " + state.kab) : (state.prov ? ("Prov. " + state.prov) : ((regionById[state.region] || {}).label || "Indonesia"));
        hMetaEl.textContent = scopeLabel + " (" + (curDate || "—") + "): " + dayCount.toLocaleString("id-ID") + deltaText +
          (freshness.syncAgeMinutes != null ? " · sinkron " + freshness.syncAgeMinutes + "m lalu" : " · S-NPP, NOAA-20, NOAA-21");
      }
      if (hPeriodEl) {
        hPeriodEl.textContent = winDates.length > 1
          ? (winDates[0] + " → " + winDates[winDates.length - 1] + " (" + winDates.length + "d UTC)")
          : ((curDate || "—") + " (UTC)");
      }

      // KPI 2: Concessions
      var concSummary = computeConcessionSummaryForScope();
      var cValEl = document.getElementById("kpi-concessions-val");
      var cMetaEl = document.getElementById("kpi-concessions-meta");
      var cBadgeEl = document.getElementById("kpi-concessions-badge");
      var cPeriodEl = document.getElementById("kpi-concessions-period");
      if (concSummary.state === "unavailable") {
        if (cValEl) { cValEl.textContent = "DATA UNAVAILABLE"; cValEl.className = "kpi-card-value unavailable"; }
        if (cBadgeEl) { cBadgeEl.textContent = "UNAVAILABLE"; cBadgeEl.className = "avail-badge unavailable"; }
      } else {
        if (cValEl) {
          cValEl.textContent = Number(concSummary.count || 0).toLocaleString("id-ID") + " izin";
          cValEl.className = "kpi-card-value";
        }
        if (cBadgeEl) {
          cBadgeEl.textContent = concSummary.badge || "OFFICIAL";
          cBadgeEl.className = "avail-badge " + concSummary.state;
        }
      }
      if (cMetaEl) cMetaEl.textContent = concSummary.meta || "";
      if (cPeriodEl) cPeriodEl.textContent = concSummary.period || "BIG & GFW";

      // KPI 3: Dossiers & WALHI Claims (#7: CURATED / INVESTIGATIVE)
      var dValEl = document.getElementById("kpi-dossiers-val");
      var dMetaEl = document.getElementById("kpi-dossiers-meta");
      var dBadgeEl = document.getElementById("kpi-dossiers-badge");
      var dPeriodEl = document.getElementById("kpi-dossiers-period");
      if (state.region !== "indonesia" && state.region !== "kalimantan") {
        if (dValEl) { dValEl.textContent = "DATA UNAVAILABLE"; dValEl.className = "kpi-card-value unavailable"; }
        if (dBadgeEl) { dBadgeEl.textContent = "UNAVAILABLE"; dBadgeEl.className = "avail-badge unavailable"; }
        if (dMetaEl) dMetaEl.textContent = "Dossier investigatif kurasi saat ini hanya tersedia untuk Kalimantan (bukan 0 klaim).";
        if (dPeriodEl) dPeriodEl.textContent = "Cakupan: Kalimantan saja";
      } else if (state.kab) {
        if (dValEl) { dValEl.textContent = "DATA UNAVAILABLE"; dValEl.className = "kpi-card-value unavailable"; }
        if (dBadgeEl) { dBadgeEl.textContent = "UNAVAILABLE (KAB)"; dBadgeEl.className = "avail-badge unavailable"; }
        if (dMetaEl) dMetaEl.textContent = "Dossier kurasi Kalimantan dicatat pada tingkat provinsi/pulau, bukan per kabupaten (" + state.kab + ").";
        if (dPeriodEl) dPeriodEl.textContent = "Resolusi: Provinsi/Pulau";
      } else {
        var matchingDossiers = filteredDossiers();
        var islandOnlyDossiers = dossiers.filter(function (d) { return d.province === "Kalimantan"; }).length;
        var totalDossierCount = state.region === "indonesia" && !dossiers.length ? 12 : matchingDossiers.length;
        if (dValEl) {
          dValEl.textContent = totalDossierCount + " dossier kurasi";
          dValEl.className = "kpi-card-value";
        }
        if (dBadgeEl) {
          dBadgeEl.textContent = state.prov ? "PARTIAL · INVESTIGATIVE" : "CURATED · INVESTIGATIVE";
          dBadgeEl.className = "avail-badge " + (state.prov ? "partial" : "curated");
        }
        if (dMetaEl) {
          if (state.prov) {
            dMetaEl.textContent = matchingDossiers.length + " dossier investigatif di " + state.prov +
              " (" + islandOnlyDossiers + " dossier sawit berlabel pulau 'Kalimantan' tidak dimasukkan diam-diam).";
          } else {
            dMetaEl.textContent = "Klaim WALHI Kalimantan (kurasi OSINT, bukan inventaris resmi pemerintah): 25.524 / 34.262 hotspot (74%) di konsesi.";
          }
        }
        if (dPeriodEl) dPeriodEl.textContent = "WALHI · 1 Jan – 27 Jul 2026";
      }

      renderOverviewTrendChart();
      renderOverviewRegionalTable();
    }

    function renderOverviewTrendChart() {
      var wrap = document.getElementById("overview-trend-svg");
      var cap = document.getElementById("overview-trend-caption");
      var titleEl = document.getElementById("trend-widget-title");
      if (!wrap) return;
      var scopeName = state.kab
        ? ("Kab. " + state.kab)
        : (state.prov
          ? ("Prov. " + state.prov)
          : (state.region === "indonesia" ? "Indonesia" : ((regionById[state.region] || {}).label || state.region)));
      if (titleEl) titleEl.textContent = "Tren Harian Deteksi Panas · " + scopeName;

      var dates = activeDatesForWindow();
      if (!dates.length) {
        wrap.innerHTML = '<div class="insp-empty">Tidak ada data tanggal FIRMS.</div>';
        return;
      }
      var series = dates.map(function (d) {
        return { date: d, count: scopeHotspotCountForDate(d) };
      });
      var maxVal = series.reduce(function (m, item) { return Math.max(m, item.count); }, 1);
      var w = 360, h = 74, padL = 8, padR = 8, padT = 14, padB = 18;
      var plotW = w - padL - padR;
      var plotH = h - padT - padB;
      var barW = Math.max(16, Math.min(54, Math.floor(plotW / Math.max(1, series.length)) - 10));
      var step = series.length > 1 ? (plotW - barW) / (series.length - 1) : 0;

      var bars = series.map(function (item, idx) {
        var x = series.length === 1 ? (w - barW) / 2 : padL + idx * step;
        var bh = Math.max(3, Math.round((item.count / maxVal) * plotH));
        var y = padT + (plotH - bh);
        var isCurrent = item.date === currentDate();
        var fill = isCurrent ? "#e23a14" : "#8b341c";
        var stroke = isCurrent ? "#e3a008" : "none";
        return '<g class="trend-bar" data-date="' + escapeHtml(item.date) + '" style="cursor:pointer">' +
          '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + barW + '" height="' + bh + '" fill="' + fill + '" stroke="' + stroke + '" stroke-width="1" rx="1"/>' +
          '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + (y - 3).toFixed(1) + '" fill="#d8d4cc" font-family="IBM Plex Mono, monospace" font-size="9" text-anchor="middle">' + item.count.toLocaleString("id-ID") + '</text>' +
          '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + (h - 4) + '" fill="' + (isCurrent ? "#e3a008" : "#7a756c") + '" font-family="IBM Plex Mono, monospace" font-size="9" text-anchor="middle">' + escapeHtml(item.date.slice(5)) + '</text>' +
        '</g>';
      }).join("");

      wrap.innerHTML = '<svg viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="Grafik tren harian deteksi panas FIRMS">' + bars + '</svg>';
      wrap.querySelectorAll(".trend-bar").forEach(function (g) {
        g.addEventListener("click", function () {
          var clickedDate = g.getAttribute("data-date");
          var idx = (state.dates || []).indexOf(clickedDate);
          if (idx >= 0) {
            state.dateIdx = idx;
            elTime.value = idx;
            loadSelectedDate();
          }
        });
      });
      if (cap) {
        cap.textContent = "Sumber: NASA FIRMS VIIRS · Cakupan: " + scopeName + " (point-in-polygon admin BPS) · Klik batang untuk memilih tanggal.";
      }
    }

    function renderOverviewRegionalTable() {
      var wrap = document.getElementById("overview-regional-table-wrap");
      if (!wrap) return;
      var curDate = currentDate();
      var allDates = (state.dates || []).slice().sort();
      var curIdx = allDates.indexOf(curDate);
      var prevDate = curIdx > 0 ? allDates[curIdx - 1] : null;
      var isConsecutivePrev = false;
      if (prevDate && curDate) {
        var d1 = Date.parse(prevDate + "T00:00:00Z");
        var d2 = Date.parse(curDate + "T00:00:00Z");
        isConsecutivePrev = isFinite(d1) && isFinite(d2) && Math.round((d2 - d1) / 86400000) === 1;
      }

      var rows = regions.map(function (r) {
        var today = regionCountForDate(r.id, curDate);
        var prev = isConsecutivePrev ? regionCountForDate(r.id, prevDate) : null;
        var diff = prev != null ? today - prev : null;
        var diffStr = diff == null ? "—" : ((diff >= 0 ? "+" : "") + diff.toLocaleString("id-ID"));
        var invCount = (adminIndex && adminIndex.regions && adminIndex.regions[r.id] && adminIndex.regions[r.id].concessions)
          ? adminIndex.regions[r.id].concessions.deduplicatedCount
          : ((concessionManifest && concessionManifest.regions && concessionManifest.regions[r.id]) ? concessionManifest.regions[r.id].inventoryCount : 0);
        var activeCls = state.region === r.id ? " active" : "";
        return '<tr class="region-row' + activeCls + '" data-region="' + escapeHtml(r.id) + '" tabindex="0">' +
          '<td>' + escapeHtml(r.label) + '</td>' +
          '<td class="num">' + today.toLocaleString("id-ID") + '</td>' +
          '<td class="num">' + diffStr + '</td>' +
          '<td class="num">' + Number(invCount || 0).toLocaleString("id-ID") + '</td>' +
          '<td><span class="avail-badge ' + (r.id === "kalimantan" ? "curated" : "unavailable") + '">' + (r.id === "kalimantan" ? "12 DOSSIER (CURATED)" : "INV ONLY") + '</span></td>' +
        '</tr>';
      }).join("");

      wrap.innerHTML = '<table class="regional-mini-table" aria-label="Perbandingan 7 wilayah Indonesia">' +
        '<thead><tr><th>Wilayah</th><th class="num">FIRMS (' + escapeHtml((curDate || "").slice(5) || "Hari") + ')</th><th class="num">Δ 24j</th><th class="num">Konsesi</th><th>Dossier</th></tr></thead>' +
        '<tbody>' + rows + '</tbody></table>';

      wrap.querySelectorAll("tr.region-row").forEach(function (tr) {
        function activate() {
          var rid = tr.getAttribute("data-region");
          if (rid) selectRegion(rid, currentDate());
        }
        tr.addEventListener("click", activate);
        tr.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(); }
        });
      });
    }

    function renderMetricEnvelopeHtml(env) {
      if (!env) return '<div class="insp-empty">Metadata metrik tidak ditemukan.</div>';
      if (env.id === "firms-hotspots") evaluateFirmsFreshnessRuntime();
      var avail = env.availability || {};
      var prov = env.provenance || {};
      var verif = env.verification || {};
      var obs = env.observationPeriod || {};
      var scope = env.scope || {};
      var valText = avail.state === "unavailable"
        ? "DATA UNAVAILABLE (Bukan 0)"
        : (env.value != null ? Number(env.value).toLocaleString("id-ID") + " " + (env.units || "") : "—");
      var caveatsHtml = (env.caveats || []).map(function (c) {
        return '<div class="caveat">' + escapeHtml(c) + '</div>';
      }).join("");
      var provCategory = prov.category || avail.quality || "UNAVAILABLE";
      var badgeProvCat = provCategory === "civil_society_investigative" ? "INVESTIGATIVE" : provCategory;
      var verifStatus = verif.status || (badgeProvCat === "OFFICIAL" ? "VERIFIED_OFFICIAL" : (badgeProvCat === "INVESTIGATIVE" || badgeProvCat === "CURATED" ? "CURATED_OSINT" : "UNVERIFIED"));
      var verifBasis = verif.basis || "Lihat metodologi sumber";
      return '<article class="env-card" data-envelope-id="' + escapeHtml(env.id) + '">' +
        '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px">' +
          '<span class="tag amber">' + escapeHtml(env.layerType || "Layer") + '</span>' +
          '<span class="avail-badge ' + escapeHtml(avail.state || "unavailable") + '">' + escapeHtml((avail.state || "unavailable").toUpperCase()) + ' · ' + escapeHtml(badgeProvCat) + '</span>' +
        '</div>' +
        '<h3>' + escapeHtml(env.title) + '</h3>' +
        '<dl class="kv">' +
          '<dt>Nilai saat ini</dt><dd>' + escapeHtml(valText) + '</dd>' +
          '<dt>Ketersediaan (Availability)</dt><dd>' + escapeHtml((avail.state || "unavailable").toUpperCase()) + ' — ' + escapeHtml(avail.reason || "Sehat & tervalidasi") + '</dd>' +
          '<dt>Asal Sumber (Provenance)</dt><dd><strong>' + escapeHtml(provCategory) + '</strong> · <a href="' + escapeHtml(prov.sourceUrl || env.url || "#") + '" target="_blank" rel="noopener">' + escapeHtml(prov.source || env.source) + ' ↗</a></dd>' +
          '<dt>Status Verifikasi (Verification)</dt><dd><strong>' + escapeHtml(verifStatus) + '</strong> — ' + escapeHtml(verifBasis) + '</dd>' +
          '<dt>Produk / versi</dt><dd>' + escapeHtml(env.product) + ' (v' + escapeHtml(env.version) + ')</dd>' +
          '<dt>Periode observasi</dt><dd>' + escapeHtml(obs.label || "—") + '</dd>' +
          '<dt>Sinkronisasi</dt><dd>' + escapeHtml(env.updatedAt ? formatWib(env.updatedAt, true) + " (" + env.updatedAt + ")" : "Belum tersedia") + '</dd>' +
          '<dt>Resolusi cakupan</dt><dd>' + escapeHtml((scope.supportedGranularities || []).join(", ")) + '</dd>' +
          '<dt>Frekuensi / unit</dt><dd>' + escapeHtml(env.granularity + " · " + env.units) + '</dd>' +
        '</dl>' +
        caveatsHtml +
      '</article>';
    }

    function renderDataCatalogView() {
      var grid = document.getElementById("data-view-grid");
      if (!grid) return;
      evaluateFirmsFreshnessRuntime();
      var metrics = (sourcesManifest && sourcesManifest.metrics) ? sourcesManifest.metrics : {};
      var keys = Object.keys(metrics);
      if (!keys.length) {
        grid.innerHTML = '<div class="insp-empty">Memuat katalog provenance data/sources-manifest.json…</div>';
        return;
      }
      grid.innerHTML = keys.map(function (k) { return renderMetricEnvelopeHtml(metrics[k]); }).join("");
    }

    function openProvenanceDrawer(metricId) {
      var drawer = document.getElementById("provenance-drawer");
      var body = document.getElementById("provenance-drawer-body");
      var title = document.getElementById("provenance-drawer-title");
      if (!drawer || !body) return;
      evaluateFirmsFreshnessRuntime();
      var metrics = (sourcesManifest && sourcesManifest.metrics) ? sourcesManifest.metrics : {};
      if (metricId && metrics[metricId]) {
        if (title) title.textContent = "Provenance · " + metrics[metricId].title;
        body.innerHTML = renderMetricEnvelopeHtml(metrics[metricId]) +
          '<div style="margin-top:12px"><button type="button" class="filter-reset-btn" id="btn-show-all-envelopes">Lihat Semua Sumber Data (8)</button></div>';
        var allBtn = document.getElementById("btn-show-all-envelopes");
        if (allBtn) {
          allBtn.addEventListener("click", function () { openProvenanceDrawer(null); });
        }
      } else {
        if (title) title.textContent = "Katalog Sumber & Kesegaran Data";
        var keys = Object.keys(metrics);
        body.innerHTML = keys.map(function (k) { return renderMetricEnvelopeHtml(metrics[k]); }).join("");
      }
      drawer.classList.add("open");
    }

    function closeProvenanceDrawer() {
      var drawer = document.getElementById("provenance-drawer");
      if (drawer) drawer.classList.remove("open");
    }
"""


def build_patched_index(source: str) -> str:
    use_crlf = "\r\n" in source
    text = source.replace("\r\n", "\n")
    if "function setView(viewName, skipUrlSync)" in text:
        return source
    if "function refreshConcessionInventoryLayer()" not in text:
        raise RuntimeError(
            "v2 foundation patch must run after patch_concession_inventory_dashboard.py"
        )

    # 1. Inject v2 CSS before </style>
    text = replace_once(text, "  </style>", V2_CSS + "\n  </style>", "v2 CSS")

    # 2. Inject Primary Navigation + Provenance button in topbar
    text = replace_once(
        text,
        '      <div class="mode-toggle" role="group" aria-label="Mode kanvas">',
        V2_TOPBAR_HTML,
        "v2 topbar navigation",
    )

    # 3. Inject Shared Geographic & Date Filter Bar right after </header>
    text = replace_once(
        text,
        "    </header>\n\n    <div class=\"main\">",
        "    </header>\n\n" + V2_SHARED_FILTER_BAR_HTML + "\n\n    <div class=\"main\">",
        "v2 shared filter bar",
    )

    # 4. Inject Overview KPI/Trend/Regional strip and Data Catalog panel inside .canvas-wrap, plus Provenance Drawer before </div> of .app
    text = replace_once(
        text,
        '        <div class="findings-banner" id="findings-banner" aria-label="Ringkasan klaim WALHI">',
        V2_OVERVIEW_AND_DRAWER_HTML
        + '\n        <div class="findings-banner" id="findings-banner" aria-label="Ringkasan klaim WALHI">',
        "v2 overview strip and data view",
    )

    text = replace_once(
        text,
        "    <footer class=\"scrubber\">",
        V2_DRAWER_ASIDE_HTML + "\n\n    <footer class=\"scrubber\">",
        "v2 provenance drawer aside",
    )

    # 5. Load data/admin-index.json, data/sources-manifest.json, and data/admin-boundaries.geojson in initial Promise.all
    old_loader = (
        '      loadJson("data/affiliated-land-holdings.json").catch(function () { return { meta: {}, people: [], holdings: [] }; }),\n'
        '      loadJson("data/affiliated-land-display-centers.json").catch(function () { return { meta: {}, centers: {} }; })\n'
        '    ]).then(function (pair) {\n'
        '      boot(pair[0], pair[1], pair[2], pair[3], pair[4], pair[5], pair[6]);'
    )
    new_loader = (
        '      loadJson("data/affiliated-land-holdings.json").catch(function () { return { meta: {}, people: [], holdings: [] }; }),\n'
        '      loadJson("data/affiliated-land-display-centers.json").catch(function () { return { meta: {}, centers: {} }; }),\n'
        '      loadJson("data/admin-index.json").catch(function () { return null; }),\n'
        '      loadJson("data/sources-manifest.json").catch(function () { return null; }),\n'
        '      loadJson("data/admin-boundaries.geojson").catch(function () { return null; })\n'
        '    ]).then(function (pair) {\n'
        '      boot(pair[0], pair[1], pair[2], pair[3], pair[4], pair[5], pair[6], pair[7], pair[8], pair[9]);'
    )
    text = replace_once(text, old_loader, new_loader, "v2 manifest loader")

    text = replace_once(
        text,
        "    function boot(regionsPayload, hotspotsManifest, pipelineStatusPayload, dossierManifest, concessionManifest, affiliatedPayload, holdingCentersPayload) {",
        "    function boot(regionsPayload, hotspotsManifest, pipelineStatusPayload, dossierManifest, concessionManifest, affiliatedPayload, holdingCentersPayload, adminIndexPayload, sourcesManifestPayload, adminBoundariesPayload) {",
        "v2 boot signature",
    )

    text = replace_once(
        text,
        "    var currentConcessionInventoryManifest = null;",
        "    var currentConcessionInventoryManifest = null;"
        + V2_JS_HELPERS
        + "\n    adminIndex = adminIndexPayload;\n    sourcesManifest = sourcesManifestPayload;\n    indexAdminBoundaries(adminBoundariesPayload);\n    evaluateFirmsFreshnessRuntime();",
        "v2 JS helpers",
    )

    # 6. Extend state with view, kab, window
    text = replace_once(
        text,
        '      region: "indonesia",\n      prov: "",',
        '      view: "overview",\n      region: "indonesia",\n      prov: "",\n      kab: "",\n      window: "all",',
        "v2 state fields",
    )

    # 7. Patch firmsForView() and refreshFirmsLayer() for administrative point-in-polygon filtering (#3)
    old_firms_for_view = (
        "    function firmsForView() {\n"
        "      var d = currentDate();\n"
        "      return firms.filter(function (p) {\n"
        "        if (d && p.date !== d) return false;\n"
        "        if (state.conf && p.conf !== state.conf) return false;\n"
        "        if (state.platform && normalizePlatform(p) !== state.platform) return false;\n"
        "        return true;\n"
        "      });\n"
        "    }"
    )
    new_firms_for_view = (
        "    function firmsForView() {\n"
        "      var d = currentDate();\n"
        "      return firms.filter(function (p) {\n"
        "        if (d && p.date !== d) return false;\n"
        "        if (state.conf && p.conf !== state.conf) return false;\n"
        "        if (state.platform && normalizePlatform(p) !== state.platform) return false;\n"
        "        if (state.prov && !pointMatchesProvince(p, state.prov)) return false;\n"
        "        if (state.kab && !pointMatchesKabupaten(p, state.kab, state.prov)) return false;\n"
        "        return true;\n"
        "      });\n"
        "    }"
    )
    text = replace_once(text, old_firms_for_view, new_firms_for_view, "v2 firmsForView admin filter")

    old_legacy_pibg = (
        "    function pointInBoundaryGeometry(lon, lat, geometry) {\n"
        "      if (!geometry) return false;\n"
        "      if (geometry.type === \"Polygon\") return pointInBoundaryPolygon(lon, lat, geometry.coordinates || []);\n"
        "      if (geometry.type === \"MultiPolygon\") return (geometry.coordinates || []).some(function (polygon) { return pointInBoundaryPolygon(lon, lat, polygon); });\n"
        "      return false;\n"
        "    }"
    )
    new_upgraded_pibg = (
        "    function pointInBoundaryGeometry(lon, lat, entryOrGeom) {\n"
        "      if (!entryOrGeom) return false;\n"
        "      var geometry = entryOrGeom.geometry ? entryOrGeom.geometry : entryOrGeom;\n"
        "      if (!geometry || !geometry.type) return false;\n"
        "      var x = Number(lon), y = Number(lat);\n"
        "      if (!isFinite(x) || !isFinite(y)) return false;\n"
        "      var bbox = entryOrGeom.bbox || geometry.bbox;\n"
        "      if (Array.isArray(bbox) && bbox.length === 4) {\n"
        "        if (x < bbox[0] - 1e-6 || x > bbox[2] + 1e-6 || y < bbox[1] - 1e-6 || y > bbox[3] + 1e-6) return false;\n"
        "      }\n"
        "      if (geometry.type === \"Polygon\") return pointInBoundaryPolygon(x, y, geometry.coordinates || []);\n"
        "      if (geometry.type === \"MultiPolygon\") return (geometry.coordinates || []).some(function (polygon) { return pointInBoundaryPolygon(x, y, polygon); });\n"
        "      return false;\n"
        "    }"
    )
    if old_legacy_pibg in text:
        text = replace_once(
            text,
            old_legacy_pibg,
            new_upgraded_pibg,
            "v2 upgrade pointInBoundaryGeometry",
        )

    old_refresh_firms = (
        "    function refreshFirmsLayer() {\n"
        "      clusterGroup.clearLayers();\n"
        "      nationalSummaryLayer.clearLayers();\n"
        "      if (state.region === \"indonesia\") {\n"
        "        refreshNationalSummary();\n"
        "        var nationalCount = nationalCountForDate(currentDate());\n"
        "        elTimeLabel.textContent = (currentDate() || \"—\") + \" · \" + nationalCount.toLocaleString(\"id-ID\") + \" detections · ringkasan 7 region\";\n"
        "        return;\n"
        "      }\n"
        "      var pts = firmsForView();\n"
        "      var markers = [];\n"
        "      for (var i = 0; i < pts.length; i++) {\n"
        "        (function (p) {\n"
        "          var m = L.marker([p.lat, p.lon], { icon: fireIcon(p.conf) });\n"
        "          m.on(\"click\", function () {\n"
        "            showFirmsPoint(p, nearestConcession(p.lat, p.lon));\n"
        "          });\n"
        "          markers.push(m);\n"
        "        })(pts[i]);\n"
        "      }\n"
        "      clusterGroup.addLayers(markers);\n"
        "      var scope = (regionById[state.region] || {}).label || state.region;\n"
        "      elTimeLabel.textContent = (currentDate() || \"—\") + \" · \" + pts.length.toLocaleString(\"id-ID\") + \" satellite detections · \" + scope +\n"
        "        (state.conf ? \" · \" + state.conf : \"\") + (state.platform ? \" · \" + state.platform : \"\");\n"
        "    }"
    )
    new_refresh_firms = (
        "    function refreshAdminBoundaryHighlight() {\n"
        "      if (!adminBoundaryLayer && typeof map !== \"undefined\" && map && typeof L !== \"undefined\" && L.layerGroup) {\n"
        "        adminBoundaryLayer = L.layerGroup().addTo(map);\n"
        "      }\n"
        "      if (!adminBoundaryLayer) return;\n"
        "      adminBoundaryLayer.clearLayers();\n"
        "      var activeEntry = state.kab\n"
        "        ? adminBoundaryByKab[state.kab]\n"
        "        : (state.prov ? adminBoundaryByProv[state.prov] : null);\n"
        "      if (activeEntry && activeEntry.feature) {\n"
        "        L.geoJSON(activeEntry.feature, {\n"
        "          style: {\n"
        "            color: \"#38bdf8\",\n"
        "            weight: 1.8,\n"
        "            opacity: 0.85,\n"
        "            fillColor: \"#38bdf8\",\n"
        "            fillOpacity: 0.05,\n"
        "            dashArray: \"4 4\"\n"
        "          }\n"
        "        }).addTo(adminBoundaryLayer);\n"
        "      }\n"
        "    }\n\n"
        "    function refreshFirmsLayer() {\n"
        "      clusterGroup.clearLayers();\n"
        "      nationalSummaryLayer.clearLayers();\n"
        "      refreshAdminBoundaryHighlight();\n"
        "      if (state.showFirms === false) {\n"
        "        elTimeLabel.textContent = (currentDate() || '—') + ' · Layer Hotspots FIRMS dinonaktifkan';\n"
        "        return;\n"
        "      }\n"
        "      if (state.region === \"indonesia\" && !state.prov && !state.kab) {\n"
        "        refreshNationalSummary();\n"
        "        var nationalCount = nationalCountForDate(currentDate());\n"
        "        elTimeLabel.textContent = (currentDate() || \"—\") + \" · \" + nationalCount.toLocaleString(\"id-ID\") + \" detections · ringkasan 7 region\";\n"
        "        return;\n"
        "      }\n"
        "      var pts = firmsForView();\n"
        "      var markers = [];\n"
        "      for (var i = 0; i < pts.length; i++) {\n"
        "        (function (p) {\n"
        "          var m = L.marker([p.lat, p.lon], { icon: fireIcon(p.conf) });\n"
        "          m.on(\"click\", function () {\n"
        "            showFirmsPoint(p, nearestConcession(p.lat, p.lon));\n"
        "          });\n"
        "          markers.push(m);\n"
        "        })(pts[i]);\n"
        "      }\n"
        "      clusterGroup.addLayers(markers);\n"
        "      var scope = state.kab\n"
        "        ? (\"Kab. \" + state.kab)\n"
        "        : (state.prov ? (\"Prov. \" + state.prov) : ((regionById[state.region] || {}).label || state.region));\n"
        "      elTimeLabel.textContent = (currentDate() || \"—\") + \" · \" + pts.length.toLocaleString(\"id-ID\") + \" satellite detections · \" + scope +\n"
        "        (state.conf ? \" · \" + state.conf : \"\") + (state.platform ? \" · \" + state.platform : \"\");\n"
        "    }"
    )
    text = replace_once(text, old_refresh_firms, new_refresh_firms, "v2 refreshFirmsLayer admin sync")

    # 8. Enhance inventoryEntriesForView & refreshConcessionInventoryLayer to respect state.prov and state.kab with authoritative hierarchy (#4)
    old_inv_refresh = (
        "          var gj = L.geoJSON(payload || { type: \"FeatureCollection\", features: [] }, {\n"
        "            style: inventoryStyle,"
    )
    new_inv_refresh = (
        "          var rawFeatures = (payload && Array.isArray(payload.features)) ? payload.features : [];\n"
        "          var allowedProvs = (regionById[state.region] && regionById[state.region].provinces) || null;\n"
        "          var filteredFeatures = rawFeatures.filter(function (feat) {\n"
        "            var fp = (feat && feat.properties) || {};\n"
        "            if (state.prov && state.kab) {\n"
        "              var authParent = resolveKabupatenProvinceJs(state.kab);\n"
        "              if (authParent && authParent !== state.prov) return false;\n"
        "            }\n"
        "            if (state.prov) {\n"
        "              var rProvs = parseRecordProvinces(fp, allowedProvs);\n"
        "              if (rProvs.indexOf(state.prov) === -1) return false;\n"
        "            }\n"
        "            if (state.kab) {\n"
        "              var rKabs = parseRecordKabupaten(fp);\n"
        "              if (rKabs.indexOf(state.kab) === -1) return false;\n"
        "            }\n"
        "            return true;\n"
        "          });\n"
        "          var gj = L.geoJSON({ type: \"FeatureCollection\", features: filteredFeatures }, {\n"
        "            style: inventoryStyle,"
    )
    text = replace_once(text, old_inv_refresh, new_inv_refresh, "v2 inventory feature filter")

    # 9. Hook renderDatasetState to also update Overview KPIs, shared filter controls, and URL query
    text = replace_once(
        text,
        "      var periodEl = document.getElementById(\"walhi-period\");",
        "      syncSharedFilterControls();\n      renderOverviewKpisAndWidgets();\n      if (state.view === \"data\") renderDataCatalogView();\n      syncUrlQuery();\n      var periodEl = document.getElementById(\"walhi-period\");",
        "v2 renderDatasetState hook",
    )

    # 10. Sync sidebar #f-prov change handler with shared filter state and kabupaten options
    old_sidebar_prov = '        if (id === "f-prov") state.prov = e.target.value;'
    new_sidebar_prov = (
        '        if (id === "f-prov") {\n'
        '          state.prov = e.target.value;\n'
        '          state.kab = "";\n'
        '          updateKabupatenOptions(state.region, state.prov);\n'
        '          renderDatasetState();\n'
        '        }'
    )
    text = replace_once(text, old_sidebar_prov, new_sidebar_prov, "v2 sidebar f-prov sync")

    # 11. Wire navigation, shared filter bar events, and provenance drawer events
    old_init = (
        "    /* ---------- Init ---------- */\n"
        "    populateRegionSelector();\n"
        "    configureDates(\"indonesia\", null);\n"
        "    updateProvinceOptions(\"indonesia\");\n"
        "    selectRegion(\"indonesia\", currentDate());"
    )
    new_init = r"""    /* ---------- v2 Events (#10, #11, #19) ---------- */
    document.querySelectorAll("#primary-nav button[data-view]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setView(btn.getAttribute("data-view"));
      });
    });

    document.getElementById("f-region-shared").addEventListener("change", function (e) {
      state.prov = "";
      state.kab = "";
      selectRegion(e.target.value, currentDate());
    });

    document.getElementById("f-prov-shared").addEventListener("change", function (e) {
      state.prov = e.target.value;
      state.kab = "";
      if (state.prov && state.region === "indonesia") {
        var targetReg = resolveProvinceRegionJs(state.prov);
        if (targetReg) {
          selectRegion(targetReg, currentDate());
          return;
        }
      }
      var provSidebar = document.getElementById("f-prov");
      if (provSidebar) provSidebar.value = state.prov;
      updateKabupatenOptions(state.region, state.prov);
      renderDatasetState();
      renderList();
      refreshConcessionMarkers();
      refreshConcessionInventoryLayer();
      refreshFirmsLayer();
    });

    document.getElementById("f-kab").addEventListener("change", function (e) {
      state.kab = e.target.value;
      if (state.kab) {
        var parentProv = resolveKabupatenProvinceJs(state.kab);
        if (parentProv && !state.prov) {
          state.prov = parentProv;
          var provSidebar = document.getElementById("f-prov");
          if (provSidebar) provSidebar.value = state.prov;
          var provShared = document.getElementById("f-prov-shared");
          if (provShared) provShared.value = state.prov;
        }
        if (state.region === "indonesia" && parentProv) {
          var targetReg = resolveProvinceRegionJs(parentProv);
          if (targetReg) {
            selectRegion(targetReg, currentDate());
            return;
          }
        }
      }
      renderDatasetState();
      renderList();
      refreshConcessionMarkers();
      refreshConcessionInventoryLayer();
      refreshFirmsLayer();
    });

    document.getElementById("f-window").addEventListener("change", function (e) {
      state.window = e.target.value || "all";
      renderDatasetState();
    });

    document.getElementById("f-date-select").addEventListener("change", function (e) {
      var idx = (state.dates || []).indexOf(e.target.value);
      if (idx >= 0) {
        state.dateIdx = idx;
        elTime.value = idx;
        loadSelectedDate();
      }
    });

    document.getElementById("btn-reset-filters").addEventListener("click", function () {
      state.prov = "";
      state.kab = "";
      state.sector = "";
      state.party = "";
      state.boundary = "";
      state.conf = "";
      state.platform = "";
      state.search = "";
      state.window = "all";
      ["f-prov", "f-sector", "f-party", "f-boundary", "f-conf", "f-platform"].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.value = "";
      });
      if (elSearch) elSearch.value = "";
      selectRegion("indonesia", null);
    });

    document.getElementById("btn-provenance-drawer").addEventListener("click", function () {
      openProvenanceDrawer(null);
    });
    document.getElementById("btn-close-provenance").addEventListener("click", closeProvenanceDrawer);
    document.querySelectorAll(".kpi-cite-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openProvenanceDrawer(btn.getAttribute("data-metric-id"));
      });
    });

    /* ---------- Init ---------- */
    populateRegionSelector();
    var initialPreferredDate = applyInitialUrlFilters();
    configureDates(state.region, initialPreferredDate);
    updateProvinceOptions(state.region);
    setView(state.view, true);
    selectRegion(state.region, initialPreferredDate || currentDate());"""

    text = replace_once(text, old_init, new_init, "v2 init and events")

    if use_crlf:
        text = text.replace("\n", "\r\n")
    return text


def validate_patched(text: str) -> None:
    required = [
        'id="primary-nav"',
        'id="nav-overview"',
        'id="nav-map"',
        'id="nav-concessions"',
        'id="nav-data"',
        'id="shared-filter-bar"',
        'id="f-region-shared"',
        'id="f-prov-shared"',
        'id="f-kab"',
        'id="f-window"',
        'id="f-date-select"',
        'id="kpi-grid"',
        'id="kpi-card-hotspots"',
        'id="kpi-card-concessions"',
        'id="kpi-card-dossiers"',
        'id="kpi-card-environmental"',
        'id="overview-trend-card"',
        'id="overview-regional-card"',
        'id="data-view-panel"',
        'id="provenance-drawer"',
        'data/admin-index.json',
        'data/sources-manifest.json',
        'data/admin-boundaries.geojson',
        'function evaluateFirmsFreshnessRuntime(nowMs)',
        'function pointInBoundaryGeometry(lon, lat, entryOrGeom)',
        'function pointMatchesProvince(p, provName)',
        'function pointMatchesKabupaten(p, kabName, activeProvName)',
        'function setView(viewName, skipUrlSync)',
        'function syncUrlQuery()',
        'function openProvenanceDrawer(metricId)',
        'CURATED · INVESTIGATIVE',
        'DATA UNAVAILABLE',
    ]
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(
            "missing v2 foundation integration markers: " + ", ".join(missing)
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
        print("v2 foundation dashboard patch: OK")
        return
    if patched != source:
        INDEX.write_text(patched, encoding="utf-8")
        print("patched index.html with MERATUS v2 foundation shell, shared filters, and provenance")
    else:
        print("index.html already contains MERATUS v2 foundation patch")


if __name__ == "__main__":
    main()
