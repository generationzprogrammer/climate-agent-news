"""Recover historical publisher URLs through documented public discovery routes.

All network access is injected: the caller owns robots, DNS safety, rate limits,
timeouts, caching and source policy. No Google RPC, guessed article URL, model or
paywall workaround. A URL candidate is not a fulltext success.
"""
from __future__ import annotations

import difflib
import gzip
import html
import io
import ipaddress
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

VERSION = "publisher-recovery-1.0"
STOP = set("a an the of for to in on and or as with by from is are its this that how what why new at into over under".split())


def public_homepage(value):
    """Preserve a public source locator, excluding credentials/query secrets."""
    try:
        p = urlsplit(value or "")
        h = p.hostname or ""
        if p.scheme not in ("http", "https") or not h or p.username or p.password or p.port not in (None,80,443):
            return None
        if h == "localhost" or h.endswith((".local", ".internal")) or "." not in h:
            return None
        try:
            if not ipaddress.ip_address(h).is_global:
                return None
        except ValueError:
            pass
        return urlunsplit((p.scheme,p.netloc,p.path or "/","",""))
    except (ValueError,TypeError):
        return None


def title_text(value, publisher=None):
    value = html.unescape(value) if isinstance(value,str) else ""
    if '<' in value and '>' in value:
        value = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    if publisher:
        value = re.sub(r"\s+[|–-]\s*" + re.escape(publisher) + r"\s*$", "", value, flags=re.I)
    # Strip an RSS citation suffix, not an ordinary internal headline dash.
    value = re.sub(r"\s+-\s+[A-Z][\w .'-]{1,35}\s+-\s+(?:19|20)\d{2}\s+-\s+.*$", "", value)
    return value.strip()


def normalized(value):
    return " ".join(re.findall(r"[\w]+", unicodedata.normalize("NFKC", value).casefold()))


def tokens(value):
    return [t for t in normalized(value).split() if t not in STOP]


def same_host(url, homepage):
    def hostname(value):
        return (urlsplit(value).hostname or "").lower().removeprefix("www.")
    p = urlsplit(url)
    return p.scheme in ("http", "https") and not p.username and not p.password and hostname(url) == hostname(homepage)


def identity(expected_title, candidate_title, *, publisher=None, expected_date=None, candidate_date=None):
    expected = normalized(title_text(expected_title, publisher))
    candidate = normalized(title_text(candidate_title, publisher))
    if not expected or not candidate:
        return None
    e, c = set(tokens(expected)), set(tokens(candidate))
    exact = expected == candidate
    jac = len(e & c) / max(1, len(e | c))
    ratio = difflib.SequenceMatcher(None, expected, candidate).ratio()
    # Year, amount and target numbers distinguish otherwise similar headlines.
    if set(re.findall(r"\d+", expected)) != set(re.findall(r"\d+", candidate)):
        return None
    if not exact and (len(e & c) < 5 or jac < .88 or ratio < .88):
        return None
    date_status = "source_date_missing"
    if expected_date and candidate_date:
        try:
            days = abs((datetime.fromisoformat(str(expected_date)[:10]) - datetime.fromisoformat(str(candidate_date)[:10])).days)
        except ValueError:
            date_status = "unparsed_date"
        else:
            if days > 31:
                return None
            date_status = "within_31_days_of_rss_date"
    return {"title_exact": exact, "title_jaccard": round(jac, 5), "title_sequence_ratio": round(ratio, 5), "date_check": date_status}


def search_terms(title, publisher=None):
    cleaned = title_text(title, publisher)
    words = list(dict.fromkeys(tokens(cleaned)))
    # WordPress AND search is more reliable with a short, distinctive phrase.
    return list(dict.fromkeys([" ".join(words[:8]), " ".join(sorted(words, key=len, reverse=True)[:4])]))


