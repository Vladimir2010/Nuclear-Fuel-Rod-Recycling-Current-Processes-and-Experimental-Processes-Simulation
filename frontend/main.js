import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// ---------------------------------------------------------------------------
// Константи за етапите на цикъла (огледални на backend-а в backend/simulations)
// ---------------------------------------------------------------------------
const STAGE = {
  IDLE: 0, COOLING: 1, SHEARING: 2, DISSOLUTION: 3, EXTRACTION: 4,
  PURIFICATION: 5, REPACKAGING: 6, WASTE: 7, COMPLETE: 8,
};

const STAGE_NAMES = {
  [STAGE.IDLE]: 'STANDBY',
  [STAGE.COOLING]: 'ЕТАП 1/7 — DECAY HEAT COOLING',
  [STAGE.SHEARING]: 'ЕТАП 2/7 — SHEARING (рязане на касетата)',
  [STAGE.DISSOLUTION]: 'ЕТАП 3/7 — DISSOLUTION (HNO3)',
  [STAGE.EXTRACTION]: 'ЕТАП 4/7 — EXTRACTION (TBP)',
  [STAGE.PURIFICATION]: 'ЕТАП 5/7 — PURIFICATION (ADU → UO2)',
  [STAGE.REPACKAGING]: 'ЕТАП 6/7 — REPACKAGING',
  [STAGE.WASTE]: 'ЕТАП 7/7 — WASTE CONDITIONING',
  [STAGE.COMPLETE]: 'ЦИКЪЛЪТ Е ЗАВЪРШЕН',
};

const SHEARING_DURATION_S = 3.0; // чисто механична стъпка, няма backend физика

// backend-ът вече връща пълна времева поредица в ЕДИН отговор (batch), а не
// на интервали през "elapsed" - затова всеки етап се зарежда еднократно при
// влизане в него и после се интерполира локално спрямо реалното време.
const STAGE_REQUEST = {
  [STAGE.COOLING]: () => ({
    path: 'cooling',
    params: {
      duration: 900, sample_interval: 15,
      h_coolant: 150 + sim.speed * 400, coolant_temperature: 30,
    },
  }),
  [STAGE.DISSOLUTION]: () => ({
    path: 'dissolution/acid',
    params: {
      duration: 150, sample_interval: 5,
      mass_uo2_kg: 0.25, acid_concentration_m: 5,
      cooling_power_w: Math.max(200, 3000 / sim.speed),
      vented: sim.vented,
    },
  }),
  [STAGE.EXTRACTION]: () => ({
    path: 'extraction',
    params: { duration: 150, sample_interval: 5 },
  }),
  [STAGE.PURIFICATION]: () => ({
    path: 'purification',
    params: { duration: 220, sample_interval: 10 },
  }),
  [STAGE.REPACKAGING]: () => ({
    path: 'repackaging',
    params: { duration: 60, sample_interval: 5, speed: sim.speed },
  }),
  [STAGE.WASTE]: () => ({
    path: 'waste',
    params: { duration: 60, sample_interval: 5, speed: sim.speed },
  }),
};

const STATION_X = {
  [STAGE.COOLING]: -24,
  [STAGE.SHEARING]: -12,
  [STAGE.DISSOLUTION]: 0,
  [STAGE.EXTRACTION]: 10,
  [STAGE.PURIFICATION]: 20,
  [STAGE.REPACKAGING]: 30,
  [STAGE.WASTE]: 40,
};

const STAGE_COLOR = {
  [STAGE.COOLING]: new THREE.Color(0x4fc3f7),
  [STAGE.SHEARING]: new THREE.Color(0xcccccc),
  [STAGE.DISSOLUTION]: new THREE.Color(0xffb347),
  [STAGE.EXTRACTION]: new THREE.Color(0xc9a0ff),
  [STAGE.PURIFICATION]: new THREE.Color(0x7fffa0),
  [STAGE.REPACKAGING]: new THREE.Color(0x7fd9ff),
  [STAGE.WASTE]: new THREE.Color(0x8bd450),
};

const API_BASE = '/api';

