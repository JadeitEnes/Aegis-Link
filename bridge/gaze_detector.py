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

LEFT_IRIS   = [474, 475, 476, 477]
RIGHT_IRIS  = [469, 470, 471, 472]

LEFT_EYE_TOP     = 159
LEFT_EYE_BOTTOM  = 145
LEFT_EYE_LEFT    = 33
LEFT_EYE_RIGHT   = 133

RIGHT_EYE_TOP    = 386
RIGHT_EYE_BOTTOM = 374
RIGHT_EYE_LEFT   = 263
RIGHT_EYE_RIGHT  = 362

EAR_CLOSE_THRESHOLD = 0.015

MODEL_PATH = os.path.join(os.path.dirname(__file__), "face_landmarker.task")


class GazeDetector:
    def __init__(self):
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
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
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._detector.detect(mp_image)

        if not result.face_landmarks:
            return None

        lm = result.face_landmarks[0]
        h, w = frame.shape[:2]

        def pt(idx):
            p = lm[idx]
            return np.array([p.x * w, p.y * h])

        # Iris merkezi
        left_iris  = np.mean([pt(i) for i in LEFT_IRIS],  axis=0)
        right_iris = np.mean([pt(i) for i in RIGHT_IRIS], axis=0)

        # Iris'in göz içindeki göreceli konumu — min/max ile köşe sırası önemli değil
        def relative_iris(iris, corner1_idx, corner2_idx, top_idx, bottom_idx):
            c1  = pt(corner1_idx)
            c2  = pt(corner2_idx)
            top = pt(top_idx)
            bot = pt(bottom_idx)
            min_x = min(c1[0], c2[0])
            max_x = max(c1[0], c2[0])
            min_y = min(top[1], bot[1])
            max_y = max(top[1], bot[1])
            rx = (iris[0] - min_x) / (max_x - min_x + 1e-6)
            ry = (iris[1] - min_y) / (max_y - min_y + 1e-6)
            return rx, ry

        lx, ly = relative_iris(left_iris,  LEFT_EYE_LEFT,  LEFT_EYE_RIGHT,  LEFT_EYE_TOP,  LEFT_EYE_BOTTOM)
        rx, ry = relative_iris(right_iris, RIGHT_EYE_LEFT, RIGHT_EYE_RIGHT, RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM)

        gaze_x = float(np.clip((lx + rx) / 2, 0.0, 1.0))
        gaze_y = float(np.clip((ly + ry) / 2, 0.0, 1.0))

        def ear(top, bottom, left, right):
            vert  = np.linalg.norm(pt(top) - pt(bottom))
            horiz = np.linalg.norm(pt(left) - pt(right))
            return vert / (horiz + 1e-6)

        left_open  = ear(LEFT_EYE_TOP,  LEFT_EYE_BOTTOM,  LEFT_EYE_LEFT,  LEFT_EYE_RIGHT)  > EAR_CLOSE_THRESHOLD
        right_open = ear(RIGHT_EYE_TOP, RIGHT_EYE_BOTTOM, RIGHT_EYE_LEFT, RIGHT_EYE_RIGHT) > EAR_CLOSE_THRESHOLD

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
