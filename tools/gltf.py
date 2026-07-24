"""Scene graph + GLB (binary glTF 2.0) writer.

Nodes carry rigid transforms so the exported hierarchy stays animation-ready:
Stamp / Arm_L / Arm_R / Hand_* / finger nodes can be keyframed directly, and
the quad loops underneath are ready for skinning.
"""

import json
import math
import struct

from . import vec
from .imaging import srgb_to_linear


class Material:
    def __init__(self, name, base_color=(1, 1, 1, 1), metallic=0.0,
                 roughness=0.5, base_tex=None, mr_tex=None,
                 uv_scale=(1.0, 1.0), double_sided=False, emissive=(0, 0, 0),
                 srgb_input=True):
        """base_color is given in sRGB (converted to linear on export)."""
        self.name = name
        if srgb_input:
            lin = srgb_to_linear(base_color[:3])
            self.base_color = (lin[0], lin[1], lin[2],
                               base_color[3] if len(base_color) > 3 else 1.0)
        else:
            self.base_color = tuple(base_color) if len(base_color) == 4 else \
                tuple(base_color) + (1.0,)
        self.metallic = metallic
        self.roughness = roughness
        self.base_tex = base_tex
        self.mr_tex = mr_tex
        self.uv_scale = uv_scale
        self.double_sided = double_sided
        self.emissive = emissive


class Node:
    def __init__(self, name, matrix=None, meshes=None, children=None):
        self.name = name
        self.matrix = matrix or list(vec.IDENTITY)
        self.meshes = list(meshes or [])
        self.children = list(children or [])

    def add(self, child):
        self.children.append(child)
        return child

    def add_mesh(self, m):
        self.meshes.append(m)
        return m


class Animation:
    """Baked TRS keyframes for a set of nodes.

    Keys are baked every frame rather than sparsely: LINEAR interpolation
    between dense keys reproduces the authored easing exactly, which matters
    when the whole point is that the slam accelerates and the impact snaps.
    """

    def __init__(self, name, fps=30.0):
        self.name = name
        self.fps = fps
        self.tracks = {}          # id(node) -> {"node":.., "t":[], path:[..]}

    def key(self, node, time, translation=None, rotation=None, scale=None):
        tr = self.tracks.setdefault(id(node), {"node": node, "t": [],
                                               "translation": [],
                                               "rotation": [], "scale": []})
        tr["t"].append(float(time))
        if translation is not None:
            tr["translation"].append(tuple(float(v) for v in translation))
        if rotation is not None:
            prev = tr["rotation"][-1] if tr["rotation"] else None
            tr["rotation"].append(vec.quat_shortest(prev, rotation))
        if scale is not None:
            tr["scale"].append(tuple(float(v) for v in scale))

    def key_matrix(self, node, time, matrix):
        t, q, s = vec.mat_to_trs(matrix)
        self.key(node, time, t, q, s if abs(s[0] - 1.0) > 1e-6 else None)

    @property
    def duration(self):
        return max((tr["t"][-1] for tr in self.tracks.values()), default=0.0)


class Scene:
    def __init__(self, name="Scene"):
        self.name = name
        self.roots = []
        self.materials = {}
        self.images = {}
        self.animations = []

    def add_root(self, node):
        self.roots.append(node)
        return node

    def animation(self, anim):
        self.animations.append(anim)
        return anim

    def material(self, mat):
        self.materials[mat.name] = mat
        return mat

    def image(self, name, canvas):
        self.images[name] = canvas
        return name

    # ------------------------------------------------------------- helpers
    def flatten(self):
        """[(world_matrix, Mesh)] for every mesh in the graph."""
        out = []

        def walk(node, parent):
            world = vec.mat_mul(parent, node.matrix)
            for m in node.meshes:
                out.append((world, m))
            for c in node.children:
                walk(c, world)

        for r in self.roots:
            walk(r, vec.IDENTITY)
        return out

    def stats(self):
        tris = verts = 0
        quads = 0
        for _, m in self.flatten():
            s = m.stats()
            tris += s["triangles"]
            verts += s["verts"]
            quads += s["quads"]
        return {"triangles": tris, "quads": quads, "raw_verts": verts,
                "meshes": len(self.flatten())}


# --------------------------------------------------------------- normals


def compute_normals(mesh):
    """Area-weighted normals averaged per (welded position, shading group)."""
    acc = {}

    def key(i):
        p = mesh.pos[i]
        return (round(p[0], 5), round(p[1], 5), round(p[2], 5))

    for idx, group in mesh.faces:
        # Newell's method: robust for quads that aren't perfectly planar
        nx = ny = nz = 0.0
        n = len(idx)
        for k in range(n):
            a = mesh.pos[idx[k]]
            b = mesh.pos[idx[(k + 1) % n]]
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        for vi in idx:
            k = (key(vi), group)
            cur = acc.get(k)
            if cur is None:
                acc[k] = [nx, ny, nz]
            else:
                cur[0] += nx
                cur[1] += ny
                cur[2] += nz

    normals = {}
    for k, v in acc.items():
        l = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
        normals[k] = (v[0] / l, v[1] / l, v[2] / l) if l > 1e-12 else (0.0, 1.0, 0.0)
    return normals, key


