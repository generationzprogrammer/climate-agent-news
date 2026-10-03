import {test} from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const context = vm.createContext({window: {}, TextEncoder, URL, Blob});
vm.runInContext(readFileSync(new URL("../static/bth-report.js", import.meta.url), "utf8"), context);
const report = context.window.GruenBthReport;
const sources = [
  {id: "P-bth_policy_a22de733ef704b96", kind: "policy", title: "2025年美丽北京行动计划", source: "北京市人民政府", region: "北京市", date: "2025-04-01", url: "https://example.gov.cn/policy?a=1&b=2"},
  {id: "P-bth_policy_b50ba718aae60ed3", kind: "policy", title: "东城区行动计划", source: "东城区人民政府", region: "东城区", date: "2025-04-02", url: "https://example.gov.cn/dongcheng"},
  {id: "D-O1234", kind: "observation", title: "光伏装机", source: "统计局", region: "北京市", year: 2025, value: 210.2, unit: "万千瓦", url: "https://example.gov.cn/stat"},
];
const id1 = sources[0].id, id2 = sources[1].id;

test("free-form policy prose uses short references without changing facts", () => {
  const answer = `北京2025年发布市级行动计划[${id1}]，东城区出台区级行动计划[${id2}][${id1}]。`;
  assert.equal(report.citationText(answer, sources), "北京2025年发布市级行动计划[1]，东城区出台区级行动计划[2][1]。");
  assert(answer.includes(id1), "the raw response must remain available for follow-up evidence");
});

test("inline citations link to their matching source and escape HTML", () => {
  const html = report.citationText(`<img onerror=alert(1)>[${id1}]`, sources, {html: true});
  assert(html.includes("&lt;img")); assert(!html.includes("<img"));
  assert(html.includes('href="https://example.gov.cn/policy?a=1&amp;b=2"'));
  assert(html.includes(">[1]</a>")); assert(!html.includes(id1));
});

test("unknown IDs never create invented references", () => {
  assert.equal(report.citationText("结论[D-fabricated][引用无效]", sources), "结论（来源待核验）（来源待核验）");
  assert(!report.citationText("结论[D-fabricated]", sources, {html: true}).includes("<a"));
});

test("bold text is safe HTML and plain downloads have no Markdown markers", () => {
  const answer = `**政策作用**需要分析[${id1}]，**<img onerror=alert(1)>**；残留**标记`;
  const html = report.citationText(answer, sources, {html:true});
  assert(html.includes("<strong>政策作用</strong>"));
  assert(html.includes("<strong>&lt;img"));
  assert(!html.includes("<img")); assert(!html.includes("**"));
  assert(!report.citationText(answer,sources).includes("**"));
  assert(!report.citationText("**政策作用**",[],{streaming:true}).includes("**"));
  const special = [{...sources[0], url:"https://example.gov.cn/**/file"}];
  assert(report.citationText(`[${id1}]`, special,{html:true}).includes('href="https://example.gov.cn/**/file"'));
});

test("grouped, full-width and bare evidence citations are normalized", () => {
  assert.equal(report.citationText(`甲【${id1}、${id2}】乙［D-O1234］丙${id1}`, sources), "甲[1][2]乙[3]丙[1]");
  assert.equal(report.citationText(`[${id1}, ${id1}]`, sources), "[1]");
  assert.equal(report.citationText("[一般分析]、P-MAX技术", sources), "[一般分析]、P-MAX技术");
});

test("streamed complete and fragmented IDs never flash on screen", () => {
  for (const fragment of ["[P", "[P-", "[P-bth_policy_abc", "［D-O123", `[${id1}]`, "D-O1234"]) {
    assert.equal(report.citationText("北京气候治理" + fragment, [], {streaming: true}), "北京气候治理");
  }
  assert.equal(report.citationText(`北京[${id1}]持续推进绿色转型`, [], {streaming: true}), "北京持续推进绿色转型");
});

test("unsafe source URLs remain non-clickable and cannot inject markup", () => {
  const unsafe = [{...sources[0], url: "javascript:alert(1)", title: '\"><script>alert(1)</script>'}];
  assert.equal(report.citationText(`[${id1}]`, unsafe, {html: true}), "[1]");
  assert.equal(report.sourceUrl("https://user:secret@example.org/"), "");
});

test("report paragraphs and bibliography share the same numbering", () => {
  const result = {answer: `北京[${id1}]`, sources, charts: [], generated_at: "2026-10-02", report: {title: "北京气候治理", sections: [{heading: "市区联动", paragraphs: [`东城区[${id2}]与市级部署[${id1}]衔接。`]}]}};
  const parts = report.reportParts(result).parts.map(p => p.text).join("\n");
  assert(parts.includes("东城区[2]与市级部署[1]衔接。"));
  assert(parts.includes("[1] 2025年美丽北京行动计划")); assert(parts.includes("[2] 东城区行动计划"));
  assert(!parts.includes("P-bth_policy_")); assert(!parts.includes("D-O1234"));
});

test("chart titles and notes never show machine evidence IDs", () => {
  const svg = report.chartSvg({title: "光伏[D-O1234]", unit: "万千瓦", points: [{id: "D-O1234", label: "北京2025", value: 210.2}]}, sources);
  assert(svg.includes("光伏[3]")); assert(svg.includes("来源：[3]")); assert(!svg.includes("D-O1234"));
});

test("downloaded Word uses readable references, including answer-only exports", async () => {
  const result = {answer: `北京行动计划[${id1}]。`, sources, charts: []};
  const blob = await report.docx(result);
  const content = new TextDecoder().decode(await blob.arrayBuffer());
  assert(content.includes("北京行动计划[1]。")); assert(content.includes("[1] 2025年美丽北京行动计划"));
  assert(!content.includes("P-bth_policy_")); assert(!content.includes("D-O1234"));
});
