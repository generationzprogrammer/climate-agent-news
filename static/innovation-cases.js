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
  Object.assign(TXT.zh,{sector:"技术领域",compareHelp:"先筛选同一技术领域，勾选两至三个案例，再点击对比。",profile:"合作结构画像",raw:"原始数值",score:"刻度",missing:"未披露",rubric:"查看刻度依据",profileNote:"刻度1–5表示合作规模与结构，不表示技术水平或商业成效。",noProfile:"平台与制度安排不使用项目资助口径评分。",mixed:"所选案例包括不同层级，雷达图仅绘制项目；制度与平台请查阅下方事实表。",participants:"合作机构名录",organization:"机构",actorType:"机构类型",role:"角色",coordinator:"协调方",participant:"参与方",budget:"项目登记",grant:"欧盟最高资助额",cost:"登记总成本",objective:"技术任务",original:"研究目标原文",action:"资助类型",identifier:"官方项目编号",timeline:"项目期",scheme:"项目与制度",source:"来源",planned:"登记目标",showParticipants:"展开合作机构",status:"登记状态",signed:"已签约",closed:"已结项",unit:"单位",fundingNote:"资助额为批准上限，不是实际支出或营收。",originalTitle:"原题",scoringMethod:"合作结构刻度"});
  Object.assign(TXT.en,{sector:"Technology",compareHelp:"Filter by technology, select two or three cases, then compare.",profile:"Collaboration profile",raw:"Observation",score:"Band",missing:"Not disclosed",rubric:"Scale definitions",profileNote:"Bands 1–5 describe collaboration scale and structure, not technical quality or commercial success.",noProfile:"Platforms and institutional arrangements are not scored using project-grant metrics.",mixed:"Selection spans different levels. Radar profiles include projects only; use the fact table for platforms and rules.",participants:"Partner register",organization:"Organisation",actorType:"Actor type",role:"Role",coordinator:"Coordinator",participant:"Participant",budget:"Project register",grant:"Maximum EU contribution",cost:"Registered total cost",objective:"Technical objectives",original:"Original research objectives",action:"Action type",identifier:"Official project ID",timeline:"Project period",scheme:"Project and institutions",source:"Source",planned:"Registered objectives",showParticipants:"Explore partners",status:"Register status",signed:"Grant signed",closed:"Closed",unit:"Unit",fundingNote:"Grant figures are approved ceilings, not expenditure or revenue.",originalTitle:"Original title",scoringMethod:"Collaboration scales"});
  const number = value => typeof value === "number" ? value.toLocaleString(lang==="zh"?"zh-CN":"en-GB",{maximumFractionDigits:2}) : t("missing");
  function radarSvg(cases,axes,language="zh") {
    const labels=axes.map(a=>text(a.label,language));
    const point=(index,score)=>{const a=-Math.PI/2+index*Math.PI*2/axes.length;return [310+136*score/5*Math.cos(a),224+136*score/5*Math.sin(a)];};
    const xy=p=>p.map(v=>v.toFixed(2)).join(",");
    const rings=[1,2,3,4,5].map(n=>'<polygon points="'+axes.map((_,i)=>xy(point(i,n))).join(" ")+'" fill="none" stroke="#dce2e7" stroke-width="1"/><text x="317" y="'+(224-136*n/5+4)+'" fill="#65707a" font-size="12">'+n+'</text>').join("");
    const spokes=axes.map((_,i)=>'<line x1="310" y1="224" x2="'+point(i,5)[0]+'" y2="'+point(i,5)[1]+'" stroke="#dce2e7" stroke-width="1"/>').join("");
    const names=axes.map((a,i)=>{const p=point(i,6.1);return '<text x="'+p[0]+'" y="'+(p[1]+4)+'" text-anchor="'+(i===0?'middle':p[0]>310?'start':'end')+'" fill="#25313b" font-size="15">'+esc(labels[i])+'</text>';}).join("");
    const colors=["#286693","#a96720","#4f5660"],dashes=["","8 4","2 4"];
    const plots=cases.map((c,j)=>{
      const values=axes.map(a=>c.profile?.[a.id]?.score??null);
      const lines=values.map((v,i)=>{const next=(i+1)%values.length;return v!==null&&values[next]!==null?'<line x1="'+point(i,v)[0]+'" y1="'+point(i,v)[1]+'" x2="'+point(next,values[next])[0]+'" y2="'+point(next,values[next])[1]+'" stroke="'+colors[j]+'" stroke-width="2" stroke-dasharray="'+dashes[j]+'"/>':"";}).join("");
      const markers=values.map((v,i)=>{if(v===null)return "";const p=point(i,v),axis=axes[i],row=c.profile[axis.id];
        const tip=text(c.title,language)+" · "+labels[i]+": "+row.raw+" "+text(axis.unit,language)+" · "+v+"/5";
        return '<g tabindex="0" role="button" aria-label="'+esc(tip)+'" data-radar-case="'+esc(c.id)+'" data-radar-axis="'+axis.id+'"><title>'+esc(tip)+'</title><circle cx="'+p[0]+'" cy="'+p[1]+'" r="10" fill="transparent"/><circle cx="'+p[0]+'" cy="'+p[1]+'" r="4" fill="'+(j===1?'white':colors[j])+'" stroke="'+colors[j]+'" stroke-width="2"/></g>';
      }).join("");return lines+markers;
    }).join("");
    return '<svg class="ic-radar" viewBox="0 0 620 445" role="img" aria-label="'+esc(language==="zh"?"合作结构雷达图，刻度1至5":"Collaboration radar, bands 1 to 5")+'">'+rings+spokes+plots+names+'</svg>'+ '<div class="ic-radar-legend">'+cases.map((c,j)=>'<span><svg width="30" height="12" aria-hidden="true"><line x1="0" y1="6" x2="30" y2="6" stroke="'+colors[j]+'" stroke-width="2" stroke-dasharray="'+dashes[j]+'"/></svg>'+esc(c.project?.acronym||text(c.title,language))+'</span>').join("")+'</div>';
  }
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
      if (filters.sector && c.sector_key!==filters.sector) return false;
      if (!query) return true;
      const names = c.countries.map(code => book.countries.find(row=>row.alpha2===code)).filter(Boolean);
      const labels = ["challenges","modes","institutions","factors"].flatMap(group=>c[group].map(key=>book.taxonomy[group][key]));
      return (JSON.stringify(c) + JSON.stringify(names) + JSON.stringify(labels)).toLowerCase().includes(query);
    });
  }
  function exportCsv(book, cases, lang) {
    const sourceMap = new Map(book.sources.map(s=>[s.id,s]));
    const keys = ["id","title","countries","scope","sector","challenges","modes","institutions","factors","start_year","end_year",
      "summary","actors","mechanism","observed","constraints","transfer","source_urls","reviewed_at","official_id","eu_grant_eur","participant_count","country_count"];
    const value = (c,key) => {
      if (key==="source_urls") return c.evidence.map(ref=>sourceMap.get(ref.source_id)?.url||"").filter(Boolean).join(" | ");
      if (key==="reviewed_at") return book.reviewed_at;
      if (["official_id","eu_grant_eur","participant_count","country_count"].includes(key)) return c.project?.[key]??"";
      if (book.taxonomy[key]) return c[key].map(tag=>text(book.taxonomy[key][tag],lang)).join(" | ");
      if (Array.isArray(c[key])) return c[key].join(" | ");
      return text(c[key],lang);
    };
    return "\uFEFF" + [keys.map(csvCell).join(","), ...cases.map(c=>keys.map(k=>csvCell(value(c,k))).join(","))].join("\r\n");
  }
  let host, book, loadPromise, lang = "zh", visible = 12, selected = new Set(), lastFocus;
  let filters = {query:"",lens:"",country:"",mode:"",institution:"",sector:""};
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
  function profile(cases) {
    const axes=book.profile_axes||[];
    const known=cases.filter(c=>axes.some(a=>c.profile?.[a.id]?.score!==null&&c.profile?.[a.id]?.score!==undefined));
    if(!known.length)return '<p>'+t("noProfile")+'</p>';
    const rows=axes.map(a=>'<tr><th scope="row">'+esc(local(a.label))+'</th>'+known.map(c=>{const r=c.profile?.[a.id],s=book.sources.find(s=>s.id===r?.source_id);return '<td>'+ (r?.raw!==null&&r?.raw!==undefined?number(r.raw)+' '+esc(local(a.unit))+'<br><strong>'+r.score+'/5</strong> '+(s?anchor(s.url,t("source")):""):t("missing"))+'</td>';}).join("")+'</tr>').join("");
    return '<section class="ic-profile"><h3>'+t("profile")+'</h3><p>'+t("profileNote")+'</p>'+radarSvg(known,axes,lang)+
      '<div class="ic-radar-readout" aria-live="polite"></div><div class="ic-matrix-scroll"><table class="ic-matrix ic-score-table"><thead><tr><th>'+t("field")+'</th>'+known.map(c=>'<th>'+esc(c.project?.acronym||local(c.title))+'</th>').join("")+'</tr></thead><tbody>'+rows+'</tbody></table></div>'+
      '<details class="ic-rubric"><summary>'+t("rubric")+'</summary><div class="ic-matrix-scroll"><table class="ic-matrix ic-rubric-table"><thead><tr><th>'+t("field")+'</th>'+[1,2,3,4,5].map(v=>'<th>'+v+'</th>').join("")+'</tr></thead><tbody>'+axes.map(a=>'<tr><th>'+esc(local(a.label))+' ('+esc(local(a.unit))+')</th>'+a.bands.map(v=>'<td>'+esc(v)+'</td>').join("")+'</tr>').join("")+'</tbody></table></div></details></section>';
  }
  function projectFacts(c) {
    if(!c.project)return "";
    const p=c.project;
    const rows=[["identifier",p.official_id],["timeline",p.start_date+' — '+p.end_date],["action",p.action==='IA'?(lang==='zh'?'创新行动（IA）':'Innovation action (IA)'):(lang==='zh'?'研究与创新行动（RIA）':'Research and innovation action (RIA)')],
      ["grant",number(p.eu_grant_eur/1e6)+(lang==='zh'?' 百万欧元':' EUR million')],["cost",number(p.total_cost_eur/1e6)+(lang==='zh'?' 百万欧元':' EUR million')],["status",p.register_status==='CLOSED'?t("closed"):t("signed")]];
    return '<h3 class="ic-group-title">'+t("budget")+'</h3><dl class="ic-project-facts">'+rows.map(([k,v])=>'<div><dt>'+t(k)+'</dt><dd>'+esc(v)+'</dd></div>').join("")+'</dl><p class="ic-funding-note">'+t("fundingNote")+'</p>';
  }
  function partnerList(c) {
    if(!c.participants?.length)return "";
    return '<details class="ic-partners"><summary>'+t("showParticipants")+' ('+c.participants.length+')</summary><div class="ic-matrix-scroll"><table class="ic-matrix ic-partner-table"><thead><tr>'+["organization","country","actorType","role"].map(k=>'<th>'+t(k)+'</th>').join("")+'</tr></thead><tbody>'+c.participants.map(p=>{
      const cr=book.countries.find(row=>row.alpha2===p.country);return '<tr><td>'+esc(p.name)+'</td><td>'+esc(cr?cr[lang==='zh'?'name_zh':'name_en']:p.country)+'</td><td>'+esc(local(book.participant_types[p.type]))+'</td><td>'+t(p.role==='coordinator'?'coordinator':'participant')+'</td></tr>';
    }).join("")+'</tbody></table></div></details>';
  }
  function shell() {
    host.innerHTML = '<div class="section-heading"><div><p class="overline">GLOBAL OPEN INNOVATION</p><h2>'+t("title")+'</h2></div>'+
      '<div class="ic-top-actions"><a class="ic-report" href="reports/open-innovation.pdf" target="_blank" rel="noopener">'+(lang==='zh'?'研究报告':'Research report')+'</a><button type="button" class="ic-export">'+t("export")+'</button></div></div>'+
      '<p class="ic-research-title">'+esc(local(book.research_title))+'</p>'+
      '<div class="ic-summary"><strong>'+book.cases.length+'</strong> '+t("results")+' <span>·</span> <strong>'+book.countries.length+
      '</strong> '+t("countries")+' <span>·</span> <strong>'+book.sources.length+'</strong> '+t("sources")+'</div>'+
      '<div class="ic-lenses" role="group" aria-label="'+t("title")+'">'+["","factor","adaptation","governance"].map(value=>
        '<button type="button" data-lens="'+value+'" aria-pressed="'+(value===filters.lens)+'">'+(value?t(value):t("all"))+'</button>').join("")+'</div>'+
      '<div class="ic-filters"><label class="ic-search">'+t("search")+'<input type="search" data-filter="query" maxlength="120" placeholder="'+t("placeholder")+'" value="'+esc(filters.query)+'"></label>'+
      '<label>'+t("country")+'<select data-filter="country"><option value="">'+t("all")+'</option><option value="_global">'+t("global")+'</option>'+
        book.countries.slice().sort((a,b)=>a[lang==="zh"?"name_zh":"name_en"].localeCompare(b[lang==="zh"?"name_zh":"name_en"],lang)).map(row=>'<option value="'+row.alpha2+'">'+esc(row[lang==="zh"?"name_zh":"name_en"])+' · '+row.alpha2+'</option>').join("")+'</select></label>'+
        [["mode","modes"],["institution","institutions"]].map(([field,group])=>'<label>'+t(field)+'<select data-filter="'+field+'"><option value="">'+t("all")+'</option>'+
        Object.entries(book.taxonomy[group]).map(([key,value])=>'<option value="'+key+'">'+esc(local(value))+'</option>').join("")+'</select></label>').join("")+
      '<label>'+t("sector")+'<select data-filter="sector"><option value="">'+t("all")+'</option>'+Object.entries(book.sector_taxonomy||{}).map(([key,value])=>'<option value="'+key+'">'+esc(local(value))+'</option>').join("")+'</select></label></div>'+
      '<p class="ic-compare-help">'+t("compareHelp")+'</p>'+
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
      '<div class="ic-card-meta"><span title="'+esc(countries(c))+'">'+esc(c.countries.length>3?countries(c).split(" · ").slice(0,3).join(" · ")+' +'+(c.countries.length-3):countries(c))+'</span><span>'+esc(period(c))+'</span></div>'+
      '<h3>'+esc(local(c.title))+'</h3><p>'+esc(local(c.summary).length>190?local(c.summary).slice(0,190)+'…':local(c.summary))+'</p><div class="ic-tags">'+tags(c,"modes")+'</div>'+
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
    host.querySelectorAll("[data-radar-case]").forEach(node=>{
      const report=()=>{const c=byId(node.dataset.radarCase),a=book.profile_axes.find(a=>a.id===node.dataset.radarAxis),r=c.profile[a.id];
        const ids=[...new Set([...host.querySelectorAll('[data-radar-axis="'+a.id+'"]')].map(n=>n.dataset.radarCase))];
        host.querySelector(".ic-radar-readout").textContent=ids.map(byId).filter(other=>other.profile[a.id].score===r.score).map(other=>{
          const value=other.profile[a.id];return (other.project?.acronym||local(other.title))+" · "+local(a.label)+"："+number(value.raw)+" "+local(a.unit)+" · "+value.score+"/5";
        }).join("； ");};
      node.addEventListener("mouseenter",report);node.addEventListener("focus",report);node.addEventListener("click",report);
      node.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();report();}});
    });
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
      '<p class="ic-detail-summary">'+esc(local(c.summary))+'</p>'+projectFacts(c)+
      '<h3 class="ic-group-title">'+t("facts")+'</h3>'+
      ["actors","mechanism","observed"].map(key=>'<section><h4>'+t(key)+'</h4><p>'+esc(local(c[key]))+'</p></section>').join("")+
      partnerList(c)+(c.objective_excerpt?'<details class="ic-original"><summary>'+t("original")+'</summary><p lang="en">'+esc(c.objective_excerpt.en)+'</p></details>':"")+profile([c])+
      '<section><h4>'+t("factors")+'</h4><div class="ic-tags">'+tags(c,"factors")+'</div></section>'+
      (c.constraints||c.transfer?'<h3 class="ic-group-title">'+t("analysis")+'</h3>'+["constraints","transfer"].filter(key=>c[key]).map(key=>'<section><h4>'+t(key)+'</h4><p>'+esc(local(c[key]))+'</p></section>').join(""):"")+
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
      ["timeline",c=>c.project?c.project.start_date+' — '+c.project.end_date:period(c)],
      ["grant",c=>c.project?number(c.project.eu_grant_eur/1e6)+(lang==='zh'?' 百万欧元':' EUR million'):t("missing")],
      ["participants",c=>c.project?c.project.participant_count+' · '+c.project.company_count+(lang==='zh'?'家企业':' companies'):t("missing")],
      ["mode",c=>c.modes.map(key=>label("modes",key)).join(" · ")],
      ["institution",c=>c.institutions.map(key=>label("institutions",key)).join(" · ")],
      ["factors",c=>c.factors.map(key=>label("factors",key)).join(" · ")],
      ...["mechanism","observed","constraints","transfer"].filter(key=>cases.some(c=>local(c[key]))).map(key=>[key,c=>local(c[key])||t("missing")])
    ];
    show('<h2>'+t("compare")+'</h2>'+ (cases.some(c=>!c.project)&&cases.some(c=>c.project)?'<p>'+t("mixed")+'</p>':"")+profile(cases)+'<div class="ic-matrix-scroll" tabindex="0"><table class="ic-matrix"><thead><tr><th scope="col">'+t("field")+'</th>'+
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
      const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),45000);
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
  root.GruenInnovationCases={mount,filterCases,exportCsv,csvCell,radarSvg};
  if(typeof module==="object"&&module.exports)module.exports=root.GruenInnovationCases;
})(typeof window==="undefined"?globalThis:window);
