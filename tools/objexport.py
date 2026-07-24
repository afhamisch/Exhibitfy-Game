"""Wavefront OBJ export that keeps quads intact.

The GLB is the runtime asset; this OBJ is the "editable" copy -- import it in
Blender/Maya and the edge loops are exactly as authored, no triangle soup.
"""

import os

from . import vec
from .gltf import compute_normals


def export_obj(scene, obj_path, mtl_name="exhibitfy_fpv.mtl",
               texture_dir="textures"):
    parts = scene.flatten()
    lines = ["# Tom Rexington, Esq. -- FPV arms + Exhibitfy Bates stamp",
             "# Quads preserved. Y-up, metres, camera at origin looking -Z.",
             "mtllib %s" % mtl_name, ""]
    vbase = 1
    tbase = 1
    nbase = 1
    for world, m in parts:
        normals, key = compute_normals(m)
        lines.append("o %s" % m.name)
        lines.append("usemtl %s" % m.material)
        for p in m.pos:
            w = vec.xform_point(world, p)
            lines.append("v %.6f %.6f %.6f" % w)
        for t in m.uv:
            lines.append("vt %.6f %.6f" % (t[0], t[1]))
        # one normal per (vertex, shading group) pair, emitted per face corner
        nlist = []
        nmap = {}
        for idx, group in m.faces:
            for vi in idx:
                k = (key(vi), group)
                if k not in nmap:
                    nmap[k] = len(nlist)
                    nlist.append(vec.xform_dir(world, normals[k]))
        for n in nlist:
            l = max(1e-9, vec.length(n))
            lines.append("vn %.6f %.6f %.6f" % (n[0] / l, n[1] / l, n[2] / l))
        for idx, group in m.faces:
            corners = []
            for vi in idx:
                ni = nmap[(key(vi), group)] + nbase
                corners.append("%d/%d/%d" % (vi + vbase, vi + tbase, ni))
            lines.append("f " + " ".join(corners))
        lines.append("")
        vbase += len(m.pos)
        tbase += len(m.uv)
        nbase += len(nlist)

    with open(obj_path, "w") as f:
        f.write("\n".join(lines))

    mtl_path = os.path.join(os.path.dirname(obj_path), mtl_name)
    ml = ["# Materials for exhibitfy_fpv.obj (approximate OBJ mapping of PBR)"]
    for name, m in scene.materials.items():
        ml.append("newmtl %s" % name)
        ml.append("Kd %.4f %.4f %.4f" % m.base_color[:3])
        ml.append("Ks %.4f %.4f %.4f" % ((0.9, 0.9, 0.9) if m.metallic > 0.5
                                         else (0.25, 0.25, 0.25)))
        ml.append("Ns %.1f" % max(2.0, (1.0 - m.roughness) ** 2 * 900.0))
        ml.append("d 1.0")
        ml.append("illum 2")
        if m.base_tex:
            ml.append("map_Kd %s/%s.png" % (texture_dir, m.base_tex))
        if m.mr_tex:
            ml.append("map_Pr %s/%s.png" % (texture_dir, m.mr_tex))
        ml.append("Pm %.3f" % m.metallic)
        ml.append("Pr %.3f" % m.roughness)
        ml.append("")
    with open(mtl_path, "w") as f:
        f.write("\n".join(ml))
    return obj_path, mtl_path
