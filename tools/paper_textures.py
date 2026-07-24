"""Textures for the paper enemies.

Design rule throughout: every decal (faces, stamped marks) is drawn on a
paper-white background and applied as an opaque quad sitting a hair proud of
the sheet. No alpha blending anywhere -- the edges vanish against the page, and
opaque geometry is the cheapest thing a mobile renderer can draw.
"""

import math
import random

from .imaging import Canvas, fbm, hex_srgb, mix
from . import glyphs
from .textures import BRAND

PAPER = {
    "white": hex_srgb("#F4F3EF"),
    "shade": hex_srgb("#D9D7D0"),
    "ink": hex_srgb("#2A2C33"),
    "ink_soft": hex_srgb("#585C66"),
    "rule": hex_srgb("#8A8F99"),
    "red": hex_srgb("#B3202A"),
    "manila": hex_srgb("#D8C79A"),
    "board": hex_srgb("#3A4048"),
}


def _tooth(c, size, seed=3, strength=0.035):
    """Paper tooth: fine fibre noise so a big white sheet is not dead flat."""
    def f(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 120.0, v * 120.0, 2, seed) - 0.5
        m = fbm(u * 9.0, v * 9.0, 3, seed + 5) - 0.5
        k = 1.0 + n * strength + m * strength * 0.8
        return (cur[0] * k, cur[1] * k, cur[2] * k)
    c.shade_each(f)


# Atlas layout, v measured from the bottom:
#   v 0.50 - 1.00   front of the page (all the printing)
#   v 0.00 - 0.50   back of the page (faint show-through)
FRONT_V = (0.50, 1.0)
BACK_V = (0.0, 0.48)


FACE_ZONE = (0.20, 0.36, 0.80, 0.76)   # u0, t0, u1, t1 in front-page space


