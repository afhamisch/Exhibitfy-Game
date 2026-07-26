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
    "objection": "Paper_Objection",
    "motion": "Paper_Motion",
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

    # ------------------------------------------------------------ objections
    # These three are not exhibits to be filed -- they hunt the player and
    # strike exhibits back out of the binder, so the runtime treats them as a
    # separate class entirely. Everything here exists to make them readable as
    # a threat in the fraction of a second before one reaches you:
    #
    #   * one shared OBJECTION page, red-washed and bordered, tinted per rule
    #   * arms thrown much wider than any exhibit's, so the silhouette differs
    #     even edge-on and even in a corridor where colour is unreliable
    #   * the unused "dizzy" face, which is the only one that does not read as
    #     something running away from you
    #
    # Speed and mass follow the rule. Hearsay is the routine one and shambles;
    # character evidence is quicker and more insinuating; 403 is rare, fast and
    # heavy, because it is the one that strikes two exhibits at once.
    "hearsay": {
        "label": "Hearsay Objection",
        "paper": "objection",
        "tint": hex_srgb("#E4B4B0"),          # washed red
        "sheets": 1,
        "scale": 1.02,
        "run": {"cadence": 0.82, "stride": 40.0, "bob": 0.060, "lean": -9.0,
                "sway": 0.026, "flutter": 9.0, "jitter": 1.4, "arm": 58.0},
        "face": "dizzy",
    },
    "character": {
        "label": "Character Evidence Objection",
        "paper": "objection",
        "tint": hex_srgb("#D9B2D4"),          # violet
        "sheets": 1,
        "scale": 0.99,
        "run": {"cadence": 1.06, "stride": 44.0, "bob": 0.044, "lean": -6.0,
                "sway": 0.048, "flutter": 12.0, "jitter": 0.8, "arm": 64.0,
                "dodge": 1.0},
        "face": "dizzy",
    },
    "rule403": {
        "label": "Rule 403 Objection",
        "paper": "objection",
        "tint": hex_srgb("#E8C79A"),          # amber
        "sheets": 3,
        "stock": ("objection",),              # three objections, not one plus paper
        "scale": 1.13,
        "run": {"cadence": 1.18, "stride": 52.0, "bob": 0.066, "lean": -13.0,
                "sway": 0.022, "flutter": 6.0, "jitter": 0.6, "arm": 70.0,
                "thud": 1.0},
        "face": "dizzy",
    },
}

VARIANTS["motion"] = {
    # The boss, and the only thing in the game that outranks the binder: a
    # motion for summary judgment ends a case without ever reaching trial.
    #
    # It is big and slow and it does not flee, because it does not have to. The
    # smug face is the point -- it is the one document here that believes it has
    # already won. Seven pages of its own stock, so the thing you are fighting
    # is visibly a document with pages, which is the whole fight: the prototype
    # gives it a page count instead of a one-stamp death.
    "label": "Motion for Summary Judgment",
    "paper": "motion",
    "stock": ("motion",),
    "sheets": 7,
    "scale": 2.05,
    "run": {"cadence": 0.58, "stride": 30.0, "bob": 0.078, "lean": 8.0,
            "sway": 0.016, "flutter": 4.0, "jitter": 0.2, "arm": 24.0,
            "thud": 1.0},
    "face": "smug",
}

# ------------------------------------------------------------- the lawyer
#
# Opposing counsel is the one thing in this file that is not a document, so he
# does not go through build_enemy at all -- there is no page to flutter and no
# sheet to lie down. He is a person, at a person's scale: everything else here
# is a sheet of paper about 0.6 m tall wearing shoes, and this is 1.78 m.
#
# He does not chase you and he cannot be stamped. He throws binders, and the
# fight is whether you can get out of the way, so the only things he needs to
# do are stand, throw, and react when one of them misses.
COUNSEL = {
    "label": "Opposing Counsel",
    "height": 1.78,
    "throw_release": 12,     # the frame the binder leaves his hand
    "throw_frames": 30,
    "gloat_frames": 24,
}

# Solid colours, so he costs no texture at all: the seven documents already
# spend 3 MB on page maps and he is a silhouette in a corridor.
CMAT = {
    "suit": "Counsel_Suit",
    "shirt": "Counsel_Shirt",
    "tie": "Counsel_Tie",
    "skin": "Counsel_Skin",
    "hair": "Counsel_Hair",
}

