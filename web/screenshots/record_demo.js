// Record a demo of the prototype.
//
// SwiftShader renders a few frames a second, so recording in real time gives
// choppy slow-motion footage. Instead: stub requestAnimationFrame so the page
// only advances when we say so, and capture one frame per step. The game already
// clamps its delta with Math.min(dt, 0.05), so one step is always exactly 50 ms
// of game time -- a fixed 20 fps timestep for free, and the result plays back at
// true speed however long the capture actually took.
//
// Frames are JPEG because this ffmpeg build has an mjpeg decoder and no png one,
// concatenated into one file because it has no pipe protocol either.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const { execFileSync } = require('child_process');

const FFMPEG = '/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux';
const OUT = __dirname;
const FPS = 20;
// A ceiling, not a length: the capture stops TAIL frames after the run ends, so
// the reel finishes on the ending screen instead of cutting off mid-fight. A
// full run -- four exhibits, the hold, then eight pages of summary judgment --
// is around 45 s of game time, so give it room and let the ending stop it.
const SECONDS = Number(process.argv[2] || 60);
const FRAMES = Math.round(FPS * SECONDS);
const TAIL = Math.round(FPS * 2.5);
// How many runs to record before settling. The bot wins the bonus round about
// one in three, so recording once means usually recording a loss.
const TRIES = Number(process.argv[3] || 1);
const W = 960, H = 600;

const STUB = () => {
  window.__q = [];
  window.requestAnimationFrame = (cb) => { window.__q.push(cb); return window.__q.length; };
  window.cancelAnimationFrame = () => {};
  window.__step = () => {
    const q = window.__q.slice();
    window.__q.length = 0;
    for (const cb of q) cb(performance.now());
    return q.length;
  };
};

