#!/usr/bin/env python3
"""Paper enemies for "Tom Rexington, Esq.: Bates & Destroy".

Four anthropomorphic legal documents in the same industrial-cartoon register
as the Exhibitfy stamp: a sheet with real thickness and curl, rubber-hose
limbs, and a face drawn on the page. Each ships a looping Run cycle and a
one-shot Stamped reaction that leaves a bold orange/black Bates impression.

    python3 build_enemies.py [--no-preview] [--only pleading]

Outputs into build/enemies/:
    enemy_<variant>.glb    runtime asset, Run + Stamped animations baked in
    previews/*.png         stills, run-cycle and stamped-reaction contact sheets

Conventions: metres, Y-up, -Z forward (the direction the enemy runs). The rig
origin sits on the ground between the feet, so instances drop straight onto a
floor at y = 0.
"""

import argparse
import math
import os
import sys
import time

from tools import mesh as M, paper_textures as PT, vec
from tools.gltf import Animation, Material, Node, Scene, export_glb
from tools.imaging import Canvas, hex_srgb, write_apng
from tools.textures import BRAND

D2R = math.pi / 180.0
TAU = math.pi * 2.0

# ------------------------------------------------------------------ tuning

SHEET = {
    "w": 0.400,
    "h": 0.520,
    "thick": 0.0055,
    "nx": 6,
    "ny": 8,
    "curl": (0.030, 0.022, 0.016),   # corner curl, edge bow, twist
}

BODY_Y = 0.415          # sheet centre above the ground
HIP = (0.058, 0.166)    # x offset, y height
SHOULDER = (0.212, 0.560)

LIMB = {
    "thigh": 0.086, "shin": 0.078, "leg_r": (0.0225, 0.0165),
    "upper": 0.084, "fore": 0.076, "arm_r": (0.0185, 0.0140),
    "sides": 8,
}

MAT = {
    "paper": "Paper_Pleading",
    "privileged": "Paper_Privileged",
    "alt": "Paper_Filing",
    "binder": "Binder_Board",
    "face": "Face_Decal",
    "mark": "Bates_Impression",
    "limb": "Limb_Ink",
    "glove": "Glove_White",
    "shoe": "Shoe_Black",
    "ring": "Binder_Rings",
}

# ---------------------------------------------------------------- variants

VARIANTS = {
    "pleading": {
        "label": "Pleading Paper",
        "paper": "paper",
        "sheets": 1,
        "scale": 1.0,
        "run": {"cadence": 1.0, "stride": 46.0, "bob": 0.052, "lean": 11.0,
                "sway": 0.014, "flutter": 7.0, "jitter": 1.0, "arm": 38.0},
        "face": "calm",
    },
    "privilege": {
        "label": "Privilege Paper",
        "paper": "privileged",
        "sheets": 1,
        "scale": 0.97,
        # evasive and smug: less honest sprinting, more side-stepping
        "run": {"cadence": 1.12, "stride": 38.0, "bob": 0.038, "lean": 4.0,
                "sway": 0.052, "flutter": 11.0, "jitter": 0.5, "arm": 27.0,
                "dodge": 1.0},
        "face": "smug",
    },
    "binder": {
        "label": "Thick Discovery Binder",
        "paper": "binder",
        "sheets": 7,
        "scale": 1.16,
        # heavy: slow cadence, deep bob, hard landings, minimal arm swing
        "run": {"cadence": 0.66, "stride": 34.0, "bob": 0.070, "lean": 15.0,
                "sway": 0.020, "flutter": 3.0, "jitter": 0.3, "arm": 20.0,
                "thud": 1.0},
        "face": "calm",
    },
    "stack": {
        "label": "Chaotic PDF Stack",
        "paper": "alt",
        "sheets": 5,
        "scale": 1.04,
        "run": {"cadence": 1.25, "stride": 50.0, "bob": 0.058, "lean": 8.0,
                "sway": 0.030, "flutter": 16.0, "jitter": 2.0, "arm": 44.0,
                "scatter": 1.0},
        "face": "panic",
    },
}

