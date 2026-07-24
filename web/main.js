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

  enemyCount: 4,
  enemySpeed: 2.45,
  enemyFlee: 7.0,         // starts running when the player is this close
  enemyTurn: 3.2,
};

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
};

const state = {
  ready: false, score: 0,
  swinging: false, swingT: 0, hitDone: false,
  enemies: [],
  keys: Object.create(null),
};

// exposed for tuning and debugging from the console
window.__bates = state;
state.scene = scene;
state.camera = camera;
state.viewScene = viewScene;
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
    load(`${ASSETS}/enemies/enemy_pleading.glb`),
    load(`${ASSETS}/environment/file_cabinet.glb`),
    load(`${ASSETS}/environment/banker_boxes.glb`),
    load(`${ASSETS}/environment/desk_chair.glb`),
    load(`${ASSETS}/environment/reception_counter.glb`),
  ]);
  const props = {
    file_cabinet: propGs[0].scene,
    banker_boxes: propGs[1].scene,
    desk_chair: propGs[2].scene,
    reception_counter: propGs[3].scene,
  };

  // ---- office
  for (const h of LAYOUT.halls) scene.add(place(hallG.scene.clone(true), h.x, h.z, h.rot));
  for (const c of LAYOUT.corners) scene.add(place(cornerG.scene.clone(true), c.x, c.z, c.rot));
  for (const d of LAYOUT.doors) scene.add(place(doorG.scene.clone(true), d.x, d.z, d.rot));
  for (const p of LAYOUT.props) {
    scene.add(place(props[p.kind].clone(true), p.x, p.z, p.rot));
  }

  // ---- viewmodel: authored in view space, so it drops straight in
  const arms = viewG.scene;
  arms.position.set(0.035, -0.075, -0.02);   // clear of the crosshair
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

  // ---- enemies
  for (let i = 0; i < CFG.enemyCount; i++) {
    const g = enemyG.scene.clone(true);
    const spawn = LAYOUT.spawns[i % LAYOUT.spawns.length];
    place(g, spawn[0], spawn[1], Math.random() * Math.PI * 2);
    scene.add(g);
    const mixer = new THREE.AnimationMixer(g);
    const runClip = THREE.AnimationClip.findByName(enemyG.animations, 'Run');
    const hitClip = THREE.AnimationClip.findByName(enemyG.animations, 'Stamped');
    const run = mixer.clipAction(runClip);
    run.play();
    const hit = mixer.clipAction(hitClip);
    hit.setLoop(THREE.LoopOnce, 1);
    hit.clampWhenFinished = true;
    state.enemies.push({
      root: g, mixer, run, hit, alive: true, heading: g.rotation.y, dead: 0,
    });
  }

  state.ready = true;
  els.loading.hidden = true;
  els.go.hidden = false;
  updateHud();
}

boot().catch((err) => {
  els.loading.textContent =
    'Could not load assets — serve the repo root, not web/ (see web/README.md). ' + err;
});

// ---------------------------------------------------------------- input
els.overlay.addEventListener('click', () => { if (state.ready) controls.lock(); });
controls.addEventListener('lock', () => {
  els.overlay.style.display = 'none';
  els.hud.hidden = els.reticle.hidden = false;
});
controls.addEventListener('unlock', () => {
  els.overlay.style.display = 'flex';
  els.hud.hidden = els.reticle.hidden = true;
});
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
  state.swing.reset().play();
}

// ---------------------------------------------------------------- hits
const tmpV = new THREE.Vector3();
const fwd = new THREE.Vector3();

const strike = new THREE.Vector3();

function resolveHit() {
  camera.getWorldDirection(fwd);
  fwd.y = 0; fwd.normalize();
  strike.copy(camera.position).addScaledVector(fwd, CFG.strikeAhead);
  const range = CFG.strikeRadius + CFG.enemyRadius;

  let best = null, bestD = Infinity;
  for (const e of state.enemies) {
    if (!e.alive) continue;
    tmpV.copy(e.root.position).sub(strike);
    tmpV.y = 0;
    const d = tmpV.length();
    if (d > range) continue;
    if (d < bestD) { bestD = d; best = e; }
  }
  state.lastProbe = { at: performance.now(), nearest: bestD, hit: !!best };
  if (!best) return;
  best.alive = false;
  best.dead = 0;
  best.run.fadeOut(0.08);
  best.hit.reset().play();
  state.score += 1;
  updateHud();
}

function updateHud() {
  els.score.textContent = state.score;
  const left = state.enemies.filter((e) => e.alive).length;
  els.remaining.textContent = left === 0
    ? 'all filed — press Esc'
    : `${left} document${left === 1 ? '' : 's'} at large`;
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
      continue;
    }
    tmpV.copy(e.root.position).sub(camera.position);
    tmpV.y = 0;
    const dist = tmpV.length();

    let want = e.heading;
    if (dist < CFG.enemyFlee) {
      want = Math.atan2(tmpV.x, tmpV.z);        // face directly away
    } else {
      want = e.heading + Math.sin(performance.now() * 0.0004 + e.root.id) * 0.5;
    }
    // shortest-arc turn
    let diff = ((want - e.heading + Math.PI) % (Math.PI * 2)) - Math.PI;
    if (diff < -Math.PI) diff += Math.PI * 2;
    e.heading += THREE.MathUtils.clamp(diff, -CFG.enemyTurn * dt, CFG.enemyTurn * dt);

    // the enemy model runs towards -Z, so heading is its facing directly
    const sp = dist < CFG.enemyFlee ? CFG.enemySpeed : CFG.enemySpeed * 0.42;
    const dx = -Math.sin(e.heading) * sp * dt;
    const dz = -Math.cos(e.heading) * sp * dt;
    const mv = resolveMove(e.root.position, dx, dz);
    if (mv.dx === 0 && mv.dz === 0) {
      e.heading += 2.2 * dt;                     // cornered: turn until free
    }
    e.root.position.x += mv.dx;
    e.root.position.z += mv.dz;
    e.root.rotation.y = e.heading;
    e.mixer.update(dt * (dist < CFG.enemyFlee ? 1.0 : 0.55));
  }
}

function updateSwing(dt) {
  if (!state.swinging) return;
  state.swingT += dt;
  if (!state.hitDone && state.swingT >= CFG.swingImpact) {
    state.hitDone = true;
    resolveHit();
  }
  if (state.swingT >= CFG.swingDuration) {
    state.swinging = false;
    state.swing.stop();
  }
}

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.05);
  if (state.ready && controls.isLocked) {
    updatePlayer(dt);
    updateSwing(dt);
    updateEnemies(dt);
  }
  if (state.armMixer) state.armMixer.update(dt);

  renderer.render(scene, camera);
  renderer.autoClear = false;         // draw the viewmodel over the world
  renderer.clearDepth();
  renderer.render(viewScene, viewCamera);
  renderer.autoClear = true;
}
animate();
