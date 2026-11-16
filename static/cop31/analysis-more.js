/* COP31 · 科研分析 — seven further charts (2026-11-11, user: 为数据统计页增加更多有科研意义的、图像适宜美观、动效流畅好看的
   数据可视化). They sit among the ten of analysis.js (same data file, palette and helpers: window.GreenAnalysis) and are
   drawn by its drawAll / resize:
   · topicRanks — the 14 categories' rank by year (a bump chart: who overtakes whom, which the stacked shares hide);
   · topicQuadrant — the 83 subcategories by share and growth (a strategic diagram: emerging / rising / cooling / fading);
   · agendaDiversity — the effective number of categories, subcategories and countries per year (exp of the Shannon
     entropy: does the agenda concentrate or spread?);
   · coverageMap — mentions by country on an Equal Earth map, or a topic's lean per country (assets/countries-110m.json);
   · countrySimilarity — the 30 main countries placed by the similarity of their topic mix (PCA of centred log-ratios);
   · continentProfiles — each continent's lean towards the 14 categories (radar small multiples);
   · copWindow — reporting in the 45 days before and after the first day of a COP, against the year's daily mean (an
     event study: median and interquartile band over the sessions).
   Each card enters once when it scrolls into view (lines draw, marks rise, in step); prefers-reduced-motion: no motion.
   Plain SVG, no library; texts follow <html lang>. Charts whose data the file lacks stay hidden. */
