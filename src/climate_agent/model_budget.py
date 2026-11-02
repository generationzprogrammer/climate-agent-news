"""Shared request ledger, without prompts, credentials or personal information.

Enabled by CLIMATE_MODEL_USAGE_PATH. GitHub publishes serially and persists this
ledger between runs. It limits *requests*, including retries, not billing tier.
"""
from __future__ import annotations

import json
import os
import time
import threading
from functools import wraps
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_last_request = 0.0
_ledger_lock=threading.RLock()

def _serial_ledger(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        with _ledger_lock:return function(*args,**kwargs)
    return wrapped


class ModelBudgetExceeded(RuntimeError):
    pass


def _state() -> tuple[Path | None, dict]:
    name = os.getenv("CLIMATE_MODEL_USAGE_PATH", "")
    if not name:
        return None, {}
    path = Path(name)
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("requests"), int):
                raise ValueError("invalid ledger")
        except (ValueError, OSError) as exc:
            raise ModelBudgetExceeded("Model request ledger is unreadable; no request sent") from exc
    else:
        data = {}
    if data.get("quota_date") != today:
        data = {"quota_date": today, "timezone": "America/Los_Angeles", "requests": 0,
                "input_tokens": 0, "output_tokens": 0, "models": {}}
    return path, data


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


@_serial_ledger
def reserve_request(model: str) -> None:
    global _last_request
    path, data = _state()
    if path is None:
        return
    limit = max(0, int(os.getenv("CLIMATE_MODEL_DAILY_REQUEST_LIMIT", "18")))
    if data["requests"] >= limit:
        raise ModelBudgetExceeded("Daily model request budget reached; retained existing summaries")
    data["requests"] += 1
    data["models"][model] = data["models"].get(model, 0) + 1
    _save(path, data)
    interval = max(0.0, float(os.getenv("CLIMATE_MODEL_MIN_INTERVAL_SECONDS", "0")))
    delay = interval - (time.monotonic() - _last_request)
    if delay > 0:
        time.sleep(delay)
    _last_request = time.monotonic()


@_serial_ledger
def record_usage(usage: dict) -> None:
    path, data = _state()
    if path is None:
        return
    for source, target in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
        value = usage.get(source)
        if isinstance(value, int) and value >= 0:
            data[target] += value
    _save(path, data)
