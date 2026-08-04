const state = {
  mode: "climate", datasets: {},
  dashboard: null, archive: null, analytics: null, filtered: [], visible: 18,
  mapPeriod: "today", mapTopology: null,
  assistant: { lastRecords: [], lastPlan: null },
};
const $ = id => document.getElementById(id);
const esc = (value = "") => String(value).replace(/[&<>'"]/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[character]));
const SVG_NS = "http://www.w3.org/2000/svg";
const MAP_CENTER_LON = 55;

function safeUrl(value) {
  try {
    const url = new URL(value, location.href);
    if (url.protocol === "http:") url.protocol = "https:";
    return url.protocol === "https:" ? url.href : "#";
  } catch (_) {
    return "#";
  }
}

function formatDate(value, withTime = false) {
  if (!value) return "时间待核";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", withTime
    ? { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }
    : { year: "numeric", month: "2-digit", day: "2-digit" });
}

function beijingDay(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(date);
  const get = type => parts.find(part => part.type === type)?.value || "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function toast(message) {
  const element = $("toast");
  if (!element) return;
  element.textContent = message;
  element.classList.add("show");
  setTimeout(() => element.classList.remove("show"), 3200);
}

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

const MODE_COPY = {
  climate: {
    button: "切换到能源技术",
    mapOverline: "GLOBAL CLIMATE SITUATION",
    mapTitle: "全球气候现场",
    heroOverline: "DAILY CLIMATE TEXT INTELLIGENCE",
    heroTitle: "每天读懂全球气候变化<br><span>重点情报与文本数据库</span>",
    heroLede: "从国际机构、政府与专业媒体中筛选值得关注的气候事件，提供中文标题、完整概要、议题、地域、关键数字及原文入口。",
    datasetName: "CLIMATETEXT-8760",
    datasetTitle: "每日气候文本档案",
    todayOverline: "DAILY SIGNALS",
    todayTitle: "今日重要气候情报",
    analyticsTitle: "语料库统计分析",
    assistantOverline: "GROUNDED CLIMATE Q&A",
    assistantTitle: "气候情报问答",
    databaseOverline: "TEXT DATABASE",
    databaseTitle: "气候新闻文本数据库",
    downloadName: "国际气候情报今日简报",
    quickPrompts: [
      ["今日简报", "请给出今日简报"],
      ["本周重点", "本周有哪些值得关注的气候情报？"],
      ["本周中美比较", "比较本周中国与美国的重点气候情报"],
      ["气候资金", "近期有哪些气候资金信息？"],
    ],
  },
  energy: {
    button: "切换到气候情报",
    mapOverline: "GLOBAL ENERGY TECHNOLOGY SITUATION",
    mapTitle: "全球能源技术现场",
    heroOverline: "DAILY ENERGY TECHNOLOGY INTELLIGENCE",
    heroTitle: "追踪能源转型与技术趋势<br><span>动态情报与文本数据库</span>",
    heroLede: "从现有归档中筛选能源转型、能源技术趋势、数字能源、新型电力系统、储能、风光氢网等相关信息，保留来源、时间、地域与原文入口。",
    datasetName: "ENERGYTECH-8760",
    datasetTitle: "能源技术文本档案",
    todayOverline: "ENERGY TECH SIGNALS",
    todayTitle: "今日能源技术动态",
    analyticsTitle: "能源技术语料分析",
    assistantOverline: "GROUNDED ENERGY TECH Q&A",
    assistantTitle: "能源技术情报问答",
    databaseOverline: "ENERGY TEXT DATABASE",
    databaseTitle: "能源技术文本数据库",
    downloadName: "能源技术趋势今日简报",
    quickPrompts: [
      ["今日能源动态", "请给出今日能源技术动态简报"],
      ["本周技术趋势", "本周有哪些值得关注的能源技术趋势？"],
      ["中美能源技术", "比较本周中国与美国的能源技术动态"],
      ["数能与电网", "近期有哪些数字能源、储能或电网信息？"],
    ],
  },
};

function applyModeCopy() {
  const copy = MODE_COPY[state.mode] || MODE_COPY.climate;
  document.body.dataset.mode = state.mode;
  const modeToggle = $("modeToggle");
  if (modeToggle) modeToggle.textContent = copy.button;
  ["mapOverline", "mapTitle", "heroOverline", "heroLede", "datasetName", "datasetTitle",
    "todayOverline", "todayTitle", "analyticsTitle", "assistantOverline", "assistantTitle",
    "databaseOverline", "databaseTitle"].forEach(id => {
    const element = $(id);
    if (element) element.textContent = copy[id];
  });
  if ($("heroTitle")) $("heroTitle").innerHTML = copy.heroTitle;
  document.querySelectorAll(".quick-prompts button").forEach((button, index) => {
    const prompt = copy.quickPrompts?.[index];
    if (!prompt) return;
    button.textContent = prompt[0];
    button.dataset.prompt = prompt[1];
  });
}

function activateMode(mode) {
  const nextMode = mode === "energy" && state.datasets.energy ? "energy" : "climate";
  const dataset = state.datasets[nextMode];
  state.mode = nextMode;
  state.dashboard = dataset.dashboard;
  state.archive = dataset.archive;
  state.analytics = dataset.analytics;
  state.filtered = [];
  state.visible = 18;
  state.assistant = { lastRecords: [], lastPlan: null };
  localStorage.setItem("climateTextMode", nextMode);
  applyModeCopy();
  renderMeta();
  renderToday();
  if ($("archiveSearch")) $("archiveSearch").value = "";
  populateTopicFilter();
  applyFilters();
  renderAnalytics();
  updateMapPeriodCounts();
  switchMapPeriod("today").catch(error => {
    console.error("Mode map rendering failed", error);
    toast("地图刷新失败，请稍后重试。");
  });
}

function renderMeta() {
  const dashboard = state.dashboard;
  const archive = state.archive;
  const events = dashboard.map_events_today || dashboard.map_events || [];
  const uniquePlaces = new Set(events.map(item => item.place).filter(Boolean));
  $("archiveTotal").textContent = archive.total ?? 0;
  $("todayTotal").textContent = (dashboard.intelligence || []).length;
  $("mapPlaceTotal").textContent = uniquePlaces.size;
  $("datasetVersion").textContent = formatDate(archive.updated_at, true);
  $("generatedAt").textContent = `最近生成：${formatDate(dashboard.meta?.generated_at, true)}`;
  const briefLink = $("briefDownload");
  if (briefLink) briefLink.download = `${MODE_COPY[state.mode].downloadName}-${dashboard.meta?.date || "latest"}.pdf`;
}

function findArchiveRecord(item) {
  return state.archive.records.find(record =>
    record.article_id === item.article_id || record.canonical_url === item.canonical_url
  ) || item;
}

function renderToday() {
  const items = (state.dashboard.intelligence || [])
    .filter(item => item.title_zh && item.summary_zh);
  $("todayGrid").innerHTML = items.length ? items.slice(0, 10).map((item, index) => {
    const record = findArchiveRecord(item);
    return `<article class="signal-card">
      <div class="signal-index">${String(index + 1).padStart(2, "0")}</div>
      <div class="signal-content">
        <div class="signal-meta"><span class="topic">${esc(item.theme_zh || "气候动态")}</span></div>
        <h3>${esc(item.title_zh)}</h3>
        <p>${esc(item.summary_zh)}</p>
        <div class="signal-foot">
          <span>${esc(item.source_name)} · ${esc(formatDate(item.published_at))}</span>
          <a href="${esc(safeUrl(record.canonical_url || item.url))}" target="_blank" rel="noopener noreferrer">阅读原文 ↗</a>
        </div>
      </div>
    </article>`;
  }).join("") : '<div class="empty"><b>今日暂无新增重点情报</b><p>网站仍保留历史文本数据库，待下一次有效数据更新后自动补充。</p></div>';
}

function setupFilters() {
  populateTopicFilter();
  ["archiveSearch", "topicFilter"].forEach(id => $(id).addEventListener(id === "archiveSearch" ? "input" : "change", () => {
    state.visible = 18;
    applyFilters();
  }));
  $("loadMore").addEventListener("click", () => {
    state.visible += 18;
    renderArchiveRows();
  });
}

function populateTopicFilter() {
  const topics = [...new Set(state.archive.records.flatMap(record => record.topics || []))]
    .sort((left, right) => left.localeCompare(right, "zh-CN"));
  $("topicFilter").innerHTML = '<option value="">全部议题</option>'
    + topics.map(topic => `<option value="${esc(topic)}">${esc(topic)}</option>`).join("");
}

function applyFilters() {
  const query = $("archiveSearch").value.trim().toLowerCase();
  const topic = $("topicFilter").value;
  state.filtered = state.archive.records.filter(record => {
    const haystack = [
      record.title_zh, record.title_original, record.summary_zh, record.source_name,
      ...(record.topics || []), ...(record.places || []).map(place => place.name_zh),
    ].join(" ").toLowerCase();
    return (!query || haystack.includes(query))
      && (!topic || (record.topics || []).includes(topic));
  });
  renderArchiveRows();
}

function renderArchiveRows() {
  const shown = state.filtered.slice(0, state.visible);
  $("resultCount").textContent = state.filtered.length;
  $("archiveList").innerHTML = shown.length ? shown.map(record => {
    const facts = [
      ...(record.numbers || []).slice(0, 2),
      ...(record.places || []).slice(0, 2).map(place => place.name_zh),
    ];
    return `<article class="archive-row">
      <div class="archive-date"><b>${esc(formatDate(record.published_at))}</b></div>
      <div class="archive-title"><h3>${esc(record.title_zh)}</h3><p>${esc(record.title_original)}</p></div>
      <div class="archive-source"><b>${esc(record.source_name)}</b><span>${esc((record.topics || []).slice(0, 2).join(" · ") || "气候动态")}</span></div>
      <div class="archive-atoms">${facts.length ? facts.map(fact => `<i>${esc(fact)}</i>`).join("") : "<i>暂无独立数字或地点</i>"}<a href="${esc(safeUrl(record.canonical_url))}" target="_blank" rel="noopener noreferrer">阅读原文 ↗</a></div>
    </article>`;
  }).join("") : '<div class="empty compact"><b>没有匹配记录</b><p>请减少筛选条件或更换关键词。</p></div>';
  $("loadMore").hidden = state.visible >= state.filtered.length;
}

function svgEl(name, attrs = {}) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function decodeArc(topology, arcIndex) {
  const reverse = arcIndex < 0;
  const source = topology.arcs[reverse ? ~arcIndex : arcIndex];
  const [scaleX, scaleY] = topology.transform.scale;
  const [translateX, translateY] = topology.transform.translate;
  let x = 0;
  let y = 0;
  const points = source.map(([deltaX, deltaY]) => {
    x += deltaX;
    y += deltaY;
    return [x * scaleX + translateX, y * scaleY + translateY];
  });
  return reverse ? points.reverse() : points;
}

function worldPoint([longitude, latitude]) {
  return [(longitude + 180) / 360 * 1000, (90 - latitude) / 180 * 500];
}

function centeredPoint(longitude, latitude) {
  const centerX = (MAP_CENTER_LON + 180) / 360 * 1000;
  const baseX = (longitude + 180) / 360 * 1000;
  return [((baseX - centerX + 500) % 1000 + 1000) % 1000, (90 - latitude) / 180 * 500];
}

function ringCoordinates(topology, refs) {
  const points = [];
  refs.forEach(ref => {
    const arc = decodeArc(topology, ref);
    points.push(...(points.length ? arc.slice(1) : arc));
  });
  return points;
}

function ringPath(topology, refs) {
  const points = ringCoordinates(topology, refs);
  return points.map((point, index) => {
    const [x, y] = worldPoint(point);
    const crossesEdge = index > 0 && Math.abs(point[0] - points[index - 1][0]) > 180;
    return `${index && !crossesEdge ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join("") + "Z";
}

function geometryPath(topology, geometry) {
  if (geometry.type === "Polygon") return geometry.arcs.map(ring => ringPath(topology, ring)).join("");
  if (geometry.type === "MultiPolygon") return geometry.arcs.flatMap(polygon => polygon.map(ring => ringPath(topology, ring))).join("");
  return "";
}

function spreadMarkerPositions(events) {
  const placed = [];
  return events.map((item, index) => {
    const origin = centeredPoint(Number(item.lon), Number(item.lat));
    let [x, y] = origin;
    let attempt = 0;
    while (placed.some(point => Math.hypot(point.x - x, point.y - y) < 19) && attempt < 40) {
      attempt += 1;
      const angle = index * 2.39996 + attempt * 1.618;
      const radius = 9 * Math.sqrt(attempt);
      x = Math.max(12, Math.min(988, origin[0] + Math.cos(angle) * radius));
      y = Math.max(12, Math.min(488, origin[1] + Math.sin(angle) * radius));
    }
    placed.push({ x, y });
    return { item, x, y, originX: origin[0], originY: origin[1] };
  });
}

async function renderMap(events) {
  const topology = state.mapTopology || await fetchJson(new URL("./assets/countries-110m.json", document.baseURI).href);
  state.mapTopology = topology;
  if (!topology?.objects?.countries?.geometries?.length) throw new Error("invalid map topology");
  const svg = $("worldMap");
  svg.replaceChildren();
  const countries = svgEl("g", { "aria-hidden": "true" });
  topology.objects.countries.geometries.forEach(geometry => {
    const path = geometryPath(topology, geometry);
    if (path) countries.appendChild(svgEl("path", { d: path, class: "map-country", "fill-rule": "evenodd" }));
  });
  const shift = 500 - (MAP_CENTER_LON + 180) / 360 * 1000;
  const westernCopy = countries.cloneNode(true);
  const easternCopy = countries.cloneNode(true);
  westernCopy.setAttribute("transform", `translate(${shift},0)`);
  easternCopy.setAttribute("transform", `translate(${shift + 1000},0)`);
  svg.append(westernCopy, easternCopy);

  const [chinaX, chinaY] = centeredPoint(105, 35);
  svg.appendChild(svgEl("path", {
    d: `M${chinaX - 7},${chinaY}H${chinaX + 7}M${chinaX},${chinaY - 7}V${chinaY + 7}`,
    class: "china-anchor",
  }));
  const chinaLabel = svgEl("text", { x: chinaX + 11, y: chinaY + 5, class: "china-label" });
  chinaLabel.textContent = "中国";
  svg.appendChild(chinaLabel);

  spreadMarkerPositions(events).forEach(({ item, x, y, originX, originY }, index) => {
    const longitude = Number(item.lon);
    const latitude = Number(item.lat);
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return;
    if (Math.hypot(x - originX, y - originY) > 4) {
      svg.appendChild(svgEl("line", { x1: originX, y1: originY, x2: x, y2: y, class: "event-stem" }));
    }
    const pin = svgEl("g", {
      class: "event-pin", tabindex: "0", role: "button", "data-marker": item.marker_id,
      "aria-label": `${item.place}：${item.title_zh}`,
    });
    pin.append(
      svgEl("circle", { cx: x, cy: y, r: 13, class: "event-halo" }),
      svgEl("circle", { cx: x, cy: y, r: 6.5, class: "event-marker" }),
    );
    pin.addEventListener("click", () => selectMapEvent(item));
    pin.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") selectMapEvent(item);
    });
    pin.addEventListener("mouseenter", event => showMapTooltip(event, item));
    pin.addEventListener("mouseleave", () => $("mapTooltip").classList.remove("show"));
    svg.appendChild(pin);
    if (index === 0) selectMapEvent(item);
  });
  $("mapLoading").hidden = true;
  $("mapCanvas").classList.add("map-ready");
}

function showMapTooltip(event, item) {
  const tooltip = $("mapTooltip");
  const bounds = $("mapCanvas").getBoundingClientRect();
  tooltip.innerHTML = `<b>${esc(item.place)} · ${esc(item.theme)}</b><span>${esc(item.title_zh)}</span>`;
  tooltip.style.left = `${Math.min(bounds.width - 280, Math.max(12, event.clientX - bounds.left + 12))}px`;
  tooltip.style.top = `${Math.max(12, event.clientY - bounds.top - 80)}px`;
  tooltip.classList.add("show");
}

function selectMapEvent(item) {
  $("mapDetail").innerHTML = `<span>${esc(item.place)} · ${esc(item.theme)}</span><h2>${esc(item.title_zh)}</h2><p>${esc(item.summary_zh)}</p><small>${esc(item.source_name)} · ${esc(formatDate(item.published_at))}</small><a href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">阅读原文 ↗</a>`;
}

function renderMapPlaces(events) {
  $("mapPlaceList").innerHTML = events.length
    ? events.map(item => `<button type="button" data-map-id="${esc(item.marker_id)}"><i></i>${esc(item.place)}<span>${esc(item.theme)}</span></button>`).join("")
    : `<span>${state.mapPeriod === "today" ? "今日队列" : "本周"}暂无带有明确地理位置的新记录。</span>`;
  document.querySelectorAll("[data-map-id]").forEach(button => button.addEventListener("click", () => {
    const item = events.find(event => event.marker_id === button.dataset.mapId);
    if (item) selectMapEvent(item);
  }));
}

function mapEventsFor(period) {
  if (period === "week") return state.dashboard.map_events_week || [];
  return state.dashboard.map_events_today || state.dashboard.map_events || [];
}

async function switchMapPeriod(period) {
  state.mapPeriod = period;
  document.querySelectorAll("[data-map-period]").forEach(button => {
    const active = button.dataset.mapPeriod === period;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  const events = mapEventsFor(period);
  $("mapRangeNote").textContent = `中国位于地图中部偏右。红点表示${period === "today" ? "今日队列" : "本周"}情报明确涉及的国家或地区；点击即可查看中文摘要与原文。`;
  renderMapPlaces(events);
  await renderMap(events);
}

function setupMapPeriods() {
  updateMapPeriodCounts();
  document.querySelectorAll("[data-map-period]").forEach(button => {
    button.addEventListener("click", () => switchMapPeriod(button.dataset.mapPeriod).catch(error => {
      console.error("Map period switch failed", error);
      toast("地图切换失败，请刷新页面重试。");
    }));
  });
}

function updateMapPeriodCounts() {
  const todayEvents = mapEventsFor("today");
  const weekEvents = mapEventsFor("week");
  $("todayMapCount").textContent = todayEvents.length;
  $("weekMapCount").textContent = weekEvents.length;
}

const COUNTRY_CONCEPTS = [
  { name: "中国", terms: ["中国", "北京", "china", "chinese", "beijing"] },
  { name: "美国", terms: ["美国", "美方", "united states", "u.s.", "usa", "american", "north america", "texas", "california", "oregon", "new york", "michigan", "new england"] },
  { name: "欧盟", terms: ["欧盟", "欧洲", "europe", "european union", "eu"] },
  { name: "拉丁美洲", terms: ["拉丁美洲", "南美", "巴西", "亚马孙", "latin america", "brazil", "amazon"] },
  { name: "非洲", terms: ["非洲", "南非", "肯尼亚", "乌干达", "africa", "south africa", "kenya", "uganda"] },
  { name: "澳大利亚及太平洋", terms: ["澳大利亚", "太平洋", "大洋洲", "australia", "pacific", "oceania"] },
  { name: "南极洲", terms: ["南极", "南极洲", "antarctic", "antarctica"] },
];

const TOPIC_CONCEPTS = [
  { name: "气候资金", terms: ["气候资金", "资金", "融资", "finance", "fund", "loss and damage"] },
  { name: "能源与排放", terms: ["能源", "减排", "排放", "化石燃料", "可再生能源", "emission", "energy", "renewable", "fossil"] },
  { name: "气候适应", terms: ["适应", "韧性", "损失损害", "adaptation", "resilience"] },
  { name: "碳市场", terms: ["碳市场", "碳交易", "article 6", "carbon market", "carbon credit"] },
  { name: "极端天气", terms: ["极端天气", "高温", "洪水", "干旱", "野火", "飓风", "heat", "flood", "drought", "wildfire", "hurricane"] },
  { name: "国际谈判", terms: ["谈判", "cop31", "unfccc", "ndc", "全球盘点", "climate talks"] },
];

function recordText(record) {
  return [
    record.title_zh, record.title_original, record.summary_zh, record.why_zh, record.source_name,
    ...(record.topics || []), ...(record.places || []).map(place => place.name_zh),
  ].filter(Boolean).join(" ").toLowerCase();
}

function recordsInLatestWeek(items) {
  const latestDay = items.map(item => beijingDay(item.published_at)).filter(Boolean).sort().at(-1);
  if (!latestDay) return [];
  const latestTime = new Date(`${latestDay}T00:00:00+08:00`).getTime();
  return items.filter(record => {
    const value = new Date(record.published_at).getTime();
    return Number.isFinite(value) && value >= latestTime - 6 * 86400000 && value < latestTime + 86400000;
  });
}

function termMatches(text, term) {
  const normalized = text.toLowerCase();
  if (/[a-z]/.test(term) && !/[\u4e00-\u9fff]/.test(term)) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(^|[^a-z0-9])${escaped}([^a-z0-9]|$)`).test(normalized);
  }
  return normalized.includes(term);
}

function detectConcepts(text, concepts) {
  return concepts.filter(concept => concept.terms.some(term => termMatches(text, term)));
}

function planQuestion(query) {
  const normalized = query.toLowerCase().replace(/[？?！，。；：、]/g, " ");
  let entities = detectConcepts(normalized, COUNTRY_CONCEPTS);
  if (/中美|美中/.test(normalized)) {
    entities = COUNTRY_CONCEPTS.filter(concept => ["中国", "美国"].includes(concept.name));
  }
  const topics = detectConcepts(normalized, TOPIC_CONCEPTS);
  const isFollowUp = /这些|上述|其中|前述|继续|它们|前者|后者|第[一二三四五六七八12345678]条/.test(normalized);
  let scope = /今日|今天|当天/.test(normalized) ? "today"
    : (/本周|一周|近七天|最近7天/.test(normalized) ? "week" : "archive");
  if (isFollowUp && state.assistant.lastPlan && !/今日|今天|当天|本周|一周|近七天|最近7天|历史|档案/.test(normalized)) {
    scope = state.assistant.lastPlan.scope;
  }
  const intent = /比较|对比|差异|异同|中美|美中/.test(normalized) ? "compare"
    : (/趋势|演变|变化|进展|时间线/.test(normalized) ? "trend"
      : (/意味着|影响|含义|谈判|政策|风险|启示/.test(normalized) ? "implication"
        : (/简报|重点|概览|综述/.test(normalized) ? "brief" : "search")));
  const countMatch = normalized.match(/(\d+)\s*(?:条|项|个)/);
  const limit = Math.max(1, Math.min(8, countMatch ? Number(countMatch[1]) : (intent === "brief" ? 6 : 5)));
  const generic = /请|给出|告诉我|哪些|有什么|值得关注|气候|情报|近期|最近|今日|今天|当天|简报|本周|一周|近七天|最近7天|信息|动态|比较|对比|趋势|政策|影响|的|和|与|中/g;
  const residue = normalized.replace(generic, " ");
  const rawTerms = [
    ...(residue.match(/[a-z][a-z0-9.-]{2,}/g) || []),
    ...(residue.match(/[\u4e00-\u9fff]{2,8}/g) || []),
  ];
  const terms = [...new Set([
    ...entities.flatMap(concept => concept.terms),
    ...topics.flatMap(concept => concept.terms),
    ...rawTerms,
  ])].filter(term => term.length > 1);
  return { query, normalized, entities, topics, scope, intent, limit, terms, isFollowUp };
}

function recordMatchesConcept(record, concept) {
  const text = recordText(record);
  return concept.terms.some(term => termMatches(text, term));
}

function scopedRecords(plan) {
  const all = state.archive.records || [];
  if (plan.isFollowUp && state.assistant.lastRecords.length) return state.assistant.lastRecords;
  if (plan.scope === "today") return state.dashboard.intelligence || [];
  if (plan.scope === "week") return recordsInLatestWeek(all);
  return all;
}

function scoreRecord(record, plan) {
  const titleZh = String(record.title_zh || "").toLowerCase();
  const titleOriginal = String(record.title_original || "").toLowerCase();
  const summary = String(record.summary_zh || "").toLowerCase();
  const source = String(record.source_name || "").toLowerCase();
  const topicText = (record.topics || []).join(" ").toLowerCase();
  const placeText = (record.places || []).map(place => place.name_zh).join(" ").toLowerCase();
  const entityHits = plan.entities.filter(concept => recordMatchesConcept(record, concept)).length;
  const topicHits = plan.topics.filter(concept => recordMatchesConcept(record, concept)).length;
  // A follow-up already operates on the previous evidence set. New words such
  // as “谈判含义” describe the requested analysis and must not discard those
  // records merely because their taxonomy lacks the same literal label.
  if (!plan.isFollowUp && plan.entities.length && !entityHits) return -1;
  if (!plan.isFollowUp && plan.topics.length && !topicHits) return -1;
  let score = Number(record.relevance_score || 0) / 4 + entityHits * 34 + topicHits * 26;
  plan.terms.forEach(term => {
    if (termMatches(titleZh, term)) score += 14;
    if (termMatches(titleOriginal, term)) score += 10;
    if (termMatches(topicText, term) || termMatches(placeText, term)) score += 12;
    if (termMatches(summary, term)) score += 5;
    if (termMatches(source, term)) score += 2;
  });
  return score;
}

function selectEvidence(plan) {
  const candidates = scopedRecords(plan);
  const ranked = candidates.map(record => ({ record, score: scoreRecord(record, plan) }))
    .filter(item => item.score >= 0)
    .sort((left, right) => right.score - left.score
      || String(right.record.published_at).localeCompare(String(left.record.published_at)));
  const selected = [];
  const sourceCounts = new Map();
  const add = record => {
    if (selected.some(item => item.record_id === record.record_id || item.canonical_url === record.canonical_url)) return;
    const source = record.source_name || record.source_id;
    if ((sourceCounts.get(source) || 0) >= 2) return;
    selected.push(record);
    sourceCounts.set(source, (sourceCounts.get(source) || 0) + 1);
  };
  if (plan.intent === "compare" && plan.entities.length > 1) {
    plan.entities.forEach(concept => ranked
      .filter(item => recordMatchesConcept(item.record, concept))
      .slice(0, Math.max(2, Math.ceil(plan.limit / plan.entities.length)))
      .forEach(item => add(item.record)));
  }
  ranked.forEach(item => { if (selected.length < plan.limit) add(item.record); });
  return { records: selected.slice(0, plan.limit), candidateCount: candidates.length };
}

function scopeLabel(scope) {
  return scope === "today" ? `最新完整日（${state.dashboard.meta?.date || "待核"}，单日约10条）`
    : (scope === "week" ? "最近七个自然日" : "站内滚动档案");
}

function intentLabel(intent) {
  return ({ brief: "简报归纳", compare: "样本比较", trend: "时间线", implication: "政策含义", search: "证据检索" })[intent];
}

function planHtml(plan, records) {
  const region = plan.entities.length ? plan.entities.map(item => item.name).join(" / ") : "不限地区";
  const topic = plan.topics.length ? plan.topics.map(item => item.name).join(" / ") : "综合议题";
  return `<div class="chat-plan"><span>${esc(scopeLabel(plan.scope))}</span><span>${esc(region)}</span><span>${esc(topic)}</span><span>${esc(intentLabel(plan.intent))} · ${records.length} 条证据</span></div>`;
}

function evidenceList(records, { showWhy = false, chronological = false } = {}) {
  const ordered = chronological
    ? [...records].sort((a, b) => String(a.published_at).localeCompare(String(b.published_at)))
    : records;
  return `<ol class="evidence-list">${ordered.map((record, index) => `<li>
    <b>${chronological ? esc(formatDate(record.published_at)) + " · " : ""}${esc(record.title_zh || record.title_original)}</b>
    <p>${esc(record.summary_zh || "该条目尚无合格中文摘要。")}</p>
    ${showWhy && record.why_zh ? `<p class="evidence-implication"><strong>关注含义：</strong>${esc(record.why_zh)}</p>` : ""}
    <small>[${index + 1}] ${esc(record.source_name)} · ${esc(formatDate(record.published_at))}</small>
    <a href="${esc(safeUrl(record.canonical_url))}" target="_blank" rel="noopener noreferrer">核验原文 ↗</a>
  </li>`).join("")}</ol>`;
}

function topTopics(records) {
  const counts = new Map();
  records.flatMap(record => record.topics || []).forEach(topic => counts.set(topic, (counts.get(topic) || 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(item => item[0]).join("、") || "综合气候议题";
}

function comparisonHtml(plan, records) {
  return `<div class="chat-analysis"><h4>样本对比</h4>${plan.entities.map(concept => {
    const group = records.filter(record => recordMatchesConcept(record, concept));
    return `<p><strong>${esc(concept.name)}：</strong>${group.length
      ? `检索到 ${group.length} 条，主要涉及 ${esc(topTopics(group))}。`
      : "当前时间范围内没有足够的站内证据。"}</p>`;
  }).join("")}<p>这是对本站当前样本的比较，不代表两国全部气候行动的强弱排序。</p></div>`;
}

function addChatMessage(role, html) {
  const article = document.createElement("article");
  article.className = `chat-message ${role}`;
  article.innerHTML = `<span>${role === "user" ? "您" : "情报助手"}</span><div>${html}</div>`;
  $("chatLog").appendChild(article);
  $("chatLog").scrollTop = $("chatLog").scrollHeight;
}

function answerQuestion(query) {
  addChatMessage("user", `<p>${esc(query)}</p>`);
  const plan = planQuestion(query);
  const { records, candidateCount } = selectEvidence(plan);
  if (!records.length) {
    addChatMessage("assistant", `${planHtml(plan, records)}<p>在${esc(scopeLabel(plan.scope))}的 ${candidateCount} 条候选记录中，没有找到同时满足地区和议题条件的证据。您可以放宽时间范围或去掉一个限定词；系统不会用档案外常识补写答案。</p>`);
    return;
  }
  let analysis = `<p>在${esc(scopeLabel(plan.scope))}中，筛出 ${records.length} 条高相关证据，主要涉及 ${esc(topTopics(records))}。</p>`;
  if (plan.intent === "compare" && plan.entities.length > 1) analysis += comparisonHtml(plan, records);
  if (plan.intent === "trend") analysis += "<div class=\"chat-analysis\"><h4>时间线读法</h4><p>以下按发布时间排列，可用于观察议题推进顺序；记录数量不足时，不据此声称长期趋势已经形成。</p></div>";
  if (plan.intent === "implication") analysis += "<div class=\"chat-analysis\"><h4>政策含义</h4><p>先列来源陈述，再列系统归纳的关注含义；后者是辅助判断，不是原文事实。</p></div>";
  const evidence = evidenceList(records, {
    showWhy: plan.intent === "implication",
    chronological: plan.intent === "trend",
  });
  addChatMessage("assistant", `${planHtml(plan, records)}${analysis}${evidence}<p class="chat-boundary">证据边界：标题与摘要是来源内容的中文编译；比较、趋势和政策含义是基于当前站内样本的归纳。数字、承诺与立场请点击原文复核。</p>`);
  state.assistant.lastRecords = records;
  state.assistant.lastPlan = plan;
}

function setupAssistant() {
  $("chatForm").addEventListener("submit", event => {
    event.preventDefault();
    const input = $("chatInput");
    const query = input.value.trim();
    if (!query) return;
    input.value = "";
    answerQuestion(query);
  });
  document.querySelectorAll("[data-prompt]").forEach(button => button.addEventListener("click", () => answerQuestion(button.dataset.prompt)));
}

function formatCount(value) {
  return new Intl.NumberFormat("zh-CN").format(Number(value || 0));
}

function renderAnalytics() {
  const analytics = state.analytics;
  const container = $("analyticsKpis");
  if (!analytics || !analytics.records) {
    container.innerHTML = '<div class="empty compact"><b>语料库统计暂未生成</b><p>下一次静态导出会自动写入 corpus_analytics.json。</p></div>';
    $("analyticsNote").textContent = "未读取到可用统计文件。";
    return;
  }
  const taggedRate = `${Math.round((analytics.country_tagged_rate || 0) * 100)}%`;
  container.innerHTML = [
    ["记录总量", formatCount(analytics.records), `${analytics.date_start || "?"} 至 ${analytics.date_end || "?"}`],
    ["覆盖天数", formatCount(analytics.days_covered), `日均 ${analytics.avg_per_day || 0} 条`],
    ["主题标签", formatCount(analytics.topic_count), "支持主题频率与热度分析"],
    ["国家/地区", formatCount(analytics.country_count), `明确地理标签覆盖 ${taggedRate}`],
    ["来源数量", formatCount(analytics.source_count), "用于评估来源集中度"],
  ].map(([label, value, note]) => `<article class="analytics-kpi"><span>${esc(label)}</span><b>${esc(value)}</b><small>${esc(note)}</small></article>`).join("");
  renderLineChart("monthlyTrendChart", analytics.monthly_records || [], { x: "month", y: "count" });
  renderBarChart("topicBarChart", analytics.top_topics || [], { limit: 8, colorClass: "bar-fill" });
  renderBarChart("countryBarChart", analytics.top_countries || [], { limit: 10, colorClass: "bar-fill" });
  renderBarChart("continentBarChart", analytics.continents || [], { limit: 8, colorClass: "bar-fill alt" });
  renderBarChart("sourceBarChart", analytics.top_sources || [], { limit: 8, colorClass: "bar-fill alt" });
  renderHeatmap("countryTopicHeatmap", analytics.country_topic_matrix || {});
  $("analyticsNote").textContent = (analytics.notes || []).join(" ");
}

function renderLineChart(id, rows, { x, y }) {
  const element = $(id);
  if (!element) return;
  if (!rows.length) {
    element.innerHTML = '<div class="empty compact"><b>暂无趋势数据</b></div>';
    return;
  }
  const width = 920, height = 300, left = 54, right = 24, top = 20, bottom = 44;
  const values = rows.map(row => Number(row[y] || 0));
  const maxValue = Math.max(1, ...values);
  const span = Math.max(1, rows.length - 1);
  const px = index => left + index / span * (width - left - right);
  const py = value => top + (1 - value / maxValue) * (height - top - bottom);
  const points = rows.map((row, index) => [px(index), py(Number(row[y] || 0))]);
  const path = points.map((point, index) => `${index ? "L" : "M"}${point[0].toFixed(1)},${point[1].toFixed(1)}`).join(" ");
  const area = `${path} L${points.at(-1)[0].toFixed(1)},${height - bottom} L${points[0][0].toFixed(1)},${height - bottom} Z`;
  const tickIndexes = [...new Set([0, Math.floor(span / 3), Math.floor(span * 2 / 3), span])];
  const grid = [0, .25, .5, .75, 1].map(ratio => {
    const yy = top + ratio * (height - top - bottom);
    const label = Math.round(maxValue * (1 - ratio));
    return `<line class="chart-gridline" x1="${left}" y1="${yy}" x2="${width - right}" y2="${yy}"></line><text class="chart-muted" x="${left - 8}" y="${yy + 4}" text-anchor="end">${label}</text>`;
  }).join("");
  element.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="月度文本频率趋势图">
    ${grid}
    <path class="chart-area" d="${area}"></path>
    <path class="chart-line" d="${path}"></path>
    ${points.map((point, index) => index % Math.ceil(rows.length / 10) === 0 || index === rows.length - 1
      ? `<circle class="chart-dot" cx="${point[0]}" cy="${point[1]}" r="3.2"><title>${esc(rows[index][x])}: ${values[index]}</title></circle>`
      : "").join("")}
    <line class="chart-axis" x1="${left}" y1="${height - bottom}" x2="${width - right}" y2="${height - bottom}"></line>
    ${tickIndexes.map(index => `<text class="chart-muted" x="${px(index)}" y="${height - 15}" text-anchor="middle">${esc(rows[index][x])}</text>`).join("")}
  </svg>`;
}

function renderBarChart(id, rows, { limit = 8, colorClass = "bar-fill" } = {}) {
  const element = $(id);
  if (!element) return;
  const shown = rows.slice(0, limit);
  if (!shown.length) {
    element.innerHTML = '<div class="empty compact"><b>暂无分布数据</b></div>';
    return;
  }
  const width = 520, rowHeight = 34, left = 120, right = 54, top = 12;
  const height = top * 2 + shown.length * rowHeight;
  const maxValue = Math.max(1, ...shown.map(row => Number(row.count || 0)));
  element.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="分类频率条形图">
    ${shown.map((row, index) => {
      const y = top + index * rowHeight + 7;
      const barWidth = (width - left - right) * Number(row.count || 0) / maxValue;
      return `<text class="chart-label" x="${left - 10}" y="${y + 13}" text-anchor="end">${esc(row.name)}</text>
        <rect class="bar-track" x="${left}" y="${y}" width="${width - left - right}" height="16"></rect>
        <rect class="${colorClass}" x="${left}" y="${y}" width="${barWidth}" height="16"></rect>
        <text class="chart-value" x="${left + barWidth + 7}" y="${y + 12}">${formatCount(row.count)}</text>`;
    }).join("")}
  </svg>`;
}

function renderHeatmap(id, matrix) {
  const element = $(id);
  if (!element) return;
  const countries = matrix.countries || [];
  const topics = matrix.topics || [];
  const cells = matrix.cells || [];
  if (!countries.length || !topics.length) {
    element.innerHTML = '<div class="empty compact"><b>暂无交叉矩阵</b></div>';
    return;
  }
  const maxValue = Math.max(1, ...cells.map(cell => Number(cell.count || 0)));
  const cellMap = new Map(cells.map(cell => [`${cell.country}||${cell.topic}`, Number(cell.count || 0)]));
  element.innerHTML = `<div class="heatmap" style="--heatmap-columns:${topics.length}">
    <div class="heatmap-row header"><span></span>${topics.map(topic => `<span>${esc(topic)}</span>`).join("")}</div>
    ${countries.map(country => `<div class="heatmap-row">
      <span class="heatmap-country">${esc(country)}</span>
      ${topics.map(topic => {
        const value = cellMap.get(`${country}||${topic}`) || 0;
        const alpha = 0.08 + 0.82 * value / maxValue;
        const ink = alpha > 0.46 ? "#fff" : "#12223a";
        return `<span class="heat-cell" style="background:rgba(23,78,166,${alpha.toFixed(3)});color:${ink}" title="${esc(country)} / ${esc(topic)}：${value}">${value || ""}</span>`;
      }).join("")}
    </div>`).join("")}
  </div>`;
}

async function init() {
  const [dashboard, archive, analytics, energyDashboard, energyArchive, energyAnalytics] = await Promise.all([
    fetchJson("./data/dashboard.json"),
    fetchJson("./data/news_archive.json"),
    fetchJson("./data/corpus_analytics.json").catch(() => null),
    fetchJson("./data/energy_dashboard.json").catch(() => null),
    fetchJson("./data/energy_archive.json").catch(() => null),
    fetchJson("./data/energy_corpus_analytics.json").catch(() => null),
  ]);
  state.datasets.climate = { dashboard, archive, analytics };
  if (energyDashboard && energyArchive) {
    state.datasets.energy = { dashboard: energyDashboard, archive: energyArchive, analytics: energyAnalytics };
  }
  const requestedMode = localStorage.getItem("climateTextMode") === "energy" ? "energy" : "climate";
  activateMode(requestedMode);
  setupFilters();
  setupAssistant();
  setupMapPeriods();
  $("modeToggle")?.addEventListener("click", () => {
    activateMode(state.mode === "energy" ? "climate" : "energy");
  });
  try {
    await switchMapPeriod("today");
  } catch (error) {
    console.error("Map rendering failed", error);
    $("mapLoading").innerHTML = '<b>地图底图暂未载入</b><span>仍可点击下方地点查看今日气候情报。</span>';
    $("mapCanvas").classList.add("map-error");
  }
}

init().catch(error => {
  console.error(error);
  toast("气候情报数据读取失败，请稍后刷新页面。");
});
