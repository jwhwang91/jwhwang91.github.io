const mockSignals = ['signal1','signal2','signal3','signal4','signal5','signal6','signal7','signal8'];

const signalMeta = {};
mockSignals.forEach((name, i) => {
  signalMeta[name] = {
    name,
    description: i < 6 ? 'Synthetic measurement stream for public mock UI' : 'Synthetic characteristic/debug value for public mock UI',
    ecuAddress: '0x' + (0x10100000 + i * 0x10).toString(16).toUpperCase(),
    type: i < 6 ? 'MEASUREMENT' : 'CHARACTERISTIC',
    dataType: ['SLONG','ULONG','UWORD','UBYTE','FLOAT'][i % 5],
    variable: 'mock_symbol_' + String(i + 1).padStart(2, '0'),
    unit: i % 3 === 0 ? 'deg' : (i % 3 === 1 ? 'm/s' : 'arb'),
    setting: '0 ~ ' + (10 + i).toFixed(0),
    range: '-' + (40 + i).toFixed(1) + ' ~ ' + (40 + i).toFixed(1),
    symbol: name
  };
});

const listEl = document.getElementById('signalList');
const searchEl = document.getElementById('signalSearch');
const countEl = document.getElementById('signalCount');
const signalInfoEl = document.getElementById('signalInfo');
const xcpRoot = document.getElementById('xcpRoot');
const runStatusEl = document.getElementById('runStatus');
const jitterAvgEl = document.getElementById('jitterAvg');
const jitterMaxEl = document.getElementById('jitterMax');

let selectedSignal = mockSignals[1];
let running = false;
let tickIndex = 0;
let lastTs = performance.now();
let jitterHistory = [];
let chartHistory = [];
let animationHandle = null;

const measurementFns = [
  t => 82 + 8 * Math.sin(t / 12),
  t => 4.2 + 1.4 * Math.sin(t / 15 + 0.4),
  t => 0.14 + 0.035 * Math.sin(t / 10 + 1.0),
  t => 0.88 - 0.18 * Math.exp(-Math.pow((t - 80) / 18, 2)),
  t => 46 + 12 * Math.sin(t / 19),
  t => 0.33 + 0.17 * Math.sin(t / 11 + 0.7)
];

function renderSignalList() {
  const q = searchEl.value.trim().toLowerCase();
  const rows = mockSignals.filter(s => s.toLowerCase().includes(q));
  countEl.textContent = rows.length.toLocaleString();
  listEl.innerHTML = rows.map(name => `
    <li class="${name === selectedSignal ? 'selected' : ''}" data-name="${name}">
      ${name}
      <small>${signalMeta[name].type} · ${signalMeta[name].ecuAddress}</small>
    </li>`).join('');
  listEl.querySelectorAll('li').forEach(li => li.onclick = () => {
    selectedSignal = li.dataset.name;
    renderSignalList();
    renderSignalInfo();
  });
}

function renderSignalInfo() {
  const s = signalMeta[selectedSignal];
  document.getElementById('selectedType').textContent = s.type;
  signalInfoEl.innerHTML = `
    <dt>Name</dt><dd>${s.name}</dd>
    <dt>Description</dt><dd>${s.description}</dd>
    <dt>ECU_ADDRESS</dt><dd>${s.ecuAddress}</dd>
    <dt>Data Type</dt><dd>${s.dataType}</dd>
    <dt>Conversion/Symbol</dt><dd>${s.variable}</dd>
    <dt>Unit</dt><dd>${s.unit}</dd>
    <dt>Setting</dt><dd>${s.setting}</dd>
    <dt>Range</dt><dd>${s.range}</dd>
    <dt>Symbol</dt><dd>${s.symbol}</dd>
  `;
}

function getPortXY(nodeId, kind) {
  const workspace = document.getElementById('workspace');
  const wRect = workspace.getBoundingClientRect();
  const node = document.querySelector(`#${nodeId} .port.${kind}`);
  const rect = node.getBoundingClientRect();
  return { x: rect.left - wRect.left + rect.width / 2, y: rect.top - wRect.top + rect.height / 2 };
}

function cubicPath(a, b) {
  const dx = (b.x - a.x) * 0.45;
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
}

function renderLinks() {
  const svg = document.getElementById('linkLayer');
  const links = [
    ['m1','out','model1','in'],['m2','out','model1','in'],['m3','out','model1','in'],['m4','out','model1','in'],['m5','out','model1','in'],['m6','out','model1','in'],
    ['model1','out','model2','in'],['model1','out','model3','in'],['model2','out','model4','in'],['model3','out','model4','in'],['model4','out','characteristic','in']
  ];
  svg.innerHTML = links.map(([a, ak, b, bk]) => `<path d="${cubicPath(getPortXY(a, ak), getPortXY(b, bk))}"></path>`).join('');
}

function makeMeasurementValues(t) { return measurementFns.map(fn => fn(t)); }

