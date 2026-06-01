"""ANSI truecolor helpers for terminal-native goldfish sprites."""

from __future__ import annotations

import os
import re
import sys


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def color_enabled() -> bool:
    if os.getenv("NO_COLOR") or os.getenv("GOLDFISH_NO_COLOR"):
        return False
    return bool(getattr(sys.stdout, "isatty", lambda: False)())


def hex_color(text: str, value: str) -> str:
    if not color_enabled():
        return text
    value = value.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return f"\033[38;2;{red};{green};{blue}m{text}\033[0m"


def visible_len(text: str) -> int:
    return len(ANSI_RE.sub("", text))


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - visible_len(text))


ORANGE = "#ff8a22"
ORANGE_DARK = "#c75a14"
ORANGE_LIGHT = "#ffd083"
CREAM = "#f2e7cf"
AQUA = "#8de8f7"
AQUA_DIM = "#76b9c8"
GREEN = "#78d66b"
PURPLE = "#cc78ff"
BLUE = "#67c7e8"
BORDER = "#6e7f87"
BORDER_DIM = "#33434b"
DIM = "#8a8f91"

