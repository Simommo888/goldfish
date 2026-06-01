"""Notification extension points.

First version is intentionally a no-op. Future channels can include email,
Feishu, WeChat, and Telegram. Keep API tokens in environment variables only.
"""

from __future__ import annotations

from typing import Any, Dict


def notify(settings: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    if not settings.get("enable_notifications", False):
        return {"sent": False, "reason": "enable_notifications=false"}
    return {
        "sent": False,
        "reason": "通知接口已预留，第一版不真正发送。",
        "channels": ["email", "feishu", "wechat", "telegram"],
    }
