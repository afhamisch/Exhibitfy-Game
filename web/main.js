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
  dreamTime: 90,
  dreamPanic: 20,         // the countdown goes orange under this

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
const VARIANTS = {
  pleading:  { speed: 1.00, flee: 1.00, turn: 1.00, radius: 1.00 },
  privilege: { speed: 0.92, flee: 1.30, turn: 1.25, radius: 0.97,
               weave: { rate: 2.3, amp: 0.85 } },
  binder:    { speed: 0.49, flee: 0.80, turn: 0.55, radius: 1.16 },
  stack:     { speed: 1.36, flee: 1.15, turn: 1.35, radius: 1.04 },
};

// One of each, so every silhouette is on the floor to be told apart.
const ROSTER = ['pleading', 'privilege', 'binder', 'stack'];

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
               strikes: 1, after: 1, weight: 3 },
  character: { label: 'Character evidence', speed: 1.70, turn: 3.4,
               radius: 0.29, strikes: 1, after: 2, weight: 2,
               weave: { rate: 1.9, amp: 0.55 } },
  rule403:   { label: 'Rule 403', speed: 2.00, turn: 2.0, radius: 0.34,
               strikes: 2, after: 3, weight: 1 },
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
  halls: [
    { x: 0, z: 0, rot: 0 }, { x: 0, z: -4, rot: 0 }, { x: 0, z: -8, rot: 0 },
    { x: -4, z: -12, rot: Math.PI / 2 }, { x: -8, z: -12, rot: Math.PI / 2 },
    { x: -12, z: -8, rot: 0 }, { x: -12, z: -4, rot: 0 },
    { x: -12, z: 0, rot: 0 },
  ],
  // rot PI  -> enter from +Z, leave towards -X
  // rot -90 -> enter from +X, leave towards +Z
  corners: [
    { x: 0, z: -12, rot: Math.PI },
    { x: -12, z: -12, rot: -Math.PI / 2 },
  ],
  props: [
    { kind: 'file_cabinet', x: 0.92, z: -3.4, rot: -Math.PI / 2 },
    { kind: 'banker_boxes', x: -0.85, z: -7.4, rot: 0.24 },
    { kind: 'desk_chair', x: -6.2, z: -13.2, rot: Math.PI },
    { kind: 'reception_counter', x: -10.9, z: -5.6, rot: Math.PI / 2 },
    { kind: 'banker_boxes', x: -9.6, z: -10.9, rot: -0.5 },
    { kind: 'file_cabinet', x: -12.9, z: -2.0, rot: Math.PI / 2 },
  ],
  // caps on the two dead ends
  doors: [
    { x: 0, z: 2.0, rot: 0 },
    { x: -12, z: 2.0, rot: 0 },
  ],
  spawns: [[0, -6], [-5.5, -12], [-12, -6], [-1.0, -10.5], [-9.5, -12]],
  // Ink pods, pushed out to the far ends and the two corners rather than sat
  // along the route you would walk anyway. A pod you pass over for free is not
  // a decision; these cost you the length of a corridor.
  pods: [
    [0.55, -10.6],       // near the first corner
    [-11.4, -11.2],      // the far corner
    [0.0, 0.9],          // back at the entrance you started from
    [-12.0, -1.0],       // the opposite dead end
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

function insideWalk(x, z) {
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

addEventListener('resize', () => {
  camera.aspect = viewCamera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  viewCamera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

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
  remaining: document.getElementById('remaining'),
  warn: document.getElementById('warn'),
  inkBox: document.getElementById('inkbox'),
  inkFill: document.getElementById('inkfill'),
  inkLabel: document.getElementById('inklabel'),
  wake: document.getElementById('wake'),
  wakeTag: document.getElementById('wake-tag'),
  wakeHead: document.getElementById('wake-head'),
  wakeBody: document.getElementById('wake-body'),
  clock: document.getElementById('clock'),
  clockBox: document.getElementById('wakeclock'),
};

const state = {
  ready: false, score: 0, filed: 0, done: false, t: 0, clock: CFG.dreamTime,
  swinging: false, swingT: 0, hitDone: false,
  ink: CFG.inkMax, dryStamps: 0,
  enemies: [], pods: [], objections: [],
  struck: 0, overruled: 0, sustained: 0, nextObj: CFG.objFirst,
  closing: 0, closeBroken: 0,
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
  const [hallG, cornerG, doorG, viewG, enemyG, ...propGs] = await Promise.all([
    load(`${ASSETS}/environment/hallway_straight.glb`),
    load(`${ASSETS}/environment/hallway_corner.glb`),
    load(`${ASSETS}/environment/doorway.glb`),
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

  // ---- office
  for (const h of LAYOUT.halls) scene.add(place(hallG.scene.clone(true), h.x, h.z, h.rot));
  for (const c of LAYOUT.corners) scene.add(place(cornerG.scene.clone(true), c.x, c.z, c.rot));
  for (const d of LAYOUT.doors) scene.add(place(doorG.scene.clone(true), d.x, d.z, d.rot));
  for (const p of LAYOUT.props) {
    scene.add(place(props[p.kind].clone(true), p.x, p.z, p.rot));
  }

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
                      live: true, cooldown: 0, phase: i * 1.4 });
  });

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

function envGain(t0, attack, peak, decay) {
  const g = AC.createGain();
  g.gain.setValueAtTime(0, t0);
  g.gain.linearRampToValueAtTime(peak, t0 + attack);
  g.gain.exponentialRampToValueAtTime(0.0008, t0 + attack + decay);
  g.connect(master);
  return g;
}

function noiseBuf() {
  if (noiseBuf.b) return noiseBuf.b;
  const b = AC.createBuffer(1, AC.sampleRate, AC.sampleRate);
  const d = b.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  return (noiseBuf.b = b);
}

function playNoise(t0, dur, type, f0, f1, peak, q = 1.0) {
  const src = AC.createBufferSource();
  src.buffer = noiseBuf();
  const flt = AC.createBiquadFilter();
  flt.type = type;
  flt.Q.value = q;
  flt.frequency.setValueAtTime(f0, t0);
  flt.frequency.exponentialRampToValueAtTime(Math.max(40, f1), t0 + dur);
  src.connect(flt).connect(envGain(t0, 0.008, peak, dur));
  src.start(t0);
  src.stop(t0 + dur + 0.05);
}

function playTone(t0, dur, type, f0, f1, peak) {
  const o = AC.createOscillator();
  o.type = type;
  o.frequency.setValueAtTime(f0, t0);
  o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t0 + dur);
  o.connect(envGain(t0, 0.004, peak, dur));
  o.start(t0);
  o.stop(t0 + dur + 0.05);
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
state.spawnObjection = spawnObjection;      // for tuning from the console

// ---------------------------------------------------------------- input
els.overlay.addEventListener('click', () => {
  if (state.ready && !state.done) controls.lock();
});
controls.addEventListener('lock', () => {
  initAudio();
  startMusic();
  musicTo(MUSIC.level, 0.6);
  els.overlay.style.display = 'none';
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
document.getElementById('again').addEventListener('click', () => location.reload());
addEventListener('keydown', (e) => { state.keys[e.code] = true; });
addEventListener('keyup', (e) => { state.keys[e.code] = false; });
renderer.domElement.addEventListener('mousedown', (e) => {
  if (e.button === 0 && controls.isLocked) startSwing();
});

function startSwing() {
  if (!state.swing) return;
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
    const r = WALK[Math.floor(Math.random() * WALK.length)];
    const x = r.x0 + Math.random() * (r.x1 - r.x0);
    const z = r.z0 + Math.random() * (r.z1 - r.z0);
    if (!insideWalk(x, z)) continue;
    const d = Math.hypot(x - camera.position.x, z - camera.position.z);
    if (d >= CFG.objSpawnMin) return { x, z };
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
  }
}

/** An objection reached the binder and was sustained. */
function sustain(e) {
  const n = Math.min(state.filed, e.o.strikes);
  state.filed -= n;
  state.struck += n;
  state.sustained += 1;
  e.hit.reset().play();
  sfx.sustained();
  state.shake = 1;
  warn(n > 0
    ? `${e.o.label} sustained — ${n} exhibit${n === 1 ? '' : 's'} struck`
    : `${e.o.label} sustained — nothing in the binder to strike`);
  updateHud();
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

    if (state.ink >= CFG.inkMax) continue;      // full: leave it standing
    tmpV.copy(p.home).sub(camera.position);
    tmpV.y = 0;
    if (tmpV.length() > CFG.podRadius) continue;
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
function aimStrike() {
  camera.getWorldDirection(fwd);
  fwd.y = 0; fwd.normalize();
  strike.copy(camera.position).addScaledVector(fwd, CFG.strikeAhead);
}

function resolveHit() {
  aimStrike();

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
  updateHud();
  return true;
}

function updateHud() {
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

/** Which ruling a binder of `filed` out of `total` earns. */
function verdictFor(filed, total) {
  const k = Math.max(0, Math.min(1, filed / Math.max(1, total)));
  return VERDICTS[Math.round(k * (VERDICTS.length - 1))];
}
state.verdictFor = verdictFor;
state.VERDICTS = VERDICTS;

/**
 * The dream lets go — either because the binder is closed, or because the night
 * ran out and closed it for you. Either way you are due in court.
 */
function finish(complete) {
  if (state.done) return;
  state.done = true;
  // pull the bed down so the sting lands in the clear, then let it go
  musicTo(MUSIC.level * 0.28, 0.5);
  sfx.sting(complete);
  setTimeout(() => { musicTo(0, 2.2); MUSIC.on = false; }, 900);

  const total = state.enemies.length;
  const v = verdictFor(state.filed, total);
  els.wakeTag.textContent = v.tag;
  els.wakeHead.textContent = v.head;
  let body = v.body;
  if (!complete) body += ` You woke with ${state.filed} of ${total} filed.`;
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
  const wish = new THREE.Vector3(
    (k.KeyD ? 1 : 0) - (k.KeyA ? 1 : 0), 0,
    (k.KeyS ? 1 : 0) - (k.KeyW ? 1 : 0));
  if (wish.lengthSq() > 0) wish.normalize();

  // camera-relative, flattened
  const yaw = new THREE.Euler(0, camera.rotation.y, 0, 'YXZ');
  wish.applyEuler(yaw);

  const speed = (k.ShiftLeft || k.ShiftRight) ? CFG.sprint : CFG.walk;
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
    e.mixer.update(dt * (fleeing ? 1.0 : 0.55));
  }
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
      stampCarpet(strike.x, strike.z, camera.rotation.y, true);
      state.kick = 0.45;
      updateInk();
    } else {
      const hit = resolveHit();    // leaves `strike` at the impact point
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
  if (state.ready && controls.isLocked) {
    updateClock(dt);
    updatePlayer(dt);
    updateSwing(dt);
    updateEnemies(dt);
    updateObjections(dt);
    updateClosing(dt);
    updatePods(dt);
  }
  if (state.armMixer) state.armMixer.update(dt);
  pumpMusic();

  // impact kick: a pinch of world FOV and a dip of the arms, decaying fast.
  // The world camera's fov is otherwise never touched, so writing it only
  // while the kick is live cannot fight the resize handler.
  if (state.kick) {
    state.kick = state.kick < 0.002 ? 0 : state.kick * Math.exp(-9 * dt);
    camera.fov = 70 + state.kick * 2.4;
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
  } else if (camera.rotation.z !== 0) {
    camera.rotation.z = 0;
  }

  renderer.render(scene, camera);
  renderer.autoClear = false;         // draw the viewmodel over the world
  renderer.clearDepth();
  renderer.render(viewScene, viewCamera);
  renderer.autoClear = true;
}
animate();