def build_primitive(mesh):
    """Triangulated, de-duplicated vertex arrays for one mesh."""
    normals, key = compute_normals(mesh)
    remap = {}
    pos, nrm, uvs, tris = [], [], [], []

    def emit(vi, group):
        k = (vi, group)
        got = remap.get(k)
        if got is not None:
            return got
        got = len(pos)
        remap[k] = got
        pos.append(mesh.pos[vi])
        uvs.append(mesh.uv[vi])
        nrm.append(normals[(key(vi), group)])
        return got

    for idx, group in mesh.faces:
        vs = [emit(i, group) for i in idx]
        if len(vs) == 3:
            tris.append(tuple(vs))
        elif len(vs) == 4:
            # split along the shorter diagonal -> better shading on quads
            p = mesh.pos
            d02 = vec.length(vec.sub(p[idx[0]], p[idx[2]]))
            d13 = vec.length(vec.sub(p[idx[1]], p[idx[3]]))
            if d02 <= d13:
                tris.append((vs[0], vs[1], vs[2]))
                tris.append((vs[0], vs[2], vs[3]))
            else:
                tris.append((vs[0], vs[1], vs[3]))
                tris.append((vs[1], vs[2], vs[3]))
        else:
            for i in range(1, len(vs) - 1):
                tris.append((vs[0], vs[i], vs[i + 1]))
    return pos, nrm, uvs, tris


# ------------------------------------------------------------------ GLB


class _Buffer:
    def __init__(self):
        self.data = bytearray()
        self.views = []

    def add(self, raw, target=None, stride=None):
        while len(self.data) % 4:
            self.data.append(0)
        offset = len(self.data)
        self.data += raw
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(raw)}
        if target:
            view["target"] = target
        if stride:
            view["byteStride"] = stride
        self.views.append(view)
        return len(self.views) - 1


