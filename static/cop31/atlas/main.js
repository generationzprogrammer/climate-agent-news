// GREEN · COP31 — 全球事件地图 as the 融观 globe (2026-11-10, user: 把全球事件现场的地球改为参考的「融观地球」的一模一样的
// 样式，点击某个地点，再蹦出新闻). This entry feeds the package's atlas (atlas-view.js) with the page's own events:
// app.js stays in charge of the data — it draws its SVG pins (#worldMap, kept in the page as the accessible layer and
// the map stamp's miniature) and the place list for today / this week, in the page language; the items those show
// (dashboard.json: map_events* / map_queue*) become the atlas's points, one globe marker per place. A marker or a place
// button unfolds the globe into the map on that place and opens its news popup. Loaded by cop31/earth-atlas.js when
// the home page is idle; if the globe cannot start (no WebGL 2), the page keeps app.js's flat map and note.
import {atlasMarkup,mountAtlas,disposeAtlas} from './atlas-view.js';
import {en,t} from './i18n.js';
const HUB={coords:[30.71,36.9],label:'ANTALYA · COP31'}; // the COP31 host city: where the arcs rise from
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// app.js's own helpers (globals of the page), so the popup reads exactly as its note did, in either language
const app={
 record:item=>{try{return findArchiveRecord(item)||item;}catch{return item;}},
 place:item=>{try{return mapPlaceName(item)||item.place;}catch{return item.place;}},
 title:record=>{try{return field(record,'title_zh','title_original');}catch{return record.title_zh||record.title_original;}},
 summary:record=>{try{return summaryOrAtoms(record)||'';}catch{return record.summary_zh?`<p>${esc(record.summary_zh)}</p>`:'';}},
 date:value=>{try{return formatDate(value);}catch{return String(value||'').slice(0,10);}},
 url:value=>{try{return safeUrl(value);}catch{return '#';}},
 source:()=>{try{return tr('source');}catch{return t('查看原文','Source');}},
 theme:item=>{try{return state.language==='en'?(state.mode==='energy'?'Energy technology':'Climate'):item.theme;}catch{return item.theme;}},
 countries:()=>{try{return new Set((state.taxonomy?.countries||[]).map(row=>row.name_zh));}catch{return new Set();}},
};
export async function boot(){
 const section=document.getElementById('map'),host=document.getElementById('mapCanvas'),svg=document.getElementById('worldMap'),places=document.getElementById('mapPlaceList');
 if(!section||!host||!svg)throw Error('atlas: the map section is missing');
 const json=url=>fetch(url).then(r=>{if(!r.ok)throw Error('atlas: '+url+' '+r.status);return r.json();});
 const [geo,dashboard]=await Promise.all([json(new URL('./geography/countries.json',import.meta.url)),window.GreenLoad?.json('./data/dashboard.json')??json(new URL('./data/dashboard.json',document.baseURI))]);
 const byId=new Map(['map_events','map_events_week','map_events_today','map_queue_week','map_queue_today'].flatMap(key=>dashboard[key]||[]).map(item=>[item.marker_id,item]));
 const toggle=host.querySelector('.map-period-toggle');
 // The points now on the page: app.js's pins (located) and the rest of its queue (the place list), in its order.
 function current(){
  const pins=new Set([...svg.querySelectorAll('.event-pin[data-marker]')].map(pin=>pin.dataset.marker));
  const ids=[...new Set([...pins,...[...(places?.querySelectorAll('[data-map-id]')||[])].map(b=>b.dataset.mapId)])],nations=app.countries();
  return ids.map(id=>byId.get(id)).filter(Boolean).map(item=>{
   const record=app.record(item),lon=Number(item.lon),lat=Number(item.lat),located=pins.has(item.marker_id)&&Number.isFinite(lon)&&Number.isFinite(lat);
   return {id:item.marker_id,country:app.place(item),label:app.theme(item),coords:located?[lon,lat]:null,precision:nations.has(item.place)||item.place==='欧盟'?'country':'city',
    title:app.title(record)||item.title_zh||item.title_original||'',summaryHtml:app.summary(record),date:app.date(item.published_at),url:app.url(item.url)};
  });
 }
 let api=null,language=null,timer=0,key='';
 const signature=list=>list.map(c=>c.id+(c.coords?'':'~')).join('|');
 async function mount(){
  const list=current();language=en();key=signature(list);
  if(toggle&&toggle.parentElement!==host)host.prepend(toggle);
  disposeAtlas();host.querySelector('.atlas-view')?.remove();
  host.insertAdjacentHTML('afterbegin',atlasMarkup());
  if(toggle)host.querySelector('.atlas-view-slot').append(toggle);
  api=mountAtlas(list,geo,{hub:HUB,sourceLabel:app.source()});
  if(!api||!(await api.mounted)){ // no WebGL 2: back to app.js's flat map and its note
   disposeAtlas();if(toggle)host.prepend(toggle);host.querySelector('.atlas-view')?.remove();api=null;
   section.classList.remove('atlas-wait','atlas-on');throw Error('atlas: the globe is unavailable');
  }
  section.classList.add('atlas-on');section.classList.remove('atlas-wait');
 }
 // app.js redraws its pins and place list on load, on a period switch and on a language switch: follow it.
 const sync=()=>{clearTimeout(timer);timer=setTimeout(()=>{if(!api)return;if(en()!==language){mount().catch(error=>console.error(error));return;}const list=current(),next=signature(list);if(next!==key){key=next;api.setCases(list);}},80);};
 new MutationObserver(sync).observe(svg,{childList:true});
 if(places)new MutationObserver(sync).observe(places,{childList:true});
 // A place button under the globe opens that item: the map on its place with its news (app.js still notes the pick).
 places?.addEventListener('click',event=>{const button=event.target.closest('[data-map-id]');if(!button||!api)return;const list=current(),item=list.find(c=>c.id===button.dataset.mapId);if(item)api.open(item.coords?item.country:'',item.id);});
 // Leaving the home page (back / forward) while the map fills the window: start again from the globe.
 addEventListener('cop31:page',event=>{if(api&&event.detail?.page!=='home'&&(api.mode==='2d'||api.busy))mount().catch(error=>console.error(error));});
 await mount();
}
