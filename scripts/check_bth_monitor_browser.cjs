// Isolated desktop/mobile and fresh-user QA. Never writes a real subscription.
const fs=require("node:fs"),path=require("node:path"),http=require("node:http"),assert=require("node:assert/strict");
const {chromium,devices}=require("playwright");
const root=path.resolve(__dirname,".."),out=path.join(root,"tmp/bth-monitor-qa");fs.mkdirSync(out,{recursive:true});
const server=http.createServer((req,res)=>{
  const file=path.resolve(root,"static","."+decodeURIComponent(req.url.split("?")[0]==="/"?"/index.html":req.url.split("?")[0]));
  if(!file.startsWith(path.join(root,"static")+path.sep)||!fs.existsSync(file)){res.writeHead(404).end();return;}
  res.setHeader("Content-Type",({".html":"text/html",".js":"application/javascript",".json":"application/json",".css":"text/css",".svg":"image/svg+xml"})[path.extname(file)]||"application/octet-stream");fs.createReadStream(file).pipe(res);
});
(async()=>{
  await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));const base=`http://127.0.0.1:${server.address().port}`;
  const browser=await chromium.launch({headless:true,executablePath:process.env.BTH_QA_BROWSER||"C:/Program Files/Google/Chrome/Application/chrome.exe"});
  let assertions=0;
  try {for(const mobile of [false,true]){
    const context=await browser.newContext(mobile?{...devices["iPhone 13"]}:{viewport:{width:1440,height:1000}});
    const page=await context.newPage(),errors=[];page.on("pageerror",e=>errors.push(e.message));let challenges=0,subscriptionPosts=0,chatPosts=0;
    await page.route("**/data/bth_assistant_config.json",r=>r.fulfill({json:{endpoint:"https://assistant.test",verification:"off",sitekey:""}}));
    await page.route("**/data/subscription.json",r=>r.fulfill({json:{endpoint:"https://subscription.test/subscribe",unsubscribe_endpoint:"https://subscription.test/unsubscribe"}}));
    await page.route("https://challenges.cloudflare.com/**",r=>{challenges++;r.abort();});
    await page.route("https://assistant.test/chat",r=>{chatPosts++;r.fulfill({json:{answer:"北京应将清洁供热、交通电动化与外调绿电协同推进。",sources:[],charts:[],report:null}});});
    await page.route("https://subscription.test/**",r=>{subscriptionPosts++;r.fulfill({contentType:"text/html",body:"<html>Verifying...</html>"});});
    await page.route("https://assistant.test/subscriptions/**",r=>r.fulfill({json:{ok:true,status:r.request().url().endsWith("unsubscribe")?"unsubscribed":"subscribed"}}));
    await page.goto(base);await page.locator(".bth-energy-cards").first().waitFor({timeout:20000});
    assert.equal(challenges,0);assertions++;
    assert((await page.locator("#bth_green_transition h2").textContent()).includes("京津冀能源统计数据库"));assertions++;
    await page.locator('#bthEnergyRoot [data-energy-tab="history"]').click();
    assert.equal(await page.locator("#bthEnergyHistoryChart svg rect.bar-fill").count(),6);assertions++;
    await page.locator("#bthEnergyRoot").screenshot({path:path.join(out,mobile?"mobile-history.png":"desktop-history.png")});
    await page.locator('#bthEnergyRoot [data-energy-tab="future"]').click();
    assert(await page.locator(".bth-energy-goals article").count()>0);assertions++;
    await page.locator('#bthEnergyRoot [data-energy-tab="latest"]').click();
    const id=await page.locator(".bth-energy-record-link").first().getAttribute("data-energy-record");
    await page.locator(".bth-energy-record-link").first().click();
    assert.equal(await page.locator("[data-energy-row]").count(),1);assertions++;
    assert.equal(await page.locator(`[data-energy-row="${id}"] details`).getAttribute("open"),"");assertions++;
    await page.locator('[data-energy-filter="query"]').fill("");await page.locator('[data-energy-filter="query"]').dispatchEvent("change");
    await page.locator('#bthEnergyRoot [data-energy-filter="dimension"]').selectOption("society");
    assert((await page.locator(".bth-energy-table").textContent()).includes("常住人口"));assertions++;
    await page.locator("#bthEnergyRoot").evaluate(el=>el.scrollIntoView({block:"start"}));
    await page.screenshot({path:path.join(out,mobile?"mobile-monitor.png":"desktop-monitor.png")});
    await page.locator("#bthChatQuestion").fill("北京气候治理如何？");await page.locator(".bth-chat-send").click();
    await page.locator('.bth-chat-message.assistant:not(.streaming)').waitFor({timeout:10000});assert.equal(chatPosts,1);assertions++;
    assert.equal(challenges,0);assertions++;
    await page.evaluate(()=>document.getElementById("subscribeOpen").click());
    await page.locator("#subscribeEmail").fill("synthetic@example.com");await page.locator("#subscribeSubmit").click();
    await page.waitForFunction(()=>!document.getElementById("subscribeModal").open,{},{timeout:10000});
    assert.equal(subscriptionPosts,2);assertions++;
    assert((await page.locator("#toast").textContent()).includes("订阅成功"));assertions++;
    assert.equal(errors.length,0,errors.join("\n"));assertions++;
    if(mobile){assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));assertions++;}
    await context.close();
  }
  console.log(JSON.stringify({status:"passed",assertions,fresh_profiles:2,real_model_calls:0,real_subscriptions:0}));
  }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e.stack);server.close();process.exitCode=1;});
