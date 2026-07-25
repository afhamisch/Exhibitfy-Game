// Record the bonus round: thirty seconds of opposing counsel throwing binders.
//
// Same capture technique as record_demo.js -- stub requestAnimationFrame, step
// the page one frame at a time, one screenshot per step, so SwiftShader's few
// frames a second still come out as true-speed 20 fps footage.
//
// Capture-only: this drops straight into the bonus round rather than playing
// the ninety seconds that earn it. The case phase is what record_demo.js
// already shows; what this reel is for is the round most players will never
// reach. The binder is closed honestly first -- four exhibits filed, the memo
// redacted -- so the ending screen reports a real run.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const { execFileSync } = require('child_process');

const FFMPEG = '/opt/pw-browsers/ffmpeg-1011/ffmpeg-linux';
const OUT = __dirname;
const FPS = 20;
const SECONDS = Number(process.argv[2] || 40);
const FRAMES = Math.round(FPS * SECONDS);
const TAIL = Math.round(FPS * 2.5);
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

// A dodger. It reads the binders the way a player has to: not "where is it
// now" but "where will it pass me", which is the only question that matters
// when the thing is crossing 7 m in under a second.
const DODGER = () => {
  const s = window.__bates;
  window.__demo = {
    cool: 0, flip: 1,
    aim(tx, tz) {
      const dx = tx - s.camera.position.x, dz = tz - s.camera.position.z;
      const want = Math.atan2(-dx, -dz);
      let d = ((want - s.camera.rotation.y + Math.PI) % (Math.PI * 2)) - Math.PI;
      if (d < -Math.PI) d += Math.PI * 2;
      s.camera.rotation.y += Math.max(-0.14, Math.min(0.14, d * 0.30));
      s.camera.rotation.x += (-0.02 - s.camera.rotation.x) * 0.15;
    },
    click() {
      const el = document.querySelector('canvas');
      el.dispatchEvent(new MouseEvent('mousedown', { button: 0, bubbles: true }));
      el.dispatchEvent(new MouseEvent('mouseup', { button: 0, bubbles: true }));
    },
    /** Closest approach of a binder to the player, and how long until it. */
    threat() {
      let best = null, bestT = 1e9;
      for (const p of s.binders) {
        if (p.done || p.deflected) continue;
        const rx = s.camera.position.x - p.root.position.x;
        const rz = s.camera.position.z - p.root.position.z;
        const t = (rx * p.dir.x + rz * p.dir.z) / s.CFG.binderSpeed;
        if (t < 0) continue;                       // already past
        const cx = p.root.position.x + p.dir.x * s.CFG.binderSpeed * t;
        const cz = p.root.position.z + p.dir.z * s.CFG.binderSpeed * t;
        const miss = Math.hypot(cx - s.camera.position.x, cz - s.camera.position.z);
        if (miss < 1.1 && t < bestT) { bestT = t; best = { p, t, cx, cz, miss }; }
      }
      return best;
    },
    tick() {
      const k = s.keys;
      k.KeyW = k.KeyS = k.KeyA = k.KeyD = false;
      if (this.cool > 0) this.cool -= 1;
      if (s.done) return 'done';
      const b = s.boss;
      if (!b) return 'waiting';
      this.aim(b.root.position.x, b.root.position.z);

      const th = this.threat();
      if (!th) return 'watching';

      const dist = Math.hypot(th.p.root.position.x - s.camera.position.x,
                              th.p.root.position.z - s.camera.position.z);

      // Close enough and the stamp is armed: swat it. The rule is no two in a
      // row, so this only fires when the game says it may, and everything else
      // has to be dodged -- which is the point of the round.
      const range = s.touch ? s.CFG.deflectRangeTouch : s.CFG.deflectRange;
      if (s.deflectReady && dist < range - 0.15 && this.cool <= 0) {
        this.click();
        this.cool = 12;
        return 'deflect';
      }

      // Otherwise get off its line. Which way: whichever side of us it is
      // going to pass, we go the other way.
      const y = s.camera.rotation.y;
      const rx = Math.cos(y), rz = -Math.sin(y);
      const side = (th.cx - s.camera.position.x) * rx
                 + (th.cz - s.camera.position.z) * rz;
      let want = side > 0 ? 'KeyA' : 'KeyD';
      // A corridor is 1.72 m wide, so the chosen side is often a wall. Take
      // the other one rather than standing still and wearing it.
      const step = 0.55;
      const test = (key) => {
        const sgn = key === 'KeyD' ? 1 : -1;
        return s.insideWalk(s.camera.position.x + rx * sgn * step,
                            s.camera.position.z + rz * sgn * step);
      };
      if (!test(want)) want = want === 'KeyA' ? 'KeyD' : 'KeyA';
      if (test(want)) k[want] = true;
      return 'dodge';
    },
  };
};

