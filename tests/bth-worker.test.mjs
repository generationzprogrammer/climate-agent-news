import {test} from "node:test";
import assert from "node:assert/strict";
import worker, {BudgetGuard, retrieve, normalizeResult, collectModelStream} from "../cloudflare/bth-assistant/src/index.mjs";
const rows = ["北京市", "天津市", "河北省"].flatMap((region, i) => [
  {id: `D-O${i}`, kind: "observation", title: "光伏装机", metric: "solar", region, year: 2025, value: i * 100 + 1, unit: "万千瓦", url: "https://example.gov.cn/data"},
  {id: `P-${i}`, kind: "policy", title: "可再生能源政策", region, date: "2026-01-01", url: "https://example.gov.cn/policy"},
]);

test("challenge-free mode reports readiness without a Turnstile secret", async () => {
  const response=await worker.fetch(new Request("https://worker/health"),{BTH_VERIFICATION_MODE:"off",BTH_LLM_API_KEY:"TEST",BUDGET:{}},{});
  const payload=await response.json(); assert.equal(payload.ready,true); assert.equal(payload.verification,"off");
});

test("challenge-free requests still reserve the server budget before model calls", async () => {
  const original=globalThis.fetch; let calls=0;
  globalThis.fetch=async()=>{calls++;throw Error("must not call any upstream");};
  try {
    const response=await worker.fetch(new Request("https://worker/chat",{method:"POST",headers:{Origin:"https://generationzprogrammer.github.io","Content-Type":"text/plain"},body:JSON.stringify({question:"北京能源",transport:"json",verification:"off"})}),{BTH_VERIFICATION_MODE:"off",BTH_LLM_API_KEY:"TEST",BUDGET:{idFromName:x=>x,get:()=>({fetch:async()=>new Response('{"error":"daily_limit"}',{status:429})})}},{});
    assert.equal(response.status,429); assert.equal((await response.json()).error,"daily_limit"); assert.equal(calls,0);
  } finally {globalThis.fetch=original;}
});

test("client cannot disable required server verification", async () => {
  const response=await worker.fetch(new Request("https://worker/chat",{method:"POST",headers:{Origin:"https://generationzprogrammer.github.io"},body:JSON.stringify({question:"北京",verification:"off"})}),{BTH_LLM_API_KEY:"TEST",BUDGET:{}},{});
  assert.equal(response.status,503);
});

