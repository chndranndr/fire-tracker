const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const html = fs.readFileSync("index.html", "utf8");
const startMarker = "/* === MERATUS v2 Foundation Helpers (#10, #11, #19) === */";
const endMarker = "function closeProvenanceDrawer() {";
const start = html.indexOf(startMarker);
const end = html.indexOf(endMarker);
assert(start >= 0 && end > start, "v2 foundation helper block is missing from index.html");
const closeEnd = html.indexOf("}", end) + 1;

const adminIndex = JSON.parse(fs.readFileSync("data/admin-index.json", "utf8"));
const sourcesManifest = JSON.parse(fs.readFileSync("data/sources-manifest.json", "utf8"));
const regionsPayload = JSON.parse(fs.readFileSync("data/regions.json", "utf8"));
const hotspotsManifest = JSON.parse(fs.readFileSync("data/hotspots/manifest.json", "utf8"));
const kalDossier = JSON.parse(fs.readFileSync("data/dossiers/kalimantan.json", "utf8"));

const regions = regionsPayload.regions;
const regionById = {};
for (const r of regions) regionById[r.id] = r;

const domElements = {};
function getEl(id) {
  if (!domElements[id]) {
    domElements[id] = {
      id,
      textContent: "",
      innerHTML: "",
      className: "",
      value: "",
      classList: {
        _set: new Set(),
        add(c) { this._set.add(c); },
        remove(c) { this._set.delete(c); },
        toggle(c, cond) { if (cond) this._set.add(c); else this._set.delete(c); },
        contains(c) { return this._set.has(c); },
      },
      setAttribute() {},
      getAttribute() { return ""; },
      querySelectorAll() { return []; },
      addEventListener() {},
    };
  }
  return domElements[id];
}

const context = {
  window: {
    location: { pathname: "/index.html", search: "", hash: "" },
    history: {
      lastUrl: "/index.html",
      replaceState(_s, _t, url) { this.lastUrl = url; },
    },
  },
  document: {
    getElementById: getEl,
    querySelector() { return getEl("app-root"); },
    querySelectorAll() { return []; },
  },
  URLSearchParams,
  regions,
  regionById,
  hotspotsManifest,
  concessionManifest: JSON.parse(fs.readFileSync("data/concessions/manifest.json", "utf8")),
  dossiers: kalDossier.dossiers,
  pipelineStatus: { stale: false, pipelineStatus: "healthy" },
  firmsMeta: hotspotsManifest.meta,
  usingFallback: false,
  elTime: getEl("time-range"),
  elSearch: getEl("search"),
  state: {
    view: "overview",
    region: "indonesia",
    prov: "",
    kab: "",
    window: "all",
    sector: "",
    party: "",
    boundary: "",
    conf: "",
    platform: "",
    search: "",
    dates: ["2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27"],
    dateIdx: 3,
  },
  currentDate() { return context.state.dates[context.state.dateIdx]; },
  nationalCountForDate(date) {
    return Object.values(hotspotsManifest.regions).reduce((sum, r) => {
      const d = (r.days || []).find((x) => x.date === date);
      return sum + (d ? d.count : 0);
    }, 0);
  },
  regionCountForDate(regionId, date) {
    const r = hotspotsManifest.regions[regionId];
    const d = r && (r.days || []).find((x) => x.date === date);
    return d ? d.count : 0;
  },
  filteredDossiers() {
    return context.dossiers.filter((d) => !context.state.prov || d.province === context.state.prov);
  },
  formatWib(val) { return String(val); },
  escapeHtml(s) { return String(s == null ? "" : s); },
  loadSelectedDate() {},
  selectRegion() {},
};

