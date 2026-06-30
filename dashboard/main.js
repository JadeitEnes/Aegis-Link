// ── Gaze canvas ──────────────────────────────────────────────────
const canvas  = document.getElementById('gaze-canvas');
const ctx     = canvas.getContext('2d');
const TRAIL_LEN = 30;
const SMOOTH    = 0.15;

let targetX = canvas.width  / 2;
let targetY = canvas.height / 2;
let smoothX = targetX, smoothY = targetY;
const trail = [];

function drawFrame() {
    smoothX += (targetX - smoothX) * SMOOTH;
    smoothY += (targetY - smoothY) * SMOOTH;
    trail.push({ x: smoothX, y: smoothY });
    if (trail.length > TRAIL_LEN) trail.shift();

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = '#100514';
    ctx.lineWidth = 1;
    for (let x = 0; x <= canvas.width; x += 64) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height); ctx.stroke();
    }

    for (let i = 1; i < trail.length; i++) {
        const alpha = i / trail.length;
        ctx.beginPath();
        ctx.strokeStyle = `rgba(88,166,255,${alpha * 0.5})`;
        ctx.lineWidth = alpha * 3;
        ctx.moveTo(trail[i-1].x, trail[i-1].y);
        ctx.lineTo(trail[i].x,   trail[i].y);
        ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(smoothX, smoothY, 18, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(63,185,80,0.15)';
    ctx.fill();
    ctx.strokeStyle = '#3fb950';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(smoothX, smoothY, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#3fb950';
    ctx.fill();

    requestAnimationFrame(drawFrame);
}
requestAnimationFrame(drawFrame);

// ── Status ────────────────────────────────────────────────────────
const EVENT_LABELS  = { LEFT_BLINK: 'Sol Göz', RIGHT_BLINK: 'Sağ Göz', BOTH_BLINK: 'Her İki Göz' };
const ACTION_LABELS = { LEFT_BLINK: 'Tıklama', RIGHT_BLINK: 'Scroll',  BOTH_BLINK: 'Çift Tıklama' };

function setStatus(state) {
    const labels = {
        connected:    'Bağlı — Aktif',
        degraded:     'Bağlı — Publisher durdu',
        disconnected: 'Yeniden bağlanıyor...',
    };
    document.getElementById('status-dot').className    = state;
    document.getElementById('status-label').textContent = labels[state] || state;
}

function updateGazeUI(msg) {
    targetX = msg.gaze_x * canvas.width;
    targetY = msg.gaze_y * canvas.height;
    document.getElementById('stat-frame').textContent = msg.frame_id;
    document.getElementById('stat-conf').textContent  = (msg.confidence * 100).toFixed(0) + '%';
    document.getElementById('stat-lat').textContent   = msg.latency_us.toFixed(0) + 'µs';
    document.getElementById('stat-pos').textContent   = `${msg.gaze_x.toFixed(3)}, ${msg.gaze_y.toFixed(3)}`;
    updateEye('left',  msg.left_eye_open  === 1);
    updateEye('right', msg.right_eye_open === 1);
    updateLatencyBar(msg.latency_us);
}

function updateEye(side, isOpen) {
    const box  = document.getElementById(`eye-${side}`);
    const icon = document.getElementById(`eye-${side}-icon`);
    box.className  = 'eye-box ' + (isOpen ? 'open' : 'closed');
    icon.textContent = isOpen ? '👁' : '-_-';
}

function updateLatencyBar(us) {
    const bar = document.getElementById('latency-bar');
    bar.style.width      = Math.min(us / 10000 * 100, 100) + '%';
    bar.style.background = us < 3000 ? '#3fb950' : us < 7000 ? '#d29922' : '#f85149';
}

function addEvent(ev) {
    const log  = document.getElementById('event-log');
    const item = document.createElement('div');
    item.className = `ev-item ${ev.event_type}`;
    item.innerHTML = `
        <div class="ev-type">
            ${EVENT_LABELS[ev.event_type] || ev.event_type}
            <span style="color:#8d96a0;font-weight:400;font-size:11px;margin-left:6px;">
                → ${ACTION_LABELS[ev.event_type] || ''}
            </span>
        </div>
        <div class="ev-meta">${ev.duration_ms.toFixed(0)}ms &nbsp;|&nbsp; (${ev.gaze_x.toFixed(3)}, ${ev.gaze_y.toFixed(3)})</div>`;
    log.prepend(item);
    if (log.children.length > 30) log.removeChild(log.lastChild);
}

// ── WebSocket ─────────────────────────────────────────────────────
let ws;

function connect() {
    ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onopen  = () => setStatus('connected');
    ws.onclose = () => { setStatus('disconnected'); setTimeout(connect, 2000); };
    ws.onerror = () => ws.close();
    ws.onmessage = ({ data }) => {
        const msg = JSON.parse(data);
        if (msg.type === 'gaze')           updateGazeUI(msg);
        if (msg.type === 'event')          addEvent(msg);
        if (msg.type === 'cal_progress')   onCalProgress(msg.progress);
        if (msg.type === 'cal_point_done') onCalPointDone();
        if (msg.type === 'cal_done')       onCalDone(msg.success);
        if (msg.type === 'center_init')    onCenterInit(msg.progress);
        if (msg.type === 'center_set')     onCenterSet(msg.center_x, msg.center_y);
        if (msg.type === 'center_reset')   onCenterReset();
    };
}
connect();

// Klavye kısayolları
document.addEventListener('keydown', (e) => {
    if (e.key === 'c' || e.key === 'C') {
        startCalibration();
    }
    if (e.key === ' ') {
        e.preventDefault();
        fetch('/toggle', { method: 'POST' }).then(r => r.json()).then(d => {
            document.getElementById('status-label').textContent =
                d.mouse_control ? 'Bağlı — Aktif' : 'Bağlı — Fare DURDURULDU (Space)';
        });
    }
});

// ── Merkez ────────────────────────────────────────────────────────
function resetCenter() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'set_center' }));
    }
}

