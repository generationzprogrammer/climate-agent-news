"""Authenticated encrypted checkpoint for PUBLIC GitHub Actions repositories.

Only ciphertext is uploaded. Refuse corrupt/unavailable prior state instead of
silently losing the archive. Server deployments use their persistent disk directly.
"""
import argparse, base64, hashlib, io, json, os, sqlite3, sys, tempfile, urllib.error, urllib.request, zipfile
from contextlib import closing
from pathlib import Path
from cryptography.fernet import Fernet

PREFIX='green-daily-fulltext-state-'

def cipher():
    secret=os.environ.get('DAILY_FULLTEXT_STORAGE_KEY','')
    if len(secret)<32: raise ValueError('storage_key_requires_at_least_32_characters')
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))

def seal(root, dest):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        dbpath=root/'daily_fulltext.sqlite'
        if not dbpath.exists(): raise ValueError('state_database_missing')
        with tempfile.TemporaryDirectory() as temp:
            backup=Path(temp)/'daily_fulltext.sqlite'
            with closing(sqlite3.connect(dbpath)) as src, closing(sqlite3.connect(backup)) as out: src.backup(out)
            z.write(backup,'daily_fulltext.sqlite')
        for p in sorted(root.glob('*.json')):
            if p.name!='input.json': z.write(p,p.name)
    dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_suffix('.tmp');tmp.write_bytes(cipher().encrypt(stream.getvalue()));tmp.replace(dest)

def unseal(source, root):
    data=cipher().decrypt(source.read_bytes())
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if z.testzip(): raise ValueError('checkpoint_crc_failed')
        for n in z.namelist():
            if Path(n).name!=n or n not in ['daily_fulltext.sqlite'] and not n.endswith('.json'):
                raise ValueError('unsafe_checkpoint_member')
        if 'daily_fulltext.sqlite' not in z.namelist(): raise ValueError('checkpoint_database_missing')
        root.mkdir(parents=True,exist_ok=True)
        # Restore before opening any SQLite connections.
        for n in z.namelist():
            dest=root/n;tmp=dest.with_suffix(dest.suffix+'.tmp');tmp.write_bytes(z.read(n));tmp.replace(dest)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

def github_json(url):
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],
        'Accept':'application/vnd.github+json','User-Agent':'GREEN-Daily-Fulltext/2.0'})
    with urllib.request.urlopen(req,timeout=30) as response: return json.load(response)

def restore_latest(root):
    repo=os.environ['GITHUB_REPOSITORY'];base='https://api.github.com/repos/'+repo
    rows=github_json(base+'/actions/artifacts?per_page=100')['artifacts']
    previous=[r for r in rows if r['name'].startswith(PREFIX) and not r.get('expired')]
    if not previous:
        # Do not reset a previously used archive after retention expiry.
        runs=github_json(base+'/actions/workflows/daily-fulltext.yml/runs?per_page=10').get('workflow_runs',[])
        current=str(os.getenv('GITHUB_RUN_ID',''))
        past=[r for r in runs if str(r['id'])!=current and r.get('conclusion') in ['success','failure']]
        if past and os.getenv('DAILY_FULLTEXT_ALLOW_EMPTY_STATE')!='true':
            raise ValueError('checkpoint_missing_manual_restore_required')
        print('No previous checkpoint; initializing first run.');return
    artifact=max(previous,key=lambda r:r['created_at'])
    req=urllib.request.Request(artifact['archive_download_url'],headers={
        'Authorization':'Bearer '+os.environ['GH_TOKEN'],'User-Agent':'GREEN-Daily-Fulltext/2.0'})
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=30) as resp: payload=resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code!=302: raise
        # Signed storage download MUST NOT receive the GitHub bearer token.
        url=exc.headers['Location']
        if not url.startswith('https://'): raise ValueError('unsafe_artifact_redirect')
        with urllib.request.urlopen(url,timeout=90) as resp: payload=resp.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as z, tempfile.TemporaryDirectory() as t:
        members=[n for n in z.namelist() if n.endswith('.fulltext.enc')]
        if len(members)!=1: raise ValueError('checkpoint_member_count')
        p=Path(t)/'state.fulltext.enc';p.write_bytes(z.read(members[0]));unseal(p,root)
    print('Restored encrypted checkpoint; artifact_id='+str(artifact['id']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['seal','unseal','restore']);p.add_argument('--root',type=Path,default=Path('data/private_daily_fulltext'));p.add_argument('--file',type=Path,default=Path('.daily-fulltext-state/state.fulltext.enc'));a=p.parse_args()
    try:
        if a.action=='seal':seal(a.root,a.file)
        elif a.action=='unseal':unseal(a.file,a.root)
        else:restore_latest(a.root)
    except Exception as exc:
        # HTTP failures can contain signed URLs: never print exception text.
        print('Checkpoint operation failed: '+type(exc).__name__,file=sys.stderr);sys.exit(1)
