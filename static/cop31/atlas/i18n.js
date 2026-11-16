// GREEN · COP31: the atlas follows the page language (<html lang>, set by app.js).
export const en=()=>(document.documentElement.lang||'').toLowerCase().startsWith('en');
export const t=(zh,english)=>en()?english:zh;
export const asset=(path,base)=>new URL(path,base).href;
