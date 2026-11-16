import * as THREE from './vendor/three/three.module.js';

// Cache one geographic mesh and program. Only uniforms and the map texture change.
export function attachUnfold({host,root,scene,camera,renderer,materials,stage,signal}){
 let active=null,disposed=false;
 const columns=192,rows=96,count=(columns+1)*(rows+1),positions=new Float32Array(count*3),geographic=new Float32Array(count*2),indices=new Uint16Array(columns*rows*6);
 for(let y=0;y<=rows;y++)for(let x=0;x<=columns;x++){
  const index=y*(columns+1)+x,lon=-180+x/columns*360,lat=89.98-y/rows*179.96,lr=lon*Math.PI/180,br=lat*Math.PI/180;
  positions.set([100*Math.cos(br)*Math.sin(lr),100*Math.sin(br),100*Math.cos(br)*Math.cos(lr)],index*3);geographic.set([lon,lat],index*2);
 }
 let offset=0;for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){const a=y*(columns+1)+x,b=a+columns+1;indices.set([a,b,a+1,b,b+1,a+1],offset);offset+=6;}
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));geometry.setAttribute('geographic',new THREE.BufferAttribute(geographic,2));geometry.setIndex(new THREE.BufferAttribute(indices,1));
 const placeholder=document.createElement('canvas');placeholder.width=placeholder.height=1;
 const texture=new THREE.CanvasTexture(placeholder);texture.minFilter=THREE.LinearFilter;texture.magFilter=THREE.LinearFilter;texture.generateMipmaps=false;
 const uniforms={...materials.surface.uniforms,projectionMix:{value:0},envelopeStrength:{value:0},flatCenter:{value:new THREE.Vector2()},flatSize:{value:new THREE.Vector2(1,1)},flatZoom:{value:4},detailMap:{value:texture}};
 const material=new THREE.ShaderMaterial({side:THREE.DoubleSide,uniforms,vertexShader:`
  attribute vec2 geographic;uniform float projectionMix,flatZoom,envelopeStrength;uniform vec2 flatCenter,flatSize;
  varying vec3 normalView,localPos,viewPos;varying vec2 flatUV;
  float mercator(float lat){return log(tan(.78539816339+clamp(lat,-85.05,85.05)*.00872664626));}
  void main(){
   vec2 geo=vec2(geographic.x+flatCenter.x,geographic.y);vec2 angle=radians(geo);
   vec3 point=100.*vec3(cos(angle.y)*sin(angle.x),sin(angle.y),cos(angle.y)*cos(angle.x));
   localPos=point;normalView=normalize(normalMatrix*normalize(point));vec4 p=modelViewMatrix*vec4(point,1.);viewPos=p.xyz;vec4 sphere=projectionMatrix*p;
   vec2 merc=vec2(geographic.x/360.,(mercator(geo.y)-mercator(flatCenter.y))/6.28318530718);
   vec2 target=merc*(256.*exp2(flatZoom))*2./flatSize;flatUV=target*.5+.5;
   // Flatten at a world scale, then approach the chosen regional zoom logarithmically.
   float coverZoom=max(2.2,log2(max(flatSize.x,flatSize.y)/256.)+.35);
   float base=min(flatZoom,coverZoom),zoom=mix(base,flatZoom,smoothstep(.38,1.,projectionMix));
   vec2 plane=merc*(256.*exp2(zoom))*2./flatSize;
   float flatness=smoothstep(0.,.72,projectionMix);
   vec3 projected=mix(sphere.xyz/sphere.w,vec3(plane,0.),flatness);
   projected.xy*=1.+envelopeStrength*sin(3.14159265359*flatness);
   gl_Position=vec4(projected,1.);
  }`,fragmentShader:materials.surface.fragmentShader
   .replace('void main(){','uniform float projectionMix;uniform sampler2D detailMap;varying vec2 flatUV;\nvoid main(){')
   .replace('gl_FragColor=vec4(color,1.);',`vec3 mapRGB=texture2D(detailMap,clamp(flatUV,0.,1.)).rgb;
    vec3 mapColor=mix(mapRGB/12.92,pow((mapRGB+.055)/1.055,vec3(2.4)),step(vec3(.04045),mapRGB));
    // Finish the colour simplification on the same geographic mesh, then
    // introduce roads and labels; keep endpoints identical to both renderers.
    vec3 bridge=mix(pow(vec3(16.,35.,50.)/255.,vec3(2.2)),pow(vec3(36.,56.,62.)/255.,vec3(2.2)),texture2D(landMask,uv).a);
    color=mix(color,bridge,smoothstep(0.,.4,projectionMix));
    float edge=max(.00001,.035*(1.-smoothstep(.7,1.,projectionMix)));
    float inside=smoothstep(0.,edge,flatUV.x)*smoothstep(0.,edge,flatUV.y)*smoothstep(0.,edge,1.-flatUV.x)*smoothstep(0.,edge,1.-flatUV.y);
    color=mix(color,mapColor,smoothstep(.18,1.,projectionMix)*inside);gl_FragColor=vec4(color,1.);`)
 });
 const mesh=new THREE.Mesh(geometry,material);mesh.frustumCulled=false;
 const warmScene=new THREE.Scene();warmScene.add(mesh);renderer.compileAsync?.(warmScene,camera).catch(()=>{});
 host.dataset.projectionMesh=String(geometry.id);
 host.unfoldSurface=async({view,snapshot,reverse=false,duration=3100})=>{
  if(disposed)return;active?.finish();
  uniforms.flatCenter.value.set(...view.coords);uniforms.flatSize.value.set(stage.clientWidth,stage.clientHeight);uniforms.flatZoom.value=view.zoom;uniforms.projectionMix.value=reverse?1:0;uniforms.envelopeStrength.value=host.closest('.is-immersive')?0.65:0;
  texture.image=snapshot;texture.needsUpdate=true;renderer.initTexture?.(texture);
  const visibility=new Map(scene.children.map(child=>[child,child.visible]));scene.children.forEach(child=>child.visible=false);scene.add(mesh);
  root.classList.add('globe-is-unfolding');host.dataset.projection='morph';host.dataset.projectionProgress=reverse?'1':'0';renderer.render(scene,camera);
  const reduced=matchMedia('(prefers-reduced-motion:reduce)').matches;
  await new Promise(resolve=>{
   let frame,elapsed=0,last=performance.now(),gaps=0;
   const finish=()=>{cancelAnimationFrame(frame);signal.removeEventListener('abort',finish);scene.remove(mesh);visibility.forEach((visible,child)=>child.visible=visible);root.classList.remove('globe-is-unfolding');host.dataset.projection=reverse?'sphere':'plane';host.dataset.projectionLongFrames=String(gaps);active=null;resolve();};
   const draw=now=>{if(signal.aborted){finish();return;}const delta=now-last;last=now;if(delta>60)gaps++;elapsed+=Math.min(delta,50);const t=reduced?1:Math.min(1,elapsed/duration),ease=(1.-Math.cos(Math.PI*t))*.5,progress=reverse?1-ease:ease;uniforms.projectionMix.value=progress;host.dataset.projectionProgress=progress.toFixed(4);renderer.render(scene,camera);if(t<1)frame=requestAnimationFrame(draw);else finish();};
   active={finish};signal.addEventListener('abort',finish,{once:true});frame=requestAnimationFrame(draw);
  });
 };
 return ()=>{disposed=true;active?.finish();geometry.dispose();material.dispose();texture.dispose();delete host.unfoldSurface;};
}
