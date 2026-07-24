"""Procedural PBR textures for the Tom Rexington FPV arms.

Every map is authored here in code so the look can be re-tuned by changing a
constant instead of round-tripping a paint package. Base-colour maps are sRGB;
metallic-roughness maps are linear (G = roughness, B = metallic) per the glTF
spec.

Palette note: BRAND holds the Exhibitfy scheme. If you have the exact logo
hexes, drop them in here -- every material and decal reads from this dict.
"""

import math
import random

from .imaging import Canvas, fbm, hex_srgb, mix, shade, value_noise
from . import glyphs

# --------------------------------------------------------------- palette

BRAND = {
    "orange": hex_srgb("#D93E15"),        # deep red-orange, primary accent
    "orange_hi": hex_srgb("#F2602B"),     # lit edge / highlight
    "orange_dk": hex_srgb("#8E230A"),     # shadowed accent
    "black": hex_srgb("#121417"),         # housing black
    "black_hi": hex_srgb("#2A2E34"),
    "ink": hex_srgb("#B8280C"),           # stamp ink
}

SKIN = {
    "base": hex_srgb("#E7B396"),
    "shadow": hex_srgb("#C98A6C"),
    "warm": hex_srgb("#DE9A7C"),
    "pale": hex_srgb("#F2C7AC"),
    "hair": hex_srgb("#6A4A34"),
}

SHIRT = {
    "white": hex_srgb("#F3F4F6"),
    "shade": hex_srgb("#D5DAE2"),
    "deep": hex_srgb("#B9C0CB"),
}


# ------------------------------------------------------------------ skin
# Atlas layout (v measured from the bottom of the image):
#   v 0.00 - 0.56  forearm band (hair, freckling, tendon shading)
#   v 0.60 - 1.00  hand band    (smooth, knuckle darkening, palm warmth)

FOREARM_V = (0.0, 0.56)
HAND_V = (0.60, 1.0)


def skin_basecolor(size=512, seed=7):
    c = Canvas(size, size, SKIN["base"])
    rnd = random.Random(seed)

    def to_y(v):
        return (1.0 - v) * size

    # --- broad tonal variation over the whole sheet
    def tone(x, y, cur):
        u = x / size
        v = 1.0 - y / size
        n = fbm(u * 5.0, v * 5.0, 4, seed)
        m = fbm(u * 17.0, v * 17.0, 3, seed + 3)
        col = mix(cur, SKIN["warm"], (n - 0.45) * 0.9)
        col = mix(col, SKIN["pale"], (m - 0.5) * 0.35)
        return col

    c.shade_each(tone)

    # --- forearm band: tendon / muscle shading running along the limb
    fy0, fy1 = to_y(FOREARM_V[1]), to_y(FOREARM_V[0])
    for i in range(4):
        u = 0.12 + i * 0.22
        x = u * size
        c.line(x - size * 0.01, fy0, x + size * 0.01, fy1,
               size * 0.055, SKIN["shadow"], 0.10)
    # wrist crease band at the far end of the forearm
    c.rect(0, fy1 - size * 0.035, size, fy1 - size * 0.012,
           SKIN["shadow"], 0.16)

    # --- hand band: knuckle darkening + palm warmth
    hy0, hy1 = to_y(HAND_V[1]), to_y(HAND_V[0])
    c.rect(0, hy0, size, hy0 + (hy1 - hy0) * 0.30, SKIN["warm"], 0.22)
    c.rect(0, hy0 + (hy1 - hy0) * 0.72, size, hy1, SKIN["pale"], 0.16)

    # --- freckles / pores everywhere, denser on the forearm
    for _ in range(1400):
        x = rnd.random() * size
        y = rnd.random() * size
        r = rnd.uniform(0.6, 1.9)
        a = rnd.uniform(0.04, 0.13)
        c.circle(x, y, r, SKIN["shadow"], a, steps=8)

    # --- subtle forearm hair: short, slightly curved strokes, mostly on the
    #     dorsal half of the sweep (u ~ 0.05 - 0.70), thinning near the wrist.
    hair_count = 2200
    for _ in range(hair_count):
        u = rnd.random()
        # density mask: peak dorsal, near-zero on the inner forearm
        dens = 0.28 + 0.72 * math.exp(-((u - 0.36) ** 2) / (2 * 0.20 ** 2))
        if rnd.random() > dens:
            continue
        v = rnd.random() * (FOREARM_V[1] - 0.02)
        # thin out towards the wrist end of the band
        if rnd.random() > 0.35 + 0.65 * (1.0 - v / FOREARM_V[1]):
            continue
        x = u * size
        y = to_y(v)
        ln = rnd.uniform(5.0, 11.0)
        ang = rnd.uniform(-0.55, 0.55) + math.pi * 0.5
        bend = rnd.uniform(-0.35, 0.35)
        pts = []
        for k in range(4):
            t = k / 3.0
            a = ang + bend * t
            pts.append((x + math.cos(a) * ln * t + math.sin(a) * bend * 2.0,
                        y - math.sin(a) * ln * t))
        col = mix(SKIN["hair"], SKIN["shadow"], rnd.random() * 0.5)
        c.curve(pts, rnd.uniform(0.7, 1.15), col, rnd.uniform(0.16, 0.34))

    return c


