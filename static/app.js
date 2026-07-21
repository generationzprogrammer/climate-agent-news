const state = { dashboard: null, archive: null, filtered: [], visible: 18 };
const $ = id => document.getElementById(id);
const esc = (value = "") => String(value).replace(/[&<>'"]/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[character]));
const SVG_NS = "http://www.w3.org/2000/svg";

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

function renderMeta() {
  const dashboard = state.dashboard;
  const archive = state.archive;
  const events = dashboard.map_events || [];
  const uniquePlaces = new Set(events.map(item => item.place).filter(Boolean));
  $("archiveTotal").textContent = archive.total ?? 0;
  $("todayTotal").textContent = (dashboard.intelligence || []).length;
  $("mapPlaceTotal").textContent = uniquePlaces.size;
  $("datasetVersion").textContent = formatDate(archive.updated_at, true);
  $("generatedAt").textContent = `最近生成：${formatDate(dashboard.meta?.generated_at, true)}`;
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
  const topics = [...new Set(state.archive.records.flatMap(record => record.topics || []))]
    .sort((left, right) => left.localeCompare(right, "zh-CN"));
  $("topicFilter").innerHTML = '<option value="">全部议题</option>'
    + topics.map(topic => `<option value="${esc(topic)}">${esc(topic)}</option>`).join("");
  ["archiveSearch", "topicFilter"].forEach(id => $(id).addEventListener(id === "archiveSearch" ? "input" : "change", () => {
    state.visible = 18;
    applyFilters();
  }));
  $("loadMore").addEventListener("click", () => {
    state.visible += 18;
    renderArchiveRows();
  });
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
  const chinaX = (105 + 180) / 360 * 1000;
  const baseX = (longitude + 180) / 360 * 1000;
  return [((baseX - chinaX + 500) % 1000 + 1000) % 1000, (90 - latitude) / 180 * 500];
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

async function renderMap(events) {
  const topology = await fetchJson(new URL("./assets/countries-110m.json", document.baseURI).href);
  if (!topology?.objects?.countries?.geometries?.length) throw new Error("invalid map topology");
  const svg = $("worldMap");
  svg.replaceChildren();
  const countries = svgEl("g", { "aria-hidden": "true" });
  topology.objects.countries.geometries.forEach(geometry => {
    const path = geometryPath(topology, geometry);
    if (path) countries.appendChild(svgEl("path", { d: path, class: "map-country", "fill-rule": "evenodd" }));
  });
  const shift = 500 - (105 + 180) / 360 * 1000;
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

  events.forEach((item, index) => {
    const longitude = Number(item.lon);
    const latitude = Number(item.lat);
    if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return;
    const [x, y] = centeredPoint(longitude, latitude);
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
    : "<span>今日暂无带有明确地理位置的新记录。</span>";
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
  const events = dashboard.map_events || [];
  renderMapPlaces(events);
  try {
    await renderMap(events);
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
