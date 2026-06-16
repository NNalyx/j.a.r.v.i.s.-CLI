"""Compact formatting helpers for UI/tool outputs."""
import re
from typing import Any, Dict, List, Optional


def _short_text(value: Any, max_chars: int = 120) -> str:
    text = _uia_normalize_text(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1].rstrip() + "…"

def _compact_bounds(bounds: Optional[Dict[str, Any]]) -> Dict[str, int]:
    bounds = bounds or {}
    return {
        "x": int(bounds.get("left", 0) or 0),
        "y": int(bounds.get("top", 0) or 0),
        "w": int(bounds.get("width", 0) or 0),
        "h": int(bounds.get("height", 0) or 0),
    }

def _compact_element(element: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not element:
        return None
    return {
        "index": element.get("index"),
        "name": _short_text(element.get("name") or element.get("identity") or "(unnamed)", 100),
        "type": element.get("control_type"),
        "actions": element.get("actions", [])[:4],
        "bounds": _compact_bounds(element.get("bounds")),
    }

def _compact_route(route: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not route:
        return None
    evidence = route.get("evidence") or {}
    return {
        "target": _short_text(route.get("target"), 80),
        "action": route.get("action"),
        "type": route.get("route_type"),
        "confidence": route.get("confidence"),
        "click": route.get("click_position"),
        "nearby_text": [_short_text(item, 50) for item in (evidence.get("nearby_text") or [])[:3]],
    }

def _compact_uia_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "score": candidate.get("score"),
        "match": _short_text(candidate.get("match_text"), 80),
        "element": _compact_element(candidate.get("element")),
    }

def _compact_route_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "score": candidate.get("score"),
        "match": _short_text(candidate.get("match_text"), 80),
        "route": _compact_route(candidate.get("route")),
    }

def _compact_ocr_observation(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "text": _short_text(item.get("name"), 80),
        "confidence": item.get("ocr_confidence"),
        "bounds": _compact_bounds(item.get("bounds")),
    }

def _compact_app_context(context: Dict[str, Any], summary: str, app_entry: Dict[str, Any]) -> Dict[str, Any]:
    actionable = [item for item in context.get("elements", []) if item.get("actionable")]
    return {
        "app_key": context.get("app_key"),
        "title": _short_text(context.get("title"), 120),
        "screen_signature": context.get("screen_signature"),
        "window": {
            "type": context.get("control_type"),
            "class": context.get("class_name"),
            "bounds": _compact_bounds(context.get("bounds")),
        },
        "counts": {
            "elements": context.get("element_count"),
            "actionable": context.get("actionable_count"),
            "known_screens": len((app_entry or {}).get("screens", {})),
            "ocr_observations": len(context.get("ocr_text_elements", []) or []),
            "visual_routes": len(context.get("visual_routes", []) or []),
        },
        "fallback_mode": context.get("fallback_mode"),
        "summary": summary,
        "actionable": [_compact_element(item) for item in actionable[:12]],
        "visual_routes": [_compact_route(route) for route in (context.get("visual_routes", []) or [])[:10]],
        "ocr_observations": [
            _compact_ocr_observation(item)
            for item in (context.get("ocr_text_elements", []) or [])[:8]
        ],
    }

def _uia_normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()

