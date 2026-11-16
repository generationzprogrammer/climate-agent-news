/* GREEN · COP31 — the satellite Earth shared by the two globes (2026-11-04, user: "两个地球都改为类似于卫星图片那种有颜色的地球").
   window.GreenEarth.create(kind) returns a renderer, or null without WebGL: globe.js and countries.js then keep their
   old drawing. Each renderer owns a WebGL canvas the size of the globe's disc; the caller passes its camera and calls
   draw(), then copies that canvas into its own 2D canvas in the same frame (ctx.drawImage), so markers, arcs and stars
   stay where they were drawn before. The fragment shader inverts the caller's projection per pixel — "ortho" for the
   全球气候现场 globe (globe.js), "perspective" for the near-side view of 国家专题 (countries.js) — and samples an
   equirectangular satellite image: NASA Blue Marble (land surface, shallow water and shaded topography; NASA Goddard
   Space Flight Center / Visible Earth, public domain), assets/earth/blue-marble-4096|2048.jpg. The flat ocean of the
   source is regraded into lit deep water with a soft glint; the limb takes a thin atmosphere. "reveal" fades the
   picture in from the facing point outward in dot-sized cells (the entrance the dot-matrix globe had).
   Loading (2026-11-04, the globes stayed old on a slow line while 0.8 MB arrived): a 512 px copy is inlined below and
   shown at once; the 2048 px picture (0.24 MB, high fetch priority) is requested as soon as this file runs and replaces
   it; where the sharper 4096 px one is worth it, it follows once a globe is first drawn on screen (2026-11-07: not with
   the page, which does not show a globe at first). A sharper picture is never replaced by a softer one.   2026-11-10: 全球事件地图 is now the 融观 globe (cop31/atlas, three.js); this renderer serves 国家专题 (countries.js) only. */