// ---------------------------------------------------------------------------
// Състояние на симулацията
// ---------------------------------------------------------------------------
const TARGET_PLAYBACK_SECONDS = 20; // всеки етап се "изиграва" за толкова реални секунди,
                                     // независимо дали представлява 60s или 14 дни физика

const sim = {
  stage: STAGE.IDLE,
  speed: 1.0,
  vented: false,
  stageWallElapsed: 0,
  timeMultiplier: 1,     // физични секунди симулация за 1 реална секунда demo
  batch: null,          // { time: [...], results: { temperature: [...], progress: [...] } }
  displayedProgress: 0,
  displayedTemp: 25,
  efficiency: 0,
  backendOnline: true,
};

// ---------------------------------------------------------------------------
// DOM
// ---------------------------------------------------------------------------
const el = {
  stageName: document.getElementById('stage-name'),
  tempValue: document.getElementById('temp-value'),
  speedValue: document.getElementById('speed-value'),
  effValue: document.getElementById('eff-value'),
  progressBar: document.getElementById('progress-bar'),
  progressLabel: document.getElementById('progress-label'),
  offlineBanner: document.getElementById('offline-banner'),
};

// ---------------------------------------------------------------------------
// Renderer / сцена / камера
// ---------------------------------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x060b1f);
scene.fog = new THREE.FogExp2(0x060b1f, 0.012);

const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 500);
camera.position.set(8, 14, 32);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.35;
controls.minDistance = 6;
controls.maxDistance = 60;
controls.target.set(STATION_X[STAGE.COOLING], 0, 0);

// ---------------------------------------------------------------------------
// Постобработка (bloom за светещите елементи)
// ---------------------------------------------------------------------------
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  0.85, 0.55, 0.18
);
composer.addPass(bloomPass);
composer.addPass(new OutputPass());

// ---------------------------------------------------------------------------
// Светлини
// ---------------------------------------------------------------------------
scene.add(new THREE.AmbientLight(0x223355, 0.7));

const sun = new THREE.DirectionalLight(0xbfd9ff, 1.1);
sun.position.set(20, 35, 10);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -40;
sun.shadow.camera.right = 40;
sun.shadow.camera.top = 40;
sun.shadow.camera.bottom = -40;
scene.add(sun);

// ---------------------------------------------------------------------------
// Под + решетка (sci-fi лаборатория)
// ---------------------------------------------------------------------------
const floor = new THREE.Mesh(
  new THREE.PlaneGeometry(200, 60),
  new THREE.MeshStandardMaterial({ color: 0x0a1230, roughness: 0.85, metalness: 0.2 })
);
floor.rotation.x = -Math.PI / 2;
floor.position.y = -3.2;
floor.receiveShadow = true;
scene.add(floor);

const grid = new THREE.GridHelper(200, 100, 0x1b6f94, 0x0e1c38);
grid.position.y = -3.18;
scene.add(grid);

// ---------------------------------------------------------------------------
// Горещата клетка (защитен корпус около цялата линия)
// ---------------------------------------------------------------------------
const hotCell = new THREE.Mesh(
  new THREE.BoxGeometry(80, 14, 14),
  new THREE.MeshPhysicalMaterial({
    color: 0x14304a, transparent: true, opacity: 0.06,
    roughness: 0.1, metalness: 0, side: THREE.BackSide,
  })
);
hotCell.position.set(8, 3, 0);
scene.add(hotCell);

// ---------------------------------------------------------------------------
// Станция 1: Cooling pool
// ---------------------------------------------------------------------------
const coolingPool = new THREE.Mesh(
  new THREE.CylinderGeometry(3.2, 3.6, 2, 32),
  new THREE.MeshStandardMaterial({ color: 0x0d3a66, metalness: 0.6, roughness: 0.3 })
);
coolingPool.position.set(STATION_X[STAGE.COOLING], -2.2, 0);
coolingPool.receiveShadow = true;
scene.add(coolingPool);

