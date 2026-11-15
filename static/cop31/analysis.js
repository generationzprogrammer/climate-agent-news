/* COP31 · 科研分析 (2026-11-05, user: 科研分析功能，优先开发四类图表) — the four research charts at the top of 数据统计.
   Reads downloads/analytics.json (deploy/newsdb writes it from the research set of the governance history, research_eligible
   = 1), by its 14 topic categories (2026-11-06 history: 14 categories / 83 subcategories): 1 categories by year (exclusive
   primary category, 100 % stacked, or article counts; each year's articles and active publishers under the axis, so
   collection growth is not read as topic growth; drawn from `trend_from`, the sparse early years are only counted in the
   note), 2 the country / organisation co-occurrence network (a force layout of the 45 most frequent entities; co-mention,
   not diplomatic cooperation), 3 the 14 × 14 category co-occurrence matrix (Jaccard or counts; co-occurrence is not
   causation), 4 the policy timeline (dated official-source records) with search and a category filter. Plain SVG, no
   library; text follows <html lang>. Hidden without the data.
   2026-11-09 (user: 增加数据可视化图表，要好看，且有价值): topic clusters by year (a draggable year), the taxonomy as a two-ring
   chart (click a category to open it), the subcategories gaining and losing share, countries × categories (click a
   column to sort), months against the COP calendar, and categories → policy tools → policy stages; the network morphs
   between a force and a ring layout and opens a focused view around the clicked node.
   2026-11-10 (user: 把数据统计页面的数据和整个数据库的数据统一起来): analytics.json counts every record of the database (no
   longer only the research set), and its `corpus` block feeds the page's key figures and summary charts below, which
   app.js draws (renderAnalytics / renderSiteMetrics read window.GreenCorpus on this page instead of the original
   project's corpus_analytics.json / site_metrics.json): the page then counts as the home page and the text database do.
   Those figures are hidden until the file is in (no flash of the other numbers); without it they are the original's. */
