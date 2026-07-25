#!/usr/bin/env python3
"""Tom Rexington, Esq. -- first-person arms + Exhibitfy Bates stamp.

Builds the FPV viewmodel for "Tom Rexington, Esq.: Bates & Destroy":
forearms in rolled-up dress shirt sleeves, hands gripping a heavy Exhibitfy
Bates stamp, posed mid-ready to slam forward.

    python3 build_fpv_arms.py [--no-preview] [--bates 000137]

Outputs into build/:
    exhibitfy_fpv_arms.glb      runtime asset (PBR, textures, Stamp_Swing)
    exhibitfy_fpv_arms_single_mesh.glb   same geometry as one static object
    exhibitfy_fpv.obj / .mtl    quad-preserved editable mesh
    textures/*.png              every map, as authored
    previews/*.png              software renders incl. a wireframe pass

Conventions: metres, Y-up, camera at the origin looking down -Z (glTF style).
Every tunable number lives in the RIG / STAMP / HAND dicts near the top.
"""

import argparse
import math
import os
import random
import sys
import time

from tools import glyphs, mesh as M, textures as TX, vec
from tools.gltf import Animation, Material, Node, Scene, export_glb
from tools.imaging import Canvas, hex_srgb, write_apng
from tools.objexport import export_obj

TAU = math.pi * 2.0
D2R = math.pi / 180.0

# ---------------------------------------------------------------- tuning

HAND = {
    "palm_len": 0.092,
    "palm_w0": 0.055,      # at the wrist
    "palm_w1": 0.081,      # across the knuckles
    "palm_t0": 0.034,
    "palm_t1": 0.029,
    "palm_rings": 11,
    "palm_sides": 18,
    "finger_sides": 10,
    # a gripped bar sits here in hand-local space (used by the grip solver)
    "grip_point": (0.0, -0.0335, 0.072),
}

# name, root(x, y, z-offset from knuckle line), radius, phalanx lengths,
# splay (deg about Y), curl (deg per phalanx)
FINGERS = [
    ("Index",  (-0.0268, 0.0035, -0.004), 0.0112, (0.041, 0.027, 0.021), -3.5),
    ("Middle", (-0.0090, 0.0045, 0.000),  0.0117, (0.045, 0.030, 0.022), -0.5),
    ("Ring",   (0.0090, 0.0035, -0.004),  0.0108, (0.042, 0.028, 0.021), 3.0),
    ("Pinky",  (0.0252, 0.0010, -0.013),  0.0092, (0.034, 0.022, 0.018), 7.5),
]

STAMP = {
    # Striking head, stacked bottom-up from the die face at local y = 0.
    # Mass is deliberately concentrated down here and the tower slimmed above
    # it: heavy business end, agile shaft.
    "die_size": (0.126, 0.0088, 0.090),   # proud rubber die block
    "die_y": 0.0007,          # clears the face plate at y = 0
    "pad_size": (0.134, 0.0090, 0.098),   # wider rubber backing
    "pad_y": 0.0095,
    "sole_size": (0.142, 0.0086, 0.106),  # machined steel sole plate
    "sole_y": 0.0185,
    "base_size": (0.138, 0.042, 0.102),
    "base_y": 0.0271,         # bottom of the base block
    "collar_h": 0.0095,
    # tower -- narrower and shorter than the head, so the silhouette tapers
    "tower_y0": 0.0691,
    "tower_y1": 0.1800,
    "plate_x": 0.0455,
    "plate_th": 0.0110,
    "plate_z": 0.0820,
    "column_r": 0.0195,
    "wheel_y": 0.1060,
    "wheel_r": 0.0290,
    "wheel_half": 0.0365,
    "window_pad": 0.005,
    # head + handle
    "head_y": 0.1925,
    "head_size": (0.090, 0.026, 0.050),
    "handle_y": 0.2245,
    "handle_half": 0.0745,
    "handle_r": 0.0158,
    # side foregrip (left-hand support)
    "grip_root": (-0.0575, 0.0435, 0.017),
    "grip_tip": (-0.1330, 0.0125, 0.052),
    "grip_r": 0.0152,
}

RIG = {
    # where the stamp sits in camera space, and how it is cocked.
    # stamp_pos is the centre of the striking face.
    "stamp_pos": (0.098, -0.181, -0.462),
    "stamp_scale": 1.10,      # heavy in the hand, but still quick to swing
    "stamp_pitch": 29.0,      # about X: cocks the tower back towards the player
    "stamp_yaw": -17.0,       # about Y: turns the branded flank into view
    "stamp_roll": 7.0,        # about Z: aggressive diagonal
    # grips, in stamp-local space
    "grip_r_point": (0.040, 0.2245, 0.0),     # right hand on the T-bar
    "grip_r_axis": (1.0, 0.0, 0.0),
    "grip_r_dorsal": (0.06, 1.0, 0.22),
    # Spin about the bar. The grip solve cannot see this -- rolling the hand
    # keeps every fingertip exactly as far from the bar axis -- so it needs its
    # own measure, NOT an eyeballed render. Setting it by eye is how this
    # shipped at 300, showing the player a palm.
    #
    # The measure: the camera sits at the origin, so take the hand's world +Y
    # (the back of the hand) and dot it with the direction from the wrist back
    # to the camera. Positive means knuckles to the player, which is what
    # gripping a bar to swing it down looks like. Both values below are the
    # measured maxima -- right +0.981, left +0.988.
    #
    # The right hand is NOT at its maximum, and this is deliberate. Roll is not
    # independent of the arm: the forearm chain follows the wrist, and at 60 the
    # hand does read knuckles-out (+0.981) but the forearm swings across the
    # frame and hides it, camera-on and foreshortened. Adjusting elbow_dir_r to
    # compensate did not recover it. Facing and arm pose have to be solved
    # together -- roll, elbow direction and grip point at once -- and until that
    # is done 0 (+0.413, edge-on) is the least-bad of the three states tried;
    # 300 was worse still at -0.426, an actual palm to the player.
    "grip_r_roll": 0.0,
    # The left hand no longer touches the stamp -- it carries the exhibits.
    # These are VIEW-space, not stamp-space: the sheaf must not swing with the
    # tool, so it hangs off the root rather than off the stamp.
    "docs_point": (-0.205, -0.300, -0.430),
    "docs_axis": (0.86, 0.20, -0.47),
    "docs_dorsal": (0.10, 1.0, 0.30),
    "docs_roll": 40.0,
    "docs_sheets": 7,
    "docs_size": (0.216, 0.030, 0.279),   # letter width, sheaf thickness, depth
    "grip_l_roll": 300.0,
    "grip_l_point": (-0.0955, 0.0281, 0.0347),  # left hand on the foregrip
    "grip_l_axis": (0.888, 0.363, -0.283),
    "grip_l_dorsal": (-0.14, 1.0, 0.32),
    # forearms: direction from wrist back to the elbow, and length
    "forearm_len": 0.278,
    "elbow_dir_r": (0.44, -0.80, 0.41),
    "elbow_dir_l": (-0.42, -0.82, 0.39),
    "forearm_bow_r": (0.026, -0.016, 0.024),
    "forearm_bow_l": (-0.026, -0.020, 0.022),
    # forearm cross-section
    "r_elbow": (0.0525, 0.0475),
    "r_mid": (0.0435, 0.0385),
    "r_wrist": (0.0325, 0.0252),
    "sleeve_pad": 0.0098,
    "sleeve_t0": -0.95,       # extends behind the elbow, off-camera
    "sleeve_t1": 0.46,        # rolled up to mid-forearm
    "cuff_t0": 0.29,          # where the roll starts
    "cuff_bulge": 0.0105,
    "watch_t": 0.862,
    "watch_roll": 120.0,  # spin about the forearm; see build_watch
}

# ---------------------------------------------------------------- impact
# The surface the die is driven into: a document lying on a desk just in front
# of and below the camera, tilted up towards the player so the strike reads.
# The stamp's local origin IS the striking face, so at the impact frame the
# stamp node sits exactly on this point with its +Y along this normal --
# the face plants flush in the plane, by construction rather than by eye.
IMPACT = {
    "point": (0.062, -0.336, -0.523),
    "normal": vec.norm((0.0, 0.940, 0.341)),
    "front_hint": (0.0, 0.0, 1.0),   # which way the tool's front faces there
    "yaw": -5.0,                     # extra style rotation, applied in local
    "roll": 2.5,
}