RUN_FRAMES = 20         # frames per stride at cadence 1.0; cadence scales it
STAMP_FRAMES = 26
FPS = 30.0


# ------------------------------------------------------------------ sheet


def curl_offset(u, v, k=None):
    """Z displacement across the page: corner curl + bow + a little twist.

    u, v are -1..1 across the sheet. Paper never lies flat, and the curl is
    most of what sells "this is a sheet" in silhouette.
    """
    k = k or SHEET["curl"]
    corner = (u * u) * (0.35 + 0.65 * abs(v)) * k[0]
    bow = (1.0 - v * v) * k[1] * -0.5 + (v * v * v) * k[1] * 0.6
    twist = u * v * k[2]
    return corner + bow + twist


def build_sheet(mesh, w, h, thick, uv_front, uv_back, nx=None, ny=None,
                curl=None, group=0):
    """A page with thickness: front grid, back grid, and a rim joining them."""
    nx = nx or SHEET["nx"]
    ny = ny or SHEET["ny"]
    hw, hh = w * 0.5, h * 0.5
    ht = thick * 0.5

    def pos(i, j, front):
        u = -1.0 + 2.0 * i / nx
        v = -1.0 + 2.0 * j / ny
        z = curl_offset(u, v, curl)
        return (u * hw, v * hh, z + (ht if front else -ht))

    def uvq(i, j, rect):
        u0, v0, u1, v1 = rect
        return (u0 + (u1 - u0) * (i / nx), v0 + (v1 - v0) * (j / ny))

    base_f = len(mesh.pos)
    for j in range(ny + 1):
        for i in range(nx + 1):
            mesh.add_vertex(pos(i, j, True), uvq(i, j, uv_front))
    base_b = len(mesh.pos)
    for j in range(ny + 1):
        for i in range(nx + 1):
            mesh.add_vertex(pos(i, j, False), uvq(nx - i, j, uv_back))

    s = nx + 1
    for j in range(ny):
        for i in range(nx):
            a = base_f + j * s + i
            mesh.add_face((a, a + 1, a + s + 1, a + s), group)
            b = base_b + j * s + i
            mesh.add_face((b + s, b + s + 1, b + 1, b), group)

    # rim: walk the boundary, bridging front to back
    def fi(i, j):
        return base_f + j * s + i

    def bi(i, j):
        return base_b + j * s + i

    edge = []
    edge += [(i, 0) for i in range(nx)]
    edge += [(nx, j) for j in range(ny)]
    edge += [(i, ny) for i in range(nx, 0, -1)]
    edge += [(0, j) for j in range(ny, 0, -1)]
    for k in range(len(edge)):
        i0, j0 = edge[k]
        i1, j1 = edge[(k + 1) % len(edge)]
        mesh.add_face((fi(i1, j1), fi(i0, j0), bi(i0, j0), bi(i1, j1)),
                      group + 1)


def sheet_decal(mesh, cx, cy, w, h, uv_rect, lift=0.0016, curl=None,
                sub=2, group=0):
    """A quad lying on the page, following its curl so it never floats."""
    hw, hh = SHEET["w"] * 0.5, SHEET["h"] * 0.5
    base = len(mesh.pos)
    u0, v0, u1, v1 = uv_rect
    for j in range(sub + 1):
        for i in range(sub + 1):
            fx = i / sub
            fy = j / sub
            x = cx + (fx - 0.5) * w
            y = cy + (fy - 0.5) * h
            z = curl_offset(x / hw, y / hh, curl) + SHEET["thick"] * 0.5 + lift
            mesh.add_vertex((x, y, z),
                            (u0 + (u1 - u0) * fx, v0 + (v1 - v0) * fy))
    s = sub + 1
    for j in range(sub):
        for i in range(sub):
            a = base + j * s + i
            mesh.add_face((a, a + 1, a + s + 1, a + s), group)


# ------------------------------------------------------------------ limbs


