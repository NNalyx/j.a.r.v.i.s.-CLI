import json
import base64
import atexit
import mimetypes
import os
import queue
import re
import secrets
import sys
import threading
import time
import uuid
import webbrowser
from copy import deepcopy
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from PIL import Image, ImageDraw

try:
    import spacy
except ImportError:
    spacy = None

try:
    import pytextrank  # noqa: F401
except ImportError:
    pytextrank = None

import config_manager
from jarvis_core import state

from jarvis_cli_gui import (
    AnimationManager,
    DEFAULT_TRANSCRIPTION_BACKEND_KEY,
    MULTIMODAL_TOOL_NAMES,
    QwenAgentApp,
    TTS,
    TOOLS_DEFINITION,
    UI,
    VOICE_AVAILABLE,
    reload_llama_server_presets,
)

try:
    from jarvis_voice import LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY, WAKE_WORD, get_transcription_backend_catalog
except ImportError:
    LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY = "vosk_large"
    WAKE_WORD = "пятница"

    def get_transcription_backend_catalog(selected_key=None):
        return []

try:
    import webview
except ImportError:
    webview = None

try:
    from jarvis_tools.telegram_account import get_manager as get_telegram_account_manager
except ImportError:
    def get_telegram_account_manager():
        return None


def ensure_utf8_console():
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


ensure_utf8_console()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = BASE_DIR  # Все файлы теперь в одной папке
CHAT_STORAGE_DIR = os.path.join(BASE_DIR, "jarvis_chats")
HOST = "127.0.0.1"
PORT = 8765
WINDOW_ICON_PATH = os.path.join(BASE_DIR, "jarvis_window_icon.ico")
WINDOW_TITLE = "Jarvis Desktop"
TITLE_MODE_AUTO = "auto"
TITLE_MODE_MANUAL = "manual"
TITLE_MODEL_CANDIDATES = (
    "ru_core_news_md",
    "ru_core_news_sm",
    "xx_ent_wiki_sm",
)
TITLE_MAX_LENGTH = 64
TITLE_MAX_WORDS = 8
TITLE_GENERIC_WORDS = {
    "привет", "здравствуй", "здравствуйте", "хай", "hello", "hi", "ок", "okay",
    "ладно", "понял", "поняла", "спасибо", "thanks", "thank you", "да", "нет",
    "смотри", "слушай", "так", "вот", "ну",
}
TITLE_WEAK_PHRASES = {
    "новый чат", "пока без сообщений", "сообщение", "переписка", "пользователь",
    "ассистент", "chat", "title", "как дела", "как ты", "что делаешь",
}
TITLE_RECOMMENDATION_OBJECTS = {
    "фильмы": "фильмов",
    "фильм": "фильмов",
    "кино": "фильмов",
    "сериалы": "сериалов",
    "сериал": "сериалов",
    "книги": "книг",
    "книга": "книг",
    "музыку": "музыки",
    "музыка": "музыки",
}
TITLE_ACTION_PATTERNS = (
    (re.compile(r"\b(исправ\w*|почин\w*|чин\w*)\b", re.IGNORECASE), "Исправить"),
    (re.compile(r"\b(улучш\w*|доработ\w*|оптимиз\w*)\b", re.IGNORECASE), "Улучшить"),
    (re.compile(r"\b(добав\w*|внедр\w*)\b", re.IGNORECASE), "Добавить"),
    (re.compile(r"\b(сдел\w*|созда\w*|собер\w*|напиш\w*)\b", re.IGNORECASE), "Сделать"),
    (re.compile(r"\b(откр\w*|запуст\w*)\b", re.IGNORECASE), "Открыть"),
    (re.compile(r"\b(нажм\w*|клик\w*)\b", re.IGNORECASE), "Нажать"),
    (re.compile(r"\b(подключ\w*)\b", re.IGNORECASE), "Подключить"),
    (re.compile(r"\b(удал\w*|очист\w*)\b", re.IGNORECASE), "Удалить"),
    (re.compile(r"\b(настро\w*)\b", re.IGNORECASE), "Настроить"),
    (re.compile(r"\b(проверь\w*|провер\w*|посмотр\w*)\b", re.IGNORECASE), "Проверить"),
    (re.compile(r"\b(найд\w*|поищ\w*)\b", re.IGNORECASE), "Найти"),
    (re.compile(r"\b(обнов\w*)\b", re.IGNORECASE), "Обновить"),
    (re.compile(r"\b(переимен\w*)\b", re.IGNORECASE), "Переименовать"),
)

title_nlp = None
title_nlp_initialized = False

desktop_app = QwenAgentApp(
    interactive_prompts=False,
    init_voice=False,
    init_telegram=False
)
desktop_app.tts_disable_locked = False
chat_lock = threading.RLock()
tts_lock = threading.Lock()
voice_lock = threading.Lock()
active_stream_lock = threading.Lock()
active_stream_bridge = None
active_chat_id: Optional[str] = None

# User-prompt state for synchronous ask_user tool
pending_user_prompts: Dict[str, threading.Event] = {}
pending_user_answers: Dict[str, str] = {}
_user_prompt_lock = threading.Lock()


def register_user_prompt(question: str, timeout: float = 120.0) -> Optional[str]:
    """Show a modal prompt in the UI and block until the user answers.

    Must be called from within an active chat stream (when active_stream_bridge
    is set). If the stream is cancelled, the wait is interrupted.
    """
    prompt_id = str(uuid.uuid4())
    event = threading.Event()
    with _user_prompt_lock:
        pending_user_prompts[prompt_id] = event
        pending_user_answers.pop(prompt_id, None)

    bridge = active_stream_bridge
    if bridge is None:
        with _user_prompt_lock:
            pending_user_prompts.pop(prompt_id, None)
        raise RuntimeError("Нет активного чата для показа вопроса")

    bridge.push("user_prompt", prompt_id=prompt_id, question=question)

    try:
        # Wait for the user response or until the stream bridge is cleared.
        deadline = time.time() + max(1.0, float(timeout))
        while time.time() < deadline:
            if event.wait(timeout=0.5):
                break
            # If the stream bridge was replaced/cleared, the generation was
            # cancelled — abort the prompt.
            if active_stream_bridge is not bridge:
                with _user_prompt_lock:
                    pending_user_prompts.pop(prompt_id, None)
                    pending_user_answers.pop(prompt_id, None)
                raise RuntimeError("Генерация отменена — запрос к пользователю прерван")
        else:
            # Timeout
            with _user_prompt_lock:
                pending_user_prompts.pop(prompt_id, None)
                pending_user_answers.pop(prompt_id, None)
            raise TimeoutError("Время ожидания ответа пользователя истекло")

        with _user_prompt_lock:
            answer = pending_user_answers.pop(prompt_id, None)
            pending_user_prompts.pop(prompt_id, None)
        return answer
    except Exception:
        with _user_prompt_lock:
            pending_user_prompts.pop(prompt_id, None)
            pending_user_answers.pop(prompt_id, None)
        raise


# Register the handler so ask_user tool can use the web UI.
state.user_prompt_handler = register_user_prompt

voice_state: Dict[str, Any] = {
    "available": bool(VOICE_AVAILABLE),
    "enabled": False,
    "listening": False,
    "phase": "idle",
    "status": "Голосовая активация выключена",
    "wake_word": WAKE_WORD,
    "overlay_visible": False,
    "live_text": "",
    "final_text": "",
    "final_command_id": 0,
    "backend_key": DEFAULT_TRANSCRIPTION_BACKEND_KEY,
    "backend_label": "Vosk Small RU",
}
main_window = None

app = FastAPI(title="Jarvis Desktop")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Случайный токен для защиты локального API от других процессов/вкладок
API_TOKEN = secrets.token_urlsafe(32)


@app.middleware("http")
async def api_token_middleware(request, call_next):
    """Проверять токен для всех /api/* запросов, кроме health-check."""
    path = request.url.path
    if path.startswith("/api/") and path != "/api/health":
        token = request.headers.get("X-API-Token") or request.query_params.get("token")
        if not token or not secrets.compare_digest(token, API_TOKEN):
            return JSONResponse({"detail": "Invalid or missing API token"}, status_code=403)
    return await call_next(request)


# Middleware для отключения кэша статики в режиме разработки
@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


class ChatRequest(BaseModel):
    message: str
    images: List[str] = Field(default_factory=list)
    chat_id: Optional[str] = None


class CreateChatRequest(BaseModel):
    title: Optional[str] = None


class ChatStateRequest(BaseModel):
    title: Optional[str] = None
    ui_messages: List[Dict[str, Any]] = Field(default_factory=list)


class RenameChatRequest(BaseModel):
    title: str


class StartModelRequest(BaseModel):
    model_key: str


class PresetCreateRequest(BaseModel):
    name: str = "Default"
    llama_server_path: str
    model_path: str
    mmproj_path: str = ""
    mtp_path: str = ""
    context_size: int = 18432
    ngl: int = 99
    port: int = 8080
    make_active: bool = True


class PresetSelectRequest(BaseModel):
    preset_index: int


class PresetDeleteRequest(BaseModel):
    preset_index: int


class PresetToolsRequest(BaseModel):
    preset_index: int
    enabled_tools: List[str]


class TTSSettingsRequest(BaseModel):
    enabled: bool


class VoiceSettingsRequest(BaseModel):
    enabled: bool


class ASRSettingsRequest(BaseModel):
    engine_key: str


class UserResponseRequest(BaseModel):
    prompt_id: str
    answer: str


