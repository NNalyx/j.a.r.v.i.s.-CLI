"""Managed background processes for agent-launched development servers."""

from __future__ import annotations

import datetime as _dt
import os
import signal
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from jarvis_core.types import ToolResult


_LOCK = threading.RLock()
_TASKS: Dict[str, Dict[str, Any]] = {}
_LOG_DIR = Path(os.getenv("JARVIS_BACKGROUND_LOG_DIR", Path(tempfile.gettempdir()) / "jarvis_background_logs"))


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _refresh(task: Dict[str, Any]) -> Dict[str, Any]:
    process = task.get("process")
    if process is not None:
        returncode = process.poll()
        if returncode is not None:
            task["status"] = "stopped" if task.get("stop_requested") else ("failed" if returncode else "completed")
            task["returncode"] = returncode
            task["finished_at"] = task.get("finished_at") or _now()
    return {key: value for key, value in task.items() if key != "process"}


def list_background_tasks() -> ToolResult:
    """Return all managed background tasks and refresh their process states."""
    with _LOCK:
        tasks = [_refresh(task) for task in _TASKS.values()]
    tasks.sort(key=lambda item: item.get("started_at", ""), reverse=True)
    return ToolResult(True, {"tasks": tasks, "active_count": sum(t.get("status") == "running" for t in tasks)})


def background_tasks_context() -> str:
    """Compact state injected into every new agent request."""
    result = list_background_tasks()
    tasks = (result.data or {}).get("tasks", []) if result.success else []
    if not tasks:
        return "Active background tasks: none."
    lines = ["Active background tasks (use task_id or pid to manage them):"]
    for task in tasks:
        lines.append(
            f"- task_id={task.get('task_id')} pid={task.get('pid')} "
            f"status={task.get('status')} command={task.get('command')}"
        )
    return "\n".join(lines)


def run_background_task(command: str, cwd: str = "", label: str = "") -> ToolResult:
    """Start a long-running shell command without waiting for completion."""
    raw_command = str(command or "").strip()
    if not raw_command:
        return ToolResult(False, None, "Empty command")

    workdir = Path(cwd).expanduser() if str(cwd or "").strip() else Path.cwd()
    if not workdir.is_dir():
        return ToolResult(False, None, f"Working directory does not exist: {workdir}")

    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        task_id = f"bg-{uuid.uuid4().hex[:8]}"
        log_path = _LOG_DIR / f"{task_id}.log"
        log_file = log_path.open("ab")
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            process = subprocess.Popen(
                ["cmd.exe", "/d", "/s", "/c", raw_command], cwd=str(workdir), stdin=subprocess.DEVNULL,
                stdout=log_file, stderr=subprocess.STDOUT, creationflags=creationflags,
            )
        else:
            shell = "/bin/bash" if Path("/bin/bash").exists() else "/bin/sh"
            process = subprocess.Popen(
                [shell, "-lc", "exec " + raw_command], cwd=str(workdir), stdin=subprocess.DEVNULL,
                stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True,
            )
        log_file.close()
    except Exception as error:
        try:
            log_file.close()  # type: ignore[possibly-undefined]
        except Exception:
            pass
        return ToolResult(False, None, f"Could not start background task: {error}")

    # Verify the process actually started instead of dying immediately
    import time as _time
    _time.sleep(0.3)
    early_returncode = process.poll()
    early_log = ""
    try:
        if log_path.exists():
            early_log = log_path.read_text(encoding="utf-8", errors="replace")[:2000]
    except Exception:
        pass

    if early_returncode is not None:
        return ToolResult(
            False,
            {
                "task_id": task_id,
                "pid": process.pid,
                "command": raw_command,
                "cwd": str(workdir),
                "label": str(label or raw_command[:80]),
                "status": "failed",
                "returncode": early_returncode,
                "log_path": str(log_path),
                "log_preview": early_log,
            },
            f"Background task exited immediately with code {early_returncode}. Check log: {log_path}"
        )

    task = {
        "task_id": task_id, "pid": process.pid, "command": raw_command,
        "cwd": str(workdir), "label": str(label or raw_command[:80]),
        "status": "running", "started_at": _now(), "log_path": str(log_path),
        "process": process,
    }
    with _LOCK:
        _TASKS[task_id] = task
        data = _refresh(task)
    data["log_preview"] = early_log
    return ToolResult(True, data)


def stop_background_task(task_id: str = "", pid: Optional[int] = None) -> ToolResult:
    """Stop one managed task by task_id or PID, including its process group."""
    lookup_id = str(task_id or "").strip()
    with _LOCK:
        task = _TASKS.get(lookup_id) if lookup_id else None
        if task is None and pid is not None:
            task = next((item for item in _TASKS.values() if item.get("pid") == int(pid)), None)
        if task is None:
            return ToolResult(False, None, f"Background task not found: {lookup_id or pid}")
        _refresh(task)
        if task.get("status") != "running":
            return ToolResult(True, _refresh(task))
        process = task.get("process")
        task["stop_requested"] = True
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    process.kill()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait(timeout=3)
        except ProcessLookupError:
            pass
        except Exception as error:
            return ToolResult(False, _refresh(task), f"Could not stop background task: {error}")
        return ToolResult(True, _refresh(task))
