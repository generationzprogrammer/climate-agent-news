/* Research tools: 国家立场 / 事件追踪 / 我的关注 / 数据与方法.
   2026-11-13 (功能更新1113 handover):
   · topics are the 14 × 83 dictionary (codes, not Chinese names), chosen in a two-level menu whose rows give two
     separate numbers: reports that can be searched, and positions that have been checked against their source;
   · 事件追踪 is a timeline of reports from the private index (/api/research/events: 30 metadata rows a page, never a
     body) — reports on one topic are not merged into an "event";
   · 文本对照 is gone (its tab, view and bindings; the stored texts are untouched); #compare lands on #research;
   · data/research_index.json (≈ 26 MB) is read only by 我的关注 and the 原文语料 list, not on arrival (data-index="lazy"
     on the script tag; without it — the main site, whose database reads the same data — it loads at once as before).
   Everything that comes from a source text or the API is written with textContent; links are http / https only.
   Visitor preferences stay in this browser. */
(() => {
  'use strict';
  const host=document.getElementById('research'); if(!host)return;
  const LAZY=document.currentScript?.dataset.index==='lazy';
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const url=s=>{try{const u=new URL(s);return ['https:','http:'].includes(u.protocol)?u.href:'#';}catch{return '#';}};
  const en=()=>document.documentElement.lang==='en';
  const t=(zh,eng)=>en()?eng:zh;
  const title=r=>en()?(r.title_en||r.title_original):(r.title_zh||r.title_original);
  const passage=r=>en()?(r.source_text_en||r.source_text):(r.source_text_zh||r.source_text);
  const date=s=>String(s||'').slice(0,10);
  const label=r=>en()?(r.label_en||r.label_zh):(r.label_zh||r.label_en);
  const name=r=>en()?(r.name_en||r.name_zh):(r.name_zh||r.name_en);
  const num=n=>n==null?'—':Number(n).toLocaleString('en-US');
  const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n;};
  const still=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
  let data=null,tab='positions',country='',theme='',track='',query='',visible=20,watch={countries:[],themes:[],groups:[]};
  try{const saved=JSON.parse(localStorage.getItem('green-research-watch-v1')||'null');if(saved&&Array.isArray(saved.countries)&&Array.isArray(saved.themes))watch={...watch,...saved};}catch{}
  let dialog=document.createElement('dialog');dialog.className='research-dialog';document.body.append(dialog);

  /* ---------- motion: items rise in one after another; figures count to their value ---------- */
  function stagger(nodes){
    if(still())return;
    [...nodes].forEach((n,i)=>{n.style.setProperty('--i',Math.min(i,16));n.classList.add('rt-rise');n.addEventListener('animationend',()=>n.classList.remove('rt-rise'),{once:true});});
  }
  function roll(node,to){
    const from=Number(node.dataset.value||0);node.dataset.value=to??'';
    if(to==null||still()||from===to||!node.isConnected){node.textContent=num(to);return;}
    const start=performance.now(),step=now=>{
      if(Number(node.dataset.value)!==to)return;
      const p=Math.min(1,(now-start)/620),e=1-Math.pow(1-p,4);
      node.textContent=num(Math.round(from+(to-from)*e));
      if(p<1)requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  /* ---------- the private index: same-origin API, metadata only ---------- */
  async function api(mode,filters={},signal){
    if(!['positions','events','topics'].includes(mode))throw new Error('Invalid mode');
    const q=new URLSearchParams(Object.entries(filters).filter(([,v])=>v!==''&&v!=null)).toString();
    const r=await fetch('/api/research/'+mode+(q?'?'+q:''),{signal,credentials:'same-origin'});
    if(!r.ok)throw new Error('Research API '+r.status);
    return r.json();
  }
  /* The dictionary with its two counts per code. Without the service (another host, a local preview) the list still
     comes from research-taxonomy.json and the report counts are unknown ("—"), not zero. */
  let topicsRequest=null;
  function topics(){
    topicsRequest=topicsRequest||(async()=>{
      const stanceCounts=Promise.resolve().then(()=>window.GREEN_STANCE?.counts?.()??{}).catch(()=>({})); // asked for alongside the dictionary
      let live=true,raw;
      try{raw=await api('topics');}
      catch{live=false;const r=await fetch('./research-taxonomy.json');if(!r.ok)throw new Error('taxonomy');raw=await r.json();}
      const checked=await stanceCounts;
      const filed=raw.position_counts||{};
      const byCode=new Map();
      const subs=raw.subcategories.map(s=>({code:s.code,parent:s.parent,name_zh:s.name_zh,name_en:s.name_en,reports:live?(s.reports||0):null,positions:(checked[s.code]||0)+(filed[s.code]||0)}));
      const parents=raw.parents.map(p=>{const mine=subs.filter(s=>s.parent===p.code);return {code:p.code,name_zh:p.name_zh,name_en:p.name_en,reports:live?(p.reports||0):null,positions:mine.reduce((n,s)=>n+s.positions,0),subs:mine};});
      [...parents,...subs].forEach(v=>byCode.set(v.code,v));
      return {live,version:raw.version,parents,subs,byCode,countries:raw.countries||[],groups:raw.groups||[],total:live?raw.total:null,range:raw.range||null,years:raw.years||{},pageSize:raw.page_size||30,
        positions:subs.reduce((n,s)=>n+s.positions,0)};
    })();
    topicsRequest.catch(()=>{topicsRequest=null;});
    return topicsRequest;
  }

  /* ---------- the two-level topic menu: 14 categories that fold, 83 topics, two counts a row ---------- */
  function picker(store,{id,value='',all=false,onChange}){
    const root=el('div','rt-topic'),button=el('button','rt-topic-button'),panel=el('div','rt-topic-panel');
    button.type='button';if(id)button.id=id;button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-expanded','false');
    panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-label',t('选择议题','Choose a topic'));
    // the face: label, code + name, the two figures (kept as nodes so they can count to a new value)
    const code=el('b','rt-code'),text=el('span','rt-topic-name'),reports=el('b'),positions=el('b');
    const value_=el('span','rt-topic-value');value_.append(code,text);
    const figures=el('span','rt-topic-figures');
    const f1=el('span',null,t('可检索报道','Searchable reports')+' '),f2=el('span',null,t('已核验立场','Checked positions')+' ');f1.append(reports);f2.append(positions);figures.append(f1,f2);
    button.append(el('span','rt-topic-label',t('议题','Topic')),value_,figures,el('i','rt-chevron'));
    function face(){
      const item=store.byCode.get(value);
      code.textContent=item?item.code:'';code.hidden=!item;
      text.textContent=item?name(item):t('全部议题','All topics');
      roll(reports,item?item.reports:store.total);roll(positions,item?item.positions:store.positions);
    }
    // the menu
    const search=el('input','rt-topic-search');search.type='search';search.placeholder=t('筛选议题或编码','Filter by name or code');search.setAttribute('aria-label',search.placeholder);
    const head=el('div','rt-topic-head');head.append(search,el('span','rt-col',t('可检索报道','Reports')),el('span','rt-col',t('已核验立场','Positions')));
    const list=el('div','rt-topic-list');panel.append(head,list);
    const open=new Set();{const item=store.byCode.get(value);if(item)open.add(item.parent||item.code);}
    const row=(cls,item,textValue)=>{
      const b=el('button',cls);b.type='button';b.dataset.code=item?item.code:'';
      if((item?item.code:'')===value)b.setAttribute('aria-current','true');
      b.append(el('b','rt-code',item?item.code:''),el('span','rt-row-name',textValue),el('span','rt-n',num(item?item.reports:store.total)),el('span','rt-n rt-n-positions',num(item?item.positions:store.positions)));
      return b;
    };
    function draw(){
      const words=search.value.trim().toLowerCase();
      const hit=s=>!words||[s.code,s.name_zh,s.name_en].some(v=>v.toLowerCase().includes(words));
      list.replaceChildren();
      if(all&&!words)list.append(row('rt-sub rt-all',null,t('全部议题','All topics')));
      store.parents.forEach(p=>{
        const mine=p.subs.filter(s=>hit(s)||hit(p));if(!mine.length)return;
        const shown=words?true:open.has(p.code);
        const section=el('section','rt-parent');if(shown)section.dataset.open='';
        const head=el('button','rt-parent-row');head.type='button';head.dataset.parent=p.code;head.setAttribute('aria-expanded',String(shown));
        head.append(el('i','rt-chevron'),el('b','rt-code',p.code),el('span','rt-row-name',name(p)),el('span','rt-n',num(p.reports)),el('span','rt-n rt-n-positions',num(p.positions)));
        const fold=el('div','rt-subs'),inner=el('div','rt-subs-inner');fold.inert=!shown;
        if(!words)inner.append(row('rt-sub rt-whole',p,t('本大类全部议题','Whole category')));
        mine.forEach(s=>inner.append(row('rt-sub',s,name(s))));
        fold.append(inner);section.append(head,fold);list.append(section);
      });
      if(!list.children.length)list.append(el('p','rt-topic-none',t('没有匹配的议题。','No topic matches.')));
    }
    function setOpen(next,focus=true){
      if(panel.hidden===!next)return;
      panel.hidden=!next;button.setAttribute('aria-expanded',String(next));root.toggleAttribute('data-open',next);
      if(next){search.value='';draw();document.addEventListener('pointerdown',outside,true);
        if(matchMedia('(hover: hover) and (pointer: fine)').matches)search.focus({preventScroll:true});
        list.querySelector('[aria-current]')?.scrollIntoView({block:'nearest'});}
      else{document.removeEventListener('pointerdown',outside,true);if(focus)button.focus({preventScroll:true});}
    }
    const outside=e=>{if(!root.contains(e.target))setOpen(false,false);};
    button.onclick=()=>setOpen(panel.hidden);
    search.oninput=draw;
    list.onclick=e=>{
      const parent=e.target.closest('.rt-parent-row');
      if(parent){const p=parent.dataset.parent,section=parent.parentElement,now=!open.has(p);now?open.add(p):open.delete(p);
        if(search.value.trim())return;
        section.toggleAttribute('data-open',now);parent.setAttribute('aria-expanded',String(now));section.querySelector('.rt-subs').inert=!now;return;}
      const sub=e.target.closest('.rt-sub');if(!sub)return;
      value=sub.dataset.code;const item=store.byCode.get(value);if(item){open.clear();open.add(item.parent||item.code);}
      face();setOpen(false);onChange?.(value);
    };
    panel.onkeydown=e=>{
      if(e.key==='Escape'){e.stopPropagation();setOpen(false);return;}
      if(e.key!=='ArrowDown'&&e.key!=='ArrowUp')return;
      const items=[search,...list.querySelectorAll('button')].filter(b=>!b.closest('[inert]'));
      const at=items.indexOf(document.activeElement),next=items[Math.max(0,Math.min(items.length-1,at+(e.key==='ArrowDown'?1:-1)))];
      if(next){e.preventDefault();next.focus();}
    };
    root.append(button,panel);face();
    return {node:root,get value(){return value;},set(next){value=next;const item=store.byCode.get(value);if(item)open.add(item.parent||item.code);face();if(!panel.hidden)draw();}};
  }

  /* One report of the index: title (link to the publisher), publisher, its topics and countries. Text nodes only. */
  function reportRow(item,store,{topic='',onTopic,onCountry}={}){
    const row=el('article','rt-report');
    const heading=(en()?item.title_en:item.title_zh)||item.title||item.url;
    const href=url(item.url);
    const head=href==='#'?el('span','rt-report-title'):el('a','rt-report-title');
    head.append(el('span',null,heading));
    if(href!=='#'){head.href=href;head.target='_blank';head.rel='noopener noreferrer';head.append(el('span','rt-out','↗'));head.lastChild.setAttribute('aria-hidden','true');}
    const meta=el('div','rt-report-meta');meta.append(el('span','rt-publisher',item.publisher||''));
    const chips=el('span','rt-chips');
    const codes=[...(item.topics||[])].sort((a,b)=>Number(b===topic||b.startsWith(topic+'.'))-Number(a===topic||a.startsWith(topic+'.')));
    codes.slice(0,3).forEach(code=>{const s=store.byCode.get(code);if(!s)return;const chip=el(onTopic?'button':'span','rt-chip');if(onTopic){chip.type='button';chip.onclick=()=>onTopic(code);}chip.append(el('b',null,code),el('span',null,name(s)));chips.append(chip);});
    if(codes.length>3)chips.append(el('span','rt-chip rt-chip-more','+'+(codes.length-3)));
    const places=item.countries||[];
    places.slice(0,3).forEach(code=>{const c=store.countries.find(v=>v.code===code);const chip=el(onCountry?'button':'span','rt-chip rt-chip-place',c?name(c):code);if(onCountry){chip.type='button';chip.onclick=()=>onCountry(code);}chips.append(chip);});
    if(places.length>3)chips.append(el('span','rt-chip rt-chip-more','+'+(places.length-3)));
    meta.append(chips);row.append(head,meta);return row;
  }
  const kit={api,topics,picker,reportRow,stagger,roll,num,el};

  /* ---------- 我的关注 and the 原文语料 list: the stored excerpts (data/research_index.json), on demand ---------- */
  let indexRequest=null,indexFailed=false;
  function loadIndex(){
    indexRequest=indexRequest||fetch('./data/research_index.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error(String(r.status));return r.json();}).then(v=>{const byId=new Map(v.records.map(r=>[r.text_id,r]));v.events.forEach(e=>e.records=e.records.map(r=>byId.get(r.text_id)).filter(Boolean));data=v;window.GREEN_RESEARCH={texts:new Map(v.records.map(r=>[r.canonical_url,r])),open:detail};document.dispatchEvent(new CustomEvent('green:research-ready'));if(tab==='watch')show();}).catch(()=>{indexFailed=true;document.dispatchEvent(new CustomEvent('green:research-unavailable'));if(tab==='watch')show();});
    return indexRequest;
  }
  window.GREEN_RESEARCH_LOAD=loadIndex;
  const countryName=(c,english=en())=>{if(typeof c==='string')return c;const canonical=(data.countries||[]).find(v=>v.alpha2===c.alpha2)||c;return String((english?canonical.name_en:canonical.name_zh)||c.alpha3||c.alpha2||'');};
  const countryList=()=>[...new Map(data.records.flatMap(r=>r.country_codes||[]).filter(c=>typeof c==='object'&&c.alpha2).map(c=>[c.alpha2,{...c,name_zh:countryName(c,false),name_en:countryName(c,true)}])).values()].sort((a,b)=>countryName(a).localeCompare(countryName(b)));
  const countries=r=>(r.country_codes||[]).map(c=>typeof c==='string'?c:c.alpha2);
  const groups=r=>{const text=r.source_text+' '+r.title_original;return [['EU',/European Union|\bEU\b|欧盟/i],['AOSIS',/\bAOSIS\b|Small Island States|小岛屿国家联盟/i],['G77',/G77|七十七国集团/i],['LDC',/Least Developed Countries|\bLDCs\b|最不发达国家/i]].filter(x=>x[1].test(text)).map(x=>x[0]);};
  function matches(r){return (!country||countries(r).includes(country))&&(!theme||(r.governance_themes||[]).some(v=>v.id===theme))&&(!track||r.track===track)&&(!query||[r.title_original,r.title_zh,r.title_en,r.source_text,r.source_text_zh,r.source_text_en].filter(Boolean).join(' ').toLowerCase().includes(query.toLowerCase()));}
  const csvCell = value=>{let s=String(value??'');if(/^[\s]*[=+@-]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
  function download(rows,file){const csv=rows.map(row=>row.map(csvCell).join(',')).join('\r\n');const blob=new Blob(['﻿'+csv],{type:'text/csv;charset=utf-8'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download=file+'-'+new Date().toISOString().slice(0,10)+'.csv';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(link.href),1000);}
  function selectionRecords(){return data.records.filter(r=>matches(r)&&((!watch.countries.length||countries(r).some(c=>watch.countries.includes(c)))&&(!watch.themes.length||(r.governance_themes||[]).some(c=>watch.themes.includes(c.id)))&&(!watch.groups.length||groups(r).some(c=>watch.groups.includes(c)))));}
  function source(r){return `<div class="research-meta"><span>${esc(date(r.published_at))}</span><span>${esc(r.source_name||'')}</span><a href="${esc(url(r.publisher_url||r.canonical_url))}" target="_blank" rel="noopener noreferrer">${t('原文','Source')} ↗</a></div>`;}
  function tags(r){return `<div class="research-tags">${(r.governance_themes||[]).slice(0,3).map(v=>`<span>${esc(label(v))}</span>`).join('')}${(r.country_codes||[]).slice(0,3).map(c=>`<span>${esc(typeof c==='string'?c:(en()?c.name_en:c.name_zh))}</span>`).join('')}</div>`;}
  function card(r){
    const text=passage(r);
    return `<article class="research-card">${source(r)}<h3>${esc(title(r))}</h3>${r.version_label?`<p>${esc(r.version_label)}</p>`:''}<blockquote>${esc(text.slice(0,600))}${text.length>600?'…':''}</blockquote>${tags(r)}<button type="button" data-text="${esc(r.text_id)}">${r.document_family?t('阅读政策原文','Read policy text'):t('阅读来源文字','Read source passage')}</button></article>`;
  }
  function detail(id){if(!data)return;const r=data.records.find(v=>v.text_id===id)||data.events.flatMap(e=>e.records).find(v=>v.text_id===id);if(!r)return;
    dialog.innerHTML=`<button class="research-close" type="button" aria-label="${t('关闭','Close')}">×</button>${source(r)}<h2>${esc(title(r))}</h2>${tags(r)}<h3>${t('保存的原文摘录','Stored original passage')}</h3><div class="research-original"></div><details><summary>${t('文本与标注信息','Text and annotation information')}</summary><dl><dt>SHA-256</dt><dd class="research-hash">${esc(r.text_sha256)}</dd><dt>${t('采集时间','Collected')}</dt><dd>${esc(r.collected_at)}</dd><dt>${t('内容类型','Text type')}</dt><dd>${esc(r.text_kind)}</dd><dt>${t('标注','Annotations')}</dt><dd>${t('词典规则抽取，未逐条人工核验','Dictionary-based extraction; not individually human-verified')}</dd></dl>${[...(r.policy_tools||[]),...(r.policy_stages||[])].map(v=>`<p><strong>${esc(label(v))}</strong> · ${esc(v.evidence)}</p>`).join('')}</details>`;
    const original=dialog.querySelector('.research-original');
    original.textContent=passage(r);
    original.previousElementSibling.textContent=t('来源文字','Source passage');
    if(passage(r)!==r.source_text){const disclosure=document.createElement('details');const heading=document.createElement('summary');heading.textContent=t('查看原文','View original');const body=document.createElement('div');body.className='research-original';body.textContent=r.source_text;disclosure.append(heading,body);original.after(disclosure);}
    dialog.querySelector('.research-close').onclick=()=>dialog.close();dialog.showModal();}
  dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
  function bindDetails(){host.querySelectorAll('[data-text]').forEach(b=>b.onclick=()=>detail(b.dataset.text));}

  /* ---------- 事件追踪: the report timeline ---------- */
  const ev={topic:'',country:'',group:'',year:'',items:[],cursor:null,total:null,years:null,loading:false,failed:false,run:0,key:null};
  const evKey=()=>[ev.topic,ev.country,ev.group,ev.year].join('|');
  function drawEvents(view,store){
    const note=el('p','research-guide',t('按议题、国家与日期列出的报道时间线。同一议题下的报道各自成条，不会自动合并为同一事件；标题链接通往发布方原文。','A timeline of reports by topic, country and date. Reports on one topic stay separate entries and are not merged into an event; each title links to the publisher.'));
    if(!store.live){
      const off=el('div','rt-off');off.append(el('b',null,t('检索服务暂时无法连接','The search service cannot be reached')),el('p',null,t('报道时间线来自私有检索服务，目前无法读取。国家立场与其余栏目不受影响。','The report timeline is read from a private search service that is not answering. Positions and the other tabs still work.')));
      const again=el('button','research-more',t('重新连接','Retry'));again.type='button';again.onclick=()=>{topicsRequest=null;show();};off.append(again);
      view.replaceChildren(note,off);return;
    }
    const bar=el('div','rt-bar');
    const topic=picker(store,{id:'eventTopic',value:ev.topic,all:true,onChange:v=>{ev.topic=v;load(true);}});
    const select=(id,labelText,allText,rows,value,set)=>{
      const wrap=el('label','rt-field');wrap.append(el('span',null,labelText));
      const s=el('select');s.id=id;s.append(new Option(allText,''));
      rows.forEach(r=>s.append(new Option(name(r)+' · '+num(r.reports),r.code,false,r.code===value)));
      s.onchange=()=>{set(s.value);load(true);};wrap.append(s);return wrap;
    };
    const sortName=rows=>[...rows].sort((a,b)=>b.reports-a.reports);
    bar.append(topic.node,
      select('eventCountry',t('国家','Country'),t('全部国家','All countries'),sortName(store.countries),ev.country,v=>ev.country=v),
      select('eventGroup',t('谈判集团与区域组织','Groups and blocs'),t('不限','Any'),store.groups,ev.group,v=>ev.group=v));
    const years=el('div','rt-years');years.setAttribute('role','group');years.setAttribute('aria-label',t('按年份筛选','Filter by year'));
    const first=Number((store.range?.[0]||'1996').slice(0,4)),last=Number((store.range?.[1]||String(new Date().getFullYear())).slice(0,4));
    const bars=new Map();
    for(let y=first;y<=last;y++){const b=el('button','rt-year');b.type='button';b.dataset.year=y;b.style.setProperty('--d',y-first);if(y%10===0)b.dataset.tick='10';b.append(el('i'),el('span'));b.onclick=()=>{ev.year=ev.year===String(y)?'':String(y);load(true);};bars.set(String(y),b);years.append(b);}
    const summary=el('p','rt-summary'),total=el('b','rt-total'),unit=el('span'),clear=el('button','rt-clear');clear.type='button';clear.onclick=()=>{ev.year='';load(true);};
    summary.append(total,unit,clear);
    const list=el('ol','rt-timeline'),more=el('button','research-more');more.type='button';more.onclick=()=>load(false);
    const state=el('div','rt-state');
    view.replaceChildren(note,bar,years,summary,list,state,more);
    const setTopic=code=>{ev.topic=code;topic.set(code);load(true);scrollTo({top:host.getBoundingClientRect().top+scrollY-80,behavior:still()?'auto':'smooth'});};
    const setCountry=code=>{ev.country=code;view.querySelector('#eventCountry').value=code;load(true);scrollTo({top:host.getBoundingClientRect().top+scrollY-80,behavior:still()?'auto':'smooth'});};
    function paintYears(){
      const counts=ev.years||{},top=Math.max(1,...Object.values(counts));
      bars.forEach((b,y)=>{const n=counts[y]||0;b.style.setProperty('--h',n?Math.max(.04,Math.sqrt(n/top)).toFixed(3):'0');b.dataset.n=num(n);b.setAttribute('aria-label',y+t(' 年 ',': ')+num(n)+t(' 篇报道',' reports'));b.setAttribute('aria-pressed',String(ev.year===y));b.disabled=!n&&ev.year!==y;b.lastChild.textContent=Number(y)%5===0||ev.year===y?y:'';});
    }
    function paintSummary(){
      roll(total,ev.total??0);
      unit.textContent=' '+t('篇报道','reports')+(ev.year?' · '+ev.year:store.range?' · '+store.range[0].slice(0,4)+'—'+store.range[1].slice(0,4):'');
      clear.textContent=t('清除年份','Clear year');clear.hidden=!ev.year;
      more.hidden=!ev.cursor||ev.loading;more.textContent=t('显示更多','Show more')+' · '+num(ev.items.length)+' / '+num(ev.total);
      refreshExport();
    }
    function append(items,fresh){
      if(fresh)list.replaceChildren();
      const made=[];
      items.forEach(item=>{
        let day=list.lastElementChild;
        if(!day||day.dataset.date!==item.date){day=el('li','rt-day');day.dataset.date=item.date;const when=el('time','rt-date');when.dateTime=item.date;when.append(el('b',null,item.date.slice(5)),el('span',null,item.date.slice(0,4)));const box=el('div','rt-day-items');day.append(when,box);list.append(day);made.push(day);}
        const row=reportRow(item,store,{topic:ev.topic,onTopic:setTopic,onCountry:setCountry});day.lastElementChild.append(row);if(!made.includes(day))made.push(row);
      });
      stagger(made);
    }
    function paintState(){
      state.replaceChildren();state.hidden=false;
      if(ev.loading){state.className='rt-state rt-loading';for(let i=0;i<(ev.items.length?2:5);i++)state.append(el('i'));return;}
      state.className='rt-state';
      if(ev.failed){state.append(el('b',null,t('暂时无法读取报道','Reports could not be loaded')));const again=el('button','research-more',t('重试','Retry'));again.type='button';again.onclick=()=>load(!ev.items.length);state.append(again);return;}
      if(!ev.items.length){state.append(el('b',null,t('当前筛选下没有检索到报道','No report matches this selection')),el('p',null,t('这是检索结果为空，不代表没有相关事件。可放宽议题、国家或年份。','An empty search result, not evidence that nothing happened. Try a wider topic, country or year.')));return;}
      state.hidden=true;
    }
    async function load(fresh){
      const run=++ev.run;
      if(fresh){ev.items=[];ev.cursor=null;ev.key=evKey();list.replaceChildren();}
      ev.loading=true;ev.failed=false;paintYears();paintState();more.hidden=true;
      try{
        const page=await api('events',{topic:ev.topic,country:ev.country,group:ev.group,year:ev.year,limit:store.pageSize,cursor:fresh?'':ev.cursor});
        if(run!==ev.run)return;
        ev.items.push(...page.items);ev.cursor=page.next_cursor;
        if(fresh){ev.total=page.total??0;ev.years=page.years||{};}
        ev.loading=false;append(page.items,fresh);
      }catch{if(run!==ev.run)return;ev.loading=false;ev.failed=true;}
      paintYears();paintSummary();paintState();
    }
    if(ev.key===evKey()&&ev.items.length&&!ev.failed){ev.loading=false;append(ev.items,true);paintYears();paintSummary();paintState();}
    else load(true);
    if(!still())requestAnimationFrame(()=>years.classList.add('rt-grown'));else years.classList.add('rt-grown');
  }
  function exportEvents(store){
    const cols=['article_id','date','title','publisher','url','topic_codes','country_codes'];
    download([cols,...ev.items.map(i=>[i.id,i.date,i.title,i.publisher,i.url,(i.topics||[]).join(';'),(i.countries||[]).join(';')])],'green-report-timeline');
  }

  /* ---------- 我的关注 ---------- */
  function drawWatch(view){
    if(!data){
      if(indexFailed){view.innerHTML=`<div class="rt-off"><b>${t('语料暂时无法读取，请稍后重试。','Source texts could not be loaded. Please retry later.')}</b><a href="./data/research_texts.jsonl">${t('直接下载语料','Download source texts')}</a></div>`;return;}
      view.innerHTML=`<p class="research-loading">${t('正在读取原文语料…','Loading source texts…')}</p>`;loadIndex();return;
    }
    const ct=countryList(),selected=selectionRecords();
    view.innerHTML=`<div class="research-filters"><input id="researchQuery" value="${esc(query)}" placeholder="${t('检索原文、标题或机构','Search source text, title or institution')}" aria-label="${t('检索','Search')}"><select id="researchCountry" aria-label="${t('国家','Country')}"><option value="">${t('全部国家','All countries')}</option>${ct.map(c=>`<option value="${c.alpha2}" ${country===c.alpha2?'selected':''}>${esc(en()?c.name_en:c.name_zh)} · ${c.alpha3}</option>`).join('')}</select><select id="researchTheme" aria-label="${t('议题','Theme')}"><option value="">${t('全部议题','All themes')}</option>${data.themes.map(v=>`<option value="${v.id}" ${theme===v.id?'selected':''}>${esc(label(v))}</option>`).join('')}</select><select id="researchTrack" aria-label="${t('轨道','Track')}"><option value="">${t('全部轨道','All tracks')}</option><option value="negotiations" ${track==='negotiations'?'selected':''}>${t('谈判相关','Negotiation-related')}</option><option value="action" ${track==='action'?'selected':''}>${t('气候行动','Climate action')}</option></select></div><div class="research-watch"><fieldset><legend>${t('关注国家','Countries')}</legend><select id="watchCountries" multiple aria-label="${t('关注国家，多选','Watch countries, multiple selection')}">${ct.map(c=>`<option value="${c.alpha2}" ${watch.countries.includes(c.alpha2)?'selected':''}>${esc(en()?c.name_en:c.name_zh)}</option>`).join('')}</select></fieldset><fieldset><legend>${t('关注议题','Themes')}</legend><select id="watchThemes" multiple aria-label="${t('关注议题，多选','Watch themes, multiple selection')}">${data.themes.map(v=>`<option value="${v.id}" ${watch.themes.includes(v.id)?'selected':''}>${esc(label(v))}</option>`).join('')}</select></fieldset><fieldset><legend>${t('谈判集团','Negotiating groups')}</legend>${['EU','AOSIS','G77','LDC'].map(c=>`<label><input type="checkbox" name="watchGroup" value="${c}" ${watch.groups.includes(c)?'checked':''}>${c}</label>`).join('')}</fieldset><div><button id="saveResearchWatch" type="button">${t('保存关注','Save watchlist')}</button><button id="clearResearchWatch" type="button">${t('清空','Clear')}</button><p>${t('偏好仅保存在此浏览器。电脑多选可按住Ctrl或Command；手机按系统列表选择。','Preferences stay in this browser. On desktop hold Ctrl or Command for multiple selections; mobile uses the native selector.')}</p></div></div><div class="research-grid">${selected.slice(0,visible).map(card).join('')}</div>${selected.length>visible?`<button class="research-more" type="button">${t('显示更多','Show more')}</button>`:''}`;
    view.querySelector('#saveResearchWatch').onclick=()=>{watch={countries:[...view.querySelector('#watchCountries').selectedOptions].map(o=>o.value),themes:[...view.querySelector('#watchThemes').selectedOptions].map(o=>o.value),groups:[...view.querySelectorAll('[name=watchGroup]:checked')].map(o=>o.value)};try{localStorage.setItem('green-research-watch-v1',JSON.stringify(watch));}catch{}show();};
    view.querySelector('#clearResearchWatch').onclick=()=>{watch={countries:[],themes:[],groups:[]};try{localStorage.removeItem('green-research-watch-v1');}catch{}show();};
    const search=view.querySelector('#researchQuery');search.onchange=()=>{query=search.value.trim();visible=20;show();};search.addEventListener('keydown',e=>{if(e.key==='Enter'){query=search.value.trim();visible=20;show();}});
    [['researchCountry',v=>country=v],['researchTheme',v=>theme=v],['researchTrack',v=>track=v]].forEach(([id,set])=>view.querySelector('#'+id).onchange=e=>{set(e.target.value);visible=20;show();});
    view.querySelector('.research-more')?.addEventListener('click',()=>{visible+=20;show();});bindDetails();
    stagger(view.querySelectorAll('.research-card'));
  }

  /* ---------- 数据与方法 ---------- */
  let catalogRequest=null;
  const catalog=()=>catalogRequest=catalogRequest||fetch('./data/research_catalog.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw new Error(String(r.status));return r.json();}).catch(()=>{catalogRequest=null;return null;});
  function drawMethods(view,store){
    const figure=(value,text)=>`<article><b>${value}</b><span>${text}</span></article>`;
    view.innerHTML=`<div class="research-counts">${figure(num(store.total),t('可按议题、国家与日期检索的报道','Reports searchable by topic, country and date'))}${figure(String(store.subs.length),t('议题小类，归入 '+store.parents.length+' 个大类','Topics in '+store.parents.length+' categories'))}${figure(num(store.positions),t('已核验立场（逐条附原文证据）','Checked positions, each with its source evidence'))}</div><div class="research-counts" id="researchCorpusCounts"></div><div class="research-downloads"><a href="./data/research_texts.jsonl" download>JSONL · ${t('真实语料','Source texts')}</a><a href="./data/research_records.csv" download>CSV</a><a href="./data/research_catalog.json" download>${t('数据字典与版本','Dictionary & version')}</a><span id="researchRelease"></span></div><h3>${t('数据处理','Processing')}</h3><ol class="research-method-list"><li>${t('议题采用 14 大类、83 小类的研究用编码（非《公约》官方分类）。一篇报道可以属于多个议题；议题与国家为词典规则标注，国家指文中提及，不是发布地，也不是国家立场。','Topics use a research dictionary of 14 categories and 83 topics (not an official UNFCCC classification). A report may carry several topics; topics and countries are dictionary-based labels, and a country label means a mention, not a publisher location or a national position.')}</li><li>${t('事件追踪是报道时间线：按议题、国家与日期列出报道，不把同一议题的报道自动合并为同一事件。','Event tracking is a timeline of reports by topic, country and date; reports on one topic are not merged into a single event.')}</li><li>${t('国家立场只展示经核对的表态：主体、日期、主张、公开理由与原文证据。没有核验材料时显示“证据不足”；相关报道候选只是检索结果，不代表任何国家的立场。集团表态不自动归于其成员，欧盟作为单独主体。','Country positions show checked statements only: actor, date, claim, public reasons and source evidence. Without checked material the view says “insufficient evidence”; related reports are search results, not positions. A group statement is not attributed to its members, and the EU is an actor of its own.')}</li><li>${t('“可检索报道数”与“已核验立场数”是两个口径，不能相加或互相替代。','“Searchable reports” and “checked positions” are two different measures and are never added together.')}</li><li>${t('原文保存在私有服务端；页面每次只读取 30 条报道的元数据或经核验的短证据，不提供全文下载。','Source texts stay on a private server; the page reads thirty reports’ metadata, or short checked quotations, at a time, and offers no full-text download.')}</li><li>${t('公开语料保留RSS、官方网页及专业媒体提供的原文摘录，保留发布时间、采集时间、真实发布页和文本指纹；不绕过付费墙、登录或robots限制。','The public corpus keeps source-provided or original-page excerpts with publication and collection times, publisher URLs and text hashes; paywalls, logins and robots restrictions are not bypassed.')}</li></ol><h3>${t('字段字典','Field dictionary')}</h3><div class="research-table-wrap"><table><thead><tr><th>${t('字段','Field')}</th><th>${t('说明','Meaning')}</th></tr></thead><tbody id="researchFields"></tbody></table></div><h3>${t('引用','Citation')}</h3><p class="research-citation" id="researchCitation"></p><p>${t('新闻数量反映来源覆盖和报道活动，不能直接解释为治理成效。议题与国家标签未经逐条人工核验。','News volume reflects source coverage and reporting activity, not governance performance. Topic and country labels have not been individually human-verified.')}</p>`;
    stagger(view.querySelectorAll('.research-counts article'));
    catalog().then(c=>{
      if(!c||!view.isConnected||tab!=='methods')return;
      const s=c.statistics||{};
      view.querySelector('#researchCorpusCounts').innerHTML=figure(num(s.usable_texts),t('含实质原文的公开语料','Public records with substantive source text'))+figure(num(s.text_kinds?.article_excerpt||0),t('已回源的正文摘录','Original-page excerpts'))+figure(num(s.source_records),t('全部新闻元数据','All news metadata records'));
      if(c.release){const a=el('a',null,t('冻结研究版本','Frozen research release')+' '+c.release.id);a.href='./data/research_releases/'+encodeURIComponent(c.release.id)+'/corpus.jsonl.gz';a.download='';view.querySelector('#researchRelease').replaceWith(a);}
      const body=view.querySelector('#researchFields');(c.fields||[]).forEach(f=>{const row=el('tr'),id=el('td');id.append(el('code',null,f.id));row.append(id,el('td',null,en()?f.label_en:f.label_zh));body.append(row);});
      const cite=view.querySelector('#researchCitation');cite.textContent='GREEN. Climate Governance Source-text Corpus. Version '+c.version+'. '+date(c.generated_at)+'. '+location.origin+location.pathname;cite.append(el('br'),'SHA-256: ',el('span','research-hash',c.corpus_sha256));
    });
  }

  /* ---------- the page ---------- */
  const TABS=[['positions','国家立场','Country positions'],['events','事件追踪','Event tracking'],['watch','我的关注','My watchlist'],['methods','数据与方法','Data & methods']];
  function shell(){
    document.querySelectorAll('[data-research-nav]').forEach(a=>a.textContent=t('研究工具','Research tools'));
    host.innerHTML=`<div class="section-heading"><div><p class="overline">RESEARCH & EVIDENCE</p><h2>${t('气候治理研究工具','Climate governance research tools')}</h2></div><button type="button" class="research-export" hidden></button></div><div class="research-tabs" role="tablist">${TABS.map(([id,zh,eng])=>`<button type="button" role="tab" aria-selected="${tab===id}" data-tab="${id}">${t(zh,eng)}</button>`).join('')}<i class="rt-ink" aria-hidden="true"></i></div><div id="researchView"></div>`;
    host.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{if(tab===b.dataset.tab)return;tab=b.dataset.tab;visible=20;show();});
  }
  function ink(){
    const bar=host.querySelector('.research-tabs'),on=bar?.querySelector('[aria-selected="true"]'),line=bar?.querySelector('.rt-ink');
    if(on&&line){line.style.setProperty('--x',on.offsetLeft+'px');line.style.setProperty('--w',on.offsetWidth+'px');}
  }
  let drawing=0,refreshExport=()=>{};
  function show(){
    const view=host.querySelector('#researchView');if(!view){shell();return show();}
    host.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===tab)));ink();
    host.dataset.researchTab=tab;
    const exportButton=host.querySelector('.research-export');exportButton.hidden=true;
    const run=++drawing;
    if(tab==='watch'){
      drawWatch(view);
      if(data){const rows=selectionRecords();exportButton.hidden=false;exportButton.disabled=!rows.length;exportButton.textContent=t('导出筛选','Export results')+' · '+rows.length;
        exportButton.onclick=()=>{const keys=['text_id','title_original','title_zh','title_en','source_name','published_at','publisher_url','country_iso2','theme_ids','language','source_text','source_text_zh','source_text_en','text_sha256','rights_status','review_status','translation_status'];download([keys,...rows.map(r=>keys.map(k=>k==='country_iso2'?countries(r).join(';'):k==='theme_ids'?(r.governance_themes||[]).map(v=>v.id).join(';'):r[k]||''))],'green-source-texts');};}
      return;
    }
    if(!view.querySelector('.rt-wait')){view.innerHTML=`<p class="research-loading rt-wait">${t('正在读取议题与索引…','Loading topics and index…')}</p>`;}
    topics().then(store=>{
      if(run!==drawing)return;
      if(tab==='positions'){
        const pilot=el('div');pilot.id='stancePilot';view.replaceChildren(pilot);
        if(window.GREEN_STANCE)window.GREEN_STANCE.mount(pilot,{...kit,store});
        else pilot.append(el('p',null,t('立场证据暂时无法读取。','Position evidence is temporarily unavailable.')));
      }else if(tab==='events'){
        drawEvents(view,store);
        exportButton.hidden=false;
        refreshExport=()=>{if(tab!=='events')return;exportButton.disabled=!ev.items.length;exportButton.textContent=t('导出当前列表','Export this list')+' · '+ev.items.length;};
        exportButton.onclick=()=>exportEvents(store);refreshExport();
      }else drawMethods(view,store);
    }).catch(()=>{
      if(run!==drawing)return;
      view.innerHTML=`<div class="rt-off"><b>${t('研究工具暂时无法读取，请稍后重试。','The research tools could not be loaded. Please retry later.')}</b><button type="button" class="research-more">${t('重试','Retry')}</button></div>`;
      view.querySelector('button').onclick=show;
    });
  }
  // old entries: the 文本对照 tab is gone — links to it open the tools' first tab, and #compare lands on #research
  const tabOf=id=>TABS.some(v=>v[0]===id)?id:'positions';
  document.addEventListener('click',e=>{const button=e.target.closest('[data-research-text]');if(button){e.preventDefault();detail(button.dataset.researchText);}});
  document.querySelectorAll('[data-research-tab]').forEach(a=>a.addEventListener('click',()=>{tab=tabOf(a.dataset.researchTab);show();}));
  const redirect=()=>{if(location.hash==='#compare'){history.replaceState(null,'',location.pathname+location.search+'#research');host.scrollIntoView();}};
  addEventListener('hashchange',redirect);redirect();
  new MutationObserver(()=>{shell();show();}).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});
  addEventListener('resize',ink);document.fonts?.ready.then(ink);
  window.GREEN_RESEARCH_KIT=kit;
  shell();show();
  if(!LAZY)loadIndex();
})();
