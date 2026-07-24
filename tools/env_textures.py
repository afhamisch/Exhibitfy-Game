"""Textures for the modular law office kit.

Neutral professional palette: warm wood and cool gray, with just enough wear
that surfaces are not dead flat. Everything tiles, and the UVs are scaled in
the geometry rather than by a texture transform, so no extensions are needed.
"""

import math
import random

from .imaging import Canvas, fbm, hex_srgb, mix
from . import glyphs

PALETTE = {
    "carpet": hex_srgb("#5A6068"),
    "carpet_dk": hex_srgb("#464B53"),
    "wall": hex_srgb("#DCD8CE"),
    "wall_dk": hex_srgb("#C2BDB1"),
    "base": hex_srgb("#4A4E55"),
    "ceiling": hex_srgb("#E8E9E6"),
    "wood": hex_srgb("#8A5A32"),
    "wood_dk": hex_srgb("#5E3A1E"),
    "wood_hi": hex_srgb("#B0794A"),
    "laminate": hex_srgb("#9AA0A8"),
    "metal": hex_srgb("#8E939B"),
    "card": hex_srgb("#C3A579"),
    "card_dk": hex_srgb("#9C7F55"),
    "plastic": hex_srgb("#26282D"),
    "paper": hex_srgb("#EFEEE9"),
    "glow": hex_srgb("#FFF6E2"),
}


def carpet(size=256, seed=61):
    """Commercial loop carpet: dense speckle, faint traffic lanes."""
    c = Canvas(size, size, PALETTE["carpet"])
    rnd = random.Random(seed)

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 90.0, v * 90.0, 2, seed) - 0.5
        m = fbm(u * 11.0, v * 11.0, 3, seed + 3) - 0.5
        col = mix(cur, PALETTE["carpet_dk"], 0.5 + m * 0.9)
        k = 1.0 + n * 0.30
        return (col[0] * k, col[1] * k, col[2] * k)
    c.shade_each(f)
    for _ in range(1800):
        x, y = rnd.random() * size, rnd.random() * size
        c.circle(x, y, rnd.uniform(0.5, 1.3),
                 PALETTE["carpet_dk"] if rnd.random() < 0.5 else (0.55, 0.57, 0.6),
                 rnd.uniform(0.05, 0.22), steps=6)
    return c


def wall_paint(size=256, seed=67):
    """Eggshell paint with a scuff line where chairs and boxes hit it."""
    c = Canvas(size, size, PALETTE["wall"])
    rnd = random.Random(seed)

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 6.0, v * 6.0, 4, seed) - 0.5
        g = fbm(u * 60.0, v * 60.0, 2, seed + 2) - 0.5
        col = mix(cur, PALETTE["wall_dk"], max(0.0, n) * 0.45)
        k = 1.0 + g * 0.05
        return (col[0] * k, col[1] * k, col[2] * k)
    c.shade_each(f)
    for _ in range(40):
        x = rnd.random() * size
        y = rnd.uniform(size * 0.62, size * 0.80)
        c.line(x, y, x + rnd.uniform(-24, 24), y + rnd.uniform(-3, 3),
               rnd.uniform(1.0, 2.6), PALETTE["wall_dk"], rnd.uniform(0.10, 0.3))
    return c


def ceiling_tile(size=256, seed=71):
    """Acoustic tile: fissured face with a shadow gap at the grid line."""
    c = Canvas(size, size, PALETTE["ceiling"])
    rnd = random.Random(seed)

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 45.0, v * 45.0, 3, seed) - 0.5
        return (cur[0] * (1 + n * 0.12), cur[1] * (1 + n * 0.12),
                cur[2] * (1 + n * 0.12))
    c.shade_each(f)
    for _ in range(500):                       # fissures
        x, y = rnd.random() * size, rnd.random() * size
        a = rnd.uniform(0, math.pi)
        l = rnd.uniform(3, 14)
        c.line(x, y, x + math.cos(a) * l, y + math.sin(a) * l,
               rnd.uniform(0.7, 1.6), (0.72, 0.73, 0.71), rnd.uniform(0.2, 0.5))
    g = size * 0.018                            # grid rails at the tile edge
    for (a, b) in ((0, g), (size - g, size)):
        c.rect(a, 0, b, size, (0.62, 0.63, 0.62), 1.0)
        c.rect(0, a, size, b, (0.62, 0.63, 0.62), 1.0)
    return c


