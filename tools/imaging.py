"""Tiny image toolkit: float RGB canvas, anti-aliased polygon fill, value
noise, and a dependency-free PNG encoder. Used to author every texture the
asset ships with, so the whole pipeline stays reproducible from source.
"""

import math
import struct
import zlib


def png_chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    return out + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_apng(frames, path, fps=30.0, loops=0):
    """Write an animated PNG -- lets the swing be reviewed as motion.

    Every frame is a full-canvas update (dispose/blend = none/source), which
    keeps the encoder trivial and the file robust in every viewer that
    understands APNG. Non-APNG viewers just see frame 0.
    """
    assert frames, "no frames"
    w, h = frames[0].w, frames[0].h
    num = max(1, int(round(1000.0 / fps)))
    out = b"\x89PNG\r\n\x1a\n"
    out += png_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    out += png_chunk(b"acTL", struct.pack(">II", len(frames), loops))
    seq = 0
    for i, f in enumerate(frames):
        data = zlib.compress(f.filtered_scanlines(), 9)
        out += png_chunk(b"fcTL", struct.pack(">IIIIIHHBB", seq, w, h, 0, 0,
                                              num, 1000, 0, 0))
        seq += 1
        if i == 0:
            out += png_chunk(b"IDAT", data)
        else:
            out += png_chunk(b"fdAT", struct.pack(">I", seq) + data)
            seq += 1
    out += png_chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(out)
    return path


# ------------------------------------------------------------------ colour