function onCenterInit(progress) {
    const pct = Math.round(progress * 100);
    document.getElementById('center-status').textContent = `Merkez ölçülüyor... ${pct}%`;
    document.getElementById('center-status').style.color = '#d29922';
}

function onCenterSet(cx, cy) {
    document.getElementById('center-status').textContent = `✓ Merkez: (${cx}, ${cy})`;
    document.getElementById('center-status').style.color = '#3fb950';
}

function onCenterReset() {
    document.getElementById('center-status').textContent = 'Merkez ölçülüyor... 0%';
    document.getElementById('center-status').style.color = '#d29922';
}

// ── Kalibrasyon ───────────────────────────────────────────────────
const CAL_POINTS = [
    [0.15, 0.15], [0.5, 0.15], [0.85, 0.15],
    [0.15, 0.5],  [0.5, 0.5],  [0.85, 0.5],
    [0.15, 0.85], [0.5, 0.85], [0.85, 0.85],
];

let calIndex    = 0;
let calProgress = 0;

const calOverlay = document.getElementById('cal-overlay');
const calCanvas  = document.getElementById('cal-canvas');
const calCtx     = calCanvas.getContext('2d');
const calInfo    = document.getElementById('cal-info');

function resizeCalCanvas() {
    calCanvas.width  = window.innerWidth;
    calCanvas.height = window.innerHeight;
}
window.addEventListener('resize', resizeCalCanvas);
resizeCalCanvas();

function drawCalPoint(px, py, progress) {
    calCtx.clearRect(0, 0, calCanvas.width, calCanvas.height);
    const x = px * calCanvas.width;
    const y = py * calCanvas.height;
    const R = 24;

    // Arka halka
    calCtx.beginPath();
    calCtx.arc(x, y, R, 0, Math.PI * 2);
    calCtx.strokeStyle = '#333';
    calCtx.lineWidth   = 4;
    calCtx.stroke();

    // İlerleme yayı
    calCtx.beginPath();
    calCtx.arc(x, y, R, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * progress);
    calCtx.strokeStyle = '#58a6ff';
    calCtx.lineWidth   = 4;
    calCtx.stroke();

    // Merkez nokta
    calCtx.beginPath();
    calCtx.arc(x, y, 6, 0, Math.PI * 2);
    calCtx.fillStyle = '#58a6ff';
    calCtx.fill();
}

function startCalibration() {
    calIndex    = 0;
    calProgress = 0;
    calOverlay.classList.add('active');
    ws.send(JSON.stringify({ type: 'cal_start' }));
    collectNextPoint();
}

function collectNextPoint() {
    if (calIndex >= CAL_POINTS.length) return;
    const [px, py] = CAL_POINTS[calIndex];
    calInfo.textContent = `Nokta ${calIndex + 1} / ${CAL_POINTS.length} — Bu noktaya bakın`;
    drawCalPoint(px, py, 0);

    // 1 saniye bekleme (göz stabilize olsun), sonra toplamaya başla
    setTimeout(() => {
        ws.send(JSON.stringify({ type: 'cal_collect', screen_x: px, screen_y: py }));
    }, 1000);
}

function onCalProgress(progress) {
    calProgress = progress;
    const [px, py] = CAL_POINTS[calIndex];
    drawCalPoint(px, py, progress);
}

function onCalPointDone() {
    calIndex++;
    if (calIndex >= CAL_POINTS.length) {
        calInfo.textContent = 'Hesaplanıyor...';
        ws.send(JSON.stringify({ type: 'cal_finish' }));
    } else {
        collectNextPoint();
    }
}

function onCalDone(success) {
    calOverlay.classList.remove('active');
    const statusEl = document.getElementById('cal-status');
    if (success) {
        statusEl.textContent = '✓ Kalibre edildi';
        statusEl.style.color = '#3fb950';
    } else {
        statusEl.textContent = '✗ Kalibrasyon başarısız, tekrar deneyin.';
        statusEl.style.color = '#f85149';
    }
}
