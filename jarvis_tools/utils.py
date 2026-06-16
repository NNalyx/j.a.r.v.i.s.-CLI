"""Internal helpers for UIA, OCR, search, and text processing."""
import jarvis_core.state as _state
import hashlib
import html
import json
import os
import re
import requests
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from jarvis_core.colors import Colors
from jarvis_core.constants import (
    APP_MAPS_FILE,
    Desktop,
    FUZZY_AVAILABLE,
    OCR_AVAILABLE,
    UI_AUTOMATION_AVAILABLE,
    easyocr,
    fuzz,
    process,
)
from jarvis_core.types import ToolResult

from .app_maps import _load_app_maps, _save_app_maps
from .formatting import (
    _compact_app_context,
    _compact_element,
    _compact_ocr_observation,
    _compact_route,
    _compact_route_candidate,
    _compact_uia_candidate,
    _short_text,
    _uia_normalize_text,
)


def _uia_rect_to_dict(rect: Any) -> Dict[str, int]:
    return {
        "left": int(getattr(rect, "left", 0) or 0),
        "top": int(getattr(rect, "top", 0) or 0),
        "right": int(getattr(rect, "right", 0) or 0),
        "bottom": int(getattr(rect, "bottom", 0) or 0),
        "width": int(getattr(rect, "width", lambda: 0)() if callable(getattr(rect, "width", None)) else getattr(rect, "width", 0) or 0),
        "height": int(getattr(rect, "height", lambda: 0)() if callable(getattr(rect, "height", None)) else getattr(rect, "height", 0) or 0),
    }

def _uia_get_active_window():
    if not UI_AUTOMATION_AVAILABLE or Desktop is None:
        raise RuntimeError("pywinauto is not installed. Install it with: pip install pywinauto")

    if os.name != "nt":
        raise RuntimeError("UI Automation tools are supported only on Windows")

    ctypes = __import__("ctypes")
    handle = int(ctypes.windll.user32.GetForegroundWindow() or 0)
    if not handle:
        raise RuntimeError("Could not detect the active window")

    desktop = Desktop(backend="uia")
    return desktop.window(handle=handle), handle

def _uia_collect_actions(control_type: str) -> List[str]:
    control = str(control_type or "").lower()
    actions = ["focus"]

    if control in {
        "button", "hyperlink", "menuitem", "tabitem", "treeitem",
        "listitem", "checkbox", "radiobutton", "splitbutton"
    }:
        actions.append("click")
    if control in {"edit", "document", "combobox"}:
        actions.extend(["click", "type"])
    if control in {"checkbox", "radiobutton"}:
        actions.append("toggle")
    if control in {"tabitem", "listitem", "treeitem", "combobox"}:
        actions.append("select")

    seen = set()
    result = []
    for action in actions:
        if action not in seen:
            seen.add(action)
            result.append(action)
    return result

def _uia_is_actionable(element_payload: Dict[str, Any]) -> bool:
    if not element_payload.get("enabled", True):
        return False
    if not element_payload.get("visible", True):
        return False
    bounds = element_payload.get("bounds") or {}
    if int(bounds.get("width", 0) or 0) <= 0 or int(bounds.get("height", 0) or 0) <= 0:
        return False
    if element_payload.get("control_type") in {"Button", "Edit", "ComboBox", "TabItem", "ListItem", "MenuItem", "Hyperlink", "CheckBox", "RadioButton", "TreeItem"}:
        return True
    return False

def _uia_element_identity(element_payload: Dict[str, Any]) -> str:
    parts = [
        element_payload.get("name") or "",
        element_payload.get("control_type") or "",
        element_payload.get("automation_id") or "",
        element_payload.get("class_name") or "",
    ]
    return " | ".join(part for part in parts if part).strip()