# ------------------------------------------------------------ Stamp_Swing
# 23 frames at 30 fps (0.767 s). One scalar `s` drives the whole swing:
#   s = 0  ready stance      s < 0  cocked back      s = 1  planted on the plane
# Keys are baked every frame, so the easing below is exactly what ships.
SWING = {
    "name": "Stamp_Swing",
    "fps": 30.0,
    "frames": 23,
    # (frame, s, easing used to REACH this beat)
    "beats": [
        (0, 0.00, "linear"),   # ready
        (4, -0.26, "out"),     # short, powerful cock back and up
        (5, -0.26, "hold"),    # the loaded beat
        (11, 1.00, "in"),      # accelerate all the way into the plane
        (13, 1.00, "hold"),    # planted: 3 frames (11, 12, 13) face on plane
        (22, 0.00, "inout"),   # controlled recovery, no bounce
    ],
    # extra weight-into-the-surface during the hold (metres along -normal)
    "press": [(10, 0.0, "linear"), (11, 0.0022, "out"), (13, 0.0030, "inout"),
              (16, 0.0, "inout"), (22, 0.0, "hold")],
    "windup_s": -0.26,
    "windup_offset": (0.016, 0.048, 0.044),   # back towards the player and up
    "windup_pitch": 16.0,                     # cocks the tower further back
    "arc": (-0.008, 0.046, -0.014),           # bow of the travel path
    "wrist_lag": 8.5,                         # deg, driven by swing velocity
    "grip_squeeze": 5.5,                      # deg of extra finger curl on hit
}

MAT = {
    "skin": "Skin_Tom",
    "shirt": "Shirt_White",
    "steel": "Steel_Machined",
    "black": "Housing_Black",
    "decal": "Housing_Exhibitfy",
    "orange": "Accent_Exhibitfy_Orange",
    "rubber": "Rubber_Base",
    "die": "Stamp_Die_Face",
    "grip": "Grip_Rubber",
    "watch_steel": "Watch_Silver",
    "watch_dial": "Watch_Dial",
    "wheels": "Bates_Number_Wheels",
    "steel_cast": "Steel_Cast",
    "paper": "Exhibit_Paper",
}


# ------------------------------------------------------------- utilities


def mirror_mesh(m):
    """Mirror across X and flip winding so normals stay outward."""
    m.pos = [(-p[0], p[1], p[2]) for p in m.pos]
    m.faces = [(tuple(reversed(idx)), g) for idx, g in m.faces]
    return m


_S_MIRROR = [
    -1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
]


def mirror_node(node, mirror_matrix=False):
    """Reflect a sub-tree's *contents* across X.

    A point p in the sub-tree's local space becomes S*p, so child transforms
    become S*C*S and every mesh is flipped (winding reversed with it). The
    root's own matrix is left alone by default: it positions the sub-tree in
    the parent and must keep doing exactly that.
    """
    if mirror_matrix:
        node.matrix = vec.mat_mul(_S_MIRROR, vec.mat_mul(node.matrix, _S_MIRROR))
    if hasattr(node, "bind_local"):
        node.bind_local = list(node.matrix)
        node.mirror_sign = -node.mirror_sign
    for m in node.meshes:
        mirror_mesh(m)
    for c in node.children:
        mirror_node(c, mirror_matrix=True)
    return node


def grip_frame(axis, dorsal, point, grip_local, roll=0.0):
    """Rigid transform placing a hand so `grip_local` lands on `point`
    with hand-local +X along `axis` and +Y towards `dorsal`.

    `roll` spins the hand about the bar in degrees, which is the one degree of
    freedom the grip is blind to: every fingertip stays exactly as far from the
    bar axis however far you roll it, so a measured-clean grip can still be
    showing the player its palm. Positive rolls the back of the hand towards
    the camera.
    """
    x = vec.norm(axis)
    if roll:
        # Rodrigues: spin the dorsal reference about the bar itself
        a = roll * D2R
        c, s = math.cos(a), math.sin(a)
        d = vec.norm(dorsal)
        dorsal = vec.add(
            vec.add(vec.mul(d, c), vec.mul(vec.cross(x, d), s)),
            vec.mul(x, vec.dot(x, d) * (1.0 - c)))
    y = vec.norm(vec.sub(dorsal, vec.mul(x, vec.dot(dorsal, x))))
    z = vec.cross(x, y)
    origin = vec.sub(point, (
        x[0] * grip_local[0] + y[0] * grip_local[1] + z[0] * grip_local[2],
        x[1] * grip_local[0] + y[1] * grip_local[1] + z[1] * grip_local[2],
        x[2] * grip_local[0] + y[2] * grip_local[1] + z[2] * grip_local[2],
    ))
    return vec.mat_from_basis(x, y, z, origin)


def bezier_path(p0, p1, p2, p3, steps):
    return [vec.bezier4(p0, p1, p2, p3, i / (steps - 1)) for i in range(steps)]


# --------------------------------------------------------------- the hand


def wrap_angles(root, lengths, centre, wrap_r, max_bend=95.0, first_max=88.0):
    """Bend angles that wrap a chain of segments around a cylinder.

    Everything happens in the hand's YZ plane (the handle runs along hand X),
    working in 2D as (z, y): the finger's rest direction is +z and a positive
    bend curls it towards -y, i.e. into the palm. `centre` is the handle axis,
    `wrap_r` the radius the joints should ride on (handle + finger radius).

    Solving this instead of hand-picking angles is the difference between a
    grip that happens to look right for one handle and one that stays right
    when the handle moves or changes size.
    """
    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1])

    def add(a, b):
        return (a[0] + b[0], a[1] + b[1])

    def length(a):
        return math.hypot(a[0], a[1])

    def signed(a, b):
        """angle from a to b, positive = anticlockwise in (z, y)"""
        return math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1])

    pts = [root]
    d = length(sub(centre, root))
    l0 = lengths[0]
    # first joint: put it on the wrap circle if the proximal phalanx can reach
    hit = None
    if abs(l0 - wrap_r) <= d <= l0 + wrap_r:
        a = (l0 * l0 - wrap_r * wrap_r + d * d) / (2.0 * d)
        h = math.sqrt(max(0.0, l0 * l0 - a * a))
        u = ((centre[0] - root[0]) / d, (centre[1] - root[1]) / d)
        mid = (root[0] + u[0] * a, root[1] + u[1] * a)
        # two solutions; take the one on the palm side (curling towards -y)
        for s in (-1.0, 1.0):
            cand = (mid[0] + u[1] * h * s, mid[1] - u[0] * h * s)
            if hit is None or cand[1] < hit[1]:
                hit = cand
    if hit is None:
        # out of reach: aim straight at the circle and let the clamps hold it
        u = ((centre[0] - root[0]) / max(d, 1e-6),
             (centre[1] - root[1]) / max(d, 1e-6))
        hit = (root[0] + u[0] * l0, root[1] + u[1] * l0)
    pts.append(hit)

    # remaining joints ride around the circle, one chord per phalanx
    ang = math.atan2(hit[1] - centre[1], hit[0] - centre[0])
    for L in lengths[1:]:
        step = 2.0 * math.asin(max(-1.0, min(1.0, L / (2.0 * wrap_r))))
        ang -= step                      # walk around, curling into the palm
        pts.append(add(centre, (math.cos(ang) * wrap_r,
                                math.sin(ang) * wrap_r)))

    out = []
    prev = (1.0, 0.0)                    # rest direction is +z
    for i in range(1, len(pts)):
        v = sub(pts[i], pts[i - 1])
        if length(v) < 1e-9:
            out.append(0.0)
            continue
        v = (v[0] / length(v), v[1] / length(v))
        a = -signed(prev, v)             # positive = curl towards the palm
        lim = first_max if i == 1 else max_bend
        a = max(-8.0 * D2R, min(lim * D2R, a))
        out.append(a)
        prev = (math.cos(-a) * prev[0] - math.sin(-a) * prev[1],
                math.sin(-a) * prev[0] + math.cos(-a) * prev[1])
    return out


