#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Goldfish agent startup page - high-fidelity Windows CMD renderer.

This file renders the uploaded design as ANSI TrueColor half-block pixels.
It is intended for Windows CMD / Windows Terminal.

Run:
  python goldfish_95_cmd.py

Recommended for 95%+ fidelity:
  - Windows Terminal or Windows 10/11 CMD with ANSI enabled
  - Font: Cascadia Mono / Consolas / JetBrains Mono
  - Terminal size: 160 columns x 54 rows or larger
  - Disable extra line spacing if your terminal allows it
"""

import os
import sys
import ctypes
import shutil
import zlib
import base64

COLS = 160
ROWS = 54
PIX_H = 108

DATA_B64 = """
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
"""

ESC = "\033["

def enable_windows_ansi():
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass

def clear():
    return ESC + "2J" + ESC + "H"

def hide_cursor():
    return ESC + "?25l"

def show_cursor():
    return ESC + "?25h"

def fg(r, g, b):
    return f"{ESC}38;2;{r};{g};{b}m"

def bg(r, g, b):
    return f"{ESC}48;2;{r};{g};{b}m"

def render():
    blob = zlib.decompress(base64.b64decode(DATA_B64))
    out = [clear(), hide_cursor()]
    reset = ESC + "0m"

    # Each terminal row uses two sampled image rows:
    # upper pixel = foreground, lower pixel = background, char = upper half block.
    for row in range(ROWS):
        upper_base = row * 2 * COLS * 3
        lower_base = (row * 2 + 1) * COLS * 3
        last_fg = None
        last_bg = None

        for col in range(COLS):
            ui = upper_base + col * 3
            li = lower_base + col * 3
            fr, fg_, fb = blob[ui], blob[ui + 1], blob[ui + 2]
            br, bg_, bb = blob[li], blob[li + 1], blob[li + 2]

            fgc = (fr, fg_, fb)
            bgc = (br, bg_, bb)

            if fgc != last_fg:
                out.append(fg(fr, fg_, fb))
                last_fg = fgc
            if bgc != last_bg:
                out.append(bg(br, bg_, bb))
                last_bg = bgc

            out.append("▀")

        out.append(reset)
        if row != ROWS - 1:
            out.append("\n")

    out.append(reset)
    out.append(show_cursor())
    return "".join(out)

def main():
    enable_windows_ansi()

    cols, rows = shutil.get_terminal_size((COLS, ROWS))
    if cols < COLS or rows < ROWS:
        sys.stdout.write(clear())
        print("Goldfish high-fidelity CMD renderer")
        print()
        print("For 95%+ fidelity, resize your terminal to at least:")
        print(f"  {COLS} columns x {ROWS} rows")
        print()
        print(f"Current terminal: {cols} columns x {rows} rows")
        print()
        print("Recommended font: Cascadia Mono or Consolas.")
        return

    # UTF-8 is required for the half-block character.
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    sys.stdout.write(render())
    sys.stdout.flush()

if __name__ == "__main__":
    main()
