"""Notification channels for goldfish.

The first real channel is Feishu/Lark custom bot webhooks. Secrets are read
from environment variables only; project files may enable/disable channels but
must not contain webhook URLs or signing secrets.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Dict

from .model_setup import redact_secret_text
from .utils import get_env


JsonTransport = Callable[[str, Dict[str, Any], int], Dict[str, Any]]

FEISHU_URL_ENV_KEYS = ("GOLDFISH_FEISHU_WEBHOOK_URL", "FEISHU_WEBHOOK_URL")
FEISHU_SECRET_ENV_KEYS = ("GOLDFISH_FEISHU_WEBHOOK_SECRET", "FEISHU_WEBHOOK_SECRET")
FEISHU_APP_ID_ENV_KEYS = ("GOLDFISH_FEISHU_APP_ID", "FEISHU_APP_ID")
FEISHU_APP_SECRET_ENV_KEYS = ("GOLDFISH_FEISHU_APP_SECRET", "FEISHU_APP_SECRET")


def notify(settings: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.get("enable_notifications", False):
        return {"sent": False, "reason": "enable_notifications=false"}

    channels = _notification_channels(settings)
    results: Dict[str, Any] = {}
    if "feishu" in channels:
        results["feishu"] = send_feishu_run_notification(settings, payload)

    if not results:
        return {"sent": False, "reason": "no notification channels enabled", "channels": channels}
    return {
        "sent": any(result.get("sent") for result in results.values() if isinstance(result, dict)),
        "channels": results,
    }


def feishu_status(settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    settings = settings or {}
    webhook_url = _first_env(FEISHU_URL_ENV_KEYS)
    secret = _first_env(FEISHU_SECRET_ENV_KEYS)
    app_id = _first_env(FEISHU_APP_ID_ENV_KEYS)
    app_secret = _first_env(FEISHU_APP_SECRET_ENV_KEYS)
    return {
        "enabled_in_settings": bool(settings.get("enable_notifications", False)),
        "app_integration_enabled": bool(settings.get("enable_feishu_app_integration", False)),
        "channel_enabled": "feishu" in _notification_channels(settings),
        "has_app_id": bool(app_id),
        "has_app_secret": bool(app_secret),
        "app_id_preview": _preview_id(app_id),
        "has_webhook_url": bool(webhook_url),
        "has_signing_secret": bool(secret),
        "webhook_url_preview": _preview_url(webhook_url),
        "message_type": str(settings.get("feishu_message_type") or "post"),
        "env_keys": {
            "app_id": list(FEISHU_APP_ID_ENV_KEYS),
            "app_secret": list(FEISHU_APP_SECRET_ENV_KEYS),
            "webhook_url": list(FEISHU_URL_ENV_KEYS),
            "signing_secret": list(FEISHU_SECRET_ENV_KEYS),
        },
    }


def send_feishu_test(settings: Dict[str, Any] | None = None, *, transport: JsonTransport | None = None) -> Dict[str, Any]:
    settings = settings or {}
    return send_feishu_message(
        title="goldfish test",
        text="goldfish 已接入飞书 Webhook。收到这条消息说明通知链路可用。",
        settings=settings,
        transport=transport,
    )


def send_feishu_run_notification(
    settings: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    transport: JsonTransport | None = None,
) -> Dict[str, Any]:
    date_text = str(payload.get("date") or "")
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    paths = payload.get("paths") if isinstance(payload.get("paths"), dict) else {}
    lines = [
        f"日期：{date_text or 'unknown'}",
        f"抓取：{counts.get('fetched', 0)} 条，筛选：{counts.get('selected', 0)} 条，洞察：{counts.get('insights', 0)} 条",
        f"日报：{paths.get('daily', '') or paths.get('daily_report', '') or '未生成'}",
        f"人物动态：{paths.get('people', '') or paths.get('people_report', '') or '未生成'}",
    ]
    for label, key in [
        ("知识报告", "knowledge_report_path"),
        ("反馈报告", "feedback_report_path"),
        ("周报", "weekly_path"),
        ("Dashboard", "dashboard_path"),
    ]:
        value = payload.get(key)
        if value:
            lines.append(f"{label}：{value}")
    draft_paths = payload.get("draft_paths")
    if isinstance(draft_paths, list) and draft_paths:
        lines.append(f"草稿：{len(draft_paths)} 份")

    return send_feishu_message(
        title=f"goldfish AI 情报日报 - {date_text or 'latest'}",
        text="\n".join(lines),
        settings=settings,
        transport=transport,
    )


def send_feishu_message(
    *,
    title: str,
    text: str,
    settings: Dict[str, Any] | None = None,
    transport: JsonTransport | None = None,
) -> Dict[str, Any]:
    settings = settings or {}
    webhook_url = _first_env(FEISHU_URL_ENV_KEYS)
    if not webhook_url:
        return {
            "sent": False,
            "channel": "feishu",
            "reason": "missing FEISHU_WEBHOOK_URL or GOLDFISH_FEISHU_WEBHOOK_URL",
            "status": feishu_status(settings),
        }

    message_type = str(settings.get("feishu_message_type") or "post").lower().strip()
    body = _feishu_text_payload(title, text) if message_type == "text" else _feishu_post_payload(title, text)
    _add_feishu_signature(body)
    timeout = _int(settings.get("feishu_timeout_seconds"), default=10, minimum=1, maximum=60)
    try:
        response = (transport or _post_json)(webhook_url, body, timeout)
    except Exception as exc:
        return {
            "sent": False,
            "channel": "feishu",
            "error": redact_secret_text(str(exc)),
            "webhook_url_preview": _preview_url(webhook_url),
        }

    ok = _feishu_response_ok(response)
    return {
        "sent": ok,
        "channel": "feishu",
        "response": _redact_payload(response),
        "webhook_url_preview": _preview_url(webhook_url),
    }


def _feishu_text_payload(title: str, text: str) -> Dict[str, Any]:
    body = f"{title}\n\n{text}".strip()
    return {"msg_type": "text", "content": {"text": body}}


def _feishu_post_payload(title: str, text: str) -> Dict[str, Any]:
    content = [[{"tag": "text", "text": line}] for line in _message_lines(text)]
    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": title,
                    "content": content,
                }
            }
        },
    }


def _message_lines(text: str) -> list[str]:
    lines = [line.strip() for line in str(text or "").splitlines()]
    return [line for line in lines if line] or ["goldfish notification"]


def _add_feishu_signature(body: Dict[str, Any]) -> None:
    secret = _first_env(FEISHU_SECRET_ENV_KEYS)
    if not secret:
        return
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    body["timestamp"] = timestamp
    body["sign"] = base64.b64encode(digest).decode("utf-8")


def _post_json(url: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Feishu webhook HTTP {exc.code}: {raw}") from exc
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


def _feishu_response_ok(response: Dict[str, Any]) -> bool:
    code = response.get("code")
    status_code = response.get("StatusCode")
    if code in {0, "0"} or status_code in {0, "0"}:
        return True
    if response.get("msg") == "success":
        return True
    return False


def _notification_channels(settings: Dict[str, Any]) -> list[str]:
    raw = settings.get("notification_channels")
    if isinstance(raw, list):
        channels = [str(item).lower().strip() for item in raw if str(item).strip()]
    elif isinstance(raw, str):
        channels = [item.strip().lower() for item in raw.split(",") if item.strip()]
    else:
        channels = ["feishu"] if settings.get("enable_notifications", False) else []
    if settings.get("enable_feishu_notifications", False) and "feishu" not in channels:
        channels.append("feishu")
    return channels


def _first_env(keys: tuple[str, ...]) -> str:
    for key in keys:
        value = get_env(key, "")
        if value:
            return value
    return ""


def _preview_url(url: str) -> str:
    if not url:
        return ""
    if len(url) <= 22:
        return "***REDACTED***"
    return url[:18] + "...***"


def _preview_id(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return value[:3] + "***"
    return value[:8] + "..." + value[-4:]


def _redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_payload(nested) for key, nested in value.items() if "secret" not in str(key).lower()}
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_secret_text(value)
    return value


def _int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except Exception:
        number = default
    return max(minimum, min(maximum, number))
