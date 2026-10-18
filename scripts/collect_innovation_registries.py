"""Bounded official-directory collection. Raw pages stay in ignored cache."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, time, os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/os.environ.get('INNOVATION_REGISTRY_CACHE','tmp/innovation-registries-'+datetime.now(timezone.utc).strftime('%Y%m%d'))
UA='GruenInnovationResearch/2.0 (+https://generationzprogrammer.github.io/climate-agent-news/innovation/)'
SOURCES={
 'nsf_programme':'https://iucrc.nsf.gov/universities/',
 'embrapii_programme':'https://embrapii.org.br/perguntas-frequentes/',
 'au_programme':'https://business.gov.au/grants-and-programs/cooperative-research-centres-projects-crcp-grants',
 'jst_programme':'https://www.jst.go.jp/pf/platform/outline.html',
 'ace_programme':'https://ace.aau.org/about-ace-impact/',
 'nsf_iucrc':'https://iucrc.nsf.gov/centers/',
 'embrapii':'https://embrapii.org.br/nossas-unidades/',
 'embrapii_export':'https://embrapii.org.br/nossas-unidades/?export_xls=1',
 'australia_crcp':'https://business.gov.au/grants-and-programs/cooperative-research-centres-projects-crcp-grants/crc-projects-selection-round-outcomes',
 'jst_coinext':'https://www.jst.go.jp/pf/platform/site.html',
 'africa_ace':'https://ace.aau.org/ace-impact-centers/',
 'africa_ace2':'https://ace2.iucea.org/industry/',
 'china_moe_first':'https://www.moe.gov.cn/srcsite/A16/s3336/201903/t20190311_372924.html',
 'china_moe_first_list':'https://www.moe.gov.cn/srcsite/A16/s3336/201903/W020190311388167817123.doc',
 'china_moe_experience':'https://www.moe.gov.cn/s78/A16/tongzhi/202004/t20200417_444200.html',
 'china_moe_second':'https://www.moe.gov.cn/srcsite/A16/s3336/202009/t20200908_486338.html',
 'china_moe_second_list':'https://www.moe.gov.cn/srcsite/A16/s3336/202009/W020200908554851200604.doc',
}

def transfer(url,target,max_bytes=6_000_000):
    # curl imposes an overall deadline as well as a connection deadline.
    result=subprocess.run(['curl','--silent','--show-error','--location','--connect-timeout','10',
      '--max-time','45','--retry','0','--max-filesize',str(max_bytes),'--user-agent',UA,
      '--output',str(target),'--write-out','%{http_code}',url],capture_output=True,text=True,timeout=50)
    status=int(result.stdout.strip()[-3:]) if result.stdout.strip()[-3:].isdigit() else 0
    if result.returncode or status!=200:
        raise RuntimeError('fetch_status_'+str(status)+'_curl_'+str(result.returncode))
    body=target.read_bytes()
    if not body.strip() or len(body)>max_bytes:raise ValueError('empty_or_oversized_response')
    return body

def collect(key,url,refresh=False):
    CACHE.mkdir(parents=True,exist_ok=True)
    suffix=Path(urlsplit(url).path).suffix
    target=CACHE/(key+(suffix if suffix in {'.doc','.pdf','.xlsx','.xls'} else '.html')); audit_path=CACHE/(key+'.audit.json')
    if target.exists() and audit_path.exists() and not refresh:
        audit=json.loads(audit_path.read_text(encoding='utf-8'))
        if audit.get('sha256')==hashlib.sha256(target.read_bytes()).hexdigest():return audit
    parsed=urlsplit(url); origin=parsed.scheme+'://'+parsed.netloc
    robot_file=CACHE/(parsed.netloc+'.robots.txt')
    robot_key=CACHE/(parsed.netloc+'.robots.audit.json')
    if not robot_key.exists() or refresh:
        try:
            raw=transfer(origin+'/robots.txt',robot_file,500_000)
            robot_audit={'status':200,'fetched_at':datetime.now(timezone.utc).isoformat()}
        except RuntimeError as exc:
            if 'fetch_status_404_' not in str(exc) and 'fetch_status_410_' not in str(exc):raise
            raw=b'User-agent: *\nDisallow:'
            robot_audit={'status':404,'fetched_at':datetime.now(timezone.utc).isoformat()}
        robot_key.write_text(json.dumps(robot_audit),encoding='utf-8')
    else:
        robot_audit=json.loads(robot_key.read_text(encoding='utf-8'))
        raw=robot_file.read_bytes() if robot_audit['status']==200 else b'User-agent: *\nDisallow:'
    robots=RobotFileParser();robots.parse(raw.decode('utf-8',errors='replace').splitlines())
    if not robots.can_fetch(UA,url):raise ValueError('robots_disallowed')
    time.sleep(1)
    body=transfer(url,target)
    audit={'source':key,'url':url,'fetched_at_utc':datetime.now(timezone.utc).isoformat(),
      'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'robots_url':origin+'/robots.txt',
      'robots_status':robot_audit['status'],'status':'ok','parser_version':'2026.10.18',
      'storage':'private cached HTML; public metadata and factual compilations only'}
    audit_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return audit

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',choices=SOURCES,action='append');parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
    for key in args.source or SOURCES:
        try:result=collect(key,SOURCES[key],args.refresh)
        except Exception as exc:result={'source':key,'status':'failed','error':str(exc)[:150]}
        print(json.dumps(result,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