def build_finger(name, root, radius, phal, splay, bends, side_uv, suffix=""):
    """A finger as three jointed bones: proximal, middle, distal.

    Each bone is a straight capsule in its own space, so no amount of curl can
    fold the geometry through itself, and the capsule ends double as knuckle
    balls that keep the joints closed at any bend. Every joint is a node, so
    the finger is genuinely articulated rather than frozen in one pose.
    """
    n = HAND["finger_sides"]
    seg_names = ("", "_Mid", "_Tip")
    radii = [radius, radius * 0.90, radius * 0.80, radius * 0.72]
    v0, v1 = side_uv

    nodes = []
    for i, (ln, bend) in enumerate(zip(phal, bends)):
        m = M.Mesh("Finger_" + name + seg_names[i] + suffix, MAT["skin"])
        # slightly wider than deep, and the knuckle end a touch fatter
        M.capsule(m, ln, radii[i] * (1.06 if i else 1.10), radii[i + 1], n,
                  group=0, uv_rect=(0.0, v0, 1.0, v1),
                  base=True, tip=(i == len(phal) - 1))
        if i == 0:
            mtx = vec.mat_mul(
                vec.mat_mul(vec.translate(root), vec.rot_y(splay * D2R)),
                vec.rot_x(bend))
        else:
            mtx = vec.mat_mul(vec.translate((0.0, 0.0, phal[i - 1])),
                              vec.rot_x(bend))
        node = Node("Finger_" + name + seg_names[i] + suffix, mtx, meshes=[m])
        node.bind_local = list(node.matrix)
        node.mirror_sign = 1.0
        if nodes:
            nodes[-1].add(node)
        nodes.append(node)
    return nodes[0]


def build_palm(side_uv):
    m = M.Mesh("Palm", MAT["skin"])
    n = HAND["palm_sides"]
    rings = HAND["palm_rings"]
    L = HAND["palm_len"]
    v0, v1 = side_uv
    out = []
    for i in range(rings):
        t = i / (rings - 1)
        w = HAND["palm_w0"] + (HAND["palm_w1"] - HAND["palm_w0"]) * \
            vec.smoothstep(min(1.0, t * 1.15))
        th = HAND["palm_t0"] + (HAND["palm_t1"] - HAND["palm_t0"]) * t
        # the palm arches: knuckle end drops slightly to the palmar side
        y = -0.005 * t * t
        z = L * t
        # knuckle ridge: the back of the hand swells just before the fingers
        ridge = math.exp(-((t - 0.88) ** 2) / 0.012) * 0.0055
        prof = M.profile_super(n, w * 0.5, th * 0.5, 2.25)
        ring = []
        for (px, py) in prof:
            # thenar (thumb ball) and hypothenar pads -- the "strong hand" read
            thenar = math.exp(-((t - 0.34) ** 2) / 0.030) * \
                max(0.0, -px / (w * 0.5)) * max(0.0, -py / (th * 0.5)) * 0.011
            hypo = math.exp(-((t - 0.45) ** 2) / 0.055) * \
                max(0.0, px / (w * 0.5)) * max(0.0, -py / (th * 0.5)) * 0.006
            grow = 1.0 + (thenar + hypo) / max(1e-5, th * 0.5)
            dorsal = ridge * max(0.0, py / (th * 0.5))
            ring.append((px - thenar * 0.9, y + py * grow + dorsal, z))
        # close the seam
        ring[-1] = ring[0]
        out.append(ring)
    m.add_loft(out, uv_rect=(0.0, v0, 1.0, v1), group=0)
    m.add_grid_cap(out[0], group=1, flip=True)
    knuckle = (0.0, -0.005 * 1.0, L + HAND["palm_t1"] * 0.42)
    M.dome_tip(m, out[-1], knuckle, steps=2, group=0,
               uv_rect=(0.0, v1 - (v1 - v0) * 0.05, 1.0, v1), bulge=0.55)
    return m


def build_thumb(side_uv, curl=(34.0, 30.0), splay=-52.0, twist=-26.0,
                pitch=-16.0, suffix=""):
    """Thumb as two jointed bones, opposed across the grip.

    A power grip closes the thumb over the front of the fist rather than
    laying it along the handle -- that opposition is most of what makes a
    hold read as strong rather than as a hand resting on something.
    """
    n = HAND["finger_sides"]
    radius = 0.0148
    phal = (0.038, 0.030)
    radii = (radius, radius * 0.90, radius * 0.80)
    v0, v1 = side_uv
    root = (-HAND["palm_w0"] * 0.50, -0.008, 0.026)

    nodes = []
    for i, (ln, ang) in enumerate(zip(phal, curl)):
        m = M.Mesh("Thumb" + ("_Tip" if i else "") + suffix, MAT["skin"])
        M.capsule(m, ln, radii[i] * 1.05, radii[i + 1], n, group=0,
                  uv_rect=(0.0, v0, 1.0, v1), base=True, tip=(i == 1))
        if i == 0:
            mtx = vec.mat_mul(
                vec.mat_mul(vec.translate(root),
                            vec.mat_mul(vec.rot_y(splay * D2R),
                                        vec.rot_z(twist * D2R))),
                vec.mat_mul(vec.rot_x(pitch * D2R), vec.rot_x(ang * D2R)))
        else:
            mtx = vec.mat_mul(vec.translate((0.0, 0.0, phal[0])),
                              vec.rot_x(ang * D2R))
        node = Node("Thumb" + ("_Tip" if i else "") + suffix, mtx, meshes=[m])
        node.bind_local = list(node.matrix)
        node.mirror_sign = 1.0
        if nodes:
            nodes[-1].add(node)
        nodes.append(node)
    return nodes[0]


def build_hand(name, bar_radius, grip_point=None, tighten=None, thumb=None,
               suffix=""):
    """A LEFT hand in canonical local space: +Z fingers, +Y dorsal, +X... no.

    Canonical space is +Z along the fingers, +Y out of the back of the hand,
    and the thumb at -X. For that frame a right hand would need its thumb at
    dorsal x fingers = +X, so this builds a LEFT hand; the right side is the
    one that gets mirrored.

    Finger bends are solved so each digit wraps the handle it is actually
    holding, rather than being posed by eye and hoping it lands.
    """
    hv = TX.HAND_V
    grip = grip_point or HAND["grip_point"]
    tighten = tighten or {}
    node = Node(name)
    node.add_mesh(build_palm(hv))
    centre = (grip[2], grip[1])          # handle axis, in the hand's (z, y)

    for fname, root, radius, phal, splay in FINGERS:
        r = (root[0], root[1], HAND["palm_len"] + root[2])
        # wrap radius: the finger surface should touch the handle surface
        wrap = bar_radius + radius * 0.92 + tighten.get(fname, 0.0)
        bends = wrap_angles((r[2], r[1]), phal, centre, wrap)
        node.add(build_finger(fname, r, radius, phal, splay, bends, hv,
                              suffix))
    tk = thumb or {}
    node.add(build_thumb(hv, suffix=suffix, **tk))
    return node


# --------------------------------------------------------------- the arm


def forearm_profile(t):
    """Cross-section radii at path fraction t (0 = elbow, 1 = wrist)."""
    re, rm, rw = RIG["r_elbow"], RIG["r_mid"], RIG["r_wrist"]
    if t < 0.5:
        k = vec.smoothstep(t / 0.5)
        rx = re[0] + (rm[0] - re[0]) * k
        ry = re[1] + (rm[1] - re[1]) * k
    else:
        k = vec.smoothstep((t - 0.5) / 0.5)
        rx = rm[0] + (rw[0] - rm[0]) * k
        ry = rm[1] + (rw[1] - rm[1]) * k
    return rx, ry


