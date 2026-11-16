/* GREEN · COP31 — 全球事件地图 as the 融观 globe (2026-11-10, user: 把全球事件现场的地球改为参考的「融观地球」的一模一样的样式，
   点击某个地点，再蹦出新闻). This small script only decides when to fetch it: the globe is three.js (≈ 190 KB compressed)
   plus two textures and the land outlines, so it is not part of the first screen's download — it is imported
   (cop31/atlas/main.js, ES modules) once the home page has loaded and is idle, or when the visitor comes to the home
   page from another one. Until then #map.atlas-wait holds the dark card's place; if the import or WebGL 2 fails the
   class goes and the block is app.js's flat map with its note, as before the globe. Replaces cop31/globe.js. */
(() => {
  "use strict";
  const section = document.getElementById("map"), host = document.getElementById("mapCanvas");
  if (!section || !host || !window.WebGL2RenderingContext) return;
  const root = document.documentElement;
  section.classList.add("atlas-wait");
  let started = false;
  // The modules import each other three levels deep: over a slow link that is one round trip per level, so everything
  // the globe needs is asked for at once (module preloads, the two textures, the land outlines) before the import.
  const base = new URL("./cop31/atlas/", document.baseURI);
  const hint = (rel, path, as) => {
    const link = document.createElement("link");
    link.rel = rel; link.href = new URL(path, base).href;
    if (as) link.as = as;
    link.crossOrigin = "anonymous";
    document.head.append(link);
  };
  const start = () => {
    if (started) return;
    started = true;
    ["main.js?v=20261110-min", "atlas-view.js", "i18n.js", "detail-map.js", "immersive-stage.js", "satellite-layer.js", "regional-layer.js",
      "detailed-basemap.js", "smooth-map-zoom.js", "globe.js", "materials.js", "globe-materials.js", "unfold-surface.js",
      "vendor/three/three.module.js", "vendor/three/three.core.js", "vendor/three/OrbitControls.js"].forEach(path => hint("modulepreload", path));
    hint("preload", "geography/countries.json", "fetch");
    hint("preload", "assets/earth.jpg", "image");
    hint("preload", "assets/clouds.jpg", "image");
    import(new URL("./cop31/atlas/main.js?v=20261110-min", document.baseURI).href)
      .then(atlas => atlas.boot())
      .catch(error => { console.warn("atlas: the globe did not start, the flat map stays", error); section.classList.remove("atlas-wait", "atlas-on"); });
  };
  const onHome = () => !root.dataset.page || root.dataset.page === "home";
  const soon = () => { if (!onHome() || started) return; "requestIdleCallback" in window ? requestIdleCallback(start, { timeout: 2500 }) : setTimeout(start, 600); };
  addEventListener("cop31:page", () => setTimeout(soon, 0));
  document.readyState === "complete" ? soon() : addEventListener("load", soon, { once: true });
})();
