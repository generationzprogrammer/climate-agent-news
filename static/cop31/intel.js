/* GREEN · COP31 — 今日情报 (2026-10-29), after 100lostspecies.com.
   An intro page with floating shards (the 100lostspecies.com intro), the Enter transition, and a gallery of today's
   intelligence cards on the inside wall of a cylinder (the 100lostspecies.com gallery).
   Presentation only: the cards are read from what app.js renders into #todayGrid (title, summary, source, link); data
   and app.js state are never touched. cop31.js opens it from every 今日情报 link (window.GreenIntel.open).
   Conventions follow the reference's three.js scene: world units, y up, the camera looks down −z. The shards are drawn
   on a 2D canvas (CPU projection of 30 quads, the spec's validated recipe); the cards are real DOM elements placed with
   matrix3d under a CSS perspective equal to the camera's focal length, so text stays crisp and links stay links. */
(() => {
  "use strict";
  const root = document.documentElement;
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const finePointer = matchMedia("(hover: hover) and (pointer: fine)");
  const $ = id => document.getElementById(id);
  const make = (tag, className = "", html = "") => {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (html) element.innerHTML = html;
    return element;
  };
  const esc = text => String(text ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
  const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value)), clamp01 = value => clamp(value, 0, 1);
  const TAU = Math.PI * 2, DEG = Math.PI / 180;
  const wrapPi = a => ((a + Math.PI) % TAU + TAU) % TAU - Math.PI;

  /* ---------- Eases (immg.* = the reference's CustomEase curves; GSAP powerN) ---------- */
  const bezier = (x1, y1, x2, y2) => x => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let lo = 0, hi = 1, t = x;
    for (let i = 0; i < 28; i += 1) {
      t = (lo + hi) / 2;
      const bx = 3 * x1 * t * (1 - t) ** 2 + 3 * x2 * t * t * (1 - t) + t ** 3;
      if (bx < x) lo = t; else hi = t;
    }
    return 3 * y1 * t * (1 - t) ** 2 + 3 * y2 * t * t * (1 - t) + t ** 3;
  };
  const IO = bezier(.66, 0, .34, 1);                                    // immg.cubicInOut
  const ZOOM = bezier(.5, 0, .3, 1);                                    // immg.zoomProject
  const power1 = t => t < .5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;   // power1.inOut
  const power2 = t => t < .5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;  // power2.inOut
  const power3out = t => 1 - (1 - t) ** 4;                              // power3.out
  const ss = (a, b, x) => { const t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); };
  const prog = (t, start, duration, ease) => { const p = clamp01((t - start) / duration); return ease ? ease(p) : p; };
  const CSS_IO = "cubic-bezier(.66, 0, .34, 1)";

  /* ---------- Words (the experience's own chrome; the content comes from the page) ---------- */
  const en = () => (root.lang || "").startsWith("en");
  const WORDS = {
    enter: ["进入", "Enter"],
    title: ["今日气候情报", "Today's climate intelligence"], // the intro's title (2026-10-29; no item count)
    views: [["卡片", "Visuals"], ["地区", "Regions"], ["日期", "Dates"]],
    by: [["按卡片", "By visuals"], ["按地区", "By region"], ["按日期", "By dates"]], // 按标题 → 按地区 (2026-10-29)
    scroll: ["滚动探索", "Scroll to explore"],
    menu: ["菜单", "Menu"], // in place of 关于 / About: the site menu, as a drop-down (2026-10-29)
    regions: [["全球", "Global"], ["亚洲", "Asia"], ["欧洲", "Europe"], ["非洲", "Africa"], ["北美洲", "North America"], ["南美洲", "South America"], ["大洋洲", "Oceania"], ["南极洲", "Antarctica"]],
    explore: ["展开", "Explore"],
    tutorial: ["点击任意一张卡片，展开这条情报的概要与原文来源", "Click on any card to open its brief and its original source"],
    home: ["返回首页", "Back to the home page"],
    close: ["关闭", "Close"],
  };
  const say = pair => pair[en() ? 1 : 0];

  /* ---------- Icons (our own line drawings) ---------- */
  const svg = (body, size = 31) => `<svg viewBox="0 0 32 32" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
  const ICON = {
    globe: svg('<circle cx="16" cy="16" r="10.5"/><ellipse cx="16" cy="16" rx="4.6" ry="10.5"/><path d="M5.5 16h21M7.4 10.3h17.2M7.4 21.7h17.2"/>'),
    leaf: svg('<path d="M8 24C7 14 13 7.5 25 7c.6 11.5-6 18-16.3 17.4"/><path d="M8.2 24.4C11 19 15 15 20 12"/>'),
    drop: svg('<path d="M16 5.5c4.6 6 7.4 10.2 7.4 13.4a7.4 7.4 0 0 1-14.8 0c0-3.2 2.8-7.4 7.4-13.4z"/><path d="M12.6 19.5a3.6 3.6 0 0 0 3 3.4"/>'),
    grid: svg('<rect x="6" y="6" width="8.5" height="8.5"/><rect x="17.5" y="6" width="8.5" height="8.5"/><rect x="6" y="17.5" width="8.5" height="8.5"/><rect x="17.5" y="17.5" width="8.5" height="8.5"/>', 13),
    pin: svg('<path d="M16 28.5S7.5 19.6 7.5 13.2a8.5 8.5 0 0 1 17 0c0 6.4-8.5 15.3-8.5 15.3z"/><circle cx="16" cy="13.2" r="3"/>', 13),
    cal: svg('<rect x="5.5" y="7.5" width="21" height="19"/><path d="M5.5 13h21M11 4.5v5M21 4.5v5"/>', 13),
  };

  /* ---------- The cards' ornaments: engraved line patterns, one per item, baked into SVG images ----------
     Six families (guilloché rosette, isobars, survey sunburst, diamond lattice, interference ripples, meridians) in the
     page palette — grey-blue lines, one red accent each — on four paper tones. */
  const TONES = {
    paper: { paper: "#ffffff", line: "#7e93a8", soft: "#bccad7", accent: "#c8372d" },
    mist: { paper: "#e9eef3", line: "#587088", soft: "#a9b8c7", accent: "#c8372d" },
    deep: { paper: "#243243", line: "#8ea2b6", soft: "#4a6178", accent: "#ff7a6e" },
    blush: { paper: "#fbeeec", line: "#c08f89", soft: "#e6cbc7", accent: "#c8372d" },
  };
  const TONE_ORDER = ["paper", "mist", "paper", "deep", "blush", "paper", "mist", "paper", "deep", "paper", "blush", "mist"];
  const rng = seed => () => { seed = seed * 16807 % 2147483647; return (seed - 1) / 2147483646; };
  const f1 = n => n.toFixed(1);
  const ring = (cx, cy, radius, wave) => {
    let d = "";
    for (let i = 0; i <= 240; i += 1) {
      const t = i / 240 * TAU, r = radius + wave(t);
      d += `${i ? "L" : "M"}${f1(cx + r * Math.cos(t))} ${f1(cy + r * Math.sin(t))}`;
    }
    return `${d}Z`;
  };
  const path = (d, stroke, width = .5, extra = "") => `<path d="${d}" stroke="${stroke}" stroke-width="${width}" fill="none"${extra}/>`;
  const ORNAMENTS = [
    (c, r) => { // guilloché rosette
      const cx = 190 + r() * 50, cy = 82 + r() * 26, R = 74 + r() * 22, k = 6 + Math.floor(r() * 7), n = 11 + Math.floor(r() * 5), amp = R * (.1 + r() * .07);
      let out = "";
      for (let j = 0; j < n; j += 1) out += path(ring(cx, cy, R, t => amp * Math.sin(k * t + j * Math.PI / n / 1.1)), c.line, .45, ' opacity=".7"');
      for (let j = 0; j < 5; j += 1) out += path(ring(cx, cy, R * .56, t => R * .085 * Math.sin((2 * k + 1) * t + j * .55)), c.soft, .45);
      return out + path(ring(cx, cy, R * .8, t => amp * .5 * Math.sin(k * t)), c.accent, .8, ' opacity=".85"');
    },
    (c, r) => { // isobars
      const freq = .016 + r() * .016, amp = 7 + r() * 8, red = 8 + Math.floor(r() * 5);
      let out = "";
      for (let j = 0; j < 18; j += 1) {
        let d = "";
        for (let x = 0; x <= 300; x += 5) d += `${x ? "L" : "M"}${x} ${f1(14 + j * 9 + amp * Math.sin(x * freq + j * .3) + amp * .5 * Math.sin(x * freq * 2.3 + j * .7))}`;
        out += path(d, j === red ? c.accent : j % 4 ? c.soft : c.line, j === red ? .9 : .5);
      }
      return out;
    },
    (c, r) => { // survey sunburst
      const cx = r() < .5 ? 26 : 274, cy = 22;
      let out = "";
      for (let i = 0; i <= 56; i += 1) {
        const a = Math.PI * i / 56, len = i % 4 ? 130 : 178;
        out += path(`M${f1(cx + 30 * Math.cos(a))} ${f1(cy + 30 * Math.sin(a))}L${f1(cx + len * Math.cos(a))} ${f1(cy + len * Math.sin(a))}`, c.soft, .5);
      }
      for (let j = 1; j <= 8; j += 1) out += `<circle cx="${cx}" cy="${cy}" r="${30 + j * 21}" fill="none" stroke="${j === 5 ? c.accent : c.line}" stroke-width="${j === 5 ? .9 : .5}"${j % 2 && j !== 5 ? ' stroke-dasharray="1.5 2.5"' : ""}/>`;
      return out;
    },
    (c, r) => { // diamond lattice
      const step = 20 + Math.floor(r() * 8), reach = 190, mark = Math.floor(r() * 7);
      let out = "";
      for (let x = -reach; x < 300 + reach; x += step) out += path(`M${x} 0L${x + reach} ${reach}M${x} 0L${x - reach} ${reach}`, c.soft, .5);
      for (let y = 0, row = 0; y < reach; y += step / 2, row += 1) {
        for (let x = row % 2 ? step / 2 : 0, col = 0; x < 300; x += step, col += 1) {
          const hit = row === 4 && col === mark;
          out += `<circle cx="${f1(x)}" cy="${f1(y)}" r="${hit ? 2.8 : .95}" fill="${hit ? c.accent : c.line}"/>`;
        }
      }
      return out;
    },
    (c, r) => { // interference ripples
      const a = [80 + r() * 40, 60 + r() * 30], b = [200 + r() * 50, 90 + r() * 30];
      let out = "";
      for (let j = 1; j <= 14; j += 1) out += `<circle cx="${f1(a[0])}" cy="${f1(a[1])}" r="${j * 11}" fill="none" stroke="${c.line}" stroke-width=".5" opacity=".7"/>`;
      for (let j = 1; j <= 12; j += 1) out += `<circle cx="${f1(b[0])}" cy="${f1(b[1])}" r="${j * 12}" fill="none" stroke="${j === 6 ? c.accent : c.soft}" stroke-width="${j === 6 ? .9 : .5}"/>`;
      return out;
    },
    (c, r) => { // meridians: an engraved globe
      const cx = 200 + r() * 40, cy = 96, R = 88 + r() * 14, tilt = (r() - .5) * .5;
      let out = `<circle cx="${f1(cx)}" cy="${cy}" r="${f1(R)}" fill="none" stroke="${c.line}" stroke-width=".6"/>`;
      for (let j = 1; j < 9; j += 1) {
        const rx = Math.abs(Math.cos(j / 9 * Math.PI)) * R;
        out += `<ellipse cx="${f1(cx)}" cy="${cy}" rx="${f1(rx)}" ry="${f1(R)}" fill="none" stroke="${c.soft}" stroke-width=".5" transform="rotate(${f1(tilt / DEG)} ${f1(cx)} ${cy})"/>`;
      }
      for (let j = -3; j <= 3; j += 1) {
        const y = cy + j * R / 4, half = Math.sqrt(Math.max(0, R * R - (y - cy) ** 2));
        out += path(`M${f1(cx - half)} ${f1(y)}L${f1(cx + half)} ${f1(y)}`, j === 1 ? c.accent : c.soft, j === 1 ? .9 : .5);
      }
      return out;
    },
  ];
  function ornament(index, tone) {
    const c = TONES[tone], r = rng(index * 7919 + 101);
    const body = ORNAMENTS[index % ORNAMENTS.length](c, r);
    const svgText = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" width="600" height="600">${body}</svg>`;
    return URL.createObjectURL(new Blob([svgText], { type: "image/svg+xml" }));
  }

  /* ---------- Regions (the 按地区 view, 2026-10-29) ----------
     Each item's continent, from the places / country codes in data/dashboard.json (read only; the cards do not carry
     them), matched to the cards by their source link, then by title. An item with no place is 全球. */
  const CONTINENT = {}; // ISO 3166 alpha-2 → index in WORDS.regions
  [[1, "AE AF AM AZ BD BH BN BT CN CY GE HK ID IL IN IQ IR JO JP KG KH KP KR KW KZ LA LB LK MM MN MO MV MY NP OM PH PK PS QA SA SG SY TH TJ TL TM TR TW UZ VN YE"],
    [2, "AD AL AT AX BA BE BG BY CH CZ DE DK EE ES FI FO FR GB GG GI GR HR HU IE IM IS IT JE LI LT LU LV MC MD ME MK MT NL NO PL PT RO RS RU SE SI SJ SK SM UA VA XK"],
    [3, "AO BF BI BJ BW CD CF CG CI CM CV DJ DZ EG EH ER ET GA GH GM GN GQ GW KE KM LR LS LY MA MG ML MR MU MW MZ NA NE NG RE RW SC SD SH SL SN SO SS ST SZ TD TG TN TZ UG YT ZA ZM ZW"],
    [4, "AG AI AW BB BL BM BQ BS BZ CA CR CU CW DM DO GD GL GP GT HN HT JM KN KY LC MF MQ MS MX NI PA PM PR SV SX TC TT US VC VG VI"],
    [5, "AR BO BR CL CO EC FK GF GY PE PY SR UY VE"],
    [6, "AS AU CK FJ FM GU KI MH MP NC NF NR NU NZ PF PG PN PW SB TK TO TV UM VU WF WS"],
    [7, "AQ"]].forEach(([region, codes]) => codes.split(" ").forEach(code => { CONTINENT[code] = region; }));
  const REGION_NAME = { 全球: 0, 国际: 0, 亚洲: 1, 东亚: 1, 东南亚: 1, 南亚: 1, 中亚: 1, 西亚: 1, 中东: 1, 欧洲: 2, 非洲: 3, 北美洲: 4, 北美: 4, 南美洲: 5, 南美: 5, 拉丁美洲: 5, 大洋洲: 6, 太平洋: 6, 南极洲: 7, 南极: 7 };
  const regionOfPoint = (lon, lat) => lat < -60 ? 7 : lon < -25 ? (lat > 13 ? 4 : 5) : lon > 110 && lat < -8 ? 6 : lon > 60 || (lon > 26 && lat < 42 && lat > 12) ? 1 : lat > 36 ? 2 : 3;
  function regionOf(record) {
    const place = record.places?.[0], codes = record.country_codes || [];
    if (place && place.name_zh in REGION_NAME) return REGION_NAME[place.name_zh];
    const code = (place && codes.find(c => c.name_zh === place.name_zh)) || codes.find(c => c.alpha2 in CONTINENT);
    if (code && code.alpha2 in CONTINENT) return CONTINENT[code.alpha2];
    if (place && Number.isFinite(place.lon) && Number.isFinite(place.lat)) return regionOfPoint(place.lon, place.lat);
    return 0;
  }
  const keyOf = text => { try { return /^https?:/i.test(text) ? new URL(text).href : String(text).trim(); } catch { return String(text).trim(); } };
  // The same read gives the detail page the whole record (original title, 关注含义, figures, tags).
  let recordMap = null;
  const regionsReady = fetch(new URL("./data/dashboard.json", document.baseURI)).then(response => response.json()).then(data => {
    recordMap = new Map();
    for (const record of data.intelligence || []) {
      for (const key of [record.canonical_url, record.source_url, record.url, record.title_zh, record.title_en, record.title_original]) if (key) recordMap.set(keyOf(key), record);
    }
  }).catch(() => { recordMap = new Map(); });
  const recordFor = (href, title) => recordMap?.get(keyOf(href)) || recordMap?.get(keyOf(title)) || null;
  const regionFor = (href, title) => { const record = recordFor(href, title); return record ? regionOf(record) : 0; };

  /* ---------- Today's items, as app.js rendered them ---------- */
  const dateKey = text => {
    let m = /(\d{4})\D(\d{1,2})\D(\d{1,2})/.exec(text);
    if (m) return `${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`;
    m = /(\d{1,2})\D(\d{1,2})\D(\d{4})/.exec(text); // en-GB: dd/mm/yyyy
    return m ? `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}` : "";
  };
  let arts = [];
  function readItems() {
    arts.forEach(url => URL.revokeObjectURL(url));
    arts = [];
    return [...document.querySelectorAll("#todayGrid .signal-card")].map((card, index) => {
      const foot = card.querySelector(".signal-foot span")?.textContent.trim() || "";
      const cut = foot.lastIndexOf(" · ");
      const link = card.querySelector(".signal-foot a");
      const tone = TONE_ORDER[index % TONE_ORDER.length];
      const art = ornament(index, tone);
      arts.push(art);
      return {
        index, tone, art,
        theme: card.querySelector(".signal-meta .topic")?.textContent.trim() || "",
        title: card.querySelector(".signal-content > h3")?.textContent.trim() || "",
        summary: card.querySelector(".signal-content > p")?.textContent.trim() || "",
        source: cut > 0 ? foot.slice(0, cut) : foot,
        date: cut > 0 ? foot.slice(cut + 3) : "",
        key: dateKey(cut > 0 ? foot.slice(cut + 3) : foot),
        href: link?.href || "",
        linkText: link?.textContent.trim() || "",
        region: regionFor(link?.href || "", card.querySelector(".signal-content > h3")?.textContent.trim() || ""),
        record: recordFor(link?.href || "", card.querySelector(".signal-content > h3")?.textContent.trim() || ""),
      };
    }).filter(item => item.title).map(item => (rasterize(item), item));
  }
  // Ornaments become 512 px bitmaps: a scaled bitmap is cheap, re-rendering an SVG of thousands of segments at every
  // new scale is not (the sphere shows hundreds of cards at once).
  function rasterize(item) {
    const svgUrl = item.art, image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 512;
      canvas.getContext("2d").drawImage(image, 0, 0, 512, 512);
      canvas.toBlob(blob => {
        if (!blob || item.art !== svgUrl) return;
        const png = URL.createObjectURL(blob);
        arts.push(png);
        item.art = png;
        document.querySelectorAll("img.ig-orn").forEach(orn => { if (orn.getAttribute("src") === svgUrl) orn.src = png; });
      });
    };
    image.src = svgUrl;
  }
  const dataReady = () => !!document.querySelector("#todayGrid .signal-card, #todayGrid > .empty");
  // the regions arrive with their own read of the data: if the layer was built before, sort the region view again
  regionsReady.then(() => {
    if (!items.length) return;
    items.forEach(item => { item.region = regionFor(item.href, item.title); item.record = recordFor(item.href, item.title); });
    if (phase === "intro") buildTiles();
  });

  /* ---------- Shards (intro §2, recipe §7.2): 30 slivers on the inside of a tube pointing at the camera ---------- */
  function makeShards(canvas) {
    const CNT = 30, ROWS = 3, R = .7, SCALE = .8, OPAC = .85, GROUND = .58; // GROUND: same contrast on a light ground as theirs on black
    // The reference's sage / steel blue / sand become grey-blue / steel blue / rose: same pipeline, our palette.
    const PAL = [[138, 155, 176], [91, 140, 169], [214, 162, 154]].map(c => c.map(v => v / 255));
    const seedOf = s => { let e = s + 1831565813; e = Math.imul(e ^ e >>> 15, e | 1); e ^= e + Math.imul(e ^ e >>> 7, e | 61); return ((e ^ e >>> 14) >>> 0) / 4294967296; };
    const sat = (c, s) => { const l = c[0] * .2125 + c[1] * .7154 + c[2] * .0721; return c.map(x => l + (x - l) * s); };
    const tiles = [];
    const step = TAU / CNT * ROWS;
    for (let h = 0, a = 0, c = 0; h < CNT; h += 1) {
      tiles.push({ th0: a + (Math.random() - .5) * .1, rowY: c * .5 + (Math.random() - .5) * .1 - ROWS / 2 * .5, zOff: (Math.random() - .1) * .5 });
      a += step;
      c = Math.floor(h / (CNT / ROWS)); // updated after use, as in the source: rows of 11 / 10 / 9
    }
    tiles.forEach((tile, h) => {
      const s = seedOf(h);
      tile.sx = (1 + (Math.random() - .5) * .85) * .1;
      tile.sy = (1 + (Math.random() - .5) * .85) * .1;
      const base = PAL[Math.floor(Math.random() * 3)];
      tile.w = Math.max(.1, Math.abs(Math.sin(s * 987))) * .2;
      tile.tilt = Math.sin(s * 123) * .1;
      const n = .5 + (Math.random() + Math.random() + Math.random() - 1.5) * .34;
      tile.col0 = sat(base, 1 + Math.sin(s * 1210) * .5).map(v => v + Math.sin(s * 743) * .05 + ss(.4, 1, n) * .04 - ss(0, 1, Math.sin(.5 * s * 4)) * .03);
    });
    const ctx = canvas.getContext("2d");
    let W = 1, H = 1, dpr = 1;
    function resize() {
      W = innerWidth; H = innerHeight;
      dpr = Math.min(W < 768 ? 2 : 1.5, devicePixelRatio || 1);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
    }
    // S = { et, meshY, meshZ, O, SB, cam: { x, y, z, rx, ry }, fov }. Returns false once the mesh is culled.
    function draw(S) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const k = 1 / Math.tan(S.fov * Math.PI / 360) * H / 2;
      const cx = Math.cos(-S.cam.rx), sx = Math.sin(-S.cam.rx), cy = Math.cos(-S.cam.ry), sy = Math.sin(-S.cam.ry);
      const view = (x, y, z) => {
        x -= S.cam.x; y -= S.cam.y; z -= S.cam.z;
        const y1 = y * cx - z * sx, z1 = y * sx + z * cx;
        return [x * cy + z1 * sy, y1, -x * sy + z1 * cy];
      };
      if (S.O <= 0 || view(0, S.meshY, S.meshZ)[2] > Math.SQRT1_2 - .5) return false; // three.js frustum cull of the mesh
      const time = S.et * .7, polys = [];
      for (const tile of tiles) {
        const th = tile.th0 + time * tile.w, a = -th + tile.tilt + Math.PI, ca = Math.cos(a), sa = Math.sin(a);
        const px = R * Math.sin(th), pz = R * Math.cos(th);
        const v = [[-.5, -.5], [.5, -.5], [.5, .5], [-.5, .5]].map(([u, w]) => {
          const x = u * SCALE * tile.sx, y = w * SCALE * tile.sy;
          const X = ca * x + px, Y = y + tile.rowY, Z = sa * x + pz + tile.zOff;
          return view(X, -Z + S.meshY, Y + S.meshZ); // the rendered pose: mesh rotation.x = π/2 only
        });
        const clip = [];
        for (let i = 0; i < 4; i += 1) {
          const p = v[i], q = v[(i + 1) % 4], pin = p[2] <= -.5, qin = q[2] <= -.5;
          if (pin) clip.push(p);
          if (pin !== qin) { const t = (-.5 - p[2]) / (q[2] - p[2]); clip.push(p.map((c, j) => c + (q[j] - c) * t)); }
        }
        if (clip.length < 3) continue;
        const pts = clip.map(([x, y, z]) => [W / 2 + x * k / -z, H / 2 - y * k / -z]);
        const L = (-.5 * px - .5 * tile.rowY + .5) / (Math.sqrt(.75) * Math.hypot(px, tile.rowY, 1));
        const gam = 1 - ss(.3, .7, L) * .7;
        let col = tile.col0.map(c => Math.pow(Math.max(c, 0), 1 / gam));
        const inv = sat(col, -1.2);
        col = col.map((c, i) => (inv[i] * .4 * (1 - S.SB) + c * S.SB) * S.O);
        polys.push({ d: v.reduce((sum, p) => sum + p[2], 0) / 4, pts, col, a: OPAC * .7 * S.O * GROUND });
      }
      polys.sort((p, q) => p.d - q.d);
      for (const p of polys) {
        if (p.a < .01) continue;
        ctx.globalAlpha = p.a;
        ctx.fillStyle = `rgb(${p.col.map(c => Math.round(clamp01(c) * 255)).join(",")})`;
        ctx.beginPath();
        p.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
        ctx.closePath();
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      return true;
    }
    return { resize, draw, clear: () => { ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, canvas.width, canvas.height); } };
  }

  /* ---------- 3×3 rotations (three.js conventions) ---------- */
  const rotX = a => { const c = Math.cos(a), s = Math.sin(a); return [1, 0, 0, 0, c, -s, 0, s, c]; };
  const rotY = a => { const c = Math.cos(a), s = Math.sin(a); return [c, 0, s, 0, 1, 0, -s, 0, c]; };
  const rotZ = a => { const c = Math.cos(a), s = Math.sin(a); return [c, -s, 0, s, c, 0, 0, 0, 1]; };
  const mul3 = (a, b) => {
    const m = new Array(9);
    for (let r = 0; r < 3; r += 1) for (let c = 0; c < 3; c += 1) m[r * 3 + c] = a[r * 3] * b[c] + a[r * 3 + 1] * b[3 + c] + a[r * 3 + 2] * b[6 + c];
    return m;
  };
  const tr3 = a => [a[0], a[3], a[6], a[1], a[4], a[7], a[2], a[5], a[8]];
  const app3 = (m, x, y, z) => [m[0] * x + m[1] * y + m[2] * z, m[3] * x + m[4] * y + m[5] * z, m[6] * x + m[7] * y + m[8] * z];
  // CSS matrix for an element whose px box is a 1-unit-per-s plane: conjugate the view-space matrix by diag(s, −s, s)
  // (CSS y points down) and push it back by the focal length F (the stage's perspective puts the eye at z = F).
  const cssMatrix = (m, t, s, F) =>
    `matrix3d(${m[0]},${-m[3]},${m[6]},0,${-m[1]},${m[4]},${-m[7]},0,${m[2]},${-m[5]},${m[8]},0,${t[0] * s},${-t[1] * s},${t[2] * s + F},1)`;

  /* ---------- The experience ---------- */
  let el = null, shards = null, items = [], built = false;
  let phase = "closed", openedAt = 0, enteredAt = 0, raf = 0, lastNow = 0, clock = 0, pushed = false, gone = [];
  const ui = {};
  let view = { W: 1, H: 1, fov: 45, F: 1, s: 1 };
  const look = { x: 0, y: 0, hx: 0, hy: 0 };  // pointer NDC and its slow follower (camera mouse-look)
  const LIN = x => x;
  const power3inOut = t => t < .5 ? 8 * t ** 4 : 1 - (-2 * t + 2) ** 4 / 2;
  const lerp = (a, b, t) => a + (b - a) * t;
  const mobile = () => view.W < 768;

  /* ---------- Tween clock ----------
     GSAP-style: a tween starts from the value it finds when it starts, and takes its key over from any tween already
     running on it (delayed tweens wait their turn). `call` entries run a function at their time. */
  const tweens = [];
  function tw(obj, key, to, duration, { ease = IO, delay = 0 } = {}) { tweens.push({ obj, key, to, duration, ease, start: clock + delay, from: null }); }
  const later = (delay, call) => tweens.push({ call, start: clock + delay });
  function stepTweens() {
    for (const t of tweens) {
      if (t.dead || clock < t.start) continue;
      if (t.call) { t.dead = true; t.call(); continue; }
      if (t.from === null) {
        for (const o of tweens) if (o !== t && !o.dead && !o.call && o.from !== null && o.obj === t.obj && o.key === t.key) o.dead = true;
        t.from = t.obj[t.key];
      }
      const p = t.duration > 0 ? clamp01((clock - t.start) / t.duration) : 1;
      t.obj[t.key] = t.from + (t.to - t.from) * t.ease(p);
      if (p >= 1) t.dead = true;
    }
    let w = 0;
    for (const t of tweens) if (!t.dead) tweens[w++] = t;
    tweens.length = w;
  }

  /* ---------- Scene state (the reference's uniforms) ---------- */
  const camT = { x: 0, y: 0, z: 0, ix: 0, iy: 0 };           // camera target position, mouse-look influence
  const sc = { gz: -10, alpha: 0, bill: 0, billDepth: 5, pick: 0, texts: 0 }; // universe group z, global tile opacity, billboard
  const chrome = { head: 0, foot: 0 };
  // The three views (gallery §2, §14): Visuals = 卡片 (cylinder of cards), Names = 标题 (wheel + title list),
  // Extinction = 日期 (two rows grouped by date). Colours: red · steel grey-blue · grey-blue.
  const CFG = [
    { key: "visuals", color: [200, 55, 45], radius: 10.5, base: 1.36, ov: .3, wait: .1, camZ: -5, look: [5, 6] },
    { key: "titles", color: [91, 140, 169], radius: 10.5, base: .4128, ov: 1.05, wait: .3, camZ: -6, look: [.5, .5] },
    { key: "dates", color: [126, 147, 168], radius: 10, base: .48, ov: .6, wait: .25, camZ: -6.5, look: [.5, .5] },
  ];
  const WAIT_PAR = [.8, 1, .6];
  const U = CFG.map((cfg, index) => ({
    index, cfg, tiles: [], extras: [], root: null, open: 0, close: 0, openRadius: 10, scale: 1, opacity: 0, tint: 1,
    dark: 1, stagger: 0, globe: 0, overview: 0, ovRow: [0, 0, 0], waiting: 0, wOpening: 0, wRows: [0, 0, 0], rowsX: [0, 0, 0],
    rowsY: [0, 0, 0], rowsScale: [1, 1, 1], wrap: { x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0 }, wrapOv: { rx: 0, ry: 0, rz: 0 },
    ovA: 0, ovB: 0, openInt: 0, label: 0, texts: 0, ink: 0, extraY: 0, wto: 1, visited: false, offX: [0, 0, 0],
  }));
  let cur = 0, changing = false;
  const nextOf = i => (i + 1) % 3;
  // per-view navigation state (gallery §4, §14.1, §14.3)
  const nav = { imp: { x: 0, y: 0 }, vel: { x: 0, y: 0 }, I: 0, uV: 0, inV: 0, tilt: 0, touch: false };
  const names = { target: 0, q: 0, ds: 0, ga: 0, gb: 0, rp: 0, groups: [] };
  const dnav = { ps: 0, is: 0 };
  const inputVelocity = () => cur === 0 ? nav.inV : cur === 1 ? (names.target - names.q) * 3 : dnav.is * 700;

  const hover = { card: null, next: null, amount: 0, label: 0, switchAt: 0 };
  const cursor = { x: -100, y: -100, fx: -100, fy: -100, tx: -100, ty: -100, start: 0, on: false };
  let pointerDown = null, dragged = false;
  let pendingNav = null; // a page picked in the 菜单 drop-down: visited once the layer has closed
  function setMenu(on) {
    if (!el || el.classList.contains("menu-on") === on) return;
    el.classList.toggle("menu-on", on);
    ui.about.setAttribute("aria-expanded", String(on));
    if (on) setHoverCard(null);
  }

  function measure() {
    const W = innerWidth, H = innerHeight;
    const fov = Math.min(61, 45 / Math.min(1, 1.5 * W / H));
    const F = .5 * H / Math.tan(fov * Math.PI / 360);
    view = { W, H, fov, F, s: F / 5.5 };
    if (!el) return;
    ui.stage.style.perspective = `${F.toFixed(2)}px`;
    const card = 1.36 * view.s;
    el.style.setProperty("--c", `${card.toFixed(2)}px`);
    el.style.setProperty("--u", (card / 269).toFixed(4)); // card sizes are written for the 269 px front card
    el.style.setProperty("--vh", `${H}px`);
    el.style.setProperty("--year", `${(.43 * view.s).toFixed(2)}px`);
    el.classList.toggle("is-small", card < 220);
    shards?.resize();
    if (U[2].tiles.length) layoutDates();
  }

  function build() {
    if (built) return;
    built = true;
    el = make("div", "ig");
    el.hidden = true;
    el.setAttribute("role", "dialog");
    el.tabIndex = -1;
    el.setAttribute("aria-modal", "true");
    el.innerHTML = `
      <div class="ig-ground" aria-hidden="true"></div>
      <div class="ig-white" aria-hidden="true"></div>
      <img class="ig-ghost" alt="" aria-hidden="true">
      <canvas class="ig-shards" aria-hidden="true"></canvas>
      <div class="ig-gallery"><div class="ig-stage"><div class="ig-u" data-u="0"></div><div class="ig-u" data-u="1"></div><div class="ig-u" data-u="2"></div></div></div>
      <div class="ig-dust" aria-hidden="true"></div>
      <p class="ig-bill" aria-hidden="true"></p>
      <section class="ig-intro">
        <div class="ig-content">
          <div class="ig-logo" aria-hidden="true"><span>${ICON.globe}${ICON.leaf}${ICON.drop}${ICON.globe}</span></div>
          <h1 class="ig-h1"></h1>
          <p class="ig-h2"></p>
          <div class="ig-btnw"><span class="ig-percent" aria-hidden="true">000</span><button class="ig-enter" type="button"><span></span></button></div>
        </div>
        <div class="ig-credits"></div>
      </section>
      <div class="ig-names" hidden><span class="ig-dash" aria-hidden="true"></span><div class="ig-nlist"></div></div>
      <div class="ig-ngrad" aria-hidden="true"></div>
      <div class="ig-head">
        <div class="ig-views" role="group">
          <button type="button" data-view="0" class="is-on">${ICON.grid}<span></span></button>
          <button type="button" data-view="1">${ICON.pin}<span></span></button>
          <button type="button" data-view="2">${ICON.cal}<span></span></button>
        </div>
        <p class="ig-scroll"></p>
        <nav class="ig-menu"></nav>
        <button class="ig-about" type="button" aria-expanded="false"><span></span></button>
      </div>
      <div class="ig-foot">
        <a class="ig-home" href="./cop31/#top"><img src="./assets/green-logo-mark.png" alt="" width="34" height="34"></a>
        <p class="ig-tutorial"></p>
      </div>
      <section class="ig-detail" hidden>
        <div class="ig-dview">
          <div class="ig-dcontent">
            <div class="ig-dhero" aria-hidden="true"></div>
            <article class="ig-dtext" data-swing>
              <p class="ig-dkick"></p>
              <h2 class="ig-dtitle"></h2>
              <p class="ig-dorig"></p>
              <p class="ig-dmeta"></p>
              <p class="ig-dsum"></p>
              <p class="ig-dwhy"></p>
              <ul class="ig-dfacts"></ul>
            </article>
            <div class="ig-dlinkw" data-swing><a class="ig-dlink" target="_blank" rel="noopener noreferrer"><span></span></a></div>
            <div class="ig-dend"><button class="ig-dx" type="button"><span aria-hidden="true">×</span></button></div>
          </div>
        </div>
        <a class="ig-dhome" href="./cop31/#top"><span class="ig-dmark" aria-hidden="true"><span>${ICON.globe}${ICON.leaf}${ICON.drop}${ICON.globe}</span></span><img src="./assets/green-logo-mark.png" alt="" width="34" height="34"></a>
        <p class="ig-dscroll"></p>
        <button class="ig-dclose" type="button"><span></span></button>
      </section>
      <div class="ig-cursor" aria-hidden="true"><span></span></div>`;
    document.body.append(el);
    for (const [key, selector] of Object.entries({
      ground: ".ig-ground", white: ".ig-white", canvas: ".ig-shards", gallery: ".ig-gallery", stage: ".ig-stage", bill: ".ig-bill",
      intro: ".ig-intro", content: ".ig-content", logo: ".ig-logo", h1: ".ig-h1", h2: ".ig-h2", btnw: ".ig-btnw", percent: ".ig-percent",
      enter: ".ig-enter", credits: ".ig-credits", head: ".ig-head", views: ".ig-views", scroll: ".ig-scroll", about: ".ig-about", menu: ".ig-menu",
      foot: ".ig-foot", home: ".ig-home", tutorial: ".ig-tutorial", cursor: ".ig-cursor", ghost: ".ig-ghost",
      names: ".ig-names", nlist: ".ig-nlist", ngrad: ".ig-ngrad",
      detail: ".ig-detail", dview: ".ig-dview", dcontent: ".ig-dcontent", dhero: ".ig-dhero", dkick: ".ig-dkick", dtitle: ".ig-dtitle",
      dmeta: ".ig-dmeta", dsum: ".ig-dsum", dlink: ".ig-dlink", dx: ".ig-dx", dhome: ".ig-dhome", dscroll: ".ig-dscroll", dclose: ".ig-dclose",
      dorig: ".ig-dorig", dwhy: ".ig-dwhy", dfacts: ".ig-dfacts",
    })) ui[key] = el.querySelector(selector);
    U.forEach((u, i) => { u.root = el.querySelector(`.ig-u[data-u="${i}"]`); u.root.style.setProperty("--ucol", u.cfg.color.join(" ")); });
    shards = makeShards(ui.canvas);
    // dust: ~0.4 % of pixels as 1–2 px dark specks on a 256² tile (the reference's post pass)
    const dust = make("canvas"), g = dust.getContext("2d");
    dust.width = dust.height = 256;
    for (let i = 0; i < 262; i += 1) {
      g.fillStyle = `rgba(17, 26, 36, ${(.3 + Math.random() * .5).toFixed(2)})`;
      g.fillRect(Math.floor(Math.random() * 256), Math.floor(Math.random() * 256), Math.random() < .2 ? 2 : 1, 1);
    }
    el.style.setProperty("--dust", `url(${dust.toDataURL()})`);
    measure();
    wire();
  }

  // Words come from the page where it has them (app.js translates those), the rest from WORDS.
  // The lede keeps only its first clause (2026-10-29): "…值得关注的气候事件，提供中文标题…" → "…值得关注的气候事件。"
  const lede = () => {
    const text = $("heroLede")?.textContent.trim() || "", cut = text.search(en() ? /, with\b/ : /，/);
    return cut > 0 ? text.slice(0, cut) + (en() ? "." : "。") : text;
  };
  function words() {
    const title = say(WORDS.title);
    ui.h1.textContent = title;
    ui.h2.textContent = lede();
    // the intro's foot is the site's footer (brand + line on the left, links on the right; 2026-10-29), copied
    // from the page so it reads the same in either language; ids and i18n hooks stay on the original only
    const footer = document.querySelector("body > footer");
    ui.credits.replaceChildren(...[...(footer?.children || [])].filter(part => !part.matches(".cop31-credit")).map(part => part.cloneNode(true)));
    ui.credits.querySelectorAll("[id], [data-i18n]").forEach(node => { node.removeAttribute("id"); node.removeAttribute("data-i18n"); });
    // the 菜单 drop-down lists the site's pages, as the menu does everywhere else
    ui.menu.setAttribute("aria-label", say(WORDS.menu));
    ui.menu.replaceChildren(...[...document.querySelectorAll("#siteMenu nav > a")].map(link => {
      const item = make("a", "", `<span class="ig-mlabel"></span>`);
      item.href = link.getAttribute("href");
      item.querySelector("span").textContent = (link.querySelector(".sr-only") || link).textContent.trim();
      item.classList.toggle("is-current", /#today$/.test(item.getAttribute("href")));
      item.classList.toggle("ig-mhome", link.classList.contains("menu-home")); // 返回首页
      item.dataset.target = item.getAttribute("href").split("#")[1] || "";
      return item;
    }));
    ui.enter.querySelector("span").textContent = say(WORDS.enter);
    el.setAttribute("aria-label", title);
    ui.views.setAttribute("aria-label", say(WORDS.scroll));
    ui.views.querySelectorAll("button").forEach((button, index) => { button.querySelector("span").textContent = say(WORDS.by[index]); });
    ui.scroll.textContent = say(WORDS.scroll);
    ui.about.querySelector("span").textContent = say(WORDS.menu);
    ui.tutorial.textContent = say(WORDS.tutorial);
    ui.home.setAttribute("aria-label", say(WORDS.home));
    ui.cursor.querySelector("span").textContent = say(WORDS.explore);
    ui.dscroll.textContent = say(WORDS.scroll);
    ui.dclose.querySelector("span").textContent = say(WORDS.close);
    ui.dx.setAttribute("aria-label", say(WORDS.close));
    ui.dhome.setAttribute("aria-label", say(WORDS.home));
  }

  /* ---------- Tiles ---------- */
  const gcd = (a, b) => (b ? gcd(b, a % b) : a);
  const pad = n => String(n).padStart(2, "0");
  const cardHTML = item => `
    <div class="ig-face">
      <img class="ig-orn" alt="" src="${item.art}" draggable="false">
      <span class="ig-frame" aria-hidden="true"></span>
      <div class="ig-text">
        <span class="ig-kick">No.${pad(item.index + 1)}<b>${esc(item.theme)}</b></span>
        <h3>${esc(item.title)}</h3>
        <p>${esc(item.summary)}</p>
        <div class="ig-cfoot"><span>${esc(item.source)}</span>${item.href ? `<a href="${esc(item.href)}" target="_blank" rel="noopener noreferrer">${esc(item.linkText)}</a>` : ""}</div>
      </div>
      <i class="ig-tint" aria-hidden="true"></i><i class="ig-flat" aria-hidden="true"></i>
    </div>
    <div class="ig-label" aria-hidden="true"><b>${esc(item.source)}</b><small>${esc(item.date)}</small></div>
    <button class="ig-open sr-only" type="button">${esc(say(WORDS.explore))}：${esc(item.title)}</button>`;
  // per-tile colour (fragment shader: saturation × (1 + sin(id·1210)·.5), brightness + sin(id·743)·.05)
  const tileColor = (rgb, id) => {
    const satF = 1 + Math.sin(id * 1210) * .5, light = Math.sin(id * 743) * .05, lum = rgb[0] * .2125 + rgb[1] * .7154 + rgb[2] * .0721;
    return rgb.map(v => clamp(Math.round(lum + (v - lum) * satF + light * 255), 0, 255)).join(" ");
  };
  function makeCard(u, item, id, props) {
    const element = make("article", "ig-card", cardHTML(item));
    element.dataset.tone = item.tone;
    element.style.setProperty("--tint-rgb", tileColor(u.cfg.color, id));
    u.root.append(element);
    const tile = { el: element, kind: "card", u, item, id, flag: 0, y0: 0, row: 1, th0: 0, base: u.cfg.base, shown: true, la: -1, a: -1, ta: -1, fa: -1, matrix: "",
      tintEl: element.querySelector(".ig-tint"), flatEl: element.querySelector(".ig-flat"), tk: Math.sin(id * 1000) >= -.7 ? 1 : .4,
      vf: Math.abs(Math.sin(id * 86)), sz: Math.sin(id * 181) * 2, ...props };
    u.tiles.push(tile);
    return tile;
  }
  function makeChip(u, id, props) { // decorative tile: only ever seen as a flat colour square (waiting / overview)
    const element = make("i", "ig-chip");
    element.setAttribute("aria-hidden", "true");
    element.style.setProperty("--tint-rgb", tileColor(u.cfg.color, id));
    u.root.append(element);
    const tile = { el: element, kind: "chip", u, id, flag: 0, y0: 0, row: 1, th0: 0, base: u.cfg.base, shown: true, a: -1, matrix: "", vf: 0, sz: 0, ...props };
    u.tiles.push(tile);
    return tile;
  }
  // Every item may be on a ring several times; the copy nearest the front is the one screen readers and the keyboard
  // reach, the repeats stay pointer-only (not inert: inert elements drop out of hit-testing).
  function markPrimaries(u) {
    const best = new Map();
    u.tiles.filter(t => t.kind === "card").forEach(t => { const b = best.get(t.item.index); if (!b || t.front < b.front) best.set(t.item.index, t); });
    u.tiles.filter(t => t.kind === "card").forEach(t => {
      t.primary = best.get(t.item.index) === t;
      t.el.toggleAttribute("aria-hidden", !t.primary);
      t.el.querySelectorAll("a, button").forEach(control => (t.primary ? control.removeAttribute("tabindex") : control.setAttribute("tabindex", "-1")));
    });
  }
  function buildTiles() {
    U.forEach(u => { u.tiles.forEach(t => t.el.remove()); u.extras.forEach(e => e.el.remove()); u.tiles = []; u.extras = []; });
    ui.nlist.replaceChildren();
    const N = items.length;
    if (!N) return;
    // Visuals: 100 slots, 34 / 33 / 33 per ring, column-major (gallery §2.2); the front card of the middle row = item 1
    const V = U[0], ROWS = [{ n: 34, phase: 0, y: 2.125 }, { n: 33, phase: .085, y: 0 }, { n: 33, phase: 0, y: -2.125 }];
    const step = [7, 5, 11, 13, 17, 19, 23].find(k => gcd(k, N) === 1 && (N < 4 || (k % N !== 1 && k % N !== N - 1))) ?? 1;
    for (let t = 1; t <= 100; t += 1) {
      const row = (t - 1) % 3, col = Math.floor((t - 1) / 3), R = ROWS[row], th0 = R.phase + col * TAU / R.n;
      makeCard(V, items[((((t - 50) * step) % N) + N) % N], t, { row, th0, y0: R.y, front: Math.abs(wrapPi(th0 - Math.PI)) + (row === 1 ? 0 : .3) });
    }
    markPrimaries(V);
    // Regions (the reference's Names view, §14.1, by region since 2026-10-29): three rings around the x axis; the middle
    // one holds the items 3.6° apart, grouped by continent (2 of every 3 exist only while open); the side rings (x ∓ .5,
    // 33 each) are decoration seen in waiting / overview. The list beside it names the regions, one row each.
    const T = U[1];
    const order = items.map((item, i) => [item, i]).sort((a, b) => a[0].region - b[0].region || a[1] - b[1]).map(([item]) => item);
    order.forEach((item, c) => makeCard(T, item, c + 1, { row: 1, flag: c % 3 ? 1 : 0, th0: (.978 * Math.PI + (c + 1) * TAU / 100) % TAU, y0: 0, front: c, primary: true }));
    for (const [row, x, seed] of [[0, -.5, 101], [2, .5, 134]]) {
      for (let c = 0; c < 33; c += 1) makeChip(T, seed + c, { row, y0: x, th0: c * TAU / 33 + (Math.sin((seed + c) * 77.7) * .5) * .05 });
    }
    names.groups = [];
    order.forEach((item, c) => {
      const last = names.groups.at(-1);
      if (last && last.region === item.region) last.count += 1; else names.groups.push({ region: item.region, start: c, count: 1 });
    });
    names.groups.forEach((group, g) => {
      group.center = group.start + (group.count - 1) / 2;
      const button = make("button", "ig-name");
      button.type = "button";
      button.dataset.group = g;
      button.innerHTML = `${esc(say(WORDS.regions[group.region]))}<sup>${group.count}</sup>`;
      ui.nlist.append(button);
    });
    // Dates (Extinction, §14.3): built from the date groups; the bottom ring is decoration (waiting / overview only)
    const D = U[2];
    for (let c = 0; c < 33; c += 1) makeChip(D, 300 + c, { row: 2, flag: 1, y0: 0, th0: c * TAU / 33, base: .48 });
    buildDates();
  }
  // Two rows of date groups, ascending; each row's sequence (label, then its cards 0.65 layout units apart) is repeated
  // round the ring at the reference's density (1.153 u of arc per layout unit) — our day has 12 items, theirs 100.
  function buildDates() {
    const D = U[2], groups = new Map();
    items.forEach(item => { const key = item.key || "—"; if (!groups.has(key)) groups.set(key, []); groups.get(key).push(item); });
    const list = [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
    const rows = [[], []];
    let count = 0; // a group goes to the second row once its middle passes half of the items
    list.forEach(group => { (count + group[1].length / 2 <= items.length / 2 ? rows[0] : rows[1]).push(group); count += group[1].length; });
    if (!rows[0].length) rows[0] = rows[1];
    if (!rows[1].length) rows[1] = rows[0];
    D.dateRows = rows.map((groupsInRow, row) => ({ row, groups: groupsInRow, y: row ? -.4 : .4 }));
    let id = 500;
    D.dateRows.forEach(r => {
      r.cards = []; r.labels = [];
      const repeats = 12; // upper bound; layoutDates() uses as many as the ring holds
      for (let k = 0; k < repeats; k += 1) {
        r.groups.forEach(([key, groupItems]) => {
          const label = make("b", "ig-year", `<span>${esc(key.length >= 10 ? `${key.slice(5, 7)}.${key.slice(8, 10)}` : key)}</span>`);
          label.setAttribute("aria-hidden", "true");
          D.root.append(label);
          const extra = { el: label, row: r.row, rep: k, key, th0: 0, shown: true, matrix: "", a: -1 };
          D.extras.push(extra); r.labels.push(extra);
          groupItems.forEach(item => { const t = makeCard(D, item, id += 1, { row: r.row, y0: r.y, rep: k, front: 99 }); r.cards.push(t); });
        });
      }
    });
    layoutDates();
  }
  function layoutDates() {
    const D = U[2], s = view.s || 1;
    if (!D.dateRows) return;
    D.dateRows.forEach(r => {
      // label widths in layout units (their rendered width at the year font size, in world units, over 1.153)
      const width = key => { const e = r.labels.find(l => l.key === key); return e ? Math.max(.6, e.el.firstChild.offsetWidth / s / 1.153) : .8; };
      r.labels.forEach(l => { const w = l.el.offsetWidth, h = l.el.offsetHeight; if (w) l.el.style.margin = `${(-h / 2).toFixed(1)}px 0 0 ${(-w / 2).toFixed(1)}px`; });
      let seq = 0;
      r.groups.forEach(([key, groupItems]) => { seq += .05 + width(key); groupItems.forEach(() => { seq += .65; }); });
      seq += .3;
      const reps = clamp(Math.round(TAU * 10 / (seq * 1.153)), 1, 12), total = seq * reps;
      let t = 0;
      for (let k = 0; k < 12; k += 1) {
        r.groups.forEach(([key, groupItems]) => {
          const L = width(key), label = r.labels.find(l => l.key === key && l.rep === k);
          t += .05;
          if (label) { label.th0 = TAU - TAU * (t + L / 2) / total; label.off = k >= reps; }
          t += L;
          r.cards.filter(c => c.rep === k && c.item && groupItems.includes(c.item)).forEach(card => {
            t += .3; card.th0 = TAU - TAU * t / total; card.off = k >= reps; t += .35;
            card.front = Math.abs(wrapPi(card.th0 + (r.row ? .25 : 0) - Math.PI)) + r.row * .3;
          });
        });
        if (k === reps - 1) t = total * 2; // later repeats are not used
      }
      if (r.row === 1) r.cards.concat(r.labels).forEach(e => { e.th0 += TAU / reps / 2; }); // the second row is offset by half a sequence
    });
    markPrimaries(D);
  }

  /* ---------- Intro (intro §3, §4, §6) ---------- */
  const anim = [];
  const play = (element, keyframes, options) => { const a = element.animate(keyframes, { fill: "both", ...options }); anim.push(a); return a; };
  const rise = (element, at) => play(element, [{ transform: "translate3d(0, 100px, 0)" }, { transform: "none" }], { duration: 1625, delay: at * 1000, easing: CSS_IO });
  const fadeIn = (element, at, duration = 1.625) => play(element, [{ opacity: 0 }, { opacity: 1 }], { duration: duration * 1000, delay: at * 1000, easing: "linear" });
  let counter = { d: 0, revealed: false };
  function startIntro() {
    anim.forEach(a => a.cancel());
    anim.length = 0;
    ui.intro.hidden = false;
    ui.enter.style.visibility = "hidden";
    counter = { d: 0, revealed: false };
    if (reducedMotion.matches) { revealButton(true); return; }
    const S0 = .25; // the content shows .25 s after mount (timeline delay .2 at timeScale .8)
    rise(ui.logo, S0); fadeIn(ui.logo, S0 + .625);
    rise(ui.h1, S0 + .3125); fadeIn(ui.h1, S0 + .9375);
    rise(ui.h2, S0 + .75); fadeIn(ui.h2, S0 + 1.125);
    rise(ui.btnw, S0 + .9375); fadeIn(ui.btnw, S0 + 1.3125);
    fadeIn(ui.credits, S0 + 1.5);
  }
  function revealButton(now = false) {
    if (counter.revealed) return;
    counter.revealed = true;
    ui.percent.textContent = "100";
    ui.enter.style.visibility = "visible";
    if (now) { ui.percent.style.opacity = "0"; return; }
    play(ui.percent, [{ opacity: 1 }, { opacity: 0 }], { duration: 500, easing: "linear" });
    play(ui.enter, [{ opacity: 0 }, { opacity: 1 }], { duration: 700, delay: 400, easing: "linear" });
  }
  function tickCounter(t) { // 3-digit loader count, d += (f − d)·.04 per frame; reveal at ≥ 2 s and data ready
    if (counter.revealed) return;
    const f = dataReady() ? 1 : .62;
    counter.d += (f - counter.d) * .04;
    ui.percent.textContent = String(Math.round(Math.min(counter.d, 1) * 100)).padStart(3, "0");
    if (t >= 2 && f >= 1 && counter.d > .99) revealButton();
  }

  /* ---------- Enter (intro §5, gallery §9, §14.6): T = click + .1 s ---------- */
  function enter(fromKeyboard = false) {
    if (phase !== "intro" || !dataReady()) return;
    if (!items.length) { items = readItems(); words(); buildTiles(); }
    phase = "gallery";
    enteredAt = clock;
    const V = U[0], T = U[1];
    Object.assign(V, { open: 0, close: 0, openRadius: 10, scale: 1, opacity: 1, tint: 1, dark: 1, stagger: 1, globe: 0, overview: 0, waiting: 0, openInt: 0, texts: 0, visited: true });
    Object.assign(V.wrap, { x: 0, y: 0, z: 0, rx: 0, ry: -45 * DEG, rz: 7 * DEG });
    Object.assign(sc, { gz: -10, alpha: 0, bill: 0, pick: 0 });
    tw(sc, "gz", 0, 3.8, { delay: .2 });
    tw(V.wrap, "ry", 0, 4.5, { delay: .2 });
    tw(V.wrap, "rz", 0, 4.5, { delay: .2 });
    tw(camT, "z", -5, 3, { delay: .1 });
    for (const [key, to, d, ease] of [["open", 1, 3, IO], ["stagger", 0, 3, IO], ["tint", 0, 3, LIN], ["dark", 0, 3, IO], ["scale", 1, 3.5, IO]]) tw(V, key, to, d, { ease, delay: .1 });
    tw(sc, "alpha", 1, 1, { ease: LIN, delay: 1.6 });
    ui.bill.textContent = say(WORDS.views[0]);
    tw(sc, "bill", 1, 1, { ease: LIN, delay: 1.6 });
    tw(sc, "bill", 0, 1, { ease: LIN, delay: 2.6 });
    tw(V, "texts", 1, .5, { ease: power2, delay: 1.6 });
    tw(camT, "ix", 5, 2, { ease: power1, delay: 2.1 });
    tw(camT, "iy", 6, 2, { ease: power1, delay: 2.1 });
    tw(V, "openInt", 1, 1, { ease: power2, delay: 2.1 });
    later(2.6, () => { sc.pick = 1; });
    tw(chrome, "foot", 1, .7, { ease: LIN, delay: 4.1 });
    tw(chrome, "head", 1, .7, { ease: LIN, delay: 6.1 });
    openWaiting(T, 0); // the diamonds: the Titles view waiting
    play(ui.content, [{ opacity: 1 }, { opacity: 0 }], { duration: 400, easing: "linear" });
    play(ui.credits, [{ opacity: getComputedStyle(ui.credits).opacity }, { opacity: 0 }], { duration: 400, easing: "linear" });
    setTimeout(() => { if (phase === "gallery") ui.intro.hidden = true; }, reducedMotion.matches ? 0 : 2000);
    ui.gallery.style.visibility = "";
    el.classList.add("is-gallery");
    if (reducedMotion.matches) { enteredAt -= 10; fastForward(); }
    if (fromKeyboard) setTimeout(() => { if (phase === "gallery" && document.activeElement === ui.enter) focusFront(); }, reducedMotion.matches ? 0 : 2600);
  }
  const focusFront = () => U[cur].tiles.filter(t => t.primary).sort((a, b) => a.front - b.front)[0]?.el.querySelector(".ig-open")?.focus({ preventScroll: true });
  // reduced motion: every pending tween (and whatever their calls start) lands now
  function fastForward() {
    const saved = clock;
    for (let guard = 0; tweens.length && guard < 30; guard += 1) { clock += 10; stepTweens(); }
    clock = saved;
  }

  /* ---------- Waiting state (§14.2): the next view as faint flat diamonds ---------- */
  function openWaiting(u, d) {
    const o = { ease: IO };
    u.wOpening = 1;
    tw(u, "wOpening", 0, Math.max(d, .001), { ease: power3out });
    tw(u, "waiting", 1, d, o); tw(u, "scale", u.cfg.wait, d, o); tw(u, "openRadius", 12, d, o); tw(u, "tint", 1, d, o);
    tw(u, "dark", 1, d, o); tw(u, "opacity", .5, d, o); tw(u, "open", 0, d, o); tw(u, "globe", 0, d, o); tw(u, "overview", 0, d, o);
    for (const k of ["x", "y", "z"]) tw(u.wrap, k, 0, d, o);
    tw(u, "texts", 0, d, o);
    if (u.index === 0) { tw(u.wrap, "rx", 0, d, o); tw(u.wrap, "rz", -.25 * Math.PI, d, o); tw(u.rowsY, 0, -1.4, d, o); tw(u.rowsY, 2, 1.4, d, o); }
    if (u.index === 1) { tw(u.wrap, "rz", -.2 * Math.PI, d, o); tw(u.rowsScale, 0, 1, d, o); tw(u.rowsScale, 2, 1, d, o); }
    if (u.index === 2) { tw(u.wrap, "z", -.1, d, o); tw(u.wrap, "ry", mobile() ? .25 : 0, d, o); tw(u.wrap, "rz", .3 * Math.PI, d, o); }
  }

  /* ---------- Switching views (§7, §14.4): close → sphere of tinted squares, camera to +32 → open at 3 s ---------- */
  function switchTo(b) {
    if (changing || detail || b === cur || phase !== "gallery") return;
    changing = true;
    setMenu(false);
    sc.pick = 0;
    setHoverCard(null);
    const A = U[cur], B = U[b], prev = cur;
    tw(chrome, "head", 0, .4, { ease: LIN }); tw(chrome, "foot", 0, .4, { ease: LIN });
    later(.5, () => ui.views.querySelectorAll("button").forEach((button, i) => button.classList.toggle("is-on", i === b)));
    if (A.index === 1) hideNames();
    // old.close()
    tw(A, "open", 0, 2); tw(A, "close", 1, 2);
    tw(camT, "ix", 0, 2, { ease: power1 }); tw(camT, "iy", 0, 2, { ease: power1 });
    tw(camT, "z", 32, 3); tw(camT, "y", 0, 3); tw(camT, "x", 0, 3);
    tw(U[nextOf(prev)], "waiting", 0, 3);
    // every view goes into overview
    U.forEach(u => {
      if (u.waiting < .5 && u.index !== prev) u.opacity = 0;
      tw(u, "tint", 1, 2); tw(u, "dark", 1, 2); tw(u, "scale", u.cfg.ov, 2); tw(u, "opacity", .8, 3, { ease: LIN, delay: .5 });
      tw(u, "overview", 1, 1, { ease: LIN }); tw(u, "globe", 1, 3); tw(u, "openRadius", 10 + u.index * .1, 3);
      [-1.4, .7, -1].forEach((v, i) => tw(u.ovRow, i, v, 3));
      u.ovA = 0; u.ovB = 0;
      tw(u, "ovA", 1, 4, { ease: LIN }); tw(u, "ovB", 1, 2.95, { ease: power3inOut, delay: 2.95 });
      tw(u, "texts", 0, .8, { ease: bezier(.9, 0, .4, 1) });
      if (u.index === 0) { tw(u.wrapOv, "rx", -.3 * Math.PI, 4); tw(u.wrapOv, "rz", .75 * Math.PI, 4); tw(u.offX, 0, u.offX[0] + .4, 3); tw(u.offX, 2, u.offX[2] + .3, 3); tw(u.rowsY, 0, -1.4, 2.5); tw(u.rowsY, 2, 1.4, 2.5); }
      if (u.index === 1) { tw(u.wrapOv, "rx", -.1 * Math.PI, 4); tw(u.wrapOv, "rz", -.3 * Math.PI, 4); tw(u.wrap, "x", 0, 3); tw(u.wrap, "y", 0, 3); tw(u.rowsScale, 0, 1, 3); tw(u.rowsScale, 2, 1, 3); tw(u.rowsY, 0, .9, 3); tw(u.rowsY, 2, -.9, 3); }
      if (u.index === 2) { tw(u.wrapOv, "ry", .15 * Math.PI, 4); tw(u.wrapOv, "rz", .4 * Math.PI, 4); tw(u, "extraY", .25 * Math.PI, 3); tw(u.rowsScale, 0, 1.7, 3); tw(u.rowsScale, 2, 1.7, 3); }
    });
    ui.bill.textContent = say(WORDS.views[b]);
    sc.billDepth = 5;
    tw(sc, "bill", 1, 1.5, { ease: LIN, delay: .5 }); tw(sc, "bill", 0, 1, { ease: LIN, delay: 2.5 });
    later(3, () => {
      cur = b;
      openUniverse(B);
      openWaiting(U[nextOf(b)], 3);
      U.forEach(u => { if (u !== B && u.index !== nextOf(b)) tw(u, "opacity", 0, 2, { ease: LIN, delay: .5 }); });
    });
    later(4.6, () => { changing = false; sc.pick = 1; });
    tw(chrome, "foot", 1, .7, { ease: LIN, delay: 4 });
    tw(chrome, "head", 1, .7, { ease: LIN, delay: 6 });
    if (reducedMotion.matches) fastForward();
  }
  function openUniverse(B) {
    const o = { ease: IO };
    tw(B, "open", 1, 3, o); tw(B, "close", 0, 3, o); tw(B, "tint", 0, 3, { ease: LIN }); tw(B, "dark", 0, 3, o);
    tw(B, "scale", 1, 3.5, o); tw(B, "opacity", 1, 3, { ease: LIN }); tw(B, "globe", 0, 3, o); tw(B, "overview", 0, 3, o);
    tw(B, "waiting", 0, 3, o);
    [0, 1, 2].forEach(i => tw(B.ovRow, i, 0, 3, o));
    tw(camT, "z", B.cfg.camZ, 3, o); tw(camT, "y", 0, 3, o); tw(camT, "x", 0, 3, o);
    for (const k of ["rx", "ry", "rz"]) tw(B.wrap, k, 0, 3, o);
    if (B.index === 0) {
      tw(B, "openRadius", 10.5, 3, o);
      [0, 2].forEach(i => tw(B.rowsY, i, 0, 2.5, o));
      for (const k of ["x", "y", "z"]) tw(B.wrap, k, 0, 3, o);
      tw(B, "texts", 1, .5, { ease: power2, delay: 1.5 });
      tw(camT, "ix", 5, 2, { ease: power1, delay: 2 }); tw(camT, "iy", 6, 2, { ease: power1, delay: 2 });
    }
    if (B.index === 1) {
      tw(B, "openRadius", 10.5, 3, o);
      tw(B.wrap, "x", mobile() ? .4 : 0, 3, o); tw(B.wrap, "y", 0, 3, o); tw(B.wrap, "z", 2, 3, o);
      tw(B.rowsScale, 0, .06, 3, o); tw(B.rowsScale, 2, .06, 3, o);
      [0, 2].forEach(i => tw(B.rowsY, i, 0, 3, o));
      tw(camT, "ix", .5, 1, { ease: power1 }); tw(camT, "iy", .5, 1, { ease: power1 });
      showNames();
    }
    if (B.index === 2) {
      tw(B, "openRadius", 10, 3, o);
      for (const k of ["x", "y", "z"]) tw(B.wrap, k, 0, 3, o);
      tw(B, "extraY", 0, 5, o);
      tw(B.rowsScale, 0, 1, 3, o); tw(B.rowsScale, 2, 1, 3, o);
      tw(B, "texts", 1, .1, { ease: LIN }); B.ink = 0; tw(B, "ink", 1, 3, { delay: 2 });
      tw(camT, "ix", .5, 2, { ease: power1 }); tw(camT, "iy", .5, 2, { ease: power1 });
    }
    B.openInt = 0; tw(B, "openInt", 1, 2, { ease: LIN });
    if (!B.visited) { // first visit: the name shows a second time from open() (§14.4)
      B.visited = true;
      later(1.5, () => { ui.bill.textContent = say(WORDS.views[B.index]); });
      tw(sc, "bill", 1, 1, { ease: LIN, delay: 1.5 }); tw(sc, "bill", 0, 1, { ease: LIN, delay: 2.5 });
    }
  }

  /* ---------- Titles list (§14.1: left 66 % / top 43 %, 32 px / 110 %, pitch 55.2 px, dash fixed) ---------- */
  let namesAnim = [];
  function showNames() {
    namesAnim.forEach(a => a.cancel());
    ui.names.hidden = false;
    const kids = [...ui.nlist.children];
    if (reducedMotion.matches) return;
    namesAnim = [
      ui.names.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 1300, delay: 700, easing: "linear", fill: "both" }),
      ui.nlist.animate([{ translate: `0 ${(.3 * view.H).toFixed(0)}px` }, { translate: "0 0" }], { duration: 2200, delay: 500, easing: CSS_IO, fill: "both" }),
      ...kids.map((kid, i) => kid.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 1300, delay: 900 + Math.min(i, 29) * 100, easing: "linear", fill: "both" })),
    ];
  }
  function hideNames() {
    namesAnim.forEach(a => a.cancel());
    namesAnim = [ui.names.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 400, easing: "linear", fill: "forwards" })];
    namesAnim[0].finished.then(() => { if (cur !== 1 || changing) { ui.names.hidden = true; namesAnim.forEach(a => a.cancel()); } }).catch(() => {});
  }

  /* ---------- Per-frame ---------- */
  // Shard open timeline (intro §2.6), t seconds after the page opened: mesh (0, 0, −.5) → (0, .2, −1.8) and opacity
  // 0 → 1 over 3.5 s cubicInOut; saturation-brightness 1 → .2 over 2 s linear.
  const shardOpen = t => { const e = IO(clamp01(t / 3.5)); return { meshY: .2 * e, meshZ: -.5 - 1.3 * e, O: e, SB: 1 - .8 * clamp01(t / 2) }; };
  function frame(nowMs) {
    raf = requestAnimationFrame(frame);
    const now = nowMs / 1000, raw = Math.max(0, now - lastNow), dt = Math.min(.06, raw);
    lastNow = now;
    clock += raw > .5 ? 1 / 30 : raw; // the tween clock: real time, GSAP lag smoothing (a stall over .5 s counts as one frame)
    stepTweens();
    const t = clock - openedAt, et = now;
    // mouse-look holds while the pointer is on a card, so the card (and its source link) stays under the pointer
    if (finePointer.matches && !hover.next && Math.hypot(look.x - look.hx, look.y - look.hy) > .05) {
      look.hx += (look.x - look.hx) * dt * .35;
      look.hy += (look.y - look.hy) * dt * .35;
    }
    const still = reducedMotion.matches;
    if (phase === "intro") tickCounter(t);
    const te = phase === "gallery" ? clock - enteredAt : -1, T = te - .1;
    const zoom = detail ? detail.zoom : 0, keep = 1 - zoom;
    const cam = {
      x: camT.x + (still ? 0 : Math.sin(et * .24) * .1) * keep, y: camT.y + (still ? 0 : Math.sin(et * .33) * .1) * keep, z: camT.z,
      rx: still ? 0 : look.hy * camT.iy * .05 * keep, ry: still ? 0 : -look.hx * camT.ix * .05 * keep,
    };
    // shards: fly-in from open (3.5 s), close from T (intro §5)
    if (!ui.canvas.hidden) {
      const S = { et, fov: view.fov, cam, ...shardOpen(still ? 99 : t) };
      if (te >= 0) { // close tweens run from the values the open timeline had when they started (GSAP "to")
        const from = shardOpen(still ? 99 : enteredAt + .1 - openedAt);
        const m = 1 - prog(T, 0, 2.7, IO);
        Object.assign(S, { O: from.O * (1 - prog(T, 0, 2, IO)), SB: from.SB + (1 - from.SB) * prog(T, 0, 2), meshY: from.meshY * m, meshZ: from.meshZ * m });
      }
      if (!shards.draw(S) && te >= 0) { shards.clear(); ui.canvas.hidden = true; }
    }
    ui.white.style.opacity = te >= 0 ? prog(T, 0, 2).toFixed(4) : "0";
    if (te >= 0) frameGallery(dt, cam, now);
    frameCursor(now);
  }

  function frameGallery(dt, cam, now) {
    const { W, H, F, s } = view, touch = nav.touch;
    if (detail) tickDetail(dt);
    // chrome and billboard
    ui.gallery.style.opacity = sc.alpha.toFixed(4);
    ui.foot.style.opacity = chrome.foot.toFixed(3); ui.foot.style.visibility = chrome.foot > .001 ? "" : "hidden";
    ui.head.style.opacity = chrome.head.toFixed(3); ui.head.style.visibility = chrome.head > .001 ? "" : "hidden";
    const depth = sc.billDepth + Math.abs(sc.gz) * (changing ? 0 : 1); // it rides with the group during the entrance
    ui.bill.style.opacity = sc.bill.toFixed(3);
    ui.bill.style.transform = `translate(-50%, -50%) scale(${(5 / Math.max(depth, 1)).toFixed(4)})`;
    el.classList.toggle("can-pick", !!sc.pick && !detail && !changing);
    const iv = inputVelocity();
    // navigation of the current view
    nav.imp.x *= .15; nav.imp.y *= .15;
    const k = reducedMotion.matches ? 1 : Math.min(1, dt * (touch ? 4 : 1.5));
    nav.vel.x += (nav.imp.x - nav.vel.x) * k; nav.vel.y += (nav.imp.y - nav.vel.y) * k;
    nav.I += (Math.abs(nav.vel.x) * 40 - nav.I) * (1 - Math.exp(-.5 * dt));
    nav.I *= .95;
    nav.inV = nav.vel.x * 700;
    if (!reducedMotion.matches) nav.uV += (clamp(nav.inV, -10, 10) - nav.uV) * .08 * (touch ? .1 : .7);
    const V = U[0], freeze = 1 - (detail ? detail.zoom : 0);
    [.8, 1, .6].forEach((par, r) => { V.rowsX[r] = (V.rowsX[r] + nav.vel.x * par * freeze) % TAU; });
    if (touch) nav.tilt += nav.vel.y * .5;
    nav.tilt *= .994;
    // Titles wheel: items → rotation, the lead drives the centre magnification
    names.q -= (names.q - names.target) * Math.min(1, dt * (touch ? 4 : 1.5) * (reducedMotion.matches ? 99 : 1));
    names.ds += (Math.min(.99, Math.abs((names.target - names.q) * 3) / 7) - names.ds) * (1 - Math.exp(-4.5 * dt));
    const Tn = U[1], prog100 = names.q / 100;
    [.29, 1, .33].forEach((par, r) => { Tn.rowsX[r] = -prog100 * .99 * TAU * par; });
    names.ga += dt * .29 * .012; names.gb += dt * .33 * .018;
    Tn.rowsX[0] -= names.ga; Tn.rowsX[2] -= names.gb;
    // Dates wheel
    dnav.ps *= .15;
    dnav.is -= (dnav.is - dnav.ps) * Math.min(1, dt * (touch ? 4 : 1.5));
    const D = U[2];
    [.7, 1].forEach((par, r) => { D.rowsX[r] = (D.rowsX[r] + dnav.is * par * freeze) % TAU; });
    // the waiting view turns only while the current one moves (§14.2)
    const wu = U[nextOf(cur)];
    if (iv) WAIT_PAR.forEach((par, i) => { wu.wRows[i] = (wu.wRows[i] + (dt * .03 + wu.wOpening * .005) * par * clamp(iv, -10, 10)) % TAU; });
    if (cur === 1 && !ui.names.hidden) frameNames(dt);
    tickHover(now);
    const Rcam = mul3(rotX(cam.rx), rotY(cam.ry)), RcamT = tr3(Rcam);
    for (const u of U) frameUniverse(u, cam, RcamT, dt, W, H, F, s);
  }

  // One view's tiles: the reference's vertex shader (§3, §14.0) on the CPU, then view space → matrix3d.
  function frameUniverse(u, cam, RcamT, dt, W, H, F, s) {
    const ua = u.opacity * (1 - u.waiting * (1 - u.wto)) - .4 * u.waiting;
    if (ua <= .002 && !(detail && detail.card.u === u)) { if (!u.hidden) { u.hidden = true; u.root.style.visibility = "hidden"; } return; }
    if (u.hidden) { u.hidden = false; u.root.style.visibility = ""; }
    if (u.isCur !== (u.index === cur)) { u.isCur = u.index === cur; u.root.classList.toggle("is-cur", u.isCur); } // only the current view takes the pointer
    const uaR = Math.round(clamp01(ua) * 200) / 200, tintR = Math.round(u.tint * 200) / 200, flatR = Math.round(u.waiting * 200) / 200;
    // the wrapper chases its overview orientation while overview − unprogress lasts (§14.4): the reference's per-frame
    // lerp(rotation, overview, P), no dt — the open/waiting tweens rewrite the same angles every frame, so a factor that
    // followed the frame time made the whole ring shake with every uneven frame (and edge tiles blink in and out)
    const ovP = clamp01(u.ovA - u.ovB);
    if (ovP > 0) for (const k of ["rx", "ry", "rz"]) u.wrap[k] += (u.wrapOv[k] - u.wrap[k]) * ovP;
    let yaw = u.wrap.ry, roll = u.wrap.rz;
    if (detail && detail.card.u === u && u.index === 0) yaw += detail.alpha * detail.zoom; // the cylinder turns the card to the front
    if (u.index === 1) roll += lerp(-2, 2, items.length > 1 ? names.q / (items.length - 1) : 0) * DEG * u.openInt * (1 - u.close); // ±2° across the list
    const tilt = u.index === 0 ? nav.tilt : 0;
    const Rw = mul3(mul3(rotX(u.wrap.rx + tilt), rotY(yaw)), rotZ(roll));
    const B = mul3(RcamT, Rw);
    const Bt = app3(RcamT, u.wrap.x + (u.index === 1 && mobile() ? -.8 : 0) - cam.x, u.wrap.y - cam.y, u.wrap.z + sc.gz - cam.z);
    const oc = u.open * (1 - u.close), V = u.index === 0;
    const spread = V ? [nav.I * 4 * u.openInt, 0, -nav.I * 4 * u.openInt] : [0, 0, 0];
    const picked = detail ? detail.card : null, D = detail;
    const reach = 1.45;
    for (const tile of u.tiles) {
      if (tile.off) { if (tile.shown) { tile.shown = false; tile.el.classList.add("is-off"); } continue; }
      // shader: size, angle, height, radius (gallery §3 / §14.0)
      let vo = 1;
      if (u.index === 1) vo = power2(1 - (tile.flag ? 1 : 0) * (1 - oc));
      if (u.index === 2) vo = power2(1 - (tile.flag ? 1 : 0) * oc);
      let size = tile.base * u.scale * vo * (u.index ? u.rowsScale[tile.row] : 1);
      let theta = tile.th0 + lerp(u.rowsX[tile.row] + u.offX[tile.row] + u.ovRow[tile.row] * u.overview, u.wRows[tile.row], u.waiting) + u.extraY;
      if (V) theta += nav.uV * tile.vf * .01 * (1 - u.waiting);
      let y = tile.y0 + u.rowsY[tile.row] + spread[tile.row];
      let radius = lerp(u.openRadius, u.cfg.radius + (V ? nav.I * 1.2 * u.openInt : 0), oc) + Math.sin(tile.id * 6510) * .01;
      if (V) radius += Math.abs(u.rowsY[tile.row] + spread[tile.row]) * (1 - u.close) * (1 - u.overview) * (1 - u.waiting);
      y = lerp(y, y + Math.sin(tile.id * 150) * 5, u.globe);
      radius = lerp(radius, radius - Math.abs(y) * .5, u.globe);
      const sp = Math.sin(theta), cp = Math.cos(theta);
      let P, rot;
      if (u.index === 1) { // ring around the x axis ('y' is the x offset); faces the axis: rotation −(θ + π) about x
        P = [y, radius * sp, radius * cp];
        rot = rotX(-(theta + Math.PI));
      } else {
        P = [radius * sp, y, radius * cp];
        rot = mul3(rotY(theta - Math.PI), rotX(.1 * y * u.globe));
      }
      if (V && u.stagger) { const st = tile.sz * u.stagger; P = [P[0] + st * Math.sin(theta - Math.PI), P[1], P[2] + st * Math.cos(theta - Math.PI)]; }
      // cull what is behind the camera or off screen
      let t3 = app3(B, P[0], P[1], P[2]);
      t3[0] += Bt[0]; t3[1] += Bt[1]; t3[2] += Bt[2];
      let m = mul3(B, rot);
      let shrink = 1;
      if (D && tile !== picked && tile.u === picked.u && D.others > 0) { // the others shrink away and slide out (1.25 s)
        const len = Math.hypot(t3[0], t3[1]) || 1, push = ss(0, 3, len) * .75 * D.others;
        t3[0] += t3[0] / len * push; t3[1] += t3[1] / len * push;
        shrink = 1 - D.others;
      }
      if (D && tile === picked) ({ t3, m, size } = readingPose(t3, m, size, u));
      const d = -t3[2];
      const sx = t3[0] * F / d, sy = t3[1] * F / d;
      if (u.index === 1 && u === U[cur] && !D) size /= 1 - .35 * (Math.cos(sy / H * Math.PI) * .5 + .5) * ss(.5, 0, Math.abs(sy / H)) * names.ds; // fast wheel: centre magnifies
      if (tile.kind === "card" && hover.card === tile && !D) size *= 1 + .02 * hover.amount;
      size *= shrink;
      const half = reach * size / 1.36 * F / Math.max(d, .01);
      const slack = tile.shown ? 32 : 0; // hysteresis: a tile on screen stays until it is clearly out, so it never blinks at an edge
      const visible = size > .002 && d > (tile.shown ? .5 : .6) && Math.abs(sx) - half < W / 2 + slack && Math.abs(sy) - half * 1.4 < H / 2 + slack;
      if (visible !== tile.shown) { tile.shown = visible; tile.el.classList.toggle("is-off", !visible); }
      if (!visible) continue;
      const k = size / 1.36; // element px are 1.36 world units at scale 1
      const matrix = cssMatrix(m.map(v => +(v * k).toFixed(5)), t3.map(v => +v.toFixed(4)), s, F);
      if (matrix !== tile.matrix) { tile.matrix = matrix; tile.el.style.transform = matrix; }
      // level of detail: under ~46 px on screen a card is only its paper and tint (the sphere, the diamonds), so the
      // browser does not re-rasterise text and ornament at a new scale every frame. Between 46 and 78 px the detail fades
      // with the size (20 steps) instead of switching: a switch while the tint was still thin made the ring flicker as
      // hundreds of cards crossed the line during a view change (2026-10-29)
      const px = size * F / d, lod = tile.kind === "card" ? Math.round(ss(46, 78, px) * 20) / 20 : 1, tiny = lod === 0;
      if (tiny !== tile.tiny) { tile.tiny = tiny; tile.el.classList.toggle("is-tiny", tiny); }
      if (lod !== tile.lod) { tile.lod = lod; if (tile.kind === "card") tile.el.style.setProperty("--lod", lod); }
      if (uaR !== tile.a) { tile.a = uaR; tile.el.style.opacity = uaR; }
      if (tile.kind === "card") {
        const tintA = Math.round(tintR * tile.tk * 200) / 200;
        if (tintA !== tile.ta) { tile.ta = tintA; tile.tintEl.style.opacity = tintA; }
        if (flatR !== tile.fa) { tile.fa = flatR; tile.flatEl.style.opacity = flatR; }
      }
      if (tile.kind !== "card" || !V) continue;
      // the label under a Visuals card: hovered one on a mouse, all on touch; fades toward the screen edges
      const edge = ss(.55, .2, Math.abs(sx / W)) * ss(.55, .2, Math.abs((sy - .62 * size * F / d) / H));
      // reading: the card's label leaves as the page scrolls (phones), so it never lies over the text that rises past it
      const la = D ? (tile === picked ? D.label * (1 - clamp01(dpage.eased / (view.H * .25))) : 0) : (finePointer.matches ? (hover.card === tile ? hover.label : 0) : 1) * edge * u.texts;
      const rounded = Math.round(la * 100) / 100;
      if (rounded !== tile.la) { tile.la = rounded; tile.el.style.setProperty("--la", rounded); }
    }
    if (u.index === 2) frameYears(u, B, Bt, F, s, W, H);
  }

  // Date labels (§14.3): on the ring between the groups, facing the axis, ink about .31 u tall; their colour runs
  // from pale to ink over 3 s from 2 s into open(), and they fade toward the screen edges.
  function frameYears(u, B, Bt, F, s, W, H) {
    const show = u.texts * (1 - u.waiting);
    const ink = Math.round(lerp(233, 17, u.ink)), inkG = Math.round(lerp(238, 26, u.ink)), inkB = Math.round(lerp(243, 36, u.ink));
    const inkColor = `rgb(${ink} ${inkG} ${inkB})`;
    for (const label of u.extras) {
      const row = label.row, r = u.dateRows?.[row];
      let visible = !label.off && show > .01 && !!r;
      let matrix = "", alpha = 0;
      if (visible) {
        const theta = label.th0 + u.rowsX[row] + u.extraY, radius = lerp(u.openRadius, u.cfg.radius, u.open * (1 - u.close));
        const P = [radius * Math.sin(theta), r.y + .04, radius * Math.cos(theta)];
        const t3 = app3(B, P[0], P[1], P[2]);
        t3[0] += Bt[0]; t3[1] += Bt[1]; t3[2] += Bt[2];
        const d = -t3[2], sx = t3[0] * F / d, sy = t3[1] * F / d;
        visible = d > .6 && Math.abs(sx) < W && Math.abs(sy) < H;
        if (visible) {
          matrix = cssMatrix(mul3(B, rotY(theta - Math.PI)).map(v => +v.toFixed(5)), t3.map(v => +v.toFixed(4)), s, F);
          alpha = show * ss(.55, .2, Math.abs(sx / W)) * ss(.55, .2, Math.abs(sy / H));
        }
      }
      if (visible !== label.shown) { label.shown = visible; label.el.classList.toggle("is-off", !visible); }
      if (!visible) continue;
      if (matrix !== label.matrix) { label.matrix = matrix; label.el.style.transform = matrix; }
      const a = Math.round(alpha * 100) / 100;
      if (a !== label.a) { label.a = a; label.el.style.opacity = a; }
      if (inkColor !== label.ink) { label.ink = inkColor; label.el.style.color = inkColor; }
    }
  }

  // The region list follows the wheel: the row of the region the front card belongs to glides to the dash.
  const groupAt = q => { const g = names.groups || [], c = clamp(Math.round(q), 0, Math.max(0, items.length - 1)); let i = 0; while (i < g.length - 1 && c >= g[i + 1].start) i += 1; return i; };
  function frameNames(dt) {
    const pitch = mobile() ? 46.4 : 55.2, current = groupAt(names.q);
    names.rp += (current - names.rp) * (reducedMotion.matches ? 1 : 1 - Math.exp(-dt * 7));
    ui.nlist.style.transform = `translate3d(0, ${(-names.rp * pitch).toFixed(2)}px, 0)`;
    if (current !== names.shown) {
      names.shown = current;
      [...ui.nlist.children].forEach((child, i) => child.classList.toggle("is-on", i === current));
    }
  }

  /* ---------- Reading a card (gallery §6, §14.5) ----------
     Open (zoomProject, real times): chrome out .4 s; the others shrink to 0 and slide outward (1.25 s); the card comes
     to the front — from Visuals the cylinder turns and the camera dollies z −5 → −7.5 to the card's row (1.67 s), from
     the other views the card is carried to the same place — so it stands 494 px square at the centre; a blob sweeps
     its corner from bottom-right to top-left under a white veil (.08–2.41 s); a ghost of its ornament fills the
     background; its label shows under it (1.0–1.42 s); Close at +.9 s, the mark at +1.3 s.
     The page then scrolls by wheel (1:1, .5 s lag): the card rises 3 u and turns 18°, the text blocks swing ±5°.
     Close: everything fades (.8 s) while the camera pushes on 2 u (1.5 s); at 1.0 s the dolly snaps back unseen; at
     1.2 s the view reopens — the camera pulls back (3 s), the other cards wash their tint away (3 s) — and fades in
     from 1.3 s (2 s); chrome at 1.3 s, labels at 2.8 s. */
  let detail = null;
  const dpage = { pos: 0, eased: 0, max: 0 };
  function readingPose(t3, m, size, u) {
    const D = detail;
    let p = u.index === 0 ? 0 : D.zoom; // Visuals gets there by the camera; the others are carried
    const target = [0, 0, -3];
    let tt = [lerp(t3[0], target[0], p), lerp(t3[1], target[1], p), lerp(t3[2], target[2], p)];
    let mm = m.map((v, i) => lerp(v, [1, 0, 0, 0, 1, 0, 0, 0, 1][i], p));
    // the card is the page now (2026-10-29): on a wide screen it comes a little larger (~570 px) to be read
    let sz = lerp(size, 1.36, p) * (1 + (mobile() ? 0 : .16) * D.zoom);
    const k = 0; // (the reference's page scroll lifted the card away; here the wheel scrolls the card's own face)
    if (k > 0) {
      tt = [tt[0] - .5 * k, tt[1] + 3 * k, tt[2] - .5 * k];
      mm = mul3(rotY(-.1 * Math.PI * k), mm);
    }
    return { t3: tt, m: mm, size: sz };
  }
  function warpCard(card, dp) { // §14.5: blob centre (1 − 3dp, 1 − 3dp), radius dp + .6, edges eaten 0.3·D, veil ≤ 50 %
    const c = 1 - 3 * dp, D = (x, y) => ss(dp + .6, 0, Math.hypot(x - c, y - c)) * dp;
    const pts = [[0, 0], [.5, 0], [1, 0], [1, .5], [1, 1], [.5, 1], [0, 1], [0, .5]].map(([x, y]) => {
      const e = .3 * D(x, y);
      return `${((x + (.5 - x) * e * 2) * 100).toFixed(2)}% ${((y + (.5 - y) * e * 2) * 100).toFixed(2)}%`;
    });
    card.face.style.clipPath = dp > .001 && dp < .999 ? `polygon(${pts.join(",")})` : "";
    card.el.style.setProperty("--veil", (ss(.05, .2, D(.5, .5)) * .6).toFixed(3));
    card.el.style.setProperty("--vx", `${(c * 100).toFixed(1)}%`);
  }
  function openDetail(card, fromKeyboard = false) {
    if (detail || phase !== "gallery" || changing) return;
    setMenu(false);
    const u = card.u;
    const th = card.th0 + u.rowsX[card.row] + u.offX[card.row];
    detail = { card, alpha: wrapPi(Math.PI - th), y: card.y0, zoom: 0, others: 0, label: 0, closing: false, camZ: camT.z, camY: camT.y };
    card.face = card.el.querySelector(".ig-face");
    card.el.classList.add("is-read");
    setHoverCard(null);
    nav.imp.x = nav.imp.y = 0;
    const o = { ease: ZOOM };
    tw(detail, "zoom", 1, 1.67, o); tw(detail, "others", 1, 1.25, o);
    if (u.index === 0) { tw(camT, "z", -7.5, 1.67, o); tw(camT, "y", card.y0, 1.67, o); }
    tw(chrome, "head", 0, .4, { ease: LIN }); tw(chrome, "foot", 0, .4, { ease: LIN });
    U.forEach(w => { if (w !== u) tw(w, "wto", 0, 1, { ease: LIN }); });
    detail.dp = 0; tw(detail, "dp", 1, 2.33, { ease: LIN, delay: .08 });
    detail.ghost = 0; tw(detail, "ghost", 1, 2.08, { ease: LIN, delay: .1 });
    detail.page = 0; tw(detail, "page", 1, .5, { ease: LIN, delay: .9 });
    detail.mark = 0; tw(detail, "mark", 1, .8, { ease: LIN, delay: 1.3 });
    const item = card.item;
    ui.ghost.src = item.art;
    // The news is read on the card itself (2026-10-29): as the card grows, the light that sweeps its corner turns
    // it over to a reading face — the title in full, original title, source · date · places, the whole summary, tags
    // and the source link (a new tab). The wheel (or a finger) scrolls the face when the news is longer than the card.
    const record = item.record, zh = !en();
    const places = (record?.places || []).map(place => place.name_zh).filter(Boolean);
    const facts = record ? [...(record.topics || []), ...(record.numbers || []), ...(record.organization_tags || []).map(tag => typeof tag === "string" ? tag : tag.code), ...(record.event_tags || [])].filter(Boolean) : [];
    const original = zh && record?.title_original && record.title_original !== item.title ? record.title_original : "";
    const read = make("div", "ig-read", `
      <p class="ig-rkick">No.${pad(item.index + 1)}<b>${esc(item.theme)}</b><b>${esc(say(WORDS.regions[item.region] || WORDS.regions[0]))}</b></p>
      <h3 class="ig-rtitle">${esc(item.title)}</h3>
      ${original ? `<p class="ig-rorig">${esc(original)}</p>` : ""}
      <p class="ig-rmeta">${esc([item.source, item.date, zh ? places.slice(0, 3).join("、") : ""].filter(Boolean).join(" · "))}</p>
      <p class="ig-rsum">${esc(item.summary)}</p>
      ${facts.length ? `<ul class="ig-rfacts">${[...new Set(facts)].slice(0, 8).map(fact => `<li>${esc(fact)}</li>`).join("")}</ul>` : ""}
      <div class="ig-rfoot">${item.href ? `<a class="ig-rlink" href="${esc(item.href)}" target="_blank" rel="noopener noreferrer">${esc(item.linkText)}</a>` : ""}</div>`);
    card.face.append(read);
    detail.read = read;
    later(reducedMotion.matches ? 0 : 1.05, () => { // under the brightest of the sweep
      if (detail?.read !== read || detail.closing) return;
      card.el.classList.add("is-open");
      ui.dscroll.hidden = read.scrollHeight <= read.clientHeight + 4; // the hint only when there is more to read
    });
    later(reducedMotion.matches ? 0 : 1.8, () => { if (detail?.read === read && !detail.closing) card.el.classList.add("is-crisp"); }); // settled: re-raster sharp
    ui.detail.style.setProperty("--ucol", u.cfg.color.join(" "));
    Object.assign(dpage, { pos: 0, eased: 0, max: 0 });
    ui.detail.hidden = false;
    ui.dscroll.hidden = true;
    el.classList.add("is-reading");
    if (fromKeyboard) setTimeout(() => { if (detail?.card === card && !detail.closing) ui.dclose.focus({ preventScroll: true }); }, 1250);
    if (reducedMotion.matches) fastForward();
  }
  function closeDetail() {
    if (!detail || detail.closing) return;
    const u = detail.card.u, D = detail;
    D.closing = true;
    D.card.el.classList.remove("is-open", "is-crisp"); // the reading face turns back as the card returns
    tw(D, "page", 0, .5, { ease: LIN }); tw(D, "mark", 0, .5, { ease: LIN }); tw(D, "ghost", 0, .8, { ease: LIN });
    tw(sc, "alpha", 0, .8, { ease: LIN });
    tw(camT, "z", camT.z - 2, 1.5);
    D.dp = 0; tw(D, "dp", 1, 3.5, { ease: LIN });
    later(1, () => { D.zoom = 0; D.others = 0; D.label = 0; camT.y = 0; dpage.eased = dpage.pos = 0; });
    later(1.2, () => {
      tw(camT, "z", u.cfg.camZ, 3);
      u.tint = 1; tw(u, "tint", 0, 3, { ease: LIN });
      U.forEach(w => { if (w !== u) tw(w, "wto", 1, 3, { ease: LIN }); });
    });
    tw(sc, "alpha", 1, 2, { ease: LIN, delay: 1.3 });
    tw(chrome, "head", 1, .8, { ease: LIN, delay: 1.3 }); tw(chrome, "foot", 1, .8, { ease: LIN, delay: 1.3 });
    later(4.3, endDetail);
    if (reducedMotion.matches) fastForward();
  }
  function endDetail() {
    if (!detail) return;
    const card = detail.card;
    detail.read?.remove();
    card.el.classList.remove("is-read", "is-open", "is-crisp");
    card.el.style.removeProperty("--veil");
    card.face.style.clipPath = "";
    detail = null;
    ui.detail.hidden = true;
    ui.ghost.style.opacity = "0";
    el.classList.remove("is-reading");
    if (el.contains(document.activeElement) || document.activeElement === document.body) {
      (card.primary ? card : card.u.tiles.find(c => c.primary && c.item === card.item))?.el.querySelector(".ig-open")?.focus({ preventScroll: true });
    }
  }
  function tickDetail(dt) {
    const D = detail, card = D.card;
    warpCard(card, D.dp);
    ui.ghost.style.opacity = (.08 * D.ghost).toFixed(3);
    ui.detail.style.opacity = D.page.toFixed(3);
    ui.detail.style.visibility = D.page > 0 ? "visible" : "hidden";
    ui.dhome.style.opacity = D.mark.toFixed(3);
    // the reading face scrolls (wheel / finger), eased like the reference's page (dt·2, touch 5)
    const read = D.read;
    if (read && !D.closing) {
      dpage.max = Math.max(0, read.scrollHeight - read.clientHeight);
      dpage.pos = clamp(dpage.pos, 0, dpage.max);
      dpage.eased -= (dpage.eased - dpage.pos) * Math.min(1, dt * (nav.touch ? 5 : 2) * (reducedMotion.matches ? 99 : 1));
      if (Math.abs(read.scrollTop - dpage.eased) > .5) read.scrollTop = dpage.eased;
      ui.dscroll.style.opacity = (1 - clamp01(dpage.eased / 80)).toFixed(3);
    }
  }

  /* ---------- Hover (gallery §5): +2 % in .9 s, switching waits for the old one to settle back (.5 s) ---------- */
  const htw = {};
  function hoverTo(key, to, duration, delay, ease = LIN) { htw[key] = { from: hover[key], to, start: clock + delay, duration, ease }; }
  function setHoverCard(card) {
    if (card === hover.next) return;
    hover.next = card;
    el?.classList.toggle("is-pointing", !!card);
    cursor.on = !!card && finePointer.matches;
    if (ui.cursor) {
      ui.cursor.classList.toggle("is-on", cursor.on);
      if (card) ui.cursor.querySelector("span").textContent = card.u.index === 2 ? card.item.title : say(WORDS.explore); // Dates: the title (§14.3)
    }
    if (hover.card && hover.card !== card) { // the old one goes first
      hoverTo("amount", 0, .5, 0, power2); hoverTo("label", 0, .3, .1);
      hover.switchAt = clock + .5;
    } else if (card) {
      hover.card = card; hover.switchAt = 0;
      hoverTo("amount", 1, .9, 0, power2); hoverTo("label", 1, .4, 0);
    }
  }
  function tickHover() {
    if (hover.switchAt && clock >= hover.switchAt) {
      hover.switchAt = 0;
      hover.card = hover.next;
      if (hover.card) { hoverTo("amount", 1, .9, 0, power2); hoverTo("label", 1, .4, 0); }
    }
    for (const key of ["amount", "label"]) {
      const t = htw[key];
      if (!t) continue;
      const p = clamp01((clock - t.start) / t.duration);
      hover[key] = t.from + (t.to - t.from) * t.ease(p);
      if (p >= 1) delete htw[key];
    }
  }

  /* ---------- "Explore" tag: 10 px right / 23 px below the pointer, quickTo .4 s power3 ---------- */
  function moveCursor(x, y) {
    const now = performance.now() / 1000;
    cursor.fx = cursor.x; cursor.fy = cursor.y;
    cursor.tx = x; cursor.ty = y; cursor.start = now;
    if (cursor.x < -50) { cursor.x = cursor.fx = x; cursor.y = cursor.fy = y; }
  }
  function frameCursor(now) {
    const p = power3out(clamp01((now - cursor.start) / .4));
    cursor.x = cursor.fx + (cursor.tx - cursor.fx) * p;
    cursor.y = cursor.fy + (cursor.ty - cursor.fy) * p;
    ui.cursor.style.transform = `translate3d(${cursor.x.toFixed(1)}px, ${cursor.y.toFixed(1)}px, 0)`;
  }

  /* ---------- Input ---------- */
  const tileOf = target => { const e = target?.closest?.(".ig-card"); if (!e) return null; for (const u of U) { const t = u.tiles.find(x => x.el === e); if (t) return t; } return null; };
  function nudgeTo(tile) { // bring a focused card round to the front (keyboard reading order)
    const u = tile.u;
    if (u.index === 1) { names.target = tile.front; return; }
    const phi = wrapPi(tile.th0 + u.rowsX[tile.row] + u.offX[tile.row] + u.extraY - Math.PI);
    if (u.index === 0) nav.imp.x += phi / .176 / [.8, 1, .6][tile.row]; // an impulse a travels .176·a in total
    else dnav.ps += phi / .176 / [.7, 1][tile.row];
  }
  function wire() {
    ui.enter.addEventListener("click", event => enter(event.detail === 0));
    ui.home.addEventListener("click", event => { event.preventDefault(); close(); });
    ui.dhome.addEventListener("click", event => { event.preventDefault(); close(); });
    // 菜单: the site menu drops down here (cop31.css's drop-down, redrawn in intel.css). 今日情报 is this page; any
    // other page closes the layer first and then goes there the way the page menu does (its own transition included).
    ui.about.addEventListener("click", () => setMenu(!el.classList.contains("menu-on")));
    ui.menu.addEventListener("click", event => {
      const item = event.target.closest("a");
      if (!item || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
      event.preventDefault();
      setMenu(false);
      if (item.dataset.target === "today") return;
      pendingNav = document.querySelector(`#siteMenu nav > a[href$="#${CSS.escape(item.dataset.target)}"]`);
      close();
    });
    el.addEventListener("pointerdown", event => { if (el.classList.contains("menu-on") && !event.target.closest(".ig-menu, .ig-about")) setMenu(false); }, true);
    ui.views.addEventListener("click", event => { const button = event.target.closest("[data-view]"); if (button) switchTo(Number(button.dataset.view)); });
    // a region turns the wheel to its first card (the cards open the briefs)
    const toGroup = button => { const group = names.groups[Number(button?.dataset.group)]; if (group) names.target = group.start; };
    ui.nlist.addEventListener("click", event => { if (cur === 1 && !changing) toGroup(event.target.closest(".ig-name")); });
    ui.nlist.addEventListener("focusin", event => toGroup(event.target.closest(".ig-name")));
    el.addEventListener("pointermove", event => {
      look.x = event.clientX / innerWidth * 2 - 1;
      look.y = -event.clientY / innerHeight * 2 + 1;
      if (event.pointerType === "mouse") moveCursor(event.clientX + 10, event.clientY + 23);
      if (!pointerDown || phase !== "gallery") return;
      const dx = event.clientX - pointerDown.x, dy = event.clientY - pointerDown.y;
      pointerDown.x = event.clientX; pointerDown.y = event.clientY;
      pointerDown.total += Math.abs(dx) + Math.abs(dy);
      if (pointerDown.total > 6) dragged = true;
      const k = event.pointerType === "mouse" ? .01 : .015;
      nav.touch = event.pointerType !== "mouse";
      if (detail) { if (!detail.closing) dpage.pos = clamp(dpage.pos - dy * (nav.touch ? 2 : 3), 0, dpage.max); return; }
      if (changing) return;
      if (cur === 0) { nav.imp.x = -dx * k; nav.imp.y = clamp(-dy * k, -.2, .2); }
      if (cur === 1) names.target = clamp(names.target - dy * k, 0, items.length - 1);
      if (cur === 2) dnav.ps = -dx * k;
    });
    el.addEventListener("pointerdown", event => {
      if (phase !== "gallery" || event.button !== 0 || event.target.closest(".ig-head, .ig-foot, .ig-names, a, button")) return;
      pointerDown = { x: event.clientX, y: event.clientY, total: 0 };
      dragged = false;
      nav.touch = event.pointerType !== "mouse";
    });
    addEventListener("pointerup", () => { pointerDown = null; });
    addEventListener("pointercancel", () => { pointerDown = null; });
    el.addEventListener("pointerleave", () => { el.classList.add("is-away"); setHoverCard(null); });
    el.addEventListener("pointerenter", () => el.classList.remove("is-away"));
    ui.stage.addEventListener("pointerover", event => {
      if (!el.classList.contains("can-pick") || !finePointer.matches) return;
      const tile = tileOf(event.target);
      setHoverCard(tile && tile.u === U[cur] && tile.kind === "card" ? tile : null);
    });
    ui.stage.addEventListener("pointerout", event => { if (!tileOf(event.relatedTarget)) setHoverCard(null); });
    // a drag or a moving view never opens anything (click guards: Visuals |v| < 1.5, Titles lead < .5, Dates |v| < 1.5)
    ui.stage.addEventListener("click", event => {
      const moving = cur === 0 ? Math.abs(nav.inV) >= 1.5 : cur === 1 ? Math.abs(names.target - names.q) >= .5 : Math.abs(dnav.is * 700) >= 1.5;
      if (dragged || (event.detail !== 0 && moving)) { event.preventDefault(); event.stopPropagation(); }
    }, true);
    ui.stage.addEventListener("click", event => {
      const tile = tileOf(event.target);
      if (!tile || tile.u !== U[cur] || (event.target.closest("a") && !event.target.closest(".ig-open"))) return; // the source link opens the source
      if (event.detail !== 0 && !el.classList.contains("can-pick")) return;
      openDetail(tile, event.detail === 0);
    });
    ui.dclose.addEventListener("click", closeDetail);
    ui.gallery.addEventListener("click", event => { if (detail && !detail.closing && event.target === ui.gallery) closeDetail(); }); // a click beside the card
    ui.dx.addEventListener("click", closeDetail);
    ui.stage.addEventListener("dragstart", event => event.preventDefault());
    ui.stage.addEventListener("focusin", event => { const tile = tileOf(event.target); if (tile && tile.u === U[cur]) nudgeTo(tile); });
    addEventListener("resize", () => { if (built) { measure(); if (detail) dpage.max = Math.max(0, ui.dcontent.offsetHeight - view.H); } });
    addEventListener("popstate", () => { if (phase !== "closed" && pushed && !history.state?.greenIntel) { pushed = false; close(true); } });
  }

  /* ---------- Page-level input while the layer is open ----------
     Registered at load in the capture phase, so they run before cop31.js's window listeners (the sheet over the stage,
     the rubber band, the sheet keys) and keep those from acting on the page underneath. */
  addEventListener("wheel", event => {
    if (phase === "closed" || document.querySelector("dialog[open]")) return;
    event.stopPropagation();
    event.preventDefault();
    if (phase !== "gallery" || event.ctrlKey || !event.deltaY) return;
    const dy = event.deltaY * (event.deltaMode === 1 ? 33 : event.deltaMode === 2 ? innerHeight : 1);
    nav.touch = false;
    if (detail) { if (!detail.closing) dpage.pos = clamp(dpage.pos + dy, 0, dpage.max); return; }
    if (changing) return;
    if (cur === 0) nav.imp.x += dy * .001;
    if (cur === 1) names.target = clamp(names.target + dy * .002, 0, Math.max(0, items.length - 1)); // 500 px per item
    if (cur === 2) dnav.ps += dy * .001;
  }, { passive: false, capture: true });
  addEventListener("keydown", event => {
    if (phase === "closed" || document.querySelector("dialog[open]")) return;
    event.stopPropagation();
    if (event.key !== "Escape") return;
    event.preventDefault();
    if (el.classList.contains("menu-on")) { setMenu(false); ui.about.focus({ preventScroll: true }); return; }
    if (detail && !detail.closing) closeDetail(); else if (!detail) close();
  }, true);

  /* ---------- Open / close ---------- */
  function resetScene() {
    tweens.length = 0;
    U.forEach(u => Object.assign(u, {
      open: 0, close: 0, openRadius: 10, scale: 1, opacity: 0, tint: 1, dark: 1, stagger: 0, globe: 0, overview: 0, ovRow: [0, 0, 0],
      waiting: 0, wOpening: 0, wRows: [0, 0, 0], rowsX: [0, 0, 0], rowsY: [0, 0, 0], rowsScale: [1, 1, 1], offX: [0, 0, 0],
      wrap: { x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0 }, wrapOv: { rx: 0, ry: 0, rz: 0 }, ovA: 0, ovB: 0, openInt: 0, texts: 0, ink: 0,
      extraY: 0, wto: 1, visited: false, hidden: false,
    }));
    Object.assign(camT, { x: 0, y: 0, z: 0, ix: 0, iy: 0 });
    Object.assign(sc, { gz: -10, alpha: 0, bill: 0, billDepth: 5, pick: 0 });
    Object.assign(chrome, { head: 0, foot: 0 });
    Object.assign(nav, { imp: { x: 0, y: 0 }, vel: { x: 0, y: 0 }, I: 0, uV: 0, inV: 0, tilt: 0 });
    Object.assign(names, { target: 0, q: 0, ds: 0, ga: 0, gb: 0, rp: 0, shown: -1 });
    Object.assign(dnav, { ps: 0, is: 0 });
    cur = 0; changing = false;
    ui.views.querySelectorAll("button").forEach((button, i) => button.classList.toggle("is-on", i === 0));
    ui.names.hidden = true;
    tw(camT, "ix", .5, 2, { ease: power1 }); tw(camT, "iy", .5, 2, { ease: power1 }); // intro pointer tilt (intro §2.5)
  }
  function open(link = null, { instant = false } = {}) {
    if (phase !== "closed") return true;
    build();
    items = dataReady() ? readItems() : [];
    words();
    if (detail) endDetail();
    resetScene();
    buildTiles();
    // The intro stands on the site's own grey-blue ground (a copy of the fixed background, contours included).
    const ground = document.querySelector(".page-bg")?.cloneNode(true);
    ui.ground.replaceChildren(...(ground ? [ground] : []));
    phase = "intro";
    lastNow = performance.now() / 1000;
    openedAt = clock;
    Object.assign(hover, { card: null, next: null, amount: 0, label: 0, switchAt: 0 });
    el.classList.remove("is-gallery", "can-pick", "is-pointing", "is-reading");
    ui.canvas.hidden = false;
    ui.gallery.style.visibility = "hidden";
    ui.gallery.style.opacity = "0";
    ui.head.style.opacity = ui.foot.style.opacity = ui.bill.style.opacity = "0";
    ui.head.style.visibility = ui.foot.style.visibility = "hidden";
    ui.white.style.opacity = "0";
    el.hidden = false;
    measure();
    startIntro();
    gone = [...document.body.children].filter(child => child !== el && child.matches(".rail, .dock, main, footer, .mobile-menu"));
    gone.forEach(child => { child.inert = true; });
    root.classList.add("intel-open");
    if (!instant && !history.state?.greenIntel) { history.pushState({ ...(history.state || {}), greenIntel: true }, ""); pushed = true; }
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(frame);
    if (!instant && !reducedMotion.matches && link?.classList.contains("stamp")) slideIn();
    setTimeout(() => el.focus({ preventScroll: true }), 0);
    // the button waits for the data; the count tells how many cards there will be
    if (!dataReady()) {
      const grid = $("todayGrid");
      const watch = new MutationObserver(() => {
        if (!dataReady() || phase === "closed") return;
        watch.disconnect();
        items = readItems(); words(); buildTiles();
      });
      if (grid) watch.observe(grid, { childList: true });
    }
    return true;
  }
  // From a stamp the intro arrives the way a stamp's page does: a sheet sliding up (spring k 220 c 24, .48 s).
  function slideIn() {
    const w = Math.sqrt(220), z = 24 / (2 * w), wd = w * Math.sqrt(1 - z * z);
    const at = t => 1 - Math.exp(-z * w * t) * (Math.cos(wd * t) + z * w / wd * Math.sin(wd * t));
    const travel = innerHeight + 48, frames = [], shade = [];
    for (let i = 0; i <= 29; i += 1) {
      const p = i === 29 ? 1 : at(i / 29 * .48);
      frames.push({ transform: `translateY(${((1 - p) * travel).toFixed(1)}px)` });
      shade.push({ opacity: clamp01(p).toFixed(3) });
    }
    const backdrop = make("div", "jump-backdrop");
    document.body.append(backdrop);
    el.classList.add("is-sliding");
    el.animate(frames, { duration: 480, easing: "linear" });
    backdrop.animate(shade, { duration: 480, easing: "linear", fill: "forwards" }).finished.then(() => {
      backdrop.remove();
      el.classList.remove("is-sliding");
    });
  }
  function close(fromHistory = false) {
    if (phase === "closed" || el.classList.contains("is-leaving")) return;
    if (!fromHistory && pushed && history.state?.greenIntel) { history.back(); return; } // popstate closes
    el.classList.add("is-leaving");
    const finish = () => {
      phase = "closed";
      cancelAnimationFrame(raf);
      el.hidden = true;
      el.classList.remove("is-leaving");
      anim.forEach(a => a.cancel());
      if (detail) endDetail();
      gone.forEach(child => { child.inert = false; });
      gone = [];
      root.classList.remove("intel-open");
      setHoverCard(null);
      setMenu(false);
      if (location.hash === "#today") history.replaceState(history.state, "", `${location.pathname}${location.search}`);
      document.querySelector('.rail-menu a[href$="#today"], .stamp[data-stamp="today"]')?.focus?.({ preventScroll: true });
      if (pendingNav) { const link = pendingNav; pendingNav = null; requestAnimationFrame(() => link.click()); } // the page picked in 菜单
    };
    if (reducedMotion.matches) { finish(); return; }
    const leave = el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 500, easing: "linear", fill: "forwards" });
    leave.finished.then(() => { finish(); leave.cancel(); }); // the fill must not outlive the hidden layer (it would keep a reopened one invisible)
  }

  window.GreenIntel = {
    ready: () => !document.querySelector("#todayGrid > .empty"),
    open: (link, options) => open(link, options),
  };
  const boot = () => { if (location.hash === "#today") open(null, { instant: true }); };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", boot) : boot();
})();
