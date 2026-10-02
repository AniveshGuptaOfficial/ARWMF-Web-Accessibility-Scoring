/* A-RWMF web UI — Three.js scene (vendored, offline) + job polling.
   Modes: landing (wireframe icosahedron) -> loading (orbiting rings)
          -> results (3D bar chart of the five dimensions). */
import * as THREE from './vendor/three.module.js';

const $ = (id) => document.getElementById(id);

const DIMS = [
  { key: 'contrast',    label: 'Contrast',    color: 0xf6ad55, hex: '#f6ad55' },
  { key: 'target_size', label: 'Target size', color: 0x68d391, hex: '#68d391' },
  { key: 'layout',      label: 'Layout',      color: 0x63b3ed, hex: '#63b3ed' },
  { key: 'alt_text',    label: 'Alt text',    color: 0xb794f4, hex: '#b794f4' },
  { key: 'link_text',   label: 'Link text',   color: 0x4fd1c5, hex: '#4fd1c5' },
];
const PHASE_TEXT = {
  queued: 'queued',
  capturing: 'capturing page (Playwright)',
  scoring: 'scoring five dimensions',
  axe: 'running axe-core baseline',
  done: 'done',
};
const PHASE_WIDTH = { queued: '8%', capturing: '35%', scoring: '72%', axe: '92%', done: '100%' };

/* ================= renderer / scene ================= */
const canvas = $('scene');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.setSize(innerWidth, innerHeight);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x050912, 0.017);
const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 300);

scene.add(new THREE.HemisphereLight(0x99ccff, 0x0a0f1a, 0.7));
const keyLight = new THREE.DirectionalLight(0xffffff, 1.0);
keyLight.position.set(6, 12, 8);
scene.add(keyLight);
const rimLight = new THREE.PointLight(0x4fd1c5, 0.5, 60);
rimLight.position.set(0, 4, 6);
scene.add(rimLight);

/* starfield — always visible */
const starGeo = new THREE.BufferGeometry();
{
  const N = 1400, pos = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const r = 55 + Math.random() * 75;
    const a = Math.random() * Math.PI * 2;
    const b = Math.acos(2 * Math.random() - 1);
    pos[i * 3]     = r * Math.sin(b) * Math.cos(a);
    pos[i * 3 + 1] = r * Math.cos(b);
    pos[i * 3 + 2] = r * Math.sin(b) * Math.sin(a);
  }
  starGeo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
}
const stars = new THREE.Points(starGeo, new THREE.PointsMaterial({
  color: 0x9fd8ff, size: 0.4, sizeAttenuation: true, transparent: true, opacity: 0.75,
}));
scene.add(stars);

/* ================= landing object ================= */
const landingG = new THREE.Group();
const icosaGeo = new THREE.IcosahedronGeometry(3.1, 1);
const icosaShell = new THREE.Mesh(
  new THREE.IcosahedronGeometry(3.06, 1),
  new THREE.MeshBasicMaterial({ color: 0x061019 })
);
const icosaEdges = new THREE.LineSegments(
  new THREE.EdgesGeometry(icosaGeo),
  new THREE.LineBasicMaterial({ color: 0x4fd1c5, transparent: true, opacity: 0.9 })
);
const icosaInner = new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.6, 0)),
  new THREE.LineBasicMaterial({ color: 0xf6ad55, transparent: true, opacity: 0.75 })
);
landingG.add(icosaShell, icosaEdges, icosaInner);
landingG.position.y = 0.9;

const moons = [];
[0x4fd1c5, 0xf6ad55, 0xb794f4].forEach((c, i) => {
  const m = new THREE.Mesh(
    new THREE.SphereGeometry(0.16, 20, 20),
    new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: 0.6 })
  );
  m.userData = { r: 4.4 + i * 0.7, speed: 0.5 + i * 0.23, phase: i * 2.1, tilt: (i - 1) * 0.5 };
  moons.push(m);
  landingG.add(m);
});
scene.add(landingG);

/* ================= loading object ================= */
const loadingG = new THREE.Group();
const rings = [];
[
  [0x4fd1c5, Math.PI / 2, 0.0],
  [0xf6ad55, Math.PI / 2 + Math.PI / 3, 1.1],
  [0xb794f4, Math.PI / 2 - Math.PI / 3, 2.2],
].forEach(([c, rx, spin]) => {
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(2.1, 0.07, 18, 130),
    new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0.92 })
  );
  ring.rotation.x = rx;
  ring.userData.spin = (spin % 2 ? -1 : 1) * (0.8 + spin * 0.35);
  rings.push(ring);
  loadingG.add(ring);
});
const core = new THREE.Mesh(
  new THREE.IcosahedronGeometry(0.85, 1),
  new THREE.MeshBasicMaterial({ color: 0x4fd1c5, wireframe: true, transparent: true, opacity: 0.9 })
);
loadingG.add(core);
scene.add(loadingG);

