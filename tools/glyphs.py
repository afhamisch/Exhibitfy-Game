"""A hand-authored condensed bold all-caps typeface, defined as polygons.

Style target: heavy, squared, industrial -- the sort of grotesque you get on
stamp dies, road cases and legal exhibit stickers. Everything is expressed on
a 10-unit cap-height grid, so a glyph scales cleanly to any texture size.

Glyph = (advance_width, [polygon, ...]) with polygons in (x, y) grid units,
y up from the baseline.
"""

import math

CAP = 10.0        # cap height in grid units
S = 1.85          # stroke weight
W = 5.7           # default glyph width (condensed)
MID = 4.85        # centre line of the middle bar
MLO = MID - S / 2
MHI = MID + S / 2


def _r(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _v(w, x_off=0.0, top=CAP, bottom=0.0):
    """A 'V' stroke pair centred inside width w."""
    return [
        [(x_off, top), (x_off + S, top),
         (x_off + w / 2 + S / 2, bottom), (x_off + w / 2 - S / 2, bottom)],
        [(x_off + w - S, top), (x_off + w, top),
         (x_off + w / 2 + S / 2, bottom), (x_off + w / 2 - S / 2, bottom)],
    ]


def _o(w):
    return [
        _r(0, 0, S, CAP),
        _r(w - S, 0, w, CAP),
        _r(S, CAP - S, w - S, CAP),
        _r(S, 0, w - S, S),
    ]


_S_SHAPE = [
    _r(0, CAP - S, W, CAP),
    _r(0, MLO, S, CAP - S),
    _r(0, MLO, W, MHI),
    _r(W - S, S, W, MHI),
    _r(0, 0, W, S),
]

GLYPHS = {
    " ": (W * 0.55, []),
    "A": (W, [
        _r(0, 0, S, CAP - S),
        _r(W - S, 0, W, CAP - S),
        _r(0, CAP - S, W, CAP),
        _r(0, MLO, W, MHI),
    ]),
    "B": (W, [
        _r(0, 0, S, CAP),
        _r(S, CAP - S, W, CAP),
        _r(0, MLO, W * 0.98, MHI),
        _r(S, 0, W, S),
        _r(W - S, MHI, W, CAP - S),
        _r(W - S, S, W, MLO),
    ]),
    "C": (W, [
        _r(0, 0, S, CAP),
        _r(0, CAP - S, W, CAP),
        _r(0, 0, W, S),
    ]),
    "D": (W, [
        _r(0, 0, S, CAP),
        _r(S, CAP - S, W, CAP),
        _r(S, 0, W, S),
        _r(W - S, S, W, CAP - S),
    ]),
    "E": (W, [
        _r(0, 0, S, CAP),
        _r(0, CAP - S, W, CAP),
        _r(0, MLO, W * 0.9, MHI),
        _r(0, 0, W, S),
    ]),
    "F": (W, [
        _r(0, 0, S, CAP),
        _r(0, CAP - S, W, CAP),
        _r(0, MLO, W * 0.9, MHI),
    ]),
    "G": (W, [
        _r(0, 0, S, CAP),
        _r(0, CAP - S, W, CAP),
        _r(0, 0, W, S),
        _r(W - S, 0, W, MID),
        _r(W * 0.45, MID - S, W, MID),
    ]),
    "H": (W, [
        _r(0, 0, S, CAP),
        _r(W - S, 0, W, CAP),
        _r(0, MLO, W, MHI),
    ]),
    "I": (S + 0.9, [_r(0.45, 0, S + 0.45, CAP)]),
    "J": (W, [
        _r(W - S, S, W, CAP),
        _r(0, 0, W - S, S),
        _r(0, 0, S, MID * 0.7),
    ]),
    "K": (W, [
        _r(0, 0, S, CAP),
        [(S, MID + 0.2), (S, MID - S * 0.9), (W - S * 0.9, CAP), (W, CAP)],
        [(S, MID - 0.2), (S, MID + S * 0.9), (W - S * 0.9, 0), (W, 0)],
    ]),
    "L": (W, [
        _r(0, 0, S, CAP),
        _r(0, 0, W, S),
    ]),
    "M": (W + 1.3, [
        _r(0, 0, S, CAP),
        _r(W + 1.3 - S, 0, W + 1.3, CAP),
        [(0, CAP), (S, CAP), ((W + 1.3) / 2 + S * 0.45, 2.6),
         ((W + 1.3) / 2 - S * 0.45, 2.6)],
        [(W + 1.3 - S, CAP), (W + 1.3, CAP), ((W + 1.3) / 2 + S * 0.45, 2.6),
         ((W + 1.3) / 2 - S * 0.45, 2.6)],
    ]),
    "N": (W, [
        _r(0, 0, S, CAP),
        _r(W - S, 0, W, CAP),
        [(0, CAP), (S, CAP), (W, 0), (W - S, 0)],
    ]),
    "O": (W, _o(W)),
    "P": (W, [
        _r(0, 0, S, CAP),
        _r(S, CAP - S, W, CAP),
        _r(0, MLO, W, MHI),
        _r(W - S, MHI, W, CAP - S),
    ]),
    "Q": (W, _o(W) + [
        [(W - S * 1.9, S * 1.4), (W - S * 0.8, S * 1.4), (W + 0.5, -0.9),
         (W - 0.6, -0.9)],
    ]),
    "R": (W, [
        _r(0, 0, S, CAP),
        _r(S, CAP - S, W, CAP),
        _r(0, MLO, W, MHI),
        _r(W - S, MHI, W, CAP - S),
        [(S, MHI), (S + S * 0.9, MHI), (W, 0), (W - S, 0)],
    ]),
    "S": (W, _S_SHAPE),
    "T": (W, [
        _r(0, CAP - S, W, CAP),
        _r(W / 2 - S / 2, 0, W / 2 + S / 2, CAP - S),
    ]),
    "U": (W, [
        _r(0, S, S, CAP),
        _r(W - S, S, W, CAP),
        _r(0, 0, W, S),
    ]),
    "V": (W, _v(W)),
    "W": (W + 2.6, _v((W + 2.6) / 2 + 0.3, 0.0) + _v((W + 2.6) / 2 + 0.3,
                                                     (W + 2.6) / 2 - 0.3)),
    "X": (W, [
        [(0, 0), (S, 0), (W, CAP), (W - S, CAP)],
        [(W - S, 0), (W, 0), (S, CAP), (0, CAP)],
    ]),
    "Y": (W, [
        [(0, CAP), (S, CAP), (W / 2 + S / 2, MID - 0.3), (W / 2 - S / 2, MID - 0.3)],
        [(W - S, CAP), (W, CAP), (W / 2 + S / 2, MID - 0.3), (W / 2 - S / 2, MID - 0.3)],
        _r(W / 2 - S / 2, 0, W / 2 + S / 2, MID),
    ]),
    "Z": (W, [
        _r(0, CAP - S, W, CAP),
        _r(0, 0, W, S),
        [(W - S, CAP - S), (W, CAP - S), (S, S), (0, S)],
    ]),
    "0": (W, _o(W)),
    "1": (W * 0.8, [
        _r(W * 0.4 - S / 2, 0, W * 0.4 + S / 2, CAP),
        [(W * 0.4 - S / 2, CAP), (W * 0.4 - S / 2, CAP - S * 1.3),
         (W * 0.4 - S * 1.6, CAP - S * 0.55)],
        _r(0.0, 0, W * 0.8, S),
    ]),
    "2": (W, [
        _r(0, CAP - S, W, CAP),
        _r(W - S, MLO, W, CAP - S),
        _r(0, MLO, W, MHI),
        _r(0, S, S, MHI),
        _r(0, 0, W, S),
    ]),
    "3": (W, [
        _r(0, CAP - S, W, CAP),
        _r(W - S, MHI, W, CAP - S),
        _r(S * 0.2, MLO, W, MHI),
        _r(W - S, S, W, MLO),
        _r(0, 0, W, S),
    ]),
    "4": (W, [
        _r(0, MLO, S, CAP),
        _r(W - S, 0, W, CAP),
        _r(0, MLO, W, MHI),
    ]),
    "5": (W, _S_SHAPE),
    "6": (W, [
        _r(0, 0, S, CAP),
        _r(0, CAP - S, W, CAP),
        _r(0, MLO, W, MHI),
        _r(W - S, S, W, MHI),
        _r(0, 0, W, S),
    ]),
    "7": (W, [
        _r(0, CAP - S, W, CAP),
        [(W - S, CAP - S), (W, CAP - S), (S * 1.3, 0), (0.15, 0)],
    ]),
    "8": (W, _o(W) + [_r(0, MLO, W, MHI)]),
    "9": (W, [
        _r(0, MLO, S, CAP),
        _r(W - S, 0, W, CAP),
        _r(0, CAP - S, W, CAP),
        _r(0, MLO, W, MHI),
        _r(0, 0, W, S),
    ]),
    ".": (S * 1.4, [_r(0, 0, S, S)]),
    ",": (S * 1.4, [_r(0, 0, S, S), [(0, 0), (S, 0), (S * 0.2, -S * 1.1)]]),
    "-": (W * 0.8, [_r(0, MLO, W * 0.8, MHI)]),
    "/": (W * 0.9, [[(0, 0), (S, 0), (W * 0.9, CAP), (W * 0.9 - S, CAP)]]),
    ":": (S * 1.4, [_r(0, S * 0.6, S, S * 1.6 + 0.6),
                    _r(0, CAP - S * 2.2, S, CAP - S * 1.2)]),
    "#": (W + 0.6, [
        _r(0, MID - S * 1.9, W + 0.6, MID - S * 0.9),
        _r(0, MID + S * 0.9, W + 0.6, MID + S * 1.9),
        [(W * 0.24, 0), (W * 0.24 + S * 0.8, 0), (W * 0.44 + S * 0.8, CAP),
         (W * 0.44, CAP)],
        [(W * 0.58, 0), (W * 0.58 + S * 0.8, 0), (W * 0.78 + S * 0.8, CAP),
         (W * 0.78, CAP)],
    ]),
}


def text_width(text, size, tracking=0.12, condense=1.0):
    """Advance width in pixels for `text` at cap height `size`."""
    scale = size / CAP
    total = 0.0
    for i, ch in enumerate(text.upper()):
        g = GLYPHS.get(ch)
        if g is None:
            g = GLYPHS[" "]
        total += g[0] * condense * scale
        if i != len(text) - 1:
            total += tracking * size
    return total


def draw_text(canvas, text, x, y, size, color, tracking=0.12, align="left",
              alpha=1.0, condense=1.0, skew=0.0, rotate=0.0):
    """Draw `text` with baseline at y (canvas y grows downward).

    `align` is one of left / center / right. `skew` shears the glyphs for an
    italic 'action' look; `rotate` (radians) spins the whole run about (x, y).
    """
    scale = size / CAP
    total = text_width(text, size, tracking, condense)
    ca, sa = math.cos(rotate), math.sin(rotate)
    shift = 0.0
    if align == "center":
        shift = -total * 0.5
    elif align == "right":
        shift = -total
    # shift along the (possibly rotated) advance direction
    ox, oy = x + shift * ca, y + shift * sa
    pen = 0.0
    for ch in text.upper():
        g = GLYPHS.get(ch) or GLYPHS[" "]
        adv, polys = g
        for poly in polys:
            pts = []
            for (gx, gy) in poly:
                px = pen + gx * scale + gy * scale * skew
                py = -gy * scale
                pts.append((ox + px * ca - py * sa, oy + px * sa + py * ca))
            canvas.polygon(pts, color, alpha)
        pen += adv * condense * scale + tracking * size
    return total
