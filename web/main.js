// Tom Rexington, Esq.: Bates & Destroy -- playable prototype.
//
// Everything it renders comes from the GLBs in ../build: the FPV viewmodel with
// its Stamp_Swing clip, the paper enemy with Run and Stamped, and the modular
// office kit. Nothing is modelled here.
//
// Serve the REPO ROOT (not this folder) so ../build resolves -- see web/README.

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const ASSETS = '../build';

// ---------------------------------------------------------------- tuning
const CFG = {
  eyeHeight: 1.65,
  walk: 3.1,
  sprint: 5.0,
  accel: 14,
  friction: 11,
  playerRadius: 0.34,
  // Arrow-key turning, radians a second. The arrows are a TURN, not a strafe --
  // see the note on updatePlayer. 2.6 is a little over a quarter-turn a second,
  // fast enough to take a corner without a mouse and slow enough to aim with.
  turnSpeed: 2.6,
  snapTurn: 0.22,         // seconds for the face-nearest key to swing round

  // Stamp_Swing is 23 frames at 30fps; the die is planted on frames 11-13.
  swingDuration: 23 / 30,
  swingImpact: 11 / 30,
  // you can swing again shortly after the die lands, not after the whole clip
  swingRefire: 0.54,
  // The strike is a sphere centred ahead of the player rather than a cone
  // from the eye: a cone degenerates at point-blank range, where the angle to
  // something you are standing on top of is meaningless.
  strikeAhead: 1.05,      // metres in front of the eye
  strikeRadius: 1.05,     // metres
  enemyRadius: 0.26,

  enemySpeed: 2.45,       // the pleading paper; the rest scale off it
  enemyFlee: 7.0,         // starts running when the player is this close
  enemyTurn: 3.2,

  // A stamped document is not dead, it is FILED. Bates numbering is how
  // exhibits get indexed for trial, so the stamp is what makes a document
  // collectible -- it lies flat for the length of the Stamped clip, then
  // files itself into the binder you are carrying.
  fileDelay: 0.90,        // Stamped runs 0.833 s; let it land first
  fileTime: 0.55,         // then the flight into the binder

  // You do not get to stay asleep forever. The dream is the clock: run it out
  // and you wake with whatever binder you managed to assemble, and the verdict
  // is scaled to it.
  dreamTime: 120,
  dreamPanic: 20,         // the countdown goes orange under this

  // Falling asleep at the desk is where the dream comes from, so that is where
  // play starts: the head comes up off the desk before the clock does anything.
  // 2.4 s is long enough for two blinks to land and short enough that nobody
  // waits through it twice -- and it is skippable on any input anyway.
  wakeTime: 2.4,
  wakeDeskZ: 0.35,        // clear of the pod at z 0.9; see startWake

  // Ink is what makes a miss cost something. Without it the swing was free, so
  // there was no reason to aim, no reason to close distance, and nothing the
  // clock could actually pressure. The chain is: miss -> burn ink -> detour to
  // a pod -> lose seconds -> worse verdict.
  //
  // Capacity is 7 swings and the roster is 4 documents, so a full stamp allows
  // three misses. That is deliberately tight rather than generous: the pods are
  // off the corridor spine, so running dry is meant to be a real detour and not
  // a formality.
  inkMax: 100,
  inkPerSwing: 14,        // 7 swings on a full stamp
  inkLow: 28,             // 2 swings left: the gauge goes orange
  podRefill: 45,          // a pod is worth ~3 swings
  podRadius: 0.95,        // metres, walk-over pickup
  podRespawn: 12.0,       // seconds before a taken pod comes back
  // Pods hover instead of sitting on the floor. At the far end of a 12 m
  // corridor a floor-level pickup is a few pixels tall, low in the frame and
  // silhouetted against carpet of nearly the same value; lifting it puts it
  // near the eye line and against the wall, which is worth more than making
  // the model bigger.
  podFloat: 0.62,

  // Objections. The first is late enough that the player has learned to stamp
  // and has something in the binder to lose; after that they keep coming, so
  // there is no point in the round where the total is safe.
  objFirst: 22,           // seconds into the round
  objEvery: 15,           // and roughly every this often after
  objJitter: 4,           // +/- so the rhythm is not metronomic
  objMax: 3,              // at once -- more than this and the corridor jams
  // How close it gets before it strikes. This and the speeds below set the only
  // thing that makes objections fair: the standoff band between the range you
  // can stamp one at and the range at which it takes an exhibit.
  //
  // An objection is stampable out to strikeAhead + strikeRadius + its radius,
  // measured ~2.4 m; the band is that minus objReach. At the first speeds tried
  // (reach 1.15, hearsay 1.55 m/s, 403 2.35 m/s) the band was 1.25 m, which is
  // 0.8 s of window for hearsay and 0.53 s for 403 -- less than the swing's own
  // 0.37 s wind-up plus any human reaction, so 403 was effectively unstoppable
  // head-on. Widened to ~1.4 m and slowed, which gives 1.0 s and 0.7 s.
  //
  // All three stay well under the 3.1 m/s walk, deliberately: you must always be
  // able to break off and deal with one later.
  objReach: 1.00,
  objSpawnMin: 7.0,       // never spawn one closer to the player than this

  // How long a complete binder has to survive before the case is closed.
  //
  // Without this the round ended the instant the fourth exhibit landed, which
  // quietly cancelled the whole point of objections: they could pressure the
  // middle of a round but never touch a finished binder, so the endgame was
  // "reach four and you are safe" and the last objection on the floor was
  // irrelevant. Now the binder has to be HELD. An objection that lands during
  // the hold takes an exhibit back out and the round carries on.
  closeHold: 3.0,
  inkPerRedact: 8,        // cheaper than a stamp; you are only drawing bars

  // ---- the bonus round, and the reason to be fast
  //
  // Closing the binder early used to buy nothing: the round simply ended, so a
  // player who beat the clock by a minute got the same screen as one who
  // scraped it. Beat it by BONUS_AT and opposing counsel files a motion for
  // summary judgment instead -- a bonus round you can only lose the bonus in,
  // never the case you already won.
  bonusAt: 32,            // seconds that must still be on the clock
  // Thirty seconds, and what matters is how many you survive in them rather
  // than working through a fixed pile. A count makes the round a checklist you
  // finish; a clock makes it an endurance test you score on, which is what
  // gives it tiers worth replaying for.
  bonusTime: 30,
  // The boss does not die to one stamp; it has pages, and a Bates stamp is
  // exactly the tool for that. This is the only health bar in the game and it
  // is really a page count.
  // Opposing counsel does not walk at you and cannot be stamped -- the bonus
  // is the one part of this game that is not about the stamp at all. He throws
  // binders down the corridor and the whole round is whether you get out of
  // the way, so the numbers below are all about the dodge window.
  // No throw limit any more -- he keeps going until the clock does.
  bossRange: 7.2,         // how far down the corridor he sets up
  bossPace: 1.75,         // m/s he walks the far wall between throws
  bossWindup: 0.40,       // release lands on frame 12 of a 30-frame Throw
  bossCycle: 1.05,        // seconds between throws, tightened as it goes
  bossCycleMin: 0.45,     // by the end there are two in the air at once
  binderSpeed: 7.4,       // m/s -- about a second of flight at his range
  // These two add up to the width of the kill zone, and the first pass had
  // them at 0.42 + 0.40 = 0.82 m of RADIUS -- a 1.64 m corridor of death from
  // a binder 0.30 m across. A test that teleported the player a metre and a
  // half sideways still took all eight, which is not a dodge, it is a cutscene.
  //
  // These two total the hit radius, and the corridor sets what it can be: the
  // walkable strip is 1.72 m, so a full sidestep from the centreline is only
  // 0.86 m. At 0.56 m total that left 0.30 m of margin, which is a dodge you
  // win or lose on a rounding error. 0.48 leaves 0.38 m and still requires
  // committing to a direction.
  // A thumb on a virtual stick cannot commit to a direction as sharply as a
  // finger on a key, so the touch build gets a smaller collision. The tiers
  // then mean very slightly different things on a phone, which is the honest
  // cost of the round being playable there at all.
  binderRadiusTouch: 0.18,
  binderRadius: 0.24,     // about the real half-width of the thing
  binderSpin: 9.0,        // rad/s, end over end
  binderLead: 0.20,       // he leads your movement, but not perfectly
  playerRadius2: 0.34,    // shoulders

  // ---- deflection
  //
  // The stamp is not useless in here after all: swing at a binder in your face
  // and you knock it out of the air. But never twice running -- after a
  // deflection the next one has to be dodged, which stops the round collapsing
  // into standing still and swinging on a metronome. It is a get-out for the
  // one you read too late, not a strategy.
  deflectRange: 2.30,     // how far ahead of the eye a swing can reach one
  deflectRangeTouch: 2.75,
  deflectSpeed: 5.0,      // m/s it leaves at, back the way it came
  // Tiers, on binders survived -- dodged or deflected, both count as not
  // having been hit by a binder.
  // Measured against what he actually throws rather than picked: the first
  // cadence produced 14 binders in the 30 s, which made a 16-survived plaque
  // arithmetically impossible. At 1.05 -> 0.45 s he throws 15 to 18, so the
  // plaque asks for nearly all of them and Super Lawyer for about half.
  tierLawyer: 13,
  tierSuper: 8,
  tierDisbarred: 3,       // this many or fewer and the round is a disaster
  bossObjEvery: 8.0,      // he calls objections in his own defence
  // What one costs if it lands in there. Seconds, not exhibits: see sustain().
  objBonusCost: 4.0,
  bossKnockback: 0.55,    // metres a stamp drives it back, so hits read

  // How far a footstep carries. The longest sightline the layout can produce is
  // about 12 m, so this is deliberately just inside it: something you can hear
  // is something you could have seen if you had turned round.
  hearRadius: 11.0,
  objNearAt: 4.0,         // an objection this close mutters as well as walks
};

// The four variants, tuned from what build_enemies.py actually baked rather
// than invented here. Ground speed tracks cadence x stride, so the feet keep
// pace with the clip instead of skating: the binder lumbers at half the
// pleading paper's speed because its stride is both shorter and slower, and
// the stack outruns you because its is neither.
//
// `weave` is the privilege paper's long evasive side-step. It cannot be baked
// into a one-stride loop -- half a cycle does not close -- so it lives here,
// on the heading, where it also does something the clip never could: make it
// genuinely harder to hit.
// `stride` is the variant's Run clip length in frames, straight off the bake at
// 30 fps, and it is here so the footsteps land with the feet: a stride is two
// footfalls, so one every stride/60 seconds. Taking it from the clip rather
// than picking an interval by ear means the binder's plod and the stack's
// scurry come out of the same numbers that made them look that way.
const VARIANTS = {
  pleading:  { speed: 1.00, flee: 1.00, turn: 1.00, radius: 1.00, stride: 21 },
  privilege: { speed: 0.92, flee: 1.30, turn: 1.25, radius: 0.97, stride: 19,
               weave: { rate: 2.3, amp: 0.85 } },
  binder:    { speed: 0.49, flee: 0.80, turn: 0.55, radius: 1.16, stride: 31 },
  stack:     { speed: 1.36, flee: 1.15, turn: 1.35, radius: 1.04, stride: 17 },
};

// Two of each, so every silhouette is on the floor to be told apart and there
// is something in reach wherever you are standing.
//
// Eight rather than four because the ring is twice the floor area the U was:
// four documents in that much corridor is not a chase, it is a search -- and
// "I can't tell what I'm doing" was the report that produced this whole pass.
// Doubling the map and the population together keeps the density where it was.
//
// Interleaved rather than grouped, because spawns are handed out in list order
// and two of a kind adjacent puts identical silhouettes side by side.
const ROSTER = ['pleading', 'privilege', 'binder', 'stack',
                'stack', 'binder', 'privilege', 'pleading'];

// Objections are the other half of the game and they invert it. An exhibit runs
// away and you want to catch it; an objection comes at you and you want it gone.
// Reaching you does not hurt you -- there is no health here -- it STRIKES an
// exhibit back out of the binder, which is worse, because it is the only thing
// in the game that can take a number off the board.
//
// That is what makes the clock work as a structure without needing waves: the
// score is no longer monotonic, so the 90 seconds is a total you are defending
// rather than a counter you are filling.
//
// `strikes` is how many exhibits go if it lands. `after` gates the spawn on the
// binder having something in it worth striking -- character evidence is not
// relevant until you have put character at issue, and an objection that lands
// on an empty binder is a threat that cost the player nothing.
const OBJECTIONS = {
  hearsay:   { label: 'Hearsay', speed: 1.35, turn: 2.4, radius: 0.30,
               strikes: 1, after: 1, weight: 3, stride: 25 },
  character: { label: 'Character evidence', speed: 1.70, turn: 3.4,
               radius: 0.29, strikes: 1, after: 2, weight: 2, stride: 20,
               weave: { rate: 1.9, amp: 0.55 } },
  rule403:   { label: 'Rule 403', speed: 2.00, turn: 2.0, radius: 0.34,
               strikes: 2, after: 3, weight: 1, stride: 18 },
};

// All four come out of one GLB. The per-variant files are the art deliverable
// and still ship, but four self-contained files cannot share a texture: the
// page, face and Bates maps were 1.12 MB of duplicated pixels across them.
// Inside the combined file each variant is the subtree `Enemy_<kind>`, its
// nodes prefixed `<kind>_` so three.js binds each clip to its own enemy, and
// its clips are named `<kind>_Run` / `<kind>_Stamped`.
const ENEMIES_GLB = `${ASSETS}/enemies/enemies.glb`;

// The office is assembled from 4 m modules. Each corridor rectangle below is
// walkable floor; the player is clamped to their union, which is far more
// robust for a prototype than colliding against wall meshes.
// The corner piece has a fixed handedness: you enter through its -Z face and
// leave through its +X face. Rotation cannot turn a left turn into a right
// one, so the loop below is laid out to suit the piece rather than the other
// way round. Rotations are multiples of 90 degrees, which keeps every walkable
// rectangle exactly axis-aligned.
const MODULE = 4.0;
const HALF = 1.2 - CFG.playerRadius;      // clear half-width for the player
const LAYOUT = {
  // A closed ring, not a U. The U had two dead ends, each capped by a doorway
  // whose leaf is modelled standing 62 degrees open -- so the art said "walk
  // through" and the collision said "wall", which is exactly what it got
  // reported as. Closing the loop deletes both dead ends rather than closing
  // both doors: you can always keep walking, and you can never be cornered,
  // which was the other half of the same complaint.
  halls: [
    // the x = 0 leg -- the z = -4 module is a doorHall, below
    { x: 0, z: 0, rot: 0 }, { x: 0, z: -8, rot: 0 },
    // the z = -12 leg, across the bottom
    { x: -4, z: -12, rot: Math.PI / 2 }, { x: -8, z: -12, rot: Math.PI / 2 },
    // the x = -12 leg, back up
    { x: -12, z: -8, rot: 0 }, { x: -12, z: 0, rot: 0 },
    // and the z = +4 leg that closes it
    { x: -4, z: 4, rot: Math.PI / 2 }, { x: -8, z: 4, rot: Math.PI / 2 },
  ],
  // A corner joins a leg running out along local +X to one running out along
  // local -Z. Which pair that lands on in world space is all `rot` decides:
  // rot   0  -> +X and -Z          rot  90 -> -X and -Z
  // rot 180  -> -X and +Z          rot -90 -> +X and +Z
  corners: [
    { x: 0, z: -12, rot: Math.PI },
    { x: -12, z: -12, rot: -Math.PI / 2 },
    { x: 0, z: 4, rot: Math.PI / 2 },
    { x: -12, z: 4, rot: 0 },
  ],
  props: [
    { kind: 'file_cabinet', x: 5.4, z: -5.2, rot: -Math.PI / 2 },
    { kind: 'banker_boxes', x: 5.2, z: -2.9, rot: 0.4 },
    { kind: 'file_cabinet', x: -17.5, z: -5.2, rot: Math.PI / 2 },
    { kind: 'banker_boxes', x: -17.3, z: -2.9, rot: 0.4 },
    { kind: 'banker_boxes', x: -0.85, z: -7.4, rot: 0.24 },
    { kind: 'desk_chair', x: -6.2, z: -13.2, rot: Math.PI },
    { kind: 'reception_counter', x: -10.9, z: -5.6, rot: Math.PI / 2 },
    { kind: 'banker_boxes', x: -9.6, z: -10.9, rot: -0.5 },
    { kind: 'file_cabinet', x: -12.9, z: -2.0, rot: Math.PI / 2 },
  ],
  // Nothing to cap any more -- the ring has no dead ends. The `doorway` module
  // is still built and still validated; it is simply not what a room is
  // entered through. That is `hallway_door`: a corridor section with an
  // opening in its SIDE, rather than a wall laid across the corridor.
  doors: [],

  // Straight sections whose +X wall carries an opening. Same footprint as a
  // plain hall, so they sit on the grid in place of one.
  doorHalls: [
    { x: 0, z: -4, rot: 0 },              // opening faces +X, into room A
    { x: -12, z: -4, rot: Math.PI },      // flipped, so it faces -X
  ],

  // Rooms hanging off those openings. `x, z` is the middle of the doorway on
  // the outer face of the corridor wall -- the hall centre plus
  // (CORRIDOR + WALL_T) / 2 + WALL_T / 2 = 1.35 -- and the room runs out along
  // its local +X from there. Both sit OUTSIDE the ring: the middle of the ring
  // is solid, and a room there would have to cut through two legs to fit.
  rooms: [
    { x: 1.35, z: -4, rot: 0, w: 5.0, d: 4.0 },
    { x: -13.35, z: -4, rot: Math.PI, w: 5.0, d: 4.0 },
  ],
  // Every one of these must satisfy insideWalk, which boot() now asserts.
  // `[-1.0, -10.5]` did not: x was outside the corridor's +/-0.86 half-width
  // and z past the end of the last straight hall, so it sat in the wall. With
  // documents indexing `spawns[i % n]`, a short list meant every round reused
  // stack spawned out of bounds every single round -- free to be walked to,
  // but resolveMove will not let anything outside the set move except by luck
  // of heading, so it could stand there indefinitely.
  // One per document, spread right round the ring and into both rooms, so
  // nothing spawns on top of anything else and no leg of the loop is empty.
  // Two sit inside the side offices: a room is somewhere you have to go rather
  // than somewhere you may glance into.
  spawns: [
    [3.6, -4], [-15.8, -4],          // the two side offices
    [0, -6], [0, -10],               // the x = 0 leg
    [-5.5, -12], [-9.5, -12],        // across the bottom
    [-12, -6], [-6.5, 4],            // the far leg, and the top
  ],
  // Ink pods, pushed out to the far ends and the two corners rather than sat
  // along the route you would walk anyway. A pod you pass over for free is not
  // a decision; these cost you the length of a corridor.
  pods: [
    [0.55, -10.6],       // near the first corner
    [-11.4, -11.2],      // the far corner
    [0.0, 0.9],          // back where you woke up
    [-9.0, 4.0],         // the top leg, furthest from everything
    // One in each side office. Eight documents need more ink than four did,
    // and a refill is a second reason to walk into a room you might otherwise
    // clear from the doorway.
    [3.0, -2.9],
    [-15.0, -2.9]
  ],
};

