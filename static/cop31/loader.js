/* COP31 · 按需加载 (2026-11-07, user: 全面测试网站……加快加载速度，减少加载时间) — what only a later page needs is not fetched
   with the first one, so the first view gets the bandwidth (on a 4 Mbit/s link today's news and the statistics took ≈ 19 s,
   queued behind ≈ 6 MB nobody had asked for yet):
   1 research.js (研究工具) is loaded when the research page is first shown or a link to it is pointed at — and, where
     there is no text database (github.io), when the database page shows app.js's 原文语料 list, which reads the data
     research.js loads. Its address (with its version) is this script's data-research. Since 2026-11-13 the script no
     longer reads data/research_index.json (≈ 26 MB, ≈ 5 MB compressed) by itself on this page (data-index="lazy": only
     its 我的关注 tab does); the 原文语料 list asks for it here (GREEN_RESEARCH_LOAD).
   2 GreenLoad.json(path): one request per data file for the page's own scripts (intel.js, atlas/main.js and countries.js all
     read dashboard.json / countries-110m.json).
   3 images with data-defer-src / data-defer-srcset (the 国家专题 list photos) get their source once the page has loaded
     and the browser is idle, or at once when their page is shown or a link to it is pointed at.
   Loads nothing itself; markup and IDs are untouched. */
(() => {
  "use strict";
  const cache = new Map();
  const json = (path) => {
    const url = new URL(path, document.baseURI).href;
    if (!cache.has(url)) {
      const request = fetch(url).then((r) => { if (!r.ok) throw new Error(`${r.status} ${url}`); return r.json(); });
      request.catch(() => cache.delete(url)); // a failed request is tried again by the next caller
      cache.set(url, request);
    }
    return cache.get(url);
  };
  window.GreenLoad = { json };

  const researchSrc = document.currentScript?.dataset.research;
  let research = null;
  const loadResearch = (withIndex = false) => {
    if (!researchSrc) return;
    if (!research) {
      research = document.createElement("script");
      research.src = new URL(researchSrc, document.baseURI).href;
      research.dataset.index = withIndex ? "eager" : "lazy";
      document.body.append(research);
    } else if (withIndex) {
      if (window.GREEN_RESEARCH_LOAD) window.GREEN_RESEARCH_LOAD();
      else research.addEventListener("load", () => window.GREEN_RESEARCH_LOAD?.(), { once: true });
    }
  };

  const deferred = () => document.querySelectorAll("img[data-defer-src], img[data-defer-srcset]");
  const showImages = () => deferred().forEach((img) => {
    if (img.dataset.deferSrcset) img.srcset = img.dataset.deferSrcset;
    if (img.dataset.deferSrc) img.src = img.dataset.deferSrc;
    img.removeAttribute("data-defer-src"); img.removeAttribute("data-defer-srcset");
  });

  function start() {
    const page = (id, run) => {
      const section = document.getElementById(id);
      if (!section) return;
      new IntersectionObserver((entries, observer) => {
        if (entries.some((e) => e.isIntersecting)) { observer.disconnect(); run(); }
      }).observe(section);
    };
    page("research", () => loadResearch());
    page("countries", showImages);
    // app.js's 原文语料 list (shown where textdb.js finds no text database) reads research.js's data
    const db = document.getElementById("database");
    if (db) {
      let seen = false;
      const check = () => { if (seen && !db.classList.contains("has-textdb") && !db.classList.contains("textdb-pending")) loadResearch(true); };
      new IntersectionObserver((entries) => { seen = entries.some((e) => e.isIntersecting); check(); }).observe(db);
      new MutationObserver(check).observe(db, { attributes: true, attributeFilter: ["class"] });
    }
    const intent = (event) => {
      const link = event.target.closest?.("a[href]");
      if (!link) return;
      if (/#research$/.test(link.getAttribute("href"))) loadResearch();
      if (/#countries$/.test(link.getAttribute("href"))) showImages();
    };
    document.addEventListener("pointerover", intent, { passive: true });
    document.addEventListener("focusin", intent);
    const idle = window.requestIdleCallback ?? ((callback) => setTimeout(callback, 1500));
    const later = () => idle(showImages, { timeout: 4000 });
    document.readyState === "complete" ? later() : addEventListener("load", later, { once: true });
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
