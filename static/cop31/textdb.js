/* COP31 · 文本数据库检索（2026-11-05, user: the governance handover is the text database's history and the page shows it).
   When the server's downloads/manifest.json lists `search` (deploy/newsdb writes search-index.json since the governance
   history), this list replaces app.js's 原文语料 / 新闻元数据档案 list in #database: app.js's elements stay in the DOM
   (hidden by .has-textdb), so its IDs and hooks keep working. Search over title / Chinese title / excerpt / publisher,
   filters for the topics (since 2026-11-06 the 83 subcategories, grouped by their 14 categories, each category also as a
   whole), country and year; 20 rows at a time. "阅读全文" fetches the
   article's chunk (downloads/texts/tNNNN.json, 150 articles each) and shows the text in place; items collected after the
   history have no full text, only their excerpt and the source link. The index comes in parts (2026-11-06, 106,577
   rows): the newest 2,000 rows right after the manifest, the rest (`search.parts`) appended in turn; meanwhile the count
   ends in "…" and an empty result reads "loading". Since 2026-11-09 (240,064 rows, about 80 MB) the rest is fetched only
   when someone searches, filters or pages to the end of what is loaded; the first part carries the total (`records`) and
   the country and year filters' values (`facets`), so the list opens without it.
   2026-11-07 (user: 进入数据库后老是出现历史版本的界面): app.js's list is hidden from the start (.textdb-pending) and this
   list's frame shows as soon as the manifest is in, so the old list never flashes up while the index loads; it comes
   back only where there is no text database (no downloads/manifest.json `search`, e.g. github.io) or the index fails.
   2026-11-14 (the second batch: 436,983 rows, 22 parts, 42 MB compressed): a search or filter no longer brings the
   whole list into the browser. The page asks the server — /api/research/search (deploy/research), twenty rows a time in
   this index's own row format, every word of the query in title / Chinese title / excerpt / publisher — and keeps only
   the first part (the newest 2,000 rows, the filters' values, the total) for the opening view; 显示更多 goes on from
   the last row shown. The parts are still written and are read as before only where that service does not answer
   (a host without it, a local preview without `serve.mjs --api`).
   Text follows <html lang>; markup reuses the archive table's classes.
   Downloads (2026-11-05, user: 下载限制一次最多 100 条): rows can be ticked; 导出 writes the ticked rows — or, with none,
   the first 100 of the current results — as CSV or JSON with their full texts, at most LIMIT records at a time. */
