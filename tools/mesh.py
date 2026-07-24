"""Quad-first mesh construction.

Meshes are built from lofted rings so every part comes out as continuous edge
loops (the thing you want when this gets skinned/animated later). Quads are
kept as quads internally -- the OBJ export writes them verbatim, the glTF
export triangulates on the way out.

Smoothing is controlled per face via a "shading group" id. Normals are
averaged per (welded position, group), so UV seams and duplicated seam columns
still shade seamlessly, while a group change gives a hard edge.
"""

import math

from . import vec


class Mesh:
    def __init__(self, name, material):
        self.name = name
        self.material = material
        self.pos = []          # list[(x, y, z)]
        self.uv = []           # list[(u, v)]
        self.faces = []        # list[(tuple_of_indices, group_id)]
        self._group = 0

    # -------------------------------------------------------------- basics
    def group(self, gid):
        """Set the shading group used by subsequently added faces."""
        self._group = gid
        return self

    def add_vertex(self, p, uv=(0.0, 0.0)):
        self.pos.append((float(p[0]), float(p[1]), float(p[2])))
        self.uv.append((float(uv[0]), float(uv[1])))
        return len(self.pos) - 1

    def add_face(self, idx, group=None):
        self.faces.append((tuple(idx), self._group if group is None else group))

    def transform(self, m):
        self.pos = [vec.xform_point(m, p) for p in self.pos]
        return self

    def stats(self):
        quads = sum(1 for f, _ in self.faces if len(f) == 4)
        tris = sum(1 for f, _ in self.faces if len(f) == 3)
        return {
            "verts": len(self.pos),
            "quads": quads,
            "tris": tris,
            "triangles": quads * 2 + tris,
        }

    # --------------------------------------------------------------- lofts
    def add_ring_strip(self, ring_a, ring_b, uv_a, uv_b, group=None):
        """Bridge two equal-length vertex rows with quads."""
        assert len(ring_a) == len(ring_b)
        base = len(self.pos)
        for p, t in zip(ring_a, uv_a):
            self.add_vertex(p, t)
        for p, t in zip(ring_b, uv_b):
            self.add_vertex(p, t)
        n = len(ring_a)
        for i in range(n - 1):
            a0 = base + i
            a1 = base + i + 1
            b0 = base + n + i
            b1 = base + n + i + 1
            self.add_face((a0, a1, b1, b0), group)

    def add_loft(self, rings, v_coords=None, uv_rect=(0.0, 0.0, 1.0, 1.0),
                 group=None, flip=False):
        """Loft a list of rings (each a list of points, seam vertex duplicated).

        Returns the index of the first vertex of each ring, so callers can
        stitch caps or branches onto specific loops.
        """
        u0, v0, u1, v1 = uv_rect
        n = len(rings[0])
        if v_coords is None:
            # arc-length parameterisation keeps texel density even along the loft
            lengths = [0.0]
            for i in range(1, len(rings)):
                c_prev = _centroid(rings[i - 1])
                c_cur = _centroid(rings[i])
                lengths.append(lengths[-1] + vec.length(vec.sub(c_cur, c_prev)))
            total = lengths[-1] if lengths[-1] > 1e-9 else 1.0
            v_coords = [l / total for l in lengths]

        starts = []
        for r, ring in enumerate(rings):
            starts.append(len(self.pos))
            vv = v0 + (v1 - v0) * v_coords[r]
            for i, p in enumerate(ring):
                uu = u0 + (u1 - u0) * (i / (n - 1))
                self.add_vertex(p, (uu, vv))

        for r in range(len(rings) - 1):
            a = starts[r]
            b = starts[r + 1]
            for i in range(n - 1):
                if flip:
                    self.add_face((a + i, b + i, b + i + 1, a + i + 1), group)
                else:
                    self.add_face((a + i, a + i + 1, b + i + 1, b + i), group)
        return starts

    def add_cap(self, ring, center=None, uv_center=(0.5, 0.5), radius_uv=0.45,
                group=None, flip=False):
        """Triangle fan cap for an open ring (seam vertex duplicated)."""
        pts = ring[:-1]
        if center is None:
            center = _centroid(pts)
        base = len(self.pos)
        ci = self.add_vertex(center, uv_center)
        n = len(pts)
        for i, p in enumerate(pts):
            ang = 2.0 * math.pi * i / n
            self.add_vertex(p, (uv_center[0] + math.cos(ang) * radius_uv,
                                uv_center[1] + math.sin(ang) * radius_uv))
        for i in range(n):
            a = base + 1 + i
            b = base + 1 + (i + 1) % n
            if flip:
                self.add_face((ci, b, a), group)
            else:
                self.add_face((ci, a, b), group)

    def add_grid_cap(self, ring, group=None, flip=False, dish=0.0):
        """Cap a tube end with a fan, optionally dished in slightly.

        `dish` pulls the centre vertex back along the ring's own axis, which
        keeps flat caps from reading as perfectly hard discs under specular.
        """
        pts = ring[:-1]
        c = _centroid(pts)
        if dish:
            # move the centre along the ring normal
            n = len(pts)
            nx = ny = nz = 0.0
            for i in range(n):
                a, b = pts[i], pts[(i + 1) % n]
                nx += (a[1] - b[1]) * (a[2] + b[2])
                ny += (a[2] - b[2]) * (a[0] + b[0])
                nz += (a[0] - b[0]) * (a[1] + b[1])
            l = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            c = (c[0] + nx / l * dish, c[1] + ny / l * dish, c[2] + nz / l * dish)
        return self.add_cap(ring, center=c, group=group, flip=flip)