vm.createContext(context);
vm.runInContext(html.slice(start, closeEnd), context);
const wave3Start = html.indexOf("var hotspotHistory = null;");
const wave3End = html.indexOf("hotspotHistory = hotspotHistoryPayload;", wave3Start);
assert(wave3Start >= 0 && wave3End > wave3Start, "v2 Wave 3 JS helper block missing from index.html");
vm.runInContext(html.slice(wave3Start, wave3End), context);
const adminBoundaries = JSON.parse(fs.readFileSync("data/admin-boundaries.geojson", "utf8"));
context.adminIndex = adminIndex;
context.sourcesManifest = sourcesManifest;
context.hotspotHistory = JSON.parse(fs.readFileSync("data/hotspots/history.json", "utf8"));
context.indexAdminBoundaries(adminBoundaries);

// Extract firmsForView() from index.html so we test the actual patched map filter function
const firmsFnStart = html.indexOf("function firmsForView() {");
const firmsFnEnd = html.indexOf("function refreshAdminBoundaryHighlight()", firmsFnStart);
assert(firmsFnStart >= 0 && firmsFnEnd > firmsFnStart, "firmsForView block missing from index.html");
context.firms = JSON.parse(fs.readFileSync("data/hotspots/kalimantan/2026-08-27.json", "utf8")).points;
context.normalizePlatform = (p) => p.platform || "";
vm.runInContext(html.slice(firmsFnStart, firmsFnEnd), context);

// 1. Verify BPS code & authoritative province/kabupaten hierarchy in JS (Fix #4)
assert.deepStrictEqual(
  Array.from(context.parseRecordProvinces({ provinceCode: "64" })),
  ["Kalimantan Timur"]
);
assert.deepStrictEqual(
  Array.from(context.parseRecordProvinces({ province: "KALIMANTAN SELATAN, KALIMANTAN TIMUR" })),
  ["Kalimantan Selatan", "Kalimantan Timur"]
);
assert.deepStrictEqual(
  Array.from(context.parseRecordProvinces({ province: "Kalimantan" })),
  []
);
assert.strictEqual(context.resolveKabupatenProvinceJs("Tabalong"), "Kalimantan Selatan");
assert.strictEqual(context.resolveKabupatenProvinceJs("Paser"), "Kalimantan Timur");
assert.strictEqual(context.resolveKabupatenProvinceJs("Kutai Timur"), "Kalimantan Timur");

// 2. Verify runtime freshness evaluation against current UTC time on page load (Fix #2)
const freshEval = context.evaluateFirmsFreshnessRuntime(Date.parse("2026-08-28T05:30:00Z"));
assert.strictEqual(freshEval.state, "fresh");
assert.strictEqual(freshEval.lastKnownGood, false);

context.renderOverviewKpisAndWidgets();
assert.ok(getEl("kpi-hotspots-val").textContent.includes("67.478"), "expected national 4-day FIRMS count");
assert.strictEqual(getEl("kpi-hotspots-badge").textContent, "FRESH · NRT");
assert.ok(getEl("kpi-concessions-val").textContent.includes("7.265"), "expected national deduplicated concession count");

// Simulate page load hours/days later without a new sync -> must re-evaluate as STALE (LKG)
const staleEval = context.evaluateFirmsFreshnessRuntime(Date.parse("2026-08-30T12:00:00Z"));
assert.strictEqual(staleEval.state, "stale");
assert.strictEqual(staleEval.lastKnownGood, true);
context.renderOverviewKpisAndWidgets();
assert.strictEqual(getEl("kpi-hotspots-badge").textContent, "STALE (LKG)");
// Restore fresh evaluation for subsequent assertions
context.evaluateFirmsFreshnessRuntime(Date.parse("2026-08-28T05:30:00Z"));

// 3. Verify geographic filters (province & kabupaten) filter FIRMS map points and synchronize KPIs & charts (Fix #3)
context.state.region = "kalimantan";
context.state.prov = "";
context.state.kab = "";
const allKalMapPts = context.firmsForView();
assert.strictEqual(allKalMapPts.length, 12442, "unfiltered Kalimantan 2026-08-27 shard has 12,442 points");

