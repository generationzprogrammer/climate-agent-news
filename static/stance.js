/* Country / proposition comparisons, always backed by inspectable source spans.
   2026-11-13 (功能更新1113 handover): the topic is one of the 14 categories or 83 topics of the research dictionary
   (research.js's two-level menu), countries and negotiating groups are listed in separate tables, a topic without checked
   material says so ("证据不足") and offers the related reports as candidates — which are search results, never positions.
   Checked positions are the stance file's assertions (data/stance_pilot.json, kept as they are) plus the reviewed claims
   the private index holds for the topic (/api/research/positions). */
(() => {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const en=()=>document.documentElement.lang==='en';
  const t=(zh,eng)=>en()?eng:zh;
  const label=r=>en()?(r.name_en||r.name_zh):(r.name_zh||r.name_en);
  const text=(r,k)=>r[k+(en()?'_en':'_zh')]||'';
  const safe=s=>{try{const u=new URL(s);return ['https:','http:'].includes(u.protocol)?u.href:'#';}catch{return '#';}};
  /* Where each proposition of the stance file sits in the 83 topics: aligned by content on 2026-11-13 (an editorial
     reading, not part of the source data; a proposition that carries its own `code` keeps it). */
  const CODES={finance_delivery:'G06.01',finance_goal:'G06.01',finance_grants:'G06.06',market_article6:'G07.01',market_coordination:'G07.04',market_integrity:'G07.05',
    fossil_transition:'G03.01',fossil_subsidies:'G03.01',fossil_production:'G03.01',adaptation_indicators:'G04.01',adaptation_plans:'G04.02',adaptation_warning:'G04.03',
    mitigation_paris:'G01.01',mitigation_ndc:'G02.02',mitigation_netzero:'G02.03',mitigation_methane:'G03.06',loss_support:'G05.01',loss_fund:'G05.02',
    energy_clean:'G03.02',energy_wind:'G03.02',energy_efficiency:'G03.03',energy_technology:'G08.02',justice_equity:'G10.01',justice_workers:'G10.03',justice_participation:'G10.04',justice_trade:'G11.03',
    transparency_capacity:'G08.04',transparency_reports:'G09.02',transparency_methods:'G09.03',science_ipcc:'G09.04',science_risk:'G14.03'};
  let data=null,base=null,container=null,kit=null,store=null,view='cards',topic='G06',actor='all',proposition='all',year='all';
  const statuses=()=>Object.fromEntries(data.stances.map(s=>[s.id,label(s)]));
  const actors=()=>data.actors.filter(a=>(actor==='all'||a.id===actor)&&(view!=='cards'||actor!=='all'||rows().some(r=>r.actor_id===a.id)));
  const inTopic=code=>!topic||code===topic||String(code||'').startsWith(topic+'.');
  const props=()=>data.propositions.filter(p=>inTopic(p.code)&&(proposition==='all'||p.id===proposition));
  function rows(){const ids=new Set(props().map(p=>p.id));return data.assertions.filter(r=>ids.has(r.proposition_id)&&(actor==='all'||r.actor_id===actor)&&(year==='all'||r.statement_date.startsWith(year))).sort((a,b)=>b.statement_date.localeCompare(a.statement_date)||a.id.localeCompare(b.id));}
  function cell(actorId,propId,list=rows()){
    const items=list.filter(r=>r.actor_id===actorId&&r.proposition_id===propId);
    const latest=items.filter(r=>r.statement_date===items[0]?.statement_date);
    return {items,status:latest.length?(new Set(latest.map(r=>r.stance)).size>1?'mixed':latest[0].stance):'insufficient'};
  }
  function flag(a){return a.flagged?`<img class="stance-flag" src="./assets/flags/${esc(a.id.toLowerCase())}.svg" alt="" width="28" height="21" loading="lazy">`:`<span class="stance-group-mark" aria-hidden="true">${esc(a.id)}</span>`;}
  const FLAGS=new Set(['AU','BR','CN','EU','GB','IN','JP','US','ZA']);
  const isGroup=a=>a.kind!=='country';
  // countries and negotiating groups are two tables; the EU is an organisation of its own, never spread over its members
  const tables=list=>[[t('国家','Countries'),list.filter(a=>!isGroup(a))],[t('谈判集团与区域组织','Negotiating groups and regional organisations'),list.filter(isGroup)]].filter(g=>g[1].length);
  const topicName=code=>{const item=store?.byCode.get(code);return item?item.code+' · '+label(item):code;};
  function dateLabel(r){return `${esc(r.statement_date)} · ${esc(r.filed?r.speaker:text(r,'authority'))}`;}
  function statement(r){
    const p=data.propositions.find(v=>v.id===r.proposition_id);
    const reasons=(r.reasons||[]).map(v=>`<li>${esc(r.filed?v.text:text(v,'text'))}</li>`).join('');
    const status=r.stance in statuses()?`<span class="stance-status status-${esc(r.stance)}">${esc(statuses()[r.stance])}</span>`:`<span class="stance-status status-filed">${t('已核验表态','Checked statement')}</span>`;
    return `<div class="stance-statement"><div class="stance-proposition">${esc(label(p))}</div>${status}${r.filed&&r.summary===statuses()[r.stance]?'':`<p class="stance-summary">${esc(r.filed?r.summary:text(r,'summary'))}</p>`}<div class="stance-reason"><strong>${t('公开理由','Public reasons')}</strong>${reasons?`<ul>${reasons}</ul>`:`<p>${t('所引材料未明确给出理由。','No explicit reason is supplied in the cited passage.')}</p>`}</div><div class="stance-date">${dateLabel(r)}</div><button type="button" class="stance-evidence-button" data-stance-evidence="${esc(r.id)}">${t('查看原文证据','Inspect source evidence')} ↗</button></div>`;
  }
  function showEvidence(id){
    const record=data.assertions.find(r=>r.id===id);if(!record)return;
    let dialog=document.querySelector('#stanceEvidenceDialog');
    if(!dialog){dialog=document.createElement('dialog');dialog.id='stanceEvidenceDialog';dialog.className='research-dialog stance-dialog';document.body.append(dialog);dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});}
    const a=data.actors.find(v=>v.id===record.actor_id),p=data.propositions.find(v=>v.id===record.proposition_id);
    const head=`<button type="button" class="research-close" aria-label="${t('关闭','Close')}">×</button><p class="stance-actor-heading">${flag(a)} ${esc(label(a))}</p><h2>${esc(label(p))}</h2>`;
    if(record.filed){
      // a reviewed claim of the private index: the quote is the reviewed span of the stored text
      dialog.innerHTML=`${head}<p data-f="summary"></p><p class="stance-date">${dateLabel(record)}</p><h3>${t('立场原文','Original position evidence')}</h3><blockquote></blockquote><h3>${t('公开理由','Public reasons')}</h3><p data-f="reason"></p><a target="_blank" rel="noopener noreferrer"></a><details class="stance-provenance"><summary>${t('出处与标注','Provenance and annotation')}</summary><p>${t('人工核验：核对了发言主体、议题归属，以及引文与库内原文的字符位置。','Human-reviewed: speaker, topic and the quotation’s character position in the stored text were checked.')}</p><p data-f="review"></p></details>`;
      const part=name=>dialog.querySelector(`[data-f="${name}"]`);
      part('summary').textContent=record.summary;dialog.querySelector('blockquote').textContent=record.evidence_quote;
      part('reason').textContent=record.reasons[0]?.text||t('所引材料未明确给出理由，未作推测。','No explicit reason is supplied; no motive has been inferred.');
      const link=dialog.querySelector('a');link.textContent=(record.source_title||record.source_url)+' ↗';link.href=safe(record.source_url);
      part('review').textContent=t('审阅','Reviewed by')+': '+record.reviewer+' · '+record.reviewed_at;
    }else{
      dialog.innerHTML=`${head}<p>${esc(text(record,'summary'))}</p><p class="stance-date">${dateLabel(record)}</p><h3>${t('立场原文','Original position evidence')}</h3><blockquote lang="${esc(record.source_language)}">${esc(record.evidence_quote)}</blockquote>${record.qualifier_quote?`<h3>${t('条件与保留意见','Conditions and reservations')}</h3><blockquote>${esc(record.qualifier_quote)}</blockquote>`:''}<h3>${t('理由原文','Original reason evidence')}</h3>${record.reasons.length?record.reasons.map(r=>`<blockquote>${esc(r.quote)}</blockquote><p>${esc(text(r,'text'))}</p>`).join(''):`<p>${t('所引材料未明确给出理由，未作推测。','No explicit reason is supplied; no motive has been inferred.')}</p>`}<a href="${esc(safe(record.source_url))}" target="_blank" rel="noopener noreferrer">${esc(record.source_title)} ↗</a><details class="stance-provenance"><summary>${t('出处与标注','Provenance and annotation')}</summary><p>${t('依据官方材料逐条校编；尚无独立双人标注准确率。','AI-assisted editorial checking against official material; independently double-coded accuracy is not yet established.')}</p><p>${t('日期口径','Date basis')}: ${esc(record.date_basis||t('表态或官方文件公布日，精确到日','Statement or official publication date; day precision'))}</p><p>${t('文本指纹','Stored-text fingerprint')}: <code>${esc(record.source_sha256)}</code></p></details>`;
      const basis=dialog.querySelector('.stance-provenance p:nth-of-type(2)');
      if(basis)basis.textContent=t('日期口径','Date basis')+': '+text(record,'date_basis');
    }
    dialog.querySelector('.research-close').onclick=()=>dialog.close();dialog.showModal();
  }
  function bindEvidence(){container.querySelectorAll('[data-stance-evidence]').forEach(b=>b.onclick=()=>showEvidence(b.dataset.stanceEvidence));}

  /* Reviewed claims of the private index for the chosen topic, in the assertions' shape. A claim has no proposition of
     its own: it is listed under its topic ("已核验表态 · topic"). */
  const STANCE_WORDS=[['support',/^(支持|赞成|supports?|in favou?r)/i],['oppose',/^(反对|不支持|opposes?|against)/i],['qualified',/^(有条件|附条件|保留|conditional|qualified|reserv)/i]];
  let filedFor=null,filedRun=0;
  function withFiled(items){
    const extraProps=new Map(),extraActors=new Map();
    const made=items.map(c=>{
      const pid='filed:'+c.topic;
      if(!extraProps.has(pid)){const item=store.byCode.get(c.topic);extraProps.set(pid,{id:pid,code:c.topic,filed:true,name_zh:'已核验表态 · '+(item?item.name_zh:c.topic),name_en:'Checked statements · '+(item?item.name_en:c.topic)});}
      if(!base.actors.some(a=>a.id===c.actor)&&!extraActors.has(c.actor)){
        const place=/^[A-Z]{2}$/.test(c.actor)&&store.countries.find(v=>v.code===c.actor),group=store.groups.find(v=>v.code===c.actor);
        extraActors.set(c.actor,place?{id:c.actor,kind:'country',name_zh:place.name_zh,name_en:place.name_en}:{id:c.actor,kind:'negotiating_group',name_zh:group?.name_zh||c.actor,name_en:group?.name_en||c.actor});
      }
      return {id:'filed:'+c.cursor_id,filed:true,actor_id:c.actor,proposition_id:pid,topic_code:c.topic,statement_date:c.date,stance:(STANCE_WORDS.find(w=>w[1].test(c.stance))||['filed'])[0],
        summary:c.stance,reasons:c.reason?[{text:c.reason}]:[],evidence_quote:c.quote,speaker:c.speaker,reviewer:c.reviewer,reviewed_at:c.reviewed_at,source_url:c.url,source_title:c.title,event_id:c.id};
    });
    data={...base,actors:[...base.actors,...extraActors.values()],propositions:[...base.propositions,...extraProps.values()],assertions:[...base.assertions,...made]};
  }
  async function loadFiled(){
    if(!store?.live||filedFor===topic)return;
    const wanted=topic,run=++filedRun;
    try{
      const items=[];let cursor='';
      for(let page=0;page<5;page++){const r=await kit.api('positions',{topic:wanted,limit:100,cursor});items.push(...r.items);cursor=r.next_cursor;if(!cursor)break;}
      if(run!==filedRun||wanted!==topic)return;
      filedFor=wanted;withFiled(items);if(items.length)render();
    }catch{/* the stance file's assertions stay on screen; nothing is invented for a service that did not answer */}
  }

  /* 相关报道候选: reports of the index under the topic (and actor, year). Search results — never shown as positions. */
  function candidates(){
    const box=document.createElement('details');box.className='stance-candidates';box.id='stanceCandidates';
    const a=data.actors.find(v=>v.id===actor),item=store.byCode.get(topic);
    const known=actor==='all'&&year==='all'&&item?item.reports:null;
    const summary=document.createElement('summary');
    summary.innerHTML=`<span>${t('相关报道候选','Related reports')}</span><em>${t('未作立场判定','not adjudicated as positions')}</em><b>${known==null?'':kit.num(known)}</b>`;
    const guide=kit.el('p','research-guide',t('按当前议题、主体与年份检索到的报道，供查找原始表态的线索。报道提到某国不等于该国持有某种立场；集团报道不归于其成员。','Reports found for the current topic, actor and year: leads for locating original statements. A report that mentions a country does not establish that country’s position, and a report on a group is not attributed to its members.'));
    const list=kit.el('div','stance-candidate-list'),more=kit.el('button','research-more',t('显示更多','Show more'));more.type='button';more.hidden=true;
    const state=kit.el('p','stance-candidate-state');
    box.append(summary,guide,list,state,more);
    let cursor='',started=false,busy=false;
    const filters=()=>({topic,year:year==='all'?'':year,limit:store.pageSize,cursor,...(a?(isGroup(a)?{group:a.id}:{country:a.id}):{})});
    async function next(){
      if(busy)return;busy=true;more.hidden=true;state.textContent=t('正在检索…','Searching…');state.hidden=false;
      try{
        const page=await kit.api('events',filters());
        if(!box.isConnected)return;
        if(page.total!=null)summary.querySelector('b').textContent=kit.num(page.total);
        const made=page.items.map(report=>{const row=kit.reportRow(report,store,{topic});row.prepend(kit.el('time','rt-report-date',report.date));return row;});
        list.append(...made);kit.stagger(made);cursor=page.next_cursor;more.hidden=!cursor;
        state.hidden=Boolean(list.children.length);if(!list.children.length)state.textContent=t('当前筛选下没有检索到相关报道。','No related report was found for this selection.');
      }catch{state.textContent=t('相关报道暂时无法读取。','Related reports could not be loaded.');more.hidden=false;more.textContent=t('重试','Retry');}
      busy=false;
    }
    box.addEventListener('toggle',()=>{if(box.open&&!started){started=true;next();}});
    more.onclick=()=>{more.textContent=t('显示更多','Show more');next();};
    return box;
  }

  function frame(){
    container.innerHTML=`<div class="stance-toolbar"><div class="stance-topic-select"></div><div class="stance-downloads"><a href="./data/stance_assertions.csv" download>CSV</a><a href="./data/stance_codebook.json" download>${t('数据字典','Codebook')}</a><a href="./data/stance_assertions.jsonl" download>JSONL</a></div></div><div class="stance-view-tabs" role="tablist">${[['cards','立场卡片','Position cards'],['matrix','对比矩阵','Comparison matrix'],['timeline','时间线','Timeline']].map(([id,zh,eng])=>`<button role="tab" type="button" data-stance-view="${id}" aria-selected="${view===id}">${t(zh,eng)}</button>`).join('')}</div><div id="stanceBody"></div>`;
    if(!store.byCode.has(topic))topic=store.parents[0]?.code||'';
    const menu=kit.picker(store,{id:'stanceTopic',value:topic,onChange:v=>{topic=v;proposition='all';if(filedFor!==topic){filedFor=null;data=base;}render();loadFiled();}});
    container.querySelector('.stance-topic-select').append(menu.node);
    container.querySelectorAll('[data-stance-view]').forEach(b=>b.onclick=()=>{view=b.dataset.stanceView;container.querySelectorAll('[data-stance-view]').forEach(v=>v.setAttribute('aria-selected',String(v===b)));render();});
  }
  function render(){
    if(!container||!container.isConnected||!data)return;
    const body=container.querySelector('#stanceBody');if(!body)return;
    if(actor!=='all'&&!data.actors.some(a=>a.id===actor))actor='all';
    const inScope=data.propositions.filter(p=>inTopic(p.code));
    if(proposition!=='all'&&!inScope.some(p=>p.id===proposition))proposition='all';
    const years=[...new Set(data.assertions.map(r=>r.statement_date.slice(0,4)))].sort().reverse();
    const options=(items,value)=>items.map(r=>`<option value="${esc(r.id)}" ${r.id===value?'selected':''}>${esc(label(r))}</option>`).join('');
    const allRows=rows();const s=statuses();
    const actorOptions=tables(data.actors).map(([name,list])=>`<optgroup label="${esc(name)}">${options(list,actor)}</optgroup>`).join('');
    body.innerHTML=`<div class="stance-filters"><label>${t('主体','Actor')}<select id="stanceActor"><option value="all">${t('全部主体','All actors')}</option>${actorOptions}</select></label><label>${t('具体主张','Specific proposition')}<select id="stanceProposition" ${inScope.length?'':'disabled'}><option value="all">${inScope.length?t('本议题全部主张','All propositions in this topic'):t('本议题尚无已核验主张','No checked proposition in this topic')}</option>${options(inScope,proposition)}</select></label><label>${t('表态年份','Statement year')}<select id="stanceYear"><option value="all">${t('全部年份','All years')}</option>${years.map(y=>`<option ${year===y?'selected':''}>${y}</option>`).join('')}</select></label></div><p class="stance-scope">${t('按具体主张比较最新有日期记录；空白表示证据不足，不表示中立或反对。集团表态不自动代表每个成员国，欧盟作为单独主体列出。','Compare the latest dated record for each proposition. A blank means insufficient evidence, not neutrality or opposition. Group statements are not attributed to each member; the EU is listed as an actor of its own.')}</p><div id="stanceContent"></div>`;
    const content=body.querySelector('#stanceContent');
    const missing=(inside)=>`<div class="stance-missing ${inside?'':'stance-empty'}"><span>${esc(s.insufficient)}</span><p>${inScope.length?t('当前筛选下没有可归属该主体的已核对表态。','No source-checked statement attributable to this actor matches the selection.'):t('该议题尚无已核验立场。相关报道可以作为查找线索，但报道候选不代表任何国家的立场。','No checked position exists for this topic yet. Related reports can serve as leads, but a report is not a position.')}</p>${inside||!store.live?'':`<button type="button" class="research-more" data-stance-candidates>${t('展开相关报道候选','Open related reports')}</button>`}</div>`;
    if(view==='cards'){
      const shown=actors();
      content.innerHTML=shown.length?`<p class="stance-card-count">${t('当前有已核对证据的主体','Actors with source-checked evidence')}: ${shown.length}</p>`+tables(shown).map(([name,list])=>`<section class="stance-table"><h3 class="stance-table-title">${esc(name)}<span>${list.length}</span></h3><div class="stance-card-grid">${list.map(a=>{
        const entries=props().map(p=>cell(a.id,p.id,allRows)).filter(c=>c.items.length);
        return `<article class="stance-country-card"><h3 class="stance-actor-heading">${flag(a)}<span>${esc(label(a))}</span></h3>${entries.length?entries.map(c=>statement(c.items[0])+(c.status==='mixed'?`<p>${t('同日存在不同表述，请查阅时间线中的全部证据。','Differing statements on the same day; inspect all evidence in the timeline.')}</p>`:'')).join(''):missing(true)}</article>`;
      }).join('')}</div></section>`).join(''):missing(false);
    }else if(view==='matrix'){
      const columns=props();
      content.innerHTML=columns.length?`<p class="stance-matrix-help">${t('点击单元格查看该主张的原文依据。每格采用最新日期，不按转载数量投票。','Select a cell to inspect its evidence. Each cell uses the latest date, not a majority vote over reposts.')}</p>`+tables(actors()).map(([name,list])=>`<div class="stance-matrix-wrap"><table class="stance-matrix"><caption>${esc(topicName(topic))} · ${esc(name)}</caption><thead><tr><th scope="col">${esc(name)}</th>${columns.map(p=>`<th scope="col">${esc(label(p))}</th>`).join('')}</tr></thead><tbody>${list.map(a=>`<tr><th scope="row"><span class="stance-actor-heading">${flag(a)}${esc(label(a))}</span></th>${columns.map(p=>{const c=cell(a.id,p.id,allRows);const shownStatus=s[c.status]||t('已核验表态','Checked statement');return `<td class="stance-matrix-cell status-${esc(c.status)}">${c.items.length?`<button type="button" data-stance-evidence="${esc(c.items[0].id)}" aria-label="${esc(label(a)+' · '+label(p)+' · '+shownStatus)}"><strong>${esc(shownStatus)}</strong><span>${esc(c.items[0].statement_date)}</span><span>${new Set(c.items.map(r=>r.event_id)).size} ${t('次表态',new Set(c.items.map(r=>r.event_id)).size===1?'statement event':'statement events')}</span></button>`:`<span>${esc(s.insufficient)}</span>`}</td>`;}).join('')}</tr>`).join('')}</tbody></table></div>`).join('')+`<div class="stance-legend">${data.stances.map(v=>`<span class="status-${v.id}">${esc(label(v))}</span>`).join('')}</div>`:missing(false);
    }else{
      content.innerHTML=allRows.length?`<ol class="stance-timeline">${allRows.map(r=>{const a=data.actors.find(v=>v.id===r.actor_id);return `<li><div class="stance-timeline-date">${esc(r.statement_date)}</div><article class="stance-country-card"><h3 class="stance-actor-heading">${flag(a)}${esc(label(a))}</h3>${statement(r)}</article></li>`;}).join('')}</ol>`:missing(false);
    }
    for(const [id,set] of [['stanceActor',v=>actor=v],['stanceProposition',v=>proposition=v],['stanceYear',v=>year=v]])body.querySelector('#'+id).onchange=e=>{set(e.target.value);render();};
    bindEvidence();
    if(store.live){const box=candidates();body.append(box);body.querySelector('[data-stance-candidates]')?.addEventListener('click',()=>{box.open=true;box.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});});}
    kit.stagger(content.querySelectorAll('.stance-country-card, .stance-matrix tbody tr, .stance-empty'));
  }
  let loading=null;
  function load(){
    loading=loading||fetch('./data/stance_pilot.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('unavailable');return r.json();}).then(v=>{
      v.propositions.forEach(p=>{p.code=p.code||CODES[p.id]||null;});
      v.actors.forEach(a=>{a.flagged=FLAGS.has(a.id);});
      base=v;data=v;return v;});
    loading.catch(()=>{loading=null;});
    return loading;
  }
  /* How many checked assertions of the stance file sit under each of the 83 codes (for the topic menu's second count). */
  const counts=()=>load().then(v=>{const code=new Map(v.propositions.map(p=>[p.id,p.code])),n={};v.assertions.forEach(r=>{const c=code.get(r.proposition_id);if(c)n[c]=(n[c]||0)+1;});return n;});
  function mount(node,tools){container=node;kit=tools||window.GREEN_RESEARCH_KIT;store=tools?.store||store;
    if(!kit||!store){container.textContent=t('立场证据暂时无法读取。','Position evidence is temporarily unavailable.');return;}
    if(data){frame();render();loadFiled();return;}
    container.innerHTML=`<p class="research-loading">${t('正在读取立场证据…','Loading position evidence…')}</p>`;
    load().then(()=>{if(!container?.isConnected)return;frame();render();loadFiled();}).catch(()=>{if(container?.isConnected)container.innerHTML=`<p>${t('立场证据暂时无法读取。','Position evidence is temporarily unavailable.')}</p><button type="button" id="stanceRetry">${t('重新读取','Retry')}</button>`;container?.querySelector('#stanceRetry')?.addEventListener('click',()=>mount(container,tools));});
  }
  window.GREEN_STANCE={mount,counts};
})();