def wood(size=256, seed=73, dark=False):
    """Warm oak: grain lines plus a few darker cathedral bands."""
    base = PALETTE["wood_dk"] if dark else PALETTE["wood"]
    c = Canvas(size, size, base)
    rnd = random.Random(seed)

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        # stretched noise = grain running along u
        n = fbm(u * 3.0, v * 60.0, 4, seed)
        band = math.sin(v * 34.0 + n * 4.0) * 0.5 + 0.5
        col = mix(cur, PALETTE["wood_dk"], band * 0.42)
        col = mix(col, PALETTE["wood_hi"], max(0.0, (n - 0.62)) * 1.1)
        return col
    c.shade_each(f)
    for _ in range(60):
        y = rnd.random() * size
        c.line(0, y, size, y + rnd.uniform(-4, 4), rnd.uniform(0.5, 1.6),
               PALETTE["wood_dk"], rnd.uniform(0.06, 0.20))
    return c


def laminate(size=128, seed=79):
    c = Canvas(size, size, PALETTE["laminate"])

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 70.0, v * 70.0, 2, seed) - 0.5
        m = fbm(u * 8.0, v * 8.0, 3, seed + 1) - 0.5
        k = 1.0 + n * 0.10 + m * 0.10
        return (cur[0] * k, cur[1] * k, cur[2] * k)
    c.shade_each(f)
    return c


def cardboard(size=256, seed=83):
    """Banker's box board: kraft tone, printed rules, a bit of scuffing."""
    c = Canvas(size, size, PALETTE["card"])
    rnd = random.Random(seed)

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 55.0, v * 12.0, 3, seed) - 0.5
        m = fbm(u * 7.0, v * 7.0, 3, seed + 4) - 0.5
        k = 1.0 + n * 0.16 + m * 0.14
        return (cur[0] * k, cur[1] * k, cur[2] * k)
    c.shade_each(f)

    # printed label block on the front face of the box
    c.rect(size * 0.14, size * 0.30, size * 0.86, size * 0.34,
           PALETTE["card_dk"], 0.85)
    c.rect(size * 0.14, size * 0.62, size * 0.86, size * 0.66,
           PALETTE["card_dk"], 0.85)
    for i in range(4):
        y = size * (0.40 + i * 0.052)
        c.rect(size * 0.18, y, size * (0.50 + 0.28 * ((i * 7) % 5) / 5.0),
               y + size * 0.016, PALETTE["card_dk"], 0.55)
    glyphs.draw_text(c, "CASE FILE", size * 0.5, size * 0.28, size * 0.055,
                     PALETTE["card_dk"], 0.10, "center", 0.9)
    for _ in range(160):
        x, y = rnd.random() * size, rnd.random() * size
        c.circle(x, y, rnd.uniform(0.7, 2.4), PALETTE["card_dk"],
                 rnd.uniform(0.04, 0.16), steps=6)
    return c


def painted_metal(size=128, seed=89):
    c = Canvas(size, size, PALETTE["metal"])
    rnd = random.Random(seed)

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 40.0, v * 40.0, 2, seed) - 0.5
        return (cur[0] * (1 + n * 0.08), cur[1] * (1 + n * 0.08),
                cur[2] * (1 + n * 0.08))
    c.shade_each(f)
    for _ in range(40):
        x, y = rnd.random() * size, rnd.random() * size
        c.line(x, y, x + rnd.uniform(-14, 14), y + rnd.uniform(-2, 2),
               rnd.uniform(0.5, 1.2), (0.70, 0.72, 0.75), rnd.uniform(0.1, 0.3))
    return c


def loose_paper(size=128, seed=97):
    """Scatter papers: mostly blank with a few ruled lines."""
    c = Canvas(size, size, PALETTE["paper"])
    rnd = random.Random(seed)

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 30.0, v * 30.0, 2, seed) - 0.5
        return (cur[0] * (1 + n * 0.05), cur[1] * (1 + n * 0.05),
                cur[2] * (1 + n * 0.05))
    c.shade_each(f)
    for i in range(9):
        y = size * (0.22 + i * 0.065)
        c.rect(size * 0.18, y, size * rnd.uniform(0.55, 0.86), y + size * 0.014,
               (0.45, 0.46, 0.50), rnd.uniform(0.35, 0.6))
    return c


def build_all():
    return {
        "env_carpet": carpet(),
        "env_wall": wall_paint(),
        "env_ceiling": ceiling_tile(),
        "env_wood": wood(),
        "env_wood_dark": wood(seed=131, dark=True),
        "env_laminate": laminate(),
        "env_cardboard": cardboard(),
        "env_metal": painted_metal(),
        "env_paper": loose_paper(),
    }
