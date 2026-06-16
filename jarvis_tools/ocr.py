"""OCR-based click tool."""
import jarvis_core.state as _state
import os
import time
from typing import Optional

from jarvis_core.colors import Colors
from jarvis_core.constants import FUZZY_AVAILABLE, OCR_AVAILABLE, easyocr
from jarvis_core.types import ToolResult

from .utils import _calculate_ocr_text_similarity, _map_bbox_to_screen_coordinates


def click_text(text: str, screenshot_path: Optional[str] = None, threshold: float = 0.8) -> ToolResult:
    """
    Кликнуть по тексту на экране через OCR (EasyOCR + fuzzy поиск).

    Использует последний скриншот от take_screenshot если путь не указан.
    Распознаёт текст через EasyOCR, находит ближайший текст через fuzzy-поиск
    и кликает по центру bounding box.

    Args:
        text: Текст для поиска (например, "закрыть", "OK", "отправить")
        screenshot_path: Путь к скриншоту (если None — используется последний от take_screenshot)
        threshold: Порог fuzzy-поиска (0-1)
    """
    if not OCR_AVAILABLE:
        return ToolResult(False, None, "EasyOCR не установлен. Установите: pip install easyocr")

    if not FUZZY_AVAILABLE:
        return ToolResult(False, None, "fuzzywuzzy не установлен. Установите: pip install fuzzywuzzy")

    try:
        import pyautogui
        from PIL import ImageGrab
        import tempfile

        # Инициализируем OCR reader если нужно (ленивая загрузка)
        if _state._ocr_reader is None:
            print(f"{Colors.CYAN}[OCR] Инициализация EasyOCR (русский + английский)...{Colors.RESET}")
            _state._ocr_reader = easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)
            print(f"{Colors.GREEN}[OCR] Готово{Colors.RESET}")

        # Используем последний скриншот если путь не указан
        if screenshot_path is None:
            screenshot_path = _state._last_screenshot_path

        screenshot_meta = None
        if screenshot_path and _state._last_screenshot_meta and _state._last_screenshot_meta.get("path") == screenshot_path:
            screenshot_meta = dict(_state._last_screenshot_meta)

        # Если нет сохранённого скриншота или файл не существует — делаем новый
        if screenshot_path is None or not os.path.exists(screenshot_path):
            print(f"{Colors.CYAN}[OCR] Нет сохранённого скриншота, делаю новый...{Colors.RESET}")
            screenshot = ImageGrab.grab()
            screenshot_path = os.path.join(tempfile.gettempdir(), f"screenshot_ocr_{int(time.time())}.png")
            screenshot.save(screenshot_path, "PNG")
            screenshot_meta = {
                "path": screenshot_path,
                "scale_factor": 1.0,
                "orig_width": screenshot.width,
                "orig_height": screenshot.height,
                "scaled_width": screenshot.width,
                "scaled_height": screenshot.height,
                "offset_x": 0,
                "offset_y": 0,
                "region": None,
            }
            _state._last_screenshot_path = screenshot_path
            _state._last_screenshot_meta = dict(screenshot_meta)
        else:
            print(f"{Colors.CYAN}[OCR] Использую последний скриншот: {screenshot_path}{Colors.RESET}")
            if screenshot_meta is None:
                screenshot_meta = {
                    "path": screenshot_path,
                    "scale_factor": 1.0,
                    "offset_x": 0,
                    "offset_y": 0,
                }

        # Распознаём текст
        results = _state._ocr_reader.readtext(screenshot_path)

        if not results:
            return ToolResult(False, None, "Текст не найден на скриншоте")

        candidates = []
        for bbox, detected_text, confidence in results:
            similarity = _calculate_ocr_text_similarity(text, detected_text)
            ocr_confidence = max(0.0, min(float(confidence or 0.0), 1.0))
            if similarity < threshold:
                continue

            coords = _map_bbox_to_screen_coordinates(bbox, screenshot_meta)
            final_score = (similarity * 0.82) + (ocr_confidence * 0.18)
            candidates.append({
                "detected_text": detected_text,
                "similarity": round(similarity, 3),
                "ocr_confidence": round(ocr_confidence, 3),
                "score": round(final_score, 3),
                "bbox_scaled": coords["bbox_scaled"],
                "bbox_screen": coords["bbox_screen"],
                "click_position": [coords["center_x"], coords["center_y"]],
            })

        candidates.sort(key=lambda item: (-item["score"], -item["similarity"], -item["ocr_confidence"]))

        if not candidates:
            best_alternative = None
            for bbox, detected_text, confidence in results:
                similarity = _calculate_ocr_text_similarity(text, detected_text)
                if best_alternative is None or similarity > best_alternative["similarity"]:
                    best_alternative = {
                        "detected_text": detected_text,
                        "similarity": round(similarity, 3),
                        "ocr_confidence": round(max(0.0, min(float(confidence or 0.0), 1.0)), 3),
                    }
            return ToolResult(
                False,
                None,
                f"Текст '{text}' не найден с threshold={threshold:.2f}"
                + (
                    f" (лучшее совпадение: '{best_alternative['detected_text']}' "
                    f"sim={best_alternative['similarity']:.3f}, ocr={best_alternative['ocr_confidence']:.3f})"
                    if best_alternative else ""
                )
            )

        best_candidate = candidates[0]
        click_x, click_y = best_candidate["click_position"]
        pyautogui.click(x=click_x, y=click_y)

        return ToolResult(True, {
            "text": text,
            "matched_text": best_candidate["detected_text"],
            "confidence": best_candidate["similarity"],
            "ocr_confidence": best_candidate["ocr_confidence"],
            "score": best_candidate["score"],
            "bbox": best_candidate["bbox_screen"],
            "bbox_scaled": best_candidate["bbox_scaled"],
            "click_position": best_candidate["click_position"],
            "scale_factor": float((screenshot_meta or {}).get("scale_factor") or 1.0),
            "screenshot_path": screenshot_path,
            "top_candidates": candidates[:5],
            "message": f"Клик по тексту '{best_candidate['detected_text']}' в ({click_x}, {click_y})"
        })

    except ImportError as e:
        return ToolResult(False, None, f"Import error: {str(e)}")
    except Exception as e:
        return ToolResult(False, None, f"click_text error: {str(e)}")

