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
context.adminIndex = adminIndex;
context.sourcesManifest = sourcesManifest;
context.hotspotHistory = JSON.parse(fs.readFileSync("data/hotspots/history.json", "utf8"));

// 1. Verify BPS code & cross-border province parsing in JS
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

// 2. Verify national overview KPI rendering uses actual counts and keeps environmental feed UNAVAILABLE
context.renderOverviewKpisAndWidgets();
assert.ok(getEl("kpi-hotspots-val").textContent.includes("67.478"), "expected national 4-day FIRMS count");
assert.ok(getEl("kpi-concessions-val").textContent.includes("7.265"), "expected national deduplicated concession count");

// 3. Verify filtering by province sets FIRMS KPI to DATA UNAVAILABLE rather than substituting island total
context.state.region = "kalimantan";
context.state.prov = "Kalimantan Timur";
context.renderOverviewKpisAndWidgets();
assert.strictEqual(
  getEl("kpi-hotspots-val").textContent,
  "DATA UNAVAILABLE",
  "filtering by province must not substitute island hotspot total"
);
assert.ok(
  getEl("kpi-dossiers-val").textContent.includes("3 dossier"),
  "Kalimantan Timur has 3 curated dossiers (kideco, kpc, kiani)"
);

// 4. Verify non-Kalimantan region sets Dossiers KPI to DATA UNAVAILABLE (not 0)
context.state.region = "sumatra";
context.state.prov = "";
context.renderOverviewKpisAndWidgets();
assert.strictEqual(
  getEl("kpi-dossiers-val").textContent,
  "DATA UNAVAILABLE",
  "non-Kalimantan region must mark curated dossiers as DATA UNAVAILABLE, not 0"
);

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

// 6. Verify Wave 2 Unified ConcessionViewModel, pagination, and contextual Inspector (#12, #13, #14)
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
context.firmsForView = () => [];
context.pointInBoundaryGeometry = () => false;
context.boundaryGeometryDistanceKm = () => 999;
context.renderSourceLinks = () => "Kompas.id";
context.renderSources = () => "<ul><li>Kompas.id</li></ul>";
context.openMobileInspector = () => {};
context.closeMobileInspector = () => {};
context.renderList = () => {};

vm.runInContext(wave2Code, context);

const kalMining = JSON.parse(fs.readFileSync("data/concessions/kalimantan/inventory/mining.geojson", "utf8"));
const kalBounds = JSON.parse(fs.readFileSync("data/concessions/kalimantan/boundaries.geojson", "utf8"));
const builtVm = context.buildUnifiedConcessionViewModels(
  kalMining.features,
  kalDossier.dossiers,
  kalBounds.features,
  "kalimantan",
  regionById.kalimantan.provinces
);
context.unifiedConcessionCache["kalimantan"] = builtVm;
assert.strictEqual(builtVm.stats.rawInventoryCount, 1223);
assert.strictEqual(builtVm.stats.matchedDossierCount, 5); // kideco, kpc, agm, bre, adaro in mining
assert.strictEqual(builtVm.stats.unmatchedDossierOnlyCount, 7); // 7 non-mining dossiers stay independent when only mining shard passed
assert.strictEqual(builtVm.stats.totalDossierCount, 12);

// Generic inventory row must NOT render Investigation tab
const genericVm = builtVm.rows.find((r) => !r.hasInvestigativeDossier);
assert(genericVm, "expected at least one generic inventory row");
context.state.prov = "";
context.state.kab = "";
context.state.search = "KIDECO";
context.state.concessionPage = 1;
context.showUnifiedConcessionDetail(genericVm.viewModelId, "summary");
assert.ok(context.elInsp.innerHTML.includes('id="insp-tab-summary"'));
assert.ok(context.elInsp.innerHTML.includes('id="insp-tab-map"'));
assert.ok(!context.elInsp.innerHTML.includes('id="insp-tab-investigation"'), "generic inventory row must never expose Investigation tab");

// Dossier-linked row MUST render Investigation tab and preserve search/filter state
const kidecoVm = builtVm.rows.find((r) => r.linkedDossierId === "kideco");
assert(kidecoVm, "expected kideco matched row");
context.showUnifiedConcessionDetail(kidecoVm.viewModelId, "investigation");
assert.ok(context.elInsp.innerHTML.includes('id="insp-tab-investigation"'));
assert.ok(context.elInsp.innerHTML.includes('id="insp-pane-investigation"'));
assert.strictEqual(context.state.search, "KIDECO", "search filter must be preserved across inspector navigation");

// 7. Verify Wave 3 reusable time-series chart & delta strip (#16, #17, #18)
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

// Switch to WIB timezone -> 5 WIB days
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