test("subscription relay has fixed public routes and requires explicit acknowledgement", async () => {
  const original=globalThis.fetch; let destination;
  globalThis.fetch=async(url,init)=>{destination=String(url);assert.equal(init.headers.Origin,"https://generationzprogrammer.github.io");return new Response('{"ok":true,"status":"subscribed"}');};
  const request=()=>new Request("https://worker/subscriptions/subscribe",{method:"POST",headers:{Origin:"https://generationzprogrammer.github.io"},body:JSON.stringify({email:"test@example.com",url:"https://attacker.example"})});
  try {
    assert.equal((await worker.fetch(request(),{},{})).status,200);
    assert.equal(destination,"https://climate-news-subscriptions.1090697345.workers.dev/subscribe");
    globalThis.fetch=async()=>new Response('<html>Verifying...</html>');
    assert.equal((await worker.fetch(request(),{},{})).status,502);
    const denied=await worker.fetch(new Request("https://worker/subscriptions/subscribers",{headers:{Origin:"https://generationzprogrammer.github.io"}}),{},{});
    assert.equal(denied.status,404);
  } finally {globalThis.fetch=original;}
});
test("retrieval keeps all three provinces", () => {const selected = retrieve(rows, "比较三地光伏装机2025年"); assert.equal(new Set(selected.filter(r => r.kind === "observation").map(r => r.region)).size, 3);});
test("follow-up inherits region", () => {assert(retrieve(rows, "生成报告", [{role: "user", content: "北京光伏"}]).every(r => r.region === "北京市"));});
test("invalid references and fabricated charts cannot enter artifact", () => {
  const result = normalizeResult({answer: "比较[D-O0]与[D-fake]", charts: [{observation_ids: ["D-O0", "D-fake"]}], source_ids: ["D-fake"]}, rows);
  assert.equal(result.charts.length, 0); assert.equal(result.sources.length, 1); assert(result.answer.includes("引用无效"));
});
test("chart values come from observations, not model", () => {const result = normalizeResult({answer: "结论", charts: [{observation_ids: ["D-O0", "D-O1"], values: [999, 999]}]}, rows); assert.deepEqual(result.charts[0].points.map(p => p.value), [1, 101]);});
test("different units and metrics not mixed", () => {const other = {...rows[2], metric: "gdp", unit: "亿元"}; assert.equal(normalizeResult({answer: "测试", charts: [{observation_ids: ["D-O0", other.id]}]}, [rows[0], other]).charts.length, 0);});
test("missing secrets fail closed without upstream call", async () => {
  const result = await worker.fetch(new Request("https://worker/chat", {method: "POST", headers: {Origin: "https://generationzprogrammer.github.io"}}), {}, {}); assert.equal(result.status, 503);
});
test("untrusted origin refused", async () => {const result = await worker.fetch(new Request("https://worker/chat", {method: "POST", headers: {Origin: "https://attacker.example"}}), {}, {}); assert.equal(result.status, 403);});
test("budget is atomic and persists only counters", async () => {
  let value; const storage = {get: async () => value, put: async (_, data) => {value = data;}, setAlarm: async () => {}, deleteAll: async () => {value = undefined;}};
  const guard = new BudgetGuard({storage, blockConcurrencyWhile: callback => callback()}, {BTH_DAILY_LIMIT: "1"});
  const request = key => new Request("https://budget/reserve", {method: "POST", body: JSON.stringify({key})});
  assert.equal((await guard.fetch(request("a".repeat(64)))).status, 200);
  assert.equal((await guard.fetch(request("b".repeat(64)))).status, 429);
  assert.equal(value.total, 1); assert(!JSON.stringify(value).includes("question"));
});
test("full route streams validated report and evidence without real API", async () => {
  const originalFetch = globalThis.fetch, originalCaches = globalThis.caches;
  const modelResult = {answer: "三地装机比较[D-O0][D-O1]", source_ids: ["D-O0", "D-O1"], report: {title: "三地光伏装机比较", sections: [{heading: "规模", paragraphs: ["北京市1万千瓦[D-O0]。"]}]}, charts: [{title: "光伏装机", observation_ids: ["D-O0", "D-O1"]}]};
  let calls = 0;
  globalThis.caches = {default: {match: async () => new Response(JSON.stringify({schema_version: 1, records: rows})), put: async () => {}}};
  globalThis.fetch = async (url, options) => {
    if (String(url).includes("siteverify")) return new Response(JSON.stringify({success: true, hostname: "generationzprogrammer.github.io", action: "bth_chat"}));
    calls++; const payload = JSON.parse(options.body); assert.equal(payload.enable_thinking, false); assert.equal(payload.max_tokens, 4096);
    assert(payload.messages[0].content.includes("不要以数据库"));
    const data = JSON.stringify({choices: [{delta: {content: JSON.stringify(modelResult)}, finish_reason: "stop"}]});
    return new Response(`data: ${data}\n\ndata: [DONE]\n\n`);
  };
  try {
    const pending = [], env = {BTH_LLM_API_KEY: "TEST-NOT-A-CREDENTIAL", BTH_TURNSTILE_SECRET_KEY: "TEST-NOT-A-CREDENTIAL", BUDGET: {idFromName: x => x, get: () => ({fetch: async () => new Response('{"ok":true}')})}};
    for (const transport of ["stream", "json"]) {
      const response = await worker.fetch(new Request("https://worker/chat", {method: "POST", headers: {Origin: "https://generationzprogrammer.github.io", "Content-Type": transport === "stream" ? "text/plain;charset=UTF-8" : "application/json"}, body: JSON.stringify({question: "三地光伏比较，生成报告", token: "TEST", transport})}), env, {waitUntil: p => pending.push(p)});
      assert.equal(response.status, 200); const body = await response.text(); await Promise.all(pending);
      assert(body.includes("三地光伏装机比较"));
      if (transport === "stream") assert(body.includes("event: result"));
      else {assert(response.headers.get("Content-Type").includes("application/json")); assert.equal(JSON.parse(body).sources.length,2);}
    }
    assert.equal(calls, 2, "one provider call per request, no retry");
  } finally {globalThis.fetch = originalFetch; globalThis.caches = originalCaches;}
});

