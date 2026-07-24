"""Standalone GLB sanity checker.

Re-parses the exported file from disk (not from the in-memory scene) and
verifies the things that actually break importers: chunk framing, JSON
integrity, accessor/bufferView bounds, index ranges, normal lengths, POSITION
min/max, and that every image really is a PNG.

    python3 -m tools.validate_glb build/exhibitfy_fpv_arms.glb
"""

import json
import math
import struct
import sys

COMPONENT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2),
             5125: ("I", 4), 5126: ("f", 4)}
TYPE_N = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_glb(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, total = struct.unpack_from("<III", data, 0)
    assert magic == 0x46546C67, "not a GLB (bad magic)"
    assert version == 2, "expected glTF 2.0, got %d" % version
    assert total == len(data), "header length %d != file size %d" % (total, len(data))
    off = 12
    js = None
    bin_ = b""
    while off < total:
        clen, ctype = struct.unpack_from("<II", data, off)
        off += 8
        chunk = data[off:off + clen]
        assert len(chunk) == clen, "truncated chunk"
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942:
            bin_ = chunk
        off += clen
        assert off % 4 == 0, "chunk not 4-byte aligned"
    assert js is not None, "no JSON chunk"
    return js, bin_


def accessor_values(g, bin_, index):
    a = g["accessors"][index]
    bv = g["bufferViews"][a["bufferView"]]
    fmt, size = COMPONENT[a["componentType"]]
    n = TYPE_N[a["type"]]
    stride = bv.get("byteStride") or size * n
    base = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    out = []
    for i in range(a["count"]):
        off = base + i * stride
        out.append(struct.unpack_from("<" + fmt * n, bin_, off))
    return out


def validate(path, verbose=True):
    g, bin_ = read_glb(path)
    problems = []
    notes = []

    for i, bv in enumerate(g.get("bufferViews", [])):
        end = bv.get("byteOffset", 0) + bv["byteLength"]
        if end > len(bin_):
            problems.append("bufferView %d runs past the binary chunk" % i)

    for i, img in enumerate(g.get("images", [])):
        bv = g["bufferViews"][img["bufferView"]]
        o = bv.get("byteOffset", 0)
        if bin_[o:o + 8] != b"\x89PNG\r\n\x1a\n":
            problems.append("image %d (%s) is not a PNG" % (i, img.get("name")))

    total_tris = 0
    total_verts = 0
    for mi, m in enumerate(g.get("meshes", [])):
        for pi, prim in enumerate(m["primitives"]):
            tag = "%s/prim%d" % (m.get("name", mi), pi)
            pos = accessor_values(g, bin_, prim["attributes"]["POSITION"])
            nrm = accessor_values(g, bin_, prim["attributes"]["NORMAL"])
            uv = accessor_values(g, bin_, prim["attributes"]["TEXCOORD_0"])
            idx = accessor_values(g, bin_, prim["indices"])
            total_verts += len(pos)
            total_tris += len(idx) // 3
            if not (len(pos) == len(nrm) == len(uv)):
                problems.append("%s: attribute counts differ" % tag)
            if len(idx) % 3:
                problems.append("%s: index count not a multiple of 3" % tag)
            mx = max(v[0] for v in idx)
            if mx >= len(pos):
                problems.append("%s: index %d >= vertex count %d"
                                % (tag, mx, len(pos)))
            acc = g["accessors"][prim["attributes"]["POSITION"]]
            mn = [min(p[k] for p in pos) for k in range(3)]
            mxs = [max(p[k] for p in pos) for k in range(3)]
            for k in range(3):
                if abs(acc["min"][k] - mn[k]) > 1e-5 or \
                        abs(acc["max"][k] - mxs[k]) > 1e-5:
                    problems.append("%s: POSITION min/max wrong on axis %d" % (tag, k))
            bad = 0
            for n in nrm:
                l = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2)
                if abs(l - 1.0) > 1e-3:
                    bad += 1
            if bad:
                problems.append("%s: %d non-unit normals" % (tag, bad))
            degen = 0
            for t in range(0, len(idx), 3):
                a, b, c = idx[t][0], idx[t + 1][0], idx[t + 2][0]
                if a == b or b == c or a == c:
                    degen += 1
            if degen:
                notes.append("%s: %d degenerate triangles" % (tag, degen))
            if "material" not in prim:
                notes.append("%s: no material assigned" % tag)

    # ---- animations
    anim_summary = []
    for ai, anim in enumerate(g.get("animations", [])):
        name = anim.get("name", "<unnamed>")
        if not anim.get("channels"):
            problems.append("animation %s has no channels" % name)
            continue
        targets = set()
        t_lo, t_hi, nkeys = 1e30, -1e30, 0
        for ci, ch in enumerate(anim["channels"]):
            samp = anim["samplers"][ch["sampler"]]
            path = ch["target"]["path"]
            node = ch["target"].get("node")
            if node is None:
                problems.append("%s ch%d has no target node" % (name, ci))
                continue
            targets.add(node)
            # a node driven by animation must not carry a matrix
            if "matrix" in g["nodes"][node]:
                problems.append("%s targets node %d which uses `matrix` "
                                "(glTF forbids this on animated nodes)"
                                % (name, node))
            times = accessor_values(g, bin_, samp["input"])
            vals = accessor_values(g, bin_, samp["output"])
            if len(times) != len(vals):
                problems.append("%s ch%d: %d times vs %d values"
                                % (name, ci, len(times), len(vals)))
            ts = [t[0] for t in times]
            if any(ts[i] >= ts[i + 1] for i in range(len(ts) - 1)):
                problems.append("%s ch%d: times not strictly increasing"
                                % (name, ci))
            t_lo = min(t_lo, ts[0])
            t_hi = max(t_hi, ts[-1])
            nkeys = max(nkeys, len(ts))
            if path == "rotation":
                for q in vals:
                    l = math.sqrt(sum(v * v for v in q))
                    if abs(l - 1.0) > 1e-3:
                        problems.append("%s ch%d: non-unit quaternion"
                                        % (name, ci))
                        break
                # neighbouring keys on opposite hemispheres spin the long way
                flips = sum(1 for i in range(len(vals) - 1)
                            if sum(vals[i][k] * vals[i + 1][k]
                                   for k in range(4)) < 0.0)
                if flips:
                    problems.append("%s ch%d: %d quaternion key(s) take the "
                                    "long way round" % (name, ci, flips))
        anim_summary.append((name, len(targets), len(anim["channels"]),
                             t_lo, t_hi, nkeys))

    used = set()

    def walk(i, depth=0, seen=()):
        if i in seen:
            problems.append("node cycle at %d" % i)
            return
        used.add(i)
        for c in g["nodes"][i].get("children", []):
            walk(c, depth + 1, seen + (i,))

    for r in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(r)
    orphans = [i for i in range(len(g["nodes"])) if i not in used]
    if orphans:
        notes.append("%d nodes not reachable from the scene" % len(orphans))

    if verbose:
        print("glTF %s | %d nodes, %d meshes, %d materials, %d images"
              % (g["asset"]["version"], len(g["nodes"]), len(g["meshes"]),
                 len(g.get("materials", [])), len(g.get("images", []))))
        print("%d triangles, %d vertices, %.1f KB binary"
              % (total_tris, total_verts, len(bin_) / 1024.0))
        for (nm, ntgt, nch, lo, hi, nk) in anim_summary:
            print("animation '%s': %d nodes, %d channels, %d keys, "
                  "%.3f-%.3f s (%d frames @ 30 fps)"
                  % (nm, ntgt, nch, nk, lo, hi, round(hi * 30) + 1))
        for n in notes:
            print("  note: %s" % n)
        for p in problems:
            print("  FAIL: %s" % p)
        print("  %s" % ("OK -- no problems found" if not problems
                        else "%d problem(s)" % len(problems)))
    return problems, {"triangles": total_tris, "vertices": total_verts}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "build/exhibitfy_fpv_arms.glb"
    probs, _ = validate(path)
    sys.exit(1 if probs else 0)
