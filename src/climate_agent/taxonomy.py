from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COUNTRY_CODES_PATH = ROOT / "config" / "country_codes.json"

ORGANIZATION_GROUPS = (
    {
        "group": "联合国与气候机制",
        "items": (
            ("UN", "联合国", (r"\bunited nations\b", r"联合国")),
            ("UNFCCC", "联合国气候变化框架公约", (r"\bunfccc\b", r"联合国气候变化框架公约")),
            ("COP", "联合国气候变化大会", (r"\bcop\s*-?\s*\d{1,2}\b", r"联合国气候(?:变化)?大会", r"conference of the parties")),
        ),
    },
    {
        "group": "全球经济与政策协调",
        "items": (
            ("G20", "二十国集团", (r"\bg\s*-?\s*20\b", r"group of twenty", r"二十国集团")),
            ("G7", "七国集团", (r"\bg\s*-?\s*7\b", r"group of seven", r"七国集团")),
            ("BRICS", "金砖国家", (r"\bbrics\+?\b", r"金砖国家", r"金砖合作")),
            ("OECD", "经济合作与发展组织", (r"\boecd\b", r"经济合作与发展组织")),
        ),
    },
    {
        "group": "区域合作机制",
        "items": (
            ("BRI", "一带一路", (r"\bbelt and road initiative\b", r"\bbri\b", r"一带一路", r"丝绸之路经济带")),
            ("APEC", "亚太经济合作组织", (r"\bapec\b", r"亚太经济合作组织")),
            ("ASEAN", "东南亚国家联盟", (r"\basean\b", r"东南亚国家联盟", r"东盟")),
            ("SCO", "上海合作组织", (r"\bshanghai cooperation organi[sz]ation\b", r"\bsco\b", r"上海合作组织", r"上合组织")),
            ("EU", "欧洲联盟", (r"\beuropean union\b", r"欧盟")),
            ("AU", "非洲联盟", (r"\bafrican union\b", r"非洲联盟", r"非盟")),
            ("PIF", "太平洋岛国论坛", (r"\bpacific islands forum\b", r"\bsouth pacific forum\b", r"太平洋岛国论坛", r"南太平洋论坛")),
            ("CPTPP", "全面与进步跨太平洋伙伴关系协定", (r"\bcptpp\b", r"全面与进步跨太平洋伙伴关系协定")),
        ),
    },
    {
        "group": "国际能源机构",
        "items": (
            ("IEA", "国际能源署", (r"\binternational energy agency\b", r"\biea\b", r"国际能源署")),
            ("IRENA", "国际可再生能源署", (r"\binternational renewable energy agency\b", r"\birena\b", r"国际可再生能源署")),
        ),
    },
)

COUNTRY_ALIASES = {
    "US": ("united states", "united states of america", "u.s.", "u.s.a.", "usa", "美国"),
    "GB": ("united kingdom", "britain", "british", "英国"),
    "CN": ("china", "chinese", "people's republic of china", "中国", "中华人民共和国"),
    "RU": ("russia", "russian federation", "russian", "俄罗斯", "俄联邦", "россия", "россии", "российск"),
    "KR": ("south korea", "republic of korea", "korean", "韩国"),
    "KP": ("north korea", "democratic people's republic of korea", "朝鲜"),
    "CZ": ("czechia", "czech republic", "捷克"),
    "TR": ("türkiye", "turkiye", "turkey", "土耳其"),
    "AE": ("united arab emirates", "uae", "阿联酋"),
    "CI": ("côte d’ivoire", "cote d'ivoire", "ivory coast", "科特迪瓦"),
    "VN": ("viet nam", "vietnam", "越南"),
    "BO": ("bolivia", "plurinational state of bolivia", "玻利维亚"),
    "TZ": ("tanzania", "united republic of tanzania", "坦桑尼亚"),
    "VE": ("venezuela", "bolivarian republic of venezuela", "委内瑞拉"),
    "IR": ("iran", "islamic republic of iran", "伊朗"),
    "SY": ("syria", "syrian arab republic", "叙利亚"),
    "LA": ("laos", "lao people's democratic republic", "老挝"),
    "MD": ("moldova", "republic of moldova", "摩尔多瓦"),
    "BN": ("brunei", "brunei darussalam", "文莱"),
}

