import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from shm_reader import GazeSnapshot

class EventType(Enum):
    LEFT_BLINK = auto()
    RIGHT_BLINK = auto()
    BOTH_BLINK = auto()

@dataclass 
class GazeEvent:
    type: EventType
    gaze_x: float
    gaze_y: float
    duration_ms: float

class _EyeTracker:
    def __init__(self, threshold_ms: float, cooldown_ms: float):
        self._threshold_ms = threshold_ms
        self._cooldown_ms = cooldown_ms
        self._closed_since: Optional[float] = None
        self._last_event_at: float = 0.0
        self._fired: bool = False

    def update(self, is_active: bool, now: float) -> Optional[float]:

        if not is_active:
            self._closed_since = None
            self._fired = False 
            return None

        if self._closed_since is None:
            self._closed_since = now

        closed_ms = (now - self._closed_since) * 1000.0
        cooldown_passed = (now - self._last_event_at) * 1000.0 > self._cooldown_ms

        if closed_ms >= self._threshold_ms and not self._fired and cooldown_passed:
            self._fired = True
            self._last_event_at = now
            return closed_ms

        return None       
        
class EventDetector:

    def __init__(
            self,
            left_threshold_ms: float = 800.0,
            right_threshold_ms: float = 800.0,
            both_threshold_ms: float = 600.0,
            cooldown_ms: float = 1500.0,
    ):
        self._left = _EyeTracker(threshold_ms=left_threshold_ms, cooldown_ms=cooldown_ms)
        self._right = _EyeTracker(threshold_ms=right_threshold_ms, cooldown_ms=cooldown_ms)
        self._both = _EyeTracker(threshold_ms=both_threshold_ms, cooldown_ms=cooldown_ms)

    def update(self, snap: GazeSnapshot) -> Optional[GazeEvent]:

        now = time.monotonic()

        left_open = bool(snap.left_eye_open)
        right_open = bool(snap.right_eye_open)

        both_closed = not left_open and not right_open
        left_solo = not left_open and right_open
        right_solo = left_open and not right_open

        both_dur = self._both.update(both_closed, now)
        if both_dur is not None:
            return GazeEvent(
                type = EventType.BOTH_BLINK,
                gaze_x = snap.gaze_x,
                gaze_y = snap.gaze_y,
                duration_ms = both_dur,
            )
        
        left_dur = self._left.update(left_solo, now)
        if left_dur is not None:
            return GazeEvent(
                type = EventType.LEFT_BLINK,
                gaze_x = snap.gaze_x,
                gaze_y = snap.gaze_y,
                duration_ms = left_dur,
            )
        
        right_dur = self._right.update(right_solo, now)
        if right_dur is not None:
            return GazeEvent(
                type        = EventType.RIGHT_BLINK,
                gaze_x      = snap.gaze_x,
                gaze_y      = snap.gaze_y,
                duration_ms = right_dur,
            )
 
        return None
     