/** AABB of a local rectangle placed at (cx, cz) under a 90-degree rotation. */
function rect(cx, cz, rot, lx0, lz0, lx1, lz1) {
  const c = Math.round(Math.cos(rot)), s = Math.round(Math.sin(rot));
  const xs = [], zs = [];
  for (const [lx, lz] of [[lx0, lz0], [lx1, lz0], [lx1, lz1], [lx0, lz1]]) {
    xs.push(cx + lx * c + lz * s);
    zs.push(cz - lx * s + lz * c);
  }
  return { x0: Math.min(...xs), x1: Math.max(...xs),
           z0: Math.min(...zs), z1: Math.max(...zs) };
}

const WALK = [];
for (const h of LAYOUT.halls) {
  WALK.push(rect(h.x, h.z, h.rot, -HALF, -MODULE / 2, HALF, MODULE / 2));
}
for (const c of LAYOUT.corners) {
  // entry leg runs down local -Z; exit leg runs out along local +X
  WALK.push(rect(c.x, c.z, c.rot, -HALF, -MODULE / 2, HALF, HALF));
  WALK.push(rect(c.x, c.z, c.rot, -HALF, -HALF, MODULE / 2, HALF));
}
// A doorHall walks exactly like the straight section it replaces.
for (const h of LAYOUT.doorHalls) {
  WALK.push(rect(h.x, h.z, h.rot, -HALF, -MODULE / 2, HALF, MODULE / 2));
}
// Rooms are two rects each: the threshold through the wall, and the floor.
//
// The threshold has to OVERLAP the corridor rather than abut it. Rects that
// merely touch leave resolveMove with no cell to step into, and the opening
// becomes a wall you can see through -- which is the same defect this layout
// exists to stop shipping.
const DOOR_HALF = 0.95 / 2;              // DOOR_W, from build_environment.py
for (const r of LAYOUT.rooms) {
  const slot = DOOR_HALF - CFG.playerRadius;
  WALK.push(rect(r.x, r.z, r.rot, -0.65, -slot, 0.40, slot));
  const inset = 0.15 + CFG.playerRadius;
  WALK.push(rect(r.x, r.z, r.rot, 0.40, -(r.d / 2 - inset),
                 r.w - inset, r.d / 2 - inset));
}

// Props used to be scenery you walked through: a filing cabinet was a picture
// of a filing cabinet. Their footprints are measured off the placed geometry in
// boot() rather than written down here, so the collision cannot drift from the
// model the way a hand-copied table would.
//
// Everything in WALK is already inset by playerRadius, so these are inset the
// same way and the whole set stays a test on the player's centre.
const BLOCKERS = [];

/**
 * Inside the walls, furniture ignored.
 *
 * The distinction matters: insideWalk answers "can a person stand here", which
 * has to refuse desks and tables. This answers "is this still in the room",
 * which is what anything airborne needs.
 */
function insideBounds(x, z) {
  for (const r of WALK) {
    if (x >= r.x0 && x <= r.x1 && z >= r.z0 && z <= r.z1) return true;
  }
  return false;
}

function insideWalk(x, z) {
  for (const b of BLOCKERS) {
    if (x >= b.x0 && x <= b.x1 && z >= b.z0 && z <= b.z1) return false;
  }
  for (const r of WALK) {
    if (x >= r.x0 && x <= r.x1 && z >= r.z0 && z <= r.z1) return true;
  }
  return false;
}

/** Slide along walls: try the full move, then each axis alone. */
function resolveMove(from, dx, dz) {
  if (insideWalk(from.x + dx, from.z + dz)) return { dx, dz };
  if (insideWalk(from.x + dx, from.z)) return { dx, dz: 0 };
  if (insideWalk(from.x, from.z + dz)) return { dx: 0, dz };
  return { dx: 0, dz: 0 };
}

// ---------------------------------------------------------------- setup
const app = document.getElementById('app');
// ------------------------------------------------------------------ retro
//
// What makes Wolfenstein and GoldenEye still look good is not that they had
// better art -- it is that they COMMIT. Chunky pixels, hard texel edges, a
// small palette, and every asset agreeing to the same rules. Rendered smooth
// and half-realistic, this viewmodel sits in the uncanny middle: detailed
// enough to invite the comparison with a real arm, not painted enough to win
// it. Rendered at 40% and point-sampled up, the same geometry reads as a
// deliberate style rather than as a near miss.
//
// It costs nothing -- it renders a third of the pixels -- and it is a shrunken
// drawing buffer scaled by the browser, not a post-process chain: no render
// targets, no EffectComposer, nothing to vendor.
//
// OFF by default: tried, looked at side by side, and not kept. It muddies the
// die's EXHIBITFY plate, which is the joke, and the form shading in the skin
// map turned out to be doing the work this was supposed to do. Left switchable
// rather than deleted because it is four functions and a CSS class, and the
// judgement is a taste one that may go the other way on a different screen.
const RETRO = { on: false, scale: 0.55 };

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
app.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0d0f12);
scene.fog = new THREE.Fog(0x0d0f12, 12, 34);

const camera = new THREE.PerspectiveCamera(70, innerWidth / innerHeight, 0.02, 120);

// The viewmodel is drawn by a second camera on top, so it never clips into
// walls -- the standard trick for first-person weapons.
const VIEW_FOV = 70;                     // must match the world camera
const viewCamera = new THREE.PerspectiveCamera(VIEW_FOV, innerWidth / innerHeight, 0.01, 5);
const viewScene = new THREE.Scene();

/**
 * Fit the view to the screen, including the shape of it.
 *
 * three.js `fov` is VERTICAL, so a portrait phone keeps the vertical angle and
 * throws away horizontal: the world narrows and the viewmodel -- authored for
 * a landscape frame -- ends up filling the lower half of the screen with
 * stamp. Widening the vertical fov on a tall screen gives back roughly the
 * horizontal angle a desktop has, and the arms are pushed down and out of the
 * way to match.
 */
function fitView() {
  const aspect = innerWidth / innerHeight;
  camera.aspect = viewCamera.aspect = aspect;
  // 70 deg vertical at 16:9; on a 9:19.5 phone that leaves a letterbox slot of
  // a world, so open it up as the frame gets taller.
  const widen = aspect < 1 ? Math.min(26, (1 / aspect - 1) * 22) : 0;
  camera.fov = state.baseFov = 70 + widen;
  viewCamera.fov = VIEW_FOV + widen;
  camera.updateProjectionMatrix();
  viewCamera.updateProjectionMatrix();
  applyRes();
  if (state.arms) {
    // shrink and drop the tool on a narrow screen so it frames rather than fills
    const k = aspect < 1 ? Math.max(0.62, aspect * 0.95) : 1;
    state.arms.scale.setScalar(k);
    state.arms.position.y = state.armsBaseY - (1 - k) * 0.10;
  }
  els.rotateHint.hidden = !(state.touch && aspect < 0.95);
}
/**
 * Size the drawing buffer. In retro mode it is deliberately smaller than the
 * element, and `false` stops three.js writing the CSS size back -- the canvas
 * keeps filling the screen and the browser scales the small buffer up. The
 * `image-rendering: pixelated` rule in index.html is what makes that scale a
 * hard point-sample instead of a blur, so the two have to move together.
 */
function applyRes() {
  const k = RETRO.on ? RETRO.scale : 1;
  renderer.setPixelRatio(RETRO.on ? 1 : Math.min(devicePixelRatio, 2));
  renderer.setSize(Math.round(innerWidth * k), Math.round(innerHeight * k), false);
  renderer.domElement.style.width = '100%';
  renderer.domElement.style.height = '100%';
  renderer.domElement.classList.toggle('crisp', RETRO.on);
}

/** Point-sample every texture, so texels stay square instead of smearing. */
function retroFilter(root) {
  root.traverse((o) => {
    for (const m of (o.material ? [].concat(o.material) : [])) {
      for (const key of ['map', 'emissiveMap', 'metalnessMap', 'roughnessMap',
                         'normalMap', 'aoMap']) {
        const t = m[key];
        if (!t) continue;
        // Nearest on magnification is the look. Minification keeps its
        // mipmaps: nearest there is authentically 1992 and authentically
        // nauseating, a shimmering mess on every wall down a 12 m corridor.
        t.magFilter = RETRO.on ? THREE.NearestFilter : THREE.LinearFilter;
        t.needsUpdate = true;
      }
    }
  });
}

function setRetro(on) {
  RETRO.on = !!on;
  applyRes();
  retroFilter(scene);
  retroFilter(viewScene);
  warn(RETRO.on ? 'Retro on' : 'Retro off');
}

addEventListener('resize', fitView);
addEventListener('orientationchange', () => setTimeout(fitView, 120));
// NB: `state` is declared further down, so nothing here may touch it at module
// scope -- an assignment like `state.fitView = fitView` right here throws on
// the temporal dead zone and takes the whole game down before it boots. It is
// exposed with the other console hooks instead.

// Metals need something to reflect. Without an environment map every metallic
// surface in the kit -- the watch, the stamp's steel, the cabinet -- renders
// black. RoomEnvironment is a cheap generated probe, built once.
const pmrem = new THREE.PMREMGenerator(renderer);
const envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
scene.environment = envRT.texture;
pmrem.dispose();

// ---- lighting: cool ambient + a warm overhead, matching the troffers
scene.add(new THREE.HemisphereLight(0xaebccd, 0x2a2622, 0.85));
const key = new THREE.DirectionalLight(0xfff3e0, 1.25);
key.position.set(3, 9, 2);
scene.add(key);
viewScene.environment = envRT.texture;
viewScene.add(new THREE.HemisphereLight(0xaebccd, 0x2a2622, 0.8));
const vkey = new THREE.DirectionalLight(0xfff3e0, 1.5);
vkey.position.set(-0.4, 1.0, 0.8);
viewScene.add(vkey);

const controls = new PointerLockControls(camera, renderer.domElement);
camera.position.set(0, CFG.eyeHeight, 1.2);

// ---------------------------------------------------------------- loading
const loader = new GLTFLoader();
const load = (path) => new Promise((res, rej) => loader.load(path, res, undefined, rej));

const els = {
  overlay: document.getElementById('overlay'),
  loading: document.getElementById('loading'),
  go: document.getElementById('go'),
  hud: document.getElementById('hud'),
  reticle: document.getElementById('reticle'),
  score: document.getElementById('score'),
  scoreLabel: document.getElementById('score-label'),
  remaining: document.getElementById('remaining'),
  warn: document.getElementById('warn'),
  swear: document.getElementById('swear'),
  touchUi: document.getElementById('touch-ui'),
  stick: document.getElementById('stick'),
  stickNub: document.getElementById('stick-nub'),
  redactBtn: document.getElementById('redact-btn'),
  findBtn: document.getElementById('find-btn'),
  rotateHint: document.getElementById('rotate-hint'),
  intro: document.getElementById('intro'),
  introVideo: document.getElementById('intro-video'),
  introSkip: document.getElementById('intro-skip'),
  banner: document.getElementById('banner'),
  bannerTitle: document.getElementById('banner-title'),
  bannerSub: document.getElementById('banner-sub'),
  inkBox: document.getElementById('inkbox'),
  inkFill: document.getElementById('inkfill'),
  inkLabel: document.getElementById('inklabel'),
  wake: document.getElementById('wake'),
  wakeTag: document.getElementById('wake-tag'),
  wakeHead: document.getElementById('wake-head'),
  wakeBody: document.getElementById('wake-body'),
  clock: document.getElementById('clock'),
  clockLabel: document.getElementById('clock-label'),
  clockBox: document.getElementById('wakeclock'),
  markers: document.getElementById('markers'),
  lids: document.getElementById('lids'),
  lidTop: document.querySelector('#lids i.t'),
  lidBottom: document.querySelector('#lids i.b'),
};

const state = {
  ready: false, score: 0, filed: 0, done: false, t: 0, clock: CFG.dreamTime,
  swinging: false, swingT: 0, hitDone: false,
  ink: CFG.inkMax, dryStamps: 0,
  enemies: [], pods: [], objections: [],
  struck: 0, overruled: 0, sustained: 0, nextObj: CFG.objFirst,
  redactions: 0, overRedacted: 0, privilegeSaved: false, waived: false,
  misses: 0, muted: false,
  closing: 0, closeBroken: 0,
  phase: 'case',          // 'case' -> 'bonus' -> done
  boss: null, bossHits: 0, bonusWon: false, caseWon: false, timeLeft: 0,
  binders: [], binderHits: 0, lastX: 0, lastZ: 0, swearT: 0,
  deflects: 0, deflectReady: true, survived: 0, bonusTier: null, intro: false,
  keys: Object.create(null),
};

// exposed for tuning and debugging from the console
window.__bates = state;
state.CFG = CFG;                    // live-tunable: __bates.CFG.walk = 6
state.VARIANTS = VARIANTS;
state.scene = scene;
state.camera = camera;
state.viewScene = viewScene;
state.viewCamera = viewCamera;
state.THREE = THREE;

function place(obj, x, z, rot = 0) {
  obj.position.set(x, 0, z);
  obj.rotation.y = rot;
  return obj;
}

