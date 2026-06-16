"""Qwen agent implementation."""
import base64
import contextlib
import getpass
import inspect
import io
import json
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from jarvis_core.colors import Colors
from jarvis_core.types import ToolResult
from jarvis_memory.manager import MemoryManager
from jarvis_tools.definitions import TOOLS_DEFINITION, TOOLS_MAP
from jarvis_ui.animation import AnimationManager
from jarvis_ui.console import UI


class QwenAgent:
    """Агент с поддержкой инструментов"""

    def __init__(self, base_url: str = "http://localhost:8080", app=None):
        self.base_url = base_url
        self.api_url = f"{base_url}/v1/chat/completions"
        self.messages: List[Dict[str, Any]] = []
        self.max_iterations = 45
        self.system_prompt = self._build_system_prompt()
        self.app = app  # Ссылка на QwenAgentApp для управления флагами
        self.enabled_tools: Optional[List[str]] = None
        self.interactive_prompts = bool(getattr(app, "interactive_prompts", True))
        self.last_exact_context_tokens: Optional[int] = None
        self.last_exact_context_source: Optional[str] = None
        self.last_active_file_path: Optional[str] = None
        self._stop_requested = threading.Event()
        self._active_stream_response = None
        self._stream_response_lock = threading.Lock()
        self.reset_history()

    def request_stop(self):
        self._stop_requested.set()
        with self._stream_response_lock:
            if self._active_stream_response is not None:
                try:
                    self._active_stream_response.close()
                except Exception:
                    pass

    def set_enabled_tools(self, enabled_tools: Optional[List[str]]) -> None:
        self.enabled_tools = enabled_tools

    def get_active_tools_definition(self) -> List[Dict[str, Any]]:
        if self.enabled_tools is None:
            return TOOLS_DEFINITION
        enabled_set = set(self.enabled_tools)
        return [tool for tool in TOOLS_DEFINITION if tool["function"]["name"] in enabled_set]

    def clear_stop_request(self):
        self._stop_requested.clear()

    def stop_requested(self) -> bool:
        return self._stop_requested.is_set()

    def _set_active_stream_response(self, response):
        with self._stream_response_lock:
            self._active_stream_response = response

    def _clear_active_stream_response(self, response=None):
        with self._stream_response_lock:
            if response is None or self._active_stream_response is response:
                self._active_stream_response = None

    def _build_system_prompt(self) -> str:
        """Build system prompt with user memory context"""
        memory_context = MemoryManager.get_context_for_prompt()

        # Динамические системные пути (без хардкода конкретного пользователя)
        windows_username = getpass.getuser()
        home_path = str(Path.home())
        # Для Markdown экранируем обратные слэши
        home_path_md = home_path.replace("\\", "\\\\")
        desktop_path_md = os.path.join(home_path, "Desktop").replace("\\", "\\\\")
        projects_path_md = os.path.join(home_path, "PycharmProjects").replace("\\", "\\\\")

        # Base prompt (shortened)
        base_prompt = f"""You are Jarvis (Friday). A local AI assistant on Windows with access to tools.

## 🎩 STYLE
- Address the user as **"Sir"** (1-2 times per response)
- Tone: polite, professional, concise

## 🏷️ !STT
If the message starts with **!STT** — it's voice input (may contain errors). Ignore the label, try to understand the meaning.

## 📱 !PH
If the message starts with **!PH** — the user is on a **phone via Telegram**.
- Respond **briefly**, no tables or ASCII art
- No visual elements (dividers, frames)
- Only text and emojis
- Avoid long lists and complex formatting

## 📎 SYSTEM PATH
Your Windows username is **{windows_username}**.
When writing file paths, ALWAYS use: `{home_path_md}`.
Avoid using non-ASCII characters in Windows paths.
Desktop path: `{desktop_path_md}`
Your projects: `{projects_path_md}`

## ⛔ FORBIDDEN
**NEVER use `run_python` to output answers!** Only for calculations. Write final responses directly to chat.

## 🧠 MEMORY
"""

        # Memory block
        if memory_context:
            memory_block = f"""{memory_context}
**Important:** This information is already in context — do NOT call manage_memory to retrieve it.
"""
        else:
            memory_block = "Memory is empty.\n"

        # Tools prompt (shortened)
        tools_prompt = """
## 🎯 PRIORITIES
✅ **run_cmd commands** — reliable and fast:
- Open a site: `run_cmd(command="start https://youtube.com")`
- Open a file: `run_cmd(command="start notepad.exe \"C:\\path\\to\\file.txt\"")`
- Open a folder: `run_cmd(command="explorer \"C:\\Users\\Public\"")`
- Close an app: `run_cmd(command="taskkill /F /IM app.exe")`
- Files: `dir`, `copy`, `del`, `move`, `mkdir`
- System: `systeminfo`, `tasklist`

✅ **For Windows desktop app control, UI Automation is the PRIMARY path**
- First use: `launch_app(app_name)` if the app is not open
- Then use: `get_app_context()`
- Then use: `do_action_in_app(target, action, text)`
- Reuse `get_app_context()` after actions when you need updated state
- Do NOT start with screenshots for ordinary desktop app interaction if UI Automation can be used
- For Chromium/Electron/web-app windows, `get_app_context()` may include OCR observations and derived visual app-map routes when native controls are hidden
- For Chromium/Electron/web-app windows, `do_action_in_app()` must use UIA elements or app-map routes; OCR text alone is not a button

## 👁️ VL (VISION-LANGUAGE) APPROACH
📸 **Screenshots** — use mainly for visual inspection, validation, or when UI Automation does not expose the needed control
📝 **click_text(text)** — last-resort emergency fallback only. Prefer app-map routes built by `get_app_context()`.

## 🔧 TOOLS

1. **search_web(query)** — Search via DuckDuckGo HTML
2. **read_url(url)** — Extract text from page
3. **run_cmd(command)** — Windows shell command with auto-detection (PowerShell/CMD)
4. **run_python(code)** — Python code (calculations ONLY!)
5. **read_file(path)** — Read file
6. **read_code(path, start_line, end_line)** — Read code smartly (by line range or symbols). ALWAYS pass the full file path.
7. **check_syntax(path)** — Check file syntax via compilation. Supports: Python, JS/TS, JSON, HTML/XML, YAML, CSS/SCSS, Shell, Markdown. ALWAYS pass the full file path and ALWAYS use after editing code!
8. **edit_code(path, line, new_code, mode, end_line, expected_old_code)** — Edit PART of a file. `path` is ALWAYS required. Use `expected_old_code` for replace/delete to avoid stale line-number mistakes.
9. **write_file(path, content)** — Write file (ONLY for new files/full rewrites!)
10. **list_directory(path)** — List directory contents
11. **take_screenshot(region)** — Take screenshot (full screen or region)
12. **click_text(text, threshold)** — Click on text via OCR (uses last screenshot from take_screenshot)
13. **type_text(text)** — Type text via keyboard
14. **get_cursor_position()** — Get cursor coordinates
15. **press_key(key)** — Press a key
16. **hotkey(keys)** — Key combination
17. **launch_app(app_name)** — Launch an application
18. **get_app_context(refresh, max_elements)** — Inspect the active app window via UI Automation and update the cached app map
19. **do_action_in_app(target, action, text)** — Find a UI element in the active app and act on it
20. **manage_memory(operation, content)** — Memory: read/write/append/clear
21. **wait(seconds)** — Wait N seconds (0.1-300)
22. **telegram_account_info()** — Summary of connected Telegram account (name, dialogs, unread)
23. **telegram_get_chats(limit)** — List Telegram dialogs/chats/groups
24. **telegram_get_unread(limit)** — Fetch unread Telegram messages across dialogs
25. **telegram_send_message(entity, text)** — Send a message to a Telegram chat
26. **telegram_join_chat(link_or_username)** — Join a public Telegram channel/group
27. **telegram_request_join(invite_link)** — Request to join a private Telegram group
28. **telegram_global_search(query, limit)** — Global search across Telegram messages
29. **telegram_get_messages(entity, limit)** — Read messages in a specific Telegram chat
30. **ask_user(question, timeout)** — Ask the user a question and wait for an answer (modal UI)

Call format: `{"tool": "name", "args": {...}}`

## 💡 VL EXAMPLES
- Inspect desktop app: `get_app_context()` → `do_action_in_app(target="Settings", action="click")`
- Inspect Chromium app: `get_app_context()` → inspect `Visual app-map routes` in summary → `do_action_in_app(target="Моя волна", action="click")`
- Visual verification only: `take_screenshot()` after an action to confirm the result

## 📱 TELEGRAM ACCOUNT
- The user can connect their personal Telegram account in Settings → Telegram account.
- Use **telegram_account_info()** first to verify the account is connected.
- Use **telegram_get_chats()** and **telegram_get_unread()** to show dialogs/unread messages.
- Use **telegram_send_message(entity, text)** to send messages. **ALWAYS call ask_user() before sending** unless the user explicitly asked to send this exact message.
- Use **telegram_join_chat()** for public groups/channels, **telegram_request_join()** for private invite links.
- Use **telegram_global_search(query)** to search across all Telegram messages.
- Use **telegram_get_messages(entity)** to read the latest messages in a chat.
- If the user asks to perform a sensitive/irreversible action, call **ask_user(question)** for confirmation.

## 📋 ALGORITHM
1. If this is a Windows desktop app task: **launch_app()** if needed → **get_app_context()** → **do_action_in_app(...)**
2. Use **take_screenshot()** only for visual analysis, verification, or if UI Automation failed
3. For web-app shells, rely on the visual app-map routes returned by **get_app_context()**
4. Use **click_text(text)** only as a final emergency fallback after UIA and app-map routes failed
5. Check results → if enough info, **respond immediately**

## ⚠️ RULES
- **One tool at a time** | Max **45 iterations**
- For Windows desktop apps, **always try `get_app_context()` and `do_action_in_app()` before screenshots or OCR**
- **Do not use `click_text()` or screenshot-driven clicking as the first choice** for standard desktop app controls
- For web-app shells inside desktop windows, use `get_app_context()` because it builds app-map routes from OCR observations and visual controls
- OCR observations are not buttons. Actions must go through UIA elements or `Visual app-map routes`.
- **Use screenshots primarily to read information from the screen**, inspect visual state, or verify a result
- Use **click_text()** only if UI Automation and app-map routes failed, the target control is not exposed, or the task is purely visual
- The model receives a screenshot scaled to **1920x1080** — coordinates will be in this range
- Check results | If enough info — **respond immediately**
- Respond in the user's language
- To get the current time, always use a powershell command

## 💻 CODING RULES (CRITICAL!)
❌ **NEVER rewrite the entire file!** Use **edit_code** to change only affected parts
✅ **ALWAYS read the file first** with read_code, then use **edit_code** with specific line numbers
✅ When you call **read_code**, **edit_code**, **check_syntax**, **read_file**, **list_file**, or **search_text_in_file**, ALWAYS include the same full `path` again in every tool call — never omit `path` even if the file was just read in the previous step
✅ For **replace/delete**, pass `expected_old_code` copied from `read_code` so the tool can verify the target block before editing
✅ After editing, ALWAYS verify with **check_syntax(path)**:
   - For Python: `check_syntax(path="C:/path/file.py")` — checks via ast compilation
   - For JSON/HTML/JS/TS/etc: `check_syntax(path="file")` — validates syntax
   - If errors found → fix with edit_code and check_syntax again
✅ Only use write_file for completely new files or when user explicitly asks for full rewrite
❌ Never use write_file for small changes — wastes tokens and crashes server
✅ edit_code modes: replace (change lines), insert_before/insert_after (add lines), delete (remove lines — new_code NOT needed!)
✅ Prefer `replace` over insert+delete chains when modifying an existing block

⚠️ **CRITICAL: edit_code with mode="replace" MUST include new_code!**
⚠️ **CRITICAL: edit_code MUST include path!**
   Example of CORRECT call:
   ```
   {
     "path": "C:/path/file.py",
     "line": 23,
     "end_line": 23,
     "mode": "replace",
     "new_code": "pygame.display.set_caption('Змейка')"
   }
   ```
   ❌ WRONG: calling edit_code without new_code (the tool will FAIL)
   ❌ WRONG: calling edit_code without path (the tool will FAIL)
   ✅ RIGHT: ALWAYS include new_code — it's the actual code you want to put in the file!
   ✅ RIGHT: ALWAYS copy the full file path from the previous read_code/read_file result into edit_code/check_syntax

   If you already know what to replace (e.g. "pymgame" → "pygame"), you MUST put the corrected text in new_code — don't just call the tool with line numbers!

## 🎯 QUICK EXAMPLES
- "AI news?" → `search_web("AI 2026")`
- "https://..." → `read_url(url)`
- "Files" → `list_directory(path)`
- "Open Chrome" → `run_cmd("start https://chrome.com")`
- "Open file on desktop" → `run_cmd("start notepad.exe \"C:\\Users\\<username>\\Desktop\\file.txt\"")`
- "Open Documents folder" → `run_cmd("explorer \"C:\\Users\\<username>\\Documents\"")`
- "Close Notepad" → `run_cmd("taskkill /F /IM notepad.exe")`
- "Remember name" → `manage_memory("append", "name...")`
- "Click Close button" → `take_screenshot()` → `click_text("Close")`


## 💡 IMPORTANT
- You are an **agent** — you choose tools yourself
- Don't guess — **use a tool**
- 🎯 For desktop apps, **start with `get_app_context`**, not screenshots
- 🖱️ Use **do_action_in_app** as the default way to press buttons, open tabs, choose list items, and focus inputs
- 🌐 For Chromium/Electron-style apps, rely on **get_app_context** and **do_action_in_app** first; they use OCR only to build visual routes
- 📸 Use screenshots when you need visual information, visual confirmation, or UI Automation is unavailable
- 📝 **click_text** is a fallback tool, not the default desktop interaction tool
- 🚀 Sites/apps: `run_cmd("start ...")` — fast and reliable
- 🗑️ Closing: `taskkill` is more reliable than GUI
- ❗ ALL tool error messages and explanations MUST be in English — never respond with Russian error details
- When you see a tool error, summarize the issue in English and retry with corrected arguments
"""

        return base_prompt + memory_block + tools_prompt

    def reset_history(self):
        """Сбросить историю чата"""
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.last_active_file_path = None

    def refresh_system_prompt(self):
        """
        Обновить системный промпт с актуальной памятью.
        Вызывается после изменения памяти через manage_memory.
        """
        self.system_prompt = self._build_system_prompt()

        # Обновляем системное сообщение в истории если оно есть
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = self.system_prompt

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    def _extract_token_count_from_tokenize_response(self, data: Any) -> Optional[int]:
        if isinstance(data, dict):
            tokens = data.get("tokens")
            if isinstance(tokens, list):
                return len(tokens)

            for key in ("n_tokens", "count", "token_count"):
                value = self._safe_int(data.get(key))
                if value is not None and value >= 0:
                    return value

        if isinstance(data, list):
            return len(data)

        return None

    @staticmethod
    def _tool_uses_file_path(tool_name: str) -> bool:
        return tool_name in {
            "read_file",
            "search_text_in_file",
            "write_file",
            "read_code",
            "edit_code",
            "list_file",
            "check_syntax",
        }

    def _resolve_missing_tool_path(self, tool_name: str, args: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
        if not isinstance(args, dict):
            return {}, None

        normalized_args = dict(args)
        current_path = normalized_args.get("path")
        if isinstance(current_path, str) and current_path.strip():
            return normalized_args, None

        if self._tool_uses_file_path(tool_name) and self.last_active_file_path:
            normalized_args["path"] = self.last_active_file_path
            return normalized_args, self.last_active_file_path

        return normalized_args, None

    def _remember_tool_file_path(self, tool_name: str, args: Dict[str, Any], result: Optional[ToolResult] = None):
        if not self._tool_uses_file_path(tool_name):
            return

        candidate = None
        if isinstance(args, dict):
            raw_path = args.get("path")
            if isinstance(raw_path, str) and raw_path.strip():
                candidate = raw_path.strip()

        if not candidate and isinstance(result, ToolResult) and isinstance(result.data, dict):
            raw_path = result.data.get("path")
            if isinstance(raw_path, str) and raw_path.strip():
                candidate = raw_path.strip()

        if not candidate:
            return

        try:
            if os.path.isdir(candidate):
                return
        except Exception:
            return

        self.last_active_file_path = candidate

    def _update_exact_context_from_timings(self, timings: Any) -> Optional[int]:
        if not isinstance(timings, dict):
            return None

        prompt_n = self._safe_int(timings.get("prompt_n"))
        cache_n = self._safe_int(timings.get("cache_n"))
        predicted_n = self._safe_int(timings.get("predicted_n"))

        if prompt_n is None and cache_n is None and predicted_n is None:
            return None

        total = max(prompt_n or 0, 0) + max(cache_n or 0, 0) + max(predicted_n or 0, 0)
        self.last_exact_context_tokens = total
        self.last_exact_context_source = "server_timings"
        return total

    def get_exact_context_usage(self) -> Optional[Dict[str, Any]]:
        """
        Попытаться получить честный размер текущего контекста через llama-server.
        Приоритет:
        1. apply-template + tokenize по текущей истории
        2. точные timings последнего ответа сервера
        """
        template_payload: Dict[str, Any] = {
            "messages": self._build_server_safe_messages(),
            "add_generation_prompt": True,
        }

        template_variants = [
            {**template_payload, "tools": self.get_active_tools_definition()},
            template_payload,
        ]

        for payload in template_variants:
            try:
                template_response = requests.post(
                    f"{self.base_url}/apply-template",
                    json=payload,
                    timeout=4,
                )
                template_response.raise_for_status()
                template_data = template_response.json()
                prompt = template_data.get("prompt", "") if isinstance(template_data, dict) else ""
                if not isinstance(prompt, str) or not prompt:
                    continue

                tokenize_response = requests.post(
                    f"{self.base_url}/tokenize",
                    json={"content": prompt},
                    timeout=4,
                )
                tokenize_response.raise_for_status()
                token_count = self._extract_token_count_from_tokenize_response(tokenize_response.json())
                if token_count is not None:
                    source = "server_apply_template_tokenize_with_tools" if "tools" in payload else "server_apply_template_tokenize"
                    self.last_exact_context_tokens = token_count
                    self.last_exact_context_source = source
                    return {"used": token_count, "source": source}
            except Exception:
                continue

        if self.last_exact_context_tokens is not None:
            return {
                "used": self.last_exact_context_tokens,
                "source": self.last_exact_context_source or "server_timings",
            }

        return None

    def _estimate_tokens(self, text: str) -> int:
        """
        Приблизительная оценка количества токенов в тексте.
        Для русского/английского текста: ~4 символа на токен.
        """
        return len(text) // 4

    def _trim_screenshots(self, max_screenshots: int = 2):
        """
        Оставить только последние N сообщений со скриншотами в истории чата.

        Удаляет старые сообщения с изображениями (image_url) из self.messages,
        сохраняя только последние max_screenshots.

        Args:
            max_screenshots: Максимальное количество скриншотов для хранения (по умолчанию 2)
        """
        if len(self.messages) <= 1:
            return

        # Находим все сообщения с изображениями
        screenshot_indices = []

        for i, msg in enumerate(self.messages[1:], 1):  # Пропускаем системный промпт
            content = msg.get("content", "")

            # Проверяем, есть ли в сообщении изображение
            if isinstance(content, list):
                has_image = any(
                    isinstance(item, dict) and
                    item.get("type") == "image_url" and
                    "image_url" in item
                    for item in content
                )
                if has_image:
                    screenshot_indices.append(i)

        # Если скриншотов больше чем max_screenshots — удаляем старые
        if len(screenshot_indices) > max_screenshots:
            # Индексы для удаления (все кроме последних max_screenshots)
            indices_to_remove = screenshot_indices[:-max_screenshots]

            # Сначала удаляем временные файлы скриншотов
            for i in indices_to_remove:
                msg = self.messages[i]
                content = msg.get("content", "")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and "image_url" in item:
                            try:
                                img_url = item["image_url"].get("url", "")
                                if img_url.startswith("data:"):
                                    # Это base64 data URL — файл не удаляем через URL
                                    # Путь к файлу может быть сохранён в "file_path"
                                    file_path = item.get("file_path")
                                    if file_path and os.path.exists(file_path):
                                        os.remove(file_path)
                            except Exception as e:
                                print(f"{Colors.DIM}[SCREENSHOT] Ошибка удаления {file_path}: {e}{Colors.RESET}")

            # Создаём новую историю без старых скриншотов
            new_messages = [msg for i, msg in enumerate(self.messages) if i not in indices_to_remove]

            self.messages = new_messages
            print(
                f"{Colors.DIM}[SCREENSHOT] Удалено {len(indices_to_remove)} старых скриншотов, "
                f"оставлено {max_screenshots}{Colors.RESET}")

    def _trim_history(self, max_tokens: int = 14000):
        """
        Обрезать историю чата, чтобы уместиться в лимит контекста.
        Сохраняет системный промпт и последние сообщения.

        Args:
            max_tokens: Максимальное количество токенов для истории
        """
        if len(self.messages) <= 1:
            return

        # Считаем токены в системном промпте
        system_tokens = self._estimate_tokens(self.messages[0]["content"])

        # Считаем токены с конца (от новых к старым), пока не достигнем лимита
        tokens_so_far = system_tokens
        messages_to_keep = []

        # Идём с конца (от последнего сообщения к началу)
        for msg in reversed(self.messages[1:]):
            content = msg.get("content", "")
            if isinstance(content, str):
                msg_tokens = self._estimate_tokens(content)
            elif isinstance(content, list):
                msg_tokens = 0
                for item in content:
                    if isinstance(item, dict) and "text" in item:
                        msg_tokens += self._estimate_tokens(item["text"])
            else:
                msg_tokens = self._estimate_tokens(str(content))

            # Если добавление этого сообщения превысит лимит — останавливаемся
            if tokens_so_far + msg_tokens > max_tokens:
                break

            tokens_so_far += msg_tokens
            messages_to_keep.append(msg)

        # Если все сообщения помещаются — ничего не делаем
        if len(messages_to_keep) == len(self.messages) - 1:
            return

        # Переворачиваем обратно (от старых к новым) и добавляем системный промпт
        messages_to_keep.reverse()
        self.messages = [self.messages[0]] + messages_to_keep

        print(
            f"{Colors.DIM}[ИСТОРИЯ] Обрезано до {len(self.messages)} сообщений (~{tokens_so_far} токенов){Colors.RESET}")

    def _normalize_trailing_assistant_messages(self):
        """
        Нормализовать хвост истории перед API-запросом.
        Некоторые модели/агентные сценарии могут оставить несколько assistant-сообщений подряд
        в конце списка, что ломает OpenAI-совместимый chat completions API.
        """
        if len(self.messages) <= 2:
            return

        trailing_indexes: List[int] = []
        for idx in range(len(self.messages) - 1, 0, -1):
            msg = self.messages[idx]
            if msg.get("role") != "assistant":
                break
            if msg.get("tool_calls"):
                break
            if not isinstance(msg.get("content"), str):
                break
            trailing_indexes.append(idx)

        if len(trailing_indexes) <= 1:
            return

        trailing_indexes.reverse()
        merged_parts = []
        for idx in trailing_indexes:
            content = str(self.messages[idx].get("content", "")).strip()
            if content:
                merged_parts.append(content)

        merged_content = "\n\n".join(merged_parts)
        first_idx = trailing_indexes[0]
        self.messages[first_idx] = {"role": "assistant", "content": merged_content}

        for idx in reversed(trailing_indexes[1:]):
            del self.messages[idx]

    @staticmethod
    def _coerce_text_part_for_content(value: Any) -> Dict[str, str]:
        return {"type": "text", "text": str(value)}

    def _merge_assistant_content(self, left: Any, right: Any) -> Any:
        if left in (None, ""):
            return right
        if right in (None, ""):
            return left

        if isinstance(left, str) and isinstance(right, str):
            return f"{left.rstrip()}\n\n{right.lstrip()}".strip()

        if isinstance(left, list) and isinstance(right, list):
            return left + right

        if isinstance(left, list):
            return left + [self._coerce_text_part_for_content(right)]

        if isinstance(right, list):
            return [self._coerce_text_part_for_content(left)] + right

        return f"{left}\n\n{right}"

    def _build_server_safe_messages(self, messages: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Схлопывает подряд идущие assistant-сообщения в одно сообщение,
        чтобы OpenAI-совместимый сервер не падал на истории с промежуточными ответами.
        """
        source_messages = messages if messages is not None else self.messages
        safe_messages: List[Dict[str, Any]] = []

        for original in source_messages:
            msg = dict(original)

            if (
                safe_messages
                and msg.get("role") == "assistant"
                and safe_messages[-1].get("role") == "assistant"
            ):
                previous = dict(safe_messages[-1])
                merged_tool_calls = list(previous.get("tool_calls") or [])
                merged_tool_calls.extend(list(msg.get("tool_calls") or []))

                previous["content"] = self._merge_assistant_content(
                    previous.get("content"),
                    msg.get("content"),
                )

                if merged_tool_calls:
                    previous["tool_calls"] = merged_tool_calls
                else:
                    previous.pop("tool_calls", None)

                safe_messages[-1] = previous
                continue

            safe_messages.append(msg)

        return safe_messages

    def check_health(self) -> bool:
        """Проверить доступность сервера"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False

    def encode_image(self, path: str) -> Optional[str]:
        """Кодировать изображение в base64"""
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            print(f"{Colors.RED}Ошибка чтения изображения: {e}{Colors.RESET}")
            return None

    def get_mime_type(self, path: str) -> str:
        """Определить MIME-тип"""
        ext = os.path.splitext(path)[1].lower()
        mime_types = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png', '.gif': 'image/gif',
            '.webp': 'image/webp', '.bmp': 'image/bmp'
        }
        return mime_types.get(ext, 'image/jpeg')

    def execute_tool(self, tool_name: str, args: Dict) -> ToolResult:
        """Выполнить инструмент"""
        if tool_name not in TOOLS_MAP:
            return ToolResult(False, None, f"Инструмент '{tool_name}' не найден")

        tool_func = TOOLS_MAP[tool_name]
        try:
            args, auto_filled_path = self._resolve_missing_tool_path(tool_name, args)

            # Проверяем наличие обязательных аргументов перед вызовом
            sig = inspect.signature(tool_func)
            required_params = {
                name for name, param in sig.parameters.items()
                if param.default == inspect.Parameter.empty
            }
            missing = required_params - set(args.keys())
            if missing:
                extra_hint = ""
                if "path" in missing and self._tool_uses_file_path(tool_name):
                    if self.last_active_file_path:
                        extra_hint = (
                            f" Reuse the same file path from the previous code tool call: "
                            f"path='{self.last_active_file_path}'."
                        )
                    else:
                        extra_hint = (
                            " Add the full file path explicitly, for example: "
                            "path='C:\\Users\\<username>\\Desktop\\snake_game.py'."
                        )
                return ToolResult(
                    False, None,
                    f"Error: tool '{tool_name}' requires arguments: {', '.join(sorted(missing))}. "
                    f"Specify them correctly. Signature: {inspect.signature(tool_func)}{extra_hint}"
                )

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            # Инструменты не должны писать напрямую в консоль, иначе они
            # конфликтуют с фоновой анимацией выполнения.
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                if args:
                    result = tool_func(**args)
                else:
                    result = tool_func()

            captured_stdout = stdout_buffer.getvalue().strip()
            captured_stderr = stderr_buffer.getvalue().strip()

            if isinstance(result, ToolResult) and (captured_stdout or captured_stderr):
                if isinstance(result.data, dict):
                    result.data = dict(result.data)
                    if captured_stdout:
                        result.data["console_stdout"] = captured_stdout[:2000]
                    if captured_stderr:
                        result.data["console_stderr"] = captured_stderr[:1000]
                elif result.data is None:
                    result.data = {}
                    if captured_stdout:
                        result.data["console_stdout"] = captured_stdout[:2000]
                    if captured_stderr:
                        result.data["console_stderr"] = captured_stderr[:1000]

            if isinstance(result, ToolResult):
                if auto_filled_path:
                    if isinstance(result.data, dict):
                        result.data = dict(result.data)
                        result.data.setdefault("path", auto_filled_path)
                        result.data["path_auto_filled"] = auto_filled_path
                    elif result.data is None:
                        result.data = {
                            "path": auto_filled_path,
                            "path_auto_filled": auto_filled_path
                        }
                if result.success:
                    self._remember_tool_file_path(tool_name, args, result)

            return result
        except TypeError as te:
            # TypeError usually означает неправильные аргументы
            sig = inspect.signature(tool_func)
            example_sig = ", ".join([f"{k}='...'" for k in sig.parameters.keys()])
            return ToolResult(
                False, None,
                f"Error: wrong arguments for '{tool_name}': {str(te)}. "
                f"Call the tool again with correct arguments. "
                f"Signature: {tool_name}({example_sig})"
            )
        except Exception as e:
            return ToolResult(False, None, f"Execution error: {str(e)}")

    def execute_tool_with_animation(self, tool_name: str, args: Dict,
                                    hidden_count: int = 0) -> ToolResult:
        """
        Выполнить инструмент в worker-thread, пока основной поток крутит анимацию.
        Это устойчивее, чем держать анимацию в фоне рядом с синхронным инструментом.
        """
        result_box = {
            "result": None,
            "error": None
        }

        def _worker():
            try:
                result_box["result"] = self.execute_tool(tool_name, args)
            except Exception as e:
                result_box["error"] = e

        worker = threading.Thread(target=_worker, daemon=True)
        AnimationManager.start(mode="tool", label=f"Выполняется: {tool_name}", initial_count=hidden_count)
        worker.start()

        try:
            while worker.is_alive():
                AnimationManager.tick()
                worker.join(timeout=0.12)
        finally:
            AnimationManager.stop()

        if result_box["error"] is not None:
            return ToolResult(False, None, f"Execution error: {str(result_box['error'])}")

        result = result_box["result"]
        if isinstance(result, ToolResult):
            return result
        return ToolResult(False, None, f"Execution error: tool '{tool_name}' returned invalid result")

    def parse_tool_call(self, content: str) -> Optional[Dict]:
        """Распарсить вызов инструмента из ответа"""
        if not content:
            return None

        decoder = json.JSONDecoder()

        # Сначала пробуем fenced code blocks целиком
        fenced_patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
        ]

        for pattern in fenced_patterns:
            for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
                candidate = (match.group(1) or "").strip()
                if not candidate:
                    continue
                try:
                    data = json.loads(candidate)
                except json.JSONDecodeError:
                    continue

                if isinstance(data, dict) and "tool" in data:
                    return {
                        "tool": data.get("tool"),
                        "args": data.get("args", {})
                    }

        # Затем ищем любой корректный JSON-объект в тексте через raw_decode.
        # Это устойчиво к вложенным args: {"tool":"x","args":{"a":1}}
        for match in re.finditer(r'\{', content):
            start = match.start()
            try:
                data, end = decoder.raw_decode(content[start:])
            except json.JSONDecodeError:
                continue

            if not isinstance(data, dict) or "tool" not in data:
                continue

            return {
                "tool": data.get("tool"),
                "args": data.get("args", {})
            }
        return None

    def parse_xml_tool_calls(self, content: str) -> List[Dict]:
        tool_calls = []

        # Паттерн для <function=name>...</function>
        pattern = r'<function=(\w+)>(.*?)</function>'

        for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
            tool_name = match.group(1)
            inner = match.group(2).strip()

            # Пробуем распарсить как JSON
            try:
                args = json.loads(inner)
                tool_calls.append({
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args)
                    }
                })
                continue
            except json.JSONDecodeError:
                pass

            # Пробуем распарсить <parameter=name>value</parameter>
            args = {}
            param_pattern = r'<parameter=(\w+)>(.*?)</parameter>'
            for p_match in re.finditer(param_pattern, inner, re.DOTALL):
                param_name = p_match.group(1)
                param_value = p_match.group(2).strip()
                args[param_name] = param_value

            if args:
                tool_calls.append({
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args)
                    }
                })

        return tool_calls

    @staticmethod
    def _extract_text_value(value: Any) -> str:
        """Извлечь текст из разных форматов чанков стриминга."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    if isinstance(item.get("text"), str):
                        parts.append(item["text"])
                    elif item.get("type") == "text" and isinstance(item.get("content"), str):
                        parts.append(item["content"])
            return "".join(parts)
        if isinstance(value, dict):
            if isinstance(value.get("text"), str):
                return value["text"]
            if isinstance(value.get("content"), str):
                return value["content"]
        return ""

    def _parse_streaming_response(self, response, show_thinking: bool = True,
                                  stop_event: Optional[threading.Event] = None) -> Dict[str, Any]:
        """Разобрать SSE-стрим от совместимого chat completions API."""
        assistant_state = None
        thinking_state = None
        thinking_buffer = []
        streamed_tool_calls: Dict[int, Dict[str, Any]] = {}
        streamed_tool_call_counts: Dict[int, int] = {}
        thinking_finished = False
        waiting_spinner_active = AnimationManager.is_running()
        latest_timings: Optional[Dict[str, Any]] = None

        # Декодируем байты в строки явно через UTF-8
        line_iterator = response.iter_lines()
        while True:
            if stop_event is not None and stop_event.is_set():
                response.close()
                break

            try:
                raw_line = next(line_iterator)
            except StopIteration:
                break
            except Exception:
                if stop_event is not None and stop_event.is_set():
                    try:
                        response.close()
                    except Exception:
                        pass
                    break
                raise

            if not raw_line:
                continue

            # Декодируем байты в строку с кодировкой UTF-8
            try:
                line = raw_line.decode('utf-8').strip()
            except UnicodeDecodeError:
                # Fallback на другие кодировки
                try:
                    line = raw_line.decode('cp1251').strip()
                except:
                    continue

            if not line.startswith("data:"):
                continue

            data_str = line[5:].strip()
            if not data_str:
                continue
            if data_str == "[DONE]":
                break

            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if isinstance(event.get("timings"), dict):
                latest_timings = event.get("timings")

            choice = (event.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}

            if waiting_spinner_active:
                AnimationManager.stop_bg()
                AnimationManager.start(mode="generating", label="Jarvis генерирует ответ")
                waiting_spinner_active = False

            reasoning_delta = self._extract_text_value(
                delta.get("reasoning_content") or delta.get("reasoning")
            )
            if reasoning_delta:
                thinking_buffer.append(reasoning_delta)
                # Выводим мышление потоково, если ещё не начали вывод ответа
                if not thinking_finished and show_thinking:
                    if thinking_state is None:
                        thinking_state = UI.start_streaming_thinking()
                    UI.update_streaming_thinking(thinking_state, reasoning_delta)

            content_delta = self._extract_text_value(delta.get("content"))
            if content_delta:
                # Если пришло содержимое ответа — завершаем вывод мышления
                if thinking_buffer and not thinking_finished and show_thinking:
                    thinking_finished = True
                    if thinking_state:
                        UI.finish_streaming_thinking(thinking_state)
                    else:
                        # Если мышление было, но не началось — выводим сразу
                        UI.print_streaming_thinking_block("".join(thinking_buffer))

                if assistant_state is None:
                    assistant_state = UI.start_streaming_response("Ответ")
                UI.update_streaming_response(assistant_state, content_delta)

            for tc_delta in delta.get("tool_calls", []) or []:
                idx = tc_delta.get("index", len(streamed_tool_calls))
                streamed_tool_call_counts.setdefault(idx, 0)
                tool_call = streamed_tool_calls.setdefault(idx, {
                    "id": tc_delta.get("id", f"call_{idx}"),
                    "type": tc_delta.get("type", "function"),
                    "function": {
                        "name": "",
                        "arguments": ""
                    }
                })

                if tc_delta.get("id"):
                    tool_call["id"] = tc_delta["id"]
                    streamed_tool_call_counts[idx] += len(tc_delta["id"])

                function_delta = tc_delta.get("function", {})
                if function_delta.get("name"):
                    name_part = function_delta["name"]
                    tool_call["function"]["name"] += name_part
                    streamed_tool_call_counts[idx] += len(name_part)
                if function_delta.get("arguments"):
                    args_part = function_delta["arguments"]
                    tool_call["function"]["arguments"] += args_part
                    streamed_tool_call_counts[idx] += len(args_part)

        # Завершаем вывод мышления если оно ещё не завершено
        if thinking_buffer and not thinking_finished and show_thinking:
            if thinking_state:
                UI.finish_streaming_thinking(thinking_state)
            else:
                UI.print_streaming_thinking_block("".join(thinking_buffer))

        return {
            "content": UI.finish_streaming_response(assistant_state).strip() if assistant_state else "",
            "reasoning_content": "".join(thinking_buffer).strip(),
            "tool_calls": [
                {
                    **streamed_tool_calls[i],
                    "_hidden_count": streamed_tool_call_counts.get(i, 0)
                }
                for i in sorted(streamed_tool_calls)
            ],
            "timings": latest_timings,
        }

    @staticmethod
    def _is_native_tool_args_parse_error(error: requests.exceptions.HTTPError) -> bool:
        response = getattr(error, "response", None)
        if response is None:
            return False

        try:
            body = response.text or ""
        except Exception:
            body = ""

        if not body:
            return False

        body_lower = body.lower()
        return (
            "failed to parse tool call arguments as json" in body_lower
            or "missing closing quote" in body_lower
            or "parse error at line" in body_lower
        )

    def _send_completion_request(
        self,
        payload: Dict[str, Any],
        stream: bool,
        show_thinking: bool,
        allow_native_tool_retry: bool = True,
        stop_event: Optional[threading.Event] = None
    ) -> tuple[str, str, List[Dict[str, Any]]]:
        response = requests.post(
            self.api_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
            stream=stream
        )
        if stream:
            self._set_active_stream_response(response)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            if allow_native_tool_retry and self._is_native_tool_args_parse_error(error):
                UI.print_status(
                    "Сервер вернул битый native tool_call. Повторяю запрос в безопасном режиме...",
                    "warning"
                )
                return self._retry_completion_without_native_tools(
                    stream=stream,
                    show_thinking=show_thinking,
                    stop_event=stop_event
                )
            raise

        response.encoding = 'utf-8'

        try:
            if stream:
                parsed = self._parse_streaming_response(
                    response,
                    show_thinking=show_thinking,
                    stop_event=stop_event
                )
                self._update_exact_context_from_timings(parsed.get("timings"))
                return (
                    parsed.get("content", ""),
                    parsed.get("reasoning_content", ""),
                    parsed.get("tool_calls", []),
                )

            data = response.json()
            self._update_exact_context_from_timings(data.get("timings"))
            message = data.get("choices", [{}])[0].get("message", {})
            return (
                message.get("content", ""),
                message.get("reasoning_content", ""),
                message.get("tool_calls", []),
            )
        finally:
            if stream:
                self._clear_active_stream_response(response)

    def _retry_completion_without_native_tools(
        self,
        stream: bool,
        show_thinking: bool,
        stop_event: Optional[threading.Event] = None
    ) -> tuple[str, str, List[Dict[str, Any]]]:
        retry_messages = self._build_server_safe_messages()
        retry_messages.append({
            "role": "system",
            "content": (
                "The previous native tool call failed because the tool arguments JSON was malformed. "
                "Do not emit native tool_calls in this reply. "
                "If you need a tool, output exactly one textual tool call in one of these formats:\n"
                "<function=tool_name>{\"arg\":\"value\"}</function>\n"
                "or\n"
                "<function=tool_name><parameter=arg>value</parameter></function>\n"
                "For write_file, preserve the full content verbatim inside the content parameter, including newlines and quotes. "
                "If no tool is needed, answer normally."
            )
        })

        retry_payload = {
            "messages": retry_messages,
            "max_tokens": 10000,
            "temperature": 0.3,
            "stream": stream,
        }

        response = requests.post(
            self.api_url,
            json=retry_payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
            stream=stream
        )
        if stream:
            self._set_active_stream_response(response)
        response.raise_for_status()
        response.encoding = 'utf-8'

        try:
            if stream:
                parsed = self._parse_streaming_response(
                    response,
                    show_thinking=show_thinking,
                    stop_event=stop_event
                )
                assistant_content = parsed.get("content", "")
                reasoning_content = parsed.get("reasoning_content", "")
            else:
                data = response.json()
                message = data.get("choices", [{}])[0].get("message", {})
                assistant_content = message.get("content", "")
                reasoning_content = message.get("reasoning_content", "")
        finally:
            if stream:
                self._clear_active_stream_response(response)

        tool_calls = []
        if reasoning_content:
            tool_calls = self.parse_xml_tool_calls(reasoning_content)
        if not tool_calls and assistant_content:
            tool_calls = self.parse_xml_tool_calls(assistant_content)
        if not tool_calls:
            parsed_json_call = self.parse_tool_call(assistant_content) or self.parse_tool_call(reasoning_content)
            if parsed_json_call:
                tool_calls = [{
                    "function": {
                        "name": parsed_json_call.get("tool", ""),
                        "arguments": json.dumps(parsed_json_call.get("args", {}), ensure_ascii=False)
                    }
                }]

        return assistant_content, reasoning_content, tool_calls

    def send_message(self, content: str, image_path: Optional[str] = None,
                     stream: bool = True, show_thinking: bool = True,
                     image_urls: Optional[List[str]] = None):
        """Отправить сообщение агенту"""
        self.clear_stop_request()

        # Формируем контент
        user_content = []
        if content:
            user_content.append({"type": "text", "text": content})

        if image_path and os.path.exists(image_path):
            base64_image = self.encode_image(image_path)
            if base64_image:
                mime_type = self.get_mime_type(image_path)
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}
                })

        if image_urls:
            for image_url in image_urls:
                if isinstance(image_url, str) and image_url.startswith("data:image/"):
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": image_url}
                    })

        # Добавляем в историю
        if len(user_content) == 1 and "text" in user_content[0]:
            self.messages.append({"role": "user", "content": content})
        else:
            self.messages.append({"role": "user", "content": user_content})

        # Обрезаем старые скриншоты (оставляем только последние 2)
        self._trim_screenshots(max_screenshots=2)

        # Обрезаем историю если превышает лимит контекста
        # Обрезаем историю с запасом под новый запрос (сервер 18K, обрезаем до 16K)
        self._trim_history(max_tokens=16000)

        # Агентский цикл
        iteration = 0
        tool_calls_history = []
        last_visible_content = ""
        stopped_by_user = False

        while iteration < self.max_iterations:
            if self.stop_requested():
                stopped_by_user = True
                break

            iteration += 1
            UI.print_agent_status(iteration, self.max_iterations)
            self._normalize_trailing_assistant_messages()

            # Параметры запроса
            payload = {
                "messages": self._build_server_safe_messages(),
                "max_tokens": 10000,
                "temperature": 0.7,
                "stream": stream,
                "tools": self.get_active_tools_definition(),
                "tool_choice": "auto"
            }

            try:
                if stream:
                    AnimationManager.start_bg(mode="generating", label="Jarvis думает")
                else:
                    AnimationManager.start(mode="generating", label="Jarvis генерирует ответ")
                assistant_content, reasoning_content, tool_calls = self._send_completion_request(
                    payload,
                    stream=stream,
                    show_thinking=show_thinking,
                    allow_native_tool_retry=True,
                    stop_event=self._stop_requested
                )
                if assistant_content and assistant_content.strip():
                    last_visible_content = assistant_content.strip()

                AnimationManager.stop()

                if self.stop_requested():
                    stopped_by_user = True
                    break

                # Вывод мышления уже был выполнен потоково в _parse_streaming_response
                # Для не-streaming режима выводим мышление здесь
                if not stream and show_thinking and reasoning_content:
                    UI.print_streaming_thinking_block(reasoning_content)

                # Если нет нативных tool_calls, ищем вызовы инструментов в reasoning_content (XML формат)
                if not tool_calls and reasoning_content:
                    tool_calls = self.parse_xml_tool_calls(reasoning_content)
                if not tool_calls and assistant_content:
                    tool_calls = self.parse_xml_tool_calls(assistant_content)

                if tool_calls:
                    # Модель хочет вызвать инструмент — запускаем анимацию инструмента до результата
                    for tool_index, tc in enumerate(tool_calls):
                        func = tc.get("function", {})
                        tool_name = func.get("name", "")
                        args_str = func.get("arguments", "{}")
                        tool_call_id = tc.get("id") or f"call_{iteration}_{tool_index}"

                        try:
                            args = json.loads(args_str)
                        except json.JSONDecodeError:
                            args = {}

                        # Показываем вызов инструмента и запускаем постоянную анимацию
                        tool_stop_event = UI.print_tool_call(tool_name, args, iteration)
                        hidden_count = tc.get("_hidden_count", 0)

                        # Выполняем инструмент в worker-thread, а анимацию держим в главном потоке
                        result = self.execute_tool_with_animation(tool_name, args, hidden_count=hidden_count)
                        UI.print_tool_result(tool_name, result, iteration, tool_stop_event)

                        if self.stop_requested():
                            stopped_by_user = True

                        # Если это manage_memory с операцией write/append/clear — обновляем промпт
                        if tool_name == "manage_memory" and result.success:
                            op = args.get("operation", "")
                            if op in ["write", "append", "clear"]:
                                self.refresh_system_prompt()

                        # Специальная обработка для take_screenshot — отправляем изображение модели
                        screenshot_base64 = None
                        if tool_name == "take_screenshot" and result.success and isinstance(result.data, dict):
                            img_path = result.data.get("path")
                            if img_path and os.path.exists(img_path):
                                screenshot_base64 = self.encode_image(img_path)

                        # Добавляем в историю
                        tool_calls_history.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": args_str
                                }
                            }]
                        })

                        tool_calls_history.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps(result.to_dict(), ensure_ascii=False) if isinstance(result.data,
                                                                                                      dict) else str(
                                result.data)
                        })

                        # Если это скриншот — добавляем отдельное user-сообщение с изображением для анализа
                        if screenshot_base64:
                            mime_type = self.get_mime_type(img_path)
                            tool_calls_history.append({
                                "role": "user",
                                "content": [
                                    {"type": "text",
                                     "text": f"Скриншот сделан. Размеры: {result.data.get('width')}x{result.data.get('height')}. Проанализируй изображение:"},
                                    {"type": "image_url",
                                     "image_url": {"url": f"data:{mime_type};base64,{screenshot_base64}"},
                                     "file_path": img_path}
                                ]
                            })

                        if stopped_by_user:
                            break

                    # Обновляем сообщения для следующего запроса
                    if stopped_by_user:
                        break
                    self.messages.extend(tool_calls_history)
                    tool_calls_history = []
                    continue

                # Проверяем JSON в тексте (fallback режим)
                tool_call = self.parse_tool_call(assistant_content)
                if tool_call:
                    tool_name = tool_call.get("tool", "")
                    args = tool_call.get("args", {})
                    tool_call_id = f"call_{iteration}_fallback"
                    args_str = json.dumps(args, ensure_ascii=False)

                    # Показываем вызов инструмента и запускаем постоянную анимацию
                    tool_stop_event = UI.print_tool_call(tool_name, args, iteration)

                    # Выполняем инструмент в worker-thread, а анимацию держим в главном потоке
                    result = self.execute_tool_with_animation(tool_name, args, hidden_count=0)
                    UI.print_tool_result(tool_name, result, iteration, tool_stop_event)

                    if self.stop_requested():
                        stopped_by_user = True

                    # Если это manage_memory с операцией write/append/clear — обновляем промпт
                    if tool_name == "manage_memory" and result.success:
                        op = args.get("operation", "")
                        if op in ["write", "append", "clear"]:
                            self.refresh_system_prompt()

                    # Добавляем вызов и результат в историю в совместимом tool-calls формате
                    self.messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": args_str
                            }
                        }]
                    })
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": json.dumps(result.to_dict(), ensure_ascii=False) if isinstance(result.data, dict) else str(result.data)
                    })

                    # Специальная обработка для take_screenshot — отправляем изображение модели
                    if tool_name == "take_screenshot" and result.success and isinstance(result.data, dict):
                        img_path = result.data.get("path")
                        if img_path and os.path.exists(img_path):
                            screenshot_base64 = self.encode_image(img_path)
                            if screenshot_base64:
                                mime_type = self.get_mime_type(img_path)
                                # Добавляем изображение как user-сообщение с content в формате image_url
                                self.messages.append({
                                    "role": "user",
                                    "content": [
                                        {"type": "text",
                                         "text": f"Скриншот сделан. Размеры: {result.data.get('width')}x{result.data.get('height')}. Проанализируй изображение:"},
                                        {"type": "image_url",
                                         "image_url": {"url": f"data:{mime_type};base64,{screenshot_base64}"},
                                         "file_path": img_path}
                                    ]
                                })
                            else:
                                self.messages.append({
                                    "role": "user",
                                    "content": f"Результат {tool_name}: {json.dumps(result.to_dict(), ensure_ascii=False)}"
                                })
                        else:
                            self.messages.append({
                                "role": "user",
                                "content": f"Результат {tool_name}: {json.dumps(result.to_dict(), ensure_ascii=False)}"
                            })
                    else:
                        self.messages.append({
                            "role": "user",
                            "content": f"Результат {tool_name}: {json.dumps(result.to_dict(), ensure_ascii=False) if isinstance(result.data, dict) else str(result.data)}"
                        })
                    if stopped_by_user:
                        break
                    continue

                # Если нет tool_calls — это финальный ответ
                # Если assistant_content пустой, используем reasoning_content (мысли) как финальный ответ
                final_content = assistant_content.strip() if assistant_content else ""
                if not final_content and reasoning_content:
                    # Модель написала ответ в мыслях, а не в финальном ответе
                    final_content = reasoning_content.strip()

                self.messages.append({"role": "assistant", "content": final_content})

                self.clear_stop_request()
                yield {
                    "type": "final",
                    "content": final_content,
                    "iterations": iteration
                }
                return

            except requests.exceptions.ConnectionError:
                AnimationManager.stop()
                self.clear_stop_request()
                raise ConnectionError(f"Не удалось подключиться к серверу {self.base_url}")
            except requests.exceptions.Timeout:
                AnimationManager.stop()
                self.clear_stop_request()
                raise TimeoutError("Превышено время ожидания")
            except requests.exceptions.HTTPError as e:
                AnimationManager.stop()
                self.clear_stop_request()
                raise RuntimeError(f"HTTP ошибка: {e.response.status_code}")
            except Exception as e:
                AnimationManager.stop()
                self.clear_stop_request()
                raise

        self.clear_stop_request()

        if stopped_by_user:
            if last_visible_content:
                self.messages.append({"role": "assistant", "content": last_visible_content})
            yield {
                "type": "final",
                "content": last_visible_content,
                "iterations": iteration
            }
            return

        # Достигнут лимит итераций: завершаем молча, без дополнительной ошибки
        yield {
            "type": "final",
            "content": last_visible_content,
            "iterations": iteration
        }