def pleading_page(size=1024, seed=11, case="000137", privileged=False,
                  density=1.0, title="SUPERIOR COURT OF THE STATE",
                  face_zone=FACE_ZONE):
    """Generic pleading paper: numbered left margin, caption block, text bars.

    Legible as "a legal document" at gameplay distance, which is the whole
    job -- the individual words never need to be read.
    """
    c = Canvas(size, size, PAPER["white"])
    rnd = random.Random(seed)
    _tooth(c, size, seed)

    # ---- back of the sheet (bottom half): show-through only
    def back(x, y, cur):
        v = 1.0 - y / size
        if v > BACK_V[1]:
            return cur
        return mix(cur, PAPER["shade"], 0.10)
    c.shade_each(back)

    # front page occupies the top half of the sheet
    y0, y1 = 0.0, size * 0.50
    H = y1 - y0

    def fy(t):
        return y0 + t * H

    # ---- margin rules: the instant "this is a pleading" read
    for u in (0.088, 0.104):
        c.rect(size * u, fy(0.02), size * u + size * 0.0035, fy(0.98),
               PAPER["red"] if not privileged else PAPER["red"], 0.85)
    c.rect(size * 0.945, fy(0.02), size * 0.945 + size * 0.0030, fy(0.98),
           PAPER["rule"], 0.75)

    # ---- line numbers down the left margin
    lines = 28
    for i in range(lines):
        t = 0.075 + i * (0.895 / lines)
        glyphs.draw_text(c, str(i + 1), size * 0.075, fy(t), H * 0.024,
                         PAPER["ink_soft"], 0.10, "right", 0.9)

    # ---- caption block
    cx = size * 0.55
    glyphs.draw_text(c, title, cx, fy(0.085), H * 0.030, PAPER["ink"],
                     0.12, "center", 1.0, 0.95)
    glyphs.draw_text(c, "COUNTY OF EXHIBIT", cx, fy(0.125), H * 0.028,
                     PAPER["ink"], 0.12, "center", 1.0, 0.95)
    c.rect(size * 0.16, fy(0.150), size * 0.94, fy(0.153), PAPER["ink"], 0.8)

    # party block: two columns split by a vertical rule, like a real caption
    c.rect(size * 0.55, fy(0.170), size * 0.552, fy(0.330), PAPER["ink"], 0.7)
    for i, txt in enumerate(("TOM REXINGTON, ESQ.,", "PLAINTIFF,", "V.",
                             "THE DOCUMENTS,", "DEFENDANTS.")):
        glyphs.draw_text(c, txt, size * 0.17, fy(0.195 + i * 0.030),
                         H * 0.026, PAPER["ink"], 0.10, "left", 0.95)
    glyphs.draw_text(c, "CASE NO. " + case, size * 0.58, fy(0.200),
                     H * 0.028, PAPER["ink"], 0.10, "left", 0.95)
    glyphs.draw_text(c, "DECLARATION IN", size * 0.58, fy(0.245),
                     H * 0.026, PAPER["ink"], 0.10, "left", 0.95)
    glyphs.draw_text(c, "SUPPORT OF MOTION", size * 0.58, fy(0.278),
                     H * 0.026, PAPER["ink"], 0.10, "left", 0.95)
    c.rect(size * 0.16, fy(0.345), size * 0.94, fy(0.348), PAPER["ink"], 0.8)

    # ---- body text as bars: reads as prose, costs nothing
    t = 0.385
    while t < 0.94:
        if rnd.random() < 0.12:                 # paragraph break
            t += 0.030 * density
            continue
        indent = 0.20 if rnd.random() < 0.18 else 0.135
        end = rnd.uniform(0.72, 0.93)
        if face_zone and face_zone[1] <= t <= face_zone[3]:
            # keep the face patch clear: text under an opaque decal reads as
            # a sticker stuck on the page
            if indent < face_zone[2] and end > face_zone[0]:
                if indent < face_zone[0]:
                    c.rect(size * indent, fy(t), size * face_zone[0],
                           fy(t + 0.0095), PAPER["ink_soft"],
                           rnd.uniform(0.55, 0.85))
                if end > face_zone[2]:
                    c.rect(size * face_zone[2], fy(t), size * end,
                           fy(t + 0.0095), PAPER["ink_soft"],
                           rnd.uniform(0.55, 0.85))
                t += 0.0315 * density
                continue
        c.rect(size * indent, fy(t), size * end, fy(t + 0.0095),
               PAPER["ink_soft"], rnd.uniform(0.55, 0.85))
        t += 0.0315 * density

    if privileged:
        # big diagonal marking -- unmistakable at gameplay distance
        for off, col, a in (((6, 6), (0, 0, 0), 0.28),
                            ((0, 0), PAPER["red"], 1.0)):
            glyphs.draw_text(c, "PRIVILEGED", size * 0.55 + off[0],
                             fy(0.255) + off[1], H * 0.135, col, 0.04,
                             "center", a, 0.92, 0.0, -0.30)
        c.rect(size * 0.10, fy(0.055), size * 0.98, fy(0.062), PAPER["red"], 1.0)
        glyphs.draw_text(c, "ATTORNEY-CLIENT PRIVILEGE", cx, fy(0.048),
                         H * 0.030, PAPER["red"], 0.14, "center", 1.0, 0.95)
        # a red border so the silhouette itself reads red-flagged
        for (a, b) in ((0.012, 0.018),):
            c.rect(size * a, fy(0.012), size * b, fy(0.985), PAPER["red"], 0.9)
            c.rect(size * (1 - b), fy(0.012), size * (1 - a), fy(0.985),
                   PAPER["red"], 0.9)

    # ---- honest wear: fold line, a few specks, softened corners
    c.rect(0, fy(0.50), size, fy(0.503), PAPER["shade"], 0.35)
    for _ in range(60):
        x, y = rnd.random() * size, rnd.random() * size * 0.5
        c.circle(x, y, rnd.uniform(0.6, 2.0), PAPER["shade"],
                 rnd.uniform(0.05, 0.20), steps=8)
    return c


def binder_cover(size=512, seed=17, face_zone=FACE_ZONE):
    """Dark board cover, with the face sitting on a white spine label.

    Uses the same front/back atlas split as a page. The face decal is drawn on
    paper white, so on a dark board it needs a light label to sit on -- which
    conveniently is exactly what a discovery binder has.
    """
    c = Canvas(size, size, PAPER["board"])
    rnd = random.Random(seed)

    def grain(x, y, cur):
        u, v = x / size, 1.0 - y / size
        n = fbm(u * 80.0, v * 80.0, 2, seed) - 0.5
        m = fbm(u * 7.0, v * 7.0, 3, seed + 2) - 0.5
        k = 1.0 + n * 0.16 + m * 0.20
        return (cur[0] * k, cur[1] * k, cur[2] * k)
    c.shade_each(grain)

    H = size * 0.50            # the front of the cover is the top half

    def fy(t):
        return t * H

    # ---- header, printed on the board itself
    glyphs.draw_text(c, "DISCOVERY", size * 0.5, fy(0.145), H * 0.115,
                     PAPER["white"], 0.06, "center", 1.0, 0.92)
    c.rect(size * 0.16, fy(0.175), size * 0.84, fy(0.192), BRAND["orange"], 1.0)
    glyphs.draw_text(c, "PRODUCTION VOL. II", size * 0.5, fy(0.255),
                     H * 0.055, hex_srgb("#C8CCD4"), 0.14, "center", 1.0)

    # ---- the label the face lives on
    z0, z1 = face_zone[1] - 0.045, face_zone[3] + 0.045
    c.round_rect(size * 0.135, fy(z0), size * 0.865, fy(z1), size * 0.018,
                 hex_srgb("#D6D2C6"), 1.0)
    c.round_rect(size * 0.150, fy(z0) + size * 0.012, size * 0.850,
                 fy(z1) - size * 0.012, size * 0.014, PAPER["white"], 1.0)

    # ---- footer, back on the board
    glyphs.draw_text(c, "BATES 000001 - 004812", size * 0.5, fy(0.855),
                     H * 0.050, hex_srgb("#C8CCD4"), 0.13, "center", 1.0)
    glyphs.draw_text(c, "EXHIBITFY", size * 0.5, fy(0.945), H * 0.075,
                     BRAND["orange"], 0.10, "center", 1.0, 0.92)

    # ---- punch reinforcements down the hinge side
    for ry in (0.30, 0.52, 0.74):
        c.circle(size * 0.055, fy(ry), size * 0.020, (0.62, 0.64, 0.68), 1.0, 18)
        c.circle(size * 0.055, fy(ry), size * 0.011, (0.10, 0.11, 0.13), 1.0, 16)

    for _ in range(150):
        x, y = rnd.random() * size, rnd.random() * size
        c.circle(x, y, rnd.uniform(0.8, 2.4), (0.55, 0.57, 0.60),
                 rnd.uniform(0.03, 0.14), steps=8)
    return c


