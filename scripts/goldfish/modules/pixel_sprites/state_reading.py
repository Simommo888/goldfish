"""Reading goldfish sprite."""

from __future__ import annotations

from .colors import AQUA, CREAM, hex_color
from .state_idle import sprite as idle_sprite


def sprite(large: bool = False) -> list[str]:
    fish = idle_sprite(large=large)
    book = [
        hex_color("  ╭─╮╭─╮", AQUA),
        hex_color("  │·││·│", CREAM),
        hex_color("  ╰─╯╰─╯", AQUA),
    ]
    if large:
        rows = fish[:]
        rows[5] = book[0] + "  " + rows[5]
        rows[6] = book[1] + "  " + rows[6]
        rows[7] = book[2] + "  " + rows[7]
        return rows
    return [book[0]] + fish[:3] + [book[1], book[2]]
