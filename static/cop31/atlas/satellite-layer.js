import {t} from './i18n.js';
// Render the same geographic image used by the globe into Mercator tiles locally.
// Each scanline is reprojected; a stretched image overlay would misplace latitude.
let imagery;
function image(){return imagery??=new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>{imagery=null;reject(Error('地球影像未能加载'));};img.src=new URL('./assets/earth.jpg',import.meta.url).href;});}
export function satelliteLayer(L){
 const Layer=L.GridLayer.extend({
  createTile(coords,done){
   const tile=document.createElement('canvas');tile.width=256;tile.height=256;
   image().then(img=>{const ctx=tile.getContext('2d'),n=2**coords.z,x=((coords.x%n)+n)%n;const sx=x/n*img.naturalWidth,sw=img.naturalWidth/n;
    for(let row=0;row<256;row++){const y=(coords.y+(row+.5)/256)/n,lat=Math.atan(Math.sinh(Math.PI*(1-2*y))),sy=(.5-lat/Math.PI)*img.naturalHeight;ctx.drawImage(img,sx,Math.max(0,sy-.5),sw,1,0,row,256,1);}
    done(null,tile);
   }).catch(error=>done(error,tile));return tile;
  }
 });
 return new Layer({tileSize:256,noWrap:true,bounds:[[-85.05112878,-180],[85.05112878,180]],minZoom:2,maxZoom:10,maxNativeZoom:4,attribution:t('地表影像 © NASA Blue Marble','Imagery © NASA Blue Marble')});
}