# ---- faces -------------------------------------------------------------
# One atlas, 2x2. Every cell is drawn on paper white so the decal quad melts
# into the sheet. Cells (u, v from bottom-left):
#   (0,1) calm      (1,1) panic
#   (0,0) smug      (1,0) dizzy
FACE_CELLS = {
    "calm": (0.0, 0.5, 0.5, 1.0),
    "panic": (0.5, 0.5, 1.0, 1.0),
    "smug": (0.0, 0.0, 0.5, 0.5),
    "dizzy": (0.5, 0.0, 1.0, 0.5),
}


def faces(size=512, seed=29):
    c = Canvas(size, size, PAPER["white"])
    _tooth(c, size, seed, 0.025)
    ink = PAPER["ink"]
    half = size * 0.5

    def cell(col, row):
        return col * half, (1 - row) * half - half + half * (1 - 0), half

    def eye_white(cx, cy, rx, ry):
        pts = [(cx + math.cos(a * math.pi / 12) * rx,
                cy + math.sin(a * math.pi / 12) * ry) for a in range(24)]
        c.polygon(pts, (1.0, 1.0, 1.0), 1.0)
        c.polygon(pts, ink, 0.0)
        for i in range(24):     # outline
            a = pts[i]
            b = pts[(i + 1) % 24]
            c.line(a[0], a[1], b[0], b[1], size * 0.008, ink, 1.0)

    # ---------- calm / determined (top-left)
    ox, oy = 0.0, 0.0
    c.circle(ox + half * 0.34, oy + half * 0.42, half * 0.058, ink, 1.0, 20)
    c.circle(ox + half * 0.66, oy + half * 0.42, half * 0.058, ink, 1.0, 20)
    c.line(ox + half * 0.24, oy + half * 0.30, ox + half * 0.43, oy + half * 0.26,
           half * 0.030, ink, 1.0)
    c.line(ox + half * 0.57, oy + half * 0.26, ox + half * 0.76, oy + half * 0.30,
           half * 0.030, ink, 1.0)
    c.curve([(ox + half * 0.38, oy + half * 0.66), (ox + half * 0.50, oy + half * 0.70),
             (ox + half * 0.62, oy + half * 0.66)], half * 0.028, ink, 1.0)

    # ---------- panic (top-right)
    ox = half
    eye_white(ox + half * 0.34, oy + half * 0.40, half * 0.115, half * 0.135)
    eye_white(ox + half * 0.66, oy + half * 0.40, half * 0.115, half * 0.135)
    c.circle(ox + half * 0.35, oy + half * 0.43, half * 0.045, ink, 1.0, 18)
    c.circle(ox + half * 0.65, oy + half * 0.43, half * 0.045, ink, 1.0, 18)
    c.line(ox + half * 0.19, oy + half * 0.20, ox + half * 0.44, oy + half * 0.14,
           half * 0.034, ink, 1.0)
    c.line(ox + half * 0.56, oy + half * 0.14, ox + half * 0.81, oy + half * 0.20,
           half * 0.034, ink, 1.0)
    mouth = [(ox + half * (0.50 + 0.16 * math.cos(a * math.pi / 8)),
              oy + half * (0.72 + 0.115 * math.sin(a * math.pi / 8)))
             for a in range(16)]
    c.polygon(mouth, ink, 1.0)
    # sweat bead
    c.polygon([(ox + half * 0.86, oy + half * 0.30),
               (ox + half * 0.905, oy + half * 0.38),
               (ox + half * 0.815, oy + half * 0.38)],
              hex_srgb("#7FB6E8"), 0.95)
    c.circle(ox + half * 0.86, oy + half * 0.40, half * 0.045,
             hex_srgb("#7FB6E8"), 0.95, 16)

    # ---------- smug (bottom-left)
    ox, oy = 0.0, half
    c.line(ox + half * 0.24, oy + half * 0.44, ox + half * 0.44, oy + half * 0.44,
           half * 0.036, ink, 1.0)
    c.line(ox + half * 0.56, oy + half * 0.44, ox + half * 0.76, oy + half * 0.44,
           half * 0.036, ink, 1.0)
    c.line(ox + half * 0.22, oy + half * 0.26, ox + half * 0.45, oy + half * 0.30,
           half * 0.028, ink, 1.0)
    c.line(ox + half * 0.58, oy + half * 0.22, ox + half * 0.80, oy + half * 0.30,
           half * 0.028, ink, 1.0)
    c.curve([(ox + half * 0.36, oy + half * 0.68), (ox + half * 0.52, oy + half * 0.74),
             (ox + half * 0.68, oy + half * 0.62)], half * 0.030, ink, 1.0)

    # ---------- dizzy / stamped (bottom-right)
    ox = half
    for cx in (0.34, 0.66):
        for (dx, dy) in ((-1, -1), (-1, 1)):
            c.line(ox + half * (cx - 0.09 * dx), oy + half * (0.40 - 0.09 * dy),
                   ox + half * (cx + 0.09 * dx), oy + half * (0.40 + 0.09 * dy),
                   half * 0.034, ink, 1.0)
    pts = []
    for i in range(13):
        t = i / 12.0
        pts.append((ox + half * (0.34 + 0.32 * t),
                    oy + half * (0.72 + 0.05 * math.sin(t * math.pi * 3))))
    c.curve(pts, half * 0.028, ink, 1.0)
    return c


