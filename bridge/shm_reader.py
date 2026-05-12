import ctypes 
import time
from multiprocessing.shared_memory import SharedMemory
from dataclasses import dataclass

class _EyeTrackFrame(ctypes.Structure):

    _pack_ = 1
    _fields_ = [
        ("timestamps_ns", ctypes.c_uint64),
        ("gaze_x", ctypes.c_float),
        ("gaze_y", ctypes.c_float),
        ("confidence", ctypes.c_float),
        ("frame_id", ctypes.c_uint32),
        ("writer_flag", ctypes.c_uint8),
        ("left_eye_open", ctypes.c_uint8),
        ("right_eye_open", ctypes.c_uint8),
        ("pad", ctypes.c_uint8),
    ]
EXPECTED_SIZE = 28

if ctypes.sizeof(_EyeTrackFrame) != EXPECTED_SIZE:
    raise RuntimeError(
        f"Struct boyutu uyuşmazlığı:"
        f"beklenen={EXPECTED_SIZE}, gerçek={ctypes.sizeof(_EyeTrackFrame)}."
        f"shared_structs.h ile senkronize edin."
    )


@dataclass 

class GazeSnapshot:
    gaze_x: float
    gaze_y: float
    confidence: float
    frame_id: int
    timestamps_ns: int
    read_at_ns: int
    left_eye_open: int
    right_eye_open: int

class ShmReader:

    SHM_NAME = "aegis_eye_frame"
    MAX_SPIN = 100 

    def __init__(self):
        self._shm: SharedMemory | None = None
        self._frame: _EyeTrackFrame | None = None

    def connect(self, timeout: float = 10.0) -> None:

        deadline = time.monotonic() + timeout
        while True:
            try:
                self._shm = SharedMemory(name=self.SHM_NAME, create=False)
                break
            except FileNotFoundError:
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        f"'{self.SHM_NAME}' shared memory'si {timeout}s içinde "
                        f"bulunamadı. C++ publisher çalışıyor mu?" 
                    )  
                time.sleep(0.05)
        self._frame = _EyeTrackFrame.from_buffer(self._shm.buf)
    def close(self) -> None:
        if self._shm:
            self._shm.close()
            self._shm = None
            self._frame = None 

    def read(self) -> GazeSnapshot:

        if self._frame is None:
            raise RuntimeError("connect() çağırılmadan read() kullanılamaz.")
        

        for _ in range(self.MAX_SPIN):
            if self._frame.writer_flag == 0:
                break
            time.sleep(0.000_01)
        
        snap_raw = _EyeTrackFrame()
        ctypes.memmove(
            ctypes.addressof(snap_raw),
            ctypes.addressof(self._frame),
            ctypes.sizeof(_EyeTrackFrame)
        )

        read_at_ns = time.monotonic_ns()

        return GazeSnapshot(
            gaze_x = snap_raw.gaze_x,
            gaze_y = snap_raw.gaze_y,
            confidence = snap_raw.confidence,
            frame_id = snap_raw.frame_id,
            timestamps_ns = snap_raw.timestamps_ns,
            read_at_ns = read_at_ns,
            left_eye_open = snap_raw.left_eye_open,
            right_eye_open =  snap_raw.right_eye_open,

        )
    
    @property

    def is_connected(self) -> bool:
        return self._shm is not None
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, *_):
        self.close()

                        
