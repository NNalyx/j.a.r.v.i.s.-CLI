"""Web search and URL reading tools.

URL reading intentionally uses a regular browser context for pages that need
JavaScript.  It does not try to defeat CAPTCHA or access-control challenges;
those are reported clearly so the model can use search results or ask for a
different source.
"""
import html
import re
import time
from difflib import SequenceMatcher
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from jarvis_core.types import ToolResult

from .utils import (
    _augment_web_error_message,
    _format_search_results,
    _search_with_bing,
    _search_with_duckduckgo_html,
    _search_with_google_playwright,
)


_MAX_TEXT_CHARS = 4000
_REQUEST_TIMEOUT = (8, 20)
_BROWSER_TIMEOUT_MS = 35_000
_CHALLENGE_MARKERS = (
    "verify you are human",
    "checking your browser",
    "enable javascript and cookies",
    "captcha",
    "access denied",
    "cf-chl-",
)
_COMMON_NOISE = (
    "script, style, noscript, svg, canvas, nav, footer, aside, form, "
    "[aria-modal='true'], [role='dialog'], [role='navigation'], "
    ".cookie, .cookies, .consent, .modal, .popup"
)

_WEATHER_INTENT = re.compile(r"\b(?:погод\w*|прогноз\w*|weather|forecast)\b", re.IGNORECASE)
_WEATHER_WORDS = re.compile(
    r"\b(?:погод\w*|прогноз\w*|weather|forecast|сегодня|завтра|сейчас|на|день|неделю|"
    r"today|tomorrow|now|current|tonight|in|for|at|the|в|во|для)\b",
    re.IGNORECASE,
)
_SEARCH_STOP_WORDS = {
    "the", "and", "for", "with", "from", "what", "when", "where", "who", "how", "why",
    "today", "tomorrow", "now", "current", "latest", "search", "find", "web", "internet",
    "это", "как", "что", "где", "когда", "почему", "найди", "поиск", "интернет",
    "пожалуйста", "сегодня", "завтра", "сейчас", "какой", "какая", "какие", "прогноз",
    "погода", "weather", "forecast",
}
_SEARCH_INTENT_ROOTS = {"погод", "прогноз", "weather", "forecast"}
_WMO_WEATHER_CODES = {
    0: "ясно", 1: "преимущественно ясно", 2: "переменная облачность", 3: "пасмурно",
    45: "туман", 48: "изморозевый туман", 51: "слабая морось", 53: "морось",
    55: "сильная морось", 56: "слабая ледяная морось", 57: "сильная ледяная морось",
    61: "слабый дождь", 63: "дождь", 65: "сильный дождь", 66: "слабый ледяной дождь",
    67: "сильный ледяной дождь", 71: "слабый снег", 73: "снег", 75: "сильный снег",
    77: "снежные зёрна", 80: "слабые ливни", 81: "ливни", 82: "сильные ливни",
    85: "слабый снегопад", 86: "сильный снегопад", 95: "гроза", 96: "гроза с градом",
    99: "сильная гроза с градом",
}


