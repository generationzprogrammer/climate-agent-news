import {en,t} from './i18n.js';
let sources;
const load=()=>sources??=Promise.all(['countries','regions','rivers','cities'].map(async name=>{const r=await fetch(new URL('./geography/'+name+'.json',import.meta.url));if(!r.ok)throw Error('区域资料未能加载');return r.json();}));
export const preloadRegional=()=>load().catch(()=>{sources=undefined;});
export async function regionalLayer(L,map,country,isDisposed){
 const [countries,regions,rivers,cities]=await load();if(isDisposed())return ()=>{};
 const dark=()=>true;
 const land=L.geoJSON(countries,{interactive:false,style:()=>({color:'#63817f',weight:.8,opacity:.65,fillColor:dark()?'#192e34':'#284044',fillOpacity:1})}).addTo(map);
 const state=L.geoJSON(regions,{interactive:false,style:{color:'#78928a',weight:.65,opacity:.35}}).addTo(map);
 const river=L.geoJSON(rivers,{interactive:false,style:{color:'#426677',weight:.8,opacity:.55}}).addTo(map);
 const Labels=L.Layer.extend({onAdd(map){this.map=map;this.canvas=L.DomUtil.create('canvas','regional-label-canvas');this.canvas.setAttribute('aria-hidden','true');map.getPane('tooltipPane').append(this.canvas);map.on('moveend zoomend resize',this.draw,this);this.draw();},onRemove(map){map.off('moveend zoomend resize',this.draw,this);this.canvas.remove();},draw(){
  const size=map.getSize(),ratio=Math.min(devicePixelRatio,2),canvas=this.canvas;canvas.width=size.x*ratio;canvas.height=size.y*ratio;canvas.style.width=size.x+'px';canvas.style.height=size.y+'px';L.DomUtil.setPosition(canvas,map.containerPointToLayerPoint([0,0]));
  const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);const zoom=map.getZoom(),occupied=[];
  const put=(text,coords,font,color)=>{const p=map.latLngToContainerPoint([coords[1],coords[0]]);if(p.x<25||p.y<20||p.x>size.x-25||p.y>size.y-20)return;ctx.font=font;const width=ctx.measureText(text).width,box=[p.x-width/2-9,p.y-10,width+18,22];if(occupied.some(b=>box[0]<b[0]+b[2]&&box[0]+box[2]>b[0]&&box[1]<b[1]+b[3]&&box[1]+box[3]>b[1]))return;occupied.push(box);ctx.textAlign='center';ctx.lineWidth=3;ctx.strokeStyle='#122c35';ctx.strokeText(text,p.x,p.y);ctx.fillStyle=color;ctx.fillText(text,p.x,p.y);};
  if(zoom<5)for(const f of countries.features){const p=f.properties;if(Number.isFinite(p.LABEL_X)&&Number.isFinite(p.LABEL_Y))put((en()?p.NAME_EN:p.NAME_ZH)||p.NAME,[p.LABEL_X,p.LABEL_Y],'12px sans-serif','#a9bab1');}
  if(zoom>=4)for(const f of [...cities.features].sort((a,b)=>(b.properties.POP_MAX||0)-(a.properties.POP_MAX||0))){const p=f.properties;if((p.SCALERANK||0)>zoom+1)continue;put((en()?p.NAME_EN:p.NAME_ZH)||p.NAME,f.geometry.coordinates,'12px sans-serif','#c5cec0');}
 }});
 const labels=new Labels().addTo(map);
 const detach=()=>{for(const layer of [labels,river,state,land])if(map.hasLayer(layer))map.removeLayer(layer);};
 map.on('atlasdetailready',detach);if(map._atlasDetailedReady)detach();
 const sync=()=>{if(map._atlasDetailedReady)return;const zoom=map.getZoom(),blend=Math.max(0,Math.min(1,(zoom-2.5)/2));land.setStyle({fillOpacity:.25+.75*blend,fillColor:dark()?'#192e34':'#284044'});state.setStyle({opacity:zoom>=4?.35:.12});river.setStyle({opacity:zoom>=5?.58:.16});const pane=map.getPane('tilePane');pane.style.opacity=String(1-.82*blend);labels.draw();};
 map.on('zoomend',sync);const observer=new MutationObserver(sync);observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});sync();map.attributionControl.addAttribution(t('区域数据 © Natural Earth','Regions © Natural Earth'));
 return ()=>{observer.disconnect();map.off('atlasdetailready',detach);map.off('zoomend',sync);map.removeLayer(labels);map.removeLayer(river);map.removeLayer(state);map.removeLayer(land);};
}
