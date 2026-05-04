from multiprocessing.shared_memory import SharedMemory
import ctypes
import time

class EyeTrackFrame(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("timestamp_ns", ctypes.c_uint64),
        ("gaze_x", ctypes.c_float),
        ("gaze_y", ctypes.c_float),
        ("confidence", ctypes.c_float),
        ("frame_id", ctypes.c_uint32),
        ("writer_flag", ctypes.c_uint8),
        ("pad", ctypes.c_uint8 * 3),
        
    ]

def main():
    print("=== Aegis-Link Python Consumer Baslatildi ===")
    print("C++ publisher bekleniyor...")

    shm = None
    while shm is None:
        try:
            shm = SharedMemory(name="aegis_eye_frame", create=False)
        except FileNotFoundError:
            time.sleep(0.1)

    print(f"Baglandi! Blok boyutu: {shm.size} byte\n")

    frame = EyeTrackFrame.from_buffer(shm.buf)
    last_frame_id = -1

    try: 
        while True:
            if frame.writer_flag == 0:
                snap = EyeTrackFrame()
                ctypes.memmove(
                    ctypes.addressof(snap),
                    ctypes.addressof(frame),
                    ctypes.sizeof(EyeTrackFrame)
                )                

                if snap.frame_id != last_frame_id:
                    last_frame_id = snap.frame_id
                    print(
                        f"[Frame {snap.frame_id:5d}] "
                        f"gaze=({snap.gaze_x:.3f}, {snap.gaze_y:.3f}) "
                        f"conf={snap.confidence:.2f}"
                    )
        time.sleep(0.001)
    except KeyboardInterrupt:
        print("\nDurduruluyor...")
    finally:
        shm.close()
        print("Baglanti kapatildi.")
if __name__ == "__main__":
    main()        