def _uia_scan_active_window(max_elements: int = 120) -> Dict[str, Any]:
    window, handle = _uia_get_active_window()

    try:
        window.set_focus()
    except Exception:
        pass

    info = getattr(window, "element_info", None)
    rect = _uia_rect_to_dict(window.rectangle())
    process_id = int(getattr(info, "process_id", 0) or 0)
    control_type = _uia_normalize_text(getattr(info, "control_type", "Window"))
    class_name = _uia_normalize_text(getattr(info, "class_name", ""))
    title = _uia_normalize_text(window.window_text())

    try:
        descendants = window.descendants()
    except Exception:
        descendants = []

    elements = []
    raw_signature_parts = []
    actionable_count = 0

    for index, child in enumerate(descendants):
        if len(elements) >= max_elements:
            break

        child_info = getattr(child, "element_info", None)
        child_name = _uia_normalize_text(child.window_text())
        child_type = _uia_normalize_text(getattr(child_info, "control_type", ""))
        child_auto_id = _uia_normalize_text(getattr(child_info, "automation_id", ""))
        child_class = _uia_normalize_text(getattr(child_info, "class_name", ""))

        if not any([child_name, child_type, child_auto_id, child_class]):
            continue

        try:
            child_rect = _uia_rect_to_dict(child.rectangle())
        except Exception:
            child_rect = {"left": 0, "top": 0, "right": 0, "bottom": 0, "width": 0, "height": 0}

        try:
            enabled = bool(child.is_enabled())
        except Exception:
            enabled = True

        try:
            visible = bool(child.is_visible())
        except Exception:
            visible = True

        element_payload = {
            "index": len(elements),
            "tree_index": index,
            "name": child_name,
            "control_type": child_type,
            "automation_id": child_auto_id,
            "class_name": child_class,
            "enabled": enabled,
            "visible": visible,
            "bounds": child_rect,
            "actions": _uia_collect_actions(child_type),
        }
        element_payload["actionable"] = _uia_is_actionable(element_payload)
        element_payload["identity"] = _uia_element_identity(element_payload)

        raw_signature_parts.append(
            "|".join([
                child_name[:80],
                child_type,
                child_auto_id[:80],
                child_class[:80],
                str(child_rect.get("left", 0)),
                str(child_rect.get("top", 0)),
                str(enabled),
                str(visible),
            ])
        )

        if element_payload["actionable"]:
            actionable_count += 1

        elements.append(element_payload)

    signature_source = "\n".join(raw_signature_parts[:200])
    screen_signature = hashlib.sha1(signature_source.encode("utf-8", errors="ignore")).hexdigest()[:16]
    process_name = f"pid-{process_id}"
    app_key = hashlib.sha1(f"{process_name}|{title}".encode("utf-8", errors="ignore")).hexdigest()[:16]

    return {
        "app_key": app_key,
        "window_handle": handle,
        "process_id": process_id,
        "process_name": process_name,
        "title": title,
        "control_type": control_type or "Window",
        "class_name": class_name,
        "bounds": rect,
        "screen_signature": screen_signature,
        "element_count": len(elements),
        "actionable_count": actionable_count,
        "elements": elements,
    }

def _summarize_app_context(context: Dict[str, Any], max_items: int = 10) -> str:
    lines = [
        f"Active window: {context.get('title') or '(untitled)'}",
        f"App key: {context.get('app_key')} | PID: {context.get('process_id')} | Signature: {context.get('screen_signature')}",
        f"Window type: {context.get('control_type')} | Class: {context.get('class_name') or '-'}",
        f"Elements: {context.get('element_count', 0)} total, {context.get('actionable_count', 0)} actionable",
        "Top actionable elements:",
    ]

    actionable = [item for item in context.get("elements", []) if item.get("actionable")]
    for item in actionable[:max_items]:
        label = _short_text(item.get("name") or item.get("automation_id") or item.get("class_name") or "(unnamed)", 90)
        lines.append(
            f"- [{item.get('index')}] {label} | {item.get('control_type') or '?'} | actions={','.join(item.get('actions') or [])}"
        )

    if len(actionable) > max_items:
        lines.append(f"- ... and {len(actionable) - max_items} more actionable elements")

    ocr_items = context.get("ocr_text_elements", []) or []
    if ocr_items:
        lines.append("Visible OCR observations:")
        for item in ocr_items[:6]:
            lines.append(f"- {_short_text(item.get('name'), 70)} | ocr={item.get('ocr_confidence', 0.0):.2f}")
        if len(ocr_items) > 6:
            lines.append(f"- ... and {len(ocr_items) - 6} more OCR observations")

    visual_routes = context.get("visual_routes", []) or []
    if visual_routes:
        lines.append("Visual app-map routes:")
        for route in visual_routes[:8]:
            evidence = route.get("evidence") or {}
            nearby = ", ".join(_short_text(item, 35) for item in (evidence.get("nearby_text", []) or [])[:2])
            suffix = f" | near={nearby}" if nearby else ""
            lines.append(
                f"- {_short_text(route.get('target'), 70)} -> {route.get('action')} | {route.get('route_type')} | conf={route.get('confidence', 0.0):.2f}{suffix}"
            )
        if len(visual_routes) > 8:
            lines.append(f"- ... and {len(visual_routes) - 8} more visual routes")

    return "\n".join(lines)

