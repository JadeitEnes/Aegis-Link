import numpy as np
import cv2
from typing import Optional

class CalibrationMapper:
    def __init__(self):
        self._H: Optional[np.ndarray] = None
        self._raw: list = []
        self._screen: list = []

    def add_point(self, raw_x: float, raw_y: float, screen_x: float, screen_y: float) -> None:
        self._raw.append([raw_x, raw_y])
        self._screen.append([screen_x, screen_y])

    def compute(self) -> bool:
        if len(self._raw) < 4:
            return False
        src = np.array(self._raw,   dtype=np.float32)
        dst = np.array(self._screen, dtype=np.float32)
        H, _ = cv2.findHomography(src, dst, cv2.RANSAC)
        self._H = H
        return H is not None

    def transform(self, raw_x: float, raw_y: float) -> tuple[float, float]:
        if self._H is None:
            return raw_x, raw_y
        pt  = np.array([[[raw_x, raw_y]]], dtype=np.float32)
        out = cv2.perspectiveTransform(pt, self._H)
        x   = float(np.clip(out[0][0][0], 0.0, 1.0))
        y   = float(np.clip(out[0][0][1], 0.0, 1.0))
        return x, y

    def reset(self) -> None:
        self._H = None
        self._raw = []
        self._screen = []

    @property
    def is_calibrated(self) -> bool:
        return self._H is not None
