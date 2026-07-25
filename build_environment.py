#!/usr/bin/env python3
"""Modular law office kit for "Tom Rexington, Esq.: Bates & Destroy".

Clean but industrial: warm wood, cool gray, fluorescent troffers overhead, and
just enough scattered paper and worn edge to look lived in. Eight pieces, each
exported on its own so they can be instanced and snapped on a grid.

    python3 build_environment.py [--no-preview] [--only desk_chair]

Grid contract
-------------
Every piece has its origin on the floor at the centre of its module footprint,
with -Z as "forward" down a corridor. Corridor pieces are MODULE (4 m) square
in plan, so hallway and corner sections butt together without a seam. Props sit
on the floor at y = 0 and are placed by hand.

Scale is first-person real: 2.4 m corridor, 2.8 m ceiling, 2.1 m doors,
0.75 m desks, 1.1 m counter -- an eye height of ~1.65 m reads correctly.
"""

import argparse
import math
import os
import random
import sys
import time

from tools import env_textures as ET, mesh as M, vec
from tools.gltf import Material, Node, Scene, export_glb
from tools.imaging import hex_srgb

D2R = math.pi / 180.0

# ------------------------------------------------------------------ metrics

MODULE = 4.00          # grid pitch for corridor pieces
CORRIDOR = 2.40        # clear width between walls
WALL_H = 2.80          # floor to ceiling
WALL_T = 0.15
BASE_H = 0.11          # baseboard
DOOR_W = 0.95
DOOR_H = 2.10

MAT = {
    "carpet": "Floor_Carpet",
    "wall": "Wall_Paint",
    "base": "Wall_Base",
    "ceiling": "Ceiling_Tile",
    "wood": "Wood_Oak",
    "wood_dk": "Wood_Walnut",
    "laminate": "Laminate_Gray",
    "metal": "Metal_Painted",
    "card": "Cardboard",
    "plastic": "Plastic_Black",
    "paper": "Paper_Loose",
    "glow": "Light_Fluorescent",
    "steel": "Steel_Trim",
    "ink": "Ink_Exhibitfy",
    "ink_glow": "Ink_Beacon",
}


def materials(scene):
    for name, canvas in ET.build_all().items():
        scene.image(name, canvas)
    P = ET.PALETTE
    scene.material(Material(MAT["carpet"], (1, 1, 1, 1), 0.0, 0.96, "env_carpet"))
    scene.material(Material(MAT["wall"], (1, 1, 1, 1), 0.0, 0.86, "env_wall"))
    scene.material(Material(MAT["base"], P["base"], 0.05, 0.55))
    scene.material(Material(MAT["ceiling"], (1, 1, 1, 1), 0.0, 0.92,
                            "env_ceiling"))
    scene.material(Material(MAT["wood"], (1, 1, 1, 1), 0.0, 0.42, "env_wood"))
    scene.material(Material(MAT["wood_dk"], (1, 1, 1, 1), 0.0, 0.46,
                            "env_wood_dark"))
    scene.material(Material(MAT["laminate"], (1, 1, 1, 1), 0.0, 0.38,
                            "env_laminate"))
    scene.material(Material(MAT["metal"], (1, 1, 1, 1), 0.55, 0.40, "env_metal"))
    scene.material(Material(MAT["card"], (1, 1, 1, 1), 0.0, 0.90,
                            "env_cardboard"))
    scene.material(Material(MAT["plastic"], P["plastic"], 0.0, 0.52))
    scene.material(Material(MAT["paper"], (1, 1, 1, 1), 0.0, 0.90, "env_paper",
                            double_sided=True))
    scene.material(Material(MAT["glow"], P["glow"], 0.0, 0.40,
                            emissive=P["glow"], double_sided=True))
    scene.material(Material(MAT["steel"], hex_srgb("#AEB3BA"), 1.0, 0.30))
    # The kit is deliberately drab -- grey carpet, beige walls, oak. The ink
    # pod is the only thing in it the player is meant to spot and chase, so it
    # gets the brand accent, a bit of gloss to pick up the troffers, and a low
    # emissive so it does not go to mud at the far end of a corridor. Measured
    # from 9 m down a hallway it was a ~10 px grey-orange speck without this,
    # which is not something you can be asked to detour towards.
    scene.material(Material(MAT["ink"], hex_srgb("#D93E15"), 0.0, 0.34,
                            emissive=hex_srgb("#5E1A08")))
    # The beacon is meant to be seen and not lit by: fully emissive, so it holds
    # its colour at the end of a corridor where the troffers do not reach, and
    # double-sided so a thin cone does not vanish when viewed from inside it.
    scene.material(Material(MAT["ink_glow"], hex_srgb("#F2602B"), 0.0, 0.9,
                            emissive=hex_srgb("#F2602B"), double_sided=True))


# ------------------------------------------------------------------ helpers