(() => {
  "use strict";
  const box = document.getElementById("researchCharts");
  if (!box) return;
  let G = null; // window.GreenAnalysis, set by analysis.js before it calls draw()
  const $ = (id) => document.getElementById(id);
  const state = { mapTopic: "", cop: "all" };
  const COPY = {
    zh: {
      ranks: "议题位次变迁", ranksNote: "14 个大类议题每年按主议题报道占比排出的名次。占比图里看不清的「谁超过了谁」在这里一目了然；名次只反映报道结构，不等于议题重要性。悬停一条线查看该议题历年名次与占比。",
      rankTip: (name, y, r, p) => `${y} · ${name}：第 ${r} 位，占 ${p}%`,
      quadrant: "议题战略象限", quadrantNote: (a, b) => `83 个小类议题按近期占比（横轴，对数）与相对早期的增长倍数（纵轴，${a} → ${b}）分布，气泡大小为两期报道量。右上为升温中的主流议题，左上为新兴议题，右下为降温的主流议题，左下为边缘回落。样本过少的小类未画出。`,
      qEmerging: "新兴", qRising: "主流 · 升温", qCooling: "主流 · 降温", qFading: "边缘 · 回落", qShare: "近期占比", qGrowth: "增长倍数",
      quadTip: (name, parent, p, g, n) => `${name}（${parent}）：近期占 ${p}%，为早期的 ${g} 倍，共 ${n} 篇`,
      diversity: "议程多样性指数", diversityNote: "每年报道在议题和国家上的分散程度，用「有效数量」表示：香农熵的指数，相当于多少个受到同等关注的议题或国家。数值上升说明议程趋于多元，下降说明注意力向少数议题或国家集中。",
      divCats: (k) => `有效议题数 · 大类（共 ${k}）`, divSubs: (k) => `有效议题数 · 小类（共 ${k}）`, divCountries: "有效国家数",
      divTip: (y, a, b, c) => `${y}：大类 ${a} · 小类 ${b}${c ? ` · 国家 ${c}` : ""}`,
      map: "全球报道关注度地图", mapNote: "各国在报道中被提及的次数（对数色阶）。选择一个议题后，颜色改为该议题在该国议题构成中的比重相对全球平均的倍数：红色高于平均、蓝色低于平均。国家标签为文本提及，不等于报道立场；提及过少的国家留灰。",
      mapTopic: "议题", mapAll: "全部议题（提及量）", mapFew: "少", mapMany: "多", mapBelow: "低于平均", mapAbove: "高于平均", mapNone: "数据不足",
      mapTip: (name, n, p) => `${name}：${n} 篇报道提及，占 ${p}%`, mapLeanTip: (name, topic, n, p, l) => `${name} × ${topic}：${n} 篇 · 占该国 ${p}% · 为全球平均的 ${l} 倍`,
      similarity: "国家议题画像相似图", similarityNote: "把 30 个被提及最多的国家按「议题构成」降到二维（中心化对数比的主成分分析）：两点越近，报道这两个国家时涉及的议题结构越相似。颜色是该国最突出的议题，大小为报道量。它描述的是报道框架，不是国家立场。悬停查看最相近的国家。",
      simAxis: (neg, pos, p) => `← ${neg}　　${pos} →（解释 ${p}% 差异）`, simTip: (name, tops, near) => `${name} · 突出议题：${tops} · 最相近：${near}`,
      continents: "各大洲议题画像", continentsNote: "提及各大洲国家的报道在 14 个大类议题上的偏重：每条辐线是一个议题，离中心越远，该议题在该洲的比重越高于全球平均（虚线圈为平均水平）。可用来比较区域议程的差异；洲别由国家标签映射，跨洲报道会重复计入。",
      contLean: "偏重", contTip: (a, b, n, p, l) => `${a} × ${b}：${n} 篇 · 占 ${p}% · 为全球平均的 ${l} 倍`, contArticles: (n) => `${n} 篇`,
      cop: "COP 会议窗口", copNote: (n, from, to) => `以每届 COP 开幕日为第 0 天，前后各 45 天的每日报道量（7 日滑动平均，去掉周内波动）相对当年日均水平的倍数（事件研究）：粗线为 ${n} 届（${from}–${to}）的中位数，色带为四分位区间，细线为各届。可看出关注度何时起势、会后多久回落。「谈判议题」只统计主议题为全球气候治理机制与国际谈判的报道。`,
      copAll: "全部报道", copTalks: "谈判议题", copDay: (d) => (d === 0 ? "开幕日" : d > 0 ? `开幕后第 ${d} 天` : `开幕前 ${-d} 天`), copSession: "会期",
      copTip: (day, m, a, b) => `${day}：中位数 ${m} 倍（四分位 ${a}–${b}）`, copLine: (n, city, y, day, v) => `COP${n} ${city} ${y} · ${day}：${v} 倍`, copAxis: "相对当年日均",
    },
    en: {
      ranks: "Topics by rank", ranksNote: "The 14 topic categories ranked each year by their share of articles (primary topic). Who overtakes whom, which stacked shares hide, shows at once; a rank describes reporting, not a topic's importance. Point at a line for its ranks and shares.",
      rankTip: (name, y, r, p) => `${y} · ${name}: rank ${r}, ${p}%`,
      quadrant: "Strategic diagram of topics", quadrantNote: (a, b) => `The 83 subcategories by recent share (across, log scale) and growth against the earlier period (up, ${a} to ${b}); bubble size is the articles of both periods. Top right: mainstream and rising; top left: emerging; bottom right: mainstream and cooling; bottom left: fading. Subcategories with too few articles are left out.`,
      qEmerging: "Emerging", qRising: "Mainstream · rising", qCooling: "Mainstream · cooling", qFading: "Marginal · fading", qShare: "Recent share", qGrowth: "Growth",
      quadTip: (name, parent, p, g, n) => `${name} (${parent}): ${p}% recently, ${g}× the earlier share, ${n} articles`,
      diversity: "Agenda diversity", diversityNote: "How widely each year's reporting spreads over topics and countries, as an effective number: the exponential of the Shannon entropy, the number of equally covered topics or countries it equals. A rising value means a broader agenda, a falling one attention gathering on a few.",
      divCats: (k) => `Effective categories (of ${k})`, divSubs: (k) => `Effective subcategories (of ${k})`, divCountries: "Effective countries",
      divTip: (y, a, b, c) => `${y}: categories ${a} · subcategories ${b}${c ? ` · countries ${c}` : ""}`,
      map: "Where the reporting looks", mapNote: "Mentions of each country (log colour scale). With a topic chosen, the colour is that topic's weight in the country's mix of topics against the world average: red above, blue below. Country labels are text mentions, not positions; countries with too few mentions stay grey.",
      mapTopic: "Topic", mapAll: "All topics (mentions)", mapFew: "few", mapMany: "many", mapBelow: "below average", mapAbove: "above average", mapNone: "too little data",
      mapTip: (name, n, p) => `${name}: mentioned in ${n} articles, ${p}%`, mapLeanTip: (name, topic, n, p, l) => `${name} × ${topic}: ${n} articles · ${p}% of the country's · ${l}× the world average`,
      similarity: "Countries by topic profile", similarityNote: "The 30 most mentioned countries placed by their mix of topics (principal components of centred log-ratios): the closer two points, the more alike the topics reported with them. Colour is a country's most distinctive topic, size its articles. It describes how countries are reported, not their positions. Point at one for its nearest neighbours.",
      simAxis: (neg, pos, p) => `← ${neg}    ${pos} → (${p}% of the variance)`, simTip: (name, tops, near) => `${name} · distinctive: ${tops} · nearest: ${near}`,
      continents: "Continents by topic profile", continentsNote: "The lean of articles mentioning each continent's countries towards the 14 categories: one spoke per topic, the further out the more that topic weighs there against the world average (the dashed ring). Continents come from country labels; an article naming several is counted in each.",
      contLean: "Leans to", contTip: (a, b, n, p, l) => `${a} × ${b}: ${n} articles · ${p}% · ${l}× the world average`, contArticles: (n) => `${n} articles`,
      cop: "The COP window", copNote: (n, from, to) => `Daily articles (a 7-day mean, to take out the weekly cycle) in the 45 days before and after the first day of a COP, as multiples of that year's daily mean (an event study): the heavy line is the median of ${n} sessions (${from}–${to}), the band the interquartile range, thin lines the sessions. It shows when attention builds and how fast it falls away. "Negotiations" counts articles whose primary category is governance and negotiations.`,
      copAll: "All articles", copTalks: "Negotiations", copDay: (d) => (d === 0 ? "opening day" : d > 0 ? `day +${d}` : `day ${d}`), copSession: "session",
      copTip: (day, m, a, b) => `${day}: median ${m}× (quartiles ${a}–${b})`, copLine: (n, city, y, day, v) => `COP${n} ${city} ${y} · ${day}: ${v}×`, copAxis: "× the year's daily mean",
    },
  };
  const t = () => COPY[G.en() ? "en" : "zh"];
  const lang = () => (G.en() ? "en" : "zh");

  // ---------- entrance: a card's marks appear once, when it scrolls into view ----------
  const seen = new IntersectionObserver((entries) => entries.forEach((entry) => {
    if (!entry.isIntersecting) return;
    entry.target.classList.add("rc-in");
    seen.unobserve(entry.target);
  }), { threshold: 0.16 });
  const arm = (card) => { card.classList.add("rc-more"); if (!card.classList.contains("rc-in")) seen.observe(card); };
  const later = (node, ms) => { node.style.setProperty("--d", `${Math.round(ms)}ms`); return node; };
  const text = (attrs, content) => { const node = G.svg("text", attrs); node.textContent = content; return node; };
  const mixRgb = (a, b, k) => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * k)).join(" ")})`;
  const entropyNumber = (counts) => { const sum = counts.reduce((s, n) => s + n, 0); return sum ? Math.exp(-counts.reduce((s, n) => (n ? s + (n / sum) * Math.log(n / sum) : s), 0)) : 0; };
  const trendYears = () => { const D = G.data; return D.years.filter((y) => !D.trend_from || y.year >= D.trend_from); };
  const smooth = (points) => points.map(([x, y], i) => { if (!i) return `M${x},${y}`; const [px, py] = points[i - 1], mx = (px + x) / 2; return `C${mx},${py} ${mx},${y} ${x},${y}`; }).join("");

  /* ---------- topics by rank ---------- */
  function drawRanks() {
    const c = t(), card = $("topicRanks"), D = G.data;
    if (!card) return;
    const years = trendYears(), ids = D.topics.map((x) => x.id);
    if (years.length < 3) { card.hidden = true; return; }
    G.head(card, "00 · TOPIC RANKS", c.ranks, c.ranksNote);
    arm(card);
    const W = Math.max(600, G.widthOf(card) - 8), L = 30, R = G.en() ? 300 : 250, T = 12, RH = 25, H = T + ids.length * RH + 28;
    const every = [1, 2, 5, 10].find((k) => ((W - L - R) / (years.length - 1)) * k >= 34) || 10;
    const x = (i) => L + (i / (years.length - 1)) * (W - L - R), y = (r) => T + r * RH + RH / 2;
    const table = years.map((yr) => {
      const total = ids.reduce((s, k) => s + (yr.primary[k] || 0), 0) || 1, order = [...ids].sort((a, b) => (yr.primary[b] || 0) - (yr.primary[a] || 0));
      return Object.fromEntries(order.map((k, r) => [k, { r, share: (yr.primary[k] || 0) / total }]));
    });
    const plot = G.svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-ranks", role: "img" });
    ids.forEach((_, r) => { plot.append(G.svg("line", { x1: L, x2: W - R, y1: y(r), y2: y(r), class: "rc-grid rc-grid-soft" }), text({ x: L - 12, y: y(r) + 3.5, "text-anchor": "end", class: "rc-axis" }, r + 1)); });
    years.forEach((yr, i) => { if (!((years.length - 1 - i) % every)) plot.append(text({ x: x(i), y: H - 8, "text-anchor": "middle", class: "rc-axis" }, yr.year)); });
    const lastRank = (id) => table[table.length - 1][id].r;
    [...ids].sort((a, b) => lastRank(b) - lastRank(a)).forEach((id) => {
      const g = G.svg("g", { class: "rc-rank" }), points = years.map((_, i) => [x(i), y(table[i][id].r)]), d = smooth(points), order = lastRank(id);
      g.style.setProperty("--rc", G.COLORS[id]);
      g.append(G.svg("path", { d, class: "rc-rank-hit" }), later(G.svg("path", { d, class: "rc-rank-line rc-a-draw", pathLength: 1 }), order * 55));
      points.forEach(([px, py], i) => g.append(later(G.svg("circle", { cx: px, cy: py, r: 3.1, class: "rc-rank-dot rc-a-fade" }), order * 55 + 500 + (i / years.length) * 900)));
      const end = table[table.length - 1][id];
      g.append(later(text({ x: W - R + 12, y: y(end.r) + 4, class: "rc-rank-name rc-a-fade" }, `${G.topicName(id)}  ${(end.share * 100).toFixed(1)}%`), order * 55 + 1100));
      g.addEventListener("pointermove", (event) => {
        const i = G.clamp(Math.round((((event.clientX - plot.getBoundingClientRect().left) * W) / plot.clientWidth - L) / ((W - L - R) / (years.length - 1))), 0, years.length - 1);
        G.showTip(event, c.rankTip(G.topicName(id), years[i].year, table[i][id].r + 1, (table[i][id].share * 100).toFixed(1)));
      });
      g.addEventListener("pointerenter", () => { plot.classList.add("is-focus"); g.classList.add("is-on"); plot.append(g); });
      g.addEventListener("pointerleave", () => { plot.classList.remove("is-focus"); g.classList.remove("is-on"); G.hideTip(); });
      plot.append(g);
    });
    card.append(G.el("div", { className: "rc-plot" }, plot));
  }

  /* ---------- strategic diagram of the subcategories ---------- */
  function drawQuadrant() {
    const c = t(), card = $("topicQuadrant"), D = G.data;
    if (!card) return;
    if (!D.subcategories || D.years.length < 10) { card.hidden = true; return; }
    const full = D.years.slice(0, -1), last = Number(full[full.length - 1].year), recentFrom = last - 2, baseTo = recentFrom - 4, baseFrom = baseTo - 2; // the windows of the rising / falling chart
    const span = (a, b) => { const out = {}; let sum = 0; for (const y of D.years) if (Number(y.year) >= a && Number(y.year) <= b) for (const [k, n] of Object.entries(y.sub || {})) { out[k] = (out[k] || 0) + n; sum += n; } return { out, sum: sum || 1 }; };
    const A = span(baseFrom, baseTo), B = span(recentFrom, last);
    G.head(card, "00 · STRATEGIC DIAGRAM", c.quadrant, c.quadrantNote(`${baseFrom}–${baseTo}`, `${recentFrom}–${last}`));
    arm(card);
    const rows = D.subcategories.map((s) => ({ s, na: A.out[s.id] || 0, nb: B.out[s.id] || 0 })).filter((r) => r.na >= 8 && r.nb >= 8 && r.na + r.nb >= 60)
      .map((r) => ({ ...r, a: r.na / A.sum, b: r.nb / B.sum, n: r.na + r.nb })).map((r) => ({ ...r, g: G.clamp(Math.log2(r.b / r.a), -3, 3) }));
    if (rows.length < 8) { card.hidden = true; return; }
    const W = Math.max(420, G.widthOf(card) - 8), H = Math.round(G.clamp(W * 0.8, 340, 470)), L = 50, R = 16, T = 16, Bm = 40;
    const lo = Math.log10(Math.min(...rows.map((r) => r.b)) * 0.8), hi = Math.log10(Math.max(...rows.map((r) => r.b)) * 1.25);
    const x = (v) => L + ((Math.log10(v) - lo) / (hi - lo)) * (W - L - R), y = (g) => T + ((3.2 - g) / 6.4) * (H - T - Bm);
    const maxN = Math.max(...rows.map((r) => r.n)), radius = (n) => 4 + Math.sqrt(n / maxN) * 19;
    const median = [...rows].sort((p, q) => p.b - q.b)[Math.floor(rows.length / 2)].b;
    const plot = G.svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-quadrant", role: "img" });
    for (const g of [-3, -2, -1, 0, 1, 2, 3]) plot.append(G.svg("line", { x1: L, x2: W - R, y1: y(g), y2: y(g), class: g ? "rc-grid rc-grid-soft" : "rc-zero" }), text({ x: L - 8, y: y(g) + 3.5, "text-anchor": "end", class: "rc-axis" }, g === 0 ? "×1" : g > 0 ? `×${2 ** g}` : `÷${2 ** -g}`));
    for (const p of [0.001, 0.003, 0.01, 0.03, 0.1, 0.3]) if (Math.log10(p) > lo && Math.log10(p) < hi) plot.append(G.svg("line", { x1: x(p), x2: x(p), y1: T, y2: H - Bm, class: "rc-grid rc-grid-soft" }), text({ x: x(p), y: H - Bm + 15, "text-anchor": "middle", class: "rc-axis" }, `${p * 100}%`));
    plot.append(G.svg("line", { x1: x(median), x2: x(median), y1: T, y2: H - Bm, class: "rc-zero rc-dashed" }));
    plot.append(text({ x: W - R, y: H - 6, "text-anchor": "end", class: "rc-cover" }, `${c.qShare} →`), text({ x: 12, y: T + 4, class: "rc-cover", transform: `rotate(-90 12 ${T + 4})`, "text-anchor": "end" }, `${c.qGrowth} →`));
    for (const [label, px, py, anchor] of [[c.qEmerging, L + 8, T + 14, "start"], [c.qRising, W - R - 8, T + 14, "end"], [c.qFading, L + 8, H - Bm - 9, "start"], [c.qCooling, W - R - 8, H - Bm - 9, "end"]]) plot.append(text({ x: px, y: py, "text-anchor": anchor, class: "rc-quad-corner" }, label));
    const placed = [[L, T, 96], [W - R - 150, T, 150], [L, H - Bm - 22, 110], [W - R - 150, H - Bm - 22, 150]], parents = Object.fromEntries(D.topics.map((p) => [p.id, p])); // the corner captions
    const marks = rows.sort((p, q) => q.n - p.n).map((r, i) => {
      const cx = x(r.b), cy = y(r.g), rr = radius(r.n), parent = r.s.parent || r.s.id.slice(0, 3);
      const dot = later(G.svg("circle", { cx, cy, r: rr, fill: G.COLORS[parent] || "#8899aa", class: "rc-bubble rc-a-pop" }), 120 + i * 14);
      dot.addEventListener("pointermove", (event) => G.showTip(event, c.quadTip(r.s[lang()], parents[parent]?.[lang()] || parent, (r.b * 100).toFixed(2), (r.b / r.a).toFixed(2), G.num(r.n))));
      dot.addEventListener("pointerleave", G.hideTip);
      plot.append(dot);
      return { r, cx, cy, rr, weight: Math.abs(r.g) * 0.9 + (Math.log10(r.b) - lo) / (hi - lo) * 2 };
    });
    // names for the points that stand out most, where they fit
    marks.sort((p, q) => q.weight - p.weight).slice(0, 26).forEach((m, i) => {
      const name = m.r.s[lang()], w = name.length * (G.en() ? 5.6 : 11) + 6, right = m.cx + m.rr + 4 + w < W - R, bx = right ? m.cx + m.rr + 4 : m.cx - m.rr - 4 - w, by = m.cy - 7;
      if (bx < L || placed.some((b) => bx < b[0] + b[2] && bx + w > b[0] && by < b[1] + 15 && by + 15 > b[1])) return;
      placed.push([bx, by, w]);
      plot.append(later(text({ x: right ? bx : bx + w, y: m.cy + 3.5, "text-anchor": right ? "start" : "end", class: "rc-bubble-name rc-a-fade" }, name), 700 + i * 30));
    });
    card.append(G.el("div", { className: "rc-plot" }, plot));
  }

  /* ---------- agenda diversity: effective numbers per year ---------- */
  function drawDiversity() {
    const c = t(), card = $("agendaDiversity"), D = G.data;
    if (!card) return;
    const years = trendYears(), ids = D.topics.map((x) => x.id);
    if (years.length < 3) { card.hidden = true; return; }
    G.head(card, "00 · AGENDA DIVERSITY", c.diversity, c.diversityNote);
    arm(card);
    const series = [
      { label: c.divCats(ids.length), color: "#2f5f8f", values: years.map((y) => entropyNumber(ids.map((k) => y.primary[k] || 0))) },
      { label: c.divSubs(D.subtopics || (D.subcategories || []).length), color: "#2f7d6d", values: years.map((y) => entropyNumber(Object.values(y.sub || {}))) },
      ...(years.some((y) => y.country_effective) ? [{ label: c.divCountries, color: "#c8372d", values: years.map((y) => y.country_effective || 0) }] : []),
    ];
    const W = Math.max(380, G.widthOf(card) - 8), L = 40, R = 46, PH = 96, GAP = 22, T = 6, H = T + series.length * (PH + GAP) + 14;
    const x = (i) => L + (i / (years.length - 1)) * (W - L - R), every = [1, 2, 5, 10].find((k) => ((W - L - R) / (years.length - 1)) * k >= 36) || 10;
    const plot = G.svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-diversity", role: "img" });
    const defs = G.svg("defs"); plot.append(defs);
    const guide = G.svg("line", { x1: 0, x2: 0, y1: T, y2: H - 18, class: "rc-guide", opacity: 0 }), focus = [];
    series.forEach((s, k) => {
      const top = T + k * (PH + GAP) + 16, bottom = top + PH - 16, min = Math.min(...s.values), max = Math.max(...s.values), pad = (max - min) * 0.18 || 1;
      const y = (v) => bottom - ((v - (min - pad)) / (max - min + 2 * pad)) * (bottom - top), points = s.values.map((v, i) => [x(i), y(v)]), d = smooth(points);
      const id = `rc-div-${k}`, gradient = G.svg("linearGradient", { id, x1: 0, y1: 0, x2: 0, y2: 1 });
      gradient.append(G.svg("stop", { offset: 0, "stop-color": s.color, "stop-opacity": 0.2 }), G.svg("stop", { offset: 1, "stop-color": s.color, "stop-opacity": 0 }));
      defs.append(gradient);
      plot.append(text({ x: L, y: top - 6, class: "rc-panel-label" }, s.label));
      for (const v of [min, max]) plot.append(G.svg("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "rc-grid rc-grid-soft" }), text({ x: L - 6, y: y(v) + 3.5, "text-anchor": "end", class: "rc-axis" }, v.toFixed(1)));
      plot.append(later(G.svg("path", { d: `${d}L${x(years.length - 1)},${bottom}L${x(0)},${bottom}Z`, fill: `url(#${id})`, class: "rc-a-fade" }), 500 + k * 220));
      plot.append(later(G.svg("path", { d, stroke: s.color, class: "rc-line rc-a-draw", pathLength: 1 }), k * 220));
      plot.append(later(G.svg("circle", { cx: x(years.length - 1), cy: y(s.values[s.values.length - 1]), r: 3.6, fill: s.color, class: "rc-a-pop" }), 1200 + k * 220));
      plot.append(later(text({ x: x(years.length - 1) + 8, y: y(s.values[s.values.length - 1]) + 4, class: "rc-end-value rc-a-fade", fill: s.color }, s.values[s.values.length - 1].toFixed(1)), 1300 + k * 220));
      const dot = G.svg("circle", { r: 4, fill: "#fff", stroke: s.color, "stroke-width": 2, opacity: 0 });
      plot.append(dot); focus.push({ dot, y, s });
    });
    years.forEach((yr, i) => { if (!((years.length - 1 - i) % every)) plot.append(text({ x: x(i), y: H - 4, "text-anchor": "middle", class: "rc-axis" }, yr.year)); });
    plot.append(guide);
    const hit = G.svg("rect", { x: L, y: T, width: W - L - R, height: H - T - 18, fill: "transparent" });
    hit.addEventListener("pointermove", (event) => {
      const i = G.clamp(Math.round((((event.clientX - plot.getBoundingClientRect().left) * W) / plot.clientWidth - L) / ((W - L - R) / (years.length - 1))), 0, years.length - 1);
      guide.setAttribute("x1", x(i)); guide.setAttribute("x2", x(i)); guide.setAttribute("opacity", 1);
      focus.forEach((f) => { f.dot.setAttribute("cx", x(i)); f.dot.setAttribute("cy", f.y(f.s.values[i])); f.dot.setAttribute("opacity", 1); });
      G.showTip(event, c.divTip(years[i].year, series[0].values[i].toFixed(1), series[1].values[i].toFixed(1), series[2]?.values[i].toFixed(1)));
    });
    hit.addEventListener("pointerleave", () => { guide.setAttribute("opacity", 0); focus.forEach((f) => f.dot.setAttribute("opacity", 0)); G.hideTip(); });
    plot.append(hit);
    card.append(G.el("div", { className: "rc-plot" }, plot));
  }

  /* ---------- the world map ---------- */
  // ISO 3166 numeric → alpha-2 for the 174 coded shapes of assets/countries-110m.json (world-atlas)
  const ISO = "242FJ834TZ732EH124CA840US398KZ860UZ598PG360ID032AR152CL180CD706SO404KE729SD148TD332HT214DO643RU044BS238FK578NO304GL260TF626TL710ZA426LS484MX858UY076BR068BO604PE170CO591PA188CR558NI340HN222SV320GT084BZ862VE328GY740SR250FR218EC630PR388JM192CU716ZW072BW516NA686SN466ML478MR204BJ562NE566NG120CM768TG288GH384CI324GN624GW430LR694SL854BF140CF178CG266GA226GQ894ZM454MW508MZ748SZ024AO108BI376IL422LB450MG275PS270GM788TN012DZ400JO784AE634QA414KW368IQ512OM548VU116KH764TH418LA104MM704VN408KP410KR496MN356IN050BD064BT524NP586PK004AF762TJ417KG795TM364IR760SY051AM752SE112BY804UA616PL040AT348HU498MD642RO440LT428LV233EE276DE100BG300GR792TR008AL191HR756CH442LU056BE528NL620PT724ES372IE540NC090SB554NZ036AU144LK156CN380IT208DK826GB352IS031AZ268GE608PH458MY096BN705SI246FI703SK203CZ232ER392JP600PY887YE682SA010AQ196CY504MA818EG434LY231ET262DJ800UG646RW070BA807MK688RS499ME780TT728SS";
  const alpha2 = (id) => { const at = ISO.indexOf(String(id).padStart(3, "0")); return id == null || at < 0 || at % 5 ? null : ISO.slice(at + 3, at + 5); };
  // Equal Earth (Šavrič, Patterson, Jenny 2018): equal areas, so a colour is not flattered by a country's latitude
  const equalEarth = (lon, lat) => {
    const A1 = 1.340264, A2 = -0.081106, A3 = 0.000893, A4 = 0.003796, th = Math.asin((Math.sqrt(3) / 2) * Math.sin((lat * Math.PI) / 180)), t2 = th * th, t6 = t2 * t2 * t2;
    return [(((lon * Math.PI) / 180) * Math.cos(th)) / ((Math.sqrt(3) / 2) * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))), th * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))];
  };
  let world = null, worldLoading = null;
  function loadWorld() {
    worldLoading ||= (window.GreenLoad?.json("./assets/countries-110m.json") ?? fetch(new URL("./assets/countries-110m.json", document.baseURI)).then((r) => r.json())).then((topo) => {
      const [sx, sy] = topo.transform.scale, [tx, ty] = topo.transform.translate;
      const arcs = topo.arcs.map((arc) => { let px = 0, py = 0; return arc.map(([dx, dy]) => { px += dx; py += dy; return [px * sx + tx, py * sy + ty]; }); });
      const ring = (refs) => refs.flatMap((ref, i) => { const points = ref < 0 ? arcs[~ref].slice().reverse() : arcs[ref]; return i ? points.slice(1) : points; });
      // a ring that crosses the antimeridian (Russia, Fiji) is unwrapped into one piece and drawn twice, 360° apart;
      // the map's outline clips what falls outside
      const unwrap = (points) => { let shift = 0, crosses = false; const out = points.map(([lon, lat], i) => { if (i && Math.abs(lon - points[i - 1][0]) > 180) { shift += lon < points[i - 1][0] ? 360 : -360; crosses = true; } return [lon + shift, lat]; }); return crosses ? [out, out.map(([lon, lat]) => [lon - 360, lat]), out.map(([lon, lat]) => [lon + 360, lat])].filter((copy) => copy.some(([lon]) => lon > -180 && lon < 180)) : [points]; };
      world = topo.objects.countries.geometries.map((g) => ({ id: alpha2(g.id), name: g.properties?.name, polygons: (g.type === "Polygon" ? [g.arcs] : g.arcs).flatMap((polygon) => unwrap(ring(polygon[0])).map((outer) => [outer])) })).filter((shape) => shape.id !== "AQ");
      return world;
    }).catch(() => null);
    return worldLoading;
  }
  function drawMap() {
    const c = t(), card = $("coverageMap"), D = G.data;
    if (!card) return;
    if (!D.countries_all?.length) { card.hidden = true; return; }
    if (!world) { loadWorld().then((shapes) => { if (shapes) drawMap(); else card.hidden = true; }); if (!card.firstChild) card.hidden = false; return; }
    const ids = D.topics.map((x) => x.id), byId = new Map(D.countries_all.map((row) => [row.id, row]));
    const select = G.el("select", { ariaLabel: c.mapTopic }, G.el("option", { value: "", textContent: c.mapAll }), ...D.topics.map((x) => G.el("option", { value: x.id, textContent: x[lang()] })));
    select.value = state.mapTopic;
    const legend = G.el("div", { className: "rc-map-legend" });
    G.head(card, "00 · WHERE THE REPORTING LOOKS", c.map, c.mapNote, G.el("div", { className: "rc-filters rc-map-controls" }, G.el("label", {}, G.el("span", { textContent: c.mapTopic }), select), legend));
    arm(card);
    const W = Math.max(520, Math.min(1180, G.widthOf(card) - 8)), H = Math.round(W * 0.487), k = W / 5.42, project = (lon, lat) => { const [px, py] = equalEarth(lon, lat); return [W / 2 + px * k, H / 2 - py * k]; };
    const plot = G.svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-map", role: "img" });
    const edge = []; for (let lat = -90; lat <= 90; lat += 3) edge.push(project(-180, lat)); for (let lat = 90; lat >= -90; lat -= 3) edge.push(project(180, lat));
    const outline = `M${edge.map((p) => p.map((v) => v.toFixed(1)).join(",")).join("L")}Z`, clip = G.svg("clipPath", { id: "rc-map-clip" }), lands = G.svg("g", { "clip-path": "url(#rc-map-clip)" });
    clip.append(G.svg("path", { d: outline }));
    plot.append(clip, G.svg("path", { d: outline, class: "rc-map-sea" }));
    for (let lon = -150; lon <= 150; lon += 30) { const pts = []; for (let lat = -90; lat <= 90; lat += 5) pts.push(project(lon, lat).map((v) => v.toFixed(1)).join(",")); plot.append(G.svg("path", { d: `M${pts.join("L")}`, class: "rc-map-grat" })); }
    for (let lat = -60; lat <= 60; lat += 30) plot.append(G.svg("line", { x1: project(-180, lat)[0], x2: project(180, lat)[0], y1: project(0, lat)[1], y2: project(0, lat)[1], class: "rc-map-grat" }));
    const total = D.corpus?.country_tagged_records || D.countries_all[0].n, maxN = D.countries_all[0].n;
    const mixAll = ids.map((_, j) => D.countries_all.reduce((s, row) => s + row.t[j], 0)), mixSum = mixAll.reduce((s, n) => s + n, 0) || 1;
    const value = (row, j) => { const mine = row.t.reduce((s, n) => s + n, 0) || 1; return { n: row.t[j], share: row.t[j] / (row.n || 1), lift: (row.t[j] / mine) / (mixAll[j] / mixSum), mine }; };
    const shapes = world.map((shape) => {
      let west = 180;
      const d = shape.polygons.map((polygon) => polygon.map((points) => `M${points.map(([lon, lat]) => { if (lon >= -180) west = Math.min(west, lon); return project(lon, lat).map((v) => v.toFixed(1)).join(","); }).join("L")}Z`).join("")).join("");
      const path = later(G.svg("path", { d, class: "rc-map-land rc-a-fade" }), ((west + 180) / 360) * 900), row = byId.get(shape.id);
      path.addEventListener("pointermove", (event) => {
        const j = ids.indexOf(state.mapTopic), name = row ? row[lang()] : shape.name;
        if (!row) { G.showTip(event, `${name} · ${c.mapNone}`); return; }
        if (j < 0) G.showTip(event, c.mapTip(name, G.num(row.n), ((row.n / total) * 100).toFixed(1)));
        else { const v = value(row, j); G.showTip(event, c.mapLeanTip(name, G.topicName(state.mapTopic), G.num(v.n), (v.share * 100).toFixed(1), v.lift.toFixed(2))); }
      });
      path.addEventListener("pointerleave", G.hideTip);
      lands.append(path);
      return { path, row };
    });
    plot.append(lands);
    function paint() {
      const j = ids.indexOf(state.mapTopic);
      for (const { path, row } of shapes) {
        let fill = "#e2e8ee";
        if (row && j < 0) { const v = Math.log(row.n + 1) / Math.log(maxN + 1); fill = v < 0.55 ? mixRgb([226, 233, 241], [124, 158, 194], v / 0.55) : mixRgb([124, 158, 194], [28, 54, 88], (v - 0.55) / 0.45); }
        else if (row && j >= 0) { const v = value(row, j); if (v.mine >= 80) { const lean = G.clamp(Math.log2(Math.max(v.lift, 0.01)) / 1.4, -1, 1); fill = lean >= 0 ? mixRgb([238, 240, 243], [200, 55, 45], lean) : mixRgb([238, 240, 243], [47, 95, 143], -lean); } }
        path.style.fill = fill;
      }
      const bar = j < 0 ? "linear-gradient(90deg, rgb(226 233 241), rgb(124 158 194) 55%, rgb(28 54 88))" : "linear-gradient(90deg, rgb(47 95 143), rgb(238 240 243) 50%, rgb(200 55 45))";
      legend.replaceChildren(G.el("span", { textContent: j < 0 ? c.mapFew : c.mapBelow }), G.el("i", { style: `background:${bar}` }), G.el("span", { textContent: j < 0 ? c.mapMany : c.mapAbove }), G.el("i", { className: "rc-map-none" }), G.el("span", { textContent: c.mapNone }));
    }
    select.addEventListener("change", () => { state.mapTopic = select.value; paint(); });
    paint();
    card.append(G.el("div", { className: "rc-plot" }, plot));
  }

  /* ---------- countries by the similarity of their topic mix ---------- */
  function principal(X, dims) { // the leading eigenvectors of XᵀX by power iteration (X column-centred)
    const m = X[0].length, cov = Array.from({ length: m }, (_, a) => Array.from({ length: m }, (_, b) => X.reduce((s, row) => s + row[a] * row[b], 0) / (X.length - 1)));
    const trace = cov.reduce((s, row, i) => s + row[i], 0), out = [];
    for (let d = 0; d < dims; d += 1) {
      let v = Array.from({ length: m }, (_, i) => Math.sin(i * 1.7 + d + 1)), lambda = 0;
      for (let it = 0; it < 240; it += 1) { const w = cov.map((row) => row.reduce((s, c, i) => s + c * v[i], 0)); lambda = Math.hypot(...w) || 1; v = w.map((c) => c / lambda); }
      const big = v.reduce((best, c, i) => (Math.abs(c) > Math.abs(v[best]) ? i : best), 0); if (v[big] < 0) v = v.map((c) => -c);
      out.push({ v, share: lambda / (trace || 1) });
      for (let a = 0; a < m; a += 1) for (let b = 0; b < m; b += 1) cov[a][b] -= lambda * v[a] * v[b];
    }
    return out;
  }
  function drawSimilarity() {
    const c = t(), card = $("countrySimilarity"), D = G.data;
    if (!card) return;
    const rows = D.country_topics || [];
    if (rows.length < 8) { card.hidden = true; return; }
    G.head(card, "00 · COUNTRIES BY TOPIC PROFILE", c.similarity, c.similarityNote);
    arm(card);
    const ids = D.topics.map((x) => x.id);
    let X = rows.map((row) => { const v = ids.map((id) => Math.log((row.topics[id] || 0) + 0.5)), mean = v.reduce((s, a) => s + a, 0) / v.length; return v.map((a) => a - mean); });
    const means = ids.map((_, j) => X.reduce((s, row) => s + row[j], 0) / X.length);
    X = X.map((row) => row.map((a, j) => a - means[j]));
    const [p1, p2] = principal(X, 2), score = X.map((row) => [row.reduce((s, a, j) => s + a * p1.v[j], 0), row.reduce((s, a, j) => s + a * p2.v[j], 0)]);
    const W = Math.max(400, G.widthOf(card) - 8), H = Math.round(G.clamp(W * 0.82, 340, 480)), pad = 46, B = 34;
    const ext = (k) => { const vals = score.map((s) => s[k]); return [Math.min(...vals), Math.max(...vals)]; }, [x0, x1] = ext(0), [y0, y1] = ext(1);
    const x = (v) => pad + ((v - x0) / (x1 - x0 || 1)) * (W - 2 * pad), y = (v) => H - B - 26 - ((v - y0) / (y1 - y0 || 1)) * (H - B - 26 - 22);
    const plot = G.svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-similarity", role: "img" });
    plot.append(G.svg("line", { x1: 8, x2: W - 8, y1: y(0), y2: y(0), class: "rc-zero rc-dashed" }), G.svg("line", { x1: x(0), x2: x(0), y1: 8, y2: H - B - 6, class: "rc-zero rc-dashed" }));
    const pole = (p, sign) => G.topicName(ids[p.v.reduce((best, v, i) => (v * sign > p.v[best] * sign ? i : best), 0)]);
    plot.append(text({ x: W / 2, y: H - 8, "text-anchor": "middle", class: "rc-cover" }, c.simAxis(pole(p1, -1), pole(p1, 1), (p1.share * 100).toFixed(0))));
    plot.append(text({ x: 12, y: (H - B) / 2, "text-anchor": "middle", class: "rc-cover", transform: `rotate(-90 12 ${(H - B) / 2})` }, c.simAxis(pole(p2, -1), pole(p2, 1), (p2.share * 100).toFixed(0))));
    const maxN = Math.max(...rows.map((r) => r.articles)), links = G.svg("g", { class: "rc-sim-links" }); plot.append(links);
    const distinct = (i, n) => X[i].map((v, j) => [v, j]).sort((a, b) => b[0] - a[0]).slice(0, n).map(([, j]) => ids[j]);
    const nearest = (i) => X.map((row, j) => [Math.hypot(...row.map((v, k) => v - X[i][k])), j]).filter(([, j]) => j !== i).sort((a, b) => a[0] - b[0]).slice(0, 3).map(([, j]) => j);
    const placed = [];
    rows.forEach((row, i) => {
      const cx = x(score[i][0]), cy = y(score[i][1]), r = 5 + Math.sqrt(row.articles / maxN) * 14, name = row[lang()], g = G.svg("g", { class: "rc-sim" });
      const dot = later(G.svg("circle", { cx, cy, r, fill: G.COLORS[distinct(i, 1)[0]], class: "rc-bubble rc-a-pop" }), 100 + i * 32);
      const w = name.length * (G.en() ? 5.8 : 11.4) + 4, right = cx + r + 4 + w < W - 6, bx = right ? cx + r + 4 : cx - r - 4 - w, clash = placed.some((b) => bx < b[0] + b[2] && bx + w > b[0] && cy - 8 < b[1] + 16 && cy + 8 > b[1]);
      const label = later(text({ x: right ? bx : bx + w, y: cy + 4, "text-anchor": right ? "start" : "end", class: `rc-bubble-name rc-a-fade${clash ? " is-extra" : ""}` }, name), 500 + i * 32);
      if (!clash) placed.push([bx, cy - 8, w]);
      g.append(dot, label);
      g.addEventListener("pointerenter", () => {
        plot.classList.add("is-focus"); g.classList.add("is-on");
        links.replaceChildren(...nearest(i).map((j) => G.svg("line", { x1: cx, y1: cy, x2: x(score[j][0]), y2: y(score[j][1]), class: "rc-sim-link", pathLength: 1 })));
      });
      g.addEventListener("pointermove", (event) => G.showTip(event, c.simTip(name, distinct(i, 2).map(G.topicName).join("、"), nearest(i).map((j) => rows[j][lang()]).join("、"))));
      g.addEventListener("pointerleave", () => { plot.classList.remove("is-focus"); g.classList.remove("is-on"); links.replaceChildren(); G.hideTip(); });
      plot.append(g);
    });
    card.append(G.el("div", { className: "rc-plot" }, plot));
  }

  /* ---------- continents by topic profile ---------- */
  function drawContinents() {
    const c = t(), card = $("continentProfiles"), D = G.data;
    if (!card) return;
    const rows = (D.continents || []).filter((row) => row.id !== "Antarctica" && row.n >= 500);
    if (rows.length < 3) { card.hidden = true; return; }
    G.head(card, "00 · CONTINENTS BY TOPIC PROFILE", c.continents, c.continentsNote);
    arm(card);
    const ids = D.topics.map((x) => x.id), mixAll = ids.map((_, j) => rows.reduce((s, row) => s + row.t[j], 0)), mixSum = mixAll.reduce((s, n) => s + n, 0) || 1;
    const W = Math.max(360, G.widthOf(card) - 8), cols = W >= 1040 ? 6 : W >= 600 ? 3 : 2, cell = W / cols, R = Math.min(96, cell / 2 - 22), CH = R * 2 + 92, H = Math.ceil(rows.length / cols) * CH;
    const reach = (lift) => R * (0.16 + 0.84 * (G.clamp(Math.log2(Math.max(lift, 0.01)), -1.5, 1.5) + 1.5) / 3);
    const plot = G.svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-continents", role: "img" });
    rows.forEach((row, i) => {
      const cx = (i % cols) * cell + cell / 2, cy = Math.floor(i / cols) * CH + R + 12, mine = row.t.reduce((s, n) => s + n, 0) || 1;
      const lift = ids.map((_, j) => (row.t[j] / mine) / (mixAll[j] / mixSum)), at = (j, radius) => { const a = -Math.PI / 2 + (j / ids.length) * Math.PI * 2; return [cx + Math.cos(a) * radius, cy + Math.sin(a) * radius]; };
      for (const level of [0.5, 2]) plot.append(G.svg("circle", { cx, cy, r: reach(level), class: "rc-radar-ring" }));
      plot.append(G.svg("circle", { cx, cy, r: reach(1), class: "rc-radar-ring rc-radar-mean" }));
      ids.forEach((id, j) => { const [ex, ey] = at(j, R); plot.append(G.svg("line", { x1: cx, y1: cy, x2: ex, y2: ey, class: "rc-radar-spoke" })); });
      const points = ids.map((_, j) => at(j, reach(lift[j])));
      const shape = later(G.svg("polygon", { points: points.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" "), class: "rc-radar-shape rc-a-grow" }), 150 + i * 130);
      shape.style.transformOrigin = `${cx}px ${cy}px`;
      plot.append(shape);
      ids.forEach((id, j) => {
        const dot = later(G.svg("circle", { cx: points[j][0], cy: points[j][1], r: 3.4, fill: G.COLORS[id], class: "rc-radar-dot rc-a-pop" }), 600 + i * 130 + j * 22);
        dot.addEventListener("pointermove", (event) => G.showTip(event, c.contTip(row[lang()], G.topicName(id), G.num(row.t[j]), ((row.t[j] / mine) * 100).toFixed(1), lift[j].toFixed(2))));
        dot.addEventListener("pointerleave", G.hideTip);
        plot.append(dot);
      });
      const leaders = lift.map((v, j) => [v, j]).sort((a, b) => b[0] - a[0]).slice(0, 2).map(([, j]) => G.topicName(ids[j]));
      plot.append(text({ x: cx, y: cy + R + 30, "text-anchor": "middle", class: "rc-radar-name" }, row[lang()]), text({ x: cx, y: cy + R + 46, "text-anchor": "middle", class: "rc-cover" }, c.contArticles(G.num(row.n))));
      leaders.forEach((name, k) => plot.append(text({ x: cx, y: cy + R + 62 + k * 13, "text-anchor": "middle", class: "rc-radar-lean" }, `${k ? "" : `${c.contLean} · `}${name}`)));
    });
    const legend = G.el("div", { className: "rc-legend" }, ...ids.map((id) => G.el("span", {}, G.el("i", { style: `background:${G.COLORS[id]}` }), G.topicName(id))));
    card.append(G.el("div", { className: "rc-plot" }, plot), legend);
  }

  /* ---------- the COP window (an event study) ---------- */
  function drawCop() {
    const c = t(), card = $("copWindow"), D = G.data;
    if (!card) return;
    const win = D.cop_window, talks = state.cop === "talks";
    const sessions = (win?.sessions || []).filter((s) => (talks ? s.base_talks >= 0.4 : s.base >= 3));
    if (!win || sessions.length < 5) { card.hidden = true; return; }
    G.head(card, "00 · THE COP WINDOW", c.cop, c.copNote(sessions.length, sessions[0].year, sessions[sessions.length - 1].year),
      G.toggle([["all", c.copAll], ["talks", c.copTalks]], state.cop, (key) => { state.cop = key; drawCop(); }));
    arm(card);
    const before = win.before, size = before + win.after + 1, offsets = Array.from({ length: size }, (_, i) => i - before);
    const ratio = sessions.map((s) => { const raw = talks ? s.talks : s.days, base = talks ? s.base_talks : s.base; return raw.map((_, i) => { let sum = 0, n = 0; for (let k = i - 3; k <= i + 3; k += 1) if (raw[k] != null) { sum += raw[k]; n += 1; } return sum / n / base; }); }); // a 7-day centred mean: publishing has a weekly cycle
    const quant = (list, q) => { const sorted = [...list].sort((a, b) => a - b), at = (sorted.length - 1) * q, lo = Math.floor(at); return sorted[lo] + (sorted[Math.min(sorted.length - 1, lo + 1)] - sorted[lo]) * (at - lo); };
    const med = offsets.map((_, i) => quant(ratio.map((r) => r[i]), 0.5)), q1 = offsets.map((_, i) => quant(ratio.map((r) => r[i]), 0.25)), q3 = offsets.map((_, i) => quant(ratio.map((r) => r[i]), 0.75));
    const top = Math.max(2, Math.ceil(Math.max(...q3) * 1.12));
    const W = Math.max(400, G.widthOf(card) - 8), H = Math.round(G.clamp(W * 0.62, 280, 400)), L = 40, R = 14, T = 14, Bm = 38;
    const x = (d) => L + ((d + before) / (size - 1)) * (W - L - R), y = (v) => T + (1 - v / top) * (H - T - Bm);
    const plot = G.svg("svg", { viewBox: `0 0 ${W} ${H}`, class: "rc-svg rc-cop", role: "img" });
    const length = quant(sessions.map((s) => s.length), 0.5);
    plot.append(G.svg("rect", { x: x(0), y: T, width: x(length - 1) - x(0), height: H - T - Bm, class: "rc-cop-session rc-a-fade" }), text({ x: (x(0) + x(length - 1)) / 2, y: T + 12, "text-anchor": "middle", class: "rc-cover" }, c.copSession));
    const step = top <= 4 ? 1 : top <= 8 ? 2 : Math.ceil(top / 4);
    for (let v = 0; v <= top; v += step) plot.append(G.svg("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: v === 1 ? "rc-zero rc-dashed" : "rc-grid rc-grid-soft" }), text({ x: L - 6, y: y(v) + 3.5, "text-anchor": "end", class: "rc-axis" }, `×${v}`));
    for (const d of [-45, -30, -15, 0, 15, 30, 45]) plot.append(text({ x: x(d), y: H - Bm + 15, "text-anchor": "middle", class: "rc-axis" }, d > 0 ? `+${d}` : d));
    plot.append(text({ x: L, y: H - 6, class: "rc-cover" }, c.copAxis));
    const pathOf = (values) => smooth(values.map((v, i) => [x(offsets[i]), y(v)]));
    const frame = G.svg("clipPath", { id: "rc-cop-clip" }); frame.append(G.svg("rect", { x: L, y: T, width: W - L - R, height: H - T - Bm }));
    const thin = G.svg("g", { class: "rc-cop-thin", "clip-path": "url(#rc-cop-clip)" });
    plot.append(frame);
    ratio.forEach((r, k) => { const line = later(G.svg("path", { d: pathOf(r), class: "rc-cop-one rc-a-fade" }), 300 + k * 40); line.dataset.session = k; thin.append(line); });
    plot.append(thin);
    const band = `${pathOf(q3)}L${[...q1].reverse().map((v, i) => `${x(offsets[size - 1 - i])},${y(v)}`).join("L")}Z`;
    plot.append(later(G.svg("path", { d: band, class: "rc-cop-band rc-a-fade" }), 500), later(G.svg("path", { d: pathOf(med), class: "rc-line rc-cop-median rc-a-draw", pathLength: 1 }), 150));
    const guide = G.svg("line", { y1: T, y2: H - Bm, class: "rc-guide", opacity: 0 }), dot = G.svg("circle", { r: 4.2, class: "rc-cop-dot", opacity: 0 });
    const hit = G.svg("rect", { x: L, y: T, width: W - L - R, height: H - T - Bm, fill: "transparent" });
    hit.addEventListener("pointermove", (event) => {
      const box = plot.getBoundingClientRect(), px = ((event.clientX - box.left) * W) / plot.clientWidth, py = ((event.clientY - box.top) * H) / plot.clientHeight;
      const i = G.clamp(Math.round(((px - L) / (W - L - R)) * (size - 1)), 0, size - 1);
      guide.setAttribute("x1", x(offsets[i])); guide.setAttribute("x2", x(offsets[i])); guide.setAttribute("opacity", 1);
      // the session whose line runs under the pointer, if one is close; else the median
      let near = -1, gap = 9; ratio.forEach((r, k) => { const dy = Math.abs(y(r[i]) - py); if (dy < gap) { gap = dy; near = k; } });
      if (Math.abs(y(med[i]) - py) <= gap + 2) near = -1;
      thin.querySelectorAll(".is-on").forEach((node) => node.classList.remove("is-on"));
      if (near >= 0) { thin.children[near].classList.add("is-on"); const s = sessions[near]; dot.setAttribute("cx", x(offsets[i])); dot.setAttribute("cy", y(ratio[near][i])); dot.setAttribute("opacity", 1); G.showTip(event, c.copLine(s.n, s.city, s.year, c.copDay(offsets[i]), ratio[near][i].toFixed(1))); }
      else { dot.setAttribute("cx", x(offsets[i])); dot.setAttribute("cy", y(med[i])); dot.setAttribute("opacity", 1); G.showTip(event, c.copTip(c.copDay(offsets[i]), med[i].toFixed(1), q1[i].toFixed(1), q3[i].toFixed(1))); }
    });
    hit.addEventListener("pointerleave", () => { guide.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); thin.querySelectorAll(".is-on").forEach((node) => node.classList.remove("is-on")); G.hideTip(); });
    plot.append(guide, dot, hit);
    card.append(G.el("div", { className: "rc-plot" }, plot));
  }

  function draw(resized) {
    G = window.GreenAnalysis;
    if (!G?.data) return;
    for (const chart of [drawRanks, drawQuadrant, drawDiversity, drawMap, drawSimilarity, drawContinents, drawCop]) {
      try { chart(resized); } catch (error) { console.error("analysis-more", chart.name, error); }
    }
  }
  // analysis.js calls extra.draw() from its drawAll (first draw, language) and on a resize; if it has drawn already
  // (this file arrived late), draw now
  (window.GreenAnalysis ||= {}).extra = { draw };
  if (window.GreenAnalysis.data) draw();
})();
