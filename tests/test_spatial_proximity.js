const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const html = fs.readFileSync("index.html", "utf8");
const startMarker = "/* spatial proximity helpers */";
const endMarker = "/* end spatial proximity helpers */";
const start = html.indexOf(startMarker);
const end = html.indexOf(endMarker);
assert(start >= 0 && end > start, "spatial proximity helper block is missing");

const dossiers = JSON.parse(fs.readFileSync("data/dossiers.json", "utf8")).dossiers;
const boundaries = JSON.parse(fs.readFileSync("data/boundaries.geojson", "utf8"));
const boundaryById = {};
for (const feature of boundaries.features || []) {
  const id = feature.properties && feature.properties.dossierId;
  if (!id || !feature.geometry) continue;
  (boundaryById[id] ||= []).push(feature);
}

const context = {
  dossiers,
  boundaryById,
  normalizeBoundaryQuality(value) {
    const q = String(value || "").trim().toUpperCase();
    return q === "OFFICIAL" || q === "GFW" || q === "PERKIRAAN" ? q : "PERKIRAAN";
  },
};
vm.createContext(context);
vm.runInContext(html.slice(start, end + endMarker.length), context);

function firstBoundaryCoordinate(feature) {
  const geometry = feature.geometry;
  if (geometry.type === "Polygon") return geometry.coordinates[0][0];
  if (geometry.type === "MultiPolygon") return geometry.coordinates[0][0][0];
  throw new Error(`unsupported geometry ${geometry.type}`);
}

for (const dossierId of ["kiani", "kpc"]) {
  const feature = (boundaryById[dossierId] || [])[0];
  assert(feature, `expected boundary for ${dossierId}`);
  const [lon, lat] = firstBoundaryCoordinate(feature);
  const result = context.nearestConcession(lat, lon);
  assert(result, `expected a proximity result for ${dossierId}`);
  assert.strictEqual(result.id, dossierId, `point on ${dossierId} boundary must resolve to the same dossier`);
  assert.strictEqual(result._proximity.relation, "inside");
}

console.log("polygon-aware hotspot proximity tests passed");
