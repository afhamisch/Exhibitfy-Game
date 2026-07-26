# Playable prototype

A first-person slice of **Tom Rexington, Esq.: Bates & Destroy**, in the
browser. Everything it renders is loaded from the GLBs in `../build` — the FPV
viewmodel with its `Stamp_Swing` clip, the seven paper enemies out of the
shared-texture `enemies.glb`, opposing counsel out of `enemy_counsel.glb`, and
the modular office kit including the conference room he fights you in. No
geometry is authored here.

**[▶ Watch a full run](screenshots/bates_demo.webm)** (45 s, silent) — waking up
at the desk, chasing the four documents down, redacting the privileged one
before stamping it, overruling an objection, closing the binder, and then
surviving the bonus round: opposing counsel throwing binders down a conference
room for thirty seconds, two of them swatted out of the air and fourteen
dodged, none taken. It ends on Lawyer of the Year, which is the run's actual
outcome and not a scripted one — the harness records up to `tries` runs and
keeps the best, and this is what the run reported when it finished:

```
final: {"filed":4,"phase":"bonus","done":true,"clock":0,"redactions":1,
        "survived":14,"tier":"lawyer","deflects":2,"binderHits":0,
        "bonusWon":true,"dryStamps":0,"overruled":1,"struck":0,
        "ending":"Motion denied · Lawyer of the Year"}
```

The capture harness stubs `requestAnimationFrame` and steps the page one frame
at a time. It has to: this renders on SwiftShader at a few frames a second, so
recording in real time gives choppy slow motion. The game clamps its delta with
`Math.min(dt, 0.05)`, so one step is always exactly 50 ms of game time — a fixed
20 fps timestep, and footage that plays at true speed however long the capture
took. It is driven by a bot rather than a scripted camera path, so it cannot
desync from enemies that move on their own.

```bash
node web/screenshots/record_demo.js [max-seconds] [tries]
```

The capture stops 2.5 s after the ending screen rather than at a frame count,
so there is no dead time on the end. The bot's one concession to the camera is
pulling the first objection forward — a competent run closes the binder before
the first one is due at 22 s, so the mechanic would otherwise never appear. The
one thing it is bad at is corners: it walks a straight line at its target, and
the office is a corridor kit, so it needs a sidestep watchdog to get round them.

![corridor](screenshots/prototype_corridor.png)

### The floor plan is a ring with two side offices

It used to be a U, and the two dead ends were capped with the `doorway` module
— whose leaf is modelled standing 62° open. So the art said *walk through* and
the collision said *wall*, and the first person to play it said "I can't go
through the doors." Fair.

Closing the loop deletes the dead ends rather than closing the doors: the
corridor is now a 12 × 16 m ring, you can always keep walking, and you can
never be cornered — which was the same player's other complaint. Two side
offices hang off it through real openings (`hallway_door`, a corridor section
with a hole in its *side*, as opposed to `doorway`, which is a wall laid across
one). Two of the eight document spawns are inside those rooms, and so is an ink pod
each, so a room is somewhere you have to go rather than somewhere you glance
into.

**Eight documents, not four**, because the ring is twice the floor area the U
was and four in that much corridor is a search rather than a chase. The clock
went to **two minutes** with them: the bonus round needs every document filed,
and eight in ninety seconds put it out of reach. Nothing hard-codes either
number — `updateClosing` and `verdictFor` both read `state.enemies.length`.

The things that attack you were always there. Objections chase you down, shake
the view and strike filed exhibits back *out* of your binder — but they are
gated on having filed something (1, 2 and 3 respectively), so a player who
never files one never meets one. That was a discoverability problem, not a
missing feature, and eight documents fixes it by getting you on the board
sooner.

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

**It plays on a phone.** iOS Safari has no Pointer Lock API at all — not
"needs a gesture", it does not exist — so touch is a second input model rather
than an adaptation of the first: left thumb anywhere on the left of the screen
is a virtual stick, right thumb drags to look, a tap on the right stamps, and
redaction gets an on-screen button because there is no second mouse button to
put it on. Sprint is the far end of the stick. Which model is live is decided
once, from `(pointer: fine)`, and everything downstream reads `state.touch`.

Two things the phone build changes on purpose. The world FOV opens up as the
frame gets taller — three.js `fov` is vertical, so a portrait phone keeps the
vertical angle and throws away the horizontal, and the viewmodel authored for a
landscape frame ends up filling half the screen with stamp; the arms shrink to
match. And the binder collision is smaller on touch (`binderRadiusTouch`),
because a thumb on a stick cannot commit to a direction as sharply as a finger
on a key, which does mean the bonus tiers ask slightly less of a phone.

### The arms are lit in the texture, not just by the engine

