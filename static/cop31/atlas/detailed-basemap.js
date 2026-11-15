import {en,t} from './i18n.js';
const here=path=>new URL(path,import.meta.url).href;
// GREEN: the labels follow the page language (the style asks for name:zh).
async function mapStyle(){const url=here('./detailed-style.json');if(!en())return url;try{return JSON.parse((await (await fetch(url)).text()).replaceAll('"name:zh"','"name:en"'));}catch{return url;}}
let runtime;
function script(src){return new Promise((resolve,reject)=>{const s=document.createElement('script');s.src=src;s.onload=resolve;s.onerror=()=>reject(Error('详细地图组件暂未加载'));document.head.append(s);});}
async function library(){
 if(!runtime)runtime=(async()=>{const css=document.createElement('link');css.rel='stylesheet';css.href=here('./vendor/maplibre-gl.css');document.head.append(css);await script(here('./vendor/maplibre-gl.js'));await script(here('./vendor/leaflet-maplibre-gl.js'));})();
 return runtime;
}
export const preloadDetailedRuntime=library;
export async function detailedBasemap(L,map,host,isDisposed){
 await library();const style=await mapStyle();if(isDisposed())return ()=>{};
 const pane=map.createPane('detailedVectorPane');pane.style.zIndex='450';pane.style.pointerEvents='none';pane.style.opacity='0';pane.style.transition='opacity .7s ease';
 const layer=L.maplibreGL({pane:'detailedVectorPane',updateInterval:16,style,interactive:false,renderWorldCopies:false,canvasContextAttributes:{preserveDrawingBuffer:false},preserveDrawingBuffer:false,attribution:'<a href="https://openfreemap.org/" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> · © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>'});
 // Continuous Leaflet zoom emits move frames, not CSS zoomanim frames.
 // The adapter must not freeze its camera between zoomstart and zoomend.
 layer._zoomStart=function(){this._zooming=false;};
 const cssZoom=layer._animateZoom;layer._animateZoom=function(event){this._zooming=true;return cssZoom.call(this,event);};layer.addTo(map);
 const gl=layer.getMaplibreMap();let disposed=false,ready=false,failTimer,finishInitial;
 const rendered=()=>{host.dataset.renderZoom=(gl.getZoom()+1).toFixed(4);};gl.on('render',rendered);
 const initialReady=new Promise(resolve=>{finishInitial=resolve;});
 const notice=host.querySelector('.detail-map-network');
 const show=()=>{if(disposed||isDisposed()||!gl.isStyleLoaded()||!gl.areTilesLoaded())return;ready=true;clearTimeout(failTimer);pane.style.opacity='1';host.dataset.detailQuality='vector';notice.hidden=true;if(!map._atlasDetailedReady){map._atlasDetailedReady=true;map.fire('atlasdetailready');}finishInitial();};
 gl.on('idle',show);
 gl.on('error',()=>{if(disposed||ready)return;finishInitial();host.dataset.detailQuality='fallback';notice.hidden=false;notice.textContent=t('详细地图连接暂不可用，当前保留本地区域地图与全部事件点','The detailed map is unavailable; the local regional map and all event points remain');});
 failTimer=setTimeout(()=>{if(disposed||ready)return;notice.hidden=false;notice.textContent=t('详细底图仍在连接，可先浏览本地区域地图和事件点','Still connecting to the detailed map; the local regional map and event points are ready');},12000);
 // The Leaflet markers and popup interactions stay above the vector surface.
 const pressed=()=>{if(ready)host.dataset.detailQuality='vector';};map.on('moveend zoomend',pressed);
 const dispose=()=>{disposed=true;finishInitial();clearTimeout(failTimer);gl.off('idle',show);gl.off('render',rendered);map.off('moveend zoomend',pressed);if(map.hasLayer(layer))map.removeLayer(layer);pane.remove();};dispose.ready=initialReady;
 // Copy within the render callback: no permanent drawing-buffer retention is needed.
 dispose.capture=async()=>{if(!ready)return null;return new Promise(resolve=>{let settled=false;const finish=value=>{if(settled)return;settled=true;clearTimeout(timer);gl.off('render',copy);resolve(value);};const copy=()=>{if(disposed||isDisposed()){finish(null);return;}try{const source=gl.getCanvas(),r=source.getBoundingClientRect(),canvas=document.createElement('canvas');canvas.width=source.width;canvas.height=source.height;canvas.getContext('2d').drawImage(source,0,0);finish({canvas,left:r.left,top:r.top,width:r.width,height:r.height});}catch{finish(null);}};const timer=setTimeout(()=>finish(null),1500);gl.once('render',copy);gl.triggerRepaint();});};return dispose;
}
