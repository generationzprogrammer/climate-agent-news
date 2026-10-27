// Alternative hostname, same private subscription service. No list or secrets here.
const upstream='https://climate-news-subscriptions.1090697345.workers.dev';
const allowed='https://generationzprogrammer.github.io';
export default {async fetch(request) {
  const path=new URL(request.url).pathname;
  const origin=request.headers.get('Origin');
  const headers={'Access-Control-Allow-Origin':allowed,'Vary':'Origin','Cache-Control':'no-store','Content-Type':'application/json','X-Content-Type-Options':'nosniff'};
  const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers});
  if(path==='/health')return reply({ok:true,service:'gruen-subscription-relay'});
  if(origin!==allowed)return reply({error:'origin_not_allowed'},403);
  if(!['/subscribe','/unsubscribe'].includes(path))return reply({error:'not_found'},404);
  if(request.method==='OPTIONS')return new Response(null,{status:204,headers:{...headers,'Access-Control-Allow-Methods':'POST,OPTIONS','Access-Control-Allow-Headers':'Content-Type'}});
  if(request.method!=='POST')return reply({error:'method_not_allowed'},405);
  if(Number(request.headers.get('Content-Length'))>2048)return reply({error:'request_too_large'},413);
  const body=await request.text();if(body.length>2048)return reply({error:'request_too_large'},413);
  try {
    const response=await fetch(upstream+path,{method:'POST',headers:{Origin:allowed,'Content-Type':'text/plain;charset=UTF-8'},body,redirect:'error',signal:AbortSignal.timeout(15000)});
    const result=await response.json();
    return reply(result,response.status);
  }catch{return reply({error:'subscription_unavailable'},502);}
}};
