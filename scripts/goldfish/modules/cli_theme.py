"""Python terminal startup page for goldfish chat.

This renderer belongs to the default Python conversation entrypoint. It uses
ANSI truecolor and Unicode block characters only; no PNGs, no raster assets.
"""

from __future__ import annotations

import shutil
from typing import Mapping

from .pixel_sprites import get_sprite
from .pixel_sprites.colors import (
    AQUA,
    AQUA_DIM,
    BLUE,
    BORDER,
    BORDER_DIM,
    CREAM,
    DIM,
    GREEN,
    ORANGE,
    ORANGE_LIGHT,
    PURPLE,
    hex_color,
    pad,
    visible_len,
)
from .pixel_sprites.state_idle import bubbles


TARGET_WIDTH = 154
LEFT_WIDTH = 86
RIGHT_WIDTH = 58
CONTENT_HEIGHT = 43


def terminal_width(default: int = TARGET_WIDTH) -> int:
    width = shutil.get_terminal_size((default, 48)).columns
    return max(120, min(width, TARGET_WIDTH))


def orange(text: str) -> str:
    return hex_color(text, ORANGE)


def water(text: str) -> str:
    return hex_color(text, AQUA)


def green(text: str) -> str:
    return hex_color(text, GREEN)


def dim(text: str) -> str:
    return hex_color(text, DIM)


def cream(text: str) -> str:
    return hex_color(text, CREAM)


def border(text: str) -> str:
    return hex_color(text, BORDER)


def banner(status: Mapping[str, object] | None = None) -> str:
    status = status or {}
    page = _page(status)
    return "\n".join(page)


def setup_banner() -> str:
    lines = [
        orange("><(((o>  goldfish setup"),
        water("model dock"),
        "",
        cream("Commands:") + " /model  /model list  /search  /search list  /language  /doctor  /exit",
        dim("API keys are stored in user environment variables, not project files."),
    ]
    return "\n".join(_panel(92, 7, "SETUP", lines))


def status(action: str, detail: str = "") -> str:
    suffix = f" {dim(detail)}" if detail else ""
    return f"{orange('><(((o>')} {cream(action)}{suffix}"


def telemetry(status_name: str, context_bar: str, tokens: str = "", detail: str = "") -> str:
    detail_part = f" {dim(detail)}" if detail else ""
    token_part = f"  {dim(tokens)}" if tokens else ""
    return f"{orange('><(((o>')} {cream(status_name)}{detail_part}  {water('ctx')} {green(context_bar)}{token_part}"


def prompt_telemetry(context_bar: str, tokens: str = "") -> str:
    token_part = f"  {dim(tokens)}" if tokens else ""
    return f"{water('ctx')} {green(context_bar)}{token_part}"


def prompt(name: str = "gf", telemetry: str = "") -> str:
    prefix = f"{telemetry}  " if telemetry else ""
    return prefix + green(f"{name} > ")


def farewell() -> str:
    return status("session closed")


def thinking() -> str:
    return status("thinking", "calling the configured model")


def _page(status: Mapping[str, object]) -> list[str]:
    model = str(status.get("model") or "gpt-4.1")
    provider = str(status.get("provider") or "openai")
    tools = str(status.get("tools") or "24")
    memory = str(status.get("memory") or "on")
    mode = str(status.get("status") or "ready")

    visual_state = _visual_state(mode)
    left = _left_column(visual_state)
    right = _right_column(memory=memory, tools=tools, model=model, provider=provider, mode=mode)
    rows = _join_main_columns(left, right)
    rows = rows[:CONTENT_HEIGHT] + [""] * max(0, CONTENT_HEIGHT - len(rows))

    frame_width = LEFT_WIDTH + RIGHT_WIDTH + 7
    top = orange("▘") + border("─" * (frame_width - 2)) + orange("▝")
    bottom = orange("▖") + border("─" * (frame_width - 2)) + orange("▗")
    prompt_rule = border("  " + "─" * (frame_width - 6))

    framed = [top]
    framed.extend(border("│") + " " + pad(row, frame_width - 4) + " " + border("│") for row in rows)
    framed.append(border("│") + prompt_rule + " " * max(0, frame_width - 4 - visible_len(prompt_rule)) + border(" │"))
    framed.append(bottom)
    return framed


