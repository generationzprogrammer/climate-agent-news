"""Rebuild lightweight, source-labelled SVGs after each successful admission."""
import json,hashlib,argparse
from pathlib import Path
from collections import Counter
from html import escape
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--site',default='static');args=parser.parse_args()
    site=ROOT/args.site
    path=site/'data/innovation_cases.json';book=json.loads(path.read_text(encoding='utf-8'))
    cases=book['cases'];regions=['asia','europe','north_america','south_america','africa','oceania','cross_region'];out=site/'innovation/assets';out.mkdir(parents=True,exist_ok=True)
    values=[sum(c['research_annotation']['continent']==g for c in cases) for g in regions];maximum=max(values);scale=680/(maximum*1.12)
    parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="510" viewBox="0 0 1080 510" role="img" aria-label="案例地域覆盖"><rect width="1080" height="510" fill="white"/><g font-family="Microsoft YaHei,Arial,sans-serif" fill="#24343f"><text x="35" y="44" font-size="25">科产融合案例地域覆盖</text>']
    for i,g in enumerate(regions):
        y=97+i*49;p=sum(c['research_annotation']['continent']==g and c['research_annotation']['grain']=='platform' for c in cases);n=values[i]
        parts.append(f'<text x="230" y="{y+21}" text-anchor="end" font-size="19">{escape(book["analysis"]["group_labels"][g]["zh"])}</text><rect x="250" y="{y}" width="{p*scale:.2f}" height="29" fill="#275679"/><rect x="{250+p*scale:.2f}" y="{y}" width="{(n-p)*scale:.2f}" height="29" fill="#a2becb"/><text x="{260+n*scale:.2f}" y="{y+21}" font-size="19">{n}</text>')
    parts.append(f'<text x="250" y="465" font-size="17">深色：机构与平台　浅色：资助项目　共 {len(cases)} 条</text><text x="35" y="496" font-size="15">主要所在地互斥计数；非国家创新绩效排名。更新：{escape(book["updated_at"])}</text></g></svg>')
    target=out/'coverage-latest.svg';target.write_text(''.join(parts),encoding='utf-8')
    snapshot={'updated_at':book['updated_at'],'cases':len(cases),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'figure_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'focus_regions':dict(zip(regions,values)),'update_policy':book['research']['update_policy']}
    (site/'data/innovation_update.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cases':len(cases),'figure':'innovation/assets/coverage-latest.svg'}))
if __name__=='__main__':main()
