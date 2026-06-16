"""UI Automation context and action tools."""
from typing import Optional

from jarvis_core.colors import Colors
from jarvis_core.types import ToolResult

from .formatting import _compact_app_context, _short_text
from .utils import (
    _build_visual_routes_from_observations,
    _extract_ocr_elements_from_screenshot,
    _find_best_uia_element,
    _find_best_visual_route,
    _looks_like_web_app_context,
    _store_app_context,
    _summarize_app_context,
    _take_region_screenshot,
    _uia_scan_active_window,
)


def get_app_context(refresh: bool = False, max_elements: int = 300) -> ToolResult:
    """
    Получить структурированный контекст активного окна через UI Automation.

    Возвращает короткий summary для модели и обновляет локальный кэш карты приложения.
    """
    try:
        max_elements = max(50, min(int(max_elements or 300), 600))
        context = _uia_scan_active_window(max_elements=max_elements)

        ocr_text_elements = []
        visual_routes = []
        fallback_mode = "uia"
        screenshot_path = None
        screenshot_meta = None
        if _looks_like_web_app_context(context):
            bounds = context.get("bounds") or {}
            region = {
                "x": int(bounds.get("left", 0) or 0),
                "y": int(bounds.get("top", 0) or 0),
                "width": int(bounds.get("width", 0) or 0),
                "height": int(bounds.get("height", 0) or 0),
            }
            if region["width"] > 0 and region["height"] > 0:
                try:
                    screenshot_path, screenshot_meta, _ = _take_region_screenshot(region=region, max_width=1600, max_height=1000)
                    ocr_text_elements = _extract_ocr_elements_from_screenshot(
                        screenshot_path,
                        screenshot_meta=screenshot_meta,
                        max_results=40,
                    )
                    visual_routes = _build_visual_routes_from_observations(
                        screenshot_path,
                        screenshot_meta,
                        ocr_text_elements,
                    )
                    if visual_routes:
                        fallback_mode = "uia+visual_map"
                except Exception as ocr_error:
                    print(f"{Colors.YELLOW}[AppContext] OCR fallback failed: {ocr_error}{Colors.RESET}")

        context["ocr_text_elements"] = ocr_text_elements
        context["visual_routes"] = visual_routes
        context["fallback_mode"] = fallback_mode
        summary = _summarize_app_context(context)
        app_entry = _store_app_context(context, summary)

        payload = _compact_app_context(context, summary, app_entry)
        payload["cache_refreshed"] = bool(refresh)
        payload["screenshot_path"] = screenshot_path
        payload["message"] = f"Captured app context for '{_short_text(context.get('title') or 'active window', 80)}'"
        return ToolResult(True, payload)
    except Exception as e:
        return ToolResult(False, None, f"Get app context error: {str(e)}")

