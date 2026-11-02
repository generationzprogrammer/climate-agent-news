import {test} from 'node:test';
import assert from 'node:assert/strict';
import assistant from '../cloudflare/bth-assistant/src/index.mjs';
import relay from '../cloudflare/subscription-relay/_worker.js';
const origins='https://generationzprogrammer.github.io,https://www.example.org';
test('assistant accepts only the explicitly configured old and new origins',async()=>{
  for(const origin of origins.split(',')){
    const r=await assistant.fetch(new Request('https://worker/chat',{method:'OPTIONS',headers:{Origin:origin}}),{BTH_ALLOWED_ORIGIN:origins},{});
    assert.equal(r.status,204);assert.equal(r.headers.get('access-control-allow-origin'),origin);
  }
  const r=await assistant.fetch(new Request('https://worker/chat',{method:'OPTIONS',headers:{Origin:'https://attacker.invalid'}}),{BTH_ALLOWED_ORIGIN:origins},{});assert.equal(r.status,403);
});
test('subscription relay accepts the configured origin without exposing administration',async()=>{
  const env={CLIMATE_ALLOWED_ORIGIN:origins,CLIMATE_SUBSCRIBERS_KV:{}};
  const r=await relay.fetch(new Request('https://relay/subscribe',{method:'OPTIONS',headers:{Origin:'https://www.example.org'}}),env);
  assert.equal(r.status,200);assert.equal(r.headers.get('access-control-allow-origin'),'https://www.example.org');
  assert.equal((await relay.fetch(new Request('https://relay/subscribers',{headers:{Origin:'https://www.example.org'}}),env)).status,404);
  assert.equal((await relay.fetch(new Request('https://relay/subscribe',{method:'OPTIONS',headers:{Origin:'https://attacker.invalid'}}),env)).status,403);
});
