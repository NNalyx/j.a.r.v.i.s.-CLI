"""Web search and URL reading tools."""
import time
from typing import Optional

from jarvis_core.types import ToolResult

from .utils import (
    _augment_web_error_message,
    _search_with_bing,
    _search_with_duckduckgo_html,
    _search_with_google_playwright,
)


def search_web(query: str) -> ToolResult:
    """Поиск информации в интернете через DuckDuckGo HTML"""
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

def read_url(url: str) -> ToolResult:
    """Извлечь текст со страницы по URL (Playwright)"""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )

            page = browser.new_page()

            # Маскируем автоматизацию
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            # Устанавливаем заголовки
            page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            try:
                # Переходим на страницу
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Ждем загрузки основного контента
                time.sleep(1)

                # Извлекаем заголовок страницы
                title = page.title()

                # Извлекаем весь видимый текст со страницы
                text = page.inner_text('body')

                # Пытаемся извлечь только основной контент
                main_content = ""
                main_elems = page.query_selector_all('main, article, .content, #content, #main')

                if main_elems:
                    main_content = "\n".join(
                        [elem.inner_text() for elem in main_elems if elem.inner_text().strip()])

                # Используем основной контент если есть, иначе весь текст
                final_text = main_content if main_content.strip() else text

                browser.close()

                return ToolResult(True, {
                    'title': title,
                    'text': final_text[:4000],
                    'url': url
                })

            except Exception as e:
                browser.close()
                return ToolResult(False, None, _augment_web_error_message(f"Page load error: {str(e)}", url=url))

    except ImportError:
        return ToolResult(False, None, "Playwright not installed. Run: pip install playwright")
    except Exception as e:
        return ToolResult(False, None, _augment_web_error_message(f"Error: {str(e)}", url=url))

