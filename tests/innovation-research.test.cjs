const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const b=JSON.parse(fs.readFileSync(path.join(__dirname,'../static/data/innovation_cases.json'),'utf8'));
const {filterCases}=require('../static/innovation-cases.js'),r=require('../static/innovation-research.js');
test('five-year origin and activity filters use explicit chronology',()=>{
 const x=filterCases(b,{timeScope:'china_plans',timeBasis:'activity',period:'cn_fyp_13'});
 assert(x.some(c=>c.id==='oi_tsari_suzhou'));assert(x.every(c=>c.research_annotation.country==='CN'));
 const y=filterCases(b,{timeScope:'china_plans',period:'cn_fyp_11'});assert(y.some(c=>c.id==='oi_siat'));
});
test('group filters follow selected documented-country scope',()=>{
 const x=filterCases(b,{organization:'EU',organizationScope:'focus'});assert(x.every(c=>c.organization_tags.includes('EU')));
 assert(!x.some(c=>c.research_annotation.country==='GB'));
});
test('research CSV escapes formulas and preserves raw numeric counts',()=>{
 const csv=r.csv([{name:'=HYPERLINK("bad")',count:3}]);assert(csv.includes("'=HYPERLINK"));assert(csv.includes('"3"'));
});
test('English export provides sufficient label space',()=>{
 const svg=r.chartSvg({title:'Factors',subtitle:'Institutions',labels:['Knowledge and technology + Markets and industrial demand'],values:[154],notes:'Counts not causal effects',lang:'en'});assert(svg.includes('x="492"'));assert(svg.includes('width="1220"'));
});
