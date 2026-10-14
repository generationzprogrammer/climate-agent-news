"""Explicit historical additions compiled from named official evidence."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
REVIEW='2026-10-14'

def pair(zh,en):return {'zh':zh,'en':en}

def main():
    cases=[];sources=[]
    def case(key,zh,en,country,year,model,modes,factors,url,publisher,summary,actors,mechanism,observed,province=None,city=None):
        sid='s_hist_case_'+key
        row={'id':'oi_'+key,'title':pair(zh,en),'countries':[country],'scope':'national',
          'sector':pair('应用技术与产业创新','Applied research and industrial innovation'),'sector_key':'applied_innovation',
          'aliases':[zh,en],'challenges':['factor','adaptation'],'modes':modes,'institutions':['research'],
          'factors':factors,'start_year':year,'end_year':None,'review_status':'reviewed','reviewed_at':REVIEW,
          'summary':summary,'actors':actors,'mechanism':mechanism,'observed':observed,
          'evidence':[{'source_id':sid,'supports':['summary','actors','mechanism','observed','start_year']}],
          'research_annotation':{'primary_model':model,'country':country,'cohort':'history_review','basis':'source_grounded_editorial_review'}}
        if province:row['research_annotation'].update(province=province,city=city)
        cases.append(row)
        sources.append({'id':sid,'url':url,'title':zh+' 官方介绍','publisher':publisher,'language':'zh' if country=='CN' else 'en',
          'published_date':None,'reviewed_at':REVIEW,'access':'public_metadata_and_paraphrase','source_role':'primary'})
    case('tuspark_history','清华科技园大学科技转化与企业孵化','Tsinghua Science Park university translation and incubation','CN',1994,'venture',['incubation','translation'],['knowledge','talent','capital','market'],
      'https://www.tsinghua.edu.cn/info/1779/72206.htm','清华大学',
      pair('清华大学1994年启动建设的大学科技园，将大学技术和人才资源同企业研发、孵化与产业化结合。其设立目标包括技术创新、高科技企业孵化和技术及管理人才培养。','Tsinghua launched its science park in 1994 to connect university knowledge and talent with company research, incubation and commercial application.'),
      pair('清华大学及科技园运营团队、入园科技企业和跨国公司研发机构。','Tsinghua University, the park operator, technology tenants and corporate research organisations.'),
      pair('通过科技园集中承接大学服务经济的功能，为企业集聚提供空间和组织服务；技术创新、孵化和人才培养共同构成园区定位。','The university park hosts technology firms and organises translation, incubation and talent development alongside research activity.'),
      pair('清华大学对建设历程的回顾明确区分1993年筹划与1994年正式启动，并记录园区汇集企业总部和研发机构的实践。','The university history distinguishes initial planning in 1993 from the formal launch in 1994 and documents the subsequent concentration of firms and research centres.'),'CN-BJ','北京市海淀区')
    case('shenzhen_virtual_university','深圳虚拟大学园跨校科研与产业对接','Shenzhen Virtual University Park research and industrial links','CN',1999,'cluster',['network','translation'],['knowledge','talent','infrastructure','market'],
      'https://stic.sz.gov.cn/gkmlpt/content/11/11730/post_11730004.html?jump=true','深圳市科技创新委员会',
      pair('深圳虚拟大学园自1999年起集聚境内外高校资源，面向深圳产业组织科研、人才培养与成果转化。园区通过联席会议等方式连接高校和地方创新需求。','Founded in 1999, the park connects domestic and overseas universities with Shenzhen research, training and translation needs through a shared local platform.'),
      pair('深圳市科技创新主管部门、园区服务机构及入园高校，官方会议报道列举清华大学、北京大学和香港大学等。','Shenzhen science and technology authorities, the park service organisation and participating universities, including Tsinghua, Peking University and the University of Hong Kong.'),
      pair('地方提供共享组织载体，引入不同大学的科研与人才资源，再通过园区协调开展本地合作。其机制重在跨校资源对接，不把大学名称数量作为转化效果。','A shared local organisation brings together university resources and coordinates industrial links; its function is inter-university access rather than a count of institutional names.'),
      pair('2024年联席会议回顾园区1999年成立的历程，并报道其资源集成实践于2023年入选国家自主创新示范区改革创新典型案例。','The 2024 joint meeting recalled the 1999 foundation and reported recognition of its resource-integration practice in a national reform case list in 2023.'),'CN-GD','深圳市南山区')
    case('tsinghua_beijing_eiri','清华大学能源互联网创新研究院','Tsinghua Energy Internet Innovation Research Institute','CN',2015,'intermediary',['translation','joint'],['knowledge','talent','infrastructure','market'],
      'https://www.eiri.tsinghua.edu.cn/gywm/byjj/index.htm','清华大学能源互联网创新研究院',
      pair('清华大学2015年4月在北京设立的能源互联网专业研究机构，连接能源规划、关键技术研发和科技成果转化，并参与产业生态与人才培养。','Established in Beijing in April 2015, the institute connects energy-system planning, technical research, technology translation and industrial talent development.'),
      pair('清华大学相关学科、研究院研发团队、国家能源局及参与能源互联网合作的产业机构。','Tsinghua research disciplines, institute teams, the National Energy Administration and industrial collaborators.'),
      pair('依托清华多学科研究，将政策战略、创新规划与工程技术研发联系起来，组织成果转化和产业合作。','The institute combines multidisciplinary research with policy analysis, planning, engineering development and industrial translation.'),
      pair('官方简介明确2015年4月正式挂牌，并将战略研究、关键技术、成果转化和人才培养列为机构工作内容。','The official profile dates the inauguration to April 2015 and specifies strategy, technology development, translation and training functions.'),'CN-BJ','北京市海淀区')
    case('tsinghua_tianjin_ieit','清华大学天津电子信息研究院','Tsinghua Tianjin Electronic Information Research Institute','CN',2015,'intermediary',['translation','incubation'],['knowledge','talent','capital','market'],
      'https://www.ee.tsinghua.edu.cn/info/1078/1546.htm','清华大学电子工程系',
      pair('清华大学电子工程系与天津地方合作建设的研究转化机构，2015年完成批准、签约和注册。其初期建设同时涵盖研发团队引进、项目筛选、孵化与产业化对接。','The institute links Tsinghua electronic-engineering research with Tianjin industrial development. Approval, cooperation agreements and registration were completed in 2015.'),
      pair('清华大学及电子工程系、天津滨海新区、中新天津生态城、研发与项目孵化团队。','Tsinghua University and its electronic-engineering department, Tianjin Binhai New Area, the Sino-Singapore Tianjin Eco-city and technical teams.'),
      pair('通过校地协议建立本地研发与项目孵化载体，设置项目筛选和合同管理规则，将大学技术团队与地方产业化条件连接。','University–local agreements establish a translation and incubation organisation with project screening and contract rules.'),
      pair('2015年度工作简报列明1月9日校内批准、5月23日地方签约和7月20日正式注册等不同节点，并报告当年的建设与项目组织工作。','The 2015 work report distinguishes university approval on 9 January, local agreements on 23 May and registration on 20 July, alongside organisation and project activities.'),'CN-TJ','天津市滨海新区')
    case('stanford_research_park','斯坦福研究园大学与企业研发共址','Stanford Research Park university and industrial research co-location','US',1951,'cluster',['translation','incubation'],['knowledge','talent','infrastructure','market'],
      'https://stanfordresearchpark.com/about/','Stanford Research Park',
      pair('斯坦福大学与帕洛阿尔托1951年合作建立的研究园，通过大学附近的研发空间承接科技企业与研发团队，形成大学知识、人才和企业研发活动的连接。','Founded in 1951 through a partnership between Stanford and Palo Alto, the park hosts companies and research teams close to university knowledge and talent.'),
      pair('斯坦福大学、帕洛阿尔托市及入园企业，官方介绍列明Varian、惠普、SAP和特斯拉等历史或现有研发参与者。','Stanford University, the City of Palo Alto and tenants, with the official history naming Varian, HP, SAP and Tesla among past or present participants.'),
      pair('由大学关联园区提供研发集聚空间和社区联系，企业保持独立运营，并通过邻近大学接触科研和人才资源。','A university-affiliated park provides research space and community links while companies operate independently and access nearby academic resources.'),
      pair('官方园区历史将起点标为1951年，并记录多个时期企业研发部门在园区布局；这些企业不被假定为同时在场或共同完成同一项目。','The official history dates the park to 1951 and records corporate research tenants over different periods, without implying simultaneous tenancy or participation in one project.'))
    case('cambridge_science_park','剑桥科学园大学土地与产业研发集聚','Cambridge Science Park university land and industrial research','GB',1970,'cluster',['translation','incubation'],['knowledge','talent','infrastructure','market'],
      'https://www.cambridgesciencepark.co.uk/our-story/','Cambridge Science Park',
      pair('剑桥大学三一学院1970年创办的科学园，利用大学土地和长期运营安排，为研究型企业提供集聚空间，连接学术研究与产业发展。','Founded by Trinity College Cambridge in 1970, the science park uses university land and long-term stewardship to connect research-intensive firms with academia.'),
      pair('剑桥大学三一学院、园区运营团队和入园科研及科技企业。','Trinity College Cambridge, the park operator and resident research and technology firms.'),
      pair('通过大学关联的空间载体组织科研企业集聚，使企业接近大学研究和人才网络；园区提供的组织环境与具体项目成果分开记录。','A university-linked location places firms close to academic research and talent networks; the enabling environment is recorded separately from project outcomes.'),
      pair('官方历史明确1970年创办，并介绍长期容纳生命科学、电子与可持续材料等企业研发活动。','The official history records the 1970 foundation and subsequent research activity in life sciences, electronics and sustainable materials.'))
    case('tno_history','荷兰TNO应用研究与产业合作','TNO applied research and industrial collaboration','NL',1932,'intermediary',['translation','joint'],['knowledge','talent','infrastructure','market'],
      'https://www.tno.nl/en/about-tno/organisation/','TNO',
      pair('荷兰1932年依法设立的应用科学研究组织，围绕社会和产业问题组织科研合作，在能源、产业、建筑和数字技术等领域提供研究能力。','Established by law in 1932, TNO organises applied research around societal and industrial problems, including energy, industry, buildings and digital technology.'),
      pair('TNO应用研究团队、企业合作方和公共部门；不同项目的参与者按各自协议组织。','TNO research teams, industrial partners and public organisations, with participation arranged at project level.'),
      pair('以独立应用研究机构衔接知识研究与产业需要，按研究主题开展多方合作，不要求所有企业将研发活动集中到同一园区。','An independent applied-research organisation connects knowledge with industrial needs through thematic collaborations rather than requiring all research to share one park.'),
      pair('官方组织介绍明确1932年的法定设立时间，并列出能源系统、工业低碳和技术应用等研究领域。','The official profile identifies its statutory foundation in 1932 and research areas including energy systems, industrial decarbonisation and technology application.'))
    result={'reviewed_at':REVIEW,'cases':cases,'sources':sources,
      'sector_taxonomy':{'applied_innovation':pair('应用技术与产业创新','Applied research and industrial innovation')}}
    (ROOT/'config/open_innovation_historical_cases.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cases':len(cases),'sources':len(sources)}))
if __name__=='__main__':main()