def skin_mr(size=128):
    """Skin is dielectric; roughness dips slightly on knuckles/tendons."""
    c = Canvas(size, size, (0.0, 0.62, 0.0))

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        r = 0.58 + fbm(u * 8.0, v * 8.0, 3, 11) * 0.16
        if v > HAND_V[0]:
            r -= 0.06
        return (0.0, r, 0.0)

    c.shade_each(f)
    return c


# ----------------------------------------------------------------- shirt


def shirt_basecolor(size=512, seed=21):
    c = Canvas(size, size, SHIRT["white"])
    rnd = random.Random(seed)

    def weave(x, y, cur):
        u, v = x / size, 1.0 - y / size
        # fine oxford weave
        w = (math.sin(x * math.pi) * 0.5 + math.sin(y * math.pi) * 0.5) * 0.012
        n = fbm(u * 40.0, v * 40.0, 2, seed) * 0.05 - 0.025
        soft = fbm(u * 3.5, v * 3.5, 4, seed + 9)
        col = mix(cur, SHIRT["shade"], max(0.0, (soft - 0.52)) * 1.35)
        return (col[0] + w + n, col[1] + w + n, col[2] + w + n * 1.2)

    c.shade_each(weave)

    # rolled-cuff area (top of the sheet) reads as denser folded cloth
    c.rect(0, 0, size, size * 0.18, SHIRT["shade"], 0.28)
    for i in range(26):
        x = rnd.random() * size
        h = size * rnd.uniform(0.02, 0.16)
        c.line(x, 0, x + rnd.uniform(-10, 10), h, rnd.uniform(1.5, 5.0),
               SHIRT["deep"], rnd.uniform(0.10, 0.22))

    # soft creases along the sleeve
    for _ in range(38):
        x0 = rnd.random() * size
        y0 = rnd.random() * size
        ln = rnd.uniform(40, 190)
        ang = rnd.uniform(-0.5, 0.5) + math.pi / 2
        pts = [(x0 + math.cos(ang) * ln * t / 3.0 + rnd.uniform(-3, 3),
                y0 + math.sin(ang) * ln * t / 3.0) for t in range(4)]
        c.curve(pts, rnd.uniform(2.0, 6.0), SHIRT["shade"],
                rnd.uniform(0.05, 0.16))
    c.box_blur(1)
    return c


def shirt_mr(size=64):
    c = Canvas(size, size, (0.0, 0.86, 0.0))

    def f(x, y, cur):
        r = 0.82 + fbm(x / size * 9.0, y / size * 9.0, 3, 31) * 0.12
        return (0.0, r, 0.0)

    c.shade_each(f)
    return c


# ------------------------------------------------------- stamp die face
# This is the hero read of the whole weapon: the face the player slams into
# the camera. Bold condensed EXHIBITFY + a rolling Bates number.