def export_glb(scene, path, generator="exhibitfy-fpv-builder"):
    buf = _Buffer()
    gltf = {
        "asset": {"version": "2.0", "generator": generator},
        "scene": 0,
        "scenes": [{"name": scene.name, "nodes": []}],
        "nodes": [],
        "meshes": [],
        "materials": [],
        "accessors": [],
        "bufferViews": [],
        "buffers": [],
    }

    # ---- images / samplers / textures
    img_index = {}
    if scene.images:
        gltf["images"] = []
        gltf["samplers"] = [{
            "magFilter": 9729, "minFilter": 9987,  # linear, linear-mip-linear
            "wrapS": 10497, "wrapT": 10497,
        }]
        gltf["textures"] = []
        for name, canvas in scene.images.items():
            png = canvas.to_png_bytes()
            view = buf.add(png)
            gltf["images"].append({"name": name, "bufferView": view,
                                   "mimeType": "image/png"})
            gltf["textures"].append({"name": name, "sampler": 0,
                                     "source": len(gltf["images"]) - 1})
            img_index[name] = len(gltf["textures"]) - 1

    # ---- materials
    mat_index = {}
    for name, m in scene.materials.items():
        pbr = {
            "baseColorFactor": list(m.base_color),
            "metallicFactor": m.metallic,
            "roughnessFactor": m.roughness,
        }
        if m.base_tex and m.base_tex in img_index:
            pbr["baseColorTexture"] = {"index": img_index[m.base_tex]}
        if m.mr_tex and m.mr_tex in img_index:
            pbr["metallicRoughnessTexture"] = {"index": img_index[m.mr_tex]}
        entry = {"name": name, "pbrMetallicRoughness": pbr,
                 "doubleSided": bool(m.double_sided)}
        if any(m.emissive):
            entry["emissiveFactor"] = list(srgb_to_linear(m.emissive))
        gltf["materials"].append(entry)
        mat_index[name] = len(gltf["materials"]) - 1

    def accessor(view, count, ctype, atype, mn=None, mx=None):
        a = {"bufferView": view, "componentType": ctype, "count": count,
             "type": atype}
        if mn is not None:
            a["min"] = mn
            a["max"] = mx
        gltf["accessors"].append(a)
        return len(gltf["accessors"]) - 1

    def make_mesh(meshes, name):
        prims = []
        for m in meshes:
            pos, nrm, uvs, tris = build_primitive(m)
            if not tris:
                continue
            pbytes = bytearray()
            nbytes = bytearray()
            tbytes = bytearray()
            mn = [1e30] * 3
            mx = [-1e30] * 3
            for p in pos:
                pbytes += struct.pack("<3f", *p)
                for k in range(3):
                    mn[k] = min(mn[k], p[k])
                    mx[k] = max(mx[k], p[k])
            for n in nrm:
                nbytes += struct.pack("<3f", *n)
            for t in uvs:
                tbytes += struct.pack("<2f", t[0], 1.0 - t[1])  # glTF v is down
            big = len(pos) > 65535
            ibytes = bytearray()
            for tri in tris:
                if big:
                    ibytes += struct.pack("<3I", *tri)
                else:
                    ibytes += struct.pack("<3H", *tri)
            vp = buf.add(bytes(pbytes), 34962)
            vn = buf.add(bytes(nbytes), 34962)
            vt = buf.add(bytes(tbytes), 34962)
            vi = buf.add(bytes(ibytes), 34963)
            prim = {
                "attributes": {
                    "POSITION": accessor(vp, len(pos), 5126, "VEC3", mn, mx),
                    "NORMAL": accessor(vn, len(nrm), 5126, "VEC3"),
                    "TEXCOORD_0": accessor(vt, len(uvs), 5126, "VEC2"),
                },
                "indices": accessor(vi, len(tris) * 3,
                                    5125 if big else 5123, "SCALAR"),
                "mode": 4,
            }
            if m.material in mat_index:
                prim["material"] = mat_index[m.material]
            prims.append(prim)
        if not prims:
            return None
        gltf["meshes"].append({"name": name, "primitives": prims})
        return len(gltf["meshes"]) - 1

    node_index = {}

    def add_node(node):
        entry = {"name": node.name}
        # TRS rather than a matrix: glTF forbids `matrix` on animated nodes,
        # and every transform here is rotation + uniform scale + translation,
        # so the decomposition is exact.
        if node.matrix != list(vec.IDENTITY):
            t, q, s = vec.mat_to_trs(node.matrix)
            if any(abs(v) > 1e-9 for v in t):
                entry["translation"] = [float(v) for v in t]
            if abs(q[3] - 1.0) > 1e-9 or any(abs(v) > 1e-9 for v in q[:3]):
                entry["rotation"] = [float(v) for v in q]
            if any(abs(v - 1.0) > 1e-9 for v in s):
                entry["scale"] = [float(v) for v in s]
        gltf["nodes"].append(entry)
        my = len(gltf["nodes"]) - 1
        node_index[id(node)] = my
        if node.meshes:
            mi = make_mesh(node.meshes, node.name + "_mesh")
            if mi is not None:
                gltf["nodes"][my]["mesh"] = mi
        kids = [add_node(c) for c in node.children]
        if kids:
            gltf["nodes"][my]["children"] = kids
        return my

    for r in scene.roots:
        gltf["scenes"][0]["nodes"].append(add_node(r))

    # ---- animations
    if scene.animations:
        gltf["animations"] = []
        for anim in scene.animations:
            samplers = []
            channels = []
            for tr in anim.tracks.values():
                ni = node_index.get(id(tr["node"]))
                if ni is None:
                    continue
                times = tr["t"]
                tb = b"".join(struct.pack("<f", t) for t in times)
                tv = buf.add(tb)
                ta = accessor(tv, len(times), 5126, "SCALAR",
                              [min(times)], [max(times)])
                for chan_path, comps in (("translation", 3), ("rotation", 4),
                                         ("scale", 3)):
                    vals = tr[chan_path]
                    if not vals:
                        continue
                    if len(vals) != len(times):
                        raise ValueError("%s: %d %s keys for %d times"
                                         % (tr["node"].name, len(vals),
                                            chan_path, len(times)))
                    vb = b"".join(struct.pack("<" + "f" * comps, *v)
                                  for v in vals)
                    vv = buf.add(vb)
                    va = accessor(vv, len(vals), 5126,
                                  "VEC3" if comps == 3 else "VEC4")
                    samplers.append({"input": ta, "output": va,
                                     "interpolation": "LINEAR"})
                    channels.append({"sampler": len(samplers) - 1,
                                     "target": {"node": ni,
                                                "path": chan_path}})
            gltf["animations"].append({"name": anim.name,
                                       "samplers": samplers,
                                       "channels": channels})

    gltf["bufferViews"] = buf.views
    gltf["buffers"] = [{"byteLength": len(buf.data)}]

    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_bytes) % 4:
        json_bytes += b" "
    bin_bytes = bytes(buf.data)
    while len(bin_bytes) % 4:
        bin_bytes += b"\x00"

    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(json_bytes), 0x4E4F534A))
        f.write(json_bytes)
        f.write(struct.pack("<II", len(bin_bytes), 0x004E4942))
        f.write(bin_bytes)
    return path, gltf