def _left_column(visual_state: str) -> list[str]:
    hero = _hero(visual_state)
    divider = border("─" * LEFT_WIDTH)
    bottom = _join_panels(
        _quick_start_panel(),
        _tools_panel(),
        gap=2,
        width=LEFT_WIDTH,
    )
    return hero + [divider] + bottom


def _hero(visual_state: str) -> list[str]:
    wordmark = _wordmark()
    version = _version_badge("v0.1.0")
    rows: list[str] = []
    for index, line in enumerate(wordmark):
        suffix = version[index] if index < len(version) else ""
        rows.append(" " * 7 + line + "  " + suffix)
    rows.append("")
    rows.append(" " * 19 + water("small agent, sharp memory"))
    rows.append("")

    fish = get_sprite(visual_state, large=True)
    bubble = bubbles()
    water_speckles = [
        " " * 13 + hex_color("·", AQUA_DIM) + " " * 10 + hex_color("·", AQUA_DIM) + " " * 30 + hex_color("·", AQUA_DIM),
        " " * 20 + hex_color("◦", AQUA_DIM) + " " * 35 + hex_color("◦", AQUA_DIM),
        " " * 7 + hex_color("·", AQUA_DIM) + " " * 52 + hex_color("·", AQUA_DIM),
    ]
    for index in range(9):
        bubble_part = bubble[index] if index < len(bubble) else ""
        fish_part = fish[index] if index < len(fish) else ""
        drift = water_speckles[index % len(water_speckles)] if index in {0, 2, 7} else ""
        if fish_part:
            rows.append(pad(" " * 8 + bubble_part, 24) + fish_part)
        else:
            rows.append(drift)
    rows.extend(
        [
            " " * 8 + hex_color("╱╲", "#5e8b31") + "  " + hex_color("╲╱", "#7a9f3b") + "       " + dim("▁  ▁▂▁   ▁▂") + "       " + hex_color("╱╲", "#5e8b31"),
            " " * 7 + hex_color("╲╱", "#3e641f") + " " + hex_color("╱╲", "#5e8b31") + "  " + hex_color("▃▄▃", "#7d6a4a") + " " + dim("▁▂  ▁   ▁▂▁") + " " + hex_color("▃▄", "#7d6a4a") + " " + hex_color("╲╱", "#5e8b31"),
            "",
            " " * 7 + orange(".✦") + "  " + water("welcome to your intelligence companion") + "  " + orange("✦."),
            "",
        ]
    )
    return [_fit(line, LEFT_WIDTH) for line in rows[:27]]


def _visual_state(mode: str) -> str:
    if mode in {"idle", "search", "reading", "thinking", "run"}:
        return mode
    return "idle"


def _wordmark() -> list[str]:
    return [
        orange("   ▄████  ▄████  ██     █████  █████  ██  █████ ██   ██"),
        orange("  ██     ██  ██  ██     ██  ██ ██     ██ ██     ██   ██"),
        orange("  ██ ███ ██  ██  ██     ██  ██ ████   ██ ████   ███████"),
        orange("  ██  ██ ██  ██  ██     ██  ██ ██     ██    ██  ██   ██"),
        orange("   ████   ████   █████  █████  ██    ███ █████  ██   ██"),
    ]


def _version_badge(text: str) -> list[str]:
    width = len(text) + 4
    return [
        border("╭" + "─" * width + "╮"),
        border("│  ") + cream(text) + border("  │"),
        border("╰" + "─" * width + "╯"),
    ]