def _store_app_context(context: Dict[str, Any], summary: str) -> Dict[str, Any]:
    data = _load_app_maps()
    apps = data.setdefault("apps", {})
    app_key = context.get("app_key") or "unknown"
    app_entry = apps.setdefault(app_key, {
        "app_key": app_key,
        "process_name": context.get("process_name"),
        "process_id": context.get("process_id"),
        "latest_title": context.get("title"),
        "last_seen_at": None,
        "screens": {},
    })

    app_entry["process_name"] = context.get("process_name")
    app_entry["process_id"] = context.get("process_id")
    app_entry["latest_title"] = context.get("title")
    app_entry["last_seen_at"] = datetime.now().isoformat(timespec="seconds")

    screens = app_entry.setdefault("screens", {})
    screen_key = context.get("screen_signature") or "unknown"
    screen_entry = screens.get(screen_key, {})
    screen_entry.update({
        "screen_signature": screen_key,
        "title": context.get("title"),
        "class_name": context.get("class_name"),
        "control_type": context.get("control_type"),
        "element_count": context.get("element_count"),
        "actionable_count": context.get("actionable_count"),
        "summary": summary,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "elements": [
            _compact_element(item)
            for item in (context.get("elements", []) or [])
            if item.get("actionable")
        ][:30],
        "ocr_text_elements": [
            _compact_ocr_observation(item)
            for item in (context.get("ocr_text_elements", []) or [])[:20]
        ],
        "visual_routes": [
            _compact_route(route)
            for route in (context.get("visual_routes", []) or [])[:20]
        ],
    })
    screens[screen_key] = screen_entry
    _save_app_maps()
    return app_entry

def _uia_action_rank(element_payload: Dict[str, Any], action: str = "click") -> int:
    control_type = str(element_payload.get("control_type") or "")
    actions = set(element_payload.get("actions") or [])

    if action == "click":
        if "click" not in actions:
            return -100
        if control_type in {"Button", "Hyperlink", "MenuItem"}:
            return 40
        if control_type in {"ListItem", "TabItem", "TreeItem"}:
            return 30
        if control_type in {"CheckBox", "RadioButton"}:
            return 25
        if control_type == "Document":
            return -30
        return 5

    if action == "type":
        if "type" in actions:
            return 40 if control_type in {"Edit", "ComboBox"} else 10
        return -100

    return 10 if action in actions or action == "focus" else -100

def _find_best_uia_element(target: str, elements: List[Dict[str, Any]], action: str = "click") -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    target_norm = _uia_normalize_text(target)
    candidates = []

    for item in elements:
        if not item.get("actionable"):
            continue
        action_rank = _uia_action_rank(item, action)
        if action_rank < 0:
            continue

        texts = [
            item.get("name") or "",
            item.get("automation_id") or "",
            item.get("identity") or "",
            item.get("class_name") or "",
        ]
        non_empty_texts = [text for text in texts if text]
        if not non_empty_texts:
            continue

        best_score = max(_calculate_text_similarity(target_norm, text) for text in non_empty_texts)
        if best_score <= 0:
            continue
        match_text = max(non_empty_texts, key=lambda value: _calculate_text_similarity(target_norm, value or ""))
        name_norm = _uia_normalize_text(item.get("name") or "").lower()
        target_lower = target_norm.lower()
        exact_name = bool(name_norm and name_norm == target_lower)
        exact_identity = _uia_normalize_text(item.get("identity") or "").lower() == target_lower

        candidates.append({
            "score": round(best_score, 3),
            "action_rank": action_rank,
            "exact_name": exact_name,
            "exact_identity": exact_identity,
            "element": item,
            "match_text": match_text,
        })

    candidates.sort(
        key=lambda entry: (
            entry["score"],
            entry["action_rank"],
            1 if entry.get("exact_identity") else 0,
            1 if entry.get("exact_name") else 0,
            -len(entry["element"].get("identity") or ""),
        ),
        reverse=True,
    )

    return (candidates[0]["element"] if candidates else None), candidates[:5]

