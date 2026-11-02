/* Country/proposition comparisons, always backed by inspectable source spans. */
(() => {
  'use strict';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const en=()=>document.documentElement.lang==='en';
  const t=(zh,eng)=>en()?eng:zh;
  const label=r=>en()?r.name_en:r.name_zh;
  const text=(r,k)=>r[k+(en()?'_en':'_zh')]||'';
  const safe=s=>{try{const u=new URL(s);return u.protocol==='https:'?u.href:'#';}catch{return '#';}};
  let data=null,container=null,view='cards',topic='finance',actor='all',proposition='all',year='all';
  const statuses=()=>Object.fromEntries(data.stances.map(s=>[s.id,label(s)]));
  const actors=()=>data.actors.filter(a=>actor==='all'||a.id===actor);
  const props=()=>data.propositions.filter(p=>p.topic===topic&&(proposition==='all'||p.id===proposition));
  function rows(){const ids=new Set(props().map(p=>p.id));return data.assertions.filter(r=>ids.has(r.proposition_id)&&(actor==='all'||r.actor_id===actor)&&(year==='all'||r.statement_date.startsWith(year))).sort((a,b)=>b.statement_date.localeCompare(a.statement_date)||a.id.localeCompare(b.id));}
  function cell(actorId,propId,list=rows()){
    const items=list.filter(r=>r.actor_id===actorId&&r.proposition_id===propId);
    const latest=items.filter(r=>r.statement_date===items[0]?.statement_date);
    return {items,status:latest.length?(new Set(latest.map(r=>r.stance)).size>1?'mixed':latest[0].stance):'insufficient'};
  }
  function flag(a){return a.kind==='negotiating_group'?'<span class="stance-group-mark" aria-hidden="true">G77</span>':`<img class="stance-flag" src="./assets/flags/${esc(a.id.toLowerCase())}.svg" alt="" width="28" height="21" loading="lazy">`;}
  function dateLabel(r){return `${esc(r.statement_date)} · ${esc(text(r,'authority'))}`;}
  function statement(r){
    const p=data.propositions.find(v=>v.id===r.proposition_id);
    const reasons=(r.reasons||[]).map(v=>`<li>${esc(text(v,'text'))}</li>`).join('');
    return `<div class="stance-statement"><div class="stance-proposition">${esc(label(p))}</div><span class="stance-status status-${esc(r.stance)}">${esc(statuses()[r.stance])}</span><p class="stance-summary">${esc(text(r,'summary'))}</p><div class="stance-reason"><strong>${t('公开理由','Public reasons')}</strong>${reasons?`<ul>${reasons}</ul>`:`<p>${t('所引材料未明确给出理由。','No explicit reason is supplied in the cited passage.')}</p>`}</div><div class="stance-date">${dateLabel(r)}</div><button type="button" class="stance-evidence-button" data-stance-evidence="${esc(r.id)}">${t('查看原文证据','Inspect source evidence')} ↗</button></div>`;
  }
  function showEvidence(id){
    const record=data.assertions.find(r=>r.id===id);if(!record)return;
    let dialog=document.querySelector('#stanceEvidenceDialog');
    if(!dialog){dialog=document.createElement('dialog');dialog.id='stanceEvidenceDialog';dialog.className='research-dialog stance-dialog';document.body.append(dialog);dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});}
    const a=data.actors.find(v=>v.id===record.actor_id),p=data.propositions.find(v=>v.id===record.proposition_id);
    dialog.innerHTML=`<button type="button" class="research-close" aria-label="${t('关闭','Close')}">×</button><p class="stance-actor-heading">${flag(a)} ${esc(label(a))}</p><h2>${esc(label(p))}</h2><p>${esc(text(record,'summary'))}</p><p class="stance-date">${dateLabel(record)}</p><h3>${t('立场原文','Original position evidence')}</h3><blockquote lang="${esc(record.source_language)}">${esc(record.evidence_quote)}</blockquote>${record.qualifier_quote?`<h3>${t('条件与保留意见','Conditions and reservations')}</h3><blockquote>${esc(record.qualifier_quote)}</blockquote>`:''}<h3>${t('理由原文','Original reason evidence')}</h3>${record.reasons.length?record.reasons.map(r=>`<blockquote>${esc(r.quote)}</blockquote><p>${esc(text(r,'text'))}</p>`).join(''):`<p>${t('所引材料未明确给出理由，未作推测。','No explicit reason is supplied; no motive has been inferred.')}</p>`}<a href="${esc(safe(record.source_url))}" target="_blank" rel="noopener noreferrer">${esc(record.source_title)} ↗</a><details class="stance-provenance"><summary>${t('出处与标注','Provenance and annotation')}</summary><p>${t('依据官方材料逐条校编；尚无独立双人标注准确率。','AI-assisted editorial checking against official material; independently double-coded accuracy is not yet established.')}</p><p>${t('日期口径','Date basis')}: ${esc(record.date_basis||t('表态或官方文件公布日，精确到日','Statement or official publication date; day precision'))}</p><p>${t('文本指纹','Stored-text fingerprint')}: <code>${esc(record.source_sha256)}</code></p></details>`;
    const basis=dialog.querySelector('.stance-provenance p:nth-of-type(2)');
    if(basis)basis.textContent=t('日期口径','Date basis')+': '+text(record,'date_basis');
    dialog.querySelector('.research-close').onclick=()=>dialog.close();dialog.showModal();
  }
  function bindEvidence(){container.querySelectorAll('[data-stance-evidence]').forEach(b=>b.onclick=()=>showEvidence(b.dataset.stanceEvidence));}
  function render(){
    if(!container||!container.isConnected||!data)return;
    const years=[...new Set(data.assertions.map(r=>r.statement_date.slice(0,4)))].sort().reverse();
    const options=(items,value)=>items.map(r=>`<option value="${esc(r.id)}" ${r.id===value?'selected':''}>${esc(label(r))}</option>`).join('');
    const allRows=rows();const s=statuses();
    container.innerHTML=`<div class="stance-toolbar"><div class="stance-topic-tabs" aria-label="${t('比较议题','Comparison topics')}">${data.topics.map(v=>`<button type="button" data-stance-topic="${v.id}" aria-pressed="${topic===v.id}">${esc(label(v))}</button>`).join('')}</div><div class="stance-downloads"><a href="./data/stance_assertions.csv" download>CSV</a><a href="./data/stance_codebook.json" download>${t('数据字典','Codebook')}</a><a href="./data/stance_assertions.jsonl" download>JSONL</a></div></div><div class="stance-view-tabs" role="tablist">${[['cards','立场卡片','Position cards'],['matrix','对比矩阵','Comparison matrix'],['timeline','时间线','Timeline']].map(([id,zh,eng])=>`<button role="tab" type="button" data-stance-view="${id}" aria-selected="${view===id}">${t(zh,eng)}</button>`).join('')}</div><div class="stance-filters"><label>${t('主体','Actor')}<select id="stanceActor"><option value="all">${t('全部主体','All actors')}</option>${options(data.actors,actor)}</select></label><label>${t('具体主张','Specific proposition')}<select id="stanceProposition"><option value="all">${t('本议题全部主张','All propositions in this topic')}</option>${options(data.propositions.filter(p=>p.topic===topic),proposition)}</select></label><label>${t('表态年份','Statement year')}<select id="stanceYear"><option value="all">${t('全部年份','All years')}</option>${years.map(y=>`<option ${year===y?'selected':''}>${y}</option>`).join('')}</select></label></div><p class="stance-scope">${t('按具体主张比较最新有日期记录；空白表示证据不足。集团表态不自动代表每个成员国。','Compare the latest dated record for each proposition. Missing evidence is not neutrality. Group statements are not attributed to each member.')}</p><div id="stanceContent"></div>`;
    const content=container.querySelector('#stanceContent');
    if(view==='cards'){
      content.innerHTML=`<div class="stance-card-grid">${actors().map(a=>{
        const entries=props().map(p=>cell(a.id,p.id,allRows)).filter(c=>c.items.length);
        return `<article class="stance-country-card"><h3 class="stance-actor-heading">${flag(a)}<span>${esc(label(a))}</span></h3>${entries.length?entries.map(c=>statement(c.items[0])+(c.status==='mixed'?`<p>${t('同日存在不同表述，请查阅时间线中的全部证据。','Differing statements on the same day; inspect all evidence in the timeline.')}</p>`:'')).join(''):`<div class="stance-missing"><span>${esc(s.insufficient)}</span><p>${t('当前筛选下没有可归属该主体的已核对表态。','No source-checked statement attributable to this actor matches the selection.')}</p></div>`}</article>`;
      }).join('')}</div>`;
    }else if(view==='matrix'){
      content.innerHTML=`<p class="stance-matrix-help">${t('点击单元格查看该主张的原文依据。每格采用最新日期，不按转载数量投票。','Select a cell to inspect its evidence. Each cell uses the latest date, not a majority vote over reposts.')}</p><div class="stance-matrix-wrap"><table class="stance-matrix"><caption>${esc(label(data.topics.find(v=>v.id===topic)))} · ${t('具体主张对比','Specific-proposition comparison')}</caption><thead><tr><th scope="col">${t('国家或集团','Country or group')}</th>${props().map(p=>`<th scope="col">${esc(label(p))}</th>`).join('')}</tr></thead><tbody>${actors().map(a=>`<tr><th scope="row"><span class="stance-actor-heading">${flag(a)}${esc(label(a))}</span></th>${props().map(p=>{const c=cell(a.id,p.id,allRows);return `<td class="stance-matrix-cell status-${c.status}">${c.items.length?`<button type="button" data-stance-evidence="${esc(c.items[0].id)}" aria-label="${esc(label(a)+' · '+label(p)+' · '+s[c.status])}"><strong>${esc(s[c.status])}</strong><span>${esc(c.items[0].statement_date)}</span><span>${new Set(c.items.map(r=>r.event_id)).size} ${t('次表态','statement events')}</span></button>`:`<span>${esc(s.insufficient)}</span>`}</td>`;}).join('')}</tr>`).join('')}</tbody></table></div><div class="stance-legend">${data.stances.map(v=>`<span class="status-${v.id}">${esc(label(v))}</span>`).join('')}</div>`;
    }else{
      content.innerHTML=allRows.length?`<ol class="stance-timeline">${allRows.map(r=>{const a=data.actors.find(v=>v.id===r.actor_id);return `<li><div class="stance-timeline-date">${esc(r.statement_date)}</div><article class="stance-country-card"><h3 class="stance-actor-heading">${flag(a)}${esc(label(a))}</h3>${statement(r)}</article></li>`;}).join('')}</ol>`:`<div class="stance-missing">${t('当前筛选下没有已核对表态。','No source-checked statements match this selection.')}</div>`;
    }
    container.querySelectorAll('[data-stance-topic]').forEach(b=>b.onclick=()=>{topic=b.dataset.stanceTopic;proposition='all';render();});
    container.querySelectorAll('[data-stance-view]').forEach(b=>b.onclick=()=>{view=b.dataset.stanceView;render();});
    for(const [id,set] of [['stanceActor',v=>actor=v],['stanceProposition',v=>proposition=v],['stanceYear',v=>year=v]])container.querySelector('#'+id).onchange=e=>{set(e.target.value);render();};
    bindEvidence();
  }
  let loading=null;
  function mount(node){container=node;if(data){render();return;}
    container.innerHTML=`<p>${t('正在读取立场证据…','Loading position evidence…')}</p>`;
    loading=loading||fetch('./data/stance_pilot.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('unavailable');return r.json();}).then(v=>{data=v;render();}).catch(()=>{loading=null;if(container?.isConnected)container.innerHTML=`<p>${t('立场证据暂时无法读取。','Position evidence is temporarily unavailable.')}</p><button type="button" id="stanceRetry">${t('重新读取','Retry')}</button>`;container?.querySelector('#stanceRetry')?.addEventListener('click',()=>mount(container));});
  }
  window.GREEN_STANCE={mount};
})();