/* ================= results object ================= */
const resultsX = () => (innerWidth < 900 ? 0 : 5.4);
const resultsG = new THREE.Group();
resultsG.position.x = resultsX();
const grid = new THREE.GridHelper(80, 80, 0x21485c, 0x112433);
grid.position.y = -0.02;
resultsG.add(grid);
scene.add(resultsG);

let bars = [];        // {mesh, h, t0, dur} — grow from 0 with easing
let labelSpecs = [];  // {obj, off, el}   — DOM labels tracked in 3D
const labelsEl = $('labels');

function addLabel(obj, off, title, value, sub, na) {
  const el = document.createElement('div');
  el.className = 'lbl' + (na ? ' na' : '');
  el.innerHTML =
    `<span class="t">${title}</span><span class="v">${value}</span>` +
    (sub ? `<span class="s">${sub}</span>` : '');
  labelsEl.appendChild(el);
  labelSpecs.push({ obj, off, el });
}

function clearGroup(obj) {
  const keep = new Set([grid]);
  [...obj.children].forEach((child) => {
    if (keep.has(child)) return;
    obj.remove(child);
    child.traverse?.((o) => {
      o.geometry?.dispose?.();
      if (o.material) {
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) => m.dispose());
      }
    });
  });
}

function growBar(mesh, h, delay) {
  mesh.scale.y = 0.001;
  bars.push({ mesh, h, t0: performance.now() + delay, dur: 850 });
}