(() => {
  "use strict";
  const page = document.getElementById("analytics");
  const box = document.getElementById("researchCharts");
  if (!page || !box) return;
  const root = document.documentElement;
  const en = () => (root.lang || "").startsWith("en");
  const NS = "http://www.w3.org/2000/svg";
  // the 14 categories in hue families (governance blues, transition greens, risk reds, finance / diplomacy violets,
  // society ochres, land olive), unclassified grey
  const COLORS = {
    G01: "#2f5f8f", G02: "#5b88b5", G09: "#9ab7d3",
    G03: "#2f7d6d", G07: "#5fa894", G08: "#9cc9ba",
    G04: "#c8372d", G05: "#8f2620", G14: "#e0806f",
    G06: "#6c5b9a", G11: "#a497c6",
    G10: "#b39b4d", G13: "#d9c78f",
    G12: "#7d8a3c",
    unclassified: "#c4ccd4",
  };
  const COPY = {
    zh: {
      overline: "RESEARCH ANALYSIS", title: "科研分析",
      clusters: "议题簇", clustersNote: "每个气泡是一个小类议题，按 14 个大类成簇，面积为当年该议题占已分类报道的比例（用比例而非篇数，避免把采集量增长读成议题升温）。拖动时间条或直接在图上左右拖动，查看历年变化。",
      play: "播放", pause: "暂停", yearPick: "选择年份", bubble: (a, b, y, n, p) => `${y} · ${a}（${b}）：${n} 篇，占 ${p}%`,
      spectrum: "议题分类谱系", spectrumNote: "全部已分类报道按主议题的构成：内圈 14 个大类，外圈 83 个小类。点击任一扇区展开该大类，点击中心返回。", spectrumAll: "已分类报道",
      spectrumNone: (n) => `另有 ${n} 篇未归入任何议题，未计入`,
      movers: "议题升降榜", moversNote: (a, b) => `小类议题在已分类报道中的占比：${a}（灰点）→ ${b}（彩点），列出升降最大的各 7 个，右侧为百分点变化。只反映报道结构，不等于议题重要性或政策进展。`,
      netForce: "力导向", netRing: "环形", netBack: "返回全图",
      countries: "国家 × 议题矩阵", countriesNote: "报道中提及最多的 24 个国家分别与哪些议题同时出现。「偏好」为该议题在该国议题构成中的比重，相对主要国家平均水平的倍数，红色高于平均、蓝色低于平均，便于比较各国的议题侧重。国家标签为文本提及，不等于报道对象或国家立场。点击列名按该议题排序。",
      lift: "偏好", ctCell: (a, b, n, p, l) => `${a} × ${b}：${n} 篇 · 占该国 ${p}% · 偏好为主要国家平均的 ${l} 倍`,
      calendar: "COP 节律", calendarNote: "每年各月报道量相对当年月均水平的高低，颜色越深越集中，红框为当年 COP 举行的月份。2021 年含大量归档采集，当年分布仅供参考。",
      months: ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"],
      calCell: (y, m, n, p, cop) => `${y} 年 ${m} 月：${n} 篇，占当年 ${p}%${cop ? " · COP 举行月" : ""}`,
      flows: "议题—政策工具—政策阶段", flowsNote: "各议题的报道提到了哪类政策工具，这些工具又处在什么阶段。同一篇可提及多种工具与阶段，流量为共现次数而非文章数；标签为规则候选。悬停节点查看其流向。",
      tools: { regulation: "法规与标准", economic: "经济手段", planning: "规划与路线图", information: "信息披露", cooperation: "国际合作" },
      stages: { target: "目标", proposed: "拟议", adopted: "通过", implemented: "实施", effective: "生效" },
      note: (n, from, to) => `基于文本数据库全部记录（${n} 篇，${from}–${to}），议题标签为规则候选，未经人工逐篇确认。`,
      corpusNotes: ["统计范围为文本数据库全部记录，与文本数据库检索、首页数字同一口径。", "国家/地区标签只在文本明确出现时生成，未强行推断。", "图表用于描述语料库样本分布，不等同于全球气候事件真实发生频率。"],
      trend: "COP 议题历时演变",
      trendNote: (n, early) => `按年份统计 ${n} 个大类气候治理议题（主议题，互斥）的报道数量与占比。不同年份的来源覆盖不同，请对照下方的年度文章数与来源数，避免把采集量增长误读为议题重要性上升。${early ? `${early.from}–${early.to} 年样本过少（共 ${early.n} 篇），未画出。` : ""}`,
      share: "占比", count: "文章数", articles: "文章", publishers: "来源", unclassified: "未分类",
      network: "国家与国际组织共同出现网络", networkNote: "同一篇报道中共同出现的国家与国际组织（出现最多的 45 个）。线越粗，共同出现越集中（Jaccard 系数）。共同出现只表示报道关联，不能直接解释为外交合作关系。",
      country: "国家", org: "国际组织", together: (n, j) => `共同出现 ${n} 篇 · Jaccard ${j}`, mentions: (n) => `${n} 篇报道`,
      matrix: "气候治理议题共现矩阵", matrixNote: "两类议题在同一篇报道中同时出现的程度，可为政策协同与冲突研究提供候选线索；共现本身不能证明因果联系。",
      jaccard: "Jaccard", pairs: "共同出现数", cell: (a, b, n, j) => `${a} × ${b}：共同出现 ${n} 篇，Jaccard ${j}`,
      timeline: "重大气候政策事件时间轴", timelineNote: "来自官方来源核对层、日期与原句齐备的政策事件；点击事件查看原句与来源。新闻与事件之间尚未建立精确关联。",
      search: "检索事件", searchPh: "关键词、国家或机构", topicAll: "全部议题", events: (n) => `${n} 个事件`, source: "查看来源", none: "没有符合条件的事件",
    },
    en: {
      overline: "RESEARCH ANALYSIS", title: "Research charts",
      clusters: "Topic clusters", clustersNote: "Each bubble is a subcategory, grouped by the 14 categories; its area is that topic's share of the year's classified articles (shares, so collection growth is not read as a topic heating up). Drag the year bar, or drag across the chart.",
      play: "Play", pause: "Pause", yearPick: "Choose a year", bubble: (a, b, y, n, p) => `${y} · ${a} (${b}): ${n} articles, ${p}%`,
      spectrum: "Topic taxonomy", spectrumNote: "Classified articles by primary topic: 14 categories inside, 83 subcategories outside. Click a segment to open its category, the centre to go back.", spectrumAll: "classified articles",
      spectrumNone: (n) => `${n} articles matched no topic and are not counted`,
      movers: "Rising and falling topics", moversNote: (a, b) => `Each subcategory's share of classified articles: ${a} (grey) to ${b} (colour), the seven largest gains and falls, with the change in points at right. It describes reporting, not a topic's importance or policy progress.`,
      netForce: "Force", netRing: "Ring", netBack: "Back to all",
      countries: "Countries × topics", countriesNote: "Which topics the 24 most mentioned countries appear with. Lean is the topic's weight in the country's mix of topics against the average of the main countries: red above average, blue below. Country labels are text mentions, not a report's subject or a national position. Click a column to sort by it.",
      lift: "Lean", ctCell: (a, b, n, p, l) => `${a} × ${b}: ${n} articles · ${p}% of the country's · lean ${l}× the main countries' average`,
      calendar: "The COP rhythm", calendarNote: "Each month against that year's monthly average (darker = more concentrated); red outlines mark the month of that year's COP. 2021 holds a large archive collection: read its pattern with care.",
      months: ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"],
      calCell: (y, m, n, p, cop) => `${y}-${String(m).padStart(2, "0")}: ${n} articles, ${p}% of the year${cop ? " · COP month" : ""}`,
      flows: "Topics, policy tools and stages", flowsNote: "Which kinds of policy tool the articles on each topic mention, and at what stage. An article can name several, so flows are co-mentions, not article counts; labels are rule-based candidates. Point at a node to follow its flows.",
      tools: { regulation: "Regulation", economic: "Economic", planning: "Planning", information: "Disclosure", cooperation: "Cooperation" },
      stages: { target: "Target", proposed: "Proposed", adopted: "Adopted", implemented: "Implemented", effective: "In force" },
      note: (n, from, to) => `From all records of the text database (${n} articles, ${from}–${to}); topic labels are rule-based candidates, not reviewed one by one.`,      trend: "COP topics over time",
      trendNote: (n, early) => `Coverage of the ${n} climate-governance topic categories by year (exclusive primary topic), as counts and shares. Source coverage differs between years: read it against the yearly articles and publishers below, so collection growth is not mistaken for a topic gaining importance.${early ? ` ${early.from}–${early.to}: too few articles (${early.n} in all), not drawn.` : ""}`,
      share: "Share", count: "Articles", articles: "articles", publishers: "publishers", unclassified: "Unclassified",
      network: "Countries and organisations mentioned together", networkNote: "Countries and international organisations named in the same article (the 45 most frequent). Thicker lines: more concentrated co-mention (Jaccard). Co-mention is a reporting link, not diplomatic cooperation.",
      country: "Country", org: "Organisation", together: (n, j) => `${n} articles together · Jaccard ${j}`, mentions: (n) => `${n} articles`,
      matrix: "Topic co-occurrence matrix", matrixNote: "How often two topics appear in the same article — leads for research on policy synergy and conflict; co-occurrence alone does not prove a causal link.",
      jaccard: "Jaccard", pairs: "Co-occurring", cell: (a, b, n, j) => `${a} × ${b}: ${n} articles together, Jaccard ${j}`,
      timeline: "Major climate policy events", timelineNote: "Dated policy events from the official-source layer with a quote; click an event for the quote and source. News articles are not yet linked to the events.",
      search: "Search events", searchPh: "Keyword, country or body", topicAll: "All topics", events: (n) => `${n} events`, source: "Open source", none: "No events match",
    },
  };
  const t = () => COPY[en() ? "en" : "zh"];
  const num = (n) => Number(n || 0).toLocaleString(en() ? "en" : "zh-CN");
  const el = (tag, props = {}, ...kids) => { const node = Object.assign(document.createElement(tag), props); node.append(...kids.filter((k) => k != null && k !== "")); return node; };
  const svg = (tag, attrs = {}) => { const node = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v); return node; };
  let data = null;
  const state = { trend: "share", matrix: "jaccard", q: "", topic: "", net: "force", year: null, spectrum: null, country: "lift", countrySort: null };
  const topicName = (id) => (id === "unclassified" ? t().unclassified : (data.topics.find((x) => x.id === id) || {})[en() ? "en" : "zh"] || id);

  // a floating tag for hovered marks
  const tip = el("div", { className: "rc-tip", hidden: true });
  const showTip = (event, text) => {
    tip.textContent = text; tip.hidden = false;
    const r = box.getBoundingClientRect();
    tip.style.left = `${Math.min(event.clientX - r.left + 12, r.width - tip.offsetWidth - 4)}px`;
    tip.style.top = `${event.clientY - r.top + 14}px`;
  };
  const hideTip = () => { tip.hidden = true; };

  function head(card, overline, title, note, controls) {
    // the plate number follows the card's place on the page (2026-11-11: seven charts joined the ten, analysis-more.js)
    overline = overline.replace(/^\d+ · /, `${String([...box.querySelectorAll(".rc-card")].indexOf(card) + 1).padStart(2, "0")} · `);
    card.replaceChildren(el("div", { className: "chart-heading rc-heading" }, el("span", { textContent: overline }), el("h3", { textContent: title }),
      el("p", { textContent: note })), ...(controls ? [controls] : []));
  }
  function toggle(options, value, onChange) {
    const group = el("div", { className: "rc-toggle", role: "group" });
    for (const [key, label] of options) {
      const b = el("button", { type: "button", textContent: label });
      b.setAttribute("aria-pressed", String(key === value));
      b.addEventListener("click", () => { group.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); onChange(key); });
      group.append(b);
    }
    return group;
  }
  const widthOf = (node) => Math.max(300, Math.round(node.clientWidth || 640));
  // A phone's plate (2026-11-15): the three charts that kept a desktop width there — 国家 × 议题矩阵 and the flows had to
  // be scrolled sideways (half of each was out of sight), the co-occurrence matrix shrank until its names were 5px — are
  // drawn for the width they get: shorter names, column names upright, labels on two lines.
  const narrowOf = (card) => widthOf(card) < 520;
  const clip = (text, n) => { const chars = [...String(text)]; return chars.length > n ? `${chars.slice(0, n - 1).join("")}…` : String(text); };
  const SHORT_NAMES = { 中华人民共和国: "中国", 阿拉伯联合酋长国: "阿联酋", 巴基斯坦伊斯兰共和国: "巴基斯坦", 委内瑞拉玻利瓦尔共和国: "委内瑞拉",
    朝鲜民主主义人民共和国: "朝鲜", 老挝人民民主共和国: "老挝", "刚果民主共和国(DRC)": "刚果（金）", 中国香港特别行政区: "中国香港" };
  // a label on up to `max` lines of `per` characters: Chinese at a natural break (、与和及) or else evenly, English by words
  function wrapLabel(text, per, max) {
    const chars = [...String(text)];
    if (chars.length <= per) return [String(text)];
    if (/\s/.test(text)) {
      const lines = [""];
      for (const word of String(text).split(/\s+/)) {
        const i = lines.length - 1;
        if (lines[i] && `${lines[i]} ${word}`.length > per && lines.length < max) lines.push(word); else lines[i] += (lines[i] ? " " : "") + word;
      }
      return lines.map((line) => clip(line, per + 2));
    }
    // two lines: at a natural break when both halves fit, else cut in the middle
    let cut = Math.ceil(chars.length / 2);
    for (let d = 0; d <= 3; d += 1) {
      const at = [cut + d, cut - d].find((i) => i > 1 && i <= per && chars.length - i <= per && (/[与和及]/.test(chars[i]) || /[、，]/.test(chars[i - 1])));
      if (at) { cut = at; break; }
    }
    cut = Math.min(cut, per);
    return [chars.slice(0, cut).join(""), clip(chars.slice(cut).join(""), per)];
  }

  /* 1 ---------- topics over time ---------- */
  function drawTrend() {
    const c = t(), card = document.getElementById("topicTrend");
    const years = data.years.filter((y) => !data.trend_from || y.year >= data.trend_from), keys = [...data.topics.map((x) => x.id), "unclassified"];
    const early = data.years.filter((y) => !years.includes(y));
    head(card, "01 · TOPIC TRENDS", c.trend, c.trendNote(data.topics.length, early.length ? { from: early[0].year, to: early[early.length - 1].year, n: num(early.reduce((s, y) => s + y.articles, 0)) } : null),
      toggle([["share", c.share], ["count", c.count]], state.trend, (k) => { state.trend = k; drawTrend(); }));
    const W = widthOf(card) - 8, H = Math.round(Math.min(380, Math.max(240, W * 0.42))), L = en() ? 70 : 46, R = 26, T = 10, B = 58;
    // every year's label (and coverage figures) when they fit, else every second / fifth … one
    const every = [1, 2, 5, 10].find((k) => ((W - L - R) / Math.max(1, years.length - 1)) * k >= 38) || 10;
    const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg", role: "img" });
    const x = (i) => L + (years.length === 1 ? 0 : (i / (years.length - 1)) * (W - L - R));
    const totals = years.map((y) => keys.reduce((s, k) => s + (y.primary[k] || 0), 0));
    const maxTotal = Math.max(...totals, 1);
    const y = (v) => T + (H - T - B) * (1 - v);
    const value = (yi, k) => (state.trend === "share" ? (years[yi].primary[k] || 0) / (totals[yi] || 1) : (years[yi].primary[k] || 0) / maxTotal);
    // grid
    for (let g = 0; g <= 4; g += 1) {
      const gy = y(g / 4);
      plot.append(svg("line", { x1: L, x2: W - R, y1: gy, y2: gy, class: "rc-grid" }));
      const label = state.trend === "share" ? `${g * 25}%` : num(Math.round((maxTotal * g) / 4));
      const tx = svg("text", { x: L - 6, y: gy + 3, class: "rc-axis", "text-anchor": "end" }); tx.textContent = label; plot.append(tx);
    }
    // stacked areas (bottom → top in topic order)
    const base = years.map(() => 0);
    keys.forEach((k) => {
      const top = years.map((_, i) => base[i] + value(i, k));
      const d = [...years.map((_, i) => `${x(i)},${y(top[i])}`), ...years.map((_, i) => `${x(years.length - 1 - i)},${y(base[years.length - 1 - i])}`)];
      const area = svg("path", { d: `M${d.join("L")}Z`, fill: COLORS[k] || "#999", class: "rc-area" });
      area.addEventListener("pointermove", (event) => {
        const i = Math.max(0, Math.min(years.length - 1, Math.round(((event.offsetX * W) / plot.clientWidth - L) / ((W - L - R) / Math.max(1, years.length - 1)))));
        const n = years[i].primary[k] || 0;
        showTip(event, `${years[i].year} · ${topicName(k)}：${num(n)}（${((n / (totals[i] || 1)) * 100).toFixed(1)}%）`);
      });
      area.addEventListener("pointerleave", hideTip);
      plot.append(area);
      top.forEach((v, i) => { base[i] = v; });
    });
    // year labels, then the coverage rows (articles · publishers per year)
    years.forEach((yr, i) => {
      if ((years.length - 1 - i) % every) return; // counted back from the latest year, which is always labelled
      const yx = x(i);
      const lab = svg("text", { x: yx, y: H - B + 16, class: "rc-axis", "text-anchor": "middle" }); lab.textContent = yr.year; plot.append(lab);
      const a = svg("text", { x: yx, y: H - B + 32, class: "rc-cover", "text-anchor": "middle" }); a.textContent = num(yr.articles); plot.append(a);
      const p = svg("text", { x: yx, y: H - B + 46, class: "rc-cover", "text-anchor": "middle" }); p.textContent = num(yr.publishers); plot.append(p);
    });
    for (const [row, label] of [[32, c.articles], [46, c.publishers]]) {
      const tx = svg("text", { x: L - 6, y: H - B + row, class: "rc-cover", "text-anchor": "end" }); tx.textContent = label; plot.append(tx);
    }
    const legend = el("div", { className: "rc-legend" }, ...keys.map((k) => el("span", {}, el("i", { style: `background:${COLORS[k]}` }), topicName(k))));
    card.append(el("div", { className: "rc-plot" }, plot), legend);
  }

  /* 2 ---------- topic clusters by year (draggable) ---------- */
  const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const easeBack = (p) => 1 + 2.3 * Math.pow(p - 1, 3) + 1.3 * Math.pow(p - 1, 2);
  // a parent's colour, lightened along its subcategories
  const tintOf = (hex, k) => { const v = parseInt(hex.slice(1), 16); return `rgb(${[16, 8, 0].map((s) => Math.round(((v >> s) & 255) + (255 - ((v >> s) & 255)) * k)).join(" ")})`; };
  const subName = (s) => s[en() ? "en" : "zh"];
  const subTotals = () => { const out = {}; for (const y of data.years) for (const [k, n] of Object.entries(y.sub || {})) out[k] = (out[k] || 0) + n; return out; };
  let clusters = null;
  function drawClusters() {
    const c = t(), card = document.getElementById("topicClusters");
    if (!card) return;
    if (!data.subcategories) { card.hidden = true; return; }
    if (clusters) { cancelAnimationFrame(clusters.raf); clearInterval(clusters.timer); }
    const years = data.years.filter((y) => !data.trend_from || y.year >= data.trend_from);
    if (state.year == null || !years.some((y) => y.year === state.year)) state.year = years[years.length - 1].year;
    head(card, "02 · TOPIC CLUSTERS", c.clusters, c.clustersNote);
    const W = Math.max(520, Math.min(1160, widthOf(card) - 8)), H = Math.round(clamp(W * 0.46, 380, 520));
    const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-clusters", role: "img" });
    const big = svg("text", { x: W - 8, y: H - 14, "text-anchor": "end", class: "rc-bigyear" });
    plot.append(big);
    // the largest category in the middle, the others around it
    const totals = subTotals(), weight = (id) => data.subcategories.filter((x) => x.parent === id).reduce((sum, x) => sum + (totals[x.id] || 0), 0);
    const biggest = [...data.topics].sort((a, b) => weight(b.id) - weight(a.id))[0], rest = data.topics.filter((x) => x !== biggest), anchors = { [biggest.id]: { x: W / 2, y: H / 2 + 8 } };
    rest.forEach((x, i) => { const a = -Math.PI / 2 + ((i + 0.5) / rest.length) * Math.PI * 2; anchors[x.id] = { x: W / 2 + Math.cos(a) * W * 0.41, y: H / 2 + 8 + Math.sin(a) * H * 0.37 }; });
    const siblings = {};
    const nodes = data.subcategories.map((s) => {
      const i = (siblings[s.parent] = (siblings[s.parent] || 0) + 1), a = anchors[s.parent], g = svg("g", { class: "rc-bubble" });
      const circle = svg("circle", { fill: tintOf(COLORS[s.parent] || "#587088", ((i - 1) % 5) * 0.14), r: 0 });
      const label = svg("text", { "text-anchor": "middle", class: "rc-bubble-label" });
      g.append(circle, label);
      if (((i - 1) % 5) * 0.14 >= 0.28) label.classList.add("is-dark");
      const node = { s, a, g, circle, label, x: a.x + Math.cos(i * 2.4) * 26, y: a.y + Math.sin(i * 2.4) * 26, vx: 0, vy: 0, r: 0, rt: 0, n: 0, share: 0 };
      g.addEventListener("pointermove", (event) => showTip(event, c.bubble(subName(s), topicName(s.parent), state.year, num(node.n), (node.share * 100).toFixed(1))));
      g.addEventListener("pointerleave", hideTip);
      plot.append(g);
      return node;
    });
    const heads = data.topics.map((x) => { const text = svg("text", { "text-anchor": "middle", class: "rc-cluster-name" }); text.textContent = x[en() ? "en" : "zh"]; plot.append(text); return { id: x.id, text }; });
    const paint = () => {
      for (const n of nodes) {
        n.circle.setAttribute("cx", n.x.toFixed(1)); n.circle.setAttribute("cy", n.y.toFixed(1)); n.circle.setAttribute("r", Math.max(0, n.r).toFixed(1));
        n.label.setAttribute("x", n.x.toFixed(1)); n.label.setAttribute("y", (n.y + 3.5).toFixed(1));
        const name = subName(n.s), fits = name.length * (en() ? 5.2 : 10.5) < n.r * 1.8;
        n.label.textContent = fits ? name : "";
      }
      for (const h of heads) {
        const mine = nodes.filter((n) => n.s.parent === h.id && n.r > 0.5);
        const x = mine.length ? mine.reduce((s, n) => s + n.x, 0) / mine.length : anchors[h.id].x;
        const y = mine.length ? Math.min(...mine.map((n) => n.y - n.r)) - 6 : anchors[h.id].y;
        h.x = clamp(x, 44, W - 44); h.y = Math.max(12, y); h.w = (h.text.textContent.length * (en() ? 6 : 11)) / 2 + 6;
      }
      const seen = [];  // a name never sits on another: it steps up until it is clear
      for (const h of [...heads].sort((a, b) => b.w - a.w)) {
        for (let guard = 0; guard < 8 && seen.some((o) => Math.abs(o.x - h.x) < o.w + h.w && Math.abs(o.y - h.y) < 13); guard += 1) h.y = Math.max(12, h.y - 14) === h.y ? h.y : Math.max(12, h.y - 14);
        seen.push(h);
        h.text.setAttribute("x", h.x.toFixed(1)); h.text.setAttribute("y", h.y.toFixed(1));
      }
    };
    const step = () => {
      let energy = 0;
      for (const n of nodes) { const dr = (n.rt - n.r) * 0.16; n.r += dr; energy += Math.abs(dr); }
      // each cluster holds together around its own centre, and that centre leans to its place
      const hubs = {};
      for (const n of nodes) { const h = (hubs[n.s.parent] ||= { x: 0, y: 0, m: 0 }), w = n.r * n.r + 1; h.x += n.x * w; h.y += n.y * w; h.m += w; }
      for (const n of nodes) {
        const h = hubs[n.s.parent], cx = h.x / h.m, cy = h.y / h.m;
        n.vx = (n.vx + (cx - n.x) * 0.05 + (n.a.x - cx) * 0.03) * 0.72;
        n.vy = (n.vy + (cy - n.y) * 0.05 + (n.a.y - cy) * 0.03) * 0.72;
        n.px = n.x; n.py = n.y; n.x += n.vx; n.y += n.vy;
      }
      for (let pass = 0; pass < 4; pass += 1) {
        for (let i = 0; i < nodes.length; i += 1) {
          const a = nodes[i];
          if (a.r < 0.3) continue;
          for (let j = i + 1; j < nodes.length; j += 1) {
            const b = nodes[j];
            if (b.r < 0.3) continue;
            const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.01, min = a.r + b.r + (a.s.parent === b.s.parent ? 1.5 : 9);
            if (d < min) {
              const push = (min - d) / d, wa = b.r * b.r / (a.r * a.r + b.r * b.r), wb = 1 - wa; // the small one gives way
              a.x -= dx * push * wa; a.y -= dy * push * wa; b.x += dx * push * wb; b.y += dy * push * wb;
            }
          }
        }
        for (const n of nodes) { n.x = clamp(n.x, n.r + 2, W - n.r - 2); n.y = clamp(n.y, n.r + 16, H - n.r - 2); }
      }
      for (const n of nodes) energy += Math.abs(n.x - n.px) + Math.abs(n.y - n.py);
      return energy;
    };
    const run = () => {
      cancelAnimationFrame(clusters.raf);
      if (still()) { for (let i = 0; i < 240; i += 1) step(); paint(); return; }
      let frames = 0;
      const tick = () => { const energy = step(); paint(); frames += 1; if (energy > 0.6 && frames < 420) clusters.raf = requestAnimationFrame(tick); };
      clusters.raf = requestAnimationFrame(tick);
    };
    const range = el("input", { type: "range", min: 0, max: years.length - 1, step: 1, className: "rc-range", value: years.findIndex((y) => y.year === state.year) });
    range.setAttribute("aria-label", c.yearPick);
    const setYear = (index) => {
      const y = years[clamp(index, 0, years.length - 1)];
      state.year = y.year; range.value = years.indexOf(y); big.textContent = y.year;
      const total = Object.values(y.sub || {}).reduce((s, n) => s + n, 0) || 1, k = Math.sqrt((0.21 * W * H) / Math.PI);
      for (const n of nodes) { n.n = (y.sub || {})[n.s.id] || 0; n.share = n.n / total; n.rt = n.n ? Math.min(H * 0.25, Math.max(3, k * Math.sqrt(n.share))) : 0; }
      run();
    };
    clusters = { raf: 0, timer: 0 };
    const stop = () => { clearInterval(clusters.timer); clusters.timer = 0; play.textContent = c.play; };
    range.addEventListener("input", () => { stop(); setYear(Number(range.value)); });
    const play = el("button", { type: "button", className: "rc-play", textContent: c.play });
    play.addEventListener("click", () => {
      if (clusters.timer) { stop(); return; }
      if (Number(range.value) >= years.length - 1) setYear(0);
      play.textContent = c.pause;
      clusters.timer = setInterval(() => { const next = Number(range.value) + 1; if (next >= years.length) { stop(); return; } setYear(next); }, 1100);
    });
    // dragging across the chart scrubs the years too
    let drag = null;
    plot.addEventListener("pointerdown", (event) => { drag = { x: event.clientX, from: Number(range.value) }; plot.setPointerCapture(event.pointerId); stop(); plot.classList.add("is-drag"); });
    plot.addEventListener("pointermove", (event) => { if (!drag) return; const next = clamp(drag.from + Math.round(((event.clientX - drag.x) / plot.clientWidth) * years.length * 1.4), 0, years.length - 1); if (next !== Number(range.value)) setYear(next); });
    const release = () => { drag = null; plot.classList.remove("is-drag"); };
    plot.addEventListener("pointerup", release); plot.addEventListener("pointercancel", release);
    const every = [1, 2, 5].find((k) => ((widthOf(card) - 110) / years.length) * k >= 40) || 5;
    const ticks = el("div", { className: "rc-ticks" }, ...years.map((y, i) => el("span", { textContent: (years.length - 1 - i) % every ? "" : y.year })));
    card.append(el("div", { className: "rc-plot" }, plot), el("div", { className: "rc-scrub" }, play, el("div", { className: "rc-scrub-track" }, range, ticks)));
    setYear(Number(range.value));
  }

  /* 3 ---------- the taxonomy as a ring ---------- */
  function drawSpectrum() {
    const c = t(), card = document.getElementById("topicSpectrum");
    if (!card) return;
    if (!data.subcategories) { card.hidden = true; return; }
    head(card, "03 · TOPIC TAXONOMY", c.spectrum, c.spectrumNote);
    const S = 520, C = S / 2, totals = subTotals(), all = Object.values(totals).reduce((s, n) => s + n, 0) || 1;
    const none = data.years.reduce((s, y) => s + (y.primary.unclassified || 0), 0);
    const cats = data.topics.map((x) => {
      const subs = data.subcategories.filter((s) => s.parent === x.id).map((s) => ({ s, n: totals[s.id] || 0 })).sort((a, b) => b.n - a.n);
      return { x, subs, n: subs.reduce((s, v) => s + v.n, 0) };
    });
    const arc = (r0, r1, a0, a1) => {
      const span = Math.min(a1 - a0, Math.PI * 2 - 0.0005), end = a0 + span;
      if (span <= 0.0002) return "M0 0";
      const p = (r, a) => `${(C + r * Math.cos(a)).toFixed(2)} ${(C + r * Math.sin(a)).toFixed(2)}`, large = span > Math.PI ? 1 : 0;
      return `M${p(r1, a0)}A${r1} ${r1} 0 ${large} 1 ${p(r1, end)}L${p(r0, end)}A${r0} ${r0} 0 ${large} 0 ${p(r0, a0)}Z`;
    };
    const plot = svg("svg", { viewBox: `0 0 ${S} ${S}`, class: "rc-svg rc-spectrum", role: "img" });
    const segs = [];
    const add = (kind, cat, sub, fill, r0, r1, name, n) => {
      const path = svg("path", { fill, class: `rc-seg rc-seg-${kind}` }), seg = { kind, cat, sub, path, r0, r1, a0: -Math.PI / 2, a1: -Math.PI / 2, f0: 0, f1: 0, t0: 0, t1: 0 };
      path.addEventListener("pointermove", (event) => showTip(event, `${name}：${num(n)}（${((n / all) * 100).toFixed(1)}%）`));
      path.addEventListener("pointerleave", hideTip);
      path.addEventListener("click", () => setFocus(state.spectrum === cat.x.id ? null : cat.x.id));
      plot.append(path); segs.push(seg);
    };
    for (const cat of cats) {
      const base = COLORS[cat.x.id] || "#587088";
      add("cat", cat, null, base, 112, 168, cat.x[en() ? "en" : "zh"], cat.n);
      cat.subs.forEach((v, i) => add("sub", cat, v, tintOf(base, 0.12 + (i / Math.max(1, cat.subs.length)) * 0.55), 172, 244, subName(v.s), v.n));
    }
    const centre = svg("g", { class: "rc-spec-centre" });
    const value = svg("text", { x: C, y: C - 2, "text-anchor": "middle", class: "rc-spec-value" }), label = svg("text", { x: C, y: C + 22, "text-anchor": "middle", class: "rc-spec-label" });
    const hit = svg("circle", { cx: C, cy: C, r: 106, fill: "transparent" });
    hit.addEventListener("click", () => setFocus(null));
    centre.append(hit, value, label); plot.append(centre);
    const list = el("ol", { className: "rc-spec-list" });
    let raf = 0;
    function layout(focus) {
      let a = -Math.PI / 2;
      const pool = focus ? cats.filter((x) => x.x.id === focus) : cats, sum = pool.reduce((s, x) => s + x.n, 0) || 1;
      for (const cat of cats) {
        const on = pool.includes(cat), span = on ? (cat.n / sum) * Math.PI * 2 : 0;
        const mine = segs.filter((s) => s.cat === cat), top = mine.find((s) => s.kind === "cat");
        top.t0 = a; top.t1 = a + span;
        let b = a;
        for (const s of mine) if (s.kind === "sub") { const w = cat.n ? (s.sub.n / cat.n) * span : 0; s.t0 = b; s.t1 = b + w; b += w; }
        a += span;
      }
    }
    function fill(focus) {
      const cat = cats.find((x) => x.x.id === focus);
      value.textContent = num(cat ? cat.n : all);
      label.textContent = cat ? cat.x[en() ? "en" : "zh"] : c.spectrumAll;
      const rows = cat ? cat.subs : cats.flatMap((x) => x.subs.map((v) => ({ ...v, parent: x.x.id }))).sort((a, b) => b.n - a.n);
      const shown = rows.slice(0, cat ? 8 : 8), max = shown[0]?.n || 1;
      list.replaceChildren(...shown.map((v) => el("li", {}, el("span", { textContent: subName(v.s) }),
        el("i", {}, el("b", { style: `width:${(v.n / max) * 100}%;background:${COLORS[v.s.parent] || "#587088"}` })), el("em", { textContent: num(v.n) }))));
    }
    function setFocus(focus) {
      state.spectrum = focus; hideTip(); layout(focus); fill(focus);
      for (const s of segs) { s.f0 = s.a0; s.f1 = s.a1; }
      cancelAnimationFrame(raf);
      const start = performance.now(), dur = still() ? 0 : 760;
      const tick = (now) => {
        const p = dur ? clamp((now - start) / dur, 0, 1) : 1, e = easeInOut(p);
        for (const s of segs) { s.a0 = s.f0 + (s.t0 - s.f0) * e; s.a1 = s.f1 + (s.t1 - s.f1) * e; s.path.setAttribute("d", arc(s.r0, s.r1, s.a0, s.a1)); }
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    }
    card.append(el("div", { className: "rc-spec" }, el("div", { className: "rc-plot" }, plot), el("div", { className: "rc-spec-side" }, list, el("p", { className: "rc-count", textContent: c.spectrumNone(num(none)) }))));
    setFocus(cats.some((x) => x.x.id === state.spectrum) ? state.spectrum : null);
  }

  /* 4 ---------- which subcategories gained or lost share ---------- */
  function drawMovers() {
    const c = t(), card = document.getElementById("topicMovers");
    if (!card) return;
    if (!data.subcategories) { card.hidden = true; return; }
    const full = data.years.slice(0, -1), last = Number(full[full.length - 1].year);
    const window_ = (a, b) => { const out = {}; let sum = 0; for (const y of data.years) if (Number(y.year) >= a && Number(y.year) <= b) for (const [k, n] of Object.entries(y.sub || {})) { out[k] = (out[k] || 0) + n; sum += n; } return { out, sum: sum || 1 }; };
    const recentFrom = last - 2, baseTo = recentFrom - 4, baseFrom = baseTo - 2;   // the 2021 archive bulge stays out of both windows
    const A = window_(baseFrom, baseTo), B = window_(recentFrom, last);
    head(card, "04 · RISING AND FALLING", c.movers, c.moversNote(`${baseFrom}–${baseTo}`, `${recentFrom}–${last}`));
    const rows = data.subcategories.map((s) => ({ s, a: (A.out[s.id] || 0) / A.sum, b: (B.out[s.id] || 0) / B.sum })).map((r) => ({ ...r, d: r.b - r.a })).sort((x, y) => y.d - x.d);
    const shown = [...rows.slice(0, 7), ...rows.slice(-7)];
    const W = Math.max(420, widthOf(card) - 8), L = en() ? 236 : 172, R = 58, T = 8, RH = 27, H = T + shown.length * RH + 30;
    const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg", role: "img" });
    const max = Math.max(...shown.map((r) => Math.max(r.a, r.b)), 0.01), x = (v) => L + (v / max) * (W - L - R);
    for (let g = 0; g <= 4; g += 1) {
      const gx = x((max * g) / 4);
      plot.append(svg("line", { x1: gx, x2: gx, y1: T, y2: H - 24, class: "rc-grid" }));
      const lab = svg("text", { x: gx, y: H - 8, "text-anchor": "middle", class: "rc-axis" }); lab.textContent = `${((max * g * 25)).toFixed(1)}%`; plot.append(lab);
    }
    shown.forEach((r, i) => {
      const y = T + i * RH + RH / 2, up = r.d >= 0, g = svg("g", { class: "rc-mover" });
      const name = svg("text", { x: L - 10, y: y + 4, "text-anchor": "end", class: "rc-mover-name" }); name.textContent = subName(r.s);
      const bar = svg("line", { x1: x(r.a), x2: x(r.b), y1: y, y2: y, class: up ? "rc-move rc-up" : "rc-move rc-down" });
      const dotA = svg("circle", { cx: x(r.a), cy: y, r: 4, class: "rc-dot-a" }), dotB = svg("circle", { cx: x(r.b), cy: y, r: 5, class: up ? "rc-dot-b rc-up" : "rc-dot-b rc-down" });
      const delta = svg("text", { x: W - 4, y: y + 3.5, "text-anchor": "end", class: up ? "rc-delta rc-up" : "rc-delta rc-down" }); delta.textContent = `${up ? "+" : "−"}${Math.abs(r.d * 100).toFixed(2)}`;
      g.append(svg("rect", { x: 0, y: y - RH / 2, width: W, height: RH, fill: "transparent" }), name, bar, dotA, dotB, delta);
      g.addEventListener("pointermove", (event) => showTip(event, `${subName(r.s)}：${(r.a * 100).toFixed(2)}% → ${(r.b * 100).toFixed(2)}%`));
      g.addEventListener("pointerleave", hideTip);
      plot.append(g);
    });
    card.append(el("div", { className: "rc-plot" }, plot));
  }

  /* 6 ---------- countries × categories ---------- */
  function drawCountries() {
    const c = t(), card = document.getElementById("countryTopics");
    if (!card) return;
    if (!data.country_topics) { card.hidden = true; return; }
    head(card, "06 · COUNTRIES AND TOPICS", c.countries, c.countriesNote, toggle([["lift", c.lift], ["share", c.share], ["count", c.count]], state.country, (k) => { state.country = k; paint(); }));
    const ids = data.topics.map((x) => x.id), mix = (row) => ids.reduce((s, id) => s + (row.topics[id] || 0), 0);
    // articles mentioning a country carry more labels than the average one: compare each country's mix of topics
    const allMix = data.country_topics.reduce((s, row) => s + mix(row), 0) || 1;
    const baseRate = Object.fromEntries(ids.map((id) => [id, data.country_topics.reduce((s, row) => s + (row.topics[id] || 0), 0) / allMix]));
    const rows = data.country_topics.slice(0, 24);
    const value = (row, id) => { const n = row.topics[id] || 0, share = n / (row.articles || 1), lift = (n / (mix(row) || 1)) / (baseRate[id] || 1); return { n, share, lift }; };
    // on a phone: every column in the plate's width — short country names, the column names upright
    const narrow = narrowOf(card);
    const rowName = (row) => { const name = row[en() ? "en" : "zh"]; return narrow ? clip(SHORT_NAMES[name] || name, en() ? 15 : 6) : name; };
    const headName = (id) => (narrow ? clip(topicName(id), en() ? 24 : 14) : topicName(id));
    const W = narrow ? widthOf(card) - 8 : Math.max(640, Math.min(1160, widthOf(card) - 8)), L = narrow ? (en() ? 104 : 80) : en() ? 150 : 118;
    const longest = Math.max(...ids.map((id) => [...headName(id)].length)) * (en() ? 5.6 : 10.2);
    const over = narrow ? 6 : Math.round(longest * 0.72), T = (narrow ? Math.round(longest) + 4 : over) + 14;
    const S = Math.max(narrow ? 12 : 26, Math.floor((W - L - over) / ids.length)), RH = narrow ? 22 : 24, H = T + rows.length * RH + 6;
    const plot = svg("svg", { viewBox: `0 0 ${L + S * ids.length + over} ${H}`, class: `rc-svg rc-ct${narrow ? " rc-phone" : ""}`, role: "img" });
    const band = svg("rect", { x: 0, y: T, width: S, height: rows.length * RH, class: "rc-ct-band", opacity: 0 });
    plot.append(band);
    const heads = ids.map((id, j) => {
      const text = svg("text", { class: "rc-axis rc-ct-head", transform: `translate(${L + j * S + S / 2 + 3},${T - 6}) rotate(${narrow ? -90 : -45})` }); text.textContent = headName(id);
      text.addEventListener("click", () => { state.countrySort = state.countrySort === id ? null : id; order(); });
      text.addEventListener("pointerenter", () => { band.setAttribute("x", L + j * S); band.setAttribute("opacity", 1); });
      text.addEventListener("pointerleave", () => band.setAttribute("opacity", 0));
      plot.append(text);
      return { id, text };
    });
    const groups = rows.map((row) => {
      const g = svg("g", { class: "rc-ct-row" });
      const name = svg("text", { x: L - 8, y: RH / 2 + 3.5, "text-anchor": "end", class: "rc-ct-name" }); name.textContent = rowName(row);
      g.append(name);
      const cells = ids.map((id, j) => {
        const rect = svg("rect", { x: L + j * S + 1, y: 1, width: S - 2, height: RH - 2, rx: 2, class: "rc-ct-cell" });
        rect.addEventListener("pointermove", (event) => {
          const v = value(row, id);
          showTip(event, c.ctCell(row[en() ? "en" : "zh"], topicName(id), num(v.n), (v.share * 100).toFixed(1), v.lift.toFixed(2)));
          band.setAttribute("x", L + j * S); band.setAttribute("opacity", 1);
        });
        rect.addEventListener("pointerleave", () => { hideTip(); band.setAttribute("opacity", 0); });
        g.append(rect);
        return { id, rect };
      });
      plot.append(g);
      return { row, g, cells };
    });
    function paint() {
      let max = 0;
      for (const { row } of groups) for (const id of ids) { const v = value(row, id); max = Math.max(max, state.country === "count" ? v.n : v.share); }
      for (const { row, cells } of groups) for (const { id, rect } of cells) {
        const v = value(row, id);
        if (state.country === "lift") {
          const k = clamp(Math.log2(Math.max(v.lift, 0.01)) / 1.5, -1, 1);
          rect.setAttribute("fill", k >= 0 ? `rgba(200, 55, 45, ${(0.04 + k * 0.86).toFixed(3)})` : `rgba(47, 95, 143, ${(0.04 - k * 0.62).toFixed(3)})`);
        } else {
          rect.setAttribute("fill", `rgba(47, 95, 143, ${(0.05 + Math.sqrt((state.country === "count" ? v.n : v.share) / (max || 1)) * 0.92).toFixed(3)})`);
        }
      }
    }
    function order() {
      const sorted = [...groups].sort((a, b) => (state.countrySort ? value(b.row, state.countrySort).share - value(a.row, state.countrySort).share : b.row.articles - a.row.articles));
      sorted.forEach((item, i) => { item.g.style.transform = `translate(0px, ${T + i * RH}px)`; });
      for (const h of heads) h.text.classList.toggle("is-on", h.id === state.countrySort);
    }
    paint(); order();
    card.append(el("div", { className: "rc-plot" }, plot));
  }

  /* 8 ---------- months against the COP calendar ---------- */
  const COP_MONTHS = { 2006: [11], 2007: [12], 2008: [12], 2009: [12], 2010: [11, 12], 2011: [11, 12], 2012: [11, 12], 2013: [11], 2014: [12], 2015: [11, 12], 2016: [11], 2017: [11], 2018: [12], 2019: [12], 2021: [11], 2022: [11], 2023: [11, 12], 2024: [11], 2025: [11], 2026: [11] };
  function drawCalendar() {
    const c = t(), card = document.getElementById("issueCalendar");
    if (!card) return;
    if (!data.years.some((y) => y.months)) { card.hidden = true; return; }
    head(card, "08 · THE COP RHYTHM", c.calendar, c.calendarNote);
    const years = data.years.filter((y) => y.months && (!data.trend_from || y.year >= data.trend_from)).reverse();
    const L = 44, T = 22, S = 38, RH = 20, W = L + S * 12 + 6, H = T + years.length * RH + 6;
    const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-plot-calendar", role: "img" });
    for (let m = 0; m < 12; m += 1) { const tx = svg("text", { x: L + m * S + S / 2, y: T - 8, "text-anchor": "middle", class: "rc-axis" }); tx.textContent = c.months[m]; plot.append(tx); }
    years.forEach((y, i) => {
      const ry = T + i * RH, sum = y.months.reduce((s, n) => s + n, 0) || 1;
      const name = svg("text", { x: L - 6, y: ry + RH / 2 + 3.5, "text-anchor": "end", class: "rc-axis" }); name.textContent = y.year; plot.append(name);
      y.months.forEach((n, m) => {
        const share = n / sum, cop = (COP_MONTHS[y.year] || []).includes(m + 1);
        const rect = svg("rect", { x: L + m * S + 1, y: ry + 1, width: S - 2, height: RH - 2, rx: 2, class: cop ? "rc-cal rc-cal-cop" : "rc-cal", fill: `rgba(47, 95, 143, ${(0.05 + clamp((share * 12 - 0.6) / 1.0, 0, 1) * 0.9).toFixed(3)})` });
        rect.addEventListener("pointermove", (event) => showTip(event, c.calCell(y.year, m + 1, num(n), (share * 100).toFixed(1), cop)));
        rect.addEventListener("pointerleave", hideTip);
        plot.append(rect);
      });
    });
    card.append(el("div", { className: "rc-plot" }, plot));
  }

  /* 9 ---------- categories → policy tools → policy stages ---------- */
  function drawFlows() {
    const c = t(), card = document.getElementById("policyFlows");
    if (!card) return;
    if (!data.flows) { card.hidden = true; return; }
    head(card, "09 · POLICY INSTRUMENTS", c.flows, c.flowsNote);
    // on a phone: the three columns in the plate's width — category names on two lines (three in English), the
    // tools named above their nodes
    const narrow = narrowOf(card);
    const linesOf = (name) => (narrow ? wrapLabel(name, en() ? 14 : 7, en() ? 3 : 2) : [name]);
    const leftLines = data.topics.map((x) => linesOf(x[en() ? "en" : "zh"]));
    const longest = Math.max(...leftLines.flat().map((line) => [...line].length));
    const W = narrow ? widthOf(card) - 8 : Math.max(640, Math.min(1160, widthOf(card) - 8)), L = Math.round(longest * (en() ? 6.4 : 12.4)) + 12, R = narrow ? (en() ? 78 : 44) : en() ? 104 : 72;
    const G = 6, NW = narrow ? 10 : 13, SLOT = narrow ? 13 * Math.max(...leftLines.map((lines) => lines.length)) + 3 : 15;
    const PAD = narrow ? 34 : 16, H = narrow ? Math.max(540, data.topics.length * (SLOT + G) + PAD + 20) : 540;
    const SHADES = { regulation: "#2f5f8f", economic: "#6c5b9a", planning: "#2f7d6d", information: "#b39b4d", cooperation: "#8f2620", target: "#9ab7d3", proposed: "#5b88b5", adopted: "#2f5f8f", implemented: "#2f7d6d", effective: "#c8372d" };
    const names = { ...Object.fromEntries(data.topics.map((x) => [x.id, x[en() ? "en" : "zh"]])), ...c.tools, ...c.stages };
    const col = (keys, x) => keys.map((id) => ({ id, x, inn: 0, out: 0, y: 0, h: 0, yi: 0, yo: 0 }));
    const left = col(data.topics.map((x) => x.id), L), mid = col(Object.keys(c.tools), (L + W - R - NW) / 2), right = col(Object.keys(c.stages), W - R - NW);
    const byId = Object.fromEntries([...left, ...mid, ...right].map((n) => [n.id, n]));
    const links = [...data.flows.topic_tool, ...data.flows.tool_stage].filter(([a, b]) => byId[a] && byId[b]).map(([a, b, n]) => { byId[a].out += n; byId[b].inn += n; return { a: byId[a], b: byId[b], n }; });
    const columns = [left, mid, right];
    const sized = (n) => Math.max(n.inn, n.out);
    const gapOf = (list) => (narrow && list === mid ? 20 : G), slotOf = (list) => (list === left ? SLOT : 15); // room for a name above each tool
    let scale = Math.min(...columns.map((list) => (H - PAD - gapOf(list) * (list.length - 1)) / (list.reduce((s, n) => s + sized(n), 0) || 1)));
    const usedBy = (list) => list.reduce((s, n) => s + Math.max(sized(n) * scale, slotOf(list)), 0) + gapOf(list) * (list.length - 1);
    for (let round = 0; round < 6; round += 1) scale *= Math.min(1, (H - PAD) / Math.max(...columns.map(usedBy)));   // a small node still takes a label's height
    for (const list of columns) {
      list.sort((a, b) => sized(b) - sized(a));
      let y = (H - usedBy(list)) / 2 + (narrow ? 7 : 0);
      for (const n of list) { const slot = Math.max(sized(n) * scale, slotOf(list)); n.h = sized(n) * scale; n.y = n.yi = n.yo = y + (slot - n.h) / 2; y += slot + gapOf(list); }
    }
    links.sort((p, q) => (p.a.y - q.a.y) || (p.b.y - q.b.y));
    const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: `rc-svg rc-flows${narrow ? " rc-phone" : ""}`, role: "img" });
    const colorOf = (n) => COLORS[n.id] || SHADES[n.id] || "#587088";
    const ribbons = links.map((l) => {
      const w = l.n * scale, x0 = l.a.x + NW, x1 = l.b.x, y0 = l.a.yo + w / 2, y1 = l.b.yi + w / 2, m = (x0 + x1) / 2;
      l.a.yo += w; l.b.yi += w;
      const path = svg("path", { d: `M${x0} ${y0}C${m} ${y0} ${m} ${y1} ${x1} ${y1}`, "stroke-width": Math.max(0.6, w).toFixed(2), stroke: colorOf(l.a), class: "rc-ribbon" });
      path.addEventListener("pointermove", (event) => showTip(event, `${names[l.a.id]} → ${names[l.b.id]}：${num(l.n)}`));
      path.addEventListener("pointerleave", hideTip);
      plot.append(path);
      return { l, path };
    });
    for (const list of columns) for (const n of list) {
      const g = svg("g", { class: "rc-flow-node" });
      g.append(svg("rect", { x: n.x, y: n.y, width: NW, height: Math.max(1.5, n.h), rx: 2, fill: colorOf(n) }));
      const side = list === left;
      let tx;
      if (narrow && side) { // the category's name on its lines, centred on the node
        const lines = linesOf(names[n.id]);
        tx = svg("text", { x: n.x - 6, y: n.y + n.h / 2 + 3.5 - (lines.length - 1) * 6.5, "text-anchor": "end", class: "rc-flow-label" });
        lines.forEach((line, i) => { const span = svg("tspan", { x: n.x - 6, dy: i ? 13 : 0 }); span.textContent = line; tx.append(span); });
      } else if (narrow && list === mid) { // the tool's name above its node, over the ribbons
        tx = svg("text", { x: n.x + NW / 2, y: n.y - 5, "text-anchor": "middle", class: "rc-flow-label rc-flow-over" }); tx.textContent = names[n.id];
      } else {
        tx = svg("text", { x: side ? n.x - 7 : n.x + NW + 7, y: n.y + n.h / 2 + 3.5, "text-anchor": side ? "end" : "start", class: "rc-flow-label" }); tx.textContent = names[n.id];
      }
      g.append(tx);
      g.addEventListener("pointerenter", () => { plot.classList.add("is-focus"); for (const r of ribbons) r.path.classList.toggle("is-on", r.l.a === n || r.l.b === n); });
      g.addEventListener("pointerleave", () => { plot.classList.remove("is-focus"); for (const r of ribbons) r.path.classList.remove("is-on"); });
      plot.append(g);
    }
    card.append(el("div", { className: "rc-plot" }, plot));
  }

  /* 5 ---------- country / organisation network ---------- */
  let layout = null;
  function forceLayout(nodes, links, W, H) {
    const pos = nodes.map((_, i) => ({ x: W / 2 + Math.cos(i * 2.4) * W * 0.3 * Math.sqrt((i + 1) / nodes.length), y: H / 2 + Math.sin(i * 2.4) * H * 0.3 * Math.sqrt((i + 1) / nodes.length), vx: 0, vy: 0 }));
    const index = new Map(nodes.map((n, i) => [n.id, i]));
    const edges = links.map((l) => [index.get(l.a), index.get(l.b), l.jaccard]).filter((e) => e[0] != null && e[1] != null);
    for (let step = 0; step < 320; step += 1) {
      const cool = 1 - step / 320;
      for (let i = 0; i < pos.length; i += 1) {
        for (let j = i + 1; j < pos.length; j += 1) {
          const dx = pos[i].x - pos[j].x, dy = pos[i].y - pos[j].y, d2 = dx * dx + dy * dy + 0.01, f = 2600 / d2;
          pos[i].vx += dx * f / Math.sqrt(d2); pos[i].vy += dy * f / Math.sqrt(d2); pos[j].vx -= dx * f / Math.sqrt(d2); pos[j].vy -= dy * f / Math.sqrt(d2);
        }
      }
      for (const [a, b, w] of edges) {
        const dx = pos[b].x - pos[a].x, dy = pos[b].y - pos[a].y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 70) * 0.012 * (0.4 + w * 4);
        pos[a].vx += (dx / d) * f; pos[a].vy += (dy / d) * f; pos[b].vx -= (dx / d) * f; pos[b].vy -= (dy / d) * f;
      }
      for (const p of pos) {
        p.vx += (W / 2 - p.x) * 0.004; p.vy += (H / 2 - p.y) * 0.004;
        p.x += Math.max(-12, Math.min(12, p.vx * 0.5 * cool)); p.y += Math.max(-12, Math.min(12, p.vy * 0.5 * cool));
        p.vx *= 0.55; p.vy *= 0.55;
        p.x = Math.max(24, Math.min(W - 24, p.x)); p.y = Math.max(18, Math.min(H - 18, p.y));
      }
    }
    return pos;
  }
  // the drawn network: two overview layouts (force / ring) and a focused view; every change is one eased morph of the
  // same elements (2026-11-09, user: 关系网做一个视觉切换，动效要好看，点到某一个点以其为中心放大)
  let net = null;
  function drawNetwork() {
    const c = t(), card = document.getElementById("entityNetwork");
    if (net) { cancelAnimationFrame(net.raf); removeEventListener("keydown", net.keys); }
    head(card, "05 · CO-MENTION NETWORK", c.network, c.networkNote, toggle([["force", c.netForce], ["ring", c.netRing]], state.net, (k) => { state.net = k; net.focus = null; net.morph(); }));
    const W = Math.max(520, Math.min(1160, widthOf(card) - 8)), H = Math.max(440, Math.round(W * 0.56)), CX = W / 2, CY = H / 2, { nodes, links } = data.network;
    if (!layout) layout = forceLayout(nodes, links, 640, 470);
    const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-network", role: "img" });
    const maxN = Math.max(...nodes.map((n) => n.articles), 1), maxJ = Math.max(...links.map((l) => l.jaccard), 0.01);
    const index = new Map(nodes.map((n, i) => [n.id, i]));
    const nodeName = (id) => { const n = nodes[index.get(id)]; return n ? n[en() ? "en" : "zh"] : id; };
    const baseR = (n) => 4 + Math.sqrt(n.articles / maxN) * 18;
    const items = nodes.map((n, i) => ({ n, i, x: layout[i].x * (W / 640), y: layout[i].y * (H / 470), r: baseR(n), o: 1 }));
    const wires = links.map((l) => {
      const path = svg("path", { class: "rc-link", fill: "none", "stroke-width": (0.4 + (l.jaccard / maxJ) * 3.6).toFixed(2) });
      path.dataset.a = l.a; path.dataset.b = l.b;
      path.addEventListener("pointermove", (event) => showTip(event, `${nodeName(l.a)} — ${nodeName(l.b)}：${c.together(num(l.articles), l.jaccard.toFixed(3))}`));
      path.addEventListener("pointerleave", hideTip);
      plot.append(path);
      return { l, path, a: items[index.get(l.a)], b: items[index.get(l.b)] };
    });
    const spokes = svg("g", { class: "rc-spokes" });
    plot.append(spokes);
    for (const item of items) {
      const n = item.n, g = svg("g", { class: `rc-node rc-${n.kind}`, tabindex: 0, role: "button" });
      item.g = g;
      item.circle = svg("circle", { fill: n.kind === "org" ? "#c8372d" : COLORS[n.topic] || "#587088" });
      item.label = svg("text", { class: "rc-node-label" }); item.label.textContent = n[en() ? "en" : "zh"];
      g.append(item.circle, item.label);
      g.setAttribute("aria-label", item.label.textContent);
      g.addEventListener("pointermove", (event) => {
        const pair = net.focus && (data.network.partners?.[net.focus] || []).find((p) => p[0] === n.id);
        showTip(event, pair ? `${nodeName(net.focus)} — ${item.label.textContent}：${c.together(num(pair[1]), pair[2].toFixed(3))}` : `${item.label.textContent}（${n.kind === "org" ? c.org : c.country}）· ${c.mentions(num(n.articles))} · ${topicName(n.topic)}`);
        if (net.focus) return;
        plot.classList.add("is-focus");
        wires.forEach((w) => w.path.classList.toggle("is-on", w.l.a === n.id || w.l.b === n.id));
      });
      g.addEventListener("pointerleave", () => { hideTip(); plot.classList.remove("is-focus"); wires.forEach((w) => w.path.classList.remove("is-on")); });
      const choose = () => { hideTip(); plot.classList.remove("is-focus"); wires.forEach((w) => w.path.classList.remove("is-on")); net.focus = net.focus === n.id ? null : n.id; net.morph(); };
      g.addEventListener("click", (event) => { event.stopPropagation(); choose(); });
      g.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); choose(); } });
      plot.append(g);
    }
    plot.addEventListener("click", () => { if (net.focus) { net.focus = null; net.morph(); } });

    // where everything goes in each view: x, y, r, o(pacity) per node, and how far the links bow towards the centre
    function targets() {
      if (net.focus) {
        const me = items[index.get(net.focus)], side = Math.min(W, H);
        const pals = (data.network.partners?.[net.focus] || []).filter((p) => index.has(p[0]));
        const top = pals[0]?.[2] || 0.01, near = new Map();
        pals.forEach(([id, , j], i) => {
          const a = -Math.PI / 2 + (i / pals.length) * Math.PI * 2, d = side * (0.44 - (j / top) * 0.16);
          near.set(id, { x: CX + Math.cos(a) * d * (W > H ? 1.28 : 1), y: CY + Math.sin(a) * d, r: 7 + Math.sqrt(j / top) * 17, o: 1 });
        });
        return { curve: 0, at: (item) => {
          if (item === me) return { x: CX, y: CY, r: side * 0.105, o: 1 };
          if (near.has(item.n.id)) return near.get(item.n.id);
          const a = Math.atan2(item.y - CY, item.x - CX);
          return { x: CX + Math.cos(a) * Math.max(W, H) * 0.7, y: CY + Math.sin(a) * Math.max(W, H) * 0.7, r: 2, o: 0 };
        } };
      }
      if (state.net === "ring") {
        const R = Math.min(W, H) / 2 - 70;
        const order = [...items].sort((a, b) => (a.n.kind === b.n.kind ? String(a.n.topic).localeCompare(String(b.n.topic)) || b.n.articles - a.n.articles : a.n.kind === "org" ? -1 : 1));
        const spot = new Map(order.map((item, i) => [item, -Math.PI / 2 + (i / order.length) * Math.PI * 2]));
        return { curve: 0.86, at: (item) => { const a = spot.get(item); return { x: CX + Math.cos(a) * R, y: CY + Math.sin(a) * R, r: 3 + Math.sqrt(item.n.articles / maxN) * 10, o: 1, a }; } };
      }
      return { curve: 0, at: (item) => ({ x: layout[item.i].x * (W / 640), y: layout[item.i].y * (H / 470), r: baseR(item.n), o: 1 }) };
    }
    let curve = 0;
    function paint() {
      for (const item of items) {
        item.circle.setAttribute("cx", item.x.toFixed(1)); item.circle.setAttribute("cy", item.y.toFixed(1)); item.circle.setAttribute("r", Math.max(0.1, item.r).toFixed(1));
        item.g.style.opacity = item.o.toFixed(3);
      }
      for (const w of wires) {
        const mx = (w.a.x + w.b.x) / 2, my = (w.a.y + w.b.y) / 2;
        w.path.setAttribute("d", `M${w.a.x.toFixed(1)} ${w.a.y.toFixed(1)}Q${(mx + (CX - mx) * curve).toFixed(1)} ${(my + (CY - my) * curve).toFixed(1)} ${w.b.x.toFixed(1)} ${w.b.y.toFixed(1)}`);
      }
    }
    // labels are placed once the nodes have arrived (they fade while anything moves)
    function placeLabels(tg) {
      const placed = [], fits = (b) => !placed.some((o) => b.x < o.x + o.w && o.x < b.x + b.w && b.y < o.y + o.h && o.y < b.y + b.h);
      const focusItem = net.focus ? items[index.get(net.focus)] : null;
      for (const item of [...items].sort((a, b) => b.n.articles - a.n.articles)) {
        const { label } = item, name = label.textContent, end = tg.at(item);
        label.removeAttribute("transform");
        label.classList.remove("is-centre");
        let show = true;
        if (item === focusItem) {
          label.setAttribute("x", item.x); label.setAttribute("y", item.y + 5); label.setAttribute("text-anchor", "middle"); label.classList.add("is-centre");
        } else if (focusItem) {
          show = end.o > 0.5;
          label.setAttribute("x", item.x); label.setAttribute("y", item.y - item.r - 5); label.setAttribute("text-anchor", "middle");
        } else if (state.net === "ring") {
          const out = item.r + 6, right = Math.cos(end.a) >= 0, deg = (end.a * 180) / Math.PI + (right ? 0 : 180), lx = item.x + Math.cos(end.a) * out, ly = item.y + Math.sin(end.a) * out;
          label.setAttribute("x", lx.toFixed(1)); label.setAttribute("y", (ly + 3.5).toFixed(1)); label.setAttribute("text-anchor", right ? "start" : "end");
          label.setAttribute("transform", `rotate(${deg.toFixed(1)} ${lx.toFixed(1)} ${ly.toFixed(1)})`);
        } else {
          const w = name.length * (en() ? 6 : 11), b = { x: item.x - w / 2, y: item.y - item.r - 15, w, h: 14 };
          show = fits(b);
          if (show) placed.push(b);
          label.setAttribute("x", item.x.toFixed(1)); label.setAttribute("y", (item.y - item.r - 3).toFixed(1)); label.setAttribute("text-anchor", "middle");
        }
        label.style.display = show ? "" : "none";
      }
    }
    const info = el("div", { className: "rc-ego", hidden: true });
    function drawSpokes(tg) {
      const me = net.focus ? items[index.get(net.focus)] : null;
      if (!me) { spokes.replaceChildren(); return; }
      const end = tg.at(me), pals = (data.network.partners?.[net.focus] || []).filter((p) => index.has(p[0])), top = pals[0]?.[2] || 0.01;
      spokes.replaceChildren(...pals.map(([id, , j], i) => {
        const to = tg.at(items[index.get(id)]);
        const path = svg("line", { x1: end.x, y1: end.y, x2: to.x, y2: to.y, class: "rc-spoke", "stroke-width": (0.8 + (j / top) * 4.5).toFixed(2), pathLength: 1 });
        path.style.animationDelay = `${0.32 + i * 0.03}s`;
        return path;
      }));
      const n = me.n;
      const back = el("button", { type: "button", textContent: c.netBack });
      back.addEventListener("click", (event) => { event.stopPropagation(); net.focus = null; net.morph(); });
      info.replaceChildren(el("b", { textContent: n[en() ? "en" : "zh"] }), el("span", { textContent: `${n.kind === "org" ? c.org : c.country} · ${c.mentions(num(n.articles))} · ${topicName(n.topic)}` }), back);
    }
    net = { focus: null, raf: 0, keys: (event) => { if (event.key === "Escape" && net.focus && box.contains(document.activeElement)) { net.focus = null; net.morph(); } }, morph() {
      cancelAnimationFrame(net.raf);
      hideTip();
      const tg = targets(), dur = still() ? 0 : net.focus ? 980 : 1120, start = performance.now(), from = items.map((item) => ({ x: item.x, y: item.y, r: item.r, o: item.o })), c0 = curve;
      const ends = items.map((item) => tg.at(item));
      plot.classList.add("is-moving");
      plot.classList.toggle("is-ego", !!net.focus);
      plot.classList.toggle("is-ring", !net.focus && state.net === "ring");
      info.hidden = !net.focus;
      drawSpokes(tg);
      const tick = (now) => {
        const p = dur ? clamp((now - start) / dur, 0, 1) : 1;
        items.forEach((item, i) => {
          const local = dur ? clamp(p * 1.22 - ((i * 7) % 45) * 0.0049, 0, 1) : 1, e = net.focus ? easeBack(easeInOut(local)) : easeInOut(local), to = ends[i], f = from[i];
          item.x = f.x + (to.x - f.x) * e; item.y = f.y + (to.y - f.y) * e; item.r = f.r + (to.r - f.r) * e; item.o = clamp(f.o + (to.o - f.o) * easeInOut(local), 0, 1);
        });
        curve = c0 + (tg.curve - c0) * easeInOut(p);
        paint();
        if (p < 1) { net.raf = requestAnimationFrame(tick); return; }
        placeLabels(tg);
        plot.classList.remove("is-moving");
      };
      net.raf = requestAnimationFrame(tick);
    } };
    addEventListener("keydown", net.keys);
    const legend = el("div", { className: "rc-legend" },
      el("span", {}, el("i", { style: "background:#c8372d" }), c.org),
      el("span", {}, el("i", { style: "background:#5b88b5" }), `${c.country}（${en() ? "colour = main topic" : "颜色为主要议题"}）`));
    card.append(el("div", { className: "rc-plot rc-plot-net" }, plot, info), legend);
    if (state.net === "ring") { curve = 0.86; }
    net.morph();
  }

  /* 7 ---------- topic co-occurrence matrix ---------- */
  function drawMatrix() {
    const c = t(), card = document.getElementById("topicMatrix");
    head(card, "07 · TOPIC CO-OCCURRENCE", c.matrix, c.matrixNote, toggle([["jaccard", c.jaccard], ["pairs", c.pairs]], state.matrix, (k) => { state.matrix = k; drawMatrix(); }));
    const ids = data.topics.map((x) => x.id), n = ids.length, { totals, pairs } = data.matrix;
    const pairOf = (i, j) => (i < j ? pairs[i][j] : pairs[j][i]);
    const jac = (i, j) => { const p = pairOf(i, j); return p / Math.max(1, totals[i] + totals[j] - p); };
    // on a phone: the rows keep their names (numbered), the columns carry the numbers only — at the plate's width, so
    // the type stays its size instead of shrinking with a 630px drawing
    const narrow = narrowOf(card);
    const label = (i) => (narrow ? clip(topicName(ids[i]), en() ? 22 : 14) : topicName(ids[i])), no = (i) => String(i + 1).padStart(2, "0");
    // room for the longest name (10px mono: ≈ 6px a Latin letter, 10px a Chinese character); column names turn 60°
    const longest = Math.max(...ids.map((id, i) => [...label(i)].length)) * (en() ? 6.1 : 10.2) + 10;
    const T = 8, L = Math.round(longest) + (narrow ? 18 : 0), S = narrow ? Math.max(9, Math.floor((widthOf(card) - 8 - L - 2) / n)) : 28, SH = narrow ? 21 : S;
    const W = narrow ? L + n * S + 2 : Math.round(L + n * S + longest * 0.5 + 8), H = narrow ? T + n * SH + 20 : Math.round(T + n * S + longest * 0.87 + 12);
    const plot = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: `rc-svg rc-matrix${narrow ? " rc-matrix-phone" : ""}`, role: "img" });
    let max = 0;
    for (let i = 0; i < n; i += 1) for (let j = 0; j < n; j += 1) if (i !== j) max = Math.max(max, state.matrix === "jaccard" ? jac(i, j) : pairOf(i, j));
    for (let i = 0; i < n; i += 1) {
      const row = svg("text", { x: L - 6, y: T + i * SH + SH / 2 + 4, "text-anchor": "end", class: "rc-axis" }); row.textContent = label(i); plot.append(row);
      if (narrow) {
        const mark = svg("text", { x: 0, y: T + i * SH + SH / 2 + 4, class: "rc-axis rc-axis-no" }); mark.textContent = no(i); plot.append(mark);
        const col = svg("text", { x: L + i * S + S / 2, y: T + n * SH + 13, "text-anchor": "middle", class: "rc-axis rc-axis-no" }); col.textContent = no(i); plot.append(col);
      } else {
        const col = svg("text", { x: 0, y: 0, class: "rc-axis", transform: `translate(${L + i * S + S / 2 + 4},${T + n * S + 6}) rotate(60)` }); col.textContent = topicName(ids[i]); plot.append(col);
      }
      for (let j = 0; j < n; j += 1) {
        const v = i === j ? null : state.matrix === "jaccard" ? jac(i, j) : pairOf(i, j);
        const k = v == null ? 0 : Math.sqrt(v / (max || 1));
        const rect = svg("rect", { x: L + j * S + (narrow ? 0.5 : 1), y: T + i * SH + 1, width: S - (narrow ? 1 : 2), height: SH - 2, rx: narrow ? 1 : 2,
          fill: v == null ? "#eef2f6" : `rgba(47, 95, 143, ${(0.06 + k * 0.94).toFixed(3)})`, class: "rc-cell" });
        if (v != null) {
          rect.addEventListener("pointermove", (event) => showTip(event, c.cell(topicName(ids[i]), topicName(ids[j]), num(pairOf(i, j)), jac(i, j).toFixed(3))));
          rect.addEventListener("pointerleave", hideTip);
        }
        plot.append(rect);
      }
    }
    card.append(el("div", { className: "rc-plot rc-plot-matrix" }, plot));
  }

  /* 10 ---------- policy timeline ---------- */
  function drawTimeline() {
    const c = t(), card = document.getElementById("policyTimeline");
    const search = el("input", { type: "search", placeholder: c.searchPh, value: state.q, autocomplete: "off" });
    const topics = el("select", {}, el("option", { value: "", textContent: c.topicAll }), ...data.topics.map((x) => el("option", { value: x.id, textContent: x[en() ? "en" : "zh"] })));
    topics.value = state.topic;
    const controls = el("div", { className: "rc-filters" }, el("label", {}, el("span", { textContent: c.search }), search), el("label", {}, el("span", { textContent: en() ? "Topic" : "议题" }), topics));
    head(card, "10 · POLICY TIMELINE", c.timeline, c.timelineNote, controls);
    const body = el("div", { className: "rc-timeline" });
    card.append(body);
    const render = () => {
      const q = state.q.toLowerCase();
      const events = data.timeline.filter((e) => (!state.topic || e.topics.includes(state.topic)) &&
        (!q || `${e.title} ${e.summary} ${e.quotes.join(" ")} ${e.actor_name?.zh} ${e.actor_name?.en} ${e.actor}`.toLowerCase().includes(q)));
      const all = data.timeline, t0 = Date.parse(all[0].date), t1 = Date.parse(all[all.length - 1].date) || t0 + 1;
      const W = 960, H = 74, L = 14, R = 14;
      const axis = svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-axisbar", role: "img" });
      axis.append(svg("line", { x1: L, x2: W - R, y1: 46, y2: 46, class: "rc-grid" }));
      for (let yr = new Date(t0).getUTCFullYear(); yr <= new Date(t1).getUTCFullYear(); yr += 1) {
        const tx = L + ((Date.UTC(yr, 0, 1) - t0) / (t1 - t0 || 1)) * (W - L - R);
        if (tx < L || tx > W - R) continue;
        axis.append(svg("line", { x1: tx, x2: tx, y1: 42, y2: 50, class: "rc-tick" }));
        const lab = svg("text", { x: tx, y: 66, "text-anchor": "middle", class: "rc-axis" }); lab.textContent = yr; axis.append(lab);
      }
      const list = el("ol", { className: "rc-events" });
      events.forEach((e, i) => {
        const ex = L + ((Date.parse(e.date) - t0) / (t1 - t0 || 1)) * (W - L - R);
        const dot = svg("circle", { cx: ex, cy: 46 - ((i % 4) * 9), r: 4.5, fill: COLORS[e.topics[0]] || "#587088", class: "rc-event-dot" });
        const item = el("li", { className: "rc-event" });
        dot.addEventListener("click", () => { item.querySelector("details").open = true; item.scrollIntoView({ block: "nearest", behavior: "smooth" }); });
        dot.addEventListener("pointermove", (event) => showTip(event, `${e.date} · ${e.actor_name?.[en() ? "en" : "zh"] || e.actor} · ${e.title}`));
        dot.addEventListener("pointerleave", hideTip);
        axis.append(dot);
        const details = el("details", {},
          el("summary", {}, el("time", { textContent: e.date }), el("b", { textContent: e.actor_name?.[en() ? "en" : "zh"] || e.actor || "" }),
            el("span", { textContent: e.title || "" }), el("em", {}, ...e.topics.map((k) => el("i", { style: `--rc:${COLORS[k]}`, textContent: topicName(k) })))),
          el("div", {}, e.summary ? el("p", { textContent: e.summary }) : null, ...e.quotes.map((x) => el("blockquote", { textContent: x })),
            e.url ? el("a", { href: e.url, target: "_blank", rel: "noopener noreferrer", textContent: c.source }) : null));
        item.append(details);
        list.append(item);
      });
      body.replaceChildren(el("div", { className: "rc-plot" }, axis), el("p", { className: "rc-count", textContent: c.events(num(events.length)) }),
        events.length ? list : el("p", { className: "rc-count", textContent: c.none }));
    };
    let timer = 0;
    search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { state.q = search.value.trim(); render(); }, 200); });
    topics.addEventListener("change", () => { state.topic = topics.value; render(); });
    render();
  }

  function drawAll() {
    if (!data) return;
    const c = t(), ys = data.years, all = data.corpus;
    const n = all?.records ?? ys.reduce((s, y) => s + y.articles, 0); // the span as the home page gives it (from coverage_from)
    document.getElementById("researchChartsHead").replaceChildren(el("p", { className: "overline", textContent: c.overline }),
      el("h3", { className: "rc-title", textContent: c.title })); // the lede sentence under it was removed (2026-11-11, user)
    drawTrend(); drawClusters(); drawSpectrum(); drawMovers(); drawNetwork(); drawCountries(); drawMatrix(); drawCalendar(); drawFlows(); drawTimeline();
    if (!tip.isConnected) box.append(tip);
    api.extra?.draw();
  }
  // what the seven further charts (analysis-more.js, 2026-11-11) share with these: the data, the palette and the helpers
  const api = window.GreenAnalysis = { COLORS, el, svg, num, en, head, toggle, showTip, hideTip, widthOf, topicName, clamp, still, tintOf, get data() { return data; }, extra: window.GreenAnalysis?.extra || null };
  const jump = () => {
    const id = decodeURIComponent(location.hash.slice(1));
    if (data && (id === "policyTimeline" || id === "researchCharts")) requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ block: "start" }));
  };

  // the manifest (one early request shared with downloads.js / textdb.js) and then the chart data (≈ 15 KB) are fetched
  // at load, so the charts are drawn as soon as the page is opened, also over a slow link (2026-11-07)
  const dataReady = (window.GreenManifest ||= fetch("downloads/manifest.json", { priority: "high" })
    .then((r) => (r.ok ? r.json() : null)).catch(() => null))
    .then((manifest) => (manifest?.analytics?.path ? fetch(`downloads/${manifest.analytics.path}`, { priority: "high" }).then((r) => (r.ok ? r.json() : null)) : null))
    .catch(() => null);

  // the key figures and summary charts below the research charts (app.js), in the shape of corpus_analytics.json, one per
  // language; the old country × topic heatmap gets the database's figures too (cop31.css hides it as the same figures as
  // the countries × topics matrix above)
  function corpusView(d, lang) {
    const name = (rows) => (rows || []).map((x) => ({ name: x[lang] || x.name || x.id, count: x.count }));
    const cats = d.topics.map((x, i) => [x, d.matrix?.totals?.[i] || 0]).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([x]) => x);
    const rows = (d.country_topics || []).slice(0, 8);
    return {
      ...d.corpus, notes: COPY.zh.corpusNotes,
      top_topics: name(d.corpus.top_topics), top_countries: name(d.corpus.top_countries),
      continents: name(d.corpus.continents), top_sources: name(d.corpus.top_sources),
      country_topic_matrix: { countries: rows.map((r) => r[lang]), topics: cats.map((x) => x[lang]),
        cells: rows.flatMap((r) => cats.map((x) => ({ country: r[lang], topic: x[lang], count: r.topics?.[x.id] || 0 }))) },
    };
  }
  page.classList.add("corpus-wait");
  const settle = () => page.classList.remove("corpus-wait");
  const giveUp = setTimeout(settle, 12000); // a stalled request: the original figures meanwhile, the database's when in
  dataReady.then((d) => {
    clearTimeout(giveUp);
    if (d?.corpus?.records && d.topics?.length) {
      window.GreenCorpus = { zh: corpusView(d, "zh"), en: corpusView(d, "en"), archive: d.corpus.archive_cumulative };
      page.classList.add("corpus-ready");
      // app.js draws them once its own files are in; if it already has, they are drawn again
      if (document.querySelector("#analyticsKpis > .analytics-kpi, #analyticsKpis > .empty")) {
        try { window.renderAnalytics?.(); window.renderSiteMetrics?.(); } catch (error) { console.error("statistics", error); }
      }
    }
    settle();
  });

  let started = false;
  async function start() {
    if (started) return;
    started = true;
    data = await dataReady;
    if (!data?.years?.length) { data = null; return; }
    box.hidden = false;
    drawAll();
    jump();
    new MutationObserver(drawAll).observe(root, { attributes: true, attributeFilter: ["lang"] });
    let width = box.clientWidth;
    new ResizeObserver(() => { if (Math.abs(box.clientWidth - width) > 40) { width = box.clientWidth; drawTrend(); drawClusters(); drawMovers(); drawNetwork(); drawCountries(); drawFlows(); drawMatrix(); api.extra?.draw(true); } }).observe(box);
  }
  new IntersectionObserver((entries, observer) => { if (entries.some((e) => e.isIntersecting)) { observer.disconnect(); start(); } }).observe(page);
  addEventListener("cop31:page", (event) => { if (event.detail?.page === "analytics") { start().then(jump); setTimeout(jump, 400); } });
  addEventListener("hashchange", () => setTimeout(jump, 300));
})();