const coolingWater = new THREE.Mesh(
  new THREE.CylinderGeometry(3.0, 3.0, 0.3, 32),
  new THREE.MeshPhysicalMaterial({
    color: 0x4fc3f7, transparent: true, opacity: 0.55,
    roughness: 0.1, transmission: 0.4, emissive: 0x1a6fa0, emissiveIntensity: 0.6,
  })
);
coolingWater.position.set(STATION_X[STAGE.COOLING], -1.1, 0);
scene.add(coolingWater);

// ---------------------------------------------------------------------------
// Станция 1.5: Shearing (механично рязане, няма backend физика)
// ---------------------------------------------------------------------------
const shearBase = new THREE.Mesh(
  new THREE.BoxGeometry(2.6, 0.4, 2.6),
  new THREE.MeshStandardMaterial({ color: 0x5a6270, metalness: 0.8, roughness: 0.3 })
);
shearBase.position.set(STATION_X[STAGE.SHEARING], -2.8, 0);
scene.add(shearBase);

const shearBlade = new THREE.Mesh(
  new THREE.BoxGeometry(2.8, 0.15, 0.4),
  new THREE.MeshStandardMaterial({ color: 0xd8dee8, metalness: 0.95, roughness: 0.15 })
);
shearBlade.position.set(STATION_X[STAGE.SHEARING], 1.5, 0);
scene.add(shearBlade);

// ---------------------------------------------------------------------------
// Станция 2: Dissolver tank (стъклен съд + издигащ се разтвор вътре)
// ---------------------------------------------------------------------------
const tankGlass = new THREE.Mesh(
  new THREE.CylinderGeometry(2.4, 2.4, 6, 32, 1, true),
  new THREE.MeshPhysicalMaterial({
    color: 0xbfe9ff, transmission: 0.9, roughness: 0.05, thickness: 0.5,
    transparent: true, opacity: 0.35, side: THREE.DoubleSide, metalness: 0,
  })
);
tankGlass.position.set(STATION_X[STAGE.DISSOLUTION], 0, 0);
scene.add(tankGlass);

const tankLiquid = new THREE.Mesh(
  new THREE.CylinderGeometry(2.2, 2.2, 1, 32),
  new THREE.MeshStandardMaterial({ color: 0xffb347, emissive: 0xff8c1a, emissiveIntensity: 0.9, roughness: 0.3 })
);
tankLiquid.position.set(STATION_X[STAGE.DISSOLUTION], -2.9, 0);
scene.add(tankLiquid);

// ---------------------------------------------------------------------------
// Станция 2.5a: Extraction contactor (две течни фази - водна/органична)
// ---------------------------------------------------------------------------
const extractionTank = new THREE.Mesh(
  new THREE.CylinderGeometry(2.0, 2.0, 4, 32, 1, true),
  new THREE.MeshPhysicalMaterial({
    color: 0xe8d9ff, transmission: 0.85, roughness: 0.05, thickness: 0.4,
    transparent: true, opacity: 0.3, side: THREE.DoubleSide, metalness: 0,
  })
);
extractionTank.position.set(STATION_X[STAGE.EXTRACTION], -1, 0);
scene.add(extractionTank);

const extractionAqueous = new THREE.Mesh(
  new THREE.CylinderGeometry(1.8, 1.8, 1.2, 32),
  new THREE.MeshStandardMaterial({ color: 0xffb347, emissive: 0xcc6a00, emissiveIntensity: 0.5, roughness: 0.3 })
);
extractionAqueous.position.set(STATION_X[STAGE.EXTRACTION], -2.4, 0);
scene.add(extractionAqueous);

const extractionOrganic = new THREE.Mesh(
  new THREE.CylinderGeometry(1.8, 1.8, 0.2, 32),
  new THREE.MeshStandardMaterial({ color: 0xc9a0ff, emissive: 0x7a3dc4, emissiveIntensity: 0.6, roughness: 0.2 })
);
extractionOrganic.position.set(STATION_X[STAGE.EXTRACTION], -1.1, 0);
scene.add(extractionOrganic);

