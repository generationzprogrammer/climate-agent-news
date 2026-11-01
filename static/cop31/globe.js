/* GREEN · COP31 — the "global climate situation" globe (2026-10-29).
   A dot-matrix Earth on a pale square plate (since 2026-10-29; the dark panel is gone), drawn on a 2D canvas: land is sampled once from
   assets/countries-110m.json into a few thousand dots (even density on the sphere) and projected orthographically every
   frame. The events app.js maps (dashboard.json, today / this week) glow red with pulse rings; great-circle arcs rise from
   Antalya, the COP31 host, to each event and carry a light along them. The globe turns slowly by itself, can be dragged
   (with inertia), and turns to an event on a spring when it is picked — here, in the place list, or by keyboard.
   app.js stays in charge: picking dispatches to its own SVG pins (#worldMap .event-pin[data-marker]), which remain in the
   page, hidden, as the accessible layer and as the source of the map stamp's miniature. Presentation only.
   prefers-reduced-motion: no spin, pulses, lights or entrance; the globe is drawn still and turns instantly. */
(() => {
  "use strict";
  const host = document.getElementById("mapCanvas");
  const svg = document.getElementById("worldMap");
  const M = window.GreenMotion;
  if (!host || !svg || !M) return;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const RAD = Math.PI / 180;
  const HUB = { lon: 30.71, lat: 36.9 }; // Antalya
  const SPIN = 4.2; // degrees per second while idle
  const clamp = M.clamp;
  const smooth = t => t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t);
  const easeOutBack = t => { const c = 1.7; return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2; };

  const canvas = document.createElement("canvas");
  canvas.className = "globe";
  canvas.style.cursor = "grab";
  canvas.setAttribute("aria-hidden", "true");
  host.prepend(canvas);
  host.classList.add("has-globe");
  const ctx = canvas.getContext("2d");

  // ---------- Geometry: unit vectors (x east, y north, z through lon 0 / lat 0) ----------
  const vec = (lon, lat) => { const l = lon * RAD, p = lat * RAD, c = Math.cos(p); return [c * Math.sin(l), Math.sin(p), c * Math.cos(l)]; };
  const view = { lon: 18, lat: 22 }; // the point facing the viewer
  let rot = null;
  const updateRotation = () => {
    const l = view.lon * RAD, p = view.lat * RAD;
    rot = { cl: Math.cos(l), sl: Math.sin(l), cp: Math.cos(p), sp: Math.sin(p) };
  };
  const turn = ([x, y, z]) => { // yaw by −lon, then pitch by lat: the view point lands on +z
    const x1 = x * rot.cl - z * rot.sl, z1 = z * rot.cl + x * rot.sl;
    return [x1, y * rot.cp - z1 * rot.sp, y * rot.sp + z1 * rot.cp];
  };
  let W = 0, H = 0, R = 0, CX = 0, CY = 0, DPR = 1;
  const screen = ([x, y]) => [CX + x * R, CY - y * R];

  // ---------- Land dots from the topology ----------
  let land = [];
  function decode(topo) {
    const [sx, sy] = topo.transform?.scale || [1, 1], [tx, ty] = topo.transform?.translate || [0, 0];
    const arcs = topo.arcs.map(arc => { let x = 0, y = 0; return arc.map(([dx, dy]) => { x += dx; y += dy; return [x * sx + tx, y * sy + ty]; }); });
    const ring = refs => refs.flatMap((ref, index) => { const points = ref < 0 ? arcs[~ref].slice().reverse() : arcs[ref]; return index ? points.slice(1) : points; });
    const object = topo.objects.land || topo.objects.countries;
    const geometries = object.type === "GeometryCollection" ? object.geometries : [object];
    const polygons = [];
    geometries.forEach(g => {
      if (g.type === "Polygon") polygons.push(g.arcs.map(ring));
      else if (g.type === "MultiPolygon") g.arcs.forEach(polygon => polygons.push(polygon.map(ring)));
    });
    return polygons;
  }
  function sampleLand(polygons) {
    const mw = 1440, mh = 720, mask = document.createElement("canvas");
    mask.width = mw; mask.height = mh;
    const m = mask.getContext("2d", { willReadFrequently: true });
    m.fillStyle = "#000";
    for (const shift of [-360, 0, 360]) { // rings that cross the antimeridian are unwrapped and drawn three times
      m.beginPath();
      polygons.forEach(rings => rings.forEach(points => {
        let last = null, offset = 0;
        points.forEach(([lon, lat], index) => {
          if (last !== null && Math.abs(lon - last) > 180) offset += lon < last ? 360 : -360;
          last = lon;
          const x = (lon + offset + shift + 180) / 360 * mw, y = (90 - lat) / 180 * mh;
          index ? m.lineTo(x, y) : m.moveTo(x, y);
        });
        m.closePath();
      }));
      m.fill("evenodd");
    }
    const pixels = m.getImageData(0, 0, mw, mh).data, dots = [], step = 1.35;
    for (let lat = -82; lat <= 84; lat += step) {
      const lonStep = step / Math.max(.18, Math.cos(lat * RAD));
      for (let lon = -180; lon < 180; lon += lonStep) {
        const x = Math.floor((lon + 180) / 360 * mw), y = Math.floor((90 - lat) / 180 * mh);
        if (pixels[(y * mw + x) * 4 + 3] > 127) {
          const v = vec(lon, lat);
          v.push(Math.random()); // per-dot jitter for the entrance sweep
          dots.push(v);
        }
      }
    }
    return dots;
  }

  // ---------- Events (the lists app.js maps) and their arcs from Antalya ----------
  const hubVec = vec(HUB.lon, HUB.lat);
  let byId = new Map(), events = [], selected = null, hovered = null, focused = null;
  function arcPoints(to) {
    const dot = clamp(hubVec[0] * to[0] + hubVec[1] * to[1] + hubVec[2] * to[2], -1, 1), omega = Math.acos(dot);
    const lift = .05 + .2 * omega / Math.PI, points = [], n = Math.max(12, Math.round(omega / RAD / 2.5));
    for (let i = 0; i <= n; i += 1) {
      const t = i / n, s = Math.sin(omega) || 1;
      const a = Math.sin((1 - t) * omega) / s, b = Math.sin(t * omega) / s, h = 1 + lift * Math.sin(Math.PI * t);
      points.push([(a * hubVec[0] + b * to[0]) * h, (a * hubVec[1] + b * to[1]) * h, (a * hubVec[2] + b * to[2]) * h]);
    }
    return points;
  }
  let refreshAt = 0; // a period switch redraws the arcs and markers (the land stays)
  function setEvents(ids) {
    const list = ids.map(id => byId.get(id)).filter(Boolean);
    const changed = list.map(item => item.marker_id).join() !== events.map(event => event.id).join();
    events = list.map((item, index) => {
      const v = vec(Number(item.lon), Number(item.lat));
      return { id: item.marker_id, lon: Number(item.lon), lat: Number(item.lat), v, arc: arcPoints(v), phase: (index * .37) % 1 };
    }).filter(event => Number.isFinite(event.lon) && Number.isFinite(event.lat));
    if (changed || !events.some(event => event.id === selected)) selected = events[0]?.id ?? null; // app.js selects the first on every redraw
    if (changed && intro >= 1) { refreshAt = performance.now(); if (selected) aimAt(selected); wake(); }
    draw();
  }
  // Progress of the arcs/markers entrance: the first entrance, or the last period switch.
  const arcClock = now => Math.min(intro, reduced.matches ? 1 : clamp((now - refreshAt) / 2200, 0, 1));
  const stagger = () => Math.min(.05, 1.1 / Math.max(1, events.length));
  const pinFor = id => svg.querySelector(`.event-pin[data-marker="${CSS.escape(id)}"]`);

  // ---------- Camera: idle spin, drag with inertia, spring to a picked event ----------
  let idleSince = 0, drag = null, inertia = { lon: 0, lat: 0 }, aim = null, aiming = false;
  const shortest = (from, to) => ((to - from + 540) % 360) - 180;
  function aimAt(id) {
    const event = events.find(item => item.id === id);
    if (!event) return;
    aim?.stop();
    inertia = { lon: 0, lat: 0 };
    const from = { ...view }, dLon = shortest(from.lon, event.lon), toLat = clamp(event.lat * .75, -38, 42);
    idleSince = performance.now() + 2600; // hold still a moment after arriving
    if (reduced.matches) { view.lon = from.lon + dLon; view.lat = toLat; draw(); return; }
    aim = M.progress({ k: 120, c: 20, m: 1 }, p => { view.lon = from.lon + dLon * p; view.lat = M.lerp(from.lat, toLat, p); });
    aiming = true;
    aim.finished.then(() => { aiming = false; });
    wake();
  }
  function select(id, turnTo = true) {
    if (!id) return;
    selected = id;
    if (turnTo) aimAt(id);
    draw();
  }

  // ---------- Drawing ----------
  let intro = 0, introStart = 0, running = false, onScreen = false, last = 0;
  const visibleLifted = ([x, y, z]) => z > 0 || x * x + y * y > 1; // a lifted point beyond the limb is still in view
  const depth = z => smooth((z + .35) / .55); // the far side of an arc recedes
  // The plate the globe sits on (2026-10-29; the pale card itself is .map-canvas in cop31.css): a crosshair, a ring
  // with degree ticks that turns with the globe, and a dotted outer ring, engraved behind the sphere.
  function drawPlate() {
    const TAU = Math.PI * 2, r0 = R * 1.16, turnBy = -view.lon * RAD;
    ctx.save();
    ctx.lineWidth = DPR;
    ctx.strokeStyle = "rgba(20, 34, 52, .07)";
    ctx.beginPath(); ctx.moveTo(0, CY); ctx.lineTo(W, CY); ctx.moveTo(CX, 0); ctx.lineTo(CX, H); ctx.stroke();
    ctx.strokeStyle = "rgba(20, 34, 52, .13)";
    ctx.beginPath(); ctx.arc(CX, CY, r0, 0, TAU); ctx.stroke();
    ctx.beginPath();
    for (let a = 0; a < 360; a += 5) {
      const len = (a % 30 === 0 ? 9 : a % 10 === 0 ? 5 : 2.5) * DPR, t = a * RAD + turnBy, c = Math.cos(t), s = Math.sin(t);
      ctx.moveTo(CX + c * r0, CY + s * r0); ctx.lineTo(CX + c * (r0 + len), CY + s * (r0 + len));
    }
    ctx.stroke();
    ctx.strokeStyle = "rgba(20, 34, 52, .1)";
    ctx.setLineDash([2 * DPR, 6 * DPR]);
    ctx.beginPath(); ctx.arc(CX, CY, R * 1.36, 0, TAU); ctx.stroke();
    ctx.restore();
  }
  function drawSphere() {
    const glow = ctx.createRadialGradient(CX, CY, R * .92, CX, CY, R * 1.32);
    glow.addColorStop(0, "rgba(140, 172, 205, .22)");
    glow.addColorStop(.35, "rgba(110, 145, 182, .08)");
    glow.addColorStop(1, "rgba(110, 145, 182, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath(); ctx.arc(CX, CY, R * 1.32, 0, Math.PI * 2); ctx.fill();
    const body = ctx.createRadialGradient(CX - R * .38, CY - R * .42, R * .1, CX, CY, R);
    body.addColorStop(0, "#3d5370");
    body.addColorStop(.55, "#253446");
    body.addColorStop(1, "#141e2a");
    ctx.fillStyle = body;
    ctx.beginPath(); ctx.arc(CX, CY, R, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "rgba(170, 198, 226, .22)";
    ctx.lineWidth = DPR;
    ctx.stroke();
  }
  function drawGraticule() {
    ctx.strokeStyle = "rgba(160, 190, 222, .07)";
    ctx.lineWidth = DPR;
    const line = points => {
      ctx.beginPath();
      let pen = false;
      points.forEach(p => { const q = turn(p); if (q[2] > 0) { const [x, y] = screen(q); pen ? ctx.lineTo(x, y) : ctx.moveTo(x, y); pen = true; } else pen = false; });
      ctx.stroke();
    };
    for (let lon = -180; lon < 180; lon += 30) { const pts = []; for (let lat = -80; lat <= 80; lat += 4) pts.push(vec(lon, lat)); line(pts); }
    for (let lat = -60; lat <= 60; lat += 30) { const pts = []; for (let lon = -180; lon <= 180; lon += 4) pts.push(vec(lon, lat)); line(pts); }
  }
  function drawLand(now) {
    const buckets = Array.from({ length: 6 }, () => new Path2D()), size = 1.25 * DPR;
    const sweep = reduced.matches ? 2 : intro * 1.35;
    for (const dot of land) {
      const q = turn(dot);
      if (q[2] <= 0) continue;
      const reveal = clamp((sweep - (1 - q[2]) * .9 - dot[3] * .25) * 4, 0, 1); // entrance: from the facing point outward
      if (reveal <= 0) continue;
      const level = Math.min(5, Math.floor(q[2] * reveal * 6));
      const s = size * (.55 + .55 * q[2]);
      const [x, y] = screen(q);
      buckets[level].rect(x - s / 2, y - s / 2, s, s);
    }
    buckets.forEach((path, level) => { ctx.fillStyle = `rgba(214, 228, 242, ${(.16 + level * .13).toFixed(3)})`; ctx.fill(path); });
  }
  function drawArc(event, index, now) {
    const pts = event.arc.map(turn), born = clamp((arcClock(now) * 1.7 - .45 - index * stagger()) / .55, 0, 1);
    if (born <= 0) return;
    const upto = Math.max(1, Math.floor(born * (pts.length - 1)));
    const emphasis = event.id === selected || event.id === hovered;
    ctx.lineCap = "round";
    ctx.lineWidth = (emphasis ? 1.6 : 1) * DPR;
    const alpha = emphasis ? .8 : .36;
    for (let i = 1; i <= upto; i += 1) { // per segment, so depth can fade it
      if (!visibleLifted(pts[i]) || !visibleLifted(pts[i - 1])) continue;
      const fade = depth(Math.min(pts[i][2], pts[i - 1][2]));
      if (fade <= .01) continue;
      const [x0, y0] = screen(pts[i - 1]), [x1, y1] = screen(pts[i]);
      ctx.strokeStyle = emphasis ? `rgba(255, 128, 112, ${(alpha * fade).toFixed(3)})` : `rgba(222, 92, 78, ${(alpha * fade).toFixed(3)})`;
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    }
    if (reduced.matches || born < 1) return;
    // A light travels from Antalya to the event: a short comet with a bright head.
    const period = 2600, head = ((now / period + event.phase) % 1) * 1.25, tail = .22;
    for (let i = 1; i < pts.length; i += 1) {
      const t = i / (pts.length - 1), k = 1 - (head - t) / tail;
      if (t > head || k <= 0 || !visibleLifted(pts[i]) || !visibleLifted(pts[i - 1])) continue;
      const [x0, y0] = screen(pts[i - 1]), [x1, y1] = screen(pts[i]);
      ctx.strokeStyle = `rgba(255, ${Math.round(150 + 100 * k)}, ${Math.round(140 + 110 * k)}, ${(k * .95 * depth(Math.min(pts[i][2], pts[i - 1][2]))).toFixed(3)})`;
      ctx.lineWidth = (1 + 1.6 * k) * DPR;
      ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke();
    }
  }
  function drawMarker(event, index, now) {
    const q = turn(event.v);
    if (q[2] <= .02) return;
    const pop = reduced.matches ? 1 : clamp((arcClock(now) * 1.7 - .75 - index * stagger()) / .35, 0, 1);
    if (pop <= 0) return;
    const scale = easeOutBack(pop) * (.6 + .4 * q[2]), [x, y] = screen(q), on = event.id === selected, hot = event.id === hovered || event.id === focused;
    if (!reduced.matches) { // pulse ring
      const phase = ((now / 2400) + event.phase) % 1;
      ctx.strokeStyle = `rgba(255, 110, 96, ${((1 - phase) * .55 * q[2]).toFixed(3)})`;
      ctx.lineWidth = DPR;
      ctx.beginPath(); ctx.arc(x, y, (4 + 16 * phase) * DPR * scale, 0, Math.PI * 2); ctx.stroke();
    }
    const glow = ctx.createRadialGradient(x, y, 0, x, y, 12 * DPR * scale);
    glow.addColorStop(0, "rgba(255, 96, 80, .55)");
    glow.addColorStop(1, "rgba(255, 96, 80, 0)");
    ctx.fillStyle = glow;
    ctx.beginPath(); ctx.arc(x, y, 12 * DPR * scale, 0, Math.PI * 2); ctx.fill();
    if (on || hot) { // beacon: a short line along the surface normal, ringed dot on top
      const tip = screen(turn(event.v.map(c => c * 1.13)));
      ctx.strokeStyle = "rgba(255, 255, 255, .7)";
      ctx.lineWidth = DPR;
      ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(tip[0], tip[1]); ctx.stroke();
      ctx.fillStyle = "#ffffff";
      ctx.beginPath(); ctx.arc(tip[0], tip[1], 2.2 * DPR, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = "rgba(255, 255, 255, .9)";
      ctx.beginPath(); ctx.arc(x, y, 7.5 * DPR * scale, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.fillStyle = on ? "#ff5a48" : "#e2463a";
    ctx.beginPath(); ctx.arc(x, y, (on ? 4.2 : 3) * DPR * scale, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = "rgba(255, 255, 255, .85)";
    ctx.lineWidth = .8 * DPR;
    ctx.stroke();
    event.screen = [x / DPR, y / DPR];
  }
  function drawHub(now) {
    const q = turn(hubVec);
    if (q[2] <= 0) return;
    const [x, y] = screen(q), a = reduced.matches ? 0 : now / 3200 * Math.PI * 2;
    ctx.strokeStyle = "rgba(255, 255, 255, .55)";
    ctx.lineWidth = DPR;
    ctx.setLineDash([3 * DPR, 4 * DPR]);
    ctx.beginPath(); ctx.arc(x, y, 11 * DPR, a, a + Math.PI * 2); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#ffffff";
    ctx.beginPath(); ctx.arc(x, y, 3.4 * DPR, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "rgba(255, 255, 255, .62)";
    ctx.font = `${10 * DPR}px ${getComputedStyle(host).getPropertyValue("--font-mono") || "monospace"}`;
    ctx.fillText("ANTALYA · COP31", x + 15 * DPR, y - 13 * DPR);
  }
  function draw(now = performance.now()) {
    if (!rot || !W) return;
    ctx.clearRect(0, 0, W, H);
    drawPlate();
    drawSphere();
    drawGraticule();
    drawLand(now);
    events.forEach((event, index) => { event.screen = null; drawArc(event, index, now); });
    drawHub(now);
    events.forEach((event, index) => drawMarker(event, index, now));
  }
  function frame(now) {
    const dt = Math.min(.05, (now - last) / 1000);
    last = now;
    if (!reduced.matches) {
      if (introStart && intro < 1) intro = clamp((now - introStart) / 2200, 0, 1);
      if (!drag && !aiming && now > idleSince) {
        view.lon += inertia.lon * dt;
        view.lat = clamp(view.lat + inertia.lat * dt, -60, 60);
        inertia.lon *= Math.pow(.05, dt); inertia.lat *= Math.pow(.05, dt);
        if (Math.abs(inertia.lon) < SPIN) view.lon -= SPIN * dt * (1 - Math.abs(inertia.lon) / SPIN);
      }
    }
    updateRotation();
    draw(now);
    if (onScreen && !document.hidden && !reduced.matches) requestAnimationFrame(frame); else running = false;
  }
  function wake() {
    if (reduced.matches) { updateRotation(); draw(); return; }
    if (!running && onScreen && !document.hidden) { running = true; last = performance.now(); requestAnimationFrame(frame); }
  }

  // ---------- Size ----------
  function resize() {
    const box = host.getBoundingClientRect();
    DPR = Math.min(2, window.devicePixelRatio || 1);
    W = Math.round(box.width * DPR); H = Math.round(box.height * DPR);
    canvas.width = W; canvas.height = H;
    R = Math.min(W * .44, H * .43);
    CX = W * .5; CY = H * .53;
    updateRotation();
    draw();
  }

  // ---------- Input ----------
  const local = event => { const box = canvas.getBoundingClientRect(); return [event.clientX - box.left, event.clientY - box.top]; };
  function hit(px, py) {
    let best = null, bestD = 14;
    for (const event of events) {
      if (!event.screen) continue;
      const d = Math.hypot(event.screen[0] - px, event.screen[1] - py);
      if (d < bestD) { best = event; bestD = d; }
    }
    return best;
  }
  function setHover(event, pointer) {
    const id = event?.id ?? null;
    if (id === hovered) return;
    if (hovered) pinFor(hovered)?.dispatchEvent(new MouseEvent("mouseleave"));
    hovered = id;
    canvas.style.cursor = id ? "pointer" : drag ? "grabbing" : "grab";
    if (id) pinFor(id)?.dispatchEvent(new MouseEvent("mouseenter", { clientX: pointer.clientX, clientY: pointer.clientY }));
    draw();
  }
  canvas.addEventListener("pointerdown", event => {
    if (event.button !== 0) return;
    canvas.setPointerCapture(event.pointerId);
    aim?.stop();
    const [x, y] = local(event);
    drag = { x, y, x0: x, y0: y, lon: view.lon, lat: view.lat, t: performance.now(), moved: false };
    inertia = { lon: 0, lat: 0 };
    canvas.style.cursor = "grabbing";
    wake();
  });
  canvas.addEventListener("pointermove", event => {
    const [x, y] = local(event);
    if (!drag) { setHover(hit(x, y), event); return; }
    const k = 180 / (Math.PI * R / DPR), now = performance.now(), dt = Math.max(1, now - drag.t) / 1000;
    if (Math.hypot(x - drag.x0, y - drag.y0) > 4) drag.moved = true;
    const lon = drag.lon - (x - drag.x0) * k, lat = clamp(drag.lat + (y - drag.y0) * k, -60, 60);
    inertia = { lon: (lon - view.lon) / dt, lat: (lat - view.lat) / dt };
    view.lon = lon; view.lat = lat;
    drag.t = now;
    if (reduced.matches) { updateRotation(); draw(); }
  });
  const endDrag = event => {
    if (!drag) return;
    const moved = drag.moved;
    drag = null;
    canvas.style.cursor = hovered ? "pointer" : "grab";
    idleSince = performance.now() + (moved ? 1800 : 0);
    if (!moved) {
      inertia = { lon: 0, lat: 0 };
      const [x, y] = local(event), picked = hit(x, y);
      if (picked) { pinFor(picked.id)?.dispatchEvent(new MouseEvent("click", { bubbles: true })); select(picked.id); }
    }
  };
  canvas.addEventListener("pointerup", endDrag);
  canvas.addEventListener("pointercancel", () => { drag = null; });
  canvas.addEventListener("pointerleave", () => { if (!drag) setHover(null, {}); });
  // Picking from the place list, hovering it, or tabbing through app.js's pins turns the globe as well.
  const places = document.getElementById("mapPlaceList");
  places?.addEventListener("click", event => { const button = event.target.closest("[data-map-id]"); if (button) select(button.dataset.mapId); });
  places?.addEventListener("pointerover", event => { const button = event.target.closest("[data-map-id]"); hovered = button?.dataset.mapId ?? null; draw(); });
  places?.addEventListener("pointerleave", () => { hovered = null; draw(); });
  svg.addEventListener("focusin", event => { const pin = event.target.closest(".event-pin"); if (pin) { focused = pin.dataset.marker; select(focused); } });
  svg.addEventListener("focusout", () => { focused = null; draw(); });
  svg.addEventListener("click", event => { const pin = event.target.closest(".event-pin"); if (pin && event.isTrusted) select(pin.dataset.marker); });

  // ---------- Start ----------
  async function start() {
    try {
      const [topo, dashboard] = await Promise.all([
        fetch(new URL("./assets/countries-110m.json", document.baseURI)).then(response => response.json()),
        fetch(new URL("./data/dashboard.json", document.baseURI)).then(response => response.json()),
      ]);
      land = sampleLand(decode(topo));
      byId = new Map([...(dashboard.map_events || []), ...(dashboard.map_events_week || []), ...(dashboard.map_events_today || [])].map(item => [item.marker_id, item]));
    } catch (error) {
      console.error("globe: data unavailable", error);
      host.classList.remove("has-globe");
      canvas.remove();
      return;
    }
    // app.js redraws its pins on load and on every period switch: follow them.
    const sync = () => setEvents([...svg.querySelectorAll(".event-pin[data-marker]")].map(pin => pin.dataset.marker));
    new MutationObserver(sync).observe(svg, { childList: true });
    sync();
    new ResizeObserver(resize).observe(host);
    resize();
    new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting;
      if (onScreen && !introStart) { introStart = performance.now(); view.lon = 70; }
      wake();
    }, { threshold: .08 }).observe(host);
    document.addEventListener("visibilitychange", wake);
    reduced.addEventListener?.("change", () => { intro = 1; wake(); });
    if (reduced.matches) intro = 1;
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
