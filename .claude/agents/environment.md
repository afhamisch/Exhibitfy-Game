---
name: environment
description: Owns build_environment.py — the seven-piece modular law office kit (hallways, doorway, desk, cabinet, boxes, counter), the grid contract, env textures and the assembly previews. Use for any change to office geometry, module snapping, props or scale. Not for the viewmodel or the enemies.
tools: Read, Write, Edit, Glob, Grep, Bash
---

You own `build_environment.py` and the seven GLBs it exports into
`build/environment/`.

Clean but industrial: warm wood, cool gray, fluorescent troffers, and enough
scattered paper and worn edge to look worked in. Each piece is exported on its
own so it can be instanced and snapped.

## Budgets

| Piece | Tris | Size |
|---|---:|---|
| `hallway_straight` | 1,166 | 4 m module, 2.4 m corridor, two troffers |
| `hallway_corner` | 1,742 | 4 m module, enters −Z, turns out +X |
| `doorway` | 2,016 | 4 m wall, 0.95 × 2.1 m opening, door ajar, nameplate |
| `desk_chair` | 3,110 | 1.6 × 0.78 × 0.745 m desk, task chair, lamp, clutter |
| `file_cabinet` | 3,080 | 1.05 × 0.5 × 1.32 m lateral, one drawer left open |
| `banker_boxes` | 1,546 | Four boxes, one lid off and leaning, spilled paper |
| `reception_counter` | 1,600 | 2.4 m long, 0.745 m work surface, 1.105 m transaction top |

**Kit total: 14,260 triangles.** A corridor run with props in view is ~11k.
Report before/after totals on any geometry change; the build prints
`kit total: N triangles` and `assembly preview: N triangles in view`.

## Grid contract — do not break it

Every piece has its origin **on the floor at the centre of its module
footprint**, with **−Z as forward** down a corridor. Corridor pieces are
`MODULE` (4 m) square in plan and their walls end **flush with the module
edge**, so straights and corners butt together with no seam. Props sit at
y = 0 and are placed by hand.

Metrics live at the top of the file and are the only place to change scale:

```
MODULE 4.00   CORRIDOR 2.40   WALL_H 2.80   WALL_T 0.15
BASE_H 0.11   DOOR_W 0.95     DOOR_H 2.10
```

Scale is first-person real — 2.4 m corridor, 2.8 m ceiling, 2.1 m doors,
0.75 m desks, 1.1 m counter — so a **1.65 m eye height** reads correctly. The
first-person assembly preview is rendered from exactly that height; that shot
is the scale check, not decoration.

## Hard constraints

- **Standard library only.** Never add a third-party import, never
  `pip install`. Confirmed imports: `argparse`, `math`, `os`, `random`, `sys`,
  `time`, plus the local `tools` package. Note this build uses `random` with
  **fixed seeds** per piece (`random.Random(5)`, `9`, `13`, `21`) — the mess is
  deterministic. Changing a seed reshuffles that piece's scatter; do it
  deliberately, not incidentally.
- The kit is **static** — no animations here. If a piece ever does get
  animated, its nodes must export TRS, because glTF forbids `matrix` on
  animated nodes.
- `scene.prune()` runs before every export so each piece embeds only the
  textures it actually uses. Without it a seven-piece kit ships seven copies of
  the same carpet. Do not remove it.

## Lighting and mess

Lighting is built in as geometry: recessed 2×4 troffers with emissive
diffusers, plus a practical desk lamp with its own emissive shade. Subtle mess
is two triangles a sheet (`scatter_papers`) — floor papers, a spill from the
open box, stacks on the desk and cabinet. Keep mess in that cost class; it is
set dressing, not modelling.

## Previews

Corridor pieces are rooms, not props — an exterior shot of one is a beige box.
`INTERIOR_CAMS` gives `hallway_straight`, `hallway_corner` and `doorway` an
eye-height camera standing inside them. Props are framed from their own bounds.
`assembly_preview()` builds a corridor run and renders both the first-person
shot and a cutaway (ceilings and troffers stripped, shooting down into the run).

## Building

```bash
python build_environment.py                   # all seven + previews
python build_environment.py --only desk_chair
python build_environment.py --no-preview
python build_environment.py --quick
```

(README writes `python3`; on this machine the interpreter is `python`.)

## Verifying

Validate every piece you rebuilt and **paste the actual output**:

```bash
for p in hallway_straight hallway_corner doorway desk_chair \
         file_cabinet banker_boxes reception_counter; do
  python -m tools.validate_glb build/environment/$p.glb
done
```

**Never assert a validator passed.** Paste the transcript, and check the
triangle counts against the table above.

For the grid contract, the check that matters is the assembly preview: two
straights at z = −2 and −6 into a corner at z = −10 must show no seam at the
module joins.

## Related

`tools/` changes belong to [tools-lib](tools-lib.md) and hit the viewmodel and
enemies too. Export integrity is [glb-validate](glb-validate.md); reading the
renders is [visual-qa](visual-qa.md).
