import {test} from 'node:test';
import assert from 'node:assert/strict';
import relay from '../cloudflare/subscription-relay/_worker.js';
import primary from '../cloudflare/subscription-worker/src/index.js';
test('Pages writes the same private weekly list, retains language and refuses public list access',async()=>{
 const records=new Map();
 const kv={put:async(k,v)=>records.set(k,JSON.parse(v)),get:async k=>records.get(k),delete:async k=>records.delete(k),list:async()=>({list_complete:true,keys:[...records.keys()].map(name=>({name}))})};
 const env={CLIMATE_SUBSCRIBERS_KV:kv};
 const response=await relay.fetch(new Request('https://relay.pages.dev/subscribe',{method:'POST',headers:{Origin:'https://generationzprogrammer.github.io'},body:JSON.stringify({email:'reader@example.invalid',language:'en'})}),env);
 assert.equal(response.status,201);assert.equal((await response.json()).language,'en');assert.equal(records.size,1);
 const list=await primary.fetch(new Request('https://primary.test/subscribers',{headers:{Authorization:'Bearer TEST'}}),{...env,CLIMATE_SUBSCRIBER_ADMIN_TOKEN:'TEST'});
 assert.equal((await list.json()).preferences[0].language,'en');
 const denied=await relay.fetch(new Request('https://relay.pages.dev/subscribers',{headers:{Origin:'https://generationzprogrammer.github.io'}}),env);assert.equal(denied.status,404);
 const foreign=await relay.fetch(new Request('https://relay.pages.dev/subscribe',{method:'POST',headers:{Origin:'https://foreign.invalid'},body:'{}'}),env);assert.equal(foreign.status,403);
});
