"""Bounded, cached public evidence requests; no credentials or private fields."""
import argparse
import gzip
import hashlib
import io
import json
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'tmp/us-innovation'
UA = 'GruenOpenInnovation/1.2 (public project metadata research)'


def fetch(url, *, maximum=20_000_000):
    parts = urlparse(url)
    if parts.scheme != 'https' or parts.hostname not in {'arpa-e.energy.gov', 'api.nsf.gov', 'www.nsf.gov'}:
        raise ValueError('URL outside official source allowlist')
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()
    dest = CACHE / (key + '.response')
    audit_file = CACHE / (key + '.audit.json')
    if dest.exists() and audit_file.exists():
        return dest
    if parts.path != '/robots.txt':
        robotfile = fetch(parts.scheme + '://' + parts.netloc + '/robots.txt', maximum=200_000)
        robots = urllib.robotparser.RobotFileParser()
        robots.parse(robotfile.read_text(encoding='utf-8', errors='replace').splitlines())
        if not robots.can_fetch(UA, url):
            raise PermissionError('Disallowed by robots.txt')
    time.sleep(1)
    request = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(maximum + 1)
        if len(data) > maximum or time.monotonic() - started > 90:
            raise ValueError('Response exceeds request budget')
        if response.headers.get('Content-Encoding') == 'gzip':
            data = gzip.GzipFile(fileobj=io.BytesIO(data)).read(maximum + 1)
            if len(data) > maximum:
                raise ValueError('Expanded response exceeds size budget')
        audit = {'url': url, 'final_url': response.url, 'http_status': response.status,
                 'content_type': response.headers.get('Content-Type'), 'bytes': len(data),
                 'sha256': hashlib.sha256(data).hexdigest(),
                 'fetched_at_utc': datetime.now(timezone.utc).isoformat(),
                 'timeout_seconds': 30, 'retry_limit': 0, 'minimum_interval_seconds': 1,
                 'cache_policy': 'manual refresh only', 'parser_version': 'us-official-1.0'}
    dest.write_bytes(data)
    audit_file.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
    return dest


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('url')
    args = cli.parse_args()
    path = fetch(args.url)
    print(json.dumps({'cache_file': str(path), 'bytes': path.stat().st_size}))
