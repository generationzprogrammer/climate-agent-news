// Alternative hostname, SAME private KV and validation code; no administrative secret.
import handler from '../subscription-worker/src/index.js';
const allowed='https://generationzprogrammer.github.io';
export default {async fetch(request, env) {
  const path=new URL(request.url).pathname;
  const origin=request.headers.get('Origin');
  const headers={'Access-Control-Allow-Origin':allowed,'Vary':'Origin','Cache-Control':'no-store','Content-Type':'application/json','X-Content-Type-Options':'nosniff'};
  const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers});
  if(path==='/health')return reply({ok:!!env.CLIMATE_SUBSCRIBERS_KV,service:'gruen-subscription-relay',version:'20261027-shared-kv'});
  if(origin!==allowed)return reply({error:'origin_not_allowed'},403);
  if(!['/subscribe','/unsubscribe'].includes(path))return reply({error:'not_found'},404);
  if(!env.CLIMATE_SUBSCRIBERS_KV)return reply({error:'service_not_configured'},503);
  return handler.fetch(request,{CLIMATE_SUBSCRIBERS_KV:env.CLIMATE_SUBSCRIBERS_KV,CLIMATE_ALLOWED_ORIGIN:allowed});
}};
