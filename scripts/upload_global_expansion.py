"""Resume checksum-verified small uploads to the explicitly private release only."""
import concurrent.futures as cf,hashlib,json,math,subprocess,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from export_global_expansion import file_hash
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/global_expansion_20261106';REPO='generationzprogrammer/climate-agent-news';TAG='governance-handover-20261106';ASSET='GREEN-global-climate-fulltexts-20261106.zip';CHUNK=16*1024*1024
def main():
 receipt=json.loads((OUT/'delivery_receipt.json').read_text('utf-8'));package=Path(receipt['path'])
 if not all(receipt['goals'].values()):raise RuntimeError('Delivery goals not met; no completed-release upload.')
 if package.stat().st_size!=receipt['bytes'] or file_hash(package)!=receipt['sha256']:raise RuntimeError('Local package checksum mismatch')
 auth=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,cwd=ROOT/'.publish-climate-agent-news',timeout=30)
 token=dict(x.split('=',1) for x in auth.stdout.splitlines() if '=' in x).get('password')
 if not token:raise RuntimeError('Git authentication unavailable')
 def req(method,url,payload=None,binary=False):
  data=payload if binary else json.dumps(payload).encode() if payload is not None else None
  r=urllib.request.Request(url,data=data,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'GREEN-private-dataset','Content-Type':'application/octet-stream' if binary else 'application/json'})
  with urllib.request.urlopen(r,timeout=90 if binary else 30) as response:return json.load(response)
 base='https://api.github.com/repos/'+REPO
 if req('GET',base).get('private') is not True:raise RuntimeError('Repository must remain private')
 try:release=req('GET',base+'/releases/tags/'+TAG)
 except urllib.error.HTTPError as e:
  if e.code!=404:raise
  release=req('POST',base+'/releases',{'tag_name':TAG,'target_commitish':'main','name':'全球气候治理全文与83项议题标签 · 2026-11-06','body':f"授权协作者内部研究交接。合格全文{receipt['counts']['eligible']:,}条；14大类83个二级议题；249个ISO国家地区原文提及覆盖。最早原始文章为1992年。自动标签为带证据的候选，非独立人工验证。全文不具有统一公开再分发许可。\n\n下载所有part分卷及Merge-GREEN-20261106.ps1，合并后按SHA-256校验。整包SHA-256：`{receipt['sha256']}`。",'draft':False,'prerelease':False})
 upload=release['upload_url'].split('{')[0];assets={a['name']:a for a in release.get('assets',[])}
 def put(name,data):
  digest=hashlib.sha256(data).hexdigest();old=assets.get(name)
  if old:
   if old.get('size')!=len(data) or old.get('digest')!='sha256:'+digest:raise RuntimeError('Existing remote asset mismatch; no overwrite')
   return {'name':name,'bytes':len(data),'sha256':digest,'status':'already_verified'}
  for attempt in range(2):
   try:
    if req('GET',base).get('private') is not True:raise RuntimeError('Visibility changed; stopped')
    a=req('POST',upload+'?name='+urllib.parse.quote(name),data,True)
    if a.get('state')!='uploaded' or a.get('size')!=len(data) or a.get('digest')!='sha256:'+digest:raise RuntimeError('Remote checksum not confirmed')
    return {'name':name,'bytes':len(data),'sha256':digest,'status':'uploaded','url':a['browser_download_url']}
   except (urllib.error.URLError,TimeoutError) as e:
    if isinstance(e,urllib.error.HTTPError) and e.code not in (408,409,422,429,500,502,503,504):raise
    latest=req('GET',base+'/releases/'+str(release['id']))
    old=next((x for x in latest.get('assets',[]) if x['name']==name),None)
    if old and old.get('state')=='uploaded' and old.get('digest')=='sha256:'+digest:return {'name':name,'bytes':len(data),'sha256':digest,'status':'verified_after_retry'}
    if old:raise RuntimeError('Incomplete remote asset needs inspection; no deletion')
    if attempt:raise
    time.sleep(3)
 total=math.ceil(receipt['bytes']/CHUNK);results=[]
 def part(i):
  with package.open('rb') as stream:stream.seek(i*CHUNK);data=stream.read(CHUNK)
  return put(ASSET+f'.part{i+1:03d}',data)
 with cf.ThreadPoolExecutor(max_workers=3) as pool:
  for result in pool.map(part,range(total)):
   results.append(result);print(json.dumps({'part':result['name'],'status':result['status'],'completed':len(results),'total':total}),flush=True)
   (OUT/'upload_parts_receipt.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 helper=f'''$ErrorActionPreference = 'Stop'
$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$output = Join-Path $folder '{ASSET}'
if (Test-Path -LiteralPath $output) {{ throw 'Output already exists; verify it before repeating.' }}
$parts = Get-ChildItem -LiteralPath $folder -Filter '{ASSET}.part*' | Sort-Object Name
if ($parts.Count -ne {total}) {{ throw 'Missing parts: download all {total} parts from the private release.' }}
$outStream = [System.IO.File]::Create($output)
try {{ foreach ($part in $parts) {{ $inStream=[System.IO.File]::OpenRead($part.FullName); try {{ $inStream.CopyTo($outStream) }} finally {{ $inStream.Dispose() }} }} }} finally {{ $outStream.Dispose() }}
if ((Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant() -ne '{receipt['sha256']}') {{ throw 'Checksum mismatch. Keep the parts and inspect the download.' }}
Write-Output 'Verified. The ZIP is ready to open.'
'''
 results.append(put('Merge-GREEN-20261106.ps1',helper.encode('utf-8-sig')))
 results.append(put(ASSET+'.sha256',(receipt['sha256']+'  '+ASSET+'\n').encode()))
 stable_parts=[{k:r[k] for k in ('name','bytes','sha256')} for r in results[:total]]
 results.append(put('parts-manifest.json',json.dumps({'file':ASSET,'sha256':receipt['sha256'],'bytes':receipt['bytes'],'parts':stable_parts},ensure_ascii=False,indent=2).encode()))
 if req('GET',base).get('private') is not True:raise RuntimeError('Visibility changed after upload')
 final={'status':'verified','private':True,'release_url':release['html_url'],'parts':total,'bytes':receipt['bytes'],'sha256':receipt['sha256']}
 (OUT/'upload_receipt.json').write_text(json.dumps(final,indent=2),encoding='utf-8');print(json.dumps(final),flush=True)
if __name__=='__main__':
 try:main()
 except urllib.error.HTTPError as e:print(json.dumps({'status':'failed','http_status':e.code}));raise SystemExit(1)
 except Exception as e:print(json.dumps({'status':'failed','error':type(e).__name__,'detail':str(e) if isinstance(e,RuntimeError) else 'Credentials are not logged'}));raise SystemExit(1)