def wordpress_candidates(row, endpoint, read):
    if not same_host(endpoint, row.get("publisher_homepage") or endpoint):
        return []
    for query in search_terms(row["title"], row.get("source"))[:2]:
        if not query:
            continue
        url = endpoint + ("&" if "?" in endpoint else "?") + urlencode({"search": query, "per_page": 10, "_fields": "id,link,title,date,date_gmt"})
        raw = read(url)
        if not raw:
            continue
        try:
            posts = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(posts, list):
            continue
        hits = []
        for p in posts:
            if not isinstance(p, dict) or not same_host(p.get("link", ""), endpoint):
                continue
            title = (p.get("title") or {}).get("rendered", "")
            date = p.get("date_gmt") or p.get("date")
            match = identity(row["title"], title, publisher=row.get("source"), expected_date=row.get("date"), candidate_date=date)
            if match:
                hits.append({"publisher_url": p["link"], "source_page_title": title_text(title), "source_date": date,
                             "route": "publisher_wordpress_search", "discovery_url": url, "api_endpoint": endpoint,
                             "archive_post_id": p.get("id"), "identity": match})
        if hits:
            return hits
    return []


def wordpress_site_candidates(row, endpoint, read):
    """Public all-post-type search: newsletters/resources may not be 'posts'."""
    if not endpoint.rstrip('/').endswith('/wp/v2/posts'):
        return []
    root = endpoint.rstrip('/')[:-len('/posts')] + '/search'
    for query in search_terms(row['title'],row.get('source'))[:2]:
        search_url = root+'?'+urlencode({'search':query,'per_page':10,'_fields':'id,title,url,subtype'})
        try:
            rows=json.loads(read(search_url))
        except (ValueError,TypeError):
            continue
        if not isinstance(rows,list):
            continue
        hits=[]
        for p in rows:
            if not isinstance(p,dict) or not same_host(p.get('url',''),endpoint):
                continue
            if identity(row['title'],p.get('title',''),publisher=row.get('source')):
                checked=page_identity(row,p['url'],read(p['url']))
                if checked:
                    hits.append({**checked,'route':'publisher_wordpress_all_types_search','discovery_url':search_url,'post_type':p.get('subtype')})
        if hits:
            return hits
    return []


def page_identity(row, url, raw):
    soup = BeautifulSoup(raw, "lxml")
    heads = [soup.find('meta',property='og:title')] + soup.select('article h1, main h1') + [soup.title] + soup.find_all('h1')[:3]
    titles=[x.get('content') or x.get_text(' ',strip=True) for x in heads if x is not None]
    title=next((x for x in titles if identity(row['title'],x,publisher=row.get('source'))),None)
    if title is None:
        return None
    date_node = soup.find("meta", property="article:published_time") or soup.find("time", datetime=True)
    date = (date_node.get("content") or date_node.get("datetime")) if date_node else None
    if not date:
        for script in soup.find_all('script',type='application/ld+json'):
            try:
                structured=json.loads(script.get_text())
            except ValueError:
                continue
            pending=structured if isinstance(structured,list) else [structured]
            while pending:
                item=pending.pop()
                if not isinstance(item,dict):
                    continue
                if item.get('datePublished'):
                    date=item['datePublished']
                    break
                graph=item.get('@graph')
                if isinstance(graph,list):pending.extend(graph)
            if date:
                break
    match = identity(row["title"], title, publisher=row.get("source"), expected_date=row.get("date"), candidate_date=date)
    if not match:
        return None
    canonical = soup.find("link", rel="canonical")
    canonical_url = urljoin(url, canonical.get("href", "")) if canonical else url
    if not same_host(canonical_url, url):
        return None
    return {"publisher_url": canonical_url, "source_page_title": title, "source_date": date, "identity": match}


