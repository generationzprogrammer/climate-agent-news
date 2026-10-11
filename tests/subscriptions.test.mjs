import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {runInNewContext} from "node:vm";
const code=readFileSync(new URL("../static/subscriptions.js",import.meta.url),"utf8");
const setup=request=>{const window={GruenBthTransport:{request}};runInNewContext(code,{window,URL,AbortController,setTimeout,clearTimeout});return window.GruenSubscriptions;};
test("alternate route starts while primary is stalled and cancels outstanding request",async()=>{
  const calls=[];const api=setup(async(url,options)=>{calls.push({url,options});if(url.includes("slow"))return new Promise(()=>{});return {ok:true,status:"subscribed"};});
  assert.equal((await api.submit(["https://slow.test","https://good.test"],"synthetic@example.com","subscribe",{stagger:5,timeout:100})).status,"subscribed");
  assert.equal(calls.length,2);assert.equal(calls[0].options.signal.aborted,true);assert.equal(calls[0].options.accept,"application/json");
  assert(!calls[0].url.includes("@"));
});
test("unconfirmed response never becomes success",async()=>{
  const api=setup(async()=>({ok:true}));await assert.rejects(api.submit(["https://test.invalid"],"synthetic@example.com"),/subscription_not_confirmed/);
});
test("all failed routes reject rather than hanging",async()=>{
  const api=setup(async()=>{throw Error("network_unreachable");});await assert.rejects(api.submit(["https://a.test","https://b.test"],"synthetic@example.com","subscribe",{stagger:1,timeout:50}),/network_unreachable/);
});
test("retirement requires unsubscribe acknowledgement",async()=>{
  const api=setup(async()=>({ok:true,status:"unsubscribed"}));assert.equal((await api.submit(["https://test.invalid"],"synthetic@example.com","unsubscribe")).status,"unsubscribed");
});
test("insecure routes are not used and duplicate routes are removed",async()=>{
  let count=0;const api=setup(async()=>{count++;return {ok:true,status:"subscribed"};});await api.submit(["http://no.test","https://a.test","https://a.test"],"synthetic@example.com");assert.equal(count,1);
});