The skin map used to measure a luminance spread of 16 out of 255 — effectively
a flat colour, with every bit of shape on the arm coming from three.js lighting
alone. That, not polygon count, was why the forearm read as a pale tube: the
viewmodel is 12,780 triangles, an order of magnitude more than a 1997 console
ever gave a first-person hand.

`_form_shade()` in `tools/textures.py` now paints the form in the way a texture
artist would, and the light is deliberately placed off to one silhouette edge
rather than on the side facing you. That last part is the whole trick: the arm
is posed knuckles-to-camera on purpose, so a light centred on the visible face
puts the terminator behind the tube and leaves everything you can see in flat
full light. Measured that way it changed nothing at all. Off to the edge, the
visible sweep runs 218 → 148 and the limb reads round.

There is also a retro renderer — 55% drawing buffer, point-sampled up, nearest
magnification, the Wolfenstein look. It is **off**; it was tried and not kept,
because it muddies the `EXHIBITFY` plate on the die. **Press P** to see it.

**WebGL is still required**, and over anything but `localhost` you still need
**HTTPS**, since pointer lock is refused outside a secure context on desktop.
A small gate in `index.html` checks WebGL *before* `main.js` is fetched, so a
browser that cannot render gets a sentence and a link to the demo video rather
than a black screen and 12 MB off its data plan.

Deploying is just static files: `build/` and `web/` uploaded together, with
`build/` kept as a sibling of `web/` because `main.js` fetches `../build`.
There is no server code, no build step and no database, so any static host
works — the only host-side requirements are HTTPS and serving `.glb`, `.webm`,
`.mp4`, `.ogg` and `.m4a` rather than 404ing on the extension.

### The intro hands over to a live game

One click. **Play the game** starts `web/video/intro.mp4`, and when it ends
you are already playing — no second click, no loading screen between the two.

The whole trick is order, and it is the opposite of the obvious one. Pointer
lock is granted to a **fresh** user gesture and to nothing else, so asking for
it after a fifteen-second video is asking with a stale gesture and being
refused. So the click takes the lock *immediately* and starts the world; the
video is then drawn over a game that is already live and simply held still by
`running()`, which returns false while `state.intro` is up. When the video ends
the overlay goes and the world is already yours — measured, the clock reads
90.0 through the whole reel and 89.9 a second after it. The music bed is held
back the same way (`startBed()`), so the reel's own audio is not competing with
it.

Fifteen seconds is the brief. `INTRO_MAX` caps it at 16 s regardless of the
file — a second clear of the authored cut's 15.04 s, so the video's own `ended`
normally does the handover and the timer is only the backstop for a file that
is longer, stalled or still buffering. There is a shorter 4 s timeout too, for
a reel that never reaches `readyState 2` at all: nobody waits on a video that
is not coming. Any click, tap, Escape, Space or Enter skips.

`introSource()` picks the file rather than assuming one: H.264 MP4 first, VP8
WebM second, and if neither is playable it skips the reel and starts the game
with the music up rather than sitting on a black rectangle. That last branch is
not hypothetical — Playwright's bundled Chromium reports no H.264 at all, which
is also why the MP4 path cannot be exercised in this repo's tests and the WebM
is what they actually play. The WebM is a gameplay cut, not the authored intro,
because the ffmpeg available here has libvpx and **no H.264 decoder** — the
authored file cannot be transcoded, only shipped as-is.

Sound is attempted unmuted, since the click that got us here is a gesture. If
the browser refuses anyway the code retries muted rather than losing the intro
over it, and only gives up and skips if that is refused too. It replays once
per session, not once per reload: `sessionStorage` remembers.

## Controls

| | Desktop | Phone |
|---|---|---|
| Walk | `↑` `↓` | Left thumb, anywhere on the left |
| **Turn** | `←` `→` | Right thumb, drag |
| Face nearest exhibit | `F` | — |
| Stamp | Left click | Tap, right side |
| Redact | Right click | The orange button |
| Sprint | `Shift` | Push the stick to its edge |
| Strafe | `W` `A` `S` `D` + mouse | — |
| Mute | `M` | — |
| Release cursor | `Esc` | — |

The title card shows whichever set applies before you start.

**The arrows turn, they do not strafe.** That is the 1992 scheme and it is the
default on purpose. `WASD` needs the mouse to turn, and that is the whole
difficulty for anyone who does not already play shooters: walk into a corridor
that bends and "forward" stops meaning forward, so you grind along a wall
wondering why `W` changed direction. Turning on the keyboard means the corridor
is always ahead of you. Both schemes are live at once and nobody has to be told
which one they are using.

