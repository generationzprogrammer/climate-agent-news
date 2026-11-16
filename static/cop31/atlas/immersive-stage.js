// Resize the live renderer only at the endpoints. The browser compositor scales
// a frozen copy in between; no per-frame layout or WebGL work is performed here.
export function immersiveStage(content,{signal,onExit}){
 let placeholder,parent,savedStyle,savedOverflow,savedGutter,stage,stageStyle,view,viewStyle,insets,active=false,overlay=null,animations=[];
 const globe=()=>content.querySelector('.atlas-globe-layer');
 const reduce=()=>matchMedia('(prefers-reduced-motion:reduce)').matches;
 const viewport=()=>({left:0,top:0,width:innerWidth,height:innerHeight});
 const rect=r=>({left:r.left,top:r.top,width:r.width,height:r.height});
 const clip=r=>`inset(${r.top}px ${Math.max(0,innerWidth-r.left-r.width)}px ${Math.max(0,innerHeight-r.top-r.height)}px ${r.left}px round 8px)`;
 const clear=()=>{animations.forEach(a=>a.cancel());animations=[];overlay?.remove();overlay=null;};
 const restore=()=>{
  clear();if(parent?.isConnected&&placeholder?.isConnected)parent.insertBefore(content,placeholder);else if(active)content.remove();
  placeholder?.remove();placeholder=null;content.classList.remove('is-immersive');delete content.dataset.framing;
  for(const [element,style] of [[content,savedStyle],[stage,stageStyle],[view,viewStyle]])if(element){if(style===null)element.removeAttribute('style');else element.setAttribute('style',style);}
  document.documentElement.style.overflow=savedOverflow;document.documentElement.style.scrollbarGutter=savedGutter;active=false;document.documentElement.classList.remove('atlas-immersive');globe()?.freezeViewport?.(false);
 };
 function picture(){globe()?.suspendAtlas?.(true);const snapshot=globe()?.captureViewport?.();globe()?.freezeViewport?.(true);return snapshot;}
 function cover(snapshot,from,to,fromClip,toClip,reverse){
  overlay=document.createElement('div');overlay.className='atlas-compositor-cover';overlay.setAttribute('aria-hidden','true');
  Object.assign(overlay.style,{position:'fixed',inset:'0',zIndex:'10030',pointerEvents:'none',overflow:'hidden',willChange:'clip-path',clipPath:fromClip,background:reverse?'#102332':originalBackground});
  const canvas=snapshot.canvas;Object.assign(canvas.style,{position:'absolute',left:'0',top:'0',width:snapshot.width+'px',height:snapshot.height+'px',transformOrigin:'0 0',willChange:'transform',transform:from});overlay.append(canvas);document.body.append(overlay);
  const options={duration:reduce()?0:320,easing:'cubic-bezier(.22,.65,.25,1)',fill:'forwards'};
  animations=[canvas.animate([{transform:from},{transform:to}],options),overlay.animate([{clipPath:fromClip,backgroundColor:reverse?'#102332':originalBackground},{clipPath:toClip,backgroundColor:reverse?originalBackground:'#102332'}],options)];
  return Promise.all(animations.map(a=>a.finished.catch(()=>{})));
 }
 const transform=(x,y,scale)=>`translate3d(${x}px,${y}px,0) scale(${scale})`;
 let originalBackground='#e9eef3';
 return {get active(){return active;},
  async enter(){
   if(active)return;parent=content.parentElement;savedStyle=content.getAttribute('style');stage=content.querySelector('.globe-stage');view=content.querySelector('.globe-view');stageStyle=stage.getAttribute('style');viewStyle=view.getAttribute('style');
   const r=rect(content.getBoundingClientRect()),s=rect(stage.getBoundingClientRect()),snapshot=picture();
   originalBackground='#e9eef3';insets={top:s.top-r.top,left:s.left-r.left,right:r.left+r.width-s.left-s.width,bottom:r.top+r.height-s.top-s.height};
   placeholder=document.createElement('div');placeholder.className='atlas-stage-placeholder';placeholder.style.height=r.height+'px';parent.insertBefore(placeholder,content);
   savedOverflow=document.documentElement.style.overflow;savedGutter=document.documentElement.style.scrollbarGutter;
   const scale=innerHeight/s.height,ending=transform((innerWidth-s.width*scale)/2,0,scale);
   const motion=snapshot?cover(snapshot,transform(s.left,s.top,1),ending,clip(r),'inset(0px 0px 0px 0px round 0px)',false):Promise.resolve();
   document.documentElement.style.scrollbarGutter='auto';document.documentElement.style.overflow='hidden';document.body.append(content);active=true;document.documentElement.classList.add('atlas-immersive');content.classList.add('is-immersive');content.dataset.framing='opening';content.style.opacity='0';
   Object.assign(content.style,{left:'0px',top:'0px',width:'100vw',height:'100dvh',borderRadius:'0px'});globe()?.syncViewport?.();
   await motion;if(signal.aborted)return;globe()?.freezeViewport?.(false);content.style.removeProperty('opacity');clear();delete content.dataset.framing;
  },
  async exit(){
   if(!active)return;const r=rect(placeholder.getBoundingClientRect()),snapshot=picture();content.dataset.framing='closing';
   const s={left:r.left+insets.left,top:r.top+insets.top,width:r.width-insets.left-insets.right,height:r.height-insets.top-insets.bottom};
   const scale=s.height/innerHeight;
   content.style.opacity='0';
   await (snapshot?cover(snapshot,transform(0,0,1),transform(s.left+(s.width-innerWidth*scale)/2,s.top,scale),'inset(0px 0px 0px 0px round 0px)',clip(r),true):Promise.resolve());
   if(signal.aborted)return;restore();onExit?.();
  },dispose(){if(active)restore();else clear();}
 };
}
