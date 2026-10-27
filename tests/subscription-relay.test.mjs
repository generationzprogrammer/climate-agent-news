import {test} from 'node:test';
import assert from 'node:assert/strict';
import relay from '../cloudflare/subscription-relay/_worker.js';
test('Pages uses service binding, retains language and refuses list access',async()=>{
 let calls=0;
 const env={SUBSCRIPTIONS:{fetch:async request=>{calls++;assert.equal(request.url,'https://climate-news-subscriptions.1090697345.workers.dev/subscribe');assert.equal((await request.json()).language,'en');return Response.json({ok:true,status:'subscribed',language:'en'},{status:201});}}};
 const response=await relay.fetch(new Request('https://relay.pages.dev/subscribe',{method:'POST',headers:{Origin:'https://generationzprogrammer.github.io'},body:JSON.stringify({email:'reader@example.invalid',language:'en'})}),env);
 assert.equal(response.status,201);assert.equal((await response.json()).language,'en');assert.equal(calls,1);
 const denied=await relay.fetch(new Request('https://relay.pages.dev/subscribers',{headers:{Origin:'https://generationzprogrammer.github.io'}}),env);assert.equal(denied.status,404);assert.equal(calls,1);
 const foreign=await relay.fetch(new Request('https://relay.pages.dev/subscribe',{method:'POST',headers:{Origin:'https://foreign.invalid'},body:'{}'}),env);assert.equal(foreign.status,403);
});