test("mobile transport decodes split UTF-8 and the final unterminated frame", async () => {
  const encoded = new TextEncoder().encode('data:' + JSON.stringify({choices:[{delta:{content:JSON.stringify({answer:"北京**绿色治理**",charts:[],source_ids:[]})},finish_reason:"stop"}]}));
  const stream = new ReadableStream({start(c) {for (let i=0;i<encoded.length;i+=2) c.enqueue(encoded.slice(i,i+2)); c.close();}});
  assert.equal((await collectModelStream(new Response(stream))).answer, "北京**绿色治理**");
});

test("truncated or invalid model JSON fails instead of giving an empty mobile answer", async () => {
  const response = finish => new Response("data: " + JSON.stringify({choices:[{delta:{content:'{"answer":"unfinished'},finish_reason:finish}]}));
  await assert.rejects(collectModelStream(response("length")), /output_truncated/);
  await assert.rejects(collectModelStream(response("stop")), SyntaxError);
});

test("policy targets cannot become actual-value charts", () => {
  const target = {...rows[0], id:"P-target_bj",kind:"target", value:14.4};
  assert.equal(normalizeResult({answer:"目标分析",charts:[{observation_ids:[target.id,rows[2].id]}]},[target,rows[2]]).charts.length,0);
  assert(retrieve([target,...rows],"北京目标追踪").some(r => r.kind === "target"));
});

test("mobile gets response headers and connected status before slow verification", async () => {
  const originalFetch = globalThis.fetch; let release, calls = 0;
  const stalled = new Promise(resolve => {release = resolve;});
  globalThis.fetch = async () => {calls++; await stalled; return new Response(JSON.stringify({success:false}));};
  const pending = [];
  try {
    const response = await worker.fetch(new Request("https://worker/chat", {method:"POST",headers:{Origin:"https://generationzprogrammer.github.io","Content-Type":"application/json"},body:JSON.stringify({question:"北京气候治理",token:"TEST",transport:"stream"})}), {BTH_LLM_API_KEY:"TEST",BTH_TURNSTILE_SECRET_KEY:"TEST",BUDGET:{}}, {waitUntil:p=>pending.push(p)});
    assert.equal(response.status,200); assert(response.headers.get("Cache-Control").includes("no-transform"));
    const reader = response.body.getReader(), decoder = new TextDecoder();
    let text = decoder.decode((await reader.read()).value);
    text += decoder.decode((await reader.read()).value);
    assert(text.includes('"phase":"connected"'), "must not wait for model or verification");
    release(); while (true) {const chunk = await reader.read(); if (chunk.done) break; text += decoder.decode(chunk.value);}
    await Promise.all(pending); assert(text.includes("verification_failed")); assert.equal(calls,1, "verification failure must never call model");
  } finally {release(); globalThis.fetch = originalFetch;}
});

test("disconnect before verification completes does not spend model quota", async () => {
  const originalFetch = globalThis.fetch; let release, calls = 0;
  const stalled = new Promise(resolve => {release = resolve;});
  globalThis.fetch = async () => {calls++; await stalled; return new Response(JSON.stringify({success:true,hostname:"generationzprogrammer.github.io",action:"bth_chat"}));};
  const pending = [];
  try {
    const response = await worker.fetch(new Request("https://worker/chat", {method:"POST",headers:{Origin:"https://generationzprogrammer.github.io","Content-Type":"application/json"},body:JSON.stringify({question:"北京气候治理",token:"TEST"})}), {BTH_LLM_API_KEY:"TEST",BTH_TURNSTILE_SECRET_KEY:"TEST",BUDGET:{}}, {waitUntil:p=>pending.push(p)});
    await response.body.cancel(); release(); await Promise.all(pending);
    assert.equal(calls,1, "only verification, no model request after cancellation");
  } finally {release(); globalThis.fetch = originalFetch;}
});