(() => {
  "use strict";
  const base = new URL("./cop31/assets/earth/", document.baseURI);
  const TINY = "data:image/jpeg;base64,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";
  const fetchImage = (width, priority) => {
    const done = new Promise((resolve, reject) => {
      const img = new Image();
      img.decoding = "async";
      img.fetchPriority = priority;
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = width === 512 ? TINY : new URL(`blue-marble-${width}.jpg`, base).href;
    });
    done.catch(() => {});
    return done;
  };
  let images = null; // one download per size for both globes: [inlined, quick, () => sharp or null]
  function loadImages() {
    if (images) return images;
    const tiny = fetchImage(512, "high"), quick = fetchImage(2048, "high");
    const probe = document.createElement("canvas").getContext("webgl2");
    const worth = !!probe && probe.getParameter(probe.MAX_TEXTURE_SIZE) >= 4096 && (devicePixelRatio > 1 || innerWidth > 1100);
    // the sharp one (0.8 MB) is asked for when a globe is first drawn on screen, and only once the page has loaded and
    // the browser is idle — not beside the page's own data (2026-11-07)
    let sharp = null;
    const settled = new Promise(resolve => {
      const idle = () => (window.requestIdleCallback ?? (callback => setTimeout(callback, 1200)))(resolve, { timeout: 3000 });
      document.readyState === "complete" ? idle() : addEventListener("load", idle, { once: true });
    });
    const later = () => {
      if (worth && !sharp) {
        const next = () => settled.then(() => fetchImage(4096, "low"));
        sharp = quick.then(next, next); // after the quick one, not beside it
        sharp.catch(() => {});
      }
      return sharp;
    };
    return (images = [tiny, quick, later]);
  }
  if (window.WebGLRenderingContext) loadImages();

  const VERT = `
    attribute vec2 aPos;
    void main() { gl_Position = vec4(aPos, 0.0, 1.0); }`;
  // GLSL shared by both versions; SAMPLE() is the texture lookup (seam-safe gradients where WebGL 2 allows them).
  const BODY = `
    uniform vec2 uSize;      // canvas size, px
    uniform float uR;        // disc radius on screen, px
    uniform float uS;        // perspective: sphere scale S (px); ortho: unused
    uniform float uP;        // perspective: viewer distance in sphere radii; ortho: 0
    uniform vec4 uRot;       // cos/sin of view lon, cos/sin of view lat
    uniform float uReveal;   // entrance sweep (>= 2: fully shown)
    uniform vec3 uBase;      // the sphere's colour before the picture arrives
    uniform float uAtmo;     // limb atmosphere strength
    const float PI = 3.14159265;
    float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    vec4 shade() {
      vec2 d = gl_FragCoord.xy - uSize * 0.5;
      float r = length(d);
      float edge = clamp(uR - r + 0.5, 0.0, 1.0);
      if (edge <= 0.0) return vec4(0.0);
      vec3 q;
      if (uP > 0.0) { // near-side perspective: X = S·x·(P−1)/(P−z), from the eye at (0, 0, P)
        vec2 ab = d / uS / (uP - 1.0);
        float a2 = dot(ab, ab);
        float disc = max(0.0, uP * uP - (a2 + 1.0) * (uP * uP - 1.0));
        float t = (uP - sqrt(disc)) / (a2 + 1.0);
        q = vec3(ab * t, uP - t);
      } else {
        vec2 xy = d / uR;
        q = vec3(xy, sqrt(max(0.0, 1.0 - dot(xy, xy))));
      }
      q = normalize(q);
      // undo turn(): pitch by −lat, then yaw by +lon (x east, y north, z through lon 0 / lat 0)
      float y = q.y * uRot.z + q.z * uRot.w;
      float z1 = -q.y * uRot.w + q.z * uRot.z;
      vec3 w = vec3(q.x * uRot.x + z1 * uRot.y, y, z1 * uRot.x - q.x * uRot.y);
      float lon = atan(w.x, w.z), lat = asin(clamp(w.y, -1.0, 1.0));
      vec2 uv = vec2(lon / (2.0 * PI) + 0.5, 0.5 - lat / PI);
      vec3 c = SAMPLE(uv);
      // the source's flat ocean → lit deep water
      float lum = dot(c, vec3(0.299, 0.587, 0.114));
      float ocean = smoothstep(0.03, 0.1, c.b - max(c.r, c.g)) * (1.0 - smoothstep(0.22, 0.4, lum));
      vec3 L = normalize(vec3(-0.42, 0.48, 0.77));
      float diff = clamp(dot(q, L), 0.0, 1.0);
      vec3 sea = mix(vec3(0.015, 0.06, 0.15), vec3(0.04, 0.2, 0.36), diff);
      c = mix(c, sea + c * 0.18, ocean);
      float glint = pow(max(dot(reflect(-L, q), vec3(0.0, 0.0, 1.0)), 0.0), 36.0) * 0.28 * ocean;
      c = c * (0.6 + 0.55 * diff) + glint;
      // thin atmosphere toward the limb
      float limb = pow(1.0 - clamp(q.z, 0.0, 1.0), 2.6);
      c = mix(c, vec3(0.55, 0.74, 0.96), limb * uAtmo);
      // entrance: from the facing point outward, cell by cell (like the dots it replaces)
      float cell = hash(floor(vec2(lon, lat) / (1.35 * PI / 180.0)));
      float reveal = clamp((uReveal - (1.0 - q.z) * 0.9 - cell * 0.25) * 4.0, 0.0, 1.0);
      c = mix(uBase, c, reveal);
      return vec4(c * edge, edge);
    }`;
  const FRAG2 = `#version 300 es
    precision highp float;
    uniform sampler2D uTex;
    out vec4 outColor;
    vec3 SAMPLE(vec2 uv) {
      vec2 alt = vec2(fract(uv.x + 0.5), uv.y); // same lookup without the jump at ±180°
      vec2 dx = dFdx(uv), dy = dFdy(uv), dxA = dFdx(alt), dyA = dFdy(alt);
      bool seam = max(abs(dx.x), abs(dy.x)) > max(abs(dxA.x), abs(dyA.x));
      return textureGrad(uTex, uv, seam ? dxA : dx, seam ? dyA : dy).rgb;
    }
    ${BODY}
    void main() { outColor = shade(); }`;
  const FRAG1 = `
    precision highp float;
    uniform sampler2D uTex;
    vec3 SAMPLE(vec2 uv) { return texture2D(uTex, uv).rgb; }
    ${BODY}
    void main() { gl_FragColor = shade(); }`;

  function create(kind, host = null) { // host: the caller's canvas, whose entering the window asks for the sharp picture
    const canvas = document.createElement("canvas");
    const options = { alpha: true, premultipliedAlpha: true, antialias: false, preserveDrawingBuffer: false };
    let gl = canvas.getContext("webgl2", options), v2 = !!gl;
    if (!gl) gl = canvas.getContext("webgl", options);
    if (!gl) return null;
    const compile = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, v2 ? src.replace(/^\s*attribute /m, "in ") : src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    let program;
    try {
      program = gl.createProgram();
      gl.attachShader(program, compile(gl.VERTEX_SHADER, v2 ? `#version 300 es\n${VERT}` : VERT));
      gl.attachShader(program, compile(gl.FRAGMENT_SHADER, v2 ? FRAG2 : FRAG1));
      gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
    } catch (error) {
      console.warn("earth: shader unavailable", error);
      return null;
    }
    gl.useProgram(program);
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(program, "aPos");
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    const u = name => gl.getUniformLocation(program, name);
    const loc = { size: u("uSize"), r: u("uR"), s: u("uS"), p: u("uP"), rot: u("uRot"), reveal: u("uReveal"), base: u("uBase"), atmo: u("uAtmo"), tex: u("uTex") };
    let ready = false, lost = false;
    const texture = gl.createTexture();
    const renderer = { canvas, kind, get ready() { return ready && !lost; }, onready: null };
    let shown = 0; // the sharpest level uploaded so far
    const upload = (img, level) => {
      if (lost || level <= shown) return;
      shown = level;
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
      gl.generateMipmap(gl.TEXTURE_2D); // both sizes are powers of two, so WebGL 1 can mipmap too
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, v2 ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      ready = true;
      renderer.onready?.();
    };
    const [tiny, quick, sharpLater] = loadImages();
    tiny.then(img => upload(img, 1), () => {});
    quick.then(img => upload(img, 2), () => console.warn("earth: satellite image unavailable"));
    let asked = false;
    // globes start drawing a little before they scroll in (their entrance): the sharp picture waits until one is in the window
    const inView = () => {
      if (!host) return true;
      const box = host.getBoundingClientRect();
      return box.bottom > 0 && box.top < innerHeight && box.width > 0;
    };
    canvas.addEventListener("webglcontextlost", event => { event.preventDefault(); lost = true; });

    // camera: { r: disc radius px, rot: {cl, sl, cp, sp}, s, p (perspective only), reveal, base: [r, g, b], atmo }
    renderer.draw = camera => {
      if (!asked && inView()) { asked = true; sharpLater()?.then(img => upload(img, 3), () => {}); }
      if (!renderer.ready) return false;
      const side = Math.max(2, Math.ceil(camera.r * 2 + 2));
      if (canvas.width !== side || canvas.height !== side) { canvas.width = side; canvas.height = side; }
      gl.viewport(0, 0, side, side);
      gl.uniform2f(loc.size, side, side);
      gl.uniform1f(loc.r, camera.r);
      gl.uniform1f(loc.s, camera.s || camera.r);
      gl.uniform1f(loc.p, kind === "perspective" ? camera.p : 0);
      gl.uniform4f(loc.rot, camera.rot.cl, camera.rot.sl, camera.rot.cp, camera.rot.sp);
      gl.uniform1f(loc.reveal, camera.reveal ?? 2);
      gl.uniform3fv(loc.base, camera.base || [0.08, 0.12, 0.17]);
      gl.uniform1f(loc.atmo, camera.atmo ?? 0.35);
      gl.uniform1i(loc.tex, 0);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      return true;
    };
    return renderer;
  }

  window.GreenEarth = { create, preload: loadImages };
})();
