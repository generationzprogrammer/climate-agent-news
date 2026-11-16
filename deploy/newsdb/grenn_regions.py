#!/usr/bin/env python3
"""One China in every classification (2026-11-15, user: 把中国台湾和中华人民共和国合并到一起，包括网站上的所有地方，
包括区域分类和地图上，统一为中华人民共和国).

What changes: wherever a record is *classified* — ISO country codes (TW → CN, TWN → CHN), country entries
({alpha2, alpha3, name_zh, name_en}), country names used as tags or as a company's country (中国台湾 / 中华民国 / Taiwan …
→ 中华人民共和国 / China), places (a "Taiwan" place becomes the China place the data already uses), tables keyed by
country, and the counts beside them (merged, not dropped). A list that ends up naming China twice keeps it once.
What does not change: what was published — titles, summaries, source texts, quoted evidence and the words matched in
them (an article that says "Taiwan" still says so); only the label it is filed under changes.

Used by
  grenn_newsdb.py   every record entering news.db (finish / country_fields) and `normalize-regions` for the rows already in it
  sync-data.sh      `grenn_regions.py apply <snapshot folder>`: the site data the original project's pipeline writes
                    (its code labels Taiwan separately and is not ours to change) — JSON, JSON lines and the CSV downloads
Standard library only.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
from pathlib import Path

CN = {"alpha2": "CN", "alpha3": "CHN", "name_zh": "中华人民共和国", "name_en": "China"}
CODE2 = {"TW": "CN"}
CODE3 = {"TWN": "CHN"}
NAME_ZH = "中华人民共和国"
NAME_EN = "China"
# names that file a record under Taiwan (exact values only: a sentence that mentions Taiwan is text, not a label)
NAMES_ZH = {"中国台湾", "台湾", "台灣", "臺灣", "台湾省", "中国台湾省", "台湾地区", "中国台湾地区", "中华民国", "中華民國"}
NAMES_EN = {"Taiwan", "Chinese Taipei", "Taiwan, Province of China", "Taiwan (Province of China)", "Republic of China (Taiwan)"}
# keys whose value is a country's English name (an exact "Taiwan" under any other key — a matched word, a quote — stays)
EN_NAME_KEYS = {"name_en", "en", "country_en", "country", "country_name", "name", "admin", "label_en"}
# a Taiwan place becomes the China place of the site data
CHINA_PLACE = {"name_zh": "中国", "name_en": "China", "lat": 35.0, "lon": 105.0}
# descriptive text that names the "Republic of China" as a state (company overviews from Wikidata): the authority named
# as the region's, the rest untouched
DESCRIPTION_KEYS = {"overview_zh", "description_zh", "summary_zh_profile"}
COUNT_KEYS = ("count", "value", "n", "articles", "records", "reports", "total", "mentions")


def is_taiwan_name(value) -> bool:
    return isinstance(value, str) and (value.strip() in NAMES_ZH or value.strip() in NAMES_EN)


def code2(code: str) -> str:
    return CODE2.get(code, code)


def codes2(codes) -> list:
    """A list of alpha-2 codes, Taiwan filed under China, each code once (order kept)."""
    return list(dict.fromkeys(code2(c) for c in codes if c))


class Fixer:
    def __init__(self):
        self.changes = 0

    def _set(self, obj, key, value):
        if obj.get(key) != value:
            obj[key] = value
            self.changes += 1

    def country_entry(self, d: dict) -> None:
        """{alpha2: TW, …} / {label_id: TW, …} / {id|code: TW, zh, en …} → China's values; other keys stay."""
        for key, val in (("alpha2", "CN"), ("label_id", "CN"), ("id", "CN"), ("code", "CN"), ("iso2", "CN"), ("country_code", "CN")):
            if d.get(key) == "TW":
                self._set(d, key, val)
        for key in ("alpha3", "iso3"):
            if d.get(key) == "TWN":
                self._set(d, key, "CHN")
        for key in ("name_zh", "zh", "country_zh"):
            if key in d and is_taiwan_name(d[key]):
                self._set(d, key, NAME_ZH)
        for key in ("name_en", "en", "country_en"):
            if key in d and is_taiwan_name(d[key]):
                self._set(d, key, NAME_EN)

    def is_country_entry(self, d: dict) -> bool:
        if d.get("alpha2") == "TW" or d.get("alpha3") == "TWN" or d.get("iso2") == "TW" or d.get("country_code") == "TW":
            return True
        if d.get("label_id") == "TW" and d.get("label_type", "country") in ("country", "country_mention", "countries"):
            return True
        named = any(k in d for k in ("zh", "en", "name_zh", "name_en", "name"))
        return named and (d.get("id") == "TW" or d.get("code") == "TW")

    def is_place(self, d: dict) -> bool:
        return ("lat" in d or "lon" in d or "lng" in d) and (is_taiwan_name(d.get("name_zh")) or is_taiwan_name(d.get("name")) or is_taiwan_name(d.get("name_en")))

    def fix(self, obj, key=None):
        if isinstance(obj, dict):
            if self.is_place(obj):
                for k, v in CHINA_PLACE.items():
                    if k in obj or k in ("name_zh", "lat", "lon"):
                        self._set(obj, k, v)
                if "lng" in obj:
                    self._set(obj, "lng", CHINA_PLACE["lon"])
            elif self.is_country_entry(obj):
                self.country_entry(obj)
            for k in list(obj):
                obj[k] = self.fix(obj[k], k)
                if k in DESCRIPTION_KEYS and isinstance(obj[k], str) and ("中华民国" in obj[k] or "中華民國" in obj[k]):
                    new = obj[k].replace("中华民国经济部", "中国台湾地区经济主管部门").replace("中华民国", "中国台湾地区").replace("中華民國", "中国台湾地区")
                    self._set(obj, k, new)
            self.keyed(obj)
            return obj
        if isinstance(obj, list):
            before = self.changes
            out = [self.fix(v, key) for v in obj]
            return self.merge_list(out) if self.changes != before else out
        if isinstance(obj, str):
            if obj == "TW":
                self.changes += 1
                return "CN"
            if obj == "TWN":
                self.changes += 1
                return "CHN"
            if obj.strip() in NAMES_ZH:
                self.changes += 1
                return NAME_ZH
            if obj.strip() in NAMES_EN and key in EN_NAME_KEYS:
                self.changes += 1
                return NAME_EN
        return obj

    def keyed(self, d: dict) -> None:
        """Tables keyed by country ({"TW": 3, "CN": 9}, {"中国台湾": …}): Taiwan's entry folded into China's."""
        for old, new in (("TW", "CN"), ("TWN", "CHN"), *((n, NAME_ZH) for n in NAMES_ZH)):
            if old not in d:
                continue
            if old in ("TW", "TWN") and not all(re.fullmatch(r"[A-Z]{2,3}", k) for k in d):
                continue  # not a table of countries
            value = d.pop(old)
            self.changes += 1
            if new not in d:
                d[new] = value
            elif isinstance(d[new], (int, float)) and isinstance(value, (int, float)) and not isinstance(value, bool):
                d[new] += value
            elif isinstance(d[new], list) and isinstance(value, list):
                d[new] = list(dict.fromkeys(json.dumps(v, ensure_ascii=False, sort_keys=True) for v in d[new] + value))
                d[new] = [json.loads(v) for v in d[new]]
            elif isinstance(d[new], dict) and isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and isinstance(d[new].get(k), (int, float)):
                        d[new][k] += v
                    else:
                        d[new].setdefault(k, v)

    def merge_list(self, items: list) -> list:
        """After a rename: China listed once. Country entries by code; plain strings; and {name, count} rows summed."""
        if all(isinstance(v, str) for v in items):
            return list(dict.fromkeys(items))
        if all(isinstance(v, dict) for v in items) and items:
            ident = next((k for k in ("alpha2", "alpha3", "iso2", "id", "code", "name_zh", "name", "zh") if all(k in v for v in items)), None)
            if not ident:
                return items
            countable = [k for k in COUNT_KEYS if all(isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool) for v in items)]
            if ident in ("alpha2", "alpha3", "iso2") and not countable and any("start" in v or "quote" in v for v in items):
                return items  # evidence spans: each one is a different place in the text
            out, seen = [], {}
            for v in items:
                k = v.get(ident)
                if k in seen and (k in ("CN", "CHN", NAME_ZH, NAME_EN) or k == CHINA_PLACE["name_zh"]):
                    first = seen[k]
                    for c in countable:
                        first[c] += v[c]
                    continue
                seen.setdefault(k, v)
                out.append(v)
            return out
        return items


