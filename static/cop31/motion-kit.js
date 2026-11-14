/* GREEN · COP31 — small motion kit (springs, FLIP, text scramble, pointer helpers).
   Parameters follow the reference spring/entrance study (measured from the reference site).
   Exposed as window.GreenMotion; used by cop31.js. */
(() => {
  "use strict";
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");

  // stiffness / damping / mass
  const SPRING = {
    settle: { k: 180, c: 22, m: 1 },   // flights, snap-backs (≈1 % overshoot)
    throw: { k: 190, c: 24, m: 1 },    // tosses, closes
    reel: { k: 320, c: 38, m: .7 },    // over-damped glide for reels
    width: { k: 260, c: 34, m: .8 },   // capsule width
    press: { k: 520, c: 34, m: .5 },   // press swell
    release: { k: 340, c: 36, m: .6 },
  };
  // Motion's duration → spring conversion: k = (2π / 1.2d)², c = 2(1 − bounce)√k
  const springFor = (seconds, bounce = 0) => { const k = (2 * Math.PI / (1.2 * seconds)) ** 2; return { k, c: 2 * (1 - bounce) * Math.sqrt(k), m: 1 }; };

  // Integrates one value with semi-implicit Euler (sub-steps of 1/240 s). Returns a handle with stop().
  function spring(from, to, { k, c, m = 1 }, { velocity = 0, restDelta = .5, restSpeed = 10, onUpdate, onDone } = {}) {
    if (reduced.matches) { onUpdate?.(to); onDone?.(); return { stop() {}, value: to, velocity: 0, finished: Promise.resolve() }; }
    let x = from, v = velocity, last = performance.now(), raf = 0, resolve;
    const finished = new Promise(done => { resolve = done; });
    const tick = now => {
      let dt = Math.min(.064, (now - last) / 1000);
      last = now;
      while (dt > 0) { const h = Math.min(1 / 240, dt); v += ((-k * (x - to) - c * v) / m) * h; x += v * h; dt -= h; }
      if (Math.abs(x - to) < restDelta && Math.abs(v) < restSpeed) { onUpdate?.(to); onDone?.(); resolve(); return; }
      onUpdate?.(x);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return { stop() { cancelAnimationFrame(raf); resolve(); }, get value() { return x; }, get velocity() { return v; }, finished };
  }
  // Progress 0 → 1 on a spring (for multi-property interpolation).
  const progress = (preset, onUpdate, options = {}) => spring(0, 1, preset, { restDelta: .001, restSpeed: .01, onUpdate, ...options });

  const lerp = (a, b, t) => a + (b - a) * t;
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  // Past an edge the overflow approaches a ceiling of C px.
  const resistEdge = (x, min, max, R = 70, C = 16) =>
    x > max ? max + (x - max) / ((x - max) + R) * C : x < min ? min - (min - x) / ((min - x) + R) * C : x;
  function sampler() { // velocity from the last 3 pointer deltas younger than 150 ms
    const samples = [];
    return {
      push(dx, dy, dt, t) { samples.push({ dx, dy, dt, t }); if (samples.length > 3) samples.shift(); },
      velocity(now = performance.now()) {
        let dt = 0, dx = 0, dy = 0;
        for (const sample of samples) if (now - sample.t <= 150) { dt += sample.dt; dx += sample.dx; dy += sample.dy; }
        return { vx: dt ? dx / dt * 1000 : 0, vy: dt ? dy / dt * 1000 : 0 };
      },
    };
  }

  // Random-glyph text scramble (340 ms, easeInOut, per-character thresholds, re-roll p = .5625).
  const GLYPHS = [..."♩♪♫♬★☆♠♣♥♦✦✧▲△▷►▼▽◁◄◊◌←↑→↓↕↖↗↘↙░▒▓▀▄∆∑∏√∞≈ABCDEFGHIJKLMNOPQRSTUVWXYZÉ"];
  function scramble(element, from, to, ms = 340, force = false) { // force: animate even when the text is unchanged
    if (reduced.matches || (from === to && !force)) { element.textContent = to; return Promise.resolve(); }
    const n = Math.max(from.length, to.length);
    const roll = () => GLYPHS[Math.random() * GLYPHS.length | 0];
    const noise = Array.from({ length: n }, roll);
    const thresholds = [...to].map((_, index) => Math.min(.999, index / to.length * .7 + .3 * Math.random()));
    const ease = t => t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
    const start = performance.now();
    return new Promise(done => {
      const frame = now => {
        const p = ease(Math.min(1, (now - start) / ms));
        for (let index = 0; index < n; index += 1) if (Math.random() < .5625) noise[index] = roll();
        const length = Math.round(from.length + (to.length - from.length) * p);
        let out = "";
        for (let index = 0; index < length; index += 1) {
          const char = to[index] ?? "";
          out += char === " " || (char && p >= thresholds[index]) ? char : noise[index];
        }
        element.textContent = p < 1 ? out : to;
        if (p < 1) requestAnimationFrame(frame); else done();
      };
      requestAnimationFrame(frame);
    });
  }

  // FLIP: measure → (caller re-renders) → play. Surviving keys glide on SETTLE with a 50 ms stagger;
  // new keys fade + rise 12 px over 400 ms with a ≤300 ms total stagger.
  function measure(elements, keyOf) {
    const rects = new Map();
    elements.forEach(element => { const key = keyOf(element); if (key && !rects.has(key)) rects.set(key, element.getBoundingClientRect()); });
    return rects;
  }
  function play(before, elements, keyOf) {
    if (reduced.matches) return;
    const fresh = [];
    let moved = 0;
    elements.forEach(element => {
      const old = before.get(keyOf(element));
      if (!old) { fresh.push(element); return; }
      const now = element.getBoundingClientRect();
      const dx = old.left - now.left, dy = old.top - now.top;
      if (Math.abs(dx) < .5 && Math.abs(dy) < .5) return;
      element.style.transform = `translate(${dx}px, ${dy}px)`;
      const delay = Math.min(moved++, 8) * 50;
      setTimeout(() => progress(SPRING.settle, p => {
        element.style.transform = p >= 1 ? "" : `translate(${dx * (1 - p)}px, ${dy * (1 - p)}px)`;
      }), delay);
    });
    const step = fresh.length > 1 ? Math.min(50, 300 / (fresh.length - 1)) : 0;
    fresh.forEach((element, index) => element.animate(
      [{ opacity: 0, transform: "translateY(12px)" }, { opacity: 1, transform: "none" }],
      { duration: 400, delay: index * step, easing: "cubic-bezier(.2, .6, .2, 1)", fill: "backwards" },
    ));
  }

  window.GreenMotion = { SPRING, springFor, spring, progress, lerp, clamp, resistEdge, sampler, scramble, flip: { measure, play }, reduced };
})();
