"""Allow-listed private handover; never includes credentials or subscription data."""
import argparse,json,os,platform,zipfile
from pathlib import Path
import fulltext_pilot as p
from export_global_expansion import file_hash
ROOT=p.ROOT;OUT=ROOT/'analysis/global_expansion_20261106';PRIVATE=ROOT/'data/private_global_expansion_20261106'
SCRIPTS=['fulltext_pilot','bulk_fulltext','fulltext_review_rules','recover_fulltext_urls','collect_public_fulltext_library','collect_global_expansion','probe_expansion_sources','expansion_quality','label_global_expansion','label_priority_supplement','ocr_historical_issue','ocr_1992_english','assemble_1992_article','assemble_1997_press_release','collect_airclim_history','collect_targeted_coverage','resolve_targeted_dates','review_targeted_coverage','postvalidate_global_labels','export_global_expansion','census_global_acquisition','audit_expansion_sources','expansion_progress','probe_early_unfccc','package_global_expansion','build_fulltext_research_index']
MODULES=['__init__','article_content','research','taxonomy','governance_labels','governance_taxonomy_v2','publisher_recovery']
SCRIPTS.extend(['audit_global_snapshot','review_source_crosscheck','run_expansion_tests','repartition_label_cache'])
def main(args):
 if Path(args.output_name).name!=args.output_name or not args.output_name.endswith('.zip'):raise SystemExit('Output must be a ZIP filename, not a path.')
 package=OUT/args.output_name
 if package.exists():raise SystemExit('Existing package retained; choose a new delivery version.')
 snap=OUT/args.snapshot;v=json.loads((snap/'validation.json').read_text('utf-8'));cov=json.loads((snap/'coverage.json').read_text('utf-8'))
 if not v['snapshot_complete']:raise SystemExit('Incomplete annotation snapshot; packaging blocked.')
 qa=json.loads((snap/'quality_audit.json').read_text('utf-8'))
 counts=v['counts'];goals={'eligible_at_least_100000':counts['eligible']>=100000,'countries_249':v['country_coverage']==249,'subtopics_83':v['subcategory_coverage']==83,'original_1992_article':cov['years'].get('1992',0)>0}
 goals['country_and_topic_code_sets_verified']=not any(qa[k] for k in ['missing_country_codes','unknown_country_codes','missing_subtopic_codes','unknown_subtopic_codes'])
 baseline_map=json.loads((OUT/'baseline_split_map.json').read_text('utf-8'))
 goals['original_files_unchanged']=all(file_hash(ROOT/name.replace('\\','/'))==record['sha256'] for name,record in baseline_map.items())
 files={str(f.relative_to(snap)):f for f in snap.iterdir() if f.is_file() and f.suffix in ('.json','.gz','.sqlite') and f.name!='package_manifest.json'}
 for name in ['global_fulltext_collection_protocol_20261106.txt','global_fulltext_visualization_queries.sql']:files['说明/'+name]=ROOT/'docs'/name
 for name in SCRIPTS:files['reproduction/scripts/'+name+'.py']=ROOT/'scripts'/(name+'.py')
 for name in MODULES:files['reproduction/src/climate_agent/'+name+'.py']=ROOT/'src/climate_agent'/(name+'.py')
 for name in ['country_codes.json','research_archives.json','global_coverage_seeds_20261106.json']:files['reproduction/config/'+name]=ROOT/'config'/name
 files['reproduction/requirements-fulltext-runtime.txt']=ROOT/'requirements-fulltext-runtime.txt'
 for f in OUT.glob('*.json'):
  if f.name.startswith(('run_config','acquisition_freeze','acquisition_census','source_probes','baseline_split_map','source_crosscheck','targeted_attempts','airclim_attempts','test_results','label_cache_manifest')) or f.name.endswith('_state.json'):files['audit/'+f.name]=f
 for f in (PRIVATE/'source_audit').glob('*.json'):files['audit/source_page_crosscheck/'+f.name]=f
 for f in (PRIVATE/'targeted').glob('*.json'):files['audit/verified_supplement/'+f.name]=f
 for f in (PRIVATE/'historical').glob('*_verified.json'):files['audit/verified_supplement/'+f.name]=f
 for name in ['source.pdf','page_14.png','ocr_page_14_english.json','article_reconstruction_audit.json','english_model_provenance.json']:
  f=PRIVATE/'historical/airclim_june_1992'/name
  if f.exists():files['audit/1992_source/'+name]=f
 f=PRIVATE/'historical/early_unfccc/indust.htm.gz'
 if f.exists():files['audit/1997_source/indust.htm.gz']=f
 for f in (ROOT/'analysis/governance_handover_20261105_final').glob('*labeled_fulltexts.jsonl.gz'):files['baseline_archive/'+f.name]=f
 for pattern in ['test_global_postvalidation.py','test_expansion_quality.py','test_governance_taxonomy_v2.py','test_fulltext*.py','test_bulk_fulltext.py','test_public_fulltext_library.py']:
  for f in (ROOT/'tests').glob(pattern):files['reproduction/tests/'+f.name]=f
 missing=[name for name,f in files.items() if not f.exists()]
 if missing:raise SystemExit('Missing allow-listed files: '+str(missing))
 readme=f'''全球气候治理全文语料交接说明（2026-11-06）

一、当前结果
去重后共{counts['unique_records']:,}条记录；其中{counts['eligible']:,}条通过本次完整性与相关性规则，{counts['review_required']:,}条列入待复核层。合格集合含1992年原始文章。国家及地区提及覆盖{v['country_coverage']}项ISO代码，二级议题覆盖{v['subcategory_coverage']}项。
目标检查：{json.dumps(goals,ensure_ascii=False)}。
“通过规则筛选”不等于逐篇人工审读。国家覆盖依据原文提及证据，不代表各地样本均衡，也不等于报道主要讨论该国。请同时使用coverage.json中的重点候选统计。

二、建议交付给研究合作者的文件
优先使用climate_governance.sqlite；其中articles保存原文，labels保存分类，evidence保存逐条证据位置，lineage保存来源批次和重复关系。
使用Python或其他数据工具时，可直接读取original_recovery.jsonl.gz和new_library.jsonl.gz；两者为合格正文。review_required.jsonl.gz必须另行筛选。
baseline_archive保存上一版两份原始文件，供追溯使用，已在新版中处理，不能再次叠加计数。
taxonomy_14_83.json为议题字典，country_codes.json为国家地区代码；coverage_evidence_examples.json提供每个国家和议题的原文证据入口。
coverage.json给出真实分布；validation.json给出质量检查；manifest.json校验数据快照；package_manifest.json校验整个交接包。

三、使用须知
正文未翻译、未用模型续写。日期精度见date_precision；月份记录不能当作已知具体日期。数据库在1992年有已核验原文，但早期年份仍稀疏，不能据此声称具有连续、均衡的1992年以来新闻覆盖。
标签是带原文证据的机器候选；研究发表前仍需独立人工标注样本评估精确率和召回率。共同出现网络只表示文本关联，不证明外交合作或因果关系。
来源名称统一按网站域名分组，原显示名称保存在publisher_name_original。部分行业新闻来自机构或企业供稿，content_origin_hint和origin_attribution可用于区分。
涉及出版方版权；本包供授权合作者内部研究，不附加统一开放许可证，不得未经许可公开再分发全文。包内不包含用户API密钥、邮箱订阅列表或人员信息原文件。

四、核查与复现
先核查package_manifest.json的SHA-256，再查询SQLite的eligible=1集合。中文方法规程和SQL示例见“说明”目录。
reproduction含本次脚本、依赖和必要模块。使用独立Python 3.12环境安装requirements-fulltext-runtime.txt，再设置PYTHONPATH=src;scripts。网站生产环境不需要更换依赖。
如需重新采集，将baseline_archive内两份文件复制到reproduction/analysis/governance_handover_20261105_final；将audit中的run_config.json及source_probes*.json放入reproduction/analysis/global_expansion_20261106。运行collect_global_expansion.py可按冻结时间和检查点重跑；实时网页可能变化，重抓结果不保证与本快照相同。
原始API批次和完整运行缓存仍在采集端本地保存；交接包保留提取文本、输入指纹及抽查证据。原始缓存如需复核，可由项目方另外提供。

五、可视化准备
提供年度议题量、来源覆盖分母、国家与机构共现、议题共现及政策时间轴资料。SQL示例采用文章级计数和多标签口径。主要分析建议同时报告来源分布，并用共同来源样本进行稳健性检验。
本包未制作可视化看板。图表应从真实数据查询生成，不能用示意数据替代研究结果。
'''
 textfile=snap/'文件说明.txt';textfile.write_text(readme,encoding='utf-8');files['文件说明.txt']=textfile
 manifest={name:{'bytes':f.stat().st_size,'sha256':file_hash(f)} for name,f in files.items()}
 manifestfile=snap/'package_manifest.json';p.dump(manifestfile,{'created_at':p.stamp(),'python':platform.python_version(),'goals':goals,'files':manifest});files['package_manifest.json']=manifestfile
 with zipfile.ZipFile(package,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=5,allowZip64=True) as archive:
  for name,file in files.items():archive.write(file,name,compress_type=zipfile.ZIP_STORED if file.suffix in ('.gz','.pdf','.png') else zipfile.ZIP_DEFLATED)
 with zipfile.ZipFile(package) as archive:assert archive.testzip() is None
 receipt={'path':str(package),'bytes':package.stat().st_size,'sha256':file_hash(package),'counts':counts,'goals':goals,'snapshot':args.snapshot,'file_count':len(files),'zip_crc_check':'passed'}
 p.dump(OUT/'delivery_receipt.json',receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--snapshot',required=True);a.add_argument('--output-name',default='GREEN_global_climate_fulltexts_20261106_private.zip');args=a.parse_args()
 lock=OUT/'packaging.lock'
 try:
  with lock.open('x') as stream:stream.write(str(os.getpid()))
 except FileExistsError:raise SystemExit('Another package run holds packaging.lock; inspect it before continuing.')
 try:main(args)
 finally:lock.unlink()
