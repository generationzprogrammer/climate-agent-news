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
test('energy and COP31 keep their existing database behaviour',()=>{assert.equal(records({mode:'energy'})[0].canonical_url,'old');assert.equal(records({},true)[0].canonical_url,'old');});
test('English topics derive from English labels',()=>{assert.equal(records({language:'en'})[0].topics[0],'Climate finance');});
test('comparison action is not rebound to pagination and cleared',()=>{
  const research=fs.readFileSync(require('node:path').join(__dirname,'../static/research.js'),'utf8');
  assert.match(research,/if\(tab==='events'\|\|tab==='watch'\)host\.querySelector\('\.research-more'\)/);
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
