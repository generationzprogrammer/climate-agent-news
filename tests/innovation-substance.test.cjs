const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {casePresentation,substantiveField,exportCsv}=require('../static/innovation-cases.js');
const book=JSON.parse(fs.readFileSync(new URL('../static/data/innovation_cases.json','file://'+__filename.replaceAll('\\','/')),'utf8'));
test('presentation preserves every stored case and factual field',()=>{
  const before=JSON.stringify(book);
  for(const c of book.cases)for(const lang of ['zh','en']){
    const v=casePresentation(c,lang);assert(v.summary.length>0);
    if(c.registry_record){assert.equal(v.sections.constraints,'');assert.equal(v.sections.transfer,'');}
    else assert.equal(v.summary,c.summary[lang]);
  }
  assert.equal(JSON.stringify(book),before);
});
test('programme rules are separate from case observations',()=>{
  const c=book.cases.find(c=>c.registry_record?.registry==='nsf_iucrc');
  const v=casePresentation(c);assert.equal(v.programme,c.mechanism.zh);assert.equal(v.sections.mechanism,'');
  assert(substantiveField(c,'mechanism').startsWith('计划共同规则：'));
  assert.equal(substantiveField(c,'constraints'),'');
});
test('an empty member register is not displayed as zero participation',()=>{
  const c=book.cases.find(c=>c.registry_record?.registry==='nsf_iucrc'&&!c.registry_record.member_names.length);
  assert(c);assert(!casePresentation(c).facts.some(r=>r.key==='members'));
  assert.equal(casePresentation(c).sections.observed,'');
});
test('specific Chinese transfer practice remains individual evidence',()=>{
  const c=book.cases.find(c=>c.registry_record?.practice);const v=casePresentation(c);
  assert.equal(v.sections.mechanism,c.registry_record.practice);assert.equal(v.programme,'');
  assert(v.facts.some(r=>r.key==='designation'));
});
test('Australian technical objective and named partners remain available',()=>{
  const c=book.cases.find(c=>c.registry_record?.registry==='australia_crcp');const v=casePresentation(c);
  assert.equal(v.original,c.registry_record.objective_original);
  assert.equal(Number(v.facts.find(r=>r.key==='partners').value),c.registry_record.partners.length);
});
test('generic directory-existence statements are not presented as results',()=>{
  for(const c of book.cases.filter(c=>['jst_coinext','africa_ace','africa_ace2'].includes(c.registry_record?.registry))){
    const v=casePresentation(c);assert.equal(v.sections.observed,'');assert(v.programme);
  }
});
test('CSV separates shared programme rules and excludes generic filler',()=>{
  const c=book.cases.find(c=>c.registry_record?.registry==='nsf_iucrc');
  const csv=exportCsv(book,[c],'zh');
  assert(csv.includes('"programme_rules","mechanism_scope"'));
  assert(csv.includes(c.mechanism.zh));assert(!csv.includes(c.constraints.zh));assert(!csv.includes(c.transfer.zh));
  assert(csv.includes('"programme"'));
});
test('reviewed detail augments a case with linked technical facts',()=>{
  const c=book.cases.find(c=>c.case_detail);assert(c);
  const v=casePresentation(c);assert.equal(v.summary,c.case_detail.summary.zh);
  assert.equal(v.title,c.case_detail.title.zh);
  assert.equal(v.facts.filter(r=>r.key==='detail').length,c.case_detail.facts.length);
  assert(v.facts.filter(r=>r.key==='detail').every(r=>r.source_id&&r.locator));
});
