/* COP31 · 文本数据库下载条
   Reads downloads/manifest.json (written by the server's news database, deploy/newsdb) and offers its files
   by range (last 7 / 30 days, a month, everything) and format. Without a manifest — local preview, or a host
   that does not run the database — the bar stays hidden. Text follows <html lang>, like intel.js. */
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
    },
    en: {
      range: "Range", format: "Format", download: "Download", all: "All records", last7d: "Last 7 days", last30d: "Last 30 days",
      month: (y, m) => new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en", { month: "short", year: "numeric", timeZone: "UTC" }),
      records: (n) => `${n} records`, total: (n) => `${n} records`,
      span: (a, b) => `${a} – ${b}`, updated: (t) => `Updated ${t}`, readme: "Field guide", empty: "No records in this range",
    },
  };
  const FORMATS = { csv: "CSV", jsonl: "JSONL", sqlite: "SQLite" };
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

  function downloadName(file) {
    const day = (manifest.generated_at || "").slice(0, 10).replaceAll("-", "");
    const ext = file.path.split("/").pop().replace(/^climate-news-[^.]+/, "");
    return `GRENN-climate-news-${file.id}-${day}${ext}`;
  }

  fetch(base + "manifest.json", { cache: "no-cache" })
    .then((response) => (response.ok ? response.json() : null))
    .then((data) => {
      if (!data || !Array.isArray(data.files) || !data.files.length) return;
      manifest = data;
      render();
      bar.hidden = false;
      new MutationObserver(render).observe(root, { attributes: true, attributeFilter: ["lang"] });
    })
    .catch(() => {});
})();