context.state.prov = "Kalimantan Timur";
const kaltimMapPts = context.firmsForView();
assert.ok(kaltimMapPts.length > 0 && kaltimMapPts.length < allKalMapPts.length, "province filter must spatially subset FIRMS map points");
assert.strictEqual(kaltimMapPts.length, 667, "expected 667 FIRMS points inside Kalimantan Timur on 2026-08-27");

context.renderOverviewKpisAndWidgets();
assert.strictEqual(
  getEl("kpi-hotspots-val").textContent,
  (1643).toLocaleString("id-ID") + " deteksi",
  "filtering by Kalimantan Timur must synchronize KPI to Kalimantan Timur 4-day total (1.643)"
);
assert.ok(
  getEl("kpi-hotspots-meta").textContent.includes("667"),
  "KPI meta must show 667 detections on active date 2026-08-27 for Kalimantan Timur"
);
assert.ok(
  getEl("kpi-dossiers-val").textContent.includes("3 dossier"),
  "Kalimantan Timur has 3 curated dossiers (kideco, kpc, kiani)"
);

// Narrow further to Kabupaten Kutai Timur
context.state.kab = "Kutai Timur";
const kutimMapPts = context.firmsForView();
assert.ok(kutimMapPts.length > 0 && kutimMapPts.length < kaltimMapPts.length, "kabupaten filter must further subset province FIRMS points");
assert.strictEqual(kutimMapPts.length, 326, "expected 326 FIRMS points inside Kutai Timur on 2026-08-27");
context.renderOverviewKpisAndWidgets();
assert.strictEqual(
  getEl("kpi-hotspots-val").textContent,
  (602).toLocaleString("id-ID") + " deteksi",
  "filtering by Kutai Timur must synchronize KPI to Kutai Timur 4-day total (602)"
);

// Hierarchy mismatch (Kalimantan Barat + Kutai Timur) -> 0 map points
context.state.prov = "Kalimantan Barat";
context.state.kab = "Kutai Timur";
assert.strictEqual(context.firmsForView().length, 0, "mismatched province and kabupaten must return 0 map points");

// 4. Verify non-Kalimantan region sets Dossiers KPI to DATA UNAVAILABLE (not 0) and WALHI uses CURATED · INVESTIGATIVE (Fix #7)
context.state.region = "sumatra";
context.state.prov = "";
context.state.kab = "";
context.renderOverviewKpisAndWidgets();
assert.strictEqual(
  getEl("kpi-dossiers-val").textContent,
  "DATA UNAVAILABLE",
  "non-Kalimantan region must mark curated dossiers as DATA UNAVAILABLE, not 0"
);
const walhiCardHtml = context.renderMetricEnvelopeHtml(sourcesManifest.metrics["walhi-dossiers"]);
assert.ok(walhiCardHtml.includes("CURATED · INVESTIGATIVE"), "WALHI dossier envelope must render CURATED · INVESTIGATIVE badge");
assert.ok(walhiCardHtml.includes("Availability"), "envelope HTML must display separated Availability row");
assert.ok(walhiCardHtml.includes("Provenance"), "envelope HTML must display separated Provenance row");
assert.ok(walhiCardHtml.includes("Verification"), "envelope HTML must display separated Verification row");

// 5. Verify URL query serialization
context.state.view = "concessions";
context.state.region = "kalimantan";
context.state.prov = "Kalimantan Timur";
context.state.kab = "Kutai Timur";
context.syncUrlQuery();
assert.ok(context.window.history.lastUrl.includes("view=concessions"));
assert.ok(context.window.history.lastUrl.includes("region=kalimantan"));
assert.ok(context.window.history.lastUrl.includes("prov=Kalimantan+Timur"));
assert.ok(context.window.history.lastUrl.includes("kab=Kutai+Timur"));

