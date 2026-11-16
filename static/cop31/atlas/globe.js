// 融观地球 (源码包 2026-11-10) on the GREEN · COP31 page — the globe, its rotation, interaction and arcs.
// Kept from the package: the renderer, materials, camera flights, marker projection, the unfold hooks.
// Changed for this site (2026-11-10): relative module paths; the land mask is drawn without d3; the dark theme is
// fixed; the points can be replaced without rebuilding the renderer (setCases: today / this week); the arcs rise
// from the COP31 host city to every place with news instead of joining sample country pairs; the wheel is left to
// the page (its sheet and scroll handling listen on window), zoom is the buttons and pinch; texts follow <html lang>.
import * as THREE from './vendor/three/three.module.js';
import {OrbitControls} from './vendor/three/OrbitControls.js';
import {globeMaterials} from './materials.js';
import {attachUnfold} from './unfold-surface.js';
import {t} from './i18n.js';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const radians=Math.PI/180;
// GREEN (2026-11-10, full-window stage): the camera's resting distance. 365 shows the globe a little larger than the
// package's 380; a stage narrower than it is tall moves the camera back until the globe fits the width.
const BASE=365,fit=aspect=>Math.max(BASE,100/Math.sin(Math.atan(.9*Math.tan(19*Math.PI/180)*aspect)));
const vector=([lon,lat],radius=100)=>new THREE.Vector3(radius*Math.cos(lat*radians)*Math.sin(lon*radians),radius*Math.sin(lat*radians),radius*Math.cos(lat*radians)*Math.cos(lon*radians));
let landCache,landGeo;
// The geographic mask of the real-image globe: land filled on an equirectangular canvas (the package drew it with
// d3.geoPath; Natural Earth rings are already cut at the antimeridian, so a plain lon / lat fill gives the same mask).
function landPositions(geo){
 if(landCache&&landGeo===geo)return landCache;
 const canvas=document.createElement('canvas');canvas.width=2048;canvas.height=1024;
 const ctx=canvas.getContext('2d',{willReadFrequently:true});
 ctx.fillStyle='#fff';
 for(const f of geo.features){
  if(!f.geometry)continue;
  const polygons=f.geometry.type==='Polygon'?[f.geometry.coordinates]:f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[];
  for(const rings of polygons){
   ctx.beginPath();
   for(const ring of rings){ring.forEach(([lon,lat],i)=>{const x=(lon+180)/360*2048,y=(90-lat)/180*1024;if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.closePath();}
   ctx.fill('evenodd');
  }
 }
 landGeo=geo;return landCache={canvas};
}
export function mountGlobe(host,cases,geo,options={}){
 if(!geo)throw Error('缺少陆地资料');
 // Create the renderer before changing the UI so unsupported WebGL has a clean fallback.
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,powerPreference:'high-performance'});
 renderer.setPixelRatio(1);renderer.setClearColor(0x000000,0);
 const hub=options.hub||null;
 const count=n=>t(`${n} 条新闻`,`${n} ${n===1?'story':'stories'}`);
 const recordsOf=list=>{const names=[...new Set(list.filter(c=>Array.isArray(c.coords)).map(c=>c.country))];return names.map(country=>({country,coords:list.find(c=>c.country===country&&Array.isArray(c.coords)).coords,count:list.filter(c=>c.country===country).length}));};
 let records=recordsOf(cases);
 host.innerHTML=`<div class="globe-view"><div class="globe-toolbar"><span class="atlas-map-kicker">EARTH OBSERVATORY · GREEN</span><div class="globe-actions"><button type="button" data-globe-action="rotate" aria-pressed="true"></button><button type="button" data-globe-action="reset">${t('复位','Reset')}</button><button type="button" data-globe-action="in" aria-label="${t('放大地球','Zoom in')}">＋</button><button type="button" data-globe-action="out" aria-label="${t('缩小地球','Zoom out')}">−</button></div></div><div class="globe-locate"><label for="globe-country">${t('定位地点','Locate')}</label><select id="globe-country"></select><label class="globe-arcs-label"><input type="checkbox" id="globe-arcs" checked>${t('飞线示意','Arcs')}</label></div><div class="globe-stage"><div class="globe-aura" aria-hidden="true"></div><div class="globe-canvas"></div><div class="globe-markers"></div><div class="globe-tooltip" aria-hidden="true" hidden></div><span class="globe-instruction">${t('拖动旋转 · 双指缩放','Drag to turn · pinch to zoom')}</span></div><div class="globe-selection" hidden></div><div class="globe-footer"><span><i></i><b class="globe-count"></b></span><span>${t('NASA 地表影像 · 云层为动态演示 · 飞线为示意','NASA imagery · clouds are animated · arcs are illustrative')}</span></div></div>`;
 const root=host.querySelector('.globe-view'),stage=root.querySelector('.globe-stage'),canvasHost=root.querySelector('.globe-canvas'),tooltip=root.querySelector('.globe-tooltip'),markerHost=root.querySelector('.globe-markers'),select=root.querySelector('#globe-country');
 canvasHost.append(renderer.domElement);renderer.domElement.setAttribute('aria-label',t('可旋转的三维地球；也可使用上方地点选择框定位','A globe you can turn; the place list above locates a place too'));renderer.domElement.setAttribute('role','img');
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,1,1000);
 let home=BASE;const initialCamera=vector([65,22],home);camera.position.copy(initialCamera);
 const controls=new OrbitControls(camera,renderer.domElement);controls.enablePan=false;controls.enableDamping=true;controls.dampingFactor=.08;controls.minDistance=home*.6;controls.maxDistance=home*1.27;controls.autoRotateSpeed=.45;controls.rotateSpeed=.55;controls.zoomSpeed=.6;
 // The package kept the wheel from the controls (the page scrolls over the globe); here the event must also reach the
 // page's own wheel handling, so the controls' wheel listener is taken off instead of stopping the event.
 renderer.domElement.removeEventListener('wheel',controls._onMouseWheel);
 const landData=landPositions(geo),materials=globeMaterials(landData.canvas,{sharp:Math.max(innerWidth,innerHeight)*Math.min(devicePixelRatio,2)>1300&&!navigator.connection?.saveData,onchange:()=>refresh?.()});
 materials.dots.uniforms.pixelRatio.value=renderer.getPixelRatio();
 scene.add(new THREE.Mesh(new THREE.SphereGeometry(100,128,96),materials.surface));

 scene.add(new THREE.Mesh(new THREE.SphereGeometry(104,96,64),materials.atmosphere));
 const gridMaterial=new THREE.LineBasicMaterial({transparent:true,opacity:.012});
 for(let lat=-60;lat<=60;lat+=30){const pts=[];for(let lon=-180;lon<=180;lon+=2)pts.push(vector([lon,lat],100.1));scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),gridMaterial))}
 for(let lon=0;lon<180;lon+=30){const pts=[];for(let angle=0;angle<=360;angle+=2){const a=angle*radians;pts.push(new THREE.Vector3(100.1*Math.cos(a)*Math.sin(lon*radians),100.1*Math.sin(a),100.1*Math.cos(a)*Math.cos(lon*radians)))}scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),gridMaterial))}
 const arcsGroup=new THREE.Group();arcsGroup.visible=true;scene.add(arcsGroup);
 // Arcs from the COP31 host city to each place with news: an illustration, not a data relation.
 let arcs=[];
 const buildArcs=()=>{
  for(const arc of arcs){arcsGroup.remove(arc.base,arc.trail);arc.base.geometry.dispose();arc.trail.geometry.dispose();arc.baseMaterial.dispose();arc.trailMaterial.dispose();}
  arcs=[];if(!hub)return;
  for(const record of records){
   const start=vector(hub.coords,1),end=vector(record.coords,1),angle=start.angleTo(end),pts=[];if(!(angle>.04)||!(Math.PI-angle>.04))continue;
   for(let i=0;i<=100;i++){const s=i/100;const v=start.clone().multiplyScalar(Math.sin((1-s)*angle)).add(end.clone().multiplyScalar(Math.sin(s*angle))).divideScalar(Math.sin(angle));pts.push(v.multiplyScalar(101+Math.sin(Math.PI*s)*Math.min(36,angle*20)))}
   const baseMaterial=new THREE.LineBasicMaterial({transparent:true,opacity:.3,color:'#528d68'}),trailMaterial=new THREE.LineBasicMaterial({transparent:true,opacity:.8,color:'#a17937'});
   const base=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),baseMaterial),trail=new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),trailMaterial);trail.geometry.setDrawRange(0,1);
   arcsGroup.add(base,trail);arcs.push({baseMaterial,trailMaterial,base,trail});
  }
 };
 const controller=new AbortController(),signal=controller.signal,reduced=matchMedia('(prefers-reduced-motion: reduce)');
 let flight=null,suspended=false;
 let alive=true,rotating=!reduced.matches,arcsVisible=true,interacting=false,frame=0,last=0,elapsed=0,visible=true;
 let markerButtons=[],markerPositions=[];
 const hubPosition=hub?vector(hub.coords,101):null;let hubMark=null;
 const world=new THREE.Vector3(),projected=new THREE.Vector3(),facing=new THREE.Vector3();
 const hideTooltip=()=>{tooltip.hidden=true;};
 // Markers, the place list and the count for the current records.
 const buildMarkers=()=>{
  hideTooltip();
  markerHost.innerHTML=records.map((r,i)=>`<button type="button" class="globe-marker" data-index="${i}" data-country="${esc(r.country)}" aria-label="${esc(t(`查看${r.country}的${r.count}条新闻`,`${r.country}: ${count(r.count)}`))}" hidden><span></span></button>`).join('')+(hub?`<span class="globe-hub" aria-hidden="true" hidden><i></i><b>${esc(hub.label)}</b></span>`:'');
  markerButtons=[...markerHost.querySelectorAll('.globe-marker')];markerPositions=records.map(r=>vector(r.coords,101));hubMark=markerHost.querySelector('.globe-hub');
  markerButtons.forEach((button,index)=>{
   const show=()=>{const r=records[index];tooltip.innerHTML=`<strong>${esc(r.country)}</strong><span>${count(r.count)} · ${t('点击查看','open')} ↗</span>`;tooltip.hidden=false;const rect=button.getBoundingClientRect(),bounds=stage.getBoundingClientRect();tooltip.style.left=Math.max(8,Math.min(bounds.width-tooltip.offsetWidth-8,rect.left-bounds.left+18))+'px';tooltip.style.top=Math.max(8,Math.min(bounds.height-tooltip.offsetHeight-8,rect.top-bounds.top-tooltip.offsetHeight-10))+'px'};
   button.addEventListener('pointerenter',show,{signal});button.addEventListener('focus',show,{signal});button.addEventListener('pointerleave',hideTooltip,{signal});button.addEventListener('blur',hideTooltip,{signal});
  });
  select.innerHTML=`<option value="">${t('选择地点查看位置','Choose a place')}</option>${[...records].sort((a,b)=>a.country.localeCompare(b.country,t('zh','en'))).map(r=>`<option value="${esc(r.country)}">${esc(r.country)} · ${count(r.count)}</option>`).join('')}`;
  root.querySelector('.globe-count').textContent=t(`${records.length} 个事件地点 · 点击标记查看`,`${records.length} places with news · pick a marker`);
  root.querySelector('.globe-selection').hidden=true;root.dataset.markers=String(records.length);
 };
 const updateRotation=()=>{controls.autoRotate=rotating&&!interacting;root.querySelector('[data-globe-action=rotate]').textContent=rotating?t('暂停旋转','Pause'):t('自动旋转','Rotate');root.querySelector('[data-globe-action=rotate]').setAttribute('aria-pressed',String(rotating))};
 // The package's light theme (2026-11-10: the globe sits on the page's own pale background; the map it unfolds into
 // stays the package's dark map).
 materials.theme(false);gridMaterial.color.set('#b9c3bc');gridMaterial.opacity=.035;
 let viewportMotion=false,viewportFrozen=false,bufferWidth=0,bufferHeight=0;
 // GREEN (2026-11-10): the full-window globe is drawn at the screen's own resolution where it can be (up to 2x and
 // 4.2 M pixels; the package stopped at 1.5x and 1.6 M, soft on a large stage). `budget` drops back to the package's
 // if this machine cannot keep up (see draw).
 let budget=4200000,slow=0;
 const buffer=(w,h)=>{const ratio=Math.min(devicePixelRatio,2,Math.sqrt(budget/Math.max(1,w*h))),bw=Math.round(w*ratio),bh=Math.round(h*ratio);if(bw!==bufferWidth||bh!==bufferHeight){renderer.setSize(bw,bh,false);bufferWidth=bw;bufferHeight=bh;}};
 const resize=()=>{if(viewportFrozen)return;const w=stage.clientWidth,h=stage.clientHeight;if(!w||!h)return;if(!viewportMotion)buffer(w,h);if(camera.aspect!==w/h){camera.aspect=w/h;camera.updateProjectionMatrix();}
  // keep the globe's size on screen in step with the stage's shape (not while a flight or the unfold owns the camera)
  const next=fit(w/h);if(next!==home&&!flight&&!suspended&&!root.classList.contains('globe-is-unfolding')){camera.position.setLength(camera.position.length()*next/home);initialCamera.setLength(next);home=next;controls.minDistance=home*.6;controls.maxDistance=home*1.27;controls.update();}if(!frame&&!flight&&!root.classList.contains('globe-is-unfolding'))renderer.render(scene,camera);};
 host.freezeViewport=flag=>{viewportFrozen=flag;if(!flag)resize();};
 host.beginViewportMotion=()=>{viewportMotion=true;buffer(innerWidth,innerHeight);};
 host.endViewportMotion=()=>{viewportMotion=false;resize();};
 host.captureViewport=()=>{const r=stage.getBoundingClientRect();scene.updateMatrixWorld();camera.updateMatrixWorld();renderer.render(scene,camera);const canvas=document.createElement('canvas');canvas.width=renderer.domElement.width;canvas.height=renderer.domElement.height;canvas.getContext('2d').drawImage(renderer.domElement,0,0);return {canvas,width:r.width,height:r.height};};
 host.syncViewport=resize;
 let refresh=()=>{if(!frame&&!flight&&!root.classList.contains('globe-is-unfolding'))renderer.render(scene,camera);};
 const resizeObserver=new ResizeObserver(resize);resizeObserver.observe(stage);resize();
 stage.addEventListener('pointerleave',hideTooltip,{signal});
 const selection=root.querySelector('.globe-selection');
 select.addEventListener('change',event=>{const record=records.find(r=>r.country===event.target.value);if(!record){selection.hidden=true;return}rotating=false;updateRotation();controls.reset();camera.position.copy(vector(record.coords,home*.92));controls.target.set(0,0,0);controls.update();selection.innerHTML=`<span>${t('已定位','Located')} <strong>${esc(record.country)}</strong></span><button type="button" class="button small" data-country="${esc(record.country)}">${t(`查看 ${record.count} 条新闻`,`Open ${count(record.count)}`)} ↗</button>`;selection.hidden=false},{signal});
 root.querySelector('#globe-arcs').addEventListener('change',event=>{arcsVisible=event.target.checked;arcsGroup.visible=arcsVisible},{signal});
 root.querySelector('.globe-actions').addEventListener('click',event=>{const action=event.target.closest('[data-globe-action]')?.dataset.globeAction;if(!action)return;hideTooltip();if(action==='rotate'){rotating=!rotating;updateRotation();if(!rotating){const damping=controls.enableDamping;controls.enableDamping=false;controls.update();controls.enableDamping=damping;}}else if(action==='reset'){controls.reset();camera.position.copy(initialCamera);controls.target.set(0,0,0);selection.hidden=true;select.value='';controls.update()}else{camera.position.setLength(THREE.MathUtils.clamp(camera.position.length()*(action==='in'?.8:1.25),controls.minDistance,controls.maxDistance));controls.update()}},{signal});
 controls.addEventListener('start',()=>{interacting=true;hideTooltip();updateRotation()});controls.addEventListener('end',()=>{interacting=false;updateRotation()});
 const motion=()=>{if(reduced.matches){rotating=false;updateRotation()}};reduced.addEventListener('change',motion);
 host.pickCountryAt=(x,y)=>{let nearest=null,distance=27;for(const button of markerButtons){if(button.hidden)continue;const r=button.getBoundingClientRect(),d=Math.hypot(x-r.left-r.width/2,y-r.top-r.height/2);if(d<distance){distance=d;nearest=button.dataset.country;}}return nearest;};
 host.homeDistance=()=>home;
 host.getView=()=>({coords:[Math.atan2(camera.position.x,camera.position.z)/radians,Math.asin(camera.position.y/camera.position.length())/radians],distance:camera.position.length()});
 host.suspendAtlas=flag=>{suspended=flag;if(flag&&frame){cancelAnimationFrame(frame);frame=0;}if(!flag&&!frame&&!document.hidden)frame=requestAnimationFrame(draw);};
 host.flyCamera=(coords,distance,duration=2200,restore=false,styleTarget=materials.surface.uniforms.mapBlend.value)=>new Promise(resolve=>{
  flight?.resolve();rotating=false;updateRotation();controls.enabled=false;controls.minDistance=110;controls.enableDamping=false;
  const target=vector(coords,distance),finish=()=>{if(restore){controls.minDistance=home*.6;controls.enableDamping=true;controls.enabled=true;rotating=!reduced.matches;updateRotation();}resolve();};
  if(!duration||reduced.matches){materials.surface.uniforms.mapBlend.value=styleTarget;camera.position.copy(target);camera.lookAt(0,0,0);scene.updateMatrixWorld();camera.updateMatrixWorld();renderer.render(scene,camera);finish();return;}
  flight={styleFrom:materials.surface.uniforms.mapBlend.value,styleTarget,from:camera.position.clone(),to:target,elapsed:0,last:performance.now(),duration,resolve:finish};
  if(!frame&&!document.hidden)frame=requestAnimationFrame(draw);
 });
 host.flyToCountry=(country,duration=2200)=>{const record=records.find(r=>r.country===country);return host.flyCamera(record?.coords||host.getView().coords,122,duration);};
 // GREEN: another set of points (today / this week) on the same globe.
 host.setCases=next=>{records=recordsOf(next);buildMarkers();buildArcs();if(!frame&&!flight&&!root.classList.contains('globe-is-unfolding')){place();renderer.render(scene,camera);}};
 host.recordFor=country=>records.find(r=>r.country===country)||null;
 const put=(element,position,w,h,margin)=>{world.copy(position);facing.copy(camera.position).sub(world);const front=world.dot(facing)>0;projected.copy(world).project(camera);const x=(projected.x+1)*w/2,y=(1-projected.y)*h/2;element.hidden=!front||projected.z>1||x<margin||x>w-margin||y<margin||y>h-margin;if(!element.hidden){element.style.transform=`translate(${x}px,${y}px) translate(-50%,-50%)`;element.style.zIndex=String(10+Math.round((1-projected.z)*1000))}};
 function place(){scene.updateMatrixWorld();camera.updateMatrixWorld();const w=stage.clientWidth,h=stage.clientHeight;markerButtons.forEach((button,i)=>put(button,markerPositions[i],w,h,5));if(hubMark)put(hubMark,hubPosition,w,h,5);}
 function draw(time){if(!alive)return;frame=0;if(document.hidden||((!visible||suspended)&&!flight)){last=0;return}const delta=last?Math.min((time-last)/1000,.05):0;last=time;elapsed+=delta;
  if(budget>1600000&&delta){slow=delta>.034?slow+1:Math.max(0,slow-2);if(slow>45){budget=1600000;slow=0;resize();}} // ~1 s under 30 fps: the lighter buffer
  materials.tick?.(elapsed);
  if(flight){flight.elapsed+=Math.min(time-flight.last,34);flight.last=time;const p=flight.duration?Math.min(1,flight.elapsed/flight.duration):1;const ease=p*p*p*(p*(p*6-15)+10);
   materials.surface.uniforms.mapBlend.value=THREE.MathUtils.lerp(flight.styleFrom,flight.styleTarget,ease);
   const from=flight.from.clone().normalize(),to=flight.to.clone().normalize();const rotation=new THREE.Quaternion().setFromUnitVectors(from,to);from.applyQuaternion(new THREE.Quaternion().slerp(rotation,ease));
   camera.position.copy(from.multiplyScalar(THREE.MathUtils.lerp(flight.from.length(),flight.to.length(),ease)));camera.lookAt(0,0,0);
   if(p>=1){const done=flight.resolve;flight=null;done();}
  }else if(controls.enabled)controls.update(delta);
  if(arcsVisible)arcs.forEach((arc,i)=>{const head=reduced.matches?60:Math.floor(((elapsed/3.5+i*.17)%1)*100);arc.trail.geometry.setDrawRange(Math.max(0,head-17),Math.min(18,head+1))});
  place();
  renderer.render(scene,camera);frame=requestAnimationFrame(draw);
 }
 const resume=()=>{if(!frame&&alive&&!document.hidden&&visible&&!suspended)frame=requestAnimationFrame(draw)};
 document.addEventListener('visibilitychange',resume,{signal});const intersection=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;resume()});intersection.observe(stage);
 renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();rotating=false;updateRotation();const message=document.createElement('div');message.className='globe-context-error';message.setAttribute('role','status');message.textContent=t('3D显示暂时中断，请刷新页面后再试。','The 3D view was interrupted; please reload the page.');stage.append(message)},{signal});
 const cloudLabel=document.createElement('label');cloudLabel.className='crystal-motion-control';cloudLabel.innerHTML=`<input type="checkbox" id="cloud-layer-toggle" checked>${t('轻薄云层','Clouds')}`;root.querySelector('.globe-locate').append(cloudLabel);
 const cloudToggle=cloudLabel.querySelector('input');cloudToggle.addEventListener('change',()=>{materials.surface.uniforms.cloudStrength.value=cloudToggle.checked?.38:0;},{signal});
 const disposeEffect=()=>cloudLabel.remove();
 const disposeUnfold=attachUnfold({host,root,scene,camera,renderer,materials,stage,signal});
 buildMarkers();buildArcs();updateRotation();resume();root.dataset.ready='true';
 return ()=>{disposeUnfold();flight?.resolve();delete host.flyToCountry;delete host.flyCamera;delete host.freezeViewport;delete host.captureViewport;delete host.beginViewportMotion;delete host.endViewportMotion;delete host.pickCountryAt;delete host.syncViewport;delete host.getView;delete host.homeDistance;delete host.suspendAtlas;delete host.setCases;delete host.recordFor;disposeEffect();alive=false;cancelAnimationFrame(frame);controller.abort();resizeObserver.disconnect();intersection.disconnect();reduced.removeEventListener('change',motion);controls.dispose();const geometries=new Set(),sceneMaterials=new Set();scene.traverse(obj=>{if(obj.geometry)geometries.add(obj.geometry);if(obj.material)(Array.isArray(obj.material)?obj.material:[obj.material]).forEach(m=>sceneMaterials.add(m))});geometries.forEach(g=>g.dispose());sceneMaterials.forEach(m=>m.dispose());materials.dispose?.();materials.texture.dispose();renderer.dispose();renderer.forceContextLoss();host.replaceChildren()};
}
