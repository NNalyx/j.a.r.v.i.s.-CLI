#!/usr/bin/env python3
"""
Jarvis Telegram Bot Integration — Синхронная интеграция с Telegram

Использует библиотеку pyTelegramBotAPI (telebot) для:
• Приёма сообщений от пользователя
• Отправки ответов от Jarvis
• Верификации хозяина по коду подтверждения
• Команды /reset_tg для сброса токена
"""

import json
import os
import threading
import time
import random
from typing import Optional, Callable, Dict, Any
from datetime import datetime

# Путь к файлу памяти (там же где jarvis_agent_cli.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "jarvis_memory.json")

# Токен бота и host_id храним отдельно от общей памяти,
# чтобы не попадать в git и не светиться в обычном JSON.
TELEGRAM_SECRET_FILE = os.path.join(BASE_DIR, "jarvis_telegram_secret.json")


def _load_telegram_secret() -> Dict[str, Any]:
    """Загрузить токен и host_id из секретного файла."""
    if not os.path.exists(TELEGRAM_SECRET_FILE):
        return {}
    try:
        with open(TELEGRAM_SECRET_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_telegram_secret(bot_token: Optional[str], host_id: Optional[int]) -> None:
    """Сохранить токен и host_id в секретный файл."""
    data: Dict[str, Any] = {"saved_at": datetime.now().isoformat()}
    if bot_token is not None:
        data["bot_token"] = bot_token
    if host_id is not None:
        data["host_id"] = host_id
    try:
        with open(TELEGRAM_SECRET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"{Colors.RED}[Telegram] Ошибка сохранения секрета: {e}{Colors.RESET}")


def _delete_telegram_secret() -> None:
    """Удалить секретный файл Telegram."""
    try:
        if os.path.exists(TELEGRAM_SECRET_FILE):
            os.remove(TELEGRAM_SECRET_FILE)
    except Exception as e:
        print(f"{Colors.RED}[Telegram] Ошибка удаления секрета: {e}{Colors.RESET}")

# Цвета для консоли
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"
    WHITE = "\033[37m"
    
    # Яркие цвета
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_RED = "\033[91m"


class TelegramBotManager:
    """
    Менеджер Telegram бота для Jarvis
    
    Хранит:
    - bot_token: токен бота от BotFather
    - host_id: Telegram ID хозяина (после верификации)
    - verification_code: код для текущей верификации
    - is_verified: флаг успешной верификации
    """
    
    def __init__(self):
        self.bot_token: Optional[str] = None
        self.host_id: Optional[int] = None
        self.verification_code: Optional[str] = None
        self.is_verified: bool = False
        self.bot = None
        self._listener_thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._message_callback: Optional[Callable[[str, int], str]] = None
        self._status_callback: Optional[Callable[[], str]] = None
        
    def load_credentials(self) -> bool:
        """Загрузить токен и host_id из секретного файла."""
        try:
            secret = _load_telegram_secret()
            self.bot_token = secret.get("bot_token") or None
            self.host_id = secret.get("host_id")
            if isinstance(self.host_id, str):
                try:
                    self.host_id = int(self.host_id)
                except ValueError:
                    self.host_id = None

            if self.bot_token and self.host_id:
                self.is_verified = True

                # Создаём объект бота
                import telebot
                self.bot = telebot.TeleBot(self.bot_token, threaded=True)

                print(f"{Colors.GREEN}[Telegram] Бот подключён и верифицирован (host_id: {self.host_id}){Colors.RESET}")
                return True
            elif self.bot_token:
                print(f"{Colors.YELLOW}[Telegram] Бот подключён, но требует верификации{Colors.RESET}")
                return False

            return False
        except Exception as e:
            print(f"{Colors.RED}[Telegram] Ошибка загрузки: {e}{Colors.RESET}")
            return False

    def save_credentials(self):
        """Сохранить токен и host_id в секретный файл (не в общую память)."""
        _save_telegram_secret(self.bot_token, self.host_id)
        print(f"{Colors.GREEN}[Telegram] Учётные данные сохранены{Colors.RESET}")

    def clear_credentials(self):
        """Удалить токен и host_id."""
        _delete_telegram_secret()

        self.bot_token = None
        self.host_id = None
        self.is_verified = False
        self._running = False

        print(f"{Colors.YELLOW}[Telegram] Учётные данные удалены{Colors.RESET}")
    
    def connect(self, token: str) -> bool:
        """
        Подключиться к Telegram боту

        Args:
            token: Токен бота от BotFather

        Returns:
            True если успешно
        """
        try:
            import telebot

            self.bot_token = token
            self.bot = telebot.TeleBot(token, threaded=True)

            # Проверяем токен
            me = self.bot.get_me()
            print(f"{Colors.GREEN}[Telegram] Подключён бот: @{me.username} ({me.first_name}){Colors.RESET}")

            # Генерируем код верификации
            self.verification_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            
            # Сбрасываем флаг верификации при новом подключении
            self.is_verified = False

            return True

        except ImportError:
            print(f"{Colors.RED}[Telegram] telebot не установлен. Установите: pip install pyTelegramBotAPI{Colors.RESET}")
            return False
        except Exception as e:
            print(f"{Colors.RED}[Telegram] Ошибка подключения: {e}{Colors.RESET}")
            return False
    
    def start_verification(self) -> str:
        """
        Начать верификацию хозяина
        
        Returns:
            Код верификации для отправки в бота
        """
        if not self.bot:
            return ""
        
        self.is_verified = False
        
        print(f"\n{Colors.CYAN}{'='*60}{Colors.RESET}")
        print(f"{Colors.BRIGHT_MAGENTA}🔐 ВЕРИФИКАЦИЯ ХОЗЯИНА{Colors.RESET}")
        print(f"{Colors.CYAN}{'='*60}{Colors.RESET}")
        print(f"\n{Colors.WHITE}Откройте диалог с ботом @{self.bot.get_me().username} и отправьте:{Colors.RESET}")
        print(f"\n  {Colors.BRIGHT_GREEN}█{Colors.BRIGHT_YELLOW}█{Colors.BRIGHT_GREEN}█{Colors.RESET} {Colors.BOLD}{self.verification_code}{Colors.RESET} {Colors.BRIGHT_YELLOW}█{Colors.BRIGHT_GREEN}█{Colors.BRIGHT_YELLOW}█{Colors.RESET}")
        print(f"\n{Colors.DIM}Это подтвердит что вы владелец бота и Jarvis.{Colors.RESET}")
        print(f"{Colors.CYAN}{'='*60}{Colors.RESET}\n")
        
        return self.verification_code
    
    def set_message_callback(self, callback: Callable[[str, int], str]):
        """
        Установить колбэк для обработки сообщений
        
        Args:
            callback: Функция(message_text, from_id) -> response_text
        """
        self._message_callback = callback
    
    def set_status_callback(self, callback: Callable[[], str]):
        """
        Установить колбэк для получения статуса Jarvis
        
        Args:
            callback: Функция() -> status_text
        """
        self._status_callback = callback
    
    def _handle_message(self, message):
        """Обработчик входящих сообщений"""
        try:
            from_id = message.from_user.id
            from_username = message.from_user.username or message.from_user.first_name
            text = message.text or ""
            
            # Отладка: показываем все входящие сообщения
            print(f"{Colors.DIM}[Telegram] Входящее: '{text}' от {from_username} (ID: {from_id}){Colors.RESET}")
            print(f"{Colors.DIM}[Telegram] is_verified={self.is_verified}, verification_code={self.verification_code}{Colors.RESET}")
            
            # Команда /start
            if text == "/start":
                if self.is_verified and from_id == self.host_id:
                    self.bot.reply_to(message, 
                        f"✅ Jarvis онлайн!\n\n"
                        f"Хозяин: {from_username}\n"
                        f"Отправляйте сообщения для обработки.")
                else:
                    self.bot.reply_to(message,
                        f"🔐 Jarvis ожидает верификации.\n\n"
                        f"Отправьте код: `{self.verification_code}`")
                return
            
            # Команда /reset_tg
            if text == "/reset_tg":
                if self.is_verified and from_id == self.host_id:
                    self.clear_credentials()
                    self.bot.reply_to(message,
                        "🗑️ Учётные данные Telegram удалены.\n\n"
                        "Перезапустите Jarvis для повторной настройки.")
                else:
                    self.bot.reply_to(message, "⛔ Доступ запрещён.")
                return
            
            # Команда /status
            if text == "/status":
                if self._status_callback:
                    status = self._status_callback()
                    self.bot.reply_to(message, f"📊 {status}")
                else:
                    self.bot.reply_to(message, "📊 Jarvis онлайн")
                return
            
            # Верификация по коду
            if not self.is_verified:
                if text.strip() == self.verification_code:
                    self.host_id = from_id
                    self.is_verified = True
                    self.save_credentials()
                    
                    self.bot.reply_to(message,
                        f"✅ **ВЕРИФИКАЦИЯ УСПЕШНА!**\n\n"
                        f"Ваш ID: `{from_id}`\n"
                        f"Теперь вы можете управлять Jarvis.\n\n"
                        f"Команды:\n"
                        f"/status — статус Jarvis\n"
                        f"/reset_tg — отвязать бота\n\n"
                        f"Отправляйте любые сообщения для обработки.")
                    
                    print(f"{Colors.GREEN}[Telegram] Хозяин верифицирован: {from_username} (ID: {from_id}){Colors.RESET}")
                else:
                    self.bot.reply_to(message,
                        f"❌ Неверный код.\n\n"
                        f"Ожидается: `{self.verification_code}`\n"
                        f"Попробуйте ещё раз или перезапустите Jarvis.")
                return
            
            # Проверка хозяина
            if from_id != self.host_id:
                self.bot.reply_to(message, "⛔ Доступ запрещён. Только хозяин может управлять Jarvis.")
                return
            
            # Обработка сообщения от хозяина
            print(f"{Colors.MAGENTA}[Telegram] Сообщение от хозяина: {text[:50]}...{Colors.RESET}")

            # Добавляем префикс !PH для обозначения "с телефона"
            if self._message_callback:
                response = self._message_callback(f"!PH {text}", from_id)

                if response:
                    # Проверяем что это кортеж (текст, скриншот)
                    if isinstance(response, tuple):
                        response_text, screenshot_path = response
                    else:
                        response_text = response
                        screenshot_path = None

                    # Отправляем текст (разбиваем на части если длинный)
                    self._send_long_message(message.chat.id, response_text)
                    
                    # Отправляем скриншот если есть
                    if screenshot_path and os.path.exists(screenshot_path):
                        try:
                            with open(screenshot_path, 'rb') as photo:
                                self.bot.send_photo(message.chat.id, photo)
                                print(f"{Colors.DIM}[Telegram] Скриншот отправлен{Colors.RESET}")
                        except Exception as e:
                            print(f"{Colors.YELLOW}[Telegram] Ошибка отправки скриншота: {e}{Colors.RESET}")
                        
                        # Удаляем временный файл
                        try:
                            os.remove(screenshot_path)
                        except:
                            pass
            
        except Exception as e:
            print(f"{Colors.RED}[Telegram] Ошибка обработки сообщения: {e}{Colors.RESET}")
            try:
                self.bot.reply_to(message, f"⚠️ Ошибка: {str(e)}")
            except:
                pass
    
    def _send_long_message(self, chat_id: int, text: str, max_length: int = 4000):
        """Отправить длинное сообщение частями"""
        try:
            if len(text) <= max_length:
                self.bot.send_message(chat_id, text, parse_mode="Markdown")
            else:
                # Разбиваем на части
                parts = []
                current = ""
                
                for line in text.split("\n"):
                    if len(current) + len(line) + 1 <= max_length:
                        current += line + "\n"
                    else:
                        parts.append(current)
                        current = line + "\n"
                
                if current:
                    parts.append(current)
                
                for i, part in enumerate(parts):
                    if i > 0:
                        time.sleep(0.5)  # Пауза между частями
                    self.bot.send_message(chat_id, part, parse_mode="Markdown")
                    
        except Exception as e:
            print(f"{Colors.RED}[Telegram] Ошибка отправки: {e}{Colors.RESET}")
    
    def start_listening(self):
        """Запустить слушатель сообщений в отдельном потоке"""
        if not self.bot:
            print(f"{Colors.RED}[Telegram] Бот не подключён{Colors.RESET}")
            return
        
        if self._running:
            print(f"{Colors.YELLOW}[Telegram] Уже слушает{Colors.RESET}")
            return
        
        self._running = True
        
        # Регистрируем обработчики
        self.bot.message_handler(func=lambda message: True)(self._handle_message)
        
        # Запускаем в отдельном потоке
        def run_polling():
            print(f"{Colors.GREEN}[Telegram] Запуск слушателя сообщений...{Colors.RESET}")
            self.bot.infinity_polling(timeout=10, long_polling_timeout=30)
        
        self._listener_thread = threading.Thread(target=run_polling, daemon=True)
        self._listener_thread.start()
        
        # Даём время на запуск
        time.sleep(1)
    
    def stop_listening(self):
        """Остановить слушатель"""
        self._running = False
        if self.bot:
            try:
                self.bot.stop_polling()
            except:
                pass
        print(f"{Colors.YELLOW}[Telegram] Слушатель остановлен{Colors.RESET}")
    
    def send_message(self, text: str):
        """Отправить сообщение хозяину"""
        if not self.bot or not self.is_verified or not self.host_id:
            return
        
        try:
            self._send_long_message(self.host_id, text)
        except Exception as e:
            print(f"{Colors.RED}[Telegram] Ошибка отправки: {e}{Colors.RESET}")
    
    def is_connected(self) -> bool:
        """Проверить подключён ли бот"""
        return self.bot_token is not None
    
    def is_ready(self) -> bool:
        """Проверить готовность (подключён + верифицирован)"""
        return self.is_connected() and self.is_verified


# Глобальный экземпляр
_telegram_bot: Optional[TelegramBotManager] = None


def get_bot() -> Optional[TelegramBotManager]:
    """Получить глобальный экземпляр бота"""
    global _telegram_bot
    return _telegram_bot


def init_bot() -> TelegramBotManager:
    """Инициализировать глобальный бот"""
    global _telegram_bot
    _telegram_bot = TelegramBotManager()
    return _telegram_bot
