const state = { dashboard: null, archive: null, filtered: [], visible: 18, selected: null };
const $ = id => document.getElementById(id);
const esc = (value = "") => String(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const SVG_NS = "http://www.w3.org/2000/svg";

function safeUrl(value) {
  try {
    const url = new URL(value, location.href);
    if (url.protocol === "http:") url.protocol = "https:";
    return url.protocol === "https:" ? url.href : "#";
  } catch (_) { return "#"; }
}

function formatDate(value, withTime = false) {
  if (!value) return "时间待核";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", withTime
    ? {year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}
    : {year:"numeric",month:"2-digit",day:"2-digit"});
}

function toast(message) {
  const element = $("toast");
  if (!element) return;
  element.textContent = message;
  element.classList.add("show");
  setTimeout(() => element.classList.remove("show"), 3200);
}

async function fetchJson(url) {
  const response = await fetch(url, {cache:"no-store"});
  if (!response.ok) throw new Error(`${response.status} ${url}`);
  return response.json();
}

function qualityLabel(record) {
  const tier = record.quality?.tier || "B";
  return tier === "A" ? "A · 人工校编" : "B · AI 编译待复核";
}

function renderMeta() {
  const dashboard = state.dashboard;
  const archive = state.archive;
  $("archiveTotal").textContent = archive.total ?? 0;
  $("todayTotal").textContent = (dashboard.intelligence || []).length;
  $("sourceHealth").textContent = dashboard.metrics?.p0_connected ?? 0;
  $("datasetVersion").textContent = formatDate(archive.updated_at, true);
  $("generatedAt").textContent = `最近生成：${formatDate(dashboard.meta?.generated_at, true)}`;
  const modelCount = (dashboard.intelligence || []).filter(item => item.translation_status === "model_generated_needs_review").length;
  $("dataNote").textContent = modelCount
    ? `${modelCount} 条为 AI 编译待复核；点击原文复核数字与表述。`
    : "当前发布项均为人工校编；点击原文复核数字与表述。";
}

function findArchiveRecord(item) {
  return state.archive.records.find(record =>
    record.article_id === item.article_id || record.canonical_url === item.canonical_url
  ) || item;
}

function renderToday() {
  const items = (state.dashboard.intelligence || []).filter(item => item.title_zh && item.summary_zh);
  $("todayGrid").innerHTML = items.length ? items.slice(0, 8).map((item, index) => {
    const record = findArchiveRecord(item);
    const tier = record.quality?.tier || (item.translation_status === "human_reviewed" ? "A" : "B");
    return `<article class="signal-card" data-record-id="${esc(record.article_id)}">
      <div class="signal-index">${String(index + 1).padStart(2, "0")}</div>
      <div class="signal-content">
        <div class="signal-meta"><span class="topic">${esc(item.theme_zh || "气候动态")}</span><span class="quality tier-${tier.toLowerCase()}">${esc(tier)} 级</span></div>
        <h3>${esc(item.title_zh)}</h3>
        <p>${esc(item.summary_zh)}</p>
        <div class="signal-foot"><span>${esc(item.source_name)} · ${esc(formatDate(item.published_at))}</span><button type="button" data-select-record="${esc(record.article_id)}">查看信息分子 →</button></div>
      </div>
    </article>`;
  }).join("") : '<div class="empty"><b>今日暂无通过质量门禁的新记录</b><p>系统保留上一版高质量数据，不以英文占位或空摘要覆盖。</p></div>';
  document.querySelectorAll("[data-select-record]").forEach(button => button.addEventListener("click", () => {
    selectRecord(button.dataset.selectRecord);
    $("molecule").scrollIntoView({behavior:"smooth"});
  }));
}

function setupFilters() {
  const topics = [...new Set(state.archive.records.flatMap(record => record.topics || []))].sort((a, b) => a.localeCompare(b, "zh-CN"));
  $("topicFilter").innerHTML = '<option value="">全部议题</option>' + topics.map(topic => `<option value="${esc(topic)}">${esc(topic)}</option>`).join("");
  ["archiveSearch", "topicFilter", "qualityFilter"].forEach(id => $(id).addEventListener(id === "archiveSearch" ? "input" : "change", () => {
    state.visible = 18;
    applyFilters();
  }));
  $("loadMore").addEventListener("click", () => {
    state.visible += 18;
    renderArchiveRows();
  });
  $("archiveList").addEventListener("click", event => {
    const row = event.target.closest("[data-record-row]");
    if (!row || event.target.closest("a")) return;
    selectRecord(row.dataset.recordRow);
    $("molecule").scrollIntoView({behavior:"smooth"});
  });
}

function applyFilters() {
  const query = $("archiveSearch").value.trim().toLowerCase();
  const topic = $("topicFilter").value;
  const quality = $("qualityFilter").value;
  state.filtered = state.archive.records.filter(record => {
    const haystack = [
      record.title_zh, record.title_original, record.summary_zh, record.source_name,
      ...(record.topics || []), ...(record.places || []).map(place => place.name_zh),
    ].join(" ").toLowerCase();
    return (!query || haystack.includes(query))
      && (!topic || (record.topics || []).includes(topic))
      && (!quality || record.quality?.tier === quality);
  });
  renderArchiveRows();
}

