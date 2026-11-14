/* GREEN · COP31 — photographs behind the home stamp stage (2026-11-02).
   Real landscapes of the low-carbon transition and the COP31 host (Antalya's gulf and coast, offshore wind, a glacier
   lagoon, solar, forest), one after another. WebGL dissolves each into the next like ink spreading through wet paper:
   a front from a random point broken up by fbm noise, a faint grey-blue tide line on its edge, the incoming photo
   coming into focus while the outgoing one softens and is pushed aside. Between changes each photo settles slowly
   (1.08 → 1.035) and leans a little toward the pointer. It only runs while the stage is on screen.
   Without WebGL, or with reduced motion, plain cross-fades (CSS, cop31.css .hp-img). Decorative: no text. */
(() => {
  "use strict";
  const layer = document.querySelector(".home-photos");
  const stage = layer?.closest(".cop31-intro");
  if (!layer || !stage) return;
  const root = document.documentElement;
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = matchMedia("(hover: hover) and (pointer: fine)");
  const NAMES = ["antalya-gulf", "offshore-wind", "glacier", "solar", "forest", "antalya-coast"]; // assets/home, sources in docs/CHANGES.md
  const HOLD = 7000, FADE = 3600; // ms a photo stays · ms a change takes
  const large = Math.max(innerWidth, innerHeight) * Math.min(devicePixelRatio || 1, 2) > 1700;
  const url = name => `./assets/home/${name}-${large ? 2400 : 1280}.jpg`;
  // The downloaded files are kept; each showing decodes a fresh copy, because a decoded bitmap is closed once it is on
  // the GPU — reusing a closed one uploads an empty texture (width 0), which drew black on the second round (2026-11-02).
  const files = [];
  const load = i => {
    files[i] ||= fetch(url(NAMES[i])).then(response => {
      if (!response.ok) throw new Error(response.status);
      return response.blob();
    });
    files[i].catch(() => { files[i] = null; }); // a failed download is tried again next round
    return files[i].then(blob => ("createImageBitmap" in window ? createImageBitmap(blob) : new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(img.src); resolve(img); };
      img.onerror = reject;
      img.src = URL.createObjectURL(blob);
    }))).then(image => {
      if (!image.width || !image.height) throw new Error("empty image");
      return image;
    });
  };
  const ease = t => .5 - Math.cos(Math.PI * t) / 2; // the front keeps moving; a cubic rushes the middle

  // Without the sheet (phones, reduced motion) the layer bleeds from the stage to the top and both edges of the page.
  function place() {
    const box = stage.getBoundingClientRect();
    layer.style.setProperty("--hp-top", `${(box.top + scrollY).toFixed(1)}px`);
    layer.style.setProperty("--hp-left", `${box.left.toFixed(1)}px`);
    layer.style.setProperty("--hp-width", `${root.clientWidth}px`);
  }
  place();
  addEventListener("resize", place);
  if ("ResizeObserver" in window) new ResizeObserver(place).observe(stage);

  let wake = () => {};
  // On screen = home page, tab visible, and either the sheet is down (desktop) or the stage is in view (phones).
  let inView = true;
  if ("IntersectionObserver" in window) new IntersectionObserver(entries => { inView = entries[entries.length - 1].isIntersecting; wake(); }).observe(stage);
  const onScreen = () => document.visibilityState === "visible" && (root.dataset.page || "home") === "home" &&
    (root.classList.contains("has-sheet") ? !root.dataset.sheet || root.dataset.sheet === "closed" : inView);

  const gl = reducedMotion.matches ? null : glStage();
  const stageApi = gl || cssStage();
  wake = stageApi.wake;
  stageApi.start();
  new MutationObserver(() => wake()).observe(root, { attributes: true, attributeFilter: ["data-page", "data-sheet", "class"] });
  document.addEventListener("visibilitychange", () => wake());

  /* ---------- Cross-fades without WebGL ---------- */
  function cssStage() {
    const slides = NAMES.map(() => layer.appendChild(Object.assign(document.createElement("div"), { className: "hp-img" })));
    let index = -1, timer = 0, misses = 0;
    async function show(i) {
      try {
        const image = await load(i);
        if (!slides[i].style.backgroundImage) slides[i].style.backgroundImage = `url("${url(NAMES[i])}")`;
        image.close?.();
      } catch { if (++misses < NAMES.length) next(i); return; } // a missing photo is skipped
      slides.forEach((slide, k) => slide.classList.toggle("is-on", k === i));
      index = i;
      schedule();
    }
    const next = from => setTimeout(() => show((from + 1) % NAMES.length), 0);
    function schedule() {
      clearTimeout(timer);
      timer = setTimeout(() => (onScreen() ? show((index + 1) % NAMES.length) : (timer = 0)), HOLD + FADE);
    }
    return { start: () => show(0), wake: () => { if (!timer && index >= 0 && onScreen()) schedule(); } };
  }

  /* ---------- WebGL ink dissolve ---------- */
  function glStage() {
    const canvas = layer.appendChild(document.createElement("canvas"));
    const gl = canvas.getContext("webgl", { alpha: false, antialias: false, depth: false, stencil: false, powerPreference: "low-power" });
    if (!gl) { canvas.remove(); return null; }
    const VERT = "attribute vec2 p;varying vec2 vUv;void main(){vUv=p*.5+.5;gl_Position=vec4(p,0.,1.);}";
    const FRAG = `
precision highp float;
varying vec2 vUv;
uniform sampler2D uA, uB;
uniform vec2 uRes, uSizeA, uSizeB, uOrigin, uPar;
uniform vec3 uCamA, uCamB; // scale, pan x, pan y
uniform float uP, uSeed;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  f = f * f * (3. - 2. * f);
  return mix(mix(hash(i), hash(i + vec2(1., 0.)), f.x), mix(hash(i + vec2(0., 1.)), hash(i + 1.), f.x), f.y);
}
float fbm(vec2 p) {
  float v = 0., a = .5;
  for (int i = 0; i < 5; i++) { v += a * noise(p); p = p * 2.03 + 17.1; a *= .5; }
  return v;
}
vec2 cover(vec2 uv, vec2 size, vec3 cam) { // object-fit: cover, then the photo's own settle and pan, then parallax
  float ra = uRes.x / uRes.y, ri = size.x / size.y;
  vec2 s = ra > ri ? vec2(1., ri / ra) : vec2(ra / ri, 1.);
  uv = (uv - .5) * s / cam.x + .5 + cam.yz + uPar;
  return vec2(uv.x, 1. - uv.y); // images arrive top row first
}
vec3 grade(vec3 c) { // a touch cooler and calmer, toward the page's grey-blue
  float l = dot(c, vec3(.2126, .7152, .0722));
  c = mix(vec3(l), c, .84);
  return mix(c, c * vec3(.95, .985, 1.035), .7);
}
vec3 soft(sampler2D t, vec2 uv, float r) { // 1 + 8 taps on a golden-angle spiral, r in uv units
  vec3 c = texture2D(t, uv).rgb;
  if (r < .0004) return c;
  for (int i = 1; i < 9; i++) {
    float k = float(i), a = k * 2.39996;
    c += texture2D(t, uv + vec2(cos(a), sin(a)) * r * sqrt(k / 8.) * vec2(uRes.y / uRes.x, 1.)).rgb;
  }
  return c / 9.;
}
void main() {
  vec2 uv = vUv;
  if (uP <= 0.) { gl_FragColor = vec4(grade(texture2D(uA, cover(uv, uSizeA, uCamA)).rgb), 1.); return; }
  vec2 asp = vec2(uRes.x / uRes.y, 1.);
  float n = fbm(uv * asp * 2.4 + uSeed);
  float r = length((uv - uOrigin) * asp) / length(asp);
  float field = r * .78 + n * .5;            // where the ink arrives early (low) or late (high)
  float w = .22, t = uP * (1.32 + w) - w;
  float m = 1. - smoothstep(t, t + w, field);   // 1 = the new photo
  float edge = m * (1. - m) * 4.;
  vec2 dir = normalize((uv - uOrigin) * asp + 1e-4) / asp;
  vec2 push = dir * edge * .022 + (vec2(n, fbm(uv * 3.1 - uSeed)) - .5) * edge * .03;
  vec3 a = soft(uA, cover(uv + push, uSizeA, uCamA), (uP * .004 + edge * .004));
  vec3 b = soft(uB, cover(uv - push * .6, uSizeB, uCamB), ((1. - uP) * (1. - uP) * .012 + edge * .005));
  vec3 c = mix(a, b, m);
  float tide = smoothstep(.18, .5, m) * smoothstep(.82, .5, m); // pigment gathers on the drying edge
  c = mix(c, vec3(.184, .255, .337), tide * .14);
  c += edge * edge * .035;
  gl_FragColor = vec4(grade(c), 1.);
}`;
    const shader = (type, source) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, source);
      gl.compileShader(s);
      return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
    };
    const vs = shader(gl.VERTEX_SHADER, VERT), fs = shader(gl.FRAGMENT_SHADER, FRAG);
    const program = gl.createProgram();
    if (vs && fs) { gl.attachShader(program, vs); gl.attachShader(program, fs); gl.linkProgram(program); }
    if (!vs || !fs || !gl.getProgramParameter(program, gl.LINK_STATUS)) { canvas.remove(); return null; }
    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const at = gl.getAttribLocation(program, "p");
    gl.enableVertexAttribArray(at);
    gl.vertexAttribPointer(at, 2, gl.FLOAT, false, 0, 0);
    const u = {};
    ["uA", "uB", "uRes", "uSizeA", "uSizeB", "uOrigin", "uPar", "uCamA", "uCamB", "uP", "uSeed"].forEach(name => { u[name] = gl.getUniformLocation(program, name); });
    gl.uniform1i(u.uA, 0);
    gl.uniform1i(u.uB, 1);

    const texture = source => {
      const t = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, t);
      [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]
        .forEach(([key, value]) => gl.texParameteri(gl.TEXTURE_2D, key, value));
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, source);
      return t;
    };
    // The first photo comes in over the bare paper, the same way the others follow each other.
    const paperCanvas = Object.assign(document.createElement("canvas"), { width: 1, height: 1 });
    const pc = paperCanvas.getContext("2d");
    pc.fillStyle = getComputedStyle(root).getPropertyValue("--surface-page").trim() || "#e9eef3";
    pc.fillRect(0, 0, 1, 1);
    const photo = (tex, w, h) => ({ tex, w, h, born: 0, pan: [Math.random() - .5, Math.random() - .5] });
    let cur = photo(texture(paperCanvas), 1, 1), nxt = null, index = -1, pending = 0, misses = 0;
    let clock = 0, last = 0, raf = 0, phase = "wait", since = 0, seed = 0, origin = [.5, .5];
    const par = [0, 0], parTo = [0, 0];

    function size() {
      const dpr = Math.min(devicePixelRatio || 1, 2), w = canvas.clientWidth, h = canvas.clientHeight;
      const k = Math.min(dpr, Math.sqrt(4.2e6 / Math.max(1, w * h))); // at most ~4 megapixels
      const W = Math.max(1, Math.round(w * k)), H = Math.max(1, Math.round(h * k));
      if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; gl.viewport(0, 0, W, H); return true; }
      return false;
    }
    async function prepare(i) { // decode off the main thread, upload during a hold, never mid-change
      pending = i + 1;
      try {
        const image = await load(i);
        if (gl.isContextLost()) return;
        nxt = photo(texture(image), image.width, image.height);
        image.close?.();
        index = i;
        wake();
        misses = 0;
      } catch { // skip a photo that will not load; after a full round of misses, wait for the next one
        pending = 0;
        if (++misses < NAMES.length) prepare((i + 1) % NAMES.length);
        else setTimeout(() => { misses = 0; if (!pending && !nxt) prepare((i + 1) % NAMES.length); }, HOLD);
        return;
      }
      pending = 0; // the next photo is fetched during this one's hold, so the page loads one at a time
    }
    const camera = (p, now) => {
      const life = Math.min(1, (now - p.born) / (HOLD + 2 * FADE));
      const settle = 1 - (1 - life) * (1 - life);
      return [1.08 - .045 * settle, p.pan[0] * .016 * (settle - .5), p.pan[1] * .012 * (settle - .5)];
    };
    function draw() {
      const p = phase === "fade" ? ease(Math.min(1, (clock - since) / FADE)) : 0;
      gl.uniform2f(u.uRes, canvas.width, canvas.height);
      gl.uniform2f(u.uPar, par[0], par[1]);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, cur.tex);
      gl.uniform2f(u.uSizeA, cur.w, cur.h);
      gl.uniform3fv(u.uCamA, camera(cur, clock));
      if (phase === "fade") {
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, nxt.tex);
        gl.uniform2f(u.uSizeB, nxt.w, nxt.h);
        gl.uniform3fv(u.uCamB, camera(nxt, clock));
        gl.uniform2f(u.uOrigin, origin[0], origin[1]);
        gl.uniform1f(u.uSeed, seed);
      }
      gl.uniform1f(u.uP, p);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
    function frame(now) {
      raf = 0;
      if (!onScreen() || gl.isContextLost()) { last = 0; return; } // the clock stops with the stage: nothing is missed
      clock += last ? Math.min(64, now - last) : 16;
      last = now;
      par[0] += (parTo[0] - par[0]) * .05;
      par[1] += (parTo[1] - par[1]) * .05;
      if (phase === "wait" && nxt) begin();
      else if (phase === "hold" && clock - since >= HOLD && nxt) begin();
      else if (phase === "fade" && clock - since >= FADE) {
        gl.deleteTexture(cur.tex);
        cur = nxt; nxt = null; phase = "hold"; since = clock;
        if (!pending) prepare((index + 1) % NAMES.length);
      }
      draw();
      raf = requestAnimationFrame(frame);
    }
    function begin() {
      phase = "fade"; since = clock; nxt.born = clock;
      seed = Math.random() * 50;
      origin = [.2 + Math.random() * .6, .2 + Math.random() * .6];
    }
    const wakeUp = () => { if (!raf && onScreen()) raf = requestAnimationFrame(frame); };
    if (finePointer.matches) addEventListener("pointermove", event => {
      parTo[0] = (event.clientX / innerWidth - .5) * -.008;
      parTo[1] = (event.clientY / innerHeight - .5) * .006;
      wakeUp();
    }, { passive: true });
    const resized = () => { if (size() && raf >= 0) draw(); }; // a resize clears the canvas: repaint at once, even while paused
    if ("ResizeObserver" in window) new ResizeObserver(resized).observe(canvas);
    else addEventListener("resize", resized);
    canvas.addEventListener("webglcontextlost", () => { // carry on with cross-fades
      cancelAnimationFrame(raf);
      raf = -1;
      canvas.remove();
      const css = cssStage();
      wake = css.wake;
      css.start();
    });
    return {
      start: () => { size(); draw(); prepare(0); wakeUp(); },
      wake: wakeUp,
    };
  }
})();
