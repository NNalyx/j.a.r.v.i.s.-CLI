"""Per-agent-turn file snapshots used by the change review panel."""
import difflib
import os
import threading
import uuid

_local = threading.local()
_lock = threading.RLock()
_sessions = {}
_MAX_SESSIONS = 80


def begin_change_session():
    session_id = uuid.uuid4().hex
    session = {"id": session_id, "files": {}}
    _local.session = session
    return session


def capture_before_write(path):
    session = getattr(_local, "session", None)
    if not session:
        return
    try:
        path = os.path.abspath(path)
        if path not in session["files"]:
            existed = os.path.isfile(path)
            if existed:
                with open(path, "rb") as source:
                    original = source.read()
            else:
                original = b""
            session["files"][path] = {"before": original, "existed": existed}
    except (OSError, ValueError):
        pass


def finish_change_session(session):
    if getattr(_local, "session", None) is session:
        _local.session = None
    files = []
    for path, entry in session["files"].items():
        try:
            after = open(path, "rb").read() if os.path.isfile(path) else b""
        except OSError:
            continue
        before = entry["before"]
        if before == after and entry["existed"]:
            continue
        old_text = before.decode("utf-8", errors="replace").splitlines(keepends=True)
        new_text = after.decode("utf-8", errors="replace").splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old_text, new_text, fromfile="До", tofile="После", n=3))
        files.append({"path": path, "diff": diff, "created": not entry["existed"], "rollback_available": True})
        entry["after"] = after
    result = {"id": session["id"], "files": files}
    with _lock:
        _sessions[session["id"]] = session
        while len(_sessions) > _MAX_SESSIONS:
            _sessions.pop(next(iter(_sessions)))
    return result


def rollback_change(session_id, path):
    with _lock:
        session = _sessions.get(session_id)
        if not session or path not in session["files"]:
            return False, "Изменение не найдено или срок хранения истёк"
        entry = session["files"][path]
        absolute = os.path.abspath(path)
        try:
            current = open(absolute, "rb").read() if os.path.isfile(absolute) else b""
            if current != entry.get("after", b""):
                return False, "Файл изменился после работы агента; откат отменён, чтобы не затереть новые правки"
            if entry["existed"]:
                with open(absolute, "wb") as target:
                    target.write(entry["before"])
            elif os.path.exists(absolute):
                os.remove(absolute)
            del session["files"][path]
            return True, "Изменение отменено"
        except OSError as exc:
            return False, str(exc)
