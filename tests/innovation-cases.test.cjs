const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {filterCases, exportCsv, csvCell} = require("../static/innovation-cases.js");
const book = JSON.parse(fs.readFileSync(path.join(__dirname,"../static/data/innovation_cases.json"),"utf8"));

test("country and mechanism filters intersect",()=>{
  const rows=filterCases(book,{country:"CN",institution:"ip"});
  assert.equal(rows.length,2);
  assert(rows.some(c=>c.id==="oi_cerc"));
});
test("Chinese and English search use country names and original titles",()=>{
  assert(filterCases(book,{query:"新加坡"}).some(c=>c.id==="oi_artc"));
  assert(filterCases(book,{query:"Singapore"}).some(c=>c.id==="oi_artc"));
  assert.equal(filterCases(book,{query:"不存在的案例"}).length,0);
});
test("governance is a research lens, not all cases",()=>{
  const rows=filterCases(book,{lens:"governance"});
  assert(rows.length>0&&rows.length<book.cases.length);
  assert(rows.every(c=>c.challenges.includes("governance")));
});
test("institution and regional filters remain precise",()=>{
  assert.equal(filterCases(book,{country:"_global",institution:"ip"}).length,1);
  assert.equal(filterCases(book,{country:"CN",mode:"rules"}).length,0);
});
test("CSV includes sources and separates facts from interpretation",()=>{
  const csv=exportCsv(book,[book.cases.find(c=>c.id==="oi_cerc")],"zh");
  assert(csv.startsWith("\uFEFF"));
  assert(csv.includes('"observed","constraints","transfer","source_urls","reviewed_at"'));
  assert(csv.includes("https://www.energy.gov/node/4813415"));
  assert(csv.includes("中美清洁汽车"));
});
test("CSV prevents spreadsheet formula execution",()=>{
  assert.equal(csvCell("=2+2"),'"\'=2+2"');
  assert.equal(csvCell(" @SUM(1)"),'"\' @SUM(1)"');
  assert.equal(csvCell('a"b'),'"a""b"');
});