// ---------------------------------------------------------------------------
// Станция 2.5b: Purification furnace (утаяване -> калцинация -> редукция)
// ---------------------------------------------------------------------------
const purificationFurnace = new THREE.Mesh(
  new THREE.CylinderGeometry(1.6, 1.8, 4.5, 24),
  new THREE.MeshStandardMaterial({ color: 0x6b4a3a, metalness: 0.4, roughness: 0.6 })
);
purificationFurnace.position.set(STATION_X[STAGE.PURIFICATION], -0.8, 0);
scene.add(purificationFurnace);

const purificationGlow = new THREE.Mesh(
  new THREE.CylinderGeometry(1.3, 1.3, 0.3, 24),
  new THREE.MeshStandardMaterial({ color: 0x7fffa0, emissive: 0x2a8f4a, emissiveIntensity: 0.8, roughness: 0.3 })
);
purificationGlow.position.set(STATION_X[STAGE.PURIFICATION], 1.5, 0);
scene.add(purificationGlow);

// ---------------------------------------------------------------------------
// Станция 3: Repackaging mould
// ---------------------------------------------------------------------------
const mould = new THREE.Mesh(
  new THREE.CylinderGeometry(1.5, 1.5, 5, 24, 1, true),
  new THREE.MeshStandardMaterial({ color: 0x9aa5b1, metalness: 0.85, roughness: 0.25, side: THREE.DoubleSide })
);
mould.position.set(STATION_X[STAGE.REPACKAGING], -0.5, 0);
scene.add(mould);

// ---------------------------------------------------------------------------
// Станция 4: Waste cask + капак
// ---------------------------------------------------------------------------
const wasteCask = new THREE.Mesh(
  new THREE.CylinderGeometry(2.2, 2.4, 3, 24),
  new THREE.MeshStandardMaterial({ color: 0x5a5a1e, metalness: 0.7, roughness: 0.35 })
);
wasteCask.position.set(STATION_X[STAGE.WASTE], -2, 0);
wasteCask.castShadow = true;
scene.add(wasteCask);

const wasteLid = new THREE.Mesh(
  new THREE.CylinderGeometry(2.3, 2.3, 0.4, 24),
  new THREE.MeshStandardMaterial({ color: 0x8a8a2e, metalness: 0.75, roughness: 0.3 })
);
wasteLid.position.set(STATION_X[STAGE.WASTE], 1.5, 0);
wasteLid.castShadow = true;
scene.add(wasteLid);

// ---------------------------------------------------------------------------
// Станционни точкови светлини (цветово кодирани)
// ---------------------------------------------------------------------------
const stationLights = {};
for (const [stageKey, x] of Object.entries(STATION_X)) {
  const light = new THREE.PointLight(STAGE_COLOR[stageKey], 1.2, 18, 2);
  light.position.set(Number(x), 3, 0);
  scene.add(light);
  stationLights[stageKey] = light;
}

// ---------------------------------------------------------------------------
// Роботизирана ръка
// ---------------------------------------------------------------------------
const robot = new THREE.Group();
const robotBase = new THREE.Mesh(
  new THREE.BoxGeometry(1.4, 0.6, 1.4),
  new THREE.MeshStandardMaterial({ color: 0x8892a0, metalness: 0.7, roughness: 0.3 })
);
robotBase.position.y = 5.2;
robotBase.castShadow = true;
const robotArm = new THREE.Mesh(
  new THREE.BoxGeometry(0.35, 3.4, 0.35),
  new THREE.MeshStandardMaterial({ color: 0xc9d2de, metalness: 0.6, roughness: 0.35 })
);
robotArm.position.y = 3.4;
robotArm.castShadow = true;
robot.add(robotBase, robotArm);
robot.position.x = STATION_X[STAGE.COOLING];
scene.add(robot);

// ---------------------------------------------------------------------------
// Продукт (горивото, преминаващо през станциите) + отделен отпадъчен къс
// ---------------------------------------------------------------------------
const product = new THREE.Mesh(
  new THREE.IcosahedronGeometry(1.1, 2),
  new THREE.MeshStandardMaterial({ color: 0xff7043, emissive: 0xff3d00, emissiveIntensity: 1.2, roughness: 0.3 })
);
product.position.set(STATION_X[STAGE.COOLING], 0.5, 0);
product.castShadow = true;
scene.add(product);