def _code_text_to_lines(text: str) -> List[str]:
    """Преобразовать текст кода в список строк с сохранением структуры."""
    if text is None:
        return []

    text = str(text)
    if text == "":
        return []

    parts = text.splitlines(keepends=True)
    if not parts:
        return [text]

    if not parts[-1].endswith(("\n", "\r")):
        parts[-1] += "\n"
    return parts

def _normalize_code_for_compare(text: str) -> str:
    """Нормализовать код для безопасного сравнения без шума от переводов строк."""
    return str(text or "").replace("\r\n", "\n").rstrip("\n")

def _locate_code_block(lines: List[str], expected_old_code: str) -> Optional[tuple[int, int]]:
    """Найти точный блок кода в файле и вернуть диапазон строк (1-indexed)."""
    normalized_target = _normalize_code_for_compare(expected_old_code)
    if not normalized_target:
        return None

    normalized_file = "".join(lines).replace("\r\n", "\n")
    needle = normalized_target
    matches = []
    search_from = 0
    while True:
        idx = normalized_file.find(needle, search_from)
        if idx == -1:
            break
        matches.append(idx)
        search_from = idx + 1

    if len(matches) != 1:
        return None

    start_char = matches[0]
    end_char = start_char + len(needle)
    start_line = normalized_file[:start_char].count("\n") + 1
    matched_line_count = needle.count("\n") + 1
    end_line = start_line + matched_line_count - 1
    return start_line, end_line

def _augment_web_error_message(message: str, *, url: Optional[str] = None) -> str:
    raw_message = str(message or "").strip()
    lowered = raw_message.lower()

    vpn_signals = (
        "timeout",
        "timed out",
        "net::err_timed_out",
        "net::err_connection_timed_out",
        "net::err_connection_reset",
        "net::err_connection_closed",
        "net::err_connection_refused",
        "net::err_name_not_resolved",
        "net::err_tunnel_connection_failed",
        "net::err_network_changed",
        "dns",
    )

    vpn_hint = ""
    if any(signal in lowered for signal in vpn_signals):
        resource_label = url or "this resource"
        vpn_hint = f" This resource may require a VPN from your region: {resource_label}"

    return f"{raw_message}{vpn_hint}".strip()

def _normalize_search_text(value: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()

def _extract_real_search_url(raw_url: Optional[str]) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""
    if url.startswith("//"):
        url = f"https:{url}"

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for param in ("uddg", "q", "url", "u"):
        values = query.get(param)
        if values and values[0].startswith("http"):
            return unquote(values[0])
    return url

def _format_search_results(search_results: List[Dict[str, str]], provider_name: str) -> ToolResult:
    formatted = [f"Search provider: {provider_name}"]
    for i, result in enumerate(search_results[:10], 1):
        formatted.append(
            f"Результат {i}:\n"
            f"Заголовок: {result['title']}\n"
            f"Ссылка: {result['link']}\n"
            f"Описание: {result['snippet'][:280]}"
        )
    return ToolResult(True, "\n\n".join(formatted))

def _search_with_google_playwright(query: str) -> ToolResult:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        try:
            page = browser.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=10000)

            try:
                page.click('button:has-text("Принять")', timeout=3000)
            except Exception:
                pass

            page.fill('textarea[name="q"]', query)
            page.press('textarea[name="q"]', 'Enter')

            try:
                page.wait_for_selector('#search, div#search, div.g, div.MjjYud', timeout=10000)
            except Exception:
                time.sleep(2)

            page_text = page.inner_text('body') if page.query_selector('body') else ""
            page_url = page.url or ""
            page_text_lower = page_text.lower()

            blocked_markers = (
                "unusual traffic",
                "not a robot",
                "detected unusual traffic",
                "captcha",
                "на ваш компьютер или сеть отправляется необычный трафик",
            )
            if "sorry" in page_url or any(marker in page_text_lower for marker in blocked_markers):
                return ToolResult(
                    False,
                    None,
                    "Search engine blocked or challenged the automated request. Google may be showing CAPTCHA or anti-bot protection."
                )

            search_results = []
            blocks = page.query_selector_all('div.MjjYud, div.g, div[data-snc]')
            for block in blocks:
                try:
                    link_elem = block.query_selector('a[href]')
                    if not link_elem:
                        continue

                    link = _extract_real_search_url(link_elem.get_attribute('href'))
                    if (
                        not link or
                        not link.startswith('http') or
                        'google.com' in link or
                        '/search?' in link or
                        link.startswith('https://webcache.googleusercontent.com')
                    ):
                        continue

                    title_elem = block.query_selector('h3')
                    title = title_elem.inner_text().strip() if title_elem else ""
                    if not title:
                        continue

                    snippet_elem = block.query_selector('div.VwiC3b, div[data-sncf="1"], div.yXK7lf, span.aCOpRe')
                    snippet = snippet_elem.inner_text().strip() if snippet_elem else ""
                    search_results.append({
                        'title': title,
                        'link': link,
                        'snippet': snippet
                    })
                except Exception:
                    continue

            if search_results:
                return _format_search_results(search_results, "Google")

            has_no_results_text = (
                "did not match any documents" in page_text_lower or
                "no results found" in page_text_lower or
                "ничего не найдено" in page_text_lower or
                "по запросу" in page_text_lower and "ничего не найдено" in page_text_lower
            )
            if has_no_results_text:
                return ToolResult(False, None, f"No search results found for query: {query.strip()[:200]}")
            return ToolResult(
                False,
                None,
                "Search page loaded, but no parsable results were extracted. Google may have changed markup or blocked automated access."
            )
        finally:
            browser.close()

