"""Web search and URL reading tools.

URL reading intentionally uses a regular browser context for pages that need
JavaScript.  It does not try to defeat CAPTCHA or access-control challenges;
those are reported clearly so the model can use search results or ask for a
different source.
"""
import html
import re
import time
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from jarvis_core.types import ToolResult

from .utils import (
    _augment_web_error_message,
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


def search_web(query: str) -> ToolResult:
    """Search the web through several providers."""
    try:
        providers = [
            ("duckduckgo", lambda: _search_with_duckduckgo_html(query)),
            ("google", lambda: _search_with_google_playwright(query)),
            ("bing", lambda: _search_with_bing(query)),
        ]
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
                return result

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