def _weather_query_location(query: str) -> str:
    place = _WEATHER_WORDS.sub(" ", str(query or ""))
    place = re.sub(r"\b(?:в|во|для|на|in|for|at)\b", " ", place, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", re.sub(r"[^\w, -]", " ", place, flags=re.UNICODE)).strip(" ,-_")


def _search_weather(query: str) -> ToolResult:
    """Return live weather for an explicitly named place instead of geo-biased SERP links."""
    location_query = _weather_query_location(query)
    if not location_query:
        return ToolResult(False, None, "Укажи город для погодного запроса — местоположение по VPN не используется.")

    session = requests.Session()
    try:
        query_parts = [
            _search_term_root(part)
            for part in re.findall(r"[\w-]+", location_query.lower(), flags=re.UNICODE)
            if len(part) >= 3
        ]

        def location_score(candidate: Dict[str, Any]) -> float:
            candidate_parts = [
                _search_term_root(part)
                for field in ("name", "admin1", "admin2", "country")
                for part in re.findall(r"[\w-]+", str(candidate.get(field) or "").lower(), flags=re.UNICODE)
                if len(part) >= 3
            ]
            if not query_parts or not candidate_parts:
                return 0.0
            lexical = sum(
                max(SequenceMatcher(None, wanted, actual).ratio() for actual in candidate_parts)
                for wanted in query_parts
            ) / len(query_parts)
            city_bonus = 0.05 if candidate.get("feature_code") == "PPLC" else 0.0
            return lexical + city_bonus

        def lookup(name: str) -> List[Dict[str, Any]]:
            response = session.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": name, "count": 10, "language": "ru", "format": "json"},
                headers={"User-Agent": "Jarvis/1.0 (weather lookup)"},
                timeout=(3, 6),
            )
            response.raise_for_status()
            return (response.json() or {}).get("results") or []

        locations = lookup(location_query)
        place = max(locations, key=location_score) if locations else None
        # Geocoding's prefix matching can mistake declined Russian city names
        # (e.g. «Москве») for unrelated names. Retry the stem to find «Москва».
        if not place or location_score(place) < 0.95:
            words = location_query.split()
            if words and re.search(r"[а-яё]", words[-1], re.IGNORECASE):
                for suffix in ("ого", "ему", "ами", "ями", "ой", "ом", "е", "ы", "у", "и", "ю"):
                    word = words[-1]
                    if len(word) > len(suffix) + 2 and word.lower().endswith(suffix):
                        stem_query = " ".join(words[:-1] + [word[:-len(suffix)]])
                        if stem_query.lower() != location_query.lower():
                            retry_locations = lookup(stem_query)
                            if retry_locations:
                                retry_place = max(retry_locations, key=location_score)
                                if not place or location_score(retry_place) > location_score(place):
                                    place = retry_place
                            if place and location_score(place) >= 0.95:
                                break

        if not place:
            return ToolResult(False, None, f"Не удалось найти город «{location_query}» для погодного запроса.")
        if location_score(place) < 0.55:
            return ToolResult(False, None, f"Не удалось однозначно сопоставить место «{location_query}».")
        timezone = place.get("timezone") or "UTC"
        forecast_response = session.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
                "timezone": timezone,
                "forecast_days": 1,
            },
            headers={"User-Agent": "Jarvis/1.0 (weather lookup)"},
            timeout=(3, 6),
        )
        forecast_response.raise_for_status()
        forecast = forecast_response.json()
        current = forecast.get("current") or {}
        daily = forecast.get("daily") or {}
        date = current.get("time", "").split("T", 1)[0]
        condition = _WMO_WEATHER_CODES.get(current.get("weather_code"), "условия не определены")
        label = ", ".join(dict.fromkeys(filter(None, [place.get("name"), place.get("admin1"), place.get("country")])))
        parts = [
            f"Погода — {label}, {date} (местное время {timezone}):",
            f"Сейчас: {condition}, {current.get('temperature_2m', '—')} °C",
            f"ощущается как {current.get('apparent_temperature', '—')} °C",
            f"ветер {current.get('wind_speed_10m', '—')} км/ч",
            f"влажность {current.get('relative_humidity_2m', '—')}%",
            f"осадки {current.get('precipitation', '—')} мм.",
        ]
        if daily.get("temperature_2m_min"):
            parts.append(
                f"За день: {daily['temperature_2m_min'][0]}…{daily['temperature_2m_max'][0]} °C, "
                f"вероятность осадков до {daily.get('precipitation_probability_max', ['—'])[0]}%."
            )
        summary = " ".join(parts)
        link = (
            "https://open-meteo.com/en/docs?"
            f"latitude={place['latitude']}&longitude={place['longitude']}&timezone={timezone}"
        )
        return ToolResult(True, {
            "provider": "Open-Meteo",
            "results": [{"title": f"Погода: {label}", "link": link, "snippet": summary}],
            "weather": {"location": place, "current": current, "daily": daily, "timezone": timezone},
            "formatted": summary + f"\nИсточник: {link}",
        })
    except (requests.RequestException, ValueError, KeyError) as error:
        return ToolResult(False, None, f"Не удалось получить погоду для «{location_query}»: {error}")


def _search_term_root(term: str) -> str:
    value = term.lower()
    for suffix in (
        "иями", "ями", "ами", "ого", "ему", "ыми", "ими", "ать", "ять", "ение", "ения",
        "ов", "ев", "ом", "ем", "ам", "ям", "ах", "ях", "ой", "ей", "ую", "юю",
        "ое", "ее", "ая", "яя", "ые", "ие", "ый", "ий", "а", "я", "ы", "и", "е", "у", "ю", "s",
    ):
        if len(value) > 4 and value.endswith(suffix):
            return value[:-len(suffix)]
    return value