def stamp_mark(size=512, bates="000137", seed=5):
    """The impression the Bates stamp leaves: bold orange/black on paper."""
    c = Canvas(size, size, PAPER["white"])
    rnd = random.Random(seed)
    _tooth(c, size, seed, 0.03)

    ink = BRAND["orange"]
    m = size * 0.10
    c.round_rect(m, m * 1.35, size - m, size - m * 1.35, size * 0.03, ink, 1.0)
    c.round_rect(m + size * 0.022, m * 1.35 + size * 0.022,
                 size - m - size * 0.022, size - m * 1.35 - size * 0.022,
                 size * 0.02, PAPER["white"], 1.0)
    c.round_rect(m + size * 0.040, m * 1.35 + size * 0.040,
                 size - m - size * 0.040, size - m * 1.35 - size * 0.040,
                 size * 0.015, ink, 1.0)
    c.round_rect(m + size * 0.052, m * 1.35 + size * 0.052,
                 size - m - size * 0.052, size - m * 1.35 - size * 0.052,
                 size * 0.012, PAPER["white"], 1.0)

    glyphs.draw_text(c, "EXHIBITFY", size * 0.5, size * 0.44, size * 0.155,
                     ink, 0.045, "center", 1.0, 0.90)
    c.rect(size * 0.20, size * 0.475, size * 0.80, size * 0.492, ink, 1.0)
    glyphs.draw_text(c, "EXHIBIT NO.", size * 0.5, size * 0.575, size * 0.058,
                     hex_srgb("#1B1D22"), 0.14, "center", 1.0)
    glyphs.draw_text(c, bates, size * 0.5, size * 0.71, size * 0.125,
                     hex_srgb("#1B1D22"), 0.07, "center", 1.0, 0.95)

    # ink bleed and skipped patches -- a real impression is never even
    for _ in range(320):
        x, y = rnd.random() * size, rnd.random() * size
        c.circle(x, y, rnd.uniform(1.0, 4.5), PAPER["white"],
                 rnd.uniform(0.05, 0.30), steps=8)
    for _ in range(120):
        x, y = rnd.random() * size, rnd.random() * size
        c.circle(x, y, rnd.uniform(1.5, 6.0), ink, rnd.uniform(0.04, 0.16),
                 steps=8)
    return c


def build_all(bates="000137"):
    return {
        "paper_pleading": pleading_page(seed=11, case=bates),
        "paper_privileged": pleading_page(seed=23, case=bates, privileged=True),
        "paper_alt": pleading_page(seed=41, case=bates, density=1.25,
                                   title="UNITED STATES DISTRICT COURT"),
        "binder_cover": binder_cover(),
        "faces": faces(),
        "stamp_mark": stamp_mark(bates=bates),
    }
