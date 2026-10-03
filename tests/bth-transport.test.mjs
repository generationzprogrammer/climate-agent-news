import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";
const code = readFileSync(new URL("../static/bth-transport.js", import.meta.url), "utf8");
function setup() {
  let active;
  class XHR {
    constructor() {active = this; this.readyState = 0; this.responseText = ""; this.status = 0; this.headers = {};}
    open(method, url) {this.method = method; this.url = url; this.readyState = 1;}
    setRequestHeader(key, value) {this.headers[key] = value;}
    send(body) {this.body = body;}
    abort() {this.aborted = true; this.onabort?.();}
    getResponseHeader() {return this.type || "text/event-stream";}
    chunk(value) {this.status = 200; this.readyState = 3; this.responseText += value; this.onreadystatechange?.(); this.onprogress?.();}
    end(value = "") {this.status ||= 200; this.readyState = 4; this.responseText += value; this.onload?.();}
  }
  const window = {};
  runInNewContext(code, {window, XMLHttpRequest: XHR, DOMException});
  return {transport: window.GruenBthTransport, xhr: () => active};
}
const frame = (event, data) => `event: ${event}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`;
test("fragmented events and heartbeat comments do not lose Chinese text", () => {
  const {transport} = setup(), received = [];
  const parser = transport.eventParser((event, data) => received.push({event, data}));
  const text = ": heartbeat\r\n\r\n" + frame("delta", {text: "北京与天津"}) + frame("result", {answer: "河北省"});
  for (const char of text) parser(char);
  assert.equal(received.length, 2); assert.equal(received[0].data.text, "北京与天津");
});
test("mobile receives result before the connection ends, without Fetch streams", async () => {
  const {transport, xhr} = setup(), events = [];
  const pending = transport.request("https://example/chat", {method: "POST", payload: {transport: "stream"}, onEvent: (name) => events.push(name)});
  xhr().chunk(frame("status", {phase: "connected"}));
  assert.equal(xhr().headers["Content-Type"],"text/plain;charset=UTF-8");
  const result = frame("result", {answer: "北京绿色转型", sources: [], charts: []});
  xhr().chunk(result.slice(0, 22)); xhr().chunk(result.slice(22));
  assert.equal((await pending).answer, "北京绿色转型"); assert(xhr().aborted);
  assert.deepEqual(events, ["status", "result"]);
});
test("fully buffered mobile response and final frame without blank line work", async () => {
  const {transport, xhr} = setup();
  const pending = transport.request("https://example/chat", {method: "POST"});
  xhr().end(frame("result", {answer: "天津转型"}).trimEnd());
  assert.equal((await pending).answer, "天津转型");
});
test("streamed service errors reject, not an endless busy state", async () => {
  const {transport, xhr} = setup();
  const pending = transport.request("https://example/chat");
  xhr().chunk(frame("error", {error: "verification_failed"}));
  await assert.rejects(pending, /verification_failed/);
});
test("timeout, network failure and cancellation settle exactly once", async () => {
  for (const failure of ["ontimeout", "onerror", "abort"]) {
    const {transport, xhr} = setup(), controller = new AbortController();
    const pending = transport.request("https://example/chat", {signal: controller.signal});
    if (failure === "abort") controller.abort(); else xhr()[failure]();
    await assert.rejects(pending, error => failure === "abort" ? error.name === "AbortError" : /connection_timeout|network_unreachable/.test(error.message));
    assert(xhr().aborted); assert.equal(xhr().onload, null);
  }
});
test("health uses a ten second deadline and sends no question or token", async () => {
  const {transport, xhr} = setup();
  const pending = transport.health("https://example/");
  assert.equal(xhr().url, "https://example/health"); assert.equal(xhr().timeout, 10000); assert.equal(xhr().body, null);
  xhr().type = "application/json"; xhr().end('{"ok":true,"ready":true}'); await pending;
});
test("HTTP error details survive buffered non-stream responses", async () => {
  const {transport, xhr} = setup();
  const pending = transport.request("https://example/chat");
  xhr().status = 429; xhr().type = "application/json"; xhr().end('{"error":"daily_limit"}');
  await assert.rejects(pending, /daily_limit/);
});