def box(mesh, size, center, chamfer=0.006, group=0, uv=(0, 0, 1, 1),
        segments=1):
    M.box_chamfered(mesh, size, chamfer, center, group=group, uv_rect=uv,
                    segments=segments)


def slab(mesh, w, d, h, center, mat_uv_scale=1.0, group=0, chamfer=0.008):
    """Axis-aligned block with UVs scaled to its own footprint (tiling)."""
    box(mesh, (w, h, d), center, chamfer, group,
        (0, 0, w * mat_uv_scale, d * mat_uv_scale))


def slab_box(mesh, w, h, d, center, tile=1.0, group=0, subdiv=1):
    """A closed axis-aligned box with planar UVs on every face.

    box_chamfered lofts along Y and caps the ends with a fan, which leaves the
    top face with degenerate UVs -- fine for a drawer front, useless for a
    carpeted floor. This keeps the tiling correct on the faces you actually
    look at, and closes all six sides so nothing reads as hollow from below.
    """
    x, y, z = center
    hw, hh, hd = w * 0.5, h * 0.5, d * 0.5
    uv = (0, 0, w * tile, d * tile)
    uvx = (0, 0, d * tile, h * tile)
    uvz = (0, 0, w * tile, h * tile)
    M.plate(mesh, (x, y + hh, z), (1, 0, 0), (0, 0, -1), w, d, group=group,
            uv_rect=uv, subdiv=subdiv)                       # top    +Y
    M.plate(mesh, (x, y - hh, z), (1, 0, 0), (0, 0, 1), w, d, group=group,
            uv_rect=uv, subdiv=subdiv)                       # bottom -Y
    M.plate(mesh, (x + hw, y, z), (0, 0, -1), (0, 1, 0), d, h, group=group + 1,
            uv_rect=uvx)                                     # +X
    M.plate(mesh, (x - hw, y, z), (0, 0, 1), (0, 1, 0), d, h, group=group + 2,
            uv_rect=uvx)                                     # -X
    M.plate(mesh, (x, y, z + hd), (1, 0, 0), (0, 1, 0), w, h, group=group + 3,
            uv_rect=uvz)                                     # +Z
    M.plate(mesh, (x, y, z - hd), (-1, 0, 0), (0, 1, 0), w, h, group=group + 4,
            uv_rect=uvz)                                     # -Z


FLOOR_T = 0.08
CEIL_T = 0.06


def floor_plate(mesh, w, d, center=(0, 0, 0), tile=0.9, group=0):
    """Walking surface stays at y = 0; the slab hangs below it."""
    slab_box(mesh, w, FLOOR_T, d,
             (center[0], center[1] - FLOOR_T * 0.5, center[2]), tile, group)


def ceiling_plate(mesh, w, d, y, tile=1.6, group=0):
    slab_box(mesh, w, CEIL_T, d, (0.0, y + CEIL_T * 0.5, 0.0), tile, group)


def wall_panel(mesh_wall, mesh_base, x, z, length, along_z=True, group=0):
    """A wall slab plus its baseboard, centred on (x, z)."""
    if along_z:
        size = (WALL_T, WALL_H, length)
        bsize = (WALL_T * 0.28, BASE_H, length)
        boff = (-WALL_T * 0.5 - WALL_T * 0.14 if x > 0 else
                WALL_T * 0.5 + WALL_T * 0.14)
        bcenter = (x + boff, BASE_H * 0.5, z)
        uv = (0, 0, length * 0.55, WALL_H * 0.55)
    else:
        size = (length, WALL_H, WALL_T)
        bsize = (length, BASE_H, WALL_T * 0.28)
        boff = (-WALL_T * 0.5 - WALL_T * 0.14 if z > 0 else
                WALL_T * 0.5 + WALL_T * 0.14)
        bcenter = (x, BASE_H * 0.5, z + boff)
        uv = (0, 0, length * 0.55, WALL_H * 0.55)
    box(mesh_wall, size, (x, WALL_H * 0.5, z), 0.004, group, uv)
    box(mesh_base, bsize, bcenter, 0.004, group)


def troffer(scene, node, x, z, rot=0.0):
    """Recessed 2x4 fluorescent: housing, diffuser, and the light itself."""
    body = M.Mesh("Troffer_Housing", MAT["metal"])
    box(body, (0.62, 0.10, 1.24), (0.0, WALL_H - 0.05, 0.0), 0.01)
    glow = M.Mesh("Troffer_Diffuser", MAT["glow"])
    M.plate(glow, (0.0, WALL_H - 0.098, 0.0), (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0), 0.56, 1.18, group=0)
    n = Node("Troffer", vec.mat_mul(vec.translate((x, 0.0, z)),
                                    vec.rot_y(rot)), meshes=[body, glow])
    node.add(n)
    return n