def do_action_in_app(target: str, action: str = "click", text: Optional[str] = None) -> ToolResult:
    """
    Выполнить действие над элементом активного окна, найденным по текстовому запросу.
    """
    try:
        import pyautogui

        action_norm = str(action or "click").strip().lower()
        if action_norm not in {"click", "double_click", "right_click", "type", "focus"}:
            return ToolResult(False, None, f"Unsupported action: {action_norm}")
        if action_norm == "type" and text is None:
            return ToolResult(False, None, "Action 'type' requires the 'text' argument")

        context = _uia_scan_active_window(max_elements=600)
        best_element, candidates = _find_best_uia_element(target, context.get("elements", []), action=action_norm)
        match_source = "uia"

        best_route = None
        route_candidates = []
        if _looks_like_web_app_context(context):
            bounds = context.get("bounds") or {}
            region = {
                "x": int(bounds.get("left", 0) or 0),
                "y": int(bounds.get("top", 0) or 0),
                "width": int(bounds.get("width", 0) or 0),
                "height": int(bounds.get("height", 0) or 0),
            }
            if region["width"] > 0 and region["height"] > 0:
                screenshot_path, screenshot_meta, _ = _take_region_screenshot(region=region, max_width=1600, max_height=1000)
                ocr_elements = _extract_ocr_elements_from_screenshot(
                    screenshot_path,
                    screenshot_meta=screenshot_meta,
                    max_results=40,
                )
                context["ocr_text_elements"] = ocr_elements
                visual_routes = _build_visual_routes_from_observations(
                    screenshot_path,
                    screenshot_meta,
                    ocr_elements,
                )
                context["visual_routes"] = visual_routes
                best_route, route_candidates = _find_best_visual_route(target, action_norm, visual_routes)

        if not best_element and not best_route:
            return ToolResult(
                False,
                None,
                f"No UIA element or app-map route found for '{target}'"
            )

        route_score = route_candidates[0].get("score", 0.0) if route_candidates else 0.0
        uia_score = candidates[0].get("score", 0.0) if candidates else 0.0
        prefer_route = bool(best_route) and (
            not best_element
            or route_score > uia_score + 0.12
            or (action_norm == "click" and best_route.get("route_type") == "visual_play_button" and target.lower() in {"play", "воспроизвести", "включить"})
        )

        if prefer_route:
            match_source = "visual_map"
            if route_score < 0.58:
                return ToolResult(
                    False,
                    None,
                    f"Low-confidence route for '{target}'. Best route: '{best_route.get('target')}' score={route_score}"
                )
            click = best_route.get("click_position") or {}
            click_x = int(click.get("x", 0) or 0)
            click_y = int(click.get("y", 0) or 0)
            if click_x <= 0 or click_y <= 0:
                return ToolResult(False, None, f"Matched route '{best_route.get('target')}' has invalid click position")
            matched_payload = best_route
        elif candidates and candidates[0].get("score", 0.0) < 0.55:
            return ToolResult(
                False,
                None,
                f"Low-confidence match for '{target}'. Best candidate: '{best_element.get('identity')}' score={candidates[0].get('score')}"
            )
        else:
            bounds = best_element.get("bounds") or {}
            if int(bounds.get("width", 0) or 0) <= 0 or int(bounds.get("height", 0) or 0) <= 0:
                return ToolResult(False, None, f"Matched element '{best_element.get('identity')}' has invalid bounds")

            click_x = int((int(bounds.get("left", 0)) + int(bounds.get("right", 0))) / 2)
            click_y = int((int(bounds.get("top", 0)) + int(bounds.get("bottom", 0))) / 2)
            matched_payload = best_element

        if action_norm == "click":
            pyautogui.click(x=click_x, y=click_y)
        elif action_norm == "double_click":
            pyautogui.doubleClick(x=click_x, y=click_y)
        elif action_norm == "right_click":
            pyautogui.rightClick(x=click_x, y=click_y)
        elif action_norm == "focus":
            pyautogui.click(x=click_x, y=click_y)
        elif action_norm == "type":
            pyautogui.click(x=click_x, y=click_y)
            pyautogui.write(text or "", interval=0.03)

        refreshed_context = _uia_scan_active_window(max_elements=300)
        refreshed_summary = _summarize_app_context(refreshed_context)
        app_entry = _store_app_context(refreshed_context, refreshed_summary)
        before_sig = context.get("screen_signature")
        after_sig = refreshed_context.get("screen_signature")

        return ToolResult(True, {
            "target": target,
            "action": action_norm,
            "typed_text": text if action_norm == "type" else None,
            "matched": _compact_route(matched_payload) if match_source == "visual_map" else _compact_element(matched_payload),
            "match_source": match_source,
            "match_score": route_candidates[0].get("score") if route_candidates else (candidates[0].get("score") if candidates else None),
            "top_candidates": [_compact_uia_candidate(item) for item in candidates[:3]],
            "top_routes": [_compact_route_candidate(item) for item in route_candidates[:3]],
            "click_position": {"x": click_x, "y": click_y},
            "screen_changed": before_sig != after_sig,
            "screen_signature_before": before_sig,
            "screen_signature_after": after_sig,
            "known_screens": len((app_entry or {}).get("screens", {})),
            "post_action_counts": {
                "elements": refreshed_context.get("element_count"),
                "actionable": refreshed_context.get("actionable_count"),
            },
            "message": f"Action '{action_norm}' executed via {match_source} for '{target}'",
        })
    except ImportError as e:
        return ToolResult(False, None, f"Import error: {str(e)}")
    except Exception as e:
        return ToolResult(False, None, f"Do action in app error: {str(e)}")

