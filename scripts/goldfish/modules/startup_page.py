from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from rich.console import Console
from rich.text import Text

try:
    from . import startup_cmd95
except Exception:  # pragma: no cover - fallback startup must survive optional renderer failures.
    startup_cmd95 = None


COLOR_BACKGROUND = "#02070a"
COLOR_ORANGE = "#ff941f"
COLOR_ORANGE_SOFT = "#ffb35a"
COLOR_CYAN = "#8eeeff"
COLOR_GREEN = "#73d86b"
COLOR_BODY = "#f1e5d0"
COLOR_MUTED = "#8a8f92"
COLOR_LINE = "#5d6264"
COLOR_LINE_DIM = "#33393b"
COLOR_ROCK = "#6d5b3e"
COLOR_PLANT = "#6f9a35"
COLOR_CREAM = "#ffe1a0"

CANVAS_WIDTH = 150
CANVAS_HEIGHT = 48

WORDMARK = [
    " ██████╗  ██████╗ ██╗     ██████╗ ███████╗██╗███████╗██╗  ██╗",
    "██╔════╝ ██╔═══██╗██║     ██╔══██╗██╔════╝██║██╔════╝██║  ██║",
    "██║  ███╗██║   ██║██║     ██║  ██║█████╗  ██║███████╗███████║",
    "██║   ██║██║   ██║██║     ██║  ██║██╔══╝  ██║╚════██║██╔══██║",
    "╚██████╔╝╚██████╔╝███████╗██████╔╝██║     ██║███████║██║  ██║",
    " ╚═════╝  ╚═════╝ ╚══════╝╚═════╝ ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝",
]

FISH_ROWS = [
    "                         ██████████▓▓▓        ▓▓▓▓▓▓▓▓▓▓",
    "                    ██████████████████▓▓    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓",
    "               ▓▓███████████████████████▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓",
    "            ▓▓███████▓▓████████████████████▓▓▓▓▓▓▓▓▓▓▓",
    "          ▓▓███████▓  ▓██████████████████████▓▓▓▓▓▓",
    "        ▓▓█████████▓  ▓████████████████████████▓",
    "       ▓████████████▓▓██████████████▓▓▓▓██████▓",
    "      ▓██████████████████████████▓▓      ▓████▓",
    "        ▓▓████████████████████▓▓        ▓▓████▓▓",
    "           ▓▓██████████████▓▓        ▓▓▓▓██████▓▓",
    "              ▓▓▓██████▓▓           ▓▓████████▓▓",
    "                  ▓▓▓                 ▓▓▓▓▓▓▓",
]

FISH_CREAM_OVERLAY = [
    (28, 4, "██"),
    (27, 5, "████"),
    (26, 6, "█████"),
    (27, 7, "████"),
    (28, 8, "██"),
    (52, 0, "██████"),
    (51, 1, "████████"),
    (52, 2, "██████"),
    (51, 9, "██████"),
    (50, 10, "████████"),
]

BUBBLES = [
    (17, 10, "◻", "#8eeeff"),
    (22, 12, "○", "#8eeeff"),
    (17, 14, "○", "#8eeeff"),
    (24, 16, "·", "#8eeeff"),
]

LEFT_PLANT = [
    (9, 19, "╱╲"),
    (8, 20, "╱  ╲"),
    (7, 21, "╱╲ ╱╲"),
    (8, 22, "╲╱ ╲╱"),
]

RIGHT_PLANT = [
    (72, 18, "╱╲"),
    (73, 19, "╲╲"),
    (72, 20, "╱╱╲"),
    (73, 21, "╲╱"),
]


class Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.chars = [[" " for _ in range(width)] for _ in range(height)]
        self.styles = [[COLOR_BODY for _ in range(width)] for _ in range(height)]

    def put(self, x: int, y: int, text: str, style: str = COLOR_BODY) -> None:
        if y < 0 or y >= self.height:
            return
        for offset, char in enumerate(text):
            xx = x + offset
            if 0 <= xx < self.width:
                self.chars[y][xx] = char
                self.styles[y][xx] = style

    def hline(self, x: int, y: int, width: int, style: str = COLOR_LINE, char: str = "─") -> None:
        self.put(x, y, char * max(0, width), style)

    def vline(self, x: int, y: int, height: int, style: str = COLOR_LINE, char: str = "│") -> None:
        for yy in range(y, y + height):
            self.put(x, yy, char, style)

    def box(self, x: int, y: int, width: int, height: int, title: str = "", style: str = COLOR_LINE) -> None:
        self.put(x, y, "┌" + "─" * (width - 2) + "┐", style)
        for yy in range(y + 1, y + height - 1):
            self.put(x, yy, "│", style)
            self.put(x + width - 1, yy, "│", style)
        self.put(x, y + height - 1, "└" + "─" * (width - 2) + "┘", style)
        if title:
            label = f" {title} "
            self.put(x + 2, y, label, COLOR_ORANGE)

    def render(self) -> Text:
        output = Text(no_wrap=True)
        for y, row in enumerate(self.chars):
            x = 0
            while x < self.width:
                style = self.styles[y][x]
                start = x
                while x < self.width and self.styles[y][x] == style:
                    x += 1
                output.append("".join(row[start:x]), style=style)
            if y != self.height - 1:
                output.append("\n")
        return output


