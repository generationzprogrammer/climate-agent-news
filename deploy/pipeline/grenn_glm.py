#!/usr/bin/env python3
"""Run one step of the original project's daily pipeline with Zhipu's free GLM-4-Flash in place of Gemini (2026-11-07).

Usage (from the pipeline repo, PYTHONPATH=src, the model settings in the environment):
  grenn_glm.py -m climate_agent.cli sync --skip-ndc        a module, like python -m
  grenn_glm.py scripts/update_research_corpus.py ...      a script

The original code runs unchanged; before handing over, this
  - pins the model: only glm-4-flash-250414 on open.bigmodel.cn may be called (the user asked for this free model
    only; the key could reach paid ones);
  - gives the model a longer timeout (CLIMATE_MODEL_TIMEOUT_SECONDS, default 180 s; upstream has 60 s);
  - checks every news compilation against the evidence it was given and drops the ones that fail, so the original
    code falls back to its conservative compilation (which never replaces an earlier good summary) and retries on
    the next run. Measured 2026-11-07 with GLM-Z1-Flash (tried first): with only a headline to go on it wrote
    150–180 characters of invented detail; with full text it added numbers the text does not have (an
    oversubscription rate, shareholdings, a year) and turned "$3.1 billion" into "3.1亿" (a tenth of it).
"""
from __future__ import annotations

import json
import os
import re
import runpy
import sys
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urlsplit

MODEL = "glm-4-flash-250414"
HOST = "open.bigmodel.cn"
TIMEOUT = int(os.environ.get("CLIMATE_MODEL_TIMEOUT_SECONDS", "180"))

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
SCALE = re.compile(r"(\d+(?:\.\d+)?)\s*(trillion|billion|bn|million|mn)\b", re.I)
# magnitude words after a number, Chinese first (longest match first), then the languages the sources use
UNITS = [(re.compile(pattern, re.I), factor) for pattern, factor in (
    (r"\s*万亿", 1e12), (r"\s*千亿", 1e11), (r"\s*百亿", 1e10), (r"\s*十亿", 1e9), (r"\s*亿", 1e8), (r"\s*千万", 1e7),
    (r"\s*百万", 1e6), (r"\s*十万", 1e5), (r"\s*万", 1e4), (r"\s*千(?![克米瓦])", 1e3),
    (r"\s*(?:trillions?|trilh(?:ão|ões)|billones?|Billionen)\b", 1e12),
    (r"\s*(?:billions?|bn|bilh(?:ão|ões)|milliards?|Milliarden?|Mrd|mil millones)\b", 1e9),
    (r"\s*(?:millions?|mn|mln|milh(?:ão|ões)|millones|millón|Millionen|Mio|m)\b", 1e6),
    (r"\s*(?:thousand|mil|k)\b", 1e3),
)]
# GLM-4-Flash leaves out the English fields the original prompt adds at its end, and translates a press release line
# by line where it should summarise; the prompt also gets the number rules the checks below enforce
PROMPT_SUPPLEMENT = (
    "\n补充要求（必须遵守）：每项必须同时包含 title_en 与 summary_en 两个英文字段，不得省略或留空。"
    "summary_zh 是概括，不是逐句翻译，不写电头、股票代码与联系方式。"
    "所有数字必须与原文一致，不得改动小数点位置；换算单位时 million＝百万（16 million＝1600万），"
    "billion＝十亿（3.1 billion＝31亿），trillion＝万亿；原文没有的数字、日期与比例一律不写。"
)


def log(**fields) -> None:
    print(json.dumps({"grenn_glm": fields}, ensure_ascii=False), flush=True)


def signature(token: str) -> str:
    """Significant digits, so unit conversions still match: 1600(万) ~ 16 (million), 31(亿) ~ 3.1 (billion)."""
    return re.sub(r"\D", "", token).strip("0")


def rounds_to(source: str, sig: str) -> bool:
    """A source figure's significant digits, cut or rounded to the length of a summary's: 162668016 → 1627, 16."""
    if source == sig:
        return True
    if len(source) <= len(sig):
        return False
    rounded = Decimal(source[:len(sig)] + "." + source[len(sig):]).quantize(Decimal(1), ROUND_HALF_UP)
    return source.startswith(sig) or str(rounded).strip("0") == sig


def invented_numbers(text: str, evidence: str) -> list[str]:
    known = {signature(token) for token in NUMBER.findall(evidence)} - {""}
    found = []
    for token in NUMBER.findall(text):
        sig = signature(token)
        plain = token.replace(",", "")
        # days, months, small counts and percentages written out in words are too common to check
        if len(sig) < 2 or (plain.isdigit() and int(plain) <= 31):
            continue
        if not any(rounds_to(source, sig) for source in known):
            found.append(token)
    return found


def wrong_scale(text: str, evidence: str) -> list[str]:
    """English amounts carried over with the number unchanged but the wrong Chinese unit: 3.1 billion → 3.1亿."""
    wrong = []
    for number, unit in set(SCALE.findall(evidence)):
        unit = unit.lower()
        bad = ("亿", "万(?!亿)") if unit in ("trillion", "billion", "bn") else ("亿", "万")
        for suffix in bad:
            if re.search(rf"(?<![\d.]){re.escape(number)}\s*{suffix}", text):
                wrong.append(f"{number} {unit} → {number}{suffix[0]}")
    return wrong


