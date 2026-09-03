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
            ("APEC", "亚太经济合作组织", (r"\bapec\b", r"亚太经济合作组织")),
            ("ASEAN", "东南亚国家联盟", (r"\basean\b", r"东南亚国家联盟", r"东盟")),
            ("SCO", "上海合作组织", (r"\bshanghai cooperation organi[sz]ation\b", r"\bsco\b", r"上海合作组织", r"上合组织")),
            ("EU", "欧洲联盟", (r"\beuropean union\b", r"欧盟")),
            ("AU", "非洲联盟", (r"\bafrican union\b", r"非洲联盟", r"非盟")),
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
    "RU": ("russia", "russian federation", "russian", "俄罗斯", "俄联邦"),
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


def country_codes_for(
    text: str,
    *,
    places: list[dict] | None = None,
    country_tags: list[str] | None = None,
) -> list[dict]:
    """Return ISO 3166-1 alpha-2/alpha-3 tags without treating regions as states."""
    index = country_index()
    haystack = _normalise(text)
    place_text = _normalise(" ".join(
        str(place.get("name_zh") or "") for place in (places or []) if isinstance(place, dict)
    ))
    tag_text = _normalise(" ".join(str(tag) for tag in (country_tags or [])))
    explicit_text = f" {place_text} {tag_text} "
    matched: list[dict] = []
    for row in index:
        code = str(row["alpha2"])
        names = {_normalise(row.get("name_zh")), _normalise(row.get("name_en"))}
        aliases = {_normalise(term) for term in COUNTRY_ALIASES.get(code, ())}
        explicit = any(name and name in explicit_text for name in names | aliases)
        free_terms = aliases or names
        free_match = any(
            term and term not in AMBIGUOUS_ENGLISH_NAMES and _contains_term(haystack, term)
            for term in free_terms
        )
        if explicit or free_match:
            matched.append({
                "name_zh": row["name_zh"],
                "alpha2": row["alpha2"],
                "alpha3": row["alpha3"],
            })
    return matched


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
    return {
        "schema_version": "1.0",
        "country_standard": "ISO 3166-1",
        "countries": list(country_index()),
        "organization_groups": [
            {
                "label_zh": group["group"],
                "organizations": [
                    {"code": code, "name_zh": name} for code, name, _patterns in group["items"]
                ],
            }
            for group in ORGANIZATION_GROUPS
        ],
    }