def _right_column(memory: str, tools: str, model: str, provider: str, mode: str) -> list[str]:
    status_rows = [
        hex_color("◉", PURPLE) + "  memory           :  " + green(memory),
        hex_color("⚒", CREAM) + "  tools            :  " + green(tools),
        hex_color("▣", BLUE) + "  model            :  " + green(model),
        hex_color("⌁", AQUA) + "  api              :  " + green(provider),
        hex_color("⌁", AQUA) + "  status           :  " + green(mode),
        hex_color("▰", ORANGE_LIGHT) + "  workspace        :  " + cream("~/workspace"),
        cream("▤") + "  session          :  " + cream("new"),
    ]
    recent_rows = [
        green("1") + "   ai-news-agent" + " " * 24 + dim("2h ago"),
        green("2") + "   startup-watch" + " " * 24 + dim("1d ago"),
        green("3") + "   paper-digest" + " " * 25 + dim("2d ago"),
        "",
        " " * 29 + water("more... (gf sessions)"),
    ]
    tips_rows = [
        orange("+") + "  type " + green("/") + " to see all commands",
        orange("+") + "  use " + border("↑") + " " + border("↓") + " to navigate history",
        orange("+") + "  ctrl + c to interrupt",
        orange("+") + "  goldfish remembers what matters",
        orange("+") + "  your data stays in your control",
        "",
        " " * 31 + orange("><(((o>") + "  " + water("° °"),
        " " * 27 + hex_color("▌▌", "#5e8b31") + dim("▁▁") + hex_color("▐▐", "#5e8b31"),
    ]
    rows: list[str] = []
    rows.extend(_panel(RIGHT_WIDTH, 13, orange("><(((o> STATUS"), status_rows))
    rows.append("")
    rows.extend(_panel(RIGHT_WIDTH, 10, orange("◷ RECENT SESSIONS") + water(" (3)"), recent_rows))
    rows.append("")
    rows.extend(_panel(RIGHT_WIDTH, 16, orange("✦ TIPS"), tips_rows))
    return rows


def _quick_start_panel() -> list[str]:
    rows = [
        green("/chat") + "      " + cream("start a conversation"),
        green("/resume") + "    " + cream("continue last task"),
        green("/memory") + "    " + cream("inspect memory"),
        green("/tools") + "     " + cream("list available tools"),
        green("/plan") + "      " + cream("create a task plan"),
        green("/help") + "      " + cream("show all commands"),
        green("/exit") + "      " + cream("quit goldfish"),
    ]
    return _panel(42, 15, orange("▸ QUICK START"), rows)


def _tools_panel() -> list[str]:
    rows = [
        water("◎") + "  web-search      " + cream("search the web"),
        cream("▤") + "  file-read       " + cream("read files"),
        orange("▰") + "  file-write      " + cream("write files"),
        border("▣") + "  shell-exec      " + cream("run shell commands"),
        cream("<>") + " code-exec       " + cream("run code"),
        hex_color("◉", PURPLE) + "  memory-save     " + cream("save to memory"),
        "",
        water("more tools via ") + green("/tools"),
    ]
    return _panel(42, 15, orange("⚒ AVAILABLE TOOLS") + water(" (6)"), rows)


def _panel(width: int, height: int, title: str, body: list[str]) -> list[str]:
    title_text = " " + title + " "
    top_fill = max(0, width - 2 - visible_len(title_text))
    top = border("╭") + title_text + border("─" * top_fill + "╮")
    inner_width = width - 4
    rows = [top]
    for line in body[: height - 2]:
        rows.append(border("│") + " " + _fit(line, inner_width) + " " + border("│"))
    while len(rows) < height - 1:
        rows.append(border("│") + " " * (width - 2) + border("│"))
    rows.append(border("╰" + "─" * (width - 2) + "╯"))
    return rows


def _join_panels(left: list[str], right: list[str], gap: int, width: int) -> list[str]:
    height = max(len(left), len(right))
    rows = []
    for index in range(height):
        left_line = left[index] if index < len(left) else ""
        right_line = right[index] if index < len(right) else ""
        rows.append(_fit(left_line, visible_len(left_line)) + " " * gap + right_line)
    return [_fit(row, width) for row in rows]


def _join_main_columns(left: list[str], right: list[str]) -> list[str]:
    height = max(len(left), len(right), CONTENT_HEIGHT)
    rows = []
    for index in range(height):
        left_line = left[index] if index < len(left) else ""
        right_line = right[index] if index < len(right) else ""
        rows.append(_fit(left_line, LEFT_WIDTH) + " " + border("│") + " " + _fit(right_line, RIGHT_WIDTH))
    return rows


def _fit(text: str, width: int) -> str:
    if visible_len(text) <= width:
        return pad(text, width)
    # Avoid cutting ANSI sequences; trim plain visible text only after color has
    # already done its job in nearby segments.
    plain = ""
    in_escape = False
    count = 0
    idx = 0
    while idx < len(text) and count < width:
        char = text[idx]
        if char == "\033":
            in_escape = True
        if not in_escape:
            count += 1
        plain += char
        if in_escape and char == "m":
            in_escape = False
        idx += 1
    return pad(plain, width)
