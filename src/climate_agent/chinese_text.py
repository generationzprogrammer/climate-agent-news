from __future__ import annotations

import re
from functools import lru_cache

from opencc import OpenCC


_CHINESE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_MALFORMED_DASHED_LATIN = re.compile(r"(?:[A-Za-z0-9]-){3,}")


@lru_cache(maxsize=1)
def _converter() -> OpenCC:
    return OpenCC("t2s")


def to_simplified(value: object) -> str:
    """Return display text in simplified Chinese without changing identifiers or URLs."""
    return _converter().convert(str(value or "")).strip()


def chinese_character_count(value: object) -> int:
    return len(_CHINESE.findall(str(value or "")))


def is_readable_chinese_title(value: object) -> bool:
    text = to_simplified(value)
    return (
        4 <= chinese_character_count(text) <= 120
        and len(text) <= 180
        and not _MALFORMED_DASHED_LATIN.search(text)
    )
