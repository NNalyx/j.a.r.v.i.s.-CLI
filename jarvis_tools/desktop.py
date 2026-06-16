"""Desktop automation tools (screenshot, mouse, keyboard, app launch)."""
import jarvis_core.state as _state
import os
import time
from typing import Dict, List, Optional

from app_launcher import launch_app_fuzzy
from jarvis_core.types import ToolResult


def take_screenshot(region: Optional[Dict[str, int]] = None, max_width: int = 1920,
                    max_height: int = 1080) -> ToolResult:
    """Сделать скриншот экрана (с масштабированием до FullHD)"""
    try:
        from PIL import Image, ImageGrab
        import tempfile

        # region = {"x": x1, "y": y1, "width": w, "height": h}
        offset_x = 0
        offset_y = 0
        if region:
            bbox = (
                region.get("x", 0),
                region.get("y", 0),
                region.get("x", 0) + region.get("width", 0),
                region.get("y", 0) + region.get("height", 0)
            )
            offset_x = int(region.get("x", 0) or 0)
            offset_y = int(region.get("y", 0) or 0)
            screenshot = ImageGrab.grab(bbox=bbox)
        else:
            screenshot = ImageGrab.grab()

        # Масштабирование если разрешение больше целевого
        orig_width, orig_height = screenshot.size
        scale_factor = 1.0

        if orig_width > max_width or orig_height > max_height:
            # Сохраняем aspect ratio
            scale_factor = min(max_width / orig_width, max_height / orig_height)
            new_width = int(orig_width * scale_factor)
            new_height = int(orig_height * scale_factor)
            screenshot = screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(
                f"[SCREENSHOT] Масштабирование: {orig_width}x{orig_height} → {new_width}x{new_height} (scale={scale_factor:.3f})")

        # Сохраняем во временный файл
        temp_path = os.path.join(tempfile.gettempdir(), f"screenshot_{int(time.time())}.png")
        screenshot.save(temp_path, "PNG")

        # Сохраняем путь для последующего использования в click_text
        _state._last_screenshot_path = temp_path
        _state._last_screenshot_meta = {
            "path": temp_path,
            "scale_factor": scale_factor,
            "orig_width": orig_width,
            "orig_height": orig_height,
            "scaled_width": screenshot.width,
            "scaled_height": screenshot.height,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "region": region or None,
        }

        return ToolResult(True, {
            "path": temp_path,
            "width": screenshot.width,
            "height": screenshot.height,
            "scale_factor": scale_factor,
            "orig_width": orig_width,
            "orig_height": orig_height,
            "offset_x": offset_x,
            "offset_y": offset_y,
            "message": f"Скриншот сохранён: {temp_path} ({screenshot.width}x{screenshot.height})"
        })
    except ImportError:
        return ToolResult(False, None, "PIL not installed. Run: pip install Pillow")
    except Exception as e:
        return ToolResult(False, None, f"Screenshot error: {str(e)}")

def move_mouse(x: int, y: int, duration: float = 0.5) -> ToolResult:
    """Переместить курсор мыши"""
    try:
        import pyautogui
        pyautogui.moveTo(x=x, y=y, duration=duration)
        return ToolResult(True, {"x": x, "y": y, "message": f"Cursor moved to ({x}, {y})"})
    except ImportError:
        return ToolResult(False, None, "pyautogui not installed. Run: pip install pyautogui")
    except Exception as e:
        return ToolResult(False, None, f"Move error: {str(e)}")

def type_text(text: str, interval: float = 0.05) -> ToolResult:
    """Напечатать текст с клавиатуры"""
    try:
        import pyautogui
        pyautogui.write(text, interval=interval)
        return ToolResult(True, {"text": text[:100], "message": f"Text typed ({len(text)} chars)"})
    except ImportError:
        return ToolResult(False, None, "pyautogui not installed. Run: pip install pyautogui")
    except Exception as e:
        return ToolResult(False, None, f"Input error: {str(e)}")

def get_cursor_position() -> ToolResult:
    """Получить координаты курсора"""
    try:
        import pyautogui
        pos = pyautogui.position()
        return ToolResult(True, {"x": pos.x, "y": pos.y, "message": f"Cursor position: ({pos.x}, {pos.y})"})
    except ImportError:
        return ToolResult(False, None, "pyautogui not installed. Run: pip install pyautogui")
    except Exception as e:
        return ToolResult(False, None, f"Error: {str(e)}")

def press_key(key: str) -> ToolResult:
    """Нажать клавишу на клавиатуре"""
    try:
        import pyautogui
        pyautogui.press(key)
        return ToolResult(True, {"key": key, "message": f"Key '{key}' pressed"})
    except ImportError:
        return ToolResult(False, None, "pyautogui not installed. Run: pip install pyautogui")
    except Exception as e:
        return ToolResult(False, None, f"Error: {str(e)}")

def hotkey(keys: List[str]) -> ToolResult:
    """Нажать комбинацию клавиш (hotkey)"""
    try:
        import pyautogui
        pyautogui.hotkey(*keys)
        return ToolResult(True, {"keys": keys, "message": f"Hotkey {'+'.join(keys)} pressed"})
    except ImportError:
        return ToolResult(False, None, "pyautogui not installed. Run: pip install pyautogui")
    except Exception as e:
        return ToolResult(False, None, f"Error: {str(e)}")

def launch_app(app_name: str) -> ToolResult:
    """Запустить приложение по имени (гибкий поиск)

    Ищет приложение в:
    - Program Files / Program Files (x86)
    - Меню Пуск и на рабочем столе
    - Реестре (Uninstall keys)

    Использует нечёткое сопоставление имён.
    """
    try:
        success = launch_app_fuzzy(app_name)
        if success:
            return ToolResult(True, {"app": app_name, "message": f"App '{app_name}' launched"})
        else:
            return ToolResult(False, None,
                              f"App '{app_name}' not found. Try a different name or use run_cmd.")
    except Exception as e:
        return ToolResult(False, None, f"Launch error: {str(e)}")