// A bot, not a cinematic: it plays the game, which shows the mechanics off
// better than a scripted camera path and cannot desync from the enemies.
const DEMO = () => {
  const s = window.__bates;
  window.__demo = {
    cool: 0,
    aim(tx, tz) {
      const dx = tx - s.camera.position.x, dz = tz - s.camera.position.z;
      const want = Math.atan2(-dx, -dz);
      let d = ((want - s.camera.rotation.y + Math.PI) % (Math.PI * 2)) - Math.PI;
      if (d < -Math.PI) d += Math.PI * 2;
      s.camera.rotation.y += Math.max(-0.11, Math.min(0.11, d * 0.28));
      const dist = Math.hypot(dx, dz);
      // Aim at the middle of a standing sheet, and clamp the pitch: looking
      // straight at the base of something 1.5 m away points the camera at the
      // carpet, and the footage is then mostly floor.
      let drop = -Math.atan2(s.CFG.eyeHeight - 1.05, Math.max(0.8, dist));
      drop = Math.max(-0.26, Math.min(0.06, drop));
      s.camera.rotation.x += (drop - s.camera.rotation.x) * 0.16;
      return { dist, aligned: Math.abs(d) < 0.16 };
    },
    click(button) {
      const el = document.querySelector('canvas');
      el.dispatchEvent(new MouseEvent('mousedown', { button, bubbles: true }));
      el.dispatchEvent(new MouseEvent('mouseup', { button, bubbles: true }));
    },
    tick() {
      s.keys.KeyW = false; s.keys.ShiftLeft = false;
      s.keys.KeyA = false; s.keys.KeyD = false;
      if (this.cool > 0) this.cool -= 1;
      if (s.done) return 'done';

      // Stick to a target until it is gone. Re-picking the nearest every frame
      // makes it dither between two documents and never close on either.
      const live = (x) => x && (x.alive !== false);
      if (this.lockOn && !live(this.lockOn.ref)) this.lockOn = null;
      if (this.lockOn && this.lockOn.kind === 'pod'
          && (!this.lockOn.ref.live || s.ink >= s.CFG.inkMax)) this.lockOn = null;

      if (!this.lockOn) {
        let pick = null;
        // Ink outranks everything, including the boss. Eight pages need eight
        // wet swings and the bonus starts with barely two in the barrel, so
        // topping up at two swings left -- rather than at zero -- is the
        // difference between numbering the motion and dry-stamping at it while
        // it walks in. Refilling first was the whole reason the last capture
        // never finished the fight.
        const floor = s.phase === 'bonus'
          ? s.CFG.inkPerSwing * 2 : s.CFG.inkPerSwing;
        if (s.ink < floor) {
          const p = s.pods.filter(x => x.live).sort((a, b) =>
            a.home.distanceTo(s.camera.position)
            - b.home.distanceTo(s.camera.position))[0];
          if (p) pick = { ref: p, kind: 'pod' };
        }
        if (!pick && s.boss && s.boss.alive) pick = { ref: s.boss, kind: 'boss' };
        if (!pick) {
          const o = s.objections.filter(x => x.alive)[0];
          if (o) pick = { ref: o, kind: 'objection' };
        }
        if (!pick) {
          const e = s.enemies.filter(x => x.alive).sort((a, b) =>
            a.root.position.distanceTo(s.camera.position)
            - b.root.position.distanceTo(s.camera.position))[0];
          if (e) pick = { ref: e, kind: e.kind };
        }
        this.lockOn = pick;
        this.held = 0;
        this.mark = null;                // new target, new progress baseline
        this.strafe = 0;
      }
      if (!this.lockOn) { s.keys.KeyW = true; return 'idle'; }

      // Hold the target in a local: the give-up below clears this.lockOn, and
      // reading through it after that is a TypeError.
      const { kind, ref } = this.lockOn;
      const t = kind === 'pod' ? ref.home : ref.root.position;
      const { dist, aligned } = this.aim(t.x, t.z);
      s.keys.KeyS = false;
      // Two thresholds, not one. The things that come at you have to be held in
      // a BAND: `close` is where the bot stops advancing, `back` is where it
      // gives ground. With a single threshold at 2.5 m the bot advanced to 2.5
      // and then reversed at 3.1 m/s from a boss walking at 1.15, so the motion
      // never got inside the 2.72 m the stamp can actually reach and the fight
      // was unwinnable -- it walked backwards for the whole bonus round.
      //
      // The reach numbers it is sitting between: a stamp lands 1.05 m ahead of
      // the eye with a 1.05 m radius, so a 0.62 m boss is hittable out to
      // 2.72 m, and reaching 1.35 m of the player means summary judgment is
      // granted. 2.05-2.55 is inside the first and clear of the second.
      const band = kind === 'pod' ? [0.5, 0.0]
        : kind === 'boss' ? [2.55, 2.30]
        : kind === 'objection' ? [2.20, 1.60] : [1.5, 0.0];
      let side = null;
      if (dist > band[0]) {
        s.keys.KeyW = true;
        // The exhibits flee at up to 3.3 m/s and the walk is 3.1, so anything
        // not already in range has to be sprinted down or it is never caught.
        if (dist > band[0] + 0.9) s.keys.ShiftLeft = true;
      } else if (dist < band[1]) {
        s.keys.KeyS = true;
        // Give ground in a circle, not a straight line. Backing straight away
        // from the motion works until there is a wall behind you, and then the
        // fight is lost from full retreat: two runs got seven of eight pages
        // and were reached in a corner holding the last one.
        if (kind === 'boss') side = (Math.floor(s.t / 2.2) % 2) ? 'KeyA' : 'KeyD';
        // Inside the last half metre of the band, run. A walk only beats the
        // motion by 1.95 m/s and the pages take long enough to number that the
        // margin gets eaten; the sprint applies to the whole move vector, so it
        // works backwards.
        if (dist < band[1] - 0.35) s.keys.ShiftLeft = true;
      }
      // Stuck watchdog, measured on the bot's own displacement rather than on
      // the range to the target. The bot walks a straight line at whatever it
      // is chasing and the office is a corridor kit, so anything around a
      // corner is unreachable: resolveMove slides it along the wall and W does
      // nothing at all. One capture spent 39 s pinned at x=-11.1 with the
      // motion two rooms away, recording an unwinnable bonus round in full.
      //
      // Displacement is the honest signal. Range is not: a paper fleeing at
      // 3.3 m/s from a 3.1 m/s walk holds its distance perfectly while both
      // are moving, which is not stuck and must not trigger a sidestep.
      if (this.strafe > 0) {
        this.strafe -= 1;
        side = this.strafeKey;
      } else if (s.keys.KeyW || s.keys.KeyS) {
        // Retreat gets stuck on walls exactly the way pursuit does, and being
        // stuck while giving ground is the one that loses the round.
        const px = s.camera.position.x, pz = s.camera.position.z;
        if (!this.mark) { this.mark = [px, pz]; this.marked = 20; }
        if (--this.marked <= 0) {
          // A second of walking is 3.1 m and a second of sprinting is 5. Under
          // half a metre means a wall, not slow progress.
          if (Math.hypot(px - this.mark[0], pz - this.mark[1]) < 0.5) {
            this.strafe = 20;
            this.flip = !this.flip;
            this.strafeKey = this.flip ? 'KeyA' : 'KeyD';
            side = this.strafeKey;
          }
          this.mark = [px, pz];
          this.marked = 20;
        }
      } else {
        this.mark = null;
      }
      if (side) s.keys[side] = true;
      // Give up on a target that is not resolving, or one bad decision pins the
      // bot on the same document for the rest of the capture.
      this.held = (this.held || 0) + 1;
      if (this.held > 140) { this.lockOn = null; this.held = 0; }

      // Redaction does not file anything -- it only blacks the pages out. The
      // privileged memo therefore takes two actions in order: redact it, then
      // stamp the redacted version to get it into the binder. Stamping first is
      // the mistake the game is built around.
      const redact = kind === 'privilege' && !ref.redacted;
      // A swing with less than inkPerSwing in the barrel still swings -- it just
      // files nothing. Gate on the cost of the action being taken, so the bot
      // never spends its turn on a dry stamp it could have spent on a pod.
      const cost = redact ? s.CFG.inkPerRedact : s.CFG.inkPerSwing;
      if (kind !== 'pod' && aligned && dist < (kind === 'boss' ? 2.55 : 2.3)
          && this.cool <= 0 && s.ink >= cost) {
        this.click(redact ? 2 : 0);
        // swingRefire is 0.54 s -- 10.8 frames -- so 11 is as fast as the stamp
        // can physically be worked, and a shorter fight is a fight the motion
        // has less time to corner you in.
        this.cool = redact ? 12 : 11;
      }
      return kind;
    },
  };
};

