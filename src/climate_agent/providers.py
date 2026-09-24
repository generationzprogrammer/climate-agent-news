from __future__ import annotations

import json
import os
import smtplib
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from collections import Counter
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path


@dataclass(slots=True)
class OpenAICompatibleModel:
    """Small replaceable adapter for OpenAI-compatible chat-completions APIs."""

    base_url: str
    api_key: str
    model: str
    timeout: int = 60

    @classmethod
    def from_env(cls) -> "OpenAICompatibleModel":
        return cls(
            base_url=os.environ["CLIMATE_MODEL_BASE_URL"].rstrip("/"),
            api_key=os.environ["CLIMATE_MODEL_API_KEY"],
            model=os.environ["CLIMATE_MODEL_NAME"],
        )

    def complete_json(self, system: str, payload: dict) -> dict:
        body = json.dumps({
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        }).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json" if "models.github.ai" in self.base_url else "application/json",
            "User-Agent": "ClimateText-Lab/1.0",
        }
        if "models.github.ai" in self.base_url:
            headers["X-GitHub-Api-Version"] = "2026-03-10"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body, method="POST", headers=headers,
        )
        last_error: Exception | None = None
        for attempt, delay in enumerate((0, 2, 5)):
            if delay:
                time.sleep(delay)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    result = json.loads(response.read())
                content = str(result["choices"][0]["message"]["content"]).strip()
                if content.startswith("```"):
                    content = content.split("\n", 1)[-1]
                    content = content.rsplit("```", 1)[0].strip()
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    start = content.find("{")
                    end = content.rfind("}")
                    if start >= 0 and end > start:
                        return json.loads(content[start:end + 1])
                    raise
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                    raise
            except (OSError, urllib.error.URLError) as exc:
                last_error = exc
                if attempt == 2:
                    raise
        raise RuntimeError(f"model request failed: {last_error}")


def publish_file(markdown: str, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    return output


def publish_webhook(markdown: str, webhook_url: str, *, timeout: int = 15) -> None:
    body = json.dumps({"msgtype": "text", "text": {"content": markdown[:3500]}}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(webhook_url, data=body, method="POST", headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status >= 300:
            raise RuntimeError(f"webhook returned HTTP {response.status}")


def publish_wecom(markdown: str, webhook_url: str, *, timeout: int = 15) -> None:
    """Send one compact Markdown notification to an internal WeCom group bot."""
    host = (urlparse(webhook_url).hostname or "").lower()
    if host != "qyapi.weixin.qq.com":
        raise ValueError("企业微信机器人地址必须属于 qyapi.weixin.qq.com")
    body = json.dumps({
        "msgtype": "markdown",
        "markdown": {"content": markdown},
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url, data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if int(result.get("errcode", -1)) != 0:
        raise RuntimeError(f"企业微信推送失败：{result.get('errmsg', 'unknown error')}")


def publish_email(markdown: str, recipient: str, *, subject: str = "国际气候谈判情报简报") -> None:
    host = os.environ["CLIMATE_SMTP_HOST"]
    port = int(os.getenv("CLIMATE_SMTP_PORT", "587"))
    username = os.getenv("CLIMATE_SMTP_USERNAME", "")
    password = os.getenv("CLIMATE_SMTP_PASSWORD", "")
    sender = os.getenv("CLIMATE_SMTP_SENDER", username)
    if not sender:
        raise ValueError("缺少 CLIMATE_SMTP_SENDER 或 CLIMATE_SMTP_USERNAME")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1] if "@" in sender else None)
    message["Reply-To"] = sender
    message["Auto-Submitted"] = "auto-generated"
    message["Precedence"] = "bulk"
    message["List-Unsubscribe"] = f"<mailto:{sender}?subject=unsubscribe>"
    message.set_content(markdown)
    security = os.getenv("CLIMATE_SMTP_SECURITY", "ssl" if port == 465 else "starttls").lower()
    if security == "ssl":
        client = smtplib.SMTP_SSL(host, port, context=ssl.create_default_context())
    else:
        client = smtplib.SMTP(host, port)
    with client:
        if security == "starttls":
            client.starttls(context=ssl.create_default_context())
        if username:
            client.login(username, password)
        client.send_message(message)


def publish_email_batch(markdown: str, recipients: list[str], *, subject: str, retries: int = 1) -> dict:
    """Deliver to every recipient without exposing addresses or stopping at the first failure."""
    sent = 0
    failures: Counter[str] = Counter()
    for recipient in recipients:
        for attempt in range(retries + 1):
            try:
                publish_email(markdown, recipient, subject=subject)
                sent += 1
                break
            except (OSError, smtplib.SMTPException) as exc:
                if attempt >= retries:
                    failures[type(exc).__name__] += 1
                else:
                    time.sleep(2 * (attempt + 1))
            except Exception as exc:
                failures[type(exc).__name__] += 1
                break
    return {"sent": sent, "failed": sum(failures.values()), "failure_types": dict(failures)}


def fetch_subscribers(endpoint: str, admin_token: str, *, timeout: int = 20) -> list[str]:
    """Read the active weekly list from a protected HTTPS subscription service."""
    parts = urlparse(endpoint or "")
    if parts.scheme != "https" or not parts.netloc:
        raise ValueError("订阅者接口必须使用公开 HTTPS 地址")
    if not admin_token:
        raise ValueError("缺少订阅者接口管理令牌")
    request = urllib.request.Request(
        endpoint,
        headers={
            "Authorization": f"Bearer {admin_token}",
            "Accept": "application/json",
            "User-Agent": "ClimateText-Lab/1.0",
        },
    )
    result = None
    last_error: Exception | None = None
    for attempt, delay in enumerate((0, 2, 5)):
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read(1_000_001)
                if len(payload) > 1_000_000:
                    raise ValueError("订阅者接口响应过大")
            result = json.loads(payload)
            break
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 2:
                raise
    if not isinstance(result, dict) or not isinstance(result.get("subscribers"), list):
        raise ValueError(f"订阅者接口未返回有效名单: {type(last_error).__name__ if last_error else 'invalid_schema'}")
    subscribers = []
    for value in result.get("subscribers") or []:
        email = str(value or "").strip().lower()
        if email and "@" in email and email not in subscribers:
            subscribers.append(email)
    return subscribers
