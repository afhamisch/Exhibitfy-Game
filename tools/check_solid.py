"""Find open geometry: meshes with boundary edges, i.e. holes.

A closed solid has every edge shared by exactly two faces. Anything with
edges used once is open -- you can see inside it from some angle. Flat decals
(a sheet of paper, a label) are open by nature and are meant to be, so this
reports rather than fails, and flags which is which by counting faces.

    python3 -m tools.check_solid build/environment/desk_chair.glb
    python3 -m tools.check_solid --scene environment
"""

import sys


def boundary_edges(positions, faces, tol=5):
    """Edges used by only one face, keyed on welded vertex positions."""
    def key(i):
        p = positions[i]
        return (round(p[0], tol), round(p[1], tol), round(p[2], tol))

    count = {}
    for idx in faces:
        n = len(idx)
        for k in range(n):
            a = key(idx[k])
            b = key(idx[(k + 1) % n])
            e = (a, b) if a <= b else (b, a)
            count[e] = count.get(e, 0) + 1
    return [e for e, c in count.items() if c == 1]


def check_mesh(mesh):
    faces = [idx for idx, _g in mesh.faces]
    open_edges = boundary_edges(mesh.pos, faces)
    total_edges = sum(len(f) for f in faces)
    # every edge used exactly once means nothing is shared: the mesh is a
    # collection of loose plates (paper, labels, a light diffuser), which is
    # meant to be flat. Anything else with boundary edges has a real hole.
    return {"name": mesh.name, "faces": len(faces),
            "open_edges": len(open_edges),
            "flat": len(open_edges) == total_edges}


def check_scene(scene, label=""):
    rows = []
    for _world, m in scene.flatten():
        rows.append(check_mesh(m))
    bad = [r for r in rows if r["open_edges"] and not r["flat"]]
    flat = [r for r in rows if r["open_edges"] and r["flat"]]
    if label:
        print("=== %s" % label)
    for r in sorted(bad, key=lambda r: -r["open_edges"]):
        print("   OPEN  %-26s %4d faces, %4d boundary edges"
              % (r["name"], r["faces"], r["open_edges"]))
    for r in flat:
        print("   flat  %-26s %4d faces (single-sided decal)"
              % (r["name"], r["faces"]))
    if not bad and not flat:
        print("   all meshes closed")
    return bad, flat


if __name__ == "__main__":
    if "--scene" in sys.argv:
        which = sys.argv[sys.argv.index("--scene") + 1]
        if which == "environment":
            import build_environment as E
            from tools.gltf import Scene
            total = 0
            for name, (fn, _desc) in E.PIECES.items():
                sc = Scene(name)
                E.materials(sc)
                sc.add_root(fn(sc))
                bad, flat = check_scene(sc, name)
                total += len(bad)
            print("\n%d open solid mesh(es) across the kit" % total)
        elif which == "fpv":
            import build_fpv_arms as B
            check_scene(B.build_scene("000137"), "fpv arms")