def discover_publisher(row, read, *, endpoint=None, sitemap_limit=3):
    """Bounded official search/sitemap discovery, yielding verified URL metadata."""
    home = row.get("publisher_homepage")
    if not home or (urlsplit(home).hostname or "").endswith("google.com"):
        return []
    if endpoint:
        hits = wordpress_candidates(row, endpoint, read)
        if hits:
            return hits
        hits = wordpress_site_candidates(row,endpoint,read)
        if hits:
            return hits
    raw = read(home)
    if not raw:
        return []
    soup = BeautifulSoup(raw, "lxml")
    for a in soup.find_all('a',href=True):
        u=urljoin(home,a['href'])
        if same_host(u,home) and identity(row['title'],a.get_text(' ',strip=True),publisher=row.get('source')):
            checked=page_identity(row,u,read(u))
            if checked:
                return [{**checked,'route':'publisher_homepage_anchor','discovery_url':home}]
    api_link = soup.find("link", rel="https://api.w.org/")
    if api_link and api_link.get("href"):
        api_root = urljoin(home, api_link["href"])
        if same_host(api_root, home):
            endpoint = api_root.rstrip("/") + "/wp/v2/posts"
            hits = wordpress_candidates(row, endpoint, read)
            if hits:
                return hits
            hits = wordpress_site_candidates(row,endpoint,read)
            if hits:
                return hits
    # Follow only GET search forms actually advertised by the publisher.
    for form in soup.find_all("form"):
        if str(form.get("method", "get")).lower() != "get":
            continue
        inp = form.find("input", attrs={"type": "search"}) or next((x for x in form.find_all("input") if x.get("name") in ("s", "q", "query", "search")), None)
        if inp is None or not inp.get("name"):
            continue
        action = urljoin(home, form.get("action") or home)
        if not same_host(action, home):
            continue
        params = {x["name"]: x.get("value", "") for x in form.find_all("input", type="hidden") if x.get("name") and not re.search(r"nonce|token|key|auth|pass", x["name"], re.I)}
        params[inp["name"]] = search_terms(row["title"], row.get("source"))[0]
        search_url = action + ("&" if "?" in action else "?") + urlencode(params)
        content = read(search_url)
        if content:
            result_soup = BeautifulSoup(content, "lxml")
            for a in result_soup.find_all("a", href=True):
                u = urljoin(search_url, a["href"])
                if same_host(u, home) and identity(row["title"], a.get_text(" ", strip=True), publisher=row.get("source")):
                    checked = page_identity(row, u, read(u))
                    if checked:
                        return [{**checked, "route": "publisher_advertised_search", "discovery_url": search_url}]
        break
    # Only sitemaps declared in robots/homepage; never manufacture an article slug.
    if sitemap_limit <= 0:
        return []
    origin = urlunsplit((*urlsplit(home)[:2], "/robots.txt", "", ""))
    robots = read(origin).decode("utf-8", "replace")
    sitemaps = re.findall(r"(?im)^Sitemap:\s*(https?://\S+)", robots)
    sitemaps += [urljoin(home, x.get("href", "")) for x in soup.find_all("link", rel="sitemap")]
    seen = set()
    budget = sitemap_limit
    expected = set(tokens(title_text(row["title"], row.get("source"))))
    while sitemaps and budget > 0:
        sm = sitemaps.pop(0)
        if sm in seen or not same_host(sm, home):
            continue
        seen.add(sm)
        budget -= 1
        data = read(sm)
        try:
            if data[:2] == b"\x1f\x8b":
                with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
                    data = f.read(8*1024*1024+1)
                if len(data) > 8*1024*1024:
                    continue
            tree = ET.fromstring(data)
        except (ET.ParseError, OSError, EOFError):
            continue
        if tree.tag.endswith("sitemapindex"):
            children = [x.text for x in tree.iter() if x.tag.endswith("loc") and x.text]
            # Timestamped shards that match the target year are tried first.
            year = str(row.get("date") or "")[:4]
            children.sort(key=lambda u: (bool(year and year in u), "post" in u), reverse=True)
            sitemaps = children[:budget] + sitemaps
            continue
        candidates = []
        for loc in tree.iter():
            if not loc.tag.endswith("loc") or not loc.text or not same_host(loc.text, home):
                continue
            actual = set(tokens(urlsplit(loc.text).path.replace("-", " ")))
            score = len(expected & actual) / max(1, len(expected | actual))
            if score >= .45 and len(expected & actual) >= min(4, len(expected)):
                candidates.append((score, loc.text))
        for _, u in sorted(candidates, reverse=True)[:2]:
            checked = page_identity(row, u, read(u))
            if checked:
                return [{**checked, "route": "publisher_declared_sitemap", "discovery_url": sm}]
    return []


EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def scholarly_candidates(row, read):
    """Metadata only. Fulltext is read separately only for declared OA deposits."""
    title = title_text(row["title"], row.get("source"))
    q = 'TITLE:"' + title.replace('"', " ") + '"'
    query = EPMC + "/search?" + urlencode({"query": q, "format": "json", "pageSize": 5, "resultType": "core"})
    raw = read(query)
    try:
        results = json.loads(raw).get("resultList", {}).get("result", [])
    except (ValueError, AttributeError):
        return []
    out = []
    for r in results:
        match = identity(title, r.get("title", ""), expected_date=row.get("date"), candidate_date=r.get("firstPublicationDate"))
        if not match:
            continue
        pmcid, doi = r.get("pmcid"), r.get("doi")
        out.append({"publisher_url": "https://doi.org/" + doi if doi else None, "source_page_title": r["title"],
                    "source_date": r.get("firstPublicationDate"), "doi": doi, "pmcid": pmcid,
                    "repository_open_access": r.get("isOpenAccess") == "Y", "route": "europe_pmc_title_search",
                    "discovery_url": query, "identity": match,
                    "fulltext_xml_url": EPMC + "/" + pmcid + "/fullTextXML" if pmcid and r.get("isOpenAccess") == "Y" else None})
    return out


def jats_text(raw, expected_title):
    """Licensed OA repository body: preserve paragraphs, sections and tables."""
    root = ET.fromstring(raw)
    title = root.findtext(".//article-title") or ""
    if not identity(expected_title, title):
        raise ValueError("repository_title_mismatch")
    license_node = root.find(".//permissions/license")
    if license_node is None:
        raise ValueError("repository_license_missing")
    license_text = " ".join(license_node.itertext()).strip()
    license_urls = [v for k, v in license_node.attrib.items() if k.endswith("href")]
    license_urls += [v for el in license_node.iter() for k, v in el.attrib.items() if k.endswith("href")]
    if not any("creativecommons.org/licenses/" in x for x in license_urls) and not re.search(r"Creative Commons|open.access", license_text, re.I):
        raise ValueError("repository_license_not_recognized")
    body = root.find("body")
    if body is None:
        raise ValueError("repository_body_missing")
    blocks = []
    def walk(el):
        if el.tag == "table":
            for row in el.iter("tr"):
                cells=[" ".join("".join(x.itertext()).split()) for x in row if x.tag in ("td","th")]
                if cells:
                    blocks.append(" | ".join(cells))
        elif el.tag in ("p", "title", "caption", "ref"):
            text = " ".join("".join(el.itertext()).split())
            if text:
                blocks.append(text)
        else:
            for child in el:
                walk(child)
    for abstract in root.findall(".//article-meta/abstract"):
        walk(abstract)
    walk(body)
    back = root.find("back")
    if back is not None:
        walk(back)
    text = "\n\n".join(blocks)
    if len(text) < 500:
        raise ValueError("repository_body_too_short")
    return text, {"source_page_title": title, "license_text": license_text, "license_urls": sorted(set(license_urls)),
                  "extraction_method": "licensed_repository_jats", "paragraphs": len(blocks), "status": "candidate_complete",
                  "completeness_flags": [], "title_match": True, "completeness_basis": "JATS body present; no independent word-level human gold standard"}
