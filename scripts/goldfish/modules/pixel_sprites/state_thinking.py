"""Thinking goldfish sprite."""

from __future__ import annotations

from .colors import ORANGE_LIGHT, hex_color
from .state_idle import sprite as idle_sprite


def sprite(large: bool = False) -> list[str]:
    fish = idle_sprite(large=large)
    bulb = hex_color("✦", ORANGE_LIGHT)
    if large:
        return ["       " + bulb + "  " + fish[0]] + fish[1:]
    return [bulb + " " + line if idx == 0 else line for idx, line in enumerate(fish)]