def fix(obj):
    """Return (the same object, fixed in place where it could be; the number of changes)."""
    f = Fixer()
    out = f.fix(obj)
    return out, f.changes


# ---------------------------------------------------------------- files
CSV_CODE_COLUMNS = re.compile(r"(^|_)(country|countries|iso2|iso3|alpha2|alpha3|country_iso2|country_iso3|country_codes|places|nation)s?$", re.I)


def fix_csv_cell(value: str) -> tuple[str, int]:
    if not value:
        return value, 0
    parts = re.split(r"([;,|])", value)
    out, n = [], 0
    for p in parts:
        s = p.strip()
        if s == "TW":
            out.append(p.replace("TW", "CN")); n += 1
        elif s == "TWN":
            out.append(p.replace("TWN", "CHN")); n += 1
        elif s in NAMES_ZH:
            out.append(p.replace(s, NAME_ZH)); n += 1
        elif s in NAMES_EN:
            out.append(p.replace(s, NAME_EN)); n += 1
        else:
            out.append(p)
    if not n:
        return value, 0
    # China once per cell
    seps = out[1::2]
    vals = list(dict.fromkeys(v for v in out[0::2]))
    joined = vals[0]
    for i, v in enumerate(vals[1:]):
        joined += (seps[i] if i < len(seps) else ";") + v
    return joined, n


