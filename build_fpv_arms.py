#!/usr/bin/env python3
"""Tom Rexington, Esq. -- first-person arms + Exhibitfy Bates stamp.

Builds the FPV viewmodel for "Tom Rexington, Esq.: Bates & Destroy":
forearms in rolled-up dress shirt sleeves, hands gripping a heavy Exhibitfy
Bates stamp, posed mid-ready to slam forward.

    python3 build_fpv_arms.py [--no-preview] [--bates 000137]

Outputs into build/:
    exhibitfy_fpv_arms.glb      runtime asset (PBR + embedded textures)
    exhibitfy_fpv.obj / .mtl    quad-preserved editable mesh
    textures/*.png              every map, as authored
    previews/*.png              software renders incl. a wireframe pass

Conventions: metres, Y-up, camera at the origin looking down -Z (glTF style).
Every tunable number lives in the RIG / STAMP / HAND dicts near the top.
"""

import argparse
import math
import os
import sys
import time

from tools import glyphs, mesh as M, textures as TX, vec
from tools.gltf import Material, Node, Scene, export_glb
from tools.imaging import Canvas, hex_srgb
from tools.objexport import export_obj

TAU = math.pi * 2.0
D2R = math.pi / 180.0

# ---------------------------------------------------------------- tuning

HAND = {
    "palm_len": 0.094,
    "palm_w0": 0.058,      # at the wrist
    "palm_w1": 0.086,      # across the knuckles
    "palm_t0": 0.037,
    "palm_t1": 0.031,
    "palm_rings": 9,
    "palm_sides": 16,
    "finger_sides": 8,
    # a gripped bar sits here in hand-local space (used by the grip solver)
    "grip_point": (0.0, -0.036, 0.074),
}

# name, root(x, y, z-offset from knuckle line), radius, phalanx lengths,
# splay (deg about Y), curl (deg per phalanx)
FINGERS = [
    ("Index",  (-0.0305, 0.0035, -0.004), 0.0118, (0.040, 0.026, 0.021), -7.0),
    ("Middle", (-0.0100, 0.0045, 0.000),  0.0124, (0.044, 0.029, 0.022), -1.0),
    ("Ring",   (0.0105, 0.0035, -0.004),  0.0114, (0.041, 0.027, 0.021), 5.0),
    ("Pinky",  (0.0290, 0.0010, -0.014),  0.0098, (0.033, 0.022, 0.018), 12.0),
]

STAMP = {
    # base / die
    "pad_size": (0.128, 0.017, 0.092),
    "pad_y": 0.004,
    "base_size": (0.146, 0.050, 0.112),
    "base_y": 0.021,          # bottom of the base block
    "collar_h": 0.011,
    # tower
    "tower_y0": 0.071,
    "tower_y1": 0.213,
    "plate_x": 0.054,
    "plate_th": 0.013,
    "plate_z": 0.094,
    "column_r": 0.0225,
    "wheel_y": 0.118,
    "wheel_r": 0.0335,
    "wheel_half": 0.042,
    # head + handle
    "head_y": 0.226,
    "head_size": (0.104, 0.030, 0.058),
    "handle_y": 0.264,
    "handle_half": 0.089,
    "handle_r": 0.0205,
    # side foregrip (left-hand support)
    "grip_root": (-0.064, 0.052, 0.020),
    "grip_tip": (-0.156, 0.014, 0.062),
    "grip_r": 0.0192,
}

