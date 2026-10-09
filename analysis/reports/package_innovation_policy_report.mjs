// Native packaging with scoped layout/conversion CSS; no custom chart renderer.
import {readFileSync,writeFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const folder=resolve(dirname(fileURLToPath(import.meta.url)),'open_innovation_20261009');
const scripts=resolve(process.argv[2],'skills/build-report/scripts');
const {buildPortableArtifact}=await import(pathToFileURL(resolve(scripts,'build_portable_artifact.mjs')));
const {extractPortableChartSvgs}=await import(pathToFileURL(resolve(scripts,'extract_portable_chart_svgs.mjs')));
const {verifyPortableArtifact}=await import(pathToFileURL(resolve(scripts,'verify_portable_artifact.mjs')));
const input=resolve(folder,'artifact.json'),output=resolve(folder,'科产融合全球模式与中国区域适配政策研究报告.html');
const a=JSON.parse(readFileSync(input,'utf8')),css=readFileSync(resolve(folder,'report_preflight.css'),'utf8');
const packageHtml=charts=>buildPortableArtifact(a,charts?{staticCharts:charts}:{}).replace('</head>','<style id="report-preflight">'+css+'</style></head>');
writeFileSync(output,packageHtml(),'utf8');
const charts=await extractPortableChartSvgs({htmlPath:output,readyTimeoutMs:10000});
for(const [id,c] of Object.entries(charts)){
 for(const theme of ['light','dark']){
  const match=c[theme].svg.match(/viewBox="([^"]+)"/);
  if(!match)throw new Error('Native SVG frame missing: '+id);
  const [x,y,w,h]=match[1].split(/\s+/).map(Number);
  c[theme].svg=c[theme].svg.replace(match[0],'viewBox="'+[x-120,y,w+120,h].join(' ')+'"');
 }
 c.width+=120;
}
if(Object.keys(charts).length!==a.manifest.charts.length)throw new Error('Missing native chart');
writeFileSync(output,packageHtml(charts),'utf8');
const checked=await verifyPortableArtifact({artifactPath:input,htmlPath:output,timeoutMs:25000});
writeFileSync(resolve(folder,'verification_receipt.json'),JSON.stringify({ok:true,stages:{verification:'passed'},...checked,staticCharts:Object.keys(charts)},null,2)+'\n');
console.log(JSON.stringify({status:'passed',blocks:a.manifest.blocks.length,charts:Object.keys(charts)}));
