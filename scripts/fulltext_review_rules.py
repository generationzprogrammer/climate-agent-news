"""Conservative source-backed adjudication, never generated replacement prose."""
import re
from urllib.parse import urlsplit
from climate_agent.publisher_recovery import identity, normalized

VERSION='source-tail-review-20261104-v3'
END=('.', '!', '?', '"', '”', '’', ')', ']', '。', '！', '？', ':', '）', '」', '』', '»', '■')

def title_identity(expected, actual, source, url):
    direct=identity(expected,actual,publisher=source)
    if direct: return {**direct,'basis':'strict_original_title_rule'}
    host=(urlsplit(url).hostname or '').removeprefix('www.')
    aliases=('新华网','新华社','Xinhua','Xinhua English') if host in ('news.cn','english.news.cn') else ()
    if host=='environewsnigeria.com':
        aliases=('EnviroNews Nigeria','EnviroNews - latest environment news, climate change, renewable energy')
    def clean(s):
        for name in aliases:
            s=re.sub(r'\s*[-_|–—]\s*'+re.escape(name)+r'\s*$','',s,flags=re.I)
        return re.sub(r"(?<=\w)['’](?=\w)",'',s)
    a,c=clean(expected),clean(actual)
    if normalized(a)==normalized(c) and normalized(a):
        return {'title_exact':True,'basis':'punctuation_or_verified_publisher_suffix','publisher_domain':host,'version':VERSION}
    return None

def terminal_kind(text):
    value=text.strip()
    if re.search(r'(?:doi\s*:\s*|https?://doi\.org/)10\.\d{4,9}/\S+\s*$',value,re.I): return 'bibliographic_reference'
    if re.match(r'^(?:Reporting credit:|Maps by |(?:Inside Climate News )?journalist .{1,90} contributed reporting\b|Traducci[oó]n al espa[nñ]ol:|Translated by |Traducido con una herramienta)',value,re.I): return 'reporting_or_translation_credit'
    if re.match(r'^(?:文字记者|记者|编辑|责任编辑|海报设计|新华社记者)[：:]',value) or re.fullmatch(r'【纠错】\s*【责任编辑[:：].{1,30}】',value): return 'editorial_credit'
    if value.lower() in ('citation:','citations:','references','references:','article information'): return 'bibliography_heading'
    return None

def review_terminal(doc):
    """Only resolve a tail flag when an intact prose ending precedes metadata."""
    flags=doc.get('completeness_flags') or []
    if 'last_block_needs_review' not in flags: return None
    if doc.get('extraction_method')!='semantic_article_dom' or doc.get('source_block_coverage')!=1 or not doc.get('first_block_present') or not doc.get('last_block_present'): return None
    blocks=[s.strip() for s in doc['source_text'].split('\n\n') if s.strip()]
    if len(blocks)<3: return None
    kinds=[]
    for block in reversed(blocks[-8:]):
        kind=terminal_kind(block)
        if kind:
            kinds.append(kind); continue
        if kinds and len(block)>=80 and block.endswith(END):
            return {'version':VERSION,'basis':'terminal_editorial_metadata_after_complete_prose','terminal_kinds':kinds,'preceding_prose_characters':len(block),'source_dom_coverage':1}
        return None
    return None