`F` is the other half of that. It turns you — only turns, it does not fire — to
face the nearest live exhibit, then the objection, then the boss. Hunting a
0.6 m sheet of paper down a grey corridor with a mouse assumes a skill the rest
of the game does not.

And every live exhibit carries an orange chevron with its distance, clamped to
the screen edge with an arrow when it is behind you, fading out inside 4 m
where the paper speaks for itself. A document at 10 m is about nine pixels of
white on a grey wall; the marker is what makes it a target.

You fell asleep assembling a trial binder. Chase the paperwork down and stamp
it — Bates numbering is how exhibits get indexed, so a stamped document isn't
destroyed, it's **filed**: it flattens, takes the impression, then files itself
into the binder you're carrying.

You have **two minutes** before you wake up, and the binder you assemble in that
time is the evidentiary record you walk into court with. The chaotic stack is the
one that costs you — at 3.33 m/s it is faster than your walk, so it has to be
sprinted down or cornered.

### Ink is the cost of a miss

The stamp holds **seven swings**, and every swing spends one whether it lands or
not. Run it dry and the die still comes down — it just leaves a ghost impression
on the carpet and files nothing, however well you aimed. Refills are the orange
pods, deliberately sited at the dead ends and the far corner rather than along
the route you would walk anyway, so running out costs you a corridor and the
seconds it takes to cover it.

Pods hover at 0.62 m and carry a tapered emissive beacon, both for the same
reason: from the far end of a 12 m corridor the bottle on its own is about
14 × 18 px, low in the frame, against carpet of nearly its own value. You cannot
be asked to detour towards something you cannot pick out.

That chain is the whole point: **miss → burn ink → detour → lose clock → worse
verdict.** Before it existed the swing was free, so there was no reason to aim,
close distance, or fear the clock.

### Objections

Three of them — **Hearsay**, **Character evidence** and **Rule 403** — and they
invert the game. An exhibit runs away and you want to catch it; an objection
comes *at* you and you want it gone. Reaching you does not hurt you, because
there is no health here: it **strikes an exhibit back out of the binder**. 403
takes two.

That is what makes a 90-second clock work as a structure without waves. The
score is no longer monotonic, so the round is a total you defend rather than a
counter you fill, and holding ink back becomes a real decision — your last swing
either files a new exhibit or overrules the objection walking at you.

In the bonus round the same objection costs **4 seconds off the ruling clock**
instead of an exhibit. The binder is closed and the case is already won by the
time you get in there, so an objection that could still strike it would be the
game taking back a prize it had just awarded — one test run ended on "Adverse
inference" after the verdict had been decided. The bonus has its own currency,
which is time, so that is what it charges.

Overrule one by stamping it, same verb, and it costs the same ink. The window is
the standoff band between the range you can stamp one at (~2.4 m) and the range
at which it strikes (1.0 m): about a second for hearsay, 0.7 s for 403. All
three are slower than your walk, so breaking off and dealing with one later is
always available.

A rule only appears once the binder holds enough to be worth striking — character
evidence is not relevant until you have put character at issue — so an objection
never lands on an empty binder.

### Closing the binder

A complete binder is not an instant win. It has to be **held for three seconds**,
and an objection that lands inside that window takes an exhibit back out and the
round carries on. Without the hold, filing the fourth exhibit ended the round on
the same frame, which cancelled the whole point of objections: they could
pressure the middle of a round but never touch a finished binder.

### The bonus round

Closing the binder used to buy nothing — beat the clock by a minute and you got
the same screen as someone who scraped it. Close it with **32 seconds still on
the clock** and opposing counsel turns up **in person**, and you are both shown
into a conference room for thirty seconds.

He throws binders. The round inverts everything before it: up to here you have
been closing on paper that runs away, and now paper is coming at you and the
stamp does not solve it. Swinging at *him* does nothing at all — that is the
joke, and the reason the round exists.

What the stamp does do is **swat a binder out of the air**, and that counts as
surviving it. But never twice running: a deflection disarms it until some
binder resolves by dodge or hit, so you cannot stand still and swing on a
metronome. It is a get-out for the one you read too late.

Scored on what you survive, in tiers, because a clock makes an endurance test
where a fixed pile makes a checklist. He throws 15 to 18 in the thirty seconds:

| Survived | |
|---|---|
| 13+ | **Motion denied · Lawyer of the Year** |
| 8–12 | **Motion denied · Super Lawyer** |
| 4–7 | the verdict on the binder stands |
| 0–3 | **In re Rexington · disbarment** |

Disbarment outranks the won case deliberately. Every other outcome leaves the
verdict standing; standing still while a man throws thirty seconds of discovery
at you does not, and the binder being immaculate is the joke rather than a
defence.

Aim is locked when he starts the **wind-up**, not when the binder leaves his
hand — that is what makes the animation a tell you can read, and gives you
0.40 s at 3.1 m/s to be somewhere else.