class TelegramAccountSetupStartRequest(BaseModel):
    api_id: int
    api_hash: str
    phone: str


class TelegramAccountConfirmCodeRequest(BaseModel):
    code: str


class TelegramAccountConfirm2FARequest(BaseModel):
    password: str


def _get_voice_state() -> Dict[str, Any]:
    with voice_lock:
        return dict(voice_state)


def _update_voice_state(**changes) -> Dict[str, Any]:
    with voice_lock:
        voice_state.update(changes)
        return dict(voice_state)


def _get_selected_asr_backend() -> Dict[str, Any]:
    selected_key = getattr(desktop_app, "voice_backend_key", DEFAULT_TRANSCRIPTION_BACKEND_KEY)
    backends = desktop_app.get_voice_backend_options() if hasattr(desktop_app, "get_voice_backend_options") else get_transcription_backend_catalog(selected_key)
    for backend in backends:
        if backend.get("key") == selected_key:
            return dict(backend)
    return {
        "key": selected_key,
        "label": selected_key,
        "description": "",
        "available": False,
        "reason": "Backend не найден",
        "selected": True,
    }


def _ensure_voice_initialized() -> bool:
    if not VOICE_AVAILABLE:
        _update_voice_state(
            available=False,
            enabled=False,
            listening=False,
            phase="error",
            status="Голосовая активация недоступна",
        )
        return False

    if getattr(desktop_app, "voice_activator", None) is not None:
        return True

    try:
        desktop_app._init_voice()
        activator = getattr(desktop_app, "voice_activator", None)
        if activator is None:
            raise RuntimeError("Voice activator was not initialized")

        activator.set_callback(_on_voice_command)
        activator.set_status_callback(_on_voice_status)
        if hasattr(activator, "set_partial_callback"):
            activator.set_partial_callback(_on_voice_partial)
        backend = _get_selected_asr_backend()
        _update_voice_state(
            available=bool(VOICE_AVAILABLE),
            backend_key=backend.get("key", DEFAULT_TRANSCRIPTION_BACKEND_KEY),
            backend_label=backend.get("label", "Vosk Small RU"),
        )
        return True
    except Exception as exc:
        _update_voice_state(
            enabled=False,
            listening=False,
            phase="error",
            status=f"Ошибка голосовой активации: {exc}",
        )
        return False


def _on_voice_status(status: str) -> None:
    phase = "idle"
    overlay_visible = False
    status_lower = str(status or "").lower()
    if "wake word услышан" in status_lower or "говорите команду" in status_lower:
        phase = "capturing"
        overlay_visible = True
        _bring_window_to_front()
    elif "отправляю" in status_lower:
        phase = "submitting"
        overlay_visible = True
    elif "слушаю wake word" in status_lower:
        phase = "armed"
    elif "выключена" in status_lower:
        phase = "idle"

    _update_voice_state(
        listening=bool(getattr(getattr(desktop_app, "voice_activator", None), "is_running", False)),
        status=status,
        phase=phase,
        overlay_visible=overlay_visible,
    )


def _on_voice_partial(text: str) -> None:
    _update_voice_state(
        enabled=bool(getattr(desktop_app, "voice_enabled", False)),
        listening=bool(getattr(getattr(desktop_app, "voice_activator", None), "is_running", False)),
        phase="capturing",
        status="Слушаю команду...",
        overlay_visible=True,
        live_text=str(text or "").strip(),
    )


def _on_voice_command(command: str) -> None:
    current = _get_voice_state()
    _update_voice_state(
        enabled=bool(getattr(desktop_app, "voice_enabled", False)),
        listening=bool(getattr(getattr(desktop_app, "voice_activator", None), "is_running", False)),
        phase="ready_to_submit",
        status="Команда готова к отправке",
        overlay_visible=True,
        live_text=str(command or "").strip(),
        final_text=str(command or "").strip(),
        final_command_id=int(current.get("final_command_id", 0)) + 1,
    )


def _ensure_chat_storage_dir() -> None:
    os.makedirs(CHAT_STORAGE_DIR, exist_ok=True)


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_chat_id(chat_id: Optional[str] = None) -> str:
    candidate = str(chat_id or uuid.uuid4().hex).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", candidate):
        raise HTTPException(status_code=400, detail="Invalid chat id")
    return candidate


def _chat_file_path(chat_id: str) -> str:
    return os.path.join(CHAT_STORAGE_DIR, f"{_safe_chat_id(chat_id)}.json")


def _default_agent_messages() -> List[Dict[str, Any]]:
    desktop_app.agent.refresh_system_prompt()
    return [{"role": "system", "content": desktop_app.agent.system_prompt}]


