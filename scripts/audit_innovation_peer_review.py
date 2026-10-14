"""Executed, bounded notebook for the second frozen-release review."""
import contextlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/innovation_research_20261014_r2'

def main():
    cells=[]
    def md(text):cells.append({'cell_type':'markdown','id':'review-'+str(len(cells)),'metadata':{},'source':text})
    def code(text):cells.append({'cell_type':'code','id':'review-'+str(len(cells)),'metadata':{},'source':text,'outputs':[],'execution_count':None})
    md('# 科产融合案例库审阅复算\n## 结论与范围\n769条记录分为181个机构与588个资助项目；机构日期有证据46例。来源和观察层级明显影响模式构成。本文仅进行数据诊断，不估计总体准确率、政策因果或国家绩效。')
    md('## 方法\n冻结版本2026.10.14-r2；第一版保持不变。按记录层级和采集批次计算覆盖与构成，以逐一剔除批次检查敏感性。单来源统计只覆盖主要事实叙述所引用的case.evidence，不含日期专用来源。')
    code("""from pathlib import Path
import json, hashlib
from collections import Counter
root=next(p for p in (Path.cwd(),*Path.cwd().parents) if (p/'config/open_innovation_models.json').exists())
out=root/'analysis/innovation_research_20261014_r2'
book=json.loads((out/'data/cases_nested.json').read_text(encoding='utf-8'))
old=json.loads((root/'analysis/innovation_research_20261014/data/cases_nested.json').read_text(encoding='utf-8'))
cases=book['cases']; institutions=[c for c in cases if c['research_annotation']['grain']=='platform']
print({'cases':len(cases),'institutions':len(institutions),'projects':len(cases)-len(institutions)})
print([{'case_id':c['id'],'country':c['research_annotation'].get('country'),'origin':c['timeline']['origin_year']} for c in institutions[:5]])""")
    md('## 核查结果\n### 保留旧记录与主键')
    code("""current={c['id']:c for c in cases}
assert len(current)==len(cases)
ignored={'research_annotation','timeline','organization_tags','organization_participant_tags','organization_basis','developments'}
for case in old['cases']:
    assert case['id'] in current
    for field,value in case.items():
        if field not in ignored:assert current[case['id']][field]==value,(case['id'],field)
sources={s['id']:s for s in book['sources']}
assert len(sources)==len(book['sources'])==len({s['url'] for s in book['sources']})
assert all(ref['source_id'] in sources for c in cases for ref in c['evidence'])
print({'retained_case_facts':len(old['cases']),'new_cases':len(cases)-len(old['cases']),'sources':len(sources)})""")
    md('### 分层时间缺失率与单来源依赖')
    code("""rows=[]
for grain in ('platform','project'):
    subset=[c for c in cases if c['research_annotation']['grain']==grain]
    known=sum(c['timeline']['origin_year'] is not None for c in subset)
    rows.append({'grain':grain,'denominator':len(subset),'dated':known,'coverage':known/len(subset)})
single=sum(len({e['source_id'] for e in c['evidence']})==1 for c in cases)
print(rows)
print({'single_narrative_source':single,'denominator':len(cases),'fraction':single/len(cases)})
assert rows[0]['dated']==46 and rows[1]['dated']==588""")
    md('### 观察层级与来源剔除敏感性')
    code("""diagnostics=book['research']['review_diagnostics']
models=book['analysis']['archetypes']
for model in models:
    full=sum(c['research_annotation']['primary_model']==model['id'] for c in cases)/len(cases)
    platform=sum(c['research_annotation']['primary_model']==model['id'] for c in institutions)/len(institutions)
    print(model['id'],{'pooled_share':round(full,4),'institution_share':round(platform,4),'difference_percentage_points':round(100*(platform-full),2)})
for row in diagnostics['model_sensitivity']:
    subset=[c for c in cases if (row['grain']=='all' or c['research_annotation']['grain']==row['grain']) and c['research_annotation']['cohort']!=row['omitted_cohort']]
    assert len(subset)==row['denominator']
    assert sum(c['research_annotation']['primary_model']==row['model'] for c in subset)==row['count']
print('All source-omission model counts reconciled independently')""")
    md('### 要素组合与非置信区间范围')
    code("""for row in diagnostics['factor_sensitivity']:
    for estimate in row['source_cohort_results']:
        subset=[c for c in institutions if c['research_annotation']['cohort']!=estimate['omitted_cohort']]
        both=sum(row['first'] in c['factors'] and row['second'] in c['factors'] for c in subset)
        union=sum(row['first'] in c['factors'] or row['second'] in c['factors'] for c in subset)
        assert both==estimate['count'] and union==estimate['union']
        assert estimate['jaccard']==(both/union if union else None)
    if row['first'] not in ('knowledge','market') and row['second'] not in ('knowledge','market'):
        print({k:row[k] for k in ('first','second','count','jaccard','leave_one_cohort_out_min','leave_one_cohort_out_max')})""")
    md('### 固定文件校验')
    code("""manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
for f in manifest['files']:
    data=(out/f['path']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==f['sha256'] and len(data)==f['bytes']
print({'frozen_data_files':len(manifest['files']),'checksum_status':'passed'})""")
    md('## 使用判断\n可用于来源可追溯的案例检索和分层描述研究。日期缺失、单一来源、实体粒度差异以及未验证的编码仍限制历史和绩效推断。没有独立双人核验，不报告准确率。')
    namespace={}
    number=0
    for cell in cells:
        if cell['cell_type']!='code':continue
        number+=1
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):exec(compile(cell['source'],'review_cell_'+str(number),'exec'),namespace)
        cell['execution_count']=number
        cell['outputs']=[{'output_type':'stream','name':'stdout','text':stream.getvalue()}]
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python','version':'3.12'}},'cells':cells}
    # Use notebook-safe validation when the optional maintenance package exists.
    try:
        import nbformat
        nbformat.validate(nbformat.from_dict(notebook))
    except ImportError:
        pass
    (OUT/'审阅复算.ipynb').write_text(json.dumps(notebook,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'executed_cells':number,'status':'passed','notebook':'审阅复算.ipynb'},ensure_ascii=False))

if __name__=='__main__':main()
