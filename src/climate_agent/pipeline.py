from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "spm"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    ]
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path.rstrip("/") or "/", urlencode(query), ""))


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def event_priority(event: dict) -> int:
    """Return an explainable 0-100 decision priority score."""
    evidence = min(100, event["independent_sources"] * 12 + event["official_sources"] * 18)
    score = (
        event["negotiation_relevance"] * 0.30
        + event["china_relevance"] * 0.25
        + event["urgency"] * 0.20
        + evidence * 0.15
        + float(event["confidence"]) * 100 * 0.10
    )
    return max(0, min(100, round(score)))


class AgentModule(Protocol):
    module_id: str
    display_name: str

    def analyze(self, event: dict) -> dict: ...


@dataclass(slots=True)
class RuleEvidenceAgent:
    module_id: str = "evidence.rules.v1"
    display_name: str = "证据分层 Agent"

    def analyze(self, event: dict) -> dict:
        support = event["independent_sources"] + event["official_sources"]
        return {
            "evidence_level": "A" if event["official_sources"] >= 1 and support >= 3 else "B" if support >= 2 else "C",
            "fact": event["fact"],
            "source_support": support,
            "requires_review": event["confidence"] < 0.8,
        }


@dataclass(slots=True)
class RuleDecisionAgent:
    module_id: str = "decision.rules.v1"
    display_name: str = "谈判影响 Agent"

    def analyze(self, event: dict) -> dict:
        return {
            "priority": event_priority(event),
            "assessment": event["assessment"],
            "action": event["action"],
            "decision_boundary": "系统建议，需由业务人员复核",
        }


MODULES: dict[str, AgentModule] = {
    module.module_id: module
    for module in (RuleEvidenceAgent(), RuleDecisionAgent())
}


def module_manifest() -> list[dict]:
    return [
        {
            "id": "collector.rss.v1",
            "name": "RSS/API 采集器",
            "kind": "collector",
            "replaceable": True,
            "status": "ready",
        },
        *[
            {
                "id": module.module_id,
                "name": module.display_name,
                "kind": "agent",
                "replaceable": True,
                "status": "ready",
            }
            for module in MODULES.values()
        ],
        {
            "id": "model.openai_compatible.v1",
            "name": "OpenAI 兼容模型接口",
            "kind": "model",
            "replaceable": True,
            "status": "configure",
        },
        {
            "id": "publisher.multi.v1",
            "name": "邮件 / Webhook / 文件发布器",
            "kind": "publisher",
            "replaceable": True,
            "status": "ready",
        },
    ]


def decode_event(row: dict) -> dict:
    item = dict(row)
    item["source_refs"] = json.loads(item.pop("source_refs_json"))
    item["tags"] = json.loads(item.pop("tags_json"))
    item["demo"] = bool(item["demo"])
    item["priority"] = event_priority(item)
    item["evidence"] = MODULES["evidence.rules.v1"].analyze(item)
    return item