function renderArchiveRows() {
  const shown = state.filtered.slice(0, state.visible);
  $("resultCount").textContent = state.filtered.length;
  $("archiveList").innerHTML = shown.length ? shown.map(record => {
    const tier = record.quality?.tier || "B";
    const atoms = [
      ...(record.numbers || []).slice(0, 2),
      ...(record.places || []).slice(0, 2).map(place => place.name_zh),
    ];
    return `<article class="archive-row" tabindex="0" data-record-row="${esc(record.article_id)}">
      <div class="archive-date"><b>${esc(formatDate(record.published_at))}</b><span class="quality tier-${tier.toLowerCase()}">${esc(tier)} 级</span><small>Q${esc(record.quality?.score ?? "—")}</small></div>
      <div class="archive-title"><h3>${esc(record.title_zh)}</h3><p>${esc(record.title_original)}</p></div>
      <div class="archive-source"><b>${esc(record.source_name)}</b><span>${esc((record.topics || []).slice(0, 2).join(" · ") || "气候动态")}</span></div>
      <div class="archive-atoms">${atoms.length ? atoms.map(atom => `<i>${esc(atom)}</i>`).join("") : "<i>文本记录</i>"}<a href="${esc(safeUrl(record.canonical_url))}" target="_blank" rel="noopener noreferrer">原文 ↗</a></div>
    </article>`;
  }).join("") : '<div class="empty compact"><b>没有匹配记录</b><p>请减少筛选条件或更换关键词。</p></div>';
  $("loadMore").hidden = state.visible >= state.filtered.length;
  document.querySelectorAll("[data-record-row]").forEach(row => row.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      selectRecord(row.dataset.recordRow);
      $("molecule").scrollIntoView({behavior:"smooth"});
    }
  }));
}

function selectRecord(articleId) {
  const record = state.archive.records.find(item => item.article_id === articleId);
  if (!record) return;
  state.selected = record;
  const molecule = record.molecule || {};
  const source = molecule.source_atom || {};
  const evidence = molecule.evidence_atom || {};
  document.querySelector(".atom-source").innerHTML = `<small>来源</small><b>${esc(source.name || record.source_name)}</b>`;
  document.querySelector(".atom-evidence").innerHTML = `<small>证据</small><b>${esc(evidence.quality_tier || record.quality?.tier || "B")} 级</b>`;
  document.querySelector(".atom-topic").innerHTML = `<small>议题</small><b>${esc((record.topics || [record.theme_zh])[0] || "气候动态")}</b>`;
  document.querySelector(".atom-number").innerHTML = `<small>数字</small><b>${esc((record.numbers || [])[0] || "无孤立数字")}</b>`;
  document.querySelector(".atom-geo").innerHTML = `<small>地域</small><b>${esc((record.places || []).map(place => place.name_zh).join("、") || "全球")}</b>`;
  $("moleculeTheme").textContent = record.theme_zh || (record.topics || [])[0] || "气候动态";
  $("moleculeScore").textContent = `Q${record.quality?.score ?? "—"}`;
  $("moleculeDetail").innerHTML = `
    <p class="record-id">${esc(record.article_id)} · ${esc(qualityLabel(record))}</p>
    <h3>${esc(record.title_zh)}</h3>
    <p class="molecule-summary">${esc(record.summary_zh)}</p>
    <dl class="molecule-facts">
      <div><dt>来源</dt><dd>${esc(record.source_name)}（权威度 ${esc(record.authority)}/5）</dd></div>
      <div><dt>政策信号</dt><dd>${esc(record.why_zh || "进入持续观察队列。")}</dd></div>
      <div><dt>证据状态</dt><dd>${esc(record.fact_status === "opinion_or_context" ? "观点或背景材料" : "来源陈述，需回原文核验")}</dd></div>
      <div><dt>内容哈希</dt><dd><code>${esc((record.content_hash || "").slice(0, 16))}</code></dd></div>
    </dl>
    <a class="primary-link" href="${esc(safeUrl(record.canonical_url))}" target="_blank" rel="noopener noreferrer">打开原始来源 ↗</a>`;
}

function svgEl(name, attrs = {}) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function decodeArc(topology, arcIndex) {
  const reverse = arcIndex < 0;
  const source = topology.arcs[reverse ? ~arcIndex : arcIndex];
  const [sx, sy] = topology.transform.scale;
  const [tx, ty] = topology.transform.translate;
  let x = 0, y = 0;
  const points = source.map(([dx, dy]) => { x += dx; y += dy; return [x * sx + tx, y * sy + ty]; });
  return reverse ? points.reverse() : points;
}