// 6. Verify Wave 2 Lightweight Concession Metadata Index, lazy geometry loading, and contextual Inspector (Fix #5, #12, #13, #14)
const wave2Start = html.indexOf("var unifiedConcessionCache = {};");
const wave2End = html.indexOf("function applyStaticPayload(payload) {");
assert(wave2Start >= 0 && wave2End > wave2Start, "v2 Wave 2 JS helper block missing from index.html");
const wave2Code = html.slice(wave2Start, wave2End);

context.elInsp = getEl("inspector");
context.elDossierCount = getEl("dossier-count");
context.elSheetLabel = getEl("explorer-sheet-label");
context.elList = getEl("obj-list");
context.walhi = kalDossier.walhiSummary;
context.boundaryById = {};
context.boundaryGeometryDistanceKm = () => 999;
context.renderSourceLinks = () => "Kompas.id";
context.renderSources = () => "<ul><li>Kompas.id</li></ul>";
context.openMobileInspector = () => {};
context.closeMobileInspector = () => {};
context.renderList = () => {};
let geoJsonFetchCount = 0;
const kalIndex = JSON.parse(fs.readFileSync("data/concessions/kalimantan/inventory/index.json", "utf8"));
const kalMining = JSON.parse(fs.readFileSync("data/concessions/kalimantan/inventory/mining.geojson", "utf8"));
context.loadJson = (url) => {
  if (url.endsWith("index.json")) {
    return Promise.resolve(JSON.parse(JSON.stringify(kalIndex)));
  }
  if (url.endsWith(".geojson")) {
    geoJsonFetchCount += 1;
    return Promise.resolve(kalMining);
  }
  return Promise.resolve(null);
};
context.loadConcessionInventoryData = (layerObj) => context.loadJson(layerObj.url);

vm.runInContext(wave2Code, context);

// Populate viewModelById from lightweight index.json without fetching any .geojson layer (Fix #5)
kalIndex.rows.forEach((row) => {
  context.viewModelById[row.viewModelId] = row;
});
kalIndex.geometryLoaded = false;
context.unifiedConcessionCache["kalimantan"] = kalIndex;
assert.strictEqual(kalIndex.stats.rawInventoryCount, 3053);
assert.strictEqual(kalIndex.stats.matchedDossierCount, 9);
assert.strictEqual(kalIndex.stats.unmatchedDossierOnlyCount, 3);
assert.strictEqual(kalIndex.stats.totalDossierCount, 12);
assert.strictEqual(geoJsonFetchCount, 0, "loading list view models from index.json must not fetch full GeoJSON layers");

// Generic inventory row has no loaded polygon features initially and must NOT render Investigation tab
const genericVm = kalIndex.rows.find(
  (r) => !r.hasInvestigativeDossier && Array.isArray(r.layerUrls) && r.layerUrls.some((u) => u.endsWith("mining.geojson"))
);
assert(genericVm, "expected at least one generic mining inventory row");
assert.strictEqual(context.featureByViewModelId[genericVm.viewModelId], undefined, "index-backed row must start without loaded polygon geometry");
context.state.prov = "";
context.state.kab = "";
context.state.search = "KIDECO";
context.state.concessionPage = 1;
context.showUnifiedConcessionDetail(genericVm.viewModelId, "summary");
assert.ok(context.elInsp.innerHTML.includes('id="insp-tab-summary"'));
assert.ok(context.elInsp.innerHTML.includes('id="insp-tab-map"'));
assert.ok(!context.elInsp.innerHTML.includes('id="insp-tab-investigation"'), "generic inventory row must never expose Investigation tab");
assert.strictEqual(geoJsonFetchCount, 0, "opening summary tab must not fetch full GeoJSON layer");

// Lazy-load geometry on demand for genericVm
context.ensureConcessionGeometryForRow(genericVm).then((loadedFeatures) => {
  assert.strictEqual(geoJsonFetchCount, 1, "ensureConcessionGeometryForRow must lazily fetch the specific GeoJSON layer once");
  assert.ok(Array.isArray(loadedFeatures) && loadedFeatures.length > 0 && loadedFeatures[0].geometry, "polygon geometry must be attached after lazy load");
});