def apply_file(path: Path) -> int:
    text = path.read_text("utf-8-sig" if path.suffix == ".csv" else "utf-8")
    bom = path.read_bytes()[:3] == b"\xef\xbb\xbf"
    changes = 0
    if path.suffix == ".json":
        if not any(w in text for w in ('"TW"', "TWN", "台湾", "台灣", "臺灣", "中华民国", "中華民國", "Taiwan", "Chinese Taipei")):
            return 0
        data, changes = fix(json.loads(text))
        if changes:
            out = json.dumps(data, ensure_ascii=False, separators=(",", ":") if "\n" not in text[:2000] else None, indent=None if "\n" not in text[:2000] else 2)
    elif path.suffix == ".jsonl":
        lines = []
        for line in text.splitlines():
            if line.strip() and any(w in line for w in ('"TW"', "TWN", "台湾", "臺灣", "中华民国", "Taiwan", "Chinese Taipei")):
                data, n = fix(json.loads(line))
                if n:
                    changes += n
                    line = json.dumps(data, ensure_ascii=False)
            lines.append(line)
        out = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    elif path.suffix == ".csv":
        rows = list(csv.reader(io.StringIO(text)))
        if not rows:
            return 0
        header = rows[0]
        cols = [i for i, name in enumerate(header) if CSV_CODE_COLUMNS.search(name.strip())]
        for row in rows[1:]:
            for i in cols:
                if i < len(row):
                    row[i], n = fix_csv_cell(row[i])
                    changes += n
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\r\n" if "\r\n" in text[:5000] else "\n").writerows(rows)
        out = buf.getvalue()
    else:
        return 0
    if changes:
        tmp = path.with_name(path.name + ".regions-tmp")
        tmp.write_text(("﻿" if bom else "") + out, encoding="utf-8")
        os.chmod(tmp, path.stat().st_mode & 0o777)
        os.replace(tmp, path)
    return changes


def apply(folder: Path) -> dict:
    report = {}
    for path in sorted(folder.iterdir()):
        if path.is_file() and path.suffix in (".json", ".jsonl", ".csv"):
            n = apply_file(path)
            if n:
                report[path.name] = n
    return report


def main(argv: list) -> int:
    if len(argv) != 3 or argv[1] != "apply":
        print("usage: grenn_regions.py apply <data folder>", file=sys.stderr)
        return 2
    report = apply(Path(argv[2]))
    print("regions:", json.dumps({"files": len(report), "changes": sum(report.values()), "by_file": report}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
