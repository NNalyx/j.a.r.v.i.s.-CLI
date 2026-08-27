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
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from jarvis_core.colors import Colors
from jarvis_core.types import ToolResult
from jarvis_memory.manager import MemoryManager
from jarvis_tools.definitions import TOOLS_DEFINITION, TOOLS_MAP
from jarvis_tools.background import background_tasks_context
from jarvis_ui.animation import AnimationManager
from jarvis_ui.console import UI


IS_MACOS = sys.platform == "darwin"

# Размер чанка для SSE-стрима. requests по умолчанию читает по 512 байт,
# что создаёт огромное количество системных вызовов read() и замедляет
# получение токенов на быстрых серверах.
STREAM_CHUNK_SIZE = 65536


class QwenAgent:
    """Агент с поддержкой инструментов"""

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        app=None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        top_p: float = 0.9,
        min_p: float = 0.05,
        repeat_penalty: float = 1.15,
        frequency_penalty: float = 0.1,
        presence_penalty: float = 0.1,
        penalty_last_n: int = 512,
        context_size: int = 32768,
        backend: str = "llama-server",
        system_prompt_mode: str = "full",
    ):
        self.base_url = base_url
        self.api_url = f"{base_url}/v1/chat/completions"
        self.messages: List[Dict[str, Any]] = []
        self.max_iterations = 0
        self.system_prompt_mode = str(system_prompt_mode).strip().lower()
        if self.system_prompt_mode not in {"full", "minimal", "none"}:
            self.system_prompt_mode = "full"
        self.system_prompt = self._build_system_prompt()
        self.app = app  # Ссылка на QwenAgentApp для управления флагами
        self.enabled_tools: Optional[List[str]] = None
        self.interactive_prompts = bool(getattr(app, "interactive_prompts", True))
        self.last_exact_context_tokens: Optional[int] = None
        self.last_exact_context_source: Optional[str] = None
        self.last_exact_context_fingerprint: Optional[str] = None
        self.last_active_file_path: Optional[str] = None
        self._stop_requested = threading.Event()
        self._active_stream_response = None
        self._stream_response_lock = threading.Lock()
        self.last_generation_timings: Optional[Dict[str, Any]] = None
        # Generation hyperparameters loaded from the active preset.
        self.max_tokens = int(max_tokens) if max_tokens and int(max_tokens) > 0 else 8192
        self.context_size = int(context_size) if context_size and int(context_size) > 0 else 32768
        self.temperature = float(temperature)
        self.top_p = float(top_p)
        self.min_p = float(min_p)
        self.repeat_penalty = float(repeat_penalty)
        self.frequency_penalty = float(frequency_penalty)
        self.presence_penalty = float(presence_penalty)
        self.penalty_last_n = int(penalty_last_n)
        self.backend = str(backend).lower().strip() if backend else "llama-server"
        # Some MLX-based servers struggle with native tool_calls (constrained/grammar
        # decoding) and heavy sampler penalties. Default to XML tool calls for them.
        self.native_tools_enabled = self.backend not in {"mlx-vlm", "mlx-optiq", "mtplx"}
        # Отслеживание неудачных вызовов инструментов в текущем ходе
        self._failed_tool_attempts: List[Tuple[str, str]] = []
        # Защита от зацикливания: счётчики повторов и история видимого текста
        self._tool_attempt_counts: Dict[str, int] = {}
        self._recent_tool_fingerprints: deque = deque(maxlen=12)
        self._visible_content_history: deque = deque(maxlen=6)
        # Активный план задачи — создаётся агентом и подкладывается в каждый запрос
        self.active_plan: Optional[Dict[str, Any]] = None
        # Рабочая директория для команд и фоновых задач
        self.working_directory: Optional[str] = None
        self.reset_history()

    def _is_mlx_like_backend(self) -> bool:
        return self.backend in {"mlx-vlm", "mlx-optiq", "mtplx"}

    def _prepare_payload_for_backend(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Apply backend-specific payload adjustments.

        MLX/OptiQ/MTPLX servers often implement native tool_calls through slow
        Python-side constrained decoding and apply penalties as per-token Python
        loops. For those backends we fall back to XML tool calls (already supported
        by the parser) and drop the penalty-heavy sampler params unless the user
        explicitly asked for them via the preset. Llama-server keeps full native
        tool support and penalties.
        """
        adjusted = dict(payload)
        if self._is_mlx_like_backend():
            # Remove native tool schema to avoid grammar/constrained decoding.
            adjusted.pop("tools", None)
            adjusted.pop("tool_choice", None)
            # Remove sampler penalties that are known to be slow on MLX Python servers.
            # Temperature/top_p/min_p are kept because they are vectorized.
            for key in ("repeat_penalty", "frequency_penalty", "presence_penalty", "penalty_last_n"):
                adjusted.pop(key, None)
        return adjusted

    def _log_request(self, payload: Dict[str, Any], tag: str = "request") -> None:
        """Log the actual payload and timings for debugging speed issues."""
        try:
            log_dir = Path(__file__).resolve().parent.parent / "jarvis_logs"
            log_dir.mkdir(exist_ok=True)
            log_path = log_dir / "last_llm_request.json"
            # Strip huge base64 images from the logged copy.
            clean = self._strip_image_data_from_payload(payload)
            entry = {
                "tag": tag,
                "backend": self.backend,
                "api_url": self.api_url,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "payload": clean,
                "native_tools_enabled": self.native_tools_enabled,
            }
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _log_timings(self, timings: Dict[str, Any], tag: str = "timings") -> None:
        """Log final generation timings for post-hoc speed debugging."""
        try:
            log_dir = Path(__file__).resolve().parent.parent / "jarvis_logs"
            log_dir.mkdir(exist_ok=True)
            log_path = log_dir / "last_llm_timings.json"
            entry = {
                "tag": tag,
                "backend": self.backend,
                "api_url": self.api_url,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "timings": timings,
            }
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _perf_log(self, event: str, data: Dict[str, Any]) -> None:
        """Append a high-resolution performance trace event to a JSONL file.

        Used to diagnose where time is spent between the LLM server emitting
        a token and the user seeing it in the UI.
        """
        try:
            log_dir = Path(__file__).resolve().parent.parent / "jarvis_logs"
            log_dir.mkdir(exist_ok=True)
            log_path = log_dir / "perf_trace.jsonl"
            entry = {
                "ts": time.time(),
                "event": event,
                "backend": self.backend,
                "api_url": self.api_url,
                **data,
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    @staticmethod
    def _strip_image_data_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a payload copy with base64 image data replaced by placeholders."""
        if not isinstance(payload, dict):
            return payload
        clean = dict(payload)
        messages = clean.get("messages")
        if isinstance(messages, list):
            clean_messages = []
            for msg in messages:
                if not isinstance(msg, dict):
                    clean_messages.append(msg)
                    continue
                clean_msg = dict(msg)
                content = clean_msg.get("content")
                if isinstance(content, list):
                    clean_parts = []
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "image_url":
                            image_url = part.get("image_url", {})
                            url = image_url.get("url", "")
                            if isinstance(url, str) and url.startswith("data:"):
                                placeholder = "data:<image-data-omitted>"
                                clean_parts.append({
                                    "type": "image_url",
                                    "image_url": {"url": placeholder},
                                })
                                continue
                        clean_parts.append(part)
                    clean_msg["content"] = clean_parts
                clean_messages.append(clean_msg)
            clean["messages"] = clean_messages
        return clean

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

    def _invalidate_context_usage(self) -> None:
        """Invalidate cached context metrics after history/runtime changes."""
        self.last_exact_context_tokens = None
        self.last_exact_context_source = None
        self.last_exact_context_fingerprint = None

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
        if getattr(self, "system_prompt_mode", "full") == "none":
            return ""

        memory_context = MemoryManager.get_context_for_prompt()

        # Динамические системные пути (без хардкода конкретного пользователя)
        windows_username = getpass.getuser()
        home_path = str(Path.home())
        # Для Markdown экранируем обратные слэши
        home_path_md = home_path.replace("\\", "\\\\")
        desktop_path_md = os.path.join(home_path, "Desktop").replace("\\", "\\\\")
        projects_path_md = os.path.join(home_path, "PycharmProjects").replace("\\", "\\\\")

        platform_name = "macOS" if IS_MACOS else "Windows"
        path_warning = "Avoid using non-ASCII characters in macOS paths." if IS_MACOS else "Avoid using non-ASCII characters in Windows paths."

        # Base prompt
        base_prompt = f"""You are Jarvis (Friday), a local expert coding and system assistant on {platform_name}.

## Identity and tone
- Address the user as **Sir** (1-2 times per response).
- Be concise, professional, and direct. No filler, no unnecessary apologies.
- Respond in the user's language (Russian by default).

## Input prefixes
- `!STT` = voice input, may have transcription errors. Infer intent.
- `!PH` = phone/Telegram. Keep answers short, no tables or ASCII art.

## Platform awareness
- Platform: {platform_name}. User: {windows_username}.
- Home: `{home_path_md}`. Desktop: `{desktop_path_md}`. Projects: `{projects_path_md}`.
- {path_warning}
- On macOS use: `open`, `pkill`/`killall`, `osascript`, `defaults`, `mdfind`, `ls`, `cp`, `rm`, `mv`, `mkdir`, `find`, `ps aux`, `lsof`, `curl`, `pbcopy`/`pbpaste`.
- Never use Windows-only commands on macOS.
- Get current time from a shell command, do not guess.

## Hard constraints
- NEVER use `run_python` to output final answers. Use it only for short scripts or calculations.
- Do NOT expose secrets, credentials, or private keys.
- Ask the user before destructive actions (`rm -rf`, dropping tables, etc.).

## Output discipline
- Internal reasoning belongs in МЫСЛЬ blocks. The user does not see them.
- Final answers must be concise and contain only the result/status. Do NOT paste raw tool args, full tracebacks, step-by-step plans, or file contents.
- If something failed: state the cause and the fix in one sentence.

## Memory
"""

        # Memory block
        if memory_context:
            memory_block = f"""{memory_context}
**Important:** This information is already in context — do NOT call manage_memory to retrieve it.
"""
        else:
            memory_block = "Memory is empty.\n"

        # Platform-specific priorities and automation
        if IS_MACOS:
            platform_block = """
## macOS command priorities
- `run_cmd` is primary: `open`, `pkill -x App`, `osascript`, `ls`, `cp`, `rm`, `mv`, `mkdir`, `find`, `mdfind`, `ps aux`, `lsof -i :PORT`, `curl`.
- GUI automation: `launch_app` first, then AppleScript via `run_cmd`. Use `take_screenshot` only for visual confirmation.
"""
        else:
            platform_block = """
## Windows command priorities
- `run_cmd` is primary: `start`, `explorer`, `taskkill /F /IM app.exe`, `dir`, `copy`, `del`, `move`, `mkdir`, `systeminfo`, `tasklist`.
- GUI automation: `launch_app` first, then `get_app_context` / `do_action_in_app`. Use `take_screenshot` only for visual confirmation.
"""

        tools_prompt = f"""
{platform_block}

## Available tools
Use tools whenever needed. Key tools: run_cmd, run_background_task, read_code, edit_code, write_file, check_syntax, list_directory, grep_code, search_text_in_file, launch_app, take_screenshot, manage_memory, ask_user, search_web, read_url, generate_image, telegram_*, wait.

## How to call tools
- Output exactly one XML block per tool call. Do not describe the plan in plain text first.
```
<tool_call>
<function=TOOL_NAME>
<parameter=PARAM_NAME>VALUE</parameter>
</function>
</tool_call>
```
- Wrap every call in `<tool_call>...</tool_call>`.
- Independent calls may be emitted together; dependent calls must be sequential.

## Planning mode (optional)
Planning is optional. Do NOT create a plan automatically for every request.
- Use `create_plan` only when the task is complex, multi-step, or when you (the model) decide it helps organize the work.
- If you create a plan, mark the first step `in_progress` with `update_plan` and track progress after meaningful steps.
- The active plan is automatically injected into every subsequent request — do not repeat it in full.
- If an active plan is already shown in the Runtime context, do NOT call `create_plan` again; just follow it and use `update_plan`.
- If the task changes, update the plan; do not silently drift.
- If stuck for 3+ iterations on one step without progress, STOP and ask the user.

## Working directory
- If a "Current working directory" block appears below, use it as the default `cwd` for `run_cmd` and `run_background_task` unless the user says otherwise.
- When you read/write/edit a file inside a project, the system auto-sets that project as the working directory.
- You can also call `set_working_directory(path)` explicitly.

## Execution rules
1. Gather facts first (`read_code`, `run_cmd`, `search_web`) before editing. Never edit code you have not read.
2. Validate external resources (APIs, packages, RSS) with the same client your code will use.
3. Use the minimum set of tools. Do not call tools speculatively.
4. After every edit run `check_syntax(path)`.
5. Make the smallest change that fixes the issue. Avoid speculative refactors.

## Desktop automation algorithm
1. Desktop apps: `launch_app` → shell/AppleScript or `get_app_context`/`do_action_in_app`.
2. Use `take_screenshot` only for visual analysis or when UI Automation fails.
3. Use `click_text` only as a final fallback.
4. When you have enough information, respond immediately.

## Coding rules
- Read files with `read_code` BEFORE editing.
- Use `edit_code` with a unique `expected_old_code` block that includes 3-5 lines of context. Do not rely on line numbers alone.
- `write_file` is only for: new files, explicit full rewrites, or corrupted files.
- If `edit_code` fails with "code no longer matches", re-read the file and retry with fresh `expected_old_code`.
- Keep comments and docstrings accurate.

## Loop prevention
- If a tool fails twice with the same arguments, STOP and analyze why. Never call it a third time with identical arguments.
- If `edit_code` fails because expected_old_code does not match, re-read the file first; do not retry with the same block.
- Do not cycle between killing a process, rewriting code, and restarting without verifying each intermediate step.
- If you have made 5+ tool calls on the same subtask without clear progress, stop and ask the user.

## Servers and background processes
- Before starting a server, check the port is free (`lsof -i :PORT` on macOS, `netstat -ano | findstr :PORT` on Windows).
- After `run_background_task`, verify the process is running (read log or use `lsof`/`ps`).
- A successful `curl` to `/` does NOT prove the server works. Test the actual endpoint you changed and inspect the body.
- If a server returns 500/502/503, read the FULL log, not just the last few lines.

## Network and SSL
- Do not assume a public API is reachable. Test it first.
- On macOS, Python's `ssl`/`httpx` may fail while `curl` works. If you see SSL errors, switch the implementation to `curl` via `subprocess` instead of retrying the broken client.
- Set reasonable timeouts and handle failures gracefully (return a user-friendly error, do not crash).

## Tool result verification
- `SUCCESS` from a tool does not mean the task is done. Verify the actual outcome:
  - After `write_file`/`edit_code`: read the relevant lines and run `check_syntax`.
  - After `run_cmd` starting a server: `curl` the real endpoint and check the response.
  - After killing a process: confirm with `lsof`/`ps` that the port/PID is gone.
- If verification fails, fix the root cause before proceeding.

## Error handling
- Analyze the FULL error message, adapt the plan, and try a different approach. Do not repeat the exact same failed call.
- Summarize technical errors for the user in one sentence.

## Images
When `generate_image` succeeds, include the result as: `(image)[/absolute/path/to/image.png]`

## Final answer
- Provide a concise summary of what was done, changed files, and verification performed.
"""

        return base_prompt + memory_block + tools_prompt

    def _plan_context(self) -> str:
        """Отформатировать активный план для подстановки в системный промпт."""
        if not self.active_plan:
            return "Active plan: none."
        title = self.active_plan.get("title", "Current task")
        steps = self.active_plan.get("steps", [])
        lines = [f"Active plan: {title}"]
        for step in steps:
            sid = step.get("id", "?")
            desc = step.get("description", "")
            status = step.get("status", "pending")
            marker = {"done": "[x]", "in_progress": "[>]", "pending": "[ ]"}.get(status, f"[{status}]")
            lines.append(f"  {marker} {sid}. {desc}")
        return "\n".join(lines)

    def _cwd_context(self) -> str:
        """Отформатировать рабочую директорию для подстановки в системный промпт."""
        if not self.working_directory:
            return "Current working directory: not set. Use paths the user provides, or call set_working_directory."
        return f"Current working directory: {self.working_directory}\nUse it as the default cwd for run_cmd and run_background_task unless the user specifies otherwise."

    def _build_augmented_system_prompt(self) -> str:
        """Системный промпт + актуальный runtime-контекст (план, cwd, фоновые задачи)."""
        parts = [self.system_prompt]
        runtime = []
        cwd_ctx = self._cwd_context()
        if cwd_ctx:
            runtime.append(cwd_ctx)
        plan_ctx = self._plan_context()
        if plan_ctx:
            runtime.append(plan_ctx)
        bg_ctx = background_tasks_context()
        if bg_ctx:
            runtime.append(bg_ctx)
        if runtime:
            parts.append("## Runtime context")
            parts.extend(runtime)
        return "\n\n".join(parts)

    @staticmethod
    def _message_requires_plan(content: str) -> bool:
        """Определить, требует ли сообщение пользователя обязательного планирования."""
        if not content or not isinstance(content, str):
            return False
        lowered = content.strip().lower()
        if not lowered:
            return False

        # Приветствия и благодарности
        greetings = {
            "привет", "здравствуй", "здравствуйте", "хай", "хело", "хелло",
            "hello", "hi", "hey", "yo", "good morning", "good evening",
            "спасибо", "thanks", "thank you", "благодарю", "ок", "окей",
            "okay", "ok", "ладно", "понял", "поняла", "ясно", "понятно",
        }
        words = set(re.findall(r"[\w']+", lowered))
        if len(words) <= 3 and (words & greetings or lowered in greetings):
            return False

        # Свободные фразы
        chitchat_phrases = {
            "как дела", "как ты", "что делаешь", "что нового", "кто ты",
            "как тебя зовут", "расскажи о себе", "поговорим", "ты кто",
            "how are you", "what are you doing", "who are you", "what's up",
        }
        for phrase in chitchat_phrases:
            if phrase in lowered:
                return False

        return True

    def _emit_plan_update(self) -> None:
        """Уведомить UI об изменении активного плана."""
        try:
            hook = getattr(UI, "print_plan_update", None)
            if hook is not None and callable(hook):
                hook(self.active_plan)
        except Exception:
            pass

    def _force_create_plan(self, content: str, stream: bool = True) -> None:
        """Принудительно создать план перед выполнением задачи.

        Отправляет короткий planning-only запрос к модели и выполняет
        create_plan, если модель его вызвала. Если модель не вызвала
        create_plan, создаёт резервный одношаговый план, чтобы UI
        и контекст всегда имели активный план.
        """
        planning_prompt = (
            "The user has requested a task. You MUST call `create_plan` first "
            "with a concrete numbered plan. Do not answer the user directly yet. "
            "After creating the plan, mark step 1 as in_progress with `update_plan`."
        )
        messages = self._build_server_safe_messages()
        # Вставляем инструкцию перед последним сообщением пользователя, чтобы
        # она воспринималась как непосредственное указание к текущему запросу.
        if messages and messages[-1].get("role") == "user":
            messages.insert(-1, {"role": "system", "content": planning_prompt})
        else:
            messages.append({"role": "system", "content": planning_prompt})

        payload = {
            "messages": messages,
            "max_tokens": min(self.max_tokens, 2048),
            "temperature": self.temperature,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "penalty_last_n": self.penalty_last_n,
            "stream": False,
            "tools": self.get_active_tools_definition(),
            "tool_choice": "auto",
        }
        payload = self._prepare_payload_for_backend(payload)
        self._log_request(payload, tag="plan_request")

        plan_created = False
        try:
            connect_timeout, read_timeout = self._compute_request_timeout(payload)
            response = requests.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=(connect_timeout, read_timeout),
            )
            response.raise_for_status()
            data = response.json()
            message = data.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls", []) or []

            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else {}
                except Exception:
                    args = {}
                if tool_name == "create_plan":
                    result = self.create_plan(**args)
                    if result.success:
                        plan_created = True
                        # Сразу отмечаем первый шаг in_progress
                        steps = self.active_plan.get("steps", []) if self.active_plan else []
                        if steps:
                            self.update_plan(steps[0].get("id"), "in_progress")
                elif tool_name == "update_plan" and self.active_plan:
                    self.update_plan(**args)

            # Fallback: если модель не создала план, создаём базовый
            if not plan_created:
                fallback_title = content.strip()[:80] or "Выполнить запрос пользователя"
                self.create_plan(fallback_title, ["Выполнить запрос пользователя"])
                self.update_plan("1", "in_progress")

        except Exception as exc:
            # В случае ошибки API тоже создаём резервный план, чтобы не сломать UI
            fallback_title = content.strip()[:80] or "Выполнить запрос пользователя"
            self.create_plan(fallback_title, [f"Выполнить запрос: {fallback_title}"])
            self.update_plan("1", "in_progress")
            UI.print_status(f"Planning enforcement fallback used: {exc}", "warning")

    def create_plan(self, title: str, steps: List[str]) -> ToolResult:
        """Создать активный план задачи."""
        if not title or not isinstance(title, str):
            return ToolResult(False, None, "Plan title is required.")
        if not isinstance(steps, list) or not steps:
            return ToolResult(False, None, "steps must be a non-empty list of strings.")
        normalized_steps = []
        for idx, step in enumerate(steps, 1):
            text = str(step).strip() if step else ""
            if not text:
                continue
            normalized_steps.append({
                "id": str(idx),
                "description": text,
                "status": "pending"
            })
        if not normalized_steps:
            return ToolResult(False, None, "No valid step descriptions provided.")
        self.active_plan = {"title": title.strip(), "steps": normalized_steps}
        self._emit_plan_update()
        return ToolResult(True, {"title": title, "steps": normalized_steps}, "Plan created.")

    def update_plan(self, step_id: str, status: str) -> ToolResult:
        """Обновить статус шага активного плана."""
        if not self.active_plan:
            return ToolResult(False, None, "No active plan. Create one with create_plan first.")
        if status not in {"pending", "in_progress", "done"}:
            return ToolResult(False, None, "status must be one of: pending, in_progress, done.")
        for step in self.active_plan.get("steps", []):
            if str(step.get("id")) == str(step_id):
                step["status"] = status
                self._emit_plan_update()
                return ToolResult(True, {"step_id": step_id, "status": status}, "Plan step updated.")
        return ToolResult(False, None, f"Step '{step_id}' not found in active plan.")

    def set_working_directory(self, path: str) -> ToolResult:
        """Установить рабочую директорию для команд и фоновых задач."""
        if not path or not isinstance(path, str):
            return ToolResult(False, None, "path is required.")
        expanded = os.path.expanduser(path)
        if not os.path.isdir(expanded):
            return ToolResult(False, None, f"Directory does not exist: {expanded}")
        self.working_directory = os.path.abspath(expanded)
        return ToolResult(True, {"working_directory": self.working_directory}, "Working directory set.")

    def _maybe_update_working_directory_from_path(self, path: str) -> None:
        """Авто-определение рабочей директории по пути к файлу/директории проекта."""
        if not path or not isinstance(path, str):
            return
        expanded = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(expanded):
            return
        # Ищем корень проекта по маркерам
        candidate = Path(expanded)
        if candidate.is_file():
            candidate = candidate.parent
        markers = {".git", "pyproject.toml", "setup.py", "requirements.txt", "package.json"}
        root = candidate
        for parent in candidate.parents:
            if any((parent / m).exists() for m in markers):
                root = parent
            else:
                break
        # Ограничиваемся типичной папкой проектов пользователя
        try:
            home = Path.home()
            projects_root = home / "PycharmProjects"
            if projects_root.exists() and root != home:
                # Если путь внутри PycharmProjects, берём корень конкретного проекта
                try:
                    rel = root.relative_to(projects_root)
                    if rel.parts:
                        root = projects_root / rel.parts[0]
                except ValueError:
                    pass
        except Exception:
            pass
        self.working_directory = str(root)

    def reset_history(self):
        """Сбросить историю чата"""
        self.messages = [{"role": "system", "content": self._build_augmented_system_prompt()}]
        self.last_active_file_path = None
        self.active_plan = None
        self.working_directory = None
        self._invalidate_context_usage()

    def refresh_system_prompt(self):
        """
        Обновить системный промпт с актуальной памятью.
        Вызывается после изменения памяти через manage_memory.
        """
        self.system_prompt = self._build_system_prompt()

        # Обновляем системное сообщение в истории если оно есть
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = self._build_augmented_system_prompt()

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

    def _tool_attempt_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Уникальный ключ для вызова инструмента (для отслеживания повторов)."""
        try:
            return f"{tool_name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
        except Exception:
            return f"{tool_name}:{str(args)}"

    def _is_repeated_failure(self, tool_name: str, args: Dict[str, Any]) -> bool:
        """Проверить, не падал ли уже этот вызов в текущем ходе."""
        return self._tool_attempt_key(tool_name, args) in self._failed_tool_attempts

    def _record_tool_failure(self, tool_name: str, args: Dict[str, Any]) -> None:
        """Запомнить неудачный вызов, чтобы не повторять его."""
        key = self._tool_attempt_key(tool_name, args)
        if key not in self._failed_tool_attempts:
            self._failed_tool_attempts.append(key)

    def _record_tool_attempt(self, tool_name: str, args: Dict[str, Any]) -> None:
        """Записать факт вызова инструмента для детекции циклов."""
        key = self._tool_attempt_key(tool_name, args)
        self._tool_attempt_counts[key] = self._tool_attempt_counts.get(key, 0) + 1
        self._recent_tool_fingerprints.append(key)

    def _is_looping_tool(self, tool_name: str, args: Dict[str, Any], max_repeats: int = 3) -> bool:
        """Проверить, не повторяется ли один и тот же вызов слишком часто."""
        key = self._tool_attempt_key(tool_name, args)
        if self._tool_attempt_counts.get(key, 0) >= max_repeats:
            return True
        # Если среди последних 8 вызовов одно и то же встречается >= max_repeats
        recent = list(self._recent_tool_fingerprints)
        if recent.count(key) >= max_repeats:
            return True
        return False

    def _is_agent_looping(self, tool_calls: List[Dict[str, Any]]) -> Optional[str]:
        """Проверить весь набор вызовов итерации на повторы/циклы."""
        for tc in tool_calls:
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            args_str = func.get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else (args_str or {})
            except Exception:
                args = {}
            if self._is_looping_tool(tool_name, args, max_repeats=3):
                return tool_name
        return None

    def _record_visible_content(self, current_visible: str) -> None:
        """Сохранить видимый текст итерации для детекции стагнации."""
        normalized = re.sub(r"\s+", " ", current_visible or "").strip()
        self._visible_content_history.append(normalized)

    def _detect_stagnation(self, window: int = 4) -> bool:
        """True, если последние `window` итераций не принесли нового видимого текста."""
        if len(self._visible_content_history) < window:
            return False
        recent = list(self._visible_content_history)[-window:]
        # Считаем стагнацией, если все последние записи пустые или одинаковые
        non_empty = [x for x in recent if x]
        if not non_empty:
            return True
        return len(set(non_empty)) == 1

    @staticmethod
    def _tool_uses_file_path(tool_name: str) -> bool:
        return tool_name in {
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
        # Авто-определяем рабочую директорию по пути к файлу
        self._maybe_update_working_directory_from_path(candidate)

    def _update_exact_context_from_timings(self, timings: Any) -> Optional[int]:
        if not isinstance(timings, dict):
            return None

        prompt_n = self._safe_int(timings.get("prompt_n"))
        cache_n = self._safe_int(timings.get("cache_n"))
        predicted_n = self._safe_int(timings.get("predicted_n"))

        if prompt_n is None and cache_n is None and predicted_n is None:
            return None

        # prompt_n is the prompt size for the current request. cache_n is a
        # server-side accounting detail and predicted_n belongs to generation,
        # so adding them would overstate the context used by the next prompt.
        total = max(prompt_n if prompt_n is not None else (cache_n or 0), 0)
        self.last_exact_context_tokens = total
        self.last_exact_context_source = "server_timings"
        self.last_exact_context_fingerprint = self._context_history_fingerprint()
        return total

    def _context_history_fingerprint(self) -> str:
        try:
            return json.dumps(self._build_server_safe_messages(), ensure_ascii=False, sort_keys=True)
        except Exception:
            return repr(getattr(self, "messages", []))

    @staticmethod
    def _format_speed_footer(timings: Any) -> str:
        """Вернуть footer со скоростью генерации, если timings содержат predicted_per_second."""
        if not isinstance(timings, dict):
            return ""
        speed = timings.get("predicted_per_second")
        if speed is None:
            return ""
        try:
            speed_f = float(speed)
        except (TypeError, ValueError):
            return ""
        if speed_f <= 0:
            return ""
        return f"\n\n---\n⚡ ~{speed_f:.1f} tok/s"

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
                    self.last_exact_context_fingerprint = self._context_history_fingerprint()
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

    def _estimate_prompt_tokens(self) -> int:
        """Приблизительная оценка размера текущего промпта в токенах."""
        try:
            prompt_text = json.dumps(self._build_server_safe_messages(), ensure_ascii=False)
        except Exception:
            try:
                prompt_text = json.dumps(getattr(self, "messages", []), ensure_ascii=False)
            except Exception:
                prompt_text = ""
        return max(1, self._estimate_tokens(prompt_text))

    def _build_fallback_timings(
        self,
        content: str,
        metrics: Dict[str, Any],
        existing_timings: Optional[Dict[str, Any]] = None,
        usage: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Собрать timings на стороне клиента, если сервер (например, MLX/optiq)
        не присылает поле timings в ответе.

        metrics: {'start': t0, 'first': t_first_token, 'end': t_finish}
        usage: OpenAI-compatible usage dict (prompt_tokens, completion_tokens, ...)
        """
        if isinstance(existing_timings, dict):
            if existing_timings.get("predicted_per_second") and existing_timings.get("prompt_per_second"):
                return existing_timings
        else:
            existing_timings = None

        end = metrics.get("end") or time.time()
        start = metrics.get("start") or end
        first = metrics.get("first")
        if first is None:
            first = start

        prompt_ms = max((first - start) * 1000.0, 1.0)
        predicted_ms = max((end - first) * 1000.0, 1.0)

        prompt_n = self._safe_int(existing_timings.get("prompt_n")) if existing_timings else None
        if prompt_n is None and isinstance(usage, dict):
            prompt_n = self._safe_int(usage.get("prompt_tokens"))
        if prompt_n is None:
            prompt_n = self._estimate_prompt_tokens()

        predicted_n = self._safe_int(existing_timings.get("predicted_n")) if existing_timings else None
        if predicted_n is None and isinstance(usage, dict):
            predicted_n = self._safe_int(usage.get("completion_tokens"))
        if predicted_n is None:
            predicted_n = max(1, self._estimate_tokens(content))

        timings: Dict[str, Any] = {
            "prompt_n": prompt_n,
            "prompt_ms": prompt_ms,
            "prompt_per_second": (
                existing_timings.get("prompt_per_second")
                if existing_timings and existing_timings.get("prompt_per_second")
                else prompt_n / (prompt_ms / 1000.0)
            ),
            "predicted_n": predicted_n,
            "predicted_ms": predicted_ms,
            "predicted_per_second": (
                existing_timings.get("predicted_per_second")
                if existing_timings and existing_timings.get("predicted_per_second")
                else predicted_n / (predicted_ms / 1000.0)
            ),
        }

        cache_n = None
        if existing_timings:
            cache_n = self._safe_int(existing_timings.get("cache_n"))
        if cache_n is None and isinstance(usage, dict):
            details = usage.get("prompt_tokens_details") or {}
            cache_n = self._safe_int(details.get("cached_tokens"))
        if cache_n is not None:
            timings["cache_n"] = cache_n

        if existing_timings:
            for key in ("prompt_per_token_ms", "predicted_per_token_ms"):
                if key in existing_timings:
                    timings[key] = existing_timings[key]

        return timings

    def _compute_request_timeout(self, payload: Dict[str, Any]) -> tuple[float, float]:
        """Вычислить таймаут HTTP-запроса на основе размера промпта.

        Длинные контексты (например, 80k) на больших Q4/Q6 моделях могут
        обрабатывать prefill десятки секунд или минуты. Фиксированный
        timeout=60 приводит к ReadTimeout и обрыву стрима.
        """
        messages = payload.get("messages", [])
        try:
            prompt_text = json.dumps(messages, ensure_ascii=False)
        except Exception:
            prompt_text = str(messages)
        estimated_tokens = max(1, self._estimate_tokens(prompt_text))

        # Минимум 4 ток/сек для prefill на медленном железе;
        # ограничиваем сверху 10 минут, чтобы не ждать вечно при зависании.
        read_timeout = max(120.0, min(600.0, estimated_tokens / 4.0))
        return (30.0, read_timeout)

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

        # Считаем токены с конца (от новых к старым), пока не достигнем лимита.
        # Учитываем tool_calls и идентификаторы, иначе именно coding-задачи
        # незаметно переполняют контекст длинными результатами инструментов.
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
            if msg.get("tool_calls"):
                msg_tokens += self._estimate_tokens(json.dumps(msg["tool_calls"], ensure_ascii=False))
            if msg.get("tool_call_id"):
                msg_tokens += self._estimate_tokens(str(msg["tool_call_id"]))

            # Если добавление этого сообщения превысит лимит — останавливаемся
            if tokens_so_far + msg_tokens > max_tokens:
                # Не выбрасываем самый новый пользовательский запрос целиком,
                # даже если он сам по себе больше резервного бюджета.
                if not messages_to_keep and msg.get("role") == "user":
                    messages_to_keep.append(msg)
                break

            tokens_so_far += msg_tokens
            messages_to_keep.append(msg)

        # Если все сообщения помещаются — ничего не делаем
        if len(messages_to_keep) == len(self.messages) - 1:
            return

        # Переворачиваем обратно (от старых к новым) и добавляем системный промпт
        messages_to_keep.reverse()
        # Не оставляем историю, начинающуюся с tool-сообщения: его assistant
        # tool_call мог быть отброшен вместе со старой частью истории.
        first_user = next(
            (index for index, msg in enumerate(messages_to_keep) if msg.get("role") == "user"),
            None,
        )
        if first_user is not None and first_user > 0:
            messages_to_keep = messages_to_keep[first_user:]
        self.messages = [self.messages[0]] + messages_to_keep
        self._invalidate_context_usage()

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
        valid_tool_call_ids: set[str] = set()

        for original in source_messages:
            msg = dict(original)
            role = msg.get("role")

            if role == "assistant":
                sanitized_tool_calls = []
                dropped_tool_calls = 0
                for tool_call in msg.get("tool_calls", []) or []:
                    sanitized = self._sanitize_native_tool_call_for_server(tool_call)
                    if sanitized is None:
                        dropped_tool_calls += 1
                        continue
                    sanitized_tool_calls.append(sanitized)
                    tool_call_id = sanitized.get("id")
                    if tool_call_id:
                        valid_tool_call_ids.add(str(tool_call_id))

                if sanitized_tool_calls:
                    msg["tool_calls"] = sanitized_tool_calls
                else:
                    msg.pop("tool_calls", None)

                if dropped_tool_calls:
                    self._perf_log("dropped_invalid_native_tool_calls", {
                        "count": dropped_tool_calls,
                        "content_preview": str(msg.get("content") or "")[:160],
                    })

                if msg.get("content") is None:
                    msg["content"] = ""

            if role == "tool":
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id and str(tool_call_id) not in valid_tool_call_ids:
                    self._perf_log("dropped_orphan_tool_message", {
                        "tool_call_id": str(tool_call_id),
                        "content_preview": str(msg.get("content") or "")[:160],
                    })
                    continue

            if (
                safe_messages
                and role == "assistant"
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

    def _sanitize_native_tool_call_for_server(self, tool_call: Any) -> Optional[Dict[str, Any]]:
        """Return a server-safe native tool_call, or None if it is malformed."""
        if not isinstance(tool_call, dict):
            return None

        sanitized = dict(tool_call)
        function = sanitized.get("function")
        if not isinstance(function, dict):
            return None

        function = dict(function)
        name = str(function.get("name") or "").strip()
        if not name:
            return None

        arguments = function.get("arguments", "{}")
        if arguments is None or arguments == "":
            arguments = "{}"
        elif isinstance(arguments, str):
            try:
                json.loads(arguments)
            except Exception:
                return None
        elif isinstance(arguments, (dict, list)):
            arguments = json.dumps(arguments, ensure_ascii=False)
        else:
            return None

        function["name"] = name
        function["arguments"] = arguments
        sanitized["function"] = function
        sanitized.setdefault("type", "function")
        return sanitized

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

    @staticmethod
    def _format_tool_result_for_model(tool_name: str, result: ToolResult) -> str:
        """Преобразовать результат инструмента в строку для модели.

        При ошибке ошибка дублируется и в data, чтобы модель точно её увидела,
        даже если сфокусируется на поле data.
        """
        import json as _json

        payload = result.to_dict()
        # Если data == None при ошибке — кладём ошибку в data, чтобы модель не увидела null
        if not result.success and result.data is None and result.error:
            payload["data"] = {"error": result.error}

        data_part = _json.dumps(payload.get("data"), ensure_ascii=False, default=str)

        if result.success:
            return f"Tool '{tool_name}' succeeded.\nData: {data_part}"
        error = result.error or "Unknown error"
        return f"Tool '{tool_name}' FAILED.\nError: {error}\nData: {data_part}"

    def execute_tool(self, tool_name: str, args: Dict) -> ToolResult:
        """Выполнить инструмент"""
        # Специальные инструменты, управляющие внутренним состоянием агента
        if tool_name == "create_plan":
            return self.create_plan(**args)
        if tool_name == "update_plan":
            return self.update_plan(**args)
        if tool_name == "set_working_directory":
            return self.set_working_directory(**args)

        if tool_name not in TOOLS_MAP:
            return ToolResult(False, None, f"Инструмент '{tool_name}' не найден")

        # Защита от повторов: если этот вызов уже падал в текущем ходе, не повторяем
        if self._is_repeated_failure(tool_name, args):
            return ToolResult(
                False,
                None,
                f"[Anti-loop] You already called '{tool_name}' with the same arguments and it failed. "
                f"Do not repeat the same call; choose a different approach."
            )

        # Авто-заполнение cwd для shell-команд из рабочей директории агента
        if tool_name in ("run_cmd", "run_background_task") and self.working_directory:
            if not args.get("cwd"):
                args = dict(args)
                args["cwd"] = self.working_directory

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
                self._record_tool_failure(tool_name, args)
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
                else:
                    # Запоминаем неудачный вызов, чтобы не повторять его
                    self._record_tool_failure(tool_name, args)

            return result
        except TypeError as te:
            # TypeError usually означает неправильные аргументы
            self._record_tool_failure(tool_name, args)
            sig = inspect.signature(tool_func)
            example_sig = ", ".join([f"{k}='...'" for k in sig.parameters.keys()])
            return ToolResult(
                False, None,
                f"Error: wrong arguments for '{tool_name}': {str(te)}. "
                f"Call the tool again with correct arguments. "
                f"Signature: {tool_name}({example_sig})"
            )
        except Exception as e:
            self._record_tool_failure(tool_name, args)
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
        """Распарсить XML-вызовы инструментов из ответа модели.

        Поддерживает форматы:
          <function=name>{"arg":"value"}</function>
          <function=name><parameter=arg>value</parameter></function>
          <tool_call><function=name>...</function></tool_call>
        """
        tool_calls = []
        if not content:
            return tool_calls

        # 1) Сначала ищем полные <tool_call>...</tool_call> блоки
        tool_call_pattern = re.compile(
            r'<tool_call\s*>(.*?)</tool_call\s*>',
            re.DOTALL | re.IGNORECASE
        )
        # 2) И bare <function=...>...</function> (без обёртки)
        function_pattern = re.compile(
            r'<function=(\w+)>(.*?)</function>',
            re.DOTALL | re.IGNORECASE
        )
        # 3) Параметры
        param_pattern = re.compile(
            r'<parameter=(\w+)>(.*?)</parameter>',
            re.DOTALL | re.IGNORECASE
        )

        # Собираем все function-блоки: сначала из tool_call, потом bare
        function_blocks: List[Tuple[str, str]] = []
        for tc_match in tool_call_pattern.finditer(content):
            inner = tc_match.group(1)
            for fn_match in function_pattern.finditer(inner):
                function_blocks.append((fn_match.group(1), fn_match.group(2)))

        # Если tool_call блоков не нашлось — ищем bare function (но только если они
        # не находятся внутри уже найденных tool_call, что маловероятно при таком
        # порядке, но перестрахуемся)
        if not function_blocks:
            for fn_match in function_pattern.finditer(content):
                function_blocks.append((fn_match.group(1), fn_match.group(2)))

        for tool_name, inner in function_blocks:
            inner = inner.strip()
            args: Dict[str, Any] = {}

            # Пробуем распарсить внутренность как JSON
            try:
                args = json.loads(inner)
                if isinstance(args, dict):
                    tool_calls.append({
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(args, ensure_ascii=False)
                        }
                    })
                    continue
            except json.JSONDecodeError:
                pass

            # Пробуем распарсить <parameter=name>value</parameter>
            for p_match in param_pattern.finditer(inner):
                param_name = p_match.group(1)
                param_value = p_match.group(2).strip()
                # Пытаемся преобразовать в число/булево/None, если это явно
                lowered = param_value.lower()
                if lowered == "true":
                    param_value = True
                elif lowered == "false":
                    param_value = False
                elif lowered == "null" or lowered == "none":
                    param_value = None
                else:
                    try:
                        if '.' in param_value:
                            param_value = float(param_value)
                        else:
                            param_value = int(param_value)
                    except ValueError:
                        pass
                args[param_name] = param_value

            if args:
                tool_calls.append({
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(args, ensure_ascii=False)
                    }
                })

        return tool_calls

    @staticmethod
    def _strip_thinking_tags(text: str) -> str:
        """Удалить теги <think>...</think> из текста ( defense in depth )."""
        if not text:
            return text
        return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    @staticmethod
    def _strip_xml_tool_calls(text: str) -> str:
        """Удалить XML-разметку tool_call из видимого текста.

        Убирает полные блоки <tool_call>/<function>/<parameter> и их обрывки.
        Терпима к переносам строк и лишним пробелам внутри/вокруг тегов.
        """
        if not text:
            return text
        cleaned = text
        # 1) Полные <tool_call>...</tool_call> блоки (с атрибутами/пробелами)
        cleaned = re.sub(
            r'<tool_call\b[^>]*>.*?</tool_call\s*>',
            '', cleaned, flags=re.DOTALL | re.IGNORECASE
        )
        # 2) Полные <function=...>...</function> блоки
        cleaned = re.sub(
            r'<function=[^>]+>.*?</function\s*>',
            '', cleaned, flags=re.DOTALL | re.IGNORECASE
        )
        # 3) Одиночные <parameter=...>...</parameter>
        cleaned = re.sub(
            r'<parameter=[^>]+>.*?</parameter\s*>',
            '', cleaned, flags=re.DOTALL | re.IGNORECASE
        )
        # 4) Обрывки открывающих/закрывающих тегов
        cleaned = re.sub(r'<tool_call\b[^>]*>', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'</tool_call\s*>', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'<function=[^>]+>', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'</function\s*>', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'<parameter=[^>]+>', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'</parameter\s*>', '', cleaned, flags=re.IGNORECASE)
        # 5) Хвост, начинающийся с обрывка тега — отрезаем целиком
        cleaned = re.sub(r'<(?:tool_call|function|parameter)\b[^>]*$', '', cleaned, flags=re.IGNORECASE)
        # 6) Убираем пустые строки, оставшиеся после удаления блоков
        cleaned = re.sub(r'\n\s*\n+', '\n\n', cleaned)
        # Не обрезаем пробелы у каждого streaming-чанка: пробел часто
        # находится на границе двух чанков, и .strip() здесь склеивает слова
        # (например, "привет" + " мир" превращается в "приветмир").
        return cleaned

    @staticmethod
    def _extract_safe_streaming_text(buffer: str) -> Tuple[str, str]:
        """Извлечь безопасный текст для вывода в streaming UI.

        Возвращает кортеж (safe_text, remaining_buffer). Полные XML-блоки
        tool_call удаляются; если в буфере обнаружено начало XML-блока,
        возвращается текст до него, а остаток остаётся в буфере до
        получения большего контекста.
        """
        if not buffer:
            return "", ""

        # Удаляем полные tool_call/function/parameter блоки
        cleaned = re.sub(
            r'<tool_call\b[^>]*>.*?</tool_call\s*>',
            '', buffer, flags=re.DOTALL | re.IGNORECASE
        )
        cleaned = re.sub(
            r'<function=[^>]+>.*?</function\s*>',
            '', cleaned, flags=re.DOTALL | re.IGNORECASE
        )
        cleaned = re.sub(
            r'<parameter=[^>]+>.*?</parameter\s*>',
            '', cleaned, flags=re.DOTALL | re.IGNORECASE
        )

        if cleaned != buffer:
            # После удаления полных блоков проверяем, не остался ли обрывок тега в конце
            tail_match = re.search(r'<(?:tool_call|function|parameter)\b[^>]*$', cleaned, re.IGNORECASE)
            if tail_match:
                return cleaned[:tail_match.start()], cleaned[tail_match.start():]
            return cleaned, ""

        # Начало XML, но конца ещё нет — отрезаем только текст до начала
        match = re.search(r'<tool_call\b|<function=[^>]*>|<parameter=[^>]*>', buffer, re.IGNORECASE)
        if match:
            return buffer[:match.start()], buffer[match.start():]

        return buffer, ""

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

    def _poll_slots_progress(self, stop_event: threading.Event, max_tokens: int = 10000) -> None:
        """Опрос /slots llama-server для отображения реального прогресса prefill и decode."""
        slots_url = f"{self.base_url}/slots"
        last_prefill_percent = -1
        last_decode_percent = -1
        prefill_done_reported = False
        stable_count = 0

        while not stop_event.is_set():
            try:
                resp = requests.get(slots_url, timeout=2)
                resp.raise_for_status()
                data = resp.json()
                slots = data.get("value") if isinstance(data, dict) else data
                if not isinstance(slots, list):
                    time.sleep(0.2)
                    continue

                # Активный слот: обрабатывается или занят (state == 1)
                processing = [
                    s for s in slots
                    if s.get("is_processing") or s.get("state") == 1
                ]

                if not processing:
                    stable_count += 1
                    if stable_count > 15:
                        # Долго нет активного слота — генерация, скорее всего, закончилась.
                        break
                    time.sleep(0.1)
                    continue

                stable_count = 0
                slot = processing[0]

                total = int(slot.get("n_prompt_tokens", 0))
                processed = int(slot.get("n_prompt_tokens_processed", 0))
                next_token_raw = slot.get("next_token") or {}
                # В некоторых сборках llama.cpp next_token приходит как list [dict].
                if isinstance(next_token_raw, list) and next_token_raw:
                    next_token = next_token_raw[0] if isinstance(next_token_raw[0], dict) else {}
                elif isinstance(next_token_raw, dict):
                    next_token = next_token_raw
                else:
                    next_token = {}
                n_decoded = int(next_token.get("n_decoded", 0))
                n_remain = int(next_token.get("n_remain", -1))

                # --- Фаза prefill (обработка контекста) ---
                if total > 0 and processed < total:
                    percent = min(99, int(processed * 100 / total))
                    if percent != last_prefill_percent:
                        UI.print_prompt_progress(percent)
                        last_prefill_percent = percent
                    prefill_done_reported = False
                else:
                    # Prefill закончен. Сообщаем 100% один раз.
                    if not prefill_done_reported:
                        UI.print_prompt_progress(100)
                        prefill_done_reported = True

                    # --- Фаза decode (генерация ответа) ---
                    # n_remain: -1 == бесконечность, иначе сколько токенов осталось.
                    if n_decoded > 0 or n_remain >= 0:
                        if n_remain >= 0:
                            total_gen = n_decoded + n_remain
                        else:
                            # Бесконечная генерация — ориентируемся на max_tokens.
                            total_gen = n_decoded + max_tokens
                        decode_percent = min(100, int(n_decoded * 100 / total_gen)) if total_gen > 0 else 0
                    else:
                        decode_percent = 0

                    if decode_percent != last_decode_percent:
                        UI.print_decode_progress(decode_percent)
                        last_decode_percent = decode_percent

            except Exception:
                pass
            time.sleep(0.2)

    def _parse_streaming_response(self, response, show_thinking: bool = True,
                                  stop_event: Optional[threading.Event] = None,
                                  slot_progress_stop_event: Optional[threading.Event] = None,
                                  stream_metrics: Optional[Dict[str, Any]] = None,
                                  chunk_size: int = STREAM_CHUNK_SIZE,
                                  request_start: Optional[float] = None) -> Dict[str, Any]:
        """Разобрать SSE-стрим от совместимого chat completions API."""
        assistant_state = None
        thinking_state = None
        thinking_buffer = []
        streamed_tool_calls: Dict[int, Dict[str, Any]] = {}
        streamed_tool_call_counts: Dict[int, int] = {}
        thinking_finished = False
        waiting_spinner_active = AnimationManager.is_running()
        latest_timings: Optional[Dict[str, Any]] = None
        latest_usage: Optional[Dict[str, Any]] = None
        # Буфер для фильтрации XML tool_call разметки из streaming content.
        streaming_content_buffer = ""

        def _streaming_tool_hook(name: str, *args, **kwargs) -> None:
            hook = getattr(UI, name, None)
            if hook is None:
                return
            try:
                hook(*args, **kwargs)
            except Exception:
                pass

        def _cancel_started_streaming_tools(reason: str = "") -> None:
            """Отменить все частично выведенные native tool_calls (например, при ошибке сервера)."""
            for tc in streamed_tool_calls.values():
                if tc.pop("_streaming_started", False):
                    _streaming_tool_hook(
                        "cancel_streaming_tool_call",
                        tc.get("id", ""),
                        tc.get("function", {}).get("name", ""),
                        reason,
                    )

        # Декодируем байты в строки явно через UTF-8. Используем большой chunk_size,
        # чтобы избежать тысяч мелких read() вызовов на быстром сервере.
        line_iterator = response.iter_lines(chunk_size=chunk_size)
        chunk_index = 0
        first_data_time: Optional[float] = None
        try:
            while True:
                if stop_event is not None and stop_event.is_set():
                    response.close()
                    break

                chunk_read_start = time.time()
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

                if first_data_time is None:
                    first_data_time = time.time()

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

                parse_start = time.time()
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                parse_ms = (time.time() - parse_start) * 1000.0

                if isinstance(event.get("timings"), dict):
                    latest_timings = event.get("timings")

                if isinstance(event.get("usage"), dict):
                    latest_usage = event.get("usage")

                choice = (event.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}

                if slot_progress_stop_event is not None and (delta.get("content") or delta.get("reasoning_content") or delta.get("reasoning") or delta.get("tool_calls")):
                    slot_progress_stop_event.set()

                if stream_metrics is not None and stream_metrics.get("first") is None and (
                    delta.get("content") or delta.get("reasoning_content") or delta.get("reasoning") or delta.get("tool_calls")
                ):
                    stream_metrics["first"] = time.time()

                if waiting_spinner_active:
                    AnimationManager.stop_bg()
                    AnimationManager.start(mode="generating", label="Jarvis генерирует ответ")
                    waiting_spinner_active = False

                chunk_index += 1
                chunk_read_ms = (time.time() - chunk_read_start) * 1000.0
                delta_chars = 0

                reasoning_delta = self._extract_text_value(
                    delta.get("reasoning_content") or delta.get("reasoning")
                )
                if reasoning_delta:
                    delta_chars += len(reasoning_delta)
                    # Храним reasoning_content как есть — из него позже парсятся
                    # XML-вызовы инструментов. Но в UI мышления выводим очищенную
                    # версию без XML-разметки.
                    thinking_buffer.append(reasoning_delta)
                    # Выводим мышление потоково, если ещё не начали вывод ответа
                    if not thinking_finished and show_thinking:
                        if thinking_state is None:
                            thinking_state = UI.start_streaming_thinking()
                        UI.update_streaming_thinking(
                            thinking_state, self._strip_xml_tool_calls(reasoning_delta)
                        )

                content_delta = self._extract_text_value(delta.get("content"))
                if content_delta:
                    delta_chars += len(content_delta)
                    # Если пришло содержимое ответа — завершаем вывод мышления
                    if thinking_buffer and not thinking_finished and show_thinking:
                        thinking_finished = True
                        if thinking_state:
                            UI.finish_streaming_thinking(thinking_state)
                        else:
                            # Если мышление было, но не началось — выводим сразу
                            UI.print_streaming_thinking_block("".join(thinking_buffer))

                    # Фильтруем XML tool_call разметку из потокового текста,
                    # чтобы она не мелькала в UI и не попадала в финальный ответ.
                    streaming_content_buffer += content_delta
                    safe_text, streaming_content_buffer = self._extract_safe_streaming_text(streaming_content_buffer)
                    if safe_text:
                        if assistant_state is None:
                            assistant_state = UI.start_streaming_response("Ответ")
                        ui_update_start = time.time()
                        UI.update_streaming_response(assistant_state, safe_text)
                        ui_update_ms = (time.time() - ui_update_start) * 1000.0
                    else:
                        ui_update_ms = 0.0
                    self._perf_log("stream_chunk", {
                        "chunk_index": chunk_index,
                        "raw_line_bytes": len(raw_line),
                        "chunk_read_ms": round(chunk_read_ms, 3),
                        "parse_ms": round(parse_ms, 3),
                        "ui_update_ms": round(ui_update_ms, 3),
                        "delta_chars": delta_chars,
                        "has_content": bool(content_delta),
                        "has_reasoning": bool(reasoning_delta),
                        "time_since_request_start_ms": round((time.time() - request_start) * 1000, 3) if request_start else None,
                    })

                for tc_delta in delta.get("tool_calls", []) or []:
                    idx = tc_delta.get("index", len(streamed_tool_calls))
                    streamed_tool_call_counts.setdefault(idx, 0)
                    tool_call = streamed_tool_calls.setdefault(idx, {
                        "id": tc_delta.get("id", f"call_{idx}"),
                        "type": tc_delta.get("type", "function"),
                        "function": {
                            "name": "",
                            "arguments": ""
                        },
                        "_streaming_started": False,
                    })

                    if tc_delta.get("id"):
                        tool_call["id"] = tc_delta["id"]
                        streamed_tool_call_counts[idx] += len(tc_delta["id"])

                    function_delta = tc_delta.get("function", {})
                    name_part = function_delta.get("name", "")
                    args_part = function_delta.get("arguments", "")
                    if name_part:
                        tool_call["function"]["name"] += name_part
                        streamed_tool_call_counts[idx] += len(name_part)
                    if args_part:
                        tool_call["function"]["arguments"] += args_part
                        streamed_tool_call_counts[idx] += len(args_part)

                    name_so_far = tool_call["function"]["name"]
                    args_so_far = tool_call["function"]["arguments"]
                    if name_so_far and not tool_call["_streaming_started"]:
                        _streaming_tool_hook("start_streaming_tool_call", tool_call["id"], name_so_far)
                        tool_call["_streaming_started"] = True
                    if tool_call["_streaming_started"]:
                        _streaming_tool_hook("update_streaming_tool_call", tool_call["id"], name_so_far, args_so_far)
        except Exception:
            # При обрыве стрима отменяем висящие native tool_calls, чтобы UI
            # не показывал вечное "пишет инструмент".
            _cancel_started_streaming_tools("stream aborted before tool call completed")
            raise

        # Завершаем вывод мышления если оно ещё не завершено
        if thinking_buffer and not thinking_finished and show_thinking:
            if thinking_state:
                UI.finish_streaming_thinking(thinking_state)
            else:
                UI.print_streaming_thinking_block("".join(thinking_buffer))

        for idx in sorted(streamed_tool_calls):
            tc = streamed_tool_calls[idx]
            if tc.pop("_streaming_started", False):
                _streaming_tool_hook(
                    "finish_streaming_tool_call",
                    tc["id"],
                    tc["function"]["name"],
                    tc["function"]["arguments"],
                )

        # Выводим остаток streaming-буфера, если там остался безопасный текст.
        if streaming_content_buffer and assistant_state is not None:
            safe_tail, _ = self._extract_safe_streaming_text(streaming_content_buffer)
            if safe_tail:
                UI.update_streaming_response(assistant_state, safe_tail)

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
            "usage": latest_usage,
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
        connect_timeout, read_timeout = self._compute_request_timeout(payload)
        stream_metrics: Dict[str, Any] = {"start": time.time(), "first": None}
        request_start = time.time()
        payload_size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        self._perf_log("http_request_start", {
            "payload_bytes": payload_size,
            "messages_count": len(payload.get("messages", [])),
            "max_tokens": payload.get("max_tokens"),
            "stream": stream,
        })
        response = requests.post(
            self.api_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=(connect_timeout, read_timeout),
            stream=stream
        )
        if stream:
            self._set_active_stream_response(response)
            # Отключаем автоматическое декодирование контента, чтобы iter_lines
            # мог читать большими чанками без лишних копирований.
            response.raw.decode_content = True

        slot_progress_stop_event = threading.Event()
        progress_thread: Optional[threading.Thread] = None
        # /slots есть только у llama-server; для MLX/OptiQ/MTPLX опрос бесполезен
        # и только создаёт лишнюю нагрузку/ошибки в логе.
        if stream and not self._is_mlx_like_backend():
            progress_thread = threading.Thread(
                target=self._poll_slots_progress,
                args=(slot_progress_stop_event,),
                daemon=True
            )
            progress_thread.start()

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            slot_progress_stop_event.set()
            # Some servers (older llama-server builds) reject stream_options.
            if payload.get("stream_options"):
                try:
                    body = (error.response.text or "").lower()
                except Exception:
                    body = ""
                if "stream_options" in body or "include_usage" in body or error.response.status_code == 400:
                    UI.print_status(
                        "Сервер не поддерживает stream_options. Повторяю без него...",
                        "warning"
                    )
                    payload = dict(payload)
                    payload.pop("stream_options", None)
                    self._log_request(payload, tag="chat_request_stream_options_fallback")
                    return self._send_completion_request(
                        payload,
                        stream=stream,
                        show_thinking=show_thinking,
                        allow_native_tool_retry=allow_native_tool_retry,
                        stop_event=stop_event,
                    )
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
        self._perf_log("http_response_headers", {
            "status_code": response.status_code,
            "time_to_headers_ms": round((time.time() - request_start) * 1000, 2),
        })

        try:
            if stream:
                parsed = self._parse_streaming_response(
                    response,
                    show_thinking=show_thinking,
                    stop_event=stop_event,
                    slot_progress_stop_event=slot_progress_stop_event,
                    stream_metrics=stream_metrics,
                    chunk_size=STREAM_CHUNK_SIZE,
                    request_start=request_start,
                )
                stream_metrics["end"] = time.time()
                timings = self._build_fallback_timings(
                    parsed.get("content", ""),
                    stream_metrics,
                    parsed.get("timings"),
                    parsed.get("usage")
                )
                self._update_exact_context_from_timings(timings)
                self.last_generation_timings = timings
                self._log_timings(timings, tag="chat_timings")
                return (
                    parsed.get("content", ""),
                    parsed.get("reasoning_content", ""),
                    parsed.get("tool_calls", []),
                )

            data = response.json()
            stream_metrics["end"] = time.time()
            message = data.get("choices", [{}])[0].get("message", {})
            timings = self._build_fallback_timings(
                message.get("content", ""),
                stream_metrics,
                data.get("timings"),
                data.get("usage")
            )
            self._update_exact_context_from_timings(timings)
            self.last_generation_timings = timings
            self._log_timings(timings, tag="chat_timings")
            return (
                message.get("content", ""),
                message.get("reasoning_content", ""),
                message.get("tool_calls", []),
            )
        finally:
            slot_progress_stop_event.set()
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
            "max_tokens": self.max_tokens,
            "temperature": 0.3,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "repeat_penalty": self.repeat_penalty,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "penalty_last_n": self.penalty_last_n,
            "stream": stream,
        }
        if stream:
            retry_payload["stream_options"] = {"include_usage": True}
        retry_payload = self._prepare_payload_for_backend(retry_payload)
        self._log_request(retry_payload, tag="retry_request")

        retry_connect_timeout, retry_read_timeout = self._compute_request_timeout(retry_payload)
        stream_metrics = {"start": time.time(), "first": None}
        response = requests.post(
            self.api_url,
            json=retry_payload,
            headers={"Content-Type": "application/json"},
            timeout=(retry_connect_timeout, retry_read_timeout),
            stream=stream
        )
        if stream:
            self._set_active_stream_response(response)

        slot_progress_stop_event = threading.Event()
        progress_thread: Optional[threading.Thread] = None
        if stream and not self._is_mlx_like_backend():
            progress_thread = threading.Thread(
                target=self._poll_slots_progress,
                args=(slot_progress_stop_event,),
                daemon=True
            )
            progress_thread.start()

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as error:
            status_code = getattr(error.response, "status_code", None)
            body_preview = ""
            try:
                body_preview = (error.response.text or "")[:500]
            except Exception:
                body_preview = ""
            self._perf_log("native_tool_safe_retry_failed", {
                "status_code": status_code,
                "body_preview": body_preview,
            })
            return (
                "Не удалось безопасно повторить запрос после битого native tool_call. "
                "История очищена от повреждённого вызова; повторите команду ещё раз.",
                "",
                [],
            )
        response.encoding = 'utf-8'

        try:
            if stream:
                parsed = self._parse_streaming_response(
                    response,
                    show_thinking=show_thinking,
                    stop_event=stop_event,
                    slot_progress_stop_event=slot_progress_stop_event,
                    stream_metrics=stream_metrics
                )
                stream_metrics["end"] = time.time()
                timings = self._build_fallback_timings(
                    parsed.get("content", ""),
                    stream_metrics,
                    parsed.get("timings"),
                    parsed.get("usage")
                )
                self._update_exact_context_from_timings(timings)
                self.last_generation_timings = timings
                self._log_timings(timings, tag="retry_timings")
                assistant_content = parsed.get("content", "")
                reasoning_content = parsed.get("reasoning_content", "")
            else:
                data = response.json()
                stream_metrics["end"] = time.time()
                message = data.get("choices", [{}])[0].get("message", {})
                timings = self._build_fallback_timings(
                    message.get("content", ""),
                    stream_metrics,
                    data.get("timings"),
                    data.get("usage")
                )
                self._update_exact_context_from_timings(timings)
                self.last_generation_timings = timings
                self._log_timings(timings, tag="retry_timings")
                assistant_content = message.get("content", "")
                reasoning_content = message.get("reasoning_content", "")
        finally:
            slot_progress_stop_event.set()
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

        # Убираем XML-разметку tool_call из видимого текста, чтобы она не попала
        # в финальный ответ пользователю. Очищаем и reasoning_content, потому что
        # некоторые бэкенды (MTPLX/MLX) могут писать ответ/инструменты туда.
        assistant_content = self._strip_xml_tool_calls(assistant_content)
        reasoning_content = self._strip_xml_tool_calls(reasoning_content)
        return assistant_content, reasoning_content, tool_calls

    def send_message(self, content: str, image_path: Optional[str] = None,
                     stream: bool = True, show_thinking: bool = True,
                     image_urls: Optional[List[str]] = None):
        """Отправить сообщение агенту"""
        self.clear_stop_request()
        # Сбрасываем историю неудачных вызовов инструментов для нового сообщения
        self._failed_tool_attempts = []
        # Сбрасываем защиту от зацикливания
        self._tool_attempt_counts = {}
        self._recent_tool_fingerprints.clear()
        self._visible_content_history.clear()
        self._invalidate_context_usage()

        # Keep the model aware of long-running processes and the active plan on every new user turn.
        # This state is intentionally refreshed here, after the previous turn's
        # tools may have started or stopped a process or moved the plan forward.
        self.messages[0]["content"] = self._build_augmented_system_prompt()

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

        # Обрезаем историю с запасом под новый запрос.
        # Лимит берём из активного пресета, оставляя ~10% на служебные токены.
        history_budget = max(1024, int(self.context_size - self.max_tokens - max(1024, self.context_size * 0.05)))
        self._trim_history(max_tokens=history_budget)

        # Планирование больше не форсируется автоматически. Модель сама решает,
        # вызывать create_plan или нет, на основе system prompt.

        # Агентский цикл
        iteration = 0
        tool_calls_history = []
        last_visible_content = ""
        stopped_by_user = False

        while self.max_iterations <= 0 or iteration < self.max_iterations:
            if self.stop_requested():
                stopped_by_user = True
                break

            iteration += 1
            UI.print_agent_status(iteration, self.max_iterations)
            self._normalize_trailing_assistant_messages()
            # Не обрезаем историю между итерациями одной задачи: агент должен
            # видеть всю цепочку своих tool-вызовов и полученных результатов.
            self._invalidate_context_usage()

            # Параметры запроса (гиперпараметры берутся из активного пресета)
            payload = {
                "messages": self._build_server_safe_messages(),
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "min_p": self.min_p,
                "repeat_penalty": self.repeat_penalty,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty,
                "penalty_last_n": self.penalty_last_n,
                "stream": stream,
                "tools": self.get_active_tools_definition(),
                "tool_choice": "auto"
            }
            if stream:
                # Запрашиваем usage в финальном чанке — многие OpenAI-совместимые
                # серверы (MLX/optiq, vLLM и др.) отдают точное число токенов.
                payload["stream_options"] = {"include_usage": True}
            payload = self._prepare_payload_for_backend(payload)
            self._log_request(payload, tag="chat_request")

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
                    last_visible_content = self._strip_xml_tool_calls(
                        self._strip_thinking_tags(assistant_content.strip())
                    )

                # Tool-only iterations are valid progress: the model can spend
                # several turns inspecting files or running commands without
                # producing visible assistant text. Do not mistake that for a
                # stalled agent before the tool call is executed.
                pending_xml_calls = []
                if not tool_calls and reasoning_content:
                    pending_xml_calls = self.parse_xml_tool_calls(self._strip_thinking_tags(reasoning_content))
                if not pending_xml_calls and not tool_calls and assistant_content:
                    pending_xml_calls = self.parse_xml_tool_calls(self._strip_thinking_tags(assistant_content))
                pending_json_call = None
                if not tool_calls and not pending_xml_calls:
                    pending_json_call = self.parse_tool_call(assistant_content) or self.parse_tool_call(reasoning_content)

                if pending_xml_calls:
                    tool_calls = pending_xml_calls
                if tool_calls or pending_json_call:
                    self._visible_content_history.clear()
                else:
                    self._record_visible_content(last_visible_content)
                    if self._detect_stagnation(window=5):
                        final_content = last_visible_content or "Генерация остановлена: агент застрял в цикле без прогресса."
                        self.messages.append({"role": "assistant", "content": final_content})
                        self.clear_stop_request()
                        yield {
                            "type": "final",
                            "content": final_content,
                            "content_clean": last_visible_content or "",
                            "timings": self.last_generation_timings,
                            "iterations": iteration
                        }
                        return

                AnimationManager.stop()

                if self.stop_requested():
                    stopped_by_user = True
                    break

                # Вывод мышления уже был выполнен потоково в _parse_streaming_response
                # Для не-streaming режима выводим мышление здесь
                if not stream and show_thinking and reasoning_content:
                    UI.print_streaming_thinking_block(self._strip_xml_tool_calls(reasoning_content))

                # XML-вызовы были проверены до защиты стагнации; оставляем
                # fallback для ответов, которые меняют формат на этом шаге.
                if not tool_calls and reasoning_content:
                    tool_calls = self.parse_xml_tool_calls(self._strip_thinking_tags(reasoning_content))
                if not tool_calls and assistant_content:
                    tool_calls = self.parse_xml_tool_calls(self._strip_thinking_tags(assistant_content))

                if tool_calls:
                    # Защита от зацикливания: если модель повторяет один и тот же вызов
                    looping_tool = self._is_agent_looping(tool_calls)
                    if looping_tool:
                        final_content = last_visible_content or (
                            f"Обнаружено повторяющееся вызов `{looping_tool}`. "
                            "Завершаю работу, чтобы избежать бесконечного цикла."
                        )
                        self.messages.append({"role": "assistant", "content": final_content})
                        self.clear_stop_request()
                        yield {
                            "type": "final",
                            "content": final_content,
                            "content_clean": final_content,
                            "timings": self.last_generation_timings,
                            "iterations": iteration
                        }
                        return

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

                        self._record_tool_attempt(tool_name, args)

                        # Показываем вызов инструмента и запускаем постоянную анимацию
                        tool_stop_event = UI.print_tool_call(tool_name, args, iteration, tool_call_id=tool_call_id)
                        hidden_count = tc.get("_hidden_count", 0)

                        # Выполняем инструмент в worker-thread, а анимацию держим в главном потоке
                        result = self.execute_tool_with_animation(tool_name, args, hidden_count=hidden_count)
                        UI.print_tool_result(tool_name, result, iteration, tool_stop_event)

                        if self.stop_requested():
                            stopped_by_user = True

                        # Если изменилось состояние, влияющее на системный промпт — обновляем его
                        if result.success and (
                            tool_name in ("create_plan", "update_plan", "set_working_directory") or
                            (tool_name == "manage_memory" and args.get("operation", "") in ["write", "append", "clear"])
                        ):
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
                            "content": self._format_tool_result_for_model(tool_name, result)
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
                    self._invalidate_context_usage()
                    tool_calls_history = []
                    continue

                # Проверяем JSON в тексте (fallback режим)
                tool_call = self.parse_tool_call(assistant_content)
                if tool_call:
                    tool_name = tool_call.get("tool", "")
                    args = tool_call.get("args", {})
                    if self._is_looping_tool(tool_name, args, max_repeats=3):
                        final_content = last_visible_content or (
                            f"Обнаружено повторяющееся вызов `{tool_name}`. "
                            "Завершаю работу, чтобы избежать бесконечного цикла."
                        )
                        self.messages.append({"role": "assistant", "content": final_content})
                        self.clear_stop_request()
                        yield {
                            "type": "final",
                            "content": final_content,
                            "content_clean": final_content,
                            "timings": self.last_generation_timings,
                            "iterations": iteration
                        }
                        return

                    self._record_tool_attempt(tool_name, args)
                    tool_call_id = f"call_{iteration}_fallback"
                    args_str = json.dumps(args, ensure_ascii=False)

                    # Показываем вызов инструмента и запускаем постоянную анимацию
                    tool_stop_event = UI.print_tool_call(tool_name, args, iteration, tool_call_id=tool_call_id)

                    # Выполняем инструмент в worker-thread, а анимацию держим в главном потоке
                    result = self.execute_tool_with_animation(tool_name, args, hidden_count=0)
                    UI.print_tool_result(tool_name, result, iteration, tool_stop_event)

                    if self.stop_requested():
                        stopped_by_user = True

                    # Если изменилось состояние, влияющее на системный промпт — обновляем его
                    if result.success and (
                        tool_name in ("create_plan", "update_plan", "set_working_directory") or
                        (tool_name == "manage_memory" and args.get("operation", "") in ["write", "append", "clear"])
                    ):
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
                        "content": self._format_tool_result_for_model(tool_name, result)
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
                                    "content": f"Результат {tool_name}: {self._format_tool_result_for_model(tool_name, result)}"
                                })
                        else:
                            self.messages.append({
                                "role": "user",
                                "content": f"Результат {tool_name}: {self._format_tool_result_for_model(tool_name, result)}"
                            })
                    else:
                        self.messages.append({
                            "role": "user",
                            "content": f"Результат {tool_name}: {self._format_tool_result_for_model(tool_name, result)}"
                        })
                    if stopped_by_user:
                        break
                    continue

                # Если нет tool_calls — это финальный ответ
                # Если assistant_content пустой, используем reasoning_content (мысли) как финальный ответ
                final_content = self._strip_xml_tool_calls(
                    self._strip_thinking_tags(assistant_content.strip())
                ) if assistant_content else ""
                if not final_content and reasoning_content:
                    # Модель написала ответ в мыслях, а не в финальном ответе
                    final_content = self._strip_xml_tool_calls(
                        self._strip_thinking_tags(reasoning_content.strip())
                    )

                # Защита от стагнации: несколько итераций подряд без нового видимого текста
                self._record_visible_content(final_content)
                if self._detect_stagnation(window=4):
                    stagnation_msg = (
                        "\n\n_(Генерация остановлена: несколько итераций не принесли нового результата.)_"
                    )
                    final_content = (final_content or "") + stagnation_msg

                self.messages.append({"role": "assistant", "content": final_content})

                self.clear_stop_request()
                yield {
                    "type": "final",
                    "content": final_content,
                    "content_clean": final_content,
                    "timings": self.last_generation_timings,
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
                "content_clean": last_visible_content,
                "iterations": iteration
            }
            return

        # Достигнут лимит итераций: сообщаем пользователю и отдаём накопленное
        limit_note = "\n\n_(Достигнут лимит итераций агента; ответ может быть неполным.)_"
        final_content = (last_visible_content or "") + limit_note
        if final_content.strip():
            self.messages.append({"role": "assistant", "content": final_content})
        yield {
            "type": "final",
            "content": final_content,
            "content_clean": last_visible_content or "",
            "iterations": iteration
        }
