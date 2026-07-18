const state = { dashboard: null, selectedMarker: null };
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

function markerElement(selector, markerId) {
  return Array.from(document.querySelectorAll(selector)).find(element => element.dataset.markerId === markerId) || null;
}

function scrollToRequestedSection() {
  if (!location.hash) return;
  const anchor = document.getElementById(location.hash.slice(1));
  if (anchor) requestAnimationFrame(() => anchor.scrollIntoView({ block:"start" }));
}

function settleRequestedSection() {
  scrollToRequestedSection();
  setTimeout(scrollToRequestedSection, 120);
  setTimeout(scrollToRequestedSection, 600);
}

function toast(message) {
  const el = $("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 3600);
}

async function fetchFirst(urls) {
  let lastError;
  for (const url of urls) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) throw new Error(`${response.status} ${url}`);
      return await response.json();
    } catch (error) { lastError = error; }
  }
  throw lastError;
}

function formatDate(value) {
  if (!value) return "时间待核";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", {
    month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit", hour12:false,
  });
}

function renderIntelligence(item) {
  const translation = item.translation_status === "human_reviewed" ? "人工校编" : "AI 编译 · 待复核";
  return `<article class="intel-card" id="card-${esc(item.article_id)}">
    <div class="intel-top"><span class="theme-badge">${esc(item.theme_zh || "气候动态")}</span><span class="translation-badge">${translation}</span></div>
    <h3>${esc(item.title_zh)}</h3>
    <b class="intel-abstract-label">中文概要</b>
    <p class="intel-summary">${esc(item.summary_zh)}</p>
    <div class="intel-why"><b>为什么值得关注</b><p>${esc(item.why_zh || "进入编辑复核队列。")}</p></div>
    <div class="intel-footer"><span>${esc(item.source_name)} · ${esc(formatDate(item.published_at))}</span><a href="${esc(safeUrl(item.canonical_url))}" target="_blank" rel="noopener noreferrer">打开原文 ↗</a></div>
  </article>`;
}

function renderDashboard(data) {
  state.dashboard = data;
  const items = (data.intelligence || []).filter(item => item.title_zh && item.summary_zh);
  if ($("briefDate")) $("briefDate").textContent = `${data.meta.date} · 今日全球气候动态`;
  if ($("posterDate")) $("posterDate").textContent = `${data.meta.date} · DAILY SIGNALS`;
  if ($("countdown")) $("countdown").textContent = Math.max(0, data.metrics.cop31_countdown);
  if ($("eventList")) {
    $("eventList").innerHTML = items.length
      ? items.slice(0, 10).map(renderIntelligence).join("")
      : '<div class="quality-empty"><b>今日暂无通过中文校验的情报</b><p>系统不会用英文原文、演示数据或后台状态填充此处。</p></div>';
  }
  const modelCount = items.filter(item => item.translation_status === "model_generated_needs_review").length;
  if ($("dataNote")) $("dataNote").textContent = modelCount
    ? `${modelCount} 条为 AI 编译待复核，其余为人工校编；所有概要均以中文发布。`
    : "标题与概要均为中文；点击原文可核对事实与数字。";
  renderPhrases(data.phrases || [], items);
  renderMapPlaceList(data.map_events || []);
  renderMap(data.map_events || [])
    .then(settleRequestedSection)
    .catch(() => {
      if ($("mapLoading")) $("mapLoading").textContent = "地图底图暂不可用，请使用下方地点按钮查看情报。";
      settleRequestedSection();
    });
  settleRequestedSection();
}

function renderPhrases(phrases, items) {
  const container = $("phraseCloud");
  if (!container) return;
  let usable = phrases.filter(item => item && item.text && item.theme).slice(0, 8);
  if (!usable.length) {
    usable = items.slice(0, 8).map((item, index) => ({
      text: item.poster_phrase || item.title_zh,
      theme: item.theme_zh || "气候动态",
      weight: Math.max(1, 8 - index),
    }));
  }
  if (!usable.length) usable = [{ text:"今日暂无通过中文校验的重点情报", theme:"等待编辑更新", weight:1 }];
  container.innerHTML = usable.map((item, index) => {
    const size = index === 0 ? 42 : Math.max(27, 35 - index);
    const fluid = index === 0 ? 3.1 : Math.max(1.8, 2.45 - index * .06);
    return `<div class="phrase" style="font-size:clamp(25px,${fluid}vw,${size}px)" data-theme="${esc(item.theme)}">${esc(item.text)}</div>`;
  }).join("");
}