def scatter_papers(mesh, rnd, count, x_range, z_range, y=0.004):
    """A few sheets on the floor. Cheap mess: two triangles each."""
    for _ in range(count):
        x = rnd.uniform(*x_range)
        z = rnd.uniform(*z_range)
        a = rnd.uniform(0, math.pi)
        w, d = 0.216, 0.279
        ca, sa = math.cos(a), math.sin(a)
        M.plate(mesh, (x, y + rnd.uniform(0.0, 0.004), z),
                (ca, 0.0, sa), (-sa, 0.0, ca), w, d, group=0,
                uv_rect=(0, 0, 1, 1))


# -------------------------------------------------------------- the pieces


def piece_hallway_straight(scene):
    root = Node("Hallway_Straight")
    rnd = random.Random(5)
    floor = M.Mesh("Floor", MAT["carpet"])
    floor_plate(floor, CORRIDOR, MODULE)
    root.add_mesh(floor)

    walls = M.Mesh("Walls", MAT["wall"])
    bases = M.Mesh("Baseboards", MAT["base"])
    half = (CORRIDOR + WALL_T) * 0.5
    wall_panel(walls, bases, half, 0.0, MODULE)
    wall_panel(walls, bases, -half, 0.0, MODULE)
    root.add_mesh(walls)
    root.add_mesh(bases)

    ceil = M.Mesh("Ceiling", MAT["ceiling"])
    ceiling_plate(ceil, CORRIDOR, MODULE, WALL_H)
    root.add_mesh(ceil)

    troffer(scene, root, 0.0, -1.0)
    troffer(scene, root, 0.0, 1.0)

    papers = M.Mesh("Scatter", MAT["paper"])
    scatter_papers(papers, rnd, 3, (-0.9, 0.9), (-1.7, 1.7))
    root.add_mesh(papers)
    return root


def piece_hallway_corner(scene):
    """L-shaped: the corridor enters from -Z and turns out to +X.

    Both legs are the same clear width as the straight section and end flush
    with the module edge, so a corner butts against a straight piece on either
    face with no seam.
    """
    root = Node("Hallway_Corner")
    rnd = random.Random(9)
    half = CORRIDOR * 0.5                 # 1.20, inside face of the wall
    mid = half + WALL_T * 0.5             # wall centreline
    edge = MODULE * 0.5                   # 2.00, module boundary

    floor = M.Mesh("Floor", MAT["carpet"])
    floor_plate(floor, MODULE, MODULE)
    root.add_mesh(floor)

    walls = M.Mesh("Walls", MAT["wall"])
    bases = M.Mesh("Baseboards", MAT["base"])
    # outer corner: the long west and north walls
    wl = (edge + half + WALL_T)           # -2.00 .. +1.20+t
    wall_panel(walls, bases, -mid, (-edge + half + WALL_T) * 0.5, wl,
               along_z=True)
    wall_panel(walls, bases, (edge - half - WALL_T) * 0.5, mid, wl,
               along_z=False)
    # inner corner: the short return that closes off the un-walked quadrant
    il = edge - half                      # 0.80
    wall_panel(walls, bases, mid, -edge + il * 0.5, il, along_z=True)
    wall_panel(walls, bases, edge - il * 0.5, -mid, il, along_z=False)
    root.add_mesh(walls)
    root.add_mesh(bases)

    ceil = M.Mesh("Ceiling", MAT["ceiling"])
    ceiling_plate(ceil, MODULE, MODULE, WALL_H)
    root.add_mesh(ceil)
    troffer(scene, root, 0.0, 0.0, rot=math.pi * 0.25)

    papers = M.Mesh("Scatter", MAT["paper"])
    scatter_papers(papers, rnd, 4, (-1.0, 1.5), (-1.5, 1.0))
    root.add_mesh(papers)
    return root