# These English country names are ordinary personal names or common words.
# They are still part of the ISO index but are not inferred from free text
# without a less ambiguous alias or an already detected place.
AMBIGUOUS_ENGLISH_NAMES = {"chad", "georgia", "jordan", "jersey", "turkey"}
AMBIGUOUS_FREE_TERMS=AMBIGUOUS_ENGLISH_NAMES|{'congo','刚果','korean'}
EXTRA_COUNTRY_TERMS={
    'US':('New Mexico','New Jersey','California','Texas','Massachusetts','West Virginia','Alabama','Alaska','Arizona','Arkansas','Colorado','Connecticut','Delaware','Florida','Hawaii','Idaho','Illinois','Indiana','Iowa','Kansas','Kentucky','Louisiana','Maine','Maryland','Michigan','Minnesota','Mississippi','Missouri','Montana','Nebraska','Nevada','New Hampshire','New York','North Carolina','North Dakota','Ohio','Oklahoma','Oregon','Pennsylvania','Rhode Island','South Carolina','South Dakota','Tennessee','Utah','Vermont','Virginia','Wisconsin','Wyoming','District of Columbia','Washington, D.C.','Washington DC'),
    'GB':('UK','U.K.','Scotland','Wales','England','Northern Ireland'),
    'CN':('Beijing','Tianjin','Hebei','北京','天津','河北'),
    'RU':('Russian','Россия','России'),
    'KR':('South Korea','South Korean','Republic of Korea','韩国'),
    'KP':('North Korea','North Korean','Democratic People\'s Republic of Korea','朝鲜'),
    'CA':('British Columbia','Canadian','Ontario','Quebec','Alberta'),
    'AU':('Australian','New South Wales','Queensland','Western Australia','South Australia'),
    'DE':('German','Bavaria'), 'FR':('French',), 'JP':('Japanese',),
    'IN':('Indian government','Indian states','New Delhi'),
    'BR':('Brazilian',), 'ID':('Indonesian',), 'NG':('Nigerian',),
    'ZA':('South African',), 'NZ':('New Zealanders',),
    'TW':('Chinese Taipei',),
    'VI':('US Virgin Islands','U.S. Virgin Islands'),
    'CG':('Republic of the Congo','Republic of Congo','刚果共和国','刚果（布）','刚果(布)'),
    'CD':('Democratic Republic of the Congo','Democratic Republic of Congo','DR Congo','DRC','刚果民主共和国','刚果（金）','刚果(金)'),
    'TR':('Turkish','Türkiye','Turkiye'),
}


def _normalise(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip().lower()


@lru_cache(maxsize=1)
def country_index() -> tuple[dict, ...]:
    payload = json.loads(COUNTRY_CODES_PATH.read_text(encoding="utf-8"))
    return tuple(payload.get("countries") or ())


@lru_cache(maxsize=1)
def _country_by_code() -> dict[str, dict]:
    return {str(row["alpha2"]): dict(row) for row in country_index()}


def _contains_term(text: str, term: str) -> bool:
    term = _normalise(term)
    if not term:
        return False
    if re.search(r"[a-z]", term) and not re.search(r"[\u3400-\u9fff]", term):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))
    return term in text


@lru_cache(maxsize=1)
def _country_patterns():
    terms={}
    for row in country_index():
        for term in (row.get('name_zh'),row.get('name_en'),*COUNTRY_ALIASES.get(row['alpha2'],()),*EXTRA_COUNTRY_TERMS.get(row['alpha2'],())):
            if term and _normalise(term) not in AMBIGUOUS_FREE_TERMS:
                terms.setdefault(_normalise(term),set()).add(row['alpha2'])
    english=[];other=[]
    for term in sorted(terms,key=len,reverse=True):
        pattern=re.escape(term)
        if re.search(r'[a-z]',term) and not re.search(r'[\u3400-\u9fff]',term):english.append(pattern)
        else:other.append(pattern)
    # Share word-boundary assertions instead of repeating them for every alias
    # at every character of a long source document.
    combined=r'(?<![A-Za-z0-9])(?:'+'|'.join(english)+r')(?![A-Za-z0-9])|(?:'+'|'.join(other)+')'
    return re.compile(combined,re.I),terms