def build_arm(name, wrist_world, hand_basis, elbow_dir, bow, watch=False):
    """Forearm + sleeve, built in arm-local space (origin = elbow)."""
    L = RIG["forearm_len"]
    elbow = vec.mad(wrist_world, vec.norm(elbow_dir), L)
    # arm space: +Z runs elbow -> wrist, +Y roughly matches the hand's dorsal
    fwd = vec.norm(vec.sub(wrist_world, elbow))
    dorsal = (hand_basis[1], hand_basis[5], hand_basis[9])
    arm_world = vec.look_basis(fwd, dorsal, elbow)
    to_local = vec.rigid_inverse(arm_world)

    w_local = vec.xform_point(to_local, wrist_world)
    bow_local = vec.xform_dir(to_local, bow)
    p0 = (0.0, 0.0, 0.0)
    p3 = w_local
    p1 = vec.mad(vec.lerp(p0, p3, 0.32), bow_local, 1.0)
    p2 = vec.mad(vec.lerp(p0, p3, 0.68), bow_local, 0.45)

    def path_at(t):
        return vec.bezier4(p0, p1, p2, p3, t)

    # ---- bare skin: runs the full length so nothing peeks out under cloth
    steps = 19
    t0_skin = -0.10
    ts = [t0_skin + (1.0 - t0_skin) * i / (steps - 1) for i in range(steps)]
    pts = [path_at(t) for t in ts]
    frames = vec.parallel_frames(pts, (0.0, 1.0, 0.0))

    # untwist so the last ring lines up with the hand's own axes
    hand_x_local = vec.norm(vec.xform_dir(to_local,
                                          (hand_basis[0], hand_basis[4], hand_basis[8])))
    tan = frames[-1][2]
    want = vec.norm(vec.sub(hand_x_local, vec.mul(tan, vec.dot(hand_x_local, tan))))
    have = frames[-1][0]
    ang = math.atan2(vec.dot(vec.cross(have, want), tan),
                     max(-1.0, min(1.0, vec.dot(have, want))))

    def twisted(i):
        f = frames[i]
        a = ang * (i / (len(frames) - 1))
        c, s = math.cos(a), math.sin(a)
        x = (f[0][0] * c + f[1][0] * s, f[0][1] * c + f[1][1] * s,
             f[0][2] * c + f[1][2] * s)
        y = vec.cross(f[2], x)
        return x, y

    skin = M.Mesh(name + "_Forearm", MAT["skin"])
    rings = []
    for i, t in enumerate(ts):
        rx, ry = forearm_profile(max(0.0, t))
        x, y = twisted(i)
        e = 2.3 + 0.8 * max(0.0, t)     # flattens towards the wrist
        prof = M.profile_super(HAND["palm_sides"], rx, ry, e)
        rings.append(M.ring_from_profile(prof, pts[i], x, y))
    fv = TX.FOREARM_V
    skin.add_loft(rings, uv_rect=(0.0, fv[0], 1.0, fv[1]), group=0)
    skin.add_grid_cap(rings[0], group=1, flip=True)
    skin.add_grid_cap(rings[-1], group=2)

    # ---- shirt sleeve, rolled to mid-forearm with a thick cuff
    # Behind the elbow the sleeve follows the straight tangent rather than
    # extrapolating the bezier (which would flare off into nowhere).
    tan0 = vec.norm(vec.sub(path_at(0.02), p0))

    def sleeve_at(t):
        if t >= 0.0:
            return path_at(t)
        return vec.mad(p0, tan0, t * L)

    cloth = M.Mesh(name + "_Sleeve", MAT["shirt"])
    s0, s1 = RIG["sleeve_t0"], RIG["sleeve_t1"]
    csteps = 21
    cts = [s0 + (s1 - s0) * i / (csteps - 1) for i in range(csteps)]
    cpts = [sleeve_at(t) for t in cts]
    cframes = vec.parallel_frames(cpts, (0.0, 1.0, 0.0))
    crings = []
    for i, t in enumerate(cts):
        rx, ry = forearm_profile(max(0.0, min(1.0, t)))
        pad = RIG["sleeve_pad"] * (1.0 + 0.30 * max(0.0, -t / -s0 if s0 else 0.0))
        k = (t - RIG["cuff_t0"]) / max(1e-6, s1 - RIG["cuff_t0"])
        # cuff roll: a fat fold with a secondary ridge, like cloth turned twice
        roll = 0.0
        if k > 0.0:
            u = min(1.0, k)
            roll = RIG["cuff_bulge"] * math.sin(u * math.pi) ** 0.55
            roll += RIG["cuff_bulge"] * 0.30 * math.sin(u * math.pi * 2.0)
        prof = M.profile_super(HAND["palm_sides"], rx + pad + roll,
                               ry + pad + roll, 2.4)
        f = cframes[i]
        crings.append(M.ring_from_profile(prof, cpts[i], f[0], f[1]))
    cloth.add_loft(crings, uv_rect=(0.0, 0.0, 1.0, 1.0), group=0)
    cloth.add_grid_cap(crings[0], group=1, flip=True)
    # inner lip of the cuff, so the sleeve reads as a tube not a shell
    lip_rx, lip_ry = forearm_profile(min(1.0, s1))
    lip = M.ring_from_profile(
        M.profile_super(HAND["palm_sides"], lip_rx + 0.003, lip_ry + 0.003, 2.4),
        sleeve_at(s1 - 0.055), cframes[-1][0], cframes[-1][1])
    cloth.add_loft([crings[-1], lip], uv_rect=(0.0, 0.99, 1.0, 0.92),
                   group=2, flip=True)
    # cap the inside of the fold. The forearm passes through it, so it is never
    # seen, but it leaves the sleeve watertight instead of an open tube.
    cloth.add_grid_cap(lip, group=3, flip=True)

    node = Node(name, arm_world, meshes=[cloth, skin])
    return node, arm_world, path_at, (twisted, ts, pts)


# ------------------------------------------------------------- the watch


def build_watch(path_at, frame_fn, ts):
    """Silver watch riding on the left wrist, in arm-local space."""
    t = RIG["watch_t"]
    p = path_at(t)
    # frame by finite difference along the path
    fwd = vec.norm(vec.sub(path_at(t + 0.01), path_at(t - 0.01)))
    # match the forearm's own twisted frame at the nearest sample
    i = min(range(len(ts)), key=lambda k: abs(ts[k] - t))
    x, y = frame_fn(i)
    # The forearm's twist is derived from the hand, so rolling the grip rolls
    # the watch with it and can bury the case under the wrist. This offset
    # spins it back around the arm so the dial stays where it can be read.
    if RIG.get("watch_roll"):
        a = RIG["watch_roll"] * D2R
        c, s = math.cos(a), math.sin(a)

        def spin(v):
            return vec.add(
                vec.add(vec.mul(v, c), vec.mul(vec.cross(fwd, v), s)),
                vec.mul(fwd, vec.dot(fwd, v) * (1.0 - c)))

        x, y = spin(x), spin(y)
    rx, ry = forearm_profile(t)

    node = Node("Watch_L")
    band = M.Mesh("Watch_Band", MAT["watch_steel"])
    rings = []
    half = 0.0135
    for k in range(7):
        u = (k / 6.0 - 0.5) * 2.0
        pp = path_at(t + u * half / 0.27)
        bulge = 0.0030 * (1.0 - abs(u) ** 2) + 0.0016
        prof = M.profile_super(20, rx + bulge, ry + bulge, 2.6)
        rings.append(M.ring_from_profile(prof, pp, x, y))
    band.add_loft(rings, uv_rect=(0, 0, 1, 1), group=0)
    band.add_grid_cap(rings[0], group=1, flip=True)
    band.add_grid_cap(rings[-1], group=2)
    node.add_mesh(band)

    # The case belongs on the back of the wrist. Arm space is built with +Y
    # as dorsal, but the ring frame is untwisted to meet the hand and can come
    # out sign-flipped near the wrist -- so resolve "up" against arm space.
    up = y if vec.dot(y, (0.0, 1.0, 0.0)) >= 0.0 else vec.mul(y, -1.0)
    base = vec.mad(p, up, ry * 0.90)
    case = M.Mesh("Watch_Case", MAT["watch_steel"])
    M.cylinder(case, base, vec.mad(base, up, 0.0120), 0.0232, 0.0224, 22,
               group=0)
    M.cylinder(case, vec.mad(base, up, 0.0120), vec.mad(base, up, 0.0160),
               0.0224, 0.0192, 22, group=3)
    # crown
    side = vec.norm(vec.cross(up, fwd))
    cr = vec.mad(vec.mad(base, up, 0.006), side, 0.0222)
    M.cylinder(case, cr, vec.mad(cr, side, 0.0050), 0.0034, 0.0034, 8, group=6)
    node.add_mesh(case)

    dial = M.Mesh("Watch_Dial", MAT["watch_dial"])
    face = vec.mad(base, up, 0.0162)
    M.cylinder(dial, face, vec.mad(face, up, 0.0009), 0.0180, 0.0178, 22,
               group=0, cap_start=True, up_hint=fwd)
    node.add_mesh(dial)

    hands = M.Mesh("Watch_Hands", MAT["watch_steel"])
    f2 = vec.mad(face, up, 0.0016)
    # hour markers at the quarters, then the hands themselves
    for k in range(4):
        a = k * math.pi * 0.5
        d = vec.norm(vec.add(vec.mul(fwd, math.cos(a)), vec.mul(side, math.sin(a))))
        c = vec.mad(f2, d, 0.0140)
        M.plate(hands, c, d, vec.norm(vec.cross(up, d)), 0.0042, 0.0016,
                group=0)
    d1 = vec.norm(vec.add(vec.mul(fwd, 0.5), vec.mul(side, 0.86)))
    d2 = vec.norm(vec.add(vec.mul(fwd, -0.95), vec.mul(side, 0.3)))
    for (d, ln, w) in ((d1, 0.0105, 0.0017), (d2, 0.0140, 0.0014)):
        c = vec.mad(f2, d, ln * 0.42)
        M.plate(hands, c, d, vec.norm(vec.cross(up, d)), ln, w, group=0)
    node.add_mesh(hands)
    return node