def build_limb(name, material, length, r0, r1, tip=None, tip_mat=None,
               tip_r=0.024, flat_tip=False):
    """A rubber-hose segment hanging down -Y in its own local space."""
    m = M.Mesh(name, material)
    n = LIMB["sides"]
    rings = []
    steps = 3
    for i in range(steps + 1):
        t = i / steps
        r = r0 + (r1 - r0) * t
        prof = M.profile_ellipse(n, r, r)
        rings.append(M.ring_from_profile(prof, (0.0, -length * t, 0.0),
                                         (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
    m.add_loft(rings, uv_rect=(0, 0, 1, 1), group=0)
    m.add_grid_cap(rings[0], group=1, flip=True)
    node = Node(name, meshes=[m])
    node.bind_local = None       # filled in once the node is placed

    if tip == "glove":
        g = M.Mesh(name + "_Glove", tip_mat)
        c = (0.0, -length - tip_r * 0.35, 0.0)
        M.cylinder(g, (0.0, -length + 0.004, 0.0), c, r1 * 1.05, tip_r, n,
                   group=0, cap_start=False, cap_end=False)
        ring = M.ring_from_profile(M.profile_ellipse(n, tip_r, tip_r), c,
                                   (1, 0, 0), (0, 0, 1))
        M.dome_tip(g, ring, (0.0, -length - tip_r * 1.35, 0.0), steps=2, group=0)
        node.add_mesh(g)
    elif tip == "shoe":
        sM = M.Mesh(name + "_Shoe", tip_mat)
        # a squat wedge, longer towards -Z so it reads as a foot facing forward
        M.box_chamfered(sM, (tip_r * 1.9, tip_r * 1.15, tip_r * 3.1), 0.006,
                        (0.0, -length - tip_r * 0.5, -tip_r * 0.75), group=0)
        node.add_mesh(sM)
    else:
        e = M.Mesh(name + "_Cap", material)
        ring = M.ring_from_profile(M.profile_ellipse(n, r1, r1),
                                   (0.0, -length, 0.0), (1, 0, 0), (0, 0, 1))
        M.dome_tip(e, ring, (0.0, -length - r1, 0.0), steps=2, group=0)
        node.add_mesh(e)
    return node


# ---------------------------------------------------------------- assembly


def build_enemy(variant, cfg, images):
    scene = Scene("Enemy_" + variant)
    for name, canvas in images.items():
        scene.image(name, canvas)

    scene.material(Material(MAT["paper"], (1, 1, 1, 1), 0.0, 0.88,
                            "paper_pleading"))
    scene.material(Material(MAT["privileged"], (1, 1, 1, 1), 0.0, 0.88,
                            "paper_privileged"))
    scene.material(Material(MAT["alt"], (1, 1, 1, 1), 0.0, 0.88, "paper_alt"))
    scene.material(Material(MAT["binder"], (1, 1, 1, 1), 0.05, 0.72,
                            "binder_cover"))
    scene.material(Material(MAT["face"], (1, 1, 1, 1), 0.0, 0.90, "faces"))
    scene.material(Material(MAT["mark"], (1, 1, 1, 1), 0.0, 0.86, "stamp_mark"))
    scene.material(Material(MAT["limb"], hex_srgb("#23252B"), 0.0, 0.62))
    scene.material(Material(MAT["glove"], hex_srgb("#F2F1EC"), 0.0, 0.70))
    scene.material(Material(MAT["shoe"], hex_srgb("#15161A"), 0.05, 0.48))
    scene.material(Material(MAT["ring"], hex_srgb("#B9BEC6"), 1.0, 0.28))

    paper_mat = MAT[cfg["paper"]]
    root = Node("Enemy_" + variant)
    scene.add_root(root)
    rig = Node("Rig")
    root.add(rig)
    torso = Node("Torso", vec.translate((0.0, BODY_Y, 0.0)))
    rig.add(torso)
    body = Node("Body")          # squash/stretch only -- limbs are not children
    torso.add(body)

    w, h, th = SHEET["w"], SHEET["h"], SHEET["thick"]
    front = (0.02, PT.FRONT_V[0] + 0.01, 0.98, PT.FRONT_V[1] - 0.01)
    back = (0.02, PT.BACK_V[0] + 0.01, 0.98, PT.BACK_V[1] - 0.01)

    # ---- the page(s) -----------------------------------------------------
    main = M.Mesh("Page", paper_mat)
    build_sheet(main, w, h, th, front, back)
    body.add_mesh(main)

    extras = []
    n_sheets = cfg["sheets"]
    if variant == "binder":
        # a block of pages behind the board cover, plus the ring mechanism
        pages = M.Mesh("Pages", MAT["paper"])
        for i in range(1, n_sheets):
            t = i / (n_sheets - 1)
            off = -0.008 - 0.010 * i
            sub = M.Mesh("tmp", MAT["paper"])
            build_sheet(sub, w * (0.985 - 0.012 * t), h * (0.975 - 0.010 * t),
                        th, front, back, nx=4, ny=5,
                        curl=(0.016, 0.010, 0.008))
            for k, p in enumerate(sub.pos):
                pages.add_vertex((p[0] + 0.004 * math.sin(i * 1.7),
                                  p[1] - 0.004 * i, p[2] + off),
                                 sub.uv[k])
            base = len(pages.pos) - len(sub.pos)
            for idx, g in sub.faces:
                pages.add_face(tuple(base + v for v in idx), g)
        body.add_mesh(pages)
        rings = M.Mesh("Rings", MAT["ring"])
        for ry in (-0.16, 0.0, 0.16):
            c0 = (-w * 0.5 + 0.012, ry, 0.004)
            M.tube_along_path(rings, [
                (c0[0] + math.sin(a * math.pi / 8) * 0.022 * 0.4,
                 c0[1] + math.cos(a * math.pi / 8) * 0.022,
                 c0[2] - 0.030 - math.sin(a * math.pi / 8) * 0.022)
                for a in range(17)],
                lambda t: M.profile_ellipse(6, 0.0035, 0.0035),
                up_hint=(0, 0, 1), group=0)
        body.add_mesh(rings)
    elif n_sheets > 1:
        # a loose cluster that flaps as one unit
        for i in range(1, n_sheets):
            mtl = MAT["alt"] if i % 2 else MAT["paper"]
            sm = M.Mesh("Sheet_%d" % (i + 1), mtl)
            build_sheet(sm, w * (0.94 - 0.03 * i), h * (0.93 - 0.035 * i), th,
                        front, back, nx=4, ny=5,
                        curl=(0.034 + 0.012 * i, 0.020, 0.026))
            ang = (-1) ** i * (9.0 + 6.0 * i)
            node = Node("Sheet_%d" % (i + 1), vec.mat_mul(
                vec.translate((0.030 * ((-1) ** i) * i, -0.022 * i,
                               -0.016 - 0.013 * i)),
                vec.rot_z(ang * D2R)), meshes=[sm])
            body.add(node)
            extras.append((node, ang))

    # ---- face + Bates impression ----------------------------------------
    face_nodes = {}
    for key in ("calm", "panic", "dizzy", "smug"):
        fm = M.Mesh("Face_" + key.capitalize(), MAT["face"])
        sheet_decal(fm, 0.0, -0.030, 0.215, 0.185, PT.FACE_CELLS[key])
        vis = 1.0 if key == cfg["face"] else 0.0
        node = Node("Face_" + key.capitalize(), vec.scale(vis or 1e-4),
                    meshes=[fm])
        body.add(node)
        face_nodes[key] = node

    mk = M.Mesh("Bates_Mark", MAT["mark"])
    sheet_decal(mk, 0.020, -0.185, 0.250, 0.150, (0.03, 0.03, 0.97, 0.97))
    mark = Node("Bates_Mark", vec.scale(1e-4), meshes=[mk])
    body.add(mark)

    # ---- limbs -----------------------------------------------------------
    limbs = {}
    for side, sx in (("L", -1.0), ("R", 1.0)):
        arm = build_limb("Arm_" + side, MAT["limb"], LIMB["upper"],
                         LIMB["arm_r"][0], LIMB["arm_r"][1])
        arm.matrix = vec.translate((sx * SHOULDER[0],
                                    SHOULDER[1] - BODY_Y, 0.006))
        fore = build_limb("Forearm_" + side, MAT["limb"], LIMB["fore"],
                          LIMB["arm_r"][1], LIMB["arm_r"][1] * 0.92,
                          tip="glove", tip_mat=MAT["glove"], tip_r=0.026)
        fore.matrix = vec.translate((0.0, -LIMB["upper"], 0.0))
        arm.add(fore)
        torso.add(arm)
        limbs["arm_" + side] = arm
        limbs["fore_" + side] = fore

        leg = build_limb("Leg_" + side, MAT["limb"], LIMB["thigh"],
                         LIMB["leg_r"][0], LIMB["leg_r"][1])
        leg.matrix = vec.translate((sx * HIP[0], HIP[1], 0.0))
        shin = build_limb("Shin_" + side, MAT["limb"], LIMB["shin"],
                          LIMB["leg_r"][1], LIMB["leg_r"][1] * 0.9,
                          tip="shoe", tip_mat=MAT["shoe"], tip_r=0.021)
        shin.matrix = vec.translate((0.0, -LIMB["thigh"], 0.0))
        leg.add(shin)
        rig.add(leg)
        limbs["leg_" + side] = leg
        limbs["shin_" + side] = shin

    if cfg["scale"] != 1.0:
        root.matrix = vec.scale(cfg["scale"])

    for node in list(limbs.values()) + [n for n, _ in extras]:
        node.bind_local = list(node.matrix)
    scene.rig = {"root": root, "rig": rig, "torso": torso, "body": body,
                 "faces": face_nodes, "mark": mark, "limbs": limbs,
                 "extras": extras, "cfg": cfg}
    return scene


# ------------------------------------------------------------- animation


def _swing(deg, phase):
    return deg * math.sin(phase) * D2R


def run_cycle(scene):
    """Looping run. The last key repeats frame 0 exactly, so the seam is free.

    A looping clip has two requirements the old bake did not meet.

    The stride has to close on the clip boundary. Cadence used to warp the
    phase inside a fixed 20 frames -- the cycle spanned TAU * cadence, so it
    only closed when cadence happened to be a whole number. It did for the
    pleading paper; it did not for anyone else, and the binder (0.66) snapped
    its shin roughly 66 degrees every time the clip wrapped. Cadence now sets
    how many 30 fps frames one stride takes instead, so the phase always
    closes and the bake stays on the 30 fps grid.

    And the last key has to repeat frame 0, or the wrap has no interval to
    happen over: the final frame of motion would land in zero time and hitch.
    """
    r = scene.rig
    cfg = r["cfg"]["run"]
    anim = Animation("Run", FPS)
    poses = []
    # frames per stride at 30 fps -- fast variants take fewer, heavy ones more
    n = max(4, int(round(RUN_FRAMES / cfg["cadence"])))
    for f in range(n + 1):
        t = f / FPS
        p = TAU * (f / n)
        pose = {}

        # --- hips: bob twice per stride, lean into the run, sway sideways
        bob = cfg["bob"] * (0.5 - 0.5 * math.cos(2.0 * p))
        if cfg.get("thud"):
            # heavy variant lands hard and dwells at the bottom
            bob = cfg["bob"] * (0.5 - 0.5 * math.cos(2.0 * p)) ** 1.7
        sway = cfg["sway"] * math.sin(p)
        if cfg.get("dodge"):
            # A weave slower than one stride cannot live in a one-stride loop
            # -- half a cycle does not close. The long evasive weave belongs to
            # the AI heading (web/main.js does it); what stays here is the
            # per-stride shimmy that sells the side-step.
            sway += cfg["sway"] * 1.5 * math.sin(2.0 * p + 0.7)
        jitter = 0.004 * cfg["jitter"] * math.sin(p * 5.0 + 1.1)
        lean = cfg["lean"] + 3.0 * math.sin(2.0 * p) * cfg["jitter"] * 0.5
        pose[r["rig"]] = vec.mat_mul(
            vec.translate((sway, bob + jitter, 0.0)),
            vec.mat_mul(vec.rot_x(-lean * D2R),
                        vec.rot_z(math.sin(p) * 2.0 * D2R)))

        # --- the page itself flutters against the run
        fl = cfg["flutter"]
        pose[r["torso"]] = vec.mat_mul(
            vec.translate((0.0, BODY_Y, 0.0)),
            vec.mat_mul(vec.rot_x(math.sin(2.0 * p + 0.6) * fl * 0.5 * D2R),
                        vec.rot_z(math.sin(p + 0.9) * fl * D2R)))
        pose[r["body"]] = list(vec.IDENTITY)

        for si, (node, ang) in enumerate(r["extras"]):
            # Loose sheets lag the body -- reads as chaos, costs two curves.
            # The frequencies are whole numbers of strides so they close on the
            # loop; the chaos comes from the per-sheet phase k, not from
            # fractional rates, which only ever bought a pop at the seam.
            b = node.bind_local
            k = 1.0 + 0.9 * si
            pose[node] = vec.mat_mul(
                vec.mat_mul(vec.translate((
                    b[3] + 0.012 * math.sin(p * 2.0 + k),
                    b[7] + 0.014 * math.sin(p * 3.0 + k * 1.7),
                    b[11])),
                    vec.rot_z((ang + 8.0 * math.sin(p + k)) * D2R)),
                vec.rot_x(11.0 * math.sin(p * 2.0 + k) * D2R))

        # --- legs: thigh swings, knee folds on the way through
        for side, ph in (("L", 0.0), ("R", math.pi)):
            thigh = _swing(cfg["stride"], p + ph)
            knee = max(0.0, math.sin(p + ph + 1.15)) ** 1.4 * 74.0 * D2R
            leg = r["limbs"]["leg_" + side]
            shin = r["limbs"]["shin_" + side]
            pose[leg] = vec.mat_mul(
                vec.translate((leg.bind_local[3], leg.bind_local[7],
                               leg.bind_local[11])),
                vec.rot_x(thigh))
            pose[shin] = vec.mat_mul(vec.translate((0.0, -LIMB["thigh"], 0.0)),
                                     vec.rot_x(-knee))

            # --- arms counter-swing, elbows trail
            arm = r["limbs"]["arm_" + side]
            fore = r["limbs"]["fore_" + side]
            up = _swing(cfg["arm"], p + ph + math.pi)
            # flex tracks the shoulder: deepest as the arm comes through in
            # front, opening out as it trails behind
            elbow = (0.42 + 0.58 * math.sin(p + ph + math.pi + 0.5)) * 52.0 * D2R
            pose[arm] = vec.mat_mul(
                vec.translate((arm.bind_local[3], arm.bind_local[7],
                               arm.bind_local[11])),
                vec.mat_mul(vec.rot_x(up),
                            vec.rot_z((-1 if side == "L" else 1) *
                                      (16.0 + 8.0 * math.sin(p)) * D2R)))
            pose[fore] = vec.mat_mul(vec.translate((0.0, -LIMB["upper"], 0.0)),
                                     vec.rot_x(abs(elbow)))

        # faces and mark hold their bind state through the run
        for key, node in r["faces"].items():
            pose[node] = node.matrix
        pose[r["mark"]] = r["mark"].matrix
        poses.append(pose)

    for f, pose in enumerate(poses):
        for node, m in pose.items():
            anim.key_matrix(node, f / FPS, m)
    anim.poses = poses
    return anim


def stamped(scene):
    """One-shot reaction: flattened by the stamp, left with the impression."""
    r = scene.rig
    anim = Animation("Stamped", FPS)
    poses = []
    n = STAMP_FRAMES
    hit = 4
    for f in range(n):
        pose = {}
        if f < hit:
            k = f / hit
            rise = 0.020 * math.sin(k * math.pi * 0.5)
            squash = (1.0 - 0.05 * k, 1.0 + 0.07 * k, 1.0)
            lie = 0.0
            drop = rise
        else:
            k = (f - hit) / float(n - 1 - hit)
            # slam, a single stiff rebound, then flat -- heavy, not bouncy
            flat = 1.0 - 0.72 * math.exp(-k * 3.4) * abs(math.cos(k * 5.0)) \
                - 0.20 * min(1.0, k * 2.2)
            flat = max(0.16, flat)
            squash = (1.0 + (1.0 - flat) * 0.55, flat,
                      1.0 + (1.0 - flat) * 0.32)
            lie = min(1.0, max(0.0, (k - 0.18) / 0.55)) ** 0.8
            drop = -0.010 * min(1.0, k * 3.0)

        pose[r["rig"]] = vec.translate((0.0, drop, 0.0))
        body_y = BODY_Y * (1.0 - 0.62 * lie) + 0.02 * lie
        # the legs hang off the bottom edge of the sheet, so when the sheet
        # squashes they have to ride up with it or they detach in mid air
        hip_y = body_y - SHEET["h"] * 0.5 * squash[1] * (1.0 - 0.55 * lie) \
            + 0.014
        pose[r["torso"]] = vec.mat_mul(
            vec.translate((0.0, body_y, -0.08 * lie)),
            vec.rot_x(-78.0 * lie * D2R))
        pose[r["body"]] = vec.scale(squash)

        for node, ang in r["extras"]:
            b = node.bind_local
            spread = 1.0 + 1.9 * lie
            pose[node] = vec.mat_mul(
                vec.translate((b[3] * spread, b[7] * spread,
                               b[11] * (1.0 + 2.6 * lie))),
                vec.rot_z((ang * (1.0 + 2.2 * lie)) * D2R))

        # face: calm/smug -> panic on the anticipation -> dizzy once flattened
        panic = 1.0 if hit - 2 <= f < hit + 7 else 0.0
        dizzy = 1.0 if f >= hit + 7 else 0.0
        start = 1.0 if f < hit - 2 else 0.0
        for key, node in r["faces"].items():
            if key == "panic":
                vis = panic
            elif key == "dizzy":
                vis = dizzy
            elif key == r["cfg"]["face"]:
                vis = start
            else:
                vis = 0.0
            pose[node] = vec.scale(vis if vis > 0.0 else 1e-4)

        # the impression punches in on the hit frame with a little overshoot
        if f < hit:
            ms = 1e-4
        else:
            d = f - hit
            ms = 1.28 if d == 0 else (1.12 if d == 1 else 1.0)
        pose[r["mark"]] = vec.scale(ms)

        # limbs splay on the hit, then go limp
        for side, sgn in (("L", -1.0), ("R", 1.0)):
            splay = lie
            arm = r["limbs"]["arm_" + side]
            fore = r["limbs"]["fore_" + side]
            leg = r["limbs"]["leg_" + side]
            shin = r["limbs"]["shin_" + side]
            pose[arm] = vec.mat_mul(
                vec.translate((arm.bind_local[3], arm.bind_local[7],
                               arm.bind_local[11])),
                vec.mat_mul(vec.rot_z(sgn * (18.0 + 62.0 * splay) * D2R),
                            vec.rot_x((-52.0 * (1.0 - splay) - 6.0) * D2R)))
            pose[fore] = vec.mat_mul(vec.translate((0.0, -LIMB["upper"], 0.0)),
                                     vec.rot_x((38.0 - 30.0 * splay) * D2R))
            pose[leg] = vec.mat_mul(
                vec.translate((leg.bind_local[3], max(0.03, hip_y),
                               leg.bind_local[11])),
                vec.mat_mul(vec.rot_z(sgn * 34.0 * splay * D2R),
                            vec.rot_x((16.0 - 88.0 * splay) * D2R)))
            pose[shin] = vec.mat_mul(vec.translate((0.0, -LIMB["thigh"], 0.0)),
                                     vec.rot_x(-(20.0 + 54.0 * splay) * D2R))
        poses.append(pose)

    for f, pose in enumerate(poses):
        for node, m in pose.items():
            anim.key_matrix(node, f / FPS, m)
    anim.poses = poses
    return anim


# ---------------------------------------------------------------- previews


def preview(scene, anims, outdir, name, quick=False):
    from tools.render import Camera, render

    os.makedirs(outdir, exist_ok=True)
    w, h = (240, 300) if quick else (330, 410)
    cam = Camera((0.78, 0.60, 1.35), (0.0, 0.33, 0.0), fov_deg=34)
    ground = ground_node(scene)
    scene.roots.append(ground)
    made = []
    try:
        still = render(scene, cam, w * 2, h * 2)
        p = os.path.join(outdir, "enemy_%s.png" % name)
        still.save(p)
        made.append(p)

        for anim in anims:
            saved = {}
            for pose in anim.poses:
                for node in pose:
                    saved.setdefault(id(node), (node, list(node.matrix)))
            frames = []
            try:
                for pose in anim.poses:
                    for node, m in pose.items():
                        node.matrix = list(m)
                    frames.append(render(scene, cam, w, h))
            finally:
                for node, m in saved.values():
                    node.matrix = m
            tag = "%s_%s" % (name, anim.name.lower())
            # contact sheets for every variant; the animated PNG only for the
            # main enemy -- 8 full-frame APNGs is a lot of repo for a preview
            if name == "pleading":
                write_apng(frames, os.path.join(outdir, "%s.png" % tag),
                           fps=FPS)
            cols = 7
            rows = (len(frames) + cols - 1) // cols
            tw, th = w * 2 // 3, h * 2 // 3
            sheet = Canvas(cols * tw + (cols + 1) * 3,
                           rows * th + (rows + 1) * 3, (0.10, 0.11, 0.13))
            for i, fr in enumerate(frames):
                sheet.blit(fr.resized(tw, th), 3 + (i % cols) * (tw + 3),
                           3 + (i // cols) * (th + 3))
            sp = os.path.join(outdir, "%s_frames.png" % tag)
            sheet.save(sp)
            made.append(sp)
    finally:
        scene.roots.remove(ground)
        scene.materials.pop("Preview_Ground", None)
    return made


def ground_node(scene):
    scene.material(Material("Preview_Ground", hex_srgb("#6E6A63"), 0.0, 0.95))
    m = M.Mesh("Preview_Ground", "Preview_Ground")
    M.plate(m, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, -1.0), 3.0, 3.0,
            group=0)
    return Node("Preview_Ground", meshes=[m])


# -------------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bates", default="000137")
    ap.add_argument("--out", default="build/enemies")
    ap.add_argument("--only", default=None, help="build one variant")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)
    tex_dir = os.path.join(args.out, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    print("generating paper textures...")
    images = PT.build_all(bates=args.bates)
    for name, canvas in images.items():
        canvas.save(os.path.join(tex_dir, name + ".png"))

    names = [args.only] if args.only else list(VARIANTS)
    for name in names:
        cfg = VARIANTS[name]
        scene = build_enemy(name, cfg, images)
        run = scene.animation(run_cycle(scene))
        hit = scene.animation(stamped(scene))
        scene.prune()          # only embed the pages this variant uses
        glb = os.path.join(args.out, "enemy_%s.glb" % name)
        export_glb(scene, glb)
        st = scene.stats()
        print("  %-9s %-24s %5d tris  %s (%.0f KB)  [%s %df, %s %df]"
              % (name, cfg["label"], st["triangles"], os.path.basename(glb),
                 os.path.getsize(glb) / 1024.0, run.name, len(run.poses),
                 hit.name, len(hit.poses)))
        if not args.no_preview:
            preview(scene, [run, hit], os.path.join(args.out, "previews"),
                    name, args.quick)

    print("done in %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
