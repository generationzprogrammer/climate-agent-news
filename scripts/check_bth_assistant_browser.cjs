// Isolated local browser QA; mocks external services, never calls a paid model.
const fs = require("node:fs"), path = require("node:path"), http = require("node:http"), assert = require("node:assert/strict");
const {chromium} = require("playwright");
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
  let requests = [];
  await page.route("**/data/bth_assistant_config.json", route => route.fulfill({json: {endpoint: base, sitekey:"TEST-PUBLIC-SITE-KEY"}}));
  await page.route("https://challenges.cloudflare.com/**", route => route.fulfill({contentType:"application/javascript", body:"window.turnstile={render:(el,o)=>{window.testVerification=o; o.callback('TEST-TOKEN'); return 1;},reset:()=>window.testVerification.callback('TEST-TOKEN'),remove:()=>{}};"}));
  await page.route("**/chat", async route => {
    requests.push(route.request().postDataJSON());
    const raw = JSON.stringify(result), frame = (event, value) => `event: ${event}\ndata: ${JSON.stringify(value)}\n\n`;
    await route.fulfill({contentType:"text/event-stream", body:frame("status",{evidence_count:3}) + frame("delta",{text:raw.slice(0,90)}) + frame("delta",{text:raw.slice(90)}) + frame("result",result)});
  });
  try {
    await page.goto(base); await page.locator("#bthChatQuestion").waitFor({timeout:20000});
    await page.locator("#bthChatQuestion").fill("比较三地光伏装机，生成图表和报告");
    await page.waitForFunction(() => !!window.testVerification);
    await page.locator(".bth-chat-send").click(); await page.locator('.bth-chat-downloads [data-export="docx"]').first().waitFor();
    for (const format of ["docx","pdf","png"]) {
      const pending = page.waitForEvent("download"); await page.locator(`[data-export="${format}"]`).first().click();
      const file = await pending; await file.saveAs(path.join(output, `sample.${format}`));
    }
    await page.locator("#bthAssistantRoot").screenshot({path:path.join(output,"desktop.png")});
    await page.setViewportSize({width:390,height:844});
    await page.locator("#bthChatQuestion").fill("继续解释差异"); await page.locator(".bth-chat-send").click();
    await page.waitForFunction(() => document.querySelectorAll('[data-export="docx"]').length === 2);
    assert(requests[1].history.length >= 2, "multi-turn history missing");
    const width = await page.locator("#bthAssistantRoot").evaluate(el => el.getBoundingClientRect().width);
    assert(width <= 390, "assistant overflows mobile viewport");
    await page.locator("#bthAssistantRoot").screenshot({path:path.join(output,"mobile.png")});
    await page.locator(".bth-chat-clear").click(); assert.equal(await page.locator(".bth-chat-message").count(),0);
    assert.equal(errors.length,0,errors.join("\n"));
    console.log(JSON.stringify({status:"passed",mocked_requests:requests.length,mobile_width:width,docx:fs.statSync(path.join(output,"sample.docx")).size,pdf:fs.statSync(path.join(output,"sample.pdf")).size}));
  } finally {await browser.close(); server.close();}
})().catch(error => {console.error(error.message); server.close(); process.exitCode=1;});
