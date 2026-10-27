import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
test('both corpora render English labels without changing source counts',()=>{
  const source=readFileSync(new URL('../static/app.js',import.meta.url),'utf8').replace(/init\(\)\.catch\([\s\S]*$/, '');
  const nodes=new Map();const document={body:{dataset:{}},getElementById:id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:''});return nodes.get(id);}};
  const context={document,URL,Intl,Date,console,location:{href:'https://example.org/'}};
  runInNewContext(source+';globalThis.qa={state,renderBarChart,renderHeatmap};',context);
  context.qa.state.language='en';context.qa.state.taxonomy=JSON.parse(readFileSync(new URL('../static/data/taxonomy.json',import.meta.url)));
  for(const name of ['corpus_analytics','energy_corpus_analytics']){
    const data=JSON.parse(readFileSync(new URL(`../static/data/${name}.json`,import.meta.url)));const before=JSON.stringify(data);
    for(const key of ['top_topics','top_countries','continents','top_sources']){
      context.qa.renderBarChart(key,data[key],{limit:10});assert(!/[\u3400-\u9fff]/.test(nodes.get(key).innerHTML),key+' contains untranslated labels');
    }
    context.qa.renderHeatmap('matrix',data.country_topic_matrix);assert(!/[\u3400-\u9fff]/.test(nodes.get('matrix').innerHTML));
    assert.equal(JSON.stringify(data),before);
  }
});
