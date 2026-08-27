"""Shared mutable state for Jarvis."""
import threading
from typing import Callable, Optional

# Handler для синхронных запросов пользователю из инструментов (ask_user).
# Устанавливается jarvis_web_desktop.py при старте веб-сервера.
user_prompt_handler: Optional[Callable[[str, float], Optional[str]]] = None

# Handler для прогресса генерации изображений: (tool_call_id, percent) -> None.
# Устанавливается jarvis_web_desktop.py внутри активного chat stream.
image_progress_handler: Optional[Callable[[str, int], None]] = None

# ID активного вызова инструмента, используется для привязки прогресса к UI placeholder.
current_tool_call_id: Optional[str] = None

_tts_model = None
_tts_device = None
_tts_voice_style = None
_tts_lock = threading.Lock()

_ocr_reader = None

_last_screenshot_path = None
_last_screenshot_meta = None

_app_maps_cache = None
_app_maps_lock = threading.Lock()
