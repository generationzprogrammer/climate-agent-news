/* Convert the validated native HTML reader; no separate chart implementation. */
const {chromium}=require('playwright'),path=require('node:path'),{pathToFileURL}=require('node:url');
const folder=path.resolve(__dirname,'open_innovation_20261009'),base='科产融合全球模式与中国区域适配政策研究报告';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_BROWSER});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},colorScheme:'light',reducedMotion:'reduce'});
  await page.goto(pathToFileURL(path.join(folder,base+'.html')).href);
  await page.waitForFunction(()=>document.documentElement.dataset.dataAnalyticsPortableReader==='ready');
  await page.evaluate(()=>document.fonts.ready);
  if(process.argv.includes('--inspect')){
   console.log(JSON.stringify(await page.evaluate(()=>({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,
    overflow:[...document.querySelectorAll('*')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&r.right>document.documentElement.clientWidth+2;}).slice(0,20).map(e=>({tag:e.tagName,cls:e.className,text:e.textContent.slice(0,70),right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width,overflow:getComputedStyle(e).overflowX}))})),null,2));return;
  }
  await page.emulateMedia({media:'print'});
  await page.pdf({path:path.join(folder,base+'.pdf'),printBackground:true,preferCSSPageSize:true,displayHeaderFooter:true,headerTemplate:'<span></span>',footerTemplate:'<div style="width:100%;text-align:center;font-size:9px;color:#555"><span class="pageNumber"></span></div>'});
  console.log(JSON.stringify({status:'printed',file:base+'.pdf'}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
