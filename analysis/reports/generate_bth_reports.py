"""Generate the BTH overview, policy-research DOCX and eight-page outlook PDF."""
from __future__ import annotations

import json
import re
import argparse
from collections import Counter
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARCHIVE = ROOT / "data" / "bth_policy_archive.json"
SUMMARY = HERE / "bth_evidence_summary.json"
FIG = HERE / "figures"
WINDOW_START = "2023-09-23"
BLUE = "22577A"
TEAL = "2A9D8F"
ORANGE = "E76F51"
GRAY = "52606D"


def load() -> tuple[list[dict], dict]:
    records = json.loads(ARCHIVE.read_text(encoding="utf-8"))["records"]
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    return records, summary


def find(records: list[dict], phrase: str, province: str | None = None) -> dict:
    matches = [r for r in records if phrase in r.get("title", "") and (not province or r.get("province") == province)]
    if not matches:
        raise KeyError(phrase)
    return sorted(matches, key=lambda r: (r.get("published_at", ""), len(r.get("title", ""))), reverse=True)[0]


def refs_for(records: list[dict], province: str) -> list[dict]:
    phrases = {
        "北京市": [
            "北京市碳达峰实施方案", "北京市固定资产投资项目节能审查和碳排放评价实施办法",
            "北京市促进制造业和信息软件业绿色低碳发展的若干措施", "北京市可再生能源开发利用条例",
            "北京市绿色建筑标识管理办法", "西城区促进绿色低碳高质量发展若干措施",
        ],
        "天津市": [
            "天津市碳达峰实施方案", "天津市工业领域碳达峰实施方案", "温室气体重点排放单位核查工作指南",
            "天津市固定资产投资项目节能审查和碳排放评价实施办法", "津南区可再生能源专项规划",
            "新能源建筑垃圾运输车辆",
        ],
        "河北省": [
            "河北省工业领域碳达峰实施方案", "河北省生态环境行政处罚裁量规则",
            "廊坊市环境空气质量达标规划", "京津冀美丽中国先行区建设行动方案",
        ],
    }[province]
    selected = []
    for phrase in phrases:
        try:
            selected.append(find(records, phrase, province if phrase != "京津冀美丽中国先行区建设行动方案" else None))
        except KeyError:
            continue
    return selected


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_doc_defaults(doc: Document) -> None:
    sec = doc.sections[0]
    sec.top_margin, sec.bottom_margin = Cm(2.4), Cm(2.2)
    sec.left_margin, sec.right_margin = Cm(2.6), Cm(2.4)
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(5)
    for name, size, color in (("Title", 22, BLUE), ("Heading 1", 16, BLUE), ("Heading 2", 13, TEAL), ("Heading 3", 11, GRAY)):
        style = styles[name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = True
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer.add_run("京津冀绿色转型政策数据库 · 2026")
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string("7B8794")


def add_title(doc: Document, title: str, subtitle: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.space_after = Pt(8)
    r = p.add_run(title)
    r.bold = True
    r.font.name = "Arial"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    r.font.size = Pt(22)
    r.font.color.rgb = RGBColor.from_string(BLUE)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(subtitle)
    r2.font.size = Pt(10.5)
    r2.font.color.rgb = RGBColor.from_string(GRAY)


def add_body(doc: Document, text: str, first_indent: bool = True) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if first_indent:
        p.paragraph_format.first_line_indent = Pt(21)
    p.add_run(text)


def add_references(doc: Document, refs: list[dict]) -> None:
    doc.add_paragraph("参考文件", style="Heading 2")
    for i, item in enumerate(refs, 1):
        p = doc.add_paragraph(style=None)
        p.paragraph_format.left_indent = Pt(12)
        p.paragraph_format.first_line_indent = Pt(-12)
        r = p.add_run(f"[{i}] {item['source']}. {item['title']}[{item['published_at']}]. ")
        r.font.size = Pt(9)
        link = p.add_run(item["url"])
        link.font.name = "Times New Roman"
        link.font.size = Pt(8.5)
        link.font.color.rgb = RGBColor.from_string(BLUE)


def build_overviews(records: list[dict], summary: dict) -> Path:
    doc = Document()
    set_doc_defaults(doc)
    add_title(doc, "京津冀绿色转型政策概述", "基于官方政策文本的地区观察（2023年9月—2026年9月）")
    note = doc.add_paragraph()
    note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rr = note.add_run(f"分析窗内收录 {summary['records']} 条；完整档案 {len(records)} 条（含仍构成现行框架的基线文件）")
    rr.font.size = Pt(9)
    rr.font.color.rgb = RGBColor.from_string(GRAY)

    sections = [
        ("一、北京：由目标管理转向项目全周期约束与技术扩散", "北京市",
         "北京的绿色转型政策已形成“总量目标—项目准入—技术供给—场景落地”的连续链条。市级碳达峰方案提供能源、建筑、交通和产业的总框架；固定资产投资项目节能审查与碳排放评价办法把能耗和碳排放约束前移到项目决策环节，可再生能源开发利用条例及建设项目全过程监督办法进一步把开发利用责任嵌入规划、建设、验收和运行阶段。产业端的政策重心并非简单扩大新能源制造规模，而是通过绿色工厂、绿色供应链、节能技术目录、废旧动力电池回收和制造业绿色低碳支持措施，推动技术改造、资源循环与信息披露相衔接。空间上，西城以绿色低碳项目支持和公共机构示范为抓手，通州强调城市副中心工业与软件信息服务业转型，经开区突出先进制造业和园区场景，密云、丰台、东城等区则以区级碳达峰方案细化建筑、交通和生态治理任务。政策库中北京市级文件占比较高，区级文本已覆盖海淀、西城、丰台、密云、石景山、门头沟、东城、通州等区域；这说明政策工具正在向项目和基层治理单元下沉，但不同区公开目录的可检索程度不一，不能据收录量判断政策执行强弱。下一阶段，北京的关键不在于继续叠加原则性目标，而在于统一项目碳评价口径、将节能审查结果与绿色融资和政府采购衔接，并公开可比的年度实施数据，使技术示范能够转化为可核验的减排绩效。"),
        ("二、天津：以工业、港口和区级实施方案构成转型主轴", "天津市",
         "天津的政策组合体现出典型港口工业城市的转型逻辑：一方面以市级碳达峰方案和工业领域碳达峰方案确定能源结构、工业能效与循环利用方向，另一方面通过固定资产投资项目节能审查和碳排放评价、温室气体重点排放单位核查指南等文件强化项目与企业层面的计量、核查和责任边界。能源端同时出现海上及陆上新能源项目、盐光互补、公共机构光伏、氢能与新能源汽车等政策信号；交通和城市治理端则将新能源车辆推广、港产城融合、厨余垃圾管理、非道路移动机械排放监管等纳入同一转型体系。区级政策的颗粒度是天津样本的突出特征：津南区形成可再生能源专项规划，静海、蓟州、宁河、宝坻、武清、东丽、北辰、红桥、南开、河东、河西、和平和河北区均可检索到碳达峰方案或年度生态环境行动，显示市级目标已经进入分区实施阶段。与此同时，政策文本之间仍存在指标口径、项目清单和年度进度公开程度不一致的问题；部分文件强调污染治理或单项工程，尚需明确其与碳目标之间的量化关系。建议以重点排放单位核查数据为基础，形成工业、港口、交通和建筑四类场景的年度进度表，并把区级方案中的目标、责任部门、项目和资金安排映射到同一数据框架，从而提高政策协同和实施可追踪性。"),
        ("三、河北：产业减碳、城市空气质量与区域协同需同步推进", "河北省",
         "河北的绿色转型具有更强的实体产业约束，钢铁、建材、化工、装备制造和能源系统既是减排重点，也是就业、投资和产业链安全的重要基础。河北省工业领域碳达峰实施方案将产业结构优化、节能降碳改造、绿色制造体系和资源综合利用置于核心位置；生态环境行政处罚裁量规则中的碳排放条款及地市监督执法清单，反映出碳排放责任正在与常态化环境监管接轨。城市层面，廊坊空气质量达标规划、石家庄生态环境治理文件、雄安新区生态环境制度以及张家口可再生能源示范基础，共同构成河北参与区域转型的不同路径。区域尺度上，《京津冀美丽中国先行区建设行动方案》要求三地在大气污染联防联控、生态保护修复、绿色交通和产业协作等方面形成跨行政区行动，这意味着河北不能仅以单个行业或城市的项目改造衡量转型，而需同时处理北京非首都功能疏解承接、清洁能源供给、重化工业改造和生态屏障建设之间的关系。当前政策库对河北的官方公开页面覆盖明显弱于京津，现有文本可用于识别政策主线和重点城市，但不足以据此比较各市执行绩效。后续应优先补齐唐山、邯郸、沧州、保定、张家口等重点城市的原始政策与年度实施文件，并建设行业—企业—项目三级台账；在政策设计上，应以单位产品碳排放、清洁能源消纳、绿色运输比例和重点工程进度等可核验指标，支撑产业升级与区域减排责任的协同评估。"),
    ]
    for heading, province, text in sections:
        doc.add_paragraph(heading, style="Heading 1")
        add_body(doc, text)
        add_references(doc, refs_for(records, province))
    out = HERE / "京津冀绿色转型三地概述.docx"
    doc.save(out)
    return out


def add_metric_table(doc: Document, summary: dict) -> None:
    table = doc.add_table(rows=2, cols=5)
    table.style = "Table Grid"
    headers = ["三年政策文本", "官方来源", "官方域名", "覆盖地区", "唯一原文链接"]
    values = [summary["records"], summary["sources"], summary["official_domains"], summary["regions"], summary["unique_urls"]]
    for j, value in enumerate(headers):
        table.cell(0, j).text = value
        set_cell_shading(table.cell(0, j), BLUE)
        for run in table.cell(0, j).paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.bold = True
    for j, value in enumerate(values):
        table.cell(1, j).text = str(value)
        table.cell(1, j).vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        table.cell(1, j).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER


def build_policy_report(records: list[dict], summary: dict) -> Path:
    doc = Document()
    set_doc_defaults(doc)
    add_title(doc, "从政策并列走向任务协同", "京津冀绿色转型政策研究报告")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("核心判断：三地政策工具已具备体系化基础，但跨区域指标、项目台账和实施评价仍需统一")
    r.bold = True
    r.font.color.rgb = RGBColor.from_string(ORANGE)
    add_metric_table(doc, summary)

    doc.add_paragraph("摘要", style="Heading 1")
    add_body(doc, "京津冀绿色转型已从共同目标倡议进入项目约束、产业改造和城市治理并行推进阶段。三年政策文本显示，北京侧重项目全周期碳约束、服务业与城市治理场景，天津突出工业、港口、交通及区级碳达峰实施，河北则承担重化工业改造、清洁能源供给和生态屏障建设任务。主要问题不是政策数量不足，而是三地指标口径、项目清单和年度绩效缺少可比映射，城市和区县公开信息的结构化程度也不一致。建议建立跨区域政策—任务—指标—项目台账，围绕能源、工业、建筑、交通与生态治理形成共同指标集，优先对跨界大气、绿色电力、绿色运输和重点产业链开展年度联合评估，并以公开证据分级制度提高政策追踪的可核验性。", False)

    doc.add_paragraph("一、问题：政策体系已经形成，协同执行仍存在三处断点", style="Heading 1")
    doc.add_paragraph("（一）目标可以对应，指标尚难比较", style="Heading 2")
    add_body(doc, "三地均已形成碳达峰、节能、工业绿色化和生态环境治理政策，但同类任务在统计边界、时间尺度和公开频率上存在差异。北京的项目节能审查与碳评价、天津的重点排放单位核查、河北的工业领域碳达峰安排分别提供了不同环节的制度入口；若缺少统一的指标字典，区域协同只能停留在目标并列，难以判断一项跨区域工程由谁负责、何时完成、减排如何归属。")
    doc.add_paragraph("（二）政策文件与项目实施之间缺少稳定的数据链", style="Heading 2")
    add_body(doc, "政策库可识别方案、办法、规划、通知、目录和清单等多类工具，但多数公开页面仍以单份文件为组织单位。项目审批、资金支持、技术目录、重点排放单位、年度进度和绩效评价往往分散在不同部门，难以自动形成同一项目的时间序列。对于新能源消纳、港口运输、钢铁改造和绿色建筑等跨部门议题，这一断点直接抬高了评估成本。")
    doc.add_paragraph("（三）城市层级证据覆盖不均，易造成判断偏差", style="Heading 2")
    add_body(doc, f"分析窗内政策库覆盖 {summary['regions']} 个地区，但市级文件和部分目录结构清晰的区县占比较高。河北及部分区县的公开检索入口、历史分页和附件格式较为分散。收录量因此只能说明当前证据可得性和政策发布活动，不能替代转型绩效。任何地区排名都应同时校正来源覆盖、人口产业规模和政策类型。")
    doc.add_picture(str(FIG / "figure_01_quarterly.png"), width=Inches(6.25))
    cap = doc.add_paragraph("图1  三地政策文本的季度收录量。资料来源：京津冀绿色转型政策数据库。")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True
    cap.runs[0].font.size = Pt(8.5)

    doc.add_paragraph("二、原因与判断：三种转型角色决定了工具差异", style="Heading 1")
    doc.add_paragraph("（一）北京：需求侧治理与技术扩散中心", style="Heading 2")
    add_body(doc, "北京高端服务业和城市运行场景占比较高，政策工具自然更多落在固定资产投资约束、公共机构、建筑交通、绿色金融和技术示范。其区域价值在于形成可复制的碳评价、绿色采购和技术应用规则，并通过市场需求带动周边制造与能源供给转型。")
    doc.add_paragraph("（二）天津：港口工业与区级实施枢纽", style="Heading 2")
    add_body(doc, "天津同时具有工业基地、港口物流和超大城市治理属性。政策结构显示，工业碳达峰、重点排放单位核查、港产城融合、新能源交通和区级实施方案相互叠加。其协同价值在于把港口、航运、制造业与城市能源系统连接起来，形成可测量的绿色物流和产业链减排场景。")
    doc.add_paragraph("（三）河北：供给侧深度改造与生态安全支撑", style="Heading 2")
    add_body(doc, "河北承担钢铁、建材、能源等高碳产业改造任务，也提供可再生能源、生态空间和产业承接能力。政策重点需要同时服务减排、就业和产业链韧性，因而不能照搬北京的城市治理指标。衡量河北进展应更多采用单位产品碳排放、绿色能源消纳、清洁运输和重点工程实际进度。")
    doc.add_picture(str(FIG / "figure_02_topic_heatmap.png"), width=Inches(5.6))
    cap = doc.add_paragraph("图2  三地政策议题组合（各地内部占比）。一项政策可对应多个议题。")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True
    cap.runs[0].font.size = Pt(8.5)

    doc.add_paragraph("三、政策建议：以共同台账推动可核验协同", style="Heading 1")
    recs = [
        ("建立跨区域共同指标集", "由三地发展改革、生态环境、工业和信息化、住房城乡建设、交通等部门共同确定能源、工业、建筑、交通和生态治理五类核心指标，明确口径、基期、更新频率和责任部门。共同指标不求数量多，优先保证可比、可追溯和可年度更新。"),
        ("建设政策—任务—项目四级台账", "把政策文件拆解为任务、指标和项目，使用统一行政区划代码、部门代码、政策文号、项目主体和时间字段连接不同来源。对跨区域事项增设责任分工、资金来源、预期结果和核验状态，保留原文链接与版本信息。"),
        ("形成四类跨区域联合评估", "优先选择跨界大气污染与减污降碳、绿电生产和消纳、港口及干线绿色运输、钢铁与汽车产业链四类场景。每年发布一次证据表，分别报告目标、投入、项目进度、实际结果和不确定性，避免用单一综合分数掩盖结构差异。"),
        ("把政策公开质量纳入治理能力建设", "统一历史文件分页、附件命名、发布日期和失效状态；对计划、项目、名单和评价结果提供机器可读下载。数据库对标题相关性、正文证据、官方域名和重复链接设置质量门槛，并保留无法核验记录的排除理由。"),
        ("建立滚动复盘机制", "季度更新政策与项目台账，年度开展政策组合复盘；当技术成本、能源价格或产业政策发生变化时，及时调整项目优先级。复盘应区分政策发布、实施投入、过程产出和减排结果四个层次，不以文件数量代替执行成效。"),
    ]
    for i, (title, text) in enumerate(recs, 1):
        doc.add_paragraph(f"（{i}）{title}", style="Heading 2")
        add_body(doc, text)

    doc.add_paragraph("四、实施安排", style="Heading 1")
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for j, h in enumerate(("阶段", "重点任务", "交付物", "核验方式")):
        table.cell(0, j).text = h
        set_cell_shading(table.cell(0, j), BLUE)
        for run in table.cell(0, j).paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255); run.bold = True
    set_repeat_table_header(table.rows[0])
    rows = [
        ("0—6个月", "统一指标与元数据", "指标字典、来源登记册", "三地部门会签；抽样复核"),
        ("6—18个月", "连接政策、项目与年度数据", "四类场景台账", "原文、项目和统计数据三方校验"),
        ("18—36个月", "开展联合评估与政策复盘", "年度进展报告、政策调整清单", "公开证据表；第三方复核"),
    ]
    for values in rows:
        cells = table.add_row().cells
        for j, value in enumerate(values): cells[j].text = value

    doc.add_paragraph("研究边界", style="Heading 1")
    add_body(doc, "本报告以公开政策文件为主要证据。政策发布日期、来源和议题标签经过结构化处理；政策数量受网站公开方式、历史页面可访问性和收录规则影响。报告不使用文本数量推断实际减排量，也不对三地转型绩效作总分排名。涉及政策效果的判断需在项目、能源、排放和财政等结果数据接入后另行检验。")
    all_refs = []
    seen = set()
    for province in ("北京市", "天津市", "河北省"):
        for item in refs_for(records, province):
            if item["url"] not in seen:
                seen.add(item["url"]); all_refs.append(item)
    add_references(doc, all_refs)
    out = HERE / "京津冀绿色转型政策研究报告.docx"
    doc.save(out)
    return out


def wrap_cn(text: str, size: float, width: float) -> list[str]:
    per_line = max(8, int(width / (size * 0.95)))
    lines = []
    for paragraph in text.split("\n"):
        while len(paragraph) > per_line:
            cut = per_line
            for mark in "，；。！？、":
                pos = paragraph.rfind(mark, int(per_line * .65), per_line + 1)
                if pos > 0:
                    cut = pos + 1; break
            lines.append(paragraph[:cut]); paragraph = paragraph[cut:]
        if paragraph: lines.append(paragraph)
    return lines


class OutlookPDF:
    def __init__(self, path: Path):
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        pdfmetrics.registerFont(TTFont("Hei", r"C:\Windows\Fonts\simhei.ttf"))
        self.c = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
        self.w, self.h = A4
        self.page = 0

    def header(self, section: str) -> None:
        self.page += 1
        self.c.setFillColor(HexColor("#F5F8FA")); self.c.rect(0, self.h - 34, self.w, 34, fill=1, stroke=0)
        self.c.setFillColor(HexColor("#22577A")); self.c.setFont("Hei", 9)
        self.c.drawString(36, self.h - 22, "京津冀绿色转型展望")
        self.c.setFillColor(HexColor("#52606D")); self.c.setFont("STSong-Light", 8)
        self.c.drawRightString(self.w - 36, self.h - 22, section)
        self.c.setStrokeColor(HexColor("#D9E2EC")); self.c.line(36, 30, self.w - 36, 30)
        self.c.setFillColor(HexColor("#7B8794")); self.c.drawRightString(self.w - 36, 18, str(self.page))

    def title(self, text: str, y: float, size: float = 22, color: str = BLUE) -> float:
        self.c.setFillColor(HexColor("#" + color)); self.c.setFont("Hei", size)
        self.c.drawString(42, y, text)
        return y - size - 12

    def text(self, text: str, x: float, y: float, width: float, size: float = 10, leading: float = 16, color: str = "263238", bullet: str = "") -> float:
        self.c.setFillColor(HexColor("#" + color)); self.c.setFont("STSong-Light", size)
        lines = wrap_cn(text, size, width - (12 if bullet else 0))
        for idx, line in enumerate(lines):
            if bullet and idx == 0:
                self.c.setFillColor(HexColor("#" + TEAL)); self.c.circle(x + 3, y + 3, 2.2, fill=1, stroke=0)
                self.c.setFillColor(HexColor("#" + color)); self.c.drawString(x + 13, y, line)
            else:
                self.c.drawString(x + (13 if bullet else 0), y, line)
            y -= leading
        return y

    def metric(self, x: float, y: float, value: str, label: str, color: str) -> None:
        self.c.setFillColor(HexColor("#F7FAFC")); self.c.roundRect(x, y, 118, 66, 7, fill=1, stroke=0)
        self.c.setFillColor(HexColor("#" + color)); self.c.setFont("Hei", 22); self.c.drawString(x + 12, y + 33, value)
        self.c.setFillColor(HexColor("#52606D")); self.c.setFont("STSong-Light", 8.5); self.c.drawString(x + 12, y + 14, label)

    def image(self, path: Path, x: float, y: float, width: float, height: float) -> None:
        self.c.drawImage(ImageReader(str(path)), x, y, width=width, height=height, preserveAspectRatio=True, anchor="c", mask="auto")

    def finish_page(self): self.c.showPage()
    def save(self): self.c.save()


def build_outlook_pdf(records: list[dict], summary: dict) -> Path:
    out = HERE / "京津冀绿色转型展望报告.pdf"
    p = OutlookPDF(out)
    # 1 Cover
    p.header("2026—2030")
    y = p.title("京津冀绿色转型展望", 690, 28)
    y = p.text("从政策并列走向任务、项目与结果协同", 44, y, 500, 15, 23, ORANGE)
    p.metric(44, 500, str(summary["records"]), "三年政策文本", BLUE)
    p.metric(174, 500, str(summary["sources"]), "公开来源", TEAL)
    p.metric(304, 500, str(summary["official_domains"]), "官方域名", ORANGE)
    p.metric(434, 500, str(summary["regions"]), "覆盖地区", "6B7280")
    y = 445
    y = p.text("核心判断", 44, y, 500, 12, 19, BLUE)
    y = p.text("三地绿色转型已形成互补的政策角色：北京侧重需求侧规则与技术扩散，天津连接港口工业与区级实施，河北承担产业深度改造、清洁能源供给与生态安全支撑。下一阶段的约束不是政策数量，而是跨区域指标、项目台账和结果核验尚未形成共同语言。", 44, y - 4, 500, 11, 19)
    p.text("证据范围：2023年9月至2026年9月；另保留仍构成现行政策框架的历史基线文件。", 44, 90, 500, 8.5, 13, GRAY)
    p.finish_page()
    # 2 Evidence
    p.header("01 证据基础")
    y = p.title("证据覆盖广，但不能用数量代替绩效", 750, 19)
    p.image(FIG / "figure_04_coverage.png", 45, 285, 505, 400)
    y = 265
    for t in ("三年分析窗内共有437条唯一原文链接；完整档案502条，含现行框架基线文件。",
              "北京、天津公开目录和区级文件更易检索；河北仍需补齐重点工业城市和省级部门历史目录。",
              "后续评价必须区分政策发布、实施投入、过程产出和实际减排结果四个层次。"):
        y = p.text(t, 50, y, 490, 10, 17, bullet="•") - 5
    p.finish_page()
    # 3 Tempo
    p.header("02 政策节奏")
    y = p.title("政策更新持续推进，季度波动受目录可得性影响", 750, 18)
    p.image(FIG / "figure_01_quarterly.png", 40, 300, 520, 370)
    y = 270
    y = p.text("北京在2025年第四季度和2026年第三季度出现较高收录量，主要与市级项目、节能、绿色制造和区级文件集中发布有关；天津季度分布相对平稳；河北曲线更明显地受当前来源覆盖影响。", 48, y, 495, 10, 17)
    y = p.text("研判：政策热度可用于发现制度更新窗口，但不能独立说明执行力度。年度复盘应同步接入项目、投资、能源与排放数据。", 48, y - 12, 495, 10, 17, ORANGE)
    p.finish_page()
    # 4 Portfolio
    p.header("03 政策组合")
    y = p.title("共同议题下存在不同的工具重心", 750, 19)
    p.image(FIG / "figure_02_topic_heatmap.png", 85, 245, 430, 440)
    y = 220
    for t in ("北京：项目碳约束、建筑交通、技术目录与绿色制造政策连接较紧。",
              "天津：工业、港口、交通、重点排放单位核查和区级碳达峰方案并行。",
              "河北：现有证据突出工业与生态环境治理，但样本覆盖不足，结论需谨慎。"):
        y = p.text(t, 50, y, 490, 9.7, 16, bullet="•") - 3
    p.finish_page()
    # 5 Beijing
    p.header("04 北京")
    y = p.title("北京：把规则优势转化为可核验的场景减排", 750, 18)
    y = p.text("政策路径", 48, y, 490, 12, 18, BLUE)
    boxes = [("项目入口", "节能审查与碳排放评价"), ("技术扩散", "节能目录、绿色制造与采购"), ("城市场景", "建筑、交通、公共机构"), ("循环闭环", "动力电池和废弃物回收")]
    x = 48
    for title, body in boxes:
        p.c.setFillColor(HexColor("#EFF6F8")); p.c.roundRect(x, 530, 116, 78, 7, fill=1, stroke=0)
        p.c.setFillColor(HexColor("#22577A")); p.c.setFont("Hei", 10); p.c.drawString(x + 10, 582, title)
        p.text(body, x + 10, 558, 96, 8.5, 13)
        x += 125
    y = 490
    y = p.text("2027—2030优先事项", 48, y, 490, 12, 18, BLUE)
    for t in ("形成固定资产投资项目碳评价的公开口径与年度实施数据。", "把绿色采购、政府投资和绿色融资与项目碳绩效连接。", "以副中心、经开区和公共机构为重点，验证技术目录的实际节能减排效果。"):
        y = p.text(t, 50, y - 5, 485, 10, 17, bullet="•")
    y = p.text("主要风险：示范项目数量增长快于绩效核验能力；不同区县数据口径不一致。", 48, 220, 495, 10, 17, ORANGE)
    p.text("观察指标：项目碳评价覆盖率、节能改造实际节能量、绿色建筑运行绩效、公共领域新能源交通比例。", 48, 160, 495, 9.5, 16)
    p.finish_page()
    # 6 Tianjin
    p.header("05 天津")
    y = p.title("天津：以港口工业场景连接能源与产业转型", 750, 18)
    y = p.text("政策路径", 48, y, 490, 12, 18, TEAL)
    p.image(FIG / "figure_03_instruments.png", 45, 330, 505, 310)
    y = 300
    for t in ("以重点排放单位核查和项目节能审查形成企业与项目的共同数据底座。",
              "把港口、航运、干线运输和新能源汽车政策整合为绿色物流走廊。",
              "将各区碳达峰方案转化为年度项目清单和资金安排，避免目标与执行脱节。"):
        y = p.text(t, 50, y, 490, 10, 17, bullet="•") - 4
    p.text("观察指标：港口岸电和清洁运输比例、重点排放单位核查覆盖率、工业单位增加值能耗、区级项目完成率。", 48, 120, 495, 9.5, 16)
    p.finish_page()
    # 7 Hebei / coordination
    p.header("06 河北与区域协同")
    y = p.title("河北：产业深度改造必须与区域收益分配同步", 750, 18)
    y = p.text("河北承接的重化工业改造和清洁能源供给具有高投入、长周期特征。若三地只共享减排目标而不共享成本、基础设施和市场收益，产业链协同难以稳定。", 48, y, 495, 10.5, 18)
    p.c.setStrokeColor(HexColor("#D9E2EC")); p.c.setLineWidth(1.2)
    xs = [78, 224, 370, 496]
    nodes = [("河北供给侧", "工业改造\n清洁能源"), ("区域网络", "电网\n绿色运输"), ("京津需求侧", "市场规则\n技术应用"), ("共同结果", "减排\n韧性")]
    for i, (head, body) in enumerate(nodes):
        x = xs[i]
        p.c.setFillColor(HexColor("#F4F7F8")); p.c.circle(x, 500, 48, fill=1, stroke=1)
        p.c.setFillColor(HexColor("#22577A")); p.c.setFont("Hei", 9); p.c.drawCentredString(x, 508, head)
        p.c.setFillColor(HexColor("#52606D")); p.c.setFont("STSong-Light", 8); 
        for j, line in enumerate(body.split("\n")): p.c.drawCentredString(x, 489 - j*12, line)
        if i < len(nodes)-1:
            p.c.setStrokeColor(HexColor("#2A9D8F")); p.c.line(x+50, 500, xs[i+1]-50, 500)
    y = 410
    for t in ("共同建设钢铁、汽车、电力和物流四类产业链台账，明确减排责任与收益归属。",
              "将绿电消纳、跨界大气治理和生态补偿纳入年度联合评估。",
              "优先补齐唐山、邯郸、沧州、保定和张家口的官方政策与项目证据。"):
        y = p.text(t, 50, y, 490, 10, 17, bullet="•") - 6
    p.text("观察指标：单位产品碳排放、绿电跨区交易量、铁路和新能源货运比例、重点项目按期完成率。", 48, 165, 495, 9.5, 16)
    p.finish_page()
    # 8 Outlook
    p.header("07 2027—2030展望")
    y = p.title("以共同台账替代综合打分，以年度证据支持政策调整", 750, 18)
    stages = [
        ("2027", "统一口径", "发布共同指标字典；完成来源、政策、任务和项目映射。"),
        ("2028", "连接数据", "接入能源、排放、投资和交通结果数据；形成四类场景台账。"),
        ("2029", "联合评价", "开展跨界大气、绿电、绿色运输和产业链年度评估。"),
        ("2030", "政策复盘", "基于结果证据调整政策工具、资金投向和区域责任。"),
    ]
    y = 640
    for year, head, body in stages:
        p.c.setFillColor(HexColor("#22577A")); p.c.circle(75, y+5, 22, fill=1, stroke=0)
        p.c.setFillColor(white); p.c.setFont("Times-Roman", 9); p.c.drawCentredString(75, y+2, year)
        p.c.setFillColor(HexColor("#2A9D8F")); p.c.setFont("Hei", 11); p.c.drawString(115, y+10, head)
        p.text(body, 115, y-10, 400, 9.5, 15)
        if year != "2030": p.c.setStrokeColor(HexColor("#B8C7D1")); p.c.line(75, y-18, 75, y-92)
        y -= 115
    p.c.setFillColor(HexColor("#F7FAFC")); p.c.roundRect(42, 88, 510, 105, 7, fill=1, stroke=0)
    p.text("方法与边界", 55, 170, 480, 10, 15, BLUE)
    p.text("本报告以官方政策原文为证据，标签用于描述政策议题与工具，不推断实际减排量。数量差异受公开目录结构影响；展望属于基于现有制度信号的情景判断，不是确定性预测。图表及统计可由随附脚本复现。", 55, 148, 480, 8.5, 13, GRAY)
    p.finish_page()
    p.save()
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=("docx", "pdf", "all"), default="all")
    args = parser.parse_args()
    records, summary = load()
    outputs = []
    if args.only in {"docx", "all"}:
        outputs.extend([build_overviews(records, summary), build_policy_report(records, summary)])
    if args.only in {"pdf", "all"}:
        outputs.append(build_outlook_pdf(records, summary))
    print(json.dumps({"outputs": [str(p) for p in outputs]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