async function boot() {
  const [hallG, cornerG, doorG, doorHallG, officeG, viewG, enemyG,
         ...propGs] = await Promise.all([
    load(`${ASSETS}/environment/hallway_straight.glb`),
    load(`${ASSETS}/environment/hallway_corner.glb`),
    load(`${ASSETS}/environment/doorway.glb`),
    load(`${ASSETS}/environment/hallway_door.glb`),
    load(`${ASSETS}/environment/side_office.glb`),
    load(`${ASSETS}/exhibitfy_fpv_arms.glb`),
    load(ENEMIES_GLB),
    load(`${ASSETS}/environment/file_cabinet.glb`),
    load(`${ASSETS}/environment/banker_boxes.glb`),
    load(`${ASSETS}/environment/desk_chair.glb`),
    load(`${ASSETS}/environment/reception_counter.glb`),
    load(`${ASSETS}/environment/ink_pod.glb`),
  ]);
  const props = {
    file_cabinet: propGs[0].scene,
    banker_boxes: propGs[1].scene,
    desk_chair: propGs[2].scene,
    reception_counter: propGs[3].scene,
  };
  const podProto = propGs[4].scene;
  // The desk you wake up at is the same module the office uses, instanced once
  // more and never added to BLOCKERS -- it exists for the length of the wake
  // and is then dissolved, so it must not be part of the collision world.
  state.deskProto = props.desk_chair;

  // ---- office
  for (const h of LAYOUT.halls) scene.add(place(hallG.scene.clone(true), h.x, h.z, h.rot));
  for (const c of LAYOUT.corners) scene.add(place(cornerG.scene.clone(true), c.x, c.z, c.rot));
  for (const d of LAYOUT.doors) scene.add(place(doorG.scene.clone(true), d.x, d.z, d.rot));
  for (const h of LAYOUT.doorHalls) {
    scene.add(place(doorHallG.scene.clone(true), h.x, h.z, h.rot));
  }
  for (const r of LAYOUT.rooms) {
    scene.add(place(officeG.scene.clone(true), r.x, r.z, r.rot));
  }
  const propBox = new THREE.Box3();
  for (const p of LAYOUT.props) {
    const obj = place(props[p.kind].clone(true), p.x, p.z, p.rot);
    scene.add(obj);
    // Measured after placing, so rotation is already in it.
    obj.updateMatrixWorld(true);
    propBox.setFromObject(obj);
    BLOCKERS.push({
      kind: p.kind,
      x0: propBox.min.x - CFG.playerRadius, x1: propBox.max.x + CFG.playerRadius,
      z0: propBox.min.z - CFG.playerRadius, z1: propBox.max.z + CFG.playerRadius,
    });
  }
  // A prop dropped on a spawn or a pod would strand whatever stands there, and
  // one dropped across a corridor would cut the loop in two. Neither is true of
  // the current layout -- the tightest gap is 0.65 m of centre-line past the
  // banker's boxes -- but the layout is a table somebody will edit.
  const trapped = [];
  LAYOUT.spawns.forEach((s, i) => {
    if (!insideWalk(s[0], s[1])) trapped.push(`spawn ${i} (${s[0]}, ${s[1]})`);
  });
  LAYOUT.pods.forEach((p, i) => {
    if (!insideWalk(p[0], p[1])) trapped.push(`pod ${i} (${p[0]}, ${p[1]})`);
  });
  if (trapped.length) console.warn('layout: unreachable —', trapped.join('; '));
  state.BLOCKERS = BLOCKERS;

  // ---- viewmodel: authored in view space, so it drops straight in
  const arms = viewG.scene;
  // Clear of the crosshair, but not so low that the carrying arm is guillotined
  // by the bottom edge. The viewmodel is authored and previewed at 62 deg and
  // drawn here at 70, which crops it tighter than the previews imply; at -0.075
  // that put the left hand ~60 mm below the frame and left a disembodied wedge
  // of forearm along the bottom. At -0.055 the watch and the exhibits read and
  // the stamp handle still sits below the crosshair.
  arms.position.set(0.035, -0.055, -0.02);
  state.armsBaseY = arms.position.y;       // the impact kick dips from here
  viewScene.add(arms);
  const armMixer = new THREE.AnimationMixer(arms);
  const swingClip = THREE.AnimationClip.findByName(viewG.animations, 'Stamp_Swing')
                 || viewG.animations[0];
  const swing = armMixer.clipAction(swingClip);
  swing.setLoop(THREE.LoopOnce, 1);
  swing.clampWhenFinished = true;
  state.arms = arms;
  state.armMixer = armMixer;
  state.swing = swing;

  // ---- ink pods
  // Each is its own clone so a taken pod can hide and come back without
  // disturbing the others. The bob and spin are here rather than baked: the
  // piece is static in the kit, and a pickup wants to catch the eye.
  LAYOUT.pods.forEach(([x, z], i) => {
    const g = podProto.clone(true);
    g.position.set(x, 0, z);
    scene.add(g);
    state.pods.push({ root: g, home: new THREE.Vector3(x, 0, z),
                      beacon: g.getObjectByName('Pod_Beacon'),
                      live: true, cooldown: 0, phase: i * 1.4 });
  });

  // ---- the binder counsel throws, out of the file we already have. The
  // walking binder's BODY only: pages, rings and the face on the front, with
  // its legs left behind. A binder with legs pinwheeling at your head was
  // funnier for about four seconds and then just looked like a bug.
  const binderBody = enemyG.scene.getObjectByName('binder_Body')
                  || enemyG.scene.getObjectByName('Enemy_binder');
  if (binderBody) {
    const proto = new THREE.Group();
    const copy = binderBody.clone(true);
    copy.position.set(0, 0, 0);
    copy.rotation.set(0, 0, 0);
    copy.scale.setScalar(1);
    proto.add(copy);
    state.binderProto = proto;
  }

  // ---- objection prototypes, kept off-scene until one is called
  state.objProto = {};
  for (const kind of Object.keys(OBJECTIONS)) {
    const proto = enemyG.scene.getObjectByName(`Enemy_${kind}`);
    if (!proto) throw new Error(`Enemy_${kind} missing from ${ENEMIES_GLB}`);
    state.objProto[kind] = proto;
  }
  state.objClips = enemyG.animations;

  // ---- enemies
  ROSTER.forEach((kind, i) => {
    const v = VARIANTS[kind];
    const proto = enemyG.scene.getObjectByName(`Enemy_${kind}`);
    if (!proto) throw new Error(`Enemy_${kind} missing from ${ENEMIES_GLB}`);
    // clone the subtree, not the whole file -- child names come with it, which
    // is what lets the mixer bind this variant's clips to this instance
    const g = proto.clone(true);
    const spawn = LAYOUT.spawns[i % LAYOUT.spawns.length];
    place(g, spawn[0], spawn[1], Math.random() * Math.PI * 2);
    scene.add(g);
    const mixer = new THREE.AnimationMixer(g);
    const runClip = THREE.AnimationClip.findByName(enemyG.animations, `${kind}_Run`);
    const hitClip = THREE.AnimationClip.findByName(enemyG.animations, `${kind}_Stamped`);
    const run = mixer.clipAction(runClip);
    run.play();
    const hit = mixer.clipAction(hitClip);
    hit.setLoop(THREE.LoopOnce, 1);
    hit.clampWhenFinished = true;
    state.enemies.push({
      kind, v, root: g, mixer, run, hit, alive: true,
      heading: g.rotation.y, dead: 0, phase: i * 1.7,
      // the variants carry their own scale on the root (the binder is 1.16),
      // so the filing shrink has to be relative to it, not an absolute 1
      baseScale: g.scale.clone(), filed: false, restPos: new THREE.Vector3(),
    });
  });

  // Decode the bed while the menu is up, so the first click starts it
  // instantly. Failure here is not fatal -- loadMusic warns and leaves
  // MUSIC.buf null, and every music call no-ops on that.
  await loadMusic();

  // Point-sample everything now that every GLB is in. Textures arrive with the
  // models, so this cannot be done before the loads resolve.
  retroFilter(scene);
  retroFilter(viewScene);

  // Fit the frame now that there is a viewmodel to fit: bound to resize alone,
  // none of it applied on the orientation the page happened to load in.
  fitView();

  state.ready = true;
  els.loading.hidden = true;
  els.go.hidden = false;
  updateHud();
  updateInk();
}

boot().catch((err) => {
  els.loading.textContent =
    'Could not load assets — serve the repo root, not web/ (see web/README.md). ' + err;
});

// ---------------------------------------------------------------- audio
// Effects are synthesized on a WebAudio graph at play time -- no sound files
// for those. The music bed IS a file, in audio/, shipped as Opus-in-Ogg and
// AAC-in-M4A because no single encoding covers every browser.
//
// The context is constructed early and starts suspended, which is allowed
// without a gesture and lets the music decode during loading; the pointer-lock
// click only has to resume() it.
let AC = null, master = null;

function initAudio() {
  if (AC) { if (AC.state === 'suspended') AC.resume(); return; }
  AC = new (window.AudioContext || window.webkitAudioContext)();
  master = AC.createGain();
  master.gain.value = 0.32;
  master.connect(AC.destination);
  MUSIC.gain = AC.createGain();
  MUSIC.gain.gain.value = MUSIC.level;
  MUSIC.gain.connect(master);
}

function envGain(t0, attack, peak, decay, dest) {
  const g = AC.createGain();
  g.gain.setValueAtTime(0, t0);
  g.gain.linearRampToValueAtTime(peak, t0 + attack);
  g.gain.exponentialRampToValueAtTime(0.0008, t0 + attack + decay);
  g.connect(dest || master);
  return g;
}

function noiseBuf() {
  if (noiseBuf.b) return noiseBuf.b;
  const b = AC.createBuffer(1, AC.sampleRate, AC.sampleRate);
  const d = b.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  return (noiseBuf.b = b);
}

function playNoise(t0, dur, type, f0, f1, peak, q = 1.0, dest) {
  const src = AC.createBufferSource();
  src.buffer = noiseBuf();
  const flt = AC.createBiquadFilter();
  flt.type = type;
  flt.Q.value = q;
  flt.frequency.setValueAtTime(f0, t0);
  flt.frequency.exponentialRampToValueAtTime(Math.max(40, f1), t0 + dur);
  src.connect(flt).connect(envGain(t0, 0.008, peak, dur, dest));
  src.start(t0);
  src.stop(t0 + dur + 0.05);
}

function playTone(t0, dur, type, f0, f1, peak, dest) {
  const o = AC.createOscillator();
  o.type = type;
  o.frequency.setValueAtTime(f0, t0);
  o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t0 + dur);
  o.connect(envGain(t0, 0.004, peak, dur, dest));
  o.start(t0);
  o.stop(t0 + dur + 0.05);
}

// -------------------------------------------------- sounds that have a place
//
// Everything above plays flat into the master bus, which is right for the
// stamp in your own hands and wrong for anything out in the room. An objection
// closing on you from behind was, until now, completely silent: the first you
// knew of it was an exhibit leaving the binder.
//
// So: distance attenuation and a stereo position, which is all a corridor
// needs. A full PannerNode would model a head and a cone per source and there
// are up to eight sources; the useful part here is only "which side, how far".
const earV = new THREE.Vector3();

/** A gain/pan sink for a sound at (x, z), or null if it is out of earshot. */
function ear(x, z, spread = 1) {
  if (!AC) return null;
  const dx = x - camera.position.x;
  const dz = z - camera.position.z;
  const d = Math.hypot(dx, dz);
  if (d > CFG.hearRadius) return null;
  camera.getWorldDirection(earV);
  earV.y = 0;
  earV.normalize();
  // right-hand vector in the floor plane, so the sign is which ear it lands in
  const pan = d < 0.05 ? 0
    : Math.max(-1, Math.min(1, ((dx * -earV.z) + (dz * earV.x)) / d * spread));
  const g = AC.createGain();
  // squared falloff: linear stays audible for too long across a 12 m sightline
  const k = 1 - d / CFG.hearRadius;
  g.gain.value = k * k;
  if (AC.createStereoPanner) {
    const p = AC.createStereoPanner();
    p.pan.value = pan;
    g.connect(p).connect(master);
  } else {
    g.connect(master);                  // Safari < 14.1: mono, still audible
  }
  return g;
}

const sfx = {
  swing() {                                  // air, pitched down as it travels
    if (!AC) return;
    playNoise(AC.currentTime, 0.16, 'bandpass', 900, 260, 0.5, 0.8);
  },
  stamp(hit) {
    if (!AC) return;
    const t = AC.currentTime;
    playTone(t, 0.11, 'sine', 120, 42, 0.9);           // the floor takes it
    playNoise(t, 0.05, 'lowpass', 3200, 700, 0.55);    // die click
    if (hit) playNoise(t + 0.02, 0.14, 'highpass', 1200, 2600, 0.4); // paper slap
  },
  file() {                                   // riffle up, land in the binder
    if (!AC) return;
    const t = AC.currentTime;
    playNoise(t, 0.22, 'bandpass', 500, 2400, 0.3, 1.4);
    playTone(t + 0.20, 0.09, 'triangle', 660, 660, 0.25);
  },
  redact() {                                 // a marker dragged across a page
    if (!AC) return;
    playNoise(AC.currentTime, 0.19, 'lowpass', 1500, 380, 0.34, 0.7);
  },
  dry() {                                    // the stamp lands on nothing
    if (!AC) return;
    playNoise(AC.currentTime, 0.07, 'highpass', 2200, 3400, 0.22);
  },
  ink() {                                    // pod picked up: a rising pair
    if (!AC) return;
    const t = AC.currentTime;
    playTone(t, 0.10, 'triangle', 440, 660, 0.30);
    playTone(t + 0.09, 0.16, 'triangle', 880, 880, 0.22);
  },
  tick() {
    if (!AC) return;
    playTone(AC.currentTime, 0.03, 'square', 1900, 1500, 0.06);
  },
  objection() {                              // one is on the floor: a rasp
    if (!AC) return;
    const t = AC.currentTime;
    playNoise(t, 0.20, 'bandpass', 260, 150, 0.45, 2.2);
    playTone(t, 0.26, 'sawtooth', 196, 155, 0.20);
  },
  sustained() {                              // it landed: a gavel, downward
    if (!AC) return;
    const t = AC.currentTime;
    playTone(t, 0.16, 'sine', 150, 52, 1.0);
    playNoise(t, 0.09, 'lowpass', 1400, 260, 0.6);
    playTone(t + 0.13, 0.30, 'sawtooth', 138, 110, 0.22);
  },
  overruled() {                              // you got it: bright, upward
    if (!AC) return;
    const t = AC.currentTime;
    playNoise(t, 0.06, 'highpass', 1800, 3000, 0.35);
    playTone(t, 0.12, 'triangle', 587.33, 880, 0.28);
  },
  // ---- out in the room, rather than in your hands
  step(x, z) {                               // an exhibit's paper footfall
    const at = ear(x, z);
    if (!at) return;
    const t = AC.currentTime;
    const f = 1500 + Math.random() * 900;    // never twice the same
    playNoise(t, 0.055, 'bandpass', f, f * 0.45, 0.30, 1.6, at);
  },
  objStep(x, z) {                            // heavier, and it is coming to you
    const at = ear(x, z);
    if (!at) return;
    const t = AC.currentTime;
    playNoise(t, 0.075, 'bandpass', 420 + Math.random() * 160, 190, 0.42, 1.9, at);
    playTone(t, 0.05, 'sine', 110, 78, 0.16, at);
  },
  objNear(x, z) {                            // close enough to do something
    const at = ear(x, z);
    if (!at) return;
    const t = AC.currentTime;
    playTone(t, 0.30, 'sawtooth', 165, 138, 0.14, at);
    playNoise(t, 0.18, 'bandpass', 300, 200, 0.20, 2.4, at);
  },
  bossStep(x, z) {                           // 2 m of paper, and it lands
    const at = ear(x, z);
    if (!at) return;
    const t = AC.currentTime;
    playTone(t, 0.18, 'sine', 78, 44, 0.85, at);
    playNoise(t, 0.10, 'lowpass', 900, 240, 0.40, 0.8, at);
  },
  // ---- the bonus round
  windup(x, z) {                             // cloth and effort, up the corridor
    const at = ear(x, z);
    if (!at) return;
    const t = AC.currentTime;
    playNoise(t, 0.26, 'bandpass', 260, 620, 0.34, 1.2, at);
  },
  throwRelease(x, z) {                       // the grunt and the let-go
    const at = ear(x, z);
    if (!at) return;
    const t = AC.currentTime;
    playTone(t, 0.13, 'sawtooth', 190, 120, 0.24, at);
    playNoise(t + 0.04, 0.14, 'highpass', 900, 2000, 0.30, 1.0, at);
  },
  deflect() {                                // stamp meets binder board
    if (!AC) return;
    const t = AC.currentTime;
    playTone(t, 0.09, 'square', 420, 180, 0.55);
    playNoise(t, 0.13, 'bandpass', 2400, 700, 0.50, 1.4);
    playTone(t + 0.03, 0.20, 'triangle', 784, 988, 0.22);
  },
  whoosh() {                                 // it went past your ear
    if (!AC) return;
    const t = AC.currentTime;
    playNoise(t, 0.20, 'bandpass', 1600, 320, 0.34, 0.9);
  },
  ouch() {                                   // it did not go past your ear
    if (!AC) return;
    const t = AC.currentTime;
    // a thud on you, then the man himself: a short pained vowel, formant-ish
    playTone(t, 0.14, 'sine', 130, 60, 0.85);
    playNoise(t, 0.08, 'lowpass', 800, 200, 0.55);
    playTone(t + 0.05, 0.26, 'sawtooth', 232, 176, 0.30);
    playTone(t + 0.05, 0.24, 'sawtooth', 349, 262, 0.14);
  },
  sting(win) {
    if (!AC) return;
    const t = AC.currentTime;
    const seq = win ? [523.25, 659.25, 784.0] : [392.0, 311.13, 261.63];
    seq.forEach((f, i) => playTone(t + i * 0.16, 0.30, 'triangle', f, f, 0.22));
  },
};

// ------------------------------------------------------------ music bed
// The track is level across the wrap -- head and tail RMS agree to within 2%
// over 0.9 s -- but it does not butt-join at sample level: the last sample
// sits at +0.334 and the first at +0.220, so source.loop = true steps 0.178
// across the join, every 31.2 s, forever.
//
// So each pass is its own source and consecutive passes are equal-power
// crossfaded over the join. Rendered offline and measured, that takes the
// worst sample-to-sample jump at the join from 0.178 down to 0.019, and costs
// 0.9 to 1.4 dB of level through the 0.9 s overlap -- around the threshold of
// audibility, against a step that is not. The overlap also shortens the loop
// period to d - xfade and plays that much material twice, neither of which
// reads on an ambient bed.
const MUSIC = {
  gain: null, buf: null, nextAt: 0, on: false,
  level: 0.5,             // sits under the effects, which peak near 0.9
  xfade: 0.9,
};

const FADE_N = 64;
const FADE_IN = new Float32Array(FADE_N);
const FADE_OUT = new Float32Array(FADE_N);
for (let i = 0; i < FADE_N; i++) {
  const t = (i / (FADE_N - 1)) * Math.PI * 0.5;
  FADE_IN[i] = Math.sin(t);          // sin/cos keeps the sum at constant power
  FADE_OUT[i] = Math.cos(t);
}

