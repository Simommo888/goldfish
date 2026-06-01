from __future__ import annotations

import base64
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIRS = [
    ROOT / "assets" / "startup",
    ROOT / "modules" / "assets" / "startup",
]
CACHE_DIR = ROOT / "output_cache" / "startup"
STARTUP_IMAGE = CACHE_DIR / "goldfish-startup.png"

WIDTH = 1536
HEIGHT = 1024

BG = "#02070a"
ORANGE = "#ff941f"
ORANGE_SOFT = "#ffb35a"
CYAN = "#8eeeff"
GREEN = "#73d86b"
BODY = "#f1e5d0"
MUTED = "#8a8f92"
LINE = "#5d6264"
LINE_DIM = "#33393b"


def terminal_image_protocol() -> str | None:
    """Return the best supported terminal image protocol, or None for ANSI fallback."""
    mode = os.getenv("GOLDFISH_STARTUP_RENDERER", "auto").strip().lower()
    if mode in {"ansi", "text", "off", "none"}:
        return None
    if mode in {"kitty", "sixel", "wezterm", "imgcat"}:
        return mode
    if not _stdout_is_interactive():
        return None

    term = os.getenv("TERM", "").lower()
    term_program = os.getenv("TERM_PROGRAM", "").lower()
    if os.getenv("KITTY_WINDOW_ID") or term == "xterm-kitty":
        return "kitty"
    if term_program == "wezterm" or os.getenv("WEZTERM_EXECUTABLE"):
        return "wezterm"
    if "sixel" in term or term_program in {"mlterm", "foot", "contour"}:
        return "sixel"
    return None


def print_startup_image(status: Mapping[str, object] | None = None, *, protocol: str | None = None) -> bool:
    """Render the high-fidelity startup dashboard via Kitty or Sixel.

    The ANSI startup page remains the fallback. This function never raises for
    unsupported terminals or missing image dependencies.
    """
    protocol = protocol or terminal_image_protocol()
    if protocol not in {"kitty", "sixel", "wezterm", "imgcat"}:
        return False
    try:
        image_path = render_startup_png(status)
        if protocol in {"wezterm", "imgcat"}:
            return _print_wezterm_imgcat(image_path)
        if protocol == "kitty":
            _print_kitty_png(image_path)
            return True
        if protocol == "sixel":
            _print_sixel_png(image_path)
            return True
    except Exception:
        return False
    return False


def render_startup_png(status: Mapping[str, object] | None = None, path: Path | None = None) -> Path:
    """Compose a reference-style goldfish startup dashboard as one PNG."""
    from PIL import Image, ImageDraw

    status = status or {}
    output = path or STARTUP_IMAGE
    output.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGBA", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)
    fonts = _fonts()

    _draw_outer_frame(draw)
    _draw_header(draw, fonts)
    _draw_hero(img, draw, fonts)
    _draw_status(img, draw, fonts, status)
    _draw_sessions(img, draw, fonts)
    _draw_lower_panels(img, draw, fonts)
    _draw_prompt(draw, fonts)

    img.save(output)
    return output


def _draw_outer_frame(draw: object) -> None:
    _rect(draw, 28, 28, 1508, 996, LINE, 2)
    for x, y, sx, sy in [
        (30, 30, 1, 1),
        (1506, 30, -1, 1),
        (30, 994, 1, -1),
        (1506, 994, -1, -1),
    ]:
        _filled_rect(draw, x, y, x + 4 * sx, y + 18 * sy, ORANGE)
        _filled_rect(draw, x, y, x + 18 * sx, y + 4 * sy, ORANGE)


def _draw_header(draw: object, fonts: Mapping[str, object]) -> None:
    _draw_pixel_wordmark(draw, "goldfish", 145, 44, fonts["wordmark"])

    _line(draw, 920, 38, 920, 580, LINE, 2)


def _draw_hero(img: object, draw: object, fonts: Mapping[str, object]) -> None:
    _paste_asset(img, "hero_bubbles_left.png", 120, 190, size=(150, 268))
    _paste_asset(img, "hero_goldfish.png", 278, 192, size=(466, 307))
    _paste_asset(img, "hero_aquarium_floor.png", 96, 332, size=(704, 178))
    _paste_asset(img, "hero_plant_right.png", 706, 308, size=(90, 166))

    draw.text((116, 532), ".+", font=fonts["title"], fill=ORANGE)
    draw.text((184, 528), "welcome to your intelligence companion", font=fonts["body_big"], fill=CYAN)
    draw.text((746, 532), "+.", font=fonts["title"], fill=ORANGE)
    _line(draw, 62, 570, 898, 570, LINE, 2)


