import time
import sys
import os
import asyncio
import json
from collections import deque
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from typing import List, Set
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shm_reader import ShmReader
from event_detector import EventDetector
from input_controller import InputController
from calibration import CalibrationMapper


class GazeResponse(BaseModel):
    gaze_x: float
    gaze_y: float
    confidence: float
    frame_id: int
    left_eye_open: int
    right_eye_open: int
    latency_us: float

class HealthResponse(BaseModel):
    status: str
    shm_connected: bool
    publisher_active: bool
    last_frame_id: int

class EventResponse(BaseModel):
    type: str
    gaze_x: float
    gaze_y: float
    duration_ms: float


reader         = ShmReader()
event_detector = EventDetector()
input_ctrl     = InputController()
cal_mapper     = CalibrationMapper()

_event_queue: deque[EventResponse] = deque(maxlen=50)
_ws_clients: Set[WebSocket] = set()
_mouse_control_enabled = True

_SMOOTH_ALPHA = 0.08
_smooth_x: float = 0.5
_smooth_y: float = 0.5

# Kalibrasyon toplama durumu
_cal_collecting  = False
_cal_samples: list = []
_cal_screen_pt: tuple = (0.5, 0.5)
_CAL_SAMPLES_NEEDED = 45  # ~1.5 saniye @ 30fps


async def _broadcast(message: dict) -> None:
    if not _ws_clients:
        return
    data = json.dumps(message)
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


def _handle_event(event_type: str) -> None:
    if not _mouse_control_enabled:
        return
    if event_type == "LEFT_BLINK":
        input_ctrl.scroll(direction=1)
    elif event_type == "RIGHT_BLINK":
        input_ctrl.move(_smooth_x, _smooth_y)
        input_ctrl.left_click()
    elif event_type == "BOTH_BLINK":
        input_ctrl.move(_smooth_x, _smooth_y)
        input_ctrl.double_click()


async def _poll_loop():
    global _smooth_x, _smooth_y
    global _cal_collecting, _cal_samples

    last_frame_id = -1

    while True:
        await asyncio.sleep(0.001)

        if not reader.is_connected:
            try:
                reader.connect(timeout=0.5)
                print("[Bridge] Publisher bulundu, bağlantı kuruldu.")
            except RuntimeError:
                pass
            continue

        try:
            snap = reader.read()
        except Exception:
            continue

        if snap.frame_id == last_frame_id:
            continue
        last_frame_id = snap.frame_id

        latency_us = (snap.read_at_ns - snap.timestamps_ns) / 1_000.0

        # Kalibrasyon örneği toplama
        if _cal_collecting and snap.confidence > 0.0:
            _cal_samples.append((snap.gaze_x, snap.gaze_y))
            await _broadcast({
                "type": "cal_progress",
                "progress": len(_cal_samples) / _CAL_SAMPLES_NEEDED,
            })
            if len(_cal_samples) >= _CAL_SAMPLES_NEEDED:
                avg_x = sum(s[0] for s in _cal_samples) / len(_cal_samples)
                avg_y = sum(s[1] for s in _cal_samples) / len(_cal_samples)
                cal_mapper.add_point(avg_x, avg_y, _cal_screen_pt[0], _cal_screen_pt[1])
                _cal_collecting = False
                _cal_samples = []
                print(f"[Cal] Nokta kaydedildi: raw=({avg_x:.3f},{avg_y:.3f}) → screen={_cal_screen_pt}")
                await _broadcast({"type": "cal_point_done"})
            continue  # kalibrasyon sırasında fare hareket etmesin

        # EMA smoothing + kalibrasyon uygula
        if snap.confidence > 0.0:
            _smooth_x = _SMOOTH_ALPHA * snap.gaze_x + (1 - _SMOOTH_ALPHA) * _smooth_x
            _smooth_y = _SMOOTH_ALPHA * snap.gaze_y + (1 - _SMOOTH_ALPHA) * _smooth_y

            cx, cy = cal_mapper.transform(_smooth_x, _smooth_y)

            if _mouse_control_enabled:
                input_ctrl.move(cx, cy)

            await _broadcast({
                "type": "gaze",
                "gaze_x": round(cx, 4),
                "gaze_y": round(cy, 4),
                "confidence": round(snap.confidence, 4),
                "frame_id": snap.frame_id,
                "left_eye_open": snap.left_eye_open,
                "right_eye_open": snap.right_eye_open,
                "latency_us": round(latency_us, 2),
            })

        event = event_detector.update(snap)
        if event is not None:
            ev = EventResponse(
                type=event.type.name,
                gaze_x=round(event.gaze_x, 4),
                gaze_y=round(event.gaze_y, 4),
                duration_ms=round(event.duration_ms, 1),
            )
            _event_queue.append(ev)
            _handle_event(ev.type)
            await _broadcast({
                "type": "event",
                "event_type": ev.type,
                "gaze_x": ev.gaze_x,
                "gaze_y": ev.gaze_y,
                "duration_ms": ev.duration_ms,
            })


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Bridge] Servis başlatılıyor. Publisher bekleniyor...")
    task = asyncio.create_task(_poll_loop())
    yield
    task.cancel()
    reader.close()
    print("[Bridge] Shared memory bağlantısı kapatıldı.")


