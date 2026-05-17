import ctypes
import ctypes.wintypes
from dataclasses import dataclass

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

WHEEL_DELTA = 120

class _MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx" , ctypes.c_long),
        ("dy" , ctypes.c_long),
        ("mouseData" , ctypes.c_ulong),
        ("dwFlags" , ctypes.c_ulong),
        ("time" , ctypes.c_ulong),
        ("dwExtraInfo" ,ctypes.POINTER(ctypes.c_ulong)),
    ]

class _InputUnion(ctypes.Union):
    _fields_ = [("mi", _MouseInput)]

class _Input(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", _InputUnion),
    ]


@dataclass 

class _ScreenInfo:
    width: int
    height: int

    virtual_width: int
    virtual_height: int
    virtual_left: int
    virtual_top: int

def _get_screen_info() -> _ScreenInfo:
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()

    SM_CXSCREEN = 0
    SM_CYSCREEN = 1
    SM_XVIRTUALSCREEN = 76
    SM_YVIRTUALSCREEN = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79

    return _ScreenInfo(
        width          = user32.GetSystemMetrics(SM_CXSCREEN),
        height         = user32.GetSystemMetrics(SM_CYSCREEN),
        virtual_width  = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
        virtual_height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
        virtual_left   = user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
        virtual_top    = user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
    )


class InputController:

    def __init__(self):
        self._user32 = ctypes.windll.user32
        self._user32.SetProcessDPIAware()
        self._screen = _get_screen_info()

        print(f"[InputController] Ekran: {self._screen.width}x{self._screen.height} | "
            f"Sanal masaüstü: {self._screen.virtual_width}x{self._screen.virtual_height}")
    
    def _send_input(self, *inputs: _Input) -> None:
        n = len(inputs)
        arr = (_Input * n)(*inputs)
        sent = self._user32.SendInput(n, arr, ctypes.sizeof(_Input))
        if sent != n:
            raise RuntimeError(f"SendInput basarisiz: {sent}/{n} gonderildi.")

    def _make_mouse_input(self, dx: int, dy: int, data: int, flags: int) -> _Input:

        inp = _Input()
        inp.type = 0
        inp.ii.mi.dx = dx
        inp.ii.mi.dy = dy
        inp.ii.mi.mouseData = data
        inp.ii.mi.dwFlags = flags
        inp.ii.mi.time = 0
        inp.ii.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
        return inp
    
    def _normalize_to_absolute(self, gaze_x: float, gaze_y: float) -> tuple[int, int]:

        abs_x = int(gaze_x * 65535)
        abs_y = int(gaze_y * 65535)
        return abs_x, abs_y
    
    def move(self, gaze_x: float, gaze_y: float) -> None:

        abs_x, abs_y = self._normalize_to_absolute(
            max(0.0, min(1.0, gaze_x)),
            max(0.0, min(1.0, gaze_y)),
        )

        flags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK
        self._send_input(self._make_mouse_input(abs_x, abs_y, 0, flags))

    def left_click(self) -> None:
        down = self._make_mouse_input(0, 0, 0, MOUSEEVENTF_LEFTDOWN)
        up   = self._make_mouse_input(0, 0, 0, MOUSEEVENTF_LEFTUP)
        self._send_input(down, up)

    def right_click(self) -> None: 
        down = self._make_mouse_input(0, 0, 0, MOUSEEVENTF_RIGHTDOWN)
        up   = self._make_mouse_input(0, 0, 0, MOUSEEVENTF_RIGHTUP)
        self._send_input(down, up) 

    def double_click(self) -> None:
        self.left_click()
        self.left_click()

    def scroll(self, direction: int = 1, amount: int =3) -> None:
        delta= -direction * WHEEL_DELTA * amount
        inp = self._make_mouse_input(0, 0, ctypes.c_ulong(delta).value, MOUSEEVENTF_WHEEL)
        self._send_input(inp)  

    def refresh_screen_info(self) -> None:
        self._screen = _get_screen_info()

