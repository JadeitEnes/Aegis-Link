import ctypes
import time
import signal
import sys
from multiprocessing.shared_memory import SharedMemory
from gaze_detector import GazeDetector

SHM_NAME = "cwe_eye_frame"

class _EyeTrackFrame(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("timestamps_ns",  ctypes.c_uint64),
        ("gaze_x",         ctypes.c_float),
        ("gaze_y",         ctypes.c_float),
        ("confidence",     ctypes.c_float),
        ("frame_id",       ctypes.c_uint32),
        ("writer_flag",    ctypes.c_uint8),
        ("left_eye_open",  ctypes.c_uint8),
        ("right_eye_open", ctypes.c_uint8),
        ("pad",            ctypes.c_uint8),
    ]

def main():
    running = True
    def stop(_s, _f): nonlocal running; running = False
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    print("=== CWE MediaPipe Publisher ===")
    camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    detector = GazeDetector()
    detector.open_camera(camera_index)
    print(f"Kamera {camera_index} açıldı.")

    shm = SharedMemory(name=SHM_NAME, create=True, size=ctypes.sizeof(_EyeTrackFrame))
    frame_ptr = _EyeTrackFrame.from_buffer(shm.buf)
    print(f"Shared memory hazır: {SHM_NAME}")

    frame_id = 0
    no_detect = 0

    while running:
        img = detector.read_frame()
        if img is None:
            time.sleep(0.01)
            continue

        result = detector.detect(img)

        frame_ptr.writer_flag = 1
        if result:
            frame_ptr.gaze_x        = result.gaze_x
            frame_ptr.gaze_y        = result.gaze_y
            frame_ptr.confidence    = result.confidence
            frame_ptr.left_eye_open  = 1 if result.left_eye_open  else 0
            frame_ptr.right_eye_open = 1 if result.right_eye_open else 0
            no_detect = 0
        else:
            frame_ptr.gaze_x        = 0.5
            frame_ptr.gaze_y        = 0.5
            frame_ptr.confidence    = 0.0
            frame_ptr.left_eye_open  = 0
            frame_ptr.right_eye_open = 0
            no_detect += 1

        frame_ptr.frame_id      = frame_id
        frame_ptr.timestamps_ns = time.monotonic_ns()
        frame_ptr.writer_flag   = 0
        frame_id += 1

        if frame_id % 60 == 0:
            if result:
                print(f"[Frame {frame_id}] gaze=({result.gaze_x:.3f}, {result.gaze_y:.3f}) "
                      f"L={'A' if result.left_eye_open else 'K'} R={'A' if result.right_eye_open else 'K'}")
            else:
                print(f"[Frame {frame_id}] tespit yok ({no_detect})")

    print("\nDurduruluyor...")
    detector.close()
    shm.close()
    shm.unlink()

if __name__ == "__main__":
    main()