RIG = {
    # where the stamp sits in camera space, and how it is cocked.
    # stamp_pos is the centre of the striking face.
    "stamp_pos": (0.115, -0.222, -0.518),
    "stamp_scale": 1.22,      # the tool is deliberately oversized and heavy
    "stamp_pitch": 24.0,      # about X: cocks the tower back towards the player
    "stamp_yaw": -16.0,       # about Y: turns the branded flank into view
    "stamp_roll": 6.0,        # about Z: aggressive diagonal
    # grips, in stamp-local space
    "grip_r_point": (0.043, 0.264, 0.0),      # right hand on the T-bar
    "grip_r_axis": (1.0, 0.0, 0.0),
    "grip_r_dorsal": (0.05, 1.0, 0.15),
    "grip_l_point": (-0.112, 0.031, 0.043),   # left hand on the foregrip
    "grip_l_axis": (0.876, 0.362, -0.400),
    "grip_l_dorsal": (-0.12, 1.0, 0.30),
    # forearms: direction from wrist back to the elbow, and length
    "forearm_len": 0.272,
    "elbow_dir_r": (0.46, -0.76, 0.46),
    "elbow_dir_l": (-0.44, -0.79, 0.43),
    "forearm_bow_r": (0.026, -0.016, 0.024),
    "forearm_bow_l": (-0.026, -0.020, 0.022),
    # forearm cross-section
    "r_elbow": (0.056, 0.051),
    "r_mid": (0.046, 0.041),
    "r_wrist": (0.034, 0.0265),
    "sleeve_pad": 0.0105,
    "sleeve_t0": -0.95,       # extends behind the elbow, off-camera
    "sleeve_t1": 0.46,        # rolled up to mid-forearm
    "cuff_t0": 0.29,          # where the roll starts
    "cuff_bulge": 0.0105,
    "watch_t": 0.862,
}