def piece_doorway(scene):
    """A wall section with an office entrance, frame and a door left ajar."""
    root = Node("Doorway")
    walls = M.Mesh("Walls", MAT["wall"])
    bases = M.Mesh("Baseboards", MAT["base"])
    side = (MODULE - DOOR_W) * 0.5
    for sx in (-1.0, 1.0):
        cx = sx * (DOOR_W * 0.5 + side * 0.5)
        box(walls, (side, WALL_H, WALL_T), (cx, WALL_H * 0.5, 0.0), 0.004, 0,
            (0, 0, side * 0.55, WALL_H * 0.55))
        box(bases, (side, BASE_H, WALL_T * 1.3), (cx, BASE_H * 0.5, 0.0), 0.004)
    box(walls, (DOOR_W, WALL_H - DOOR_H, WALL_T),
        (0.0, DOOR_H + (WALL_H - DOOR_H) * 0.5, 0.0), 0.004, 0,
        (0, 0, DOOR_W * 0.55, (WALL_H - DOOR_H) * 0.55))
    root.add_mesh(walls)
    root.add_mesh(bases)

    frame = M.Mesh("Frame", MAT["wood_dk"])
    ft = 0.055
    for sx in (-1.0, 1.0):
        box(frame, (ft, DOOR_H + ft, WALL_T + 0.03),
            (sx * (DOOR_W * 0.5 + ft * 0.5), (DOOR_H + ft) * 0.5, 0.0), 0.006)
    box(frame, (DOOR_W + ft * 2, ft, WALL_T + 0.03),
        (0.0, DOOR_H + ft * 0.5, 0.0), 0.006)
    root.add_mesh(frame)

    # door leaf, hinged on the left and standing open
    leaf = M.Mesh("Door", MAT["wood"])
    box(leaf, (DOOR_W - 0.02, DOOR_H - 0.03, 0.042),
        ((DOOR_W - 0.02) * 0.5, (DOOR_H - 0.03) * 0.5, 0.0), 0.006, 0,
        (0, 0, 1.0, 2.2))
    knob = M.Mesh("Knob", MAT["steel"])
    M.cylinder(knob, (DOOR_W - 0.10, 1.03, 0.030), (DOOR_W - 0.10, 1.03, 0.060),
               0.019, 0.026, 12, group=0)
    M.cylinder(knob, (DOOR_W - 0.10, 1.03, -0.030),
               (DOOR_W - 0.10, 1.03, -0.060), 0.019, 0.026, 12, group=3)
    door = Node("Door_Leaf", vec.mat_mul(
        vec.translate((-DOOR_W * 0.5 + 0.01, 0.015, 0.0)),
        vec.rot_y(-62.0 * D2R)), meshes=[leaf, knob])
    root.add(door)

    plate = M.Mesh("Nameplate", MAT["steel"])
    box(plate, (0.22, 0.075, 0.008),
        (DOOR_W * 0.5 + side * 0.35, 1.62, WALL_T * 0.5 + 0.004), 0.003)
    root.add_mesh(plate)
    return root


def piece_desk_chair(scene):
    root = Node("Desk_Chair")
    rnd = random.Random(13)
    W, D, H = 1.60, 0.78, 0.745
    top = M.Mesh("Desk_Top", MAT["wood"])
    slab(top, W, D, 0.038, (0.0, H - 0.019, 0.0), 1.2)
    root.add_mesh(top)

    frame = M.Mesh("Desk_Body", MAT["laminate"])
    # modesty panel + a drawer pedestal on the right
    box(frame, (W - 0.16, H - 0.30, 0.030), (0.0, (H - 0.30) * 0.5 + 0.13,
                                             -D * 0.5 + 0.06), 0.006)
    ped = (0.42, H - 0.05, D - 0.08)
    box(frame, ped, (W * 0.5 - ped[0] * 0.5 - 0.03, ped[1] * 0.5, 0.0), 0.008)
    for sx in (-1.0,):
        box(frame, (0.055, H - 0.05, D - 0.10),
            (sx * (W * 0.5 - 0.07), (H - 0.05) * 0.5, 0.0), 0.006)
    root.add_mesh(frame)

    fronts = M.Mesh("Drawers", MAT["laminate"])
    pulls = M.Mesh("Pulls", MAT["steel"])
    for i in range(3):
        y = 0.16 + i * 0.215
        box(fronts, (0.39, 0.195, 0.022),
            (W * 0.5 - 0.24, y, D * 0.5 - 0.045), 0.005)
        box(pulls, (0.16, 0.016, 0.020),
            (W * 0.5 - 0.24, y + 0.055, D * 0.5 - 0.030), 0.004)
    root.add_mesh(fronts)
    root.add_mesh(pulls)

    # desk clutter: a paper stack, a couple of loose sheets, a mug
    stack = M.Mesh("Paper_Stack", MAT["paper"])
    slab(stack, 0.225, 0.290, 0.045, (-0.34, H + 0.022, 0.02), 1.0, chamfer=0.003)
    root.add_mesh(stack)
    loose = M.Mesh("Desk_Loose_Paper", MAT["paper"])
    scatter_papers(loose, rnd, 2, (-0.05, 0.30), (-0.18, 0.18), y=H + 0.002)
    root.add_mesh(loose)
    mug = M.Mesh("Mug", MAT["plastic"])
    M.cylinder(mug, (0.42, H + 0.001, -0.16), (0.42, H + 0.095, -0.16),
               0.041, 0.038, 14, group=0)
    root.add_mesh(mug)

    lamp = M.Mesh("Lamp", MAT["metal"])
    M.cylinder(lamp, (-0.66, H, -0.26), (-0.66, H + 0.012, -0.26), 0.075,
               0.070, 14, group=0)
    M.cylinder(lamp, (-0.66, H + 0.012, -0.26), (-0.60, H + 0.40, -0.20),
               0.014, 0.012, 8, group=3)
    M.cylinder(lamp, (-0.60, H + 0.40, -0.20), (-0.48, H + 0.34, -0.12),
               0.085, 0.055, 14, group=6)
    root.add_mesh(lamp)
    shade = M.Mesh("Lamp_Glow", MAT["glow"])
    M.plate(shade, (-0.50, H + 0.345, -0.13), (1.0, 0.0, 0.0),
            (0.0, 0.0, -1.0), 0.10, 0.10, group=0)
    root.add_mesh(shade)

    # ---- task chair, pushed back and turned
    chair = Node("Chair", vec.mat_mul(vec.translate((-0.08, 0.0, 0.72)),
                                      vec.rot_y(196.0 * D2R)))
    seat = M.Mesh("Chair_Seat", MAT["plastic"])
    slab(seat, 0.48, 0.46, 0.075, (0.0, 0.455, 0.0), 1.0, chamfer=0.02)
    back = M.Mesh("Chair_Back", MAT["plastic"])
    bn = Node("Chair_Back_Node", vec.mat_mul(
        vec.translate((0.0, 0.50, -0.21)), vec.rot_x(-9.0 * D2R)))
    slab(back, 0.44, 0.070, 0.50, (0.0, 0.25, 0.0), 1.0, chamfer=0.02)
    bn.add_mesh(back)
    chair.add(bn)
    post = M.Mesh("Chair_Post", MAT["steel"])
    M.cylinder(post, (0.0, 0.10, 0.0), (0.0, 0.44, 0.0), 0.036, 0.030, 12,
               group=0)
    chair.add_mesh(post)
    legs = M.Mesh("Chair_Base", MAT["plastic"])
    for i in range(5):
        a = i * math.pi * 2 / 5
        d = (math.cos(a), 0.0, math.sin(a))
        M.cylinder(legs, (d[0] * 0.03, 0.085, d[2] * 0.03),
                   (d[0] * 0.30, 0.055, d[2] * 0.30), 0.026, 0.016, 8,
                   group=i * 3, up_hint=(0, 1, 0))
        M.cylinder(legs, (d[0] * 0.31, 0.030, d[2] * 0.31),
                   (d[0] * 0.31, 0.058, d[2] * 0.31), 0.028, 0.024, 10,
                   group=i * 3 + 1)
    chair.add_mesh(legs)
    chair.add_mesh(seat)
    root.add(chair)
    return root


