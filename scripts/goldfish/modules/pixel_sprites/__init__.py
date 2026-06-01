"""Terminal-native goldfish state sprites."""

from __future__ import annotations

from . import state_idle, state_reading, state_run, state_search, state_thinking


def get_sprite(state: str = "idle", large: bool = False) -> list[str]:
    sprites = {
        "idle": state_idle.sprite,
        "search": state_search.sprite,
        "reading": state_reading.sprite,
        "thinking": state_thinking.sprite,
        "run": state_run.sprite,
    }
    return sprites.get(state, state_idle.sprite)(large=large)

