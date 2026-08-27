#!/usr/bin/env python3
"""Updater helper for Jarvis CLI.

Waits for the parent process to exit, then restarts the application.
This script is launched by jarvis_web_desktop.py after pulling updates
from GitHub so that the old process can terminate cleanly before the
new version starts.
"""
import os
import subprocess
import sys
import time


def wait_for_process(pid: int, poll_interval: float = 0.5) -> None:
    """Wait until the process with the given PID no longer exists."""
    while True:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, OSError):
            break
        time.sleep(poll_interval)


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: updater.py <parent_pid> <project_dir>", file=sys.stderr)
        sys.exit(1)

    parent_pid = int(sys.argv[1])
    project_dir = os.path.abspath(sys.argv[2])

    # Give the parent process a moment to release the webview and sockets.
    wait_for_process(parent_pid)
    time.sleep(1)

    script_path = os.path.join(project_dir, "jarvis_web_desktop.py")
    if not os.path.exists(script_path):
        print(f"Application entry point not found: {script_path}", file=sys.stderr)
        sys.exit(1)

    # Detach from the terminal/session so the new app outlives this helper.
    subprocess.Popen(
        [sys.executable, script_path],
        cwd=project_dir,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


if __name__ == "__main__":
    main()
