// Continuous zoom uses the same movement lifecycle as Leaflet 1.9.4 flyTo.
// Keep camera, projected markers and the vector renderer on one frame clock.
export function smoothMapZoom(L,map,host){
 const container=map.getContainer(),controller=new AbortController(),signal=controller.signal;
 let frame=0,target=null,anchor=null,pixel=null,last=0,enabled=true;
 const reduced=()=>matchMedia('(prefers-reduced-motion:reduce)').matches;
 const clamp=z=>Math.max(map.getMinZoom(),Math.min(map.getMaxZoom(),z));
 function stop(){cancelAnimationFrame(frame);frame=0;if(target!==null){target=null;map._atlasContinuousZoom=false;map._moveEnd(true);}last=0;}
 function draw(now){
  if(target===null)return;const dt=last?Math.min(now-last,40):16.67;last=now;
  const current=map.getZoom(),difference=target-current,settled=reduced()||Math.abs(difference)<.0015;
  const zoom=settled?target:current+difference*(1-Math.exp(-dt/115));
  const world=map.project(anchor,zoom),center=map.unproject(world.subtract(pixel.subtract(map.getSize().divideBy(2))),zoom);
  map._move(map._limitCenter(center,zoom,map.options.maxBounds),zoom,{atlasContinuous:true});host.dataset.viewZoom=zoom.toFixed(4);
  if(settled){frame=0;target=null;map._atlasContinuousZoom=false;map._moveEnd(true);last=0;}else frame=requestAnimationFrame(draw);
 }
 function change(delta,point){
  if(!enabled||host.classList.contains('map-is-travelling'))return;
  pixel=point||map.getSize().divideBy(2);anchor=map.containerPointToLatLng(pixel);
  const next=clamp((target??map.getZoom())+delta);if(next===map.getZoom()&&target===null)return;
  if(target===null){map.stop();map._atlasContinuousZoom=true;map._moveStart(true,false);}
  target=next;last=0;if(!frame)frame=requestAnimationFrame(draw);
 }
 container.addEventListener('wheel',event=>{
  if(event.target.closest?.('.leaflet-popup'))return;
  if(!enabled||host.classList.contains('map-is-travelling'))return;event.preventDefault();event.stopImmediatePropagation();
  const unit=event.deltaMode===1?16:event.deltaMode===2?container.clientHeight:1;
  change(Math.max(-1.4,Math.min(1.4,-event.deltaY*unit/420)),map.mouseEventToContainerPoint(event));
 },{capture:true,passive:false,signal});
 container.addEventListener('click',event=>{const button=event.target.closest('.leaflet-control-zoom-in,.leaflet-control-zoom-out');if(!button)return;event.preventDefault();event.stopImmediatePropagation();change(button.classList.contains('leaflet-control-zoom-in')?.5:-.5);},{capture:true,signal});
 container.addEventListener('pointerdown',event=>{if(!event.target.closest('.leaflet-control'))stop();},{capture:true,signal});
 map.scrollWheelZoom.disable();
 return {stop,enable(value){enabled=value;if(!value)stop();map.scrollWheelZoom.disable();},dispose(){stop();controller.abort();}};
}
