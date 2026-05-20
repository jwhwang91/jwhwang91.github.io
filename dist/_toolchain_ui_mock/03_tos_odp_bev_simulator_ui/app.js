let frame = 0;
let playing = true;
const maxFrame = 100;

// Canvas/world convention:
// x: lateral px from canvas center, y: longitudinal px from ego upward.
// Actual road has varying curvature. Ego prediction uses a constant-radius arc from R = Vx/yawrate.

function clamp(v, min=0, max=1){ return Math.max(min, Math.min(max, v)); }

function egoSignals(f){
  const t = f / maxFrame;
  const vxKph = 49 + 2.0 * Math.sin(t * Math.PI * 2);
  const vxMps = vxKph / 3.6;
  const yaw = 0.041 + 0.004 * Math.sin(t * Math.PI * 2 + 0.7); // rad/s
  const rMeter = vxMps / yaw;
  // Pixel radius is intentionally scaled for BEV readability.
  const rPx = 720 + 35 * Math.sin(t * Math.PI * 2 + 0.7);
  return { vxKph, vxMps, yaw, rMeter, rPx };
}

function egoConstR_X(yPx, rPx){
  // Constant left-turn arc from current Vx/yawrate: x = -R + sqrt(R^2 - y^2)
  // For y << R this approximates -y^2/(2R). Negative x means left curve.
  const y = Math.min(yPx, rPx * 0.92);
  return -rPx + Math.sqrt(Math.max(0, rPx*rPx - y*y));
}

function actualRoadX(yPx){
  // Actual road curvature is intentionally non-constant.
  // It bends more aggressively in the far field, then eases, which creates mismatch vs ego constant R.
  return -Math.pow(yPx, 2) / (2 * 430) - 34 * Math.sin(yPx / 185) + 22 * Math.sin(yPx / 78);
}

function actualRoadSlope(yPx){
  const dy = 1;
  return (actualRoadX(yPx + dy) - actualRoadX(yPx - dy)) / (2 * dy);
}

function actualRoadPoint(yPx, offsetPx=0){
  const x = actualRoadX(yPx);
  const slope = actualRoadSlope(yPx);
  // tangent in world coordinates: (dx/dy, 1)
  // canvas uses y-up converted to screen y-down later, so vehicle long-axis rotation should follow atan(slope).
  const len = Math.hypot(1, -slope);
  const nx = 1 / len;
  const ny = -slope / len;
  return {
    x: x + nx * offsetPx,
    y: yPx + ny * offsetPx,
    angle: Math.atan(slope)
  };
}

function toCanvas(p){
  return { x: 520 + p.x, y: 640 - p.y };
}

function trackStates(f){
  const t = f / maxFrame;
  const base = [
    {id:'Track1', y:170, lane:118},
    {id:'Track2', y:260, lane:112},
    {id:'Track3', y:355, lane:108},
    {id:'Track4', y:455, lane:62},   // intentionally close enough to ego constant-R corridor in far field
    {id:'Track5', y:540, lane:116}
  ];
  const sig = egoSignals(f);
  return base.map((b, i) => {
    const y = ((b.y + 88*t) % 560) + 40;
    // Adjacent lane traffic follows the actual road geometry.
    const laneOffset = b.lane + 6 * Math.sin(t*4 + i);
    const p = actualRoadPoint(y, laneOffset);
    const egoX = egoConstR_X(y, sig.rPx);
    const distToEgoCorridor = Math.abs(p.x - egoX);
    // false candidate if adjacent-lane track falls inside ego constant-R corridor
    const falseCandidate = distToEgoCorridor < 43 && y > 260;
    return {...b, y, x:p.x, cy:p.y, angle:p.angle, distToEgoCorridor, falseCandidate};
  });
}

function drawActualLane(ctx, offset, style='solid'){
  ctx.save();
  ctx.strokeStyle = '#111827';
  ctx.lineWidth = 2.2;
  ctx.setLineDash(style === 'dash' ? [14,10] : []);
  ctx.beginPath();
  for(let y=0; y<=610; y+=5){
    const p = actualRoadPoint(y, offset);
    const c = toCanvas(p);
    if(y===0) ctx.moveTo(c.x, c.y); else ctx.lineTo(c.x, c.y);
  }
  ctx.stroke();
  ctx.restore();
}