function updateValues(t) {
  const m = makeMeasurementValues(t);
  document.querySelectorAll('[data-measure]').forEach(el => {
    const idx = Number(el.dataset.measure);
    el.textContent = m[idx].toFixed(idx < 3 ? 2 : 3);
  });
  const model1a = 0.55 * m[0] / 100 + 0.25 * m[1] / 10 + 0.12 * m[2] * 3;
  const model1b = 0.60 * m[3] + 0.01 * m[4] + 0.22 * m[5];
  const model2 = 0.65 * model1a + 0.25 * Math.sin(t / 17);
  const model3 = 0.75 * model1b + 0.06 * Math.cos(t / 13);
  const model4 = 0.58 * model2 + 0.42 * model3;
  const ecuOut = Math.max(0, Math.min(1, model4));

  document.getElementById('model1Val').textContent = `${model1a.toFixed(3)} / ${model1b.toFixed(3)}`;
  document.getElementById('model2Val').textContent = model2.toFixed(3);
  document.getElementById('model3Val').textContent = model3.toFixed(3);
  document.getElementById('model4Val').textContent = model4.toFixed(3);
  document.getElementById('ecuOutVal').textContent = ecuOut.toFixed(3);

  const now = performance.now();
  const cycle = now - lastTs;
  lastTs = now;
  const jitter = Math.abs(cycle - 16.7) * 0.055 + 0.85 + 0.35 * Math.abs(Math.sin(t / 7));
  jitterHistory.push(jitter);
  if (jitterHistory.length > 180) jitterHistory.shift();
  const avg = jitterHistory.reduce((a, b) => a + b, 0) / jitterHistory.length;
  const max = Math.max(...jitterHistory);
  jitterAvgEl.textContent = `${avg.toFixed(2)} ms`;
  jitterMaxEl.textContent = `${max.toFixed(2)} ms`;

  chartHistory.push({ speed: m[0], yaw: m[2], modelOut: model4, ecuOut, jitter });
  if (chartHistory.length > 140) chartHistory.shift();
  drawChart();
}

function drawGrid(ctx, w, h) {
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = '#e7eaf0';
  ctx.lineWidth = 1;
  for (let x = 42; x < w; x += 70) { ctx.beginPath(); ctx.moveTo(x, 18); ctx.lineTo(x, h - 28); ctx.stroke(); }
  for (let y = 24; y < h - 20; y += 38) { ctx.beginPath(); ctx.moveTo(42, y); ctx.lineTo(w - 16, y); ctx.stroke(); }
}
function drawSeries(ctx, arr, key, color, min, max, w, h) {
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  arr.forEach((row, i) => {
    const x = 44 + i / Math.max(arr.length - 1, 1) * (w - 70);
    const y = h - 30 - (row[key] - min) / (max - min) * (h - 60);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}
function drawChart() {
  const c = document.getElementById('liveChart');
  const ctx = c.getContext('2d');
  const w = c.width, h = c.height;
  drawGrid(ctx, w, h);
  drawSeries(ctx, chartHistory, 'speed', '#1f4fd8', 65, 95, w, h);
  drawSeries(ctx, chartHistory, 'yaw', '#0f766e', 0.08, 0.20, w, h);
  drawSeries(ctx, chartHistory, 'modelOut', '#d946ef', -0.2, 1.1, w, h);
  drawSeries(ctx, chartHistory, 'ecuOut', '#d97706', -0.2, 1.1, w, h);
  ctx.fillStyle = '#334155';
  ctx.font = '11px system-ui';
  const labels = [['VehSpd', '#1f4fd8'], ['YawRate', '#0f766e'], ['Model4', '#d946ef'], ['ECU Write', '#d97706']];
  labels.forEach((l, i) => { ctx.fillStyle = l[1]; ctx.fillRect(54 + i * 120, h - 16, 12, 3); ctx.fillStyle = '#334155'; ctx.fillText(l[0], 71 + i * 120, h - 12); });
}

function loop() {
  if (running) {
    tickIndex += 1;
    updateValues(tickIndex);
  }
  animationHandle = requestAnimationFrame(loop);
}

function setRunning(state) {
  running = state;
  document.getElementById('startBtn').disabled = state;
  document.getElementById('stopBtn').disabled = !state;
  document.getElementById('workspace').classList.toggle('xcp-running', state);
  xcpRoot.classList.toggle('xcp-running', state);
  runStatusEl.textContent = state ? 'Online' : 'Offline';
  if (!state) {
    jitterAvgEl.textContent = '—';
    jitterMaxEl.textContent = '—';
    jitterHistory = [];
  }
}

window.addEventListener('resize', renderLinks);
searchEl.addEventListener('input', renderSignalList);
document.getElementById('startBtn').onclick = () => setRunning(true);
document.getElementById('stopBtn').onclick = () => setRunning(false);
document.getElementById('addModelBtn').onclick = () => alert('Public mock: additional TimeSeries AI stages are hidden in this demo.');
document.getElementById('allGraphBtn').onclick = () => drawChart();

renderSignalList();
renderSignalInfo();
renderLinks();
drawChart();
loop();
