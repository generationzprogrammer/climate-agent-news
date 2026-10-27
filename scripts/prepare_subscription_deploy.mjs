// Preserve the existing private KV binding. Never print settings or credentials.
import {writeFileSync, mkdirSync, copyFileSync} from 'node:fs';
import {resolve} from 'node:path';
const account=process.env.CLOUDFLARE_ACCOUNT_ID, token=process.env.CLOUDFLARE_API_TOKEN;
if(!account||!token)throw Error('Missing Cloudflare deployment configuration');
const base=`https://api.cloudflare.com/client/v4/accounts/${account}`;
const headers={Authorization:`Bearer ${token}`,'Content-Type':'application/json'};
async function api(path, options={}) {
  const response=await fetch(base+path,{...options,headers,signal:AbortSignal.timeout(20000)});
  const data=await response.json();
  if(!response.ok||!data.success)throw Error(`Cloudflare API HTTP ${response.status}`);
  return data.result;
}
const settings=await api('/workers/scripts/climate-news-subscriptions/settings');
const binding=settings.bindings.find(x=>x.name==='CLIMATE_SUBSCRIBERS_KV'&&x.type==='kv_namespace');
if(!binding?.namespace_id)throw Error('Existing private subscriber KV binding not found; deployment stopped');
const dir=resolve('.subscription-deploy');mkdirSync(dir,{recursive:true});
writeFileSync(resolve(dir,'wrangler.json'),JSON.stringify({name:'climate-news-subscriptions',main:resolve('cloudflare/subscription-worker/src/index.js'),compatibility_date:'2026-10-01',workers_dev:true,keep_vars:true,kv_namespaces:[{binding:'CLIMATE_SUBSCRIBERS_KV',id:binding.namespace_id}],observability:{enabled:false}}));
console.log('Existing subscriber KV binding preserved; no new subscriber database created.');
if(process.argv.includes('--pages')) {
  const name='gruen-climate-subscriptions';
  try {
    const projects=await api('/pages/projects');
    if(!projects.some(x=>x.name===name))await api('/pages/projects',{method:'POST',body:JSON.stringify({name,production_branch:'main'})});
    mkdirSync(resolve(dir,'pages'),{recursive:true});
    copyFileSync('cloudflare/subscription-relay/_worker.js',resolve(dir,'pages/_worker.js'));
    writeFileSync(resolve(dir,'pages/index.html'),'<!doctype html><title>GREEN subscription service</title><p>GREEN subscription service</p>');
    writeFileSync(resolve(dir,'pages.wrangler.json'),JSON.stringify({name,pages_build_output_dir:'./pages',compatibility_date:'2026-10-01',services:[{binding:'SUBSCRIPTIONS',service:'climate-news-subscriptions'}]}));
    writeFileSync(resolve(dir,'pages-ready'),'ready');
    console.log('Pages subscription relay project ready.');
  } catch(error) { console.log('Pages relay not deployed: Pages Edit permission may be required. Existing Worker remains unchanged by this optional step.'); }
}