// Dossier-linked row MUST render Investigation tab and preserve search/filter state
const kidecoVm = kalIndex.rows.find((r) => r.linkedDossierId === "kideco");
assert(kidecoVm, "expected kideco matched row");
context.showUnifiedConcessionDetail(kidecoVm.viewModelId, "investigation");
assert.ok(context.elInsp.innerHTML.includes('id="insp-tab-investigation"'));
assert.ok(context.elInsp.innerHTML.includes('id="insp-pane-investigation"'));
assert.strictEqual(context.state.search, "KIDECO", "search filter must be preserved across inspector navigation");

// 7. Verify Wave 3 reusable time-series chart, province/kabupaten series, & consecutive DoD guard (Fix #3, #6, #16, #17, #18)
context.state.region = "indonesia";
context.state.prov = "";
context.state.kab = "";
context.state.tsMetric = "firms-hotspots";
context.state.tsAggMode = "incremental";
context.state.tsTimezone = "UTC";

const tsUtc = context.buildTypedTimeSeriesForView("firms-hotspots");
assert.strictEqual(tsUtc.metricId, "firms-hotspots");
assert.strictEqual(tsUtc.granularity, "day");
assert.strictEqual(tsUtc.points.length, 4);
assert.strictEqual(tsUtc.points[3].status, "partial");

const chartWrap = getEl("overview-trend-svg");
context.renderReusableTimeSeriesChart(chartWrap, tsUtc);
assert.ok(getEl("ts-delta-strip").innerHTML.includes("-22"), "expected complete-day DoD -22 in delta strip");
assert.ok(getEl("ts-delta-strip").innerHTML.includes("+3.794"), "expected same-time-of-day +3.794 in delta strip");
assert.ok(chartWrap.innerHTML.includes("PARTIAL DAY"), "expected partial-day marker on latest bar");

// Province & kabupaten time-series support (Fix #3)
context.state.region = "kalimantan";
context.state.prov = "Kalimantan Timur";
const tsProv = context.buildTypedTimeSeriesForView("firms-hotspots");
assert.strictEqual(tsProv.coverage.completeness, "partial");
assert.strictEqual(tsProv.points.length, 4);
assert.strictEqual(tsProv.points.reduce((acc, p) => acc + (p.value || 0), 0), 1643);

context.state.kab = "Kutai Timur";
const tsKab = context.buildTypedTimeSeriesForView("firms-hotspots");
assert.strictEqual(tsKab.points.length, 4);
assert.strictEqual(tsKab.points.reduce((acc, p) => acc + (p.value || 0), 0), 602);

// Non-consecutive date gap guard in JS (Fix #6)
assert.strictEqual(context.areDatesConsecutiveJs("2026-08-25", "2026-08-26"), true);
assert.strictEqual(context.areDatesConsecutiveJs("2026-08-24", "2026-08-26"), false);

// Switch to WIB timezone -> 5 WIB days
context.state.region = "indonesia";
context.state.prov = "";
context.state.kab = "";
context.state.tsTimezone = "Asia/Jakarta";
const tsWib = context.buildTypedTimeSeriesForView("firms-hotspots");
assert.strictEqual(tsWib.points.length, 5);
assert.strictEqual(tsWib.points[4].label, "2026-08-28");

// Switch to burned-area -> explicit DATA UNAVAILABLE state, never fake zeros
context.state.tsMetric = "burned-area";
const tsBurned = context.buildTypedTimeSeriesForView("burned-area");
context.renderReusableTimeSeriesChart(chartWrap, tsBurned);
assert.ok(chartWrap.innerHTML.includes("DATA UNAVAILABLE"));

console.log("v2 frontend runtime tests passed");

