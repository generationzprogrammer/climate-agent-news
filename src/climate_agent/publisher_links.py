"""Find publisher links in public homepages and their advertised RSS feeds.

No search API, private Google decoder or generated URL is used. Candidates must
be links actually present in the publisher's page, then pass title verification
when the article is fetched. This is intentionally a bounded best-effort path.
"""
from functools import lru_cache
from html.parser import HTMLParser
import ipaddress
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlsplit

from .article_content import USER_AGENT, _robots_allows
from .collector import parse_feed


def public_url(url):
    p=urlsplit(url)
    host=p.hostname or ''
    if p.scheme not in {'http','https'} or not host or p.username or p.password:return False
    if host=='localhost' or host.endswith(('.local','.internal')):return False
    try:return ipaddress.ip_address(host).is_global
    except ValueError:return '.' in host


@lru_cache(maxsize=48)
def read_public(url):
    if not public_url(url):return b''
    p=urlsplit(url)
    if not _robots_allows(p.scheme,p.netloc,url):return b''
    request=urllib.request.Request(url,headers={'User-Agent':USER_AGENT})
    try:
        with urllib.request.urlopen(request,timeout=8) as response:
            if not public_url(response.geturl()):return b''
            data=response.read(1_000_001)
            return data if len(data)<=1_000_000 else b''
    except (OSError,ValueError):return b''


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links=[];self.feeds=[];self.href=None;self.parts=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='link' and a.get('type') in {'application/rss+xml','application/atom+xml'} and a.get('href'):
            self.feeds.append(a['href'])
        if tag=='a':
            self.href=a.get('href');self.parts=[a.get('title') or '',a.get('aria-label') or '']
    def handle_data(self,text):
        if self.href:self.parts.append(text)
    def handle_endtag(self,tag):
        if tag=='a' and self.href:
            self.links.append((' '.join(self.parts),self.href));self.href=None;self.parts=[]


def resolve_publisher(title,homepage):
    from .research import words
    if not public_url(homepage):return None
    raw=read_public(homepage)
    if not raw:return None
    parser=Links();parser.feed(raw.decode('utf-8',errors='replace'))
    candidates=[(text,urljoin(homepage,href)) for text,href in parser.links]
    # Only follow RSS URLs advertised by the publisher, never guess feed paths.
    for href in list(dict.fromkeys(parser.feeds))[:2]:
        feed=read_public(urljoin(homepage,href))
        if not feed:continue
        try:candidates.extend((r.title,r.canonical_url) for r in parse_feed(feed,'publisher'))
        except (ET.ParseError,ValueError,TypeError):
            # Malformed publisher XML must not interrupt ordinary collection.
            continue
    expected=words(title)
    if len(expected)<4:return None
    ranked=[]
    for text,url in candidates:
        actual=words(text);score=len(actual&expected)/max(1,len(actual|expected))
        if len(actual&expected)>=4 and score>=.60 and public_url(url):ranked.append((score,url))
    return max(ranked)[1] if ranked else None
