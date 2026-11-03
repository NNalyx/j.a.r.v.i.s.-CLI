"""Console-free Windows entry point used by the Jarvis installer."""
from __future__ import annotations

import os
import runpy
import sys
import traceback
from pathlib import Path


def main() -> None:
    app_dir = Path(__file__).resolve().parent
    log_dir = app_dir / "jarvis_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = (log_dir / "desktop.log").open("a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = log_file
    sys.stderr = log_file
    # Keep the GUI process windowless while child Python tools can still use
    # python.exe and its real stdout/stderr pipes.
    python_console = Path(sys.executable).with_name("python.exe")
    if python_console.is_file():
        sys.executable = str(python_console)
    os.chdir(app_dir)
    sys.path.insert(0, str(app_dir))
    try:
        runpy.run_path(str(app_dir / "jarvis_web_desktop.py"), run_name="__main__")
    except BaseException:
        traceback.print_exc()
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None,
                f"Jarvis could not start. See the log file:\n{log_dir / 'desktop.log'}",
                "Jarvis Desktop",
                0x10,
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