def _centroid(pts):
    n = len(pts)
    return (
        sum(p[0] for p in pts) / n,
        sum(p[1] for p in pts) / n,
        sum(p[2] for p in pts) / n,
    )


# ------------------------------------------------------------------ profiles
# A profile is a list of (u, v) 2D coordinates in the ring plane. Rings always
# repeat the first point at the end so the UV seam is explicit.


def profile_ellipse(n, rx, ry, phase=0.0):
    pts = []
    for i in range(n + 1):
        a = phase + 2.0 * math.pi * (i % n) / n
        pts.append((math.cos(a) * rx, math.sin(a) * ry))
    return pts


def profile_super(n, rx, ry, e=2.6, phase=0.0):
    """Superellipse -- rounded-rectangle cross sections (forearms, palms)."""
    pts = []
    p = 2.0 / e
    for i in range(n + 1):
        a = phase + 2.0 * math.pi * (i % n) / n
        ca, sa = math.cos(a), math.sin(a)
        x = math.copysign(abs(ca) ** p, ca) * rx
        y = math.copysign(abs(sa) ** p, sa) * ry
        pts.append((x, y))
    return pts


def profile_round_rect(n, w, h, r):
    """Rounded rectangle sampled at n points, evenly by perimeter."""
    hw = max(1e-5, w * 0.5 - r)
    hh = max(1e-5, h * 0.5 - r)
    corners = [(hw, hh), (-hw, hh), (-hw, -hh), (hw, -hh)]
    straight = [2 * hw, 2 * hh, 2 * hw, 2 * hh]
    arc = 0.5 * math.pi * r
    perim = sum(straight) + 4 * arc
    pts = []
    for i in range(n + 1):
        d = perim * (i % n) / n
        # walk: top edge, left arc, left edge, ... starting at (hw, hh)
        seq = [
            ("edge", (hw, hh), (-hw, hh), straight[0]),
            ("arc", (-hw, hh), 0.5 * math.pi, arc),
            ("edge", (-hw, hh), (-hw, -hh), straight[1]),
            ("arc", (-hw, -hh), math.pi, arc),
            ("edge", (-hw, -hh), (hw, -hh), straight[2]),
            ("arc", (hw, -hh), 1.5 * math.pi, arc),
            ("edge", (hw, -hh), (hw, hh), straight[3]),
            ("arc", (hw, hh), 0.0, arc),
        ]
        for kind, a, b, ln in seq:
            if d > ln:
                d -= ln
                continue
            if kind == "edge":
                t = d / ln if ln > 0 else 0.0
                pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            else:
                t = d / ln if ln > 0 else 0.0
                ang = b + t * 0.5 * math.pi
                pts.append((a[0] + math.cos(ang) * r, a[1] + math.sin(ang) * r))
            break
        else:
            pts.append(corners[0])
    return pts


