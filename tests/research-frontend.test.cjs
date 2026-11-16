const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../static/app.js'),'utf8');
const block=source.slice(source.indexOf('function archiveRecords()'),source.indexOf('function populateTopicFilter()'));
function records(overrides={},cop=false){
  const state={mode:'climate',language:'zh',sourceOnly:true,archive:{records:[{canonical_url:'old',title_original:'Metadata only'}]},...overrides};
  const record={canonical_url:'real',source_text:'Actual publisher text.',governance_themes:[{label_zh:'气候资金',label_en:'Climate finance'}],country_codes:[]};
  const context={state,COP31_EDITION:cop,window:{GREEN_RESEARCH:{texts:new Map([['real',record]])}}};
  vm.createContext(context);vm.runInContext(block+'\nresult=archiveRecords();',context);return context.result;
}
test('default climate database exposes actual source text rather than link-only records',()=>{
  const result=records();assert.equal(result.length,1);assert.equal(result[0].canonical_url,'real');assert.equal(result[0].summary_source,'Actual publisher text.');
});
test('legacy metadata remains accessible without deletion',()=>{assert.equal(records({sourceOnly:false})[0].canonical_url,'old');});
test('energy retains metadata and COP31 shares the source-text database',()=>{assert.equal(records({mode:'energy'})[0].canonical_url,'old');assert.equal(records({},true)[0].canonical_url,'real');assert.equal(records({sourceOnly:false},true)[0].canonical_url,'old');});
test('English topics derive from English labels',()=>{assert.equal(records({language:'en'})[0].topics[0],'Climate finance');});
// 2026-11-13 (功能更新1113 handover): 文本对照 is removed — tab, view and bindings — and its old entries land on the tools
test('text comparison is gone and its old entries are redirected',()=>{
  const research=fs.readFileSync(require('node:path').join(__dirname,'../static/research.js'),'utf8');
  const tabs=research.match(/const TABS=(\[\[.*?\]\]);/)[1];
  assert.deepEqual(JSON.parse(tabs.replace(/'/g,'"')).map(v=>v[0]),['positions','events','watch','methods']);
  for(const gone of ["tab==='compare'",'researchTextSelect','researchDifferences','research-comparison'])assert.ok(!research.includes(gone),gone);
  assert.match(research,/location\.hash==='#compare'/);assert.match(research,/'#research'/);
  const ctx={TABS:JSON.parse(tabs.replace(/'/g,'"'))};vm.createContext(ctx);vm.runInContext(research.match(/const tabOf=[^\n]+/)[0]+"\nold=tabOf('compare');kept=tabOf('watch');",ctx);
  assert.equal(ctx.old,'positions');assert.equal(ctx.kept,'watch');
});
test('the research API client only asks for the three metadata endpoints, thirty rows at a time',()=>{
  const research=fs.readFileSync(require('node:path').join(__dirname,'../static/research.js'),'utf8');
  assert.match(research,/\['positions','events','topics'\]\.includes\(mode\)/);
  assert.match(research,/fetch\('\/api\/research\/'\+mode/);
  assert.ok(!/api\/research\/(text|body|fulltext|article)/.test(research));
  assert.match(research,/pageSize:raw\.page_size\|\|30/);
});
test('the excerpt index is not read on arrival when the page asks for lazy loading',()=>{
  const research=fs.readFileSync(require('node:path').join(__dirname,'../static/research.js'),'utf8');
  assert.match(research,/const LAZY=document\.currentScript\?\.dataset\.index==='lazy'/);
  assert.match(research,/if\(!LAZY\)loadIndex\(\);/);
  assert.equal(research.split("fetch('./data/research_index.json'").length,2);
});
test('report rows are built from text nodes and open only http(s) links',()=>{
  const research=fs.readFileSync(require('node:path').join(__dirname,'../static/research.js'),'utf8');
  const row=research.slice(research.indexOf('function reportRow('),research.indexOf('const kit='));
  assert.ok(!row.includes('innerHTML'));
  const ctx={URL};vm.createContext(ctx);vm.runInContext(research.match(/const url=[^\n]+/)[0]+"\nbad=url('javascript:alert(1)');data=url('data:text/html,x');good=url('https://example.org/a');",ctx);
  assert.equal(ctx.bad,'#');assert.equal(ctx.data,'#');assert.equal(ctx.good,'https://example.org/a');
});
test('English research filters tolerate legacy country records without names',()=>{
  const research=fs.readFileSync(require('node:path').join(__dirname,'../static/research.js'),'utf8');
  const countryBlock=research.slice(research.indexOf('const countryName='),research.indexOf('const countries='));
  const context={data:{records:[{country_codes:[{alpha2:'GB'},{alpha2:'US',name_zh:'美国'}]}],countries:[{alpha2:'GB',name_en:'United Kingdom',name_zh:'英国'},{alpha2:'US',name_en:'United States',name_zh:'美国'}]},en:()=>true};
  vm.createContext(context);vm.runInContext(countryBlock+'\nresult=countryList();',context);
  assert.equal(context.result[0].name_en,'United Kingdom');assert.equal(context.result[1].name_en,'United States');
  context.data.countries=[];vm.runInContext('fallback=countryList();',context);assert.equal(context.fallback.length,2);
});
test('filtered CSV preserves quotes and protects spreadsheet formulas',()=>{
  const research=fs.readFileSync(require('node:path').join(__dirname,'../static/research.js'),'utf8');
  const code=research.match(/const csvCell = [^\n]+/)[0];
  const ctx={};vm.createContext(ctx);vm.runInContext(code+'\nformula=csvCell("=1+1");quoted=csvCell(\'a"b\');',ctx);
  assert.equal(ctx.formula,'"\'=1+1"');assert.equal(ctx.quoted,'"a""b"');
});
