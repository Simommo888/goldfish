"""Generate split PNG assets for the goldfish startup page.

The startup renderer composes these transparent pixel-art assets and then
converts the composed scene to ANSI half-block text at runtime.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "modules" / "assets" / "startup"

BG = "#02070a"
ORANGE = "#ff941f"
ORANGE_DARK = "#b94a12"
ORANGE_DEEP = "#7a2a11"
ORANGE_SOFT = "#ffb35a"
CREAM = "#ffe1a0"
CYAN = "#8eeeff"
CYAN_DIM = "#76b9c8"
GREEN = "#5e8b31"
GREEN_DARK = "#3e641f"
GREEN_SOFT = "#7a9f3b"
ROCK = "#6d5b3e"
ROCK_LIGHT = "#8a724b"
SHADOW = "#10120e"
BLACK = "#02070a"
WHITE = "#f1e5d0"

HERO_CANVAS_SIZE = [660, 200]
HERO_LAYERS = [
    {"name": "hero_bubbles_left.png", "x": 42, "y": 14},
    {"name": "hero_plant_left.png", "x": 46, "y": 112},
    {"name": "hero_plant_right.png", "x": 552, "y": 98},
    {"name": "hero_aquarium_floor.png", "x": 86, "y": 154},
    {"name": "hero_goldfish.png", "x": 162, "y": 34},
]
TIP_ASSETS = [{"name": "tips_scene.png", "role": "tips footer scene"}]


def transparent(size: tuple[int, int]) -> Image.Image:
    return Image.new("RGBA", size, (0, 0, 0, 0))


def save_pixelated(image: Image.Image, path: Path, scale: int = 5) -> None:
    small = image.resize((max(1, image.width // scale), max(1, image.height // scale)), Image.Resampling.NEAREST)
    pixelated = small.resize(image.size, Image.Resampling.NEAREST)
    pixelated.save(path)


def draw_bubbles() -> None:
    img = transparent((150, 145))
    d = ImageDraw.Draw(img)
    for x, y, r, color, width in [
        (46, 18, 10, CYAN, 4),
        (94, 56, 8, CYAN_DIM, 4),
        (63, 98, 7, CYAN_DIM, 4),
        (117, 128, 4, CYAN_DIM, 3),
        (128, 110, 3, CYAN, 2),
    ]:
        d.ellipse((x - r, y - r, x + r, y + r), outline=color, width=width)
    save_pixelated(img, OUT / "hero_bubbles_left.png")


def draw_floor() -> None:
    img = transparent((510, 46))
    d = ImageDraw.Draw(img)
    d.rectangle((88, 27, 416, 34), fill="#080909")
    for x in range(74, 435, 20):
        d.rectangle((x, 25 + (x % 4), x + 18, 30 + (x % 5)), fill=SHADOW)
    for x, y, r, c in [
        (38, 26, 13, ROCK),
        (56, 21, 9, ROCK_LIGHT),
        (408, 27, 14, ROCK),
        (430, 22, 9, ROCK_LIGHT),
    ]:
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    for x, y, r, c in [
        (83, 30, 4, ROCK_LIGHT),
        (122, 31, 4, ROCK),
        (352, 31, 4, ROCK_LIGHT),
        (377, 30, 3, ROCK),
    ]:
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    save_pixelated(img, OUT / "hero_aquarium_floor.png")


def draw_plant(path: str, flip: bool = False) -> None:
    img = transparent((90, 96))
    d = ImageDraw.Draw(img)
    for x0, y0, x1, y1, color, width in [
        (30, 92, 38, 28, GREEN_DARK, 6),
        (48, 92, 50, 10, GREEN, 7),
        (64, 92, 58, 42, GREEN_SOFT, 5),
        (40, 62, 20, 50, GREEN, 5),
        (50, 42, 66, 24, GREEN_SOFT, 5),
        (57, 73, 78, 59, GREEN, 5),
    ]:
        d.line((x0, y0, x1, y1), fill=color, width=width)
    if flip:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    save_pixelated(img, OUT / path)


def draw_goldfish(path: str, size: tuple[int, int] = (350, 135)) -> None:
    img = transparent(size)
    d = ImageDraw.Draw(img)
    sx = size[0] / 350
    sy = size[1] / 135

    def p(points: list[tuple[float, float]]) -> list[tuple[int, int]]:
        return [(int(x * sx), int(y * sy)) for x, y in points]

    def box(x0: float, y0: float, x1: float, y1: float) -> tuple[int, int, int, int]:
        return (int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy))

    for poly, color in [
        ([(238, 65), (344, 15), (318, 83)], CREAM),
        ([(238, 80), (340, 125), (316, 70)], ORANGE),
        ([(232, 72), (340, 55), (305, 98)], "#f6781d"),
    ]:
        d.polygon(p(poly), fill=color)
        d.line(p(poly + [poly[0]]), fill=ORANGE_DARK, width=max(2, int(4 * sx)))
    for x in range(270, 326, 14):
        d.line(p([(235, 72), (x, 28)]), fill=ORANGE_SOFT, width=max(1, int(3 * sx)))
        d.line(p([(235, 84), (x, 118)]), fill=ORANGE_SOFT, width=max(1, int(3 * sx)))

    d.ellipse(box(75, 25, 260, 112), fill="#f6781d", outline=ORANGE_DARK, width=max(2, int(5 * sx)))
    for poly, color in [
        ([(150, 30), (190, 0), (198, 48)], ORANGE),
        ([(118, 36), (150, 2), (162, 58)], ORANGE),
        ([(150, 103), (185, 135), (202, 105)], ORANGE),
        ([(92, 100), (112, 132), (126, 102)], "#e85d14"),
    ]:
        d.polygon(p(poly), fill=color)
        d.line(p(poly + [poly[0]]), fill=ORANGE_DARK, width=max(1, int(3 * sx)))

    for x in range(108, 222, 20):
        d.arc(box(x, 48, x + 32, 94), 95, 250, fill=ORANGE_SOFT, width=max(1, int(3 * sx)))
    for x, y, r in [(128, 42, 6), (176, 36, 5), (210, 64, 5), (154, 88, 6)]:
        d.ellipse(box(x - r, y - r, x + r, y + r), fill="#ffd083")

    d.polygon(p([(76, 66), (38, 74), (76, 90), (103, 77)]), fill=CREAM)
    d.ellipse(box(60, 55, 94, 86), fill=CREAM)
    d.ellipse(box(71, 51, 88, 71), fill=BLACK)
    d.ellipse(box(76, 55, 81, 60), fill=WHITE)
    d.line(p([(40, 80), (62, 80)]), fill=ORANGE_DEEP, width=max(2, int(4 * sx)))
    save_pixelated(img, OUT / path)


def draw_tips_scene() -> None:
    img = transparent((240, 80))
    d = ImageDraw.Draw(img)
    draw_goldfish("_tmp_tips_fish.png", (110, 45))
    fish = Image.open(OUT / "_tmp_tips_fish.png").convert("RGBA")
    img.alpha_composite(fish, (88, 12))
    for x, y, r in [(205, 10, 3), (220, 20, 5), (214, 31, 2)]:
        d.ellipse((x - r, y - r, x + r, y + r), outline=CYAN_DIM, width=2)
    for x, h, color in [(42, 34, GREEN), (54, 50, GREEN_DARK), (188, 34, GREEN_SOFT), (200, 44, GREEN)]:
        d.line((x, 72, x + 5, 72 - h), fill=color, width=4)
    for x, y, r, c in [(67, 72, 8, ROCK), (178, 72, 7, ROCK_LIGHT)]:
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    (OUT / "_tmp_tips_fish.png").unlink(missing_ok=True)
    save_pixelated(img, OUT / "tips_scene.png")


def draw_icon(name: str, kind: str, color: str) -> None:
    img = transparent((42, 42))
    d = ImageDraw.Draw(img)
    if kind == "rocket":
        d.polygon([(13, 31), (29, 8), (34, 13), (18, 35)], fill=color)
        d.ellipse((25, 10, 33, 18), fill=CYAN)
        d.polygon([(10, 33), (4, 39), (17, 36)], fill=ORANGE)
    elif kind == "brain":
        d.ellipse((8, 12, 22, 28), fill=color)
        d.ellipse((18, 9, 33, 28), fill=color)
        d.line((20, 10, 20, 32), fill=BLACK, width=3)
    elif kind == "wrench":
        d.line((11, 31, 31, 11), fill=color, width=7)
        d.ellipse((26, 6, 38, 18), outline=color, width=4)
    elif kind == "box":
        d.rectangle((11, 14, 31, 32), outline=color, width=4)
        d.line((11, 14, 21, 8, 31, 14), fill=color, width=4)
    elif kind == "wave":
        d.line((5, 23, 13, 23, 17, 13, 23, 32, 28, 23, 37, 23), fill=color, width=3)
    elif kind == "folder":
        d.rectangle((7, 16, 35, 32), fill=color)
        d.rectangle((9, 11, 22, 17), fill=color)
    elif kind == "document":
        d.rectangle((10, 7, 30, 35), outline=color, width=3)
        for y in [16, 22, 28]:
            d.line((15, y, 27, y), fill=color, width=2)
    elif kind == "clock":
        d.ellipse((8, 8, 34, 34), outline=color, width=4)
        d.line((21, 21, 21, 12), fill=color, width=3)
        d.line((21, 21, 29, 24), fill=color, width=3)
    elif kind == "bulb":
        d.ellipse((12, 7, 30, 27), fill=color)
        d.rectangle((16, 27, 26, 34), fill=CREAM)
    elif kind == "search":
        d.ellipse((8, 8, 25, 25), outline=color, width=4)
        d.line((23, 23, 34, 34), fill=color, width=5)
    elif kind == "file":
        d.rectangle((10, 7, 30, 35), outline=color, width=3)
        d.line((16, 18, 26, 18), fill=color, width=2)
    elif kind == "pencil":
        d.line((10, 32, 31, 11), fill=color, width=6)
        d.polygon([(28, 8), (35, 5), (33, 14)], fill=CREAM)
    elif kind == "shell":
        d.rectangle((8, 12, 34, 31), outline=color, width=3)
        d.line((14, 19, 20, 22, 14, 25), fill=color, width=2)
    elif kind == "code":
        d.line((16, 14, 8, 21, 16, 28), fill=color, width=3)
        d.line((26, 14, 34, 21, 26, 28), fill=color, width=3)
    save_pixelated(img, OUT / name, scale=3)


def compose_hero_scene() -> None:
    canvas = Image.new("RGBA", tuple(HERO_CANVAS_SIZE), (0, 0, 0, 0))
    for layer in HERO_LAYERS:
        canvas.alpha_composite(Image.open(OUT / layer["name"]).convert("RGBA"), (layer["x"], layer["y"]))
    canvas.save(OUT / "hero_scene.png")


def write_manifest() -> None:
    icon_names = sorted(path.name for path in OUT.glob("icon_*.png"))
    manifest = {
        "schema_version": 1,
        "theme": "goldfish dark pixel terminal",
        "background": BG,
        "hero_canvas_size": HERO_CANVAS_SIZE,
        "hero_layers": HERO_LAYERS,
        "tips_assets": TIP_ASSETS,
        "icons": icon_names,
        "rendering": "compose transparent PNG layers at runtime, then render with ANSI truecolor half-blocks",
    }
    (OUT / "asset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    draw_bubbles()
    draw_floor()
    draw_plant("hero_plant_left.png")
    draw_plant("hero_plant_right.png", flip=True)
    draw_goldfish("hero_goldfish.png")
    draw_tips_scene()
    compose_hero_scene()

    icon_specs = [
        ("icon_rocket.png", "rocket", ORANGE),
        ("icon_memory.png", "brain", "#cc78ff"),
        ("icon_wrench.png", "wrench", WHITE),
        ("icon_model.png", "box", "#67c7e8"),
        ("icon_status_wave.png", "wave", CYAN),
        ("icon_folder.png", "folder", "#ffb35a"),
        ("icon_document.png", "document", WHITE),
        ("icon_clock.png", "clock", "#b7df65"),
        ("icon_bulb.png", "bulb", "#ffd083"),
        ("icon_web_search.png", "search", "#67c7e8"),
        ("icon_file_read.png", "file", WHITE),
        ("icon_file_write.png", "pencil", "#ffd083"),
        ("icon_shell.png", "shell", WHITE),
        ("icon_code.png", "code", WHITE),
        ("icon_memory_save.png", "brain", "#cc78ff"),
    ]
    for filename, kind, color in icon_specs:
        draw_icon(filename, kind, color)
    write_manifest()
    print(f"generated startup assets in {OUT}")


if __name__ == "__main__":
    main()