(() => {
  "use strict";
  const section = document.getElementById("database");
  const anchor = document.getElementById("sourceArchiveModes");
  if (!section || !anchor) return;
  const root = document.documentElement;
  const en = () => (root.lang || "").startsWith("en");
  const base = "downloads/";
  // one early request for the manifest, shared with downloads.js / analysis.js (whichever runs first starts it)
  const manifestReady = (window.GreenManifest ||= fetch(`${base}manifest.json`, { priority: "high" })
    .then((r) => (r.ok ? r.json() : null)).catch(() => null));
  section.classList.add("textdb-pending");
  manifestReady.then((m) => { if (!m?.search?.path) section.classList.remove("textdb-pending"); });
  const PAGE = 20;
  const LIMIT = 100;
  const COPY = {
    zh: {
      search: "检索", placeholder: "搜索标题、摘录或来源", topic: "议题", allTopics: "全部议题", country: "国家", allCountries: "全部国家",
      year: "年份", allYears: "全部年份", results: "当前结果", date: "日期", record: "文本记录", source: "来源 / 议题", places: "国家",
      more: "显示更多记录", read: "阅读全文", close: "收起全文", link: "查看原文", loading: "正在载入…", failed: "全文暂时无法载入",
      none: "没有符合条件的记录", away: "检索暂时不可用，请稍后重试。", label: "全球气候治理新闻数据库", noText: "此条为每日新增新闻，仅有摘录，全文请查看原文。", unclassified: "未分类",
      domainAll: (name) => `${name}（全部）`,
      pick: "选择", picked: (n, max) => `已选 ${n} / ${max} 条`, exportCsv: "导出 CSV", exportJson: "导出 JSON", clear: "清除选择",
      exportNote: (max) => `一次最多导出 ${max} 条（含全文）；未勾选时导出当前结果的前 ${max} 条。`, exporting: "正在准备文件…",
      full: (max) => `最多选择 ${max} 条`,
      cols: ["日期", "标题", "中文标题", "来源", "主议题", "议题", "国家与地区", "原文链接", "正文", "来源库"],
      cohorts: { o: "原库补齐", n: "独立新增库", x: "全球扩展采集", s: "历史与定向补充", d: "每日新增" },
    },
    en: {
      search: "Search", placeholder: "Search titles, excerpts or publishers", topic: "Topic", allTopics: "All topics", country: "Country",
      allCountries: "All countries", year: "Year", allYears: "All years", results: "Results", date: "Date", record: "Text record",
      source: "Source / topic", places: "Countries", more: "Show more records", read: "Read full text", close: "Hide full text",
      link: "Open source", loading: "Loading…", failed: "The full text could not be loaded", none: "No records match",
      away: "Search is unavailable for the moment. Please try again later.",
      label: "Global climate governance news database", noText: "A daily item: only an excerpt is stored; read the full text at the source.",
      unclassified: "Unclassified", domainAll: (name) => `${name} (all)`,
      pick: "Select", picked: (n, max) => `${n} / ${max} selected`, exportCsv: "Export CSV", exportJson: "Export JSON", clear: "Clear",
      exportNote: (max) => `Up to ${max} records (with full text) per export; with none ticked, the first ${max} of the current results.`,
      exporting: "Preparing the file…", full: (max) => `At most ${max} records`,
      cols: ["date", "title", "title_zh", "publisher", "primary_topic", "topics", "countries", "url", "text", "collection"],
      cohorts: { o: "original archive (recovered)", n: "new library", x: "global expansion", s: "historical and targeted supplements", d: "daily" },
    },
  };
  const t = () => COPY[en() ? "en" : "zh"];
  const el = (tag, props = {}, ...kids) => {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...kids.filter((kid) => kid != null && kid !== ""));
    return node;
  };
  const num = (n) => Number(n || 0).toLocaleString(en() ? "en" : "zh-CN");

  let index = null, rows = [], hay = [], shown = PAGE, box = null, hits = [];
  let loading = false; // index parts still on their way
  let rest = []; // index parts not asked for yet
  let domainOf = new Map(); // subcategory → category
  const selected = new Set(); // keys of ticked rows (at most LIMIT)
  const seen = new Map(); // key → row of every row that was on screen (ticked rows may come from any search)
  // the server's search: ok null = not tried yet, false = not there (the index parts are used, as before)
  // painted: how many of its rows are on screen (rows stay, with any opened text, while further pages are added)
  const remote = { ok: null, hits: null, cursor: "", total: null, busy: false, failed: false, run: 0, stop: null, painted: 0 };
  const filtered = () => Boolean(filter.q || filter.topic || filter.country || filter.year);
  const chunks = new Map();
  const filter = { q: "", topic: "", country: "", year: "" };
  const F = {}; // field positions in a row

  const topicName = (id) => {
    const topic = index.topics.find((x) => x.id === id);
    return topic ? topic[en() ? "en" : "zh"] : t().unclassified;
  };
  const countryName = (code) => {
    const c = index.countries[code];
    return c ? c[en() ? 1 : 0] : code;
  };

  function matches(row, i) {
    if (filter.year && !row[F.date].startsWith(filter.year)) return false;
    if (filter.country && !(`,${row[F.countries]},`).includes(`,${filter.country},`)) return false;
    if (filter.topic) {
      const topics = row[F.topics] ? row[F.topics].split(",") : [];
      if (filter.topic.startsWith("d:")) {
        const domain = filter.topic.slice(2);
        if (!topics.some((id) => domainOf.get(id) === domain)) return false;
      } else if (!topics.includes(filter.topic)) return false;
    }
    if (filter.q) {
      if (!hay[i]) hay[i] = `${row[F.title]} ${row[F.title_zh]} ${row[F.excerpt]} ${row[F.publisher]}`.toLowerCase();
      return filter.q.split(/\s+/).every((word) => hay[i].includes(word));
    }
    return true;
  }

  // the countries (most mentioned first) and years of the whole index
  function fillOptions(country, year) {
    const c = t();
    country.replaceChildren(el("option", { value: "", textContent: c.allCountries }),
      ...(index.facets?.countries || []).map((code) => el("option", { value: code, textContent: countryName(code) })));
    year.replaceChildren(el("option", { value: "", textContent: c.allYears }), ...(index.facets?.years || []).map((y) => el("option", { value: y, textContent: y })));
    country.value = filter.country; year.value = filter.year;
  }

  function controls() {
    const c = t();
    const topic = el("select", { id: "textDbTopic" }, el("option", { value: "", textContent: c.allTopics }));
    for (const domain of index.domains) {
      const group = el("optgroup", { label: domain[en() ? "en" : "zh"] });
      group.append(el("option", { value: `d:${domain.id}`, textContent: c.domainAll(domain[en() ? "en" : "zh"]) }));
      for (const x of index.topics.filter((x) => x.domain === domain.id)) group.append(el("option", { value: x.id, textContent: x[en() ? "en" : "zh"] }));
      topic.append(group);
    }
    const country = el("select", { id: "textDbCountry" }), year = el("select", { id: "textDbYear" });
    fillOptions(country, year);
    const search = el("input", { id: "textDbSearch", type: "search", autocomplete: "off", placeholder: c.placeholder, value: filter.q });
    topic.value = filter.topic;
    let timer = 0;
    search.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(() => { filter.q = search.value.trim().toLowerCase(); refresh(); }, 250); });
    for (const [node, key] of [[topic, "topic"], [country, "country"], [year, "year"]]) node.addEventListener("change", () => { filter[key] = node.value; refresh(); });
    return el("div", { className: "search-panel textdb-panel" },
      el("label", { className: "search-box" }, el("span", { textContent: c.search }), search),
      el("label", {}, el("span", { textContent: c.topic }), topic),
      el("label", {}, el("span", { textContent: c.country }), country),
      el("label", {}, el("span", { textContent: c.year }), year),
      el("div", { className: "result-count" }, el("span", { textContent: c.results }), el("b", { id: "textDbCount", textContent: "—" })));
  }

  async function chunk(name) {
    if (!chunks.has(name)) chunks.set(name, fetch(`${base}texts/${name}.json`).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }));
    return chunks.get(name);
  }

  function rowNode(row) {
    const c = t();
    seen.set(row[F.key], row);
    const topics = row[F.topics] ? row[F.topics].split(",") : [];
    const codes = row[F.countries] ? row[F.countries].split(",") : [];
    const title = row[F.title_zh] && !en() ? row[F.title_zh] : row[F.title];
    const sub = row[F.title_zh] && !en() ? row[F.title] : row[F.excerpt];
    const full = el("div", { className: "archive-original textdb-full", hidden: true });
    const open = el("button", { type: "button", className: "textdb-open", textContent: c.read });
    const link = (href) => el("a", { href, target: "_blank", rel: "noopener noreferrer", textContent: c.link });
    open.addEventListener("click", async () => {
      if (!full.hidden) { full.hidden = true; open.textContent = c.read; return; }
      full.hidden = false; open.textContent = c.close;
      if (full.dataset.loaded) return;
      if (!row[F.text]) {
        full.replaceChildren(el("p", { className: "archive-source-excerpt", textContent: row[F.excerpt] || "" }), el("p", { className: "textdb-note", textContent: c.noText }), link(row[F.url]));
        full.dataset.loaded = "1";
        return;
      }
      full.replaceChildren(el("p", { className: "textdb-note", textContent: c.loading }));
      try {
        const doc = (await chunk(row[F.text]))[row[F.key]];
        const body = el("div", { className: "textdb-text" }, ...String(doc?.x || "").split(/\n{2,}/).filter((p) => p.trim()).map((p) => el("p", { textContent: p.trim() })));
        full.replaceChildren(body, link(doc?.u || ""));
        full.dataset.loaded = "1";
      } catch {
        full.replaceChildren(el("p", { className: "textdb-note", textContent: c.failed }));
      }
    });
    const pick = el("input", { type: "checkbox", checked: selected.has(row[F.key]) });
    pick.setAttribute("aria-label", `${c.pick}：${title}`);
    pick.addEventListener("change", () => {
      if (pick.checked && selected.size >= LIMIT) { pick.checked = false; status(c.full(LIMIT)); return; }
      if (pick.checked) selected.add(row[F.key]); else selected.delete(row[F.key]);
      status();
    });
    return el("article", { className: "archive-row textdb-row" },
      el("div", { className: "archive-date" }, el("label", { className: "textdb-pick" }, pick), el("b", { textContent: row[F.date].replaceAll("-", "/") })),
      el("div", { className: "archive-title" }, el("h3", { textContent: title }), sub ? el("p", { textContent: sub }) : null),
      el("div", { className: "archive-source" }, el("b", { textContent: row[F.publisher] }),
        el("span", { textContent: (topics.length ? topics.slice(0, 3).map(topicName) : [topicName("unclassified")]).join(" · ") })),
      el("div", { className: "archive-atoms" }, ...codes.slice(0, 4).map((code) => el("i", { textContent: countryName(code) })), open),
      full);
  }

  function status(message) {
    const node = box?.querySelector("#textDbPicked");
    if (node) node.textContent = message || t().picked(selected.size, LIMIT);
  }

  async function exportRows(format) {
    const c = t();
    let chosen = selected.size ? [...selected].map((key) => seen.get(key)).filter(Boolean).slice(0, LIMIT) : hits.slice(0, LIMIT);
    if (!chosen.length) return;
    status(c.exporting);
    // nothing ticked: the first LIMIT results — from the server when the list on screen holds fewer of them
    if (!selected.size && remote.hits && chosen.length < LIMIT && (remote.cursor || remote.busy)) {
      try { chosen = (await ask({ limit: LIMIT })).rows; } catch { /* the rows on screen stand in */ }
    }
    const texts = new Map();
    for (const name of new Set(chosen.map((row) => row[F.text]).filter(Boolean))) {
      try { const doc = await chunk(name); for (const row of chosen) if (row[F.text] === name && doc[row[F.key]]) texts.set(row[F.key], doc[row[F.key]]); } catch { /* the excerpt stands in */ }
    }
    const records = chosen.map((row) => {
      const doc = texts.get(row[F.key]);
      const topics = row[F.topics] ? row[F.topics].split(",") : [];
      return [row[F.date], row[F.title], row[F.title_zh], row[F.publisher], topicName(row[F.primary_topic] || "unclassified"),
        topics.map(topicName).join("; "), (row[F.countries] ? row[F.countries].split(",") : []).map(countryName).join("; "),
        doc?.u || row[F.url] || "", doc?.x || row[F.excerpt] || "", c.cohorts[row[F.cohort]] || row[F.cohort]];
    });
    let blob;
    if (format === "json") {
      const keys = COPY.en.cols;
      blob = new Blob([JSON.stringify(records.map((r) => Object.fromEntries(keys.map((k, i) => [k, r[i]]))), null, 1)], { type: "application/json" });
    } else {
      const cell = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
      blob = new Blob(["\ufeff" + [c.cols, ...records].map((r) => r.map(cell).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" });
    }
    const stamp = new Date().toISOString().slice(0, 10).replaceAll("-", "");
    const a = el("a", { href: URL.createObjectURL(blob), download: `GRENN-text-database-${stamp}-${records.length}.${format}` });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    status();
  }

  // ---- the server's search (2026-11-14)
  async function ask(extra = {}, signal) {
    const query = new URLSearchParams({ limit: PAGE, ...extra });
    for (const [key, value] of [["q", filter.q], ["topic", filter.topic.replace(/^d:/, "")], ["country", filter.country], ["year", filter.year]]) if (value) query.set(key, value);
    const response = await fetch(`/api/research/search?${query}`, { signal });
    if (!response.ok) throw new Error(response.status);
    return response.json();
  }
  // the cursor that continues after a row (the server pages on date, then key)
  const after = (row) => btoa(JSON.stringify([row[F.date], row[F.key]])).replaceAll("+", "-").replaceAll("/", "_");
  async function fetchRemote(reset) {
    const run = ++remote.run;
    remote.stop?.abort();
    remote.stop = new AbortController();
    if (reset) Object.assign(remote, { hits: [], cursor: "", total: null, painted: 0 });
    remote.busy = true; remote.failed = false;
    list();
    try {
      const page = await ask(remote.cursor ? { cursor: remote.cursor } : {}, remote.stop.signal);
      if (run !== remote.run) return;
      remote.ok = true;
      if (page.total != null) remote.total = page.total;
      remote.hits.push(...page.rows);
      remote.cursor = page.next_cursor || "";
    } catch (error) {
      if (run !== remote.run || error.name === "AbortError") return;
      if (remote.ok !== true) { // the service is not there: the index parts, as before
        Object.assign(remote, { ok: false, hits: null, busy: false });
        loadRest(); list();
        return;
      }
      remote.failed = true;
    }
    remote.busy = false;
    list();
  }
  // the filters changed
  function refresh() {
    shown = PAGE;
    if (remote.ok === false) { loadRest(); list(); return; }
    if (!filtered()) { remote.run++; remote.stop?.abort(); Object.assign(remote, { hits: null, busy: false, failed: false }); list(); return; }
    fetchRemote(true);
  }
  function showMore() {
    if (remote.hits) { if (!remote.busy && remote.cursor) fetchRemote(false); return; }
    if (remote.ok !== false && !filtered() && shown + PAGE > rows.length && rows.length) {
      // past the first part: the server goes on from the last row of it
      Object.assign(remote, { hits: rows.slice(), cursor: after(rows.at(-1)), total: index.records || null, painted: Math.min(shown, rows.length) });
      fetchRemote(false);
      return;
    }
    shown += PAGE;
    if (shown + PAGE >= rows.length) loadRest();
    list();
  }

  // keep: when more rows arrive, leave the shown rows (and any opened text) alone if they are still the same
  function list(keep = false) {
    const c = t();
    if (remote.hits) { // what the server found
      hits = remote.hits;
      const node = box.querySelector("#textDbList");
      box.querySelector("#textDbCount").textContent = remote.total == null ? "…" : num(remote.total);
      box.querySelector("#textDbMore").hidden = !remote.cursor || remote.busy;
      if (!remote.painted) node.replaceChildren();
      node.querySelector(":scope > .textdb-empty")?.remove();
      node.append(...hits.slice(remote.painted).map(rowNode));
      remote.painted = hits.length;
      const note = remote.busy ? c.loading : remote.failed ? c.away : !hits.length ? c.none : "";
      if (note) node.append(el("p", { className: "textdb-empty", textContent: note }));
      return;
    }
    const before = hits.slice(0, shown);
    hits = [];
    rows.forEach((row, i) => { if (matches(row, i)) hits.push(row); });
    const isFiltered = filtered();
    box.querySelector("#textDbCount").textContent = !rows.length ? "—" : isFiltered ? num(hits.length) + (loading ? "…" : "") : num(index.records || hits.length);
    box.querySelector("#textDbMore").hidden = remote.ok === false ? hits.length <= shown && !rest.length : !isFiltered && shown >= (index.records || rows.length);
    if (keep && before.length && before.length === Math.min(shown, hits.length) && before.every((row, i) => row === hits[i])) return;
    const items = hits.slice(0, shown).map(rowNode);
    box.querySelector("#textDbList").replaceChildren(...(items.length ? items : [el("p", { className: "textdb-empty", textContent: loading ? c.loading : c.none })]));
  }

  function render() {
    const c = t();
    const more = el("button", { type: "button", className: "load-more", id: "textDbMore", textContent: c.more });
    more.addEventListener("click", showMore);
    const table = el("div", { className: "archive-table letter textdb-table", role: "region" },
      el("div", { className: "archive-head" }, ...[c.date, c.record, c.source, c.places].map((text) => el("span", { textContent: text }))),
      el("div", { id: "textDbList" }));
    table.setAttribute("aria-label", c.label);
    const csv = el("button", { type: "button", className: "textdb-export", textContent: c.exportCsv });
    const json = el("button", { type: "button", className: "textdb-export", textContent: c.exportJson });
    const clear = el("button", { type: "button", className: "textdb-clear", textContent: c.clear });
    csv.addEventListener("click", () => exportRows("csv"));
    json.addEventListener("click", () => exportRows("json"));
    clear.addEventListener("click", () => { selected.clear(); box.querySelectorAll(".textdb-pick input").forEach((x) => { x.checked = false; }); status(); });
    const tools = el("div", { className: "textdb-tools" }, el("b", { id: "textDbPicked", textContent: c.picked(selected.size, LIMIT) }), csv, json, clear,
      el("p", { textContent: c.exportNote(LIMIT) }));
    const next = el("div", { className: "textdb", id: "textDb" }, controls(), tools, table, more);
    if (box) box.replaceWith(next); else anchor.before(next);
    box = next;
    remote.painted = 0; // a new frame (first drawing, another language): every row is drawn again
    list();
  }

  const get = (path) => fetch(base + path, { priority: "high" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  // the first part (≈ 0.3 MB; zerocarbonx.cn preloads it with the page, deploy/server/activate-release.sh) as soon as
  // the manifest is in, so the list is ready when the page is opened
  const firstReady = manifestReady.then((m) => (m?.search?.path ? get(m.search.path) : null));

  let started = false;
  async function start() {
    if (started) return;
    started = true;
    const manifest = await manifestReady;
    if (!manifest?.search?.path) return; // no governance history on this host: app.js's list stays
    // the frame at once (no filters yet, a loading line) while the first part comes
    index = { fields: [], topics: [], domains: [], countries: {}, rows: [] };
    loading = true;
    section.classList.add("has-textdb");
    render();
    new MutationObserver(render).observe(root, { attributes: true, attributeFilter: ["lang"] });
    const parts = manifest.search.parts || [];
    const first = await firstReady;
    if (!first?.rows?.length) { // no index after all: app.js's list comes back
      box.remove(); box = null;
      section.classList.remove("has-textdb", "textdb-pending");
      return;
    }
    index = first;
    index.fields.forEach((name, i) => { F[name] = i; });
    domainOf = new Map(index.topics.map((x) => [x.id, x.domain]));
    rows = index.rows;
    hay = new Array(rows.length);
    loading = false;
    rest = parts.slice();
    render();
    if (filtered()) refresh();
  }

  // the older rows, part after part, the first time they are needed
  async function loadRest() {
    if (loading || !rest.length || !rows.length) return;
    loading = true;
    while (rest.length) {
      const part = rest.shift();
      const more = await get(part.path);
      loading = rest.length > 0;
      for (const row of more?.rows || []) rows.push(row); // older rows: the order (newest first) holds
      hay.length = rows.length;
      list(true); // a missing part leaves the rows so far usable
    }
  }
  // fetch the index once the database page is on screen, or as soon as a link to it is pointed at
  new IntersectionObserver((entries, observer) => {
    if (entries.some((entry) => entry.isIntersecting)) { observer.disconnect(); start(); }
  }).observe(section);
  const intent = (event) => { if (event.target.closest?.('a[href$="#database"]')) start(); };
  document.addEventListener("pointerover", intent, { passive: true });
  document.addEventListener("focusin", intent);
})();