# The four that are exhibits, the three that are objections, and the boss.
# Nothing else in this file should hard-code any of these lists.
EXHIBITS = ("pleading", "privilege", "binder", "stack")
OBJECTIONS = ("hearsay", "character", "rule403")
# Deliberately NOT in the combined enemies.glb. Most players never earn the
# bonus round, and the boss is 3 MB of page maps they should not have to fetch
# to find that out -- the prototype loads enemy_motion.glb on qualification.
BOSS = ("motion",)

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
    # Objections share one texture and are told apart by tint, so the material
    # carries the variant's colour -- and therefore the VARIANT'S NAME. absorb()
    # merges materials by name into the combined file, so three variants all
    # calling this "Paper_Objection" collapse to whichever was absorbed last:
    # every objection came out amber, rule403's colour, in enemies.glb. The
    # per-variant GLBs looked correct the whole time, which is exactly how this
    # would have reached the browser unnoticed.
    obj_mat = "%s_%s" % (MAT["objection"], variant)
    uses_objection = (cfg["paper"] == "objection"
                      or "objection" in cfg.get("stock", ()))
    if uses_objection:
        scene.material(Material(obj_mat, cfg.get("tint", (1, 1, 1, 1)),
                                0.0, 0.84, "paper_objection"))

    def mat_for(key):
        return obj_mat if key == "objection" else MAT[key]

    if cfg["paper"] == "motion" or "motion" in cfg.get("stock", ()):
        scene.material(Material(MAT["motion"], (1, 1, 1, 1), 0.0, 0.80,
                                "paper_motion"))
    scene.material(Material(MAT["face"], (1, 1, 1, 1), 0.0, 0.90, "faces"))
    scene.material(Material(MAT["mark"], (1, 1, 1, 1), 0.0, 0.86, "stamp_mark"))
    scene.material(Material(MAT["limb"], hex_srgb("#23252B"), 0.0, 0.62))
    scene.material(Material(MAT["glove"], hex_srgb("#F2F1EC"), 0.0, 0.70))
    scene.material(Material(MAT["shoe"], hex_srgb("#15161A"), 0.05, 0.48))
    scene.material(Material(MAT["ring"], hex_srgb("#B9BEC6"), 1.0, 0.28))

    paper_mat = mat_for(cfg["paper"])
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
        # A loose cluster that flaps as one unit. The stock alternates, which is
        # the point for the chaotic stack -- a pile of unrelated filings -- but
        # it must not be hard-coded: the objections are red, and giving them
        # white pleading sheets both read wrong and pulled two more 1024 maps
        # into a file that needs neither (enemy_rule403.glb was 1355 KB against
        # hearsay's 663 KB for the same geometry).
        stock = cfg.get("stock", ("alt", "paper"))
        for i in range(1, n_sheets):
            mtl = mat_for(stock[(i - 1) % len(stock)])
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


