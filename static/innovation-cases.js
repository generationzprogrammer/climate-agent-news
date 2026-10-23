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
  // A presentation adapter, not a rewrite of the source records. Programme-wide
  // rules remain inspectable but are not presented as individual achievements.
  function casePresentation(c, language="zh") {
    const zh=language==="zh",r=c.registry_record;
    const view={title:text(c.title,language),summary:text(c.summary,language),facts:[],sections:{},programme:"",original:""};
    for(const key of ["actors","mechanism","observed","constraints","transfer"])view.sections[key]=text(c[key],language);
    if(!r)return view;
    const add=(key,cn,en,value)=>{if(value!==null&&value!==undefined&&value!=="")view.facts.push({key,label:zh?cn:en,value:String(value)});};
    view.sections.constraints="";view.sections.transfer="";view.sections.observed="";
    view.programme=view.sections.mechanism;view.sections.mechanism="";
    const key=r.registry||"";
    if(key==='nsf_iucrc'){
      const hosts=r.universities||[],members=r.member_names||[];
      add('hosts','列名高校','Listed universities',hosts.length||null);
      // An empty directory list is not evidence that the centre has no members.
      add('members','列名产业及其他成员','Listed industry and other members',members.length||null);
      add('established','成立年份','Established',r.year);
      add('location','名录所在地','Listed location',r.location);
      if(r.status==='completed')add('status','名录状态','Directory status',zh?'已完成':'Completed');
      if(zh)view.summary=view.summary.replace(/，研究覆盖[^。]+。名录登记的具体方向为/,'，研究方向为');
    }else if(key==='embrapii_export'){
      if(zh)view.summary=view.summary.split('企业可围绕')[0];
      add('location','实施地','Location',r.location);
      const focus=zh?view.summary.match(/是EMBRAPII认证的(.+?)研究单元/)?.[1]:(r.focus||[]).join('; ');
      add('focus','技术专长','Technical focus',focus);
      view.original=r.activities||"";
    }else if(key==='australia_crcp'){
      add('partners','列名合作方','Named partners',r.partners?.length||null);
      view.original=r.objective_original||"";
    }else if(key.startsWith('china_moe')){
      const year=r.designation_year;
      view.summary=zh?(r.name+(year?'于'+year+'年':'')+'入选教育部高校科技成果转化和技术转移基地。'+(r.practice||'')):
        text(c.summary,language).replace(', connecting university research with industrial application.','.');
      add('designation','认定年份','Designation year',year);
      add('city','实施地','Location',zh?r.city:null);
      if(r.practice){view.sections.mechanism=zh?r.practice:(r.practice_en||'');view.programme="";}
    }else if(key==='jst_coinext'){
      if(zh)view.summary=view.summary.replace('，在JST共创平台计划下组织围绕这一目标的研究与合作。','。');
      const status={'進行中プロジェクト':['进行中','Ongoing'],'終了プロジェクト':['已结束','Completed']}[r.stage];
      if(status)add('status','计划登记状态','Programme status',status[zh?0:1]);
    }else if(key.startsWith('africa')){
      view.summary=view.sections.actors.replace(zh?'中心与依托机构：':'Centre and host: ','');
      view.sections.actors="";
    }
    if(c.case_detail){
      view.title=text(c.case_detail.title,language);view.summary=text(c.case_detail.summary,language);
      for(const f of c.case_detail.facts||[])view.facts.push({key:'detail',label:text(f.label,language),value:text(f.value,language),source_id:f.source_id,locator:f.locator});
    }
    return view;
  }
  function substantiveField(c,key,language="zh"){
    const view=casePresentation(c,language);
    if(key==='mechanism'&&view.programme)return (language==='zh'?'计划共同规则：':'Programme rules: ')+view.programme;
    return view.sections[key]||"";
  }
  Object.assign(TXT.zh,{sector:"技术领域",compareHelp:"先筛选同一技术领域，勾选两至三个案例，再点击对比。",profile:"合作结构画像",raw:"原始数值",score:"刻度",missing:"未披露",rubric:"查看刻度依据",profileNote:"刻度1–5表示合作规模与结构，不表示技术水平或商业成效。",noProfile:"平台与制度安排不使用项目资助口径评分。",mixed:"所选案例包括不同层级，雷达图仅绘制项目；制度与平台请查阅下方事实表。",participants:"合作机构名录",organization:"机构",actorType:"机构类型",role:"角色",coordinator:"协调方",participant:"参与方",budget:"项目登记",grant:"欧盟最高资助额",cost:"登记总成本",objective:"技术任务",original:"研究目标原文",action:"资助类型",identifier:"官方项目编号",timeline:"项目期",scheme:"项目与制度",source:"来源",planned:"登记目标",showParticipants:"展开合作机构",status:"登记状态",signed:"已签约",closed:"已结项",unit:"单位",fundingNote:"资助额为批准上限，不是实际支出或营收。",originalTitle:"原题",scoringMethod:"合作结构刻度"});
  Object.assign(TXT.en,{sector:"Technology",compareHelp:"Filter by technology, select two or three cases, then compare.",profile:"Collaboration profile",raw:"Observation",score:"Band",missing:"Not disclosed",rubric:"Scale definitions",profileNote:"Bands 1–5 describe collaboration scale and structure, not technical quality or commercial success.",noProfile:"Platforms and institutional arrangements are not scored using project-grant metrics.",mixed:"Selection spans different levels. Radar profiles include projects only; use the fact table for platforms and rules.",participants:"Partner register",organization:"Organisation",actorType:"Actor type",role:"Role",coordinator:"Coordinator",participant:"Participant",budget:"Project register",grant:"Maximum EU contribution",cost:"Registered total cost",objective:"Technical objectives",original:"Original research objectives",action:"Action type",identifier:"Official project ID",timeline:"Project period",scheme:"Project and institutions",source:"Source",planned:"Registered objectives",showParticipants:"Explore partners",status:"Register status",signed:"Grant signed",closed:"Closed",unit:"Unit",fundingNote:"Grant figures are approved ceilings, not expenditure or revenue.",originalTitle:"Original title",scoringMethod:"Collaboration scales"});
  const number = value => typeof value === "number" ? value.toLocaleString(lang==="zh"?"zh-CN":"en-GB",{maximumFractionDigits:2}) : t("missing");
  Object.assign(TXT.zh,{grant:"登记资助",euGrant:"欧盟最高资助额",usGrant:"ARPA-E登记资助额",programme:"资助计划",active:"进行中",alumni:"历史项目",noProfile:"缺少同口径的完整登记数据，不绘制合作结构评分。"});
  Object.assign(TXT.en,{grant:"Registered funding",euGrant:"Maximum EU contribution",usGrant:"Listed ARPA-E award",programme:"Funding programme",active:"Active",alumni:"Alumni",noProfile:"No collaboration score is drawn without comparable complete register data."});
  const registeredPeriod = c => c.project?.start_date&&c.project?.end_date?c.project.start_date+' — '+c.project.end_date:period(c)||t("missing");
  const registeredGrant = c => !c.project?t("missing"):c.project.source_type==='AU_CRCP'?number(c.project.registered_grant_aud)+' AUD':c.project.source_type==='ARPAE'?
    (typeof c.project.award_usd==='number'?number(c.project.award_usd)+(lang==='zh'?' 美元':' USD'):t("missing")):
    (typeof c.project.eu_grant_eur==='number'?number(c.project.eu_grant_eur/1e6)+(lang==='zh'?' 百万欧元':' EUR million'):t("missing"));
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
  const FAMILIES={research:{zh:'联合研究',en:'Collaborative research',members:['mission','consortium']},transfer:{zh:'技术转移与验证',en:'Transfer and validation',members:['intermediary','pilot']},enterprise:{zh:'创业与产业集群',en:'Ventures and clusters',members:['venture','cluster']},capacity:{zh:'能力建设',en:'Capacity building',members:['capacity']},governance:{zh:'规则协调',en:'Rule coordination',members:['rules']}};
  const DOMAINS={energy:{zh:'能源与环境',en:'Energy and environment',members:['battery','grid','heat','hydrogen','industry','solar','wind','nuclear','energy_systems','marine','environment']},engineering:{zh:'制造与材料',en:'Manufacturing and materials',members:['materials','manufacturing','mobility','transport']},digital:{zh:'数字技术',en:'Digital technologies',members:['digital']},bio:{zh:'生命科学与农业',en:'Life sciences and agriculture',members:['biomanufacturing','health']},general:{zh:'综合与未细分',en:'General and unclassified',members:['general','applied_innovation']}};
  const groupOf=(dictionary,value)=>Object.keys(dictionary).find(k=>dictionary[k].members.includes(value))||(dictionary===DOMAINS?'general':'');
  function facetCounts(book,filters,field){
    const loose={...filters,[field]:''};if(field==='country')loose.focusCountry='';
    const counts={};for(const c of filterCases(book,loose)){
      const values=field==='country'?[...c.countries,...(['global','regional'].includes(c.scope)?['_global']:[])]:
        field==='mode'?c.modes:field==='institution'?c.institutions:field==='sector'?[c.sector_key]:
        field==='family'?[groupOf(FAMILIES,c.research_annotation?.primary_model)]:field==='domain'?[groupOf(DOMAINS,c.sector_key)]:
        field==='archetype'?[c.research_annotation?.primary_model]:field==='organization'?(filters.organizationScope==='focus'?c.organization_tags:c.organization_participant_tags):
        field==='period'?(filters.timeBasis==='activity'?(c.timeline?.events||[]).flatMap(e=>[e.decade,e.china_plan]):[c.timeline?.origin_period,c.timeline?.origin_decade,c.timeline?.origin_china_plan]):[c.research_annotation?.[field]];
      for(const v of new Set(values||[]))if(v)counts[v]=(counts[v]||0)+1;
    }return counts;
  }
  function filterCases(book, filters={}) {
    const query = String(filters.query || "").trim().toLowerCase();
    return book.cases.filter(c => {
      for (const key of ["province","continent","economy","grain"]) {
        if(filters[key]&&c.research_annotation?.[key]!==filters[key])return false;
      }
      if(filters.archetype&&c.research_annotation?.primary_model!==filters.archetype)return false;
      if(filters.family&&groupOf(FAMILIES,c.research_annotation?.primary_model)!==filters.family)return false;
      if(filters.domain&&groupOf(DOMAINS,c.sector_key)!==filters.domain)return false;
      if (filters.lens && !c.challenges.includes(filters.lens)) return false;
      if (filters.country === "_global" && !["global","regional"].includes(c.scope)) return false;
      if (filters.country && filters.country !== "_global" && !c.countries.includes(filters.country)) return false;
      if (filters.mode && !c.modes.includes(filters.mode)) return false;
      if (filters.institution && !c.institutions.includes(filters.institution)) return false;
      if (filters.sector && c.sector_key!==filters.sector) return false;
      if(filters.focusCountry&&c.research_annotation?.country!==filters.focusCountry)return false;
      if(filters.organization&&!((filters.organizationScope==='focus'?c.organization_tags:c.organization_participant_tags)||[]).includes(filters.organization))return false;
      if(filters.period){
        const timeline=c.timeline||{},scope=filters.timeScope||'case_period',basis=filters.timeBasis||'origin';
        if(basis==='activity'){
          if(!(timeline.events||[]).some(e=>(scope==='global_decades'?e.decade:scope==='china_plans'?e.china_plan:(e.china_plan||e.decade))===filters.period))return false;
        }else{
          const value=scope==='global_decades'?timeline.origin_decade:scope==='china_plans'?timeline.origin_china_plan:timeline.origin_period;
          if((value||'undated')!==filters.period)return false;
        }
      }
      if (!query) return true;
      const names = c.countries.map(code => book.countries.find(row=>row.alpha2===code)).filter(Boolean);
      const labels = ["challenges","modes","institutions","factors"].flatMap(group=>c[group].map(key=>book.taxonomy[group][key]));
      return (JSON.stringify(c) + JSON.stringify(names) + JSON.stringify(labels)).toLowerCase().includes(query);
    });
  }
  function exportCsv(book, cases, lang) {
    const sourceMap = new Map(book.sources.map(s=>[s.id,s]));
    const keys = ["id","title","countries","scope","sector","challenges","modes","institutions","factors","start_year","end_year",
      "summary","actors","mechanism","observed","constraints","transfer","source_urls","reviewed_at","official_id","eu_grant_eur","participant_count","country_count","award_usd","funding_basis",
      "primary_model","province","city","continent","economy","grain","cohort","verified_origin_year","origin_period","activity_periods","organization_tags","organization_participant_tags","programme_rules","mechanism_scope","case_detail_json"];
    const value = (c,key) => {
      if (key==="source_urls") return c.evidence.map(ref=>sourceMap.get(ref.source_id)?.url||"").filter(Boolean).join(" | ");
      if(key==='title'||key==='summary')return casePresentation(c,lang)[key];
      if (key==="reviewed_at") return book.reviewed_at;
      if(key==='programme_rules')return casePresentation(c,lang).programme;
      if(key==='mechanism_scope')return casePresentation(c,lang).programme?'programme':'case_description';
      if(key==='case_detail_json')return c.case_detail?JSON.stringify(c.case_detail):'';
      if(c.registry_record&&['mechanism','observed','constraints','transfer'].includes(key))return casePresentation(c,lang).sections[key];
      if(key==='verified_origin_year')return c.timeline?.origin_year??'';
      if(key==='origin_period')return c.timeline?.origin_period||'';
      if(key==='activity_periods')return (c.timeline?.activity_periods||[]).join(' | ');
      if (["primary_model","province","city","continent","economy","grain","cohort"].includes(key)) return c.research_annotation?.[key]||"";
      if (["official_id","eu_grant_eur","participant_count","country_count","award_usd","funding_basis"].includes(key)) return c.project?.[key]??"";
      if (book.taxonomy[key]) return c[key].map(tag=>text(book.taxonomy[key][tag],lang)).join(" | ");
      if (Array.isArray(c[key])) return c[key].join(" | ");
      return text(c[key],lang);
    };
    return "\uFEFF" + [keys.map(csvCell).join(","), ...cases.map(c=>keys.map(k=>csvCell(value(c,k))).join(","))].join("\r\n");
  }
  Object.assign(TXT.zh,{sources:'引用来源',review:'数据版本'});
  Object.assign(TXT.en,{sources:'Cited sources',review:'Data version'});
  let host, book, loadPromise, lang = "zh", visible = 12, selected = new Set(), lastFocus;
  let filters = {query:"",lens:"",country:"",family:"",domain:"",mode:"",institution:"",sector:"",archetype:"",province:"",continent:"",economy:"",grain:"",organization:"",organizationScope:"",period:"",timeBasis:"",timeScope:"",focusCountry:""};
  let activeView="cases";
  const t = key => TXT[lang][key];
  const local = value => text(value,lang);
  const label = (group,key) => local(book.taxonomy[group][key]);
  const byId = id => book.cases.find(c=>c.id===id);
  const countries = c => c.countries.length ? c.countries.map(code => {
    const row=book.countries.find(r=>r.alpha2===code);
    return row ? row[lang==="zh"?"name_zh":"name_en"] : code;
  }).join(lang==="zh"?" · ":" · ") : t("international");
  const location = c => {const a=c.research_annotation,p=book.analysis?.provinces.find(p=>p.id===a?.province);return p?countries(c)+' · '+local(p.name)+(lang==='zh'&&a.city?' · '+a.city:''):countries(c);};
  const modelTag = c => {const m=book.analysis?.archetypes.find(m=>m.id===c.research_annotation?.primary_model);return m?'<span>'+esc(local(m.label))+'</span>':'';};
  const tags = (c,group) => c[group].map(tag=>'<span>'+esc(label(group,tag))+'</span>').join("");
  const period = c => {const y=c.timeline?c.timeline.origin_year:c.start_year;return y?String(y)+(c.end_year&&c.end_year!==y?"–"+c.end_year:""):"";};
  const anchor = (href,title) => { const safe=url(href); return safe ? '<a href="'+esc(safe)+'" target="_blank" rel="noopener noreferrer">'+esc(title)+' ↗</a>' : esc(title); };
  function registryFacts(view){
    return view.facts.length?'<dl class="ic-project-facts ic-registry-facts">'+view.facts.map(row=>{const s=book.sources.find(s=>s.id===row.source_id);return '<div><dt>'+esc(row.label)+'</dt><dd>'+esc(row.value)+(s?' <small>'+anchor(s.url,t('source'))+'</small>':'')+'</dd></div>';}).join('')+'</dl>':'';
  }
  function compactFacts(c){
    const rows=casePresentation(c,lang).facts.filter(r=>['hosts','members','partners','designation','focus'].includes(r.key)).slice(0,2);
    return rows.length?'<dl class="ic-card-facts">'+rows.map(r=>'<div><dt>'+esc(r.label)+'</dt><dd>'+esc(r.value)+'</dd></div>').join('')+'</dl>':'';
  }
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
    if(p.source_type==='AU_CRCP')return '<h3 class="ic-group-title">'+t('budget')+'</h3><dl class="ic-project-facts"><div><dt>'+t('timeline')+'</dt><dd>'+esc(c.registry_record?.period||period(c))+'</dd></div><div><dt>'+t('grant')+'</dt><dd>'+number(p.registered_grant_aud)+' AUD</dd></div><div><dt>'+t('cost')+'</dt><dd>'+number(p.registered_project_value_aud)+' AUD</dd></div></dl>';
    const rows=p.source_type==='ARPAE'?[["identifier",p.official_id],["timeline",registeredPeriod(c)],["programme",p.programme],["usGrant",registeredGrant(c)],
      ["status",p.register_status==='Active'?t("active"):t("alumni")]]:
      [["identifier",p.official_id],["timeline",registeredPeriod(c)],["action",p.action==='IA'?(lang==='zh'?'创新行动（IA）':'Innovation action (IA)'):(lang==='zh'?'研究与创新行动（RIA）':'Research and innovation action (RIA)')],
      ["euGrant",registeredGrant(c)],["cost",number(p.total_cost_eur/1e6)+(lang==='zh'?' 百万欧元':' EUR million')],["status",p.register_status==='CLOSED'?t("closed"):t("signed")]];
    return '<h3 class="ic-group-title">'+t("budget")+'</h3><dl class="ic-project-facts">'+rows.map(([k,v])=>'<div><dt>'+t(k)+'</dt><dd>'+esc(v)+'</dd></div>').join("")+'</dl><p class="ic-funding-note">'+t("fundingNote")+'</p>';
  }
  function partnerList(c) {
    if(!c.participants?.length)return "";
    return '<details class="ic-partners"><summary>'+t("showParticipants")+' ('+c.participants.length+')</summary><div class="ic-matrix-scroll"><table class="ic-matrix ic-partner-table"><thead><tr>'+["organization","country","actorType","role"].map(k=>'<th>'+t(k)+'</th>').join("")+'</tr></thead><tbody>'+c.participants.map(p=>{
      const cr=book.countries.find(row=>row.alpha2===p.country);return '<tr><td>'+esc(p.name)+'</td><td>'+esc(cr?cr[lang==='zh'?'name_zh':'name_en']:p.country||t("missing"))+'</td><td>'+esc(local(book.participant_types[p.type])||t("missing"))+'</td><td>'+t(p.role==='coordinator'?'coordinator':'participant')+'</td></tr>';
    }).join("")+'</tbody></table></div></details>';
  }
  function shell() {
    host.innerHTML = '<div class="section-heading"><div><p class="overline">GLOBAL OPEN INNOVATION</p><h2>'+t("title")+'</h2></div>'+
      '<div class="ic-top-actions"><a class="ic-report" href="innovation/" target="_blank" rel="noopener">'+(lang==='zh'?'独立入口':'Standalone library')+'</a><a class="ic-report" href="reports/innovation-policy-brief-20261018.pdf" target="_blank" rel="noopener">'+(lang==='zh'?'政策简报':'Policy brief')+'</a><button type="button" class="ic-export">'+t("export")+'</button></div></div>'+
      '<p class="ic-research-title">'+esc(local(book.research_title))+'</p>'+
      '<div class="ic-summary"><strong>'+book.cases.length+'</strong> '+t("results")+' <span>·</span> <strong>'+book.countries.length+
      '</strong> '+t("countries")+' <span>·</span> <strong>'+book.sources.length+'</strong> '+t("sources")+'</div>'+
      '<div class="ic-lenses" role="group" aria-label="'+t("title")+'">'+["cases","models","macro",...(book.research?["insights"]:[])].map(value=>
        '<button type="button" data-case-view="'+value+'" aria-pressed="'+(value===activeView)+'">'+(lang==='zh'?{cases:'案例检索',models:'国家与区域模式',macro:'宏观对比',insights:'洞察'}[value]:{cases:'Case explorer',models:'National and regional models',macro:'Macro comparison',insights:'Insights'}[value])+'</button>').join("")+'</div>'+
      '<div data-analysis-panel="cases">'+
      '<div class="ic-filters"><label class="ic-search">'+t("search")+'<input type="search" data-filter="query" maxlength="120" placeholder="'+t("placeholder")+'" value="'+esc(filters.query)+'"></label>'+
      '<label>'+t("country")+'<select data-filter="country"><option value="">'+t("all")+'</option><option value="_global">'+t("global")+'</option>'+
        book.countries.slice().sort((a,b)=>a[lang==="zh"?"name_zh":"name_en"].localeCompare(b[lang==="zh"?"name_zh":"name_en"],lang)).map(row=>'<option value="'+row.alpha2+'">'+esc(row[lang==="zh"?"name_zh":"name_en"])+' · '+row.alpha2+'</option>').join("")+'</select></label>'+
        [["mode","modes"],["institution","institutions"]].map(([field,group])=>'<label>'+t(field)+'<select data-filter="'+field+'"><option value="">'+t("all")+'</option>'+
        Object.entries(book.taxonomy[group]).map(([key,value])=>'<option value="'+key+'">'+esc(local(value))+'</option>').join("")+'</select></label>').join("")+
      '<label>'+t("sector")+'<select data-filter="sector"><option value="">'+t("all")+'</option>'+Object.entries(book.sector_taxonomy||{}).map(([key,value])=>'<option value="'+key+'">'+esc(local(value))+'</option>').join("")+'</select></label></div>'+
      '<div class="ic-analysis-filters"><label>'+(lang==='zh'?'组织模式':'Organisational model')+'<select data-filter="archetype"><option value="">'+t('all')+'</option>'+(book.analysis?.archetypes||[]).map(m=>'<option value="'+m.id+'">'+esc(local(m.label))+'</option>').join('')+'</select></label><label>'+(lang==='zh'?'中国省份':'Chinese province')+'<select data-filter="province"><option value="">'+t('all')+'</option>'+(book.analysis?.provinces||[]).map(p=>'<option value="'+p.id+'">'+esc(local(p.name))+'</option>').join('')+'</select></label><button type="button" class="ic-reset">'+(lang==='zh'?'清除筛选':'Reset filters')+'</button></div>'+
      '<p class="ic-compare-help">'+(lang==='zh'?'先选同一技术领域，再勾选两至三个案例。对比重点看参与者分工、验证设施和适用条件；只有登记口径一致的项目才绘制合作结构雷达图。':'Filter by technology, then select two or three cases. Compare roles, validation facilities and prerequisites; radar profiles require comparable register data.')+'</p>'+
      (book.research?'<details class="ir-advanced" open><summary>'+(lang==='zh'?'发展阶段与国际组织':'Stages and international groups')+'</summary><div class="ic-analysis-filters"><label>'+(lang==='zh'?'时间依据':'Date basis')+'<select data-filter="timeBasis"><option value="">'+(lang==='zh'?'起始阶段':'Origin cohort')+'</option><option value="activity">'+(lang==='zh'?'活动阶段':'Dated activity')+'</option></select></label><label>'+(lang==='zh'?'发展阶段':'Stage')+'<select data-filter="period"><option value="">'+t('all')+'</option>'+Object.entries(book.research.period_labels).filter(([key])=>book.cases.some(c=>c.timeline?.origin_period===key||c.timeline?.activity_periods.includes(key))).map(([key,name])=>'<option value="'+key+'">'+esc(local(name))+'</option>').join('')+'</select></label><label>'+(lang==='zh'?'组织成员国关联':'Country-group association')+'<select data-filter="organization"><option value="">'+t('all')+'</option>'+book.research.organizations.map(o=>'<option value="'+o.id+'">'+esc(local(o.name))+'</option>').join('')+'</select></label><label>'+(lang==='zh'?'关联范围':'Association scope')+'<select data-filter="organizationScope"><option value="">'+(lang==='zh'?'任一已记录参与国':'Any documented participant country')+'</option><option value="focus">'+(lang==='zh'?'牵头或主要所在地':'Coordinator or focus country')+'</option></select></label></div></details>':'')+
      '<div class="ic-toolbar"><span class="ic-result" aria-live="polite"></span><div><span class="ic-selected" aria-live="polite"></span>'+
      '<button type="button" class="ic-compare">'+t("compare")+'</button><button type="button" class="ic-clear">'+t("clear")+'</button></div></div>'+
      '<div class="ic-grid"></div><button type="button" class="load-more ic-more">'+t("more")+'</button>'+
      '</div>'+(root.GruenInnovationAnalysis?.render(book,lang)||'')+(root.GruenInnovationResearch?.insightsPanel(book,lang)||'')+
      '<details class="ic-method"><summary>'+t("framework")+'</summary><p>'+esc(local(book.analysis?.definition||t('method')))+'</p><p>'+t("method")+'</p><p>'+t("countNote")+'</p></details>'+
      '<dialog class="ic-dialog" aria-label="'+t("detail")+'"><div class="ic-dialog-head"><button type="button" class="ic-close" aria-label="'+t("close")+'">×</button></div><div class="ic-dialog-body"></div></dialog>';
    if(book.research){const select=host.querySelector('[data-filter="period"]');for(const [key,name] of Object.entries(book.research.period_labels)){if(![...select.options].some(o=>o.value===key)&&book.cases.some(c=>c.timeline?.origin_decade===key||c.timeline?.events?.some(e=>e.decade===key))){select.add(new Option(local(name),key));}}}
    // Five broad entry points; detailed research codes remain available on demand.
    const primary=host.querySelector('.ic-filters'),advanced=document.createElement('details');
    advanced.className='ir-advanced';advanced.innerHTML='<summary>'+(lang==='zh'?'详细分类':'Detailed classifications')+'</summary><div class="ic-analysis-filters"></div>';
    primary.after(advanced);const advancedFields=advanced.querySelector('div');
    for(const field of ['mode','institution','sector'])advancedFields.append(host.querySelector('[data-filter="'+field+'"]').closest('label'));
    for(const [field,dictionary,title] of [['family',FAMILIES,lang==='zh'?'合作类型':'Collaboration type'],['domain',DOMAINS,t('sector')]]){
      const label=document.createElement('label');label.innerHTML=esc(title)+'<select data-filter="'+field+'"><option value="">'+t('all')+'</option>'+Object.entries(dictionary).map(([k,v])=>'<option value="'+k+'">'+esc(local(v))+'</option>').join('')+'</select>';primary.append(label);
    }
    const grainLabel=document.createElement('label');grainLabel.innerHTML=(lang==='zh'?'记录类型':'Record level')+'<select data-filter="grain"><option value="">'+t('all')+'</option><option value="platform">'+(lang==='zh'?'机构与合作平台':'Institutions and platforms')+'</option><option value="project">'+(lang==='zh'?'资助项目':'Funded projects')+'</option></select>';primary.append(grainLabel);
    for(const field of ['archetype','province'])advancedFields.append(host.querySelector('[data-filter="'+field+'"]').closest('label'));
    host.querySelectorAll('details.ir-advanced').forEach(el=>el.open=false);
    host.querySelectorAll("select[data-filter]").forEach(el=>{el.value=filters[el.dataset.filter];el._allOptions=[...el.options].map(o=>({value:o.value,label:o.textContent}));});
    const switchView=value=>{activeView=value;host.querySelectorAll('[data-analysis-panel]').forEach(p=>p.hidden=p.dataset.analysisPanel!==value);host.querySelectorAll('[data-case-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.caseView===value)));};
    host.querySelectorAll('[data-case-view]').forEach(b=>b.addEventListener('click',()=>switchView(b.dataset.caseView)));
    const resetFilters=()=>{for(const k of Object.keys(filters))filters[k]='';visible=12;host.querySelectorAll('[data-filter]').forEach(el=>el.value='');};
    host.querySelector('.ic-reset').addEventListener('click',()=>{resetFilters();renderCards();});
    root.GruenInnovationAnalysis?.attach(host,book,lang,values=>{resetFilters();Object.assign(filters,values);host.querySelectorAll('[data-filter]').forEach(el=>el.value=filters[el.dataset.filter]);switchView('cases');renderCards();},detail);
    root.GruenInnovationResearch?.attach(host,book,lang,values=>{resetFilters();Object.assign(filters,values);host.querySelectorAll('[data-filter]').forEach(el=>el.value=filters[el.dataset.filter]);switchView('cases');renderCards();},detail);
    switchView(activeView);
    host.querySelectorAll("[data-filter]").forEach(el=>el.addEventListener(el.tagName==="SELECT"?"change":"input",()=>{
      filters[el.dataset.filter]=el.value;
      if(el.dataset.filter==='period')filters.timeScope=el.value.startsWith('cn_fyp_')||el.value==='pre_1981'?'china_plans':el.value.endsWith('s')?'global_decades':'';
      if(el.dataset.filter==='country')filters.focusCountry='';
      visible=12;renderCards();
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
    for(const el of host.querySelectorAll('select[data-filter]')){
      const field=el.dataset.filter;if(['timeBasis','organizationScope'].includes(field))continue;
      const counts=facetCounts(book,filters,field),chosen=filters[field];
      el.replaceChildren(...el._allOptions.filter(o=>!o.value||counts[o.value]>0||o.value===chosen).map(o=>{
        const option=new Option(o.label+(o.value?' ('+(counts[o.value]||0)+')':''),o.value);option.disabled=!!o.value&&!counts[o.value]&&o.value!==chosen;return option;
      }));el.value=chosen;
    }
    host.querySelector(".ic-result").textContent=cases.length+" "+t("results");
    host.querySelector(".ic-selected").textContent=t("selected")+" "+selected.size+"/3";
    host.querySelector(".ic-compare").disabled=selected.size<2;
    host.querySelector(".ic-clear").disabled=!selected.size;
    host.querySelector(".ic-grid").innerHTML=cases.slice(0,visible).map(c=>'<article class="ic-card">'+
      '<div class="ic-card-meta"><span title="'+esc(location(c))+'">'+esc(c.countries.length>3?countries(c).split(" · ").slice(0,3).join(" · ")+' +'+(c.countries.length-3):location(c))+'</span><span>'+esc(period(c))+'</span></div>'+
      '<h3>'+esc(casePresentation(c,lang).title)+'</h3><p>'+esc(casePresentation(c,lang).summary.length>190?casePresentation(c,lang).summary.slice(0,190)+'…':casePresentation(c,lang).summary)+'</p>'+compactFacts(c)+'<div class="ic-tags">'+modelTag(c)+tags(c,"modes")+'</div>'+
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
    const refs=c.evidence.map(ref=>{const s=book.sources.find(s=>s.id===ref.source_id);return s?{...s,locator:ref.locator}:null;}).filter(Boolean);
    return '<ol class="ic-sources">'+refs.map(s=>'<li>'+anchor(s.url,s.title)+'<span>'+esc(s.publisher)+' · '+esc(s.language.toUpperCase())+
      (s.published_date?' · '+esc(s.published_date):"")+'</span>'+(s.locator&&s.locator!=='Programme rules'?'<span>'+(lang==='zh'?'原文定位：':'Locator: ')+esc(s.locator)+'</span>':'')+'</li>').join("")+'</ol>';
  }
  function detail(id) {
    const c=byId(id),view=casePresentation(c,lang);
    show('<p class="overline">'+esc(location(c))+(period(c)?" · "+esc(period(c)):"")+'</p><h2>'+esc(view.title)+'</h2>'+
      '<div class="ic-tags">'+modelTag(c)+tags(c,"modes")+tags(c,"institutions")+'</div>'+
      '<p class="ic-detail-summary">'+esc(view.summary)+'</p>'+registryFacts(view)+projectFacts(c)+
      (c.timeline?.events?.length?'<section class="ir-timeline"><h3>'+(lang==='zh'?'历史节点':'Documented milestones')+'</h3><ol>'+c.timeline.events.map(e=>'<li><time>'+esc(e.date)+'</time><p>'+esc(local(e.description))+'</p>'+e.source_ids.map(id=>{const s=book.sources.find(s=>s.id===id);return s?anchor(s.url,lang==='zh'?'来源':'Source'):'';}).join(' ')+'</li>').join('')+'</ol></section>':'')+
      (["actors","mechanism","observed"].some(key=>view.sections[key]&&!view.summary.includes(view.sections[key]))?'<h3 class="ic-group-title">'+t("facts")+'</h3>':'')+
      ["actors","mechanism","observed"].filter(key=>view.sections[key]&&!view.summary.includes(view.sections[key])).map(key=>'<section><h4>'+t(key)+'</h4><p>'+esc(view.sections[key])+'</p></section>').join("")+
      partnerList(c)+((c.objective_excerpt?.en||view.original)?'<details class="ic-original"><summary>'+(view.original?(lang==='zh'?'技术内容原文':'Original technical description'):t("original"))+'</summary><p>'+esc(c.objective_excerpt?.en||view.original)+'</p></details>':"")+
      (view.programme?'<details class="ic-programme"><summary>'+(lang==='zh'?'计划共同规则':'Programme rules')+'</summary><p>'+esc(view.programme)+'</p>'+c.evidence.filter(e=>e.supports?.includes('mechanism')).map(e=>{const s=book.sources.find(s=>s.id===e.source_id);return s?anchor(s.url,s.title):'';}).join(' · ')+'</details>':'')+
      ((book.profile_axes||[]).some(a=>c.profile?.[a.id]?.score!=null)?profile([c]):'')+
      '<section><h4>'+t("factors")+'</h4><div class="ic-tags">'+tags(c,"factors")+'</div></section>'+
      (view.sections.constraints||view.sections.transfer?'<h3 class="ic-group-title">'+t("analysis")+'</h3>'+["constraints","transfer"].filter(key=>view.sections[key]).map(key=>'<section><h4>'+t(key)+'</h4><p>'+esc(view.sections[key])+'</p></section>').join(""):"")+
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
      ["summary",c=>casePresentation(c,lang).summary],
      ["timeline",registeredPeriod],
      ["grant",registeredGrant],
      ["participants",c=>c.registry_record?.universities?.length?casePresentation(c,lang).facts.filter(r=>['hosts','members'].includes(r.key)).map(r=>r.label+' '+r.value).join(' · '):
        c.registry_record?.partners?.length?(lang==='zh'?'公开列名 ':'Named ')+c.registry_record.partners.length+(lang==='zh'?' 家合作方':' partners'):
        c.project?.participant_count!==null&&c.project?.participant_count!==undefined?c.project.participant_count+' · '+c.project.company_count+(lang==='zh'?'家企业':' companies'):
        c.participants?.length?(lang==='zh'?'公开列名 ':'Named ')+c.participants.length+(lang==='zh'?' 家机构（非完整统计）':' organisations (not a complete census)'):t("missing")],
      ["mode",c=>c.modes.map(key=>label("modes",key)).join(" · ")],
      ["institution",c=>c.institutions.map(key=>label("institutions",key)).join(" · ")],
      ["factors",c=>c.factors.map(key=>label("factors",key)).join(" · ")],
      ...["mechanism","observed","constraints","transfer"].filter(key=>cases.some(c=>substantiveField(c,key,lang))).map(key=>[key,c=>substantiveField(c,key,lang)||t("missing")])
    ];
    show('<h2>'+t("compare")+'</h2>'+ (cases.some(c=>!c.project)&&cases.some(c=>c.project)?'<p>'+t("mixed")+'</p>':"")+profile(cases)+'<div class="ic-matrix-scroll" tabindex="0"><table class="ic-matrix"><thead><tr><th scope="col">'+t("field")+'</th>'+
      cases.map(c=>'<th scope="col">'+esc(casePresentation(c,lang).title)+'</th>').join("")+'</tr></thead><tbody>'+
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
  root.GruenInnovationCases={mount,filterCases,facetCounts,FAMILIES,DOMAINS,exportCsv,csvCell,radarSvg,casePresentation,substantiveField,getSnapshot:()=>book};
  if(typeof module==="object"&&module.exports)module.exports=root.GruenInnovationCases;
})(typeof window==="undefined"?globalThis:window);
