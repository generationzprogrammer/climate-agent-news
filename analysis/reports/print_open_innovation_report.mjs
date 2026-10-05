// Renderer-backed fallback after Chrome CLI failed in this Windows environment.
// The verified native HTML remains the only content/graphics source.
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const {chromium}=createRequire(import.meta.url)('playwright');
const folder=resolve(dirname(fileURLToPath(import.meta.url)),'open_innovation');
const browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_BROWSER});
try {
  const page=await browser.newPage({viewport:{width:1080,height:1000},reducedMotion:'reduce'});
  await page.goto(pathToFileURL(resolve(folder,'科产融合全球开放创新生态研究报告.html')).href);
  await page.waitForFunction(()=>document.documentElement.dataset.dataAnalyticsPortableReader==='ready');
  await page.evaluate(()=>document.fonts.ready);
  await page.emulateMedia({media:'print'});
  await page.waitForTimeout(600);
  if((await page.locator('.portable-static-chart-light svg').count()+await page.locator('.native-chart-raster').count())<3)throw new Error('Printed chart missing');
  await page.pdf({path:resolve(folder,'科产融合全球开放创新生态研究报告.pdf'),format:'A4',printBackground:true,preferCSSPageSize:true});
} finally {await browser.close();}
