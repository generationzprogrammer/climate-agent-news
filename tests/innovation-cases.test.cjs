const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const {filterCases, exportCsv, csvCell, radarSvg} = require("../static/innovation-cases.js");
const book = JSON.parse(fs.readFileSync(path.join(__dirname,"../static/data/innovation_cases.json"),"utf8"));

test("country and mechanism filters intersect",()=>{
  const rows=filterCases(book,{country:"CN",institution:"ip"});
  assert(rows.length>=2);
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
  assert(filterCases(book,{country:"CN",mode:"rules"}).every(c=>c.modes.includes("rules")));
});
test("technology selection returns distinct real projects",()=>{
  assert(book.cases.length>=300);
  assert(filterCases(book,{sector:"solar"}).every(c=>c.sector_key==="solar"));
  assert(book.cases.some(c=>c.id==="oi_iea_tcp"));
});
test("radar keeps a missing observation out of marks and uses non-colour cues",()=>{
  const c=book.cases.find(c=>c.project), missing=structuredClone(c);
  missing.profile[book.profile_axes[0].id].score=null;
  const svg=radarSvg([missing,c],book.profile_axes,"zh");
  assert.equal((svg.match(/data-radar-axis=/g)||[]).length,9);
  assert(svg.includes('stroke-dasharray="8 4"'));
  assert(svg.includes('fill="none"'));
  assert(!svg.includes('data-radar-axis="undefined"'));
  assert(svg.includes('tabindex="0"'));
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

test("US coverage is independent project evidence, not repeated news",()=>{
  const rows=filterCases(book,{country:"US"}),projects=rows.filter(c=>c.project?.source_type==="ARPAE");
  assert(rows.length>=155);
  assert(projects.length>=150);
  assert.equal(new Set(projects.map(c=>c.project.official_id)).size,projects.length);
  assert(projects.every(c=>c.countries.length===1&&c.countries[0]==="US"));
  assert(new Set(projects.map(c=>c.sector_key)).size>=8);
  const c=projects[0],csv=exportCsv(book,[c],"zh");
  assert(csv.includes('"award_usd","funding_basis"'));
  assert(csv.includes('"'+c.project.award_usd+'"'));
  assert(csv.includes("listed_ARPAE_award_not_actual_expenditure"));
  assert(!Object.hasOwn(c.project,"eu_grant_eur"));
});

test("US missing complete partner census never becomes a zero radar score",()=>{
  const projects=book.cases.filter(c=>c.project?.source_type==="ARPAE");
  const svg=radarSvg(projects.slice(0,2),book.profile_axes,"zh");
  assert(!svg.includes("data-radar-axis="));
  assert(projects.every(c=>Object.values(c.profile).every(v=>v.raw===null&&v.score===null)));
});
