# Playable prototype

A first-person slice of **Tom Rexington, Esq.: Bates & Destroy**, in the
browser. Everything it renders is loaded from the GLBs in `../build` — the FPV
viewmodel with its `Stamp_Swing` clip, all four paper enemies out of the
shared-texture `enemies.glb`, and the modular office kit. No geometry is
authored here.

**[▶ Watch a full run](screenshots/gameplay_demo.webm)** (11.5 s) — captured
from the prototype itself: chasing the four documents down, stamping them,
watching them file themselves into the binder, and the wake screen when the
last one lands.

![corridor](screenshots/prototype_corridor.png)

## Run it

The page loads assets from `../build`, so **serve the repository root**, not
this folder:

```bash
cd /path/to/Exhibitfy-Game
python3 -m http.server 8000
```

Then open <http://localhost:8000/web/> and click to play.

Opening `index.html` as a `file://` URL will **not** work — browsers block
module scripts and asset fetches from the filesystem. Any static server is
fine (`npx serve`, `php -S localhost:8000`, VS Code Live Server); it just has
to be rooted at the repo, not at `web/`.

No internet connection is needed. Three.js r160 is vendored into
`web/vendor/three/` and wired up through an import map, so there is no
third-party CDN dependency — which also matters if this ends up embedded on a
landing page.

## Controls

| | |
|---|---|
| Move | `W` `A` `S` `D` |
| Look | Mouse |
| Stamp | Left click |
| Sprint | `Shift` |
| Release cursor | `Esc` |

You fell asleep assembling a trial binder. Chase the paperwork down and stamp
it — Bates numbering is how exhibits get indexed, so a stamped document isn't
destroyed, it's **filed**: it flattens, takes the impression, then files itself
into the binder you're carrying.

You have **90 seconds** before you wake up. Get all four in and the binder is
complete; run the clock out and you wake with it unfinished, which is the only
way to lose. The chaotic stack is the one that costs you — at 3.33 m/s it is
faster than your walk, so it has to be sprinted down or cornered.

## How it works

**Movement** is clamped to a set of walkable rectangles derived from the
layout, rather than colliding against wall meshes. For a prototype on a grid
kit that is both cheaper and far more reliable — you cannot fall through a
seam. Blocked axes are resolved separately so you slide along walls instead of
sticking.

**The viewmodel** is drawn by a second camera into its own scene, composited
over the world with a depth clear. That is the standard first-person weapon
trick and it means the arms never clip into a wall you stand against. The rig
is authored in view space with the camera at the origin looking down −Z, so it
drops in with no offset.

**The swing** plays the baked `Stamp_Swing` clip. Hit resolution fires once, on
the frame the die is actually planted (frame 11 of 23, so 0.367 s in) rather
than on click — so the hit lands when the stamp lands.

The strike is a **sphere centred 1.05 m ahead of the eye**, not a cone from the
camera. A cone degenerates at point-blank range: enemies do not block you, so
you routinely end up standing on top of one, and the angle to something at
0.2 m is meaningless. The sphere behaves the same at every distance.

**Lighting** uses a generated `RoomEnvironment` probe. Without an environment
map every metallic surface in the kit — the watch, the stamp's steel, the
cabinet — renders black, since there is nothing for them to reflect.

**The viewmodel camera runs at the same FOV as the world camera.** A narrower
one blows the arms up until they cover the middle of the screen, which is
exactly where enemies appear.

**Filing** is what a hit actually does. A stamped document lies flat for the
length of the `Stamped` clip, then arcs up, tumbles, shrinks and homes on the
binder below your eye. The HUD counts filed exhibits rather than kills, and
filing the last one closes the binder: the wake screen fades up and releases
the cursor.

![the wake screen](screenshots/prototype_wake.png)

**Enemies** run the looping `Run` clip, flee once you are close enough, wander
at reduced speed otherwise, and turn on the spot when cornered. Getting
stamped cross-fades to the one-shot `Stamped` clip, which flattens the sheet
and leaves the Bates impression on it.

All four variants are on the floor, one of each:

![the four variants](screenshots/prototype_variants.png)

| | Speed | Flees at | Turn (rad/s) | Behaviour |
|---|---:|---:|---:|---|
| Pleading Paper | 2.45 m/s | 7.0 m | 3.2 | the baseline |
| Privilege Paper | 2.25 m/s | 9.1 m | 4.0 | bolts early and **weaves** instead of running straight |
| Discovery Binder | 1.20 m/s | 5.6 m | 1.8 | lumbers, turns badly, but is a wider target |
| Chaotic PDF Stack | 3.33 m/s | 8.1 m | 4.3 | faster than your walk (3.1 m/s) — sprint, or cut it off at a corner |

Those speeds are not invented for the prototype: each tracks the cadence and
stride actually baked into that variant's `Run` clip, so the feet keep pace
with the ground instead of skating. The binder is half the pleading paper's
speed because its stride is both shorter and slower.

The privilege paper's long evasive weave lives here rather than in its clip. A
weave slower than one stride cannot be baked into a one-stride loop — half a
cycle does not close, and it used to pop at the seam. On the heading it also
does something the clip never could: make the thing genuinely harder to hit.

## Weight

| | |
|---|---|
| Page + script | 21.5 KB |
| Three.js (vendored) | 820 KB on disk, ~180 KB gzipped over the wire |
| Assets actually fetched | 4.05 MB (viewmodel, all four enemies, seven kit pieces) |

The enemies used to be 2.9 MB of that, as four self-contained GLBs. They could
not share a texture, so `paper_pleading` shipped three times and the face and
Bates maps four times each — **1.12 MB of byte-identical pixels**. They now come
from one `enemies.glb` (1.86 MB, six unique images instead of fourteen), which
is one request instead of four and one GPU upload of each map instead of four.
The per-variant files still ship as the art deliverable; the prototype just
does not fetch them.

Nothing here is geometry — the whole kit is ~14k triangles, and all four
enemies together are 7,340. What is left is genuinely textures: the viewmodel
is 1.2 MB of embedded PNGs and the six enemy maps are most of the rest. The
next real cut is authored resolution (the page maps are 1024², the rest 512²),
weighed against the legal headers staying readable at distance. KTX2/Basis
would beat both, but it needs a third-party encoder, which the pipeline's
standard-library-only rule does not allow — that one has to be raised, not
adopted quietly.

## Known limits of this slice

- No sound and no score persistence.
- Enemies path by fleeing and wall-sliding, not by navmesh — they can get
  briefly stuck grinding a corner before they turn out of it.
- One of each variant spawns, and that is the whole roster — there is no wave
  system, respawn, or difficulty curve.
- Collision is the walkable-rectangle set, so props (desks, boxes) do not block
  you — you walk through them.