# A second keyframe, purely to show the rig drives everything from RIG: the
# tool punched forward and down at full extension, i.e. the moment of impact.
POSE_IMPACT = {
    "stamp_pos": (0.030, -0.402, -0.780),
    "stamp_pitch": 8.0,
    "stamp_yaw": -6.0,
    "stamp_roll": 2.0,
    "elbow_dir_r": (0.62, -0.42, 0.66),
    "elbow_dir_l": (-0.60, -0.48, 0.64),
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
    for m in node.meshes:
        mirror_mesh(m)
    for c in node.children:
        mirror_node(c, mirror_matrix=True)
    return node


def grip_frame(axis, dorsal, point, grip_local):
    """Rigid transform placing a hand so `grip_local` lands on `point`
    with hand-local +X along `axis` and +Y towards `dorsal`."""
    x = vec.norm(axis)
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


def build_finger(name, root, radius, phal, splay, curl, side_uv):
    """One finger as a tapered, curled tube of quad loops.

    Built in finger-local space (origin at the knuckle, +Z down the finger)
    so the node transform can be keyframed straight away.
    """
    m = M.Mesh("Finger_" + name, MAT["skin"])
    n = HAND["finger_sides"]

    # walk the curl, sampling each phalanx into several loops
    pts = [(0.0, 0.0, 0.0)]
    radii = [radius]
    d = (0.0, 0.0, 1.0)
    knuckles = [0]
    for pi, (ln, ang) in enumerate(zip(phal, curl)):
        sub = 3
        for s in range(sub):
            a = (ang * D2R) / sub
            # curl bends towards the palm (-Y)
            r = vec.rot_x(a)
            d = vec.norm(vec.xform_dir(r, d))
            p = vec.mad(pts[-1], d, ln / sub)
            pts.append(p)
            t = (pi * sub + s + 1) / (len(phal) * sub)
            taper = radius * (1.0 - 0.30 * t)
            # slight swell over each joint reads as a knuckle
            if s == sub - 1 and pi < len(phal) - 1:
                taper *= 1.10
            elif s == 0:
                taper *= 1.05
            radii.append(taper)
        knuckles.append(len(pts) - 1)

    frames = vec.parallel_frames(pts, (0.0, 1.0, 0.0))
    rings = []
    for i, (p, f) in enumerate(zip(pts, frames)):
        rx = radii[i]
        ry = radii[i] * 0.93          # fingers are wider than they are deep
        prof = M.profile_super(n, rx, ry, 2.5)
        rings.append(M.ring_from_profile(prof, p, f[0], f[1]))

    v0, v1 = side_uv
    m.add_loft(rings, uv_rect=(0.0, v0, 1.0, v1), group=0)
    m.add_grid_cap(rings[0], group=0, flip=True)
    tip_axis = vec.mul(vec.sub(pts[-1], pts[-2]), 1.0)
    apex = vec.mad(pts[-1], vec.norm(tip_axis), radii[-1] * 1.15)
    M.dome_tip(m, rings[-1], apex, steps=2, group=0,
               uv_rect=(0.0, v1 - (v1 - v0) * 0.06, 1.0, v1))

    node = Node("Finger_" + name,
                vec.mat_mul(vec.translate(root), vec.rot_y(splay * D2R)),
                meshes=[m])
    return node


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
        y = -0.004 * t * t
        z = L * t
        prof = M.profile_super(n, w * 0.5, th * 0.5, 3.1)
        ring = []
        for (px, py) in prof:
            # thenar (thumb ball) and hypothenar pads -- the "strong hand" read
            thenar = math.exp(-((t - 0.34) ** 2) / 0.030) * \
                max(0.0, -px / (w * 0.5)) * max(0.0, -py / (th * 0.5)) * 0.011
            hypo = math.exp(-((t - 0.45) ** 2) / 0.055) * \
                max(0.0, px / (w * 0.5)) * max(0.0, -py / (th * 0.5)) * 0.006
            grow = 1.0 + (thenar + hypo) / max(1e-5, th * 0.5)
            ring.append((px - thenar * 0.9, y + py * grow, z))
        # close the seam
        ring[-1] = ring[0]
        out.append(ring)
    m.add_loft(out, uv_rect=(0.0, v0, 1.0, v1), group=0)
    m.add_grid_cap(out[0], group=1, flip=True)
    m.add_grid_cap(out[-1], group=0)
    return m


def build_thumb(side_uv, curl=(38.0, 34.0), splay=-46.0, twist=-32.0):
    m = M.Mesh("Thumb", MAT["skin"])
    n = HAND["finger_sides"]
    radius = 0.0152
    phal = (0.040, 0.032)
    pts = [(0.0, 0.0, 0.0)]
    radii = [radius]
    d = (0.0, 0.0, 1.0)
    for pi, (ln, ang) in enumerate(zip(phal, curl)):
        sub = 3
        for s in range(sub):
            d = vec.norm(vec.xform_dir(vec.rot_x((ang * D2R) / sub), d))
            pts.append(vec.mad(pts[-1], d, ln / sub))
            t = (pi * sub + s + 1) / (len(phal) * sub)
            radii.append(radius * (1.0 - 0.26 * t))
    frames = vec.parallel_frames(pts, (0.0, 1.0, 0.0))
    rings = []
    for i, (p, f) in enumerate(zip(pts, frames)):
        prof = M.profile_super(n, radii[i], radii[i] * 0.90, 2.5)
        rings.append(M.ring_from_profile(prof, p, f[0], f[1]))
    v0, v1 = side_uv
    m.add_loft(rings, uv_rect=(0.0, v0, 1.0, v1), group=0)
    m.add_grid_cap(rings[0], group=0, flip=True)
    apex = vec.mad(pts[-1], vec.norm(vec.sub(pts[-1], pts[-2])), radii[-1] * 1.2)
    M.dome_tip(m, rings[-1], apex, steps=2, group=0,
               uv_rect=(0.0, v1 - (v1 - v0) * 0.06, 1.0, v1))

    root = (-HAND["palm_w0"] * 0.46, -0.004, 0.020)
    mtx = vec.mat_mul(vec.translate(root),
                      vec.mat_mul(vec.rot_y(splay * D2R), vec.rot_z(twist * D2R)))
    return Node("Thumb", mtx, meshes=[m])


def build_hand(name, curls=None, thumb=None):
    """Right hand in canonical local space: +Z fingers, +Y dorsal, -X thumb."""
    curls = curls or {}
    hv = TX.HAND_V
    node = Node(name)
    node.add_mesh(build_palm(hv))
    for fname, root, radius, phal, splay in FINGERS:
        curl = curls.get(fname, (52.0, 72.0, 46.0))
        r = (root[0], root[1], HAND["palm_len"] + root[2])
        node.add(build_finger(fname, r, radius, phal, splay, curl, hv))
    tk = thumb or {}
    node.add(build_thumb(hv, **tk))
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
    steps = 15
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
    csteps = 18
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
               group=0, cap_start=False, up_hint=fwd)
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

    # ---- rubber pad + die face -----------------------------------------
    pad = M.Mesh("Stamp_Pad", MAT["rubber"])
    M.box_chamfered(pad, S["pad_size"], 0.004,
                    (0.0, S["pad_y"] + S["pad_size"][1] * 0.5, 0.0), group=0)
    node.add_mesh(pad)

    die = M.Mesh("Stamp_DieFace", MAT["die"])
    # Type reads the right way up when the player sees the face during the
    # slam (a real die would be mirrored -- this one is built to be read).
    M.plate(die, (0.0, S["pad_y"] - 0.0006, 0.0), (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0), S["pad_size"][0] * 0.90, S["pad_size"][2] * 0.90,
            group=0, uv_rect=(0.0, 0.0, 1.0, 1.0), subdiv=2)
    node.add_mesh(die)

    # ---- base block -----------------------------------------------------
    base = M.Mesh("Stamp_Base", MAT["black"])
    bs = S["base_size"]
    M.box_chamfered(base, bs, 0.007, (0.0, S["base_y"] + bs[1] * 0.5, 0.0),
                    group=0, segments=2)
    node.add_mesh(base)

    collar = M.Mesh("Stamp_Collar", MAT["orange"])
    M.box_chamfered(collar, (bs[0] * 1.015, S["collar_h"], bs[2] * 1.015), 0.004,
                    (0.0, S["base_y"] + bs[1] - S["collar_h"] * 0.4, 0.0),
                    group=0)
    node.add_mesh(collar)

    # ---- tower ----------------------------------------------------------
    # Two side plates, a solid back, and a front faceplate with a window that
    # the numbering wheels show through -- the Bates read at a glance.
    y0, y1 = S["tower_y0"], S["tower_y1"]
    pz = S["plate_z"] * 0.5
    win0 = S["wheel_y"] - S["wheel_r"] - 0.006
    win1 = S["wheel_y"] + S["wheel_r"] + 0.006
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
               S["column_r"], S["column_r"] * 0.88, 18, group=0)
    # cross-braces between the plates
    for by in (y0 + 0.012, y1 - 0.012):
        M.cylinder(steel, (-S["plate_x"], by, 0.0), (S["plate_x"], by, 0.0),
                   0.008, 0.008, 10, group=10)
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
            prof = M.profile_ellipse(20, rr, rr)
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
    M.tube_along_path(spring, sp, lambda t: M.profile_ellipse(6, 0.0038, 0.0038),
                      up_hint=(0.0, 1.0, 0.0), group=0)
    node.add_mesh(spring)

    # ---- plunger head + handle ------------------------------------------
    head = M.Mesh("Stamp_Head", MAT["orange"])
    M.box_chamfered(head, S["head_size"], 0.006,
                    (0.0, S["head_y"], 0.0), group=0)
    node.add_mesh(head)

    neck = M.Mesh("Stamp_Neck", MAT["steel"])
    M.cylinder(neck, (0.0, S["head_y"] + 0.010, 0.0),
               (0.0, S["handle_y"] - 0.004, 0.0), 0.016, 0.014, 14, group=0)
    node.add_mesh(neck)

    handle = M.Mesh("Stamp_Handle", MAT["grip"])
    hy, hh, hr = S["handle_y"], S["handle_half"], S["handle_r"]
    hp = [(-hh + (2 * hh) * i / 14.0, hy, 0.0) for i in range(15)]

    def hprof(t):
        # slight barrel through the middle: comfortable in a closed fist
        r = hr * (0.90 + 0.10 * math.sin(t * math.pi) ** 0.5)
        return M.profile_ellipse(14, r, r * 0.96)

    M.tube_along_path(handle, hp, hprof, up_hint=(0.0, 1.0, 0.0),
                      uv_rect=(0.0, 0.0, 1.0, 1.0), group=0,
                      cap_start=False, cap_end=False)
    node.add_mesh(handle)

    caps = M.Mesh("Stamp_HandleCaps", MAT["orange"])
    for sx in (-1, 1):
        x0 = sx * hh
        M.cylinder(caps, (x0, hy, 0.0), (x0 + sx * 0.017, hy, 0.0),
                   hr * 0.95, hr * 0.72, 14, group=0)
    node.add_mesh(caps)

    # ---- side foregrip ---------------------------------------------------
    gr = M.Mesh("Stamp_Foregrip", MAT["grip"])
    g0, g1 = S["grip_root"], S["grip_tip"]
    gp = [vec.lerp(g0, g1, i / 9.0) for i in range(10)]
    M.tube_along_path(gr, gp, lambda t: M.profile_ellipse(
        12, S["grip_r"] * (0.94 + 0.09 * math.sin(t * math.pi)),
        S["grip_r"] * 0.93), up_hint=(0.0, 1.0, 0.0), group=0,
        cap_start=False, cap_end=False)
    node.add_mesh(gr)

    gcap = M.Mesh("Stamp_ForegripFittings", MAT["orange"])
    d = vec.norm(vec.sub(g1, g0))
    M.cylinder(gcap, vec.mad(g0, d, -0.004), vec.mad(g0, d, 0.016),
               S["grip_r"] * 1.20, S["grip_r"] * 1.02, 14, group=0,
               up_hint=(0.0, 1.0, 0.0))
    M.cylinder(gcap, vec.mad(g1, d, -0.012), vec.mad(g1, d, 0.006),
               S["grip_r"] * 1.02, S["grip_r"] * 1.18, 14, group=3,
               up_hint=(0.0, 1.0, 0.0))
    node.add_mesh(gcap)

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
    scene.material(Material(MAT["black"], TX.BRAND["black"], 0.25, 0.44))
    scene.material(Material(MAT["decal"], (1, 1, 1, 1), 1.0, 1.0,
                            "housing_basecolor", "housing_mr"))
    scene.material(Material(MAT["orange"], TX.BRAND["orange"], 0.10, 0.34))
    scene.material(Material(MAT["rubber"], hex_srgb("#17181C"), 0.0, 0.92))
    scene.material(Material(MAT["die"], (1, 1, 1, 1), 0.0, 1.0,
                            "stamp_die_basecolor", "stamp_die_mr"))
    scene.material(Material(MAT["grip"], (1, 1, 1, 1), 0.0, 1.0,
                            "grip_basecolor", "grip_mr"))
    scene.material(Material(MAT["watch_steel"], hex_srgb("#C9CDD4"), 1.0, 0.20))
    scene.material(Material(MAT["watch_dial"], hex_srgb("#0E1219"), 0.2, 0.18))
    scene.material(Material(MAT["wheels"], (1, 1, 1, 1), 0.85, 0.34,
                            "wheel_digits"))

    root = Node("TomRexington_FPV_Rig")
    scene.add_root(root)

    # ---- stamp placement --------------------------------------------------
    stamp_world = vec.mat_mul(
        vec.translate(RIG["stamp_pos"]),
        vec.mat_mul(vec.rot_y(RIG["stamp_yaw"] * D2R),
                    vec.mat_mul(vec.rot_x(RIG["stamp_pitch"] * D2R),
                                vec.mat_mul(vec.rot_z(RIG["stamp_roll"] * D2R),
                                            vec.scale(RIG["stamp_scale"])))))
    stamp = build_stamp(bates)
    stamp.matrix = stamp_world
    root.add(stamp)

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
            curls = {"Index": (54.0, 74.0, 44.0), "Middle": (56.0, 76.0, 46.0),
                     "Ring": (58.0, 78.0, 46.0), "Pinky": (60.0, 80.0, 48.0)}
            thumb = {"curl": (30.0, 26.0), "splay": -52.0, "twist": -28.0}
        else:
            axis = dir_world(RIG["grip_l_axis"])
            dorsal = dir_world(RIG["grip_l_dorsal"])
            point = to_world(RIG["grip_l_point"])
            gp = (-HAND["grip_point"][0], HAND["grip_point"][1],
                  HAND["grip_point"][2])
            elbow_dir = RIG["elbow_dir_l"]
            bow = RIG["forearm_bow_l"]
            curls = {"Index": (57.0, 79.0, 48.0), "Middle": (59.0, 81.0, 50.0),
                     "Ring": (61.0, 83.0, 50.0), "Pinky": (63.0, 85.0, 52.0)}
            thumb = {"curl": (34.0, 30.0), "splay": -48.0, "twist": -30.0}

        hand_world = grip_frame(axis, dorsal, point, gp)
        wrist_world = (hand_world[3], hand_world[7], hand_world[11])

        arm_node, arm_world, path_at, frame_info = build_arm(
            "Arm_" + side, wrist_world, hand_world, elbow_dir, bow)

        hand = build_hand("Hand_" + side, curls, thumb)
        hand.matrix = vec.mat_mul(vec.rigid_inverse(arm_world), hand_world)
        if side == "L":
            mirror_node(hand)
            hand.name = "Hand_L"
        arm_node.add(hand)

        if side == "L":
            twisted, ts, _pts = frame_info
            arm_node.add(build_watch(path_at, twisted, ts))

        # name meshes per side for tidy outliners
        for m in arm_node.meshes:
            m.name = m.name
        root.add(arm_node)
        arms.append(arm_node)

    return scene


