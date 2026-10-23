const {chromium,devices}=require('playwright');
const fs=require('fs'),http=require('http'),path=require('path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../static'),out=path.resolve(__dirname,'../tmp/innovation-substance-qa');
const book=JSON.parse(fs.readFileSync(path.join(root,'data/innovation_cases.json'),'utf8'));
const server=http.createServer((req,res)=>{
  let pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);if(pathname.endsWith('/'))pathname+='index.html';
  const file=path.resolve(root,'.'+pathname);if(!file.startsWith(root+path.sep))return res.writeHead(403).end();
  fs.readFile(file,(e,data)=>{if(e)return res.writeHead(404).end();res.writeHead(200,{'Content-Type':({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json'})[path.extname(file)]||'application/octet-stream'});res.end(data);});
});
(async()=>{
  fs.mkdirSync(out,{recursive:true});await new Promise(r=>server.listen(0,'127.0.0.1',r));
  const browser=await chromium.launch({executablePath:process.env.BTH_QA_BROWSER,headless:true});let checks=0;
  try{
    for(const mobile of [false,true]){
      const context=await browser.newContext(mobile?devices['Pixel 7']:{viewport:{width:1440,height:1050}});
      const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
      await page.goto(process.env.INNOVATION_QA_URL||'http://127.0.0.1:'+server.address().port+'/innovation/',{waitUntil:'domcontentloaded'});
      await page.locator('.ic-card').first().waitFor();
      for(const registry of ['nsf_iucrc','embrapii_export','australia_crcp','jst_coinext','africa_ace2','china_moe_first_list']){
        const c=book.cases.find(c=>c.registry_record?.registry===registry);
        await page.locator('[data-filter="query"]').fill(c.id);
        await page.locator('[data-detail="'+c.id+'"]').click();
        const body=page.locator('.ic-dialog-body'),value=await body.textContent();
        assert(!value.includes('比较合作主体的职责、技术验证条件'));checks++;
        assert(!value.includes('名录提供组织、技术任务或资助事实'));checks++;
        assert(!value.includes('JST项目表列出代表机构'));checks++;
        assert(await page.locator('.ic-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth+2));checks++;
        if(registry==='nsf_iucrc'){
          assert(await body.locator('.ic-registry-facts').textContent().then(s=>s.includes('列名高校')));checks++;
          assert.equal(await body.locator('.ic-programme').getAttribute('open'),null);checks++;
          await page.screenshot({path:path.join(out,(mobile?'mobile':'desktop')+'-facts.png')});
        }
        if(registry==='australia_crcp'){
          await body.locator('.ic-original summary').click();assert(await body.locator('.ic-original p').isVisible());checks++;
        }
        await page.locator('.ic-close').click();
      }
      await page.locator('#innovationLanguage').click();
      const c=book.cases.find(c=>c.registry_record?.registry==='nsf_iucrc');
      await page.locator('[data-filter="query"]').fill(c.id);await page.locator('[data-detail="'+c.id+'"]').click();
      assert((await page.locator('.ic-dialog-body').textContent()).includes('Programme rules'));checks++;
      assert.deepEqual(errors,[]);checks++;await context.close();
    }
    console.log(JSON.stringify({status:'passed',checks}));
  }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