def stamp_die(size=1024, bates="000137", seed=5):
    rubber = hex_srgb("#17181C")
    rubber_hi = hex_srgb("#2C2E35")
    c = Canvas(size, size, rubber)
    rnd = random.Random(seed)

    def grain(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 60.0, v * 60.0, 3, seed) - 0.5
        return (cur[0] + n * 0.05, cur[1] + n * 0.05, cur[2] + n * 0.05)

    c.shade_each(grain)

    m = size * 0.055
    # raised plate the die sits on
    c.round_rect(m, m, size - m, size - m, size * 0.045, rubber_hi, 0.55)
    # double rule border, ink coloured
    c.round_rect(m * 1.5, m * 1.5, size - m * 1.5, size - m * 1.5,
                 size * 0.038, BRAND["orange"], 1.0)
    c.round_rect(m * 1.5 + size * 0.018, m * 1.5 + size * 0.018,
                 size - m * 1.5 - size * 0.018, size - m * 1.5 - size * 0.018,
                 size * 0.028, rubber, 1.0)
    c.round_rect(m * 2.35, m * 2.35, size - m * 2.35, size - m * 2.35,
                 size * 0.022, BRAND["orange"], 1.0)
    c.round_rect(m * 2.35 + size * 0.011, m * 2.35 + size * 0.011,
                 size - m * 2.35 - size * 0.011, size - m * 2.35 - size * 0.011,
                 size * 0.018, rubber, 1.0)

    def raised(text, x, y, sz, tracking=0.10, align="center", condense=1.0,
               color=None):
        """Ink-coloured text with a bevel so it reads as raised rubber."""
        color = color or BRAND["orange"]
        glyphs.draw_text(c, text, x + sz * 0.045, y + sz * 0.045, sz,
                         (0.0, 0.0, 0.0), tracking, align, 0.75, condense)
        glyphs.draw_text(c, text, x - sz * 0.022, y - sz * 0.022, sz,
                         BRAND["orange_hi"], tracking, align, 0.9, condense)
        glyphs.draw_text(c, text, x, y, sz, color, tracking, align, 1.0, condense)

    cx = size * 0.5
    raised("EXHIBITFY", cx, size * 0.40, size * 0.20, 0.055, condense=0.92)

    # divider rules
    c.rect(size * 0.16, size * 0.445, size * 0.84, size * 0.463,
           BRAND["orange"], 1.0)

    raised("EXHIBIT NO.", cx, size * 0.585, size * 0.085, 0.14)

    # Bates number block on its own recessed panel (the rolling wheels)
    c.round_rect(size * 0.17, size * 0.615, size * 0.83, size * 0.80,
                 size * 0.02, (0.03, 0.03, 0.035), 0.85)
    raised(bates, cx, size * 0.775, size * 0.145, 0.09)

    # tiny maker's mark
    glyphs.draw_text(c, "EXHIBITFY LEGAL TOOLS - MADE IN USA", cx,
                     size * 0.895, size * 0.038, BRAND["orange_dk"], 0.16,
                     "center", 0.85)

    # ink pooling / wear so it doesn't look like vector art
    for _ in range(240):
        x = rnd.random() * size
        y = rnd.random() * size
        c.circle(x, y, rnd.uniform(1.5, 7.0), rubber, rnd.uniform(0.05, 0.22),
                 steps=10)
    for _ in range(60):
        x = rnd.random() * size
        y = rnd.random() * size
        c.circle(x, y, rnd.uniform(2.0, 9.0), BRAND["ink"],
                 rnd.uniform(0.05, 0.18), steps=10)
    return c


def stamp_die_mr(size=256):
    c = Canvas(size, size, (0.0, 0.8, 0.0))

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        r = 0.74 + fbm(u * 30.0, v * 30.0, 3, 77) * 0.2
        return (0.0, r, 0.0)

    c.shade_each(f)
    return c


# --------------------------------------------------------- housing decal


