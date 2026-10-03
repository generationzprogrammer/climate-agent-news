// Isolated local browser QA; mocks external services, never calls a paid model.
const fs = require("node:fs"), path = require("node:path"), http = require("node:http"), assert = require("node:assert/strict");
const {chromium, devices} = require("playwright");
const root = path.resolve(__dirname, ".."), output = path.join(root, "tmp/bth-assistant-qa");
fs.mkdirSync(output, {recursive: true});
const server = http.createServer((req, res) => {
  let file = path.resolve(root, "static", "." + decodeURIComponent(req.url.split("?")[0]));
  if (req.url === "/") file = path.join(root, "static/index.html");
  if (!file.startsWith(path.join(root, "static") + path.sep)) {res.writeHead(403).end(); return;}
  if (!fs.existsSync(file)) {res.writeHead(404).end(); return;}
  const type = {".js":"application/javascript", ".json":"application/json", ".html":"text/html", ".css":"text/css", ".svg":"image/svg+xml"}[path.extname(file)] || "application/octet-stream";
  res.writeHead(200, {"Content-Type": type + "; charset=utf-8"}); fs.createReadStream(file).pipe(res);
});
(async () => {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({headless: true, ...(process.env.BTH_QA_BROWSER ? {executablePath: process.env.BTH_QA_BROWSER} : {})});
  const page = await browser.newPage({viewport: {width: 1280, height: 1000}, acceptDownloads: true});
  const errors = []; page.on("pageerror", error => errors.push(error.message));
  const data = JSON.parse(fs.readFileSync(path.join(root, "static/data/bth_assistant_knowledge.json"), "utf8"));
  const sources = data.records.filter(r => r.kind === "observation" && r.metric === "pv_capacity" && r.year === 2025);
  const result = {answer: `2025年北京、天津和河北光伏累计并网装机分别为210.2、1027.9和8462.9万千瓦。${sources.map(s => `[${s.id}]`).join("")}\n\n河北规模明显较大，但装机不是发电量，不能据此比较发电利用率。`, report: {title: "京津冀光伏装机比较", sections: [{heading: "装机规模", paragraphs: [`2025年三地光伏累计并网装机分别为210.2、1027.9和8462.9万千瓦。${sources.map(s => `[${s.id}]`).join("")}`]}, {heading: "区域差异", paragraphs: ["河北光伏装机规模较大。装机容量反映设备规模，发电量还受日照条件、利用小时和电网消纳影响，应分别分析。"]}]}, charts: [{title: "2025年三地光伏累计并网装机", unit: "万千瓦", points: sources.map(s => ({id:s.id, label:`${s.region} ${s.year}`, value:s.value}))}], sources, generated_at:"2026-10-02T00:00:00Z"};
  const policySources = data.records.filter(r => r.kind === "policy" && (r.province || r.region).includes("北京") && r.date.startsWith("2025")).slice(0, 3);
  assert(policySources.length >= 2, "policy test needs multiple Beijing sources");
  const policyAnswer = `**北京气候治理的关键是政策落实。**${policySources.map(s => `《${s.title}》[${s.id}]`).join("；")}。\n\n应重点分析能源替代、建筑节能与交通减排的协同，以及市区执行机制。`;
  const policyResult = {answer: policyAnswer, sources: policySources, report: null, charts: [], generated_at:"2026-10-02T00:00:00Z"};
  let requests = [];
  await page.route("**/data/bth_assistant_config.json", route => route.fulfill({json: {endpoint: base, sitekey:"TEST-PUBLIC-SITE-KEY"}}));
  await page.route("**/health", route => route.fulfill({json: {ok:true,ready:true}}));
  await page.route("https://challenges.cloudflare.com/**", route => route.fulfill({contentType:"application/javascript", body:"window.turnstile={render:(el,o)=>{window.testVerification=o; o.callback('TEST-TOKEN'); return 1;},reset:()=>window.testVerification.callback('TEST-TOKEN'),remove:()=>{}};"}));
  await page.route("**/chat", async route => {
    requests.push(route.request().postDataJSON());
    if (route.request().postDataJSON().question.includes("超时测试") || route.request().postDataJSON().question.includes("停止测试")) return;
    const answer = requests.length === 1 ? result : policyResult;
    if (route.request().postDataJSON().transport === "json") {await route.fulfill({contentType:"application/json",body:JSON.stringify(answer)}); return;}
    const raw = JSON.stringify(answer), frame = (event, value) => `event: ${event}\ndata: ${JSON.stringify(value)}\n\n`;
    await route.fulfill({contentType:"text/event-stream", body:frame("status",{evidence_count:3}) + frame("delta",{text:raw.slice(0,90)}) + frame("delta",{text:raw.slice(90)}) + frame("result",answer)});
  });
  try {
    await page.goto(base); await page.locator("#bthChatQuestion").waitFor({timeout:20000});
    await page.evaluate(() => {
      window.referenceLeaks = [];
      new MutationObserver(() => document.querySelectorAll(".bth-chat-message.assistant .bth-chat-answer").forEach(el => {
        if (/P-bth_policy_|D-O\d+/.test(el.textContent)) window.referenceLeaks.push(el.textContent);
      })).observe(document.querySelector(".bth-chat-messages"), {childList:true,subtree:true,characterData:true});
    });
    await page.locator("#bthChatQuestion").fill("比较三地光伏装机，生成图表和报告");
    await page.waitForFunction(() => !!window.testVerification);
    await page.locator(".bth-chat-send").click(); await page.locator('.bth-chat-downloads [data-export="docx"]').first().waitFor();
    assert.equal(await page.locator(".bth-citation").count(), sources.length);
    assert.equal(await page.locator(".bth-citation").first().getAttribute("href"), new URL(sources[0].url).href);
    for (const format of ["docx","pdf","png"]) {
      const pending = page.waitForEvent("download"); await page.locator(`[data-export="${format}"]`).first().click();
      const file = await pending; await file.saveAs(path.join(output, `sample.${format}`));
    }
    await page.locator("#bthAssistantRoot").screenshot({path:path.join(output,"desktop.png")});
    await page.setViewportSize({width:390,height:844});
    await page.locator("#bthChatQuestion").fill("北京这几年的气候治理如何？"); await page.locator(".bth-chat-send").click();
    await page.waitForFunction(() => document.querySelectorAll('[data-export="docx"]').length === 2);
    assert(requests[1].history.length >= 2, "multi-turn history missing");
    const policyMessage = page.locator(".bth-chat-message.assistant:not(.streaming)").last();
    assert.equal(requests[1].transport,"stream","mobile uses text events, not delayed JSON or Fetch streams");
    assert.equal(await policyMessage.locator(".bth-chat-answer strong").count(),1);
    assert(!(await policyMessage.innerText()).includes("**"),"literal bold markers remain");
    assert.equal(await policyMessage.locator(".bth-citation").count(), policySources.length);
    assert(!(await page.locator(".bth-chat-messages").innerText()).match(/P-bth_policy_|D-O\d+/));
    const policyDownload = page.waitForEvent("download");
    await policyMessage.locator('[data-export="docx"]').click();
    await (await policyDownload).saveAs(path.join(output,"policy.docx"));
    assert(!fs.readFileSync(path.join(output,"policy.docx")).toString("utf8").includes("P-bth_policy_"));
    const width = await page.locator("#bthAssistantRoot").evaluate(el => el.getBoundingClientRect().width);
    assert(width <= 390, "assistant overflows mobile viewport");
    await page.locator("#bthAssistantRoot").screenshot({path:path.join(output,"mobile.png")});
    await page.locator("#bthChatQuestion").fill("以上政策说明了什么？"); await page.locator(".bth-chat-send").click();
    await page.waitForFunction(() => document.querySelectorAll('[data-export="docx"]').length === 3);
    assert(requests[2].history.some(m => m.role === "assistant" && m.content.includes(policySources[0].id)), "internal IDs must remain in follow-up context");
    assert.equal((await page.evaluate(() => window.referenceLeaks)).length, 0, "raw citation leaked during streaming");
    await page.locator("#bthTargetTrackerRoot table").waitFor();
    assert.equal(await page.locator("[data-target-id]").count(),19);
    await page.locator('[data-target-filter="region"]').selectOption("天津市");
    assert.equal(await page.locator("[data-target-id]").count(),3);
    await page.locator('[data-target-filter="year"]').selectOption("2025");
    assert.equal(await page.locator("[data-target-id]").count(),1);
    assert((await page.locator("[data-target-id]").innerText()).includes("实绩待核验"));
    await page.locator('[data-target-filter="region"]').selectOption("");
    await page.locator('[data-target-filter="year"]').selectOption("");
    await page.locator('[data-bth-policy-filter="instrument"]').selectOption("economic");
    assert.equal(await page.locator('.bth-chat-downloads [data-export="docx"]').count(),3,"policy filters must not remount an active conversation");
    assert(await page.locator(".bth-policy-instruments").count() > 0);
    const trackerWidth = await page.locator("#bthTargetTrackerRoot").evaluate(el => el.getBoundingClientRect().width);
    assert(trackerWidth <= 390);
    await page.locator("#bthTargetTrackerRoot").screenshot({path:path.join(output,"tracker-mobile.png")});
    await page.clock.install();
    let pendingRequest = page.waitForRequest("**/chat");
    await page.locator("#bthChatQuestion").fill("超时测试"); await page.locator(".bth-chat-send").click(); await pendingRequest;
    await page.clock.fastForward(121000);
    await page.waitForFunction(() => document.querySelector(".bth-chat-status").textContent.includes("连接超时"));
    assert(await page.locator(".bth-chat-send").isEnabled());
    assert.equal(await page.locator(".streaming").count(),0);
    pendingRequest = page.waitForRequest("**/chat");
    await page.locator("#bthChatQuestion").fill("停止测试"); await page.locator(".bth-chat-send").click(); await pendingRequest;
    await page.locator(".bth-chat-stop").click();
    await page.waitForFunction(() => document.querySelector(".bth-chat-status").textContent.includes("已停止"));
    assert(await page.locator(".bth-chat-send").isEnabled());
    await page.locator(".bth-chat-clear").click(); assert.equal(await page.locator(".bth-chat-message").count(),0);
    assert.equal(errors.length,0,errors.join("\n"));

    // Actual cross-origin HTTP, chunked UTF-8 and delayed inference (no route.fulfill).
    // This catches the mobile/proxy issue which an instant mock response missed.
    let wireMode = "stream", wireRequests = 0, preflights = 0;
    const wire = http.createServer((req,res) => {
      res.setHeader("Access-Control-Allow-Origin",base);
      res.setHeader("Access-Control-Allow-Methods","GET, POST, OPTIONS");
      res.setHeader("Access-Control-Allow-Headers","Content-Type");
      res.setHeader("Cache-Control","no-store, no-transform");
      if (req.method === "OPTIONS") {preflights++; res.writeHead(204).end(); return;}
      if (req.url === "/health") {res.writeHead(200,{"Content-Type":"application/json"}).end('{"ok":true,"ready":true}'); return;}
      if (req.url !== "/chat") {res.writeHead(404).end(); return;}
      let body = ""; req.on("data",chunk=>{body+=chunk;});
      req.on("end",()=>{
        assert.equal(JSON.parse(body).transport,"stream");
        assert.equal(req.headers["content-type"],"text/plain;charset=UTF-8"); wireRequests++;
        res.writeHead(200,{"Content-Type":"text/event-stream; charset=utf-8"});
        const frame = (name,value)=>`event: ${name}\ndata: ${JSON.stringify(value)}\n\n`;
        const raw = JSON.stringify(policyResult);
        if (wireMode === "buffered") {
          setTimeout(()=>res.end(frame("status",{phase:"analysis"}) + frame("result",policyResult).trimEnd()),800); return;
        }
        res.write(":"+" ".repeat(2048)+"\n\n"+frame("status",{phase:"connected"}));
        setTimeout(()=>{
          if (res.destroyed) return;
          res.write(frame("status",{phase:"analysis"})+frame("delta",{text:raw.slice(0,50)}));
          // Split a Chinese character's bytes across network writes.
          const last = Buffer.from(frame("delta",{text:raw.slice(50)})+frame("result",policyResult));
          const firstChinese = last.findIndex(byte=>byte>=0xe0 && byte<=0xef);
          res.write(last.subarray(0,firstChinese+1));
          setTimeout(()=>{if (!res.destroyed) res.write(last.subarray(firstChinese+1));},100);
          // The frontend must finish on result, not wait for connection closure.
          setTimeout(()=>res.end(),2500);
        },800);
      });
    });
    await new Promise(resolve=>wire.listen(0,"127.0.0.1",resolve));
    const mobileContext = await browser.newContext({...devices["Pixel 7"],acceptDownloads:true});
    const phone = await mobileContext.newPage(), phoneErrors = [];
    phone.on("pageerror",error=>phoneErrors.push(error.message));
    try {
      await phone.addInitScript(({endpoint})=>{
        window.turnstile={render:(el,o)=>{window.testVerification=o;o.callback('TEST');return 1;},reset:()=>window.testVerification.callback('TEST'),remove:()=>{}};
        const original=window.fetch;
        window.fetch=(url,options)=>{
          if (String(url).includes("/data/bth_assistant_config.json")) return Promise.resolve(new Response(JSON.stringify({endpoint,sitekey:"TEST-PUBLIC-SITE-KEY"}),{headers:{"Content-Type":"application/json"}}));
          if (/\/chat$/.test(String(url))) throw new Error("Mobile Fetch streams unavailable");
          return original(url,options);
        };
      },{endpoint:`http://127.0.0.1:${wire.address().port}`});
      await phone.goto(base); await phone.locator("#bthChatQuestion").waitFor({timeout:20000});
      await phone.waitForFunction(()=>!!window.testVerification);
      await phone.locator("#bthChatQuestion").fill("北京气候治理如何？");
      await phone.locator(".bth-chat-send").click();
      await phone.waitForFunction(()=>document.querySelector(".bth-chat-status").textContent.includes("验证请求"),{},{timeout:10000});
      await phone.locator('.bth-chat-downloads [data-export="docx"]').first().waitFor({timeout:10000});
      assert.equal(await phone.locator(".bth-chat-answer strong").count(),1);
      assert(await phone.locator(".bth-chat-send").isEnabled());
      assert.equal(await phone.locator(".streaming").count(),0);
      wireMode = "buffered";
      await phone.locator("#bthChatQuestion").fill("再解释天津与河北的差异。"); await phone.locator(".bth-chat-send").click();
      await phone.waitForFunction(()=>document.querySelectorAll('[data-export="docx"]').length===2);
      assert.equal(phoneErrors.length,0,phoneErrors.join("\n")); assert.equal(wireRequests,2); assert.equal(preflights,0,"mobile request must not rely on OPTIONS preflight");
      await phone.locator("#bthAssistantRoot").screenshot({path:path.join(output,"mobile-wire.png")});
    } finally {await mobileContext.close(); wire.closeAllConnections(); wire.close();}
    console.log(JSON.stringify({status:"passed",mocked_requests:requests.length,wire_requests:wireRequests,cors_preflights:preflights,mobile_width:width,docx:fs.statSync(path.join(output,"sample.docx")).size,pdf:fs.statSync(path.join(output,"sample.pdf")).size}));
  } finally {await browser.close(); server.close();}
})().catch(error => {console.error(error.message); server.close(); process.exitCode=1;});