def ring_from_profile(profile, origin, x_axis, y_axis, sx=1.0, sy=1.0):
    """Place a 2D profile into 3D using a frame."""
    out = []
    for (u, v) in profile:
        out.append((
            origin[0] + x_axis[0] * u * sx + y_axis[0] * v * sy,
            origin[1] + x_axis[1] * u * sx + y_axis[1] * v * sy,
            origin[2] + x_axis[2] * u * sx + y_axis[2] * v * sy,
        ))
    return out


# ------------------------------------------------------------------ solids


def tube_along_path(mesh, path, profile_fn, up_hint=(0.0, 1.0, 0.0),
                    uv_rect=(0.0, 0.0, 1.0, 1.0), cap_start=True, cap_end=True,
                    group=0, cap_group=None, twist=0.0):
    """Sweep a profile along a polyline path.

    `profile_fn(t)` returns the 2D profile for path fraction t in [0, 1].
    """
    frames = vec.parallel_frames(path, up_hint)
    rings = []
    n = len(path)
    for i, (p, (x, y, _z)) in enumerate(zip(path, frames)):
        t = i / (n - 1)
        if twist:
            a = twist * t
            xr = (x[0] * math.cos(a) + y[0] * math.sin(a),
                  x[1] * math.cos(a) + y[1] * math.sin(a),
                  x[2] * math.cos(a) + y[2] * math.sin(a))
            yr = vec.cross(_z, xr)
            x, y = xr, yr
        rings.append(ring_from_profile(profile_fn(t), p, x, y))
    mesh.add_loft(rings, uv_rect=uv_rect, group=group)
    cg = group if cap_group is None else cap_group
    if cap_start:
        mesh.add_grid_cap(rings[0], group=cg, flip=True)
    if cap_end:
        mesh.add_grid_cap(rings[-1], group=cg)
    return rings


def dome_tip(mesh, ring, apex, steps=3, group=0, uv_rect=(0.0, 0.0, 1.0, 1.0),
             bulge=1.0):
    """Round off a tube end into a dome that keeps the ring's edge loops."""
    c = _centroid(ring[:-1])
    axis = vec.sub(apex, c)
    rings = [ring]
    for s in range(1, steps + 1):
        t = s / (steps + 1)
        ang = t * 0.5 * math.pi
        shrink = math.cos(ang)
        rise = math.sin(ang) * bulge
        new = []
        for p in ring:
            radial = vec.sub(p, c)
            q = vec.add(c, vec.mul(radial, shrink))
            new.append(vec.mad(q, axis, rise))
        rings.append(new)
    u0, v0, u1, v1 = uv_rect
    mesh.add_loft(rings, uv_rect=uv_rect, group=group)
    top = rings[-1]
    tip = vec.mad(c, axis, 1.0)
    mesh.add_cap(top, center=tip, uv_center=(0.5 * (u0 + u1), v1),
                 radius_uv=0.02, group=group)


def capsule(mesh, length, r0, r1, n=8, group=0, cap_rings=2,
            uv_rect=(0.0, 0.0, 1.0, 1.0), squash=0.92, tip=True, base=True):
    """A tapered tube along +Z with hemispherical ends.

    Built straight, in its own local space: a bone. Chaining these through
    node transforms gives a limb that articulates without the sweep ever
    self-intersecting on the inside of a bend, which is what happens when you
    push a single loft around a tight curl. The end caps double as the joint
    balls, so a bent joint can never open a gap.
    """
    rings = []
    v = []
    if base:
        for k in range(cap_rings, 0, -1):
            t = k / cap_rings
            a = math.acos(max(-1.0, min(1.0, t)))     # 0 at pole
            rings.append(profile_ellipse(n, r0 * math.sin(a), r0 * math.sin(a)))
            v.append(-math.cos(a) * r0 * squash)
    rings.append(profile_ellipse(n, r0, r0))
    v.append(0.0)
    rings.append(profile_ellipse(n, r1, r1))
    v.append(length)
    if tip:
        for k in range(1, cap_rings + 1):
            t = k / cap_rings
            a = math.acos(max(-1.0, min(1.0, t)))
            rings.append(profile_ellipse(n, r1 * math.sin(a), r1 * math.sin(a)))
            v.append(length + math.cos(a) * r1 * squash)

    placed = [ring_from_profile(p, (0.0, 0.0, z), (1.0, 0.0, 0.0),
                                (0.0, 1.0, 0.0)) for p, z in zip(rings, v)]
    span = v[-1] - v[0]
    vc = [(z - v[0]) / span if span else 0.0 for z in v]
    mesh.add_loft(placed, v_coords=vc, uv_rect=uv_rect, group=group)
    if base:
        mesh.add_cap(placed[0], center=(0.0, 0.0, v[0]), group=group, flip=True)
    else:
        mesh.add_grid_cap(placed[0], group=group + 1, flip=True)
    if tip:
        mesh.add_cap(placed[-1], center=(0.0, 0.0, v[-1]), group=group)
    else:
        mesh.add_grid_cap(placed[-1], group=group + 2)


