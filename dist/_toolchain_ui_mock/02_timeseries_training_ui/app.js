let epoch = 0;
let running = false;
let currentModel = 'LSTM';
const history = [];

const hyperByModel = {
  LSTM: [
    ['seq_len','100'], ['hidden_size','64'], ['num_layers','2'], ['dropout','0.100000'],
    ['lr','0.002000'], ['batch size','64'], ['epochs','20'], ['optimizer','Adam']
  ],
  TCN: [
    ['seq_len','100'], ['levels','5'], ['hidden channels','64'], ['kernel size','3'],
    ['dilation base','2'], ['dropout','0.100000'], ['lr','0.002000'], ['optimizer','Adam']
  ],
  Transformer: [
    ['seq_len','128'], ['d_model','128'], ['num_heads','4'], ['encoder_layers','3'],
    ['dropout','0.100000'], ['lr','0.000800'], ['batch size','32'], ['optimizer','AdamW']
  ],
  my_models: [
    ['my_parameter1','0.750000'], ['my_parameter2','64'], ['my_parameter3','custom_gate'], ['my_parameter4','true'],
    ['seq_len','100'], ['lr','0.001000'], ['epochs','20'], ['optimizer','Adam']
  ]
};

function renderHyper(model) {
  const grid = document.getElementById('hyperGrid');
  grid.innerHTML = hyperByModel[model].map(([k, v]) => `<div>${k}</div><input value="${v}" />`).join('');
  document.getElementById('trainStatus').textContent = `Status Printing Area
Data prepared. X:(1355,4,100), y:(1355,5), Input_dim=4, Output_dim=5
Initialized model: ${model}
Hyperparameters loaded for ${model}
Waiting for training...`;
  document.getElementById('resultInfo').textContent = `Loaded model: D:/AI_Development_1/${model}_mock.pt
Model class: ${model}
Task: Regression
seq_len: ${hyperByModel[model][0][1]}
input_dim: 4
output_dim: 5`;
}

function drawGrid(ctx, w, h) {
  ctx.clearRect(0,0,w,h);
  ctx.fillStyle = '#050607';
  ctx.fillRect(0,0,w,h);
  ctx.strokeStyle = 'rgba(255,255,255,.06)';
  ctx.lineWidth = 1;
  for (let x = 40; x < w; x += 25) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
  for (let y = 20; y < h; y += 20) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }
}
function drawSeries(ctx, arr, key, color, min, max, w, h) {
  ctx.beginPath(); ctx.strokeStyle = color; ctx.lineWidth = 2;
  arr.forEach((r, i) => {
    const x = 40 + i / Math.max(arr.length - 1, 1) * (w - 60);
    const y = h - 24 - (r[key] - min) / (max - min) * (h - 40);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}
function drawChart() {
  const c = document.getElementById('resultChart');
  const ctx = c.getContext('2d');
  const w = c.width, h = c.height;
  drawGrid(ctx, w, h);
  drawSeries(ctx, history, 'pred', '#ff8b3d', 0, 1, w, h);
  drawSeries(ctx, history, 'gt', '#4fd1ff', 0, 1, w, h);
  ctx.fillStyle = '#d1d5db';
  ctx.font = '11px system-ui';
  ctx.fillText('Prediction', 52, 18);
  ctx.fillStyle = '#ff8b3d'; ctx.fillRect(120, 12, 12, 2);
  ctx.fillStyle = '#d1d5db'; ctx.fillText('Ground Truth', 160, 18);
  ctx.fillStyle = '#4fd1ff'; ctx.fillRect(248, 12, 12, 2);
}

function appendStatus(line) {
  const box = document.getElementById('trainStatus');
  box.textContent += '\n' + line;
  box.scrollTop = box.scrollHeight;
}

function stepTrain() {
  if (!running) return;
  epoch += 1;
  const modelOffset = currentModel === 'my_models' ? 0.04 : currentModel === 'Transformer' ? 0.02 : 0;
  const pred = 0.15 + 0.75 * (1 - Math.exp(-epoch / 6)) + 0.05 * Math.sin(epoch / 2) + modelOffset;
  const gt = 0.18 + 0.68 * (1 - Math.exp(-epoch / 7));
  history.push({ pred, gt });
  if (history.length > 30) history.shift();
  drawChart();
  appendStatus(`Epoch ${epoch}: train_loss=${(0.95*Math.exp(-epoch/6)+0.04).toFixed(4)}, val_loss=${(0.82*Math.exp(-epoch/7)+0.06).toFixed(4)}`);
  document.getElementById('resultInfo').textContent = `Loaded model: D:/AI_Development_1/${currentModel}_mock.pt
Model class: ${currentModel}
Task: Regression
seq_len: ${hyperByModel[currentModel][0][1]}
input_dim: 4
output_dim: 5
Current epoch: ${epoch}
Status: training...`;
  if (epoch >= 20) {
    running = false;
    appendStatus('Training finished.');
    document.getElementById('resultInfo').textContent = `Loaded model: D:/AI_Development_1/${currentModel}_mock.pt
Model class: ${currentModel}
Task: Regression
seq_len: ${hyperByModel[currentModel][0][1]}
input_dim: 4
output_dim: 5
Status: training complete`;
    return;
  }
  setTimeout(stepTrain, 260);
}

document.getElementById('modelList').querySelectorAll('.model-item').forEach(item => {
  item.onclick = () => {
    document.querySelectorAll('.model-item').forEach(x => x.classList.remove('active'));
    item.classList.add('active');
    currentModel = item.dataset.model;
    renderHyper(currentModel);
    history.length = 0;
    drawChart();
  };
});
document.getElementById('tuneBtn').onclick = () => appendStatus('Hyper Parameter Tuning dialog opened (public mock).');
document.getElementById('trainBtn').onclick = () => {
  if (running) return;
  running = true; epoch = 0; history.length = 0; drawChart();
  document.getElementById('trainStatus').textContent = `Status Printing Area
Data prepared. X:(1355,4,100), y:(1355,5), Input_dim=4, Output_dim=5
Initialized model: ${currentModel}
Training started...`;
  stepTrain();
};

renderHyper(currentModel);
drawChart();
