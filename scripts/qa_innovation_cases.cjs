/* Isolated browser QA; local test server only, no model or email calls. */
const {chromium,devices}=require("playwright");
const http=require("http"),fs=require("fs"),path=require("path"),assert=require("node:assert/strict");
const root=path.resolve(__dirname,"../static"),out=path.resolve(__dirname,"../tmp/innovation-qa");
const book=JSON.parse(fs.readFileSync(path.join(root,"data/innovation_cases.json"),"utf8"));
const {filterCases}=require("../static/innovation-cases.js");
const server=http.createServer((req,res)=>{
  const pathname=decodeURIComponent(new URL(req.url,"http://localhost").pathname);
  const file=path.resolve(root,"."+ (pathname==="/" ? "/index.html":pathname));
  if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}
  const ext=path.extname(file),types={".html":"text/html",".js":"text/javascript",".css":"text/css",".json":"application/json",".svg":"image/svg+xml",".png":"image/png"};
  fs.readFile(file,(e,data)=>{if(e){res.writeHead(404).end();return;}res.writeHead(200,{"Content-Type":types[ext]||"application/octet-stream"});res.end(data);});
});
(async()=>{
  fs.mkdirSync(out,{recursive:true});
  await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
  const origin=process.env.CASE_QA_URL||"http://127.0.0.1:"+server.address().port+"/";
  const browser=await chromium.launch({headless:true,executablePath:process.env.BTH_QA_BROWSER});
  let checks=0;
  try {
    for(const mobile of [false,true]){
      const context=await browser.newContext(mobile?devices["Pixel 7"]:{viewport:{width:1440,height:1000}});
      const page=await context.newPage();const errors=[];page.on("pageerror",e=>errors.push(e.message));
      await page.route("**/cdn-cgi/**",route=>route.abort());
      await page.route("**/*cloudflareinsights.com/**",route=>route.abort());
      await page.goto(origin+"?mode=energy#innovationCases",{waitUntil:"domcontentloaded",timeout:60000});
      await page.locator("#innovationCases .ic-card").first().waitFor({timeout:60000});
      assert.equal(await page.locator("#innovationCases .ic-result").textContent(),book.cases.length+" 个案例");checks++;
      assert(book.cases.length>=300);checks++;
      assert.equal(await page.locator("#innovationCases .ic-card").count(),12);checks++;
      if(mobile){
        await page.locator("#mobileMenuToggle").click();
        assert(await page.locator('#mobileMenu a[href="#innovationCases"]').isVisible());checks++;
        await page.locator('#mobileMenu a[href="#innovationCases"]').click();
      }
      await page.locator('#innovationCases [data-filter="sector"]').selectOption("battery");
      assert.equal(await page.locator("#innovationCases .ic-card").count(),12);checks++;
      assert(await page.locator(".ic-compare-help").textContent().then(s=>s.includes("勾选")));checks++;
      await page.locator("#innovationCases [data-select]").nth(0).check();
      await page.locator("#innovationCases [data-select]").nth(1).check();
      await page.locator("#innovationCases .ic-compare").click();
      assert(await page.locator("#innovationCases dialog").isVisible());checks++;
      assert.equal(await page.locator("#innovationCases .ic-dialog-body>.ic-matrix-scroll .ic-matrix thead th").count(),3);checks++;
      assert(await page.locator("#innovationCases .ic-dialog-body").textContent().then(s=>s.includes("已记录的实践")));checks++;
      assert.equal(await page.locator("#innovationCases [data-radar-axis]").count(),10);checks++;
      await page.locator("#innovationCases [data-radar-axis]").first().focus();
      await page.locator("#innovationCases [data-radar-axis]").first().press("Enter");
      await page.locator("#innovationCases [data-radar-axis]").last().click();
      assert(await page.locator("#innovationCases .ic-radar-readout").textContent().then(s=>s.includes("/5")));checks++;
      await page.locator("#innovationCases dialog").screenshot({path:path.join(out,mobile?"comparison-mobile.png":"comparison-desktop.png")});
      await page.locator("#innovationCases .ic-close").click();
      assert(!await page.locator("#innovationCases dialog").isVisible());checks++;
      await page.locator('#innovationCases [data-filter="sector"]').selectOption("");
      await page.locator('#innovationCases [data-filter="country"]').selectOption("US");
      assert.equal(await page.locator("#innovationCases .ic-result").textContent(),filterCases(book,{country:"US"}).length+" 个案例");checks++;
      const usButton=page.locator('#innovationCases [data-detail^="oi_arpae_"]').first();
      const usId=await usButton.getAttribute("data-detail"),usCase=book.cases.find(c=>c.id===usId);
      await usButton.click();
      const usBody=await page.locator("#innovationCases .ic-dialog-body").textContent();
      assert(usBody.includes(usCase.summary.zh)&&usBody.includes(usCase.mechanism.zh));checks++;
      assert(usBody.includes("ARPA-E登记资助额")&&usBody.includes("美元")&&!usBody.includes("NaN")&&!usBody.includes("百万欧元"));checks++;
      assert(usBody.includes("进行中")||usBody.includes("历史项目"));checks++;
      assert.equal(await page.locator("#innovationCases [data-radar-axis]").count(),0);checks++;
      await page.locator("#innovationCases .ic-partners summary").click();
      assert(await page.locator("#innovationCases .ic-partner-table").textContent().then(s=>s.includes("未披露")));checks++;
      await page.locator("#innovationCases dialog").screenshot({path:path.join(out,mobile?"us-detail-mobile.png":"us-detail-desktop.png")});
      await page.locator("#innovationCases .ic-close").click();
      assert(!await page.locator("#innovationCases dialog").isVisible());checks++;
      await page.locator('#innovationCases [data-filter="country"]').selectOption("SG");
      await page.locator("#innovationCases [data-detail]").first().click();
      assert(await page.locator("#innovationCases .ic-dialog-body").textContent().then(s=>s.includes("适配分析")&&s.includes("原始证据")));checks++;
      await page.locator("#innovationCases dialog").screenshot({path:path.join(out,mobile?"detail-mobile.png":"detail-desktop.png")});
      await page.keyboard.press("Escape");
      await page.locator('#innovationCases [data-filter="country"]').selectOption("");
      await page.locator("#innovationCases .ic-clear").click();
      await page.locator('#innovationCases [data-filter="query"]').fill("电池");
      assert.equal(await page.locator("#innovationCases .ic-card").count(),Math.min(12,filterCases(book,{query:"电池"}).length));checks++;
      const downloadPromise=page.waitForEvent("download");
      await page.locator("#innovationCases .ic-export").click();
      const download=await downloadPromise;
      await download.saveAs(path.join(out,mobile?"mobile.csv":"desktop.csv"));
      assert(fs.readFileSync(path.join(out,mobile?"mobile.csv":"desktop.csv"),"utf8").includes("source_urls"));checks++;
      await page.locator('#innovationCases [data-filter="query"]').fill("");
      await page.locator(mobile?"#mobileMenuToggle":"#languageToggle").click();
      if(mobile)await page.locator("#mobileLanguageToggle").click();
      assert.equal(await page.locator("#innovationCases h2").textContent(),"Global science–industry innovation cases");checks++;
      await page.locator('#innovationCases [data-filter="country"]').selectOption("CN");
      assert(await page.locator("#innovationCases .ic-card").allTextContents().then(rows=>rows.some(s=>s.includes("ITER"))));checks++;
      const docWidth=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
      assert(docWidth.scroll<=docWidth.width+1,JSON.stringify(docWidth));checks++;
      await page.locator('#innovationCases [data-filter="country"]').selectOption("");
      if(mobile){await page.locator("#mobileMenuToggle").click();await page.locator("#mobileLanguageToggle").click();}
      else await page.locator("#languageToggle").click();
      await page.locator("#innovationCases").screenshot({path:path.join(out,mobile?"library-mobile.png":"library-desktop.png")});
      if(mobile){await page.locator("#mobileMenuToggle").click();await page.locator("#mobileModeToggle").click();}
      else await page.locator("#modeToggle").click();
      assert(!await page.locator("#innovationCases").isVisible());checks++;
      assert(await page.locator("#todayTitle").textContent().then(s=>s.includes("气候")));checks++;
      assert.equal(errors.length,0,JSON.stringify(errors));checks++;
      await context.close();
    }
    console.log(JSON.stringify({status:"passed",checks,desktop_mobile:true,model_calls:0,screenshots:out}));
  }finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e.stack);server.close();process.exitCode=1;});
