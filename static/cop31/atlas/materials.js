import * as THREE from './vendor/three/three.module.js';
import {globeMaterials as original} from './globe-materials.js';

// Longitudes use the same geographic coordinates as the existing case markers.
// GREEN (2026-11-10, user: 地球模型高清一些，但也不要加载得太慢): the globe starts on the package's 2048 px picture and,
// on screens wide enough to show the difference, changes to the same NASA picture at 4096 px once that has been
// fetched and decoded off the main thread (assets/earth-4096.jpg, from NASA's land_ocean_ice_8192.png).
export function globeMaterials(canvas,options={}){
 const m=original(canvas),loader=new THREE.TextureLoader();
 const earth=loader.load(new URL('./assets/earth.jpg',import.meta.url).href,()=>document.documentElement.dataset.earthTexture='ready');
 const clouds=loader.load(new URL('./assets/clouds.jpg',import.meta.url).href);
 earth.anisotropy=16;clouds.anisotropy=8;let surfaceMap=earth,disposed=false;
 const old=m.surface;
 m.surface=new THREE.ShaderMaterial({
  uniforms:{earth:{value:earth},clouds:{value:clouds},time:{value:0},cloudStrength:{value:.38},dark:{value:0},mapBlend:{value:0},landMask:{value:m.texture}},
  vertexShader:`varying vec3 normalView,localPos,viewPos;
   void main(){localPos=position;normalView=normalize(normalMatrix*normal);vec4 p=modelViewMatrix*vec4(position,1.);viewPos=p.xyz;gl_Position=projectionMatrix*p;}`,
  fragmentShader:`uniform sampler2D earth,clouds,landMask;uniform float time,dark,cloudStrength,mapBlend;varying vec3 normalView,localPos,viewPos;
   void main(){
    vec3 p=normalize(localPos),n=normalize(normalView),v=normalize(-viewPos);
    vec2 uv=vec2(atan(p.x,p.z)/6.28318530718+.5,asin(p.y)/3.14159265359+.5);
    vec3 land=pow(texture2D(earth,uv).rgb,vec3(2.2));
    vec3 light=normalize(vec3(-.65,.7,1.2));float sun=dot(n,light);
    float diffuse=smoothstep(-.24,.95,sun);
    vec3 color=land*(.16+diffuse*1.22);
    // Gentle differential drift makes clouds move independently of the surface.
    float drift=time*.0032;
    float latitudeWave=sin(uv.y*14.+time*.16)*.0025;
    vec2 cloudUV=vec2(fract(uv.x+drift+latitudeWave),clamp(uv.y+sin(uv.x*18.+time*.12)*.0018,0.,1.));
    vec4 cloud=texture2D(clouds,cloudUV);
    float vapor=clamp(dot(cloud.rgb,vec3(.333))*cloud.a,0.,1.);
    float breathing=.96+.04*sin(time*.28+uv.y*9.);
    color=mix(color,vec3(.85,.91,.94)*(.25+.75*diffuse),pow(vapor,1.3)*cloudStrength*breathing);
    float ocean=clamp((land.b-land.r)*12.,0.,1.);
    float glint=pow(max(dot(n,normalize(light+v)),0.),42.);
    color+=vec3(.38,.58,.7)*glint*ocean*.17;
    float rim=pow(1.-max(dot(n,v),0.),3.5);
    color=mix(color,vec3(.19,.48,.72),rim*.48);
    // Geographic material bridge: simplify the same coastlines before street detail.
    float landArea=texture2D(landMask,uv).a;
    vec3 atlasSea=pow(vec3(16.,35.,50.)/255.,vec3(2.2));
    vec3 atlasLand=pow(vec3(36.,56.,62.)/255.,vec3(2.2));
    vec3 cartographic=mix(atlasSea,atlasLand,landArea);
    color=mix(color,cartographic,mapBlend);
    gl_FragColor=vec4(color,1.);
    #include <colorspace_fragment>
   }`
 });old.dispose();
 const theme=m.theme;m.theme=dark=>{theme(dark);m.surface.uniforms.dark.value=dark?1:0;m.atmosphere.uniforms.color.value.set('#6badde');m.atmosphere.uniforms.strength.value=dark?.22:.13;};
 m.tick=time=>{if(!matchMedia('(prefers-reduced-motion: reduce)').matches)m.surface.uniforms.time.value=time;};
 m.dispose=()=>{disposed=true;surfaceMap.dispose();clouds.dispose();};
 if(options.sharp&&'createImageBitmap' in window){
  const upgrade=()=>{if(disposed)return;new THREE.ImageBitmapLoader().setOptions({imageOrientation:'flipY',premultiplyAlpha:'none',colorSpaceConversion:'none'}).load(new URL('./assets/earth-4096.jpg',import.meta.url).href,bitmap=>{
   if(disposed){bitmap.close?.();return;}const sharp=new THREE.Texture(bitmap);sharp.flipY=false;sharp.anisotropy=16;sharp.generateMipmaps=true;sharp.minFilter=THREE.LinearMipmapLinearFilter;sharp.magFilter=THREE.LinearFilter;sharp.needsUpdate=true;
   const previous=surfaceMap;surfaceMap=sharp;m.surface.uniforms.earth.value=sharp;options.onchange?.();setTimeout(()=>previous.dispose(),0);document.documentElement.dataset.earthTexture='sharp';
  },undefined,()=>{});};
  // after the first picture is on screen and the page is idle: the sharper one must not hold the globe back
  const later=()=>('requestIdleCallback' in window?requestIdleCallback(upgrade,{timeout:4000}):setTimeout(upgrade,1500));
  if(earth.image)later();else{const wait=setInterval(()=>{if(disposed){clearInterval(wait);return;}if(earth.image){clearInterval(wait);later();}},300);}
 }
 return m;
}
