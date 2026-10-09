"""Execute the exact notebook cells offline; retain reproducible audit output."""
import contextlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    cells=[]
    def md(text):
        cells.append(dict(cell_type="markdown",id="models-"+str(len(cells)+1),metadata={},source=text))
    def code(text):
        cells.append(dict(cell_type="code",id="models-"+str(len(cells)+1),metadata={},source=text,execution_count=None,outputs=[]))
    md("""# 科产融合模式与区域比较：复算核验
## 结论与范围
2026-10-09快照保留613个原案例，新增24个机构案例，其中中国21个。广东8个、浙江11个平台案例用于机制比较，不构成省级普查。平台与资助项目、美元与欧元分别处理，不以样本数或结构评分推断创新绩效。
数据：config/open_innovation_*.json、static/data/innovation_cases.json；报告统计为执行后的SQLite结果。问题标签保留，但不再作主分类。人工机制编码是解释而非官方评级。""")
    code("""from pathlib import Path
import json
from collections import Counter
root=next(p for p in (Path.cwd(),*Path.cwd().parents) if (p/'config/open_innovation_models.json').exists())
read=lambda p:json.loads((root/p).read_text(encoding='utf-8'))
b=read('static/data/innovation_cases.json')
old=sum([read('config/'+n)['cases'] for n in ('open_innovation_cases.json','open_innovation_projects.json','open_innovation_us_projects.json')],[])
new=read('config/open_innovation_regional_cases.json')['cases']
current={c['id']:c for c in b['cases']}
assert len(old)==613 and len(new)==24 and len(current)==637
for c in old:
    for k in ('title','summary','observed','countries','evidence'):
        assert c[k]==current[c['id']][k],(c['id'],k)
assert sum(c['countries']==['CN'] for c in new)==21
print({'retained':len(old),'added':len(new),'total':len(current),'new_China':21})""")
    md("## 分类、比较分母与证据\n宏观统计按项目协调国或平台明确的单国主体互斥计数；跨国与缺失单列，不累计所有参与国。")
    code("""a=b['analysis']; sources={s['id'] for s in b['sources']}
assert len(a['archetypes'])==8 and len(a['profiles'])==9
for p in a['profiles']:
    assert set(p['case_ids'])<=current.keys() and set(p['source_ids'])<=sources
    assert all(p[k]['zh'] and p[k]['en'] for k in ('conditions','mechanism','government','boundary','factors'))
for grain in ('platform','project'):
    subset=[c for c in b['cases'] if c['research_annotation']['grain']==grain]
    for dim in ('continent','economy'):
        rs=[r for r in a['macro'] if r['grain']==grain and r['dimension']==dim]
        assert sum(r['count'] for r in rs)==len(subset)
        for group in {r['group'] for r in rs}:
            rows=[r for r in rs if r['group']==group]; n=rows[0]['denominator']
            assert sum(r['count'] for r in rows)==n
            assert sum(rows[0]['source_cohorts'].values())==n
            assert abs(sum(r['share'] for r in rows)-1)<1e-12 if n else all(r['share'] is None for r in rows)
counts=Counter(c['research_annotation'].get('province') for c in new)
assert counts['CN-GD']==8 and counts['CN-ZJ']==11
print({'archetypes':8,'profiles':9,'province_cases':dict(counts),'sources_resolved':True})""")
    md("## 图表独立复算\n将报告SQL输出与独立Python计数逐项核对，确认图表分子、分母一致。")
    code("""audit=read('analysis/reports/open_innovation_20261009/统计核验.json')
for row in audit['regional']:
    province='CN-GD' if row['地区']=='广东' else 'CN-ZJ'
    subset=[c for c in new if c['research_annotation'].get('province')==province]
    n=sum(c['research_annotation']['primary_model']==row['模式代码'] for c in subset)
    assert n==row['案例数'] and len(subset)==row['地区样本数']
    assert abs(n/len(subset)-row['比例'])<1e-12
eu=[c for c in b['cases'] if c.get('project',{}).get('funding_basis')=='maximum_EU_contribution_not_actual_expenditure']
assert len(eu)==398
for row in audit['eu']:
    subset=[c for c in eu if c['sector']['zh']==row['技术领域']]
    def role(c):
        t=c['project']['coordinator_type']
        return '企业' if t=='PRC' else '高校与研究机构' if t in ('HES','REC') else '公共及其他机构'
    n=sum(role(c)==row['协调方'] for c in subset)
    assert n==row['项目数'] and len(subset)==row['领域项目数']
    assert abs(n/len(subset)-row['比例'])<1e-12
result={'status':'passed','cases':637,'retained_cases':613,'new_cases':24,'new_China_cases':21,
        'models':9,'archetypes':8,'Guangdong':8,'Zhejiang':11,'EU_projects':398,'SQL_independently_reconciled':True}
print(json.dumps(result,ensure_ascii=False))""")
    md("""## 使用边界
来源渠道并不均衡。宏观比例说明本库构成，不估计全球总体；项目登记目标不等于成果。UNCTAD分组不是收入等级，塞浦路斯、土耳其待完整名单复核。机构事实与适配解释分别保存。链接自动检测受403、TLS和HEAD支持限制，不将检测失败直接判为资料虚假。此报告为注明日期的研究快照；日常导出持续保留已复核案例，不自动重写结论。""")
    ns={}; count=0
    for c in cells:
        if c['cell_type']!='code':continue
        count+=1; out=io.StringIO()
        with contextlib.redirect_stdout(out):exec(compile(c['source'],c['id'],'exec'),ns)
        c.update(execution_count=count,outputs=[dict(output_type="stream",name="stdout",text=out.getvalue())])
    book=dict(nbformat=4,nbformat_minor=5,metadata={"kernelspec":{"name":"python3","display_name":"Python 3","language":"python"},"execution_driver":"Exact cells executed sequentially in one Python namespace"},cells=cells)
    assert len({c['id'] for c in cells})==len(cells)
    try:
        import nbformat
        nbformat.validate(nbformat.from_dict(book))
    except ImportError:
        import jsonschema
        jsonschema.validate(book,{"type":"object","required":["nbformat","nbformat_minor","metadata","cells"],"properties":{"nbformat":{"const":4},"cells":{"type":"array","items":{"type":"object","required":["cell_type","id","metadata","source"]}}}})
    (ROOT/'analysis/innovation_models_audit.ipynb').write_text(json.dumps(book,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'analysis/innovation_models_quality.json').write_text(json.dumps(ns['result'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(ns['result'],ensure_ascii=False))

if __name__=='__main__':main()
