(function(){
 'use strict';
 let language=new URLSearchParams(location.search).get('lang')==='en'?'en':'zh';
 const button=document.getElementById('innovationLanguage');
 async function show(){
  document.documentElement.lang=language==='en'?'en':'zh-CN';
  document.title=language==='en'?'Global science–industry collaboration cases':'科产融合全球案例库';
  document.querySelector('.standalone-brand').textContent=document.title;
  document.getElementById('innovationPermalink').textContent=language==='en'?'Permalink':'独立链接';
  document.getElementById('innovationDataset').textContent=language==='en'?'Research data 2026.10.14':'研究数据 2026.10.14';
  document.getElementById('innovationHistory').textContent=language==='en'?'Earlier report':'历史报告';
  button.textContent=language==='en'?'中文':'EN';button.setAttribute('aria-label',language==='en'?'切换到中文':'Switch to English');
  await window.GruenInnovationCases.mount(document.getElementById('innovationCases'),{mode:'energy',language});
  const book=window.GruenInnovationCases.getSnapshot();
  document.getElementById('innovationVersion').textContent=(book?.research?.version||'')+' · '+(book?.updated_at||'').slice(0,10);
 }
 button.addEventListener('click',()=>{language=language==='zh'?'en':'zh';const u=new URL(location.href);u.searchParams.set('lang',language);history.replaceState(null,'',u);show();});
 show();
})();
