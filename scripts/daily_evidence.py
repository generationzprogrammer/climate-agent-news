"""Bounded publisher-side recovery and source-faithful numeric normalization."""
import collections, re, time, unicodedata
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from climate_agent.publisher_recovery import discover_publisher
from climate_agent.research_translation import numeric_values, target_numeric_values

MONTHS='January February March April May June July August September October November December'.split()

def numbers(text):
    text=unicodedata.normalize('NFKC',text)
    values=target_numeric_values(text)
    # Conference identifiers and written English months legitimately become Chinese numerals.
    from decimal import Decimal
    values.update(Decimal(n) for n in re.findall(r'\b(?:COP|CMA|CMP)\s*(\d+)\b',text,re.I))
    for i,m in enumerate(MONTHS,1):
        if re.search(r'\b(?:'+m+'|'+m[:3]+r')\.?\s+\d',text,re.I): values.add(Decimal(i))
    return values

def nonprose(text):
    text=text.strip()
    return bool(re.fullmatch(r'https?://\S+|\[?\d+\]?|(?:©\s*)?\d{4}|(?:By\s+)?[A-Z][a-z]+(?:[ -][A-Z][a-z]+){1,3}',text))

class PublisherRecovery:
    def __init__(self,fetcher,deadline):
        self.fetcher=fetcher;self.deadline=deadline;self.cache={};self.requests=0
    def resolve(self,title,meta,timing):
        home=meta.get('publisher_homepage')
        if not home:return None
        count=0
        def read(url):
            nonlocal count
            if url in self.cache:return self.cache[url]
            if count>=10 or self.requests>=120 or time.monotonic()>self.deadline:return b''
            count+=1;self.requests+=1
            try:
                _,_,raw,_=self.fetcher.get(url,timing)
            except Exception:raw=b''
            self.cache[url]=raw
            return raw
        row={'title':title,'source':meta.get('publisher_name') or meta.get('source_name'),
             'date':meta.get('published_at_utc') or meta.get('published_at'),'publisher_homepage':home}
        hits=discover_publisher(row,read,sitemap_limit=2)
        return hits[0]['publisher_url'] if hits else None

def evidence_blocks(text):
    """IDs, not model-retyped quotations; preserve exact evidence in the output."""
    paragraphs=[x.strip() for x in re.split(r'\n\s*\n|(?<=[.!?。！？])\s+',text) if x.strip()]
    blocks=[]
    for p in paragraphs:
        for start in range(0,len(p),1400):
            blocks.append({'id':'E'+str(len(blocks)+1),'text':p[start:start+1400]})
    return blocks
