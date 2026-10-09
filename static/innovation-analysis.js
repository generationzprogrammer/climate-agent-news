/* Evidence-informed typologies. Structural comparisons, never country rankings. */
(function(root){
 "use strict";
 const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const tx=(v,l)=>v?.[l]||v?.zh||String(v??"");
 const colors=['#264c6d','#547fa1','#93b2c7','#c8d9e4','#836633','#b79961','#d4c29f','#737c83'];
 const cohortLabels={coverage_review:{zh:'区域补充案例',en:'Geographic coverage review'},regional_review:{zh:'官方机构案例',en:'Reviewed institutions'},legacy_review:{zh:'平台与制度案例',en:'Platforms and institutions'},ARPAE:{zh:'美国ARPA-E项目',en:'US ARPA-E projects'},CORDIS:{zh:'欧盟CORDIS项目',en:'EU CORDIS projects'}};
 const scopeCopy={zh:{scope:'模式范围',all:'全部模式',china:'中国区域',international:'国际案例',regionHelp:'按平台实际所在地检索。案例数量不代表地区创新绩效。'},en:{scope:'Model scope',all:'All models',china:'Chinese regions',international:'International cases',regionHelp:'Explore the documented operating location. Case counts are not regional innovation performance.'}};
 function profileScope(book,m){return m.case_ids.every(id=>{const c=book.cases.find(c=>c.id===id);return c?.research_annotation?.province;})?'china':'international';}
 const L={zh:{models:"国家与区域模式",macro:"宏观对比",select:"选择两个或三个模式",help:"先比较所需条件，再比较政府工具。可从“广东—浙江”入手，检查本地产业、工程验证和人才条件是否匹配；模式可以组合，不必整套复制。",compare:"比较所选模式",china:"广东—浙江",field:"比较维度",mechanism:"组织机制",conditions:"适用前提",factors:"生产要素与解释",government:"政府可用工具",boundary:"适用边界",cases:"案例证据",sample:"查看该组案例",platform:"平台与制度安排",project:"独立资助项目",continent:"按大洲",economy:"按发展分组",group:"组别",n:"样本数",shares:"组织机制构成",cohort:"来源渠道",noData:"该组暂无同口径案例",legend:"构成比例",read:"点击色块可查看该组、该模式的案例。",region:"中国区域案例",regionHelp:"省份按案例实际所在地标注，跨国案例不强行分配到省份。广东和浙江已有多种机制并存；其他省份的少量案例仅用于补充对照。",all:"全部",evidence:"查看原始证据",total:"合计"},
 en:{models:"National and regional models",macro:"Macro comparison",select:"Select two or three models",help:"Compare prerequisites before policy tools. Start with Guangdong–Zhejiang and check local industrial demand, engineering validation and talent. Models can be combined rather than copied wholesale.",compare:"Compare selected models",china:"Guangdong–Zhejiang",field:"Dimension",mechanism:"Organisation",conditions:"Prerequisites",factors:"Factors and interpretation",government:"Public-policy tools",boundary:"Applicability limits",cases:"Case evidence",sample:"Explore this group",platform:"Platforms and institutions",project:"Independent funded projects",continent:"By continent",economy:"By development group",group:"Group",n:"Sample size",shares:"Mechanism composition",cohort:"Source channels",noData:"No comparable cases in this group",legend:"Composition",read:"Select a segment to explore cases in that group and model.",region:"Chinese regional cases",regionHelp:"Provinces reflect documented case locations. International cases are not forced into a province. Multiple mechanisms coexist in Guangdong and Zhejiang; small samples elsewhere are supplementary contrasts.",all:"All",evidence:"Primary evidence",total:"Total"}};
 function render(book,lang){
  if(!book.analysis)return '';
  const a=book.analysis,t=k=>L[lang][k],local=v=>tx(v,lang);
  return '<section class="ic-analysis" data-analysis-panel="models" hidden><h3>'+t('models')+'</h3><p>'+esc(local(a.definition))+'</p><p class="ic-analysis-help">'+t('help')+'</p>'+
   '<div class="ic-analysis-filters"><label>'+scopeCopy[lang].scope+'<select data-model-scope>'+['all','china','international'].map(k=>'<option value="'+k+'">'+scopeCopy[lang][k]+'</option>').join('')+'</select></label></div>'+
   '<div class="ic-model-select">'+a.profiles.map(m=>'<label data-profile-scope="'+profileScope(book,m)+'"><input type="checkbox" data-model-select="'+m.id+'" '+(['guangdong','zhejiang'].includes(m.id)?'checked':'')+'>'+esc(local(m.name))+'</label>').join('')+'</div>'+
   '<div class="ic-model-actions"><button type="button" data-model-compare>'+t('compare')+'</button><button type="button" data-china-compare>'+t('china')+'</button><button type="button" data-model-clear>'+(lang==='zh'?'清空选择':'Clear selection')+'</button><span class="ic-model-status" aria-live="polite">'+t('select')+'</span></div><div class="ic-model-comparison"></div>'+
   '<h3>'+t('region')+'</h3><p>'+scopeCopy[lang].regionHelp+'</p><div class="ic-region-cards">'+a.provinces.map(p=>'<button type="button" data-explore-province="'+p.id+'"><strong>'+esc(local(p.name))+'</strong><span>'+p.count+' '+(lang==='zh'?'例':'cases')+'</span>'+(lang==='zh'?'<span>'+esc(p.cities.join(' · '))+'</span>':'')+'</button>').join('')+'</div></section>'+
   '<section class="ic-analysis" data-analysis-panel="macro" hidden><h3>'+t('macro')+'</h3><div class="ic-macro-controls"><label>'+t('group')+'<select data-macro-dimension><option value="continent">'+t('continent')+'</option><option value="economy">'+t('economy')+'</option></select></label><label>'+t('sample')+'<select data-macro-grain><option value="platform">'+t('platform')+'</option><option value="project">'+t('project')+'</option></select></label></div><p>'+esc(local(a.macro_note))+'</p><div class="ic-macro-chart"></div><p>'+t('read')+'</p><div class="ic-macro-table ic-matrix-scroll"></div><p>'+esc(a.classification_source.title)+' · <a href="'+esc(a.classification_source.url)+'" target="_blank" rel="noopener noreferrer">'+t('evidence')+' ↗</a></p></section>';
 }
 function comparison(book,ids,lang){
  const a=book.analysis,t=k=>L[lang][k],local=v=>tx(v,lang),models=ids.map(id=>a.profiles.find(m=>m.id===id)).filter(Boolean);
  if(models.length<2||models.length>3)return '<p role="status">'+t('select')+'</p>';
  return '<p class="ic-table-instruction">'+(lang==='zh'?'勾选2—3个模式即可对照；手机上可左右滑动表格。':'Select 2–3 models to compare. Swipe the table horizontally on mobile.')+'</p><div class="ic-matrix-scroll" tabindex="0"><table class="ic-matrix ic-model-table"><caption>'+models.map(m=>local(m.name)).join(' × ')+'</caption><thead><tr><th>'+t('field')+'</th>'+models.map(m=>'<th scope="col">'+esc(local(m.name))+'</th>').join('')+'</tr></thead><tbody>'+
   ['mechanism','conditions','factors','government','boundary'].map(k=>'<tr><th scope="row">'+t(k)+'</th>'+models.map(m=>'<td>'+esc(local(m[k]))+'</td>').join('')+'</tr>').join('')+
   '<tr><th scope="row">'+t('cases')+'</th>'+models.map(m=>'<td>'+m.case_ids.map(id=>{const c=book.cases.find(c=>c.id===id);return '<button type="button" class="ic-evidence-case" data-detail="'+id+'">'+esc(local(c.title))+' →</button>';}).join('')+'</td>').join('')+'</tr></tbody></table></div>';
 }
 function macroRows(book,grain,dimension){return (book.analysis?.macro||[]).filter(r=>r.grain===grain&&r.dimension===dimension);}
 function macroChart(book,grain,dimension,lang){
  const a=book.analysis,rows=macroRows(book,grain,dimension),groups=[...new Set(rows.map(r=>r.group))],local=v=>tx(v,lang);
  const h=75+groups.length*52;
  const bars=groups.map((group,i)=>{let x=230;const rs=rows.filter(r=>r.group===group),n=rs[0].denominator,y=45+i*52;
   let s='<text x="0" y="'+(y+19)+'" fill="#24343f" font-size="16">'+esc(local(a.group_labels[group]))+'</text><text x="207" y="'+(y+19)+'" text-anchor="end" font-size="14" fill="#52616b">n='+n+'</text>';
   if(!n)return s+'<text x="230" y="'+(y+19)+'" fill="#737c83" font-size="14">'+L[lang].noData+'</text>';
   rs.forEach(r=>{const j=a.archetypes.findIndex(m=>m.id===r.model),w=640*r.share;if(!r.count)return;
    const tip=local(a.group_labels[group])+' · '+local(a.archetypes[j].label)+' · '+r.count+'/'+n+' ('+(100*r.share).toFixed(1)+'%)';
    s+='<rect x="'+x.toFixed(3)+'" y="'+y+'" width="'+w.toFixed(3)+'" height="29" fill="'+colors[j]+'" tabindex="0" role="button" aria-label="'+esc(tip)+'" data-macro-group="'+group+'" data-macro-model="'+r.model+'"><title>'+esc(tip)+'</title></rect>';
    if(w>65)s+='<text pointer-events="none" x="'+(x+w/2).toFixed(3)+'" y="'+(y+20)+'" text-anchor="middle" fill="'+([2,3,5,6].includes(j)?'#142b3b':'white')+'" font-size="14">'+(100*r.share).toFixed(0)+'%</text>';x+=w;});return s;
  }).join('');
  const ticks=[0,25,50,75,100].map(n=>'<text x="'+(230+640*n/100)+'" y="'+(h-2)+'" text-anchor="middle" font-size="14" fill="#52616b">'+n+'%</text>').join('');
  return '<div class="ic-chart-scroll"><svg class="ic-macro-svg" viewBox="0 0 930 '+h+'" role="img" aria-label="'+L[lang].shares+'"><text x="230" y="22" font-size="15" fill="#24343f">'+L[lang].legend+'</text>'+bars+ticks+'</svg></div><div class="ic-composition-legend">'+a.archetypes.map((m,i)=>'<span><i style="background:'+colors[i]+'"></i>'+esc(local(m.label))+'</span>').join('')+'</div><p class="ic-chart-readout" aria-live="polite"></p>';
 }
 function attach(host,book,lang,explore,detail){
  if(!book.analysis)return;
  const a=book.analysis,local=v=>tx(v,lang),t=k=>L[lang][k],checks=[...host.querySelectorAll('[data-model-select]')];
  const scope=host.querySelector('[data-model-scope]');
  scope.addEventListener('change',()=>host.querySelectorAll('[data-profile-scope]').forEach(label=>{label.hidden=scope.value!=='all'&&label.dataset.profileScope!==scope.value;}));
  const drawCompare=()=>{const ids=checks.filter(c=>c.checked).map(c=>c.dataset.modelSelect);host.querySelector('.ic-model-comparison').innerHTML=comparison(book,ids,lang);
   host.querySelector('.ic-model-status').textContent=ids.length+'/3 · '+t('select');checks.forEach(c=>c.disabled=!c.checked&&ids.length>=3);
   host.querySelectorAll('.ic-model-comparison [data-detail]').forEach(b=>b.addEventListener('click',()=>detail(b.dataset.detail)));};
  checks.forEach(c=>c.addEventListener('change',drawCompare));host.querySelector('[data-model-compare]').addEventListener('click',drawCompare);
  host.querySelector('[data-model-clear]').addEventListener('click',()=>{checks.forEach(c=>c.checked=false);drawCompare();});
  host.querySelector('[data-china-compare]').addEventListener('click',()=>{scope.value='china';scope.dispatchEvent(new Event('change'));checks.forEach(c=>c.checked=['guangdong','zhejiang'].includes(c.dataset.modelSelect));drawCompare();});drawCompare();
  host.querySelectorAll('[data-explore-province]').forEach(b=>b.addEventListener('click',()=>explore({province:b.dataset.exploreProvince,country:'CN'})));
  const drawMacro=()=>{const grain=host.querySelector('[data-macro-grain]').value,dimension=host.querySelector('[data-macro-dimension]').value,rows=macroRows(book,grain,dimension),groups=[...new Set(rows.map(r=>r.group))];
   host.querySelector('.ic-macro-chart').innerHTML=macroChart(book,grain,dimension,lang);
   host.querySelector('.ic-macro-table').innerHTML='<table class="ic-matrix ic-composition-table"><caption>'+t(grain)+' · '+t(dimension)+'</caption><thead><tr><th>'+t('group')+'</th><th>'+t('n')+'</th>'+a.archetypes.map(m=>'<th>'+esc(local(m.label))+'</th>').join('')+'<th>'+t('cohort')+'</th></tr></thead><tbody>'+groups.map(g=>{const rs=rows.filter(r=>r.group===g),first=rs[0];return '<tr><th>'+esc(local(a.group_labels[g]))+'</th><td>'+first.denominator+'</td>'+rs.map(r=>'<td>'+(r.share===null?'—':r.count+' · '+(100*r.share).toFixed(1)+'%')+'</td>').join('')+'<td>'+esc(Object.entries(first.source_cohorts).map(([k,n])=>local(cohortLabels[k]||{zh:k,en:k})+' '+n).join(' · '))+'</td></tr>';}).join('')+'</tbody></table>';
   host.querySelectorAll('[data-macro-group]').forEach(b=>{const filter={grain,archetype:b.dataset.macroModel,[dimension]:b.dataset.macroGroup};const tip=b.getAttribute('aria-label');
    b.addEventListener('mouseenter',()=>host.querySelector('.ic-chart-readout').textContent=tip);b.addEventListener('focus',()=>host.querySelector('.ic-chart-readout').textContent=tip);
    b.addEventListener('click',()=>explore(filter));b.addEventListener('keydown',e=>{if(['Enter',' '].includes(e.key)){e.preventDefault();explore(filter);}});});};
  host.querySelector('[data-macro-grain]').addEventListener('change',drawMacro);host.querySelector('[data-macro-dimension]').addEventListener('change',drawMacro);drawMacro();
 }
 root.GruenInnovationAnalysis={render,attach,comparison,macroRows,macroChart,profileScope};
 if(typeof module==='object'&&module.exports)module.exports=root.GruenInnovationAnalysis;
})(typeof window==='undefined'?globalThis:window);