def _draw_status(img: object, draw: object, fonts: Mapping[str, object], status: Mapping[str, object]) -> None:
    _box(draw, 945, 68, 1475, 343, "STATUS", fonts["title"], icon="icon_status_fish.png", img=img)
    rows = [
        ("icon_memory.png", "memory", str(status.get("memory") or "on"), GREEN),
        ("icon_wrench.png", "tools", str(status.get("tools") or "24"), GREEN),
        ("icon_model.png", "model", str(status.get("model") or "gpt-4.1"), GREEN),
        ("icon_status_wave.png", "status", str(status.get("status") or "ready"), GREEN),
        ("icon_folder.png", "workspace", str(status.get("workspace") or "~/workspace"), BODY),
        ("icon_document.png", "session", str(status.get("session") or "new"), BODY),
    ]
    y = 110
    for icon, key, value, color in rows:
        _paste_asset(img, icon, 970, y + 2, size=(28, 28))
        draw.text((1016, y), key, font=fonts["body"], fill=BODY)
        draw.text((1194, y), ":", font=fonts["body"], fill=LINE)
        draw.text((1226, y), value, font=fonts["body"], fill=color)
        y += 40


def _draw_sessions(img: object, draw: object, fonts: Mapping[str, object]) -> None:
    _box(draw, 945, 380, 1475, 565, "RECENT SESSIONS  (3)", fonts["title"], icon="icon_clock.png", img=img)
    rows = [
        ("1", "ai-news-agent", "2h ago"),
        ("2", "startup-watch", "1d ago"),
        ("3", "paper-digest", "2d ago"),
    ]
    y = 415
    for index, (num, name, age) in enumerate(rows):
        draw.text((968, y), num, font=fonts["body"], fill=GREEN)
        draw.text((1008, y), name, font=fonts["body"], fill=BODY)
        draw.text((1392, y), age, font=fonts["body"], fill=MUTED)
        if index < 2:
            _line(draw, 1008, y + 31, 1448, y + 31, LINE_DIM, 1)
        y += 43
    draw.text((1222, 530), "more... (gf sessions)", font=fonts["body"], fill=CYAN)


def _draw_lower_panels(img: object, draw: object, fonts: Mapping[str, object]) -> None:
    _box(draw, 62, 610, 488, 928, "QUICK START", fonts["title"], icon="icon_rocket.png", img=img)
    quick = [
        ("/chat", "start a conversation"),
        ("/resume", "continue last task"),
        ("/memory", "inspect memory"),
        ("/tools", "list available tools"),
        ("/plan", "create a task plan"),
        ("/help", "show all commands"),
        ("/exit", "quit goldfish"),
    ]
    _rows(draw, quick, 90, 654, 134, fonts, row_gap=40)

    _box(draw, 512, 610, 920, 928, "AVAILABLE TOOLS (6)", fonts["title"], icon="icon_wrench.png", img=img)
    tools = [
        ("web-search", "search the web"),
        ("file-read", "read files"),
        ("file-write", "write files"),
        ("shell-exec", "run shell commands"),
        ("code-exec", "run code"),
        ("memory-save", "save to memory"),
    ]
    icons = ["icon_web_search.png", "icon_file_read.png", "icon_file_write.png", "icon_shell.png", "icon_code.png", "icon_memory_save.png"]
    y = 654
    for icon, (name, desc) in zip(icons, tools):
        _paste_asset(img, icon, 538, y + 2, size=(28, 28))
        draw.text((580, y), name, font=fonts["body_small"], fill=BODY)
        draw.text((720, y), desc, font=fonts["body_small"], fill=BODY)
        y += 40
    draw.text((542, 895), "more tools via /tools", font=fonts["body_small"], fill=CYAN)

    _box(draw, 945, 610, 1475, 928, "TIPS", fonts["title"], icon="icon_bulb.png", img=img)
    tips = [
        "type / to see all commands",
        "use ↑ ↓ to navigate history",
        "ctrl + c to interrupt",
        "goldfish remembers what matters",
        "your data stays in your control",
    ]
    y = 654
    for tip in tips:
        draw.text((970, y), "+", font=fonts["body"], fill=ORANGE)
        draw.text((1006, y), tip, font=fonts["body"], fill=BODY)
        y += 48
    _paste_asset(img, "tips_goldfish_small.png", 1318, 870, size=(112, 51))
    _paste_asset(img, "tips_aquarium_floor.png", 1246, 890, size=(190, 55))


