"""Temporary QR pairing flow for Feishu notifications.

This module starts a short-lived local HTTP form and renders its URL as a QR
code in the terminal. The QR is only a pairing entrypoint: goldfish still uses
Feishu custom bot webhooks, and it never fetches or stores credentials in
project files.
"""

from __future__ import annotations

import html
import json
import os
import secrets
import socket
import threading
import time
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

from .config_loader import load_config
from .model_setup import redact_secret_text, set_user_environment_variable
from .notifier import FEISHU_APP_ID_ENV_KEYS, FEISHU_APP_SECRET_ENV_KEYS, feishu_status


DEFAULT_QR_PORT = 8765
DEFAULT_QR_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class PairingUrl:
    public_url: str
    local_url: str
    host: str
    port: int


class PairingHTTPServer(ThreadingHTTPServer):
    """Tiny one-shot setup server with an expiring token."""

    daemon_threads = True

    def __init__(self, server_address: tuple[str, int], token: str, expires_at: float) -> None:
        super().__init__(server_address, FeishuPairingHandler)
        self.token = token
        self.expires_at = expires_at
        self.done_event = threading.Event()
        self.result: Dict[str, Any] = {}


class FeishuPairingHandler(BaseHTTPRequestHandler):
    server: PairingHTTPServer

    def do_GET(self) -> None:
        if not self._token_ok():
            self._send_html(403, _error_page("配对链接无效或已过期。"))
            return
        self._send_html(200, _form_page(self.server.token))

    def do_POST(self) -> None:
        if not self._token_ok():
            self._send_html(403, _error_page("配对链接无效或已过期。"))
            return

        raw = self.rfile.read(_content_length(self.headers.get("Content-Length"))).decode("utf-8", errors="replace")
        data = {key: values[-1] for key, values in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}
        app_id = str(data.get("app_id") or "").strip()
        app_secret = str(data.get("app_secret") or "").strip()
        enable_app_integration = str(data.get("enable_app_integration") or "").lower() in {"on", "true", "1", "yes"}

        if not is_valid_feishu_app_credentials(app_id, app_secret):
            self._send_html(
                400,
                _error_page(
                    "App ID 或 App Secret 格式不正确。App ID 通常以 cli_ 开头，App Secret 不能为空。"
                ),
            )
            return

        try:
            saved = save_feishu_pairing(
                app_id=app_id,
                app_secret=app_secret,
                enable_app_integration=enable_app_integration,
            )
        except Exception as exc:
            self._send_html(500, _error_page(redact_secret_text(str(exc))))
            return

        self.server.result = saved
        self.server.done_event.set()
        self._send_html(200, _success_page(saved))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib hook name
        return

    def _token_ok(self) -> bool:
        if time.time() > self.server.expires_at:
            return False
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/feishu/setup":
            return False
        query = urllib.parse.parse_qs(parsed.query)
        supplied = (query.get("token") or [""])[-1]
        return secrets.compare_digest(supplied, self.server.token)

    def _send_html(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run_feishu_qr_setup(
    *,
    port: int = DEFAULT_QR_PORT,
    timeout_seconds: int = DEFAULT_QR_TIMEOUT_SECONDS,
    open_browser: bool = False,
) -> Dict[str, Any]:
    """Start a short-lived pairing form, print a QR code, and wait for submit."""

    timeout_seconds = max(30, min(int(timeout_seconds or DEFAULT_QR_TIMEOUT_SECONDS), 1800))
    token = secrets.token_urlsafe(18)
    server, actual_port = _start_server(token=token, port=port, timeout_seconds=timeout_seconds)
    urls = build_pairing_urls(host=detect_lan_ip(), port=actual_port, token=token)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    print(_intro_text(urls, timeout_seconds))
    qr = render_terminal_qr(urls.public_url)
    if qr:
        print(qr)
    else:
        print("二维码渲染不可用，请先安装依赖：")
        print("  pip install -r scripts/goldfish/requirements.txt")
    print("如果无法扫码，请直接打开这个链接：")
    print(f"  {urls.public_url}")
    print()

    if open_browser:
        try:
            import webbrowser

            webbrowser.open(urls.local_url)
        except Exception:
            pass

    try:
        finished = server.done_event.wait(timeout_seconds)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    if not finished:
        return {
            "status": "timeout",
            "message": "飞书二维码配对已超时。",
            "public_url": urls.public_url,
            "local_url": urls.local_url,
            "timeout_seconds": timeout_seconds,
        }

    result = dict(server.result)
    result.setdefault("status", "ok")
    result["message"] = "飞书二维码配对已完成。"
    result["public_url"] = urls.public_url
    result["local_url"] = urls.local_url
    return result


def save_feishu_pairing(
    *,
    app_id: str,
    app_secret: str,
    enable_app_integration: bool = True,
) -> Dict[str, Any]:
    if not is_valid_feishu_app_credentials(app_id, app_secret):
        raise ValueError("飞书 App ID 或 App Secret 无效。")

    os.environ[FEISHU_APP_ID_ENV_KEYS[0]] = app_id
    os.environ[FEISHU_APP_ID_ENV_KEYS[1]] = app_id
    set_user_environment_variable(FEISHU_APP_ID_ENV_KEYS[0], app_id)
    set_user_environment_variable(FEISHU_APP_ID_ENV_KEYS[1], app_id)

    os.environ[FEISHU_APP_SECRET_ENV_KEYS[0]] = app_secret
    os.environ[FEISHU_APP_SECRET_ENV_KEYS[1]] = app_secret
    set_user_environment_variable(FEISHU_APP_SECRET_ENV_KEYS[0], app_secret)
    set_user_environment_variable(FEISHU_APP_SECRET_ENV_KEYS[1], app_secret)

    settings = enable_feishu_app_settings(enable=enable_app_integration)
    status = feishu_status(settings)
    return {
        "status": "ok",
        "saved": True,
        "enabled": enable_app_integration,
        "app_id_preview": status.get("app_id_preview", ""),
        "has_app_secret": status.get("has_app_secret", False),
        "settings_path": str(load_config().config_dir / "settings.json"),
    }


def enable_feishu_app_settings(*, enable: bool = True) -> Dict[str, Any]:
    config = load_config()
    settings = dict(config.settings)
    settings["enable_feishu_app_integration"] = bool(enable)
    settings["feishu_auth_type"] = "app_credentials"
    _write_json(config.config_dir / "settings.json", settings)
    return settings


def is_valid_feishu_app_credentials(app_id: str, app_secret: str) -> bool:
    app_id = (app_id or "").strip()
    app_secret = (app_secret or "").strip()
    if not app_id.startswith("cli_"):
        return False
    if len(app_id) < 8:
        return False
    if len(app_secret) < 8:
        return False
    return True


def is_valid_feishu_webhook(url: str) -> bool:
    parsed = urllib.parse.urlparse((url or "").strip())
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if host not in {"open.feishu.cn", "open.larksuite.com"}:
        return False
    return parsed.path.startswith("/open-apis/bot/v2/hook/")


def build_pairing_urls(*, host: str, port: int, token: str) -> PairingUrl:
    safe_host = host or "127.0.0.1"
    query = urllib.parse.urlencode({"token": token})
    public_url = f"http://{safe_host}:{port}/feishu/setup?{query}"
    local_url = f"http://127.0.0.1:{port}/feishu/setup?{query}"
    return PairingUrl(public_url=public_url, local_url=local_url, host=safe_host, port=port)


def render_terminal_qr(url: str) -> str:
    try:
        import qrcode
    except Exception:
        return ""

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    lines: list[str] = []
    # Two QR module rows are packed into one terminal row; this makes the
    # printed QR about one quarter of the previous visual area.
    for index in range(0, len(matrix), 2):
        top = matrix[index]
        bottom = matrix[index + 1] if index + 1 < len(matrix) else [False] * len(top)
        lines.append("".join(_qr_half_block(top_cell, bottom_cell) for top_cell, bottom_cell in zip(top, bottom)))
    return "\n".join(lines)


def _qr_half_block(top_dark: bool, bottom_dark: bool) -> str:
    top = "0;0;0" if top_dark else "255;255;255"
    bottom = "0;0;0" if bottom_dark else "255;255;255"
    return f"\x1b[38;2;{top}m\x1b[48;2;{bottom}m▀\x1b[0m"


def detect_lan_ip() -> str:
    candidates: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            candidates.append(sock.getsockname()[0])
    except Exception:
        pass
    try:
        candidates.append(socket.gethostbyname(socket.gethostname()))
    except Exception:
        pass
    for candidate in candidates:
        if candidate and not candidate.startswith("127."):
            return candidate
    return "127.0.0.1"


def _start_server(*, token: str, port: int, timeout_seconds: int) -> tuple[PairingHTTPServer, int]:
    errors: list[str] = []
    preferred = int(port or DEFAULT_QR_PORT)
    for candidate in _candidate_ports(preferred):
        try:
            server = PairingHTTPServer(("0.0.0.0", candidate), token, time.time() + timeout_seconds)
            return server, int(server.server_address[1])
        except OSError as exc:
            errors.append(f"{candidate}: {exc}")
    raise RuntimeError("无法启动飞书二维码配置服务：" + "; ".join(errors[-3:]))


def _candidate_ports(preferred: int) -> list[int]:
    if preferred <= 0:
        return [0]
    return [preferred, preferred + 1, preferred + 2, preferred + 3, preferred + 4]


def _intro_text(urls: PairingUrl, timeout_seconds: int) -> str:
    lines = [
        "飞书二维码连接已准备好。",
        f"- 有效期：{timeout_seconds} 秒",
        f"- 局域网链接：{urls.public_url}",
        f"- 本机链接：{urls.local_url}",
        "",
        "请用同一局域网内的设备扫码，填写飞书应用的 App ID 和 App Secret。",
        "如果 Windows 防火墙拦截，请在本机打开“本机链接”，",
        "或允许 Python/goldfish 访问本地网络。",
        "",
    ]
    return "\n".join(lines)


def _form_page(token: str) -> str:
    token_html = html.escape(token)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>goldfish 飞书连接配置</title>
  <style>
    :root {{
      --text: #1f2d3d;
      --muted: #5f6b7a;
      --panel: #f7f8fa;
      --line: #e9edf2;
      --brand: #1456f0;
      --teal: #12c9b2;
      --warning: #ff6a00;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
      background: #ffffff;
      color: var(--text);
    }}
    main {{
      width: min(760px, calc(100vw - 40px));
      margin: 48px auto 32px;
      text-align: center;
    }}
    .hero {{
      width: 154px;
      height: 132px;
      margin: 0 auto 18px;
    }}
    h1 {{
      margin: 0 0 12px;
      font-size: 24px;
      line-height: 1.35;
      font-weight: 650;
      color: #0f172a;
    }}
    .hint {{
      max-width: 640px;
      margin: 0 auto 24px;
      font-size: 18px;
      line-height: 1.75;
      color: #4b5563;
    }}
    .hint strong {{
      color: var(--warning);
      font-weight: 500;
    }}
    form {{
      margin: 0 auto;
    }}
    .credential-card {{
      max-width: 660px;
      margin: 0 auto 24px;
      padding: 18px 18px 14px;
      border-radius: 16px;
      background: var(--panel);
      text-align: left;
    }}
    .field-row {{
      display: grid;
      grid-template-columns: 150px 1fr auto;
      gap: 14px;
      align-items: center;
      min-height: 52px;
    }}
    .field-row + .field-row {{
      border-top: 1px solid var(--line);
      padding-top: 12px;
      margin-top: 8px;
    }}
    label {{
      font-size: 20px;
      color: #5e6673;
      white-space: nowrap;
    }}
    input, select {{
      width: 100%;
      min-width: 0;
      border: 0;
      outline: none;
      background: transparent;
      color: #0f172a;
      font-size: 18px;
      line-height: 1.4;
      font-family: inherit;
    }}
    input::placeholder {{
      color: #a7b0bd;
    }}
    select {{
      appearance: none;
      padding-right: 20px;
      cursor: pointer;
    }}
    .field-actions {{
      display: flex;
      gap: 8px;
      align-items: center;
    }}
    .icon-btn {{
      width: 30px;
      height: 30px;
      border: 0;
      margin: 0;
      padding: 0;
      border-radius: 8px;
      background: transparent;
      color: #526070;
      font-size: 18px;
      line-height: 30px;
      cursor: pointer;
    }}
    .icon-btn:hover {{
      background: #edf1f6;
    }}
    .options {{
      max-width: 660px;
      margin: 0 auto 24px;
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      text-align: left;
    }}
    .option-card {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px 16px;
      color: #4b5563;
      background: #fff;
    }}
    .option-card label {{
      display: flex;
      gap: 10px;
      align-items: center;
      font-size: 16px;
      color: #334155;
    }}
    .option-card input {{
      width: auto;
    }}
    .message-type {{
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}
    .message-type span {{
      color: #697586;
      font-size: 14px;
    }}
    .message-type select {{
      padding: 0;
      color: #0f172a;
      font-size: 16px;
    }}
    .actions {{
      display: flex;
      justify-content: center;
      gap: 14px;
      margin-top: 8px;
    }}
    .primary {{
      min-width: 112px;
      height: 48px;
      border: 1px solid #c9d2df;
      border-radius: 9px;
      background: #fff;
      color: #0f172a;
      font-size: 18px;
      cursor: pointer;
    }}
    .primary:hover {{
      border-color: var(--brand);
      color: var(--brand);
    }}
    .secondary {{
      min-width: 112px;
      height: 48px;
      display: inline-grid;
      place-items: center;
      border: 1px solid transparent;
      border-radius: 9px;
      color: #697586;
      text-decoration: none;
      font-size: 16px;
    }}
    .security-note {{
      margin-top: 18px;
      font-size: 13px;
      color: #8a94a3;
    }}
    @media (max-width: 640px) {{
      main {{ margin-top: 28px; }}
      .field-row {{ grid-template-columns: 1fr; gap: 6px; }}
      .field-actions {{ justify-content: flex-end; }}
      label {{ font-size: 16px; }}
      input, select {{ font-size: 16px; }}
      .options {{ grid-template-columns: 1fr; }}
      .hint {{ font-size: 16px; }}
    }}
  </style>
</head>
<body>
  <main>
    <svg class="hero" viewBox="0 0 154 132" role="img" aria-label="连接配置插画">
      <path d="M31 86c24-8 36-26 38-54" fill="none" stroke="#17418f" stroke-width="2.5" stroke-linecap="round"/>
      <path d="M45 94c20-10 35-10 46 5" fill="none" stroke="#17418f" stroke-width="2" stroke-linecap="round"/>
      <path d="M70 24l50-13c7-2 13 2 15 9l15 58c2 7-2 14-9 15L91 106c-7 2-14-2-15-9L57 39c-2-7 2-14 9-15z" fill="#10c8b3"/>
      <path d="M122 30l22 5c5 1 8 5 9 10l8 34c1 5-2 10-7 11l-19 5z" fill="#10bfcf"/>
      <path d="M68 93l53-14 6 20-53 14z" fill="#2f67ff"/>
      <path d="M83 84l23-6 3 10-23 6z" fill="#ffc31a"/>
      <path d="M76 50l18 15 24-37" fill="none" stroke="#fff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M31 68l-8 26c-1 5 2 9 7 8l21-4c8-2 15-8 18-16l4-10c2-6-2-12-8-13l-18-2c-7-1-13 4-16 11z" fill="#fff"/>
      <path d="M32 67l-8 27c-1 5 2 9 7 8l21-4c8-2 15-8 18-16" fill="none" stroke="#17418f" stroke-width="2"/>
      <path d="M50 59l2 36M58 61l1 31M66 65l-2 20" stroke="#17418f" stroke-width="1.8" stroke-linecap="round"/>
      <path d="M18 104c14-2 24-6 31-15" fill="none" stroke="#17418f" stroke-width="1.8" stroke-linecap="round"/>
      <path d="M16 26l29-8" stroke="#17418f" stroke-width="4" stroke-linecap="round"/>
      <path d="M18 32l28-8" stroke="#17418f" stroke-width="2" stroke-linecap="round"/>
    </svg>
    <h1>飞书接入配置</h1>
    <p class="hint">
      智能体服务接入成功后，即可打开当前应用开始使用。请妥善保管
      <strong>App ID 和 App Secret</strong>，避免他人操控应用，造成数据泄露。
    </p>
    <form method="post" action="/feishu/setup?token={token_html}">
      <section class="credential-card">
        <div class="field-row">
          <label for="app_id">App ID：</label>
          <input id="app_id" name="app_id" required autocomplete="off" placeholder="cli_aaab080165f8dcff">
          <div class="field-actions">
            <button class="icon-btn" type="button" title="粘贴" onclick="pasteInto('app_id')">⧉</button>
          </div>
        </div>
        <div class="field-row">
          <label for="app_secret">App Secret：</label>
          <input id="app_secret" name="app_secret" type="password" required autocomplete="off" placeholder="请输入飞书应用 App Secret">
          <div class="field-actions">
            <button class="icon-btn" type="button" title="显示/隐藏" onclick="toggleSecret()">◉</button>
            <button class="icon-btn" type="button" title="粘贴" onclick="pasteInto('app_secret')">⧉</button>
          </div>
        </div>
      </section>
      <section class="options">
        <div class="option-card">
          <label><input type="checkbox" name="enable_app_integration" checked> 启用 goldfish 飞书应用接入</label>
        </div>
        <div class="option-card message-type">
          <span>凭据保存位置</span>
          <strong>用户级环境变量</strong>
        </div>
      </section>
      <div class="actions">
        <button class="primary" type="submit">保存配置</button>
        <a class="secondary" href="https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot" target="_blank" rel="noreferrer">查看飞书文档</a>
      </div>
      <p class="security-note">该页面为临时本地页面；配置只写入用户级环境变量，不写入项目文件。</p>
    </form>
  </main>
  <script>
    function toggleSecret() {{
      const input = document.getElementById('app_secret');
      input.type = input.type === 'password' ? 'text' : 'password';
    }}
    async function pasteInto(id) {{
      if (!navigator.clipboard) return;
      try {{
        document.getElementById(id).value = await navigator.clipboard.readText();
      }} catch (_) {{}}
    }}
  </script>
</body>
</html>"""


def _success_page(result: Dict[str, Any]) -> str:
    preview = html.escape(str(result.get("app_id_preview", "")))
    secret = "已配置" if result.get("has_app_secret") else "未配置"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>goldfish 飞书连接成功</title>
<style>
body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif;background:#fff;color:#1f2d3d}}
main{{width:min(700px,calc(100vw - 40px));margin:64px auto;text-align:center}}
.mark{{width:96px;height:96px;margin:0 auto 18px;border-radius:28px;background:#12c9b2;display:grid;place-items:center;color:#fff;font-size:54px;transform:rotate(-10deg)}}
h1{{font-size:24px;margin:0 0 14px;color:#0f172a}}p{{font-size:17px;line-height:1.7;color:#4b5563}}
.card{{margin:26px auto 22px;padding:18px 24px;border-radius:16px;background:#f7f8fa;text-align:left}}
.row{{display:grid;grid-template-columns:140px 1fr;gap:14px;min-height:44px;align-items:center;font-size:18px}}
.row+.row{{border-top:1px solid #e9edf2;padding-top:12px;margin-top:8px}}
.label{{color:#5f6b7a}}code{{color:#0f172a;font-family:Consolas,monospace}}
button{{height:44px;padding:0 18px;border:1px solid #c9d2df;border-radius:9px;background:#fff;color:#0f172a;font-size:17px;cursor:pointer}}
</style></head>
<body><main><div class="mark">✓</div><h1>连接成功</h1><p>goldfish 已保存飞书应用接入配置。请妥善保管 App ID 和 App Secret，避免他人操控应用或造成数据泄露。</p>
<section class="card"><div class="row"><span class="label">App ID：</span><code>{preview}</code></div><div class="row"><span class="label">App Secret：</span><span>{secret}</span></div></section>
<p>现在可以关闭这个页面，并运行 <code>goldfish notify status</code> 查看配置状态。</p><button onclick="window.close()">关闭页面</button></main></body></html>"""


def _error_page(message: str) -> str:
    safe = html.escape(message)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>goldfish 飞书连接失败</title>
<style>body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",Arial,sans-serif;background:#fff;color:#1f2d3d}}main{{width:min(640px,calc(100vw - 40px));margin:72px auto;text-align:center}}h1{{color:#d92d20}}p{{font-size:17px;line-height:1.7;color:#4b5563}}.card{{margin-top:22px;padding:18px 22px;border-radius:16px;background:#fff4f2;text-align:left;color:#7a271a}}</style></head>
<body><main><h1>配置失败</h1><p>飞书接入配置没有保存，请检查 App ID / App Secret 或稍后重试。</p><div class="card">{safe}</div></main></body></html>"""


def _content_length(value: str | None) -> int:
    try:
        return max(0, min(int(value or "0"), 16_384))
    except Exception:
        return 0


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
