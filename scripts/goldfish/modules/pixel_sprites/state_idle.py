"""Idle goldfish sprite.

The mascot is intentionally sparse: it is drawn directly into the terminal
scene with ANSI truecolor and Unicode blocks, without a rectangular canvas or
image-like background.
"""

from __future__ import annotations

from .colors import AQUA_DIM, CREAM, ORANGE, ORANGE_DARK, ORANGE_LIGHT, hex_color


_FISH_LARGE = [
    "                 ▄▄▓▓▓▓▄        ▄▄        ",
    "            ▄▄▓▓▒▒░░▒▒▓▓▄   ▄▄▓▓▀         ",
    "         ▄▓▓▒░░  ▄▄  ░▒▓▓▄▄▓▓▀            ",
    "       ▄▓▓▒░   ▄████  ░▒▓▓▀               ",
    "      ▐▓▓▒░    ▀██▀  ░▒▓▓▄                ",
    "       ▀▓▓▒░░      ░▒▓▓▀▓▓▄               ",
    "          ▀▓▓▒▒░░▒▒▓▓▀   ▀▓▄              ",
    "             ▀▀▓▓▀▀        ▀              ",
]

_FISH_SMALL = [
    "        ▄▓▓▓▄    ▄▄",
    "    ▄▓▒░░▒▓▓▄▄▓▀ ",
    "   ▐▓░ ██ ░▓▓▀   ",
    "    ▀▓░░░▒▓▀▓▄   ",
    "      ▀▓▓▀   ▀   ",
]


def sprite(large: bool = False) -> list[str]:
    return _paint(_FISH_LARGE if large else _FISH_SMALL)


def _paint(lines: list[str]) -> list[str]:
    painted = []
    for line in lines:
        line = line.replace("▓", hex_color("▓", ORANGE))
        line = line.replace("▒", hex_color("▒", ORANGE_DARK))
        line = line.replace("░", hex_color("░", ORANGE_LIGHT))
        line = line.replace("█", hex_color("█", "#05090d"))
        line = line.replace("▄", hex_color("▄", ORANGE_LIGHT))
        line = line.replace("▀", hex_color("▀", CREAM))
        painted.append(line)
    return painted


def bubbles() -> list[str]:
    return [
        hex_color("      ○", AQUA_DIM),
        hex_color("  ◌       ○", AQUA_DIM),
        hex_color("       ◦", AQUA_DIM),
        hex_color("    ○", AQUA_DIM),
        hex_color("          ·", AQUA_DIM),
    ]
