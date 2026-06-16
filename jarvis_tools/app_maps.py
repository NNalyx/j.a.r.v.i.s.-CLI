"""App-map cache helpers."""
import jarvis_core.state as _state
import json
import os
from typing import Any, Dict

from jarvis_core.constants import APP_MAPS_FILE


def _load_app_maps() -> Dict[str, Any]:

    with _state._app_maps_lock:
        if _state._app_maps_cache is not None:
            return _state._app_maps_cache

        if os.path.exists(APP_MAPS_FILE):
            try:
                with open(APP_MAPS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("apps"), dict):
                    _state._app_maps_cache = data
                    return _state._app_maps_cache
            except Exception:
                pass

        _state._app_maps_cache = {"apps": {}}
        return _state._app_maps_cache


def _save_app_maps() -> None:
    with _state._app_maps_lock:
        if _state._app_maps_cache is None:
            return
        try:
            with open(APP_MAPS_FILE, "w", encoding="utf-8") as f:
                json.dump(_state._app_maps_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