function buildResults(res) {
  clearGroup(resultsG);
  labelsEl.innerHTML = '';
  bars = [];
  labelSpecs = [];

  const weight = (k) =>
    res.applied_weights[k] != null ? `weight ${res.applied_weights[k].toFixed(2)}` : '';

  /* five dimension bars, front row */
  DIMS.forEach((d, i) => {
    const v = res.dimensions[d.key];
    const na = v == null;
    const h = na ? 0.14 : Math.max((v / 100) * 5.2, 0.14);
    const geo = new THREE.BoxGeometry(1.05, 1, 1.05);
    geo.translate(0, 0.5, 0); // grow upward from the floor
    const mat = new THREE.MeshStandardMaterial({
      color: na ? 0x3a4a5a : d.color,
      metalness: 0.25,
      roughness: 0.35,
      emissive: na ? 0x000000 : d.color,
      emissiveIntensity: na ? 0 : 0.2,
      transparent: na,
      opacity: na ? 0.55 : 1,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set((i - 2) * 1.95, 0, 1.6);
    resultsG.add(mesh);
    growBar(mesh, h, i * 130);
    addLabel(mesh, 0.75, d.label, na ? 'n/a' : v.toFixed(1), na ? '' : weight(d.key), na);
  });

  /* composite pillar (ours) — colour encodes the score, red -> green */
  const ch = (res.composite / 100) * 6.6;
  const compColor = new THREE.Color().setHSL(
    Math.min(Math.max(res.composite / 100, 0), 1) * 0.36, 0.6, 0.48
  );
  const compGeo = new THREE.BoxGeometry(1.7, 1, 1.7);
  compGeo.translate(0, 0.5, 0);
  const compMesh = new THREE.Mesh(compGeo, new THREE.MeshStandardMaterial({
    color: compColor, metalness: 0.3, roughness: 0.3,
    emissive: compColor, emissiveIntensity: 0.3,
  }));
  compMesh.position.set(-1.5, 0, -3.4);
  resultsG.add(compMesh);
  growBar(compMesh, ch, 0);
  addLabel(compMesh, 0.8, 'Composite', res.composite.toFixed(1), 'fused', false);

  /* axe-core baseline — white wireframe ghost pillar */
  const ah = (res.axe.axe_score / 100) * 6.6;
  const axeGeo = new THREE.BoxGeometry(1.7, 1, 1.7);
  axeGeo.translate(0, 0.5, 0);
  const axeMesh = new THREE.Mesh(axeGeo, new THREE.MeshBasicMaterial({
    color: 0xffffff, wireframe: true, transparent: true, opacity: 0.6,
  }));
  axeMesh.position.set(1.5, 0, -3.4);
  resultsG.add(axeMesh);
  growBar(axeMesh, ah, 220);
  addLabel(axeMesh, 0.8, 'axe-core', res.axe.axe_score.toFixed(1),
    `${res.axe.n_violations} violations`, false);
}

/* ================= camera orbit ================= */
const PRESETS = {
  landing: { r: 12, phi: 1.0, target: () => [0, 0.7, 0] },
  loading: { r: 8.5, phi: 1.22, target: () => [0, 0, 0] },
  results: { r: 15.5, phi: 1.16, target: () => [resultsX() - (innerWidth < 900 ? 1.0 : 3.6), 2.6, -0.6] },
};
const orbit = {
  r: 12, tr: 12,
  theta: 0.55, tt: 0.55,
  phi: 1.0, tp: 1.0,
  target: new THREE.Vector3(0, 0.7, 0),
  ttarget: new THREE.Vector3(0, 0.7, 0),
  drag: false, lx: 0, ly: 0,
};

let mode = 'landing';
function setMode(m) {
  mode = m;
  landingG.visible = m === 'landing';
  loadingG.visible = m === 'loading';
  resultsG.visible = m === 'results';
  const P = PRESETS[m];
  orbit.tr = P.r;
  orbit.tp = P.phi;
  orbit.ttarget.set(...P.target());
  if (m === 'results') orbit.tt = 0.3; // settle into the composed front-3/4 view
  ['landing', 'loading', 'results'].forEach((id) =>
    $(id).classList.toggle('hidden', id !== m)
  );
}

canvas.addEventListener('pointerdown', (e) => {
  orbit.drag = true;
  orbit.lx = e.clientX;
  orbit.ly = e.clientY;
  canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener('pointermove', (e) => {
  if (!orbit.drag) return;
  orbit.tt -= (e.clientX - orbit.lx) * 0.006;
  orbit.tp = Math.min(1.5, Math.max(0.35, orbit.tp - (e.clientY - orbit.ly) * 0.005));
  orbit.lx = e.clientX;
  orbit.ly = e.clientY;
});
['pointerup', 'pointercancel'].forEach((ev) =>
  canvas.addEventListener(ev, () => { orbit.drag = false; })
);
canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  orbit.tr = Math.min(40, Math.max(6, orbit.tr + e.deltaY * 0.012));
}, { passive: false });

/* ================= render loop ================= */
const clock = new THREE.Clock();
const _v = new THREE.Vector3();

function frame() {
  requestAnimationFrame(frame);
  const dt = Math.min(clock.getDelta(), 0.05);
  const t = clock.elapsedTime;
  const now = performance.now();

  /* object animations per mode */
  stars.rotation.y += dt * 0.004;
  if (landingG.visible) {
    landingG.rotation.y += dt * 0.16;
    landingG.rotation.x = Math.sin(t * 0.3) * 0.15;
    icosaInner.rotation.y -= dt * 0.5;
    icosaInner.rotation.z += dt * 0.25;
    moons.forEach((m) => {
      const u = m.userData;
      const a = t * u.speed + u.phase;
      m.position.set(Math.cos(a) * u.r, Math.sin(a * 1.7) * 0.9 + u.tilt, Math.sin(a) * u.r);
    });
  }
  if (loadingG.visible) {
    rings.forEach((r) => { r.rotation.z += dt * r.userData.spin; });
    core.scale.setScalar(1 + 0.14 * Math.sin(t * 3.2));
    core.rotation.y += dt * 0.7;
    core.rotation.x += dt * 0.3;
  }

  /* camera: eased spherical orbit around eased target */
  if (!orbit.drag && mode !== 'results') orbit.tt += dt * 0.045; // drift only outside results
  orbit.theta += (orbit.tt - orbit.theta) * 0.1;
  orbit.phi += (orbit.tp - orbit.phi) * 0.08;
  orbit.r += (orbit.tr - orbit.r) * 0.06;
  orbit.target.lerp(orbit.ttarget, 0.06);
  camera.position.set(
    orbit.target.x + orbit.r * Math.sin(orbit.phi) * Math.sin(orbit.theta),
    orbit.target.y + orbit.r * Math.cos(orbit.phi),
    orbit.target.z + orbit.r * Math.sin(orbit.phi) * Math.cos(orbit.theta)
  );
  camera.lookAt(orbit.target);

  /* bar growth + floating labels */
  for (const b of bars) {
    const p = Math.min(1, Math.max(0, (now - b.t0) / b.dur));
    b.mesh.scale.y = Math.max(0.001, b.h * (1 - Math.pow(1 - p, 3)));
  }
  if (mode === 'results') {
    labelsEl.style.display = '';
    for (const L of labelSpecs) {
      // world x/z from the object, y rides the animated bar top + fixed margin
      L.obj.getWorldPosition(_v);
      _v.y += L.obj.scale.y + L.off;
      _v.project(camera);
      const x = (_v.x * 0.5 + 0.5) * innerWidth;
      const y = (-_v.y * 0.5 + 0.5) * innerHeight;
      L.el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) translate(-50%, -115%)`;
      L.el.style.opacity = _v.z > 1 ? 0 : 1;
    }
  } else {
    labelsEl.style.display = 'none';
  }

  renderer.render(scene, camera);
}

addEventListener('resize', () => {
  renderer.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  resultsG.position.x = resultsX();
  if (mode === 'results') orbit.ttarget.set(...PRESETS.results.target());
});

/* ================= UI: job submission + polling ================= */
let pollTimer = null;
let warmTimer = null;
let currentJob = null;
let lastPhase = '';
let DATASET = null;   // { byKey, byHost } of recorded demo results
let demoTimers = [];  // scripted phase timers (demo mode)

function banner(msg) {
  const el = $('error-banner');
  el.textContent = msg;
  el.classList.remove('hidden');
  el.classList.remove('shake');
  void el.offsetWidth; // restart animation
  el.classList.add('shake');
}

function normalizeUrl(raw) {
  let u = (raw || '').trim();
  if (!u) return null;
  if (!/^https?:\/\//i.test(u)) u = 'https://' + u;
  if (!/^https?:\/\/[^\s/]+\.[^\s/]+/i.test(u)) return null;
  return u;
}

function setPhase(p) {
  lastPhase = p;
  $('phase-text').textContent = PHASE_TEXT[p] || p;
  $('progress-fill').style.width = PHASE_WIDTH[p] || '50%';
}

function stopPoll() {
  demoTimers.forEach(clearTimeout);
  demoTimers = [];
}

/* ---------- demo mode: recorded dataset lookup + scripted phases ---------- */
function canon(u) {
  try {
    const x = new URL(u);
    const host = x.host.toLowerCase().replace(/^www\./, '');
    const path = x.pathname.replace(/\/+$/, '');
    return 'https://' + host + path + x.search;
  } catch {
    return u;
  }
}

function lookupRecord(url) {
  if (!DATASET) return null;
  const key = canon(url);
  if (DATASET.byKey.has(key)) return DATASET.byKey.get(key);
  return DATASET.byHost.get(key.split('/')[2] || '') || null;
}

function runDemoPhases(rec) {
  const plan = [['queued', 450], ['capturing', 1500], ['scoring', 2400], ['axe', 1800]];
  const jitter = () => 0.85 + Math.random() * 0.3;
  let t = 0;
  lastPhase = '';
  plan.forEach(([ph, ms]) => {
    t += ms * jitter();
    demoTimers.push(setTimeout(() => setPhase(ph), t));
  });
  demoTimers.push(setTimeout(() => {
    showResults({ result: { ...rec.score, axe: rec.axe, screenshot: rec.screenshot } });
  }, t + 550));
}

$('analyze-form').addEventListener('submit', (e) => {
  e.preventDefault();
  $('error-banner').classList.add('hidden');
  const url = normalizeUrl($('url-input').value);
  if (!url) {
    banner('Enter a valid URL — e.g. https://example.com');
    return;
  }
  if (!DATASET) {
    banner('Demo data is still loading — one moment…');
    return;
  }
  const rec = lookupRecord(url);
  if (!rec) {
    banner('Not in the recorded demo set — pick one of the chips below, ' +
           'or run the live pipeline locally:  python webapp/server.py');
    return;
  }
  $('url-input').value = url;
  $('loading-url').textContent = url;
  setMode('loading');
  stopPoll();
  runDemoPhases(rec);
});

/* live polling removed: this site replays recorded results (see runDemoPhases) */

$('cancel-btn').addEventListener('click', () => { stopPoll(); setMode('landing'); });
$('again-btn').addEventListener('click', () => { setMode('landing'); $('url-input').focus(); });

/* ================= results rendering ================= */
function countUp(el, to, ms = 1100) {
  const t0 = performance.now();
  const step = (now) => {
    const p = Math.min(1, (now - t0) / ms);
    el.textContent = (to * (1 - Math.pow(1 - p, 3))).toFixed(1);
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function renderDims(res) {
  const box = $('r-dims');
  box.innerHTML = '';
  DIMS.forEach((d, i) => {
    const v = res.dimensions[d.key];
    const w = res.applied_weights[d.key];
    const row = document.createElement('div');
    row.className = 'dim' + (v == null ? ' na' : '');
    row.innerHTML =
      `<span class="d-label"><i style="background:${d.hex}"></i>${d.label}</span>` +
      `<div class="d-track"><div class="d-fill" style="background:${d.hex};transition-delay:${i * 90}ms"></div></div>` +
      `<span class="d-val">${v == null ? 'n/a' : v.toFixed(1)}</span>` +
      `<span class="d-w">${w != null ? 'w ' + w.toFixed(2) : '—'}</span>`;
    box.appendChild(row);
    if (v != null) {
      requestAnimationFrame(() =>
        requestAnimationFrame(() => { row.querySelector('.d-fill').style.width = `${v}%`; })
      );
    }
  });
}

function renderViolations(axe) {
  const box = $('r-violations');
  $('r-viol-count').textContent = axe.n_violations ? `(${axe.n_violations})` : '';
  if (!axe.violations.length) {
    box.innerHTML = '<div class="no-viol">No axe-core violations detected 🎉</div>';
    return;
  }
  const order = { critical: 0, serious: 1, moderate: 2, minor: 3 };
  const list = [...axe.violations].sort(
    (a, b) => (order[a.impact] ?? 4) - (order[b.impact] ?? 4)
  );
  box.innerHTML = list.map((v) => {
    const impact = (v.impact || 'minor').toLowerCase();
    return `<span class="vchip ${impact}">${v.id} <b>×${v.nodes_count}</b> <i>${impact}</i></span>`;
  }).join('');
}

function renderMeta(res) {
  const c = res.counts;
  let html =
    `<div class="kv"><span>viewport</span><b>${res.viewport}</b></div>` +
    `<div class="kv"><span>DOM / text / interactive</span><b>${c.n_elements} / ${c.text_elements} / ${c.interactive}</b></div>` +
    `<div class="kv"><span>images / links</span><b>${c.images_applicable} / ${c.links}</b></div>` +
    `<div class="kv"><span>scoring time</span><b>${res.seconds} s</b></div>` +
    `<div class="kv"><span>fusion weights</span><b>static defaults</b></div>`;
  if (res.degraded && res.degraded.length) {
    html += `<div class="warn-note">degraded: ${res.degraded.join(', ')} → deterministic fallback used</div>`;
  }
  $('r-meta').innerHTML = html;
}

function showResults(job) {
  const res = job.result;
  buildResults(res);
  setMode('results');

  $('r-url').textContent = res.url;
  $('r-sub').textContent =
    `${res.viewport} viewport · ${res.counts.n_elements} elements · scored in ${res.seconds} s`;
  countUp($('r-composite'), res.composite);

  $('r-axe-score').textContent = res.axe.axe_score.toFixed(1);
  const box = $('r-axe-box');
  box.classList.remove('good', 'warn', 'bad');
  box.classList.add(res.axe.axe_score >= 90 ? 'good' : res.axe.axe_score >= 75 ? 'warn' : 'bad');

  renderDims(res);
  renderViolations(res.axe);
  renderMeta(res);

  const shot = $('r-shot');
  if (res.screenshot) shot.href = res.screenshot;
  else shot.style.display = 'none';
}

/* ================= boot: load recorded demo results ================= */
setMode('landing');
frame();
fetch('data/demo-results.json')
  .then((r) => { if (!r.ok) throw new Error('demo data missing'); return r.json(); })
  .then((d) => {
    const byKey = new Map();
    const byHost = new Map();
    d.pages.forEach((p) => {
      const k = canon(p.url);
      byKey.set(k, p);
      byHost.set(k.split('/')[2], p);
    });
    DATASET = { byKey, byHost };
    buildChips(d.pages);
  })
  .catch(() => banner('Demo data failed to load — refresh the page.'));

function buildChips(pages) {
  const box = $('chips');
  box.innerHTML = '';
  pages.forEach((p) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.textContent = p.label;
    b.title = p.url;
    b.addEventListener('click', () => {
      $('url-input').value = p.url;
      $('analyze-form').requestSubmit();
    });
    box.appendChild(b);
  });
}