# -------------------------------------------------------------- the stamp


def build_stamp(bates="000137"):
    """Exhibitfy Bates stamp, in stamp-local space.

    Local origin sits at the centre of the striking face; +Y runs up the
    tower to the handle, +Z is the front of the tool.
    """
    S = STAMP
    node = Node("Stamp_Exhibitfy")

    # ---- striking head --------------------------------------------------
    # Stepped like a real die: a proud rubber die block, a wider rubber
    # backing above it, then a machined steel sole plate. The step gives the
    # face a shoulder to catch light, so the business end reads as the heavy
    # end of the tool rather than a flat slab.
    ds = S["die_size"]
    ps = S["pad_size"]
    pad = M.Mesh("Stamp_DieBlock", MAT["rubber"])
    M.box_chamfered(pad, ds, 0.0028, (0.0, S["die_y"] + ds[1] * 0.5, 0.0),
                    group=0)
    M.box_chamfered(pad, ps, 0.0035, (0.0, S["pad_y"] + ps[1] * 0.5, 0.0),
                    group=10)
    node.add_mesh(pad)

    sole = M.Mesh("Stamp_SolePlate", MAT["steel_cast"])
    ss = S["sole_size"]
    M.box_chamfered(sole, ss, 0.0032, (0.0, S["sole_y"] + ss[1] * 0.5, 0.0),
                    group=0)
    node.add_mesh(sole)

    die = M.Mesh("Stamp_DieFace", MAT["die"])
    # The face sits exactly on the stamp's local y = 0 plane, so the node
    # origin IS the striking surface -- that is what the impact plane and the
    # Stamp_DieAnchor emitter align to.
    # Type reads the right way up when the player sees the face during the
    # slam (a real die would be mirrored -- this one is built to be read).
    M.plate(die, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
            ds[0] * 0.955, ds[2] * 0.955,
            group=0, uv_rect=(0.0, 0.0, 1.0, 1.0), subdiv=2)
    node.add_mesh(die)

    # ---- base block -----------------------------------------------------
    base = M.Mesh("Stamp_Base", MAT["black"])
    bs = S["base_size"]
    M.box_chamfered(base, bs, 0.006, (0.0, S["base_y"] + bs[1] * 0.5, 0.0),
                    group=0, segments=3)
    node.add_mesh(base)

    collar = M.Mesh("Stamp_Collar", MAT["orange"])
    M.box_chamfered(collar, (bs[0] * 1.02, S["collar_h"], bs[2] * 1.02), 0.0035,
                    (0.0, S["base_y"] + bs[1] - S["collar_h"] * 0.4, 0.0),
                    group=0)
    node.add_mesh(collar)

    # ---- tower ----------------------------------------------------------
    # Two side plates, a solid back, and a front faceplate with a window that
    # the numbering wheels show through -- the Bates read at a glance.
    y0, y1 = S["tower_y0"], S["tower_y1"]
    pz = S["plate_z"] * 0.5
    win0 = S["wheel_y"] - S["wheel_r"] - S["window_pad"]
    win1 = S["wheel_y"] + S["wheel_r"] + S["window_pad"]
    inner_w = (S["plate_x"] - S["plate_th"] * 0.5) * 2.0

    plates = M.Mesh("Stamp_SidePlates", MAT["black"])
    for sx in (-1, 1):
        M.box_chamfered(plates, (S["plate_th"], y1 - y0, S["plate_z"]), 0.004,
                        (sx * S["plate_x"], (y0 + y1) * 0.5, 0.0),
                        group=0, segments=2)
    # back panel closes the housing
    M.box_chamfered(plates, (inner_w + S["plate_th"], y1 - y0, S["plate_th"]),
                    0.004, (0.0, (y0 + y1) * 0.5, -pz + S["plate_th"] * 0.5),
                    group=10, segments=2)
    # front faceplate above and a sill below the wheel window
    M.box_chamfered(plates, (inner_w + S["plate_th"], y1 - win1, S["plate_th"]),
                    0.004, (0.0, (win1 + y1) * 0.5, pz - S["plate_th"] * 0.5),
                    group=20, segments=2)
    M.box_chamfered(plates, (inner_w + S["plate_th"], win0 - y0, S["plate_th"]),
                    0.004, (0.0, (y0 + win0) * 0.5, pz - S["plate_th"] * 0.5),
                    group=30)
    node.add_mesh(plates)

    decals = M.Mesh("Stamp_Branding", MAT["decal"])
    px = S["plate_x"] + S["plate_th"] * 0.5 + 0.0007
    dh = (y1 - y0) * 0.72
    dw = S["plate_z"] * 0.90
    M.plate(decals, (-px, (y0 + y1) * 0.5, 0.0), (0.0, 0.0, 1.0),
            (0.0, 1.0, 0.0), dw, dh, group=0)
    M.plate(decals, (px, (y0 + y1) * 0.5, 0.0), (0.0, 0.0, -1.0),
            (0.0, 1.0, 0.0), dw, dh, group=0)
    # wordmark band across the front faceplate -- the panel the player is
    # looking straight at while the tool is cocked
    M.plate(decals, (0.0, (win1 + y1) * 0.5, pz + 0.0012),
            (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
            (inner_w + S["plate_th"]) * 0.86, (y1 - win1) * 0.66,
            group=0, uv_rect=(0.03, 0.375, 0.97, 0.695))
    # nameplate on the front of the base block
    M.plate(decals, (0.0, S["base_y"] + bs[1] * 0.52, bs[2] * 0.5 + 0.0012),
            (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), bs[0] * 0.78, bs[1] * 0.62,
            group=0, uv_rect=(0.03, 0.375, 0.97, 0.695))
    node.add_mesh(decals)

    steel = M.Mesh("Stamp_Mechanism", MAT["steel"])
    M.cylinder(steel, (0.0, y0 - 0.01, 0.0), (0.0, y1 + 0.006, 0.0),
               S["column_r"], S["column_r"] * 0.88, 22, group=0)
    # cross-braces between the plates
    for by in (y0 + 0.012, y1 - 0.012):
        M.cylinder(steel, (-S["plate_x"], by, 0.0), (S["plate_x"], by, 0.0),
                   0.0072, 0.0072, 12, group=10)
    node.add_mesh(steel)

    # numbering wheels: the detail that says "Bates" at a glance
    wheels = M.Mesh("Stamp_NumberWheels", MAT["wheels"])
    wy, wr, wh = S["wheel_y"], S["wheel_r"], S["wheel_half"]
    ndisc = 6
    rings = []
    vs = []
    for i in range(ndisc):
        x0 = -wh + (2 * wh) * i / ndisc
        x1 = -wh + (2 * wh) * (i + 1) / ndisc
        for (xx, rr) in ((x0 + 0.0006, wr * 0.86), (x0 + 0.0022, wr),
                         (x1 - 0.0022, wr), (x1 - 0.0006, wr * 0.86)):
            prof = M.profile_ellipse(24, rr, rr)
            rings.append(M.ring_from_profile(prof, (xx, wy, 0.0),
                                             (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
            vs.append((xx + wh) / (2 * wh))
    wheels.add_loft(rings, v_coords=vs, uv_rect=(0, 0, 1, 1), group=0)
    wheels.add_grid_cap(rings[0], group=1, flip=True)
    wheels.add_grid_cap(rings[-1], group=2)
    node.add_mesh(wheels)

    # return spring around the column
    spring = M.Mesh("Stamp_Spring", MAT["steel"])
    turns, sub = 3.0, 13
    sp = []
    sy0, sy1 = win1 + 0.007, y1 - 0.004
    n = int(turns * sub)
    for i in range(n + 1):
        a = TAU * turns * i / n
        yy = sy0 + (sy1 - sy0) * i / n
        rr = S["column_r"] + 0.010
        sp.append((math.cos(a) * rr, yy, math.sin(a) * rr))
    M.tube_along_path(spring, sp, lambda t: M.profile_ellipse(8, 0.0034, 0.0034),
                      up_hint=(0.0, 1.0, 0.0), group=0)
    node.add_mesh(spring)

    # ---- plunger head + handle ------------------------------------------
    head = M.Mesh("Stamp_Head", MAT["orange"])
    M.box_chamfered(head, S["head_size"], 0.006,
                    (0.0, S["head_y"], 0.0), group=0)
    node.add_mesh(head)

    neck = M.Mesh("Stamp_Neck", MAT["steel"])
    M.cylinder(neck, (0.0, S["head_y"] + 0.010, 0.0),
               (0.0, S["handle_y"] - 0.004, 0.0), 0.0152, 0.0132, 18, group=0)
    node.add_mesh(neck)

    handle = M.Mesh("Stamp_Handle", MAT["grip"])
    hy, hh, hr = S["handle_y"], S["handle_half"], S["handle_r"]
    hp = [(-hh + (2 * hh) * i / 18.0, hy, 0.0) for i in range(19)]

    def hprof(t):
        # slight barrel through the middle: comfortable in a closed fist
        r = hr * (0.90 + 0.10 * math.sin(t * math.pi) ** 0.5)
        return M.profile_ellipse(18, r, r * 0.96)

    M.tube_along_path(handle, hp, hprof, up_hint=(0.0, 1.0, 0.0),
                      uv_rect=(0.0, 0.0, 1.0, 1.0), group=0,
                      cap_start=True, cap_end=True)
    node.add_mesh(handle)

    caps = M.Mesh("Stamp_HandleCaps", MAT["orange"])
    for sx in (-1, 1):
        x0 = sx * hh
        M.cylinder(caps, (x0, hy, 0.0), (x0 + sx * 0.017, hy, 0.0),
                   hr * 0.95, hr * 0.70, 18, group=0)
    node.add_mesh(caps)

    # The side foregrip is gone. A Bates numbering stamp is a one-handed desk
    # tool -- you hold it and drive it down -- so the two-handed grip was an
    # invention of the viewmodel rather than anything the object called for.
    # The left hand now carries the exhibits instead.

    return node


def build_documents(name="Exhibits"):
    """The sheaf of exhibits the left hand carries.

    Built in the grip's own frame: +X along the gripped edge, +Y the sheaf
    normal, +Z running away from the hand. The hand grips the near edge, so the
    stack extends forward and the fingers close on a slab about as thick as the
    bar the foregrip used to be.
    """
    w, th, d = RIG["docs_size"]
    n = RIG["docs_sheets"]
    node = Node(name)
    mesh = M.Mesh("Exhibit_Stack", MAT["paper"])
    rnd = random.Random(4021)
    for i in range(n):
        # each sheet fanned a little, so the stack reads as paper not a block
        f = i / max(1, n - 1) - 0.5
        y = -th * 0.5 + th * (i / max(1, n - 1))
        sx = rnd.uniform(-0.004, 0.004) + f * 0.010
        sz = rnd.uniform(-0.006, 0.010)
        yaw = rnd.uniform(-0.9, 0.9) + f * 2.4
        c, sn = math.cos(yaw * D2R), math.sin(yaw * D2R)
        t = th / n * 0.72
        corners = [(-w * 0.5, 0.0), (w * 0.5, 0.0), (w * 0.5, -d), (-w * 0.5, -d)]
        pts = []
        for (px, pz) in corners:
            rx = px * c - pz * sn + sx
            rz = px * sn + pz * c + sz
            pts.append((rx, rz))
        base = len(mesh.pos)
        for yy in (y, y + t):
            for (px, pz) in pts:
                mesh.add_vertex((px, yy, pz),
                                ((px / w) + 0.5, pz / d))
        b0, b1 = base, base + 4
        mesh.add_face((b1 + 0, b1 + 1, b1 + 2, b1 + 3), 0)      # top
        mesh.add_face((b0 + 3, b0 + 2, b0 + 1, b0 + 0), 1)      # bottom
        for k in range(4):
            k2 = (k + 1) % 4
            mesh.add_face((b0 + k, b0 + k2, b1 + k2, b1 + k), 2)
    node.add_mesh(mesh)
    return node


# ------------------------------------------------------------- assembly


def build_scene(bates="000137", images=None):
    scene = Scene("TomRexington_FPV")

    # ---- textures + materials -------------------------------------------
    for name, canvas in (images or TX.build_all(bates=bates)).items():
        scene.image(name, canvas)

    scene.material(Material(MAT["skin"], (1, 1, 1, 1), 0.0, 1.0,
                            "skin_basecolor", "skin_mr"))
    scene.material(Material(MAT["shirt"], (1, 1, 1, 1), 0.0, 1.0,
                            "shirt_basecolor", "shirt_mr"))
    scene.material(Material(MAT["steel"], (1, 1, 1, 1), 1.0, 1.0,
                            "steel_basecolor", "steel_mr"))
    scene.material(Material(MAT["black"], (1, 1, 1, 1), 1.0, 1.0,
                            "housing_plain_basecolor", "paint_mr"))
    scene.material(Material(MAT["decal"], (1, 1, 1, 1), 1.0, 1.0,
                            "housing_basecolor", "housing_mr"))
    scene.material(Material(MAT["orange"], (1, 1, 1, 1), 1.0, 1.0,
                            "accent_basecolor", "paint_mr"))
    scene.material(Material(MAT["rubber"], (1, 1, 1, 1), 0.0, 0.95,
                            "rubber_basecolor"))
    scene.material(Material(MAT["die"], (1, 1, 1, 1), 0.0, 1.0,
                            "stamp_die_basecolor", "stamp_die_mr"))
    scene.material(Material(MAT["grip"], (1, 1, 1, 1), 0.0, 1.0,
                            "grip_basecolor", "grip_mr"))
    scene.material(Material(MAT["paper"], hex_srgb("#F2F0EA"), 0.0, 0.86))
    scene.material(Material(MAT["watch_steel"], hex_srgb("#C9CDD4"), 1.0, 0.16))
    scene.material(Material(MAT["watch_dial"], hex_srgb("#0E1219"), 0.2, 0.18))
    scene.material(Material(MAT["wheels"], (1, 1, 1, 1), 0.85, 0.34,
                            "wheel_digits"))
    scene.material(Material(MAT["steel_cast"], hex_srgb("#8E949C"), 1.0, 0.44))

    root = Node("TomRexington_FPV_Rig")
    scene.add_root(root)

    # ---- stamp placement --------------------------------------------------
    stamp_world = vec.mat_mul(
        vec.mat_mul(vec.translate(RIG["stamp_pos"]), ready_rotation()),
        vec.scale(RIG["stamp_scale"]))
    stamp = build_stamp(bates)
    stamp.matrix = stamp_world
    root.add(stamp)

    # the stamp frame without scale -- hands hang off this, so the grips stay
    # rigid no matter what stamp_scale is set to
    stamp_rigid = vec.mat_mul(
        vec.translate(RIG["stamp_pos"]), ready_rotation())
    rig = {"stamp": stamp, "grip_local": {}, "hand_local": {},
           "arm_bind": {}, "arm": {}, "hand": {}, "fingers": {}}
    scene.rig = rig

    def to_world(p):
        return vec.xform_point(stamp_world, p)

    def dir_world(d):
        return vec.norm(vec.xform_dir(stamp_world, d))

    arms = []
    for side in ("R", "L"):
        if side == "R":
            axis = dir_world(RIG["grip_r_axis"])
            dorsal = dir_world(RIG["grip_r_dorsal"])
            point = to_world(RIG["grip_r_point"])
            gp = HAND["grip_point"]
            elbow_dir = RIG["elbow_dir_r"]
            bow = RIG["forearm_bow_r"]
            # primary hand: closes hardest, thumb locked over the front
            bar_r = STAMP["handle_r"] * RIG["stamp_scale"]
            tighten = {"Index": -0.0012, "Middle": -0.0018,
                       "Ring": -0.0016, "Pinky": -0.0010}
            thumb = {"curl": (40.0, 34.0), "splay": -56.0, "twist": -20.0,
                     "pitch": -22.0}
            roll = RIG["grip_r_roll"]
        else:
            # VIEW space, not stamp space: this hand carries the exhibits and
            # must not swing with the tool.
            axis = vec.norm(RIG["docs_axis"])
            dorsal = RIG["docs_dorsal"]
            point = RIG["docs_point"]
            gp = (-HAND["grip_point"][0], HAND["grip_point"][1],
                  HAND["grip_point"][2])
            elbow_dir = RIG["elbow_dir_l"]
            bow = RIG["forearm_bow_l"]
            # carrying hand: closes on the sheaf, relaxed rather than locked
            bar_r = RIG["docs_size"][1] * 0.58
            tighten = {"Index": -0.0008, "Middle": -0.0012,
                       "Ring": -0.0010, "Pinky": -0.0006}
            thumb = {"curl": (34.0, 28.0), "splay": -50.0, "twist": -26.0,
                     "pitch": -16.0}
            roll = RIG["docs_roll"]

        hand_world = grip_frame(axis, dorsal, point, gp, roll)
        wrist_world = (hand_world[3], hand_world[7], hand_world[11])

        arm_node, arm_world, path_at, frame_info = build_arm(
            "Arm_" + side, wrist_world, hand_world, elbow_dir, bow)

        hand = build_hand("Hand_" + side, bar_r, gp, tighten, thumb,
                          "_" + side)
        hand.matrix = vec.mat_mul(vec.rigid_inverse(arm_world), hand_world)
        if side == "R":
            mirror_node(hand)
            hand.name = "Hand_R"
        arm_node.add(hand)

        if side == "L":
            twisted, ts, _pts = frame_info
            arm_node.add(build_watch(path_at, twisted, ts))
            docs = build_documents()
            docs.matrix = vec.mat_mul(vec.rigid_inverse(arm_world), hand_world)
            arm_node.add(docs)

        root.add(arm_node)
        arms.append(arm_node)

        # everything the animation needs: the constant grip offset in the
        # stamp's rigid frame, and the bind wrist relationship
        rig["grip_local"][side] = vec.mat_mul(
            vec.rigid_inverse(stamp_rigid), hand_world)
        rig["hand_local"][side] = list(hand.matrix)
        rig["arm_bind"][side] = list(arm_node.matrix)
        rig["arm"][side] = arm_node
        rig["hand"][side] = hand
        rig["fingers"][side] = [c for c in hand.children
                                if hasattr(c, "bind_local")]

    # ---- locators the game hooks impact effects onto ---------------------
    # Emitter at the striking face. +Y points out of the face along the
    # strike direction; the compensating scale keeps its world scale at 1.
    anchor = Node("Stamp_DieAnchor",
                  vec.mat_mul(vec.rot_x(math.pi),
                              vec.scale(1.0 / RIG["stamp_scale"])))
    stamp.add(anchor)
    rig["die_anchor"] = anchor

    # The surface the die is driven into: origin on the plane, +Y = normal.
    ny = vec.norm(IMPACT["normal"])
    nz = vec.norm(vec.sub(IMPACT["front_hint"],
                          vec.mul(ny, vec.dot(IMPACT["front_hint"], ny))))
    plane = Node("Impact_Plane",
                 vec.mat_from_basis(vec.cross(ny, nz), ny, nz, IMPACT["point"]))
    root.add(plane)
    rig["impact_plane"] = plane

    return scene


# ------------------------------------------------------------- the swing


def ease(kind, t):
    t = max(0.0, min(1.0, t))
    if kind == "hold":
        return 0.0
    if kind == "linear":
        return t
    if kind == "out":          # fast off the mark, settles in
        return 1.0 - (1.0 - t) ** 2.2
    if kind == "in":           # loads up, then drives hard -- the slam
        return t ** 2.6
    return t * t * (3.0 - 2.0 * t)     # inout


def piecewise(beats, frame):
    """Sample a (frame, value, easing) curve, easing named on the later beat."""
    if frame <= beats[0][0]:
        return beats[0][1]
    for i in range(1, len(beats)):
        f0, v0, _ = beats[i - 1]
        f1, v1, k = beats[i]
        if frame <= f1:
            span = max(1e-9, f1 - f0)
            return v0 + (v1 - v0) * ease(k, (frame - f0) / span)
    return beats[-1][1]


def impact_rotation():
    """Stamp orientation with the die flush in the impact plane."""
    y = vec.norm(IMPACT["normal"])
    f = IMPACT["front_hint"]
    z = vec.norm(vec.sub(f, vec.mul(y, vec.dot(f, y))))
    x = vec.cross(y, z)
    base = vec.mat_from_basis(x, y, z)
    return vec.mat_mul(base, vec.mat_mul(vec.rot_y(IMPACT["yaw"] * D2R),
                                         vec.rot_z(IMPACT["roll"] * D2R)))


def ready_rotation():
    return vec.mat_mul(vec.rot_y(RIG["stamp_yaw"] * D2R),
                       vec.mat_mul(vec.rot_x(RIG["stamp_pitch"] * D2R),
                                   vec.rot_z(RIG["stamp_roll"] * D2R)))


def swing_stamp_rigid(s, press=0.0):
    """Stamp transform (no scale) for swing parameter `s`.

    s = 0 ready, s = 1 die planted on the impact plane, s < 0 cocked back.
    """
    p_ready = RIG["stamp_pos"]
    p_hit = IMPACT["point"]
    q_ready = vec.quat_from_mat(ready_rotation())
    q_hit = vec.quat_from_mat(impact_rotation())

    if s >= 0.0:
        mid = vec.lerp(p_ready, p_hit, 0.5)
        ctrl = vec.add(mid, SWING["arc"])
        pos = vec.bezier3(p_ready, ctrl, p_hit, s)
        q = vec.quat_slerp(q_ready, q_hit, s)
    else:
        k = s / SWING["windup_s"]          # 0 at ready, 1 at full cock
        pos = vec.mad(p_ready, SWING["windup_offset"], k)
        q_wind = vec.quat_from_mat(
            vec.mat_mul(vec.rot_x(SWING["windup_pitch"] * D2R), ready_rotation()))
        q = vec.quat_slerp(q_ready, q_wind, k)

    if press:
        pos = vec.mad(pos, IMPACT["normal"], -press)
    return vec.mat_mul(vec.translate(pos), vec.mat_from_quat(q))


def build_swing(scene, anim=None):
    """Bake Stamp_Swing onto the rig.

    The hands stay welded to their grips: each hand's world transform is the
    stamp's transform times a constant grip offset, and the forearm is then
    solved backwards from the hand. Wrist lag is the one place the arm is
    allowed to drift from the hand, which is what gives the swing follow
    through without the forearm geometry pulling apart at the wrist.
    """
    rig = scene.rig
    anim = anim or Animation(SWING["name"], SWING["fps"])
    fps = SWING["fps"]
    n = SWING["frames"]

    s_of = [piecewise(SWING["beats"], f) for f in range(n)]
    press_of = [piecewise(SWING["press"], f) for f in range(n)]
    poses = []

    for f in range(n):
        t = f / fps
        s = s_of[f]
        rigid = swing_stamp_rigid(s, press_of[f])
        full = vec.mat_mul(rigid, vec.scale(RIG["stamp_scale"]))
        anim.key_matrix(rig["stamp"], t, full)

        # swing velocity in frames, used for wrist lag and grip squeeze
        nxt = s_of[min(n - 1, f + 1)]
        prv = s_of[max(0, f - 1)]
        vel = (nxt - prv) * 0.5
        # taper the lag to nothing at both ends so the first and last frames
        # are exactly the ready stance -- the clip loops and blends cleanly
        edge = min(1.0, min(f, n - 1 - f) / 2.0)
        lag = max(-1.0, min(1.0, vel * 3.4)) * SWING["wrist_lag"] * D2R * edge
        squeeze = SWING["grip_squeeze"] * max(0.0, min(1.0, s)) ** 2 * D2R

        pose = {rig["stamp"]: full}
        for side in ("R", "L"):
            if side == "R":
                # welded to the tool: hand world is the stamp times a constant
                # grip offset, and the forearm follows from there
                hand_world = vec.mat_mul(rigid, rig["grip_local"][side])
                hand_local = vec.mat_mul(rig["hand_local"][side],
                                         vec.rot_x(-lag))
                arm_world = vec.mat_mul(hand_world,
                                        vec.rigid_inverse(hand_local))
                sq = squeeze
            else:
                # The carrying arm is not attached to the stamp, so it must not
                # inherit the swing. It braces instead: a small counter-lift as
                # the tool comes down, which reads as taking the weight rather
                # than as a limb pasted into frame.
                brace = SWING.get("carry_brace", 3.2) * D2R * max(0.0, min(1.0, s))
                arm_world = vec.mat_mul(rig["arm_bind"][side],
                                        vec.rot_x(-brace))
                hand_local = vec.mat_mul(rig["hand_local"][side],
                                         vec.rot_x(brace * 0.5))
                sq = squeeze * 0.35
            anim.key_matrix(rig["arm"][side], t, arm_world)
            anim.key_matrix(rig["hand"][side], t, hand_local)
            pose[rig["arm"][side]] = arm_world
            pose[rig["hand"][side]] = hand_local
            for node in rig["fingers"][side]:
                m = vec.mat_mul(node.bind_local,
                                vec.rot_x(sq * node.mirror_sign))
                anim.key_matrix(node, t, m)
                pose[node] = m
        poses.append(pose)
    anim.poses = poses
    return anim


def swing_report():
    """Text summary of the timing, and the die-to-plane distance per frame."""
    n = SWING["frames"]
    rows = []
    for f in range(n):
        s = piecewise(SWING["beats"], f)
        press = piecewise(SWING["press"], f)
        m = swing_stamp_rigid(s, press)
        face = (m[3], m[7], m[11])            # stamp origin == die face centre
        gap = vec.dot(vec.sub(face, IMPACT["point"]), IMPACT["normal"])
        rows.append((f, f / SWING["fps"], s, gap))
    return rows


# ---------------------------------------------------------------- previews


def make_previews(scene, outdir, quick=False):
    from tools.render import Camera, render

    os.makedirs(outdir, exist_ok=True)
    w, h = (640, 400) if quick else (1100, 690)
    sp = RIG["stamp_pos"]
    mid = (sp[0], sp[1] + 0.11, sp[2] + 0.03)
    stamp_world = None
    for r in scene.roots:
        for n in [r] + r.children:
            if n.name == "Stamp_Exhibitfy":
                stamp_world = n.matrix
    if stamp_world is None:
        stamp_world = vec.translate(sp)

    # name, camera, wireframe, only-these-root-nodes
    shots = [
        ("fpv_main", Camera((0, 0, 0), (0, -0.10, -1), fov_deg=62), False, None),
        ("fpv_wireframe", Camera((0, 0, 0), (0, -0.10, -1), fov_deg=62), True,
         None),
        ("fpv_hero_left", Camera((-0.40, 0.16, -0.06), (0.07, -0.20, -0.58),
                                 fov_deg=50), False, None),
        ("stamp_three_quarter",
         Camera((sp[0] + 0.34, sp[1] + 0.26, sp[2] + 0.42), mid, fov_deg=40),
         False, ["Stamp_Exhibitfy"]),
        ("stamp_flank",
         Camera((sp[0] + 0.52, sp[1] + 0.10, sp[2] + 0.10), mid, fov_deg=36),
         False, ["Stamp_Exhibitfy"]),
        # straight down the striking normal, with the tool's front as screen
        # up -- the canonical way to read the die
        ("stamp_die_face",
         Camera(vec.xform_point(stamp_world, (0.0, -0.32, 0.0)),
                vec.xform_point(stamp_world, (0.0, 0.0, 0.0)),
                up=vec.norm(vec.xform_dir(stamp_world, (0.0, 0.0, 1.0))),
                fov_deg=34), False, ["Stamp_Exhibitfy"]),
        ("hand_right_detail", Camera((-0.10, 0.20, -0.16), (0.13, -0.07, -0.44),
                                     fov_deg=34), False, None),
        ("hand_left_watch", Camera((-0.26, 0.10, -0.20), (-0.05, -0.19, -0.49),
                                   fov_deg=34), False, None),
    ]
    made = []
    all_roots = list(scene.roots)
    by_name = {}

    def collect(n):
        by_name[n.name] = n
        for c in n.children:
            collect(c)

    for r in all_roots:
        collect(r)

    for name, cam, wire, only in shots:
        t = time.time()
        if only:
            scene.roots = [by_name[n] for n in only if n in by_name]
        else:
            scene.roots = all_roots
        img = render(scene, cam, w, h, wireframe=wire)
        p = os.path.join(outdir, name + ".png")
        img.save(p)
        made.append(p)
        print("  %-20s %5.1fs  %s" % (name, time.time() - t, p))
    scene.roots = all_roots
    return made


# -------------------------------------------------------------------- main


def debug_paper_node(scene):
    """A sheet of paper lying in the impact plane -- previews only.

    Never added to the exported scene: the plane is shipped as the
    `Impact_Plane` locator so the game can place its own surface and effects.
    """
    scene.material(Material("Paper_Debug", hex_srgb("#E9E7E1"), 0.0, 0.88,
                            double_sided=True))
    ny = vec.norm(IMPACT["normal"])
    nz = vec.norm(vec.sub(IMPACT["front_hint"],
                          vec.mul(ny, vec.dot(IMPACT["front_hint"], ny))))
    nx = vec.cross(ny, nz)
    m = M.Mesh("Debug_Paper", "Paper_Debug")
    origin = vec.mad(IMPACT["point"], ny, -0.0012)
    M.plate(m, origin, nz, nx, 0.30, 0.40, group=0)
    return Node("Debug_Paper", meshes=[m])


def render_swing(scene, anim, outdir, quick=False):
    """Render every frame of the swing: an APNG plus a contact sheet."""
    from tools.render import Camera, render

    w, h = (300, 188) if quick else (440, 275)
    cam = Camera((0, 0, 0), (0, -0.16, -1), fov_deg=62)
    paper = debug_paper_node(scene)
    scene.roots.append(paper)
    saved = {}
    for pose in anim.poses:
        for node in pose:
            saved.setdefault(id(node), (node, list(node.matrix)))

    frames = []
    t0 = time.time()
    try:
        for i, pose in enumerate(anim.poses):
            for node, m in pose.items():
                node.matrix = list(m)
            frames.append(render(scene, cam, w, h))
    finally:
        for node, m in saved.values():
            node.matrix = m
        scene.roots.remove(paper)
        scene.materials.pop("Paper_Debug", None)

    apng = os.path.join(outdir, "stamp_swing.png")
    write_apng(frames, apng, fps=anim.fps)

    cols, gap = 6, 4
    rows = (len(frames) + cols - 1) // cols
    tw, th = w // 2, h // 2
    sheet = Canvas(cols * tw + (cols + 1) * gap, rows * th + (rows + 1) * gap,
                   (0.10, 0.11, 0.13))
    for i, f in enumerate(frames):
        small = f.resized(tw, th)
        sheet.blit(small, gap + (i % cols) * (tw + gap),
                   gap + (i // cols) * (th + gap))
    sheet_path = os.path.join(outdir, "stamp_swing_frames.png")
    sheet.save(sheet_path)
    print("  %-20s %5.1fs  %s (+ contact sheet)"
          % ("stamp_swing", time.time() - t0, apng))
    return apng, sheet_path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bates", default="000137",
                    help="number shown on the stamp die face")
    ap.add_argument("--out", default="build")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="smaller preview renders")
    args = ap.parse_args(argv)

    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)
    tex_dir = os.path.join(args.out, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    print("building scene...")
    scene = build_scene(args.bates)
    anim = scene.animation(build_swing(scene))
    plant = [r for r in swing_report() if r[3] <= 0.0]
    print("  %s: %d frames @ %g fps (%.3fs), %d planted frame(s) %s"
          % (anim.name, SWING["frames"], SWING["fps"],
             SWING["frames"] / SWING["fps"], len(plant),
             [r[0] for r in plant]))

    for name, canvas in scene.images.items():
        canvas.save(os.path.join(tex_dir, name + ".png"))
    print("  %d textures -> %s" % (len(scene.images), tex_dir))

    glb = os.path.join(args.out, "exhibitfy_fpv_arms.glb")
    export_glb(scene, glb)
    obj = os.path.join(args.out, "exhibitfy_fpv.obj")
    export_obj(scene, obj)

    # A single-object copy of the same geometry. The rigged file is 16 objects
    # so it can animate; in a DCC that means Edit Mode only ever shows the one
    # you have selected. This one opens as a single mesh with a material slot
    # per material -- select, tab in, and everything is there.
    single = scene.merged("TomRexington_FPV")
    solo = os.path.join(args.out, "exhibitfy_fpv_arms_single_mesh.glb")
    export_glb(single, solo)

    st = scene.stats()
    print("  meshes %d | quads %d | triangles %d"
          % (st["meshes"], st["quads"], st["triangles"]))
    print("  %s (%.1f KB)  rigged, %s" % (glb, os.path.getsize(glb) / 1024.0,
                                          anim.name))
    print("  %s (%.1f KB)  single mesh, static"
          % (solo, os.path.getsize(solo) / 1024.0))
    print("  %s" % obj)

    if not args.no_preview:
        print("rendering previews...")
        prev = os.path.join(args.out, "previews")
        make_previews(scene, prev, args.quick)
        render_swing(scene, anim, prev, args.quick)

    print("done in %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
