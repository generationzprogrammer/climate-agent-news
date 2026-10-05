"""Create and execute a bounded, source-backed data-quality companion."""
from pathlib import Path
import json, io, contextlib, types
try:
    import nbformat as nb
    from nbclient import NotebookClient
except ImportError:
    # This desktop lacks Jupyter packages and its package index is unavailable.
    # Generate nbformat 4.5 JSON, validate the cells, and execute the exact code
    # in one Python namespace. No unexecuted results are inserted.
    def cell(kind, source):
        result={"cell_type":kind,"metadata":{},"source":source}
        if kind=='code': result.update(execution_count=None,outputs=[])
        return result
    nb=types.SimpleNamespace(v4=types.SimpleNamespace(
        new_markdown_cell=lambda source:cell('markdown',source),
        new_code_cell=lambda source:cell('code',source),
        new_notebook=lambda **kwargs:{"nbformat":4,"nbformat_minor":5,**kwargs}))
    NotebookClient=None

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/reports/open_innovation/数据核验与统计复算.ipynb"
md = nb.v4.new_markdown_cell
code = nb.v4.new_code_cell
cells = [
md("""# 科产融合案例：数据核验与统计复算
## 核心结果
保留原有25例，合计423例；结构统计仅使用398个独立资助项目。项目参与机构中位数11家、登记参与国中位数6个、最高欧盟资助额中位数约5.05百万欧元。
## 范围与方法
2026-10-05官方CORDIS Horizon Europe快照；目的性能源协作样本，非全球普查。机构按同项目内机构编号去重，金额非支出，目标非已实现成果。
### 关键假设
登记机构及其类型反映所选公开快照；科研主体为HES与REC之和。不同框架与项目粒度不混加绩效，缺失数据不评分。未联网采集、未调用模型。
来源：config/open_innovation_projects.json、config/open_innovation_cases.json、static/data/innovation_cases.json；图表实际SQL及数据见artifact.json。"""),
code("""from pathlib import Path
import json, math, statistics
from collections import Counter
root = next(p for p in (Path.cwd(), *Path.cwd().parents) if (p/'config/open_innovation_projects.json').exists())
book = json.loads((root/'static/data/innovation_cases.json').read_text(encoding='utf-8'))
prior = json.loads((root/'config/open_innovation_cases.json').read_text(encoding='utf-8'))
projects = [c for c in book['cases'] if c.get('project',{}).get('funding_basis')=='maximum_EU_contribution_not_actual_expenditure']
audit = json.loads((root/'analysis/reports/open_innovation/analysis_results.json').read_text(encoding='utf-8'))
print({'report_snapshot_cases':len(projects)+len(prior['cases']), 'current_catalog_cases':len(book['cases']), 'projects':len(projects), 'retained':len(prior['cases'])})"""),
md("## 数据检查\n按官方项目编号与机构编号核验粒度，独立复算雷达图的原始量；公开参与方字段采用白名单。"),
code("""assert len({c['project']['official_id'] for c in projects}) == len(projects)
published = {c['id']:c for c in book['cases']}
for c in prior['cases']:
    assert all(published[c['id']][field] == c[field] for field in ('summary','actors','mechanism','observed'))
for c in projects:
    participants, p = c['participants'], c['project']
    types = Counter(o['type'] for o in participants)
    assert len({o['id'] for o in participants}) == p['participant_count']
    assert len({o['country'] for o in participants}) == p['country_count']
    assert types['PRC'] == p['company_count']
    assert types['HES'] + types['REC'] == p['research_count']
    assert len(types) == p['actor_type_count']
    assert all(set(o) <= {'id','name','country','type','role','eu_contribution_eur'} for o in participants)
    assert p['funding_basis'] == 'maximum_EU_contribution_not_actual_expenditure'
print('项目唯一性、原有事实保留、机构统计与隐私字段白名单：通过')"""),
md("## 统计结果\n整体中位数、协调主体分布与相关系数由公开项目字段独立复算。"),
code("""rows = [c['project'] for c in projects]
fields = ('participant_count','country_count','company_count','research_count','eu_grant_million')
medians = {f:statistics.median(p[f] for p in rows) for f in fields}
assert medians == audit['medians']
coordinators = dict(Counter(p['coordinator_type'] for p in rows))
assert coordinators == audit['coordinators']
def correlation(values):
    xs = [math.log1p(p['participant_count']) for p in values]
    ys = [math.log1p(p['eu_grant_million']) for p in values]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/math.sqrt(sum((x-mx)**2 for x in xs)*sum((y-my)**2 for y in ys))
assert math.isclose(correlation(rows), audit['correlation']['log_pearson'], rel_tol=1e-12)
print({'medians':medians, 'coordinators':coordinators, 'log_pearson':round(correlation(rows),4)})"""),
md("### 溯源抽查\n以电池循环项目为例；资助与研究目标保持各自口径，不将项目目标写成产量或收益。"),
code("""sample = next(c for c in projects if c['project']['acronym']=='BATRAW')
source = next(s for s in book['sources'] if s['id']==sample['evidence'][0]['source_id'])
print({'project':sample['project']['official_id'], 'title':sample['title']['zh'],
       'maximum_eu_grant_million':sample['project']['eu_grant_million'], 'source':source['url']})
print(sample['objective_excerpt']['zh'])"""),
md("""## 解释与使用
科研主体协调占74.4%，不表示企业贡献较低；资助规模与机构数的相关关系不能证明参与方增加带来成果改善。样本中位数支持多对多协作的组织特征，案例原文用于分析制造、验证、循环利用与制度接口。
跨区域借鉴应先对齐技术任务和项目层级，雷达分档仅描述合作结构；不能据案例数、资助额或图形面积评估国家创新绩效。"""),
]
notebook = nb.v4.new_notebook(cells=cells, metadata={"kernelspec":{"name":"python3","display_name":"Python 3","language":"python"}})
if NotebookClient:
    NotebookClient(notebook, timeout=60, kernel_name="python3", resources={"metadata":{"path":str(ROOT)}}).execute()
    nb.validate(notebook)
    nb.write(notebook, OUT)
else:
    import jsonschema
    namespace={}
    counter=0
    for i, item in enumerate(notebook['cells']):
        item['id']=f"audit-{i+1:02d}"
        if item['cell_type']=='code':
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream): exec(compile(item['source'],f"audit-cell-{i+1}",'exec'),namespace)
            counter+=1
            item['execution_count']=counter
            item['outputs']=[{"output_type":"stream","name":"stdout","text":stream.getvalue()}]
        jsonschema.validate(item,{"type":"object","required":["cell_type","metadata","source","id"],"properties":{
            "cell_type":{"enum":["code","markdown"]},"source":{"type":"string"},"metadata":{"type":"object"},"id":{"type":"string","pattern":"^[A-Za-z0-9_-]{1,64}$"},
            "execution_count":{"type":"integer"},"outputs":{"type":"array","items":{"type":"object","required":["output_type","name","text"],"properties":{"output_type":{"const":"stream"},"name":{"const":"stdout"},"text":{"type":"string"}}}}}})
    assert notebook['nbformat']==4 and len({c['id'] for c in notebook['cells']})==len(notebook['cells'])
    notebook['metadata']['execution_driver']='Python shared namespace; Jupyter kernel unavailable; all code cells executed in order'
    OUT.write_text(json.dumps(notebook,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print("Notebook executed: 4 bounded calculation cells; all checks passed")