def readings(token: str) -> set[float]:
    """The values a number in a source may mean: 16,266,801.60 / 16.266.801,60 / 1,16 (decimal comma) / 2.100."""
    values = set()
    commas, dots = token.count(","), token.count(".")
    if commas and dots:
        decimal = "," if token.rfind(",") > token.rfind(".") else "."
        values.add(float(token.replace("." if decimal == "," else ",", "").replace(",", ".")))
    elif commas or dots:
        separator = "," if commas else "."
        head, *groups = token.split(separator)
        if all(len(group) == 3 for group in groups):
            values.add(float(head + "".join(groups)))
        if len(groups) == 1:
            values.add(float(head + "." + groups[0]))
    else:
        values.add(float(token))
    return values


def scaled(text: str, end: int, value: float) -> float:
    for pattern, factor in UNITS:
        if pattern.match(text, end):
            return value * factor
    return value


def shifted_numbers(text: str, evidence: str) -> list[str]:
    """Precise figures (4+ significant digits) must equal a source figure after unit conversion — catches a moved
    decimal point, which the significant-digit match cannot: 16,266,801.60 → 162668016.00."""
    known = set()
    for match in NUMBER.finditer(evidence):
        for value in readings(match.group()):
            known.update((value, scaled(evidence, match.end(), value)))
    found = []
    for match in NUMBER.finditer(text):
        token = match.group()
        if len(signature(token)) < 4:
            continue
        value = scaled(text, match.end(), float(token.replace(",", "")))
        if not any(abs(value - other) <= 0.005 * max(abs(value), abs(other)) for other in known):
            found.append(token)
    return found


def check(item: dict, article: dict) -> str | None:
    """Why this compilation must not be used, or None."""
    excerpt = str(article.get("article_excerpt") or "")
    summary = str(article.get("summary") or "")
    evidence = " ".join((str(article.get("title") or ""), summary, excerpt))
    body = len(excerpt) if len(excerpt) > len(summary) else len(summary)
    summary_zh = str(item.get("summary_zh") or "")
    summary_en = str(item.get("summary_en") or "")
    # a summary cannot hold more than its evidence: Chinese runs at well under 0.7 characters per English one
    if len(summary_zh) > max(80, int(body * 0.7)):
        return f"summary_zh {len(summary_zh)} chars from {body} chars of evidence"
    if len(summary_en) > max(240, int(body * 1.1)):
        return f"summary_en {len(summary_en)} chars from {body} chars of evidence"
    text = " ".join(str(item.get(key) or "") for key in ("title_zh", "summary_zh", "importance_zh", "title_en", "summary_en"))
    invented = invented_numbers(text, evidence)
    if invented:
        return "numbers not in the evidence: " + ", ".join(invented[:6])
    scale = wrong_scale(text, evidence)
    if scale:
        return "wrong unit: " + ", ".join(scale[:3])
    shifted = shifted_numbers(text, evidence)
    if shifted:
        return "figures that differ from the evidence: " + ", ".join(shifted[:4])
    return None


def install() -> None:
    from climate_agent import providers

    model_class = providers.OpenAICompatibleModel
    original_from_env = model_class.from_env.__func__
    original_complete = model_class.complete_json

    def from_env(cls):
        model = original_from_env(cls)
        model.timeout = max(model.timeout, TIMEOUT)
        return model

    def complete_json(self, system: str, payload: dict) -> dict:
        if self.model.lower() != MODEL or urlsplit(self.base_url).hostname != HOST:
            raise RuntimeError(f"only {MODEL} on {HOST} may be called, not {self.model} on {urlsplit(self.base_url).hostname}")
        self.timeout = max(self.timeout, TIMEOUT)
        articles = payload.get("articles") if isinstance(payload, dict) else None
        if isinstance(articles, list) and "translations" in system:
            system += PROMPT_SUPPLEMENT
        result = original_complete(self, system, payload)
        if isinstance(articles, list) and isinstance(result, dict) and isinstance(result.get("translations"), list):
            by_id = {str(article.get("article_id")): article for article in articles if isinstance(article, dict)}
            kept = []
            for item in result["translations"]:
                article = by_id.get(str(item.get("article_id"))) if isinstance(item, dict) else None
                reason = check(item, article) if article else "unknown article_id"
                if reason:
                    log(rejected=str(item.get("article_id") if isinstance(item, dict) else item)[:40], reason=reason)
                else:
                    kept.append(item)
            log(compiled=len(result["translations"]), kept=len(kept))
            result["translations"] = kept
        return result

    model_class.from_env = classmethod(from_env)
    model_class.complete_json = complete_json

    # 2026-11-10: the copy starts from the original's own data, so an article that already has a model summary (the
    # original's Gemini one) keeps it — GLM compiles only those without one (translation.py imports this at each call)
    from climate_agent import cop_coverage
    original_prioritize = cop_coverage.prioritize_translation

    def summarised(row) -> bool:
        try:
            meta = json.loads(row.get("metadata_json") or "{}")
        except (TypeError, ValueError):
            return False
        return bool(meta.get("summary_zh")) and meta.get("translation_status") in ("model_generated_needs_review", "human_reviewed")

    def only_gaps(rows, limit, *args, **kwargs):
        return original_prioritize([row for row in rows if not summarised(row)], limit, *args, **kwargs)

    cop_coverage.prioritize_translation = only_gaps


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    if os.environ.get("CLIMATE_MODEL_API_KEY"):
        name, host = os.environ.get("CLIMATE_MODEL_NAME"), urlsplit(os.environ.get("CLIMATE_MODEL_BASE_URL", "")).hostname
        if (name or "").lower() != MODEL or host != HOST:
            raise SystemExit(f"model settings must name {MODEL} on {HOST} (got {name} on {host})")
    install()
    args = sys.argv[1:]
    if args[0] == "-m":
        sys.argv = [args[1], *args[2:]]
        runpy.run_module(args[1], run_name="__main__", alter_sys=True)
    else:
        sys.argv = args
        runpy.run_path(args[0], run_name="__main__")


if __name__ == "__main__":
    main()