async function loadMusic() {
  initAudio();
  // Ask the browser which encoding it wants rather than guessing: Chromium
  // builds without the proprietary codecs cannot decode AAC, and Safari only
  // grew Opus support recently. Whichever it names, the other is the fallback.
  const probe = document.createElement('audio');
  const order = probe.canPlayType('audio/ogg; codecs=opus')
    ? ['calm_loop.ogg', 'calm_loop.m4a'] : ['calm_loop.m4a', 'calm_loop.ogg'];
  for (const name of order) {
    try {
      const bytes = await fetch(`audio/${name}`).then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${name}`);
        return r.arrayBuffer();
      });
      MUSIC.buf = await AC.decodeAudioData(bytes);
      MUSIC.file = name;
      return;
    } catch (err) {
      console.warn(`music: ${name} unusable —`, err.message || err);
    }
  }
  console.warn('music: no encoding decoded here; running with effects only');
}

function scheduleMusicPass(startAt) {
  const d = MUSIC.buf.duration;
  const xf = Math.min(MUSIC.xfade, d * 0.25);
  const src = AC.createBufferSource();
  src.buffer = MUSIC.buf;
  const g = AC.createGain();
  g.gain.setValueAtTime(0, startAt);
  g.gain.setValueCurveAtTime(FADE_IN, startAt, xf);
  g.gain.setValueAtTime(1, startAt + xf);
  g.gain.setValueCurveAtTime(FADE_OUT, startAt + d - xf, xf);
  src.connect(g).connect(MUSIC.gain);
  src.start(startAt);
  src.stop(startAt + d + 0.05);
  MUSIC.nextAt = startAt + d - xf;        // the next pass overlaps by xf
}

/** Keep roughly two seconds of the bed queued ahead of the playhead. */
function pumpMusic() {
  if (!MUSIC.on || !MUSIC.buf || !AC) return;
  while (MUSIC.nextAt < AC.currentTime + 2.0) scheduleMusicPass(MUSIC.nextAt);
}

function startMusic() {
  if (!MUSIC.buf || MUSIC.on) return;
  MUSIC.on = true;
  MUSIC.nextAt = AC.currentTime + 0.05;
  pumpMusic();
}

function musicTo(level, sec) {
  if (!MUSIC.gain || !AC) return;
  const g = MUSIC.gain.gain;
  g.cancelScheduledValues(AC.currentTime);
  g.setValueAtTime(g.value, AC.currentTime);
  g.linearRampToValueAtTime(level, AC.currentTime + sec);
}
state.MUSIC = MUSIC;

// ------------------------------------------------------ the stamped carpet
// Every swing plants a Bates impression where the die lands, and the number
// wheel advances with each one -- the die in the GLB reads 000137, so the
// carpet starts there. Misses stamp the office; that is half the joke, and it
// also teaches the strike range better than any tutorial text.
const DECALS = { max: 40, list: [], serial: 137 };
const decalGeo = new THREE.PlaneGeometry(0.42, 0.21);

function batesTexture(serial) {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 128;
  const g = c.getContext('2d');
  g.strokeStyle = g.fillStyle = 'rgba(224, 58, 21, 0.92)';
  g.lineWidth = 7;
  g.strokeRect(10, 10, 236, 108);
  g.textAlign = 'center';
  g.font = '700 34px system-ui, sans-serif';
  g.fillText('EXHIBITFY', 128, 52);
  g.font = '700 44px ui-monospace, monospace';
  g.fillText(String(serial).padStart(6, '0'), 128, 100);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function stampCarpet(x, z, yaw, dry) {
  if (!insideWalk(x, z)) return;           // no carpet there, no impression
  const mat = new THREE.MeshBasicMaterial({
    map: batesTexture(DECALS.serial++), transparent: true, depthWrite: false,
    // A dry stamp still leaves a mark, just a ghost of one. That is the
    // clearest possible read on why nothing got filed: the impression is
    // there on the carpet, and it is too faint to be an exhibit.
    opacity: dry ? 0.22 : 1.0,
  });
  const m = new THREE.Mesh(decalGeo, mat);
  // XYZ euler applies the in-plane spin (z) before laying the plane flat (x)
  m.rotation.set(-Math.PI / 2, 0, yaw + (Math.random() - 0.5) * 0.5);
  m.position.set(x, 0.004, z);
  m.renderOrder = 2;
  scene.add(m);
  DECALS.list.push(m);
  if (DECALS.list.length > DECALS.max) {
    const old = DECALS.list.shift();
    scene.remove(old);
    old.material.map.dispose();
    old.material.dispose();
  }
}
state.DECALS = DECALS;
state.OBJECTIONS = OBJECTIONS;
state.insideWalk = insideWalk;          // for tuning from the console
state.fitView = fitView;
state.LAYOUT = LAYOUT;
state.WALK = WALK;
state.BLOCKERS = BLOCKERS;
state.setRetro = setRetro;
state.RETRO = RETRO;
state.sfx = sfx;                        // same object the loops call through
state.spawnObjection = spawnObjection;      // for tuning from the console
// `startBonus` is a hoisted function declaration so this is safe here; BOSS_GLB
// is a const declared with it further down and must NOT be touched from up here.
state.startBonus = startBonus;              // for tuning from the console

// ---------------------------------------------------------------- input
//
// Two input models, because iOS Safari has no Pointer Lock API at all -- not
// "needs a gesture", not "needs a flag", it does not exist. Aiming is pointer
// lock on a desktop, so a phone cannot be given a slightly adapted version of
// the same thing; it needs its own.
//
// TOUCH is decided once, from whether the device reports a coarse pointer, and
// everything downstream keys off `state.touch` rather than sniffing the event
// type at each site.
const TOUCH = (() => {
  const q = matchMedia('(pointer: fine)');
  const fine = q.media === 'not all' ? true : q.matches;
  return !fine || navigator.maxTouchPoints > 1;
})();
state.touch = TOUCH;

/** Is the game meant to be simulating right now? */
function running() {
  if (state.intro) return false;      // the world waits behind the video
  if (state.waking) return false;     // ...and behind the head coming up
  return TOUCH ? state.playing : controls.isLocked;
}
state.running = running;

/** Start play under whichever model this device uses. */
function beginPlay() {
  if (!state.ready || state.done) return;
  if (!TOUCH) { controls.lock(); playIntro(); return; }
  state.playing = true;
  initAudio();                 // the tap that started us IS the gesture
  els.overlay.style.display = 'none';
  els.hud.hidden = els.reticle.hidden = els.clockBox.hidden = false;
  els.inkBox.hidden = false;
  els.touchUi.hidden = false;
  playIntro();
}
state.beginPlay = beginPlay;

// ---------------------------------------------------------------- the intro
//
// Press play, watch the reel, and be in the game when it ends -- no second
// click, no loading screen between the two.
//
// The whole trick is ORDER. Pointer lock is granted to a user gesture and
// nothing else, so asking for it after a half-minute video is asking with a
// stale gesture and being refused. The click takes the lock immediately; the
// video is then drawn over a game that is already live and simply held still
// by running(). When the video ends the overlay goes and the world is already
// yours.
// The authored intro first, the generated gameplay cut second.
//
// The MP4 is H.264, which every shipping browser plays -- including Safari,
// where WebM support is version-dependent. The WebM is what this toolchain can
// produce (libvpx only; the ffmpeg here has no H.264 encoder and no mp4 muxer)
// and covers builds without the proprietary codecs, which is not a hypothetical:
// the Chromium these tests run in reports no H.264 at all.
const INTRO_MP4 = './video/intro.mp4';
const INTRO_WEBM = './screenshots/intro.webm';
// However long the file is, the intro ends here. Fifteen seconds is the brief
// and the authored cut is 15.04 s (read off its mvhd), so the ceiling sits a
// second clear of it: the video's own `ended` is what normally hands over, and
// this is the backstop for a file that is longer, or stalled, or buffering.
// Set flush at 15.0 it would win the race every time and clip the last frames.
const INTRO_MAX = 16.0;
let introTimer = null;
let introCap = null;

function introSource() {
  const v = els.introVideo;
  if (!v.canPlayType) return null;
  if (v.canPlayType('video/mp4; codecs="avc1.42E01E"')) return INTRO_MP4;
  if (v.canPlayType('video/webm; codecs="vp8"')) return INTRO_WEBM;
  return null;
}

// Point the element at the file now rather than at the click. The game is
// already fetching GLBs when this runs, so the reel buffers alongside them and
// the click has something to play instead of four seconds of stall timeout on
// a phone connection.
{
  const src = introSource();
  if (src) els.introVideo.src = src;
}

function playIntro() {
  const v = els.introVideo;
  const src = introSource();
  // Nothing playable, or seen already this session: straight to the game
  // rather than a black rectangle or a reel on every replay.
  if (!src || sessionStorage.getItem('bates-intro') === 'seen') {
    startBed();
    startWake();
    return;
  }
  try { sessionStorage.setItem('bates-intro', 'seen'); } catch (e) { /* private mode */ }

  state.intro = true;
  els.intro.hidden = false;
  if (!v.src) v.src = src;
  v.currentTime = 0;
  const done = () => endIntro();
  v.addEventListener('ended', done, { once: true });
  v.addEventListener('error', done, { once: true });
  // A reel that will not start is not a reason to keep somebody waiting.
  clearTimeout(introTimer);
  introTimer = setTimeout(() => { if (v.readyState < 2) endIntro(); }, 4000);
  clearTimeout(introCap);
  introCap = setTimeout(endIntro, INTRO_MAX * 1000);

  // With sound if the browser will allow it. The click that got us here is a
  // user gesture, so it usually will; if it refuses, fall back to muted rather
  // than losing the intro over it.
  v.muted = false;
  v.volume = 0.9;
  const p = v.play();
  if (p && p.catch) {
    p.catch(() => {
      v.muted = true;
      const q = v.play();
      if (q && q.catch) q.catch(() => endIntro());
    });
  }
}

/** The music bed, held back until the intro is out of the way. */
function startBed() {
  // Ordinarily the lock/tap handler has already done this, but the no-intro
  // path runs synchronously inside beginPlay -- ahead of the lock event -- and
  // a context still suspended there would start the bed into silence.
  initAudio();
  startMusic();
  musicTo(MUSIC.level, 0.6);
}

function endIntro() {
  if (!state.intro) return;
  state.intro = false;
  clearTimeout(introTimer);
  clearTimeout(introCap);
  els.intro.hidden = true;
  try { els.introVideo.pause(); } catch (e) { /* nothing to pause */ }
  startBed();
  startWake();
}
state.endIntro = endIntro;

// ----------------------------------------------------------- waking up
//
// The ending screen has always said "you wake up" -- this is the other end of
// that. You start face-down on your own desk and the office dissolves into the
// corridor you dream about, which is the only explanation the game owes anyone
// for why a lawyer is hunting paper with a Bates stamp.
//
// It is a camera move and an overlay, not a cutscene: the world is already
// live, `running()` simply holds it still exactly as it does under the intro,
// so the handover at the end costs nothing and cannot desync. The desk is the
// real office kit's `desk_chair`, instanced a second time and dissolved on the
// way out. It is deliberately NOT in BLOCKERS -- it is scenery for 2.4 s and
// then it is gone, and a collision box left behind would wall off the corridor
// you spawn in.
const WAKE_FROM = { x: -0.05, y: 0.87, z: 0.70, pitch: -0.62, yaw: 0.055, roll: 0.42 };

// Lid coverage over time, as a fraction of half the frame each bar takes.
// Two blinks, because one reads as a fade and three reads as a malfunction:
// the eyes crack at 0.18, shut again at 0.34, and the second one at 0.80 is
// shallower than the first, which is what makes it look involuntary.
const LIDS = [
  [0.00, 0.97], [0.18, 0.62], [0.34, 0.90], [0.62, 0.42],
  [0.80, 0.72], [1.15, 0.20], [1.60, 0.06], [2.10, 0.00],
];

function lidAt(t) {
  if (t <= LIDS[0][0]) return LIDS[0][1];
  for (let i = 1; i < LIDS.length; i++) {
    if (t <= LIDS[i][0]) {
      const [t0, v0] = LIDS[i - 1], [t1, v1] = LIDS[i];
      return v0 + (v1 - v0) * ((t - t0) / (t1 - t0));
    }
  }
  return 0;
}

function startWake() {
  if (!state.deskProto || state.done) { finishWake(); return; }
  // An F-turn still in flight would keep rotating the scripted camera.
  state.snap = null;
  state.waking = true;
  state.wakeT = 0;
  state.wakeFading = false;

  const desk = place(state.deskProto.clone(true), 0, CFG.wakeDeskZ, 0);
  // Clone the materials too. Without this the fade at the end would take every
  // other desk in the building with it -- GLTFLoader shares one material across
  // every clone of a subtree, and `.clone()` does not deep-copy them.
  desk.traverse((o) => {
    if (!o.material) return;
    o.material = Array.isArray(o.material)
      ? o.material.map((m) => m.clone()) : o.material.clone();
  });
  scene.add(desk);
  state.wakeDesk = desk;

  // The ink pods sit out for the duration. One of them is parked at z 0.9 --
  // "back at the entrance you started from" -- and the camera slides from 0.70
  // to 1.20 as you sit back, straight through it. Its beacon is a pair of
  // crossed emissive quads, so passing through it fills half the frame with a
  // flat orange wedge. They come back the moment the eyes are open, which also
  // reads correctly: the dream furnishes itself as you arrive in it.
  for (const p of state.pods) p.root.visible = false;

  camera.position.set(WAKE_FROM.x, WAKE_FROM.y, WAKE_FROM.z);
  camera.rotation.set(WAKE_FROM.pitch, WAKE_FROM.yaw, WAKE_FROM.roll);
  els.lids.hidden = false;
  // The whole HUD goes, not just the reticle. A document count and a countdown
  // reading over a desk you have not lifted your head off yet is the game
  // telling you the rules before the character knows there are any.
  els.reticle.hidden = true;
  els.hud.hidden = els.clockBox.hidden = els.inkBox.hidden = true;
  els.touchUi.hidden = true;
  if (state.arms) state.arms.position.y = state.armsBaseY - 0.17;

  if (AC) {
    const t = AC.currentTime;
    playNoise(t, 0.40, 'bandpass', 2600, 1100, 0.13, 0.8);   // cheek off paper
    playTone(t + 0.55, 0.30, 'sawtooth', 210, 128, 0.026);   // the chair gives
    playNoise(t + 0.58, 0.22, 'lowpass', 700, 240, 0.10);
    playNoise(t + 1.45, 0.55, 'lowpass', 820, 300, 0.085);   // the first breath
  }
  updateWake(0);
}

function updateWake(dt) {
  state.wakeT += dt;
  const T = CFG.wakeTime;
  const t = Math.min(state.wakeT, T);

  // The lift is weighted late: the head stays down through the first blink and
  // most of the travel happens once the eyes are actually open, so the camera
  // is not doing its best work behind a closed lid.
  const e = smoothstep(Math.max(0, Math.min(1, (t - 0.45) / (T - 0.75))));
  camera.position.set(
    WAKE_FROM.x + (0 - WAKE_FROM.x) * e,
    WAKE_FROM.y + (CFG.eyeHeight - WAKE_FROM.y) * e,
    WAKE_FROM.z + (1.2 - WAKE_FROM.z) * e);
  // Written as a whole Euler every frame. Setting one component at a time
  // re-derives the camera quaternion from the others, which is the trap the
  // shake handler documents further down.
  camera.rotation.set(WAKE_FROM.pitch * (1 - e), WAKE_FROM.yaw * (1 - e),
                      WAKE_FROM.roll * (1 - e));
  state.rolled = false;

  const lid = lidAt(t) * 50;
  els.lidTop.style.height = `${lid}vh`;
  els.lidBottom.style.height = `${lid}vh`;

  // The arms come up with the head rather than appearing on a frame boundary.
  if (state.arms) state.arms.position.y = state.armsBaseY - 0.17 * (1 - e);

  // The office fades out over the last stretch: real desk into dreamt corridor.
  const a = Math.max(0, Math.min(1, (t - (T - 0.75)) / 0.6));
  if (state.wakeDesk && a > 0) {
    // `transparent` is flipped once, on the frame the fade starts, and it
    // carries needsUpdate because it changes the material's program. Flipping
    // it at clone time instead would put the desk on the blended path for the
    // whole two seconds it is meant to look solid, and a self-overlapping
    // model sorts badly there.
    const first = !state.wakeFading;
    state.wakeFading = true;
    state.wakeDesk.traverse((o) => {
      if (!o.material) return;
      for (const m of [].concat(o.material)) {
        if (first) { m.transparent = true; m.needsUpdate = true; }
        m.opacity = 1 - a;
      }
    });
  }

  if (state.wakeT >= T) finishWake();
}

function finishWake() {
  state.waking = false;
  els.lids.hidden = true;
  if (state.wakeDesk) {
    scene.remove(state.wakeDesk);
    state.wakeDesk.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      for (const m of (o.material ? [].concat(o.material) : [])) m.dispose();
    });
    state.wakeDesk = null;
  }
  // Only the pods that are actually out come back -- updatePods owns `live`,
  // and a taken one on cooldown must stay hidden.
  for (const p of state.pods) p.root.visible = p.live;
  camera.position.set(0, CFG.eyeHeight, 1.2);
  camera.rotation.set(0, 0, 0);
  if (state.arms) state.arms.position.y = state.armsBaseY;
  if (!state.done) {
    els.reticle.hidden = false;
    els.hud.hidden = els.clockBox.hidden = els.inkBox.hidden = false;
    els.touchUi.hidden = !TOUCH;      // desktop never had one to restore
  }
  banner('Bates & Destroy', 'Two minutes — stamp everything');
}
state.startWake = startWake;
state.finishWake = finishWake;

/** Smoothstep. Local, so the wake does not reach into three.js maths. */
function smoothstep(x) { return x * x * (3 - 2 * x); }

// Skip on anything deliberate. Under pointer lock every mouse event goes to
// the locked canvas rather than to the overlay, so this listens on the
// document instead of on the button.
els.introSkip.addEventListener('click', endIntro);
els.introSkip.addEventListener('touchstart', (e) => {
  e.preventDefault(); endIntro();
}, { passive: false });
addEventListener('mousedown', () => {
  if (state.intro) endIntro();
  else if (state.waking) finishWake();
});
addEventListener('touchstart', () => {
  if (state.intro) endIntro();
  else if (state.waking) finishWake();
}, { passive: true });
addEventListener('keydown', (e) => {
  const deliberate = e.code === 'Escape' || e.code === 'Space'
                  || e.code === 'Enter';
  if (state.intro && deliberate) endIntro();
  else if (state.waking && deliberate) finishWake();
});

els.overlay.addEventListener('click', beginPlay);
controls.addEventListener('lock', () => {
  initAudio();
  // The bed waits for the intro -- see startBed. If there is no intro, it
  // starts immediately, which is what playIntro does on the way out.
  els.overlay.style.display = 'none';
  // Not while a reel or a wake is up. `lock` is asynchronous -- beginPlay asks
  // for the lock and then calls playIntro synchronously, so on the paths where
  // the wake starts inside that same call (no video, or a restart) this event
  // lands AFTER startWake has hidden the HUD and would put it straight back.
  // finishWake is what reveals it in every case.
  if (state.intro || state.waking) return;
  els.hud.hidden = els.reticle.hidden = els.clockBox.hidden = false;
  els.inkBox.hidden = false;
});
controls.addEventListener('unlock', () => {
  // once the binder is closed the wake screen owns the view, not the menu
  if (!state.done) els.overlay.style.display = 'flex';
  els.hud.hidden = els.reticle.hidden = els.clockBox.hidden = true;
  els.inkBox.hidden = true;
  // the bed keeps running under the menu, just further back. Stopping it
  // would mean rescheduling the crossfade chain from scratch on every pause.
  if (!state.done) musicTo(MUSIC.level * 0.35, 0.4);
});
document.getElementById('again').addEventListener('click', () => {
  restart();
  beginPlay();              // the tap or click is the gesture; spend it
});
addEventListener('keydown', (e) => {
  state.keys[e.code] = true;
  // Mute. This is going to get shown in a room with other people in it.
  // P flips the look. Kept because "does this read better smooth or chunky"
  // is a judgement call somebody has to make with their own eyes, side by side.
  if (e.code === 'KeyP') setRetro(!RETRO.on);
  if (e.code === 'KeyF') faceNearest();
  // The arrows scroll the page otherwise, which drags the canvas off screen
  // on the one browser that is not holding the pointer.
  if (e.code.startsWith('Arrow')) e.preventDefault();
  if (e.code === 'KeyM' && master) {
    state.muted = !state.muted;
    master.gain.value = state.muted ? 0 : 0.32;
    warn(state.muted ? 'Sound off' : 'Sound on');
  }
});
addEventListener('keyup', (e) => { state.keys[e.code] = false; });

// ------------------------------------------------------------ touch input
//
// Left half of the screen drives a virtual stick, right half looks and taps to
// stamp. The split is by where the touch STARTED, held for the life of that
// finger, so a look-drag that wanders across the middle does not suddenly
// start walking -- which is what happens if you test the current position.
//
// Everything here is analogue where the keyboard is binary: the stick reports
// a magnitude, so a phone gets fine movement the keyboard cannot express, and
// sprint is just the far end of the same stick rather than a second control
// there is no room for.
const TOUCHES = new Map();
const STICK = { id: null, cx: 0, cy: 0, dx: 0, dy: 0 };
const LOOK = { id: null, x: 0, y: 0, moved: 0, t0: 0 };
const STICK_R = 62;          // px of travel for full deflection
const LOOK_SENS = 0.0042;    // radians per px
const TAP_MS = 260;          // shorter than this, and barely moved, is a tap
const TAP_SLOP = 14;         // px

function touchStart(e) {
  if (!state.playing) return;
  for (const t of e.changedTouches) {
    const left = t.clientX < innerWidth * 0.42;
    if (left && STICK.id === null) {
      STICK.id = t.identifier;
      STICK.cx = t.clientX; STICK.cy = t.clientY;
      STICK.dx = 0; STICK.dy = 0;
      showStick(true, t.clientX, t.clientY);
    } else if (!left && LOOK.id === null) {
      LOOK.id = t.identifier;
      LOOK.x = t.clientX; LOOK.y = t.clientY;
      LOOK.moved = 0; LOOK.t0 = performance.now();
    }
    TOUCHES.set(t.identifier, t);
  }
  e.preventDefault();
}

function touchMove(e) {
  // running(), not state.playing: a look-drag during the reel or the wake
  // would fight a camera that is being written every frame from a script.
  if (!running()) return;
  for (const t of e.changedTouches) {
    if (t.identifier === STICK.id) {
      STICK.dx = (t.clientX - STICK.cx) / STICK_R;
      STICK.dy = (t.clientY - STICK.cy) / STICK_R;
      const m = Math.hypot(STICK.dx, STICK.dy);
      if (m > 1) { STICK.dx /= m; STICK.dy /= m; }
      moveStickNub(STICK.dx, STICK.dy);
    } else if (t.identifier === LOOK.id) {
      const dx = t.clientX - LOOK.x;
      const dy = t.clientY - LOOK.y;
      LOOK.moved += Math.hypot(dx, dy);
      camera.rotation.y -= dx * LOOK_SENS;
      camera.rotation.x = Math.max(-1.2, Math.min(1.2,
        camera.rotation.x - dy * LOOK_SENS));
      LOOK.x = t.clientX; LOOK.y = t.clientY;
    }
  }
  e.preventDefault();
}

/**
 * Reconcile against the touches STILL down, rather than trusting
 * changedTouches to name the one that left.
 *
 * Some event sources hand you a touchend with an empty changedTouches -- the
 * headless driver does exactly that -- and a handler that only reads
 * changedTouches then never releases the finger. The symptom was subtle and
 * total: the first look-drag worked, LOOK.id was never cleared, and every tap
 * to stamp afterwards was silently dropped for the rest of the session.
 */
function touchEnd(e) {
  const live = new Set();
  for (const t of e.touches) live.add(t.identifier);
  if (STICK.id !== null && !live.has(STICK.id)) {
    STICK.id = null; STICK.dx = 0; STICK.dy = 0;
    showStick(false);
  }
  if (LOOK.id !== null && !live.has(LOOK.id)) {
    // a quick stab that did not really travel is a swing, not a look
    const quick = performance.now() - LOOK.t0 < TAP_MS;
    if (quick && LOOK.moved < TAP_SLOP && state.playing) startSwing();
    LOOK.id = null;
  }
  for (const id of [...TOUCHES.keys()]) if (!live.has(id)) TOUCHES.delete(id);
  e.preventDefault();
}

if (TOUCH) {
  const el = renderer.domElement;
  el.addEventListener('touchstart', touchStart, { passive: false });
  el.addEventListener('touchmove', touchMove, { passive: false });
  el.addEventListener('touchend', touchEnd, { passive: false });
  el.addEventListener('touchcancel', touchEnd, { passive: false });
  // Redaction has no second mouse button to live on, so it gets a key of its
  // own on screen. Sized for a thumb, not for a cursor.
  els.redactBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (state.playing) redact();
  }, { passive: false });
  // The F key, for thumbs. stopPropagation so the tap is not also read as a
  // look-drag landing on the right half of the screen.
  els.findBtn.addEventListener('touchstart', (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (state.playing) faceNearest();
  }, { passive: false });
}

function showStick(on, x, y) {
  els.stick.hidden = !on;
  if (on) {
    els.stick.style.left = x + 'px';
    els.stick.style.top = y + 'px';
    moveStickNub(0, 0);
  }
}

function moveStickNub(dx, dy) {
  els.stickNub.style.transform =
    `translate(${dx * STICK_R - 22}px, ${dy * STICK_R - 22}px)`;
}
renderer.domElement.addEventListener('contextmenu', (e) => e.preventDefault());
renderer.domElement.addEventListener('mousedown', (e) => {
  if (e.button === 2 && controls.isLocked) { redact(); return; }
  if (e.button === 0 && controls.isLocked) startSwing();
});

function startSwing() {
  if (!state.swing || state.intro || state.waking) return;
  if (state.swinging && state.swingT < CFG.swingRefire) return;
  state.swinging = true;
  state.swingT = 0;
  state.hitDone = false;
  // A dry stamp still swings. Blocking the input would be cheaper to write and
  // much worse to play: the animation plus a faint impression and no filing
  // tells the player exactly what is wrong, where a dead mouse button does not.
  state.swingDry = state.ink < CFG.inkPerSwing;
  if (!state.swingDry) {
    state.ink = Math.max(0, state.ink - CFG.inkPerSwing);
    updateInk();
  }
  state.swing.reset().play();
  sfx.swing();
}

// The gauge is written on change, not per frame, so every path that moves the
// ink has to say so. There are only three -- boot, swinging, and picking up a
// pod -- and this is the fourth, for setting it from the console without the
// readout silently drifting out of step with the number.
state.setInk = (n) => {
  state.ink = Math.max(0, Math.min(CFG.inkMax, n));
  updateInk();
  return state.ink;
};

function updateInk() {
  const k = Math.max(0, Math.min(1, state.ink / CFG.inkMax));
  els.inkFill.style.width = `${k * 100}%`;
  const dry = state.ink < CFG.inkPerSwing;
  els.inkBox.classList.toggle('dry', dry);
  els.inkBox.classList.toggle('low', !dry && state.ink <= CFG.inkLow);
  els.inkLabel.textContent = dry
    ? 'Stamp dry — find ink'
    : `Stamp ink · ${Math.floor(state.ink / CFG.inkPerSwing)} left`;
}

// ---------------------------------------------------------------- redaction
//
// The joke, and the one trap in the game. A Bates stamp indexes a document for
// production -- so stamping the PRIVILEGE paper produces privileged material to
// the other side, which is the single worst thing a litigator can do by
// accident. That one has to be REDACTED (right mouse) instead, and everything
// else is fair game to over-redact if you feel like blacking out a pleading.

function redactable() {
  aimStrike();
  let best = null, bestD = Infinity;
  for (const e of state.enemies) {
    if (!e.alive || e.redacted) continue;
    tmpV.copy(e.root.position).sub(strike);
    tmpV.y = 0;
    const d = tmpV.length();
    if (d > CFG.strikeRadius + CFG.enemyRadius * e.v.radius) continue;
    if (d < bestD) { bestD = d; best = e; }
  }
  return best;
}

/** Black out every page of a document. Cheaper than a stamp, and reversible by
 *  nothing at all -- a redacted exhibit is still filed, just unreadable. */
function redact() {
  if (state.intro) return;
  if (state.phase === 'bonus') return;         // nothing to redact in there
  if (state.ink < CFG.inkPerRedact) { sfx.dry(); warn('No ink to redact with'); return; }
  const e = redactable();
  if (!e) return;
  state.ink -= CFG.inkPerRedact;
  updateInk();
  e.redacted = true;
  // Materials are shared by name across the combined GLB, so clone before
  // darkening or every document of this kind goes black at once.
  e.root.traverse((o) => {
    if (!o.isMesh || !o.material) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    // Keep what was there. Restarting has to put the document back, and by the
    // time it does, the only reference to the original material is this one.
    if (o.userData.mat0 === undefined) o.userData.mat0 = o.material;
    o.material = (Array.isArray(o.material) ? mats : mats).map((m) => {
      if (/Face|Limb|Glove|Shoe|Ring/i.test(m.name)) return m;   // keep the face
      const c = m.clone();
      c.color.setRGB(0.045, 0.045, 0.05);
      c.map = null;                            // the point is that it is gone
      return c;
    });
    if (!Array.isArray(o.material)) o.material = o.material[0];
  });
  state.redactions += 1;
  if (e.kind === 'privilege') {
    state.privilegeSaved = true;
    warn('Privileged material redacted');
  } else {
    state.overRedacted += 1;
    warn('Redacted — nobody asked you to');
  }
  sfx.redact();
}

// --------------------------------------------------------------- objections

/** Pick a rule that is allowed to appear yet, weighted so 403 stays rare. */
function pickObjection() {
  const pool = [];
  for (const [kind, o] of Object.entries(OBJECTIONS)) {
    if (state.filed < o.after) continue;      // nothing worth striking yet
    for (let i = 0; i < o.weight; i++) pool.push(kind);
  }
  if (!pool.length) return null;
  return pool[Math.floor(Math.random() * pool.length)];
}

/** A walkable spot at least objSpawnMin away, so nothing appears on top of you. */
function objSpawnPoint() {
  let best = null, bestD = -1;
  for (let i = 0; i < 48; i++) {
    // Inside the room once the round moves there. The arena is a walkable
    // island with no path back to the corridor, so an objection spawned in the
    // hallway would walk at a wall for thirty seconds and threaten nothing.
    const r = state.arena ? state.arena.rect
      : WALK[Math.floor(Math.random() * WALK.length)];
    const x = r.x0 + Math.random() * (r.x1 - r.x0);
    const z = r.z0 + Math.random() * (r.z1 - r.z0);
    if (!insideWalk(x, z)) continue;
    const d = Math.hypot(x - camera.position.x, z - camera.position.z);
    // The room is 9 x 7, so nothing in it is 7 m from you: ask for less in
    // there or every spawn falls through to the "furthest we found" branch.
    if (d >= (state.arena ? CFG.objSpawnMin * 0.6 : CFG.objSpawnMin)) {
      return { x, z };
    }
    if (d > bestD) { bestD = d; best = { x, z }; }   // fall back to the furthest
  }
  return best;
}

function spawnObjection() {
  if (state.objections.filter((o) => o.alive).length >= CFG.objMax) return;
  const kind = pickObjection();
  if (!kind) return;
  const at = objSpawnPoint();
  if (!at) return;

  const o = OBJECTIONS[kind];
  const g = state.objProto[kind].clone(true);
  g.position.set(at.x, 0, at.z);
  g.rotation.y = Math.random() * Math.PI * 2;
  scene.add(g);
  const mixer = new THREE.AnimationMixer(g);
  const run = mixer.clipAction(
    THREE.AnimationClip.findByName(state.objClips, `${kind}_Run`));
  run.play();
  const hit = mixer.clipAction(
    THREE.AnimationClip.findByName(state.objClips, `${kind}_Stamped`));
  hit.setLoop(THREE.LoopOnce, 1);
  hit.clampWhenFinished = true;
  state.objections.push({
    kind, o, root: g, mixer, run, hit, alive: true, dead: 0,
    heading: g.rotation.y, phase: Math.random() * 6.28,
    baseScale: g.scale.clone(),
  });
  warn(`${o.label} — objection!`);
  sfx.objection();
}

function updateObjections(dt) {
  // schedule
  state.nextObj -= dt;
  if (state.nextObj <= 0) {
    spawnObjection();
    state.nextObj = CFG.objEvery + (Math.random() * 2 - 1) * CFG.objJitter;
  }

  for (const e of state.objections) {
    if (!e.alive) {
      e.dead += dt;
      e.mixer.update(dt);
      if (!e.gone && e.dead > 1.1) {          // let Stamped finish, then clear
        e.gone = true;
        scene.remove(e.root);
      }
      continue;
    }
    tmpV.copy(e.root.position).sub(camera.position);
    tmpV.y = 0;
    const dist = tmpV.length();

    // it has reached the binder: strike exhibits back out of the record
    if (dist <= CFG.objReach) {
      e.alive = false;
      e.dead = 0;
      e.run.fadeOut(0.08);
      sustain(e);
      continue;
    }

    // hunt: face the player, which is the opposite sign to a fleeing exhibit
    let want = Math.atan2(tmpV.x, tmpV.z);
    if (e.o.weave) {
      want += Math.sin(state.t * e.o.weave.rate + e.phase) * e.o.weave.amp;
    }
    let diff = ((want - e.heading + Math.PI) % (Math.PI * 2)) - Math.PI;
    if (diff < -Math.PI) diff += Math.PI * 2;
    const turn = e.o.turn;
    e.heading += THREE.MathUtils.clamp(diff, -turn * dt, turn * dt);

    const sp = e.o.speed;
    const mv = resolveMove(e.root.position,
                           -Math.sin(e.heading) * sp * dt,
                           -Math.cos(e.heading) * sp * dt);
    if (mv.dx === 0 && mv.dz === 0) e.heading += 2.4 * dt;
    e.root.position.x += mv.dx;
    e.root.position.z += mv.dz;
    e.root.rotation.y = e.heading;
    e.mixer.update(dt);
    // An objection used to be silent all the way in, so one coming from behind
    // announced itself by taking an exhibit out of the binder. Now it walks
    // audibly, and mutters once it is close enough to be about to land.
    footfall(e, e.o.stride, dt, sfx.objStep);
    e.mutter = (e.mutter || 0) - dt;
    if (dist < CFG.objNearAt && e.mutter <= 0) {
      e.mutter = 1.3;
      sfx.objNear(e.root.position.x, e.root.position.z);
    }
  }
}

/** An objection reached the binder and was sustained. */
function sustain(e) {
  state.sustained += 1;
  e.hit.reset().play();
  sfx.sustained();
  state.shake = 1;

  // The bonus is a round you can only lose the bonus in. An objection landing
  // during it used to strike exhibits out of a binder that was already closed
  // and already won -- a run ended on "Adverse inference" after the case had
  // been decided, which reads as the game taking back a prize it awarded.
  // In here the currency is the ruling clock, so that is what it costs.
  if (state.phase === 'bonus') {
    state.clock = Math.max(0, state.clock - CFG.objBonusCost);
    warn(`${e.o.label} sustained — ${CFG.objBonusCost}s off the ruling`);
    updateHud();
    return;
  }

  const n = Math.min(state.filed, e.o.strikes);
  state.filed -= n;
  state.struck += n;
  if (n > 0) swear(true);          // losing one off the board deserves it
  warn(n > 0
    ? `${e.o.label} sustained — ${n} exhibit${n === 1 ? '' : 's'} struck`
    : `${e.o.label} sustained — nothing in the binder to strike`);
  updateHud();
}

// ------------------------------------------------------------- bonus round

const BOSS_GLB = `${ASSETS}/enemies/enemy_counsel.glb`;
const ARENA_GLB = `${ASSETS}/environment/conference_room.glb`;

// The bonus round does not happen in the corridor any more.
//
// A corridor is 1.72 m of walkable width -- 0.86 m of sidestep from the
// centreline -- and the binder collision had to be shaved twice to keep the
// dodge winnable in it. That is balancing the round against the hallway rather
// than designing it. The conference room is 9 x 7 m of clear floor, parked
// well clear of the corridor loop, and both of you are shown into it when the
// round starts.
const ARENA = { x: 15.0, z: -6.0, w: 10.0, d: 8.5 };

/**
 * Opposing counsel turns up in person. Fetched here rather than with the rest
 * of the assets: it is a bonus round most players never earn, and nobody
 * should pay for a lawyer up front to find out they were too slow. The load
 * happens under the transition card.
 *
 * The round inverts the whole game. Everything up to here has been you closing
 * on paper that runs away; this is paper coming at you and the stamp being no
 * use at all. You cannot number a binder in flight -- you move, or you wear it.
 */
async function startBonus() {
  state.phase = 'bonus';
  state.caseWon = true;
  state.timeLeft = state.clock;          // banked, and reported in the ending
  banner('Opposing counsel', 'Dodge every binder');
  musicTo(MUSIC.level * 1.15, 0.8);

  let g, clips;
  try {
    // Fetched once per page, not once per bonus round: a player who restarts
    // and qualifies again has already paid for this.
    if (!state.bossGltf) {
      state.bossGltf = await load(BOSS_GLB);
      retroFilter(state.bossGltf.scene);   // fetched on qualification, after boot
    }
    g = state.bossGltf.scene.clone(true);
    clips = state.bossGltf.animations;
    await openArena();
    // Shown in through the door on the near wall, facing the room.
    camera.position.set(ARENA.x, CFG.eyeHeight, ARENA.z - ARENA.d * 0.5 + 0.9);
    camera.rotation.set(0, Math.PI, 0);
    state.lastX = camera.position.x;
    state.lastZ = camera.position.z;
  } catch (err) {
    // The bonus is a reward, not a requirement: if it will not load, award the
    // case that was already won rather than stranding the player in an empty
    // round.
    console.warn('bonus: counsel failed to load —', err && err.message);
    finishBonus(false);
    return;
  }

  // Down the corridor from you, facing you, at throwing range. Not the
  // furthest walkable rectangle the way the walking boss used it -- he has to
  // have a clear line to throw along, and you have to be able to see him wind
  // up, which is the entire tell you get.
  const spawn = counselSpawnPoint();
  g.position.set(spawn.x, 0, spawn.z);
  scene.add(g);
  const mixer = new THREE.AnimationMixer(g);
  const idle = mixer.clipAction(THREE.AnimationClip.findByName(clips, 'Idle'));
  idle.play();
  const throwA = mixer.clipAction(THREE.AnimationClip.findByName(clips, 'Throw'));
  throwA.setLoop(THREE.LoopOnce, 1);
  throwA.clampWhenFinished = true;
  const gloat = mixer.clipAction(THREE.AnimationClip.findByName(clips, 'Gloat'));
  gloat.setLoop(THREE.LoopOnce, 1);
  gloat.clampWhenFinished = true;
  state.boss = {
    root: g, mixer, idle, throwA, gloat, alive: true, dead: 0,
    thrown: 0, dodged: 0, next: 1.4, winding: -1,
    baseScale: g.scale.clone(),
  };
  state.binders = [];
  state.clock = CFG.bonusTime;
  state.nextObj = CFG.bossObjEvery;
  els.clockLabel.textContent = 'before the ruling';
  updateHud();
}

/**
 * Open the room: put its geometry in the scene, its floor in the walkable set,
 * and its furniture in the blockers.
 */
async function openArena() {
  if (!state.arenaGltf) {
    state.arenaGltf = await load(ARENA_GLB);
    retroFilter(state.arenaGltf.scene);    // the room is fetched on qualification too
  }
  const g = state.arenaGltf.scene.clone(true);
  g.position.set(ARENA.x, 0, ARENA.z);
  scene.add(g);

  const pad = CFG.playerRadius;
  const rect = {
    x0: ARENA.x - ARENA.w * 0.5 + pad, x1: ARENA.x + ARENA.w * 0.5 - pad,
    z0: ARENA.z - ARENA.d * 0.5 + pad, z1: ARENA.z + ARENA.d * 0.5 - pad,
  };
  WALK.push(rect);
  // Table and chairs along the far wall, and the discovery stacked in the
  // corner it came out of. Both are solid, which also stops counsel walking
  // through his own furniture.
  const added = [
    // table and its chairs down the left wall, discovery stacked on the right
    { kind: 'table', x0: ARENA.x - 4.5 - pad, x1: ARENA.x - 2.9 + pad,
      z0: ARENA.z - 2.4 - pad, z1: ARENA.z + 2.4 + pad },
    { kind: 'discovery', x0: ARENA.x + 4.1 - pad, x1: ARENA.x + 4.9 + pad,
      z0: ARENA.z - 1.75 - pad, z1: ARENA.z - 0.95 + pad },
  ];
  for (const b of added) BLOCKERS.push(b);

  state.arena = { root: g, rect, blockers: added.length };
  return rect;
}

/** Put the room away again, so a second round is not built on the first. */
function closeArena() {
  const a = state.arena;
  if (!a) return;
  scene.remove(a.root);
  const i = WALK.indexOf(a.rect);
  if (i >= 0) WALK.splice(i, 1);
  BLOCKERS.length = Math.max(0, BLOCKERS.length - a.blockers);
  state.arena = null;
}
state.closeArena = closeArena;

/** A spot down a corridor from the player, with a clear line to throw along. */
function counselSpawnPoint() {
  // In the room he stands at the far end of it, with the whole width to work.
  if (state.arena) {
    // The far end, clear of the table: he needs somewhere to stand that is
    // not furniture, or his own line-of-sight test fails and he never throws.
    return { x: ARENA.x + 0.8, z: ARENA.z + ARENA.d * 0.5 - 1.3 };
  }
  let best = null, bestScore = -1;
  for (let i = 0; i < 200; i++) {
    const r = WALK[Math.floor(Math.random() * WALK.length)];
    const x = r.x0 + Math.random() * (r.x1 - r.x0);
    const z = r.z0 + Math.random() * (r.z1 - r.z0);
    if (!insideWalk(x, z)) continue;
    const d = Math.hypot(x - camera.position.x, z - camera.position.z);
    // He wants to be about bossRange away: close enough to read, far enough
    // that a binder takes a second to arrive.
    let score = 10 - Math.abs(d - CFG.bossRange);
    if (!clearLine(camera.position.x, camera.position.z, x, z)) score -= 20;
    if (score > bestScore) { bestScore = score; best = { x, z }; }
  }
  return best || { x: camera.position.x, z: camera.position.z - CFG.bossRange };
}

/** Is the straight line between two points walkable the whole way? */
function clearLine(x0, z0, x1, z1) {
  const n = Math.ceil(Math.hypot(x1 - x0, z1 - z0) / 0.35);
  for (let i = 1; i < n; i++) {
    const t = i / n;
    if (!insideWalk(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t)) return false;
  }
  return true;
}

function updateBoss(dt) {
  const b = state.boss;
  if (!b) return;
  b.mixer.update(dt);
  if (!b.alive) { b.dead += dt; return; }

  // face the player, always: the wind-up is only a tell if you can see it
  tmpV.copy(b.root.position).sub(camera.position);
  tmpV.y = 0;
  b.root.rotation.y = Math.atan2(-tmpV.x, -tmpV.z);

  // He works the room rather than standing at one end of it: pacing changes
  // the angle every throw comes in at, which is most of what makes the wider
  // floor worth having.
  if (state.arena) {
    // Turn at the FURNITURE, not at an imagined limit. Half his pacing run
    // used to cross the conference table: he stood inside it, every binder
    // thrown from there spawned outside the walkable set and was deleted on
    // the same frame -- and a deleted binder scores as one you dodged. Two
    // thirds of his throws were being credited to the player for nothing.
    b.pace = b.pace || 1;
    const nx = b.root.position.x + b.pace * CFG.bossPace * dt;
    if (insideWalk(nx, b.root.position.z)) b.root.position.x = nx;
    else b.pace *= -1;
  }

  // If you walk out of his line he repositions rather than throwing into a
  // wall -- otherwise the corner nearest him is a safe room and the round is
  // over as a game.
  const seen = clearLine(camera.position.x, camera.position.z,
                         b.root.position.x, b.root.position.z);
  if (!seen && b.winding < 0) {
    const spot = counselSpawnPoint();
    b.root.position.x += (spot.x - b.root.position.x) * Math.min(1, dt * 1.6);
    b.root.position.z += (spot.z - b.root.position.z) * Math.min(1, dt * 1.6);
  }

  if (b.winding >= 0) {
    b.winding += dt;
    if (b.winding >= CFG.bossWindup) {
      b.winding = -1;
      throwBinder();
    }
    return;
  }

  // Muttering between throws, on its own slow timer. `swear` has a cooldown of
  // its own, so this cannot machine-gun the bubble.
  if (Math.random() < dt * 0.28) swear();

  b.next -= dt;
  if (b.next <= 0 && seen) {
    b.winding = 0;
    // Aim is locked HERE, at the start of the wind-up, not at the release.
    // The corridor is 1.72 m wide and the player can only be 0.86 m off its
    // centreline, so a throw aimed where you stand when it leaves his hand is
    // not dodgeable in the space available -- it is a cutscene with a die roll.
    // Locking it a wind-up early makes the wind-up the tell it is animated to
    // be, and gives you 0.40 s at 3.1 m/s to be somewhere else.
    b.aimX = camera.position.x + (camera.position.x - state.lastX) * CFG.binderLead * 30;
    b.aimZ = camera.position.z + (camera.position.z - state.lastZ) * CFG.binderLead * 30;
    b.throwA.reset().play();
    sfx.windup(b.root.position.x, b.root.position.z);
    // He winds up through the round: by the last third there is one in the
    // air while he is already cocking the next.
    // Clamped at BOTH ends. Math.min alone let k go negative whenever the
    // clock was above bonusTime -- which a console tweak or a longer round
    // does -- and at k = -29 the interval came out at 21 seconds, i.e. he
    // simply stopped throwing.
    const k = Math.max(0, Math.min(1, 1 - state.clock / CFG.bonusTime));
    b.next = CFG.bossCycle + (CFG.bossCycleMin - CFG.bossCycle) * k
           + CFG.bossWindup;
  }
}

/** The binder leaves his hand, on the frame the clip says it does. */
function throwBinder() {
  const b = state.boss;
  if (!b || !state.binderProto) return;
  b.thrown += 1;

  // Belt and braces: if he has somehow ended up somewhere a binder cannot
  // exist, do not throw one, rather than throwing one that dies instantly and
  // is scored as a dodge.
  if (!insideWalk(b.root.position.x, b.root.position.z)) {
    b.thrown -= 1;
    return;
  }
  const g = state.binderProto.clone(true);
  // out of the hand, not out of his navel
  const from = new THREE.Vector3(b.root.position.x, 1.30, b.root.position.z);
  g.position.copy(from);
  g.scale.setScalar(0.85);
  scene.add(g);

  // Where you were when he started winding up, plus a little lead on the
  // movement you were making then. Committed early on purpose -- see the note
  // in updateBoss about the width of a corridor.
  const aim = new THREE.Vector3(b.aimX, 1.15, b.aimZ);
  const dir = aim.sub(from).normalize();

  state.binders.push({
    root: g, dir, life: 0,
    spin: (Math.random() < 0.5 ? -1 : 1) * CFG.binderSpin,
  });
  sfx.throwRelease(from.x, from.z);
  updateHud();
}

/**
 * A swing in progress protects you for as long as it lasts.
 *
 * Not a test on the impact frame: the die lands 0.367 s after the click and a
 * binder covers 2.7 m in that time, so by the time the strike resolved the
 * thing was already past you or on you -- measured, zero deflections in three
 * attempts that were aimed correctly. The whole swing is the window instead,
 * which is what "swing at it" means to anybody playing.
 */
function tryDeflect() {
  if (!state.swinging || !state.deflectReady || state.phase !== 'bonus') return;
  camera.getWorldDirection(fwd);
  fwd.y = 0;
  fwd.normalize();
  for (const p of state.binders) {
    if (p.done || p.deflected) continue;
    const dx = p.root.position.x - camera.position.x;
    const dz = p.root.position.z - camera.position.z;
    const d = Math.hypot(dx, dz);
    if (d > (state.touch ? CFG.deflectRangeTouch : CFG.deflectRange)) continue;
    if (dx * fwd.x + dz * fwd.z <= 0.0) continue;    // behind you
    deflectBinder(p);
    return;
  }
}

function updateBinders(dt) {
  tryDeflect();
  for (const p of state.binders) {
    if (p.done) continue;
    p.life += dt;
    // Where it was, before it moves: the hit test is swept along the step.
    const ax = p.root.position.x, az = p.root.position.z;
    p.root.position.addScaledVector(p.dir, CFG.binderSpeed * dt);
    p.root.rotation.x += p.spin * dt;
    p.root.rotation.z += p.spin * 0.4 * dt;

    // Did it get you? Tested against the SEGMENT it travelled this frame, not
    // against where it happened to land.
    //
    // At 7.4 m/s and the delta clamped to 0.05 s, a binder can move 0.37 m in
    // one step, against a hit radius of 0.48 -- so on a slow frame it steps
    // most of the way through you and whether it connects depends on where the
    // frames fell. That is not a hypothetical: measured here, a binder whose
    // trajectory passed exactly through the player (perpendicular distance
    // 0.00) sometimes registered nothing. A phone at 30 fps and a desktop at
    // 144 would also be playing subtly different games.
    const dy = p.root.position.y - CFG.eyeHeight;
    const reach = CFG.playerRadius2
                + (state.touch ? CFG.binderRadiusTouch : CFG.binderRadius);
    if (segmentDistance(ax, az, p.root.position.x, p.root.position.z,
                        camera.position.x, camera.position.z) < reach
        && Math.abs(dy) < 1.0) {
      p.done = true;
      scene.remove(p.root);
      hitByBinder();
      continue;
    }
    // Gone past, into a wall, or out of the world. Tested against the room's
    // BOUNDS, not against insideWalk: that one also refuses the furniture,
    // which is right for feet and wrong for something flying at 1.2 m. It cost
    // 12 of 15 binders in a round -- counsel paces the top edge of the
    // conference table, threw diagonally across it, and every one of those
    // was deleted 0.05 s after leaving his hand and scored to the player as a
    // dodge. A binder clears a 0.74 m table.
    if (p.life > 3.0 || !insideBounds(p.root.position.x, p.root.position.z)
        || p.root.position.y < 0.05) {
      p.done = true;
      scene.remove(p.root);
      if (!p.deflected) dodgedBinder();   // a deflection already scored
    }
  }
  if (state.binders.some((p) => p.done)) {
    state.binders = state.binders.filter((p) => !p.done);
  }
}

/** Closest distance from the point (px, pz) to the segment (ax,az)-(bx,bz). */
function segmentDistance(ax, az, bx, bz, px, pz) {
  const vx = bx - ax, vz = bz - az;
  const len2 = vx * vx + vz * vz;
  let t = len2 > 1e-9 ? ((px - ax) * vx + (pz - az) * vz) / len2 : 0;
  t = Math.max(0, Math.min(1, t));
  return Math.hypot(px - (ax + vx * t), pz - (az + vz * t));
}

/** One went past you. */
function dodgedBinder() {
  const b = state.boss;
  if (!b || !b.alive) return;
  b.dodged += 1;
  // A binder resolving without a deflection re-arms the stamp: the rule is no
  // two deflections in a row, not one deflection per round.
  state.deflectReady = true;
  sfx.whoosh();
  updateHud();
}

/** One did not. */
function hitByBinder() {
  const b = state.boss;
  state.binderHits += 1;
  state.deflectReady = true;      // being hit also re-arms it
  state.shake = 1;
  state.kick = 1;
  sfx.ouch();
  swear(true);
  if (b && b.alive) { b.idle.stop(); b.gloat.reset().play(); b.idle.play(); }
  updateHud();
}

/** Batted out of the air. Counts as survived, and locks the stamp for one. */
function deflectBinder(p) {
  const b = state.boss;
  p.dir.set(-p.dir.x, 0.35, -p.dir.z).normalize();
  p.spin *= -2.2;
  p.deflected = true;
  p.life = 2.4;                   // it is somebody else's problem now
  if (b) b.deflected = (b.deflected || 0) + 1;
  state.deflects += 1;
  state.deflectReady = false;     // the next one has to be dodged
  state.kick = 0.8;
  sfx.deflect();
  warn('Deflected — the next one you dodge');
  updateHud();
}

/**
 * Work out the tier from the counters. Idempotent, and called both by
 * settleBonus and by finish(), so any path out of the round scores it.
 *
 * The belt and braces is cheap and worth it, but the bug that appeared to
 * demand it was not real: a test kept reporting "no tier, ending says Verdict
 * for the defense", which is the placeholder text sitting in index.html's
 * #wake-tag. Its poll ran 100 s of wall clock, and headless game time runs
 * about a quarter of that -- it was giving up before a 30 s round could end
 * and reading the markup default. Check that the round actually finished
 * before believing anything about how it finished.
 */
function scoreBonus() {
  const b = state.boss;
  const survived = b ? b.dodged + (b.deflected || 0) : 0;
  state.survived = survived;
  state.bonusTier = survived >= CFG.tierLawyer ? 'lawyer'
    : survived >= CFG.tierSuper ? 'super'
    : survived <= CFG.tierDisbarred ? 'disbarred' : 'plain';
  return state.bonusTier;
}
state.scoreBonus = scoreBonus;

/**
 * The clock ran out. Score what you survived.
 *
 * Both a dodge and a deflection count: the round asks whether a binder got
 * you, and either way one did not.
 */
function settleBonus() {
  const b = state.boss;
  if (!b || !b.alive) return;
  b.alive = false;
  b.dead = 0;
  scoreBonus();
  finishBonus(state.bonusTier === 'lawyer');
}

/**
 * The bonus ends. `granted` means the motion reached you, which is a loss of the
 * bonus only: the case was already won on the binder before any of this began.
 */
function finishBonus(won, granted) {
  if (state.done) return;
  state.bonusWon = !!won;
  state.bonusGranted = !!granted;
  finish(true, true);
}

/**
 * A complete binder has to be held for closeHold before the case is closed, so
 * an objection can still take it apart on the last second.
 */
function updateClosing(dt) {
  const total = state.enemies.length;
  if (state.filed < total) {
    if (state.closing > 0) {          // it was broken into: back to work
      state.closing = 0;
      state.closeBroken += 1;
      warn('Binder reopened');
      updateHud();
    }
    return;
  }
  const first = state.closing === 0;
  state.closing += dt;
  if (first) updateHud();
  if (state.closing >= CFG.closeHold) finish(true);
}

function updateBonusClock(dt) {
  state.clock = Math.max(0, state.clock - dt);
  const s = Math.ceil(state.clock);
  els.clock.textContent = `0:${String(s % 60).padStart(2, '0')}`;
  els.clock.classList.toggle('low', state.clock <= 12);
  if (s !== state.lastTickS) {
    state.lastTickS = s;
    if (state.clock > 0 && state.clock <= 12) sfx.tick();
  }
  if (state.clock === 0) settleBonus();
}

function updatePods(dt) {
  for (const p of state.pods) {
    if (!p.live) {
      p.cooldown -= dt;
      if (p.cooldown <= 0) {
        p.live = true;
        p.root.visible = true;
      }
      continue;
    }
    // idle motion, so a pod reads as a pickup and not as kit dressing
    p.root.position.y = p.home.y + CFG.podFloat
                      + Math.sin(state.t * 2.1 + p.phase) * 0.045;
    p.root.rotation.y += dt * 1.5;

    tmpV.copy(p.home).sub(camera.position);
    tmpV.y = 0;
    const near = tmpV.length();
    // The beacon is for finding a pod across a room; up close it is a wall of
    // orange across the middle of the screen. On full ink a pod is not picked
    // up at all, so the player can stand inside one indefinitely -- switch the
    // beacon off before that happens.
    if (p.beacon) p.beacon.visible = near > CFG.podRadius * 1.9;
    if (state.ink >= CFG.inkMax) continue;      // full: leave it standing
    if (near > CFG.podRadius) continue;
    p.live = false;
    p.cooldown = CFG.podRespawn;
    p.root.visible = false;
    state.ink = Math.min(CFG.inkMax, state.ink + CFG.podRefill);
    updateInk();
    sfx.ink();
  }
}

// ---------------------------------------------------------------- hits
const tmpV = new THREE.Vector3();
const fwd = new THREE.Vector3();

const strike = new THREE.Vector3();
const fileTo = new THREE.Vector3();

/** Put `strike` where the die lands: a point ahead of the eye, on the floor. */
/**
 * Turn to face the nearest thing worth facing. The "auto look".
 *
 * Not an auto-aim that fires: it only rotates, and only when asked. Hunting a
 * 0.6 m sheet of paper down a corridor with a mouse is the part of this that
 * assumes you already play shooters, and nothing else in the game does.
 *
 * Priority is documents first, then an objection, then the boss -- an objection
 * is on a timer and the boss cannot be missed, so neither needs the help that a
 * fleeing exhibit does.
 */
function faceNearest() {
  if (!running()) return;
  const here = camera.position;
  const pick = (list, live) => list
    .filter(live)
    .sort((a, b) => a.root.position.distanceTo(here)
                  - b.root.position.distanceTo(here))[0];
  const t = pick(state.enemies, (e) => e.alive)
    || pick(state.objections, (o) => o.alive)
    || (state.boss ? state.boss : null);
  if (!t) { warn('Nothing left to file'); return; }

  const want = Math.atan2(here.x - t.root.position.x,
                          here.z - t.root.position.z);
  let d = ((want - camera.rotation.y + Math.PI) % (Math.PI * 2)) - Math.PI;
  if (d < -Math.PI) d += Math.PI * 2;
  state.snap = { left: d };
}
state.faceNearest = faceNearest;

// -------------------------------------------------------------- markers
//
// A document is 0.6 m of paper in a grey corridor and at 10 m it is a smudge.
// These are the smallest thing that fixes that: one chevron per live exhibit,
// projected to the screen, clamped to the edge with an arrow when it is behind
// you. They fade out inside 4 m, where the paper speaks for itself.
const MARK = { pool: [] };

function updateMarkers() {
  const live = running() && !state.done
    ? state.enemies.filter((e) => e.alive) : [];
  const w = innerWidth, h = innerHeight;
  // The pool grows to the roster, whatever the roster is. It was capped at a
  // literal 8 -- exactly the roster size, so nothing was visibly wrong, and
  // the ninth enemy anyone adds would have silently gone unmarked.
  for (let i = 0; i < Math.max(MARK.pool.length, live.length); i++) {
    let el = MARK.pool[i];
    if (!el && i < live.length) {
      el = document.createElement('div');
      el.className = 'mark';
      els.markers.appendChild(el);
      MARK.pool[i] = el;
    }
    if (!el) continue;
    const e = live[i];
    if (!e) { el.style.display = 'none'; continue; }

    MARK.v = MARK.v || new THREE.Vector3();
    // Aim at the middle of the sheet, not the floor between its feet.
    MARK.v.set(e.root.position.x, e.root.position.y + 0.45, e.root.position.z);
    const dist = camera.position.distanceTo(MARK.v);
    MARK.v.project(camera);
    // `project` mirrors everything behind the camera, so z > 1 has to be
    // handled or the marker for something at your back tracks the wrong way.
    const behind = MARK.v.z > 1;
    let x = (behind ? -MARK.v.x : MARK.v.x) * 0.5 + 0.5;
    let y = (behind ? 1 : -MARK.v.y * 0.5 + 0.5);
    const off = behind || x < 0.02 || x > 0.98 || y < 0.02 || y > 0.98;
    x = Math.max(0.03, Math.min(0.97, x));
    y = Math.max(0.06, Math.min(0.94, y));

    el.style.display = 'block';
    el.style.left = `${x * w}px`;
    el.style.top = `${y * h}px`;
    el.textContent = off ? (x < 0.5 ? '\u25c0' : '\u25b6') : `\u25bc ${Math.round(dist)}m`;
    el.style.opacity = dist < 4 ? Math.max(0, (dist - 2.2) / 1.8) : 0.9;
  }
}

function aimStrike() {
  camera.getWorldDirection(fwd);
  fwd.y = 0; fwd.normalize();
  strike.copy(camera.position).addScaledVector(fwd, CFG.strikeAhead);
}

function resolveHit() {
  aimStrike();

  // Counsel himself is deliberately NOT a target. He is a person rather than a
  // document, the stamp indexes documents, and swinging at him is the joke:
  // the round is a dodge, and the one tool you have does not solve it for you.

  // Objections are checked first and win ties outright. They are the only thing
  // on the floor that can take a number off the board, so when one is inside
  // the same swing as an exhibit, overruling it is always the better play and
  // the game should not make the player fight its target selection to get it.
  let obj = null, objD = Infinity;
  for (const e of state.objections) {
    if (!e.alive) continue;
    tmpV.copy(e.root.position).sub(strike);
    tmpV.y = 0;
    const d = tmpV.length();
    if (d > CFG.strikeRadius + e.o.radius) continue;
    if (d < objD) { objD = d; obj = e; }
  }
  if (obj) {
    obj.alive = false;
    obj.dead = 0;
    obj.run.fadeOut(0.08);
    obj.hit.reset().play();
    state.overruled += 1;
    warn(`${obj.o.label} overruled`);
    sfx.overruled();
    state.lastProbe = { at: performance.now(), nearest: objD, hit: true,
                        overruled: true };
    updateHud();
    return true;
  }

  let best = null, bestD = Infinity;
  for (const e of state.enemies) {
    if (!e.alive) continue;
    tmpV.copy(e.root.position).sub(strike);
    tmpV.y = 0;
    const d = tmpV.length();
    // the binder is a wider target than a single sheet, and reads that way
    if (d > CFG.strikeRadius + CFG.enemyRadius * e.v.radius) continue;
    if (d < bestD) { bestD = d; best = e; }
  }
  state.lastProbe = { at: performance.now(), nearest: bestD, hit: !!best };
  if (!best) return false;
  best.alive = false;
  best.dead = 0;
  best.restPos.copy(best.root.position);
  best.run.fadeOut(0.08);
  best.hit.reset().play();
  state.score += 1;
  // The trap: Bates-stamping the privilege paper indexes it for production, so
  // an unredacted one goes out to the other side. It still files -- that is
  // what makes it a mistake rather than a miss.
  if (best.kind === 'privilege' && !best.redacted) {
    state.waived = true;
    warn('Privilege WAIVED — you produced it unredacted');
    sfx.sustained();
  }
  updateHud();
  return true;
}

function updateHud() {
  if (state.phase === 'bonus') {
    const b = state.boss;
    const survived = b ? b.dodged + (b.deflected || 0) : 0;
    els.scoreLabel.textContent = 'SURVIVED';
    els.score.textContent = `${survived}`;
    els.score.classList.toggle('struck', state.binderHits > 0);
    els.remaining.textContent = survived >= CFG.tierLawyer
      ? 'lawyer of the year'
      : survived >= CFG.tierSuper ? `super lawyer · ${CFG.tierLawyer} for the plaque`
      : `${CFG.tierSuper} for super lawyer`;
    return;
  }
  els.scoreLabel.textContent = 'FILED';
  const total = state.enemies.length;
  els.score.textContent = `${state.filed} / ${total}`;
  const left = state.enemies.filter((e) => e.alive).length;
  // an exhibit that has been struck is loose again as far as the binder is
  // concerned, so it is not "in flight" -- only count the ones still travelling
  const inFlight = Math.max(0, state.score - state.filed - state.struck);
  els.remaining.textContent = state.closing > 0 ? 'binder closing — hold it'
    : left > 0 ? `${left} document${left === 1 ? '' : 's'} at large`
    : inFlight > 0 ? 'filing…'
    : state.struck > 0 ? `${state.struck} struck from the record`
    : 'binder complete';
  els.score.classList.toggle('struck', state.struck > 0);
}

/** A one-line callout: which objection, and what it just did. */
let warnTimer = null;
function warn(text) {
  els.warn.textContent = text;
  els.warn.classList.add('on');
  clearTimeout(warnTimer);
  warnTimer = setTimeout(() => els.warn.classList.remove('on'), 2200);
}

// What a man says when a discovery binder hits him in a dream about work.
// Grawlixes rather than words: it is funnier, it is in the register of the
// rest of the game, and it is the version you can put in a CLE presentation.
const SWEARS = ['#*%!?', '%!**!', '@#$%&!', '*&%$#@', '$#@*!!', '#@!*%&?',
                '&%$#@!', '!?#*%'];

/**
 * Put one in the bubble. `force` jumps the queue for a hit, so being clobbered
 * always says something even if he only just muttered.
 */
let swearTimer = null;
function swear(force) {
  if (!force && state.t < state.swearT) return;
  state.swearT = state.t + 2.2;
  els.swear.textContent = SWEARS[Math.floor(Math.random() * SWEARS.length)];
  els.swear.classList.add('on');
  clearTimeout(swearTimer);
  swearTimer = setTimeout(() => els.swear.classList.remove('on'), 1500);
}
state.swear = swear;

/** The bigger, slower card that announces a phase change. */
let bannerTimer = null;
function banner(title, sub) {
  els.bannerTitle.textContent = title;
  els.bannerSub.textContent = sub || '';
  els.banner.classList.add('on');
  clearTimeout(bannerTimer);
  bannerTimer = setTimeout(() => els.banner.classList.remove('on'), 3400);
}

function updateClock(dt) {
  if (state.done) return;
  state.clock = Math.max(0, state.clock - dt);
  const s = Math.ceil(state.clock);
  els.clock.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  els.clock.classList.toggle('low', state.clock <= CFG.dreamPanic);
  // the wake clock becomes audible once it goes orange
  if (s !== state.lastTickS) {
    state.lastTickS = s;
    if (state.clock > 0 && state.clock <= CFG.dreamPanic) sfx.tick();
  }
  if (state.clock === 0) finish(false);
}

// You do not win or lose a case, you get a ruling. The binder you assembled is
// the evidentiary record you walk into court with, so the outcome is graded on
// it: a complete binder wins, and every exhibit still loose in the pile is one
// you cannot authenticate. Filing three of four used to be indistinguishable
// from filing none, which made partial competence invisible.
const VERDICTS = [
  { tag: 'Judgment for the plaintiff', head: 'You lose the case.',
    body: 'You walk in with an empty binder. Nothing is Bates-stamped, nothing '
      + 'is indexed, and nothing you try to put in front of the jury survives '
      + 'an objection. The court finds for the plaintiff on every count and '
      + 'invites a fee motion.' },
  { tag: 'Judgment for the plaintiff', head: 'You lose the case.',
    body: 'One exhibit is in order. The rest are loose paper, and loose paper '
      + 'is not evidence — opposing counsel objects to each one in turn and is '
      + 'sustained each time. Judgment for the plaintiff, and the court has '
      + 'notes about your preparation.' },
  { tag: 'Directed verdict, in part', head: 'You lose the case.',
    body: 'Half a binder. Enough to survive the morning, not enough to survive '
      + 'the afternoon: the exhibits you never stamped are the ones the whole '
      + 'theory rested on. The court directs a verdict against you on the '
      + 'counts you could not document.' },
  { tag: 'Adverse inference', head: 'You lose the case — barely.',
    body: 'Three of four. Every exhibit you filed comes in clean, and the one '
      + 'you did not becomes the only thing anyone remembers. The jury is '
      + 'instructed it may infer the missing document said exactly what the '
      + 'plaintiff claims it said. It does.' },
  { tag: 'Verdict for the defense', head: 'You win the case.',
    body: 'Every page stamped, numbered and in order. Each exhibit goes in '
      + 'without a single sustained objection, because there is nothing to '
      + 'object to. The court finds for the defense — and you have absolutely '
      + 'no memory of doing the work.' },
];

// Above the verdict table entirely: you do not get here by winning the case, you
// get here by winning it early enough that opposing counsel tried to end it
// without a trial, and then numbering every page of the motion they filed.
const LAWYER_OF_THE_YEAR = {
  tag: 'Motion denied · Lawyer of the Year',
  head: 'You wake up famous.',
  body: 'The binder was closed with time to spare, so opposing counsel came '
      + 'down the corridor himself and threw his entire discovery production at '
      + 'your head for thirty seconds. You are still standing and most of it is '
      + 'on the carpet behind you. The motion is denied in a two-line order, the '
      + 'case is yours, and somebody has put your name on a plaque in a hotel '
      + 'ballroom. You still cannot remember doing any of it.',
};

// Second place, and the one most players who take the round seriously will
// actually see: you stayed on your feet, you just were not perfect.
const SUPER_LAWYER = {
  tag: 'Motion denied · Super Lawyer',
  head: 'You wake up respected.',
  body: 'Opposing counsel threw his entire discovery production at your head '
      + 'and most of it went past you. The motion is denied, the case is '
      + 'yours, and a magazine nobody reads puts you on a list of people to '
      + 'watch. Not the plaque. A list.',
};

// And the floor. Being hit by that many binders in thirty seconds is not bad
// luck, it is a pattern of conduct.
const DISBARRED = {
  tag: 'In re Rexington · disbarment',
  head: 'You wake up unemployed.',
  body: 'You stood in a corridor while a man threw thirty seconds of discovery '
      + 'at you and you barely moved. Someone filmed it. The binder you '
      + 'assembled is immaculate and it does not matter, because the panel has '
      + 'seen the footage and the question before it was never really about '
      + 'the exhibits.',
};

// Endings that beat the verdict table because what you did is a better story
// than how many exhibits you filed. Each one hangs off something already
// counted, so they are all reachable by playing badly on purpose -- which is
// the only reason anyone replays a two-minute game.
//
// Checked in order, and none of them outrank Lawyer of the Year: that one is
// earned, these are mostly self-inflicted.
const SPECIALS = [
  {
    when: (s) => s.overRedacted >= 3,
    tag: 'In re Exhibitfy · sanctions',
    head: 'You produced a binder of black rectangles.',
    body: 'Somewhere in there was a case. You redacted almost all of it, on no '
        + "instruction from anybody, and what went over was a stack of pages "
        + 'redacted edge to edge. Opposing counsel filed a motion to compel '
        + 'that is four words long. The court granted it from the bench.',
  },
  {
    when: (s) => s.misses >= 8 && s.filed <= 2,
    tag: 'Facilities has questions',
    head: 'You Bates-stamped the building.',
    body: 'The carpet is numbered. The doorframes are numbered. A banker\'s box '
        + 'is numbered twice. Of the documents that were actually supposed to '
        + 'be indexed you got a couple, and the rest of the sequence is '
        + 'distributed across the fourth floor in a way the property manager '
        + 'describes as "deliberate".',
  },
  {
    when: (s) => s.score === 0 && s.dryStamps === 0 && s.misses === 0,
    tag: 'No appearance entered',
    head: 'You just walked around.',
    body: 'Two minutes, a loaded Bates stamp, eight documents actively '
        + 'fleeing from you, and not one swing. The binder is as empty as it '
        + 'was when you fell asleep. Opposing counsel, who prepared, is having '
        + 'a lovely morning.',
  },
];

/** Which ruling a binder of `filed` out of `total` earns. */
function verdictFor(filed, total) {
  const k = Math.max(0, Math.min(1, filed / Math.max(1, total)));
  return VERDICTS[Math.round(k * (VERDICTS.length - 1))];
}

/**
 * The whole ending decision, in one place and out of finish().
 *
 * Same reason verdictFor came out: finish() calls controls.unlock(), which stops
 * the update loop, so it can only ever fire once per page load and testing five
 * outcomes against it tests one.
 */
function endingFor(s, total) {
  if (s.bonusWon) return LAWYER_OF_THE_YEAR;
  // The tiers outrank the joke endings and the verdict table alike: what
  // happened in that corridor is the most recent and most vivid thing about
  // this dream. Disbarment beats a won case on purpose -- the binder being
  // perfect is the joke, not a defence.
  if (s.bonusTier === 'super') return SUPER_LAWYER;
  if (s.bonusTier === 'disbarred') return DISBARRED;
  return SPECIALS.find((sp) => sp.when(s)) || verdictFor(s.filed, total);
}
state.verdictFor = verdictFor;
state.endingFor = endingFor;
state.VERDICTS = VERDICTS;
state.SPECIALS = SPECIALS;

/**
 * Put the office back and deal another round, without a page load.
 *
 * "File another binder" used to be `location.reload()`, which re-fetched about
 * 12 MB to rebuild a scene that was already sitting in memory: several seconds
 * of black screen between two rounds of a two-minute game, and on a
 * projector's wifi rather longer than that. Everything below is scene state,
 * so all of it can simply be wound back.
 *
 * The invariant to keep: anything a round mutates has to be listed here. That
 * is the cost of not reloading, and it is why the pods, the decals and the
 * redaction materials are all handled explicitly rather than trusted to come
 * back on their own.
 */
function restart() {
  // ---- a wake still in flight is torn down before another one is started
  if (state.waking || state.wakeDesk) finishWake();

  // ---- the boss and any objections leave with the round that made them
  if (state.boss) {
    scene.remove(state.boss.root);
    state.boss = null;
  }
  for (const o of state.objections) scene.remove(o.root);
  state.objections.length = 0;
  for (const p of state.binders || []) scene.remove(p.root);
  state.binders = [];
  closeArena();

  // ---- the documents go back to their spawns, un-redacted
  state.enemies.forEach((e, i) => {
    const spawn = LAYOUT.spawns[i % LAYOUT.spawns.length];
    e.root.position.set(spawn[0], 0, spawn[1]);
    e.root.rotation.set(0, Math.random() * Math.PI * 2, 0);
    e.root.scale.copy(e.baseScale);
    e.root.visible = true;
    e.heading = e.root.rotation.y;
    e.alive = true;
    e.filed = false;
    e.dead = 0;
    if (e.redacted) {
      // Restore the material the redaction replaced, and drop the clone it
      // made -- the GPU keeps every texture it is handed until told otherwise,
      // and a restart per round would accumulate them.
      e.root.traverse((o) => {
        if (!o.isMesh || o.userData.mat0 === undefined) return;
        for (const m of [].concat(o.material)) {
          if (![].concat(o.userData.mat0).includes(m)) m.dispose();
        }
        o.material = o.userData.mat0;
      });
      e.redacted = false;
    }
    e.hit.stop();
    e.run.reset().play();
  });

  // ---- ink pods come back standing, beacons lit
  for (const p of state.pods) {
    p.live = true;
    p.cooldown = 0;
    p.root.visible = true;
    if (p.beacon) p.beacon.visible = true;
  }

  // ---- the carpet is clean again, but the numbering carries on: the stamp
  // does not rewind just because you woke up
  for (const d of DECALS.list) {
    scene.remove(d);
    d.material.map.dispose();
    d.material.dispose();
  }
  DECALS.list.length = 0;

  // ---- counters
  Object.assign(state, {
    score: 0, filed: 0, done: false, clock: CFG.dreamTime,
    swinging: false, swingT: 0, hitDone: false, swingDry: false,
    ink: CFG.inkMax, dryStamps: 0,
    struck: 0, overruled: 0, sustained: 0, nextObj: CFG.objFirst,
    redactions: 0, overRedacted: 0, privilegeSaved: false, waived: false,
    misses: 0, closing: 0, closeBroken: 0,
    phase: 'case', bossHits: 0, binderHits: 0, bonusWon: false,
    bonusGranted: false, deflects: 0, deflectReady: true, survived: 0,
    bonusTier: null,
    caseWon: false, timeLeft: 0, kick: 0, shake: 0, rolled: false,
  });
  state.round = (state.round || 0) + 1;   // fences timers owned by the last one
  if (state.swing) state.swing.stop();

  // ---- back to the door you came in by
  camera.position.set(0, CFG.eyeHeight, 1.2);
  camera.rotation.set(0, 0, 0);
  camera.fov = VIEW_FOV;
  camera.updateProjectionMatrix();
  if (state.arms) fitView();

  // ---- chrome
  els.wake.classList.remove('on');
  els.wake.hidden = true;
  els.banner.classList.remove('on');
  els.warn.classList.remove('on');
  els.score.classList.remove('struck');
  els.scoreLabel.textContent = 'FILED';
  els.clockLabel.textContent = 'until you wake';
  els.clock.classList.remove('low');
  updateHud();
  updateInk();
  updateClock(0);

  // The bed was faded out and switched off by finish(); start it again from
  // the top rather than trying to resume a chain that has already ended.
  MUSIC.on = false;
  startMusic();
  musicTo(MUSIC.level, 0.8);
}
state.restart = restart;
state.finishRef = finish;
state.settleBonusRef = settleBonus;

/**
 * The dream lets go — either because the binder is closed, or because the night
 * ran out and closed it for you. Either way you are due in court.
 */
function finish(complete, fromBonus) {
  if (state.done) return;
  // Closing the binder with time to spare does not end the round -- it earns
  // one. Only reachable from the case phase, so the bonus cannot recurse.
  if (complete && !fromBonus && state.phase === 'case'
      && state.clock >= CFG.bonusAt) {
    startBonus();
    return;
  }
  state.done = true;
  // Whoever got here, if it was during the bonus the round still has to be
  // scored -- see scoreBonus.
  if (state.phase === 'bonus' && !state.bonusTier) {
    scoreBonus();
    state.bonusWon = state.bonusTier === 'lawyer';
  }
  // pull the bed down so the sting lands in the clear, then let it go
  musicTo(MUSIC.level * 0.28, 0.5);
  sfx.sting(complete);
  // Tagged with the round it belongs to. Restarting inside this 900 ms is easy
  // -- the wake screen is up and the button is right there -- and an untagged
  // timeout would then switch off a bed the new round had just started, once,
  // unreproducibly, and only for players who click fast.
  const round = state.round;
  setTimeout(() => {
    if (state.round !== round) return;
    musicTo(0, 2.2);
    MUSIC.on = false;
  }, 900);

  const total = state.enemies.length;
  const v = endingFor(state, total);
  els.wakeTag.textContent = v.tag;
  els.wakeHead.textContent = v.head;
  let body = v.body;
  if (!complete) body += ` You woke with ${state.filed} of ${total} filed.`;
  // The bonus can only be lost, never the case: say so plainly, because losing
  // a round you were awarded for winning reads as a punishment otherwise.
  if (state.phase === 'bonus') {
    const n = state.binderHits;
    const d = state.deflects;
    body += ` You closed the binder ${Math.round(state.timeLeft)}s early, which`
          + ' brought opposing counsel down the corridor in person with an'
          + ` armful of discovery: ${state.survived} of them went past you`
          + (d > 0 ? `, ${d} swatted out of the air with the stamp` : '')
          + (n > 0 ? `, and ${n} did not.` : ', and none of them landed.');
    if (state.bonusTier !== 'disbarred') {
      body += ' The verdict on the binder stands.';
    }
  }
  if (state.struck > 0) {
    body += ` ${state.struck} exhibit${state.struck === 1 ? ' was' : 's were'} `
          + `struck from the record on ${state.sustained} sustained `
          + `objection${state.sustained === 1 ? '' : 's'}`
          + (state.overruled > 0
              ? `; you overruled ${state.overruled}.` : '.');
  } else if (state.overruled > 0) {
    body += ` You overruled ${state.overruled} objection`
          + `${state.overruled === 1 ? '' : 's'} and lost nothing to any of them.`;
  }
  if (state.dryStamps > 0) {
    body += ` ${state.dryStamps} swing${state.dryStamps === 1 ? '' : 's'} came `
          + 'down on a dry stamp and left nothing but an impression.';
  }
  if (state.waived) {
    body += ' The privilege log is a formality now: you Bates-stamped the '
          + 'attorney-client memo and produced it unredacted, so it is theirs, '
          + 'it is admissible, and it is going in their opening.';
  } else if (state.privilegeSaved) {
    body += ' The privileged memo went out redacted to the margins, which is '
          + 'the one thing here nobody can complain about.';
  }
  if (state.overRedacted > 0) {
    body += ` You also blacked out ${state.overRedacted} document`
          + `${state.overRedacted === 1 ? '' : 's'} that nobody had asked you `
          + 'to redact.';
  }
  els.wakeBody.textContent = body;
  els.wake.hidden = false;
  // let the last document land before the room dissolves
  setTimeout(() => {
    els.wake.classList.add('on');
    controls.unlock();
  }, 700);
}

// ---------------------------------------------------------------- loop
const vel = new THREE.Vector3();
const clock = new THREE.Clock();

function updatePlayer(dt) {
  const k = state.keys;

  // The arrows are the 1992 scheme on purpose: up/down walk, LEFT/RIGHT TURN.
  // WASD strafes and needs the mouse to turn, which is the whole difficulty --
  // walk into a corridor that bends and "forward" stops meaning forward, so you
  // grind along a wall wondering why W changed direction. Turning on the
  // keyboard means the corridor is always ahead of you. Both schemes are live
  // at once; nobody has to be told which one they are using.
  if (k.ArrowLeft) camera.rotation.y += CFG.turnSpeed * dt;
  if (k.ArrowRight) camera.rotation.y -= CFG.turnSpeed * dt;

  // A turn under way outranks the keys -- see faceNearest.
  if (state.snap) {
    const step = Math.min(1, dt / CFG.snapTurn);
    camera.rotation.y += state.snap.left * step;
    state.snap.left -= state.snap.left * step;
    if (Math.abs(state.snap.left) < 0.002) state.snap = null;
  }

  const wish = new THREE.Vector3(
    (k.KeyD ? 1 : 0) - (k.KeyA ? 1 : 0), 0,
    (k.KeyS ? 1 : 0) - (k.KeyW ? 1 : 0)
    + (k.ArrowDown ? 1 : 0) - (k.ArrowUp ? 1 : 0));
  if (wish.lengthSq() > 0) wish.normalize();

  // The stick is analogue and overrides the keys when it is being held: a
  // phone can ask for half speed, which no combination of WASD can express.
  let push = 1.0;
  if (TOUCH && STICK.id !== null) {
    const m = Math.min(1, Math.hypot(STICK.dx, STICK.dy));
    if (m > 0.12) {
      wish.set(STICK.dx, 0, STICK.dy).normalize();
      push = m;
    } else {
      wish.set(0, 0, 0);
    }
  }

  // camera-relative, flattened
  const yaw = new THREE.Euler(0, camera.rotation.y, 0, 'YXZ');
  wish.applyEuler(yaw);

  // Sprint is the far end of the stick rather than a second control there is
  // no thumb left for.
  const sprinting = (k.ShiftLeft || k.ShiftRight)
    || (TOUCH && push > 0.86);
  const speed = (sprinting ? CFG.sprint : CFG.walk) * (TOUCH ? push : 1);
  vel.x += (wish.x * speed - vel.x) * Math.min(1, CFG.accel * dt);
  vel.z += (wish.z * speed - vel.z) * Math.min(1, CFG.accel * dt);
  if (wish.lengthSq() === 0) {
    const f = Math.max(0, 1 - CFG.friction * dt);
    vel.x *= f; vel.z *= f;
  }

  const move = resolveMove(camera.position, vel.x * dt, vel.z * dt);
  camera.position.x += move.dx;
  camera.position.z += move.dz;
  if (move.dx === 0) vel.x = 0;
  if (move.dz === 0) vel.z = 0;

  // head bob, scaled by how fast we are actually moving
  const sp = Math.hypot(vel.x, vel.z);
  state.bobT = (state.bobT || 0) + dt * sp * 2.4;
  camera.position.y = CFG.eyeHeight + Math.sin(state.bobT * 2) * 0.022 * Math.min(1, sp / CFG.walk);
  // one frame of history, which is all the lead aim needs
  state.lastX = camera.position.x - vel.x * dt;
  state.lastZ = camera.position.z - vel.z * dt;
}

function updateEnemies(dt) {
  for (const e of state.enemies) {
    if (!e.alive) {
      e.dead += dt;
      e.mixer.update(dt);
      if (!e.filed && e.dead >= CFG.fileDelay) {
        const k = Math.min(1, (e.dead - CFG.fileDelay) / CFG.fileTime);
        const ease = k * k * (3 - 2 * k);
        // home on the binder you are carrying, just below the eye
        fileTo.copy(camera.position);
        fileTo.y -= 0.5;
        e.root.position.lerpVectors(e.restPos, fileTo, ease);
        e.root.position.y += Math.sin(ease * Math.PI) * 0.7;   // arc up
        e.root.rotation.y = e.heading + ease * Math.PI * 2;    // and tumble
        e.root.scale.copy(e.baseScale).multiplyScalar(1 - ease * 0.88);
        if (k >= 1) {
          e.filed = true;
          e.root.visible = false;
          state.filed += 1;
          sfx.file();
          updateHud();
        }
      }
      continue;
    }
    tmpV.copy(e.root.position).sub(camera.position);
    tmpV.y = 0;
    const dist = tmpV.length();
    const flee = CFG.enemyFlee * e.v.flee;
    const fleeing = dist < flee;

    let want = e.heading;
    if (fleeing) {
      // Face directly away. The model runs towards its local -Z, so a node at
      // heading h moves along (-sin h, -cos h); to travel along +tmpV (player
      // to enemy, extended) the heading must negate both components. With the
      // un-negated atan2 every "fleeing" document marched straight into the
      // stamp -- measured 2.39 m closing to 0.82 m over four stationary
      // seconds before this sign flip, and 2.74 m opening to 4.46 m after.
      want = Math.atan2(-tmpV.x, -tmpV.z);
      // the privilege paper does not flee honestly -- it weaves
      if (e.v.weave) want += Math.sin(state.t * e.v.weave.rate + e.phase) * e.v.weave.amp;
    } else {
      want = e.heading + Math.sin(state.t * 0.4 + e.phase) * 0.5;
    }
    // shortest-arc turn
    let diff = ((want - e.heading + Math.PI) % (Math.PI * 2)) - Math.PI;
    if (diff < -Math.PI) diff += Math.PI * 2;
    const turn = CFG.enemyTurn * e.v.turn;
    e.heading += THREE.MathUtils.clamp(diff, -turn * dt, turn * dt);

    // the enemy model runs towards -Z, so heading is its facing directly
    const base = CFG.enemySpeed * e.v.speed;
    const sp = fleeing ? base : base * 0.42;
    const dx = -Math.sin(e.heading) * sp * dt;
    const dz = -Math.cos(e.heading) * sp * dt;
    const mv = resolveMove(e.root.position, dx, dz);
    if (mv.dx === 0 && mv.dz === 0) {
      e.heading += 2.2 * dt;                     // cornered: turn until free
    }
    e.root.position.x += mv.dx;
    e.root.position.z += mv.dz;
    e.root.rotation.y = e.heading;
    // The clip is played at 0.55 speed when it is only milling about, so the
    // footfalls have to stretch by the same factor or the feet and the sound
    // walk at different speeds.
    const rate = fleeing ? 1.0 : 0.55;
    e.mixer.update(dt * rate);
    footfall(e, e.v.stride, dt * rate, sfx.step);
  }
}

/**
 * Tick an entity's stride and fire `snd` on each footfall.
 *
 * A stride is two steps, and `stride` is the Run clip's own length in frames at
 * 30 fps, so the sound is locked to the bake rather than to a number picked by
 * ear: change the clip and the audio follows.
 */
function footfall(e, strideFrames, dt, snd) {
  const half = strideFrames / 60;
  e.stepT = (e.stepT || Math.random() * half) + dt;
  if (e.stepT < half) return;
  e.stepT -= half;
  snd(e.root.position.x, e.root.position.z);
}

function updateSwing(dt) {
  if (!state.swinging) return;
  state.swingT += dt;
  if (!state.hitDone && state.swingT >= CFG.swingImpact) {
    state.hitDone = true;
    if (state.swingDry) {
      // The die still lands -- it just has no ink on it, so nothing is filed
      // however well aimed the swing was. Aim is not the failure here, supply
      // is, and the ghost impression on the carpet says so.
      state.dryStamps += 1;
      aimStrike();
      sfx.dry();
      swear();
      stampCarpet(strike.x, strike.z, camera.rotation.y, true);
      state.kick = 0.45;
      updateInk();
    } else {
      const hit = resolveHit();    // leaves `strike` at the impact point
      if (!hit) state.misses += 1;
      sfx.stamp(hit);
      stampCarpet(strike.x, strike.z, camera.rotation.y, false);
      state.kick = 1;
      if (hit) {
        els.reticle.classList.add('hit');
        setTimeout(() => els.reticle.classList.remove('hit'), 130);
      }
    }
  }
  if (state.swingT >= CFG.swingDuration) {
    state.swinging = false;
    state.swing.stop();
  }
}

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.05);
  state.t += dt;
  if (state.ready && running()) {
    if (state.phase === 'bonus') {
      updateBonusClock(dt);
      updatePlayer(dt);
      updateSwing(dt);
      updateObjections(dt);      // he keeps calling them
      updateBoss(dt);
      updateBinders(dt);
      updatePods(dt);
    } else {
      updateClock(dt);
      updatePlayer(dt);
      updateSwing(dt);
      updateEnemies(dt);
      updateObjections(dt);
      updateClosing(dt);
      updatePods(dt);
    }
  }
  if (state.waking) updateWake(dt);
  updateMarkers();
  if (state.armMixer) state.armMixer.update(dt);
  pumpMusic();

  // impact kick: a pinch of world FOV and a dip of the arms, decaying fast.
  // The world camera's fov is otherwise never touched, so writing it only
  // while the kick is live cannot fight the resize handler.
  if (state.kick) {
    state.kick = state.kick < 0.002 ? 0 : state.kick * Math.exp(-9 * dt);
    camera.fov = (state.baseFov || 70) + state.kick * 2.4;
    camera.updateProjectionMatrix();
    if (state.arms) state.arms.position.y = state.armsBaseY - state.kick * 0.010;
  }
  // A sustained objection shakes the view. It is the only thing that takes a
  // number off the board, so it gets the only camera effect the player does not
  // cause themselves -- rotational, not positional, so it cannot push the eye
  // through a wall.
  if (state.shake) {
    state.shake = state.shake < 0.002 ? 0 : state.shake * Math.exp(-6 * dt);
    const a = state.shake * 0.020;
    camera.rotation.z = Math.sin(state.t * 47.0) * a;
    state.rolled = true;
    if (!state.shake) { camera.rotation.z = 0; state.rolled = false; }
  } else if (state.rolled) {
    // Clear the roll once, on the frame the shake ends -- not every frame
    // forever. Writing a single Euler component re-derives the whole camera
    // quaternion from the decomposed Euler, so an unconditional `rotation.z = 0`
    // silently destroys any roll another system introduced. It was harmless
    // here only because PointerLockControls keeps z at zero anyway.
    camera.rotation.z = 0;
    state.rolled = false;
  }

  renderer.render(scene, camera);
  renderer.autoClear = false;         // draw the viewmodel over the world
  renderer.clearDepth();
  renderer.render(viewScene, viewCamera);
  renderer.autoClear = true;
}
animate();