def _draw_prompt(draw: object, fonts: Mapping[str, object]) -> None:
    version = "v0.1.0"
    line_y = 950
    bbox = draw.textbbox((0, 0), version, font=fonts["body_small"])
    version_width = bbox[2] - bbox[0]
    version_center_x = (62 + 1475) // 2
    gap = 22
    _line(draw, 62, line_y, version_center_x - version_width // 2 - gap, line_y, LINE, 2)
    _line(draw, version_center_x + version_width // 2 + gap, line_y, 1475, line_y, LINE, 2)
    draw.text((version_center_x, line_y), version, font=fonts["body_small"], fill=BODY, anchor="mm")
    draw.text((62, 965), "gf >", font=fonts["prompt"], fill=GREEN)
    draw.rectangle((151, 962, 168, 992), fill=ORANGE)


def _rows(draw: object, rows: list[tuple[str, str]], x: int, y: int, gap: int, fonts: Mapping[str, object], row_gap: int = 38) -> None:
    for command, desc in rows:
        draw.text((x, y), command, font=fonts["body"], fill=GREEN)
        draw.text((x + gap, y), desc, font=fonts["body"], fill=BODY)
        y += row_gap


def _box(draw: object, x1: int, y1: int, x2: int, y2: int, title: str, title_font: object, *, icon: str = "", img: object | None = None) -> None:
    _rect(draw, x1, y1, x2, y2, LINE, 2)
    if icon and img is not None:
        _paste_asset(img, icon, x1 + 14, y1 - 13, size=(30, 30))
        title_x = x1 + 50
    else:
        title_x = x1 + 20
    draw.rectangle((title_x - 6, y1 - 18, title_x + len(title) * 18 + 18, y1 + 12), fill=BG)
    draw.text((title_x, y1 - 22), title, font=title_font, fill=ORANGE)


def _badge(draw: object, x1: int, y1: int, x2: int, y2: int, text: str, font: object) -> None:
    _rect(draw, x1, y1, x2, y2, LINE, 2)
    draw.text((x1 + 18, y1 + 9), text, font=font, fill=BODY)


def _rect(draw: object, x1: int, y1: int, x2: int, y2: int, color: str, width: int = 1) -> None:
    for offset in range(width):
        draw.rectangle((x1 + offset, y1 + offset, x2 - offset, y2 - offset), outline=color)


def _filled_rect(draw: object, x1: int, y1: int, x2: int, y2: int, color: str) -> None:
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    draw.rectangle((left, top, right, bottom), fill=color)


def _line(draw: object, x1: int, y1: int, x2: int, y2: int, color: str, width: int = 1) -> None:
    draw.line((x1, y1, x2, y2), fill=color, width=width)


def _paste_asset(img: object, name: str, x: int, y: int, *, size: tuple[int, int] | None = None) -> None:
    asset = _asset_path(name)
    if not asset:
        return
    from PIL import Image

    layer = Image.open(asset).convert("RGBA")
    if size:
        layer = layer.resize(size, Image.Resampling.NEAREST)
    img.alpha_composite(layer, (x, y))


def _draw_pixel_wordmark(draw: object, text: str, x: int, y: int, font: object) -> None:
    from PIL import Image, ImageDraw

    mask = Image.new("L", (410, 92), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.text((0, -8), text, font=font, fill=255)
    px = mask.load()
    cell = 4
    dot = 3
    shadow_offset = 4
    for yy in range(0, mask.height, cell):
        for xx in range(0, mask.width, cell):
            sample = 0
            for sy in range(yy, min(yy + cell, mask.height)):
                for sx in range(xx, min(xx + cell, mask.width)):
                    sample += px[sx, sy]
            if sample > 255 * 4:
                draw.rectangle((x + xx + shadow_offset, y + yy + shadow_offset, x + xx + shadow_offset + dot, y + yy + shadow_offset + dot), fill="#7a2a11")
                draw.rectangle((x + xx, y + yy, x + xx + dot, y + yy + dot), fill=ORANGE)


def _asset_path(name: str) -> Path | None:
    for directory in ASSET_DIRS:
        path = directory / name
        if path.exists():
            return path
    return None


def _fonts() -> dict[str, object]:
    from PIL import ImageFont

    regular = _font_path("consola.ttf")
    bold = _font_path("consolab.ttf") or regular
    return {
        "wordmark": ImageFont.truetype(str(bold), 82) if bold else ImageFont.load_default(),
        "subtitle": ImageFont.truetype(str(regular), 29) if regular else ImageFont.load_default(),
        "title": ImageFont.truetype(str(bold), 26) if bold else ImageFont.load_default(),
        "body_big": ImageFont.truetype(str(regular), 25) if regular else ImageFont.load_default(),
        "body": ImageFont.truetype(str(regular), 21) if regular else ImageFont.load_default(),
        "body_small": ImageFont.truetype(str(regular), 19) if regular else ImageFont.load_default(),
        "prompt": ImageFont.truetype(str(bold), 31) if bold else ImageFont.load_default(),
    }


def _font_path(name: str) -> Path | None:
    candidates = [
        Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name,
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        Path("/System/Library/Fonts/Menlo.ttc"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _print_kitty_png(path: Path) -> None:
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    chunks = [encoded[i : i + 4096] for i in range(0, len(encoded), 4096)]
    for index, chunk in enumerate(chunks):
        more = 1 if index < len(chunks) - 1 else 0
        if index == 0:
            prefix = f"\x1b_Ga=T,f=100,t=d,q=2,c=150,r=48,m={more};"
        else:
            prefix = f"\x1b_Gm={more};"
        sys.stdout.write(prefix + chunk + "\x1b\\")
    sys.stdout.write("\n")
    sys.stdout.flush()


def _print_sixel_png(path: Path) -> None:
    sixel = _png_to_sixel(path)
    sys.stdout.buffer.write(sixel)
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def _print_wezterm_imgcat(path: Path) -> bool:
    wezterm = os.getenv("WEZTERM_EXECUTABLE") or shutil.which("wezterm")
    if not wezterm:
        return False
    result = subprocess.run(
        [wezterm, "imgcat", "--width", "150", str(path)],
        check=False,
    )
    return result.returncode == 0


def _png_to_sixel(path: Path) -> bytes:
    from PIL import Image

    image = Image.open(path).convert("RGB")
    max_width = int(os.getenv("GOLDFISH_SIXEL_WIDTH", "960"))
    if image.width > max_width:
        height = max(1, int(image.height * (max_width / image.width)))
        image = image.resize((max_width, height), Image.Resampling.NEAREST)
    image = image.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    palette = image.getpalette() or []
    width, height = image.size

    out = io.StringIO()
    out.write("\x1bPq")
    out.write(f'"1;1;{width};{height}')
    used_colors = sorted(set(image.getdata()))
    for color_index in used_colors:
        base = color_index * 3
        r, g, b = palette[base : base + 3]
        out.write(f"#{color_index};2;{round(r * 100 / 255)};{round(g * 100 / 255)};{round(b * 100 / 255)}")

    pixels = image.load()
    for y in range(0, height, 6):
        first_color = True
        for color_index in used_colors:
            row = []
            for x in range(width):
                bits = 0
                for bit in range(6):
                    yy = y + bit
                    if yy < height and pixels[x, yy] == color_index:
                        bits |= 1 << bit
                row.append(chr(63 + bits))
            encoded = _sixel_rle(row)
            if encoded:
                if not first_color:
                    out.write("$")
                out.write(f"#{color_index}{encoded}")
                first_color = False
        out.write("-")
    out.write("\x1b\\")
    return out.getvalue().encode("ascii")


def _sixel_rle(chars: list[str]) -> str:
    while chars and chars[-1] == "?":
        chars.pop()
    if not chars:
        return ""
    result: list[str] = []
    index = 0
    while index < len(chars):
        char = chars[index]
        count = 1
        while index + count < len(chars) and chars[index + count] == char:
            count += 1
        if count >= 4:
            result.append(f"!{count}{char}")
        else:
            result.append(char * count)
        index += count
    return "".join(result)


def _stdout_is_interactive() -> bool:
    if os.getenv("GOLDFISH_FORCE_IMAGE"):
        return True
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def available_external_renderers() -> dict[str, bool]:
    return {
        "kitty": terminal_image_protocol() == "kitty",
        "sixel": terminal_image_protocol() == "sixel" or shutil.which("img2sixel") is not None,
    }
