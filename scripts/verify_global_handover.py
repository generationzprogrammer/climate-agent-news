"""Verify every archived file and run tests using only the packaged code."""
import hashlib,json,os,subprocess,sys,zipfile
from pathlib import Path,PurePosixPath
import fulltext_pilot as p

out=p.ROOT/'analysis/global_expansion_20261106'
receipt=json.loads((out/'delivery_receipt.json').read_text('utf-8'))
target=out/('packaged_code_smoke_test_'+receipt['sha256'][:12])
if target.exists():raise SystemExit('Smoke-test directory already exists; inspect the previous result.')
target.mkdir()
with zipfile.ZipFile(receipt['path']) as archive:
    manifest=json.loads(archive.read('package_manifest.json'))['files']
    for name,expected in manifest.items():
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:raise RuntimeError('Unsafe archive path')
        h=hashlib.sha256();size=0
        with archive.open(name) as stream:
            for chunk in iter(lambda:stream.read(2*1024*1024),b''):
                h.update(chunk);size+=len(chunk)
        assert size==expected['bytes'] and h.hexdigest()==expected['sha256'],name
        if name.startswith('reproduction/'):archive.extract(name,target)
work=target/'reproduction'
env=dict(os.environ,PYTHONPATH=os.pathsep.join(['src','scripts']),PYTHONIOENCODING='utf-8')
run=subprocess.run([sys.executable,'scripts/run_expansion_tests.py','--output',str(out/'test_results_packaged.json')],cwd=work,env=env,timeout=120,check=True)
result={'verified_at':p.stamp(),'archive_files_sha256_verified':len(manifest),'packaged_code_tests':'passed','package_sha256':receipt['sha256']}
p.dump(out/'handover_verification.json',result)
print(json.dumps(result))