/**
 * One recorded run, frames written to `framesPath`. Returns how it ended.
 *
 * The bot wins the bonus round about one run in three -- the motion is not
 * scripted and a corridor corner at the wrong moment ends it on seven pages of
 * eight -- so a capture is an attempt, not a result, and the caller retries.
 */
async function record(browser, framesPath) {
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });

  await page.addInitScript(STUB);
  await page.goto('http://127.0.0.1:8123/web/index.html', { waitUntil: 'load' });

  for (let i = 0; i < 500; i++) {
    await page.evaluate(() => window.__step());
    if (await page.evaluate(() => !!(window.__bates && window.__bates.ready))) break;
    await page.waitForTimeout(60);
  }
  console.log('ready:', await page.evaluate(() => !!window.__bates.ready));

  let locked = false;
  for (let i = 0; i < 20 && !locked; i++) {
    await page.mouse.click(W / 2, H / 2);
    for (let k = 0; k < 6; k++) await page.evaluate(() => window.__step());
    locked = await page.evaluate(() => document.pointerLockElement !== null);
    if (!locked) await page.waitForTimeout(200);
  }
  console.log('locked:', locked);
  await page.evaluate(() => {
    window.__bates.muted = true;
    if (window.__bates.MUSIC) window.__bates.MUSIC.on = false;
    // Capture-only: the first objection is due at 22 s and a competent run
    // closes the binder before then, so it would never appear on camera. Pulled
    // forward so the reel shows the mechanic. Nothing else is altered.
    window.__bates.nextObj = 7;
  });
  await page.evaluate(DEMO);

  const fd = fs.openSync(framesPath, 'w');
  const t0 = Date.now();
  const seen = {};
  let shot = 0, after = -1;
  for (let i = 0; i < FRAMES; i++) {
    const kind = await page.evaluate(() => window.__demo.tick());
    seen[kind] = (seen[kind] || 0) + 1;
    await page.evaluate(() => window.__step());
    const buf = await page.screenshot({ type: 'jpeg', quality: 82 });
    fs.writeSync(fd, buf);
    shot += 1;
    // The wake screen fades up over 1.1 s. Hold it long enough to read the
    // verdict and then stop -- an earlier cut ran to a fixed frame count and
    // left 13 s of nobody playing on the end of the reel.
    if (kind === 'done') { if (after < 0) after = 0; else after += 1; }
    if (after >= TAIL) break;
    if (i % 50 === 0) {
      const el = (Date.now() - t0) / 1000;
      console.log(`  frame ${i}/${FRAMES}  ${el.toFixed(0)}s  ` +
        `${(el / Math.max(1, i)).toFixed(2)}s/frame  doing=${kind}`);
    }
  }
  fs.closeSync(fd);
  console.log('capture', ((Date.now() - t0) / 1000).toFixed(0) + 's wall, '
    + shot + ' frames = ' + (shot / FPS).toFixed(1) + 's of footage');
  console.log('frames spent on:', JSON.stringify(seen));
  const out = await page.evaluate(() => ({
    filed: window.__bates.filed, phase: window.__bates.phase,
    done: window.__bates.done, clock: Math.round(window.__bates.clock),
    redactions: window.__bates.redactions, bossHits: window.__bates.bossHits,
    pagesLeft: window.__bates.boss ? window.__bates.boss.pages : null,
    bonusWon: window.__bates.bonusWon, dryStamps: window.__bates.dryStamps,
    overruled: window.__bates.overruled, struck: window.__bates.struck,
    ending: document.getElementById('wake-tag').textContent.trim() }));
  console.log('final:', JSON.stringify(out));
  console.log('errors:', JSON.stringify(errs));
  await page.close();
  return Object.assign(out, { frames: shot, errs });
}

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader',
           '--no-sandbox', '--disable-dev-shm-usage', '--hide-scrollbars'],
  });

  // Keep going until a run wins the bonus round, and keep the best attempt if
  // none does -- a reel that ends on summary judgment being granted is still a
  // reel that ends on an ending, which is the whole point of the re-record.
  let best = null;
  for (let a = 1; a <= TRIES; a++) {
    console.log(`--- attempt ${a}/${TRIES}`);
    const path = `${OUT}/frames_${a}.mjpeg`;
    const r = await record(browser, path);
    r.path = path;
    if (!best || r.bonusWon > best.bonusWon
        || (r.bonusWon === best.bonusWon && r.bossHits > best.bossHits)) {
      if (best) fs.unlinkSync(best.path);
      best = r;
    } else {
      fs.unlinkSync(path);
    }
    if (best.bonusWon) break;
  }
  await browser.close();
  console.log('kept:', best.ending, `${best.bossHits}/8 pages,`,
    `${(best.frames / FPS).toFixed(1)}s`);

  const webm = `${OUT}/bates_demo.webm`;
  execFileSync(FFMPEG, ['-hide_banner', '-loglevel', 'error',
    '-f', 'image2pipe', '-c:v', 'mjpeg', '-r', String(FPS),
    '-i', 'file:' + best.path,
    '-c:v', 'libvpx', '-b:v', '2500k',
    '-pix_fmt', 'yuv420p', '-y', webm], { stdio: 'inherit' });
  console.log('wrote', webm,
    (fs.statSync(webm).size / 1048576).toFixed(2) + ' MB');
})().catch(e => { console.error('FAILED:', e); process.exit(1); });
