// 融观地球 (源码包 2026-11-10) on the GREEN · COP31 page — the 2D map the globe unfolds into.
// Kept from the package: Leaflet + the local imagery / regional layers + the online vector basemap, continuous zoom,
// golden-angle placement of points that share a location, the capture used by the fold / unfold.
// Changed for this site (2026-11-10): a point is a news item (place · theme, title, summary, date, source link) and
// its popup can be opened by id (the place picked on the globe opens with its news); items without a location are
// listed and open as a popup at the map centre; relative paths; texts follow <html lang>.
import {satelliteLayer} from './satellite-layer.js';
import {regionalLayer,preloadRegional} from './regional-layer.js';
import {detailedBasemap,preloadDetailedRuntime} from './detailed-basemap.js';
import {smoothMapZoom} from './smooth-map-zoom.js';
import {t} from './i18n.js';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const here=path=>new URL(path,import.meta.url).href;
let loading;
function library(){
 if(globalThis.L)return Promise.resolve(globalThis.L);
 if(!loading)loading=new Promise((resolve,reject)=>{const style=document.createElement('link');style.rel='stylesheet';style.href=here('./vendor/leaflet.css');document.head.append(style);const script=document.createElement('script');script.src=here('./vendor/leaflet.js');script.onload=()=>resolve(globalThis.L);script.onerror=()=>{loading=null;reject(Error('详细地图组件暂未加载'));};document.head.append(script);});
 return loading;
}
// GREEN (2026-11-10, user: 点击后进入事件地图要更快): everything the map needs that does not depend on the place is
// fetched while the globe is idle — the two libraries, the regional outlines / rivers / cities (3.7 MB of JSON that
// used to start downloading at the first click) and the connection to the tile server.
export function prewarmDetailMap(){
 if(!document.querySelector('link[data-atlas-tiles]')){const link=document.createElement('link');link.rel='preconnect';link.href='https://tiles.openfreemap.org';link.crossOrigin='anonymous';link.dataset.atlasTiles='';document.head.append(link);}
 return Promise.all([library(),preloadDetailedRuntime(),preloadRegional()]).catch(()=>{});
}
export async function mountDetailMap(host,cases,country,onBack,signal,options={}){
 const L=await library();if(signal.aborted||!host.isConnected)return ()=>{};
 const selected=cases,focus=country?cases.filter(c=>c.country===country):cases;
 const located=selected.filter(c=>Array.isArray(c.coords));
 const count=n=>t(`${n} 条新闻`,`${n} ${n===1?'story':'stories'}`);
 const precision=c=>!Array.isArray(c.coords)?t('未定位','no location'):c.precision==='city'?t('城市级位置','city-level location'):t('国家级概略位置','approximate national location');
 host.innerHTML=`<section class="detail-atlas" aria-label="${t('新闻地点地图','Map of news locations')}"><header class="detail-map-heading"><button type="button" class="button" data-back-globe>← ${t('返回地球','Back to the globe')}</button><div><h3>${esc(country||t('全球事件地图','Global event map'))}</h3><p>${t(`共 ${selected.length} 条新闻`,`${count(selected.length)} in all`)} · ${country?t(`当前地区 ${focus.length} 条`,`${focus.length} here`):t(`${located.length} 条有定位`,`${located.length} located`)}</p></div><span>${t('拖动浏览 · 滚轮缩放 · 点击地点查看新闻','Drag to move · wheel to zoom · pick a point for its news')}</span></header><div class="detail-map-stage"><div class="detail-map-canvas" role="region" aria-label="${t('可拖动缩放的详细地图','A map you can drag and zoom')}"></div><div class="detail-map-network" role="status" hidden></div></div><div class="detail-map-note">${t('实心点：城市级位置 · 空心点：国家级概略位置。重叠的新闻仅在屏幕上错开，不改变原始坐标。','Solid points: city-level locations · hollow points: approximate national locations. Items that overlap are only spread on screen; their coordinates are unchanged.')}<details><summary>${t(`查看全部 ${selected.length} 条新闻`,`All ${count(selected.length)}`)}</summary><div class="unlocated-cases">${selected.map(c=>`<button type="button" data-map-read="${esc(c.id)}">${esc(c.title)} <span>${esc(c.country)} · ${precision(c)} ↗</span></button>`).join('')}</div></details></div></section>`;
 const stage=host.querySelector('.detail-map-stage'),map=L.map(host.querySelector('.detail-map-canvas'),{zoomControl:false,worldCopyJump:false,maxBounds:[[-85.05112878,-180],[85.05112878,180]],maxBoundsViscosity:1,minZoom:2,maxZoom:18,zoomSnap:0,zoomDelta:.5,scrollWheelZoom:false});
 L.control.zoom({position:'bottomright'}).addTo(map);
 const smoothZoom=smoothMapZoom(L,map,host);
 let tiles,finishReady,readyTimer,disposed=false;
 const ready=new Promise(resolve=>{finishReady=()=>{clearTimeout(readyTimer);resolve();};});
 const notice=host.querySelector('.detail-map-network');
 let disposeRegional=()=>{};const regionReady=regionalLayer(L,map,country,()=>disposed).then(dispose=>{if(disposed)dispose?.();else disposeRegional=dispose;}).catch(()=>{notice.hidden=false;notice.textContent=t('区域资料暂未加载，仍可查看地球影像和事件点','Regional data did not load; the imagery and event points remain');});
 tiles=satelliteLayer(L);tiles.on('tileerror',()=>{notice.hidden=false;notice.textContent=t('影像加载暂不可用，事件点位仍可浏览','The imagery is unavailable; the event points remain');finishReady();});tiles.on('load',()=>{host.dataset.tileState='ready';finishReady();});readyTimer=setTimeout(finishReady,5000);tiles.addTo(map);
 let disposeDetailed=()=>{},finishDetail;
 const detailReady=new Promise(resolve=>{finishDetail=resolve;});
 detailedBasemap(L,map,host,()=>disposed).then(async dispose=>{if(disposed)dispose?.();else disposeDetailed=dispose||(()=>{});await dispose?.ready;finishDetail();}).catch(()=>{finishDetail();if(!disposed){notice.hidden=false;notice.textContent=t('详细底图暂不可用，仍可使用本地区域地图和事件点','The detailed map is unavailable; the local regional map and event points remain');}});
 const grouped=new Map();for(const c of located){const key=c.coords.join(',');if(!grouped.has(key))grouped.set(key,[]);grouped.get(key).push(c);}
 // The news of a point: what the page's note showed (place · theme, title, summary, date) and the source link.
 function popup(list){return `<article class="map-case-popup">${list.map(c=>`<div class="map-popup-location">${esc(c.country)}${c.label?` · ${esc(c.label)}`:''}</div><div class="map-popup-case"><div><h4>${esc(c.title)}</h4>${c.summaryHtml||''}${c.date?`<p class="map-popup-date">${esc(c.date)}</p>`:''}<div class="map-popup-links">${Array.isArray(c.coords)?`<button type="button" data-map-zoom="${esc(c.id)}">${t('查看周边','Zoom in')}</button>`:''}${c.url&&c.url!=='#'?`<a href="${esc(c.url)}" target="_blank" rel="noopener noreferrer">${esc(options.sourceLabel||t('查看原文','Source'))}</a>`:''}</div></div></div>`).join('')}</article>`;}
 const popupOptions={maxWidth:390,minWidth:260,autoPanPaddingTopLeft:[25,96],autoPanPaddingBottomRight:[25,25],className:'case-location-popup'};
 const bounds=[],markers=new Map();
 for(const list of grouped.values()){
  // Stable golden-angle placement avoids a rigid grid without changing geographic anchors.
  list.forEach((c,index)=>{const point=[c.coords[1],c.coords[0]],kind=c.precision==='city'?'city':'country';if(!country||c.country===country)bounds.push(point);
   const angle=index*2.3999632297-.7,radius=list.length>1?9+13*Math.sqrt(index):0,dx=Math.cos(angle)*radius,dy=Math.sin(angle)*radius;
   const tether=radius>0?`<svg class="marker-tether" width="16" height="16" aria-hidden="true"><line x1="8" y1="8" x2="${8-dx}" y2="${8-dy}"/></svg>`:'';
   const marker=L.marker(point,{zIndexOffset:kind==='city'?1000:0,title:c.title+' · '+precision(c),icon:L.divIcon({className:'case-location-marker precision-'+kind,html:`${tether}<button type="button" data-map-case="${esc(c.id)}" aria-label="${esc(c.title)} · ${precision(c)}"><span class="point-ring"></span><i></i></button>`,iconSize:[16,16],iconAnchor:[8-dx,8-dy],popupAnchor:[dx,dy-12]})});
   marker.bindPopup(popup([c]),popupOptions).addTo(map);
   marker.on('popupopen',()=>{marker.setPopupContent(popup([c]));host.dataset.popupCase=c.id;host.querySelectorAll('[data-map-case]').forEach(b=>b.classList.toggle('is-active',b.dataset.mapCase===c.id));if(!matchMedia('(prefers-reduced-motion:reduce)').matches)marker.getElement()?.querySelector('.point-ring')?.animate([{transform:'scale(.75)',opacity:.9},{transform:'scale(2.6)',opacity:0}],{duration:650,easing:'cubic-bezier(.2,.8,.2,1)'});});
   marker.on('popupclose',()=>{marker.getElement()?.querySelector('button')?.classList.remove('is-active');if(host.dataset.popupCase===c.id)delete host.dataset.popupCase;});
   marker.bindTooltip(c.title+' · '+precision(c),{direction:'top',className:'case-point-tooltip',offset:[dx,dy-10]});
   markers.set(c.id,marker);
  });
 }
 host.dataset.casePoints=String(located.length);
 if(!country)map.setView([24,20],2);else if(bounds.length>1)map.fitBounds(bounds,{padding:[75,70],maxZoom:5});else if(bounds.length===1)map.setView(bounds[0],5);else{const coords=located.find(c=>c.coords)?.coords||[15,25];map.setView([coords[1],coords[0]],country?5:2);}
 // GREEN: the news of one item, on its point or (no location) at the map centre.
 function openCase(id){
  const c=cases.find(x=>x.id===id);if(!c)return false;smoothZoom.stop();
  const marker=markers.get(id);if(marker){marker.openPopup();return true;}
  L.popup({...popupOptions,autoPan:false}).setLatLng(map.getCenter()).setContent(popup([c])).openOn(map);host.dataset.popupCase=c.id;return true;
 }
 const click=e=>{const zoom=e.target.closest('[data-map-zoom]');if(zoom){e.stopPropagation();const c=cases.find(x=>x.id===zoom.dataset.mapZoom);if(c&&Array.isArray(c.coords)){smoothZoom.stop();map.closePopup();map.flyTo([c.coords[1],c.coords[0]],c.precision==='city'?12:6,{duration:matchMedia('(prefers-reduced-motion:reduce)').matches?0:1.1});}return;}const back=e.target.closest('[data-back-globe]');if(back){e.stopPropagation();onBack();return;}const c=e.target.closest('[data-map-read]');if(c){e.stopPropagation();c.closest('details')?.removeAttribute('open');openCase(c.dataset.mapRead);}};host.addEventListener('click',click,{signal,capture:true});
 const fitWorld=()=>{map.invalidateSize({pan:false});const world=L.latLngBounds([[-85.05112878,-180],[85.05112878,180]]);map.setMinZoom(Math.max(2,map.getBoundsZoom(world,true)));map.panInsideBounds(world,{animate:false});};
 const resize=new ResizeObserver(fitWorld);resize.observe(stage);fitWorld();map.whenReady(()=>{host.dataset.mapReady='true';});
 const dispose=()=>{disposed=true;finishReady();smoothZoom.dispose();disposeDetailed();disposeRegional();resize.disconnect();map.remove();host.removeEventListener('click',click,true);delete host.dataset.mapReady;};
 dispose.ready=Promise.all([ready,regionReady,Promise.race([detailReady,new Promise(resolve=>setTimeout(resolve,500))])]);
 dispose.getView=()=>({coords:[map.getCenter().lng,map.getCenter().lat],zoom:map.getZoom()});
 dispose.openCase=openCase;
 dispose.closePopup=()=>{const open=!!host.querySelector('.leaflet-popup');map.closePopup();return open;};
 dispose.capture=async()=>{
  smoothZoom.stop();map.stop();map.closePopup();
  const canvas=document.createElement('canvas'),ratio=Math.min(devicePixelRatio,2),bounds=stage.getBoundingClientRect();canvas.width=Math.round(bounds.width*ratio);canvas.height=Math.round(bounds.height*ratio);
  const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);ctx.fillStyle='#102332';ctx.fillRect(0,0,bounds.width,bounds.height);
  const draw=source=>{const r=source.getBoundingClientRect();if(r.width&&r.height)ctx.drawImage(source,r.left-bounds.left,r.top-bounds.top,r.width,r.height);};
  const detailed=await disposeDetailed.capture?.();
  if(detailed)ctx.drawImage(detailed.canvas,detailed.left-bounds.left,detailed.top-bounds.top,detailed.width,detailed.height);else{
   for(const tile of stage.querySelectorAll('.leaflet-tile-pane canvas'))draw(tile);
   const svg=stage.querySelector('.leaflet-overlay-pane svg');if(svg){const img=new Image();const xml=new XMLSerializer().serializeToString(svg);await new Promise(resolve=>{img.onload=resolve;img.onerror=resolve;img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(xml);});if(img.naturalWidth){const r=svg.getBoundingClientRect();ctx.drawImage(img,r.left-bounds.left,r.top-bounds.top,r.width,r.height);}}
   const labels=stage.querySelector('.regional-label-canvas');if(labels)draw(labels);
  }
  for(const point of stage.querySelectorAll('[data-map-case]')){const r=point.getBoundingClientRect(),x=r.left-bounds.left+r.width/2,y=r.top-bounds.top+r.height/2;if(x<0||y<0||x>bounds.width||y>bounds.height)continue;const style=getComputedStyle(point);ctx.beginPath();ctx.arc(x,y,r.width/2,0,Math.PI*2);ctx.fillStyle=style.backgroundColor;ctx.fill();ctx.strokeStyle=style.borderTopColor;ctx.lineWidth=1;ctx.stroke();ctx.beginPath();ctx.arc(x,y,2,0,Math.PI*2);ctx.fillStyle='#e2e8c5';ctx.fill();}
  return canvas;
 };
 dispose.approach=duration=>{smoothZoom.stop();map.closePopup();map.dragging.disable();map.scrollWheelZoom.disable();host.classList.add('map-is-travelling');map.flyTo(map.getCenter(),Math.max(2.5,map.getZoom()-1.8),{duration:duration/1000,animate:duration>0});};
 dispose.interactive=enabled=>{host.classList.toggle('map-is-travelling',!enabled);smoothZoom.enable(enabled);if(enabled)map.dragging.enable();else map.dragging.disable();};
 return dispose;
}
