/* GREEN · COP31 — 国家专题: the country / region pages (2026-11-12).
   Each .focus-country section (index.html) is one country or region; cop31/countries.js lays it out as a topic page
   (picture, giant title, content). This file fills it with every crawled news item of that place: the records of
   data/news_archive.json (already read by app.js: state.archive) whose country codes hold the section's code
   (data-country), or whose places carry one of its names (data-match; "=名" must be the whole name: 印度 is not 印度尼西亚), or whose organisations hold one of its codes
   (data-org: the EU). Newest first, twenty at a time; the tabs are the topics found, with their counts.
   Presentation only: the cards are app.js's own spotlight cards (spotlightCard), nothing is written back. */
(() => {
  "use strict";
  const root = document.documentElement;
  const sections = [...document.querySelectorAll(".focus-country[data-country]")];
  if (!sections.length) return;
  const en = () => (root.lang || "").startsWith("en");
  const esc = text => String(text ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
  const PAGE = 20;
  // the record topics, in the order of the tabs
  const TOPICS = [["国际气候谈判", "Climate talks"], ["国家气候承诺", "National pledges"], ["履约与全球盘点", "Compliance and stocktake"], ["能源与排放", "Energy and emissions"],
    ["气候资金", "Climate finance"], ["气候适应", "Adaptation"], ["气候动态", "Climate watch"], ["国际碳市场", "Carbon markets"]];
  const topicEn = new Map(TOPICS);
  const WORDS = {
    all: ["全部", "All"],
    count: [(n, a, b) => `共 ${n} 条相关新闻${a ? ` · ${a} 至 ${b}` : ""}`, (n, a, b) => `${n} news item${n === 1 ? "" : "s"}${a ? ` · ${a} to ${b}` : ""}`],
    none: ["暂无相关新闻", "No news yet"],
    more: ["显示更多", "Show more"],
  };
  const say = pair => pair[en() ? 1 : 0];
  const archive = () => { try { return state.archive?.records || null; } catch { return null; } }; // app.js's state (a global of the page)
  const views = new Map(); // section → { topic, shown, source, rows }

  function rowsOf(section, records) {
    const view = views.get(section) || { topic: "", shown: PAGE };
    views.set(section, view);
    if (view.source === records) return view;
    const code = section.dataset.country;
    const names = (section.dataset.match || "").split("|").filter(Boolean), orgs = (section.dataset.org || "").split("|").filter(Boolean);
    view.source = records;
    view.rows = records.filter(record =>
      (record.country_codes || []).some(country => country.alpha2 === code)
      || (record.places || []).some(place => names.some(name => name[0] === "=" ? place.name_zh === name.slice(1) : String(place.name_zh || "").includes(name)))
      || (orgs.length && (record.organization_tags || []).some(tag => orgs.includes(typeof tag === "string" ? tag : tag?.code))))
      .sort((a, b) => String(b.published_at || "").localeCompare(String(a.published_at || "")));
    return view;
  }
  const labelOf = record => {
    const topic = (record.topics || [])[0] || "";
    return en() ? topicEn.get(topic) || (typeof tr === "function" ? tr("archive") : "") : record.theme_zh || topic;
  };

  function render(section) {
    const records = archive();
    if (!records || typeof spotlightCard !== "function") return false;
    const view = rowsOf(section, records), all = view.rows;
    const tabs = section.querySelector(".fc-tabs"), list = section.querySelector(".fc-list"), more = section.querySelector(".fc-more"), count = section.querySelector(".fc-count");
    const found = TOPICS.map(([zh, english]) => ({ zh, english, n: all.filter(record => (record.topics || []).includes(zh)).length })).filter(topic => topic.n);
    if (view.topic && !found.some(topic => topic.zh === view.topic)) view.topic = "";
    tabs.innerHTML = [{ zh: "", english: "", n: all.length }, ...found].map(topic =>
      `<button class="${view.topic === topic.zh ? "active" : ""}" type="button" data-fc-topic="${esc(topic.zh)}">${esc(topic.zh ? (en() ? topic.english : topic.zh) : say(WORDS.all))}<small>${topic.n}</small></button>`).join("");
    tabs.hidden = !all.length;
    const rows = view.topic ? all.filter(record => (record.topics || []).includes(view.topic)) : all;
    list.innerHTML = rows.slice(0, view.shown).map(record => spotlightCard(record, labelOf(record))).join("") || `<div class="empty compact"><b>${esc(say(WORDS.none))}</b></div>`;
    more.hidden = rows.length <= view.shown;
    more.textContent = `${say(WORDS.more)} · ${rows.length - view.shown}`;
    const dates = all.map(record => String(record.published_at || "").slice(0, 10)).filter(Boolean);
    if (count) count.textContent = say(WORDS.count)(all.length, dates.at(-1), dates[0]);
    return true;
  }
  // the data may still be on its way (a direct load of a country page, a slow line: the archive is ≈ 2.4 MB): keep
  // asking for as long as the page is the one on screen
  function show(section) {
    if (!render(section)) setTimeout(() => { if (root.dataset.page === section.id) show(section); }, 400);
  }

  sections.forEach(section => section.addEventListener("click", event => {
    const tab = event.target.closest("[data-fc-topic]"), view = views.get(section);
    if (tab && view) { view.topic = tab.dataset.fcTopic || ""; view.shown = PAGE; render(section); return; }
    if (event.target.closest(".fc-more") && view) { view.shown += PAGE; render(section); }
  }));
  const current = () => sections.find(section => section.id === root.dataset.page);
  addEventListener("cop31:page", event => { const section = sections.find(s => s.id === event.detail?.page); if (section) show(section); });
  new MutationObserver(() => { const section = current(); if (section) render(section); }).observe(root, { attributes: true, attributeFilter: ["lang"] });
  const boot = () => { const section = current(); if (section) show(section); };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", boot) : boot();
})();