def box_chamfered(mesh, size, chamfer=0.006, center=(0.0, 0.0, 0.0),
                  group=0, uv_rect=(0.0, 0.0, 1.0, 1.0), segments=1):
    """Axis-aligned chamfered box built as a loft along Y.

    Chamfered edges catch a highlight, which is what makes hard-surface props
    read as "machined" instead of "programmer cube".
    """
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    c = chamfer
    n = 24
    rings = []
    levels = [
        (-sy, sx - c, sz - c),
        (-sy + c, sx, sz),
    ]
    for i in range(1, segments):
        t = i / segments
        levels.append((-sy + c + (2 * sy - 2 * c) * t, sx, sz))
    levels += [
        (sy - c, sx, sz),
        (sy, sx - c, sz - c),
    ]
    for (y, ex, ez) in levels:
        prof = profile_round_rect(n, ex * 2, ez * 2, min(ex, ez) * 0.22)
        ring = [(center[0] + p[0], center[1] + y, center[2] + p[1]) for p in prof]
        rings.append(ring)
    mesh.add_loft(rings, uv_rect=uv_rect, group=group)
    mesh.add_grid_cap(rings[0], group=group + 1, flip=True)
    mesh.add_grid_cap(rings[-1], group=group + 2)
    return rings


def cylinder(mesh, p0, p1, r0, r1, n=16, group=0, uv_rect=(0.0, 0.0, 1.0, 1.0),
             cap_start=True, cap_end=True, up_hint=(0.0, 1.0, 0.0),
             cap_group_offset=(1, 2)):
    axis = vec.sub(p1, p0)
    frame = vec.look_basis(axis, up_hint)
    x = (frame[0], frame[4], frame[8])
    y = (frame[1], frame[5], frame[9])
    prof = profile_ellipse(n, 1.0, 1.0)
    rings = [
        ring_from_profile(prof, p0, x, y, r0, r0),
        ring_from_profile(prof, p1, x, y, r1, r1),
    ]
    mesh.add_loft(rings, uv_rect=uv_rect, group=group)
    if cap_start:
        mesh.add_grid_cap(rings[0], group=group + cap_group_offset[0], flip=True)
    if cap_end:
        mesh.add_grid_cap(rings[-1], group=group + cap_group_offset[1])
    return rings


def plate(mesh, origin, x_axis, y_axis, w, h, group=0,
          uv_rect=(0.0, 0.0, 1.0, 1.0), subdiv=1):
    """A flat quad (optionally subdivided) -- used for decal faces."""
    u0, v0, u1, v1 = uv_rect
    base = len(mesh.pos)
    for j in range(subdiv + 1):
        for i in range(subdiv + 1):
            fu = i / subdiv
            fv = j / subdiv
            p = (
                origin[0] + x_axis[0] * (fu - 0.5) * w + y_axis[0] * (fv - 0.5) * h,
                origin[1] + x_axis[1] * (fu - 0.5) * w + y_axis[1] * (fv - 0.5) * h,
                origin[2] + x_axis[2] * (fu - 0.5) * w + y_axis[2] * (fv - 0.5) * h,
            )
            mesh.add_vertex(p, (u0 + (u1 - u0) * fu, v0 + (v1 - v0) * fv))
    s = subdiv + 1
    for j in range(subdiv):
        for i in range(subdiv):
            a = base + j * s + i
            mesh.add_face((a, a + 1, a + s + 1, a + s), group)
