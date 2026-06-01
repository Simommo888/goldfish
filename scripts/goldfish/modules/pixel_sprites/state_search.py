"""Search goldfish sprite."""

from __future__ import annotations

from .colors import AQUA, ORANGE, hex_color
from .state_idle import sprite as idle_sprite


def sprite(large: bool = False) -> list[str]:
    fish = idle_sprite(large=large)
    if large:
        glass = [
            hex_color("        ◯", AQUA),
            hex_color("         ╲", AQUA),
            hex_color("          ╲", AQUA),
        ]
        rows = fish[:]
        rows[4] = rows[4] + "  " + glass[0]
        rows[5] = rows[5] + "  " + glass[1]
        rows[6] = rows[6] + "  " + glass[2]
        return rows
    return [line + ("  " + hex_color("⌕", ORANGE) if idx == 2 else "") for idx, line in enumerate(fish)]