@lru_cache(maxsize=32768)
def country_mentions_with_evidence(text: str) -> list[dict]:
    """Longest-name-first spans, with conservative ambiguous-name handling.

    Country tags describe textual/geographic relevance, not a policy's legal
    jurisdiction or the nationality of an attributed speaker.
    """
    text=str(text or '')
    masked=re.sub(r'https?://\S+',lambda m:' '*len(m.group()),text)
    # The Korean Peninsula is a region, not an explicit North-Korean reference.
    masked=re.sub('朝鲜半岛',lambda m:' '*len(m.group()),masked)
    pattern,terms=_country_patterns();index=_country_by_code();result=[]
    for match in pattern.finditer(masked):
        for code in terms.get(_normalise(match.group()),()):
            if code=='US' and _normalise(match.group()) in {'u.s.','u.s.a.'} and re.match(r'\$|\s*[- ]?dollars?\b',masked[match.end():],re.I):continue
            result.append({**index[code],'start':match.start(),'end':match.end(),'matched_text':text[match.start():match.end()],
                           'method':'country-span-v2'})
    # "US" in running text must be an uppercase acronym, never the pronoun
    # "us", and a currency prefix must not create a US country tag.
    for match in re.finditer(r'(?<![A-Za-z0-9])(?:US|U\.S\.)(?![A-Za-z0-9])',masked):
        if re.match(r'\$|\s*[- ]?dollars?\b',masked[match.end():],re.I):continue
        result.append({**index['US'],'start':match.start(),'end':match.end(),'matched_text':text[match.start():match.end()],'method':'country-acronym-v2'})
    rules=[('GE',r'\bGeorgia\b',r'Tbilisi|Caucasus|Republic of Georgia'),
           ('JO',r'\bJordan\b',r'Amman|Hashemite Kingdom|Jordanian government'),
           ('TD',r'\bChad\b',r"N.?Djamena|Chadian|Republic of Chad|Chad.s (?:NDC|government|president|minister)"),
           ('TR',r'\bTurkey\b',r'Turkish|Türkiye|Ankara|Erdo[gğ]an|Turkey.s (?:government|climate|energy|NDC)|Turkey (?:hosts|will host)')]
    for code,name,context in rules:
        if not re.search(context,masked,re.I):continue
        for match in re.finditer(name,masked,re.I):
            result.append({**index[code],'start':match.start(),'end':match.end(),'matched_text':text[match.start():match.end()],'method':'country-context-v2'})
    return sorted({(r['alpha2'],r['start'],r['end']):r for r in result}.values(),key=lambda r:(r['start'],r['alpha2']))


def country_codes_for(
    text: str,
    *,
    places: list[dict] | None = None,
    country_tags: list[str] | None = None,
) -> list[dict]:
    """Return ISO 3166-1 alpha-2/alpha-3 tags without treating regions as states."""
    matches=list(country_mentions_with_evidence(text))
    matches+=country_mentions_with_evidence(' '.join(str(p.get('name_zh') or '') for p in (places or []) if isinstance(p,dict)))
    codes={r['alpha2'] for r in matches}
    explicit={_normalise(v) for v in (country_tags or [])}
    for row in country_index():
        if explicit & {_normalise(row['alpha2']),_normalise(row['alpha3']),_normalise(row['name_zh']),_normalise(row['name_en'])}:
            codes.add(row['alpha2'])
    return [dict(row) for row in country_index() if row['alpha2'] in codes]


def organization_tags_for(text: str) -> list[str]:
    haystack = _normalise(text)
    matches: list[str] = []
    for group in ORGANIZATION_GROUPS:
        for code, _name, patterns in group["items"]:
            if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in patterns):
                matches.append(code)
    # UNFCCC and COP are more useful classifications than the generic UN tag.
    if "UNFCCC" in matches or "COP" in matches:
        matches = [code for code in matches if code != "UN"]
    return matches


def event_tags_for(text: str) -> list[str]:
    tags = []
    for match in re.finditer(r"\bcop\s*-?\s*(\d{1,2})\b", _normalise(text), re.IGNORECASE):
        tag = f"COP{match.group(1)}"
        if tag not in tags:
            tags.append(tag)
    return tags


def public_taxonomy() -> dict:
    names_en = {
        "UN": "United Nations", "UNFCCC": "UN Framework Convention on Climate Change", "COP": "UN Climate Change Conference",
        "G20": "Group of Twenty", "G7": "Group of Seven", "BRICS": "BRICS", "OECD": "Organisation for Economic Co-operation and Development",
        "BRI": "Belt and Road Initiative", "APEC": "Asia-Pacific Economic Cooperation", "ASEAN": "Association of Southeast Asian Nations",
        "SCO": "Shanghai Cooperation Organisation", "EU": "European Union", "AU": "African Union", "PIF": "Pacific Islands Forum",
        "CPTPP": "Comprehensive and Progressive Agreement for Trans-Pacific Partnership", "IEA": "International Energy Agency", "IRENA": "International Renewable Energy Agency",
    }
    groups_en = {"联合国与气候机制": "United Nations and climate mechanisms", "全球经济与政策协调": "Global economic and policy coordination", "区域合作机制": "Regional cooperation", "国际能源机构": "International energy organisations"}
    return {
        "schema_version": "1.0",
        "country_standard": "ISO 3166-1",
        "countries": list(country_index()),
        "organization_groups": [
            {
                "label_zh": group["group"],
                "label_en": groups_en[group["group"]],
                "organizations": [
                    {"code": code, "name_zh": name, "name_en": names_en[code]} for code, name, _patterns in group["items"]
                ],
            }
            for group in ORGANIZATION_GROUPS
        ],
    }
