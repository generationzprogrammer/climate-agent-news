import * as THREE from './vendor/three/three.module.js';

// View-space studio lighting stays consistent as the globe is explored.
const surfaceVertex=`
 varying vec3 vNormal;
 varying vec3 vPosition;
 varying vec3 vLocal;
 void main(){
  vLocal=position;
  vNormal=normalize(normalMatrix*normal);
  vec4 p=modelViewMatrix*vec4(position,1.0);
  vPosition=p.xyz;
  gl_Position=projectionMatrix*p;
 }`;

export function globeMaterials(landCanvas){
 const texture=new THREE.CanvasTexture(landCanvas);
 texture.anisotropy=4;
 const surface=new THREE.ShaderMaterial({
  uniforms:{landMask:{value:texture},sea:{value:new THREE.Color()},land:{value:new THREE.Color()},shade:{value:new THREE.Color()},pearl:{value:new THREE.Color()},rim:{value:new THREE.Color()},dark:{value:0}},
  vertexShader:surfaceVertex,
  fragmentShader:`
   uniform sampler2D landMask;
   uniform vec3 sea,land,shade,pearl,rim;
   uniform float dark;
   varying vec3 vNormal,vPosition,vLocal;
   void main(){
    vec3 n=normalize(vNormal),view=normalize(-vPosition);
    vec3 light=normalize(mix(vec3(-0.95,0.95,0.65),vec3(-0.65,0.85,1.0),dark));
    vec3 p=normalize(vLocal);
    vec2 uv=vec2(atan(p.x,p.z)/6.28318530718+0.5,asin(p.y)/3.14159265359+0.5);
    float mask=texture2D(landMask,uv).a;
    float diffuse=smoothstep(-0.42,0.95,dot(n,light));
    vec3 pigment=mix(sea,land,mask*mix(0.94,0.72,dark));
    vec3 ceramic=pigment*(0.38+0.62*diffuse);
    vec3 color=mix(ceramic,mix(shade,pigment,0.16+0.84*diffuse),dark);
    float softbox=pow(max(dot(n,normalize(light+view)),0.0),24.0);
    color+=pearl*softbox*mix(0.035,0.12,dark);
    float fresnel=pow(1.0-max(dot(n,view),0.0),3.5);
    color=mix(color,rim,fresnel*mix(0.025,0.4,dark));
    gl_FragColor=vec4(color,1.0);
    #include <colorspace_fragment>
   }`
 });
 const dots=new THREE.ShaderMaterial({
  uniforms:{color:{value:new THREE.Color()},pixelRatio:{value:1},dark:{value:0}},transparent:true,depthWrite:false,
  vertexShader:`
   uniform float pixelRatio,dark;
   varying float vLight,vFacing,vGrain;
   void main(){
    vec3 n=normalize(normalMatrix*normalize(position));
    vec4 p=modelViewMatrix*vec4(position,1.0);
    vFacing=max(dot(n,normalize(-p.xyz)),0.0);
    vLight=0.52+0.48*max(dot(n,normalize(vec3(-0.65,0.85,1.0))),0.0);
    vGrain=fract(sin(dot(position,vec3(12.9898,78.233,37.719)))*43758.5453);
    gl_PointSize=clamp(mix(1.15,1.65,dark)*pixelRatio*330.0/-p.z,1.0,4.0*pixelRatio);
    gl_Position=projectionMatrix*p;
   }`,
  fragmentShader:`
   uniform vec3 color;
   uniform float dark;
   varying float vLight,vFacing,vGrain;
   void main(){
    float d=length(gl_PointCoord-0.5);
    float alpha=(1.0-smoothstep(0.26,0.5,d))*smoothstep(0.02,0.32,vFacing)*mix(0.14,0.76,dark)*mix(step(0.78,vGrain),1.0,dark);
    gl_FragColor=vec4(color*vLight,alpha);
    #include <colorspace_fragment>
   }`
 });
 const atmosphere=new THREE.ShaderMaterial({
  uniforms:{color:{value:new THREE.Color()},strength:{value:0.3}},
  vertexShader:surfaceVertex,transparent:true,depthWrite:false,side:THREE.FrontSide,
  fragmentShader:`
   uniform vec3 color;
   uniform float strength;
   varying vec3 vNormal,vPosition;
   void main(){
    float facing=abs(dot(normalize(vNormal),normalize(-vPosition)));
    float halo=exp(-pow((facing-0.24)/0.15,2.0));
    gl_FragColor=vec4(color,halo*strength);
    #include <colorspace_fragment>
   }`
 });
 function theme(dark){
  const u=surface.uniforms;

  u.sea.value.set('#eceeeb');
  u.land.value.set('#aab7a7');
  u.shade.value.set(dark?'#030e19':'#244c50');
  u.pearl.value.set(dark?'#80c7b5':'#faf9f4');
  u.rim.value.set(dark?'#528f8b':'#c3ccc3');u.dark.value=dark?1:0;
  dots.uniforms.dark.value=dark?1:0;
  dots.uniforms.color.value.set(dark?'#acd6b8':'#637260');
  atmosphere.uniforms.color.value.set(dark?'#79bdad':'#97baae');
  atmosphere.uniforms.strength.value=dark?.2:0;
 }
 return {surface,dots,atmosphere,texture,theme};
}
