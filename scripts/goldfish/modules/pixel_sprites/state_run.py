"""Run goldfish sprite."""

from __future__ import annotations

from .colors import AQUA, ORANGE, ORANGE_LIGHT, hex_color
from .state_idle import sprite as idle_sprite


def sprite(large: bool = False) -> list[str]:
    fish = idle_sprite(large=large)
    wake = hex_color("  · ·", AQUA)
    flame = hex_color(" ▸", ORANGE_LIGHT) + hex_color("▸", ORANGE)
    if large:
        return [wake + line + (flame if idx in {3, 4, 5} else "") for idx, line in enumerate(fish)]
    return [wake + line + (flame if idx in {2, 3} else "") for idx, line in enumerate(fish)]
