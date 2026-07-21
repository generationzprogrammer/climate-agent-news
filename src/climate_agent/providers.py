from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass
from email.message import EmailMessage
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
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            result = json.loads(response.read())
        return json.loads(result["choices"][0]["message"]["content"])


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
