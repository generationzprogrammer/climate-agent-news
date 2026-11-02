/* GREEN · COP31 — 国家专题 (2026-10-29), after icebergdoc.org/impact-in-action.
   The list page: a globe on the left (the reference's Mapbox globe redrawn on a 2D canvas with the same near-side
   perspective), the country topics on the right; hovering a topic turns the globe to it (1 s, cubic-bezier(.25, .1,
   .25, 1), rhumb path, restarted by every hover). Chosen from another page, 国家专题 comes in behind the reference's
   six-column overlay (blinds closing from the right, then opening right to left). A topic opens its page: the list slides out, a dark hold, then the
   panel slides in, the flat map fades in, the picture wipes down, the title rises letter by letter, NEXT rises.
   Specs: the icebergdoc.org list page, the icebergdoc.org topic page.
   The topic pages are the original 中国碳市场 / 新加坡 sections (app.js renders them; IDs untouched), laid out anew.
   Routing: cop31.js owns the pages; this file asks it for bare swaps (window.GreenPages) and plays the choreography. */
(() => {
  "use strict";
  const root = document.documentElement;
  const $ = id => document.getElementById(id);
  const make = (tag, className = "", html = "") => { const e = document.createElement(tag); if (className) e.className = className; if (html) e.innerHTML = html; return e; };
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const fine = matchMedia("(hover: hover) and (pointer: fine)");
  const wide = matchMedia("(min-width: 1101px)");
  const RAD = Math.PI / 180, TAU = Math.PI * 2;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v)), clamp01 = v => clamp(v, 0, 1), lerp = (a, b, t) => a + (b - a) * t;
  const en = () => (root.lang || "").startsWith("en");
  const list = $("countries");
  if (!list) return;
  const listCol = list.querySelector(".ct-list"), panel = list.querySelector(".ct-panel");
  const rows = [...list.querySelectorAll(".ct-row")];
  const topics = rows.map((row, index) => ({
    id: row.dataset.focus, lat: Number(row.dataset.lat), lon: Number(row.dataset.lon), row, index,
    image: row.querySelector("img")?.getAttribute("src") || "", section: $(row.dataset.focus),
  })).filter(t => t.section);
  const OWN = new Set(["countries", ...topics.map(t => t.id)]);
  let current = null; // the topic page on screen
  const topicOf = id => topics.find(t => t.id === id);

  /* ---------- Eases (GSAP power2 = cubic, power4 = quint; Mapbox easeTo = cubic-bezier(.25, .1, .25, 1)) ---------- */
  const bezier = (x1, y1, x2, y2) => x => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let lo = 0, hi = 1, t = x;
    for (let i = 0; i < 26; i += 1) {
      t = (lo + hi) / 2;
      const bx = 3 * x1 * t * (1 - t) ** 2 + 3 * x2 * t * t * (1 - t) + t ** 3;
      if (bx < x) lo = t; else hi = t;
    }
    return 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t * t * (1 - t) + t ** 3;
  };
  const MAPBOX = bezier(.25, .1, .25, 1);
  const E = {
    cubicInOut: p => p < .5 ? 4 * p * p * p : 1 - (-2 * p + 2) ** 3 / 2,
    cubicOut: p => 1 - (1 - p) ** 3,
    quintOut: p => 1 - (1 - p) ** 5,
  };
  // Timeline of absolutely placed tweens [{ at, dur, ease, set(v) }] on the wall clock (GSAP lagSmoothing(0)).
  function play(tweens, alive = () => true) { // alive(): false stops the timeline where it is (a newer move took over)
    return new Promise(done => {
      tweens.forEach(t => t.set(0));
      if (reduced.matches) { tweens.forEach(t => t.set(1)); done(); return; }
      const t0 = performance.now(), end = Math.max(...tweens.map(t => t.at + t.dur));
      const tick = now => {
        if (!alive()) { done(); return; }
        const s = (now - t0) / 1000;
        for (const t of tweens) t.set(t.ease(clamp01((s - t.at) / t.dur)));
        if (s < end) requestAnimationFrame(tick); else done();
      };
      requestAnimationFrame(tick);
    });
  }
  const wait = ms => new Promise(r => setTimeout(r, reduced.matches ? 0 : ms));
  const HOLD = 600; // the reference's dark hold between the list and a topic page

  /* ---------- World data (assets/countries-110m.json) ---------- */
  let world = null;
  const worldReady = fetch("./assets/countries-110m.json").then(r => r.json()).then(topo => {
    const [sx, sy] = topo.transform?.scale || [1, 1], [tx, ty] = topo.transform?.translate || [0, 0];
    const arcs = topo.arcs.map(arc => { let x = 0, y = 0; return arc.map(([dx, dy]) => { x += dx; y += dy; return [x * sx + tx, y * sy + ty]; }); });
    const ring = refs => refs.flatMap((ref, i) => { const p = ref < 0 ? arcs[~ref].slice().reverse() : arcs[ref]; return i ? p.slice(1) : p; });
    const uses = new Map(), rings = [];
    const count = refs => refs.forEach(ref => { const i = ref < 0 ? ~ref : ref; uses.set(i, (uses.get(i) || 0) + 1); });
    for (const g of topo.objects.countries.geometries) {
      if (g.type === "Polygon") { g.arcs.forEach(count); g.arcs.forEach(r => rings.push(ring(r))); }
      else if (g.type === "MultiPolygon") g.arcs.forEach(poly => { poly.forEach(count); poly.forEach(r => rings.push(ring(r))); });
    }
    // an arc shared by two countries is a border; an arc used once is a coastline (not stroked, like the reference)
    const borders = [...uses].filter(([, n]) => n > 1).map(([i]) => arcs[i]);
    world = { rings, borders };
    return world;
  }).catch(() => null);

  /* ---------- The scribble X (our own hand-drawn marker: seeded multi-stroke arms) ---------- */
  function scribble(w, h, color, width, seed) {
    const c = make("canvas"), s = 2;
    c.width = w * s; c.height = h * s;
    const g = c.getContext("2d");
    g.scale(s, s);
    let r = seed * 7919 + 13;
    const rnd = () => (r = (r * 16807) % 2147483647) / 2147483647;
    g.strokeStyle = color; g.lineCap = "round"; g.lineJoin = "round";
    for (const arm of [0, 1]) {
      const n = 5 + Math.floor(rnd() * 4);
      for (let i = 0; i < n; i += 1) {
        const jx = (rnd() - .5) * w * .16, jy = (rnd() - .5) * h * .16;
        const x0 = (arm ? .84 : .16) * w + jx, x1 = (arm ? .16 : .84) * w + jx;
        g.globalAlpha = .45 + rnd() * .55;
        g.lineWidth = width * (.7 + rnd() * .6);
        g.beginPath();
        g.moveTo(x0 + (rnd() - .5) * 5, .14 * h + jy + (rnd() - .5) * 5);
        g.quadraticCurveTo(w / 2 + (rnd() - .5) * w * .3, h / 2 + (rnd() - .5) * h * .3, x1 + (rnd() - .5) * 5, .86 * h + jy + (rnd() - .5) * 5);
        g.stroke();
      }
    }
    return c;
  }
  const RED = "#d8463a";
  const sprites = topics.map(t => ({ normal: scribble(46, 40, "#ffffff", 1, t.index + 3), active: scribble(62, 54, RED, 1.7, t.index + 11) }));

  /* ---------- The globe (iceberg-list §2, §9): near-side perspective, zoom 2 (1.5 on phones) ---------- */
  const globe = (() => {
    const canvas = list.querySelector(".ct-globe"), ctx = canvas.getContext("2d");
    const view = { lon: 30.7, lat: 36.9 }; // Antalya, the COP31 host city (the reference starts on Barcelona)
    let W = 1, H = 1, dpr = 1, S = 461, P = 4.38, Rs = 365, f = 1500, cx = 0, cy = 0, pad = 0;
    let rot = null, tween = null, padTween = null, inertia = null, raf = 0, active = null, ready = false, live = false, bg = null;
    const setRot = () => { const l = view.lon * RAD, p = view.lat * RAD; rot = { cl: Math.cos(l), sl: Math.sin(l), cp: Math.cos(p), sp: Math.sin(p) }; };
    const vec = (lon, lat) => { const l = lon * RAD, p = lat * RAD, c = Math.cos(p); return [c * Math.sin(l), Math.sin(p), c * Math.cos(l)]; };
    const turn = (x, y, z) => { const x1 = x * rot.cl - z * rot.sl, z1 = z * rot.cl + x * rot.sl; return [x1, y * rot.cp - z1 * rot.sp, y * rot.sp + z1 * rot.cp]; };
    // stars: 16 000 seeded points on a sphere locked to the earth; the far side shows behind the globe (§2.3)
    const stars = new Float32Array(16000 * 5);
    { let r = 30; const rnd = () => (r = (r * 16807) % 2147483647) / 2147483647;
      for (let i = 0; i < 16000; i += 1) {
        const z = rnd() * 2 - 1, a = rnd() * TAU, s = Math.sqrt(1 - z * z);
        stars.set([s * Math.cos(a), z, s * Math.sin(a), .5 + rnd(), 2 * rnd()], i * 5);
      } }
    const starSprite = (() => { const c = make("canvas"); c.width = c.height = 16; const g = c.getContext("2d"); const gr = g.createRadialGradient(8, 8, 0, 8, 8, 8); gr.addColorStop(0, "rgba(255,255,255,1)"); gr.addColorStop(.45, "rgba(235,242,250,.55)"); gr.addColorStop(1, "rgba(220,230,240,0)"); g.fillStyle = gr; g.fillRect(0, 0, 16, 16); return c; })();
    function size() {
      const box = canvas.getBoundingClientRect();
      W = Math.max(1, box.width); H = Math.max(1, box.height);
      dpr = Math.min(2, devicePixelRatio || 1);
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      const zoom = wide.matches ? 2 : 1.5, Rw = 512 * 2 ** zoom / TAU, vh = wide.matches ? H : innerHeight;
      S = Math.SQRT2 * Rw; P = 1 + 1.06066 * vh / Rw; Rs = S * Math.sqrt((P - 1) / (P + 1)); f = 1.5 * vh;
      if (!wide.matches) { const fit = Math.min(Rs, Math.min(W, H) * .62); S *= fit / Rs; Rs = fit; }
      bg = null;
      if (live && wide.matches) pad = listOpen ? W / 2 : 0;
      wake();
    }
    // the panel ground: the grey-blue of our globe panel (the 全球气候现场 panel's gradients)
    function ground() {
      if (bg) return bg;
      const c = make("canvas"); c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
      const g = c.getContext("2d"); g.scale(dpr, dpr);
      const lin = g.createLinearGradient(0, 0, W * .34, H); lin.addColorStop(0, "#243243"); lin.addColorStop(.78, "#111a24"); lin.addColorStop(1, "#111a24");
      g.fillStyle = lin; g.fillRect(0, 0, W, H);
      const a = g.createRadialGradient(W * .3, H * .52, 0, W * .3, H * .52, Math.max(W, H) * .55); a.addColorStop(0, "rgba(92,128,168,.30)"); a.addColorStop(1, "rgba(92,128,168,0)");
      g.fillStyle = a; g.fillRect(0, 0, W, H);
      const b = g.createRadialGradient(W, 0, 0, W, 0, Math.max(W, H) * .5); b.addColorStop(0, "rgba(200,55,45,.14)"); b.addColorStop(1, "rgba(200,55,45,0)");
      g.fillStyle = b; g.fillRect(0, 0, W, H);
      return (bg = c);
    }
    function draw() {
      setRot();
      cx = (W - pad) / 2; cy = H / 2;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.drawImage(ground(), 0, 0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (Rs < 8) return; // not laid out yet
      // stars (far side), drawn before the globe covers them
      for (let i = 0; i < 16000; i += 1) {
        const o = i * 5, q = turn(stars[o], stars[o + 1], stars[o + 2]);
        if (q[2] > -.5) continue;
        const X = cx + f * q[0] / -q[2], Y = cy - f * q[1] / -q[2];
        if (X < -4 || Y < -4 || X > W + 4 || Y > H + 4) continue;
        const r = .00075 * f * stars[o + 3] * 1.6;
        ctx.globalAlpha = Math.min(1, .4 * stars[o + 4]);
        ctx.drawImage(starSprite, X - r, Y - r, 2 * r, 2 * r);
      }
      ctx.globalAlpha = 1;
      // ocean, then land with the hidden part of each ring run along the limb (§9.3)
      ctx.beginPath(); ctx.arc(cx, cy, Rs, 0, TAU); ctx.fillStyle = "#070c12"; ctx.fill();
      ctx.save(); ctx.clip();
      if (world) {
        const proj = q => { const k = (P - 1) / (P - q[2]); return [cx + S * k * q[0], cy - S * k * q[1]]; };
        const limb = q => { const n = Math.hypot(q[0], q[1]) || 1; return [cx + Rs * q[0] / n, cy - Rs * q[1] / n]; };
        ctx.beginPath();
        for (const ring of world.rings) {
          let any = false;
          const pts = ring.map(([lon, lat]) => { const v = vec(lon, lat), q = turn(v[0], v[1], v[2]); const vis = q[2] > 1 / P; if (vis) any = true; return vis ? proj(q) : limb(q); });
          if (!any) continue;
          pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
          ctx.closePath();
        }
        ctx.fillStyle = "#1c2735"; ctx.fill("evenodd");
        ctx.beginPath();
        for (const line of world.borders) {
          let down = false;
          for (const [lon, lat] of line) {
            const v = vec(lon, lat), q = turn(v[0], v[1], v[2]);
            if (q[2] <= 1 / P) { down = false; continue; }
            const [x, y] = proj(q);
            if (down) ctx.lineTo(x, y); else { ctx.moveTo(x, y); down = true; }
          }
        }
        ctx.strokeStyle = "#6b7e92"; ctx.lineWidth = 1; ctx.stroke();
      }
      // haze toward the limb, additive (§2.2)
      const haze = ctx.createRadialGradient(cx, cy, 0, cx, cy, Rs);
      [[0, 0], [.53, 0], [.6, 4], [.66, 8], [.71, 12], [.77, 17], [.82, 22], [.88, 28], [.93, 34], [.96, 37], [.99, 45], [1, 50]].forEach(([s, n]) => haze.addColorStop(s, `rgb(${Math.round(n * .78)},${Math.round(n * .9)},${n})`));
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = haze; ctx.fillRect(cx - Rs, cy - Rs, 2 * Rs, 2 * Rs);
      ctx.globalCompositeOperation = "source-over";
      ctx.restore();
      // rim and glow
      ctx.beginPath(); ctx.arc(cx, cy, Rs - 1, 0, TAU); ctx.strokeStyle = "rgb(104,121,140)"; ctx.lineWidth = 1.5; ctx.stroke();
      const glow = ctx.createRadialGradient(cx, cy, Rs, cx, cy, Rs + 18);
      [[0, .26], [2 / 18, .178], [4 / 18, .114], [6 / 18, .069], [8 / 18, .04], [10 / 18, .025], [12 / 18, .015], [14 / 18, .01], [16 / 18, .005], [1, 0]].forEach(([s, a]) => glow.addColorStop(s, `rgba(214,226,238,${a})`));
      ctx.beginPath(); ctx.arc(cx, cy, Rs + 18, 0, TAU); ctx.arc(cx, cy, Rs, 0, TAU, true); ctx.fillStyle = glow; ctx.fill();
      // markers: hard cut at the horizon, active one red and larger, swapped on the hover frame (§3)
      for (const t of topics) {
        const v = vec(t.lon, t.lat), q = turn(v[0], v[1], v[2]);
        if (q[2] <= 1 / P) continue;
        const k = (P - 1) / (P - q[2]), X = cx + S * k * q[0], Y = cy - S * k * q[1];
        const sp = t === active ? sprites[t.index].active : sprites[t.index].normal, w = sp.width / 2, h = sp.height / 2;
        ctx.drawImage(sp, X - w / 2, Y - h / 2, w, h);
      }
    }
    function frame(now) {
      raf = 0;
      let more = false;
      if (padTween) { const p = clamp01((now - padTween.t0) / padTween.dur); pad = lerp(padTween.from, padTween.to, MAPBOX(p)); if (p < 1) more = true; else padTween = null; }
      if (tween) more = tween(now) || more;
      if (inertia) {
        const p = clamp01((now - inertia.t0) / inertia.dur), e = bezier(0, 0, .3, 1)(p);
        view.lon = inertia.lon + inertia.dlon * e; view.lat = clamp(inertia.lat + inertia.dlat * e, -85, 85);
        if (p < 1) more = true; else inertia = null;
      }
      draw();
      if (more) raf = requestAnimationFrame(frame);
    }
    function wake() { if (!raf && live) raf = requestAnimationFrame(frame); }
    // hover → rotate (copy of the reference's panTo, §9.4): 1000 ms for any hop of 347 km or more, bezier(.25,.1,.25,1),
    // linear in Web-Mercator (rhumb line), shortest way round, restarted from wherever the globe is; zoom never changes
    const mercY = lat => Math.log(Math.tan(Math.PI / 4 + lat * RAD / 2));
    const unMercY = y => (2 * Math.atan(Math.exp(y)) - Math.PI / 2) / RAD;
    const km = (a, b) => { const p1 = a.lat * RAD, p2 = b.lat * RAD, dp = p2 - p1, dl = (b.lon - a.lon) * RAD; const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2; return 2 * 6371.0088 * Math.asin(Math.min(1, Math.sqrt(h))); };
    function panTo(t) {
      if (!ready) return;
      inertia = null;
      const from = { lon: view.lon, lat: view.lat };
      let dLon = t.lon - from.lon;
      dLon = ((dLon + 540) % 360) - 180;
      const duration = 5000 / clamp(km(from, t) * .0144, .5, 5);
      if (reduced.matches) { view.lon = from.lon + dLon; view.lat = t.lat; wake(); return; }
      const y0 = mercY(from.lat), y1 = mercY(t.lat), t0 = performance.now();
      tween = now => {
        const p = MAPBOX(Math.min(1, (now - t0) / duration));
        view.lon = from.lon + dLon * p; view.lat = unMercY(y0 + (y1 - y0) * p);
        if (p >= 1) tween = null;
        return p < 1;
      };
      wake();
    }
    function setActive(t) { if (active !== t) { active = t; wake(); } }
    // drag (Mapbox dragPan): the point under the cursor follows; release coasts (linearity .3, bezier(0,0,.3,1), 2500 px/s²)
    let drag = null;
    canvas.addEventListener("pointerdown", event => {
      if (event.button !== 0) return;
      drag = { x: event.clientX, y: event.clientY, t: performance.now(), vx: 0, vy: 0 };
      tween = null; inertia = null;
      canvas.setPointerCapture?.(event.pointerId);
      canvas.style.cursor = "grabbing";
    });
    canvas.addEventListener("pointermove", event => {
      if (!drag) return;
      const now = performance.now(), dx = event.clientX - drag.x, dy = event.clientY - drag.y, dt = Math.max(1, now - drag.t);
      view.lon -= dx / (S * Math.max(.2, Math.cos(view.lat * RAD))) / RAD;
      view.lat = clamp(view.lat + dy / S / RAD, -85, 85);
      drag.vx = drag.vx * .5 + dx / dt * 1000 * .5; drag.vy = drag.vy * .5 + dy / dt * 1000 * .5;
      Object.assign(drag, { x: event.clientX, y: event.clientY, t: now });
      wake();
    });
    const release = () => {
      if (!drag) return;
      const speed = Math.min(1400, Math.hypot(drag.vx, drag.vy) * .3);
      if (speed > 40 && !reduced.matches && performance.now() - drag.t < 80) {
        const dur = speed / 2500, dist = speed * dur / 2, n = Math.hypot(drag.vx, drag.vy) || 1;
        inertia = { t0: performance.now(), dur: dur * 1000, lon: view.lon, lat: view.lat,
          dlon: -(drag.vx / n * dist) / (S * Math.max(.2, Math.cos(view.lat * RAD))) / RAD, dlat: (drag.vy / n * dist) / S / RAD };
        wake();
      }
      drag = null;
      canvas.style.cursor = "";
    };
    canvas.addEventListener("pointerup", release);
    canvas.addEventListener("pointercancel", release);
    let listOpen = true;
    return {
      view, panTo, setActive, size,
      start() { live = true; size(); wake(); },
      stop() { live = false; cancelAnimationFrame(raf); raf = 0; tween = null; inertia = null; padTween = null; },
      reset() { view.lon = 30.7; view.lat = 36.9; active = null; tween = null; inertia = null; },
      // the list opening: the globe glides from the window centre into the free half (padding, 600 ms) — then hovers turn it.
      // `delay` stands in for the reference's map load, which starts the glide (warm: .4–1 s after the page mounts)
      glide(delay = 0) {
        ready = false;
        if (!wide.matches || reduced.matches) { pad = wide.matches ? W / 2 : 0; ready = true; wake(); return; }
        padTween = { from: 0, to: W / 2, t0: performance.now() + delay, dur: 600 };
        pad = 0;
        setTimeout(() => { ready = true; }, delay + 600);
        wake();
      },
      redraw: wake,
    };
  })();
  addEventListener("resize", () => { if (root.classList.contains("focus-list")) globe.size(); if (root.classList.contains("focus-detail")) drawMap(current); });
  worldReady.then(() => { globe.redraw(); if (root.classList.contains("focus-detail")) drawMap(current); });

  /* ---------- The list (§5): rows as the reference lays them out ---------- */
  rows.forEach(row => { // text column (kicker, title, meta) next to the picture
    const text = make("span", "ct-text");
    [...row.children].filter(c => !c.classList.contains("ct-img")).forEach(c => text.append(c));
    row.prepend(text);
  });
  const line = make("i", "ct-line"); line.setAttribute("aria-hidden", "true");
  panel.append(line);
  let hovered = null;
  listCol.addEventListener("mouseover", event => {
    if (!fine.matches) return;
    const t = topics.find(x => x.row === event.target.closest?.(".ct-row"));
    if (!t || t === hovered) return;
    hovered = t; globe.panTo(t); globe.setActive(t);
  });
  listCol.addEventListener("mouseleave", () => { hovered = null; globe.setActive(null); }); // the globe stays where it is
  listCol.addEventListener("click", event => {
    const t = topics.find(x => x.row === event.target.closest?.(".ct-row"));
    if (!t || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    openTopic(t);
  });

  /* ---------- The topic pages (iceberg-detail §3): picture, title, content, agencies table, NEXT ---------- */
  const mapCanvas = make("canvas", "pd-map");
  mapCanvas.setAttribute("aria-hidden", "true");
  document.body.append(mapCanvas);
  const words = { next: () => (en() ? "Next" : "下一个") };
  topics.forEach((t, i) => {
    const s = t.section, heading = s.querySelector(":scope > .section-heading");
    s.classList.add("pd");
    const img = make("div", "pd-img", `<img alt="" data-src="${t.image}" draggable="false">`); // src set on the first visit (setClasses)
    img.setAttribute("aria-hidden", "true");
    const lines = make("div", "pd-lines", "<i></i><i></i><i></i>");
    lines.setAttribute("aria-hidden", "true");
    const content = make("div", "pd-content");
    [...s.children].filter(c => c !== heading).forEach(c => content.append(c));
    const coverage = heading?.querySelector(":scope > p"); // 新加坡: the coverage note opens the content
    if (coverage) { const intro = make("div", "pd-intro"); intro.append(coverage); content.prepend(intro); }
    s.prepend(img, lines);
    s.append(content);
    Object.assign(t, { heading, img, lines, content, nextTopic: topics[(i + 1) % topics.length] });
  });
  // NEXT: one bar for every topic page, fixed under the map (a fixed element inside the sliding panel would ride with it)
  const nextBar = make("a", "pd-next");
  nextBar.innerHTML = `<span class="pd-next-label"></span><span class="pd-next-body"><b class="pd-next-title"></b><small class="pd-next-place"></small></span>`;
  nextBar.addEventListener("click", event => { event.preventDefault(); event.stopPropagation(); if (current) goNext(current.nextTopic); });
  document.body.append(nextBar);
  topics.forEach(t => { t.next = nextBar; });
  function fillWords() {
    const n = current?.nextTopic;
    nextBar.querySelector(".pd-next-label").textContent = words.next();
    if (!n) return;
    nextBar.href = `./cop31/#${n.id}`;
    nextBar.querySelector(".pd-next-title").textContent = n.row.querySelector(".ct-title")?.textContent.trim() || "";
    nextBar.querySelector(".pd-next-place").textContent = n.row.querySelector(".ct-place")?.textContent.trim() || "";
  }
  new MutationObserver(fillWords).observe(root, { attributes: true, attributeFilter: ["lang"] });
  fillWords();
  // agencies → the reference's closing table: lines grow left to right (.7 s, .15 s apart), cells fade (.6 s, .1 s apart),
  // once, when its top crosses 70 % of the window
  const tableWatch = "IntersectionObserver" in window ? new IntersectionObserver(entries => entries.forEach(entry => {
    if (!entry.isIntersecting) return;
    tableWatch.unobserve(entry.target);
    [...entry.target.querySelectorAll(".agency-card")].forEach((card, i) => { card.style.setProperty("--dl", `${i * .15}s`); card.style.setProperty("--dc", `${.2 + i * .1}s`); });
    entry.target.classList.add("is-drawn");
  }), { rootMargin: "0px 0px -30% 0px" }) : null;

  // the flat map of a topic (§3.5, §6.4): Web Mercator at zoom 5 (2607.6 px per radian), centred on the topic, drawn once
  function drawMap(t) {
    if (!t || !wide.matches) return;
    const w = Math.round(innerWidth * .33), h = innerHeight, dpr = Math.min(2, devicePixelRatio || 1);
    mapCanvas.width = w * dpr; mapCanvas.height = h * dpr;
    const g = mapCanvas.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.fillStyle = "#0c131b"; g.fillRect(0, 0, w, h);
    if (!world) return;
    const k = 2607.6, mY = lat => Math.log(Math.tan(Math.PI / 4 + clamp(lat, -85, 85) * RAD / 2)), y0 = mY(t.lat);
    const P = ([lon, lat]) => [w / 2 + k * (lon - t.lon) * RAD, h / 2 - k * (mY(lat) - y0)];
    const near = pts => pts.some(([lon, lat]) => Math.abs(lon - t.lon) < 40 && Math.abs(lat - t.lat) < 35);
    g.beginPath();
    for (const ring of world.rings) {
      if (!near(ring)) continue;
      ring.forEach((p, i) => { const [x, y] = P(p); i ? g.lineTo(x, y) : g.moveTo(x, y); });
      g.closePath();
    }
    g.fillStyle = "#1a2431"; g.fill("evenodd");
    g.beginPath();
    for (let lon = Math.floor(t.lon - 12); lon <= t.lon + 12; lon += 1) { const [x] = P([lon, t.lat]); g.moveTo(x, 0); g.lineTo(x, h); }
    for (let lat = Math.floor(t.lat - 12); lat <= t.lat + 12; lat += 1) { const [, y] = P([t.lon, lat]); g.moveTo(0, y); g.lineTo(w, y); }
    g.strokeStyle = "rgba(205,215,225,.032)"; g.lineWidth = 1; g.stroke();
    g.strokeStyle = "rgba(205,215,225,.10)"; g.lineWidth = .8; g.stroke();
    g.beginPath();
    for (const arc of world.borders) {
      if (!near(arc)) continue;
      arc.forEach((p, i) => { const [x, y] = P(p); i ? g.lineTo(x, y) : g.moveTo(x, y); });
    }
    g.strokeStyle = "rgba(205,215,225,.24)"; g.lineWidth = 1; g.stroke();
    const sp = scribble(46, 40, "#ffffff", 1.1, t.index + 3);
    g.drawImage(sp, w / 2 - 23, h / 2 - 20, 46, 40);
  }

  /* ---------- Splitting the title into rising characters (SplitText replacement, §6.5) ---------- */
  const CJK = /[\u2E80-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF]/;
  function splitChars(el) {
    if (!el) return [];
    const text = el.dataset.plain ?? el.textContent.trim();
    el.dataset.plain = text;
    el.textContent = "";
    // words (a CJK character is a word of its own), then the words grouped into the lines they fall on
    const words = [];
    let gap = false;
    for (const token of text.match(/[\u2E80-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF]|[^\s\u2E80-\u9FFF\uF900-\uFAFF\uFF00-\uFFEF]+|\s+/g) || []) {
      if (/^\s+$/.test(token)) { gap = true; continue; }
      const word = make("span", "pd-word");
      for (const ch of token) { const c = make("span", "pd-char"); c.textContent = ch; word.append(c); }
      if (gap && words.length) el.append(" ");
      el.append(word);
      words.push({ word, gap: gap && words.length > 0 });
      gap = false;
    }
    const lines = [];
    words.forEach(w => { const top = w.word.offsetTop, last = lines.at(-1); if (last && Math.abs(last.top - top) < 4) last.words.push(w); else lines.push({ top, words: [w] }); });
    el.textContent = "";
    const chars = [];
    lines.forEach(entry => {
      const line = make("span", "pd-line");
      entry.words.forEach((w, i) => { if (i && w.gap) line.append(" "); line.append(w.word); chars.push(...w.word.children); });
      el.append(line);
    });
    return chars;
  }
  // app.js rewrites the heading on a language switch: forget the split so the next entrance splits the new words
  topics.forEach(t => { const h2 = t.heading?.querySelector("h2"), over = t.heading?.querySelector(".overline");
    [h2, over].forEach(el => el && new MutationObserver(() => { if (!el.querySelector(".pd-char")) delete el.dataset.plain; }).observe(el, { childList: true })); });

  /* ---------- Page states ---------- */
  const setClasses = page => {
    const isList = page === "countries", isDetail = !!topicOf(page);
    root.classList.toggle("focus-page", isList || isDetail);
    root.classList.toggle("focus-list", isList);
    root.classList.toggle("focus-detail", isDetail);
    // the full-size photos (≈1.4 MB) load once 国家专题 is open, not with the home page (2026-11-02)
    if (isList || isDetail) topics.forEach(t => { const photo = t.img?.querySelector("img[data-src]"); if (photo) { photo.src = photo.dataset.src; photo.removeAttribute("data-src"); } });
  };
  let busy = false, swapping = false;
  const swap = id => { swapping = true; window.GreenPages?.swap(id); swapping = false; setClasses(id === "countries" || topicOf(id) ? id : "home"); };
  const push = id => history.pushState({ ...(history.state || {}), focus: id }, "", `${location.pathname}${location.search}#${id}`);

  // entering the list: it slides in from the right (.6 s cubic in-out); fresh from elsewhere the globe glides from the
  // window centre into the left half; back from a topic the globe fades in after the slide (the reference's order)
  async function enterList(fromTopic = false, glideDelay = 0) {
    current = null;
    setClasses("countries");
    hovered = null;
    globe.start();
    if (fromTopic) globe.reset();
    globe.setActive(null);
    // fresh, the list starts a whole window plus 40u to the right (the reference's translateX(calc(100vw + 40u)))
    const dx = (fromTopic ? listCol.offsetWidth : innerWidth) + 40 * innerWidth / 2024;
    const tw = [{ at: 0, dur: .6, ease: E.cubicInOut, set: v => { listCol.style.transform = v < 1 ? `translate3d(${(1 - v) * dx}px,0,0)` : ""; } }];
    if (fromTopic) {
      panel.style.opacity = "0";
      tw.push({ at: .6, dur: .6, ease: E.cubicOut, set: v => { panel.style.opacity = v.toFixed(3); } });
      setTimeout(() => globe.glide(), reduced.matches ? 0 : 600);
    } else { panel.style.opacity = ""; globe.glide(glideDelay); }
    await play(tw);
    panel.style.opacity = "";
  }
  // a topic's entrance (§2.4), t′ = 0 at mount
  let run = 0; // the topic entrance playing; NEXT, Esc or Back during it stop it (2026-10-29: they were ignored till it ended)
  async function enterTopic(t) {
    const me = run += 1;
    current = t;
    setClasses(t.id);
    fillWords();
    (wide.matches ? document.body : t.section).append(nextBar); // phones: NEXT closes the page in the flow
    globe.stop();
    drawMap(t);
    if (tableWatch) { const grid = t.content.querySelector(".agency-grid"); grid?.classList.remove("is-drawn"); if (grid) tableWatch.observe(grid); }
    const s = t.section, h2 = t.heading?.querySelector("h2"), over = t.heading?.querySelector(".overline");
    const chars = [...splitChars(h2), ...splitChars(over)];
    const charsEnd = 1.2 + Math.max(0, chars.length - 1) * .01 + 1;
    const tw = [
      { at: 0, dur: .8, ease: E.cubicInOut, set: v => { s.style.transform = v < 1 ? `translate3d(${((1 - v) * 100).toFixed(3)}%,0,0)` : ""; } },
      { at: .4, dur: .6, ease: E.cubicInOut, set: v => { mapCanvas.style.opacity = t.lines.style.opacity = v.toFixed(3); } },
      { at: .8, dur: .8, ease: E.quintOut, set: v => { t.img.style.clipPath = v < 1 ? `polygon(0 0,100% 0,100% ${(v * 100).toFixed(2)}%,0 ${(v * 100).toFixed(2)}%)` : ""; } },
      ...chars.map((c, i) => ({ at: 1.2 + i * .01, dur: 1, ease: E.quintOut, set: v => { c.style.transform = v < 1 ? `translate3d(0,${((1 - v) * 100).toFixed(2)}%,0)` : ""; c.style.opacity = v < 1 ? v.toFixed(3) : ""; } })),
      { at: 1.81, dur: .6, ease: E.cubicOut, set: v => { t.next.style.transform = `translate3d(0,${((1 - v) * 100).toFixed(2)}%,0)`; } },
      { at: charsEnd - .4, dur: .8, ease: E.cubicInOut, set: v => { t.content.style.opacity = v < 1 ? v.toFixed(3) : ""; } },
    ];
    await play(tw, () => me === run);
  }
  async function openTopic(t) {
    if (busy) return;
    busy = true;
    try {
      const dx = listCol.offsetWidth + 40 * innerWidth / 2024;
      await play([
        { at: 0, dur: .6, ease: E.cubicInOut, set: v => { listCol.style.transform = `translate3d(${v * dx}px,0,0)`; } },
        { at: 0, dur: .6, ease: E.cubicInOut, set: v => { panel.style.opacity = (1 - v).toFixed(3); } },
      ]);
      push(t.id);
      drawMap(t);
      prepareTopic(t);
      await wait(HOLD);
      swap(t.id);
      listCol.style.transform = ""; panel.style.opacity = "";
      busy = false; // the page is up: from here NEXT / Esc may cut the entrance short
      await enterTopic(t);
    } finally { busy = false; }
  }
  function prepareTopic(t) { // the entrance's start state, before the page is shown
    t.section.style.transform = "translate3d(100%,0,0)";
    mapCanvas.style.opacity = t.lines.style.opacity = "0";
    t.img.style.clipPath = "polygon(0 0,100% 0,100% 0,0 0)";
    t.next.style.transform = "translate3d(0,100%,0)";
    t.content.style.opacity = "0";
  }
  // Esc on a topic: NEXT drops, map and lines fade, the panel slides away, the dark hold, the list comes back (§3.10)
  async function closeTopic() {
    const t = current;
    if (!t || busy) return;
    busy = true;
    run += 1; // an entrance still playing stops where it is, and the close carries on from there
    const from = (element, pattern) => Number(pattern.exec(element.style.transform)?.[1] || 0);
    const n0 = from(t.next, /translate3d\(0,\s*([-\d.]+)%/), s0 = from(t.section, /translate3d\(([-\d.]+)%/);
    const m0 = mapCanvas.style.opacity === "" ? 1 : Number(mapCanvas.style.opacity);
    try {
      await play([
        { at: 0, dur: .6, ease: E.cubicOut, set: v => { t.next.style.transform = `translate3d(0,${(n0 + (100 - n0) * v).toFixed(2)}%,0)`; } },
        { at: .2, dur: .6, ease: E.cubicInOut, set: v => { mapCanvas.style.opacity = t.lines.style.opacity = (m0 * (1 - v)).toFixed(3); } },
        { at: .4, dur: .8, ease: E.cubicInOut, set: v => { t.section.style.transform = `translate3d(${(s0 + (100 - s0) * v).toFixed(3)}%,0,0)`; } },
      ]);
      push("countries");
      await wait(HOLD);
      swap("countries");
      t.section.style.transform = "";
      await enterList(true);
    } finally { busy = false; }
  }
  // NEXT: the whole page fades as one layer (.6 s), then the next topic's full entrance (§3.9)
  async function goNext(n) {
    if (busy || !current) return;
    busy = true;
    run += 1; // stop an entrance still playing
    try {
      await fadePage(0);
      push(n.id);
      prepareTopic(n);
      swap(n.id);
      fadePageReset();
      busy = false; // the next page is up: it can be left again during its entrance
      await enterTopic(n);
    } finally { busy = false; }
  }
  const pageLayers = () => [document.querySelector("main"), mapCanvas, nextBar];
  const fadePage = () => play([{ at: 0, dur: .6, ease: E.cubicInOut, set: v => pageLayers().forEach(l => { l.style.opacity = (1 - v).toFixed(3); }) }]);
  const fadePageReset = () => pageLayers().forEach(l => { l.style.opacity = l === mapCanvas ? "0" : ""; });
  // the shared bar's own rest state between pages
  const hideNext = () => { nextBar.style.transform = "translate3d(0,100%,0)"; };

  /* ---------- 国家专题 chosen on another page: the six-column overlay (the reference's route middleware) ----------
     Six columns in the page colour close over the old page from the right: scaleX 0 → 1 from each column's right edge,
     .4 s each, .07 s apart, power2.out, right-most first. The page swaps underneath; .3 s later they open: scaleX 1 → 0
     towards each left edge, .6 s each, .1 s apart, power2.out, right-most first, while the list slides in. ≤1023 px:
     four columns of 25 %, the two hidden ones keeping their places in the stagger (as in the reference). */
  const overlay = make("div", "ct-overlay");
  overlay.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 6; i += 1) overlay.append(make("div"));
  document.body.append(overlay);
  const columns = [...overlay.children].reverse();
  function blinds(close) {
    if (close) root.classList.add("blinds-on"); // while it lasts (cop31.js holds the 数据统计 entrance till it opens)
    columns.forEach(c => { c.style.transformOrigin = close ? "right center" : "left center"; });
    return play(columns.map((c, i) => close
      ? { at: i * .07, dur: .4, ease: E.cubicOut, set: v => { c.style.transform = `scaleX(${v.toFixed(4)})`; } }
      : { at: .3 + i * .1, dur: .6, ease: E.cubicOut, set: v => { c.style.transform = `scaleX(${(1 - v).toFixed(4)})`; } }))
      .then(() => { if (!close) root.classList.remove("blinds-on"); });
  }
  // From a topic page the reference never runs the overlay: the page fades as one layer, then the list comes back.
  async function arrive(onSwap) {
    if (busy) return;
    busy = true;
    try {
      if (topicOf(window.GreenPages?.current())) {
        await fadePage();
        swap("countries"); onSwap?.(); fadePageReset();
        await enterList(true);
        return;
      }
      await blinds(true);
      swap("countries"); onSwap?.();
      const entering = enterList(false, 700); // the glide lands while the left columns open
      await blinds(false);
      await entering;
    } finally { busy = false; }
  }

  // Back / Forward: the current view fades as one layer, then the other view enters (§4)
  addEventListener("popstate", async () => {
    const id = decodeURIComponent(location.hash.slice(1)), page = window.GreenPages?.current();
    const toOwn = OWN.has(id), fromOwn = OWN.has(page);
    if (!toOwn && !fromOwn) return;
    if (busy) return;
    busy = true;
    run += 1; // stop an entrance still playing
    try {
      if (fromOwn) { await fadePage(); }
      if (topicOf(id)) { prepareTopic(topicOf(id)); swap(id); fadePageReset(); await enterTopic(topicOf(id)); }
      else if (id === "countries") { swap("countries"); fadePageReset(); await enterList(!!topicOf(page)); }
      else { swap(id || "top"); fadePageReset(); leave(); }
    } finally { busy = false; }
  });
  addEventListener("keydown", event => {
    if (event.key === "Escape" && current && !event.defaultPrevented && !document.querySelector("dialog[open]") && !root.classList.contains("menu-open")) { event.preventDefault(); closeTopic(); }
  });
  function leave() { // another page took over (menu, stamps, hash): put everything back to rest
    current = null;
    setClasses("home");
    globe.stop();
    mapCanvas.style.opacity = "0";
    hideNext();
    listCol.style.transform = ""; panel.style.opacity = "";
    topics.forEach(t => { t.section.style.transform = ""; });
  }
  // pages cop31.js switches to (menu, stamps, reel, typed hash) start their own entrance here
  addEventListener("cop31:page", event => {
    if (swapping) return;
    const page = event.detail.page;
    if (page === "countries") enterList(false);
    else if (topicOf(page)) { prepareTopic(topicOf(page)); enterTopic(topicOf(page)); }
    else if (root.classList.contains("focus-page")) leave();
  });

  window.GreenFocus = { owns: id => OWN.has(id), open: arrive, blinds }; // blinds: cop31.js runs it for 语料分析 / 情报问答 / 文本数据库 too
  // a direct load of #countries / #chinaCarbon / #singapore (cop31.js has already chosen the page)
  const boot = () => {
    const page = root.dataset.page;
    if (page === "countries") enterList(false);
    else if (topicOf(page)) { prepareTopic(topicOf(page)); enterTopic(topicOf(page)); }
  };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", boot) : boot();
})();
