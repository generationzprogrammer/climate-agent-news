"""Upload only the generated public site; never synchronise a repository root."""
import argparse,json,mimetypes,os,re
from pathlib import Path

FORBIDDEN={'.env','.git','climate.db','subscribers.json','subscriber_list.json'}
def public_files(site):
    site=Path(site).resolve()
    if not (site/'index.html').is_file() or not (site/'data/dashboard.json').is_file():
        raise ValueError('Expected a generated public site with index.html and data/dashboard.json')
    result=[]
    for path in sorted(site.rglob('*')):
        if path.is_symlink():raise ValueError('Symlinks are not allowed in the public upload')
        if not path.is_file():continue
        rel=path.relative_to(site)
        if any(part.lower() in FORBIDDEN or (part.startswith('.') and part!='.nojekyll') for part in rel.parts):
            raise ValueError('Non-public file detected; upload cancelled')
        if re.search(r'(?:subscriber.*list|private|credentials|secret|model_usage|translation_usage)',str(rel),re.I):
            raise ValueError('Potentially private file detected; upload cancelled')
        result.append((path,rel.as_posix()))
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--site',type=Path,default=Path('site'));p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    files=public_files(a.site)
    if a.dry_run:
        print(json.dumps({'status':'dry_run','public_files':len(files),'bytes':sum(f.stat().st_size for f,_ in files)}));return
    import oss2
    from oss2.credentials import EnvironmentVariableCredentialsProvider
    # Credentials are scoped to this process by the Actions step, never files.
    os.environ['OSS_ACCESS_KEY_ID']=os.environ['ALIYUN_OSS_ACCESS_KEY_ID']
    os.environ['OSS_ACCESS_KEY_SECRET']=os.environ['ALIYUN_OSS_ACCESS_KEY_SECRET']
    bucket_name=os.environ['ALIYUN_OSS_BUCKET'];endpoint=os.environ['ALIYUN_OSS_ENDPOINT'];region=os.environ['ALIYUN_OSS_REGION']
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]',bucket_name):raise ValueError('Invalid OSS bucket name')
    if not re.fullmatch(r'https://oss-[a-z0-9-]+\.aliyuncs\.com',endpoint):raise ValueError('Expected an official HTTPS OSS endpoint')
    bucket=oss2.Bucket(oss2.ProviderAuthV4(EnvironmentVariableCredentialsProvider()),endpoint,bucket_name,region=region)
    for path,key in files:
        mime=mimetypes.guess_type(key)[0] or 'application/octet-stream'
        if key.endswith('.jsonl'):mime='application/x-ndjson'
        if key.endswith(('.html','.css','.js','.json','.csv','.jsonl')):mime+='; charset=utf-8'
        headers={'Content-Type':mime,'Cache-Control':'public, max-age=300, must-revalidate'}
        public_token=os.getenv('ALIYUN_WEB_ANALYTICS_SITE_TOKEN','').strip()
        if key.endswith('.html') and public_token:
            if not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',public_token):raise ValueError('Invalid public analytics site token')
            from bs4 import BeautifulSoup
            soup=BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser')
            beacon=soup.select_one('script[data-cf-beacon]')
            if beacon is None:
                beacon=soup.new_tag('script',src='https://static.cloudflareinsights.com/beacon.min.js');beacon['defer']='';soup.body.append(beacon)
            beacon['data-cf-beacon']=json.dumps({'token':public_token})
            bucket.put_object(key,str(soup).encode('utf-8'),headers=headers)
        else:bucket.put_object_from_file(key,str(path),headers=headers)
    # No bucket listing, ACL changes or deletion; old public assets remain.
    print(json.dumps({'status':'uploaded','files':len(files)}))

if __name__=='__main__':main()
