import json
import os
import shutil
import subprocess
import threading
import time
import winreg
from difflib import SequenceMatcher

__all__ = [
    "launch_app_fuzzy",
]


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, "app_launcher_cache.json")
CACHE_TTL_SECONDS = 24 * 60 * 60
_cache_lock = threading.Lock()


def similarity(a: str, b: str) -> float:
    """Возвращает коэффициент сходства строк (0…1)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _normalize_name(value: str) -> str:
    cleaned = (value or "").strip().lower()
    return " ".join(cleaned.split())


def _launch_target(target: str) -> bool:
    if not target:
        return False

    try:
        if os.path.exists(target):
            os.startfile(target)
            return True
    except Exception:
        pass

    try:
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        subprocess.Popen(
            [target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
        )
        return True
    except Exception:
        return False


def _iter_shortcut_roots():
    up = os.environ.get("USERPROFILE")
    pd = os.environ.get("PROGRAMDATA")
    if up:
        yield os.path.join(up, "Desktop")
        yield os.path.join(up, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs")
    if pd:
        yield os.path.join(pd, "Microsoft", "Windows", "Start Menu", "Programs")


def _iter_exe_roots():
    for env in ("ProgramFiles", "ProgramFiles(x86)"):
        path = os.environ.get(env)
        if path:
            yield path

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        yield os.path.join(local_app_data, "Programs")


def _load_cache() -> dict:
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _save_cache(data: dict) -> None:
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _collect_shortcut_candidates():
    candidates = []
    seen = set()

    for root in _iter_shortcut_roots():
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                if not filename.lower().endswith(".lnk"):
                    continue
                full_path = os.path.join(dirpath, filename)
                lowered = full_path.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                display_name = os.path.splitext(filename)[0]
                candidates.append(
                    {
                        "name": display_name,
                        "target": full_path,
                        "kind": "shortcut",
                    }
                )
    return candidates


def _collect_registry_candidates(app_name: str):
    results = []
    hives = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    query = _normalize_name(app_name)

    for hive, subkey in hives:
        try:
            reg = winreg.OpenKey(hive, subkey)
        except FileNotFoundError:
            continue

        for i in range(winreg.QueryInfoKey(reg)[0]):
            try:
                sk_name = winreg.EnumKey(reg, i)
                sk = winreg.OpenKey(reg, sk_name)
                display_name = winreg.QueryValueEx(sk, "DisplayName")[0]
                if query and query not in _normalize_name(display_name):
                    continue

                try:
                    install_location = winreg.QueryValueEx(sk, "InstallLocation")[0]
                except Exception:
                    install_location = ""

                if install_location and os.path.isdir(install_location):
                    for filename in os.listdir(install_location):
                        if filename.lower().endswith(".exe"):
                            results.append(
                                {
                                    "name": display_name,
                                    "target": os.path.join(install_location, filename),
                                    "kind": "registry",
                                }
                            )

                try:
                    uninstall_string = winreg.QueryValueEx(sk, "UninstallString")[0]
                    exe_path = uninstall_string.split('"')[1] if '"' in uninstall_string else uninstall_string.split()[0]
                    if exe_path.lower().endswith(".exe") and os.path.isfile(exe_path):
                        results.append(
                            {
                                "name": display_name,
                                "target": exe_path,
                                "kind": "registry",
                            }
                        )
                except Exception:
                    pass
            except OSError:
                continue

    return results


def _collect_exe_candidates(app_name: str):
    exe_lower = f"{app_name}.exe".lower()
    results = []
    seen = set()

    for root in _iter_exe_roots():
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                if filename.lower() != exe_lower:
                    continue
                full_path = os.path.join(dirpath, filename)
                lowered = full_path.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                results.append(
                    {
                        "name": os.path.splitext(filename)[0],
                        "target": full_path,
                        "kind": "exe",
                    }
                )
    return results


def _build_shortcut_cache() -> dict:
    entries = _collect_shortcut_candidates()
    return {
        "version": 2,
        "created_at": time.time(),
        "shortcuts": entries,
    }


def _get_shortcut_cache() -> list:
    with _cache_lock:
        cache = _load_cache()
        created_at = float(cache.get("created_at", 0) or 0)
        if cache.get("version") == 2 and cache.get("shortcuts") and (time.time() - created_at) < CACHE_TTL_SECONDS:
            return cache["shortcuts"]

        cache = _build_shortcut_cache()
        _save_cache(cache)
        return cache["shortcuts"]


def _score_candidates(app_name: str, candidates: list, threshold: float) -> list:
    query = _normalize_name(app_name)
    scored = []

    for candidate in candidates:
        display_name = candidate.get("name", "")
        normalized_name = _normalize_name(display_name)
        target = candidate.get("target", "")
        if not display_name or not target:
            continue

        if normalized_name == query:
            score = 1.0
        elif query and (normalized_name.startswith(query) or query in normalized_name):
            score = 0.95
        else:
            score = similarity(query, normalized_name)

        if score >= threshold:
            scored.append((score, target, display_name))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def _try_launch_from_path(app_name: str) -> bool:
    raw_name = (app_name or "").strip()
    if not raw_name:
        return False

    if os.path.exists(raw_name):
        return _launch_target(raw_name)

    if _launch_target(raw_name):
        return True

    which_target = shutil.which(raw_name)
    if which_target:
        return _launch_target(which_target)

    exe_name = raw_name if raw_name.lower().endswith(".exe") else f"{raw_name}.exe"
    which_target = shutil.which(exe_name)
    if which_target:
        return _launch_target(which_target)

    return False


def _find_best_candidate(app_name: str, threshold: float) -> str:
    shortcut_matches = _score_candidates(app_name, _get_shortcut_cache(), threshold)
    if shortcut_matches:
        return shortcut_matches[0][1]

    registry_matches = _score_candidates(app_name, _collect_registry_candidates(app_name), threshold)
    if registry_matches:
        return registry_matches[0][1]

    exe_matches = _score_candidates(app_name, _collect_exe_candidates(app_name), threshold)
    if exe_matches:
        return exe_matches[0][1]

    return ""


def launch_app_fuzzy(app_name: str, threshold: float = 0.7) -> bool:
    """
    Поиск и запуск приложения по "гибкому" совпадению имени.
    Сначала пробует быстрые пути, затем кэш ярлыков, и только потом медленный обход диска.
    """
    if _try_launch_from_path(app_name):
        return True

    best_target = _find_best_candidate(app_name, threshold)
    if not best_target:
        return False

    return _launch_target(best_target)