def _search_with_duckduckgo_html(query: str) -> ToolResult:
    response = requests.get(
        f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        },
        timeout=15,
    )
    response.raise_for_status()
    page_html = response.text

    block_pattern = re.compile(r'<div[^>]*class="result[^"]*"[^>]*>(.*?)</div>\s*</div>', re.IGNORECASE | re.DOTALL)
    link_pattern = re.compile(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    snippet_pattern = re.compile(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>|<div[^>]*class="result__snippet"[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)

    search_results = []
    for block_match in block_pattern.finditer(page_html):
        block_html = block_match.group(1)
        link_match = link_pattern.search(block_html)
        if not link_match:
            continue

        link = _extract_real_search_url(link_match.group(1))
        title = _normalize_search_text(link_match.group(2))
        if not link or not title:
            continue

        snippet_match = snippet_pattern.search(block_html)
        snippet = _normalize_search_text((snippet_match.group(1) or snippet_match.group(2)) if snippet_match else "")
        search_results.append({"title": title, "link": link, "snippet": snippet})

    if search_results:
        return _format_search_results(search_results, "DuckDuckGo HTML")

    page_text = _normalize_search_text(page_html).lower()
    if "no results" in page_text:
        return ToolResult(False, None, f"No search results found for query: {query.strip()[:200]}")
    return ToolResult(False, None, "DuckDuckGo HTML search returned no parsable results.")

def _search_with_bing(query: str) -> ToolResult:
    response = requests.get(
        f"https://www.bing.com/search?q={quote_plus(query)}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        },
        timeout=15,
    )
    response.raise_for_status()
    page_html = response.text

    block_pattern = re.compile(r'<li[^>]*class="b_algo"[^>]*>(.*?)</li>', re.IGNORECASE | re.DOTALL)
    link_pattern = re.compile(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
    snippet_pattern = re.compile(r'<p>(.*?)</p>', re.IGNORECASE | re.DOTALL)

    search_results = []
    for block_match in block_pattern.finditer(page_html):
        block_html = block_match.group(1)
        link_match = link_pattern.search(block_html)
        if not link_match:
            continue

        link = _extract_real_search_url(link_match.group(1))
        title = _normalize_search_text(link_match.group(2))
        if not link or not title:
            continue

        snippet_match = snippet_pattern.search(block_html)
        snippet = _normalize_search_text(snippet_match.group(1) if snippet_match else "")
        search_results.append({"title": title, "link": link, "snippet": snippet})

    if search_results:
        return _format_search_results(search_results, "Bing")

    page_text = _normalize_search_text(page_html).lower()
    if "there are no results for" in page_text or "no results found for" in page_text:
        return ToolResult(False, None, f"No search results found for query: {query.strip()[:200]}")
    return ToolResult(False, None, "Bing search returned no parsable results.")

def _read_text_file_lines(path: str):
    encodings = ['utf-8', 'cp1251', 'cp866', 'latin-1']
    for encoding in encodings:
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.readlines(), encoding
        except UnicodeDecodeError:
            continue
    return None, None

def _normalize_search_queries(query: Any) -> List[str]:
    if isinstance(query, list):
        raw_items = query
    else:
        raw_items = re.split(r"[,;\n]", str(query or ""))
    return [str(item).strip() for item in raw_items if str(item).strip()]

def _calculate_text_similarity(query_text: str, line_text: str) -> float:
    query_norm = str(query_text or "").strip()
    line_norm = str(line_text or "").strip()
    if not query_norm or not line_norm:
        return 0.0

    if query_norm.lower() in line_norm.lower():
        return 1.0

    if FUZZY_AVAILABLE and fuzz is not None:
        try:
            scores = [
                fuzz.ratio(query_norm.lower(), line_norm.lower()) / 100.0,
                fuzz.partial_ratio(query_norm.lower(), line_norm.lower()) / 100.0,
                fuzz.token_set_ratio(query_norm.lower(), line_norm.lower()) / 100.0,
            ]
            return max(scores)
        except Exception:
            pass

    from difflib import SequenceMatcher

    line_tokens = re.findall(r"[A-Za-zА-Яа-яЁё0-9_./\\:-]+", line_norm.lower())
    token_scores = [SequenceMatcher(None, query_norm.lower(), token).ratio() for token in line_tokens]
    token_scores.append(SequenceMatcher(None, query_norm.lower(), line_norm.lower()).ratio())
    return max(token_scores) if token_scores else 0.0

def _calculate_ocr_text_similarity(query_text: str, detected_text: str) -> float:
    query_norm = str(query_text or "").strip()
    detected_norm = str(detected_text or "").strip()
    if not query_norm or not detected_norm:
        return 0.0

    query_lower = query_norm.lower()
    detected_lower = detected_norm.lower()
    if query_lower == detected_lower:
        return 1.0
    if query_lower in detected_lower:
        return 0.97

    if FUZZY_AVAILABLE and fuzz is not None:
        try:
            scores = [
                fuzz.ratio(query_lower, detected_lower) / 100.0,
                fuzz.partial_ratio(query_lower, detected_lower) / 100.0,
                fuzz.token_set_ratio(query_lower, detected_lower) / 100.0,
            ]
            return max(scores)
        except Exception:
            pass

    from difflib import SequenceMatcher
    return SequenceMatcher(None, query_lower, detected_lower).ratio()

def _map_bbox_to_screen_coordinates(bbox, screenshot_meta: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    x1 = int(min(p[0] for p in bbox))
    y1 = int(min(p[1] for p in bbox))
    x2 = int(max(p[0] for p in bbox))
    y2 = int(max(p[1] for p in bbox))

    scale_factor = float((screenshot_meta or {}).get("scale_factor") or 1.0)
    offset_x = int((screenshot_meta or {}).get("offset_x") or 0)
    offset_y = int((screenshot_meta or {}).get("offset_y") or 0)
    if scale_factor <= 0:
        scale_factor = 1.0

    real_x1 = int(round(x1 / scale_factor)) + offset_x
    real_y1 = int(round(y1 / scale_factor)) + offset_y
    real_x2 = int(round(x2 / scale_factor)) + offset_x
    real_y2 = int(round(y2 / scale_factor)) + offset_y

    return {
        "bbox_scaled": [x1, y1, x2, y2],
        "bbox_screen": [real_x1, real_y1, real_x2, real_y2],
        "center_x": (real_x1 + real_x2) // 2,
        "center_y": (real_y1 + real_y2) // 2,
    }

def _ensure_ocr_reader():

    if not OCR_AVAILABLE or easyocr is None:
        raise RuntimeError("EasyOCR is not installed. Install it with: pip install easyocr")

    if _state._ocr_reader is None:
        print(f"{Colors.CYAN}[OCR] Initializing EasyOCR (ru + en)...{Colors.RESET}")
        _state._ocr_reader = easyocr.Reader(['ru', 'en'], gpu=False, verbose=False)
        print(f"{Colors.GREEN}[OCR] Ready{Colors.RESET}")

    return _state._ocr_reader

def _take_region_screenshot(region: Optional[Dict[str, int]] = None, max_width: int = 1920,
                            max_height: int = 1080) -> Tuple[str, Dict[str, Any], Any]:
    from PIL import Image, ImageGrab
    import tempfile

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

    orig_width, orig_height = screenshot.size
    scale_factor = 1.0

    if orig_width > max_width or orig_height > max_height:
        scale_factor = min(max_width / orig_width, max_height / orig_height)
        new_width = int(orig_width * scale_factor)
        new_height = int(orig_height * scale_factor)
        screenshot = screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
        print(f"[SCREENSHOT] Scaled: {orig_width}x{orig_height} -> {new_width}x{new_height} (scale={scale_factor:.3f})")

    temp_path = os.path.join(tempfile.gettempdir(), f"screenshot_{int(time.time())}.png")
    screenshot.save(temp_path, "PNG")

    meta = {
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

    _state._last_screenshot_path = temp_path
    _state._last_screenshot_meta = dict(meta)
    return temp_path, meta, screenshot

def _extract_ocr_elements_from_screenshot(screenshot_path: str,
                                          screenshot_meta: Optional[Dict[str, Any]] = None,
                                          max_results: int = 40) -> List[Dict[str, Any]]:
    reader = _ensure_ocr_reader()
    results = reader.readtext(screenshot_path)
    if not results:
        return []

    elements = []
    for bbox, detected_text, confidence in results:
        detected_norm = _uia_normalize_text(detected_text)
        if not detected_norm:
            continue

        coords = _map_bbox_to_screen_coordinates(bbox, screenshot_meta)
        elements.append({
            "name": detected_norm,
            "control_type": "OCRText",
            "automation_id": "",
            "class_name": "ocr",
            "enabled": True,
            "visible": True,
            "bounds": {
                "left": coords["bbox_screen"][0],
                "top": coords["bbox_screen"][1],
                "right": coords["bbox_screen"][2],
                "bottom": coords["bbox_screen"][3],
                "width": int(coords["bbox_screen"][2] - coords["bbox_screen"][0]),
                "height": int(coords["bbox_screen"][3] - coords["bbox_screen"][1]),
            },
            "actions": ["observe"],
            "actionable": False,
            "identity": detected_norm,
            "ocr_confidence": round(max(0.0, min(float(confidence or 0.0), 1.0)), 3),
            "bbox_scaled": coords["bbox_scaled"],
            "bbox_screen": coords["bbox_screen"],
            "source": "ocr",
        })

    elements.sort(key=lambda item: (-item.get("ocr_confidence", 0.0), -len(item.get("name") or "")))
    return elements[:max_results]

def _screen_distance(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

def _dedupe_visual_routes(routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped = []
    seen = set()
    for route in sorted(routes, key=lambda item: item.get("confidence", 0.0), reverse=True):
        click = route.get("click_position") or {}
        key = (
            _uia_normalize_text(route.get("target", "")).lower(),
            route.get("action"),
            int((click.get("x", 0) or 0) / 16),
            int((click.get("y", 0) or 0) / 16),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(route)
    return deduped

def _detect_yellow_play_targets(screenshot_path: str,
                                screenshot_meta: Optional[Dict[str, Any]],
                                ocr_elements: List[Dict[str, Any]],
                                max_targets: int = 12) -> List[Dict[str, Any]]:
    try:
        from PIL import Image
    except ImportError:
        return []

    try:
        image = Image.open(screenshot_path).convert("RGB")
    except Exception:
        return []

    width, height = image.size
    pixels = image.load()
    visited = set()
    components = []

    def is_yellow(x: int, y: int) -> bool:
        r, g, b = pixels[x, y]
        return r >= 180 and g >= 135 and b <= 95 and (r - b) >= 90 and (g - b) >= 55

    sample_step = 3
    for y in range(0, height, sample_step):
        for x in range(0, width, sample_step):
            key = (x, y)
            if key in visited or not is_yellow(x, y):
                continue

            stack = [key]
            visited.add(key)
            xs = []
            ys = []

            while stack:
                cx, cy = stack.pop()
                xs.append(cx)
                ys.append(cy)
                for nx, ny in (
                    (cx + sample_step, cy),
                    (cx - sample_step, cy),
                    (cx, cy + sample_step),
                    (cx, cy - sample_step),
                ):
                    nkey = (nx, ny)
                    if nx < 0 or ny < 0 or nx >= width or ny >= height or nkey in visited:
                        continue
                    if is_yellow(nx, ny):
                        visited.add(nkey)
                        stack.append(nkey)

            if len(xs) < 18:
                continue

            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            comp_w = x2 - x1 + sample_step
            comp_h = y2 - y1 + sample_step
            if comp_w < 18 or comp_h < 18:
                continue
            if comp_w > width * 0.35 or comp_h > height * 0.35:
                continue

            aspect = comp_w / max(comp_h, 1)
            if aspect < 0.45 or aspect > 2.2:
                continue

            mapped = _map_bbox_to_screen_coordinates(
                [(x1, y1), (x2, y1), (x2, y2), (x1, y2)],
                screenshot_meta,
            )
            components.append({
                "center": (mapped["center_x"], mapped["center_y"]),
                "bbox_screen": mapped["bbox_screen"],
                "area": comp_w * comp_h,
                "score": min(1.0, (comp_w * comp_h) / 9000.0),
            })

    components.sort(key=lambda item: item["area"], reverse=True)
    routes = []
    for component in components[:max_targets]:
        center = component["center"]
        nearby_text = []
        for text_item in ocr_elements:
            bounds = text_item.get("bounds") or {}
            text_center = (
                int((bounds.get("left", 0) + bounds.get("right", 0)) / 2),
                int((bounds.get("top", 0) + bounds.get("bottom", 0)) / 2),
            )
            distance = _screen_distance(center, text_center)
            if distance > 520:
                continue
            nearby_text.append((distance, text_item))

        nearby_text.sort(key=lambda item: item[0])
        labels = [item.get("name") for _, item in nearby_text[:4] if item.get("name")]

        targets = ["play", "воспроизвести", "включить"]
        targets.extend(labels[:2])
        if labels:
            targets.append(" ".join(labels[:2]))

        for target in targets:
            routes.append({
                "target": target,
                "action": "click",
                "route_type": "visual_play_button",
                "click_position": {"x": center[0], "y": center[1]},
                "confidence": round(0.62 + min(component["score"], 0.28), 3),
                "evidence": {
                    "visual": "yellow play-like control",
                    "nearby_text": labels[:4],
                    "bbox_screen": component["bbox_screen"],
                },
                "source": "visual_map",
            })

    return _dedupe_visual_routes(routes)

def _build_visual_routes_from_observations(screenshot_path: Optional[str],
                                           screenshot_meta: Optional[Dict[str, Any]],
                                           ocr_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    routes = []
    if screenshot_path:
        routes.extend(_detect_yellow_play_targets(screenshot_path, screenshot_meta, ocr_elements))

    # Text observations are anchors for routes, not direct click targets.
    for item in ocr_elements:
        name = item.get("name")
        bounds = item.get("bounds") or {}
        if not name or int(bounds.get("width", 0) or 0) <= 0 or int(bounds.get("height", 0) or 0) <= 0:
            continue

        text_center_x = int((bounds.get("left", 0) + bounds.get("right", 0)) / 2)
        text_center_y = int((bounds.get("top", 0) + bounds.get("bottom", 0)) / 2)
        routes.append({
            "target": name,
            "action": "focus",
            "route_type": "text_anchor",
            "click_position": {"x": text_center_x, "y": text_center_y},
            "confidence": round(0.35 + min(float(item.get("ocr_confidence", 0.0) or 0.0), 1.0) * 0.25, 3),
            "evidence": {
                "visual": "OCR text anchor only",
                "text": name,
                "bbox_screen": item.get("bbox_screen"),
            },
            "source": "visual_map",
        })

    return _dedupe_visual_routes(routes)

def _find_best_visual_route(target: str, action: str, routes: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    target_norm = _uia_normalize_text(target)
    action_norm = str(action or "click").strip().lower()
    candidates = []

    for route in routes:
        route_action = str(route.get("action") or "click").lower()
        if route_action != action_norm:
            continue

        texts = [
            route.get("target") or "",
            " ".join(route.get("evidence", {}).get("nearby_text", []) or []),
            route.get("route_type") or "",
        ]
        score = max(_calculate_text_similarity(target_norm, text) for text in texts if text)
        if action_norm == "click" and route.get("route_type") == "visual_play_button":
            score = max(score, _calculate_text_similarity(target_norm, "play воспроизвести включить"))
        if score <= 0:
            continue

        candidates.append({
            "score": round((score * 0.78) + (float(route.get("confidence", 0.0) or 0.0) * 0.22), 3),
            "route": route,
            "match_text": route.get("target"),
        })

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return (candidates[0]["route"] if candidates else None), candidates[:5]

def _looks_like_web_app_context(context: Dict[str, Any]) -> bool:
    class_name = str(context.get("class_name") or "").lower()
    elements = context.get("elements", []) or []

    if "chrome_widgetwin" in class_name or "electron" in class_name:
        return True
    if any((item.get("class_name") or "").lower() == "chrome_renderwidgethosthwnd" for item in elements):
        return True
    return False