function drawEgoR(ctx){
  const sig = egoSignals(frame);
  ctx.save();

  // filled corridor around constant-R ego path
  ctx.fillStyle = 'rgba(37,99,235,0.10)';
  ctx.beginPath();
  for(let y=0; y<=610; y+=5){
    const x = egoConstR_X(y, sig.rPx) - 42;
    const c = toCanvas({x, y});
    if(y===0) ctx.moveTo(c.x, c.y); else ctx.lineTo(c.x, c.y);
  }
  for(let y=610; y>=0; y-=5){
    const x = egoConstR_X(y, sig.rPx) + 42;
    const c = toCanvas({x, y});
    ctx.lineTo(c.x, c.y);
  }
  ctx.closePath();
  ctx.fill();

  // centerline
  ctx.strokeStyle = '#2563eb';
  ctx.lineWidth = 3.2;
  ctx.beginPath();
  for(let y=0; y<=610; y+=5){
    const x = egoConstR_X(y, sig.rPx);
    const c = toCanvas({x, y});
    if(y===0) ctx.moveTo(c.x, c.y); else ctx.lineTo(c.x, c.y);
  }
  ctx.stroke();

  // corridor boundaries
  ctx.strokeStyle = 'rgba(37,99,235,.55)';
  ctx.lineWidth = 1.5;
  [-42, 42].forEach(offset => {
    ctx.beginPath();
    for(let y=0; y<=610; y+=5){
      const x = egoConstR_X(y, sig.rPx) + offset;
      const c = toCanvas({x, y});
      if(y===0) ctx.moveTo(c.x, c.y); else ctx.lineTo(c.x, c.y);
    }
    ctx.stroke();
  });

  ctx.restore();
}

function roundedRect(ctx,x,y,w,h,r){
  ctx.beginPath();
  ctx.moveTo(x+r,y);
  ctx.arcTo(x+w,y,x+w,y+h,r);
  ctx.arcTo(x+w,y+h,x,y+h,r);
  ctx.arcTo(x,y+h,x,y,r);
  ctx.arcTo(x,y,x+w,y,r);
  ctx.closePath();
}

function drawVehicle(ctx, tr){
  const c = toCanvas({x: tr.x, y: tr.cy});
  ctx.save();
  ctx.translate(c.x, c.y);
  ctx.rotate(tr.angle);
  ctx.fillStyle = '#ffffff';
  ctx.strokeStyle = tr.falseCandidate ? '#ef4444' : '#111827';
  ctx.lineWidth = tr.falseCandidate ? 3 : 2;
  roundedRect(ctx, -19, -31, 38, 62, 4);
  ctx.fill();
  ctx.stroke();
  // Small heading marker, aligned with vehicle orientation
  ctx.strokeStyle = tr.falseCandidate ? '#ef4444' : '#111827';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(0, -31);
  ctx.lineTo(0, -43);
  ctx.stroke();
  ctx.restore();

  ctx.fillStyle = tr.falseCandidate ? '#ef4444' : '#111827';
  ctx.font = tr.falseCandidate ? '23px system-ui' : '21px system-ui';
  ctx.fillText(tr.id, c.x + 20, c.y + 4);

  if(tr.falseCandidate){
    ctx.font = '18px system-ui';
    ctx.fillText('False Detection', c.x + 22, c.y + 30);
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(c.x, c.y, 43, 0, Math.PI*2);
    ctx.stroke();
  }
}

function drawEgo(ctx){
  const p = toCanvas({x:0, y:0});
  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.fillStyle = '#ffffff';
  ctx.strokeStyle = '#111827';
  ctx.lineWidth = 2.6;
  roundedRect(ctx, -28, -45, 56, 90, 5);
  ctx.fill();
  ctx.stroke();
  ctx.restore();

  ctx.fillStyle = '#111827';
  ctx.font = '34px system-ui';
  ctx.fillText('EGO', p.x - 36, p.y + 64);
}

