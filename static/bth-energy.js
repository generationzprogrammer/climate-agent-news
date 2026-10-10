/* Canonical observations are shared by database, monitor and research assistant. */
(() => {
  "use strict";
  let promise;
  const state = {tab:"latest", region:"", metric:"pv_capacity", dimension:"", year:"", query:"", visible:30};
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const link = value => {try {const u=new URL(value); return u.protocol === "https:" ? esc(u.href) : "#";} catch {return "#";}};
  const number = value => new Intl.NumberFormat("zh-CN",{maximumFractionDigits:4}).format(value);
  async function mount(root, language="zh") {
    if (!root) return;
    const en=language === "en", t=(zh,english)=>en?english:zh;
    root.innerHTML=`<p role="status">${t("正在加载能源统计…","Loading energy statistics…")}</p>`;
    try {
      promise ||= fetch("./data/bth_energy_database.json",{cache:"no-cache"}).then(r=>{if(!r.ok)throw Error("data");return r.json();}).catch(e=>{promise=null;throw e;});
      const data=await promise;
      if(!root.isConnected)return;
      const byId=new Map(data.records.map(r=>[r.id,r]));
      const regionName=r=>en?(data.regions.find(x=>x.zh===r)?.en || r):r;
      const option=(key,values,empty)=>`<select data-energy-filter="${key}" aria-label="${esc(empty)}"><option value="">${esc(empty)}</option>${values.map(v=>`<option value="${esc(v.id)}" ${String(state[key])===String(v.id)?"selected":""}>${esc(v.label)}</option>`).join("")}</select>`;
      const regionOptions=data.regions.map(r=>({id:r.zh,label:en?r.en:r.zh}));
      const indicators=data.indicators || [];
      const selectedIndicator=()=>indicators.find(i=>i.metric===state.metric) || indicators[0];
      const actualLabel=r=>en?({pv_capacity:"Solar PV capacity",power_society:"Electricity consumption",population:"Resident population",gdp_current:"GDP (current prices)",nev_stock:"NEV stock",power_residential_society:"Residential electricity use",re_capacity_share_local:"Local renewable capacity share"}[r.metric] || r.label):r.label;
      const unit=r=>en?({"万千瓦":"10,000 kW","亿千瓦时":"100 million kWh","万人":"10,000 people","亿元":"100 million CNY","万辆":"10,000 vehicles"}[r.unit]||r.unit):r.unit;
      const recordLink=r=>`<button type="button" class="bth-energy-record-link" data-energy-record="${esc(r.id)}">${esc(t("查看记录","View record"))} ↗</button>`;
      const sourceLink=r=>`<a href="${link(r.source.url)}" target="_blank" rel="noopener noreferrer">${esc(r.source.publisher)} ↗</a>`;
      const render=()=>{
        const latest=indicators.map(i=>({i,rows:i.latest_ids.map(id=>byId.get(id)).filter(r=>r&&(!state.region||r.region===state.region))}));
        const future=(data.targets||[]).filter(r=>r.year>=Number(data.generated_at.slice(0,4))&&(!state.region||r.region===state.region));
        const filtered=data.records.filter(r=>(!state.region||r.region===state.region)&&(!state.dimension||r.dimension===state.dimension)&&(!state.year||String(r.year)===state.year)&&(!state.query||`${r.id} ${r.label} ${r.metric} ${r.unit} ${r.source.title} ${r.source.publisher} ${r.notes||""}`.toLowerCase().includes(state.query.toLowerCase())))
          .sort((a,b)=>b.year-a.year||a.region.localeCompare(b.region,"zh-CN")||a.label.localeCompare(b.label,"zh-CN"));
        const health=data.updates.health || [], check=data.updates.last_successful_check_at;
        const content=state.tab==="latest"?`<div class="bth-energy-cards">${latest.filter(x=>x.rows.length).map(({i,rows})=>`<article><h4>${esc(en?i.en:i.zh)}</h4>${rows.map(r=>`<div class="bth-energy-value"><span>${esc(regionName(r.region))}<time>${r.period}${r.status==="preliminary"?" · "+t("初步","preliminary"):""}</time></span><strong>${number(r.value)}<small>${esc(unit(r))}</small></strong>${recordLink(r)}</div>`).join("")}</article>`).join("")}</div>`:
          state.tab==="history"?`<div class="bth-energy-history"><label>${t("比较指标","Comparison metric")}<select data-energy-metric>${indicators.map(i=>`<option value="${esc(i.metric)}" ${selectedIndicator()?.metric===i.metric?"selected":""}>${esc(en?i.en:i.zh)}</option>`).join("")}</select></label><h4>${esc(en?selectedIndicator()?.en:selectedIndicator()?.zh)} · ${esc(unit(byId.get(selectedIndicator()?.history_ids[0])||{}))}</h4><div id="bthEnergyHistoryChart" class="bth-energy-chart"></div><div class="bth-energy-history-links">${(selectedIndicator()?.history_ids||[]).map(id=>byId.get(id)).filter(r=>r&&(!state.region||r.region===state.region)).map(r=>`<span>${esc(regionName(r.region))} ${r.year}：${number(r.value)} ${esc(unit(r))} ${recordLink(r)}</span>`).join("")}</div></div>`:
          `<div class="bth-energy-goals">${future.map(r=>`<article><div>${esc(regionName(r.region))} · ${r.year} · ${t("政策目标","Policy target")}</div><h4>${esc(en?r.title_en:r.title_zh)}</h4><strong>${esc(en?r.wording_en:r.wording_zh)}</strong><a href="${link(r.source.url)}" target="_blank" rel="noopener noreferrer">${esc(r.source.title)} ↗</a></article>`).join("")}</div>`;
        root.innerHTML=`<section class="bth-energy-monitor"><div class="bth-energy-heading"><div><p class="overline">CARBON NEUTRALITY MONITOR</p><h3>${t("京津冀碳中和进程监视器","BTH carbon-neutrality progress monitor")}</h3></div>${option("region",regionOptions,t("全部地区","All regions"))}</div>
          <div class="bth-energy-tabs" role="group" aria-label="${t("监视器视图","Monitor view")}">${[["latest","最新实绩","Latest observations"],["history","历史比较","Historical comparison"],["future","未来目标","Future targets"]].map(([id,zh,english])=>`<button type="button" data-energy-tab="${id}" aria-pressed="${state.tab===id}" class="${state.tab===id?"active":""}">${t(zh,english)}</button>`).join("")}</div>${content}
          ${state.tab==="latest"&&(data.recent_records||[]).length?`<h4>${t("最新月度发布","Recent monthly observations")}</h4><div class="bth-energy-cards">${data.recent_records.map(id=>byId.get(id)).filter(r=>!state.region||r.region===state.region).map(r=>`<article><h4>${esc(r.label)}</h4><div>${esc(regionName(r.region))} · ${esc(r.period)} · ${t("年内累计","Year to date")}</div><strong>${number(r.value)} ${esc(unit(r))}</strong> ${recordLink(r)}</article>`).join("")}</div>`:""}
          <details class="bth-energy-refresh"><summary>${t("更新记录与统计口径","Updates and definitions")} · ${check?esc(check.slice(0,10)):t("尚无成功联网核查记录","No successful online check recorded")}</summary><p>${t("每周核查官方发布。页面显示最新已公布数据的所属期；核查时间不是数据所属期。未来仅列政策目标，不插值、不预测，也不计算缺乏同口径排放依据的碳中和完成率。","Official releases are checked weekly. Observation period is not the check date. Future values are policy targets, not forecasts. No invented emissions or neutrality scores.")}</p><ul>${health.map(h=>`<li>${esc(regionName(h.region))}：${h.status==="checked"?t("已核查","Checked"):t("来源暂不可用，保留原值","Source unavailable; earlier values retained")} · ${esc(h.checked_at.slice(0,10))}</li>`).join("")}</ul><p>${t("GDP采用来源现价口径；保留原始修订说明，不据此计算不变价增长率。","GDP follows source current-price definitions and revisions, not constant-price growth.")}</p></details></section>
          <details class="bth-energy-database" open><summary><h3>${t("统计记录检索","Statistical records")}</h3><span>${data.counts.observations.toLocaleString()} ${t("条统计记录","observations")}</span></summary><div class="bth-energy-filters"><input data-energy-filter="query" value="${esc(state.query)}" aria-label="${t("检索统计记录","Search observations")}" placeholder="${t("指标、变量、来源或记录编号","Indicator, variable, source or ID")}">${option("region",regionOptions,t("全部地区","All regions"))}${option("dimension",data.categories.map(c=>({id:c.id,label:en?c.en:c.zh})),t("全部维度","All dimensions"))}${option("year",[...new Set(data.records.map(r=>r.year))].sort((a,b)=>b-a).map(y=>({id:y,label:y})),t("全部年份","All years"))}<span role="status">${filtered.length} ${t("条","records")}</span></div>
          <div class="bth-energy-table-wrap" tabindex="0"><table class="bth-energy-table"><thead><tr>${[t("地区与时期","Region / period"),t("指标与原始单位","Indicator / original unit"),t("数值","Value"),t("官方来源与口径","Source / definition")].map(x=>`<th>${x}</th>`).join("")}</tr></thead><tbody>${filtered.slice(0,state.visible).map(r=>`<tr data-energy-row="${esc(r.id)}"><td>${esc(regionName(r.region))}<time>${esc(r.period)}</time></td><td><b>${esc(actualLabel(r))}</b><span>${esc(unit(r))}</span></td><td class="bth-energy-number">${number(r.value)}</td><td>${sourceLink(r)}<details><summary>${t("记录详情","Record details")}</summary><p>${esc(r.source.title)}</p><p>${esc(r.notes || r.scope)}</p>${r.excerpt?`<p>${esc(r.excerpt)}</p>`:""}<p>${esc(r.id)} · ${esc(r.metric)} · ${esc(r.locator||"")}</p><p>${t("公布日期","Published")}: ${esc(r.published_at || t("未核定","Not verified"))} · ${t("取得日期","Accessed")}: ${esc(r.access_date||"—")}</p></details></td></tr>`).join("")||`<tr><td colspan="4">${t("无匹配记录","No matching observations")}</td></tr>`}</tbody></table></div>${filtered.length>state.visible?`<button type="button" data-energy-more class="secondary">${t("加载更多","Show more")}</button>`:""}</details>`;
        root.querySelectorAll("[data-energy-tab]").forEach(b=>b.onclick=()=>{state.tab=b.dataset.energyTab;render();});
        root.querySelectorAll("[data-energy-filter]").forEach(el=>el.addEventListener("change",()=>{state[el.dataset.energyFilter]=el.value;state.visible=30;render();}));
        root.querySelector("[data-energy-metric]")?.addEventListener("change",e=>{state.metric=e.target.value;render();});
        root.querySelector("[data-energy-more]")?.addEventListener("click",()=>{state.visible+=30;render();});
        root.querySelectorAll("[data-energy-record]").forEach(b=>b.onclick=()=>{state.query=b.dataset.energyRecord;state.dimension="";state.year="";state.visible=30;render();const row=root.querySelector(`[data-energy-row="${CSS.escape(state.query)}"]`); if(row){row.querySelector("details").open=true;row.scrollIntoView({block:"center",behavior:"smooth"});}});
        if(state.tab==="history") {
          const rows=(selectedIndicator()?.history_ids||[]).map(id=>byId.get(id)).filter(r=>r&&(!state.region||r.region===state.region)).sort((a,b)=>a.region.localeCompare(b.region,"zh-CN")||a.year-b.year);
          if(new Set(rows.map(r=>r.unit)).size===1) window.renderBarChart?.("bthEnergyHistoryChart",rows.map(r=>({name:`${regionName(r.region)} ${r.year}`,count:r.value})),{limit:30,valueFormat:number,ariaLabel:en?selectedIndicator()?.en:selectedIndicator()?.zh});
        }
      };
      render();
    } catch {if(root.isConnected) root.innerHTML=`<p role="status">${t("能源统计暂未加载。","Energy statistics unavailable.")} <button type="button" data-energy-retry>${t("重试","Retry")}</button></p>`;root.querySelector("[data-energy-retry]")?.addEventListener("click",()=>mount(root,language));}
  }
  window.GruenBthEnergy={mount};
})();
