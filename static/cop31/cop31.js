/* GREEN · COP31 — motion layer for the paper edition.
   Presentation only: never changes data or app.js state. Specs: a frame-by-frame study of the reference sites.
   Modules: reveal roles · scroll-spy + section reel · smooth scroll · stamps (click = section slides up as a sheet) ·
            FLIP on tab/filter changes · number scramble · dialog flight · chart lightbox · drag-scroll ·
            sheet over the stage (wheel-driven works drawer) · page-edge rubber band.
   With prefers-reduced-motion every module jumps to its end state and app.js behaves as before. */
(() => {
  "use strict";
  const M = window.GreenMotion;
  const root = document.documentElement;
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = matchMedia("(hover: hover) and (pointer: fine)");
  const $ = id => document.getElementById(id);
  const make = (tag, className) => Object.assign(document.createElement(tag), { className });
  const esc = text => String(text).replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
  const SECTION_IDS = ["map", "today", "countries", "analytics", "assistant", "database"]; // menu / reel order
  // pages of their own; home = the stamp stage + 全球气候现场. The country topics are pages reached from 国家专题.
  const PAGE_IDS = ["today", "countries", "chinaCarbon", "singapore", "analytics", "assistant", "database"];
  const menuIdOf = id => (id === "chinaCarbon" || id === "singapore" ? "countries" : id); // a topic lights 国家专题

  /* ---------- Reveal roles (the reference spring/entrance study) ---------- */
  const ROLES = [
    { sel: ".section-heading", role: "text", rows: [[":scope > div > .overline"], [":scope > div > h2"], [":scope > p", ":scope > .compact-filter"]] },
    { sel: ".signal-card", role: "text", rows: [[".signal-index", ".signal-meta"], [".signal-content > h3"], [".signal-content > p"], [".signal-foot"]] },
    { sel: ".archive-row", role: "text", rows: [[".archive-date"], [".archive-title"], [".archive-source"], [".archive-atoms"]] },
    { sel: ".spotlight-card", role: "text", rows: [[".spotlight-card-meta"], [":scope > h3"], [":scope > p"], [".spotlight-card-foot"]], step: true },
    { sel: ".agency-card", role: "text", rows: [[":scope > b", ":scope > i"], [":scope > span"]], step: true },
    { sel: ".analytics-kpi", role: "text", rows: [[":scope > span"], [":scope > b"], [":scope > small"]], step: true },
    { sel: ".chart-heading", role: "text", rows: [[":scope > span"], [":scope > h3"], [":scope > p"]] },
    { sel: ".assistant-intro", role: "text", rows: [[".assistant-status"], [":scope > h3"], [":scope > p"], [".quick-prompts"]] },
    { sel: "body > footer", role: "text", rows: [[":scope > div:first-child"], [".footer-links"], [".cop31-credit"]] },
    { sel: ".map-canvas, .chart-box, .assistant-shell, .today-grid, .archive-table, .search-panel, .map-place-list, .spotlight-tabs, .analytics-note", role: "media" },
  ];
  const ROLE_SELECTOR = ROLES.map(def => def.sel).join(",");
  let suppressReveal = false; // set while FLIP owns freshly rendered nodes
  const revealObserver = "IntersectionObserver" in window ? new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const element = entry.target;
      element.setAttribute("data-revealed", "");
      revealObserver.unobserve(element);
      // Once shown, drop the stagger so later hover transitions start immediately.
      setTimeout(() => element.style.setProperty("--step", 0), 1200);
    });
  }, { rootMargin: "0px 0px -12% 0px", threshold: 0 }) : null;

  function prepare(element, def) {
    if (element.hasAttribute("data-reveal") || element.closest(".lightbox, [data-cop31-excluded]")) return;
    element.setAttribute("data-reveal", def.role);
    if (def.role === "text") {
      def.rows.forEach((group, index) => group.forEach(selector => element.querySelectorAll(selector).forEach(row => {
        row.setAttribute("data-row", "");
        row.style.setProperty("--row", index);
      })));
    }
    if (def.step && element.parentElement) {
      const siblings = [...element.parentElement.children].filter(child => child.matches(def.sel));
      element.style.setProperty("--step", Math.min(siblings.indexOf(element), 3));
    }
    if (!revealObserver || reducedMotion.matches || suppressReveal) showNow(element);
    else revealObserver.observe(element);
  }
  function showNow(element) {
    element.classList.add("reveal-now");
    element.setAttribute("data-revealed", "");
    revealObserver?.unobserve(element);
    requestAnimationFrame(() => requestAnimationFrame(() => element.classList.remove("reveal-now")));
  }
  function scan(node) {
    if (node.nodeType !== 1) return;
    ROLES.forEach(def => {
      if (node.matches(def.sel)) prepare(node, def);
      node.querySelectorAll(def.sel).forEach(element => prepare(element, def));
    });
  }
  // After a page turn lands, everything on screen is shown complete (the letter showed it that way).
  const revealInView = () => document.querySelectorAll("[data-reveal]:not([data-revealed])").forEach(element => {
    const rect = element.getBoundingClientRect();
    if (rect.bottom > 0 && rect.top < innerHeight) showNow(element);
  });

  /* ---------- Chinese / English chrome that app.js does not translate ---------- */
  const localize = () => {
    const en = root.lang.startsWith("en"), word = en ? "MENU" : "菜单", focus = en ? "Country focus" : "国家专题";
    document.querySelectorAll(".rail-label, .menu-pop-label").forEach(label => { label.textContent = word; });
    const home = en ? "Home" : "返回首页"; // the drop-down's way home (a link with morphing glyphs: compare its spoken label)
    document.querySelectorAll(".menu-home").forEach(item => { if ((item.querySelector(".sr-only")?.textContent ?? item.textContent) !== home) item.textContent = home; });
    const cueDown = document.querySelector(".scroll-cue-down .scroll-cue-label"), cueUp = document.querySelector(".scroll-cue-up .scroll-cue-label");
    if (cueDown) cueDown.textContent = en ? "Scroll down" : "向下滑动";
    if (cueUp) cueUp.textContent = en ? "Back up to home" : "向上回到首页";
    document.querySelectorAll(".nav-countries").forEach(item => { // the rail link holds morphing glyphs: compare its spoken label
      if ((item.querySelector(".sr-only")?.textContent ?? item.textContent) !== focus) item.textContent = focus;
    });
    document.querySelectorAll(".ct-place[data-en]").forEach(place => { place.dataset.zh ??= place.textContent; place.textContent = en ? place.dataset.en : place.dataset.zh; });
  };

  /* ---------- Scroll-spy (the reference writings page R5: 45 % line, last section at the page end) + reel ---------- */
  let holdId = null; // a navigation target stays current until the motion settles (no flicker through sections)
  let reel = null;
  const sectionsInPage = () => ["map", ...PAGE_IDS].map($).filter(section => section && !section.hidden && section.offsetParent !== null);
  function currentSectionId() {
    if (holdId) return holdId;
    const sections = sectionsInPage();
    if (!sections.length) return null;
    if (innerHeight + scrollY >= root.scrollHeight - 4) return sections.at(-1).id;
    let id = null;
    for (const section of sections) if (section.getBoundingClientRect().top <= innerHeight * .45) id = section.id;
    return id;
  }
  function setupSpy() {
    const links = [...document.querySelectorAll(".rail-menu nav a, .sheet nav a")];
    const idOf = link => decodeURIComponent(new URL(link.href, location.href).hash.slice(1));
    let current;
    const pick = () => {
      const id = menuIdOf(currentSectionId());
      if (id === current) return;
      current = id;
      links.forEach(link => link.classList.toggle("is-current", idOf(link) === id));
      reel?.setActive(id);
    };
    let queued = false;
    const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(() => { queued = false; pick(); }); } };
    addEventListener("scroll", schedule, { passive: true });
    addEventListener("resize", schedule);
    pick();
    return { refresh: () => { current = undefined; pick(); } };
  }

  function setupReel() {
    const box = document.querySelector(".reel");
    const track = box?.querySelector(".reel-track");
    if (!box || !track) return null;
    const labels = [...track.querySelectorAll("[data-reel]")];
    const ticks = [...box.querySelectorAll(".reel-ticks i")];
    const viewport = box.querySelector(".reel-viewport");
    const steps = [...document.querySelectorAll("[data-reel-step]")];
    let x = 0, motion = null, active = -1, widthMotion = null, width = 200;
    const centres = () => labels.map(label => label.offsetLeft + label.offsetWidth / 2);
    const paint = value => {
      x = value;
      track.style.transform = `translateX(${value.toFixed(2)}px)`;
      const mid = viewport.clientWidth / 2 - value, list = centres();
      labels.forEach((label, index) => {
        const blur = M.clamp((Math.abs(list[index] - mid) - 32) / 60, 0, 1) * .8; // distance blur
        label.style.filter = blur > .01 ? `blur(${blur.toFixed(2)}px)` : "";
      });
      let fractional = 0; // fractional index of the reel centre → progressive tick fill
      for (let index = 0; index < list.length - 1; index += 1) {
        if (mid >= list[index]) fractional = index + M.clamp((mid - list[index]) / (list[index + 1] - list[index]), 0, 1);
      }
      ticks.forEach((tick, index) => tick.style.setProperty("--lit", M.clamp(fractional - index + 1, 0, 1).toFixed(3)));
    };
    const targetFor = index => viewport.clientWidth / 2 - centres()[index];
    function setActive(id) {
      const index = Math.max(0, SECTION_IDS.indexOf(id ?? "map"));
      if (index === active && motion) return;
      active = index;
      labels.forEach((label, i) => label.classList.toggle("is-current", i === index));
      steps.forEach(button => button.setAttribute("aria-disabled", String(index + Number(button.dataset.reelStep) < 0 || index + Number(button.dataset.reelStep) >= labels.length)));
      motion?.stop();
      motion = M.spring(x, targetFor(index), M.SPRING.reel, { onUpdate: paint });
      const wanted = M.clamp(labels[index].offsetWidth + 120, 168, 280);
      widthMotion?.stop();
      widthMotion = M.spring(width, wanted, M.SPRING.width, { onUpdate: value => { width = value; box.style.setProperty("--reel-w", `${value.toFixed(1)}px`); } });
    }
    const go = index => {
      const id = SECTION_IDS[M.clamp(index, 0, labels.length - 1)], target = $(id);
      if (target) navigate("smooth", target); // another page → page swap (navigate)
    };
    labels.forEach((label, index) => label.addEventListener("click", event => { if (!box.dataset.dragged) go(index); event.preventDefault(); }));
    steps.forEach(button => button.addEventListener("click", () => go(active + Number(button.dataset.reelStep))));
    // Horizontal swipe on the capsule scrubs sections (hand-over at 70 % of the gap, carry .09 × velocity).
    let start = null;
    const velocity = M.sampler();
    box.addEventListener("pointerdown", event => { start = { x: event.clientX, base: x, t: performance.now(), last: event.clientX, lastT: performance.now() }; delete box.dataset.dragged; });
    addEventListener("pointermove", event => {
      if (!start) return;
      const dx = event.clientX - start.x;
      if (!box.dataset.dragged && Math.abs(dx) < 4) return;
      box.dataset.dragged = "1";
      const now = performance.now();
      velocity.push(event.clientX - start.last, 0, now - start.lastT, now);
      start.last = event.clientX; start.lastT = now;
      motion?.stop();
      const list = centres();
      const min = targetFor(list.length - 1), max = targetFor(0);
      paint(M.resistEdge(start.base + dx, min, max));
    });
    addEventListener("pointerup", () => {
      if (!start) return;
      const dragged = box.dataset.dragged;
      start = null;
      if (!dragged) return;
      const mid = viewport.clientWidth / 2 - (x + velocity.velocity().vx * .09);
      const list = centres();
      let index = 0, best = Infinity;
      list.forEach((centre, i) => { if (Math.abs(centre - mid) < best) { best = Math.abs(centre - mid); index = i; } });
      setTimeout(() => delete box.dataset.dragged, 300);
      if (index !== active) go(index); else setActive(SECTION_IDS[active]);
    });
    addEventListener("resize", () => { if (active >= 0) paint(targetFor(active)); });
    return { setActive };
  }

  /* ---------- Smooth scroll for in-page jumps (the reference writings page R6: 16·√Δ ms, cubic-bezier(.4,0,0,1)) ---------- */
  const bezier = (x1, y1, x2, y2) => x => {
    let lo = 0, hi = 1, t = x;
    for (let index = 0; index < 24; index += 1) {
      t = (lo + hi) / 2;
      const bx = 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t * t * x2 + t ** 3;
      if (bx < x) lo = t; else hi = t;
    }
    return 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t * t * y2 + t ** 3;
  };
  const scrollEase = bezier(.4, 0, 0, 1);
  function smoothScrollTo(top, maxMs = 800) {
    return new Promise(done => {
      const from = scrollY, distance = top - from;
      if (reducedMotion.matches || Math.abs(distance) < 2) { scrollTo(0, top); done(); return; }
      const duration = Math.min(16 * Math.sqrt(Math.abs(distance)), maxMs), start = performance.now();
      let raf = 0;
      const stop = () => { cancelAnimationFrame(raf); removeEventListener("wheel", stop); removeEventListener("touchstart", stop); done(); };
      addEventListener("wheel", stop, { passive: true });
      addEventListener("touchstart", stop, { passive: true });
      const step = now => {
        const p = Math.min((now - start) / duration, 1);
        scrollTo(0, from + distance * scrollEase(p));
        if (p < 1) raf = requestAnimationFrame(step); else stop();
      };
      raf = requestAnimationFrame(step);
    });
  }

  /* ---------- Stamps (the reference home page) ----------
     One rAF loop: value-noise drift (±8 px, ±1.5°, new target every ~3.1–3.6 s), the reference's discrete spring
     (k .03, d .72 per 1/120 s) for cursor follow ×0.05, scale 1.05 and tilt ±6°, a 36 px push along their own up-axis
     for stamps overlapping the hovered one, motion blur from spring velocity, and a label pill that rides along. */
  const hash = n => Math.abs(Math.sin(12.9898 * n + 78.233) * 43758.5453) % 1;
  const vnoise = x => { const n = Math.floor(x), f = x - n, s = f * f * (3 - 2 * f); return 2 * (hash(n) + (hash(n + 1) - hash(n)) * s) - 1; };
  const sp = (value = 0) => ({ cur: value, target: value, v: 0 });
  const springStep = (s, dt, k = .03, d = .72) => {
    for (let left = dt; left > 1e-6;) { const h = Math.min(1 / 120, left), u = h * 120; s.v += (s.target - s.cur) * k * u; s.v *= Math.pow(d, u); s.cur += s.v * u; left -= h; }
  };
  let stampHover = { drop() {} };

  // Relief material: one stamp at a time wears #stamp-relief; revealed over 1040 ms (ease-out cubic), lamp follows the pointer.
  const FINISH = { impasto: ["#fff4e6", "#ffe0b0"], gold: ["#ffe3a3", "#ffd27f"], silver: ["#eef0f2", "#e6e8ea"], kogei: ["#dcdce4", "#c9c9d2"] };
  const reliefReveal = document.querySelector("[data-relief-reveal]");
  const reliefLamp = document.querySelector("[data-relief-lamp]");
  let relief = null;
  function setRelief(art, finish) {
    if (relief?.art === art) return;
    relief?.art.classList.remove("is-relief");
    relief = null;
    if (!art || reducedMotion.matches) return;
    const [diffuse, specular] = FINISH[finish] || FINISH.impasto;
    document.querySelector("#stamp-relief feDiffuseLighting")?.setAttribute("lighting-color", diffuse);
    document.querySelector("#stamp-relief feSpecularLighting")?.setAttribute("lighting-color", specular);
    reliefReveal?.setAttribute("intercept", "0");
    relief = { art, start: performance.now(), lx: 0, ly: 0 };
    art.classList.add("is-relief");
  }
  function tickRelief(now, dt, nx, ny) { // nx, ny ∈ [−.5, .5]: pointer offset from the art's centre
    if (!relief) return;
    const t = Math.min(1, (now - relief.start) / 1040);
    reliefReveal?.setAttribute("intercept", (25 * (1 - (1 - t) ** 3)).toFixed(3));
    const ease = 1 - Math.exp(-dt / .125); // light position eased with τ = 125 ms
    relief.lx += (nx - relief.lx) * ease;
    relief.ly += (ny - relief.ly) * ease;
    const w = relief.art.clientWidth, h = relief.art.clientHeight;
    reliefLamp?.setAttribute("x", ((relief.lx + .5) * w).toFixed(1));
    reliefLamp?.setAttribute("y", ((relief.ly + .5) * h).toFixed(1));
    reliefLamp?.setAttribute("z", (.45 * w).toFixed(1));
  }

  function setupStamps() {
    const cluster = document.querySelector(".stamps");
    if (!cluster) return;
    const tip = cluster.querySelector(".stamp-tip");
    const list = [...cluster.querySelectorAll(".stamp")].map((el, index) => ({
      el, paper: el.querySelector(".stamp-paper"), art: el.querySelector(".stamp-art"),
      rot: parseFloat(getComputedStyle(el).getPropertyValue("--rot")) || 0,
      speed: .1 * (2.8 + .4 * hash(index * 7.1 + 1)),
      seed: [hash(index + 1) * 1000, hash(index + 1.3) * 1000 + 500, hash(index + 1.7) * 1000 + 1000],
      px: sp(), py: sp(), scale: sp(1), tx: sp(), ty: sp(), dx: 0, dy: 0, dr: 0, box: null, pressed: false,
    }));
    let hovered = null, pointer = { x: -1e4, y: -1e4 }, grace = 0, last = performance.now(), running = false, onScreen = true;
    const t0 = last;
    const measure = () => list.forEach(s => { // rest geometry in cluster coordinates, rotated bounding box
      const w = s.el.offsetWidth, h = s.el.offsetHeight, r = s.rot * Math.PI / 180;
      s.box = {
        cx: s.el.offsetLeft + w / 2, cy: s.el.offsetTop + h / 2,
        hw: (w * Math.abs(Math.cos(r)) + h * Math.abs(Math.sin(r))) / 2,
        hh: (w * Math.abs(Math.sin(r)) + h * Math.abs(Math.cos(r))) / 2,
      };
    });
    const overlaps = (a, b) => Math.abs(a.cx - b.cx) < a.hw + b.hw && Math.abs(a.cy - b.cy) < a.hh + b.hh;
    const setHover = s => {
      clearTimeout(grace);
      if (s === hovered) return;
      hovered?.el.classList.remove("lifted");
      hovered = s;
      if (s) {
        s.el.classList.add("lifted");
        cluster.dataset.focus = "";
        if (tip) { tip.textContent = s.el.querySelector(".stamp-label")?.textContent || ""; tip.classList.add("show"); } // no fade between stamps
        setRelief(s.art, s.el.dataset.finish);
      } else {
        delete cluster.dataset.focus;
        tip?.classList.remove("show");
        setRelief(null);
      }
      wake();
    };
    stampHover = { drop: () => setHover(null) };
    list.forEach(s => {
      s.el.addEventListener("pointerenter", event => { if (event.pointerType === "mouse") setHover(s); });
      s.el.addEventListener("pointerleave", event => {
        if (event.pointerType !== "mouse") return;
        clearTimeout(grace);
        grace = setTimeout(() => { if (hovered === s) setHover(null); }, 180); // 180 ms grace; entering another stamp switches directly
      });
      s.el.addEventListener("pointerdown", event => {
        if (event.pointerType !== "mouse") { pointer = { x: event.clientX, y: event.clientY }; setHover(s); }
        if (event.button === 0) { s.pressed = true; wake(); prepareSlide(s.el); } // the stamp gives under the finger; its sheet is readied
      });
      s.el.addEventListener("pointerleave", () => { s.pressed = false; });
      s.el.addEventListener("pointercancel", () => setHover(null));
      s.el.addEventListener("focus", () => setHover(s));
      s.el.addEventListener("blur", () => { if (hovered === s) setHover(null); });
    });
    addEventListener("pointerup", event => {
      list.forEach(s => { s.pressed = false; });
      if (event.pointerType !== "mouse") setTimeout(() => setHover(null), 250);
    });
    cluster.addEventListener("pointermove", event => { pointer = { x: event.clientX, y: event.clientY }; });

    const frame = now => {
      const dt = Math.min(.05, (now - last) / 1000);
      last = now;
      const t = (now - t0) / 1000, origin = cluster.getBoundingClientRect(), still = reducedMotion.matches;
      const target = hovered?.box;
      let nx = 0, ny = 0;
      for (const s of list) {
        if (!still) {
          s.dx = vnoise(t * s.speed + s.seed[0]) * 8;
          s.dy = vnoise(t * s.speed + s.seed[1]) * 8;
          s.dr = vnoise(t * s.speed + s.seed[2]) * 1.5;
        }
        if (s === hovered) {
          s.px.target = (pointer.x - (origin.left + s.box.cx)) * .05;
          s.py.target = (pointer.y - (origin.top + s.box.cy)) * .05;
          s.scale.target = s.pressed ? .985 : 1.05;
          const u = M.clamp((pointer.x - (origin.left + s.box.cx - s.box.hw)) / (2 * s.box.hw), 0, 1);
          const v = M.clamp((pointer.y - (origin.top + s.box.cy - s.box.hh)) / (2 * s.box.hh), 0, 1);
          s.tx.target = -(v - .5) * 12; // ±6°
          s.ty.target = (u - .5) * 12;
          nx = u - .5; ny = v - .5;
        } else {
          s.scale.target = 1; s.tx.target = 0; s.ty.target = 0;
          if (target && overlaps(s.box, target)) {
            const r = s.rot * Math.PI / 180;
            s.px.target = 36 * Math.sin(r);
            s.py.target = -36 * Math.cos(r);
          } else { s.px.target = 0; s.py.target = 0; }
        }
        for (const spring of [s.px, s.py, s.scale, s.tx, s.ty]) {
          if (still) { spring.cur = spring.target; spring.v = 0; } else springStep(spring, dt);
        }
        const blur = Math.max(0, Math.hypot(s.px.v, s.py.v) - 1) * 1.1; // motion blur above ~120 px/s
        s.el.style.transform = `translate(${(s.px.cur + s.dx).toFixed(2)}px, ${(s.py.cur + s.dy).toFixed(2)}px) rotate(${(s.rot + s.dr).toFixed(3)}deg)`;
        s.paper.style.transform = `rotateX(${s.tx.cur.toFixed(2)}deg) rotateY(${s.ty.cur.toFixed(2)}deg) scale(${s.scale.cur.toFixed(4)})`;
        s.paper.style.filter = blur > .05 ? `blur(${blur.toFixed(2)}px)` : "";
      }
      if (hovered && tip) {
        const rect = hovered.el.getBoundingClientRect(), half = tip.offsetWidth / 2;
        tip.style.translate = `${M.clamp(rect.left + rect.width / 2 - origin.left, half + 8, origin.width - half - 8).toFixed(1)}px ${(rect.top - origin.top).toFixed(1)}px`;
      }
      if (relief && hovered && relief.art === hovered.art) tickRelief(now, dt, nx, ny);
      if (awake()) requestAnimationFrame(frame); else running = false;
    };
    // asleep off screen, under the sheet, in a hidden tab, and under the 今日情报 layer (intel.js sets html.intel-open)
    const awake = () => onScreen && !stageCovered && !document.hidden && !root.classList.contains("intel-open");
    function wake() { if (!running && awake()) { running = true; last = performance.now(); requestAnimationFrame(frame); } }
    new MutationObserver(wake).observe(root, { attributes: true, attributeFilter: ["class"] });
    wakeStage = wake;
    new IntersectionObserver(([entry]) => { onScreen = entry.isIntersecting; wake(); }, { rootMargin: "200px" }).observe(cluster);
    document.addEventListener("visibilitychange", wake);
    addEventListener("resize", measure);
    measure();
    wake();

    // The map stamp prints a miniature of the live map once app.js has drawn it.
    const slot = cluster.querySelector("[data-stamp-map]");
    const map = $("worldMap");
    if (slot && map) {
      const copyMap = () => {
        if (!map.querySelector(".map-country")) return false;
        const mini = tidy(map.cloneNode(true));
        mini.removeAttribute("role");
        mini.removeAttribute("aria-label");
        mini.setAttribute("aria-hidden", "true");
        mini.querySelectorAll("[tabindex], [role]").forEach(node => { node.removeAttribute("tabindex"); node.removeAttribute("role"); });
        slot.replaceChildren(mini);
        return true;
      };
      if (!copyMap()) {
        const watcher = new MutationObserver(() => { if (copyMap()) watcher.disconnect(); });
        watcher.observe(map, { childList: true });
      }
    }
  }

  /* ---------- Clean copies (map stamp miniature, chart lightbox): no ids, no live regions, shown complete ---------- */
  function tidy(node) {
    node.removeAttribute?.("id");
    node.querySelectorAll?.("[id]").forEach(child => child.removeAttribute("id"));
    node.querySelectorAll?.("[aria-live]").forEach(child => child.removeAttribute("aria-live"));
    node.querySelectorAll?.(".lifted").forEach(child => child.classList.remove("lifted"));
    node.querySelectorAll?.("[data-focus]").forEach(child => delete child.dataset.focus);
    node.querySelectorAll?.("[data-reveal]").forEach(child => child.setAttribute("data-revealed", ""));
    return node;
  }

  /* ---------- Stamp → section: the destination slides up as a sheet (2026-10-29) ----------
     No zoom. The page the stamp names arrives as a sheet of paper from below the window, in the drawer's language: fold
     flap 18 → 6 px and an upward lift shadow on its top edge, backdrop (headings 15 % + blur 5 px) over what it covers.
     Spring k 220 c 24 (ζ ≈ .81: ≈ 1.3 % overshoot, covers the view at ≈ .29 s, settled by .48 s); the content rides 6 %
     behind the paper and settles into it; flap and shadow flatten out as the sheet lands. The real page moves to the
     section underneath the moment the sheet covers the view, and the sheet is lifted away once that page is drawn.
     Pressing a stamp prepares the sheet (drawn once where it will rest, 0.6 % opaque), so the release moves at once;
     keyboard activation builds it at click time. */
  const nextFrame = () => new Promise(done => requestAnimationFrame(() => done()));
  const SLIDE_S = .48, SLIDE_LAG = .06, SLIDE_SPARE = 48; // spare paper below the window for the overshoot
  const slideAt = (() => { // under-damped step response 0 → 1, k 220 c 24 m 1
    const w = Math.sqrt(220), z = 24 / (2 * w), wd = w * Math.sqrt(1 - z * z);
    return t => 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + z * w / wd * Math.sin(wd * t));
  })();
  const easeFlat = t => t * t * (3 - 2 * t), clamp01 = value => M.clamp(value, 0, 1);

  // The page as it will look at scroll position viewTop, from x = left to the window edge. Fixed parts (the desktop rail)
  // stay live above the sheet; the sticky stage is covered at every section.
  function viewClone(viewTop, left) {
    const page = make("div", "jump-page");
    const background = document.querySelector(".page-bg")?.cloneNode(true);
    if (background) { Object.assign(background.style, { position: "absolute", left: `${-left}px`, width: `${root.clientWidth}px` }); page.append(background); }
    const blocks = [...document.querySelector("main").children].flatMap(child => child.classList.contains("drawer-sheet") ? [...child.children] : [child]);
    for (const part of [document.querySelector(".rail"), ...blocks, document.querySelector("body > footer")]) {
      if (!part || part.hidden || part.matches(".drawer-paper, [data-cop31-excluded]")) continue;
      const style = getComputedStyle(part);
      if (style.display === "none" || style.position === "fixed" || style.position === "sticky") continue;
      const box = part.getBoundingClientRect(), top = box.top + scrollY - viewTop;
      if (!box.width || top >= innerHeight || top + box.height <= 0) continue;
      const copy = tidy(part.cloneNode(true));
      copy.classList.add("jump-clone");
      Object.assign(copy.style, { position: "absolute", left: `${box.left - left}px`, top: `${top}px`, width: `${box.width}px`, margin: "0", opacity: "", transform: "none" });
      page.append(copy);
    }
    return page;
  }
  function makeSlide(stamp, target) {
    const left = parseFloat(getComputedStyle(root).getPropertyValue("--sheet-x")) || 0;
    const page = withPage(pageOf(target), () => viewClone(landingTop(target), left)); // the destination page, laid out as it will land
    const sheet = make("div", "jump-sheet"), flap = make("div", "jump-flap"), backdrop = make("div", "jump-backdrop");
    sheet.setAttribute("aria-hidden", "true");
    sheet.append(page, flap);
    // Drawn once while the stamp is pressed: at its resting place, .6 % opaque. (Below 1/255 Chrome treats a layer as
    // transparent and skips rastering it, which would push the first paint into the first frames of the slide.)
    Object.assign(sheet.style, { left: `${left}px`, opacity: ".006" });
    Object.assign(backdrop.style, { left: `${left}px`, opacity: ".006" });
    document.body.append(backdrop, sheet);
    return { stamp, target, left, sheet, page, flap, backdrop, painted: nextFrame().then(nextFrame), taken: false };
  }
  let slidePrep = null;
  function dropSlide() {
    if (slidePrep && !slidePrep.taken) { slidePrep.sheet.remove(); slidePrep.backdrop.remove(); }
    slidePrep = null;
  }
  function prepareSlide(stamp) {
    dropSlide();
    if (busy || reducedMotion.matches) return;
    const target = document.getElementById(decodeURIComponent(new URL(stamp.href, location.href).hash.slice(1)));
    if (target && !intelOwns(target) && !focusEntry(target) && !blindsEntry(target)) slidePrep = makeSlide(stamp, target);
  }
  addEventListener("pointerup", () => setTimeout(() => { if (slidePrep && !slidePrep.taken) dropSlide(); }, 60)); // pressed, not clicked

  async function slideTo(target, stamp) {
    const ready = slidePrep?.stamp === stamp && slidePrep.target === target ? slidePrep : (dropSlide(), makeSlide(stamp, target));
    const leaving = pageOf(target) !== "home";
    if (leaving) root.classList.add("menu-away");
    ready.taken = true;
    slidePrep = null;
    const { sheet, page, flap, backdrop } = ready;
    const travel = innerHeight + SLIDE_SPARE;
    backdrop.style.opacity = "0";
    Object.assign(sheet.style, { transform: `translateY(${travel}px)`, opacity: "", pointerEvents: "auto" });
    await ready.painted;
    await nextFrame();
    await nextFrame();
    const steps = Math.round(SLIDE_S * 60), frames = { sheet: [], page: [], flap: [], backdrop: [] };
    let peak = 0, covered = SLIDE_S;
    for (let index = 0; index <= steps; index += 1) {
      const t = index / steps * SLIDE_S, p = index === steps ? 1 : slideAt(t), offset = index / steps;
      peak = Math.max(peak, p);
      if (p >= 1 && covered === SLIDE_S) covered = t;
      frames.sheet.push({ offset, transform: `translateY(${((1 - p) * travel).toFixed(2)}px)` });
      frames.page.push({ offset, transform: `translateY(${((1 - p) * travel * SLIDE_LAG).toFixed(2)}px)` });
      frames.flap.push({ offset, opacity: (1 - easeFlat(clamp01((peak - .86) / .14))).toFixed(3) });
      frames.backdrop.push({ offset, opacity: clamp01(p).toFixed(3) });
    }
    const start = document.timeline.currentTime;
    const run = (element, keyframes) => { const animation = element.animate(keyframes, { duration: SLIDE_S * 1000, easing: "linear", fill: "forwards" }); animation.startTime = start; return animation; };
    const motion = [run(sheet, frames.sheet), run(page, frames.page), run(flap, frames.flap), run(backdrop, frames.backdrop)];
    // On the sheet's own clock (not a timer), so the hand-off stays exact whatever the frame rate or playback rate.
    await new Promise(done => { const check = () => (motion[0].currentTime ?? 0) >= covered * 1000 || motion[0].playState === "finished" ? done() : requestAnimationFrame(check); check(); });
    land(target); // the sheet covers the view: move the real page underneath
    stampHover.drop(); // released under the sheet, so the pile does not repaint while it rises
    scrambleDescriptor();
    await Promise.all(motion.map(animation => animation.finished));
    await nextFrame();
    await nextFrame();
    sheet.remove();
    backdrop.remove();
    if (leaving) root.classList.remove("menu-away");
  }

  /* ---------- Pages (2026-10-29, after 100lostspecies) ----------
     Home is the stamp stage and 全球气候现场 only, so scrolling down ends there. Every other section is a page of its own:
     html[data-page] + .page-on, and CSS hides the rest (the sections stay in the DOM; app.js renders them as before).
     今日情报 opens the intelligence experience instead (intel.js, window.GreenIntel); without it, it is a page too. */
  const pageOf = target => {
    const section = target?.closest?.(".drawer-sheet > .section");
    return section && PAGE_IDS.includes(section.id) ? section.id : "home";
  };
  const currentPage = () => root.dataset.page || "home";
  const intelOwns = target => target?.id === "today" && !!window.GreenIntel?.ready?.();
  // 国家专题 from any other page comes in behind the reference's six-column overlay (countries.js, window.GreenFocus)
  const focusEntry = target => target?.id === "countries" && currentPage() !== "countries" && !!window.GreenFocus?.open && !reducedMotion.matches;
  // …and so do 语料分析 / 情报问答 / 文本数据库 (2026-10-29): the same overlay, the page's own entrance under it
  const BLIND_PAGES = ["analytics", "assistant", "database"];
  const blindsEntry = target => BLIND_PAGES.includes(target?.id) && currentPage() !== target.id && !!window.GreenFocus?.blinds && !reducedMotion.matches;
  function markPage(page) {
    root.dataset.page = page;
    root.classList.remove("menu-open");
    document.querySelector(".menu-pop")?.setAttribute("aria-expanded", "false");
    document.querySelectorAll(".drawer-sheet > .section").forEach(section => section.classList.toggle("page-on", section.id === (page === "home" ? "map" : page)));
  }
  let onPageChange = () => {};
  function setPage(page) {
    if (page === currentPage()) return;
    markPage(page);
    onPageChange(page); // the sheet over the stage runs on the home page only
    spy?.refresh();
    chromeRefresh();
    dispatchEvent(new CustomEvent("cop31:page", { detail: { page } })); // countries.js choreographs its own pages
  }
  function withPage(page, measure) { // lay the page out as `page` just long enough to measure or copy it
    const was = currentPage(), y = scrollY;
    if (page === was) return measure();
    markPage(page);
    try { return measure(); } finally {
      markPage(was);
      if (Math.abs(scrollY - y) > .5) scrollTo({ top: y, behavior: "instant" });
    }
  }

  /* ---------- Navigation ---------- */
  let busy = false;
  const targetTop = target => Math.max(0, target.getBoundingClientRect().top + scrollY - 16); // same offset as app.js
  const landingTop = target => pageOf(target) === "home" ? targetTop(target) : 0; // a page opens at its top
  const setHash = target => history.replaceState(history.state, "", `${location.pathname}${location.search}#${encodeURIComponent(target.id)}`);
  const inViewport = element => { const rect = element.getBoundingClientRect(); return rect.width && rect.bottom > 0 && rect.top < innerHeight; };
  function land(target) {
    setPage(pageOf(target));
    scrollTo({ top: landingTop(target), behavior: "instant" });
    setHash(target);
    revealInView();
  }
  function settle(target) {
    if (target.matches("section") && !target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
    target.focus?.({ preventScroll: true });
    dispatchEvent(new Event("scroll")); // app.js refreshes aria-current
  }
  // Rail / menu jump = the reference's page swap: hard cut, the landed screen replays its entrance (60 ms cascade),
  // and the header descriptor scrambles for 1 s.
  function jumpTo(target) {
    setPage(pageOf(target));
    scrollTo({ top: landingTop(target), behavior: "instant" });
    setHash(target);
    if (reducedMotion.matches) { revealInView(); return; }
    const blocks = [...document.querySelectorAll("[data-reveal]")].filter(inViewport);
    blocks.forEach(element => { element.classList.add("reveal-now"); element.removeAttribute("data-revealed"); revealObserver?.unobserve(element); });
    void document.body.offsetWidth;
    blocks.forEach((element, index) => {
      element.classList.remove("reveal-now");
      element.style.setProperty("--step", (Math.min(index, 8) * 1.2).toFixed(1)); // 60 ms per block
      element.setAttribute("data-revealed", "");
      setTimeout(() => element.style.setProperty("--step", 0), 1600);
    });
    scrambleDescriptor();
  }

  async function navigate(kind, target, link = null) {
    if (busy) return;
    root.classList.remove("menu-open");
    const menu = $("mobileMenu");
    if (menu && !menu.hidden) $("mobileMenuToggle")?.click();
    if (intelOwns(target)) { window.GreenIntel.open(link); return; }
    busy = true;
    holdId = SECTION_IDS.includes(target.id) ? target.id : null;
    spy?.refresh();
    try {
      if (reducedMotion.matches) land(target);
      else if (focusEntry(target)) await window.GreenFocus.open(() => { setHash(target); if (kind === "stamp") stampHover.drop(); });
      else if (blindsEntry(target)) {
        await window.GreenFocus.blinds(true); // the columns close over the old page
        jumpTo(target); // the page swaps underneath and starts its entrance
        if (kind === "stamp") stampHover.drop();
        await window.GreenFocus.blinds(false); // .3 s later they open, right to left
      }
      else if (kind === "stamp") await slideTo(target, link);
      else if (kind === "smooth" && pageOf(target) === currentPage()) {
        await smoothScrollTo(targetTop(target));
        setHash(target);
      } else jumpTo(target);
      settle(target);
    } catch (error) {
      console.error("navigation motion failed", error);
      land(target);
    } finally {
      busy = false;
      setTimeout(() => { holdId = null; spy?.refresh(); }, 150); // hold the target 150 ms after motion stops
    }
  }

  document.addEventListener("click", event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest?.(".rail-menu nav a, .sheet nav a, a.stamp, a.brand");
    if (!link) return;
    const url = new URL(link.href, location.href);
    if (url.pathname !== location.pathname || !url.hash) return;
    const target = document.getElementById(decodeURIComponent(url.hash.slice(1)));
    if (!target) return;
    const samePage = pageOf(target) === currentPage() && !intelOwns(target);
    if (reducedMotion.matches && samePage) return; // app.js scrolls within the page
    event.preventDefault();
    event.stopImmediatePropagation(); // app.js would smooth-scroll; the reference cuts
    // Menu links cut (reference page swap); a stamp sends its page up as a sheet (no enlarging flight, 2026-10-29).
    if (samePage && link.classList.contains("brand") && sheetClose()) return;
    if (samePage && Math.abs(targetTop(target) - scrollY) < 4) return;
    navigate(link.classList.contains("stamp") ? "stamp" : "jump", target, link);
  }, true);
  // A hash typed into the address bar (or history) picks the page too; app.js scrolls to the section afterwards.
  addEventListener("hashchange", () => {
    const target = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!target) return;
    if (window.GreenFocus?.owns(target.id) || window.GreenFocus?.owns(currentPage())) return; // 国家专题 routes itself (countries.js)
    if (intelOwns(target)) { window.GreenIntel.open(null, { instant: true }); return; }
    if (pageOf(target) === currentPage()) return;
    setPage(pageOf(target));
    scrollTo({ top: landingTop(target), behavior: "instant" });
    revealInView();
  });

  /* ---------- FLIP when app.js re-renders lists after a tab / filter change ---------- */
  const FLIPS = [
    { trigger: "[data-carbon-topic], [data-singapore-agency]", event: "click", items: "#carbonSpotlightList .spotlight-card, #singaporeSpotlightList .spotlight-card, #carbonAgencies .agency-card, #singaporeAgencies .agency-card",
      key: element => element.matches(".agency-card") ? `a|${element.getAttribute("href")}` : `s|${element.querySelector("h3")?.textContent}|${element.querySelector(".spotlight-card-meta span:last-child")?.textContent}` },
    { trigger: "[data-map-period]", event: "click", items: "#mapPlaceList button", key: element => element.dataset.mapId },
    { trigger: "#todayOrganizationFilter", event: "change", items: "#todayGrid .signal-card", key: element => element.querySelector("h3")?.textContent },
    { trigger: "#topicFilter, #organizationFilter", event: "change", items: "#archiveList .archive-row", key: element => element.querySelector("h3")?.textContent },
  ];
  function setupFlip() {
    ["click", "change"].forEach(type => document.addEventListener(type, event => {
      if (reducedMotion.matches) return;
      const def = FLIPS.find(entry => entry.event === type && event.target.closest?.(entry.trigger));
      if (!def) return;
      const before = M.flip.measure([...document.querySelectorAll(def.items)], def.key);
      suppressReveal = true;
      requestAnimationFrame(() => {
        suppressReveal = false;
        M.flip.play(before, [...document.querySelectorAll(def.items)], def.key);
      });
    }, true));
  }

  /* ---------- Number scramble on change (the reference spring/entrance study; first value is not scrambled) ---------- */
  function setupScramble() {
    const busyElements = new WeakSet(), lastText = new Map();
    const watch = element => {
      lastText.set(element, element.textContent);
      new MutationObserver(() => {
        if (busyElements.has(element)) return;
        const before = lastText.get(element), after = element.textContent;
        lastText.set(element, after);
        if (!before || before === after || /^[—\-0]$/.test(before.trim())) return;
        busyElements.add(element);
        M.scramble(element, before, after).then(() => busyElements.delete(element));
      }).observe(element, { childList: true, characterData: true, subtree: true });
    };
    ["todayMapCount", "weekMapCount", "resultCount"].map($).filter(Boolean).forEach(watch);
  }

  /* ---------- 数据统计 (2026-10-29): the title, and the charts app.js draws, dressed and set in motion ----------
     The page is called 数据统计 now (app.js writes its own title on load and on a language switch: it is put back).
     Each chart sits on a square paper plate (cop31.css). When a chart comes into view — or is drawn again while in
     view — it enters: the line draws itself left to right over a gradient area (1.8 s, expo out), its points pop as it
     passes, the last month keeps a slow pulse; bars grow from the left 70 ms apart while their figures count up riding
     the bar ends; the heat matrix surfaces along its diagonals; the KPI figures count up. Under the pointer the line
     shows a crosshair, a focus dot and a month · count tag that glide to the nearest month; bar rows and heat cells
     light up (a cell lights its row and column). Reading only: app.js's data and markup stay; reduced motion shows the
     end state. */
  function setupCharts() {
    // the menu word too (rail, drop-down, phone menu, reel, stamp): 数据统计 / Statistics. app.js writes 语料分析 into these
    // on load and on a language switch; it is put back (the menu links hold morphing glyphs: their spoken label is compared)
    const navWord = () => root.lang.startsWith("en") ? "Statistics" : "数据统计";
    const navFix = element => { if ((element.querySelector(".sr-only")?.textContent ?? element.textContent).trim() !== navWord()) element.textContent = navWord(); };
    document.querySelectorAll('[data-i18n="navAnalytics"]').forEach(element => {
      new MutationObserver(() => navFix(element)).observe(element, { childList: true, characterData: true, subtree: true });
      navFix(element);
    });
    new MutationObserver(() => document.querySelectorAll('[data-i18n="navAnalytics"]').forEach(navFix)).observe(root, { attributes: true, attributeFilter: ["lang"] });
    const page = $("analytics");
    if (!page) return;
    const title = $("analyticsTitle");
    const fixTitle = () => { const want = root.lang.startsWith("en") ? "Data statistics" : "数据统计"; if (title.textContent !== want) title.textContent = want; };
    if (title) {
      new MutationObserver(fixTitle).observe(title, { childList: true, characterData: true, subtree: true });
      new MutationObserver(fixTitle).observe(root, { attributes: true, attributeFilter: ["lang"] });
      fixTitle();
    }
    const NS = "http://www.w3.org/2000/svg", EXPO = "cubic-bezier(.16, 1, .3, 1)";
    const expo = t => t >= 1 ? 1 : 1 - Math.pow(2, -10 * t), clamp01 = v => Math.min(1, Math.max(0, v));
    const node = (name, attrs = {}) => { const e = document.createElementNS(NS, name); Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v)); return e; };
    const appState = () => { try { return state; } catch { return null; } }; // app.js's own data (a global of the page)
    const figure = (n, sample) => /,/.test(sample) ? Math.round(n).toLocaleString("en-US") : String(Math.round(n));
    const inView = element => { const r = element.getBoundingClientRect(); return r.width > 0 && r.bottom > 0 && r.top < innerHeight; };
    // coming in behind the blinds: start as the columns open over the left of the page (~1 s after the swap)
    const soon = fn => root.classList.contains("blinds-on") ? setTimeout(fn, 1000) : requestAnimationFrame(fn);
    let uid = 0;
    // a monotone cubic through the points (Fritsch–Carlson): smooth, and never overshooting a month
    const monotone = pts => {
      const n = pts.length, dx = [], m = [], t = [];
      for (let i = 0; i < n - 1; i += 1) { dx[i] = pts[i + 1][0] - pts[i][0] || 1e-6; m[i] = (pts[i + 1][1] - pts[i][1]) / dx[i]; }
      t[0] = m[0]; t[n - 1] = m[n - 2];
      for (let i = 1; i < n - 1; i += 1) t[i] = m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2;
      for (let i = 0; i < n - 1; i += 1) {
        if (!m[i]) { t[i] = t[i + 1] = 0; continue; }
        const a = t[i] / m[i], b = t[i + 1] / m[i], s = a * a + b * b;
        if (s > 9) { const k = 3 / Math.sqrt(s); t[i] = k * a * m[i]; t[i + 1] = k * b * m[i]; }
      }
      let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
      for (let i = 0; i < n - 1; i += 1) {
        const h = dx[i] / 3;
        d += ` C${(pts[i][0] + h).toFixed(1)},${(pts[i][1] + t[i] * h).toFixed(1)} ${(pts[i + 1][0] - h).toFixed(1)},${(pts[i + 1][1] - t[i + 1] * h).toFixed(1)} ${pts[i + 1][0].toFixed(1)},${pts[i + 1][1].toFixed(1)}`;
      }
      return d;
    };

    function dressLine(box, svg) {
      const line = svg.querySelector(".chart-line"), area = svg.querySelector(".chart-area");
      const pts = (line.getAttribute("d").match(/-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?/g) || []).map(p => p.split(",").map(Number));
      if (pts.length < 2 || !area) return false;
      const base = Number(svg.querySelector(".chart-axis")?.getAttribute("y1")) || 256;
      const grid = [...svg.querySelectorAll(".chart-gridline")], top = Number(grid[0]?.getAttribute("y1")) || 20;
      const curve = monotone(pts);
      line.setAttribute("d", curve);
      area.setAttribute("d", `${curve} L${pts.at(-1)[0]},${base} L${pts[0][0]},${base} Z`);
      const id = `c31-area-${uid += 1}`, defs = node("defs");
      defs.innerHTML = `<linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#c8372d" stop-opacity=".26"/><stop offset=".72" stop-color="#c8372d" stop-opacity=".05"/><stop offset="1" stop-color="#c8372d" stop-opacity="0"/></linearGradient>`;
      svg.prepend(defs);
      area.style.fill = `url(#${id})`;
      const plot = node("g", { class: "c31-plot" }), dots = [...svg.querySelectorAll(".chart-dot")];
      area.before(plot);
      plot.append(area, line, ...dots);
      const last = pts.at(-1);
      plot.append(node("circle", { class: "c31-pulse", cx: last[0], cy: last[1], r: 4 }));
      const cross = node("line", { class: "c31-cross", x1: last[0], x2: last[0], y1: top, y2: base });
      const focus = node("circle", { class: "c31-focus", cx: last[0], cy: last[1], r: 5.5 });
      svg.append(cross, focus);
      const tip = make("div", "c31-tip");
      tip.setAttribute("aria-hidden", "true");
      box.append(tip);
      const max = Number((svg.querySelector(".chart-muted")?.textContent || "").replace(/[^\d.]/g, "")) || 0; // the top grid label
      box.c31 = { kind: "line", svg, plot, dots, grid, pts, cross, focus, tip, base, top, max, cx: last[0], cy: last[1], target: pts.length - 1, shown: -1, rows: appState()?.analytics?.monthly_records || [] };
      return true;
    }
    function dressBars(box, svg) {
      const fills = [...svg.querySelectorAll(".bar-fill")], tracks = [...svg.querySelectorAll(".bar-track")];
      const values = [...svg.querySelectorAll(".chart-value")], labels = [...svg.querySelectorAll(".chart-label")];
      const rows = fills.map((fill, i) => {
        const y = Number(fill.getAttribute("y"));
        [fill, tracks[i]].forEach(e => { e?.setAttribute("y", y + 4); e?.setAttribute("height", 8); }); // slimmer bars
        const text = values[i]?.textContent || "";
        return { fill, label: labels[i], value: values[i], text, n: Number(text.replace(/[^\d.]/g, "")) || 0, x0: Number(fill.getAttribute("x")), w: Number(fill.getAttribute("width")), cy: y + 8 };
      });
      if (!rows.length) return false;
      rows[0].fill.classList.add("c31-top");
      const pitch = rows.length > 1 ? rows[1].cy - rows[0].cy : 34;
      box.c31 = { kind: "bars", svg, rows, pitch, hot: -1 };
      return true;
    }
    function dressHeat(box, heat) {
      const head = [...heat.querySelectorAll(".heatmap-row.header > span")].slice(1);
      [...heat.querySelectorAll(".heatmap-row:not(.header)")].forEach((row, r) => [...row.querySelectorAll(".heat-cell")].forEach((cell, c) => {
        cell.style.setProperty("--d", `${(r + c) * 36}ms`); // along the diagonals
        cell.dataset.col = c;
      }));
      let on = null;
      const mark = cell => {
        if (on === cell) return;
        on?.closest(".heatmap-row")?.classList.remove("c31-row");
        head.forEach(h => h.classList.remove("c31-col"));
        on = cell;
        if (!cell) return;
        cell.closest(".heatmap-row").classList.add("c31-row");
        head[Number(cell.dataset.col)]?.classList.add("c31-col");
      };
      heat.addEventListener("pointerover", event => mark(event.target.closest?.(".heat-cell") || null));
      heat.addEventListener("pointerleave", () => mark(null));
      box.c31 = { kind: "heat" };
      return true;
    }

    // the state before the entrance, and the entrance
    function hide(box) {
      const c = box.c31;
      if (!c || reducedMotion.matches) return;
      box.dataset.c31State = "wait";
      if (c.kind === "line") {
        c.plot.style.clipPath = "inset(-12% 100% -12% 0)";
        c.dots.forEach(dot => { dot.style.transform = "scale(0)"; });
        c.grid.forEach(line => { line.style.opacity = "0"; });
      }
      if (c.kind === "bars") c.rows.forEach(r => { r.fill.style.transform = "scaleX(0)"; if (r.value) r.value.style.opacity = "0"; });
      if (c.kind === "heat") box.classList.add("c31-wait");
    }
    function play(box) {
      const c = box.c31;
      if (!c || box.dataset.c31State !== "wait") return;
      box.dataset.c31State = "in";
      box.closest(".chart-card")?.classList.add("c31-in");
      if (c.kind === "line") {
        c.plot.style.clipPath = "";
        c.plot.animate([{ clipPath: "inset(-12% 100% -12% 0)" }, { clipPath: "inset(-12% 0% -12% 0)" }], { duration: 1800, easing: EXPO });
        c.grid.forEach((line, i) => { line.style.opacity = ""; line.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 900, delay: i * 70, easing: "linear", fill: "backwards" }); });
        const x0 = c.pts[0][0], span = c.pts.at(-1)[0] - x0 || 1;
        c.dots.forEach(dot => {
          dot.style.transform = "";
          const f = (Number(dot.getAttribute("cx")) - x0) / span;
          dot.animate([{ transform: "scale(0)" }, { transform: "scale(1)" }], { duration: 650, delay: 120 + 900 * Math.sqrt(f), easing: "cubic-bezier(.34, 1.56, .64, 1)", fill: "backwards" });
        });
      }
      if (c.kind === "bars") {
        c.rows.forEach((r, i) => { r.fill.style.transform = ""; r.fill.animate([{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], { duration: 1300, delay: i * 70, easing: EXPO, fill: "backwards" }); });
        const t0 = performance.now();
        const step = now => {
          let more = false;
          c.rows.forEach((r, i) => {
            if (!r.value) return;
            const p = expo(clamp01((now - t0 - i * 70) / 1300));
            r.value.style.opacity = p > 0 ? "" : "0";
            r.value.textContent = p >= 1 ? r.text : figure(r.n * p, r.text);
            r.value.setAttribute("x", (r.x0 + r.w * p + 7).toFixed(1)); // rides the bar end
            if (p < 1) more = true;
          });
          if (more) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }
      if (c.kind === "heat") requestAnimationFrame(() => box.classList.remove("c31-wait"));
    }

    // the line under the pointer: the nearest month, reached by easing (crosshair, focus dot, tag)
    function follow(box, c) {
      const ctm = c.svg.getScreenCTM(), frame = box.getBoundingClientRect();
      if (!ctm) return;
      const [tx, ty] = c.pts[c.target];
      c.cx += (tx - c.cx) * .24; c.cy += (ty - c.cy) * .24;
      if (Math.abs(tx - c.cx) < .2 && Math.abs(ty - c.cy) < .2) { c.cx = tx; c.cy = ty; }
      c.cross.setAttribute("x1", c.cx.toFixed(2)); c.cross.setAttribute("x2", c.cx.toFixed(2));
      c.focus.setAttribute("cx", c.cx.toFixed(2)); c.focus.setAttribute("cy", c.cy.toFixed(2));
      if (c.shown !== c.target) {
        c.shown = c.target;
        const row = c.rows[c.target], value = row ? Number(row.count || 0) : Math.round(c.max * (c.base - ty) / Math.max(1, c.base - c.top));
        c.tip.innerHTML = `${row?.month ? `<span>${esc(row.month)}</span>` : ""}<b>${value.toLocaleString("en-US")}</b>`;
      }
      const px = ctm.a * c.cx + ctm.e - frame.left, py = ctm.d * c.cy + ctm.f - frame.top;
      const below = py < 70; // near the top the tag hangs under the point
      c.tip.style.transform = `translate3d(${(px - c.tip.offsetWidth / 2).toFixed(1)}px, ${(below ? py + 16 : py - c.tip.offsetHeight - 16).toFixed(1)}px, 0)`;
      c.raf = c.cx === tx && c.cy === ty ? 0 : requestAnimationFrame(() => follow(box, c));
    }
    function wire(box) {
      box.addEventListener("pointermove", event => {
        const c = box.c31;
        if (!c || box.dataset.c31State === "wait") return;
        const ctm = c.svg?.getScreenCTM();
        if (!ctm) return;
        if (c.kind === "line") {
          const x = (event.clientX - ctm.e) / ctm.a;
          let best = Infinity;
          c.pts.forEach((p, i) => { const d = Math.abs(p[0] - x); if (d < best) { best = d; c.target = i; } });
          box.classList.add("is-hover");
          if (!c.raf) follow(box, c);
        }
        if (c.kind === "bars") {
          const y = (event.clientY - ctm.f) / ctm.d;
          const hot = c.rows.findIndex(r => Math.abs(r.cy - y) <= c.pitch / 2);
          if (hot !== c.hot) { c.hot = hot; c.rows.forEach((r, i) => [r.fill, r.label, r.value].forEach(e => e?.classList.toggle("c31-hot", i === hot))); }
        }
      });
      box.addEventListener("pointerleave", () => {
        const c = box.c31;
        box.classList.remove("is-hover");
        if (c?.kind === "bars" && c.hot !== -1) { c.hot = -1; c.rows.forEach(r => [r.fill, r.label, r.value].forEach(e => e?.classList.remove("c31-hot"))); }
      });
    }

    const io = new IntersectionObserver(entries => entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      if (entry.target === kpis) soon(playKpis); else soon(() => play(entry.target));
    }), { threshold: .2 });
    function dress(box) {
      const svg = box.querySelector(":scope > svg"), heat = box.querySelector(":scope > .heatmap");
      let done = false;
      if (svg && !svg.dataset.c31) { svg.dataset.c31 = "1"; done = svg.querySelector(".chart-line") ? dressLine(box, svg) : svg.querySelector(".bar-fill") ? dressBars(box, svg) : false; }
      else if (heat && !heat.dataset.c31) { heat.dataset.c31 = "1"; done = dressHeat(box, heat); }
      if (!done) return;
      hide(box);
      if (inView(box)) soon(() => play(box));
    }
    page.querySelectorAll(".chart-box").forEach(box => {
      wire(box);
      new MutationObserver(() => dress(box)).observe(box, { childList: true }); // app.js draws (and redraws) the chart
      io.observe(box);
      dress(box);
    });

    // the KPI figures count up (90 ms apart), and their red rules draw in
    const kpis = $("analyticsKpis");
    let kpiList = [];
    function playKpis() {
      if (kpis.dataset.c31State !== "wait") return;
      kpis.dataset.c31State = "in";
      kpis.classList.add("c31-in");
      const t0 = performance.now();
      const step = now => {
        let more = false;
        kpiList.forEach((k, i) => {
          const p = expo(clamp01((now - t0 - i * 90) / 1600));
          k.b.textContent = p >= 1 ? k.text : figure(k.n * p, k.text);
          if (p < 1) more = true;
        });
        if (more) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }
    const dressKpis = () => {
      const figures = [...kpis.querySelectorAll(".analytics-kpi b")];
      if (!figures.length || figures[0].dataset.c31) return;
      figures.forEach(b => { b.dataset.c31 = "1"; });
      kpiList = figures.map(b => ({ b, text: b.textContent, n: Number(b.textContent.replace(/[^\d.]/g, "")) })).filter(k => Number.isFinite(k.n) && k.n > 0);
      if (reducedMotion.matches) { kpis.classList.add("c31-in"); return; }
      kpis.classList.remove("c31-in");
      kpiList.forEach(k => { k.b.textContent = figure(0, k.text); });
      kpis.dataset.c31State = "wait";
      if (inView(kpis)) soon(playKpis);
    };
    if (kpis) {
      new MutationObserver(dressKpis).observe(kpis, { childList: true });
      io.observe(kpis);
      dressKpis();
    }
  }

  /* ---------- 团队信息 (2026-10-29): three cards, the lead in the middle and a little higher ----------
     The members and their details live here (data/team.json lists two of them). app.js fills #teamList each time the dialog opens; this redraws it at once: 宋伟泽 in the middle (dark
     card, raised), 张蔚然 on the left and 袁誉杭 on the right, level with each other. The lead comes first in reading
     order; the grid places the cards. On phones they stack. */
  const TEAM = [
    { name: "宋伟泽", en: "Weize Song", place: "center", email: "songwz@tsinghua.edu.cn",
      role: "清华大学低碳能源实验室，数据平台研究主任，助理教授（研究系列）",
      roleEn: "Director of Data Platform Research and Assistant Professor (Research), Low-Carbon Energy Laboratory, Tsinghua University",
      research: "低碳转型情景推演理论与方法；环境系统与智能决策；零碳园区治理与政策创新；城市空间环境绩效量化评估。",
      researchEn: "Low-carbon transition scenarios and methods; environmental systems and intelligent decision-making; zero-carbon industrial park governance and policy innovation; urban environmental performance assessment." },
    { name: "张蔚然", en: "Weiran Zhang", place: "left", email: "zhangwr25@mails.tsinghua.edu.cn",
      role: "清华大学经济管理学院在读硕士",
      roleEn: "Master's student, School of Economics and Management, Tsinghua University",
      research: "数字经济与大数据分析领域",
      researchEn: "Digital economy and big data analytics." },
    { name: "袁誉杭", en: "Yuhang Yuan", place: "right", email: "yuan-yh21@mails.tsinghua.edu.cn",
      role: "清华大学化学工程系在读博士",
      roleEn: "PhD student, Department of Chemical Engineering, Tsinghua University",
      research: "锂电池电解液与人工智能交叉领域。",
      researchEn: "Lithium-ion battery electrolytes and artificial intelligence." },
  ];
  function setupTeamCards() {
    const list = $("teamList");
    if (!list) return;
    const draw = () => {
      if (list.querySelector(":scope > .team-trio")) return; // already ours
      const en = root.lang.startsWith("en");
      const trio = make("div", "team-trio");
      TEAM.forEach(member => {
        const areas = (en ? member.researchEn : member.research).split(/[；;]\s*/).map(text => text.replace(/[。.]$/, "").trim()).filter(Boolean);
        const card = make("article", `team-card team-card--${member.place}`);
        card.innerHTML = `
          <span class="team-mark" aria-hidden="true">${esc(member.name.slice(0, 1))}</span>
          <h3>${esc(en ? member.en : member.name)}<small>${esc(en ? member.name : member.en)}</small></h3>
          <p class="team-role">${esc(en ? member.roleEn : member.role)}</p>
          <ul class="team-research">${areas.map(area => `<li>${esc(area)}</li>`).join("")}</ul>
          <a class="team-mail" href="mailto:${esc(member.email)}">${esc(member.email)}</a>`;
        trio.append(card);
      });
      list.replaceChildren(trio);
    };
    new MutationObserver(draw).observe(list, { childList: true }); // made before the dialog flight's observer: it measures our cards
    draw();
  }

  // The preview package carries no report files: preview-mode.js answers 下载今日简报 (and the report links) by writing
  // its notice into the subscribe dialog's status line, which is not on screen unless that dialog is open — so the
  // click seemed to do nothing. Shown as a toast then (2026-10-29). Without preview-mode (production) nothing changes.
  function setupPreviewNotice() {
    const hint = $("subscribeHint"), dialog = $("subscribeModal");
    if (!hint) return;
    let toast = null, timer = 0;
    new MutationObserver(() => {
      if (hint.dataset.status !== "preview" || dialog?.open || !hint.textContent.trim()) return;
      if (!toast) { toast = make("div", "preview-toast"); toast.setAttribute("role", "status"); }
      if (!toast.isConnected) document.body.append(toast);
      toast.textContent = hint.textContent.trim();
      toast.classList.remove("is-on");
      void toast.offsetWidth; // restart the entrance for a second click
      toast.classList.add("is-on");
      clearTimeout(timer);
      timer = setTimeout(() => toast.classList.remove("is-on"), 3600);
    }).observe(hint, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ["data-status"] });
  }

  // 全球气候现场's note keeps only the date on its last line (2026-10-29); app.js writes "source · date" there
  function setupMapNote() {
    const note = $("mapDetail");
    if (!note) return;
    const trim = () => {
      const small = note.querySelector("small"), text = small?.textContent || "", cut = text.lastIndexOf(" · ");
      if (cut >= 0) small.textContent = text.slice(cut + 3);
    };
    new MutationObserver(trim).observe(note, { childList: true }); // app.js replaces the note's children on every pick
    trim();
  }

  /* ---------- 文本数据库: a row opens its record (2026-10-29) ----------
     app.js draws the rows from its own state, the filtered list in order; a click on a row (not on its source link,
     which opens the source in a new tab) opens a letter-paper dialog with the record in full, flying from the row like
     the other dialogs: date · source, title, original title, summary, topics / places / figures / organisations / tags,
     and the source link (a new tab); no 关注含义 (2026-10-29). Rows take the keyboard too (Enter / Space). Reading only. */
  function setupArchiveDetail() {
    const list = $("archiveList"), dialog = $("archiveModal");
    if (!list || !dialog) return;
    const part = selector => dialog.querySelector(selector);
    const rows = () => [...list.querySelectorAll(".archive-row")];
    const arm = () => rows().forEach(row => {
      if (row.hasAttribute("tabindex")) return;
      row.tabIndex = 0;
      row.setAttribute("aria-haspopup", "dialog");
    });
    new MutationObserver(arm).observe(list, { childList: true });
    arm();
    const recordOf = row => { try { return state.filtered[rows().indexOf(row)] || null; } catch { return null; } }; // app.js's state
    const open = row => {
      const record = recordOf(row);
      if (!record) return;
      const en = root.lang.startsWith("en"), link = row.querySelector(".archive-atoms a");
      const places = (record.places || []).map(place => place.name_zh).filter(Boolean);
      part(".archive-modal-meta").textContent = [row.querySelector(".archive-date b")?.textContent.trim(), record.source_name].filter(Boolean).join(" · ");
      part("h2").textContent = en ? (record.title_en || record.title_original || "") : (record.title_zh || record.title_original || "");
      const original = !en && record.title_original && record.title_original !== record.title_zh ? record.title_original : "";
      part(".archive-modal-original").textContent = original;
      part(".archive-modal-original").hidden = !original;
      const summary = en ? (record.summary_en || record.summary_source || "") : (record.summary_zh || "");
      part(".archive-modal-summary").textContent = summary;
      part(".archive-modal-summary").hidden = !summary;
      const facts = [...(record.topics || []), ...(en ? (record.country_codes || []).map(c => c.alpha3) : places), ...(record.numbers || []),
        ...(record.organization_tags || []).map(tag => typeof tag === "string" ? tag : tag.code), ...(record.event_tags || [])].filter(Boolean);
      part(".archive-modal-facts").replaceChildren(...[...new Set(facts)].slice(0, 14).map(fact => { const li = document.createElement("li"); li.textContent = fact; return li; }));
      part(".archive-modal-facts").hidden = !facts.length;
      const out = part(".archive-modal-link");
      out.hidden = !link;
      if (link) { out.href = link.href; out.textContent = link.textContent; }
      dialog.showModal();
    };
    list.addEventListener("click", event => {
      const row = event.target.closest(".archive-row");
      if (!row || event.target.closest("a") || getSelection()?.toString()) return; // the link opens the source; selecting is not opening
      open(row);
    });
    list.addEventListener("keydown", event => {
      if ((event.key === "Enter" || event.key === " ") && event.target.matches?.(".archive-row")) { event.preventDefault(); event.target.click(); } // a click, so the dialog flies from the row
    });
  }

  /* ---------- Dialogs fly from the button that opened them (detail flight, SETTLE in / THROW out) ---------- */
  function setupDialogs() {
    let trigger = null;
    const TRIGGERS = "#subscribeOpen, [data-open-subscribe], #teamOpen, [data-open-team], #projectIntroOpen, [data-open-project], #archiveList .archive-row";
    document.addEventListener("click", event => { const button = event.target.closest?.(TRIGGERS); if (button) trigger = button; }, true);
    const sourceRect = () => {
      const rect = trigger?.getBoundingClientRect();
      if (rect && rect.width && rect.bottom > 0 && rect.top < innerHeight) return rect;
      return { left: innerWidth / 2 - 30, top: innerHeight - 70, width: 60, height: 40 }; // dock / off-screen fallback
    };
    const geometry = card => {
      const to = card.getBoundingClientRect(), from = sourceRect();
      const scale = M.clamp(Math.max(from.width / to.width, from.height / to.height), .06, 1);
      return { // start offset (card's top-left, transform-origin 0 0) so the scaled card is centred on the button
        x0: from.left + from.width / 2 - to.width * scale / 2 - to.left,
        y0: from.top + from.height / 2 - to.height * scale / 2 - to.top,
        scale,
      };
    };
    const paint = (card, g, p) => {
      card.style.transform = p >= 1 ? "" : `translate(${(g.x0 * (1 - p)).toFixed(2)}px, ${(g.y0 * (1 - p)).toFixed(2)}px) scale(${M.lerp(g.scale, 1, p).toFixed(4)})`;
    };
    document.querySelectorAll("dialog.modal").forEach(dialog => {
      const card = dialog.querySelector(".modal-card");
      let closing = false;
      new MutationObserver(() => {
        if (!dialog.open || reducedMotion.matches || closing) return;
        const g = geometry(card);
        card.style.opacity = "0";
        paint(card, g, 0);
        card.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 160, easing: "linear", fill: "forwards" }).finished.then(() => { card.style.opacity = ""; });
        M.progress(M.SPRING.settle, p => paint(card, g, p));
      }).observe(dialog, { attributes: true, attributeFilter: ["open"] });
      const close = async () => {
        if (closing || !dialog.open) return;
        if (reducedMotion.matches) { dialog.close(); return; }
        closing = true;
        dialog.classList.add("is-closing");
        const g = geometry(card);
        card.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 300, delay: 120, easing: "linear", fill: "forwards" });
        await M.progress(M.SPRING.throw, p => paint(card, g, 1 - p)).finished;
        dialog.close();
        dialog.classList.remove("is-closing");
        card.getAnimations().forEach(animation => animation.cancel());
        card.style.transform = "";
        closing = false;
        trigger?.focus?.({ preventScroll: true });
      };
      dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
      document.addEventListener("click", event => {
        if (!dialog.open) return;
        if (event.target.closest?.(".modal-close") && dialog.contains(event.target) || event.target === dialog) {
          event.preventDefault();
          event.stopImmediatePropagation();
          close();
        }
      }, true);
    });
  }

  /* ---------- Chart lightbox (the reference spring/entrance study) ---------- */
  function setupLightbox() {
    const boxes = () => document.querySelectorAll(".chart-box");
    const arm = box => {
      if (box.dataset.zoom !== undefined) return;
      box.dataset.zoom = "";
      box.tabIndex = 0;
      box.setAttribute("role", "button");
      box.setAttribute("aria-label", box.closest(".chart-card")?.querySelector("h3")?.textContent || "chart");
    };
    boxes().forEach(arm);
    let open = null;
    const openBox = async box => {
      if (open || !box.querySelector("svg, .heatmap")) return;
      const source = box.getBoundingClientRect();
      const overlay = make("div", "lightbox");
      overlay.setAttribute("aria-hidden", "true");
      const scrim = make("div", "lightbox-scrim");
      const figure = make("div", "lightbox-figure");
      const content = tidy(box.cloneNode(true));
      content.removeAttribute("data-zoom"); content.removeAttribute("role"); content.removeAttribute("tabindex");
      content.style.cssText = "min-height:0;overflow:visible;transform:none;opacity:1;translate:0 0;cursor:auto";
      figure.append(content);
      Object.assign(figure.style, { width: `${source.width}px` });
      overlay.append(scrim, figure);
      document.body.append(overlay);
      const height = figure.offsetHeight;
      const scale = Math.min(innerWidth * .9 / source.width, innerHeight * .9 / height, 2.5);
      const x1 = (innerWidth - source.width * scale) / 2, y1 = (innerHeight - height * scale) / 2;
      const paint = p => { figure.style.transform = `translate(${M.lerp(source.left, x1, p).toFixed(2)}px, ${M.lerp(source.top, y1, p).toFixed(2)}px) scale(${M.lerp(1, scale, p).toFixed(4)})`; };
      paint(0);
      box.style.visibility = "hidden";
      root.style.overflow = "hidden";
      scrim.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 400, easing: "cubic-bezier(.2, .6, .2, 1)", fill: "forwards" });
      open = { box, overlay, scrim, paint, motion: M.progress(M.SPRING.settle, paint) };
      overlay.addEventListener("click", closeBox);
    };
    const closeBox = async () => {
      if (!open) return;
      const current = open;
      open = null;
      current.motion.stop();
      current.scrim.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 360, easing: "cubic-bezier(.2, .6, .2, 1)", fill: "forwards" });
      await M.progress(M.SPRING.throw, p => current.paint(1 - p)).finished;
      current.overlay.remove();
      current.box.style.visibility = "";
      root.style.overflow = "";
      current.box.focus({ preventScroll: true });
    };
    document.addEventListener("click", event => { const box = event.target.closest?.(".chart-box[data-zoom]"); if (box && !reducedMotion.matches) openBox(box); });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && open) { event.preventDefault(); closeBox(); }
      const box = event.target.closest?.(".chart-box[data-zoom]");
      if (box && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); openBox(box); }
    });
  }

  /* ---------- Mouse drag-to-scroll for horizontal lists (FlowCarousel: 10px slop, rubber edges) ---------- */
  function dragScroll(element) {
    let start = null, moved = false, motion = null;
    const velocity = M.sampler();
    element.addEventListener("pointerdown", event => {
      if (event.pointerType !== "mouse" || event.button !== 0 || element.scrollWidth <= element.clientWidth + 1) return;
      motion?.stop();
      start = { x: event.clientX, scroll: element.scrollLeft, last: event.clientX, t: performance.now() };
      moved = false;
    });
    addEventListener("pointermove", event => {
      if (!start) return;
      const dx = event.clientX - start.x;
      if (!moved && Math.abs(dx) < 10) return;
      moved = true;
      const now = performance.now();
      velocity.push(event.clientX - start.last, 0, now - start.t, now);
      start.last = event.clientX; start.t = now;
      const max = element.scrollWidth - element.clientWidth, raw = start.scroll - dx;
      element.scrollLeft = M.clamp(raw, 0, max);
      const over = raw - M.clamp(raw, 0, max);
      element.style.translate = over ? `${(-Math.sign(over) * Math.abs(over) / (Math.abs(over) + 75) * 100).toFixed(2)}px 0` : "";
    });
    addEventListener("pointerup", () => {
      if (!start) return;
      start = null;
      if (!moved) return;
      // Swallow the click that ends a drag (300 ms window), so a tab under the pointer is not activated.
      const swallow = event => { event.preventDefault(); event.stopImmediatePropagation(); };
      element.addEventListener("click", swallow, { capture: true, once: true });
      setTimeout(() => element.removeEventListener("click", swallow, true), 300);
      const shift = parseFloat(element.style.translate) || 0;
      if (shift) M.spring(shift, 0, { k: 685, c: 52, m: 1 }, { onUpdate: value => { element.style.translate = Math.abs(value) < .2 ? "" : `${value.toFixed(2)}px 0`; } });
      const max = element.scrollWidth - element.clientWidth;
      const projected = M.clamp(element.scrollLeft - velocity.velocity().vx / 1000 * .998 / (1 - .998), 0, max);
      motion = M.spring(element.scrollLeft, projected, { k: 180, c: 2 * Math.sqrt(180), m: 1 }, { onUpdate: value => { element.scrollLeft = value; } });
    });
  }

  /* ---------- Sheet over the stage = the reference works drawer (the reference home page) ----------
     Desktop only. Everything below the stamp stage sits on one glassine sheet and the stage is sticky, so the document
     scroll from 0 to T (sheet top − 53 px gap) is the drawer travel, written here in drawer space y = T − scroll
     (0 = open). Inside the travel the wheel drives the sheet like the reference: each delta (±100) moves a target and
     the sheet follows with lerp .34 per frame, trackpads 1:1; idle 100 ms (trackpad 90) → flick > 500 px/s by
     direction, else open past 50 %, else back. Springs 240/26 open, 240/28 close (trackpad release damping × .85).
     Past T the page scrolls natively; wheel up at T drags the sheet down again. Esc / the gap band close it. */
  let stageCovered = false, wakeStage = () => {}, sheetOn = () => false, sheetClose = () => false;
  function setupSheet() {
    const sheet = document.querySelector(".drawer-sheet"), paper = sheet?.querySelector(".drawer-paper");
    const stage = document.querySelector(".cop31-intro"), band = document.querySelector(".drawer-band"), rail = document.querySelector(".rail");
    if (!sheet || !paper || !stage) return;
    const GAP = 53, GUTTER = 24, FADE = 60, LINE = 40, MAX_DELTA = 100, LERP = .34, FLICK = 500;
    const OPEN = { k: 240, c: 26 }, CLOSE = { k: 240, c: 28 }, GLIDE = { k: 240, c: 2 * Math.sqrt(240) * .85 };
    const desktop = matchMedia("(min-width: 1101px)");
    const content = [...sheet.children].filter(child => child !== paper);
    let inked = []; // the children that can show while the sheet travels (fading the whole page would repaint it all)
    const pickInked = () => { inked = content.filter(child => child.offsetTop < innerHeight - GAP); }; // app.js fills them late
    let on = false, T = 1, top = 0; // T: travel; top: document y of the sheet
    let j = 0, lerpRaf = 0, motion = null, idle = 0, owned = false;
    let source = null, lastWheel = -1e9, anyWheel = -1e9, velocity = 0; // velocity: px/s in drawer space (− = opening)
    let shown = { o: -1, deep: -1, state: "" }, lastScroll = 0, nativeFrom = null, nativeIdle = 0;

    const y = () => T - M.clamp(scrollY, 0, T);
    function render() {
      const s = scrollY, o = M.clamp(s / T, 0, 1), deep = M.clamp((s - T - GAP) / FADE, 0, 1);
      const state = s <= .5 ? "closed" : s < T - .5 ? "moving" : deep >= 1 ? "deep" : "open";
      if (o !== shown.o) {
        if (shown.state === "closed" && state !== "closed") pickInked();
        shown.o = o;
        stage.style.setProperty("--open", o.toFixed(4));
        rail?.style.setProperty("--open", o.toFixed(4));
        // Content is fully there by half-open; no item stagger. Closed = below the fold, left untouched.
        const ink = state === "closed" ? 1 : M.clamp((o - .06) / .44, 0, 1);
        inked.forEach(child => { child.style.opacity = ink < 1 ? ink.toFixed(3) : ""; });
      }
      if (band) band.style.height = `${Math.max(0, top - s).toFixed(1)}px`;
      if (deep !== shown.deep) { // once the gap has scrolled away the stage and the glassine fill fade out together
        shown.deep = deep;
        paper.style.setProperty("--paper", (1 - deep).toFixed(3));
        stage.style.opacity = deep > 0 ? (1 - deep).toFixed(3) : "";
        if ((deep >= 1) !== stageCovered) { stageCovered = deep >= 1; if (!stageCovered) wakeStage(); }
      }
      if (state !== shown.state) { shown.state = state; root.dataset.sheet = state; }
    }
    function setY(value) {
      const target = T - M.clamp(value, 0, T); // overshoot of the springs never shows
      if (Math.abs(scrollY - target) >= .5) scrollTo({ top: target, behavior: "instant" });
      render();
    }
    // The reference drawer has no item stagger: whatever the sheet brings up is shown whole.
    function revealFirstScreen() {
      const limit = top + innerHeight - GAP;
      sheet.querySelectorAll("[data-reveal]:not([data-revealed])").forEach(element => {
        if (element.getBoundingClientRect().top + scrollY < limit) showNow(element);
      });
    }
    function stop() { cancelAnimationFrame(lerpRaf); lerpRaf = 0; motion?.stop(); motion = null; }
    function springTo(open, v = 0, preset = open ? OPEN : CLOSE) {
      stop();
      if (open) revealFirstScreen();
      motion = M.spring(y(), open ? 0 : T, preset, { velocity: v, onUpdate: setY, onDone: () => { motion = null; } });
    }
    const decide = (v, preset) => springTo(Math.abs(v) > FLICK ? v < 0 : y() < T * .5, v, preset);
    function lerpStep() {
      const next = y() + (j - y()) * LERP;
      if (Math.abs(j - next) < .5) { setY(j); lerpRaf = 0; return; }
      setY(next);
      lerpRaf = requestAnimationFrame(lerpStep);
    }
    function release() {
      owned = false;
      cancelAnimationFrame(lerpRaf);
      lerpRaf = 0;
      decide(velocity, source === "trackpad" ? GLIDE : undefined);
    }
    // Reference wheel/trackpad heuristic: fractional or small, rapid deltas are a trackpad.
    const classify = (abs, gap, mode, previous) => {
      if (mode !== 0) return "wheel";
      if (abs % 1 !== 0) return "trackpad";
      const score = (abs >= 50) - (abs < 40) - (gap > 0 && gap < 50);
      return score > 0 ? "wheel" : score < 0 ? "trackpad" : previous ?? "trackpad";
    };
    const scrollsUp = node => {
      for (let element = node; element && element !== sheet && element !== document.body; element = element.parentElement) {
        if (element.scrollTop > 0 && /auto|scroll/.test(getComputedStyle(element).overflowY)) return true;
      }
      return false;
    };
    const blocked = () => busy || !!document.querySelector("dialog[open], .lightbox");

    addEventListener("wheel", event => {
      if (!on || event.defaultPrevented || event.ctrlKey || blocked()) return;
      let dy = event.deltaY, dx = event.deltaX;
      if (event.deltaMode === 1) { dy *= LINE; dx *= LINE; } else if (event.deltaMode === 2) { dy *= innerHeight; dx *= innerWidth; }
      if (!dy || Math.abs(dx) > Math.abs(dy)) return;
      const s = scrollY, now = performance.now();
      anyWheel = now;
      let consume = owned;
      if (!consume) {
        if (s < T - .5) consume = s > .5 || dy > 0;
        else if (dy < 0 && !scrollsUp(event.target)) {
          if (s <= T + .5) consume = true;
          else if (s + dy < T) { event.preventDefault(); stop(); setY(0); return; } // native scroll stops at the sheet's top edge
        }
      }
      if (!consume) return;
      event.preventDefault();
      const gap = now - lastWheel, fresh = gap > 200;
      source = classify(Math.abs(event.deltaY), fresh ? 0 : gap, event.deltaMode, source);
      velocity = fresh ? 0 : velocity * .8 + -dy / gap * 1000 * .2;
      lastWheel = now;
      if (!owned && s <= .5) revealFirstScreen();
      owned = true;
      motion?.stop();
      motion = null;
      if (source === "trackpad") {
        cancelAnimationFrame(lerpRaf);
        lerpRaf = 0;
        j = M.clamp(y() - dy, 0, T);
        setY(j);
      } else {
        j = M.clamp((lerpRaf ? j : y()) - M.clamp(dy, -MAX_DELTA, MAX_DELTA), 0, T);
        if (!lerpRaf) lerpRaf = requestAnimationFrame(lerpStep);
      }
      clearTimeout(idle);
      idle = setTimeout(release, source === "trackpad" ? 90 : 100);
    }, { passive: false });

    // Scrollbar, keyboard or find-in-page can leave the sheet half-way: settle it the way the last movement went.
    function settleNative() {
      const from = nativeFrom;
      nativeFrom = null;
      if (!on || owned || motion || lerpRaf || blocked()) return;
      const s = scrollY;
      if (s > .5 && s < T - .5) springTo(from !== null && Math.abs(s - from) > 24 ? s > from : s >= T / 2); // a stray few-px scroll falls back
    }
    addEventListener("scroll", () => {
      if (!on) return;
      const s = scrollY;
      if (!owned && !motion && !lerpRaf && !busy) {
        // A smooth wheel scroll that started below the sheet's top edge must not run on into the travel.
        if (s < T - .5 && lastScroll >= T - .5 && performance.now() - anyWheel < 400) { scrollTo({ top: T, behavior: "instant" }); lastScroll = T; render(); return; }
        nativeFrom ??= lastScroll;
        if (!("onscrollend" in window)) { clearTimeout(nativeIdle); nativeIdle = setTimeout(settleNative, 160); }
      }
      lastScroll = s;
      render();
    }, { passive: true });
    if ("onscrollend" in window) addEventListener("scrollend", settleNative);

    addEventListener("keydown", event => {
      if (!on || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey || blocked()) return;
      const s = scrollY;
      if (event.key === "Escape") { if (s > .5 && s <= T + .5) springTo(false); return; }
      const focus = event.target;
      if (focus !== document.body && focus !== root && !focus.matches?.("section, main")) return; // keys belong to the focused control
      const down = event.key === "ArrowDown" || event.key === "PageDown" || (event.key === " " && !event.shiftKey);
      const up = event.key === "ArrowUp" || event.key === "PageUp" || (event.key === " " && event.shiftKey);
      if (down && s < T - .5) { event.preventDefault(); springTo(true); }
      else if (up && s > .5 && s <= T + .5) { event.preventDefault(); springTo(false); }
    });
    band?.addEventListener("click", () => { if (on && !blocked()) springTo(false); });

    function measure() {
      const box = sheet.getBoundingClientRect();
      top = box.top + scrollY;
      T = Math.max(1, top - GAP);
      const edge = rail && getComputedStyle(rail).display !== "none" ? rail.getBoundingClientRect().right : 0;
      const x = Math.max(0, Math.min(edge, box.left) - GUTTER); // paper margin left of the content; the rail stays clear
      root.style.setProperty("--sheet-x", `${x.toFixed(1)}px`);
      paper.style.left = `${(x - box.left).toFixed(1)}px`;
      paper.style.right = `${(box.right - root.clientWidth).toFixed(1)}px`;
      content.forEach(child => { child.style.opacity = ""; });
      pickInked();
      shown.o = -1;
    }
    function apply() {
      const want = desktop.matches && !reducedMotion.matches && currentPage() === "home";
      if (!want) {
        if (!on) return;
        on = false;
        stop();
        clearTimeout(idle);
        owned = false;
        root.classList.remove("has-sheet");
        root.style.removeProperty("--sheet-x");
        delete root.dataset.sheet;
        stage.style.removeProperty("--open");
        rail?.style.removeProperty("--open");
        stage.style.opacity = "";
        content.forEach(child => { child.style.opacity = ""; });
        stageCovered = false;
        wakeStage();
        shown = { o: -1, deep: -1, state: "" };
        return;
      }
      const wasOpen = on && scrollY >= T - .5;
      on = true;
      root.classList.add("has-sheet");
      measure();
      const s = scrollY;
      if (s > .5 && s < T - .5) scrollTo({ top: wasOpen || s >= T / 2 ? T : 0, behavior: "instant" });
      lastScroll = scrollY;
      render();
    }
    sheetOn = () => on;
    sheetClose = () => { // the brand link closes an open sheet instead of cutting to the top
      if (!on || scrollY <= .5 || scrollY > T + .5) return false;
      springTo(false);
      return true;
    };
    // The sheet first screen is unrevealed (opacity 0) until it comes up, so Chrome has never painted it: the first
    // opening then pays ~150 ms of first paint (CJK text, ink filter, map) in its opening frames (measured with
    // record.mjs --no-frames; later openings run at 6–12 ms a frame). Reveal it while it is still below the fold and
    // the visitor is looking at the stage. The reference drawer shows its content whole anyway (no item stagger).
    const mapDrawn = new Promise(done => { // app.js draws the map (the heaviest thing on the sheet first screen) after load
      const map = $("worldMap");
      if (!map || map.querySelector(".map-country")) { done(); return; }
      const watch = new MutationObserver(() => { if (map.querySelector(".map-country")) { watch.disconnect(); done(); } });
      watch.observe(map, { childList: true, subtree: true });
      setTimeout(() => { watch.disconnect(); done(); }, 6000);
    });
    const loaded = new Promise(done => { document.readyState === "complete" ? done() : addEventListener("load", done, { once: true }); });
    const prepaint = () => { if (on && scrollY < T - .5 && !blocked()) revealFirstScreen(); };
    Promise.all([loaded, mapDrawn, document.fonts?.ready]).then(() => setTimeout(() => (window.requestIdleCallback ?? (callback => setTimeout(callback, 50)))(prepaint, { timeout: 1500 }), 400));
    let resizeRaf = 0;
    addEventListener("resize", () => { cancelAnimationFrame(resizeRaf); resizeRaf = requestAnimationFrame(apply); });
    desktop.addEventListener?.("change", apply);
    reducedMotion.addEventListener?.("change", apply);
    onPageChange = apply;
    apply();
  }

  /* ---------- Page-edge rubber band, desktop wheel only (the reference writings page R4) ---------- */
  function setupRubber() {
    if (!matchMedia("(min-width: 1101px) and (hover: hover) and (pointer: fine)").matches) return;
    const sheet = document.querySelector("main"), riders = [document.querySelector("body > footer")].filter(Boolean);
    const RES = 75, CEIL = 100, TUCK = .01, IDLE = 72, LIFT_MIN = 700, CLAMP = 1600, SNAP = .2;
    const springOf = period => { const w = 2 * Math.PI / (1.2 * period); return { k: w * w, c: 2 * w }; };
    const BACK = springOf(SNAP), KICK = springOf(1.5 * SNAP);
    let raw = 0, shown = 0, vel = 0, raf = 0, idle = 0, lastInput = -1e9, samples = [];
    const view = r => -Math.sign(r) * Math.abs(r) / (Math.abs(r) + RES) * CEIL;
    const unview = d => { const n = Math.min(Math.abs(d) / CEIL, .999); return -Math.sign(d) * RES * n / (1 - n); };
    const paint = d => {
      shown = d;
      if (Math.abs(d) < .15) { sheet.style.transform = ""; riders.forEach(rider => { rider.style.transform = ""; }); return; }
      const t = `translate3d(0, ${d.toFixed(2)}px, 0)`;
      sheet.style.transformOrigin = d > 0 ? "50% 100%" : "50% 0%";
      sheet.style.transform = `${t} scale(${(1 - Math.min(Math.abs(d) / CEIL, 1) * TUCK).toFixed(4)})`;
      riders.forEach(rider => { rider.style.transform = t; });
    };
    const run = (to, v, { k, c }, done, near = 0) => {
      cancelAnimationFrame(raf);
      let x = shown, prev = performance.now();
      const span = Math.abs(to - x);
      const step = now => {
        const dt = Math.min((now - prev) / 1000, 1 / 30);
        prev = now;
        v += (-k * (x - to) - c * v) * dt; x += v * dt; vel = v; paint(x);
        if (near && Math.abs(to - x) <= near * span) { done?.(); return; }
        if (Math.abs(x - to) < .15 && Math.abs(v) < 2) { vel = 0; paint(to); done?.(); return; }
        raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
    };
    const release = () => { raw = 0; run(0, vel, BACK); };
    addEventListener("wheel", event => {
      if (event.defaultPrevented || event.ctrlKey || reducedMotion.matches || busy || root.style.overflow === "hidden" || document.querySelector("dialog[open]")) return;
      if (sheetOn() && event.deltaY < 0 && scrollY <= 0) return; // the top of the page is the stage: no stretch there
      if (event.target.closest?.(".chat-log, .heatmap-box, .modal, .lightbox, .ct-list") || root.classList.contains("focus-page")) return;
      lastInput = performance.now();
      const max = root.scrollHeight - innerHeight, y = scrollY;
      const dy = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaMode === 2 ? event.deltaY * innerHeight : event.deltaY;
      const room = dy > 0 ? Math.max(max - y, 0) : -Math.max(y, 0);
      const excess = dy > 0 ? Math.max(0, dy - room) : Math.min(0, dy - room);
      if (!excess && !shown) return;
      event.preventDefault();
      cancelAnimationFrame(raf);
      if (shown && Math.sign(dy) !== -Math.sign(shown)) {
        raw = unview(shown) + dy;
        if (Math.sign(raw) !== Math.sign(unview(shown))) { scrollBy(0, raw); raw = 0; }
      } else {
        if (dy !== excess) scrollBy(0, dy - excess);
        raw = unview(shown) + excess;
      }
      paint(view(raw));
      clearTimeout(idle);
      idle = setTimeout(release, IDLE);
    }, { passive: false });
    addEventListener("scroll", () => {
      const now = performance.now(), y = scrollY, max = root.scrollHeight - innerHeight;
      samples.push({ t: now, y });
      while (samples.length > 2 && now - samples[1].t >= 100) samples.shift();
      const first = samples[0], v = now - first.t >= 60 ? (y - first.y) / (now - first.t) * 1000 : 0;
      const edge = y <= 0 && v < 0 ? -1 : y >= max - 1 && v > 0 ? 1 : 0;
      if (!edge || (edge < 0 && sheetOn()) || Math.abs(v) < LIFT_MIN || now - lastInput > 400 || shown || busy) return;
      const speed = Math.min(Math.abs(v), CLAMP);
      run(view(edge * speed * SNAP), -edge * speed, KICK, release, .15);
      samples = [];
    }, { passive: true });
  }

  /* ---------- Menu glyph morph (reference Menu-module, the reference home page) + brand descriptor scramble ----------
     The hovered item turns bold italic; the current section's item does too unless another item is hovered, and comes
     back when the pointer leaves the list (fine pointers only; isHighlighted = hovered || current && !otherHovered).
     Each label becomes per-character glyphs (aria-hidden; the text stays in an sr-only span) that morph .2 s easeInOut
     in CSS; on every switch each glyph also squashes and tilts a little mid-way, as the reference's interpolating
     outlines do. app.js rewrites the labels on a language switch, so the glyphs are rebuilt from whatever it writes. */
  const EASE_IN_OUT = "cubic-bezier(.42, 0, .58, 1)"; // framer "easeInOut"
  function setupMenuGlyphs() {
    const nav = document.querySelector(".rail-menu nav");
    if (!nav) return;
    const links = [...nav.querySelectorAll("a")];
    let hovered = null;
    const build = link => {
      const text = link.textContent.trim(), label = make("span", "sr-only"), glyphs = make("span", "nav-glyphs");
      label.textContent = text;
      glyphs.setAttribute("aria-hidden", "true");
      [...text].forEach((char, index) => {
        const glyph = make("span");
        glyph.textContent = char;
        glyph.style.setProperty("--i", index);
        glyphs.append(glyph);
      });
      link.replaceChildren(label, glyphs);
    };
    const squash = (link, italic) => link.querySelectorAll(".nav-glyphs > span").forEach((glyph, index) => {
      const seed = index * 3.7 + (italic ? .31 : .83) + glyph.textContent.charCodeAt(0) * .013;
      glyph.animate([
        { scale: "1 1", rotate: "0deg" },
        { scale: `${(.9 + .14 * hash(seed)).toFixed(3)} ${(.86 + .16 * hash(seed + 1.7)).toFixed(3)}`, rotate: `${(8 * hash(seed + 3.1) - 4).toFixed(2)}deg`, offset: .5 },
        { scale: "1 1", rotate: "0deg" },
      ], { duration: 200, easing: EASE_IN_OUT });
    });
    const render = () => links.forEach(link => {
      const italic = link === hovered || (!hovered && link.classList.contains("is-current"));
      const state = italic ? "italic" : "roman";
      if (link.dataset.glyph === state) return;
      const first = !link.dataset.glyph;
      link.dataset.glyph = state;
      if (!first && !reducedMotion.matches) squash(link, italic);
    });
    links.forEach(link => {
      build(link);
      new MutationObserver(() => { if (!link.querySelector(".nav-glyphs")) build(link); }).observe(link, { childList: true });
      new MutationObserver(render).observe(link, { attributes: true, attributeFilter: ["class"] }); // scroll-spy moves .is-current
      link.addEventListener("pointerenter", event => {
        if (event.pointerType !== "mouse" || !finePointer.matches) return;
        hovered = link;
        render();
      });
    });
    nav.addEventListener("pointerleave", () => { hovered = null; render(); });
    render();
  }
  function setupIdentity() {
    setupMenuGlyphs();
    document.querySelector(".brand")?.addEventListener("pointerenter", scrambleDescriptor);
  }
  let descriptorBusy = false;
  function scrambleDescriptor() { // 1 s scramble back to the same text (reference tagline), no new wording
    const descriptor = $("brandDescriptor");
    if (!descriptor || descriptorBusy || reducedMotion.matches) return;
    descriptorBusy = true;
    const text = descriptor.textContent;
    // The scramble glyphs differ in width: hold the line at its resting width so the brand row (and the COP31 logo
    // beside it) does not move while it runs.
    descriptor.style.width = `${descriptor.getBoundingClientRect().width}px`;
    descriptor.style.overflow = "visible";
    M.scramble(descriptor, text, text, 1000, true).then(() => {
      descriptor.style.width = "";
      descriptor.style.overflow = "";
      setTimeout(() => { descriptorBusy = false; }, 175);
    });
  }

  // The bare page swap for countries.js, which plays its own transitions: no cut-in replay, no scramble; whatever the
  // new page shows is shown whole (its entrance is countries.js's).
  window.GreenPages = {
    current: currentPage,
    swap(id) {
      const target = $(id) || $("top");
      setPage(pageOf(target));
      scrollTo({ top: pageOf(target) === "home" ? landingTop(target) : 0, behavior: "instant" });
      target.querySelectorAll("[data-reveal]:not([data-revealed])").forEach(showNow);
    },
  };

  /* ---------- Menu drop-down and the glass band behind the logos (2026-10-29, round 16) ----------
     Off the home page (desktop) the menu column is gone: the 菜单 button opens it as a drop-down, a square column of
     dark glass that rolls down from the top edge (cop31.css). It closes on a second press, a click outside, Esc, or any navigation. The glass band behind
     the fixed logos shows once content scrolls under them: on a page as soon as it scrolls, on the home page once the
     sheet's top edge has left the window (or, without the sheet, once the stage is mostly scrolled away). */
  let chromeRefresh = () => {};
  function setupChrome() {
    const button = document.querySelector(".menu-pop"), menu = $("siteMenu"), stage = document.querySelector(".cop31-intro");
    let rolling = 0, openedAt = 0;
    // the button scrolls away with the page now, so the drop-down closes once the page moves on (2026-10-29)
    addEventListener("scroll", () => { if (root.classList.contains("menu-open") && Math.abs(scrollY - openedAt) > 40) setOpen(false); }, { passive: true });
    const setOpen = open => {
      if (open) openedAt = scrollY;
      // while the glass rolls back up (.45 s) the label stays plain white over it (cop31.css)
      if (!open && root.classList.contains("menu-open")) { root.classList.add("menu-closing"); clearTimeout(rolling); rolling = setTimeout(() => root.classList.remove("menu-closing"), 450); }
      root.classList.toggle("menu-open", open);
      button?.setAttribute("aria-expanded", String(open));
    };
    button?.addEventListener("click", event => {
      const open = !root.classList.contains("menu-open");
      setOpen(open);
      if (open && event.detail === 0) requestAnimationFrame(() => menu?.querySelector("nav a")?.focus({ preventScroll: true }));
    });
    document.addEventListener("pointerdown", event => {
      if (root.classList.contains("menu-open") && !event.target.closest?.("#siteMenu, .menu-pop")) setOpen(false);
    });
    addEventListener("keydown", event => {
      if (event.key !== "Escape" || !root.classList.contains("menu-open")) return;
      setOpen(false);
      button?.focus({ preventScroll: true });
    });
    const under = () => {
      let value;
      if (currentPage() !== "home") value = scrollY > 4;
      else if (root.classList.contains("has-sheet")) value = root.dataset.sheet === "deep";
      else value = scrollY > (stage ? stage.offsetHeight * .6 : 0);
      root.classList.toggle("is-under", value);
    };
    let queued = false;
    chromeRefresh = () => { if (!queued) { queued = true; requestAnimationFrame(() => { queued = false; under(); }); } };
    addEventListener("scroll", chromeRefresh, { passive: true });
    addEventListener("resize", chromeRefresh);
    chromeRefresh();
  }

  /* ---------- Paper contours (background texture, 2026-10-29) ----------
     Faint topographic contour lines under the page: smooth 2D value noise (two octaves, float precision — SVG turbulence
     is 8-bit and terraces) sampled on a 6 px grid and traced with marching squares at 16 levels; every fourth line is a
     little stronger, like a survey map's index contours. Drawn once per window width at idle time and handed to the
     fixed background layer as an image (so copies of the background carry it); the lines fade out under the left rail. */
  function setupContours() {
    const layer = document.querySelector(".page-bg");
    if (!layer || !("toBlob" in HTMLCanvasElement.prototype)) return;
    let url = "", drawnWidth = 0;
    const cell = (x, y) => { const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453; return s - Math.floor(s); };
    const ease = t => t * t * (3 - 2 * t);
    const noise = (x, y) => {
      const xi = Math.floor(x), yi = Math.floor(y), u = ease(x - xi), v = ease(y - yi);
      const a = cell(xi, yi), b = cell(xi + 1, yi), c = cell(xi, yi + 1), d = cell(xi + 1, yi + 1);
      return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
    };
    const height = (x, y) => .7 * noise(x, y) + .3 * noise(x * 2.03 + 17.3, y * 2.03 + 9.1);
    function draw() {
      const w = innerWidth, h = Math.max(innerHeight, 900), dpr = Math.min(2, devicePixelRatio || 1);
      const canvas = make("canvas");
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      const ctx = canvas.getContext("2d");
      ctx.scale(dpr, dpr);
      const step = 6, cols = Math.ceil(w / step) + 1, rows = Math.ceil(h / step) + 1, scale = 1 / 280;
      const field = new Float32Array(cols * rows);
      for (let j = 0; j < rows; j += 1) for (let i = 0; i < cols; i += 1) field[j * cols + i] = height(i * step * scale + 3.7, j * step * scale + 1.9);
      const LEVELS = 16, normal = new Path2D(), index = new Path2D();
      for (let k = 1; k < LEVELS; k += 1) {
        const level = k / LEVELS, path = k % 4 ? normal : index;
        for (let j = 0; j < rows - 1; j += 1) for (let i = 0; i < cols - 1; i += 1) {
          const a = field[j * cols + i], b = field[j * cols + i + 1], c = field[(j + 1) * cols + i + 1], d = field[(j + 1) * cols + i];
          const code = (a > level) | (b > level) << 1 | (c > level) << 2 | (d > level) << 3;
          if (code === 0 || code === 15) continue;
          const x = i * step, y = j * step, t = (p, q) => (level - p) / (q - p);
          const top = [x + step * t(a, b), y], right = [x + step, y + step * t(b, c)], bottom = [x + step * t(d, c), y + step], left = [x, y + step * t(a, d)];
          const segment = (p, q) => { path.moveTo(p[0], p[1]); path.lineTo(q[0], q[1]); };
          switch (code) {
            case 1: case 14: segment(left, top); break;
            case 2: case 13: segment(top, right); break;
            case 3: case 12: segment(left, right); break;
            case 4: case 11: segment(right, bottom); break;
            case 6: case 9: segment(top, bottom); break;
            case 7: case 8: segment(left, bottom); break;
            case 5: segment(left, top); segment(right, bottom); break;
            case 10: segment(top, right); segment(bottom, left); break;
          }
        }
      }
      ctx.lineCap = "round";
      ctx.strokeStyle = "rgba(63, 85, 108, .34)"; ctx.lineWidth = .8; ctx.stroke(normal);
      ctx.strokeStyle = "rgba(63, 85, 108, .62)"; ctx.lineWidth = 1.1; ctx.stroke(index);
      const rail = parseFloat(getComputedStyle(root).getPropertyValue("--rail-w")) || 0;
      if (rail) { // keep the rail's text clean
        const fade = ctx.createLinearGradient(rail * .55, 0, rail * 1.04, 0);
        fade.addColorStop(0, "#000"); fade.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.globalCompositeOperation = "destination-out";
        ctx.fillStyle = fade;
        ctx.fillRect(0, 0, rail * 1.04, h);
      }
      canvas.toBlob(blob => {
        if (!blob) return;
        const next = URL.createObjectURL(blob);
        layer.style.setProperty("--contours", `url("${next}")`);
        if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
        url = next;
        drawnWidth = w;
        requestAnimationFrame(() => layer.classList.add("has-contours"));
      });
    }
    const idle = window.requestIdleCallback ?? (callback => setTimeout(callback, 200));
    idle(draw, { timeout: 1500 });
    let timer = 0;
    addEventListener("resize", () => { // a width change redraws; height changes (phone toolbars) only rescale the image
      clearTimeout(timer);
      timer = setTimeout(() => { if (Math.abs(innerWidth - drawnWidth) > 60) idle(draw, { timeout: 1500 }); }, 400);
    });
  }

  /* ---------- Start ---------- */
  let spy = null;
  const start = () => {
    const linked = location.hash ? document.getElementById(decodeURIComponent(location.hash.slice(1))) : null;
    markPage(linked && !intelOwns(linked) ? pageOf(linked) : "home"); // #today: intel.js opens itself over the home page
    localize();
    new MutationObserver(localize).observe(root, { attributes: true, attributeFilter: ["lang"] });
    scan(document.body);
    new MutationObserver(records => records.forEach(record => record.addedNodes.forEach(node => {
      if (node.nodeType === 1) scan(node);
    }))).observe(document.querySelector("main"), { childList: true, subtree: true });
    reel = setupReel();
    spy = setupSpy();
    setupStamps();
    setupIdentity();
    setupFlip();
    setupScramble();
    setupTeamCards();
    setupPreviewNotice();
    setupArchiveDetail();
    setupMapNote();
    setupCharts();
    setupDialogs();
    setupLightbox();
    if (finePointer.matches) document.querySelectorAll(".spotlight-tabs, .map-place-list").forEach(dragScroll);
    setupSheet();
    setupRubber();
    setupContours();
    setupChrome();
    const menu = $("mobileMenu");
    menu?.addEventListener("click", event => { if (event.target === menu) $("mobileMenuToggle")?.click(); });
  };
  reducedMotion.addEventListener?.("change", () => {
    if (reducedMotion.matches) document.querySelectorAll("[data-reveal]").forEach(element => element.setAttribute("data-revealed", ""));
  });
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