def run_startup_page() -> int:
    print_startup_banner()
    return 0


def print_startup_banner(status: Mapping[str, object] | None = None, *, console: Console | None = None) -> None:
    _prefer_utf8_terminal()
    renderer_mode = os.getenv("GOLDFISH_STARTUP_RENDERER", "go").strip().lower()
    if console is None and renderer_mode not in {"ansi", "rich", "legacy", "text", "off", "none"}:
        if renderer_mode in {"go", "native", "bubbletea", "lipgloss"} and _print_go_startup(status):
            return
        if _print_cmd95_startup():
            return
    console = console or Console(color_system="truecolor", legacy_windows=False, width=CANVAS_WIDTH)
    try:
        console.clear()
    except Exception:
        pass
    console.print(build_startup_banner(status))
    console.print()


def _print_cmd95_startup() -> bool:
    if startup_cmd95 is None or not _stdout_is_interactive():
        return False
    try:
        startup_cmd95.main()
        sys.stdout.write("\n")
        sys.stdout.flush()
        return True
    except Exception:
        return False


def _print_go_startup(status: Mapping[str, object] | None = None) -> bool:
    if not _stdout_is_interactive():
        return False
    root = Path(__file__).resolve().parents[1]
    binary = root / "output_cache" / "bin" / ("goldfish-startup.exe" if os.name == "nt" else "goldfish-startup")
    source_dir = root / "tui" / "startup"
    state_path = _write_go_startup_state(root, status or {})

    command: list[str]
    cwd: Path | None = None
    if binary.exists():
        command = [str(binary), "--once"]
    elif os.getenv("GOLDFISH_STARTUP_GO_RUN", "").strip().lower() in {"1", "true", "yes", "on"} and source_dir.exists():
        command = ["go", "run", ".", "--once"]
        cwd = source_dir
    else:
        return False
    if state_path is not None:
        command.extend(["--state", str(state_path)])

    try:
        result = subprocess.run(command, cwd=str(cwd) if cwd else None, check=False)
        if result.returncode == 0:
            # The Go renderer writes a full-screen-ish static dashboard and then exits.
            # Return the real Python input prompt to the left edge on the next line,
            # otherwise input(...) can continue at the child process' final cursor cell.
            sys.stdout.write("\x1b[0m\r\n")
            sys.stdout.flush()
            return True
        return False
    except Exception:
        return False


def _write_go_startup_state(root: Path, status: Mapping[str, object]) -> Path | None:
    output = root / "output_cache" / "startup" / "startup_state.json"
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        safe = {
            key: value
            for key, value in dict(status).items()
            if key not in {"api_key", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "AI_NEWS_LLM_API_KEY"}
        }
        output.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
        return output
    except Exception:
        return None


def build_startup_banner(status: Mapping[str, object] | None = None) -> Text:
    status = status or {}
    canvas = Canvas(CANVAS_WIDTH, CANVAS_HEIGHT)

    _draw_outer_frame(canvas)
    _draw_header(canvas)
    _draw_hero(canvas)
    _draw_status(canvas, status)
    _draw_sessions(canvas)
    _draw_lower_panels(canvas)
    _draw_prompt(canvas)

    return canvas.render()


def _draw_outer_frame(c: Canvas) -> None:
    c.box(2, 1, 146, 46, style=COLOR_LINE)
    c.put(2, 1, "▛", COLOR_ORANGE)
    c.put(147, 1, "▜", COLOR_ORANGE)
    c.put(2, 46, "▙", COLOR_ORANGE)
    c.put(147, 46, "▟", COLOR_ORANGE)


def _draw_header(c: Canvas) -> None:
    for index, line in enumerate(WORDMARK):
        c.put(13, 3 + index, line, COLOR_ORANGE)
    c.vline(89, 2, 25, COLOR_LINE)


def _draw_hero(c: Canvas) -> None:
    for x, y, char, style in BUBBLES:
        c.put(x, y, char, style)
    for x, y, text in LEFT_PLANT:
        c.put(x, y, text, COLOR_PLANT)
    for x, y, text in RIGHT_PLANT:
        c.put(x, y, text, COLOR_PLANT)
    c.put(10, 23, "▄▄▄   ▄▄                    ▄▄▄   ▄▄", COLOR_ROCK)
    c.put(12, 24, "▀▀▀▄▄▄▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▄▄▄▀▀▀", COLOR_LINE_DIM)

    for row_index, row in enumerate(FISH_ROWS):
        c.put(18, 11 + row_index, row, COLOR_ORANGE)
    for x, y, text in FISH_CREAM_OVERLAY:
        c.put(18 + x, 11 + y, text, COLOR_CREAM)
    c.put(32, 16, "██", "#02070a")
    c.put(33, 16, "▌", COLOR_BODY)
    c.put(29, 18, "▅", COLOR_CREAM)

    c.put(11, 26, ".+", COLOR_ORANGE)
    c.put(18, 26, "welcome to your intelligence companion", COLOR_CYAN)
    c.put(75, 26, "+.", COLOR_ORANGE)
    c.hline(6, 28, 82, COLOR_LINE)