def _normalize_agent_messages(messages: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    baseline = _default_agent_messages()
    if not isinstance(messages, list) or not messages:
        return baseline

    normalized = deepcopy(messages)
    system_message = baseline[0]
    if not normalized or normalized[0].get("role") != "system":
        normalized.insert(0, system_message)
    else:
        normalized[0]["content"] = system_message["content"]
    return normalized


def _extract_text_from_agent_content(content: Any) -> str:
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return ""

    parts: List[str] = []
    for item in content:
        if isinstance(item, str):
            text = item.strip()
            if text:
                parts.append(text)
            continue

        if not isinstance(item, dict):
            continue

        item_type = str(item.get("type") or "").strip().lower()
        if item_type in {"text", "input_text", "output_text"}:
            text = str(item.get("text") or item.get("content") or "").strip()
        elif "text" in item:
            text = str(item.get("text") or "").strip()
        elif isinstance(item.get("content"), str):
            text = str(item.get("content") or "").strip()
        else:
            text = ""

        if text:
            parts.append(text)

    return "\n".join(parts).strip()


def _format_tool_payload_for_ui(payload: Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return ""
        try:
            payload = json.loads(stripped)
        except Exception:
            return stripped
    try:
        return json.dumps(_make_json_safe(payload), ensure_ascii=False, indent=2)
    except Exception:
        return str(payload)


def _extract_tool_call_name(tool_call: Dict[str, Any]) -> str:
    function_data = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
    return str(function_data.get("name") or tool_call.get("name") or "tool")


def _extract_tool_call_args(tool_call: Dict[str, Any]) -> Any:
    function_data = tool_call.get("function") if isinstance(tool_call.get("function"), dict) else {}
    arguments = function_data.get("arguments", tool_call.get("arguments", {}))
    if isinstance(arguments, str):
        try:
            return json.loads(arguments)
        except Exception:
            return arguments
    return arguments


def _update_agent_tools_from_status(status: Dict[str, Any]) -> None:
    active_index = status.get("active_preset_index")
    presets = status.get("presets", [])
    if active_index is None or not presets or active_index >= len(presets):
        desktop_app.agent.set_enabled_tools(None)
        return

    active_preset = presets[active_index]
    enabled_tools = active_preset.get("enabled_tools")
    if enabled_tools is None:
        enabled_tools = [tool["function"]["name"] for tool in TOOLS_DEFINITION]

    if not active_preset.get("supports_images"):
        enabled_tools = [name for name in enabled_tools if name not in MULTIMODAL_TOOL_NAMES]

    desktop_app.agent.set_enabled_tools(enabled_tools)


def _fallback_ui_messages_from_agent_messages(agent_messages: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    fallback: List[Dict[str, Any]] = []
    pending_tools: Dict[str, Dict[str, Any]] = {}
    current_thinking: Optional[Dict[str, Any]] = None

    def ensure_thinking() -> Dict[str, Any]:
        nonlocal current_thinking
        if current_thinking is None:
            current_thinking = {
                "role": "thinking",
                "expanded": False,
                "buffer": "",
                "timeline": [],
                "activeThoughtId": None,
                "activeToolName": "",
                "toolCount": 0,
                "thoughtCount": 0,
                "startedAt": 0,
                "mode": "done",
                "activityLabel": "",
                "lastEventKind": "tool_result",
            }
            fallback.append(current_thinking)
        return current_thinking

    for entry in agent_messages or []:
        if not isinstance(entry, dict):
            continue

        role = str(entry.get("role") or "").strip().lower()
        if role not in {"user", "assistant", "tool"}:
            continue

        if role == "user":
            body = _extract_text_from_agent_content(entry.get("content"))
            if body.strip():
                fallback.append({"role": "user", "body": body, "images": []})
            current_thinking = None
            pending_tools.clear()
            continue

        if role == "assistant":
            tool_calls = entry.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                thinking = ensure_thinking()
                for index, tool_call in enumerate(tool_calls, start=1):
                    if not isinstance(tool_call, dict):
                        continue
                    tool_id = str(tool_call.get("id") or f"tool-{index}")
                    tool_entry = {
                        "id": tool_id,
                        "type": "tool",
                        "name": _extract_tool_call_name(tool_call),
                        "argsFormatted": _format_tool_payload_for_ui(_extract_tool_call_args(tool_call)),
                        "resultFormatted": "",
                        "images": [],
                        "success": None,
                        "status": "running",
                    }
                    thinking["timeline"].append(tool_entry)
                    pending_tools[tool_id] = tool_entry
                thinking["toolCount"] = len([item for item in thinking["timeline"] if item.get("type") == "tool"])

            body = _extract_text_from_agent_content(entry.get("content"))
            if body.strip():
                fallback.append({"role": "assistant", "body": body, "images": []})
                current_thinking = None
                pending_tools.clear()
            continue

        tool_call_id = str(entry.get("tool_call_id") or "")
        tool_entry = pending_tools.get(tool_call_id) if tool_call_id else None
        if tool_entry is None:
            thinking = ensure_thinking()
            tool_entry = {
                "id": tool_call_id or f"tool-{len(thinking['timeline']) + 1}",
                "type": "tool",
                "name": str(entry.get("name") or "tool"),
                "argsFormatted": "",
                "resultFormatted": "",
                "images": [],
                "success": None,
                "status": "running",
            }
            thinking["timeline"].append(tool_entry)
            if tool_call_id:
                pending_tools[tool_call_id] = tool_entry

        content = _extract_text_from_agent_content(entry.get("content"))
        tool_entry["resultFormatted"] = _format_tool_payload_for_ui(content)
        tool_entry["success"] = not str(content).lstrip().startswith("{\"success\": false")
        tool_entry["status"] = "done" if tool_entry["success"] else "error"
        ensure_thinking()["lastEventKind"] = "tool_result"

    return fallback


def _has_incomplete_ui_tail(ui_messages: List[Dict[str, Any]]) -> bool:
    if not ui_messages:
        return False
    tail = ui_messages[-1]
    if tail.get("role") == "assistant" and not str(tail.get("body") or "").strip():
        return True
    if tail.get("role") == "thinking" and str(tail.get("mode") or "") != "done":
        return True
    if len(ui_messages) >= 2:
        previous = ui_messages[-2]
        return (
            previous.get("role") == "thinking"
            and str(previous.get("mode") or "") != "done"
            and tail.get("role") == "assistant"
            and not str(tail.get("body") or "").strip()
        )
    return False


def _ui_restore_score(ui_messages: List[Dict[str, Any]]) -> int:
    score = 0
    for entry in ui_messages:
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        if role in {"user", "assistant", "system", "tool"} and str(entry.get("body") or "").strip():
            score += 1
        elif role == "thinking":
            timeline = entry.get("timeline") if isinstance(entry.get("timeline"), list) else []
            score += len(timeline)
    return score


def _normalize_ui_messages(
    ui_messages: Optional[List[Dict[str, Any]]],
    agent_messages: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for entry in ui_messages or []:
        if not isinstance(entry, dict):
            continue

        role = str(entry.get("role") or "system").strip().lower() or "system"
        if role == "thinking":
            normalized.append({
                "role": "thinking",
                "expanded": bool(entry.get("expanded")),
                "buffer": str(entry.get("buffer") or entry.get("body") or entry.get("content") or ""),
                "timeline": deepcopy(entry.get("timeline")) if isinstance(entry.get("timeline"), list) else [],
                "activeThoughtId": entry.get("activeThoughtId"),
                "activeToolName": str(entry.get("activeToolName") or ""),
                "toolCount": int(entry.get("toolCount") or 0),
                "thoughtCount": int(entry.get("thoughtCount") or 0),
                "startedAt": int(entry.get("startedAt") or 0),
                "mode": str(entry.get("mode") or "done"),
                "activityLabel": str(entry.get("activityLabel") or ""),
                "lastEventKind": str(entry.get("lastEventKind") or "thinking"),
            })
            continue

        images = entry.get("images") if isinstance(entry.get("images"), list) else []
        body = str(entry.get("body") or entry.get("content") or entry.get("text") or "")
        if role in {"assistant", "system", "tool"} and not body.strip() and not images:
            continue
        normalized.append({
            "role": role,
            "body": body,
            "images": [str(image) for image in images if isinstance(image, str) and image.strip()],
        })

    fallback = _fallback_ui_messages_from_agent_messages(agent_messages)
    if normalized and not _has_incomplete_ui_tail(normalized):
        return normalized
    if fallback and _ui_restore_score(fallback) >= _ui_restore_score(normalized):
        return fallback
    return normalized


def _extract_message_preview(ui_messages: Optional[List[Dict[str, Any]]]) -> str:
    for entry in reversed(ui_messages or []):
        if not isinstance(entry, dict):
            continue
        role = entry.get("role")
        if role == "thinking":
            timeline = entry.get("timeline") or []
            for timeline_entry in reversed(timeline):
                if isinstance(timeline_entry, dict) and timeline_entry.get("type") == "thought":
                    content = str(timeline_entry.get("content", "")).strip()
                    if content:
                        return content[:160]
            continue

        content = str(entry.get("body", "")).strip()
        if content:
            return content[:160]
    return ""


def _normalize_title_mode(value: Optional[str]) -> str:
    return TITLE_MODE_MANUAL if str(value or "").strip().lower() == TITLE_MODE_MANUAL else TITLE_MODE_AUTO


def _clean_title_text(text: str, fallback: str = "Новый чат") -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    normalized = normalized.strip(" .,:;!?-–—_/'\"()[]{}")
    if not normalized:
        return fallback
    words = normalized.split()
    if len(words) > TITLE_MAX_WORDS:
        normalized = " ".join(words[:TITLE_MAX_WORDS])
    if len(normalized) > TITLE_MAX_LENGTH:
        cut = normalized[:TITLE_MAX_LENGTH].rsplit(" ", 1)[0].strip()
        normalized = cut or normalized[:TITLE_MAX_LENGTH].strip()
    return normalized.strip(" .,:;!?-–—_/'\"()[]{}") or fallback


def _strip_title_noise(text: str) -> str:
    value = str(text or "")
    value = re.sub(r"```.*?```", " ", value, flags=re.DOTALL)
    value = re.sub(r"`[^`]+`", " ", value)
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"@?[A-Za-z]:\\[^\s]+", " ", value)
    value = re.sub(r"\b[\w.-]+\.(py|js|ts|tsx|jsx|json|html|css|exe|dll)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _normalize_title_seed(text: str) -> str:
    value = _strip_title_noise(text)
    value = re.sub(r"^[,.\s:;!?–—_-]+", "", value)
    leading_patterns = (
        r"^(привет|здравствуй|здравствуйте|хай|hello|hi)\b[,!\s-]*",
        r"^(так|ну|вот|смотри|слушай|короче|ладно)\b[,!\s-]*",
        r"^(я\s+хочу\s+чтобы\s+ты|хочу\s+чтобы\s+ты|можешь\s+ли\s+ты|можешь|пожалуйста|давай)\b[,!\s-]*",
        r"^(для\s+начала|сейчас|теперь)\b[,!\s-]*",
    )
    changed = True
    while changed:
        changed = False
        for pattern in leading_patterns:
            next_value = re.sub(pattern, "", value, flags=re.IGNORECASE).strip()
            if next_value != value:
                value = next_value
                changed = True
    value = re.sub(r"\b(так сказать|скажем|типа|как бы|ну то есть|то есть)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(нахуй|блин|короче)\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _split_title_sentences(text: str) -> List[str]:
    value = _normalize_title_seed(text)
    parts = re.split(r"[\n\r.!?]+|(?<=\S)\s+[;]+", value)
    sentences = [part.strip(" ,:;!?-–—") for part in parts if part.strip(" ,:;!?-–—")]
    return sentences or ([value] if value else [])


def _is_generic_title_candidate(text: str) -> bool:
    value = _clean_title_text(text, fallback="").lower()
    if not value:
        return True
    compact = re.sub(r"\s+", " ", value).strip()
    if compact in TITLE_WEAK_PHRASES or compact in TITLE_GENERIC_WORDS:
        return True
    words = compact.split()
    return len(words) <= 2 and all(word in TITLE_GENERIC_WORDS for word in words)


def _trim_title_object(text: str) -> str:
    value = _normalize_title_seed(text)
    value = re.sub(r"^(это|эту|этот|эти|с|со|по|про|насчет|на тему)\b\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(пожалуйста|если можно)\b", " ", value, flags=re.IGNORECASE)
    value = re.split(
        r"\s+\bи\s+(?:нажм\w*|клик\w*|откр\w*|запуст\w*|подключ\w*|проверь\w*|сдел\w*|добав\w*|исправ\w*)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    value = re.sub(r"\s+", " ", value).strip(" ,:;!?-–—")
    return _clean_title_text(value, fallback="")


def _build_action_title(sentence: str) -> str:
    value = _normalize_title_seed(sentence)
    lower_value = value.lower()

    recommendation_match = re.search(
        r"\b(?:какие|какой|какую|что|чего)?\s*([A-Za-zА-Яа-яЁё0-9 _-]{3,48}?)\s+(?:посовету\w*|порекоменду\w*)\b",
        value,
        flags=re.IGNORECASE,
    )
    if recommendation_match:
        subject = _trim_title_object(recommendation_match.group(1))
        if subject:
            subject = TITLE_RECOMMENDATION_OBJECTS.get(subject.lower(), subject.lower())
            return _clean_title_text(f"Рекомендации {subject.lower()}", fallback="")
        return "Рекомендации"

    if re.search(r"\b(?:посовету\w*|порекоменду\w*)\b", value, flags=re.IGNORECASE):
        obj = _trim_title_object(re.sub(r"\b(?:посовету\w*|порекоменду\w*)\b", "", value, flags=re.IGNORECASE))
        if obj:
            obj = TITLE_RECOMMENDATION_OBJECTS.get(obj.lower(), obj.lower())
            return _clean_title_text(f"Рекомендации {obj.lower()}", fallback="")
        return "Рекомендации"

    if "назван" in lower_value and "чат" in lower_value:
        return "Улучшить названия чатов"
    if "послед" in lower_value and "сохран" in lower_value and "чат" in lower_value:
        return "Исправить последний сохраненный чат"
    if "чат" in lower_value and ("сохран" in lower_value or "истори" in lower_value) and "глюч" in lower_value:
        return "Исправить сохранение чатов"

    value = re.sub(
        r"^(первая|вторая|третья|следующая)?\s*проблема\s*[-–—:]?\s*(это\s+)?",
        "Проблема ",
        value,
        flags=re.IGNORECASE,
    ).strip()

    for pattern, action in TITLE_ACTION_PATTERNS:
        match = pattern.search(value)
        if not match:
            continue
        obj = _trim_title_object(value[match.end():])
        if obj:
            return _clean_title_text(f"{action} {obj}", fallback="")
        return action

    if re.search(r"\b(проблема|ошибка|баг|глюк)\b", value, flags=re.IGNORECASE):
        return _clean_title_text(value, fallback="")

    return _clean_title_text(value, fallback="")


def _score_title_candidate(candidate: str, source_role: str = "user") -> int:
    if _is_generic_title_candidate(candidate):
        return -100
    value = candidate.lower()
    score = 10 if source_role == "user" else 2
    if any(pattern.search(candidate) for pattern, _action in TITLE_ACTION_PATTERNS):
        score += 12
    if value.startswith("рекомендации"):
        score += 18
    if any(word in value for word in ("чат", "сообщ", "сохран", "назван", "прилож", "кноп", "vpn", "впн")):
        score += 6
    if 2 <= len(candidate.split()) <= TITLE_MAX_WORDS:
        score += 4
    if len(candidate) > TITLE_MAX_LENGTH:
        score -= 6
    if any(word in value for word in ("несколько проблем", "чем могу помочь", "помочь", "рад что")):
        score -= 10
    return score


def _derive_rule_based_title(ui_messages: Optional[List[Dict[str, Any]]], fallback: str = "Новый чат") -> str:
    best_title = ""
    best_score = -101
    seen_user_messages = 0

    for role, body in _iter_title_messages(ui_messages):
        if role != "user":
            continue
        seen_user_messages += 1
        if seen_user_messages > 6:
            break
        for sentence_index, sentence in enumerate(_split_title_sentences(body)):
            candidate = _build_action_title(sentence)
            if not candidate:
                continue
            score = _score_title_candidate(candidate, role)
            score -= sentence_index
            if score > best_score:
                best_title = candidate
                best_score = score

    if best_score > -100 and best_title:
        return _clean_title_text(best_title, fallback=fallback)
    return fallback


def _iter_title_messages(ui_messages: Optional[List[Dict[str, Any]]]):
    for entry in ui_messages or []:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        body = _strip_title_noise(entry.get("body") or "")
        if body:
            yield role, body


def _derive_first_user_title(ui_messages: Optional[List[Dict[str, Any]]], fallback: str = "Новый чат") -> str:
    for role, body in _iter_title_messages(ui_messages):
        if role != "user":
            continue
        for sentence in _split_title_sentences(body):
            candidate = _build_action_title(sentence)
            if candidate and not _is_generic_title_candidate(candidate):
                return _clean_title_text(candidate, fallback=fallback)
    return fallback


def _get_title_nlp():
    global title_nlp
    global title_nlp_initialized

    if title_nlp_initialized:
        return title_nlp

    title_nlp_initialized = True
    if spacy is None or pytextrank is None:
        return None

    for model_name in TITLE_MODEL_CANDIDATES:
        try:
            candidate = spacy.load(model_name)
        except Exception:
            continue
        try:
            if "textrank" not in candidate.pipe_names:
                candidate.add_pipe("textrank")
        except Exception:
            return None
        title_nlp = candidate
        return title_nlp

    return None


def _build_title_source_text(ui_messages: Optional[List[Dict[str, Any]]], max_messages: int = 6, max_chars: int = 1800) -> str:
    chunks: List[str] = []
    current_size = 0

    for index, (role, body) in enumerate(_iter_title_messages(ui_messages)):
        if index >= max_messages or current_size >= max_chars:
            break
        label = "Пользователь" if role == "user" else "Ассистент"
        snippet = body[:400].strip()
        if not snippet:
            continue
        chunk = f"{label}: {snippet}"
        chunks.append(chunk)
        current_size += len(chunk)

    return "\n".join(chunks)


def _is_valid_generated_title(candidate: str) -> bool:
    value = _clean_title_text(candidate, fallback="")
    if len(value) < 4:
        return False
    if _is_generic_title_candidate(value):
        return False
    if not re.search(r"[A-Za-zА-Яа-яЁё]", value):
        return False
    if value.lower() in {"пользователь", "ассистент", "chat", "title", "сообщение", "переписка", "чат"}:
        return False
    return True


def _derive_pytextrank_title(ui_messages: Optional[List[Dict[str, Any]]], fallback: str) -> str:
    nlp = _get_title_nlp()
    if nlp is None:
        return fallback

    source_text = _build_title_source_text(ui_messages)
    if not source_text:
        return fallback

    try:
        doc = nlp(source_text)
    except Exception:
        return fallback

    phrases = getattr(getattr(doc, "_", None), "phrases", []) or []
    for phrase in phrases:
        candidate = _clean_title_text(getattr(phrase, "text", ""), fallback="")
        if _is_valid_generated_title(candidate):
            return candidate

    try:
        for chunk in doc.noun_chunks:
            candidate = _clean_title_text(getattr(chunk, "text", ""), fallback="")
            if _is_valid_generated_title(candidate):
                return candidate
    except Exception:
        pass

    return fallback


def _derive_chat_title(ui_messages: Optional[List[Dict[str, Any]]], fallback: str = "Новый чат") -> str:
    rule_title = _derive_rule_based_title(ui_messages, fallback=fallback)
    if _is_valid_generated_title(rule_title):
        return rule_title
    return _derive_first_user_title(ui_messages, fallback=fallback)


def _load_chat_record(chat_id: str) -> Dict[str, Any]:
    path = _chat_file_path(chat_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Chat not found")

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    agent_messages = _normalize_agent_messages(data.get("agent_messages"))
    ui_messages = _normalize_ui_messages(data.get("ui_messages"), agent_messages)
    data["id"] = _safe_chat_id(data.get("id") or chat_id)
    data["ui_messages"] = ui_messages
    data["agent_messages"] = agent_messages
    data["title_mode"] = _normalize_title_mode(data.get("title_mode"))
    data["preview"] = _extract_message_preview(ui_messages)
    existing_title = str(data.get("title") or "").strip()
    if data["title_mode"] == TITLE_MODE_AUTO and (not existing_title or _is_generic_title_candidate(existing_title)):
        data["title"] = _derive_chat_title(ui_messages) or "Новый чат"
    else:
        data["title"] = existing_title or _derive_chat_title(ui_messages) or "Новый чат"
    return data


def _write_chat_record(record: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_chat_storage_dir()
    record = deepcopy(record)
    record["id"] = _safe_chat_id(record.get("id"))
    record["agent_messages"] = _normalize_agent_messages(record.get("agent_messages"))
    ui_messages = _normalize_ui_messages(record.get("ui_messages"), record["agent_messages"])
    record["ui_messages"] = ui_messages
    record["title_mode"] = _normalize_title_mode(record.get("title_mode"))
    record["preview"] = _extract_message_preview(ui_messages)
    existing_title = str(record.get("title") or "").strip()
    if record["title_mode"] == TITLE_MODE_AUTO and (not existing_title or _is_generic_title_candidate(existing_title)):
        record["title"] = _derive_chat_title(ui_messages) or "Новый чат"
    else:
        record["title"] = existing_title or _derive_chat_title(ui_messages) or "Новый чат"
    record["created_at"] = str(record.get("created_at") or _utc_now_iso())
    record["updated_at"] = str(record.get("updated_at") or _utc_now_iso())
    if ui_messages:
        record["last_message_at"] = str(record.get("last_message_at") or record["updated_at"])
    else:
        record["last_message_at"] = str(record.get("last_message_at") or record["updated_at"])

    path = _chat_file_path(record["id"])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2)
    return record


def _chat_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": record["id"],
        "title": record.get("title", "Новый чат"),
        "preview": record.get("preview", ""),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "last_message_at": record.get("last_message_at"),
    }


def _json_fingerprint(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return repr(value)


def _list_chat_summaries() -> List[Dict[str, Any]]:
    _ensure_chat_storage_dir()
    summaries: List[Dict[str, Any]] = []
    for file_name in os.listdir(CHAT_STORAGE_DIR):
        if not file_name.endswith(".json"):
            continue
        try:
            record = _load_chat_record(file_name[:-5])
            summaries.append(_chat_summary(record))
        except Exception:
            continue

    summaries.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return summaries


def _activate_chat(chat_id: str) -> Dict[str, Any]:
    global active_chat_id

    record = _load_chat_record(chat_id)
    with chat_lock:
        desktop_app.agent.messages = deepcopy(record["agent_messages"])
        active_chat_id = record["id"]
    return record


def _create_chat_record(title: Optional[str] = None) -> Dict[str, Any]:
    now = _utc_now_iso()
    next_title = str(title or "").strip()
    is_manual_title = bool(next_title and next_title != "Новый чат")
    record = {
        "id": uuid.uuid4().hex,
        "title": next_title or "Новый чат",
        "title_mode": TITLE_MODE_MANUAL if is_manual_title else TITLE_MODE_AUTO,
        "created_at": now,
        "updated_at": now,
        "last_message_at": now,
        "ui_messages": [],
        "agent_messages": _default_agent_messages(),
    }
    record = _write_chat_record(record)
    return _activate_chat(record["id"])


def _save_chat_state(chat_id: str, ui_messages: Optional[List[Dict[str, Any]]] = None, title: Optional[str] = None) -> Dict[str, Any]:
    global active_chat_id

    chat_id = _safe_chat_id(chat_id)
    try:
        existing = _load_chat_record(chat_id)
    except HTTPException:
        existing = {
            "id": chat_id,
            "created_at": _utc_now_iso(),
            "ui_messages": [],
            "agent_messages": _default_agent_messages(),
        }

    previous_ui_messages = deepcopy(existing.get("ui_messages", []))
    previous_title = str(existing.get("title") or "")
    previous_agent_messages = deepcopy(existing.get("agent_messages", []))
    existing["title_mode"] = _normalize_title_mode(existing.get("title_mode"))

    if ui_messages is not None:
        existing["ui_messages"] = _normalize_ui_messages(ui_messages, existing.get("agent_messages"))
    if title is not None:
        if existing["title_mode"] == TITLE_MODE_MANUAL:
            existing["title"] = _clean_title_text(title)

    if active_chat_id == chat_id:
        with chat_lock:
            existing["agent_messages"] = deepcopy(desktop_app.agent.messages)

    ui_changed = _json_fingerprint(previous_ui_messages) != _json_fingerprint(existing.get("ui_messages", []))
    if existing["title_mode"] == TITLE_MODE_AUTO:
        next_title = _derive_chat_title(existing.get("ui_messages"), fallback="")
        if _is_valid_generated_title(next_title) and (ui_changed or _is_generic_title_candidate(existing.get("title", ""))):
            existing["title"] = next_title
    title_changed = previous_title != str(existing.get("title") or "")
    agent_changed = _json_fingerprint(previous_agent_messages) != _json_fingerprint(existing.get("agent_messages", []))

    if ui_changed or title_changed or agent_changed:
        existing["updated_at"] = _utc_now_iso()
        if ui_changed and existing.get("ui_messages"):
            existing["last_message_at"] = existing["updated_at"]

    record = _write_chat_record(existing)
    return record


def _rename_chat(chat_id: str, title: str) -> Dict[str, Any]:
    record = _load_chat_record(chat_id)
    next_title = str(title or "").strip() or "Новый чат"
    if next_title != str(record.get("title") or ""):
        record["title"] = next_title
        record["updated_at"] = _utc_now_iso()
    record["title_mode"] = TITLE_MODE_MANUAL
    return _write_chat_record(record)


def _delete_chat(chat_id: str) -> None:
    global active_chat_id

    path = _chat_file_path(chat_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Chat not found")

    os.remove(path)
    if active_chat_id == _safe_chat_id(chat_id):
        active_chat_id = None


def _create_default_window_icon(icon_path: str) -> Optional[str]:
    try:
        canvas_size = 256
        triangle_margin_x = 44
        triangle_top_y = 56
        triangle_bottom_y = 212

        image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.polygon(
            [
                (triangle_margin_x, triangle_top_y),
                (canvas_size - triangle_margin_x, triangle_top_y),
                (canvas_size // 2, triangle_bottom_y),
            ],
            fill=(0, 0, 0, 255),
        )
        image.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
        return icon_path
    except Exception:
        return None


def _ensure_window_icon() -> Optional[str]:
    if os.path.isfile(WINDOW_ICON_PATH):
        return WINDOW_ICON_PATH

    return _create_default_window_icon(WINDOW_ICON_PATH)


def _set_windows_app_id() -> None:
    if os.name != "nt":
        return

    try:
        ctypes = __import__("ctypes")
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JarvisDesktop.BlackTriangle")
    except Exception:
        pass


def _bring_window_to_front() -> None:
    global main_window

    window = main_window
    if window is None and webview is not None:
        try:
            window = webview.windows[0] if webview.windows else None
            main_window = window
        except Exception:
            window = None

    if window is not None:
        try:
            if hasattr(window, "restore"):
                window.restore()
        except Exception:
            pass

        try:
            if hasattr(window, "show"):
                window.show()
        except Exception:
            pass

        try:
            window.on_top = True

            def _drop_on_top():
                time.sleep(1.2)
                try:
                    window.on_top = False
                except Exception:
                    pass

            threading.Thread(target=_drop_on_top, daemon=True).start()
        except Exception:
            pass

    if os.name != "nt":
        return

    try:
        ctypes = __import__("ctypes")
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            SW_RESTORE = 9
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040

            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _speak_assistant_response_async(response_text: str):
    if not TTS.is_enabled():
        return

    paragraphs = [p.strip() for p in str(response_text or "").split("\n\n") if p.strip()]
    if not paragraphs:
        return

    def worker():
        with tts_lock:
            try:
                TTS.speak_paragraphs(paragraphs, context="ответ ассистента")
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()


def _extract_context_capacity() -> int:
    default_capacity = 18000

    try:
        response = requests.get(f"{desktop_app.agent.base_url}/props", timeout=2)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict):
            settings = data.get("default_generation_settings", {})
            n_ctx = settings.get("n_ctx")
            if isinstance(n_ctx, int) and n_ctx > 0:
                return n_ctx
    except Exception:
        pass

    try:
        response = requests.get(f"{desktop_app.agent.base_url}/slots", timeout=2)
        response.raise_for_status()
        data = response.json()
        slots = data.get("value") if isinstance(data, dict) else data
        if isinstance(slots, list):
            capacities = [slot.get("n_ctx") for slot in slots if isinstance(slot.get("n_ctx"), int)]
            if capacities:
                return max(capacities)
    except Exception:
        pass

    preset = desktop_app.get_selected_model_preset()
    command = preset.get("command", "")
    match = re.search(r"(?:^|\s)-c\s+(\d+)", command)
    if match:
        return int(match.group(1))

    return default_capacity


def _estimate_context_used() -> int:
    agent = desktop_app.agent
    total = 0

    for message in getattr(agent, "messages", []):
        role = message.get("role", "")
        total += agent._estimate_tokens(role)

        content = message.get("content", "")
        if isinstance(content, str):
            total += agent._estimate_tokens(content)
        elif isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    total += agent._estimate_tokens(str(item))
                    continue
                if "text" in item:
                    total += agent._estimate_tokens(item.get("text", ""))
                elif "image_url" in item:
                    total += 256
        else:
            total += agent._estimate_tokens(str(content))

        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            total += agent._estimate_tokens(json.dumps(tool_calls, ensure_ascii=False))

        tool_call_id = message.get("tool_call_id")
        if tool_call_id:
            total += agent._estimate_tokens(str(tool_call_id))

    return total


def _build_context_payload() -> Dict[str, Any]:
    capacity = _extract_context_capacity()
    used = min(_estimate_context_used(), capacity)
    free = max(capacity - used, 0)
    ratio = (used / capacity) if capacity else 0.0
    return {
        "ok": True,
        "used": used,
        "capacity": capacity,
        "free": free,
        "usage_ratio": ratio,
        "source": "server_capacity_plus_local_estimate",
    }
def _image_file_to_data_url(path: Optional[str]) -> Optional[str]:
    if not path or not os.path.isfile(path):
        return None
    mime_type, _ = mimetypes.guess_type(path)
    if not mime_type or not mime_type.startswith("image/"):
        return None
    try:
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"
    except Exception:
        return None


def _make_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        for encoding in ("utf-8", "cp1251", "cp866", "latin-1"):
            try:
                return value.decode(encoding)
            except Exception:
                continue
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, dict):
        safe_dict: Dict[str, Any] = {}
        for key, item in value.items():
            safe_dict[str(key)] = _make_json_safe(item)
        return safe_dict
    if isinstance(value, (list, tuple, set)):
        return [_make_json_safe(item) for item in value]
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        return str(value)


class WebStreamBridge:
    def __init__(self):
        self.events: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.originals: Dict[str, Any] = {}
        self.had_output = False
        self.last_content = ""
        self.last_thinking = ""
        self.tool_events: Dict[tuple, threading.Event] = {}
        self._tool_call_ids: Dict[tuple, str] = {}

    def push(self, event: str, **payload):
        if event == "content_delta":
            self.last_content = payload.get("content", self.last_content) or self.last_content
        elif event == "thinking_delta":
            self.last_thinking = payload.get("content", self.last_thinking) or self.last_thinking
        elif event == "thinking_block":
            self.last_thinking = payload.get("content", self.last_thinking) or self.last_thinking
        elif event == "final":
            self.last_content = payload.get("content", self.last_content) or self.last_content
        if event in {"thinking_delta", "thinking_block", "content_delta", "tool_call", "tool_result", "final"}:
            self.had_output = True
        self.events.put(_make_json_safe({"event": event, **payload}))

    @contextmanager
    def patched(self):
        self.originals = {
            "start_streaming_thinking": UI.start_streaming_thinking,
            "update_streaming_thinking": UI.update_streaming_thinking,
            "finish_streaming_thinking": UI.finish_streaming_thinking,
            "print_streaming_thinking_block": UI.print_streaming_thinking_block,
            "start_streaming_response": UI.start_streaming_response,
            "update_streaming_response": UI.update_streaming_response,
            "finish_streaming_response": UI.finish_streaming_response,
            "print_tool_call": UI.print_tool_call,
            "print_tool_result": UI.print_tool_result,
            "print_agent_status": UI.print_agent_status,
            "print_status": UI.print_status,
            "print_error": UI.print_error,
            "print_separator": UI.print_separator,
            "anim_start": AnimationManager.start,
            "anim_start_bg": AnimationManager.start_bg,
            "anim_stop": AnimationManager.stop,
            "anim_stop_bg": AnimationManager.stop_bg,
            "anim_tick": AnimationManager.tick,
            "anim_is_running": AnimationManager.is_running,
        }

        def start_thinking():
            return {"buffer": ""}

        def update_thinking(state, chunk):
            state["buffer"] += chunk
            self.push("thinking_delta", delta=chunk, content=state["buffer"])

        def finish_thinking(state):
            return state.get("buffer", "") if state else ""

        def print_thinking_block(content):
            self.push("thinking_block", content=content)

        def start_response(title="Answer"):
            return {"buffer": "", "title": title}

        def update_response(state, chunk):
            state["buffer"] += chunk
            self.push("content_delta", delta=chunk, content=state["buffer"])

        def finish_response(state):
            return state.get("buffer", "") if state else ""

        def tool_call(tool_name, args, iteration):
            # Нормализуем iteration: если None, используем 0 как дефолт
            iter_val = iteration if iteration is not None else 0
            # Генерируем уникальный tool_call_id для надёжной связи tool_call -> tool_result
            tool_call_id = f"tool-{tool_name}-{iter_val}-{uuid.uuid4().hex[:8]}"
            key = (tool_name, iter_val)
            stop_event = threading.Event()
            self.tool_events[key] = stop_event
            self._tool_call_ids[key] = tool_call_id
            print(f"[DEBUG] tool_call: {tool_name}, iteration={iter_val}, key={key}, tool_call_id={tool_call_id}", file=sys.stderr)
            # Форматируем args для отображения на фронтенде (как JSON если это dict/объект)
            try:
                if isinstance(args, (dict, list)):
                    formatted_args = json.dumps(args, ensure_ascii=False, indent=2)
                else:
                    formatted_args = str(args)
            except Exception:
                formatted_args = str(args)
            self.push("tool_call", tool_name=tool_name, args=args, args_formatted=formatted_args, iteration=iter_val, tool_call_id=tool_call_id)
            return stop_event

        def tool_result(tool_name, result, iteration, stop_event=None):
            # Нормализуем iteration
            iter_val = iteration if iteration is not None else 0
            key = (tool_name, iter_val)

            print(f"[DEBUG] tool_result: {tool_name}, iteration={iter_val}, key={key}, stop_event_provided={stop_event is not None}", file=sys.stderr)

            # Попытка найти stop_event: сначала по точному ключу, потом по tool_name
            actual_key = key
            if stop_event is None:
                stop_event = self.tool_events.pop(key, None)
                if stop_event is None:
                    # Fallback: ищем по имени инструмента (на случай несовпадения iteration)
                    for k in list(self.tool_events.keys()):
                        if k[0] == tool_name:
                            actual_key = k
                            stop_event = self.tool_events.pop(k, None)
                            print(f"[DEBUG] tool_result: found event by fallback key {k}", file=sys.stderr)
                            break

            # Получаем tool_call_id по тому же ключу (точному или fallback)
            tool_call_id = self._tool_call_ids.pop(actual_key, None)
            if tool_call_id is None:
                # Fallback: ищем по tool_name
                for k in list(self._tool_call_ids.keys()):
                    if k[0] == tool_name:
                        actual_key = k
                        tool_call_id = self._tool_call_ids.pop(k, None)
                        break
                if tool_call_id:
                    print(f"[DEBUG] tool_result: found tool_call_id by fallback key {actual_key}", file=sys.stderr)

            if stop_event:
                stop_event.set()
                print(f"[DEBUG] tool_result: stop_event.set() called", file=sys.stderr)
            else:
                print(f"[DEBUG] tool_result: WARNING - stop_event not found for key {key}", file=sys.stderr)

            # Корректная обработка result: может быть dict или объект с атрибутами
            if isinstance(result, dict):
                success = bool(result.get("success", False))
                data = result.get("data")
                error = result.get("error")
            else:
                success = bool(getattr(result, "success", False))
                data = getattr(result, "data", None)
                error = getattr(result, "error", None)

            result_images: List[str] = []
            if success and isinstance(data, dict):
                data_path = data.get("path")
                preview_image = _image_file_to_data_url(data_path)
                if preview_image:
                    result_images.append(preview_image)

            # Отправляем событие на фронтенд
            self.push(
                "tool_result",
                tool_name=tool_name,
                iteration=iter_val,
                tool_call_id=tool_call_id,
                success=success,
                data=data,
                error=error,
                images=result_images,
            )
            print(f"[DEBUG] tool_result: pushed event, success={success}, tool_call_id={tool_call_id}", file=sys.stderr)

        def agent_status(iteration, max_iterations):
            self.push("agent_status", iteration=iteration, max_iterations=max_iterations)

        def status(message, status_type="info"):
            self.push("status", message=message, status_type=status_type)

        def error(message):
            self.push("error", message=message)

        UI.start_streaming_thinking = staticmethod(start_thinking)
        UI.update_streaming_thinking = staticmethod(update_thinking)
        UI.finish_streaming_thinking = staticmethod(finish_thinking)
        UI.print_streaming_thinking_block = staticmethod(print_thinking_block)
        UI.start_streaming_response = staticmethod(start_response)
        UI.update_streaming_response = staticmethod(update_response)
        UI.finish_streaming_response = staticmethod(finish_response)
        UI.print_tool_call = staticmethod(tool_call)
        UI.print_tool_result = staticmethod(tool_result)
        UI.print_agent_status = staticmethod(agent_status)
        UI.print_status = staticmethod(status)
        UI.print_error = staticmethod(error)
        UI.print_separator = staticmethod(lambda style="double": None)

        AnimationManager.start = classmethod(lambda cls, *args, **kwargs: None)
        AnimationManager.start_bg = classmethod(lambda cls, *args, **kwargs: None)
        AnimationManager.stop = classmethod(lambda cls, *args, **kwargs: None)
        AnimationManager.stop_bg = classmethod(lambda cls, *args, **kwargs: None)
        AnimationManager.tick = classmethod(lambda cls, *args, **kwargs: None)
        AnimationManager.is_running = classmethod(lambda cls: False)

        try:
            yield self
        finally:
            UI.start_streaming_thinking = self.originals["start_streaming_thinking"]
            UI.update_streaming_thinking = self.originals["update_streaming_thinking"]
            UI.finish_streaming_thinking = self.originals["finish_streaming_thinking"]
            UI.print_streaming_thinking_block = self.originals["print_streaming_thinking_block"]
            UI.start_streaming_response = self.originals["start_streaming_response"]
            UI.update_streaming_response = self.originals["update_streaming_response"]
            UI.finish_streaming_response = self.originals["finish_streaming_response"]
            UI.print_tool_call = self.originals["print_tool_call"]
            UI.print_tool_result = self.originals["print_tool_result"]
            UI.print_agent_status = self.originals["print_agent_status"]
            UI.print_status = self.originals["print_status"]
            UI.print_error = self.originals["print_error"]
            UI.print_separator = self.originals["print_separator"]
            AnimationManager.start = self.originals["anim_start"]
            AnimationManager.start_bg = self.originals["anim_start_bg"]
            AnimationManager.stop = self.originals["anim_stop"]
            AnimationManager.stop_bg = self.originals["anim_stop_bg"]
            AnimationManager.tick = self.originals["anim_tick"]
            AnimationManager.is_running = self.originals["anim_is_running"]


@app.get("/")
def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
    except Exception:
        return FileResponse(index_path)
    # Подставляем случайный API-токен для фронтенда
    html = html.replace('{{API_TOKEN}}', API_TOKEN)
    return HTMLResponse(content=html)


def _selected_preset_payload() -> Dict[str, Any]:
    try:
        preset = desktop_app.get_selected_model_preset()
        return {
            "selected_model_key": desktop_app.selected_model_key,
            "selected_model_label": preset["label"],
            "selected_model_description": preset["description"],
            "selected_model_supports_images": bool(preset.get("supports_images", False)),
        }
    except Exception:
        return {
            "selected_model_key": None,
            "selected_model_label": None,
            "selected_model_description": None,
            "selected_model_supports_images": False,
        }


@app.get("/api/config")
def api_config_status():
    return {"ok": True, **config_manager.get_config_status()}


@app.post("/api/config/presets")
def api_create_preset(request: PresetCreateRequest):
    try:
        status = config_manager.add_preset(request.model_dump(), make_active=request.make_active)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    reload_llama_server_presets()
    active_index = status.get("active_preset_index", 0)
    desktop_app.selected_model_key = f"preset_{active_index}"
    _update_agent_tools_from_status(status)
    return {"ok": True, **status}


@app.post("/api/config/presets/select")
def api_select_preset(request: PresetSelectRequest):
    try:
        status = config_manager.select_preset_index(request.preset_index)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    reload_llama_server_presets()
    desktop_app.selected_model_key = f"preset_{request.preset_index}"
    _update_agent_tools_from_status(status)
    return {"ok": True, **status}


@app.post("/api/config/presets/delete")
def api_delete_preset(request: PresetDeleteRequest):
    try:
        status = config_manager.delete_preset_index(request.preset_index)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    reload_llama_server_presets()
    if status.get("active_preset_key"):
        desktop_app.selected_model_key = status["active_preset_key"]
    _update_agent_tools_from_status(status)
    return {"ok": True, **status}


@app.post("/api/config/presets/tools")
def api_update_preset_tools(request: PresetToolsRequest):
    try:
        status = config_manager.update_preset_tools(request.preset_index, request.enabled_tools)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    reload_llama_server_presets()
    if status.get("active_preset_key"):
        desktop_app.selected_model_key = status["active_preset_key"]
    _update_agent_tools_from_status(status)
    return {"ok": True, **status}


@app.get("/api/tools")
def api_tools():
    tools = []
    for tool in TOOLS_DEFINITION:
        function_data = tool.get("function", {})
        tools.append({
            "name": function_data.get("name", ""),
            "description": function_data.get("description", ""),
            "multimodal": function_data.get("name", "") in MULTIMODAL_TOOL_NAMES,
        })
    return {"ok": True, "tools": tools}


@app.get("/api/health")
def api_health():
    preset_info = _selected_preset_payload()
    current_voice = _get_voice_state()
    current_asr = _get_selected_asr_backend()
    return {
        "ok": True,
        "llama_server_online": desktop_app.agent.check_health(),
        "needs_setup": config_manager.needs_setup(),
        **preset_info,
        "tts_available": bool(TTS.is_available()),
        "tts_enabled": bool(TTS.is_enabled()),
        "tts_model_loaded": bool(TTS.is_model_loaded()),
        "tts_device": TTS.get_device(),
        "tts_disable_locked": bool(getattr(desktop_app, "tts_disable_locked", False)),
        "voice_available": bool(current_voice.get("available", False)),
        "voice_enabled": bool(current_voice.get("enabled", False)),
        "voice_listening": bool(current_voice.get("listening", False)),
        "voice_wake_word": current_voice.get("wake_word", WAKE_WORD),
        "voice_backend_key": current_asr.get("key", DEFAULT_TRANSCRIPTION_BACKEND_KEY),
        "voice_backend_label": current_asr.get("label", "Vosk Small RU"),
        "voice_backend_description": current_asr.get("description", ""),
        "voice_backend_available": bool(current_asr.get("available", False)),
        "voice_backend_reason": current_asr.get("reason", ""),
        "active_chat_id": active_chat_id,
    }


@app.get("/api/chats")
def api_list_chats():
    return {
        "ok": True,
        "chats": _list_chat_summaries(),
        "active_chat_id": active_chat_id,
    }


@app.post("/api/chats")
def api_create_chat(request: CreateChatRequest):
    record = _create_chat_record(request.title)
    return {
        "ok": True,
        "chat": _chat_summary(record),
        "active_chat_id": record["id"],
    }


@app.get("/api/chats/{chat_id}")
def api_get_chat(chat_id: str):
    record = _activate_chat(chat_id)
    return {
        "ok": True,
        "chat": {
            **_chat_summary(record),
            "ui_messages": record.get("ui_messages", []),
        },
        "active_chat_id": record["id"],
    }


@app.patch("/api/chats/{chat_id}")
def api_rename_chat(chat_id: str, request: RenameChatRequest):
    record = _rename_chat(chat_id, request.title)
    return {
        "ok": True,
        "chat": _chat_summary(record),
        "active_chat_id": active_chat_id,
    }


@app.delete("/api/chats/{chat_id}")
def api_delete_chat(chat_id: str):
    _delete_chat(chat_id)
    return {
        "ok": True,
        "deleted_chat_id": _safe_chat_id(chat_id),
        "active_chat_id": active_chat_id,
    }


@app.put("/api/chats/{chat_id}/state")
def api_save_chat_state(chat_id: str, request: ChatStateRequest):
    record = _save_chat_state(chat_id, ui_messages=request.ui_messages, title=request.title)
    return {
        "ok": True,
        "chat": _chat_summary(record),
        "active_chat_id": record["id"],
    }


@app.get("/api/models")
def api_models():
    models = []
    for key, preset in desktop_app.get_model_presets().items():
        models.append({
            "key": key,
            "label": preset["label"],
            "description": preset["description"],
            "supports_images": bool(preset.get("supports_images", False)),
            "selected": key == desktop_app.selected_model_key,
            "config_index": preset.get("config_index"),
        })
    return {"models": models}


@app.get("/api/asr/backends")
def api_asr_backends():
    return {"backends": desktop_app.get_voice_backend_options()}


@app.get("/api/context")
def api_context():
    if not desktop_app.agent.check_health():
        return {
            "ok": False,
            "used": 0,
            "capacity": _extract_context_capacity(),
            "free": 0,
            "usage_ratio": 0.0,
            "source": "offline",
        }

    return _build_context_payload()


@app.post("/api/server/start")
def api_start_model(request: StartModelRequest):
    if request.model_key not in desktop_app.get_model_presets():
        raise HTTPException(status_code=400, detail="Unknown model preset")

    preset = desktop_app.get_model_presets().get(request.model_key) or {}
    config_index = preset.get("config_index")
    if config_index is not None:
        try:
            config_manager.select_preset_index(int(config_index))
            reload_llama_server_presets()
        except ValueError:
            pass

    original_print_status = UI.print_status
    original_print_error = UI.print_error
    UI.print_status = staticmethod(lambda message, status_type="info": print(f"[server] {message}"))
    UI.print_error = staticmethod(lambda message: print(f"[server error] {message}"))
    try:
        started = desktop_app.start_selected_llama_server(request.model_key)
    except Exception as exc:
        import traceback
        detail = f"Failed to start llama-server: {exc}\n{traceback.format_exc()}"
        raise HTTPException(status_code=500, detail=detail) from exc
    finally:
        UI.print_status = original_print_status
        UI.print_error = original_print_error

    if not started:
        raise HTTPException(
            status_code=500,
            detail="Failed to start llama-server (timeout or process error)",
        )

    preset = desktop_app.get_selected_model_preset()
    return {
        "ok": True,
        "selected_model_key": desktop_app.selected_model_key,
        "selected_model_label": preset["label"],
    }





@app.post("/api/settings/tts")
def api_set_tts(request: TTSSettingsRequest):
    if not TTS.is_available():
        raise HTTPException(status_code=503, detail="Supertonic недоступен в этой сборке.")

    enabled = bool(request.enabled)
    if not enabled and bool(getattr(desktop_app, "tts_disable_locked", False)):
        raise HTTPException(status_code=409, detail="Перезапустите приложение для отключения озвучки.")

    with tts_lock:
        ok = TTS.load_model() if enabled else TTS.unload_model()

    if not ok:
        action = "загрузить" if enabled else "выгрузить"
        raise HTTPException(status_code=500, detail=f"Не удалось {action} модель озвучки.")

    if enabled:
        desktop_app.tts_disable_locked = True

    return {
        "ok": True,
        "tts_available": bool(TTS.is_available()),
        "tts_enabled": bool(TTS.is_enabled()),
        "tts_model_loaded": bool(TTS.is_model_loaded()),
        "tts_device": TTS.get_device(),
        "tts_disable_locked": bool(getattr(desktop_app, "tts_disable_locked", False)),
    }


@app.post("/api/settings/asr")
def api_set_asr(request: ASRSettingsRequest):
    engine_key = str(request.engine_key or "").strip()
    if not engine_key:
        raise HTTPException(status_code=400, detail="Пустой ключ backend распознавания.")

    selected = None
    for backend in desktop_app.get_voice_backend_options():
        if backend.get("key") == engine_key:
            selected = backend
            break

    if selected is None:
        raise HTTPException(status_code=400, detail="Неизвестный backend распознавания.")

    if not bool(selected.get("available", False)):
        reason = selected.get("reason") or "Выбранный backend сейчас недоступен."
        raise HTTPException(status_code=409, detail=reason)

    activator = getattr(desktop_app, "voice_activator", None)
    was_enabled = bool(getattr(desktop_app, "voice_enabled", False)) and activator is not None and bool(getattr(activator, "is_running", False))

    if was_enabled:
        activator.stop_listening()

    desktop_app.set_voice_backend(engine_key)

    if activator is not None:
        activator.set_command_backend(engine_key)
        if not activator.init_models(force_reload=engine_key == LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY):
            desktop_app.voice_enabled = False
            _update_voice_state(
                enabled=False,
                listening=False,
                phase="error",
                status="Не удалось инициализировать выбранный backend распознавания.",
            )
            raise HTTPException(status_code=500, detail="Не удалось инициализировать выбранный backend распознавания.")
        if was_enabled:
            activator.start_listening()

    state = _update_voice_state(
        backend_key=selected.get("key", engine_key),
        backend_label=selected.get("label", engine_key),
        available=bool(VOICE_AVAILABLE),
        listening=bool(getattr(getattr(desktop_app, "voice_activator", None), "is_running", False)),
    )
    return {"ok": True, "backend": selected, **state}


@app.post("/api/settings/voice")
def api_set_voice(request: VoiceSettingsRequest):
    if not VOICE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Голосовая активация недоступна в этой сборке.")

    backend = _get_selected_asr_backend()
    if not bool(backend.get("available", False)):
        raise HTTPException(status_code=409, detail=backend.get("reason") or "Выбранный backend распознавания недоступен.")

    if not _ensure_voice_initialized():
        state = _get_voice_state()
        raise HTTPException(status_code=500, detail=state.get("status") or "Не удалось инициализировать голосовую активацию.")

    activator = getattr(desktop_app, "voice_activator", None)
    if activator is None:
        raise HTTPException(status_code=500, detail="Голосовая активация не инициализирована.")

    enabled = bool(request.enabled)
    desktop_app.voice_enabled = enabled

    if enabled:
        activator.start_listening()
        state = _update_voice_state(
            available=True,
            enabled=True,
            listening=True,
            phase="armed",
            status=f"Слушаю wake word '{WAKE_WORD}'",
            wake_word=WAKE_WORD,
            overlay_visible=False,
            live_text="",
            backend_key=backend.get("key", DEFAULT_TRANSCRIPTION_BACKEND_KEY),
            backend_label=backend.get("label", "Vosk Small RU"),
        )
    else:
        activator.stop_listening()
        state = _update_voice_state(
            available=True,
            enabled=False,
            listening=False,
            phase="idle",
            status="Голосовая активация выключена",
            wake_word=WAKE_WORD,
            overlay_visible=False,
            live_text="",
            final_text="",
            backend_key=backend.get("key", DEFAULT_TRANSCRIPTION_BACKEND_KEY),
            backend_label=backend.get("label", "Vosk Small RU"),
        )

    return {"ok": True, **state}


@app.get("/api/voice/state")
def api_voice_state():
    return {"ok": True, **_get_voice_state()}


@app.post("/api/voice/reset")
def api_voice_reset():
    backend = _get_selected_asr_backend()
    state = _update_voice_state(
        phase="armed" if bool(getattr(desktop_app, "voice_enabled", False)) else "idle",
        status=f"Слушаю wake word '{WAKE_WORD}'" if bool(getattr(desktop_app, "voice_enabled", False)) else "Голосовая активация выключена",
        overlay_visible=False,
        live_text="",
        final_text="",
        backend_key=backend.get("key", DEFAULT_TRANSCRIPTION_BACKEND_KEY),
        backend_label=backend.get("label", "Vosk Small RU"),
    )
    return {"ok": True, **state}


@app.post("/api/chat")
def api_chat(request: ChatRequest):
    target_chat_id = request.chat_id or active_chat_id
    if target_chat_id:
        _activate_chat(target_chat_id)

    message = request.message.strip()
    images = [item for item in request.images if isinstance(item, str) and item.startswith("data:image/")]
    if not message and not images:
        raise HTTPException(status_code=400, detail="Empty message")

    if images and not desktop_app.selected_model_supports_images():
        raise HTTPException(status_code=400, detail="The selected model does not support attached images.")

    if not desktop_app.agent.check_health():
        raise HTTPException(status_code=503, detail="Llama server is offline. Start a model first.")

    with chat_lock:
        result = desktop_app.chat_once(
            message,
            stream=False,
            show_thinking=True,
            image_urls=images
        )

    _speak_assistant_response_async(result.get("content", ""))

    return {
        "ok": True,
        "reply": result.get("content", ""),
        "iterations": result.get("iterations", 0),
    }


@app.post("/api/chat/stream")
def api_chat_stream(request: ChatRequest):
    target_chat_id = request.chat_id or active_chat_id
    if target_chat_id:
        _activate_chat(target_chat_id)

    message = request.message.strip()
    images = [item for item in request.images if isinstance(item, str) and item.startswith("data:image/")]
    if not message and not images:
        raise HTTPException(status_code=400, detail="Empty message")

    if images and not desktop_app.selected_model_supports_images():
        raise HTTPException(status_code=400, detail="The selected model does not support attached images.")

    if not desktop_app.agent.check_health():
        raise HTTPException(status_code=503, detail="Llama server is offline. Start a model first.")

    bridge = WebStreamBridge()

    def event_generator():
        def worker():
            global active_stream_bridge
            with active_stream_lock:
                active_stream_bridge = bridge
            with chat_lock:
                with bridge.patched():
                    try:
                        for result in desktop_app.agent.send_message(
                                message,
                                stream=True,
                                show_thinking=True,
                                image_urls=images
                        ):
                            if result.get("type") == "final":
                                final_content = result.get("content", "")
                                bridge.push(
                                    "final",
                                    content=final_content,
                                    iterations=result.get("iterations", 0),
                                )
                    except Exception as exc:
                        error_message = str(exc)
                        if "Assistant response prefill is incompatible with enable_thinking" in error_message:
                            fallback_content = (bridge.last_content or "").strip()
                            if not fallback_content:
                                fallback_content = (bridge.last_thinking or "").strip()
                            if fallback_content:
                                bridge.push("final", content=fallback_content, iterations=0)
                            # Harmless llama.cpp fallback after tool use: do not surface as a user-facing error.
                        else:
                            bridge.push("error", message=error_message)
                    finally:
                        with active_stream_lock:
                            if active_stream_bridge is bridge:
                                active_stream_bridge = None
                        if target_chat_id:
                            _save_chat_state(target_chat_id)
                        final_content_for_tts = (bridge.last_content or "").strip()
                        if final_content_for_tts:
                            _speak_assistant_response_async(final_content_for_tts)
                        # Очищаем оставшиеся события инструментов при завершении сессии
                        bridge.tool_events.clear()
                        bridge._tool_call_ids.clear()
                        bridge.push("done")

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while True:
            item = bridge.events.get()
            yield f"data: {json.dumps(_make_json_safe(item), ensure_ascii=False)}\n\n"
            if item.get("event") == "done":
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/chat/stop")
def api_chat_stop():
    desktop_app.agent.request_stop()
    with active_stream_lock:
        is_active = active_stream_bridge is not None
    return {"ok": True, "stopping": is_active}


@app.post("/api/user-response")
def api_user_response(request: UserResponseRequest):
    with _user_prompt_lock:
        event = pending_user_prompts.get(request.prompt_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Prompt not found or expired")
        pending_user_answers[request.prompt_id] = request.answer
        event.set()
    return {"ok": True}


@app.get("/api/telegram-account/status")
def api_telegram_account_status():
    manager = get_telegram_account_manager()
    if manager is None:
        return {"ok": True, "available": False, "configured": False, "connected": False, "reason": "Telethon не установлен"}
    status = manager.get_status()
    return {"ok": True, "available": True, **status}


@app.post("/api/telegram-account/start-setup")
def api_telegram_account_start_setup(request: TelegramAccountSetupStartRequest):
    manager = get_telegram_account_manager()
    if manager is None:
        raise HTTPException(status_code=503, detail="Telethon не установлен")
    try:
        result = manager.setup_start(request.api_id, request.api_hash, request.phone)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/telegram-account/confirm-code")
def api_telegram_account_confirm_code(request: TelegramAccountConfirmCodeRequest):
    manager = get_telegram_account_manager()
    if manager is None:
        raise HTTPException(status_code=503, detail="Telethon не установлен")
    try:
        result = manager.setup_confirm_code(request.code)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/telegram-account/confirm-2fa")
def api_telegram_account_confirm_2fa(request: TelegramAccountConfirm2FARequest):
    manager = get_telegram_account_manager()
    if manager is None:
        raise HTTPException(status_code=503, detail="Telethon не установлен")
    try:
        result = manager.setup_confirm_2fa(request.password)
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/telegram-account/save-session")
def api_telegram_account_save_session():
    manager = get_telegram_account_manager()
    if manager is None:
        raise HTTPException(status_code=503, detail="Telethon не установлен")
    try:
        result = manager.setup_save_session()
        return {"ok": True, **result}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/telegram-account/disconnect")
def api_telegram_account_disconnect():
    manager = get_telegram_account_manager()
    if manager is None:
        raise HTTPException(status_code=503, detail="Telethon не установлен")
    manager.delete_secret()
    return {"ok": True}


def _disconnect_telegram_account() -> None:
    """Disconnect the Telegram user account client on shutdown."""
    try:
        from jarvis_tools.telegram_account import get_manager

        manager = get_manager()
        if manager is not None:
            manager.disconnect()
    except Exception:
        pass


def shutdown_resources() -> None:
    """Gracefully release resources before exit: llama-server, Telegram."""
    try:
        if desktop_app is not None:
            desktop_app.shutdown_llama_server()
    except Exception:
        pass

    _disconnect_telegram_account()


def _on_window_closing():
    """Handler called when the user closes the webview window."""
    shutdown_resources()


# Register a fallback cleanup hook for normal interpreter shutdown.
atexit.register(shutdown_resources)


@app.post("/api/shutdown")
def api_shutdown():
    """Release resources and shut down llama-server gracefully."""
    shutdown_resources()
    return {"ok": True}


def run_backend():
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


def main():
    global main_window
    _set_windows_app_id()

    reload_llama_server_presets()
    status = config_manager.get_config_status()
    if status.get("active_preset_key"):
        desktop_app.selected_model_key = status["active_preset_key"]
        _update_agent_tools_from_status(status)

    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    time.sleep(1.2)

    url = f"http://{HOST}:{PORT}"
    if webview is not None:
        window_icon = _ensure_window_icon()
        main_window = webview.create_window(
            WINDOW_TITLE,
            url,
            width=1440,
            height=960,
            min_size=(1100, 850),
            maximized=True,
        )

        # Attach shutdown handler to window close event (both pywebview 4.x and 5.x APIs).
        try:
            if hasattr(main_window, "events") and hasattr(main_window.events, "closing"):
                main_window.events.closing += _on_window_closing
            elif hasattr(main_window, "closing"):
                main_window.closing += _on_window_closing
        except Exception:
            pass

        webview.start(icon=window_icon)
    else:
        webbrowser.open(url)
        print("pywebview is not installed. Opening the interface in the browser.")
        try:
            while backend_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