app = FastAPI(
    title="CWE Bridge",
    description="Göz takip motorunu HTTP üzerinden açan köprü servisi",
    version="0.5.0",
    lifespan=lifespan,
)


@app.get("/gaze", response_model=GazeResponse)
async def get_gaze():
    if not reader.is_connected:
        raise HTTPException(status_code=503, detail="Publisher çalışmıyor.")
    try:
        snap = reader.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    latency_us = (snap.read_at_ns - snap.timestamps_ns) / 1_000.0
    cx, cy = cal_mapper.transform(snap.gaze_x, snap.gaze_y)
    return GazeResponse(
        gaze_x=round(cx, 4),
        gaze_y=round(cy, 4),
        confidence=round(snap.confidence, 4),
        frame_id=snap.frame_id,
        left_eye_open=snap.left_eye_open,
        right_eye_open=snap.right_eye_open,
        latency_us=round(latency_us, 2),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    if not reader.is_connected:
        return HealthResponse(status="degraded", shm_connected=False,
                              publisher_active=False, last_frame_id=-1)
    snap_a = reader.read()
    time.sleep(0.05)
    snap_b = reader.read()
    active = snap_b.frame_id != snap_a.frame_id
    return HealthResponse(status="ok" if active else "degraded",
                          shm_connected=True, publisher_active=active,
                          last_frame_id=snap_b.frame_id)


@app.get("/events", response_model=List[EventResponse])
async def get_events():
    events = list(_event_queue)
    _event_queue.clear()
    return events


@app.post("/toggle")
async def toggle_mouse():
    global _mouse_control_enabled
    _mouse_control_enabled = not _mouse_control_enabled
    return {"mouse_control": _mouse_control_enabled}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global _cal_collecting, _cal_samples, _cal_screen_pt
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            if msg["type"] == "cal_start":
                cal_mapper.reset()
                _cal_collecting = False
                _cal_samples = []
                print("[Cal] Kalibrasyon başladı.")

            elif msg["type"] == "cal_collect":
                _cal_screen_pt = (msg["screen_x"], msg["screen_y"])
                _cal_samples   = []
                _cal_collecting = True
                print(f"[Cal] Toplama başladı → screen={_cal_screen_pt}")

            elif msg["type"] == "cal_finish":
                ok = cal_mapper.compute()
                print(f"[Cal] Homografi hesaplandı: {'OK' if ok else 'HATA'}")
                await ws.send_text(json.dumps({
                    "type": "cal_done",
                    "success": ok,
                }))

    except WebSocketDisconnect:
        _ws_clients.discard(ws)


DASHBOARD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dashboard"
)

app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")


@app.get("/", response_class=HTMLResponse)
async def root():
    return HTMLResponse(content='<meta http-equiv="refresh" content="0; url=/dashboard">')
