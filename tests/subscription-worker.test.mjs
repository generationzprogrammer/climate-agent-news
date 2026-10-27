import {test} from "node:test";
import assert from "node:assert/strict";
import worker from "../cloudflare/subscription-worker/src/index.js";
const origin="https://generationzprogrammer.github.io";
function setup(){const records=new Map();return {records,env:{CLIMATE_SUBSCRIBER_ADMIN_TOKEN:"TEST-NOT-A-REAL-SECRET",CLIMATE_SUBSCRIBERS_KV:{put:async(k,v)=>records.set(k,JSON.parse(v)),get:async k=>records.get(k),delete:async k=>records.delete(k),list:async()=>({list_complete:true,keys:[...records.keys()].map(name=>({name}))})}}};}
const request=(email,path="subscribe")=>new Request(`https://service.test/${path}`,{method:"POST",headers:{Origin:origin,"Content-Type":"text/plain;charset=UTF-8"},body:JSON.stringify({email})});
test("independent subscribers enter the same weekly list, not an owner allowlist",async()=>{
  const {env,records}=setup();for(const email of ["reader-one@example.com","reader-two@example.net"]){const r=await worker.fetch(request(email),env);assert.equal(r.status,201);assert.equal((await r.json()).status,"subscribed");}
  assert.equal(records.size,2);assert([...records.keys()].every(k=>/^subscriber:[a-f0-9]{64}$/.test(k)));
  const response=await worker.fetch(new Request("https://service.test/subscribers",{headers:{Authorization:`Bearer ${env.CLIMATE_SUBSCRIBER_ADMIN_TOKEN}`}}),env);
  assert.equal((await response.json()).subscribers.length,2);
});
test("unsubscribe removes only the requested address",async()=>{
  const {env,records}=setup();await worker.fetch(request("reader-one@example.com"),env);await worker.fetch(request("reader-two@example.net"),env);
  assert.equal((await (await worker.fetch(request("reader-one@example.com","unsubscribe"),env)).json()).status,"unsubscribed");assert.equal(records.size,1);
});
test("public visitors cannot read the private list or use an unapproved origin",async()=>{
  const {env,records}=setup();assert.equal((await worker.fetch(new Request("https://service.test/subscribers"),env)).status,401);
  assert.equal((await worker.fetch(new Request("https://service.test/subscribe",{method:"POST",headers:{Origin:"https://other.invalid"},body:JSON.stringify({email:"reader-one@example.com"})}),env)).status,403);assert.equal(records.size,0);
});
test("language updates preserve a single private record and legacy users default to Chinese",async()=>{
  const {env,records}=setup();await worker.fetch(request("reader@example.com"),env);
  assert.equal([...records.values()][0].language,"zh");
  const r=await worker.fetch(new Request('https://service.test/subscribe',{method:'POST',headers:{Origin:origin},body:JSON.stringify({email:'reader@example.com',language:'en'})}),env);
  assert.equal((await r.json()).language,'en');assert.equal(records.size,1);
  const list=await worker.fetch(new Request('https://service.test/subscribers',{headers:{Authorization:`Bearer ${env.CLIMATE_SUBSCRIBER_ADMIN_TOKEN}`}}),env);
  assert.equal((await list.json()).preferences[0].language,'en');
});