def hex_srgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def srgb_to_linear(c):
    def f(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return (f(c[0]), f(c[1]), f(c[2]))


def linear_to_srgb(c):
    def f(x):
        x = max(0.0, min(1.0, x))
        return x * 12.92 if x <= 0.0031308 else 1.055 * (x ** (1 / 2.4)) - 0.055
    return (f(c[0]), f(c[1]), f(c[2]))


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def shade(c, f):
    return (c[0] * f, c[1] * f, c[2] * f)


# ------------------------------------------------------------------ noise


def _hash2(x, y, seed):
    n = x * 374761393 + y * 668265263 + seed * 1442695040888963407
    n = (n ^ (n >> 13)) * 1274126177
    n ^= n >> 16
    return (n & 0xFFFFFF) / float(0xFFFFFF)


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def value_noise(x, y, seed=0):
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u, v = _smooth(xf), _smooth(yf)
    a = _hash2(xi, yi, seed)
    b = _hash2(xi + 1, yi, seed)
    c = _hash2(xi, yi + 1, seed)
    d = _hash2(xi + 1, yi + 1, seed)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v


def fbm(x, y, octaves=4, seed=0, gain=0.5, lacunarity=2.0):
    total, amp, norm_ = 0.0, 1.0, 0.0
    for o in range(octaves):
        total += value_noise(x, y, seed + o * 17) * amp
        norm_ += amp
        amp *= gain
        x *= lacunarity
        y *= lacunarity
    return total / norm_


# ------------------------------------------------------------------ canvas


class Canvas:
    def __init__(self, w, h, color=(0.0, 0.0, 0.0)):
        self.w = w
        self.h = h
        self.px = [0.0] * (w * h * 3)
        self.fill(color)

    def fill(self, color):
        r, g, b = color
        for i in range(0, len(self.px), 3):
            self.px[i] = r
            self.px[i + 1] = g
            self.px[i + 2] = b

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return (self.px[i], self.px[i + 1], self.px[i + 2])

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def blend(self, x, y, c, a):
        if a <= 0.0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if a > 1.0:
            a = 1.0
        i = (y * self.w + x) * 3
        self.px[i] += (c[0] - self.px[i]) * a
        self.px[i + 1] += (c[1] - self.px[i + 1]) * a
        self.px[i + 2] += (c[2] - self.px[i + 2]) * a

    # ---------------------------------------------------------- generators
    def shade_each(self, fn):
        """fn(x, y, current_rgb) -> rgb, evaluated per pixel."""
        for y in range(self.h):
            row = y * self.w * 3
            for x in range(self.w):
                i = row + x * 3
                c = fn(x, y, (self.px[i], self.px[i + 1], self.px[i + 2]))
                self.px[i] = c[0]
                self.px[i + 1] = c[1]
                self.px[i + 2] = c[2]

    # ------------------------------------------------------------- shapes
    def polygon(self, pts, color, alpha=1.0, samples=4):
        """Anti-aliased even-odd polygon fill (sub-scanline coverage)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        xs = [p[0] for p in pts]
        y0 = max(0, int(math.floor(min(ys))))
        y1 = min(self.h - 1, int(math.ceil(max(ys))))
        x0 = max(0, int(math.floor(min(xs))))
        x1 = min(self.w - 1, int(math.ceil(max(xs))))
        if y1 < y0 or x1 < x0:
            return
        width = x1 - x0 + 1
        cov = [0.0] * width
        n = len(pts)
        inv = 1.0 / samples
        for py in range(y0, y1 + 1):
            for k in range(width):
                cov[k] = 0.0
            for s in range(samples):
                sy = py + (s + 0.5) * inv
                xsec = []
                for i in range(n):
                    ax, ay = pts[i]
                    bx, by = pts[(i + 1) % n]
                    if (ay <= sy < by) or (by <= sy < ay):
                        t = (sy - ay) / (by - ay)
                        xsec.append(ax + (bx - ax) * t)
                if not xsec:
                    continue
                xsec.sort()
                for i in range(0, len(xsec) - 1, 2):
                    sxa, sxb = xsec[i], xsec[i + 1]
                    if sxb <= x0 or sxa >= x1 + 1:
                        continue
                    sxa = max(sxa, x0)
                    sxb = min(sxb, x1 + 1)
                    ia = int(math.floor(sxa))
                    ib = int(math.floor(sxb - 1e-9))
                    if ia == ib:
                        cov[ia - x0] += (sxb - sxa) * inv
                    else:
                        cov[ia - x0] += (ia + 1 - sxa) * inv
                        for px in range(ia + 1, ib):
                            cov[px - x0] += inv
                        cov[ib - x0] += (sxb - ib) * inv
            for k in range(width):
                if cov[k] > 0.0005:
                    self.blend(x0 + k, py, color, cov[k] * alpha)

    def rect(self, x0, y0, x1, y1, color, alpha=1.0):
        self.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], color, alpha)

    def round_rect(self, x0, y0, x1, y1, r, color, alpha=1.0, steps=6):
        pts = []
        corners = [
            (x1 - r, y0 + r, -math.pi / 2, 0.0),
            (x1 - r, y1 - r, 0.0, math.pi / 2),
            (x0 + r, y1 - r, math.pi / 2, math.pi),
            (x0 + r, y0 + r, math.pi, 1.5 * math.pi),
        ]
        for cx, cy, a0, a1 in corners:
            for i in range(steps + 1):
                a = a0 + (a1 - a0) * i / steps
                pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        self.polygon(pts, color, alpha)

    def circle(self, cx, cy, r, color, alpha=1.0, steps=32):
        pts = [(cx + math.cos(2 * math.pi * i / steps) * r,
                cy + math.sin(2 * math.pi * i / steps) * r) for i in range(steps)]
        self.polygon(pts, color, alpha)

    def ring(self, cx, cy, r_out, r_in, color, alpha=1.0, steps=48):
        outer = [(cx + math.cos(2 * math.pi * i / steps) * r_out,
                  cy + math.sin(2 * math.pi * i / steps) * r_out)
                 for i in range(steps + 1)]
        inner = [(cx + math.cos(2 * math.pi * i / steps) * r_in,
                  cy + math.sin(2 * math.pi * i / steps) * r_in)
                 for i in range(steps, -1, -1)]
        self.polygon(outer + inner, color, alpha)

    def line(self, x0, y0, x1, y1, width, color, alpha=1.0):
        dx, dy = x1 - x0, y1 - y0
        l = math.hypot(dx, dy)
        if l < 1e-6:
            return
        nx, ny = -dy / l * width * 0.5, dx / l * width * 0.5
        self.polygon([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                      (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], color, alpha)

    def curve(self, pts, width, color, alpha=1.0):
        for i in range(len(pts) - 1):
            self.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      width, color, alpha)

    # -------------------------------------------------------------- filters
    def box_blur(self, radius=1, passes=1):
        if radius < 1:
            return
        w, h = self.w, self.h
        for _ in range(passes):
            tmp = [0.0] * len(self.px)
            for y in range(h):
                row = y * w * 3
                for x in range(w):
                    r = g = b = 0.0
                    cnt = 0
                    for k in range(-radius, radius + 1):
                        xx = min(w - 1, max(0, x + k))
                        i = row + xx * 3
                        r += self.px[i]
                        g += self.px[i + 1]
                        b += self.px[i + 2]
                        cnt += 1
                    i = row + x * 3
                    tmp[i] = r / cnt
                    tmp[i + 1] = g / cnt
                    tmp[i + 2] = b / cnt
            out = [0.0] * len(self.px)
            for y in range(h):
                for x in range(w):
                    r = g = b = 0.0
                    cnt = 0
                    for k in range(-radius, radius + 1):
                        yy = min(h - 1, max(0, y + k))
                        i = (yy * w + x) * 3
                        r += tmp[i]
                        g += tmp[i + 1]
                        b += tmp[i + 2]
                        cnt += 1
                    i = (y * w + x) * 3
                    out[i] = r / cnt
                    out[i + 1] = g / cnt
                    out[i + 2] = b / cnt
            self.px = out

    # ---------------------------------------------------------------- io
    def filtered_scanlines(self):
        """8-bit RGB rows with a per-row PNG filter chosen by lowest cost."""
        w, h = self.w, self.h
        raw = bytearray()
        prev = bytearray(w * 3)
        for y in range(h):
            line = bytearray(w * 3)
            base = y * w * 3
            for i in range(w * 3):
                v = self.px[base + i]
                v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
                line[i] = int(v * 255.0 + 0.5)
            sub = bytearray(w * 3)
            up = bytearray(w * 3)
            for i in range(w * 3):
                left = line[i - 3] if i >= 3 else 0
                sub[i] = (line[i] - left) & 0xFF
                up[i] = (line[i] - prev[i]) & 0xFF
            costs = [
                (sum(min(b, 256 - b) for b in line), 0, line),
                (sum(min(b, 256 - b) for b in sub), 1, sub),
                (sum(min(b, 256 - b) for b in up), 2, up),
            ]
            costs.sort(key=lambda c: c[0])
            _, ftype, data = costs[0]
            raw.append(ftype)
            raw += data
            prev = line
        return bytes(raw)

    def to_png_bytes(self):
        png = b"\x89PNG\r\n\x1a\n"
        png += png_chunk(b"IHDR",
                         struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
        png += png_chunk(b"IDAT", zlib.compress(self.filtered_scanlines(), 9))
        png += png_chunk(b"IEND", b"")
        return png

    def resized(self, w, h):
        """Box-filtered downscale (used for contact sheets)."""
        out = Canvas(w, h)
        sx = self.w / w
        sy = self.h / h
        for y in range(h):
            y0 = int(y * sy)
            y1 = max(y0 + 1, int((y + 1) * sy))
            for x in range(w):
                x0 = int(x * sx)
                x1 = max(x0 + 1, int((x + 1) * sx))
                r = g = b = 0.0
                n = 0
                for yy in range(y0, min(y1, self.h)):
                    row = yy * self.w * 3
                    for xx in range(x0, min(x1, self.w)):
                        i = row + xx * 3
                        r += self.px[i]
                        g += self.px[i + 1]
                        b += self.px[i + 2]
                        n += 1
                if n:
                    out.set(x, y, (r / n, g / n, b / n))
        return out

    def blit(self, other, x, y):
        for j in range(other.h):
            ty = y + j
            if not (0 <= ty < self.h):
                continue
            for i in range(other.w):
                tx = x + i
                if 0 <= tx < self.w:
                    self.set(tx, ty, other.get(i, j))

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.to_png_bytes())
        return path

    def sample(self, u, v):
        """Bilinear sample with wrapping -- used by the preview renderer."""
        x = (u % 1.0) * self.w - 0.5
        y = (1.0 - (v % 1.0)) * self.h - 0.5
        x0 = int(math.floor(x))
        y0 = int(math.floor(y))
        fx = x - x0
        fy = y - y0
        x0 %= self.w
        y0 %= self.h
        x1 = (x0 + 1) % self.w
        y1 = (y0 + 1) % self.h
        i00 = (y0 * self.w + x0) * 3
        i10 = (y0 * self.w + x1) * 3
        i01 = (y1 * self.w + x0) * 3
        i11 = (y1 * self.w + x1) * 3
        p = self.px
        out = []
        for k in range(3):
            a = p[i00 + k] + (p[i10 + k] - p[i00 + k]) * fx
            b = p[i01 + k] + (p[i11 + k] - p[i01 + k]) * fx
            out.append(a + (b - a) * fy)
        return tuple(out)
