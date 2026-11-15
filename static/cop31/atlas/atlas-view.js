// 融观地球 (源码包 2026-11-10) on the GREEN · COP31 page — the flow between the globe and the map.
// Kept from the package: the stage, the approach flight, the unfold / fold on one mesh, the immersive viewport.
// Changed for this site (2026-11-10): the points can be replaced (setCases), a place can be opened from outside
// (open: the place list under the globe), the map opens with the picked place's news popup, Esc goes back, the wheel
// stays inside the immersive stage; the bar has a slot for the page's own today / this week switch.
import {mountDetailMap,prewarmDetailMap} from './detail-map.js';
import {immersiveStage} from './immersive-stage.js';
import {t} from './i18n.js';
let release=()=>{},generation=0;
// GREEN (2026-11-10, user: 现在太慢了): the package's 1200 / 2450 / 700 ms, shortened; with the 320 ms opening a place
// is on the map with its news about 2.3 s after the click instead of 4.5 – 8 s.
const TIMING={approach:650,unfold:1250,retreat:420};
export function atlasMarkup(){return `<div class="atlas-view" data-theme="dark"><div class="atlas-view-bar"><span>${t('从地球总览，走近事件地点','From the globe to where the news is')}</span><div class="atlas-view-slot"></div><div class="atlas-view-toggle"><button type="button" data-atlas-mode="3d" aria-pressed="true">${t('地球总览','Globe')}</button><button type="button" data-atlas-mode="2d" aria-pressed="false">${t('事件地图','Map')}</button></div></div><div class="atlas-view-content" data-theme="dark"><div class="globe-loading" role="status">${t('正在准备地球…','Preparing the globe…')}</div></div></div>`;}
export function disposeAtlas(){generation++;release();release=()=>{};}
export function mountAtlas(cases,geo,options={}){
 const root=document.querySelector('.atlas-view');if(!root)return null;
 const content=root.querySelector('.atlas-view-content'),controller=new AbortController(),signal=controller.signal,version=generation;
 let globeLayer,mapLayer,disposeGlobe=()=>{},disposeMap=()=>{},attempt=0,busy=false,current='3d';const animations=new Set();
 const reduced=()=>matchMedia('(prefers-reduced-motion:reduce)').matches;
 const alive=request=>request===attempt&&version===generation&&!signal.aborted&&root.isConnected;
 const buttons=mode=>root.querySelectorAll('[data-atlas-mode]').forEach(b=>{b.setAttribute('aria-pressed',String(b.dataset.atlasMode===mode));b.disabled=busy;});
 const setHeight=()=>{if(immersive.active)return;const layer=current==='3d'?globeLayer:mapLayer;if(layer&&layer.scrollHeight)content.style.height=layer.scrollHeight+'px';};
 const immersive=immersiveStage(content,{signal,onExit:()=>setHeight()});
 const resize=new ResizeObserver(()=>{if(!busy)setHeight();});
 release=()=>{attempt++;controller.abort();immersive.dispose();resize.disconnect();animations.forEach(a=>a.cancel());disposeMap();disposeGlobe();};
 let ready;const mounted=new Promise(resolve=>{ready=resolve;});
 async function boot(){
  const request=++attempt;content.replaceChildren();globeLayer=document.createElement('div');globeLayer.className='atlas-globe-layer';content.append(globeLayer);
  try{const {mountGlobe}=await import('./globe.js');if(!alive(request)){ready(false);return;}disposeGlobe=mountGlobe(globeLayer,cases,geo,options);resize.observe(globeLayer);content.dataset.phase='globe';setHeight();ready(true);const warm=()=>{if(!signal.aborted&&!busy)prewarmDetailMap();};if('requestIdleCallback' in window)requestIdleCallback(warm,{timeout:2000});else setTimeout(warm,600);}
  catch(error){console.error('atlas: the globe did not start',error);ready(false);}
 }
 async function descend(country='',focus=''){
  if(busy||current==='2d')return;busy=true;const request=++attempt;buttons('3d');content.dataset.phase='preparing';
  const opening=immersive.enter();if(!alive(request))return;
  mapLayer=document.createElement('div');mapLayer.className='atlas-detail-layer is-current';Object.assign(mapLayer.style,{opacity:'0',pointerEvents:'none'});mapLayer.setAttribute('aria-hidden','true');content.append(mapLayer);
  // Prepare the hidden map at its final viewport size while the globe expands.
  mapLayer.style.setProperty('width',innerWidth+'px','important');mapLayer.style.setProperty('height',innerHeight+'px','important');
  try{
   const mounting=mountDetailMap(mapLayer,cases,country,()=>ascend(),signal,options);mounting.catch(()=>{});
   await opening;if(!alive(request))return;
   const result=await mounting;if(!alive(request)){result?.();return;}disposeMap=result||(()=>{});resize.observe(mapLayer);disposeMap.interactive?.(false);
   const view=disposeMap.getView();await opening;if(!alive(request))return;content.dataset.phase='approaching';globeLayer.suspendAtlas?.(false);
   const diagonal=Math.hypot(innerWidth,innerHeight);
   const approachDistance=Math.max(145,Math.min(290,Math.sqrt(10000+Math.pow(innerHeight*100/(Math.tan(19*Math.PI/180)*diagonal*1.04),2))));
   const approach=globeLayer.flyCamera(view.coords,approachDistance,TIMING.approach,false,.85);
   // the map's own layers get until the approach ends plus a moment; what is late joins after the unfold
   await Promise.all([opening,approach,Promise.race([disposeMap.ready,new Promise(resolve=>setTimeout(resolve,TIMING.approach+350))])]);if(!alive(request))return;
   mapLayer.style.removeProperty('width');mapLayer.style.removeProperty('height');
   const snapshot=await disposeMap.capture();if(!alive(request))return;
   globeLayer.suspendAtlas(true);content.dataset.phase='unfolding';
   await globeLayer.unfoldSurface({view,snapshot,duration:TIMING.unfold});if(!alive(request))return;
   mapLayer.removeAttribute('aria-hidden');mapLayer.style.opacity='1';globeLayer.style.opacity='0';
   if(!alive(request))return;globeLayer.style.pointerEvents='none';globeLayer.setAttribute('aria-hidden','true');globeLayer.suspendAtlas?.(true);mapLayer.style.pointerEvents='auto';disposeMap.interactive?.(true);current='2d';busy=false;content.dataset.phase='map';buttons('2d');setHeight();
   // GREEN: the picked place opens with its news (the given item, or the place's first).
   const first=focus||(country&&cases.find(c=>c.country===country&&Array.isArray(c.coords))?.id);if(first)disposeMap.openCase?.(first);
  }catch(e){if(!alive(request))return;disposeMap();mapLayer?.remove();mapLayer=null;current='3d';globeLayer.style.opacity='1';globeLayer.suspendAtlas?.(false);content.dataset.phase='globe';await globeLayer.flyCamera?.(globeLayer.getView().coords,globeLayer.homeDistance?.()??380,500,true,0);await immersive.exit();if(!alive(request))return;busy=false;buttons('3d');setHeight();console.error(e);}
 }
 async function ascend(){
  if(busy||current==='3d')return;busy=true;const request=++attempt;buttons('2d');content.dataset.phase='retreating';disposeMap.interactive?.(false);
  const snapshot=await disposeMap.capture();if(!alive(request))return;const view=disposeMap.getView();
  globeLayer.style.opacity='0';globeLayer.style.pointerEvents='none';globeLayer.removeAttribute('aria-hidden');globeLayer.suspendAtlas(true);
  await globeLayer.flyCamera(view.coords,globeLayer.homeDistance?.()??380,0,false,.85);if(!alive(request))return;
  content.dataset.phase='folding';
  const morph=globeLayer.unfoldSurface({view,snapshot,reverse:true,duration:TIMING.unfold});
  globeLayer.style.opacity='1';mapLayer.style.opacity='0';
  await morph;if(!alive(request))return;
  await globeLayer.flyCamera(view.coords,globeLayer.homeDistance?.()??380,TIMING.retreat,true,0);if(!alive(request))return;
  if(!alive(request))return;resize.unobserve(mapLayer);disposeMap();disposeMap=()=>{};mapLayer.remove();mapLayer=null;globeLayer.style.pointerEvents='auto';globeLayer.querySelector('#globe-country').value='';current='3d';content.dataset.phase='globe';await immersive.exit();if(!alive(request))return;globeLayer.suspendAtlas(false);busy=false;buttons('3d');setHeight();
 }
 const click=event=>{const country=event.target.closest('.globe-marker[data-country],.globe-selection [data-country]');if(country){event.preventDefault();event.stopPropagation();descend((event.detail>0&&globeLayer.pickCountryAt?.(event.clientX,event.clientY))||country.dataset.country);return;}const b=event.target.closest('[data-atlas-mode],[data-fallback-2d]');if(b){event.stopPropagation();if(busy)return;if(b.dataset.atlasMode==='3d')ascend();else descend();}};
 const change=event=>{if(event.target.id==='globe-country'&&event.target.value){event.stopPropagation();descend(event.target.value);}};
 root.addEventListener('click',click,{capture:true,signal});content.addEventListener('click',click,{capture:true,signal});root.addEventListener('change',change,{capture:true,signal});content.addEventListener('change',change,{capture:true,signal});
 // GREEN: while the stage fills the window, Esc closes the open news first and then returns to the globe, and
 // the wheel does not reach the page behind (lists inside the stage still scroll).
 document.addEventListener('keydown',event=>{if(event.key!=='Escape'||!immersive.active)return;event.preventDefault();event.stopPropagation();if(current==='2d'&&!busy&&!disposeMap.closePopup?.())ascend();},{capture:true,signal});
 content.addEventListener('wheel',event=>{if(!immersive.active)return;event.stopPropagation();if(!event.target.closest?.('.leaflet-popup,.detail-map-note details'))event.preventDefault();},{passive:false,signal});

 boot();
 return {mounted,
  setCases(next){cases=next;globeLayer?.setCases?.(next);},
  open(country='',focus=''){return descend(country,focus);},
  get mode(){return current;},get busy(){return busy;}};
}
