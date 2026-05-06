import time 
import sys
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shm_reader import ShmReader, GazeSnapshot

class GazeResponse(BaseModel):
    gaze_x: float
    gaze_y: float
    confidence: float
    frame_id: int
    latency_us: float

class HealthResponse(BaseModel):   
    status: str
    shm_connected: bool
    publisher_active: bool
    last_frame_id: int


reader = ShmReader()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[Bridge] Shared memory'ye bağlanılıyor...")
    try:
        reader.connect(timeout=15.0)
        print("[Bridge] Bağlantı kuruldu. Servis hazır.")
    except RuntimeError as e:
        print(f"[Bridge] Uyarı: {e}")  
    
    yield

    reader.close()
    print ("[Bridge] Shared memory bağlantısı kapatıldı.")

app = FastAPI(
    title="Aegis-Link Bridge",
    description="C++ göz takip moturunu HTTP üzerinden açan köprü servisi",
    version="0.1.0",
    lifespan=lifespan,
)  
          
@app.get("/gaze", response_model=GazeResponse)
async def get_gaze():

    if not reader.is_connected:
        raise HTTPException(
            status_code=503,
            detail="Shared memory bağlantısı yok. C++ publisher çalışıyor mu?"
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


    

    