async function record(browser, framesPath) {
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await page.addInitScript(STUB);
  await page.goto('http://127.0.0.1:8123/web/index.html', { waitUntil: 'load' });

  for (let i = 0; i < 600; i++) {
    await page.evaluate(() => window.__step());
    if (await page.evaluate(() => !!(window.__bates && window.__bates.ready))) break;
    await page.waitForTimeout(60);
  }
  let locked = false;
  for (let i = 0; i < 20 && !locked; i++) {
    await page.mouse.click(W / 2, H / 2);
    for (let k = 0; k < 6; k++) await page.evaluate(() => window.__step());
    locked = await page.evaluate(() => document.pointerLockElement !== null);
    if (!locked) await page.waitForTimeout(200);
  }
  console.log('ready + locked:', locked);

  await page.evaluate(async () => {
    const s = window.__bates;
    s.muted = true;
    if (s.MUSIC) s.MUSIC.on = false;
    // A binder closed the way the game intends, so the ending screen is
    // reporting a real one: four filed, the privileged memo redacted.
    s.enemies.forEach((e) => {
      e.alive = false; e.filed = true; e.root.visible = false;
      if (e.kind === 'privilege') e.redacted = true;
    });
    s.filed = s.enemies.length;
    s.score = s.filed;
    s.redactions = 1;
    s.privilegeSaved = true;
    s.setInk(100);
    await s.startBonus();
  });
  await page.evaluate(DODGER);

  const fd = fs.openSync(framesPath, 'w');
  const t0 = Date.now();
  const seen = {};
  let shot = 0, after = -1;
  for (let i = 0; i < FRAMES; i++) {
    const what = await page.evaluate(() => window.__demo.tick());
    seen[what] = (seen[what] || 0) + 1;
    await page.evaluate(() => window.__step());
    fs.writeSync(fd, await page.screenshot({ type: 'jpeg', quality: 82 }));
    shot += 1;
    if (what === 'done') { if (after < 0) after = 0; else after += 1; }
    if (after >= TAIL) break;
    if (i % 50 === 0) {
      const el = (Date.now() - t0) / 1000;
      console.log(`  frame ${i}/${FRAMES}  ${el.toFixed(0)}s  doing=${what}`);
    }
  }
  fs.closeSync(fd);
  const out = await page.evaluate(() => ({
    survived: window.__bates.survived, tier: window.__bates.bonusTier,
    deflects: window.__bates.deflects, hits: window.__bates.binderHits,
    thrown: window.__bates.boss ? window.__bates.boss.thrown : 0,
    tag: document.getElementById('wake-tag').textContent,
  }));
  console.log('spent on:', JSON.stringify(seen));
  console.log('final:', JSON.stringify(out));
  console.log('errors:', JSON.stringify(errs));
  await page.close();
  return Object.assign(out, { frames: shot });
}

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader',
           '--no-sandbox', '--disable-dev-shm-usage', '--hide-scrollbars'],
  });
  let best = null;
  for (let a = 1; a <= TRIES; a++) {
    console.log(`--- attempt ${a}/${TRIES}`);
    const path = `${OUT}/bonus_${a}.mjpeg`;
    const r = await record(browser, path);
    r.path = path;
    if (!best || r.survived > best.survived) {
      if (best) fs.unlinkSync(best.path);
      best = r;
    } else {
      fs.unlinkSync(path);
    }
    if (best.tier === 'lawyer') break;
  }
  await browser.close();
  console.log('kept:', best.tier, best.survived, 'survived');

  const webm = `${OUT}/bonus_demo.webm`;
  execFileSync(FFMPEG, ['-hide_banner', '-loglevel', 'error',
    '-f', 'image2pipe', '-c:v', 'mjpeg', '-r', String(FPS),
    '-i', 'file:' + best.path,
    '-c:v', 'libvpx', '-b:v', '1400k',
    '-pix_fmt', 'yuv420p', '-y', webm], { stdio: 'inherit' });
  console.log('wrote', webm,
    (fs.statSync(webm).size / 1048576).toFixed(2) + ' MB');
})().catch(e => { console.error('FAILED:', e); process.exit(1); });
