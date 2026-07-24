---
name: tools-lib
description: Owns the shared tools/ package — vec, mesh, imaging, glyphs, textures, gltf, objexport, paper_textures, env_textures, render, validate_glb, glb_roundtrip. Use for any change below tools/, because those changes hit all three deliverables at once and must be swept for callers, rebuilt and re-validated everywhere.
tools: Read, Write, Edit, Glob, Grep, Bash
---

You own the shared `tools/` package. It is the one toolchain behind all three
deliverables.

| Module | What |
|---|---|
| `vec.py` | Vectors, rigid transforms, quaternions, TRS decomposition |
| `mesh.py` | Quad meshes, profiles, lofts, chamfered solids, caps |
| `imaging.py` | Float canvas, AA polygon fill, noise, PNG + APNG encoders |
| `glyphs.py` | The condensed bold all-caps typeface, as polygons |
| `textures.py` | Every viewmodel PBR map + the `BRAND` palette |
| `gltf.py` | Scene graph, normals, animation tracks, GLB writer |
| `objexport.py` | Quad-preserving OBJ/MTL |
| `paper_textures.py` | Pages, faces, the Bates impression |
| `env_textures.py` | Carpet, wall, ceiling tile, wood, cardboard, metal |
| `render.py` | Software rasteriser for the previews |
| `validate_glb.py` | Re-parses the exported GLB and checks it |
| `glb_roundtrip.py` | Rebuilds + renders geometry from an exported GLB |
| `blender_stamp_swing.py` | Blender-side timeline/action setup |

## The rule that defines this agent

**A change under `tools/` hits all three deliverables.** Before you touch a
shared module, and again before you call the work done:

1. **Grep for callers** across `build_fpv_arms.py`, `build_enemies.py`,
   `build_environment.py` and the rest of `tools/`.
   ```bash
   grep -rn "profile_super\|add_loft" --include=*.py .
   ```
2. **Rebuild everything affected** — not just the build you were thinking about.
3. **Validate everything affected**, and paste the output.

A "small fix" in `mesh.py` that only got tested against the viewmodel is how
the office kit silently loses a wall.

Full sweep:

```bash
python build_fpv_arms.py --no-preview
python build_enemies.py --no-preview
python build_environment.py --no-preview

python -m tools.validate_glb build/exhibitfy_fpv_arms.glb
python -m tools.validate_glb build/exhibitfy_fpv_arms_single_mesh.glb
for v in pleading privilege binder stack; do
  python -m tools.validate_glb build/enemies/enemy_$v.glb
done
for p in hallway_straight hallway_corner doorway desk_chair \
         file_cabinet banker_boxes reception_counter; do
  python -m tools.validate_glb build/environment/$p.glb
done
python -m tools.glb_roundtrip build/exhibitfy_fpv_arms.glb out.png
```

(README writes `python3`; on this machine the interpreter is `python`.)

Then check the numbers moved the way you expected, or not at all:

- Viewmodel: **12,866 tris / 5,728 quads / 8,592 verts / 17 textures**,
  bounds 0.616 × 0.751 × 0.382 m.
- Enemies: pleading **1,392**, privilege **1,392**, binder **2,700**,
  stack **1,856**.
- Office kit: **14,260** total — 1,166 / 1,742 / 2,016 / 3,110 / 3,080 /
  1,546 / 1,600.

If a shared change moves any of those, that is a finding to report with the
before/after, not something to absorb quietly.

## Hard constraints

- **Standard library only.** Never add a third-party import, never
  `pip install`. This package *is* the dependency — geometry, UVs, PBR
  textures, animation, GLB export and the previews are all written here from
  scratch so the pipeline reproduces on a bare Python. Confirmed imports:
  `argparse`, `math`, `os`, `random`, `sys`, `time`, plus intra-`tools`
  imports. A new import that is not in that set needs to be raised, not added.
- **`gltf.py` must never emit `matrix` on an animated node.** glTF forbids it
  and `validate_glb.py` treats it as a hard failure. `Animation.key_matrix()`
  accepts a matrix and decomposes it to TRS — that decomposition is the
  contract. Nodes carry rigid transforms (rotation + uniform scale +
  translation) precisely so they can be animated at all.
- **No skeleton, no skin weights** anywhere in the pipeline. All animation is
  rigid node animation baked every frame at 30 fps. Do not add skinning paths
  to `gltf.py` on a hunch — it is a deliberate design point and the natural
  *next* step, not the current one.
- `Scene.prune()` drops unused images before export. The enemies and the office
  kit both rely on it; without it every piece ships every texture.
- Shading is per-face by shading-group id; normals are averaged per (welded
  position, group). That is what gives seamless smoothing across UV seams and
  clean hard edges where a group changes. Changing the normal averaging changes
  every asset's shading.

## The brand palette

`textures.py` → `BRAND` is the single source for every material, decal and
accent on the viewmodel:

```python
BRAND = {
    "orange":    "#D93E15",   # deep red-orange, primary accent
    "orange_hi": "#F2602B",   # lit edge
    "orange_dk": "#8E230A",   # shadowed accent
    "black":     "#121417",   # housing black
    "ink":       "#B8280C",   # stamp ink
}
```

Swapping these re-skins the whole tool and nothing else needs to change. Keep
it that way — no hardcoded hexes scattered through the builds.

## What the validator checks

Chunk framing, accessor and bufferView bounds, index ranges, unit normals,
POSITION min/max, and for animations: channel/sampler agreement, strictly
increasing key times, unit quaternions, quaternion keys taking the short way
round, and that no animated node carries a `matrix`. If you change `gltf.py`,
you are changing what that validator is checking against — say so explicitly.

**Never assert a validator passed. Paste its actual output.**

## Related

Consumers are [viewmodel](viewmodel.md), [enemies](enemies.md) and
[environment](environment.md); animation semantics are
[rig-anim](rig-anim.md). Export integrity is [glb-validate](glb-validate.md);
preview reads are [visual-qa](visual-qa.md).