def piece_file_cabinet(scene):
    root = Node("File_Cabinet")
    W, D, H = 1.05, 0.50, 1.32
    body = M.Mesh("Cabinet_Body", MAT["metal"])
    slab(body, W, D, H, (0.0, H * 0.5, 0.0), 1.0, chamfer=0.010)
    root.add_mesh(body)

    fronts = M.Mesh("Drawer_Fronts", MAT["metal"])
    pulls = M.Mesh("Pulls", MAT["steel"])
    labels = M.Mesh("Labels", MAT["paper"])
    n = 4
    dh = (H - 0.10) / n
    for i in range(n):
        y = 0.05 + dh * (i + 0.5)
        open_z = 0.16 if i == 2 else 0.0        # one drawer left open
        box(fronts, (W - 0.03, dh - 0.012, 0.026),
            (0.0, y, D * 0.5 + 0.013 + open_z), 0.005)
        box(pulls, (0.34, 0.020, 0.026),
            (0.0, y + dh * 0.26, D * 0.5 + 0.030 + open_z), 0.004)
        M.plate(labels, (0.0, y - dh * 0.22, D * 0.5 + 0.028 + open_z),
                (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 0.16, 0.045, group=0)
        if open_z:
            # a slice of files poking out of the open drawer
            files = M.Mesh("Files", MAT["paper"])
            for k in range(5):
                slab(files, 0.20, 0.012, dh * 0.55,
                     (-0.22 + k * 0.10, y + 0.02, D * 0.5 + open_z - 0.10),
                     1.0, chamfer=0.002)
            root.add_mesh(files)
    root.add_mesh(fronts)
    root.add_mesh(pulls)
    root.add_mesh(labels)

    topper = M.Mesh("Cabinet_Top", MAT["laminate"])
    slab(topper, W + 0.02, D + 0.02, 0.022, (0.0, H + 0.011, 0.0), 1.0)
    root.add_mesh(topper)

    clutter = M.Mesh("Cabinet_Clutter", MAT["paper"])
    slab(clutter, 0.23, 0.30, 0.055, (-0.30, H + 0.05, 0.02), 1.0,
         chamfer=0.003)
    root.add_mesh(clutter)
    return root


def piece_banker_boxes(scene):
    root = Node("Bankers_Boxes")
    rnd = random.Random(21)
    BW, BD, BH = 0.400, 0.310, 0.265
    layout = [(0.0, 0.0, 0.0, 3.0), (0.0, BH, 0.0, -6.0),
              (0.0, BH * 2, 0.0, 4.0), (0.46, 0.0, 0.10, -14.0)]
    for i, (x, y, z, rot) in enumerate(layout):
        m = M.Mesh("Box_%d" % (i + 1), MAT["card"])
        slab(m, BW, BD, BH, (0.0, BH * 0.5, 0.0), 2.4, chamfer=0.006)
        lid = M.Mesh("Lid_%d" % (i + 1), MAT["card"])
        slab(lid, BW + 0.014, BD + 0.014, 0.055,
             (0.0, BH + 0.020, 0.0), 2.4, chamfer=0.005)
        node = Node("Box_%d" % (i + 1),
                    vec.mat_mul(vec.translate((x, y, z)),
                                vec.rot_y(rot * D2R)), meshes=[m, lid])
        if i == 3:
            # lid off and leaning against the stack
            lid.pos = [(p[0], p[1] - BH - 0.02, p[2]) for p in lid.pos]
            node.meshes = [m]
            leaning = Node("Lid_Leaning", vec.mat_mul(
                vec.translate((0.30, 0.12, 0.20)),
                vec.mat_mul(vec.rot_y(28.0 * D2R), vec.rot_x(74.0 * D2R))),
                meshes=[lid])
            root.add(leaning)
        root.add(node)

    spill = M.Mesh("Spill", MAT["paper"])
    for _ in range(5):
        x = rnd.uniform(-0.15, 0.85)
        z = rnd.uniform(-0.25, 0.55)
        a = rnd.uniform(0, math.pi)
        ca, sa = math.cos(a), math.sin(a)
        M.plate(spill, (x, 0.004 + rnd.uniform(0, 0.004), z),
                (ca, 0.0, sa), (-sa, 0.0, ca), 0.216, 0.279, group=0)
    root.add_mesh(spill)
    return root


def piece_reception_counter(scene):
    root = Node("Reception_Counter")
    W, D = 2.40, 0.70
    LOW, HIGH = 0.745, 1.105
    front = M.Mesh("Counter_Front", MAT["wood"])
    slab(front, W, 0.06, HIGH - 0.02, (0.0, (HIGH - 0.02) * 0.5,
                                       D * 0.5 - 0.03), 1.1)
    root.add_mesh(front)

    band = M.Mesh("Counter_Band", MAT["wood_dk"])
    slab(band, W + 0.02, 0.030, 0.10, (0.0, 0.34, D * 0.5 - 0.005), 1.0)
    root.add_mesh(band)

    body = M.Mesh("Counter_Body", MAT["laminate"])
    slab(body, W - 0.10, D - 0.12, LOW - 0.04, (0.0, (LOW - 0.04) * 0.5,
                                                -0.04), 1.0)
    root.add_mesh(body)

    work = M.Mesh("Work_Surface", MAT["laminate"])
    slab(work, W - 0.06, D - 0.10, 0.035, (0.0, LOW - 0.017, -0.04), 1.0)
    root.add_mesh(work)

    cap = M.Mesh("Transaction_Top", MAT["wood_dk"])
    slab(cap, W + 0.10, D + 0.10, 0.045, (0.0, HIGH - 0.022, 0.02), 1.2)
    root.add_mesh(cap)

    sign = M.Mesh("Sign", MAT["steel"])
    slab(sign, 0.52, 0.020, 0.13, (0.0, HIGH + 0.075, 0.10), 1.0, chamfer=0.004)
    M.cylinder(sign, (-0.20, HIGH + 0.02, 0.10), (-0.20, HIGH + 0.075, 0.10),
               0.010, 0.010, 8, group=8)
    M.cylinder(sign, (0.20, HIGH + 0.02, 0.10), (0.20, HIGH + 0.075, 0.10),
               0.010, 0.010, 8, group=9)
    root.add_mesh(sign)

    clutter = M.Mesh("Counter_Clutter", MAT["paper"])
    slab(clutter, 0.22, 0.29, 0.035, (0.72, LOW + 0.018, -0.06), 1.0,
         chamfer=0.003)
    slab(clutter, 0.22, 0.29, 0.020, (-0.62, LOW + 0.010, -0.02), 1.0,
         chamfer=0.003)
    root.add_mesh(clutter)
    return root


def piece_ink_pod(scene):
    """Refill canister for the Bates stamp -- the one pickup in the kit.

    A prop that has to read as "grab this" from across a corridor, at 0.20 m
    tall, against grey carpet. That is what the brand orange is for; the black
    foot and cap give it enough tonal separation not to melt into the accent,
    and the steel nozzle says it dispenses rather than stores.

    Deliberately the cheapest piece in the kit -- the prototype instances it
    four times and respawns them, so it is built at 14 sides rather than the
    kit's usual 16 and carries no unique texture.

    Sized off what it has to survive on screen, not off a real ink bottle. The
    longest sightline the layout can produce is about 12 m, and measured at
    1100x690 the pod covers:

        0.30 m tall ->  9 x 13 px      0.40 m ->  14 x 18      0.51 m -> 19 x 23

    A 9 px speck is not something a player can be asked to detour towards, so
    this is built at 0.40 m -- a bulk refill jug rather than a desk inkwell, and
    the point past which it stops reading as something you would pour from. The
    rest of the legibility comes from the prototype floating it off the carpet
    rather than from making it any larger.
    """
    root = Node("Ink_Pod")
    N = 14
    S = 1.95              # ~0.40 m tall -- see the docstring

    foot = M.Mesh("Pod_Foot", MAT["plastic"])
    M.cylinder(foot, (0.0*S, 0.0*S, 0.0*S), (0.0*S, 0.022*S, 0.0*S), 0.076*S, 0.070*S, N,
               group=0)
    root.add_mesh(foot)

    body = M.Mesh("Pod_Body", MAT["ink"])
    # slight taper and a waist, so it is not a plain tube
    M.cylinder(body, (0.0*S, 0.022*S, 0.0*S), (0.0*S, 0.072*S, 0.0*S), 0.070*S, 0.064*S, N,
               group=0, cap_start=False)
    M.cylinder(body, (0.0*S, 0.072*S, 0.0*S), (0.0*S, 0.112*S, 0.0*S), 0.064*S, 0.067*S, N,
               group=3, cap_start=False, cap_end=False)
    M.cylinder(body, (0.0*S, 0.112*S, 0.0*S), (0.0*S, 0.150*S, 0.0*S), 0.067*S, 0.058*S, N,
               group=6, cap_start=False, cap_end=False)
    root.add_mesh(body)

    # label band: a hair proud of the body so it catches a different normal
    band = M.Mesh("Pod_Label", MAT["paper"])
    M.cylinder(band, (0.0*S, 0.060*S, 0.0*S), (0.0*S, 0.104*S, 0.0*S), 0.0685*S, 0.0700*S, N,
               group=0, cap_start=False, cap_end=False)
    root.add_mesh(band)

    cap = M.Mesh("Pod_Cap", MAT["plastic"])
    M.cylinder(cap, (0.0*S, 0.150*S, 0.0*S), (0.0*S, 0.186*S, 0.0*S), 0.046*S, 0.042*S, N,
               group=0)
    root.add_mesh(cap)

    nozzle = M.Mesh("Pod_Nozzle", MAT["steel"])
    M.cylinder(nozzle, (0.0*S, 0.186*S, 0.0*S), (0.0*S, 0.206*S, 0.0*S), 0.016*S, 0.013*S, N,
               group=0)
    root.add_mesh(nozzle)

    # Beacon. The bottle alone loses the argument at range: even at 0.40 m and
    # floated to eye level it is 14 x 17 px from 12 m, which is the longest
    # sightline the layout can produce.
    #
    # Two emissive quads crossed at right angles, not a column -- a round beam
    # thin enough to look like a beam is about 2 px wide at that distance, which
    # is height with no width and reads as nothing at all. Crossed quads are
    # 0.17 m across for four triangles and present the same silhouette from any
    # approach.
    #
    # Tapered to a point rather than left as a bar. The exporter has no
    # alphaMode, so the beacon cannot fade out the way a shaft of light should,
    # and a full-width opaque bar at this emissive reads as an orange pole
    # growing out of the lid. Narrowing it does the same job with geometry:
    # bright and wide where it meets the bottle, gone by the top.
    beam = M.Mesh("Pod_Beacon", MAT["ink_glow"])
    bw, tw = 0.17, 0.018
    y0, y1 = 0.20 * S, 0.20 * S + 1.15
    for ax in ((1.0, 0.0), (0.0, 1.0)):          # crossed: along X, then along Z
        base = len(beam.pos)
        for (hw, y, u) in ((-bw * 0.5, y0, 0.0), (bw * 0.5, y0, 1.0),
                           (tw * 0.5, y1, 1.0), (-tw * 0.5, y1, 0.0)):
            beam.add_vertex((hw * ax[0], y, hw * ax[1]),
                            (u, (y - y0) / (y1 - y0)))
        beam.add_face((base, base + 1, base + 2, base + 3), 0)
    root.add_mesh(beam)
    return root


PIECES = {
    "hallway_straight": (piece_hallway_straight, "Straight hallway section"),
    "hallway_corner": (piece_hallway_corner, "90 degree corner"),
    "doorway": (piece_doorway, "Office entrance with door"),
    "desk_chair": (piece_desk_chair, "Desk, chair, lamp and clutter"),
    "file_cabinet": (piece_file_cabinet, "Lateral file cabinet"),
    "banker_boxes": (piece_banker_boxes, "Stack of banker's boxes"),
    "reception_counter": (piece_reception_counter, "Reception counter"),
    "ink_pod": (piece_ink_pod, "Stamp ink refill pickup"),
}


# ---------------------------------------------------------------- previews


# Corridor pieces are rooms, not props: an exterior shot of one is a beige
# box. These get an eye-height camera standing inside them instead.
INTERIOR_CAMS = {
    "hallway_straight": ((0.0, 1.65, 1.85), (0.0, 1.50, -2.0), 70),
    "hallway_corner": ((0.0, 1.65, -1.85), (0.35, 1.52, 0.9), 74),
    "doorway": ((0.0, 1.65, 2.3), (0.02, 1.45, 0.0), 62),
}


def piece_preview(scene, root, outdir, name, quick):
    from tools.render import Camera, render
    os.makedirs(outdir, exist_ok=True)
    w, h = (420, 300) if quick else (700, 500)

    if name in INTERIOR_CAMS:
        eye, tgt, fov = INTERIOR_CAMS[name]
        img = render(scene, Camera(eye, tgt, fov_deg=fov), w, h)
        p = os.path.join(outdir, "%s.png" % name)
        img.save(p)
        return p

    # props: frame the piece from its own bounds
    pts = [vec.xform_point(m, p) for m, mesh in scene.flatten() for p in mesh.pos]
    lo = [min(p[k] for p in pts) for k in range(3)]
    hi = [max(p[k] for p in pts) for k in range(3)]
    c = [(lo[k] + hi[k]) * 0.5 for k in range(3)]
    r = max(hi[k] - lo[k] for k in range(3)) * 0.5 + 0.2
    eye = (c[0] + r * 1.35, c[1] + r * 0.85, c[2] + r * 1.75)
    img = render(scene, Camera(eye, (c[0], c[1] * 0.92, c[2]), fov_deg=38), w, h)
    p = os.path.join(outdir, "%s.png" % name)
    img.save(p)
    return p


def assembly_preview(outdir, quick):
    """First-person view down an assembled corridor -- the scale check."""
    from tools.render import Camera, render
    scene = Scene("Office_Assembly")
    materials(scene)
    root = Node("Assembly")
    scene.add_root(root)

    for i, z in enumerate((-2.0, -6.0)):
        n = piece_hallway_straight(scene)
        n.name = "Hall_%d" % i
        n.matrix = vec.translate((0.0, 0.0, z))
        root.add(n)
    corner = piece_hallway_corner(scene)
    corner.matrix = vec.translate((0.0, 0.0, -10.0))
    root.add(corner)

    door = piece_doorway(scene)
    door.matrix = vec.mat_mul(vec.translate((-CORRIDOR * 0.5 - WALL_T * 0.5,
                                             0.0, -5.4)),
                              vec.rot_y(90.0 * D2R))
    root.add(door)

    cab = piece_file_cabinet(scene)
    cab.matrix = vec.mat_mul(vec.translate((0.92, 0.0, -3.4)),
                             vec.rot_y(-90.0 * D2R))
    root.add(cab)

    boxes = piece_banker_boxes(scene)
    boxes.matrix = vec.mat_mul(vec.translate((-0.85, 0.0, -7.6)),
                               vec.rot_y(14.0 * D2R))
    root.add(boxes)

    counter = piece_reception_counter(scene)
    counter.matrix = vec.mat_mul(vec.translate((0.55, 0.0, -9.4)),
                                 vec.rot_y(180.0 * D2R))
    root.add(counter)

    w, h = (640, 400) if quick else (1100, 690)
    cam = Camera((0.0, 1.65, 0.6), (0.05, 1.45, -6.0), fov_deg=68)
    img = render(scene, cam, w, h)
    p = os.path.join(outdir, "assembly_firstperson.png")
    img.save(p)

    # cutaway: an exterior overview of a corridor is just a beige box, so drop
    # the ceilings and shoot down into the run
    stripped = []

    def strip(node):
        keep = [m for m in node.meshes if m.name != "Ceiling"]
        if len(keep) != len(node.meshes):
            stripped.append((node, node.meshes))
            node.meshes = keep
        for c in list(node.children):
            if c.name == "Troffer":
                stripped.append((node, None))
                node.children.remove(c)
            else:
                strip(c)

    strip(root)
    cam2 = Camera((2.6, 9.0, -0.4), (0.0, 0.6, -6.4), fov_deg=46)
    img2 = render(scene, cam2, w, h)
    p2 = os.path.join(outdir, "assembly_cutaway.png")
    img2.save(p2)
    return [p, p2], scene.stats()


# -------------------------------------------------------------------- main


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="build/environment")
    ap.add_argument("--only", default=None)
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)
    prev = os.path.join(args.out, "previews")

    names = [args.only] if args.only else list(PIECES)
    total = 0
    for name in names:
        fn, desc = PIECES[name]
        scene = Scene("Office_" + name)
        materials(scene)
        root = fn(scene)
        scene.add_root(root)
        scene.prune()
        glb = os.path.join(args.out, "%s.glb" % name)
        export_glb(scene, glb)
        st = scene.stats()
        total += st["triangles"]
        print("  %-18s %-34s %5d tris  (%.0f KB)"
              % (name, desc, st["triangles"], os.path.getsize(glb) / 1024.0))
        if not args.no_preview:
            piece_preview(scene, root, prev, name, args.quick)

    print("  kit total: %d triangles" % total)
    if not args.no_preview:
        os.makedirs(prev, exist_ok=True)
        _, st = assembly_preview(prev, args.quick)
        print("  assembly preview: %d triangles in view" % st["triangles"])
    print("done in %.1fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
