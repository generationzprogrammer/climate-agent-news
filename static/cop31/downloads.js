/* COP31 · 文本数据库下载条（and the figures / full-archive files on the home page's database front, 2026-11-02）
   Reads downloads/manifest.json (written by the server's news database, deploy/newsdb) and offers its files
   by range (last 7 / 30 days, a month, everything) and format. Without a manifest — local preview, or a host
   that does not run the database — the bar stays hidden. Text follows <html lang>, like intel.js.
   2026-11-04: the manifest's `datasets` (the group's full-text datasets and the crawl archive) are listed under the bar
   in one list (user: no categories). `access: account` files live under datasets/ behind the group login: they open in
   a new tab, where the browser asks for the user name and password; public ones download directly. */
(() => {
  const bar = document.getElementById("dataExport");
  if (!bar) return;
  const root = document.documentElement;
  const en = () => (root.lang || "").startsWith("en");
  const base = "downloads/";
  const COPY = {
    zh: {
      range: "下载范围", format: "格式", download: "下载", all: "全部记录", last7d: "最近 7 天", last30d: "最近 30 天",
      month: (y, m) => `${y} 年 ${m} 月`, records: (n) => `${n} 条`, total: (n) => `共 ${n} 条记录`,
      span: (a, b) => `${a} 至 ${b}`, updated: (t) => `更新于 ${t}`, readme: "字段说明", empty: "该范围暂无记录",
      statRecords: "新闻记录", statSpan: "时间范围", statFields: "字段", statUpdated: "最近更新", homeFiles: "下载全部数据",
      statTopics: "治理议题", statCountries: "国家与地区", topicsValue: (n, d) => `${d} 大类 · ${n} 小类`,
      setsTitle: "全文数据库与研究数据集", images: (n) => `${n} 张`,
      setsNote: (n, a) => (a ? `共 ${n} 个数据集。带锁的 ${a} 个需组内账号：点击后浏览器会要求输入账号和密码；其余可直接下载。` : `共 ${n} 个数据集，均可直接下载。`),
      locked: "需组内账号",
    },
    en: {
      range: "Range", format: "Format", download: "Download", all: "All records", last7d: "Last 7 days", last30d: "Last 30 days",
      month: (y, m) => new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en", { month: "short", year: "numeric", timeZone: "UTC" }),
      records: (n) => `${n} records`, total: (n) => `${n} records`,
      span: (a, b) => `${a} – ${b}`, updated: (t) => `Updated ${t}`, readme: "Field guide", empty: "No records in this range",
      statRecords: "News records", statSpan: "Coverage", statFields: "Fields", statUpdated: "Last update", homeFiles: "Download everything",
      statTopics: "Governance topics", statCountries: "Countries & regions", topicsValue: (n, d) => `${d} categories · ${n} subcategories`,
      setsTitle: "Full-text and research datasets", images: (n) => `${n} images`,
      setsNote: (n, a) => (a ? `${n} datasets. The ${a} with a lock need a group account — your browser asks for the user name and password; the rest download directly.` : `${n} datasets, all free to download.`),
      locked: "Group account required",
    },
  };
  const FORMATS = { csv: "CSV", jsonl: "JSONL", sqlite: "SQLite", zip: "ZIP", images: "Images" };
  let manifest = null;
  let choice = { id: "last30d", format: "csv" };

  const t = () => COPY[en() ? "en" : "zh"];
  const num = (n) => Number(n || 0).toLocaleString(en() ? "en" : "zh-CN");
  const size = (b) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);
  const pad = (n) => String(n).padStart(2, "0");
  const stamp = (iso) => {
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "" : `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const el = (tag, props = {}, ...kids) => {
    const node = Object.assign(document.createElement(tag), props);
    node.append(...kids.filter((kid) => kid != null));
    return node;
  };
  const files = (id) => manifest.files.filter((f) => f.id === id);
  const pick = () => files(choice.id).find((f) => f.format === choice.format) || files(choice.id)[0];

  function rangeLabel(id) {
    if (COPY.zh[id]) return t()[id];
    const [y, m] = id.split("-").map(Number);
    return t().month(y, m);
  }

  function render() {
    const c = t();
    const months = [...new Set(manifest.files.filter((f) => f.scope === "month").map((f) => f.id))].sort().reverse();
    const range = el("select", { id: "exportRange" });
    for (const id of ["last7d", "last30d"]) range.append(el("option", { value: id, textContent: rangeLabel(id) }));
    const years = new Map();
    for (const id of months) {
      const year = id.slice(0, 4);
      if (!years.has(year)) years.set(year, el("optgroup", { label: year }));
      years.get(year).append(el("option", { value: id, textContent: rangeLabel(id) }));
    }
    range.append(...years.values(), el("option", { value: "all", textContent: c.all }));
    if (!files(choice.id).length) choice.id = "last30d";
    range.value = choice.id;

    const format = el("select", { id: "exportFormat" });
    for (const f of files(choice.id)) format.append(el("option", { value: f.format, textContent: FORMATS[f.format] || f.format }));
    if (!files(choice.id).some((f) => f.format === choice.format)) choice.format = "csv";
    format.value = choice.format;

    const file = pick();
    const link = el("a", { className: "export-go", id: "exportLink", href: base + file.path, download: downloadName(file) },
      el("span", { textContent: c.download }), el("small", { textContent: ` · ${size(file.bytes)}` }));
    if (!file.records) link.setAttribute("aria-disabled", "true");
    const note = file.records ? c.records(num(file.records)) : c.empty;

    const meta = el("p", { className: "export-meta" },
      el("span", {}, el("b", { textContent: c.total(num(manifest.records)) }), ` · ${c.span(manifest.coverage_from || manifest.date_min, manifest.date_max)}`),
      el("span", {}, `${c.updated(stamp(manifest.generated_at))} · `,
        el("a", { href: base + (manifest.readme || "README.txt"), target: "_blank", rel: "noopener", textContent: c.readme })));

    bar.replaceChildren(
      el("label", {}, el("span", { textContent: c.range }), range),
      el("label", {}, el("span", { textContent: c.format }), format),
      el("div", { className: "export-action" }, link, el("span", { className: "export-count", textContent: note })),
      meta,
    );
    range.addEventListener("change", () => { choice.id = range.value; render(); });
    format.addEventListener("change", () => { choice.format = format.value; render(); });
  }

  // The home page's database front (cop31.js / index.html .home-db): key figures and the full-archive files.
  const homeStats = document.getElementById("homeDbStats"), homeFiles = document.getElementById("homeDbFiles");
  function renderHome() {
    const c = t();
    if (homeStats) {
      const stat = (label, value) => el("div", {}, el("dt", { textContent: label }), el("dd", { textContent: value }));
      // 2026-11-05 (user: the home page shows the core figures — how many topics, how many countries — and leaves out
      // what users do not need): records, topics, countries, span; the field count and update stamp went
      const sum = manifest.summary || {};
      homeStats.replaceChildren(
        stat(c.statRecords, num(manifest.records)),
        ...(sum.topics ? [stat(c.statTopics, c.topicsValue(num(sum.topics), num(sum.domains)))] : []),
        ...(sum.countries ? [stat(c.statCountries, num(sum.countries))] : []),
        stat(c.statSpan, c.span(manifest.coverage_from || manifest.date_min, manifest.date_max)),
      );
      homeStats.hidden = false;
    }
    const everything = files("all");
    if (homeFiles && everything.length) {
      const links = everything.map((f) => el("a", { href: base + f.path, download: downloadName(f), textContent: FORMATS[f.format] || f.format, title: size(f.bytes) }));
      homeFiles.replaceChildren(el("span", { textContent: c.homeFiles }), ...links,
        el("a", { href: base + (manifest.readme || "README.txt"), target: "_blank", rel: "noopener", textContent: c.readme }));
      homeFiles.hidden = false;
    }
  }

  // The datasets under the bar: one list, one row per dataset (title, description, count, file buttons).
  const sets = document.getElementById("dataSets");
  const pickLang = (item, key) => (en() && item[`${key}_en`]) || item[key] || "";
  const fileLabel = (f) => (f.format === "txt" ? f.path.split("/").pop()
    : [FORMATS[f.format] || f.format.toUpperCase(), f.compression && f.compression !== f.format ? f.compression.toUpperCase() : ""].filter(Boolean).join(" · "));
  function renderSets() {
    const all = Array.isArray(manifest.datasets) ? manifest.datasets : [];
    if (!sets || !all.length) return;
    const c = t();
    const accountBase = manifest.datasets_account || "datasets/";
    const rows = all.map((d) => {
      const locked = d.access === "account";
      const links = d.files.map((f) => {
        const link = el("a", { href: (locked ? accountBase : base) + f.path, textContent: fileLabel(f) },
          el("small", { textContent: ` · ${size(f.bytes)}` }));
        if (locked) Object.assign(link, { className: "is-locked", target: "_blank", rel: "noopener", title: c.locked });
        else link.download = "";
        return link;
      });
      const count = d.records ? (d.unit === "images" ? c.images : c.records)(num(d.records)) : "";
      return el("li", { className: links.length > 2 ? "has-many-files" : "" },
        el("div", { className: "data-set-text" }, el("h4", { textContent: pickLang(d, "title") }), el("p", { textContent: pickLang(d, "description") })),
        el("span", { className: "data-set-count", textContent: count }),
        el("div", { className: "data-set-files" }, ...links));
    });
    sets.replaceChildren(
      el("div", { className: "data-sets-head" },
        el("h3", { textContent: c.setsTitle }),
        el("p", { textContent: c.setsNote(num(all.length), all.some((d) => d.access === "account") ? num(all.filter((d) => d.access === "account").length) : 0) })),
      el("ul", { className: "data-sets-list" }, ...rows));
    sets.hidden = false;
  }

  function downloadName(file) {
    const day = (manifest.generated_at || "").slice(0, 10).replaceAll("-", "");
    const ext = file.path.split("/").pop().replace(/^climate-news-[^.]+/, "");
    return `GRENN-climate-news-${file.id}-${day}${ext}`;
  }

  // one early request, shared with textdb.js / analysis.js (2026-11-07)
  (window.GreenManifest ||= fetch(base + "manifest.json", { priority: "high" })
    .then((response) => (response.ok ? response.json() : null)).catch(() => null))
    .then((data) => {
      if (!data || !Array.isArray(data.files)) return;
      manifest = data;
      // no bulk files (since 2026-11-05 every download is capped at 100 records and made from textdb.js's list):
      // the range / format bar stays hidden, the home figures still show
      const bulk = data.files.length > 0;
      const draw = () => { if (bulk) render(); renderHome(); renderSets(); };
      draw();
      bar.hidden = !bulk;
      new MutationObserver(draw).observe(root, { attributes: true, attributeFilter: ["lang"] });
    })
    .catch(() => {});
})();