function decodeArc(topology, arcIndex) {
  const reverse = arcIndex < 0;
  const source = topology.arcs[reverse ? ~arcIndex : arcIndex];
  const [sx, sy] = topology.transform.scale;
  const [tx, ty] = topology.transform.translate;
  let x = 0, y = 0;
  const points = source.map(([dx, dy]) => {
    x += dx; y += dy;
    return [x * sx + tx, y * sy + ty];
  });
  return reverse ? points.reverse() : points;
}

function worldPoint([lon, lat]) { return [(lon + 180) / 360 * 1000, (90 - lat) / 180 * 500]; }

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
    const crossesDateLine = index > 0 && Math.abs(point[0] - points[index - 1][0]) > 180;
    return `${index && !crossesDateLine ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join("") + "Z";
}

function geometryCrossesDateLine(topology, geometry) {
  const rings = geometry.type === "Polygon" ? geometry.arcs : geometry.arcs.flat();
  return rings.some(refs => {
    const points = ringCoordinates(topology, refs);
    return points.some((point, index) => index > 0 && Math.abs(point[0] - points[index - 1][0]) > 180);
  });
}

function geometryPath(topology, geometry) {
  if (geometry.type === "Polygon") return geometry.arcs.map(ring => ringPath(topology, ring)).join("");
  if (geometry.type === "MultiPolygon") return geometry.arcs.flatMap(polygon => polygon.map(ring => ringPath(topology, ring))).join("");
  return "";
}

function svgEl(name, attrs = {}) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function centeredPoint(lon, lat) {
  const chinaX = (105 + 180) / 360 * 1000;
  const baseX = (lon + 180) / 360 * 1000;
  const x = ((baseX - chinaX + 500) % 1000 + 1000) % 1000;
  return [x, (90 - lat) / 180 * 500];
}

function renderMapPlaceList(events) {
  const container = $("mapPlaceList");
  if (!container) return;
  const unique = [];
  const seen = new Set();
  events.forEach(event => {
    const key = `${event.place}|${event.article_id}`;
    if (!seen.has(key)) { seen.add(key); unique.push(event); }
  });
  container.innerHTML = unique.length
    ? unique.map(event => `<button type="button" data-marker-id="${esc(event.marker_id)}"><i></i>${esc(event.place)}<span>${esc(event.theme)}</span></button>`).join("")
    : '<span class="map-empty">今日暂无通过地理校验的事件点位</span>';
  container.querySelectorAll("button").forEach(button => {
    button.addEventListener("click", () => {
      const event = events.find(item => item.marker_id === button.dataset.markerId);
      if (event) selectMarker(event, markerElement(".event-pin", event.marker_id));
    });
  });
  if (events.length) selectMarker(events[0], null);
}

async function renderMap(events) {
  const response = await fetch("./assets/countries-110m.json", { cache:"force-cache" });
  if (!response.ok) throw new Error("map data unavailable");
  const topology = await response.json();
  const svg = $("worldMap");
  if (!svg) return;
  svg.innerHTML = "";
  const countryGroup = svgEl("g");
  topology.objects.countries.geometries.forEach(geometry => {
    const path = geometryPath(topology, geometry);
    const className = geometryCrossesDateLine(topology, geometry) ? "map-country seam-crossing" : "map-country";
    if (path) countryGroup.appendChild(svgEl("path", { d:path, class:className, "fill-rule":"evenodd" }));
  });
  const chinaX = (105 + 180) / 360 * 1000;
  const shift = 500 - chinaX;
  const leftCopy = countryGroup.cloneNode(true);
  leftCopy.setAttribute("transform", `translate(${shift},0)`);
  const rightCopy = countryGroup.cloneNode(true);
  rightCopy.setAttribute("transform", `translate(${shift + 1000},0)`);
  svg.append(leftCopy, rightCopy);
  const [cx, cy] = centeredPoint(105, 35);
  svg.appendChild(svgEl("path", { d:`M${cx - 5},${cy}H${cx + 5}M${cx},${cy - 5}V${cy + 5}`, class:"china-anchor" }));
  const chinaLabel = svgEl("text", { x:cx + 9, y:cy + 4, class:"china-label" });
  chinaLabel.textContent = "中国（地图中心）";
  svg.appendChild(chinaLabel);
  events.forEach((event, index) => addMarker(svg, event, index));
  if ($("mapLoading")) $("mapLoading").classList.add("hidden");
  const firstPin = document.querySelector(".event-pin");
  if (events.length) selectMarker(events[0], firstPin);
}

function addMarker(svg, event, index) {
  const [cx, cy] = centeredPoint(Number(event.lon), Number(event.lat));
  const pin = svgEl("g", {
    class:"event-pin", tabindex:"0", role:"button",
    "aria-label":`${event.place}：${event.title_zh}`,
    "data-marker-id":event.marker_id,
  });
  pin.appendChild(svgEl("circle", { cx, cy, r:13, class:"event-halo" }));
  pin.appendChild(svgEl("circle", { cx, cy, r:8, class:"event-marker" }));
  const number = svgEl("text", { x:cx, y:cy + 3.2, class:"event-marker-label" });
  number.textContent = String(index + 1);
  pin.appendChild(number);
  const title = svgEl("title");
  title.textContent = `${event.place}｜${event.title_zh}`;
  pin.appendChild(title);
  pin.addEventListener("mouseenter", browserEvent => showTooltip(browserEvent, event));
  pin.addEventListener("mousemove", browserEvent => showTooltip(browserEvent, event));
  pin.addEventListener("mouseleave", hideTooltip);
  pin.addEventListener("click", () => selectMarker(event, pin));
  pin.addEventListener("keydown", keyboardEvent => {
    if (keyboardEvent.key === "Enter" || keyboardEvent.key === " ") {
      keyboardEvent.preventDefault();
      selectMarker(event, pin);
    }
  });
  svg.appendChild(pin);
}

function showTooltip(event, item) {
  const tooltip = $("mapTooltip");
  const canvas = $("mapCanvas");
  if (!tooltip || !canvas) return;
  const bounds = canvas.getBoundingClientRect();
  tooltip.innerHTML = `<b>${esc(item.place)} · ${esc(item.theme)}</b>${esc(item.title_zh)}<small>点击查看中文概要与原文</small>`;
  tooltip.style.left = `${Math.min(bounds.width - 275, Math.max(8, event.clientX - bounds.left + 12))}px`;
  tooltip.style.top = `${Math.max(8, event.clientY - bounds.top - 82)}px`;
  tooltip.classList.add("show");
}

function hideTooltip() { if ($("mapTooltip")) $("mapTooltip").classList.remove("show"); }

function selectMarker(event, pin) {
  document.querySelectorAll(".event-pin.active").forEach(item => item.classList.remove("active"));
  document.querySelectorAll(".map-place-list button.active").forEach(item => item.classList.remove("active"));
  if (pin) pin.classList.add("active");
  const placeButton = markerElement(".map-place-list button", event.marker_id);
  if (placeButton) placeButton.classList.add("active");
  state.selectedMarker = event.marker_id;
  const detail = $("mapDetail");
  if (!detail) return;
  detail.innerHTML = `<span class="theme">${esc(event.place)} · ${esc(event.theme)}</span><h3>${esc(event.title_zh)}</h3><b class="map-abstract-label">中文概要</b><p>${esc(event.summary_zh)}</p><div class="detail-meta"><span>${esc(event.source_name)}</span><span>${esc(formatDate(event.published_at))}</span></div><a class="map-open-source" href="${esc(safeUrl(event.url))}" target="_blank" rel="noopener noreferrer">打开原文 ↗</a>`;
}

const dataUrls = location.protocol === "file:" ? ["./data/dashboard.json"] : ["/api/dashboard", "./data/dashboard.json"];
fetchFirst(dataUrls).then(renderDashboard).catch(() => toast("情报数据读取失败，请重新导出网站快照。"));
