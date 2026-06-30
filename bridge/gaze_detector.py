import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class GazeResult:
    gaze_x: float
    gaze_y: float
    confidence: float
    left_eye_open: bool
    right_eye_open: bool

# Göz kapanma tespiti
LEFT_EYE_TOP     = 159
LEFT_EYE_BOTTOM  = 145
LEFT_EYE_LEFT    = 33
LEFT_EYE_RIGHT   = 133
RIGHT_EYE_TOP    = 386
RIGHT_EYE_BOTTOM = 374
RIGHT_EYE_LEFT   = 263
RIGHT_EYE_RIGHT  = 362

EAR_THRESHOLD = 0.15

# Kafa yönü için burun ve yüz kenar noktaları
NOSE_TIP      = 1
NOSE_BASE     = 168
CHIN          = 152
FOREHEAD      = 10
LEFT_TEMPLE   = 234
RIGHT_TEMPLE  = 454

MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_landmarker.task")


class GazeDetector:
    def __init__(self):
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.4,
            min_face_presence_confidence=0.4,
            min_tracking_confidence=0.4,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False,
        )
        self._detector = FaceLandmarker.create_from_options(options)
        self._cap: Optional[cv2.VideoCapture] = None

    def open_camera(self, index: int = 0) -> None:
        self._cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._cap.set(cv2.CAP_PROP_FPS, 30)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self._cap.isOpened():
            raise RuntimeError(f"Kamera {index} açılamadı.")

    def read_frame(self) -> Optional[np.ndarray]:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        return frame if ok else None

    def detect(self, frame: np.ndarray) -> Optional[GazeResult]:
        rgb      = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result   = self._detector.detect(mp_image)

        if not result.face_landmarks:
            return None

        lm   = result.face_landmarks[0]
        h, w = frame.shape[:2]

        def pt(idx):
            p = lm[idx]
            return np.array([p.x, p.y])  # normalize 0-1

        # Kafa yönü
        nose     = pt(NOSE_TIP)
        l_temple = pt(LEFT_TEMPLE)
        r_temple = pt(RIGHT_TEMPLE)
        forehead = pt(FOREHEAD)
        chin     = pt(CHIN)

        face_w = r_temple[0] - l_temple[0]
        if face_w < 1e-4:
            return None

        # X: burunun yüz içindeki yatay konumu (aynalı düzeltme)
        gaze_x = 1.0 - (nose[0] - l_temple[0]) / face_w

        # Y: başın eğim açısı — burnun yüz içindeki dikey konumu
        # Çene yukarı (yukarı bak) → burun yüzde yukarı % artar → gaze_y azalır → imleç yukarı
        face_h = max(chin[1] - forehead[1], 1e-4)
        nose_in_face_y = (nose[1] - forehead[1]) / face_h  # ~0.3-0.7
        gaze_y = 1.0 - nose_in_face_y  # ters: yukarı bak → gaze_y küçük

        # Göz kapanma — MediaPipe blend shapes kullan (kafa açısını kompanse eder)
        BLINK_THRESHOLD = 0.45
        blink_l = 0.0
        blink_r = 0.0
        if result.face_blendshapes:
            for bs in result.face_blendshapes[0]:
                if bs.category_name == 'eyeBlinkLeft':
                    blink_l = bs.score
                elif bs.category_name == 'eyeBlinkRight':
                    blink_r = bs.score

        if not hasattr(self, '_blink_log_counter'):
            self._blink_log_counter = 0
        self._blink_log_counter += 1
        if self._blink_log_counter % 30 == 0:
            print(f"[BLINK] L={blink_l:.3f} R={blink_r:.3f} threshold={BLINK_THRESHOLD}")

        # Blend shape anatomik gözü gösteriyor, aynalı swap gereksiz
        left_open  = blink_l < BLINK_THRESHOLD   # eyeBlinkLeft = kullanıcının sol gözü
        right_open = blink_r < BLINK_THRESHOLD   # eyeBlinkRight = kullanıcının sağ gözü

        gaze_x = float(np.clip(gaze_x, 0.0, 1.0))
        gaze_y = float(np.clip(gaze_y, 0.0, 1.0))

        # Ani sıçramaları at — bir frame'de 0.3'ten fazla değişim outlier'dır
        if hasattr(self, '_prev_gaze_x'):
            if abs(gaze_x - self._prev_gaze_x) > 0.3 or abs(gaze_y - self._prev_gaze_y) > 0.3:
                return None
        self._prev_gaze_x = gaze_x
        self._prev_gaze_y = gaze_y

        return GazeResult(
            gaze_x=gaze_x,
            gaze_y=gaze_y,
            confidence=1.0,
            left_eye_open=left_open,
            right_eye_open=right_open,
        )

    def close(self) -> None:
        if self._cap:
            self._cap.release()
        self._detector.close()