def housing_plate(size=512, seed=13):
    """Side plate of the stamp body: black panel, orange wordmark, wear."""
    c = Canvas(size, size, BRAND["black"])
    rnd = random.Random(seed)

    def brushed(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 90.0, v * 6.0, 3, seed) - 0.5
        g = fbm(u * 4.0, v * 4.0, 3, seed + 5) - 0.5
        f = 1.0 + n * 0.22 + g * 0.18
        return (cur[0] * f, cur[1] * f, cur[2] * f)

    c.shade_each(brushed)

    # orange band across the middle carrying the wordmark
    c.rect(0, size * 0.30, size, size * 0.62, BRAND["orange"], 1.0)
    c.rect(0, size * 0.30, size, size * 0.335, BRAND["orange_hi"], 0.8)
    c.rect(0, size * 0.60, size, size * 0.62, BRAND["orange_dk"], 0.8)

    glyphs.draw_text(c, "EXHIBITFY", size * 0.5, size * 0.545, size * 0.20,
                     BRAND["black"], 0.05, "center", 1.0, 0.92)
    glyphs.draw_text(c, "BATES & DESTROY", size * 0.5, size * 0.24,
                     size * 0.062, BRAND["orange"], 0.16, "center", 1.0, 0.95)
    glyphs.draw_text(c, "MODEL EX-1  /  HEAVY DUTY", size * 0.5, size * 0.78,
                     size * 0.05, (0.62, 0.63, 0.66), 0.16, "center", 0.9)
    glyphs.draw_text(c, "SERIAL 000137", size * 0.5, size * 0.87,
                     size * 0.042, (0.45, 0.46, 0.49), 0.16, "center", 0.85)

    # bolt heads in the corners
    for (bx, by) in [(0.07, 0.09), (0.93, 0.09), (0.07, 0.91), (0.93, 0.91)]:
        x, y = bx * size, by * size
        c.circle(x, y, size * 0.028, (0.42, 0.43, 0.45), 1.0, 20)
        c.circle(x, y, size * 0.020, (0.30, 0.31, 0.33), 1.0, 20)
        c.line(x - size * 0.014, y, x + size * 0.014, y, size * 0.008,
               (0.12, 0.12, 0.13), 1.0)

    # edge wear: paint rubbed back to bare metal
    for _ in range(150):
        e = rnd.random()
        if e < 0.25:
            x, y = rnd.random() * size, rnd.uniform(0, size * 0.05)
        elif e < 0.5:
            x, y = rnd.random() * size, rnd.uniform(size * 0.95, size)
        elif e < 0.75:
            x, y = rnd.uniform(0, size * 0.05), rnd.random() * size
        else:
            x, y = rnd.uniform(size * 0.95, size), rnd.random() * size
        c.circle(x, y, rnd.uniform(1.0, 4.0), (0.55, 0.55, 0.57),
                 rnd.uniform(0.1, 0.4), steps=8)
    for _ in range(90):
        x0, y0 = rnd.random() * size, rnd.random() * size
        c.line(x0, y0, x0 + rnd.uniform(-26, 26), y0 + rnd.uniform(-6, 6),
               rnd.uniform(0.7, 1.6), (0.6, 0.6, 0.62), rnd.uniform(0.05, 0.18))
    return c


def wheel_digits(size=512, bands=6, number="000137", seed=23):
    """Digit bands for the numbering drum.

    The drum is lofted with u running around the circumference and v along the
    axle, so the glyphs are rotated a quarter turn here: each band carries a
    full 0-9 cycle, phased so `number` faces front when the tool is at rest.
    """
    steel = hex_srgb("#C7CBD2")
    c = Canvas(size, size, steel)
    rnd = random.Random(seed)

    def brushed(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 8.0, v * 90.0, 3, seed) - 0.5
        f = 1.0 + n * 0.16
        return (cur[0] * f, cur[1] * f, cur[2] * f)

    c.shade_each(brushed)

    number = (number or "0").rjust(bands, "0")[-bands:]
    band_h = size / bands
    ink = hex_srgb("#1A1B1F")
    for j in range(bands):
        # band j sits at v in [j/bands, (j+1)/bands]; v=0 is the -X end of the
        # drum, which is the leading digit of the number
        y_top = size - (j + 1) * band_h
        y_mid = y_top + band_h * 0.5
        c.rect(0, y_top, size, y_top + band_h * 0.055, hex_srgb("#8D9199"), 0.9)
        c.rect(0, y_top + band_h * 0.945, size, y_top + band_h,
               hex_srgb("#8D9199"), 0.9)
        start = int(number[j])
        for i in range(10):
            d = str((start + i) % 10)
            u_c = (0.25 + i / 10.0) % 1.0
            for off in (-1.0, 0.0, 1.0):     # wrap across the seam
                x = (u_c + off) * size
                if x < -size * 0.1 or x > size * 1.1:
                    continue
                # rotated a quarter turn: glyph height runs along -u, so the
                # anchor is pushed back half a cap height to centre it
                cap = band_h * 0.52
                glyphs.draw_text(c, d, x + cap * 0.5, y_mid, cap, ink,
                                 0.0, "center", 1.0, 1.0, 0.0, -math.pi / 2)
    for _ in range(90):
        x, y = rnd.random() * size, rnd.random() * size
        c.line(x, y, x + rnd.uniform(-3, 3), y + rnd.uniform(-30, 30),
               rnd.uniform(0.6, 1.4), (0.75, 0.76, 0.78), rnd.uniform(0.1, 0.3))
    return c