function worldPoint([lon, lat]) { return [(lon + 180) / 360 * 1000, (90 - lat) / 180 * 500]; }
function centeredPoint(lon, lat) {
  const chinaX = (105 + 180) / 360 * 1000;
  const baseX = (lon + 180) / 360 * 1000;
  return [((baseX - chinaX + 500) % 1000 + 1000) % 1000, (90 - lat) / 180 * 500];
}
function ringCoordinates(topology, refs) {
  const points = [];
  refs.forEach(ref => { const arc = decodeArc(topology, ref); points.push(...(points.length ? arc.slice(1) : arc)); });
  return points;
}
function ringPath(topology, refs) {
  const points = ringCoordinates(topology, refs);
  return points.map((point, index) => {
    const [x, y] = worldPoint(point);
    const seam = index > 0 && Math.abs(point[0] - points[index - 1][0]) > 180;
    return `${index && !seam ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join("") + "Z";
}
function geometryPath(topology, geometry) {
  if (geometry.type === "Polygon") return geometry.arcs.map(ring => ringPath(topology, ring)).join("");
  if (geometry.type === "MultiPolygon") return geometry.arcs.flatMap(poly => poly.map(ring => ringPath(topology, ring))).join("");
  return "";
}

async function renderMap(events) {
  const topology = await fetchJson("./assets/countries-110m.json");
  const svg = $("worldMap");
  svg.innerHTML = "";
  const group = svgEl("g");
  topology.objects.countries.geometries.forEach(geometry => {
    const path = geometryPath(topology, geometry);
    if (path) group.appendChild(svgEl("path", {d:path,class:"map-country","fill-rule":"evenodd"}));
  });
  const shift = 500 - (105 + 180) / 360 * 1000;
  const left = group.cloneNode(true); left.setAttribute("transform", `translate(${shift},0)`);
  const right = group.cloneNode(true); right.setAttribute("transform", `translate(${shift + 1000},0)`);
  svg.append(left, right);
  const [cx, cy] = centeredPoint(105, 35);
  svg.appendChild(svgEl("path", {d:`M${cx-6},${cy}H${cx+6}M${cx},${cy-6}V${cy+6}`,class:"china-anchor"}));
  const label = svgEl("text", {x:cx+10,y:cy+4,class:"china-label"}); label.textContent = "中国"; svg.appendChild(label);
  events.forEach((item, index) => {
    const [x, y] = centeredPoint(Number(item.lon), Number(item.lat));
    const pin = svgEl("g", {class:"event-pin",tabindex:"0",role:"button","data-marker":item.marker_id});
    pin.append(svgEl("circle",{cx:x,cy:y,r:12,class:"event-halo"}),svgEl("circle",{cx:x,cy:y,r:6,class:"event-marker"}));
    pin.addEventListener("click", () => selectMapEvent(item));
    pin.addEventListener("mouseenter", event => showMapTooltip(event, item));
    pin.addEventListener("mouseleave", () => $("mapTooltip").classList.remove("show"));
    svg.appendChild(pin);
    if (index === 0) selectMapEvent(item);
  });
  $("mapLoading").hidden = true;
}

function showMapTooltip(event, item) {
  const tooltip = $("mapTooltip");
  const bounds = $("mapCanvas").getBoundingClientRect();
  tooltip.innerHTML = `<b>${esc(item.place)} · ${esc(item.theme)}</b><span>${esc(item.title_zh)}</span>`;
  tooltip.style.left = `${Math.min(bounds.width - 260, Math.max(10, event.clientX - bounds.left + 10))}px`;
  tooltip.style.top = `${Math.max(10, event.clientY - bounds.top - 70)}px`;
  tooltip.classList.add("show");
}

function selectMapEvent(item) {
  $("mapDetail").innerHTML = `<span>${esc(item.place)} · ${esc(item.theme)}</span><h3>${esc(item.title_zh)}</h3><p>${esc(item.summary_zh)}</p><small>${esc(item.source_name)} · ${esc(formatDate(item.published_at))}</small><a href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">打开原文 ↗</a>`;
}

function renderMapPlaces(events) {
  $("mapPlaceList").innerHTML = events.length ? events.map(item => `<button type="button" data-map-id="${esc(item.marker_id)}"><i></i>${esc(item.place)}<span>${esc(item.theme)}</span></button>`).join("") : "<span>今日暂无通过地理校验的记录。</span>";
  document.querySelectorAll("[data-map-id]").forEach(button => button.addEventListener("click", () => {
    const item = events.find(event => event.marker_id === button.dataset.mapId);
    if (item) selectMapEvent(item);
  }));
}

async function init() {
  const [dashboard, archive] = await Promise.all([
    fetchJson("./data/dashboard.json"),
    fetchJson("./data/news_archive.json"),
  ]);
  state.dashboard = dashboard;
  state.archive = archive;
  renderMeta();
  renderToday();
  setupFilters();
  applyFilters();
  if (archive.records.length) selectRecord(archive.records[0].article_id);
  const events = dashboard.map_events || [];
  renderMapPlaces(events);
  try { await renderMap(events); }
  catch (_) { $("mapLoading").textContent = "地图底图暂不可用，请使用地点按钮查看记录。"; }
}

init().catch(error => {
  console.error(error);
  toast("数据读取失败；系统未用占位信息替代正式记录。");
});