def build_counsel(images):
    """Opposing counsel: suit, tie, and an armful of binders to throw at you.

    Built at human scale with the origin on the floor between the feet, facing
    -Z, which is the same contract every other enemy honours -- the prototype
    should not have to special-case where his feet are.

    The node names follow the document rig (Rig / Torso / Arm_* / Leg_*) for
    the same reason: the runtime already knows how to drive that shape, and a
    second convention would be a second thing to get wrong.
    """
    scene = Scene("Enemy_counsel")
    for name, canvas in images.items():
        scene.image(name, canvas)
    scene.material(Material(MAT["face"], (1, 1, 1, 1), 0.0, 0.90, "faces"))
    scene.material(Material(CMAT["suit"], hex_srgb("#2C3038"), 0.0, 0.66))
    scene.material(Material(CMAT["shirt"], hex_srgb("#F2F1EC"), 0.0, 0.60))
    scene.material(Material(CMAT["tie"], hex_srgb("#D93E15"), 0.0, 0.52))
    scene.material(Material(CMAT["skin"], hex_srgb("#C9A483"), 0.0, 0.74))
    scene.material(Material(CMAT["hair"], hex_srgb("#2A2320"), 0.0, 0.58))
    scene.material(Material(MAT["shoe"], hex_srgb("#15161A"), 0.05, 0.48))
    scene.material(Material(MAT["binder"], (1, 1, 1, 1), 0.05, 0.72,
                            "paper_binder"))

    HIP_Y, SHOULDER_Y = 0.94, 1.44
    THIGH, SHIN = 0.44, 0.44
    UPPER, FORE = 0.30, 0.28
    root = Node("Enemy_counsel")
    rig = Node("Rig")
    root.add(rig)
    torso = Node("Torso", vec.translate((0.0, HIP_Y, 0.0)))
    rig.add(torso)
    body = Node("Body")
    torso.add(body)

    # ---- suit: a chest that tapers to the waist, with lapels and a tie
    suit = M.Mesh("Suit", CMAT["suit"])
    M.box_chamfered(suit, (0.44, 0.54, 0.25), 0.030,
                    (0.0, 0.26, 0.0), group=0)
    body.add_mesh(suit)

    shirt = M.Mesh("Shirt", CMAT["shirt"])
    M.box_chamfered(shirt, (0.16, 0.26, 0.06), 0.012,
                    (0.0, 0.40, -0.108), group=0)
    body.add_mesh(shirt)

    tie = M.Mesh("Tie", CMAT["tie"])
    M.box_chamfered(tie, (0.052, 0.30, 0.030), 0.008,
                    (0.0, 0.30, -0.126), group=0)
    body.add_mesh(tie)

    # ---- head, hair, and the face he keeps through all of it
    neck = M.Mesh("Neck", CMAT["skin"])
    M.cylinder(neck, (0.0, 0.52, 0.0), (0.0, 0.60, 0.0), 0.048, 0.052, 10,
               group=0)
    body.add_mesh(neck)

    head_n = Node("Head", vec.translate((0.0, 0.66, 0.0)))
    body.add(head_n)
    head = M.Mesh("Head", CMAT["skin"])
    rings = []
    for i in range(9):
        t = i / 8.0
        y = -0.11 + 0.22 * t
        r = math.sin(math.pi * (0.10 + 0.80 * t)) * 0.108
        prof = M.profile_ellipse(12, r, r * 0.88)
        rings.append(M.ring_from_profile(prof, (0.0, y, 0.0),
                                         (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
    head.add_loft(rings, uv_rect=(0, 0, 1, 1), group=0)
    head.add_grid_cap(rings[0], group=0, flip=True)
    head.add_grid_cap(rings[-1], group=0)
    head_n.add_mesh(head)

    # A cap that follows the skull, not a cone. Taking the radius down by
    # cos(t * 1.15) left the top ring at 45 mm and the dome then ran to a
    # point 24 mm above it, which is a dunce cap on a lawyer.
    hair = M.Mesh("Hair", CMAT["hair"])
    hrings = []
    for i in range(5):
        t = i / 4.0
        y = 0.004 + 0.086 * t
        r = math.cos(t * 0.62) * 0.114
        prof = M.profile_ellipse(12, r, r * 0.92)
        hrings.append(M.ring_from_profile(prof, (0.0, y, 0.0),
                                          (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
    hair.add_loft(hrings, uv_rect=(0, 0, 1, 1), group=0)
    hair.add_grid_cap(hrings[0], group=0, flip=True)
    M.dome_tip(hair, hrings[-1], (0.0, 0.118, 0.0), steps=2, group=0,
               bulge=0.55)
    head_n.add_mesh(hair)

    # The smug face out of the shared atlas -- the same expression the motion
    # wore, on the man who filed it.
    fm = M.Mesh("Face_Smug", MAT["face"])
    M.plate(fm, (0.0, 0.005, -0.099), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0),
            0.150, 0.130, group=0, uv_rect=PT.FACE_CELLS["smug"])
    head_n.add_mesh(fm)

    # ---- limbs, at his scale rather than a document's
    limbs = {}
    for side, sx in (("L", -1.0), ("R", 1.0)):
        arm = build_limb("Arm_" + side, CMAT["suit"], UPPER, 0.058, 0.046)
        arm.matrix = vec.translate((sx * 0.245, SHOULDER_Y - HIP_Y, 0.0))
        fore = build_limb("Forearm_" + side, CMAT["skin"], FORE, 0.044, 0.036,
                          tip="glove", tip_mat=CMAT["skin"], tip_r=0.050)
        fore.matrix = vec.translate((0.0, -UPPER, 0.0))
        arm.add(fore)
        torso.add(arm)
        limbs["arm_" + side] = arm
        limbs["fore_" + side] = fore

        leg = build_limb("Leg_" + side, CMAT["suit"], THIGH, 0.075, 0.060)
        leg.matrix = vec.translate((sx * 0.105, HIP_Y, 0.0))
        shin = build_limb("Shin_" + side, CMAT["suit"], SHIN, 0.058, 0.045,
                          tip="shoe", tip_mat=MAT["shoe"], tip_r=0.055)
        shin.matrix = vec.translate((0.0, -THIGH, 0.0))
        leg.add(shin)
        rig.add(leg)
        limbs["leg_" + side] = leg
        limbs["shin_" + side] = shin

    # ---- the binder in his throwing hand, hidden the moment it leaves
    held = Node("Held_Binder",
                vec.mat_mul(vec.translate((0.0, -FORE - 0.10, -0.02)),
                            vec.rot_x(90.0 * D2R)))
    hb = M.Mesh("Held_Binder", MAT["binder"])
    M.box_chamfered(hb, (0.235, 0.075, 0.300), 0.010, (0.0, 0.0, 0.0),
                    group=0, uv_rect=(0.02, 0.02, 0.98, 0.98))
    held.add_mesh(hb)
    limbs["fore_R"].add(held)
    limbs["held"] = held

    for node in list(limbs.values()) + [head_n]:
        node.bind_local = list(node.matrix)
    scene.rig = {"root": root, "rig": rig, "torso": torso, "body": body,
                 "head": head_n, "limbs": limbs}
    scene.add_root(root)
    return scene


def counsel_clips(scene):
    """Idle, Throw and Gloat, all baked at 30 fps like everything else.

    `Throw` is the only one with a contract outside this file: the binder
    leaves his hand on frame COUNSEL["throw_release"], and the prototype
    spawns the projectile on exactly that frame so the object appears where
    the hand is rather than near it.
    """
    r = scene.rig
    L = r["limbs"]
    out = []

    # ---- Idle: weight shifting, because a man standing perfectly still in a
    # corridor reads as a prop rather than as somebody waiting for you
    idle = Animation("Idle", FPS)
    n = 48
    poses = []
    for f in range(n + 1):
        p = TAU * (f / n)
        pose = {}
        pose[r["rig"]] = vec.translate((0.012 * math.sin(p),
                                        0.010 * math.sin(2 * p), 0.0))
        pose[r["torso"]] = vec.mat_mul(
            vec.translate((0.0, 0.94, 0.0)),
            vec.rot_y(3.0 * math.sin(p) * D2R))
        pose[r["head"]] = vec.mat_mul(
            vec.translate((0.0, 0.66, 0.0)),
            vec.rot_y(-5.0 * math.sin(p + 0.6) * D2R))
        for side, sgn in (("L", 1.0), ("R", -1.0)):
            pose[L["arm_" + side]] = vec.mat_mul(
                L["arm_" + side].bind_local,
                vec.rot_x(_swing(4.0, p + (0.0 if sgn > 0 else math.pi))))
        pose[L["held"]] = L["held"].bind_local
        poses.append(pose)
    for f, pose in enumerate(poses):
        for node, m in pose.items():
            idle.key_matrix(node, f / FPS, m)
    idle.poses = poses
    out.append(idle)

    # ---- Throw: wind up behind the head, whip forward, follow through
    thr = Animation("Throw", FPS)
    n = COUNSEL["throw_frames"]
    rel = COUNSEL["throw_release"]
    poses = []
    for f in range(n):
        # -1 through 0 winding up, 0 at release, then follow through
        if f <= rel:
            k = f / rel
            wind = vec.smoothstep(k)
            arm = -150.0 * wind          # up and back over the shoulder
            twist = -26.0 * wind
        else:
            k = (f - rel) / max(1, n - 1 - rel)
            arm = -150.0 + 190.0 * vec.smoothstep(min(1.0, k * 1.6))
            twist = -26.0 + 44.0 * vec.smoothstep(min(1.0, k * 1.4))
        pose = {}
        lunge = 0.0 if f <= rel else 0.10 * math.sin(math.pi * min(1.0, k))
        pose[r["rig"]] = vec.translate((0.0, 0.0, -lunge))
        pose[r["torso"]] = vec.mat_mul(
            vec.translate((0.0, 0.94, 0.0)), vec.rot_y(twist * D2R))
        pose[r["head"]] = r["head"].bind_local
        pose[L["arm_R"]] = vec.mat_mul(L["arm_R"].bind_local,
                                       vec.rot_x(arm * D2R))
        pose[L["fore_R"]] = vec.mat_mul(
            L["fore_R"].bind_local,
            vec.rot_x((-40.0 if f <= rel else -8.0) * D2R))
        pose[L["arm_L"]] = vec.mat_mul(L["arm_L"].bind_local,
                                       vec.rot_x(-18.0 * D2R))
        # the binder is in hand until the release frame and gone after it
        pose[L["held"]] = (L["held"].bind_local if f < rel
                           else vec.mat_mul(L["held"].bind_local,
                                            vec.scale(1e-4)))
        poses.append(pose)
    for f, pose in enumerate(poses):
        for node, m in pose.items():
            thr.key_matrix(node, f / FPS, m)
    thr.poses = poses
    out.append(thr)

    # ---- Gloat: what he does when one of them lands on you
    gl = Animation("Gloat", FPS)
    n = COUNSEL["gloat_frames"]
    poses = []
    for f in range(n):
        k = f / (n - 1)
        bounce = math.sin(math.pi * k)
        pose = {}
        pose[r["rig"]] = vec.translate((0.0, 0.045 * bounce, 0.0))
        pose[r["torso"]] = vec.mat_mul(
            vec.translate((0.0, 0.94, 0.0)),
            vec.rot_x(-9.0 * bounce * D2R))
        pose[r["head"]] = vec.mat_mul(
            r["head"].bind_local, vec.rot_x(-14.0 * bounce * D2R))
        for side in ("L", "R"):
            pose[L["arm_" + side]] = vec.mat_mul(
                L["arm_" + side].bind_local,
                vec.rot_x(-52.0 * bounce * D2R))
        pose[L["held"]] = vec.mat_mul(L["held"].bind_local, vec.scale(1e-4))
        poses.append(pose)
    for f, pose in enumerate(poses):
        for node, m in pose.items():
            gl.key_matrix(node, f / FPS, m)
    gl.poses = poses
    out.append(gl)
    return out


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


def preview(scene, anims, outdir, name, quick=False, scale=1.0):
    from tools.render import Camera, render

    os.makedirs(outdir, exist_ok=True)
    w, h = (240, 300) if quick else (330, 410)
    # Pull the camera back in proportion to the variant, so every preview frames
    # its subject the same way. This was a fixed rig set for a 1.0-scale sheet,
    # which cropped the boss at 2.05 down to its shins.
    cam = Camera((0.78 * scale, 0.60 * scale, 1.35 * scale),
                 (0.0, 0.33 * scale, 0.0), fov_deg=34)
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


def absorb(combined, scene, variant):
    """Fold one variant into the shared-texture file.

    Four self-contained GLBs cannot share bytes: `paper_pleading` ships three
    times and `faces` and `stamp_mark` four times each, 1.12 MB of identical
    pixels. `Scene.images` and `.materials` are keyed by name, so merging the
    dicts dedupes them for free.

    Node names have to be made unique first. glTF targets animation channels by
    node index, but three.js binds its tracks by **name** -- four subtrees all
    calling their root `Rig` would leave a clip free to drive the wrong enemy.
    This is the same bug the viewmodel hit with ten duplicate node names, and
    it only shows up at runtime, so prefix on the way in. Renaming here is safe
    because the per-variant GLB has already been written, and the animation
    tracks hold node references rather than names.
    """
    def rename(node):
        node.name = "%s_%s" % (variant, node.name)
        for c in node.children:
            rename(c)

    for root in scene.roots:
        # the root is already Enemy_<variant>, so only its descendants collide
        for child in root.children:
            rename(child)
        combined.add_root(root)
    for anim in scene.animations:
        anim.name = "%s_%s" % (variant, anim.name)
        combined.animation(anim)
    combined.materials.update(scene.materials)
    combined.images.update(scene.images)
    return combined


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

    combined = Scene("Enemies")
    # `counsel` is not a document variant -- he is built separately below, so
    # asking for him alone means building no documents at all.
    names = ([args.only] if args.only else list(VARIANTS))
    names = [n for n in names if n in VARIANTS]
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
                    name, args.quick, cfg["scale"])
        if name not in BOSS:
            absorb(combined, scene, name)

    # Opposing counsel, built his own way and shipped his own file. He is not
    # in the combined GLB for the same reason the motion is not: he belongs to
    # a bonus round most players never reach, and nobody should fetch a lawyer
    # to find that out.
    if not args.only or args.only == "counsel":
        cs = build_counsel(images)
        clips = [cs.animation(a) for a in counsel_clips(cs)]
        cs.prune()
        glb = os.path.join(args.out, "enemy_counsel.glb")
        export_glb(cs, glb)
        st = cs.stats()
        print("  %-9s %-24s %5d tris  %s (%.0f KB)  [%s]"
              % ("counsel", COUNSEL["label"], st["triangles"],
                 os.path.basename(glb), os.path.getsize(glb) / 1024.0,
                 ", ".join("%s %df" % (c.name, len(c.poses)) for c in clips)))

    if len(names) > 1:
        combined.prune()
        glb = os.path.join(args.out, "enemies.glb")
        export_glb(combined, glb)
        print("  %-9s %-24s %5d tris  %s (%.0f KB)  [%d clips]"
              % ("combined", "All seven, shared textures",
                 combined.stats()["triangles"], os.path.basename(glb),
                 os.path.getsize(glb) / 1024.0, len(combined.animations)))

    print("done in %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