def housing_mr(size=256):
    c = Canvas(size, size, (0.0, 0.42, 0.25))

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 22.0, v * 22.0, 3, 41)
        return (0.0, 0.34 + n * 0.28, 0.18 + n * 0.25)

    c.shade_each(f)
    return c


# ------------------------------------------------------------ grip rubber


def grip_rubber(size=256, ribs=16, seed=3):
    c = Canvas(size, size, hex_srgb("#191A1E"))
    rnd = random.Random(seed)

    def base(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 70.0, v * 70.0, 3, seed) - 0.5
        return (cur[0] + n * 0.08, cur[1] + n * 0.08, cur[2] + n * 0.085)

    c.shade_each(base)

    # ribs run around the grip: bands of constant v in the loft's UV space
    step = size / ribs
    for i in range(ribs):
        y = i * step
        c.rect(0, y, size, y + step * 0.42, hex_srgb("#26282E"), 0.9)
        c.rect(0, y, size, y + step * 0.10, hex_srgb("#3A3D45"), 0.55)
        c.rect(0, y + step * 0.42, size, y + step * 0.52, (0.02, 0.02, 0.03), 0.7)
    # brand ring
    c.rect(0, size * 0.47, size, size * 0.53, BRAND["orange"], 0.95)
    for _ in range(120):
        x, y = rnd.random() * size, rnd.random() * size
        c.circle(x, y, rnd.uniform(1.0, 3.0), (0.5, 0.5, 0.52),
                 rnd.uniform(0.03, 0.12), steps=8)
    return c


def grip_mr(size=64):
    c = Canvas(size, size, (0.0, 0.9, 0.0))
    return c


# ------------------------------------------------------------ steel wear


def steel_mr(size=256, seed=17):
    """Metallic-roughness for machined steel with scratch wear."""
    c = Canvas(size, size, (0.0, 0.3, 1.0))
    rnd = random.Random(seed)

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 26.0, v * 4.0, 4, seed)
        return (0.0, 0.22 + n * 0.34, 1.0 - max(0.0, (n - 0.7)) * 0.5)

    c.shade_each(f)
    for _ in range(180):
        x0, y0 = rnd.random() * size, rnd.random() * size
        c.line(x0, y0, x0 + rnd.uniform(-40, 40), y0 + rnd.uniform(-4, 4),
               rnd.uniform(0.6, 1.8), (0.0, rnd.uniform(0.45, 0.8), 1.0),
               rnd.uniform(0.2, 0.6))
    return c


def steel_basecolor(size=256, seed=19):
    c = Canvas(size, size, hex_srgb("#B9BDC4"))

    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 30.0, v * 5.0, 4, seed) - 0.5
        return (cur[0] + n * 0.13, cur[1] + n * 0.13, cur[2] + n * 0.13)

    c.shade_each(f)
    return c


def build_all(bates="000137"):
    """Generate every texture used by the asset. Returns {name: Canvas}."""
    return {
        "skin_basecolor": skin_basecolor(),
        "skin_mr": skin_mr(),
        "shirt_basecolor": shirt_basecolor(),
        "shirt_mr": shirt_mr(),
        "stamp_die_basecolor": stamp_die(bates=bates),
        "stamp_die_mr": stamp_die_mr(),
        "housing_basecolor": housing_plate(),
        "housing_mr": housing_mr(),
        "grip_basecolor": grip_rubber(),
        "wheel_digits": wheel_digits(number=bates),
        "grip_mr": grip_mr(),
        "steel_basecolor": steel_basecolor(),
        "steel_mr": steel_mr(),
    }