def _draw_status(c: Canvas, status: Mapping[str, object]) -> None:
    c.box(92, 3, 54, 14, "><(((o> STATUS", COLOR_LINE)
    rows = [
        ("◈", "memory", str(status.get("memory") or "on"), COLOR_GREEN),
        ("⌁", "tools", str(status.get("tools") or "24"), COLOR_GREEN),
        ("◇", "model", str(status.get("model") or "gpt-4.1"), COLOR_GREEN),
        ("⌁", "status", str(status.get("status") or "ready"), COLOR_GREEN),
        ("▣", "workspace", "~/workspace", COLOR_BODY),
        ("▤", "session", "new", COLOR_BODY),
    ]
    for index, (icon, key, value, value_style) in enumerate(rows):
        y = 5 + index * 2
        c.put(95, y, icon, _status_icon_color(icon))
        c.put(99, y, key, COLOR_BODY)
        c.put(117, y, ":", COLOR_LINE)
        c.put(120, y, value, value_style)


def _draw_sessions(c: Canvas) -> None:
    c.box(92, 18, 54, 10, "RECENT SESSIONS  (3)", COLOR_LINE)
    rows = [
        ("1", "ai-news-agent", "2h ago"),
        ("2", "startup-watch", "1d ago"),
        ("3", "paper-digest", "2d ago"),
    ]
    for index, (num, name, age) in enumerate(rows):
        y = 20 + index * 2
        c.put(95, y, num, COLOR_GREEN)
        c.put(99, y, name, COLOR_BODY)
        c.put(137, y, age, COLOR_MUTED)
        if index < 2:
            c.hline(98, y + 1, 43, COLOR_LINE_DIM, "┄")
    c.put(122, 26, "more... (gf sessions)", COLOR_CYAN)


def _draw_lower_panels(c: Canvas) -> None:
    c.box(6, 30, 42, 16, "» QUICK START", COLOR_LINE)
    quick = [
        ("/chat", "start a conversation"),
        ("/resume", "continue last task"),
        ("/memory", "inspect memory"),
        ("/tools", "list available tools"),
        ("/plan", "create a task plan"),
        ("/help", "show all commands"),
        ("/exit", "quit goldfish"),
    ]
    _draw_command_rows(c, 9, 32, quick)

    c.box(50, 30, 39, 16, "⌁ AVAILABLE TOOLS (6)", COLOR_LINE)
    tools = [
        ("web-search", "search the web"),
        ("file-read", "read files"),
        ("file-write", "write files"),
        ("shell-exec", "run shell commands"),
        ("code-exec", "run code"),
        ("memory-save", "save to memory"),
        ("/tools", "more tools"),
    ]
    _draw_command_rows(c, 53, 32, tools, gap=19)

    c.box(92, 30, 54, 16, "✶ TIPS", COLOR_LINE)
    tips = [
        "type / to see all commands",
        "use ↑ ↓ to navigate history",
        "ctrl + c to interrupt",
        "goldfish remembers what matters",
        "your data stays in your control",
    ]
    for index, tip in enumerate(tips):
        c.put(95, 32 + index * 2, "+", COLOR_ORANGE)
        c.put(99, 32 + index * 2, tip, COLOR_BODY)
    c.put(124, 41, "><(((o>", COLOR_ORANGE)
    c.put(137, 41, "○ ○", COLOR_CYAN)
    c.put(121, 42, "╱╲   ▄▄   ╱╲", COLOR_PLANT)
    c.put(119, 43, "━━━━━━▀▀━━━━━━", COLOR_LINE_DIM)


def _draw_command_rows(c: Canvas, x: int, y: int, rows: list[tuple[str, str]], gap: int = 13) -> None:
    for index, (command, description) in enumerate(rows):
        yy = y + index * 2
        c.put(x, yy, command, COLOR_GREEN)
        c.put(x + gap, yy, description, COLOR_BODY)


def _draw_prompt(c: Canvas) -> None:
    c.hline(6, 46, 62, COLOR_LINE)
    c.put(69, 46, " v0.1.0 ", COLOR_BODY)
    c.hline(80, 46, 64, COLOR_LINE)
    c.put(6, 46, "gf >", COLOR_GREEN)
    c.put(11, 46, "█", COLOR_ORANGE)


def _status_icon_color(icon: str) -> str:
    return {
        "◈": "#cc78ff",
        "⌁": COLOR_CYAN,
        "◇": "#67c7e8",
        "▣": COLOR_ORANGE_SOFT,
        "▤": COLOR_BODY,
    }.get(icon, COLOR_BODY)


def _workspace() -> Path:
    return Path(os.getenv("GOLDFISH_ROOT") or os.getcwd())


def _prefer_utf8_terminal() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _stdout_is_interactive() -> bool:
    if os.getenv("GOLDFISH_FORCE_STARTUP_RENDERER"):
        return True
    return bool(getattr(sys.stdout, "isatty", lambda: False)())
