"""Execute an offline, reproducible US case quality companion; no model calls."""
import contextlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    cells=[]
    def md(text):
        cells.append({'cell_type':'markdown','id':'us-'+str(len(cells)+1),'metadata':{},'source':text})
    def code(text):
        cells.append({'cell_type':'code','id':'us-'+str(len(cells)+1),'metadata':{},'source':text,
                      'execution_count':None,'outputs':[]})
    md('''# 美国科产融合项目：入库质量核验
## 核心结果
新增190个项目；保留原有423例。美国相关案例195例，全部案例613例。此数量描述采集覆盖，不是经济地位或创新绩效指数。
## 范围与方法
核验日期2026-10-05；粒度为独立官方项目节点。官方索引1721条，取得1470个完整对象，初筛193例，技术编译后发布190例。
### 关键假设
US依据美国牵头所在地。其他合作方国别和机构类型不推断；公开列名不当作完整机构普查。美元资助与欧元资助分开。时间覆盖历史及在研项目，研发目标不视为已达成果。
来源：config/open_innovation_us_projects.json、innovation_us_review.txt、innovation_us_exclusions.json、innovation_us_sector_review.json；公开API快照指纹及UTC采集时间逐条保留。中断页只接收完整解码项目，末尾不完整对象不修复。''')
    md('## 数据\n### 1. 加载复核配置与公开库')
    code('''from pathlib import Path
import json,re
from collections import Counter
root=next(p for p in (Path.cwd(),*Path.cwd().parents) if (p/'config/open_innovation_us_projects.json').exists())
read=lambda path:json.loads((root/path).read_text(encoding='utf-8'))
public=read('static/data/innovation_cases.json')
us=read('config/open_innovation_us_projects.json')
base=read('config/open_innovation_cases.json')['cases']+read('config/open_innovation_projects.json')['cases']
published={c['id']:c for c in public['cases']}
assert len(us['cases'])==190 and len(base)==423
assert len(public['cases'])==613
assert sum('US' in c['countries'] for c in public['cases'])==195
print({'new_US':len(us['cases']),'retained':len(base),'all_cases':len(public['cases']),'US_related':195})''')
    md('### 2. 粒度、旧资料保留和隐私字段')
    code('''assert len({c['project']['official_id'] for c in us['cases']})==len(us['cases'])
assert len({c['title']['en'].casefold().strip() for c in us['cases']})==len(us['cases'])
for original in base:
    for key in original:
        assert published[original['id']][key]==original[key],(original['id'],key)
for c in us['cases']:
    assert c['countries']==['US'] and c['scope']=='national'
    assert len(c['participants'])>=2
    assert all(set(p)=={'id','name','country','type','role'} for p in c['participants'])
    assert all(p['country'] is None and p['type'] is None for p in c['participants'][1:])
    assert c['project']['participant_count'] is None
    assert all(x['raw'] is None and x['score'] is None for x in c['profile'].values())
    assert c['project']['funding_basis']=='listed_ARPAE_award_not_actual_expenditure'
    assert 'eu_grant_eur' not in c['project']
    assert not re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}',json.dumps(c))
print('唯一项目、完整旧记录保留、机构白名单、缺失及币种隔离：通过')''')
    md('## 核验结果\n### 3. 技术覆盖与逐项来源关联')
    code('''sources={s['id']:s for s in us['sources']}
assert len(sources)==len(us['cases'])
for c in us['cases']:
    s=sources[c['evidence'][0]['source_id']]
    assert s['url'].startswith('https://arpa-e.energy.gov/programs-and-initiatives/search-all-projects/')
    assert len(s['snapshot_sha256'])==64 and s['fetched_at_utc'].endswith('+00:00')
    assert len(c['summary']['zh'])>=45 and len(c['mechanism']['zh'])>=15
counts=dict(Counter(c['sector_key'] for c in us['cases']))
assert sum(counts.values())==190
states=sorted({c['project']['lead_state'] for c in us['cases']})
years=[c['start_year'] for c in us['cases'] if c['start_year']]
result={'status':'passed','new_cases':190,'retained_cases':423,'total_cases':613,'US_related':195,
        'sector_counts':counts,'lead_state_codes':states,'lead_state_count':len(states),
        'start_year_range':[min(years),max(years)],'currencies_separate':True,'scores_imputed':False}
print(json.dumps(result,ensure_ascii=False))''')
    md('## 使用边界\n此核验支持案例检索与项目事实比较。美国采集集中于一个正式资助体系，未覆盖美国全部科产合作；不以案例数量、美元资助或缺失评分建立跨国绩效排名。原有研究报告的398项欧盟资助统计样本保持独立。')
    namespace={}
    count=0
    for item in cells:
        if item['cell_type']!='code':
            continue
        count+=1
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):
            exec(compile(item['source'],item['id'],'exec'),namespace)
        item['execution_count']=count
        item['outputs']=[{'output_type':'stream','name':'stdout','text':stream.getvalue()}]
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{
        'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'},
        'execution_driver':'Exact cells executed in shared Python namespace, in order'},'cells':cells}
    try:
        import nbformat
        nbformat.validate(nbformat.from_dict(notebook))
    except ImportError:
        import jsonschema
        jsonschema.validate(notebook,{'type':'object','required':['nbformat','nbformat_minor','metadata','cells'],
            'properties':{'nbformat':{'const':4},'cells':{'type':'array','items':{'type':'object',
                'required':['cell_type','id','metadata','source'],'properties':{'cell_type':{'enum':['code','markdown']},
                    'id':{'type':'string'},'source':{'type':'string'},'metadata':{'type':'object'}}}}}})
        assert len({c['id'] for c in cells})==len(cells)
    (ROOT/'analysis/innovation_us_audit.ipynb').write_text(json.dumps(notebook,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'analysis/innovation_us_quality.json').write_text(json.dumps(namespace['result'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(namespace['result'],ensure_ascii=False))


if __name__=='__main__':
    main()
