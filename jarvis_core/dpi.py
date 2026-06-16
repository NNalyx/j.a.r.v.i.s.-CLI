"""Windows DPI awareness helper."""
import os


def ensure_windows_dpi_awareness():
    if os.name != "nt":
        return

    try:
        ctypes = __import__("ctypes")

        # Per-monitor v2 awareness gives consistent physical-pixel coordinates
        # for both screen capture and mouse automation on modern Windows.
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            return
        except Exception:
            pass

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except Exception:
            pass

        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    except Exception:
        pass


ensure_windows_dpi_awareness()
