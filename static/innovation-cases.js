/* Source-backed case catalogue. No credentials, model calls or remote libraries. */
(function (root) {
  "use strict";
  const TXT = {
    zh: {title:"科产融合全球案例库", all:"全部", factor:"要素流动", adaptation:"生态适配", governance:"全球治理与制度缺口",
      search:"检索案例", placeholder:"国家、机构、技术或合作机制", country:"国家或区域", mode:"协同模式", institution:"制度安排",
      results:"个案例", compare:"对比", selected:"已选", clear:"清空", export:"导出筛选结果", detail:"查看案例", more:"显示更多案例",
      summary:"案例概要", actors:"参与主体", mechanism:"协同机制", observed:"已记录的实践", constraints:"约束与适配条件", transfer:"可借鉴做法",
      evidence:"原始证据", developments:"相关新动态", field:"比较维度", close:"关闭", review:"证据核验", global:"全球及区域机制",
      framework:"研究框架与采编规则", empty:"未找到符合条件的案例", loading:"正在载入案例", failed:"案例库暂未载入", retry:"重试",
      limit:"最多选择三个案例", hint:"请选择两个或三个案例", kind:"技术领域", period:"项目时间", undated:"不采用未经核验的起始年份",
      facts:"事实与机制", analysis:"适配分析", factors:"流动要素", sources:"条原始来源", countries:"个国家标签", international:"全球及区域",
      method:"按独立项目、平台或制度安排收录。标签表示研究维度，不等同于已经证实的治理缺陷；适配分析不作为因果结论。原始证据可追溯，项目目标与已实现成果分开记录。日期为证据核验时间，不代表网页发表时间。新闻动态仅作关联，不自动改写案例事实。",
      countNote:"案例样本，不代表各国创新绩效排名。", chain:"要素配置 · 协同机制 · 制度安排 · 跨区域适配"},
    en: {title:"Global science–industry innovation cases", all:"All", factor:"Factor mobility", adaptation:"Ecosystem adaptation", governance:"Governance and institutional gaps",
      search:"Search cases", placeholder:"Country, institution, technology or mechanism", country:"Country or region", mode:"Collaboration model", institution:"Institutional arrangement",
      results:"cases", compare:"Compare", selected:"Selected", clear:"Clear", export:"Export filtered cases", detail:"Explore case", more:"Show more cases",
      summary:"Overview", actors:"Participants", mechanism:"Collaboration mechanism", observed:"Documented practice", constraints:"Constraints and fit", transfer:"Transferable practices",
      evidence:"Primary evidence", developments:"Related developments", field:"Dimension", close:"Close", review:"Evidence reviewed", global:"Global and regional mechanisms",
      framework:"Research framework and editorial rules", empty:"No matching cases", loading:"Loading cases", failed:"Case library unavailable", retry:"Retry",
      limit:"Select up to three cases", hint:"Select two or three cases", kind:"Technology domain", period:"Project period", undated:"No unverified start date assigned",
      facts:"Facts and mechanisms", analysis:"Adaptation analysis", factors:"Innovation factors", sources:"primary sources", countries:"country tags", international:"Global and regional",
      method:"Each record is a distinct project, platform or institutional arrangement. Tags identify research dimensions, not proven governance failures. Adaptation analysis is not a causal conclusion. Goals are distinguished from achieved results. Review dates are not publication dates. Related news does not automatically replace reviewed facts.",
      countNote:"A case sample, not a ranking of national innovation performance.", chain:"Factor allocation · Collaboration · Institutions · Regional adaptation"}
  };
  const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const url = value => { try { const u = new URL(value); return u.protocol === "https:" && !u.username && !u.password ? u.href : ""; } catch { return ""; } };
  const text = (value, lang) => value && typeof value === "object" ? (value[lang] || value.zh || value.en || "") : String(value ?? "");
  function csvCell(value) {
    const v = String(value ?? "");
    return '"' + (/^[\s]*[=+\-@]/.test(v) ? "'" + v : v).replace(/"/g, '""') + '"';
  }
  function filterCases(book, filters) {
    const query = String(filters.query || "").trim().toLowerCase();
    return book.cases.filter(c => {
      if (filters.lens && !c.challenges.includes(filters.lens)) return false;
      if (filters.country === "_global" && !["global","regional"].includes(c.scope)) return false;
      if (filters.country && filters.country !== "_global" && !c.countries.includes(filters.country)) return false;
      if (filters.mode && !c.modes.includes(filters.mode)) return false;
      if (filters.institution && !c.institutions.includes(filters.institution)) return false;
      if (!query) return true;
      const names = c.countries.map(code => book.countries.find(row=>row.alpha2===code)).filter(Boolean);
      const labels = ["challenges","modes","institutions","factors"].flatMap(group=>c[group].map(key=>book.taxonomy[group][key]));
      return (JSON.stringify(c) + JSON.stringify(names) + JSON.stringify(labels)).toLowerCase().includes(query);
    });
  }
  function exportCsv(book, cases, lang) {
    const sourceMap = new Map(book.sources.map(s=>[s.id,s]));
    const keys = ["id","title","countries","scope","sector","challenges","modes","institutions","factors","start_year","end_year",
      "summary","actors","mechanism","observed","constraints","transfer","source_urls","reviewed_at"];
    const value = (c,key) => {
      if (key==="source_urls") return c.evidence.map(ref=>sourceMap.get(ref.source_id)?.url||"").filter(Boolean).join(" | ");
      if (key==="reviewed_at") return book.reviewed_at;
      if (book.taxonomy[key]) return c[key].map(tag=>text(book.taxonomy[key][tag],lang)).join(" | ");
      if (Array.isArray(c[key])) return c[key].join(" | ");
      return text(c[key],lang);
    };
    return "\uFEFF" + [keys.map(csvCell).join(","), ...cases.map(c=>keys.map(k=>csvCell(value(c,k))).join(","))].join("\r\n");
  }
  let host, book, loadPromise, lang = "zh", visible = 12, selected = new Set(), lastFocus;
  let filters = {query:"",lens:"",country:"",mode:"",institution:""};
  const t = key => TXT[lang][key];
  const local = value => text(value,lang);
  const label = (group,key) => local(book.taxonomy[group][key]);
  const byId = id => book.cases.find(c=>c.id===id);
  const countries = c => c.countries.length ? c.countries.map(code => {
    const row=book.countries.find(r=>r.alpha2===code);
    return row ? row[lang==="zh"?"name_zh":"name_en"] : code;
  }).join(lang==="zh"?" · ":" · ") : t("international");
  const tags = (c,group) => c[group].map(tag=>'<span>'+esc(label(group,tag))+'</span>').join("");
  const period = c => c.start_year ? String(c.start_year)+(c.end_year&&c.end_year!==c.start_year?"–"+c.end_year:"") : "";
  const anchor = (href,title) => { const safe=url(href); return safe ? '<a href="'+esc(safe)+'" target="_blank" rel="noopener noreferrer">'+esc(title)+' ↗</a>' : esc(title); };
  function shell() {
    host.innerHTML = '<div class="section-heading"><div><p class="overline">GLOBAL OPEN INNOVATION</p><h2>'+t("title")+'</h2></div>'+
      '<button type="button" class="ic-export">'+t("export")+'</button></div>'+
      '<p class="ic-research-title">'+esc(local(book.research_title))+'</p>'+
      '<div class="ic-summary"><strong>'+book.cases.length+'</strong> '+t("results")+' <span>·</span> <strong>'+book.countries.length+
      '</strong> '+t("countries")+' <span>·</span> <strong>'+book.sources.length+'</strong> '+t("sources")+'</div>'+
      '<div class="ic-lenses" role="group" aria-label="'+t("title")+'">'+["","factor","adaptation","governance"].map(value=>
        '<button type="button" data-lens="'+value+'" aria-pressed="'+(value===filters.lens)+'">'+(value?t(value):t("all"))+'</button>').join("")+'</div>'+
      '<div class="ic-filters"><label class="ic-search">'+t("search")+'<input type="search" data-filter="query" maxlength="120" placeholder="'+t("placeholder")+'" value="'+esc(filters.query)+'"></label>'+
      '<label>'+t("country")+'<select data-filter="country"><option value="">'+t("all")+'</option><option value="_global">'+t("global")+'</option>'+
        book.countries.slice().sort((a,b)=>a[lang==="zh"?"name_zh":"name_en"].localeCompare(b[lang==="zh"?"name_zh":"name_en"],lang)).map(row=>'<option value="'+row.alpha2+'">'+esc(row[lang==="zh"?"name_zh":"name_en"])+' · '+row.alpha2+'</option>').join("")+'</select></label>'+
        [["mode","modes"],["institution","institutions"]].map(([field,group])=>'<label>'+t(field)+'<select data-filter="'+field+'"><option value="">'+t("all")+'</option>'+
        Object.entries(book.taxonomy[group]).map(([key,value])=>'<option value="'+key+'">'+esc(local(value))+'</option>').join("")+'</select></label>').join("")+'</div>'+
      '<div class="ic-toolbar"><span class="ic-result" aria-live="polite"></span><div><span class="ic-selected" aria-live="polite"></span>'+
      '<button type="button" class="ic-compare">'+t("compare")+'</button><button type="button" class="ic-clear">'+t("clear")+'</button></div></div>'+
      '<div class="ic-grid"></div><button type="button" class="load-more ic-more">'+t("more")+'</button>'+
      '<details class="ic-method"><summary>'+t("framework")+'</summary><p>'+t("chain")+'</p><p>'+t("method")+'</p><p>'+t("countNote")+'</p></details>'+
      '<dialog class="ic-dialog" aria-label="'+t("detail")+'"><div class="ic-dialog-head"><button type="button" class="ic-close" aria-label="'+t("close")+'">×</button></div><div class="ic-dialog-body"></div></dialog>';
    host.querySelectorAll("select[data-filter]").forEach(el=>el.value=filters[el.dataset.filter]);
    host.querySelectorAll("[data-lens]").forEach(el=>el.addEventListener("click",()=>{
      filters.lens=el.dataset.lens;visible=12;
      host.querySelectorAll("[data-lens]").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.lens===filters.lens)));
      renderCards();
    }));
    host.querySelectorAll("[data-filter]").forEach(el=>el.addEventListener(el.tagName==="SELECT"?"change":"input",()=>{
      filters[el.dataset.filter]=el.value;visible=12;renderCards();
    }));
    host.querySelector(".ic-more").addEventListener("click",()=>{visible+=12;renderCards();});
    host.querySelector(".ic-clear").addEventListener("click",()=>{selected.clear();renderCards();});
    host.querySelector(".ic-compare").addEventListener("click",compare);
    host.querySelector(".ic-export").addEventListener("click",()=>{
      const blob=new Blob([exportCsv(book,filterCases(book,filters),lang)],{type:"text/csv;charset=utf-8"});
      const href=URL.createObjectURL(blob),a=document.createElement("a");a.href=href;
      a.download=(lang==="zh"?"科产融合案例":"open-innovation-cases")+"-"+book.reviewed_at+".csv";a.click();
      setTimeout(()=>URL.revokeObjectURL(href),1000);
    });
    const dialog=host.querySelector("dialog");
    host.querySelector(".ic-close").addEventListener("click",()=>dialog.close());
    dialog.addEventListener("click",event=>{if(event.target===dialog){const r=dialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)dialog.close();}});
    dialog.addEventListener("close",()=>lastFocus?.focus());
    renderCards();
  }
  function renderCards() {
    const cases=filterCases(book,filters);
    host.querySelector(".ic-result").textContent=cases.length+" "+t("results");
    host.querySelector(".ic-selected").textContent=t("selected")+" "+selected.size+"/3";
    host.querySelector(".ic-compare").disabled=selected.size<2;
    host.querySelector(".ic-clear").disabled=!selected.size;
    host.querySelector(".ic-grid").innerHTML=cases.slice(0,visible).map(c=>'<article class="ic-card">'+
      '<div class="ic-card-meta"><span>'+esc(countries(c))+'</span><span>'+esc(period(c))+'</span></div>'+
      '<h3>'+esc(local(c.title))+'</h3><p>'+esc(local(c.summary))+'</p><div class="ic-tags">'+tags(c,"modes")+'</div>'+
      '<div class="ic-card-actions"><button type="button" data-detail="'+c.id+'">'+t("detail")+' →</button>'+
      '<label><input type="checkbox" data-select="'+c.id+'" '+(selected.has(c.id)?"checked":"")+' '+(!selected.has(c.id)&&selected.size>=3?"disabled":"")+'>'+t("compare")+'</label></div></article>').join("") ||
      '<div class="ic-empty">'+t("empty")+'</div>';
    host.querySelector(".ic-more").hidden=cases.length<=visible;
    host.querySelectorAll("[data-detail]").forEach(el=>el.addEventListener("click",()=>detail(el.dataset.detail)));
    host.querySelectorAll("[data-select]").forEach(el=>el.addEventListener("change",()=>{
      if(el.checked&&selected.size<3)selected.add(el.dataset.select);else selected.delete(el.dataset.select);
      renderCards();host.querySelector('[data-select="'+el.dataset.select+'"]')?.focus();
    }));
  }
  function show(html,wide=false) {
    lastFocus=document.activeElement;
    const dialog=host.querySelector("dialog");
    dialog.classList.toggle("ic-wide",wide);host.querySelector(".ic-dialog-body").innerHTML=html;
    dialog.showModal();dialog.scrollTop=0;
    host.querySelector(".ic-close").focus();
  }
  function evidence(c) {
    const refs=c.evidence.map(ref=>book.sources.find(s=>s.id===ref.source_id)).filter(Boolean);
    return '<ol class="ic-sources">'+refs.map(s=>'<li>'+anchor(s.url,s.title)+'<span>'+esc(s.publisher)+' · '+esc(s.language.toUpperCase())+
      (s.published_date?' · '+esc(s.published_date):"")+'</span></li>').join("")+'</ol>';
  }
  function detail(id) {
    const c=byId(id);
    show('<p class="overline">'+esc(countries(c))+(period(c)?" · "+esc(period(c)):"")+'</p><h2>'+esc(local(c.title))+'</h2>'+
      '<div class="ic-tags">'+tags(c,"challenges")+tags(c,"institutions")+'</div>'+
      '<p class="ic-detail-summary">'+esc(local(c.summary))+'</p>'+
      '<h3 class="ic-group-title">'+t("facts")+'</h3>'+
      ["actors","mechanism","observed"].map(key=>'<section><h4>'+t(key)+'</h4><p>'+esc(local(c[key]))+'</p></section>').join("")+
      '<section><h4>'+t("factors")+'</h4><div class="ic-tags">'+tags(c,"factors")+'</div></section>'+
      '<h3 class="ic-group-title">'+t("analysis")+'</h3>'+
      ["constraints","transfer"].map(key=>'<section><h4>'+t(key)+'</h4><p>'+esc(local(c[key]))+'</p></section>').join("")+
      '<h3 class="ic-group-title">'+t("evidence")+'</h3>'+evidence(c)+
      '<p class="ic-review">'+t("review")+' · '+esc(book.reviewed_at)+'</p>'+
      (c.developments?.length?'<h3 class="ic-group-title">'+t("developments")+'</h3><ul class="ic-news">'+c.developments.map(n=>
        '<li><time>'+esc(n.published_at)+'</time> '+anchor(n.url,local(n.title))+'</li>').join("")+'</ul>':""));
  }
  function compare() {
    const cases=[...selected].map(byId).filter(Boolean);
    if(cases.length<2)return;
    const rows=[
      ["country",c=>countries(c)],["kind",c=>local(c.sector)],
      ["mode",c=>c.modes.map(key=>label("modes",key)).join(" · ")],
      ["institution",c=>c.institutions.map(key=>label("institutions",key)).join(" · ")],
      ["factors",c=>c.factors.map(key=>label("factors",key)).join(" · ")],
      ...["mechanism","observed","constraints","transfer"].map(key=>[key,c=>local(c[key])])
    ];
    show('<h2>'+t("compare")+'</h2><div class="ic-matrix-scroll" tabindex="0"><table class="ic-matrix"><thead><tr><th scope="col">'+t("field")+'</th>'+
      cases.map(c=>'<th scope="col">'+esc(local(c.title))+'</th>').join("")+'</tr></thead><tbody>'+
      rows.map(([key,value])=>'<tr><th scope="row">'+t(key)+'</th>'+cases.map(c=>'<td>'+esc(value(c))+'</td>').join("")+'</tr>').join("")+
      '<tr><th scope="row">'+t("evidence")+'</th>'+cases.map(c=>'<td>'+evidence(c)+'</td>').join("")+'</tr></tbody></table></div>',true);
  }
  async function mount(element,options={}) {
    if(!element)return;
    host=element;lang=options.language==="en"?"en":"zh";
    host.setAttribute("aria-label",t("title"));
    if(options.mode!=="energy"){host.querySelector("dialog[open]")?.close();return;}
    if(book){shell();return;}
    host.innerHTML='<p role="status">'+t("loading")+'</p>';
    if(!loadPromise)loadPromise=(async()=>{
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
      try{
        const response=await fetch(new URL("./data/innovation_cases.json",document.baseURI),{signal:controller.signal,cache:"no-cache"});
        if(!response.ok)throw new Error("casebook_http");
        const data=await response.json();
        if(!Array.isArray(data.cases)||!Array.isArray(data.sources)||!Array.isArray(data.countries)||!data.taxonomy)throw new Error("casebook_schema");
        book=data;
      }finally{clearTimeout(timer);}
    })();
    try{await loadPromise;if(document.body.dataset.mode==="energy")shell();}
    catch{loadPromise=null;host.innerHTML='<p role="alert">'+t("failed")+' <button class="ic-retry" type="button">'+t("retry")+'</button></p>';
      host.querySelector(".ic-retry").addEventListener("click",()=>mount(host,options));}
  }
  root.GruenInnovationCases={mount,filterCases,exportCsv,csvCell};
  if(typeof module==="object"&&module.exports)module.exports=root.GruenInnovationCases;
})(typeof window==="undefined"?globalThis:window);