function drawLabels(ctx){
  const sig = egoSignals(frame);
  ctx.fillStyle = '#111827';
  ctx.font = '26px system-ui';
  ctx.fillText('Actual road: varying R', 44, 48);
  ctx.strokeStyle = '#111827';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(44, 57);
  ctx.lineTo(288, 57);
  ctx.stroke();

  ctx.fillStyle = '#2563eb';
  ctx.font = '20px system-ui';
  ctx.fillText(`Ego RoadRadius = Vx / yawrate ≈ ${sig.rMeter.toFixed(0)} m`, 390, 48);
  ctx.fillStyle = '#64748b';
  ctx.font = '13px system-ui';
  ctx.fillText('Blue corridor is constant-R prediction from ego. Black lanes are the actual curved road.', 390, 70);
}

function drawBEV(){
  const c = document.getElementById('bev');
  const ctx = c.getContext('2d');
  ctx.clearRect(0,0,c.width,c.height);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0,0,c.width,c.height);

  // actual variable-curvature road lanes
  [-85, -20, 45, 110].forEach((offset, i) => drawActualLane(ctx, offset, i === 2 ? 'dash' : 'solid'));

  // ego constant R prediction overlay
  drawEgoR(ctx);

  // objects in adjacent lane follow the actual road
  trackStates(frame).forEach(tr => drawVehicle(ctx, tr));

  drawEgo(ctx);
  drawLabels(ctx);

  ctx.fillStyle = '#475569';
  ctx.font = '14px system-ui';
  ctx.fillText('Key point: far adjacent-lane traffic may overlap the ego constant-R corridor even when the real road curvature differs.', 32, c.height - 22);
}

function updatePanel(){
  const sig = egoSignals(frame);
  const tracks = trackStates(frame);
  const falseTracks = tracks.filter(t => t.falseCandidate);

  document.getElementById('speedVal').textContent = sig.vxKph.toFixed(0);
  document.getElementById('yawVal').textContent = sig.yaw.toFixed(3);
  document.getElementById('rVal').textContent = sig.rMeter.toFixed(0);
  document.getElementById('targetVal').textContent = falseTracks.length ? falseTracks.map(t => t.id).join(',') : 'NONE';
  document.getElementById('frameLabel').textContent = 'frame ' + String(frame).padStart(3,'0');
  document.getElementById('frameSlider').value = frame;

  document.getElementById('objectTable').innerHTML = tracks.map(t => `
    <tr>
      <td>${t.id}</td>
      <td>adjacent lane</td>
      <td><span class="flag ${t.falseCandidate ? 'bad' : 'good'}">${t.falseCandidate ? 'False Detection' : 'excluded'}</span></td>
    </tr>
  `).join('');

  document.getElementById('decisionText').textContent = falseTracks.length
    ? `${falseTracks.map(t=>t.id).join(', ')} falls inside the ego constant-R RoadRadius corridor. This visualizes the false-detection risk: actual road curvature is not constant, but ego path prediction is drawn from current Vx/yawrate.`
    : 'No adjacent-lane track overlaps the ego constant-R RoadRadius corridor at this frame.';
}

function log(msg, type='good'){
  const l = document.getElementById('eventLog');
  const d = document.createElement('div');
  d.className = type;
  d.textContent = msg;
  l.prepend(d);
  while(l.children.length > 10) l.removeChild(l.lastChild);
}

let lastFalse = false;
function render(){
  updatePanel();
  drawBEV();

  const hasFalse = trackStates(frame).some(t => t.falseCandidate);
  if(hasFalse && !lastFalse) log('Adjacent-lane track entered ego RoadRadius corridor → False Detection', 'warn');
  if(!hasFalse && lastFalse) log('Track exited ego RoadRadius corridor', 'good');
  lastFalse = hasFalse;
}

function tick(){
  if(playing){
    frame = (frame + 1) % maxFrame;
    render();
  }
  requestAnimationFrame(() => setTimeout(tick, 90));
}

document.getElementById('playBtn').onclick = () => {
  playing = !playing;
  document.getElementById('playBtn').textContent = playing ? 'Pause' : 'Play';
};
document.getElementById('resetBtn').onclick = () => {
  frame = 0;
  render();
  log('scenario reset', 'good');
};
document.getElementById('frameSlider').oninput = e => {
  frame = Number(e.target.value);
  playing = false;
  document.getElementById('playBtn').textContent = 'Play';
  render();
};

log('loaded Vx/yawrate RoadRadius false-detection scenario', 'good');
render();
tick();
