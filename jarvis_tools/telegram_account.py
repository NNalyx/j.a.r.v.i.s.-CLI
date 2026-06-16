"""Telegram user-account integration via Telethon (MTProto).

Provides a singleton manager and agent tools for reading dialogs, sending
messages, joining chats and global search using the user's own Telegram
account. Credentials are stored separately in
`jarvis_telegram_account_secret.json`, never in the main config or memory.
"""
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis_core.types import ToolResult

try:
    from telethon import TelegramClient, functions
    from telethon.errors import (
        FloodWaitError,
        PhoneCodeInvalidError,
        SessionPasswordNeededError,
    )
    from telethon.sessions import StringSession
    from telethon.tl.types import Channel, Chat, User

    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    TelegramClient = None
    functions = None
    StringSession = None
    FloodWaitError = None
    PhoneCodeInvalidError = None
    SessionPasswordNeededError = None
    Channel = None
    Chat = None
    User = None

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_FILE = BASE_DIR / "jarvis_telegram_account_secret.json"

_INSTANCE_LOCK = threading.Lock()
_INSTANCE: Optional["TelegramAccountManager"] = None


class TelegramAccountManager:
    """Singleton manager for the user's Telegram account via Telethon."""

    def __init__(self):
        self._client: Optional[TelegramClient] = None
        self._secret: Dict[str, Any] = {}
        self._setup_state: Dict[str, Any] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Secret persistence
    # ------------------------------------------------------------------
    def _load_secret(self) -> Dict[str, Any]:
        if SECRET_FILE.exists():
            try:
                with open(SECRET_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_secret(self, data: Dict[str, Any]) -> None:
        with open(SECRET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def delete_secret(self) -> None:
        with self._lock:
            self._disconnect_unsafe()
            self._secret = {}
            self._setup_state = {}
            if SECRET_FILE.exists():
                try:
                    SECRET_FILE.unlink()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------
    def is_configured(self) -> bool:
        secret = self._load_secret()
        return bool(
            secret.get("api_id")
            and secret.get("api_hash")
            and secret.get("session_string")
        )

    def is_connected(self) -> bool:
        with self._lock:
            return self._client is not None and self._client.is_connected()

    def get_status(self) -> Dict[str, Any]:
        secret = self._load_secret()
        me = None
        if self.is_connected():
            try:
                me = self._client.get_me()
            except Exception:
                pass
        return {
            "configured": self.is_configured(),
            "connected": self.is_connected(),
            "phone": secret.get("phone"),
            "username": me.username if me else secret.get("username"),
            "first_name": me.first_name if me else None,
            "last_name": me.last_name if me else None,
        }

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    def _disconnect_unsafe(self):
        if self._client is not None:
            try:
                if self._client.is_connected():
                    self._client.disconnect()
            except Exception:
                pass
            finally:
                self._client = None

    def disconnect(self) -> None:
        with self._lock:
            self._disconnect_unsafe()

    def connect(self) -> bool:
        if not TELETHON_AVAILABLE:
            return False
        secret = self._load_secret()
        api_id = secret.get("api_id")
        api_hash = secret.get("api_hash")
        session_string = secret.get("session_string")
        if not api_id or not api_hash or not session_string:
            return False

        with self._lock:
            self._disconnect_unsafe()
            try:
                session = StringSession(session_string)
                self._client = TelegramClient(
                    session,
                    int(api_id),
                    api_hash,
                    device_model="Jarvis Desktop",
                    app_version="1.0",
                    lang_code="ru",
                )
                self._client.connect()
                if not self._client.is_user_authorized():
                    self._disconnect_unsafe()
                    return False
                return True
            except Exception:
                self._disconnect_unsafe()
                return False

    def ensure_connected(self) -> bool:
        if self.is_connected():
            return True
        return self.connect()

    # ------------------------------------------------------------------
    # Setup wizard state machine
    # ------------------------------------------------------------------
    def setup_start(self, api_id: int, api_hash: str, phone: str) -> Dict[str, Any]:
        if not TELETHON_AVAILABLE:
            raise RuntimeError("Telethon не установлен. Установите: pip install telethon")
        if not api_id or not api_hash or not phone:
            raise ValueError("api_id, api_hash и phone обязательны")

        with self._lock:
            self._disconnect_unsafe()
            session = StringSession()
            self._client = TelegramClient(
                session,
                int(api_id),
                api_hash,
                device_model="Jarvis Desktop",
                app_version="1.0",
                lang_code="ru",
            )
            self._client.connect()
            try:
                result = self._client.send_code_request(phone)
                self._setup_state = {
                    "api_id": int(api_id),
                    "api_hash": api_hash,
                    "phone": phone,
                    "phone_code_hash": result.phone_code_hash,
                    "needs_code": True,
                    "needs_2fa": False,
                }
                return {"needs_code": True}
            except FloodWaitError as exc:
                self._disconnect_unsafe()
                raise RuntimeError(f"Слишком много попыток. Подождите {exc.seconds} сек.")
            except Exception as exc:
                self._disconnect_unsafe()
                raise RuntimeError(f"Не удалось отправить код: {exc}")

    def setup_confirm_code(self, code: str) -> Dict[str, Any]:
        with self._lock:
            if not self._setup_state.get("needs_code"):
                raise RuntimeError("Сначала начните настройку и введите phone")
            phone = self._setup_state["phone"]
            phone_code_hash = self._setup_state.get("phone_code_hash")
            try:
                self._client.sign_in(phone, code, phone_code_hash=phone_code_hash)
                self._setup_state["needs_code"] = False
                self._setup_state["needs_2fa"] = False
                return {"needs_2fa": False, "ok": True}
            except SessionPasswordNeededError:
                self._setup_state["needs_code"] = False
                self._setup_state["needs_2fa"] = True
                return {"needs_2fa": True}
            except PhoneCodeInvalidError:
                raise RuntimeError("Неверный код подтверждения. Попробуйте ещё раз.")
            except Exception as exc:
                raise RuntimeError(f"Не удалось подтвердить код: {exc}")

    def setup_confirm_2fa(self, password: str) -> Dict[str, Any]:
        with self._lock:
            if not self._setup_state.get("needs_2fa"):
                raise RuntimeError("2FA не требуется")
            try:
                self._client.sign_in(password=password)
                self._setup_state["needs_2fa"] = False
                return {"ok": True}
            except Exception as exc:
                raise RuntimeError(f"Не удалось подтвердить 2FA: {exc}")

    def setup_save_session(self) -> Dict[str, Any]:
        with self._lock:
            if not self._client:
                raise RuntimeError("Клиент не инициализирован")
            try:
                me = self._client.get_me()
                session_string = self._client.session.save()
                data = {
                    "api_id": self._setup_state.get("api_id"),
                    "api_hash": self._setup_state.get("api_hash"),
                    "phone": self._setup_state.get("phone"),
                    "session_string": session_string,
                    "username": me.username if me else None,
                    "user_id": me.id if me else None,
                }
                self._save_secret(data)
                self._secret = data
                self._setup_state = {}
                return {
                    "ok": True,
                    "username": data["username"],
                    "phone": data["phone"],
                    "user_id": data["user_id"],
                }
            except Exception as exc:
                raise RuntimeError(f"Не удалось сохранить сессию: {exc}")

    # ------------------------------------------------------------------
    # Entity resolution
    # ------------------------------------------------------------------
    async def _resolve_entity(self, entity: str):
        """Resolve a string entity (username, id, link) to a Telegram entity."""
        if not self._client:
            raise RuntimeError("Клиент не подключён")

        # Strip known prefixes and extract username or invite hash.
        text = entity.strip()
        if text.startswith("https://t.me/") or text.startswith("http://t.me/"):
            text = text.split("/")[-1]
        elif text.startswith("t.me/"):
            text = text[5:]

        # Invite link like +AbCdEf or joinchat/AbCdEf
        if text.startswith("+") or text.startswith("joinchat/"):
            return await self._client.get_entity(text)

        # Numeric ID
        if text.lstrip("-").isdigit():
            return await self._client.get_entity(int(text))

        # Username with or without @
        username = text.lstrip("@")
        return await self._client.get_entity(username)

    # ------------------------------------------------------------------
    # Account info
    # ------------------------------------------------------------------
    async def get_me(self) -> Dict[str, Any]:
        if not self.ensure_connected():
            raise RuntimeError("Аккаунт не подключён")
        me = await self._client.get_me()
        return {
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "phone": me.phone,
            "is_premium": bool(me.premium),
        }

    async def get_dialogs(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.ensure_connected():
            raise RuntimeError("Аккаунт не подключён")
        dialogs = []
        async for dialog in self._client.iter_dialogs(limit=limit):
            entity = dialog.entity
            item = {
                "id": entity.id,
                "title": getattr(entity, "title", None) or f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip(),
                "type": "channel" if isinstance(entity, Channel) else ("group" if isinstance(entity, Chat) else "user"),
                "unread_count": dialog.unread_count,
                "is_user": isinstance(entity, User),
            }
            if isinstance(entity, User):
                item["username"] = entity.username
                item["first_name"] = entity.first_name
                item["last_name"] = entity.last_name
            dialogs.append(item)
        return dialogs

    async def get_unread_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.ensure_connected():
            raise RuntimeError("Аккаунт не подключён")
        messages = []
        async for dialog in self._client.iter_dialogs():
            if dialog.unread_count == 0:
                continue
            count = 0
            async for message in self._client.iter_messages(dialog.entity, limit=min(dialog.unread_count, limit)):
                sender = await message.get_sender()
                messages.append({
                    "chat_id": dialog.entity.id,
                    "chat_title": getattr(dialog.entity, "title", None) or f"{getattr(dialog.entity, 'first_name', '')} {getattr(dialog.entity, 'last_name', '')}".strip(),
                    "message_id": message.id,
                    "date": message.date.isoformat() if message.date else None,
                    "text": message.text or "",
                    "sender_id": message.sender_id,
                    "sender_username": sender.username if sender else None,
                    "sender_name": f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip() if sender else None,
                })
                count += 1
                if count >= limit:
                    break
            if len(messages) >= limit:
                break
        return messages

    async def send_message(self, entity: str, text: str) -> Dict[str, Any]:
        if not self.ensure_connected():
            raise RuntimeError("Аккаунт не подключён")
        target = await self._resolve_entity(entity)
        message = await self._client.send_message(target, text)
        return {
            "ok": True,
            "chat_id": target.id,
            "message_id": message.id,
            "text": text,
        }

    async def join_chat(self, link_or_username: str) -> Dict[str, Any]:
        if not self.ensure_connected():
            raise RuntimeError("Аккаунт не подключён")
        text = link_or_username.strip()
        # Private invite link (t.me/+HASH or t.me/joinchat/HASH)
        if "t.me/+" in text or "t.me/joinchat/" in text or text.startswith("+") or text.startswith("joinchat/"):
            return await self.request_join(text)
        entity = await self._resolve_entity(text)
        await self._client(functions.channels.JoinChannelRequest(channel=entity))
        return {
            "ok": True,
            "chat_id": entity.id,
            "title": getattr(entity, "title", None),
        }

    async def request_join(self, invite_link: str) -> Dict[str, Any]:
        if not self.ensure_connected():
            raise RuntimeError("Аккаунт не подключён")
        # Extract invite hash from various link formats.
        link = invite_link.strip()
        match = re.search(r"(?:t\.me/\+?|telegram\.me/\+?|joinchat/)([A-Za-z0-9_-]+)", link)
        if not match:
            raise ValueError("Некорректная пригласительная ссылка")
        hash_value = match.group(1)
        result = await self._client(functions.messages.ImportChatInviteRequest(hash=hash_value))
        chat = result.chats[0] if result.chats else None
        return {
            "ok": True,
            "chat_id": chat.id if chat else None,
            "title": getattr(chat, "title", None),
        }

    async def search_global(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.ensure_connected():
            raise RuntimeError("Аккаунт не подключён")
        results = []
        async for result in self._client.iter_messages(None, limit=limit, search=query):
            chat = await result.get_chat()
            sender = await result.get_sender()
            results.append({
                "message_id": result.id,
                "date": result.date.isoformat() if result.date else None,
                "text": result.text or "",
                "chat_id": chat.id if chat else None,
                "chat_title": getattr(chat, "title", None) if chat else None,
                "sender_id": result.sender_id,
                "sender_username": sender.username if sender else None,
                "sender_name": f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip() if sender else None,
            })
        return results

    async def get_chat_messages(self, entity: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.ensure_connected():
            raise RuntimeError("Аккаунт не подключён")
        target = await self._resolve_entity(entity)
        messages = []
        async for message in self._client.iter_messages(target, limit=limit):
            sender = await message.get_sender()
            messages.append({
                "message_id": message.id,
                "date": message.date.isoformat() if message.date else None,
                "text": message.text or "",
                "sender_id": message.sender_id,
                "sender_username": sender.username if sender else None,
                "sender_name": f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip() if sender else None,
            })
        return messages


def get_manager() -> TelegramAccountManager:
    global _INSTANCE
    if _INSTANCE is None:
        with _INSTANCE_LOCK:
            if _INSTANCE is None:
                _INSTANCE = TelegramAccountManager()
    return _INSTANCE


# ----------------------------------------------------------------------
# Tool functions exposed to the agent
# ----------------------------------------------------------------------
def _not_configured_result() -> ToolResult:
    return ToolResult(
        False,
        None,
        "Telegram-аккаунт не настроен. Откройте Настройки → Telegram-аккаунт и пройдите авторизацию.",
    )


def _run_async(coro):
    """Run an async coroutine synchronously."""
    import asyncio
    try:
        return asyncio.get_event_loop().run_until_complete(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def telegram_account_info() -> ToolResult:
    manager = get_manager()
    if not manager.is_configured():
        return _not_configured_result()
    try:
        info = _run_async(manager.get_me())
        dialogs = _run_async(manager.get_dialogs(limit=1000))
        total_unread = sum(d.get("unread_count", 0) for d in dialogs)
        return ToolResult(
            True,
            {
                "account": info,
                "total_dialogs": len(dialogs),
                "total_unread": total_unread,
            },
        )
    except Exception as exc:
        return ToolResult(False, None, f"Ошибка получения информации об аккаунте: {exc}")


def telegram_get_chats(limit: int = 50) -> ToolResult:
    manager = get_manager()
    if not manager.is_configured():
        return _not_configured_result()
    try:
        dialogs = _run_async(manager.get_dialogs(limit=limit))
        return ToolResult(True, {"chats": dialogs})
    except Exception as exc:
        return ToolResult(False, None, f"Ошибка получения чатов: {exc}")


def telegram_get_unread(limit: int = 50) -> ToolResult:
    manager = get_manager()
    if not manager.is_configured():
        return _not_configured_result()
    try:
        messages = _run_async(manager.get_unread_messages(limit=limit))
        return ToolResult(True, {"messages": messages})
    except Exception as exc:
        return ToolResult(False, None, f"Ошибка получения непрочитанных: {exc}")


def telegram_send_message(entity: str, text: str) -> ToolResult:
    manager = get_manager()
    if not manager.is_configured():
        return _not_configured_result()
    try:
        result = _run_async(manager.send_message(entity, text))
        return ToolResult(True, result)
    except Exception as exc:
        return ToolResult(False, None, f"Ошибка отправки сообщения: {exc}")


def telegram_join_chat(link_or_username: str) -> ToolResult:
    manager = get_manager()
    if not manager.is_configured():
        return _not_configured_result()
    try:
        result = _run_async(manager.join_chat(link_or_username))
        return ToolResult(True, result)
    except Exception as exc:
        return ToolResult(False, None, f"Ошибка присоединения к чату: {exc}")


def telegram_request_join(invite_link: str) -> ToolResult:
    manager = get_manager()
    if not manager.is_configured():
        return _not_configured_result()
    try:
        result = _run_async(manager.request_join(invite_link))
        return ToolResult(True, result)
    except Exception as exc:
        return ToolResult(False, None, f"Ошибка запроса на вступление: {exc}")


def telegram_global_search(query: str, limit: int = 20) -> ToolResult:
    manager = get_manager()
    if not manager.is_configured():
        return _not_configured_result()
    try:
        results = _run_async(manager.search_global(query, limit=limit))
        return ToolResult(True, {"results": results})
    except Exception as exc:
        return ToolResult(False, None, f"Ошибка глобального поиска: {exc}")


def telegram_get_messages(entity: str, limit: int = 50) -> ToolResult:
    manager = get_manager()
    if not manager.is_configured():
        return _not_configured_result()
    try:
        messages = _run_async(manager.get_chat_messages(entity, limit=limit))
        return ToolResult(True, {"messages": messages})
    except Exception as exc:
        return ToolResult(False, None, f"Ошибка получения сообщений чата: {exc}")
