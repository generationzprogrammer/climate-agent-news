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
