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

from shm_reader import ShmReader, GazeSnapshot
from event_detector import EventDetector
from input_controller import InputController


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

reader = ShmReader()
event_detector = EventDetector()
input_ctrl = InputController()
_event_queue: deque[EventResponse] = deque(maxlen=50)
_ws_clients: Set[WebSocket] = set()
_mouse_control_enabled = True

# EMA smoothing state — titreşimi bastırır (0.0-1.0: düşük=yumuşak, yüksek=hassas)
_SMOOTH_ALPHA = 0.05
_smooth_x: float = 0.5
_smooth_y: float = 0.5
 

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

    last_frame_id = -1

    while True:
        await asyncio.sleep(0.001)

        if not reader.is_connected:
            # Publisher henüz başlamadıysa arka planda bağlanmayı dene
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

        # EMA smoothing — ham gaze titreşimini bastırır
        if snap.confidence > 0.0:
            _smooth_x = _SMOOTH_ALPHA * snap.gaze_x + (1 - _SMOOTH_ALPHA) * _smooth_x
            _smooth_y = _SMOOTH_ALPHA * snap.gaze_y + (1 - _SMOOTH_ALPHA) * _smooth_y
            if _mouse_control_enabled:
                input_ctrl.move(_smooth_x, _smooth_y)

        await _broadcast({
            "type": "gaze",
            "gaze_x": round(snap.gaze_x, 4),
            "gaze_y": round(snap.gaze_y, 4),
            "confidence": round(snap.confidence, 4),
            "frame_id": snap.frame_id,
            "left_eye_open": snap.left_eye_open,
            "right_eye_open": snap.right_eye_open,
            "latency_us": round(latency_us, 2),
        })

       
        event = event_detector.update(snap)
        if event is not None:
            ev = EventResponse(
                type = event.type.name,
                gaze_x = round(event.gaze_x, 4),
                gaze_y = round(event.gaze_y, 4),
                duration_ms = round(event.duration_ms, 1), 
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
    print ("[Bridge] Shared memory baglantisi kapatildi.")

app = FastAPI(
    title="CWE Bridge",
    description="C++ göz takip moturunu HTTP üzerinden açan köprü servisi",
    version="0.4.0",
    lifespan=lifespan,
)  
          
@app.get("/gaze", response_model=GazeResponse)
async def get_gaze():

    if not reader.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Shared memory bağlantisi yok. C++ publisher calisiyor mu?"
        )
    try:
        snap: GazeSnapshot = reader.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    latency_ns = snap.read_at_ns - snap.timestamps_ns
    latency_us = latency_ns / 1_000.0

    return GazeResponse( 
        gaze_x = round(snap.gaze_x, 4),
        gaze_y = round(snap.gaze_y, 4),
        confidence = round(snap.confidence, 4),
        frame_id =  snap.frame_id,
        left_eye_open = snap.left_eye_open,
        right_eye_open = snap.right_eye_open,
        latency_us = round(latency_us, 2),
    ) 

@app.get("/health", response_model=HealthResponse)
async def health():

    if not reader.is_connected:
        return HealthResponse(
            status="degraded",
            shm_connected=False,
            publisher_active=False,
            last_frame_id=-1,
        )
    
    snap_a = reader.read ()
    time.sleep(0.05)
    snap_b = reader.read()

    publisher_active = snap_b.frame_id != snap_a.frame_id

    return HealthResponse(
        status ="ok" if publisher_active else "degraded",
        shm_connected = True,
        publisher_active = publisher_active,
        last_frame_id = snap_b.frame_id,
    )

@app.get("/events", response_model=List[EventResponse])
async def get_events():

    events = list(_event_queue)
    _event_queue.clear()
    return events

@app.post("/toggle")
async def toggle_mouse():
    global _mouse_control_enabled
    _mouse_control_enabled = not _mouse_control_enabled
    state = "aktif" if _mouse_control_enabled else "devre disi"
    print (f"[CWE] Fare kontrolu: {state}")
    return {"mouse_control": _mouse_control_enabled}

@app.websocket ("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(ws)        

    
DASHBOARD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dashboard"
)

app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard")

@app.get("/", response_class=HTMLResponse)
async def root():
    """"http://localhost:8000 --> dashboard'a yönlendir """
    return HTMLResponse(content='<meta http-equiv="refresh" content="0; url=/dashboard">')