# ---------------------------------------------------------------- previews


def make_previews(scene, outdir, quick=False):
    from tools.render import Camera, render

    os.makedirs(outdir, exist_ok=True)
    w, h = (640, 400) if quick else (1100, 690)
    sp = RIG["stamp_pos"]
    mid = (sp[0], sp[1] + 0.13, sp[2] + 0.03)

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
        ("stamp_die_face",
         Camera((sp[0] + 0.06, sp[1] - 0.42, sp[2] + 0.16), (sp[0], sp[1], sp[2]),
                fov_deg=38), False, ["Stamp_Exhibitfy"]),
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

    for name, canvas in scene.images.items():
        canvas.save(os.path.join(tex_dir, name + ".png"))
    print("  %d textures -> %s" % (len(scene.images), tex_dir))

    glb = os.path.join(args.out, "exhibitfy_fpv_arms.glb")
    export_glb(scene, glb)
    obj = os.path.join(args.out, "exhibitfy_fpv.obj")
    export_obj(scene, obj)

    st = scene.stats()
    print("  meshes %d | quads %d | triangles %d"
          % (st["meshes"], st["quads"], st["triangles"]))
    print("  %s (%.1f KB)" % (glb, os.path.getsize(glb) / 1024.0))
    print("  %s" % obj)

    if not args.no_preview:
        print("rendering previews...")
        prev = os.path.join(args.out, "previews")
        make_previews(scene, prev, args.quick)

        # second keyframe: same rig, different RIG numbers
        from tools.render import Camera, render
        saved = dict(RIG)
        RIG.update(POSE_IMPACT)
        try:
            impact = build_scene(args.bates, images=scene.images)
            t = time.time()
            w, h = (640, 400) if args.quick else (1100, 690)
            img = render(impact, Camera((0, 0, 0), (0, -0.16, -1), fov_deg=62),
                         w, h)
            img.save(os.path.join(prev, "pose_impact.png"))
            print("  %-20s %5.1fs  %s/pose_impact.png"
                  % ("pose_impact", time.time() - t, prev))
        finally:
            RIG.clear()
            RIG.update(saved)

    print("done in %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
