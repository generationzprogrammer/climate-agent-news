import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const source=readFileSync(new URL('../static/app.js',import.meta.url),'utf8').replace(/init\(\)\.catch\([\s\S]*$/, '');
function setup(language='en') {
  const messages=[];
  const document={body:{dataset:{edition:'cop31'}},getElementById:()=>({appendChild:node=>messages.push(node.innerHTML),scrollTop:0,scrollHeight:1}),createElement:()=>({})};
  const context={document,URL,Intl,Date,console,location:{href:'https://example.org/cop31/'}};
  runInNewContext(source+`;globalThis.qa={state,planQuestion,selectEvidence,answerQuestion,scopeLabel};`,context);
  const qa=context.qa;qa.state.language=language;
  const records=Array.from({length:12},(_,i)=>({article_id:String(i),record_id:String(i),canonical_url:'https://source.test/'+i,title_zh:'气候资金行动',title_original:'Climate finance action '+i,summary_zh:'中文来源中明确记载的气候资金行动与具体安排。',summary_source:'The government approved funding for flood protection and early warning systems.',source_name:'Source',published_at:'2026-10-27T08:00:00+08:00',topics:['气候资金'],relevance_score:80}));
  qa.state.dashboard={meta:{date:'2026-10-27'},intelligence:records};qa.state.archive={records};
  return {qa,messages};
}
test('English today briefing uses the same twelve daily records',()=>{
  const {qa,messages}=setup();const plan=qa.planQuestion("Please provide today's climate briefing");
  assert.equal(plan.scope,'today');assert.equal(plan.intent,'brief');assert.equal(qa.selectEvidence(plan).records.length,12);
  qa.answerQuestion("Please provide today's climate briefing");
  assert.equal((messages[1].match(/<li>/g)||[]).length,12);assert(!/[\u3400-\u9fff]/.test(messages[1]));
});
test('English country comparison and follow-up recognise time and intent',()=>{
  const {qa,messages}=setup();const plan=qa.planQuestion('Compare China and US climate intelligence this week');
  assert.equal(plan.scope,'week');assert.equal(plan.intent,'compare');assert.equal(plan.entities.length,2);
  qa.answerQuestion('Compare China and US climate intelligence this week');assert(!/[\u3400-\u9fff]/.test(messages[1]));
  qa.state.assistant.lastPlan=plan;assert.equal(qa.planQuestion('What do these imply?').scope,'week');
});
test('Chinese briefing also returns all daily records',()=>{
  const {qa,messages}=setup('zh');qa.answerQuestion('请给出今日简报');assert.equal((messages[1].match(/<li>/g)||[]).length,12);
});