def _filter_search_results(query: str, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    terms = []
    for word in re.findall(r"[\w-]+", query.lower(), flags=re.UNICODE):
        root = _search_term_root(word)
        if len(word) >= 3 and word not in _SEARCH_STOP_WORDS and root not in _SEARCH_INTENT_ROOTS:
            terms.append(root)
    if not terms:
        return []

    minimum_matches = 2 if len(terms) >= 3 else 1
    scored = []
    seen = set()
    for result in results:
        title = str(result.get("title") or "").lower()
        snippet = str(result.get("snippet") or "").lower()
        url = str(result.get("link") or "").lower()
        matched = sum(any(term in field for field in (title, snippet, url)) for term in terms)
        if matched < minimum_matches:
            continue
        key = url.split("#", 1)[0].rstrip("/")
        if not key or key in seen:
            continue
        seen.add(key)
        scored.append((matched / len(terms), result))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [result for _score, result in scored[:10]]


def search_web(query: str) -> ToolResult:
    """Return fast, query-matched results; use a location-aware endpoint for weather."""
    try:
        query = str(query or "").strip()
        if not query:
            return ToolResult(False, None, "Search query is empty.")

        started = time.perf_counter()
        if _WEATHER_INTENT.search(query):
            result = _search_weather(query)
            if result.success and isinstance(result.data, dict):
                result.data["search_seconds"] = round(time.perf_counter() - started, 2)
            return result

        # Bing RSS is usually the fastest provider; validate it before returning.
        providers = [("Bing RSS", lambda: _search_with_bing(query))]
        providers.append(("duckduckgo", lambda: _search_with_duckduckgo_html(query)))
        try:
            import importlib.util
            if importlib.util.find_spec("playwright") is not None:
                providers.append(("google", lambda: _search_with_google_playwright(query)))
        except (ImportError, ValueError):
            pass

        provider_errors = []
        saw_explicit_no_results = False

        for provider_name, provider_fn in providers:
            try:
                result = provider_fn()
            except ImportError:
                provider_errors.append(f"{provider_name}: Playwright not installed")
                continue
            except Exception as e:
                provider_errors.append(f"{provider_name}: {_augment_web_error_message(str(e))}")
                continue

            if result.success:
                result_data = result.data if isinstance(result.data, dict) else {}
                matched = _filter_search_results(query, result_data.get("results") or [])
                if matched:
                    accepted = _format_search_results(matched, result_data.get("provider", provider_name))
                    accepted.data["search_seconds"] = round(time.perf_counter() - started, 2)
                    return accepted
                provider_errors.append(f"{provider_name}: results did not match the query; discarded")
                continue

            error_text = str(result.error or "").strip()
            if error_text:
                provider_errors.append(f"{provider_name}: {error_text}")
                if error_text.startswith("No search results found for query:"):
                    saw_explicit_no_results = True

        if saw_explicit_no_results:
            return ToolResult(False, None, f"No search results found for query: {query.strip()[:200]}")

        return ToolResult(False, None, "All search providers failed.\n" + "\n".join(f"- {item}" for item in provider_errors[:6]))
    except Exception as e:
        return ToolResult(False, None, _augment_web_error_message(f"Search error: {str(e)}"))


class _HTMLTextParser(HTMLParser):
    """Small dependency-free text extractor for the HTTP fallback."""

    _ignored = {"script", "style", "noscript", "svg", "canvas", "nav", "footer", "form"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag.lower() in self._ignored:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._ignored and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            value = re.sub(r"\s+", " ", html.unescape(data)).strip()
            if value:
                self.parts.append(value)


def _clean_text(value: str) -> str:
    lines = []
    previous = ""
    for line in re.split(r"\n+", value or ""):
        line = re.sub(r"[ \t\u00a0]+", " ", line).strip()
        if not line or line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines)


def _looks_like_access_challenge(text: str) -> bool:
    sample = (text or "").lower()
    return any(marker in sample for marker in _CHALLENGE_MARKERS)


def _normalise_url(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        raise ValueError("URL is empty")
    if not urlparse(value).scheme:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only http:// and https:// URLs are supported")
    return value


def _extract_browser_text(page: Any) -> str:
    """Extract the densest meaningful content, avoiding page chrome."""
    return _clean_text(page.locator("body").inner_text(timeout=5))


def _wait_for_content(page: Any) -> None:
    # Some SPAs render after load.  Wait for a useful body and stop once its
    # text length is stable, keeping the delay bounded for fast pages.
    page.locator("body").wait_for(state="visible", timeout=10_000)
    last_length = -1
    stable_rounds = 0
    for _ in range(6):
        time.sleep(0.45)
        current_length = len(_extract_browser_text(page))
        if current_length == last_length and current_length > 80:
            stable_rounds += 1
            if stable_rounds >= 2:
                break
        else:
            stable_rounds = 0
        last_length = current_length


def _read_with_browser(url: str) -> Dict[str, str]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = browser.new_context(
            locale="en-US",
            viewport={"width": 1365, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=_BROWSER_TIMEOUT_MS)
            try:
                page.wait_for_load_state("networkidle", timeout=8_000)
            except Exception:
                # Long-polling pages never become network-idle; DOM text is
                # still usable after the bounded wait above.
                pass
            _wait_for_content(page)

            # Remove common chrome only after loading, so consent UI cannot
            # dominate the extracted text.  This is content cleanup, not a
            # challenge bypass.
            page.evaluate(
                """(selector) => document.querySelectorAll(selector).forEach((node) => node.remove())""",
                _COMMON_NOISE,
            )
            candidates = []
            for selector in ("article", "main", "[role='main']", ".article", ".post-content", "body"):
                for element in page.locator(selector).all():
                    try:
                        text = _clean_text(element.inner_text(timeout=2))
                    except Exception:
                        continue
                    if len(text) >= 120:
                        candidates.append(text)
            text = max(candidates, key=lambda item: (len(item), item.count("\n")), default=_extract_browser_text(page))
            title = _clean_text(page.title())
            final_url = page.url
            status = response.status if response else None
            if _looks_like_access_challenge(text) and len(text) < 1200:
                raise RuntimeError("site requires an interactive access verification")
            if status and status >= 400 and len(text) < 200:
                raise RuntimeError(f"HTTP {status}")
            return {"title": title, "text": text, "url": final_url}
        finally:
            context.close()
            browser.close()


def _read_with_http(url: str) -> Dict[str, str]:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; JARVIS/1.0; +https://localhost)"},
        timeout=_REQUEST_TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()
    parser = _HTMLTextParser()
    parser.feed(response.text)
    text = _clean_text("\n".join(parser.parts))
    title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text, flags=re.I | re.S)
    title = _clean_text(html.unescape(title_match.group(1))) if title_match else ""
    return {"title": title, "text": text, "url": response.url}


def read_url(url: str) -> ToolResult:
    """Read a URL with JS rendering first and a lightweight HTTP fallback."""
    try:
        target = _normalise_url(url)
    except ValueError as e:
        return ToolResult(False, None, f"Invalid URL: {e}")

    browser_error: Optional[str] = None
    try:
        payload = _read_with_browser(target)
    except ImportError:
        browser_error = "Playwright is not installed"
    except Exception as e:
        browser_error = str(e)

    if browser_error:
        try:
            payload = _read_with_http(target)
        except Exception as http_error:
            message = _augment_web_error_message(
                f"Page could not be read: browser={browser_error}; http={http_error}", url=target
            )
            if any(token in browser_error.lower() for token in ("captcha", "challenge", "access denied", "forbidden")):
                message += " The site appears to require an interactive verification step; use another source or open it in a normal browser."
            return ToolResult(False, None, message)

    text = payload.get("text", "")
    if len(text) < 80:
        return ToolResult(
            False,
            None,
            "The page returned too little readable text (possibly JS-only or access-restricted).",
        )
    if _looks_like_access_challenge(text) and len(text) < 1200:
        return ToolResult(
            False,
            None,
            "The site requires an interactive access verification (CAPTCHA/anti-bot challenge). Use SearchWeb or another source.",
        )

    return ToolResult(True, {
        "title": payload.get("title", ""),
        "text": text[:_MAX_TEXT_CHARS],
        "url": payload.get("url", target),
    })
