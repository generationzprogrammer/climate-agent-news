import {test} from "node:test";
import assert from "node:assert/strict";
import worker, {BudgetGuard, retrieve, normalizeResult} from "../cloudflare/bth-assistant/src/index.mjs";
const rows = ["北京市", "天津市", "河北省"].flatMap((region, i) => [
  {id: `D-O${i}`, kind: "observation", title: "光伏装机", metric: "solar", region, year: 2025, value: i * 100 + 1, unit: "万千瓦", url: "https://example.gov.cn/data"},
  {id: `P-${i}`, kind: "policy", title: "可再生能源政策", region, date: "2026-01-01", url: "https://example.gov.cn/policy"},
]);
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
    const data = JSON.stringify({choices: [{delta: {content: JSON.stringify(modelResult)}, finish_reason: "stop"}]});
    return new Response(`data: ${data}\n\ndata: [DONE]\n\n`);
  };
  try {
    const pending = [], env = {BTH_LLM_API_KEY: "TEST-NOT-A-CREDENTIAL", BTH_TURNSTILE_SECRET_KEY: "TEST-NOT-A-CREDENTIAL", BUDGET: {idFromName: x => x, get: () => ({fetch: async () => new Response('{"ok":true}')})}};
    const response = await worker.fetch(new Request("https://worker/chat", {method: "POST", headers: {Origin: "https://generationzprogrammer.github.io", "Content-Type": "application/json"}, body: JSON.stringify({question: "三地光伏比较，生成报告", token: "TEST"})}), env, {waitUntil: p => pending.push(p)});
    assert.equal(response.status, 200); const body = await response.text(); await Promise.all(pending);
    assert(body.includes("event: result")); assert(body.includes("三地光伏装机比较")); assert.equal(calls, 1);
  } finally {globalThis.fetch = originalFetch; globalThis.caches = originalCaches;}
});