const wasteChunk = new THREE.Mesh(
  new THREE.IcosahedronGeometry(0.55, 1),
  new THREE.MeshStandardMaterial({ color: 0x6b8f3a, emissive: 0x3c5a1a, emissiveIntensity: 0.8, roughness: 0.4 })
);
wasteChunk.position.set(STATION_X[STAGE.DISSOLUTION], -0.5, 0);
wasteChunk.visible = false;
scene.add(wasteChunk);

// ---------------------------------------------------------------------------
// Частици (йони / мехурчета / искри — цветът зависи от активния етап)
// ---------------------------------------------------------------------------
const PARTICLE_COUNT = 260;
const particleGeometry = new THREE.BufferGeometry();
const particlePositions = new Float32Array(PARTICLE_COUNT * 3);
const particleColors = new Float32Array(PARTICLE_COUNT * 3);
const particleVelocities = new Float32Array(PARTICLE_COUNT * 3);

function spriteTexture() {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.4, 'rgba(255,255,255,0.6)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

function scatterParticles(centerX, color) {
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particlePositions[i * 3] = centerX + (Math.random() - 0.5) * 3.2;
    particlePositions[i * 3 + 1] = -3 + Math.random() * 4.5;
    particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 3.2;

    particleVelocities[i * 3] = (Math.random() - 0.5) * 0.02;
    particleVelocities[i * 3 + 1] = 0.01 + Math.random() * 0.04;
    particleVelocities[i * 3 + 2] = (Math.random() - 0.5) * 0.02;

    particleColors[i * 3] = color.r;
    particleColors[i * 3 + 1] = color.g;
    particleColors[i * 3 + 2] = color.b;
  }
  particleGeometry.attributes.position.needsUpdate = true;
  particleGeometry.attributes.color.needsUpdate = true;
}

particleGeometry.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
particleGeometry.setAttribute('color', new THREE.BufferAttribute(particleColors, 3));

const particleMaterial = new THREE.PointsMaterial({
  size: 0.28,
  map: spriteTexture(),
  vertexColors: true,
  transparent: true,
  depthWrite: false,
  blending: THREE.AdditiveBlending,
  sizeAttenuation: true,
});
const particles = new THREE.Points(particleGeometry, particleMaterial);
particles.visible = false;
scene.add(particles);

// ---------------------------------------------------------------------------
// Помощни функции
// ---------------------------------------------------------------------------
function damp(current, target, lambda, dt) {
  return current + (target - current) * (1 - Math.exp(-lambda * dt));
}

function dampVec3(obj, targetX, lambda, dt) {
  obj.position.x = damp(obj.position.x, targetX, lambda, dt);
}

function setOffline(isOffline) {
  sim.backendOnline = !isOffline;
  el.offlineBanner.classList.toggle('hidden', !isOffline);
}

// Намира стойността на values[] в момент t, чрез линейна интерполация
// спрямо времевата ос times[] (и двете идват директно от backend batch отговора).
function interpolateSeries(times, values, t) {
  if (!times || times.length === 0) return undefined;
  if (t <= times[0]) return values[0];
  if (t >= times[times.length - 1]) return values[values.length - 1];
  for (let i = 1; i < times.length; i++) {
    if (t <= times[i]) {
      const t0 = times[i - 1], t1 = times[i];
      const v0 = values[i - 1], v1 = values[i];
      const frac = t1 === t0 ? 0 : (t - t0) / (t1 - t0);
      return v0 + (v1 - v0) * frac;
    }
  }
  return values[values.length - 1];
}

