/* Policy goals are distinct from observations. No synthetic completion scores. */
(() => {
  "use strict";
  let promise;
  const filters = {region: "", theme: "", year: "", query: ""};
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const url = value => {try {const u = new URL(value); return u.protocol === "https:" ? esc(u.href) : "#";} catch {return "#";}};
  const regions = {"北京市":"Beijing", "天津市":"Tianjin", "河北省":"Hebei"};
  const statuses = {
    awaiting_observation: ["实绩待核验","Actual result awaiting verification"],
    tracking: ["进展追踪","Progress observation"],
    preliminary_met: ["初步达到目标","Preliminary: target met"],
    preliminary_below: ["初步数据低于目标","Preliminary: below target"],
    met: ["达到目标值","Target value met"], below: ["低于目标值","Below target value"]
  };
  async function mount(root, language) {
    if (!root) return;
    const en = language === "en", t = (zh, english) => en ? english : zh;
    root.innerHTML = "<p role='status'>" + t("正在加载目标追踪…", "Loading targets…") + "</p>";
    try {
      promise ||= fetch("./data/bth_target_tracker.json", {cache: "no-cache"}).then(r => {if (!r.ok) throw new Error("tracker"); return r.json();}).catch(e => {promise = null; throw e;});
      const payload = await promise;
      if (!root.isConnected) return;
      const all = payload.records || [];
      const option = (key, values, labels = {}) => `<label><span>${esc(t({region:"地区",theme:"领域",year:"目标年份"}[key],{region:"Region",theme:"Theme",year:"Target year"}[key]))}</span><select data-target-filter="${key}"><option value="">${t("全部","All")}</option>${values.map(v => `<option value="${esc(v)}" ${filters[key] === String(v) ? "selected" : ""}>${esc(labels[v] || v)}</option>`).join("")}</select></label>`;
      const themes = Object.fromEntries(all.map(r => [r.theme_zh, en ? r.theme_en : r.theme_zh]));
      const render = () => {
        const rows = all.filter(r => (!filters.region || r.region === filters.region) && (!filters.theme || r.theme_zh === filters.theme) && (!filters.year || String(r.year) === filters.year) && (!filters.query || `${r.title_zh} ${r.title_en} ${r.wording_zh} ${r.source.title}`.toLowerCase().includes(filters.query.toLowerCase())))
          .sort((a, b) => a.region.localeCompare(b.region,"zh-CN") || b.year - a.year || a.id.localeCompare(b.id));
        root.innerHTML = `<section class="bth-target-tracker" aria-label="Target Tracker">
          <div class="bth-tool-heading"><p class="overline">TARGET TRACKER</p><h3>${t("京津冀绿色转型目标追踪","BTH green-transition targets")}</h3></div>
          <div class="bth-target-filters">${option("region",Object.keys(regions),en ? regions : {})}${option("theme",Object.keys(themes),themes)}${option("year",[...new Set(all.map(r => String(r.year)))].sort().reverse())}<label><span>${t("检索","Search")}</span><input data-target-filter="query" value="${esc(filters.query)}" placeholder="${t("指标或政策名称","Metric or policy title")}"></label><span class="bth-target-count" role="status">${rows.length} ${t("项目标","targets")}</span></div>
          <div class="bth-target-table-wrap"><table class="bth-target-table"><thead><tr><th>${t("地区与指标","Region and metric")}</th><th>${t("政策目标","Policy target")}</th><th>${t("实际进展","Observed progress")}</th><th>${t("原文依据","Evidence")}</th></tr></thead><tbody>${rows.map(r => {
            const actual = r.observation, status = statuses[r.assessment] || statuses.awaiting_observation;
            const units = {"%":"%","万千瓦":"10,000 kW","万平方米":"10,000 m²","万立方米":"10,000 m³"};
            return `<tr data-target-id="${esc(r.id)}"><td><span class="bth-target-region">${esc(en ? regions[r.region] : r.region)}</span><b>${esc(en ? r.title_en : r.title_zh)}</b><span>${esc(en ? r.theme_en : r.theme_zh)}</span></td>
              <td><time>${r.year}</time><strong>${esc(en ? r.wording_en : r.wording_zh)}</strong>${r.baseline_year ? `<span>${t("基期","Baseline")}: ${r.baseline_year}</span>` : ""}</td>
              <td><span class="bth-target-assessment ${r.assessment.startsWith("preliminary") ? "preliminary" : ""}">${esc(status[en ? 1 : 0])}</span>${actual ? `<b>${actual.year}: ${actual.value}${esc(en ? units[actual.unit] || actual.unit : actual.unit)}</b><a href="${url(actual.source.url)}" target="_blank" rel="noopener noreferrer">${esc(t("进展来源","Progress source"))} ↗</a>` : "<span>—</span>"}</td>
              <td><a href="${url(r.source.url)}" target="_blank" rel="noopener noreferrer">${esc(r.source.title)} ↗</a><span>${esc(r.source.date)}</span><details><summary>${t("口径与条款","Definition and provision")}</summary><p>${esc(r.scope)}</p><p>${esc(r.excerpt)}</p><p>${esc(r.locator)} · ${t("核验日期","Reviewed")}: ${esc(r.reviewed_at)}</p>${r.source.source_type === "official_policy_explanation" ? `<p>${t("来源类型：主管部门公开解读","Source: official departmental policy explanation")}</p>` : ""}</details></td></tr>`;
          }).join("") || `<tr><td colspan="4">${t("无匹配目标","No matching targets")}</td></tr>`}</tbody></table></div>
          <details class="bth-tracker-method"><summary>${t("追踪口径与分类参考","Definitions and classification reference")}</summary><p>${t("目标值不等于实际值。只有地区、指标、单位、基期与统计范围一致时才比较。超过目标年份但未取得可比实绩的项目保留“实绩待核验”，不判断未达标。“左右”类目标不设任意容差，初步统计不标作最终结论。","Policy targets are not observations. Comparisons require matching region, metric, unit, baseline and scope. Missing results do not establish failure. Approximate targets have no arbitrary tolerance; preliminary data are not final findings.")}</p><a href="${url(payload.reference?.url)}" target="_blank" rel="noopener noreferrer">China Climate Target Tracker · PKU</a><span> · ${t("目标条款核验","Policy targets reviewed")}: ${esc(payload.reviewed_at)}</span></details>
        </section>`;
        root.querySelectorAll("[data-target-filter]").forEach(control => {
          const update = () => {filters[control.dataset.targetFilter] = control.value; render();};
          control.addEventListener("change",update);
          if (control.tagName === "INPUT") control.addEventListener("keydown",e => {if (e.key === "Enter") {e.preventDefault();update();}});
        });
      };
      render();
    } catch {if (root.isConnected) root.innerHTML = `<p role="status">${t("目标追踪暂未加载。","Could not load targets.")}<button type="button" class="secondary bth-target-retry">${t("重试","Retry")}</button></p>`; root.querySelector(".bth-target-retry")?.addEventListener("click",()=>mount(root,language));}
  }
  window.GruenBthTracker = {mount};
})();
