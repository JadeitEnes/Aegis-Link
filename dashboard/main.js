const canvas = document.getElementById('gaze-canvas');
const ctx = canvas.getContext('2d');

const TRAIL_LEN = 30;
const SMOOTH = 0.15;

let targetX = canvas.width / 2;
let targetY = canvas.height / 2;
let smoothX = targetX;
let smoothY = targetY;
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
        ctx.lineTo(trail[i].x, trail[i].y);
        ctx.stroke();
    }

    ctx.beginPath();
    ctx.arc(smoothX, smoothY, 18, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(88,166,255,0.15)';
    ctx.fill();
    ctx.strokeStyle = '#58a6ff';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(smoothX, smoothY, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#58a6ff';
    ctx.fill();

    requestAnimationFrame(drawFrame);
}

requestAnimationFrame(drawFrame);


const EVENT_LABELS = {
    LEFT_BLINK: ' Sol Göz',
    RIGHT_BLINK: ' Sağ Göz',
    BOTH_BLINK: ' Her İki Göz',
};

const ACTION_LABELS = {
    LEFT_BLINK: 'Scroll',
    RIGHT_BLINK: 'Tıklama',
    BOTH_BLINK: 'Çift Tıklama',
};

function setStatus(state) {
  const labels = {
    connected:    'Bağlı — Simülatör aktif',
    degraded:     'Bağlı — Publisher durdu',
    disconnected: 'Yeniden bağlanıyor...',
  };
  document.getElementById('status-dot').className   = state;
  document.getElementById('status-label').textContent = labels[state] || state;
}

function updateGazeUI(msg) {
    targetX = msg.gaze_x * canvas.width;
    targetY = msg.gaze_y * canvas.height;
    document.getElementById('stat-frame').textContent = msg.frame_id;
    document.getElementById('stat-conf').textContent  = (msg.confidence * 100).toFixed(0) + '%';
    document.getElementById('stat-lat').textContent   = msg.latency_us.toFixed(0) + 'µs';
    document.getElementById('stat-pos').textContent   = `${msg.gaze_x.toFixed(3)}, ${msg.gaze_y.toFixed(3)}`;
    
    updateEye('left', msg.left_eye_open === 1);
    updateEye ('right', msg.right_eye_open === 1);
    updateLatencyBar(msg.latency_us);
}

function updateEye(side, isOpen) {
    document.getElementById(`eye-${side}-icon`).textContent = isOpen ? '👁' : '-_-';
}

function updateLatencyBar(us) {
    const bar = document.getElementById('latency-bar');
    bar.style.width = Math.min(us / 10000 * 100, 100) + '%';
    bar.style.background = us < 3000 ? '#3fb950' : us < 7000 ? '#d29922' : '#f85149';
}

function addEvent(ev) {
    const log = document.getElementById('event-log');
    const item = document.createElement('div');
    item.className = `ev-item ${ev.event_type}`;
    item.innerHTML = `
    <div class="ev-type">
      ${EVENT_LABELS[ev.event_type] || ev.event_type}
      <span style="color:#8d96a0; font-weight:400; font-size:11px; margin-left:6px;">
        → ${ACTION_LABELS[ev.event_type] || ''}
      </span>
    </div>
    <div class="ev-meta">
      ${ev.duration_ms.toFixed(0)}ms &nbsp;|&nbsp;
      (${ev.gaze_x.toFixed(3)}, ${ev.gaze_y.toFixed(3)})
    </div>`;

    log.prepend(item);
    if (log.children.length > 30) log.removeChild(log.lastChild); 
}

function connect() {
    const ws = new WebSocket(`ws://${location.host}/ws`);

    ws.onopen = () => setStatus('connected');
    ws.onclose = () => { setStatus ('disconnected');
    setTimeout(connect, 2000);    
    };

    ws.onerror = () => ws.close();

    ws.onmessage = ({ data }) => {
        const msg = JSON.parse(data);
        if (msg.type === 'gaze') updateGazeUI(msg);
        if (msg.type === 'event') addEvent(msg);
    };
}

connect();