async function loadStageBatch(stage) {
  const { path, params } = STAGE_REQUEST[stage]();
  const query = new URLSearchParams(
    Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)]))
  );
  try {
    const res = await fetch(`${API_BASE}/${path}?${query}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    sim.batch = { time: data.time, results: data.results };
    const lastPhysicalTime = data.time[data.time.length - 1] || 1;
    sim.timeMultiplier = Math.max(1, lastPhysicalTime / TARGET_PLAYBACK_SECONDS);
    setOffline(false);
  } catch (err) {
    setOffline(true);
    sim.batch = null;
  }
}

// ---------------------------------------------------------------------------
// Машина на състоянията
// ---------------------------------------------------------------------------
function enterStage(stage) {
  sim.stage = stage;
  sim.stageWallElapsed = 0;
  sim.batch = null;
  el.stageName.textContent = STAGE_NAMES[stage];

  if (STATION_X[stage] !== undefined) {
    const x = STATION_X[stage];
    scatterParticles(x, STAGE_COLOR[stage]);
    particles.visible = true;
  }

  if (stage === STAGE.COOLING) {
    product.position.set(STATION_X[STAGE.COOLING], 1.5, 0);
    product.scale.setScalar(1.2);
    product.material.color.set(0xff3030);
    product.material.emissive.set(0xff1a00);
    product.material.emissiveIntensity = 2.2;
  } else if (stage === STAGE.SHEARING) {
    product.position.set(STATION_X[STAGE.SHEARING], 0.3, 0);
    product.material.color.set(0xd08030);
  } else if (stage === STAGE.DISSOLUTION) {
    product.material.color.set(0xffb347);
  } else if (stage === STAGE.EXTRACTION) {
    product.scale.setScalar(0.4);
    product.material.color.set(0xc9a0ff);
    product.material.emissive.set(0x7a3dc4);
    product.material.emissiveIntensity = 1.0;
  } else if (stage === STAGE.PURIFICATION) {
    product.material.color.set(0x9fd9b0);
    product.material.emissive.set(0x2a8f4a);
    product.material.emissiveIntensity = 0.9;
  } else if (stage === STAGE.REPACKAGING) {
    wasteChunk.visible = true;
    wasteChunk.position.set(STATION_X[STAGE.DISSOLUTION], -0.5, 0);
    product.scale.setScalar(0.25);
    product.material.color.set(0x7fd9ff);
    product.material.emissive.set(0x1f8fd4);
    product.material.emissiveIntensity = 1.4;
  } else if (stage === STAGE.WASTE) {
    // waste chunk пътува визуално към станция 4 през update()
  } else if (stage === STAGE.COMPLETE) {
    particles.visible = false;
  }

  if (stage === STAGE.SHEARING) {
    particles.visible = false; // чисто механична стъпка, няма химия за показване
  } else if (stage !== STAGE.IDLE && stage !== STAGE.COMPLETE) {
    loadStageBatch(stage);
  }
}

const STAGE_SEQUENCE = [
  STAGE.COOLING, STAGE.SHEARING, STAGE.DISSOLUTION, STAGE.EXTRACTION,
  STAGE.PURIFICATION, STAGE.REPACKAGING, STAGE.WASTE, STAGE.COMPLETE,
];

function advanceStage() {
  const idx = STAGE_SEQUENCE.indexOf(sim.stage);
  if (idx >= 0 && idx + 1 < STAGE_SEQUENCE.length) {
    enterStage(STAGE_SEQUENCE[idx + 1]);
  }
}

function resetSimulation() {
  sim.speed = 1.0;
  sim.vented = false;
  sim.stage = STAGE.IDLE;
  sim.stageWallElapsed = 0;
  sim.batch = null;
  sim.displayedProgress = 0;
  sim.displayedTemp = 25;
  sim.efficiency = 0;

  particles.visible = false;
  wasteChunk.visible = false;
  wasteLid.position.set(STATION_X[STAGE.WASTE], 1.5, 0);
  product.position.set(STATION_X[STAGE.COOLING], 0.5, 0);
  product.scale.setScalar(1.2);
  product.material.color.set(0xff7043);
  product.material.emissive.set(0xff3d00);
  product.material.emissiveIntensity = 1.2;
  robot.position.x = STATION_X[STAGE.COOLING];

  el.stageName.textContent = STAGE_NAMES[STAGE.IDLE];
  el.tempValue.textContent = '—';
  el.effValue.textContent = '0%';
  el.progressBar.style.width = '0%';
  el.progressLabel.textContent = '0%';
}

// ---------------------------------------------------------------------------
// Клавиатура
// ---------------------------------------------------------------------------
function isStageActive() {
  return sim.stage !== STAGE.IDLE && sim.stage !== STAGE.COMPLETE;
}

window.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && sim.stage === STAGE.IDLE) {
    e.preventDefault();
    enterStage(STAGE.COOLING);
  } else if (e.code === 'ArrowUp') {
    sim.speed = Math.min(5, sim.speed + 0.5);
    if (isStageActive()) { sim.stageWallElapsed = 0; loadStageBatch(sim.stage); }
  } else if (e.code === 'ArrowDown') {
    sim.speed = Math.max(0.5, sim.speed - 0.5);
    if (isStageActive()) { sim.stageWallElapsed = 0; loadStageBatch(sim.stage); }
  } else if (e.code === 'KeyV' && sim.stage === STAGE.DISSOLUTION) {
    sim.vented = !sim.vented;
    sim.stageWallElapsed = 0;
    loadStageBatch(sim.stage);
  } else if (e.code === 'KeyR') {
    resetSimulation();
  }
});

// ---------------------------------------------------------------------------
// Resize
// ---------------------------------------------------------------------------
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
  bloomPass.setSize(window.innerWidth, window.innerHeight);
});

// ---------------------------------------------------------------------------
// Основен цикъл
// ---------------------------------------------------------------------------
const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);
  const dt = Math.min(0.05, clock.getDelta());

  // Движение на частиците
  if (particles.visible) {
    const pos = particleGeometry.attributes.position.array;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      pos[i * 3] += particleVelocities[i * 3] * sim.speed;
      pos[i * 3 + 1] += particleVelocities[i * 3 + 1] * sim.speed;
      pos[i * 3 + 2] += particleVelocities[i * 3 + 2] * sim.speed;
      if (pos[i * 3 + 1] > 1.5) {
        const cx = STATION_X[sim.stage] ?? 0;
        pos[i * 3 + 1] = -3;
        pos[i * 3] = cx + (Math.random() - 0.5) * 3.2;
        pos[i * 3 + 2] = (Math.random() - 0.5) * 3.2;
      }
    }
    particleGeometry.attributes.position.needsUpdate = true;
  }

  // Отчитаме реалното изминало време в текущия етап и интерполираме спрямо
  // времевата поредица, върната наведнъж от backend-а (batch формат).
  let targetProgress = 0;
  let targetTemp = sim.displayedTemp;
  if (sim.stage === STAGE.SHEARING) {
    sim.stageWallElapsed += dt;
    targetProgress = Math.min(100, (sim.stageWallElapsed / SHEARING_DURATION_S) * 100);
    if (sim.stageWallElapsed >= SHEARING_DURATION_S) advanceStage();
  } else if (isStageActive() && sim.batch) {
    sim.stageWallElapsed += dt * sim.timeMultiplier;
    const { time, results } = sim.batch;
    const progressFraction = interpolateSeries(time, results.progress, sim.stageWallElapsed) ?? 0;
    targetProgress = progressFraction * 100;
    targetTemp = interpolateSeries(time, results.temperature, sim.stageWallElapsed) ?? targetTemp;

    const lastTime = time[time.length - 1];
    if ((sim.stageWallElapsed >= lastTime && progressFraction >= 0.999) ||
        sim.stageWallElapsed > lastTime + 2) {
      advanceStage();
    }
  }
  sim.displayedProgress = damp(sim.displayedProgress, targetProgress, 6, dt);
  sim.displayedTemp = damp(sim.displayedTemp, targetTemp, 4, dt);

  // Визуални ефекти по етап
  if (sim.stage === STAGE.COOLING) {
    const frac = sim.displayedProgress / 100;
    product.material.color.setRGB(1, 0.3 - 0.3 * frac + 0.5 * frac, 0.5 * frac);
    product.material.emissiveIntensity = damp(product.material.emissiveIntensity, 2.2 * (1 - frac) + 0.2, 4, dt);
    coolingWater.material.emissiveIntensity = damp(coolingWater.material.emissiveIntensity, 0.3 + frac * 0.6, 4, dt);
  } else if (sim.stage === STAGE.SHEARING) {
    const frac = sim.displayedProgress / 100;
    shearBlade.position.y = 1.5 - Math.sin(frac * Math.PI) * 1.3;
  } else if (sim.stage === STAGE.DISSOLUTION) {
    const frac = sim.displayedProgress / 100;
    product.scale.setScalar(damp(product.scale.x, 1.2 * (1 - frac * 0.85), 4, dt));
    tankLiquid.scale.y = damp(tankLiquid.scale.y, 1 + frac * 5, 3, dt);
    tankLiquid.position.y = damp(tankLiquid.position.y, -2.9 + frac * 2.6, 3, dt);
  } else if (sim.stage === STAGE.EXTRACTION) {
    const frac = sim.displayedProgress / 100;
    extractionOrganic.scale.y = damp(extractionOrganic.scale.y, 1 + frac * 4, 3, dt);
    extractionAqueous.scale.y = damp(extractionAqueous.scale.y, 1 - frac * 0.7, 3, dt);
    extractionOrganic.material.emissiveIntensity = damp(extractionOrganic.material.emissiveIntensity, 0.4 + frac * 1.0, 4, dt);
  } else if (sim.stage === STAGE.PURIFICATION) {
    const frac = sim.displayedProgress / 100;
    product.material.color.setRGB(0.62 + frac * 0.3, 0.85, 0.69 - frac * 0.3);
    purificationGlow.material.emissiveIntensity = damp(purificationGlow.material.emissiveIntensity, 0.4 + frac * 1.4, 4, dt);
  } else if (sim.stage === STAGE.REPACKAGING) {
    const frac = sim.displayedProgress / 100;
    product.scale.setScalar(damp(product.scale.x, 0.25 + frac * 1.0, 4, dt));
    mould.material.emissive = mould.material.emissive || new THREE.Color(0x000000);
    mould.material.emissive.setRGB(frac * 0.6, frac * 0.5, frac * 0.3);
    mould.material.emissiveIntensity = frac * 0.8;
  } else if (sim.stage === STAGE.WASTE) {
    const frac = sim.displayedProgress / 100;
    dampVec3(wasteChunk, STATION_X[STAGE.WASTE], 1.2, dt);
    wasteChunk.material.emissiveIntensity = damp(wasteChunk.material.emissiveIntensity, 0.5 + frac * 1.5, 4, dt);
    wasteChunk.material.color.setRGB(0.4 + frac * 0.1, 0.56 - frac * 0.1, 0.23 + frac * 0.4);
    if (frac > 0.97) {
      wasteLid.position.y = damp(wasteLid.position.y, 0.5, 4, dt);
    }
  }

  // Роботизирана ръка следва активната станция
  const robotTargetX = STATION_X[sim.stage] ?? STATION_X[STAGE.COOLING];
  dampVec3(robot, robotTargetX, 3, dt);

  // Камерата следва активната станция (само фокус, не позиция — orbit остава свободен)
  const focusX = STATION_X[sim.stage] ?? STATION_X[STAGE.COOLING];
  controls.target.x = damp(controls.target.x, focusX, 1.5, dt);

  // UI
  el.speedValue.textContent = `${sim.speed.toFixed(2)}x`;
  el.progressBar.style.width = `${sim.displayedProgress.toFixed(1)}%`;
  el.progressLabel.textContent = `${sim.displayedProgress.toFixed(0)}%`;
  if (sim.stage !== STAGE.IDLE) {
    el.tempValue.textContent = `${sim.displayedTemp.toFixed(0)} °C`;
  }
  if (sim.stage === STAGE.REPACKAGING || sim.stage === STAGE.WASTE || sim.stage === STAGE.COMPLETE) {
    sim.efficiency = Math.min(99, 85 + sim.speed * 3);
    el.effValue.textContent = `${sim.efficiency.toFixed(0)}%`;
  }

  controls.update();
  composer.render();
}

animate();
