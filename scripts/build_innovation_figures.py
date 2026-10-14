"""Publication-size figures from the frozen research release; no fitted causal claims."""
from collections import Counter
import json
import os
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/os.environ.get('INNOVATION_RESEARCH_OUTPUT','analysis/innovation_research_20261014')/'figures'
COLORS=['#275679','#56879b','#86aeb9','#b8d4d5','#996d36','#bb9967','#d6c3a5','#767c83']
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    b=json.loads((OUT.parent/'data/cases_nested.json').read_text(encoding='utf-8'));r=b['research'];models=b['analysis']['archetypes']
    short_en={'venture':'Venture support','mission':'Mission R&D','intermediary':'Intermediary','consortium':'Consortium','pilot':'Pilots','cluster':'Clusters','capacity':'Capability building','rules':'Rule coordination'}
    short_zh={'venture':'科研创业','mission':'任务攻关','intermediary':'专业转移','consortium':'研发联合体','pilot':'开放中试','cluster':'产业集群','capacity':'能力建设','rules':'规则协调'}
    for f in ['C:/Windows/Fonts/times.ttf','C:/Windows/Fonts/msyh.ttc']:
        if Path(f).exists():font_manager.fontManager.addfont(f)
    plt.rcParams.update({'font.family':['Times New Roman','Microsoft YaHei'],'font.size':9,'axes.titlesize':10,'axes.labelsize':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42,'axes.linewidth':.6,'xtick.major.width':.6,'ytick.major.width':.6})
    def save(fig,name):
        for ext in ('svg','pdf','png'):fig.savefig(OUT/(name+'.'+ext),dpi=450,bbox_inches='tight',facecolor='white')
        plt.close(fig)
    for lang in ('en','zh'):
        text=lambda en,zh:zh if lang=='zh' else en
        label=lambda value:value[lang]
        # Figure 1: source selection and record level, plus geography with explicit focus-country counting.
        fig,axes=plt.subplots(1,2,figsize=(7.2,3.65),gridspec_kw={'width_ratios':[1,1.25]})
        cohorts=r['source_strata'];ys=np.arange(len(cohorts));names={'ARPAE':'ARPA-E','CORDIS':'CORDIS','coverage_review':text('Geographic review','区域补充'),'expansion_review':text('Geographic expansion','地域扩充'),'history_review':text('Historical review','历史补充'),'legacy_review':text('Initial institutions','首批机构'),'regional_review':text('Institutional review','机构补充'),'peer_review':text('Reviewer supplement','审阅补充')}
        axes[0].barh(ys,[row['count'] for row in cohorts],color=['#56879b' if row['cohort'] in ('ARPAE','CORDIS') else '#275679' for row in cohorts]);axes[0].set_yticks(ys,[names[row['cohort']] for row in cohorts]);axes[0].invert_yaxis();axes[0].set_xlabel(text('Cases','案例数'));axes[0].set_xlim(0,460)
        for i,row in enumerate(cohorts):axes[0].text(row['count']+6,i,str(row['count']),va='center',fontsize=8)
        groups=['asia','europe','north_america','south_america','africa','oceania','cross_region'];pos=np.arange(len(groups));left=np.zeros(len(groups))
        for grain,color in [('platform','#275679'),('project','#86aeb9')]:
            values=[sum(c['research_annotation']['grain']==grain and c['research_annotation']['continent']==g for c in b['cases']) for g in groups]
            axes[1].barh(pos,values,left=left,color=color,label=text('Institutions' if grain=='platform' else 'Funded projects','平台机构' if grain=='platform' else '资助项目'));left+=values
        axes[1].set_yticks(pos,[label(b['analysis']['group_labels'][g]) for g in groups]);axes[1].invert_yaxis();axes[1].set_xlabel(text('Cases by focus location','按主要所在地计数'));axes[1].legend(frameon=False,loc='lower right',fontsize=8);axes[1].set_xlim(0,460)
        for i,n in enumerate(left):axes[1].text(n+6,i,str(int(n)),va='center',fontsize=8)
        for ax,letter in zip(axes,'ab'):ax.set_title(letter,loc='left',fontweight='bold');ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
        fig.tight_layout(w_pad=2);save(fig,'Figure1_coverage_'+lang)
        # Figure 2: source-by-mode composition makes the register-induced coding visible.
        matrix=np.array([[row['models'].get(m['id'],0) for m in models] for row in cohorts]);shares=matrix/matrix.sum(axis=1,keepdims=True)
        fig,ax=plt.subplots(figsize=(7.2,3.8));im=ax.imshow(shares,cmap='Blues',vmin=0,vmax=1,aspect='auto')
        ax.set_xticks(range(len(models)),[(short_zh if lang=='zh' else short_en)[m['id']] for m in models],rotation=30,ha='right');ax.set_yticks(range(len(cohorts)),[names[x['cohort']] for x in cohorts])
        for i in range(len(cohorts)):
            for j in range(len(models)):ax.text(j,i,str(matrix[i,j]),ha='center',va='center',color='white' if shares[i,j]>.5 else '#1b2730',fontsize=8)
        fig.colorbar(im,ax=ax,shrink=.7,label=text('Within-source proportion','同来源内比例'));ax.set_title(text('Counts and within-source composition','来源分层的模式构成'),loc='left');fig.tight_layout();save(fig,'Figure2_source_modes_'+lang)
        # Figure 3: verified origin cohorts only; unknown origins are not allocated to a period.
        fig,axes=plt.subplots(1,2,figsize=(7.2,3.4),gridspec_kw={'width_ratios':[1,1.25]})
        for ax,scope in zip(axes,['china_plans','global_decades']):
            rows=[row for row in r['temporal'] if row['grain']=='platform' and row['basis']=='origin' and row['scope']==scope and row['period']!='undated'];x=np.arange(len(rows));bottom=np.zeros(len(rows))
            for m,color in zip(models,COLORS):
                vals=[row['models'].get(m['id'],0) for row in rows];ax.bar(x,vals,bottom=bottom,color=color,width=.72,label=(short_zh if lang=='zh' else short_en)[m['id']]);bottom+=vals
            labels=[label(row['label']).split('（')[0] if lang=='zh' else (row['period'].split('_')[-1]+'th plan' if scope=='china_plans' else row['period']) for row in rows]
            ax.set_xticks(x,labels,rotation=40,ha='right');ax.set_ylabel(text('Institutions with verified origins','起始时间已核验的平台机构'));ax.set_title(text('China five-year plans' if scope=='china_plans' else 'Global decades','中国五年规划期' if scope=='china_plans' else '全球十年期'),loc='left');ax.yaxis.get_major_locator().set_params(integer=True);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
        handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='lower center',ncol=4,frameon=False,fontsize=8);fig.tight_layout(rect=[0,.2,1,1]);save(fig,'Figure3_origins_'+lang)
        # Figure 4: descriptive association within reviewed institutions, not register-driven grants.
        keys=list(b['taxonomy']['factors']);mat=np.eye(len(keys));counts=np.zeros((len(keys),len(keys)),dtype=int)
        for row in r['factor_pairs']:
            if row['grain']!='platform':continue
            i,j=keys.index(row['first']),keys.index(row['second']);mat[i,j]=mat[j,i]=row['jaccard'] or 0;counts[i,j]=counts[j,i]=row['count']
        fig,ax=plt.subplots(figsize=(6.3,4.3));masked=np.ma.array(mat,mask=np.eye(len(keys),dtype=bool));im=ax.imshow(masked,cmap='Blues',vmin=0,vmax=1)
        labels=[label(b['taxonomy']['factors'][k]) for k in keys];ax.set_xticks(range(len(keys)),labels,rotation=32,ha='right');ax.set_yticks(range(len(keys)),labels)
        for i in range(len(keys)):
            for j in range(len(keys)):
                if i!=j:ax.text(j,i,f'{mat[i,j]:.2f}\n(n={counts[i,j]})',ha='center',va='center',fontsize=7.5,color='white' if mat[i,j]>.55 else '#1b2730')
        ax.set_title(text('Factor overlap within reviewed institutions','平台机构中的合作要素重叠'),loc='left');fig.colorbar(im,ax=ax,shrink=.7,label='Jaccard');fig.tight_layout();save(fig,'Figure4_factors_'+lang)
        if r.get('review_diagnostics'):
            ds=r['review_diagnostics']
            # Validation figure: missing origin dates by institutional location.
            fig,axes=plt.subplots(1,2,figsize=(7.2,3.7),gridspec_kw={'width_ratios':[1,1.15]})
            groups=['asia','europe','north_america','south_america','africa','oceania','cross_region']
            platforms=[c for c in b['cases'] if c['research_annotation']['grain']=='platform']
            known=[sum(c['research_annotation']['continent']==g and c['timeline']['origin_year'] is not None for c in platforms) for g in groups]
            unknown=[sum(c['research_annotation']['continent']==g and c['timeline']['origin_year'] is None for c in platforms) for g in groups]
            y=np.arange(len(groups));axes[0].barh(y,known,color='#275679',label=text('Supported origin','起始时间有证据'))
            axes[0].barh(y,unknown,left=known,color='#e1e5e8',edgecolor='#767c83',hatch='///',linewidth=.4,label=text('Unknown origin','起始时间未核验'))
            axes[0].set_yticks(y,[label(b['analysis']['group_labels'][g]) for g in groups]);axes[0].invert_yaxis();axes[0].set_xlabel(text('Institutional cases','机构案例数'));axes[0].set_title(text('a  Origin-date coverage','a  起始日期覆盖'),loc='left');axes[0].legend(frameon=False,fontsize=7,loc='lower right')
            model_ids=[m['id'] for m in models];p=ds['model_sensitivity']
            full=[next(x['share'] for x in p if x['grain']=='all' and x['omitted_cohort']=='none' and x['model']==m) for m in model_ids]
            inst=[next(x['share'] for x in p if x['grain']=='platform' and x['omitted_cohort']=='none' and x['model']==m) for m in model_ids]
            y=np.arange(len(models));axes[1].barh(y-.17,np.array(full)*100,height=.3,color='#275679',label=text('All records','全部记录'));axes[1].barh(y+.17,np.array(inst)*100,height=.3,color='#bb9967',label=text('Institutions only','仅机构记录'))
            axes[1].set_yticks(y,[(short_zh if lang=='zh' else short_en)[m] for m in model_ids]);axes[1].invert_yaxis();axes[1].set_xlim(0,65);axes[1].set_xlabel(text('Within-subset percentage','各自子样本内占比（%）'));axes[1].set_title(text('b  Record-level sensitivity','b  记录层级敏感性'),loc='left');axes[1].legend(frameon=False,fontsize=7)
            for ax in axes:ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
            fig.tight_layout(w_pad=2);save(fig,'Figure5_validation_'+lang)
            # Non-universal factors; the interval is sensitivity to acquisition strata.
            rows=[x for x in ds['factor_sensitivity'] if x['first'] not in ('knowledge','market') and x['second'] not in ('knowledge','market')]
            fig,ax=plt.subplots(figsize=(7.2,3.6));y=np.arange(len(rows))
            for i,row in enumerate(rows):
                ax.plot([row['leave_one_cohort_out_min'],row['leave_one_cohort_out_max']],[i,i],color='#767c83',lw=2)
                ax.plot(row['jaccard'],i,'o',color='#275679',markersize=5)
                ax.text(.36,i,'n='+str(row['count']),va='center',fontsize=8)
            ax.set_yticks(y,[label(b['taxonomy']['factors'][x['first']])+' + '+label(b['taxonomy']['factors'][x['second']]) for x in rows]);ax.invert_yaxis();ax.set_xlim(-.015,.4);ax.set_xticks([0,.1,.2,.3]);ax.set_xlabel(text('Jaccard overlap; bars are leave-one-cohort-out ranges','Jaccard重叠；横线为逐一剔除采集批次的范围'));ax.set_title(text('Institutional resource-code sensitivity','机构要素编码的来源敏感性'),loc='left');ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True);fig.tight_layout();save(fig,'Figure6_sensitivity_'+lang)
    print(json.dumps({'figures':len(list(OUT.glob('*.png'))),'formats':['PNG 450 dpi','SVG','PDF']}))
if __name__=='__main__':main()
