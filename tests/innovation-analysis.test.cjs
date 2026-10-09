const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const b=JSON.parse(fs.readFileSync('static/data/innovation_cases.json','utf8'));
const {filterCases,exportCsv}=require('../static/innovation-cases.js');
const {render,comparison,macroRows,macroChart,profileScope}=require('../static/innovation-analysis.js');
test('regional filters use location and survive CSV export',()=>{
 const c=filterCases(b,{province:'CN-ZJ',archetype:'pilot'});assert(c.length>=2);assert(c.every(c=>c.research_annotation.province==='CN-ZJ'));
 const csv=exportCsv(b,c,'zh');assert(csv.includes('primary_model'));assert(csv.includes('CN-ZJ'));assert(!csv.includes('[object Object]'));
});
test('model comparison includes prerequisites, government tools and evidence',()=>{
 const h=comparison(b,['guangdong','zhejiang'],'zh');assert(h.includes('适用前提'));assert(h.includes('政府可用工具'));assert(h.includes('data-detail="oi_giri"'));assert(!h.includes('NaN'));
 assert(comparison(b,['germany'],'zh').includes('两个或三个'));
});
test('macro profiles do not mix projects with platforms',()=>{
 const rows=macroRows(b,'platform','economy');assert(rows.every(r=>r.grain==='platform'));
 const h=macroChart(b,'project','continent','en');assert(h.includes('100%'));assert(h.includes('data-macro-group'));assert(h.includes('tabindex="0"'));assert(!h.includes('NaN'));
});
test('Chinese and English panels have model and macro controls',()=>{
 for(const lang of ['zh','en']){const h=render(b,lang);assert(h.includes('data-model-compare'));assert(h.includes('data-macro-dimension'));assert(h.includes('CN-GD'));assert(!h.includes('undefined'));}
});
test('new geographic models remain discoverable and source-backed',()=>{
 assert.equal(b.analysis.profiles.length,28);assert.equal(b.analysis.provinces.length,31);
 assert.equal(profileScope(b,b.analysis.profiles.find(p=>p.id==='resource_pilots')),'china');
 assert.equal(profileScope(b,b.analysis.profiles.find(p=>p.id==='australia_crc')),'international');
 for(const lang of ['zh','en']){
  const h=render(b,lang);assert(h.includes('data-model-scope'));assert(h.includes('CN-QH'));
  const c=comparison(b,['australia_crc','latin_america_services','africa_capability'],lang);
  for(const id of ['oi_hilt_crc','oi_inti_transfer','oi_tia_stations'])assert(c.includes('data-detail="'+id+'"'));
  assert(!/undefined|NaN/.test(c));
 }
 for(const province of b.analysis.provinces)assert.equal(filterCases(b,{province:province.id}).length,province.count);
});
test('thin-region expansion survives filters and bilingual comparisons',()=>{
 assert(b.cases.length>=750);
 for(const code of ['CN-XZ','CN-JL','CN-HI','CN-NX'])assert(filterCases(b,{province:code}).length>0);
 for(const country of ['RW','NG','EC','WS','PG'])assert(filterCases(b,{country}).length>0);
 for(const lang of ['zh','en']){
  const h=comparison(b,['african_public_engineering','latin_agri_networks','pacific_adaptation'],lang);
  for(const id of ['oi_kirdi','oi_embrapa_open','oi_sros_pilot'])assert(h.includes('data-detail="'+id+'"'));
  assert(!/undefined|NaN/.test(h));
  assert.equal(profileScope(b,b.analysis.profiles.find(p=>p.id==='fujian_joint_pilots')),'china');
 }
});
