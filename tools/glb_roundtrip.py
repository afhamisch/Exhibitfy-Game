"""Re-import an exported GLB and render it, to prove the file itself is whole.

validate_glb.py checks that the structure is self-consistent. This goes
further: it rebuilds world-space triangles purely from the file's accessors and
node transforms -- the same work an importer does -- and reports what it finds,
optionally rendering the result. If the model is broken in a viewer but whole
here, the file is fine; if it is broken here, the exporter is at fault.

    python3 -m tools.glb_roundtrip build/exhibitfy_fpv_arms.glb [out.png]
"""

import math
import struct
import sys

from . import vec
from .validate_glb import accessor_values, read_glb


def node_matrix(n):
    if "matrix" in n:
        m = n["matrix"]          # glTF is column-major
        return [m[0], m[4], m[8], m[12],
                m[1], m[5], m[9], m[13],
                m[2], m[6], m[10], m[14],
                m[3], m[7], m[11], m[15]]
    t = n.get("translation", [0.0, 0.0, 0.0])
    q = n.get("rotation", [0.0, 0.0, 0.0, 1.0])
    s = n.get("scale", [1.0, 1.0, 1.0])
    r = vec.mat_from_quat(q)
    return vec.mat_mul(vec.mat_mul(vec.translate(t), r),
                       vec.scale((s[0], s[1], s[2])))


def load(path):
    """-> (parts, stats) where parts is [(name, world_matrix, positions, tris)]"""
    g, bin_ = read_glb(path)
    parts = []

    def walk(ni, parent):
        n = g["nodes"][ni]
        world = vec.mat_mul(parent, node_matrix(n))
        if "mesh" in n:
            mesh = g["meshes"][n["mesh"]]
            for pi, prim in enumerate(mesh["primitives"]):
                pos = [p for p in accessor_values(
                    g, bin_, prim["attributes"]["POSITION"])]
                idx = [i[0] for i in accessor_values(g, bin_, prim["indices"])]
                tris = [(idx[k], idx[k + 1], idx[k + 2])
                        for k in range(0, len(idx), 3)]
                parts.append(("%s/%d" % (n.get("name", ni), pi), world, pos,
                              tris))
        for c in n.get("children", []):
            walk(c, world)

    for r in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(r, vec.IDENTITY)

    lo = [1e30] * 3
    hi = [-1e30] * 3
    nv = nt = 0
    for _name, world, pos, tris in parts:
        nv += len(pos)
        nt += len(tris)
        for p in pos:
            w = vec.xform_point(world, p)
            for k in range(3):
                lo[k] = min(lo[k], w[k])
                hi[k] = max(hi[k], w[k])
    return parts, {"primitives": len(parts), "vertices": nv, "triangles": nt,
                   "min": lo, "max": hi}


def render_file(path, out_png, width=900, height=560, eye=None, target=None):
    """Render straight from the re-imported data, with no build-side objects."""
    from .gltf import Material, Node, Scene
    from .mesh import Mesh
    from .render import Camera, render

    parts, st = load(path)
    scene = Scene("roundtrip")
    scene.material(Material("RT", (0.80, 0.80, 0.82), 0.15, 0.45))
    root = Node("root")
    scene.add_root(root)
    for name, world, pos, tris in parts:
        m = Mesh(name, "RT")
        for p in pos:
            m.add_vertex(vec.xform_point(world, p), (0.0, 0.0))
        for t in tris:
            m.add_face(t, 0)
        root.add_mesh(m)

    lo, hi = st["min"], st["max"]
    c = [(lo[k] + hi[k]) * 0.5 for k in range(3)]
    r = max(hi[k] - lo[k] for k in range(3)) * 0.5 + 0.05
    eye = eye or (c[0] + r * 1.1, c[1] + r * 0.75, c[2] + r * 1.9)
    target = target or c
    img = render(scene, Camera(eye, target, fov_deg=40), width, height)
    img.save(out_png)
    return st


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "build/exhibitfy_fpv_arms.glb"
    out = sys.argv[2] if len(sys.argv) > 2 else None
    if out:
        st = render_file(path, out)
    else:
        _, st = load(path)
    print("re-imported %s" % path)
    print("  %d primitives, %d vertices, %d triangles"
          % (st["primitives"], st["vertices"], st["triangles"]))
    print("  world bounds  min %s" % [round(v, 4) for v in st["min"]])
    print("                max %s" % [round(v, 4) for v in st["max"]])
    size = [st["max"][k] - st["min"][k] for k in range(3)]
    print("  size          %s m" % [round(v, 4) for v in size])
    if out:
        print("  render -> %s" % out)