`enemy_counsel.glb` and `conference_room.glb` are fetched **on qualification,
not at boot** — most players never see either, and nobody should pay for a
lawyer and a room to find out they were too slow. If they fail to load the case
is awarded rather than leaving the player in an empty round.

### The verdict

Nine endings. You do not win or lose so much as get a ruling, graded on how much
of the binder is in order. A full binder takes the case; three of four draws an adverse
inference on the exhibit you never authenticated; below that the court starts
directing verdicts and entering judgment. Filing three used to be
indistinguishable from filing none, which made partial competence invisible.

Three endings beat the table outright, because what you did is a better story
than how many exhibits you filed: black out three documents nobody asked you to
and you get sanctioned; miss eight swings while filing almost nothing and
facilities would like a word about the numbered carpet; go the whole ninety
seconds without swinging at all and no appearance is entered. None of them
outrank Lawyer of the Year — that one is earned, the others are self-inflicted.

Redacting the privileged memo, or Bates-stamping it unredacted and waiving
privilege, adds a line to whichever ending you get.

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
| Assets actually fetched | 4.83 MB (viewmodel, seven enemies, eight kit pieces) |
| Music bed | 381 KB fetched — one of the two encodings, never both |

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

## Sound

Effects are synthesized on a WebAudio graph at play time — swing, stamp, the
riffle of a document filing itself, the wake clock, and a sting per ending.
There are no effect samples to ship.

Anything out in the room is placed rather than played flat: a gain by distance,
squared and cut off at 11 m — just inside the longest sightline the layout can
produce, so what you hear is something you could have seen had you turned — and
a stereo pan from the dot product with your right-hand vector. Not a
`PannerNode`: with up to eight sources the useful part is which side and how
far, not a modelled head. Measured, a source dead abeam pans to ±1.00, and one
at 2 m and 9 m gains 0.68 and 0.03 against a formula predicting 0.669 and
0.033.

Footfalls come off the bake, not off a number picked by ear. `stride` in
`VARIANTS` and `OBJECTIONS` is each Run clip's length in frames at 30 fps, a
stride is two steps, and when a document is only milling about — clip played at
0.55 speed — its footsteps stretch by the same 0.55. The binder plods and the
stack scurries for the same reason they look that way. Objections also mutter
inside 4 m: they arrive from behind, and before this the first you knew of one
was an exhibit leaving the binder.

The music bed is a file, `audio/calm_loop.*`, 31.2 s stereo. It ships twice
because no single encoding covers every browser: Opus-in-Ogg (381 KB) and
AAC-in-M4A (521 KB). The page asks `canPlayType` which it prefers and fetches
only that one, falling back to the other if the decode throws — Chromium builds
without the proprietary codecs cannot read AAC, and Safari only grew Opus
support recently.

It is not looped with `source.loop`. The track is level across the wrap but does
not butt-join at sample level, so plain looping steps 0.178 across the seam
every 31.2 s; consecutive passes are equal-power crossfaded instead, which
measures 0.019 at the join for about a decibel of level through the overlap.

Props are solid. Their footprints are measured off the placed geometry at boot
with a `Box3` and inset by `playerRadius`, the same inset the walkable
rectangles already carry, so collision cannot drift from the model the way a
copied table would. The tightest gap left is 0.65 m of centre-line past the
banker's boxes; boot flood-checks that every spawn and every pod is still
reachable and warns if a layout edit walls one in.

## Known limits of this slice

- No score persistence.
- The bed is one 31.2 s loop with no variation and no reaction to the clock
  running down.
- Nothing can damage *you* — objections cost you exhibits, not health, so there
  is no reason to retreat from anything except to buy time.
- One layout, eight documents, no waves and no difficulty curve beyond the
  objections arriving. A fast player can still close the binder before the first
  one spawns at 22 s — that now earns the bonus round rather than skipping
  content, but it does mean the objections themselves can go unmet.
- Counsel throws one binder at a time on a cadence, and paces while he does it.
  That is his whole repertoire — no feints, no volleys, no reading of which way
  you dodged last time. Thirty seconds is short enough that it does not wear
  out, but it is a rhythm rather than a pattern to learn.
- Objections path by hunting and wall-sliding like the exhibits, so they grind
  corners the same way.
- Enemies path by fleeing and wall-sliding, not by navmesh — they can get
  briefly stuck grinding a corner before they turn out of it.
- One of each variant spawns, and that is the whole roster — there is no wave
  system, respawn, or difficulty curve.
- Collision is rectangles — the walkable set minus the prop boxes — not the wall
  meshes, so it is correct at the corridor scale and square at the millimetre.
