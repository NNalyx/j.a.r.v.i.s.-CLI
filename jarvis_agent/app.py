"""Jarvis console application entry point."""
import base64
import json
import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional

import requests

from jarvis_core.colors import Colors
from jarvis_core.config import LLAMA_SERVER_PRESETS
from jarvis_core.constants import (
    DEFAULT_MODEL_KEY,
    DEFAULT_TRANSCRIPTION_BACKEND_KEY,
    MEMORY_FILE,
    TELEGRAM_AVAILABLE,
    TelegramBotManager,
    VOICE_AVAILABLE,
    VoiceActivator,
    get_bot,
    get_transcription_backend_catalog,
    init_bot,
)
from jarvis_memory.manager import MemoryManager
from jarvis_tts.tts import TTS
from jarvis_ui.console import UI

from .agent import QwenAgent


class QwenAgentApp:
    """Консольное приложение Jarvis AI Assistant"""

    def __init__(self, interactive_prompts: bool = True, init_voice: bool = True, init_telegram: bool = True):
        self.agent = QwenAgent(app=self)  # Передаём ссылку на себя для управления флагами
        self.show_thinking = True
        self.streaming = True
        self.running = True
        self.interactive_prompts = interactive_prompts
        self.init_voice_enabled = init_voice
        self.init_telegram_enabled = init_telegram
        self.selected_model_key = DEFAULT_MODEL_KEY
        self.current_image_path: Optional[str] = None
        self._last_llama_server_process: Optional[subprocess.Popen] = None
        self.temp_dir = os.path.join(os.environ.get("TEMP", "."), "jarvis_agent_images")
        os.makedirs(self.temp_dir, exist_ok=True)

        # Голосовая активация
        self.voice_activator: Optional[VoiceActivator] = None
        self.voice_enabled = False
        self.voice_backend_key = DEFAULT_TRANSCRIPTION_BACKEND_KEY
        self._voice_request_lock = threading.Lock()
        self._voice_request_active = False

        # Telegram бот
        self.telegram_bot: Optional[TelegramBotManager] = None
        self.telegram_enabled = False
        self.telegram_mode = False  # Флаг: обрабатывается ли сообщение из Telegram

        # Инициализация памяти при запуске
        self._init_memory()

        # Инициализация голосовой активации
        if self.init_voice_enabled:
            self._init_voice()

        # Инициализация Telegram бота
        if self.init_telegram_enabled:
            self._init_telegram()

    def _init_memory(self):
        """Проверить и создать файл памяти если не существует"""
        try:
            if not os.path.exists(MEMORY_FILE):
                MemoryManager.write("Память пуста. Нет сохраненной информации о пользователе или сессиях.")
                print(f"{Colors.BRIGHT_GREEN}[MEMORY] Файл памяти создан: {MEMORY_FILE}{Colors.RESET}")
            else:
                print(f"{Colors.BRIGHT_GREEN}[MEMORY] Память загружена из: {MEMORY_FILE}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}[MEMORY] Предупреждение: не удалось инициализировать память: {e}{Colors.RESET}")

    def _init_voice(self):
        """Инициализировать голосовую активацию"""
        if not VOICE_AVAILABLE:
            return

        try:
            self.voice_activator = VoiceActivator(transcription_backend_key=self.voice_backend_key)

            # Устанавливаем callback
            self.voice_activator.set_callback(self._on_voice_command)
            self.voice_activator.set_status_callback(self._on_voice_status)

            # Инициализируем модели
            self.voice_activator.init_models()
        except Exception as e:
            import traceback
            print(f"[VOICE] Ошибка: {e}")
            print(traceback.format_exc())
            self.voice_activator = None

    def get_voice_backend_options(self) -> List[Dict[str, Any]]:
        if self.voice_activator is not None and hasattr(self.voice_activator, "get_backend_options"):
            return self.voice_activator.get_backend_options()

        options = []
        for backend in get_transcription_backend_catalog():
            item = dict(backend)
            item["selected"] = item.get("key") == self.voice_backend_key
            options.append(item)
        return options

    def set_voice_backend(self, backend_key: str) -> None:
        if not backend_key:
            backend_key = DEFAULT_TRANSCRIPTION_BACKEND_KEY

        self.voice_backend_key = backend_key
        if self.voice_activator is not None and hasattr(self.voice_activator, "set_command_backend"):
            self.voice_activator.set_command_backend(backend_key)

    def _on_voice_command(self, command: str):
        """Обработка голосовой команды"""
        with self._voice_request_lock:
            if self._voice_request_active:
                print(f"\n{Colors.YELLOW}[Голос] Новая команда проигнорирована: предыдущая ещё обрабатывается{Colors.RESET}")
                return
            self._voice_request_active = True

        # Добавляем метку !STT для обозначения распознанного текста
        command_with_marker = f"!STT {command}"

        def _voice_worker():
            try:
                # Голосовые запросы отправляем сразу агенту
                self._send_message(command_with_marker)
            finally:
                with self._voice_request_lock:
                    self._voice_request_active = False

        threading.Thread(target=_voice_worker, daemon=True, name="VoiceCommandWorker").start()

    def _on_voice_status(self, status: str):
        """Обновление статуса голосовой активации"""
        # Выводим статус в консоль
        print(f"\r{Colors.BRIGHT_MAGENTA}{status}{Colors.RESET}                    ", end="")
        sys.stdout.flush()

    def _init_telegram(self):
        """Инициализировать Telegram бота (загрузка учётных данных)"""
        if not TELEGRAM_AVAILABLE:
            return

        try:
            # Инициализируем менеджер
            self.telegram_bot = init_bot()

            # Загружаем учётные данные
            if self.telegram_bot.load_credentials():
                # Бот подключён и верифицирован
                self.telegram_enabled = True

                # Устанавливаем колбэки
                self.telegram_bot.set_message_callback(self._handle_telegram_message)
                self.telegram_bot.set_status_callback(self._get_jarvis_status)

                # Запускаем слушатель
                self.telegram_bot.start_listening()
                print(f"{Colors.GREEN}[Telegram] Бот запущен и готов к работе{Colors.RESET}")
            # Если не загружены — просто молчим, настройка через /tg
        except Exception as e:
            import traceback
            print(f"{Colors.YELLOW}[Telegram] Ошибка инициализации: {e}{Colors.RESET}")
            print(traceback.format_exc())
            self.telegram_bot = None

    def _handle_telegram_command(self, command: str):
        """
        Обработка команды /tg

        Подкоманды:
        - /tg connect — подключить бота
        - /tg reset — отвязать бота
        - /tg (без аргументов) — показать статус
        """
        if not TELEGRAM_AVAILABLE:
            UI.print_error("Telegram не доступен. Установите: pip install pyTelegramBotAPI")
            return

        parts = command.split(maxsplit=1)
        subcmd = parts[1].lower() if len(parts) > 1 else ""

        # Показать статус
        if not subcmd:
            if self.telegram_bot and self.telegram_bot.is_verified:
                UI.print_status(f"Telegram бот подключён и верифицирован", "success")
                print(f"  Хозяин ID: {self.telegram_bot.host_id}")
                if self.telegram_bot.bot:
                    print(f"  Бот: @{self.telegram_bot.bot.get_me().username}")
                else:
                    print(f"  {Colors.YELLOW}⚠ Бот не инициализирован — перезапустите Jarvis{Colors.RESET}")
            elif self.telegram_bot and self.telegram_bot.bot_token:
                UI.print_status("Telegram бот подключён, но требует верификации", "warning")
            else:
                UI.print_status("Telegram бот не подключён", "info")
                print(f"\n{Colors.WHITE}Используйте:{Colors.RESET}")
                print(f"  {Colors.BRIGHT_CYAN}/tg connect{Colors.RESET} — подключить бота")
                print(f"  {Colors.BRIGHT_CYAN}/tg reset{Colors.RESET} — отвязать бота")
            return

        # Подключить
        if subcmd == "connect":
            if self.telegram_bot and self.telegram_bot.is_verified:
                UI.print_error("Бот уже подключён и верифицирован")
                return

            self._setup_telegram_bot()
            return

        # Сбросить
        if subcmd == "reset" or subcmd == "disconnect":
            if not self.telegram_bot or not self.telegram_bot.bot_token:
                UI.print_error("Бот не подключён")
                return

            self.telegram_bot.clear_credentials()
            self.telegram_enabled = False
            self.telegram_bot.stop_listening()
            UI.print_status("Telegram бот отключён", "success")
            print(f"  Используйте {Colors.BRIGHT_CYAN}/tg connect{Colors.RESET} для повторной настройки")
            return

        # Неизвестная подкоманда
        UI.print_error(f"Неизвестная подкоманда: {subcmd}")
        print(f"  {Colors.BRIGHT_CYAN}/tg connect{Colors.RESET} — подключить бота")
        print(f"  {Colors.BRIGHT_CYAN}/tg reset{Colors.RESET} — отвязать бота")

    def _setup_telegram_bot(self):
        """Настройка Telegram бота (первичная настройка)"""
        print(f"\n{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BRIGHT_MAGENTA}🤖 ПОДКЛЮЧЕНИЕ TELEGRAM БОТА{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}")
        print(f"\n{Colors.WHITE}Инструкция:{Colors.RESET}")
        print(f"  1. Откройте {Colors.BRIGHT_CYAN}@BotFather{Colors.RESET} в Telegram")
        print(f"  2. Отправьте: {Colors.YELLOW}/newbot{Colors.RESET}")
        print(f"  3. Введите имя бота (например: Jarvis Assistant)")
        print(f"  4. Введите username бота (должен заканчиваться на 'bot')")
        print(f"  5. Скопируйте полученный токен")
        print(f"\n{Colors.BRIGHT_CYAN}Пример токена:{Colors.RESET} 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
        print(f"\n{Colors.DIM}Нажмите Ctrl+C для отмены{Colors.RESET}")
        print(f"{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")

        try:
            token = input(f"{Colors.BRIGHT_GREEN}▶ Введите токен бота:{Colors.RESET} ").strip()

            if not token:
                print(f"{Colors.YELLOW}[Telegram] Отменено{Colors.RESET}")
                return

            # Инициализируем бота если ещё не создан
            if not self.telegram_bot:
                self.telegram_bot = init_bot()

            # Подключаемся
            if self.telegram_bot.connect(token):
                # Начинаем верификацию
                self.telegram_bot.start_verification()

                # Запускаем слушатель для приёма кода верификации
                self.telegram_bot.set_message_callback(self._handle_telegram_message)
                self.telegram_bot.set_status_callback(self._get_jarvis_status)
                self.telegram_bot.start_listening()

                # Ждём верификации (таймаут 90 секунд)
                print(f"\n{Colors.DIM}Ожидание подтверждения...{Colors.RESET}")
                print(f"{Colors.DIM}Откройте диалог с ботом и отправьте код{Colors.RESET}")
                start_time = time.time()
                timeout = 90

                while not self.telegram_bot.is_verified:
                    time.sleep(1)
                    elapsed = time.time() - start_time

                    if elapsed > timeout:
                        print(f"\n{Colors.RED}[Telegram] Превышено время ожидания{Colors.RESET}")
                        self.telegram_bot.stop_listening()
                        self.telegram_bot = None
                        return

                    # Выводим оставшееся время
                    remaining = int(timeout - elapsed)
                    print(f"\r{Colors.CYAN}⟳ Ожидание: {remaining} сек...{Colors.RESET}", end="")
                    sys.stdout.flush()

                # Успешно верифицирован
                self.telegram_enabled = True
                print(f"\n{Colors.GREEN}[Telegram] Бот подключён и готов к работе!{Colors.RESET}")
            else:
                print(f"{Colors.RED}[Telegram] Не удалось подключиться{Colors.RESET}")

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}[Telegram] Отменено{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}[Telegram] Ошибка: {e}{Colors.RESET}")

    def _handle_telegram_message(self, message_text: str, from_id: int) -> tuple:
        """
        Обработка сообщения от Telegram

        Args:
            message_text: Текст сообщения (уже с префиксом !PH)
            from_id: ID отправителя

        Returns:
            Кортеж (текст_ответа, путь_к_скриншоту)
        """
        # Проверяем что бот ещё активен
        if not self.telegram_bot or not self.telegram_bot.is_verified:
            return ("⚠️ Jarvis недоступен", None)

        # Проверяем хозяина
        if from_id != self.telegram_bot.host_id:
            return ("⛔ Доступ запрещён", None)

        # Извлекаем текст без префикса !PH для вывода в консоль
        display_text = message_text
        if message_text.startswith("!PH "):
            display_text = message_text[4:]

        # Выводим сообщение в консоль с рамкой (как обычный ввод)
        UI.print_user_message(display_text, prefix="📱 Telegram")

        # Отправляем агенту и получаем ответ
        # Для этого используем временную переменную для хранения ответа
        response_container = {"text": "", "screenshot": None}

        try:
            # Запускаем обработку через агент
            # Используем _send_message напрямую
            # message_text уже содержит !PH префикс!
            self._send_message_telegram(message_text, response_container)

        except Exception as e:
            response_container["text"] = f"⚠️ Ошибка: {str(e)}"

        return (response_container["text"], response_container.get("screenshot"))

    def _send_message_telegram(self, content: str, response_container: Dict):
        """
        Отправка сообщения для Telegram (без запоминания)

        Args:
            content: Текст сообщения
            response_container: Словарь для хранения ответа {"text": "..."}
        """
        # Устанавливаем флаг Telegram режима
        self.telegram_mode = True

        try:
            # Показываем анимацию мышления если не потоковый режим
            if not self.streaming:
                UI.print_thinking_animation()

            # Временно добавляем напоминание в системный промпт
            # чтобы модель не использовала manage_memory для Telegram
            original_system = self.agent.system_prompt

            telegram_note = "\n\n📱 **Сейчас пользователь пишет с Telegram — не используй manage_memory, просто отвечай!**"
            self.agent.system_prompt = original_system + telegram_note
            self.agent.refresh_system_prompt()

            try:
                # Отправляем запрос агенту напрямую
                for result in self.agent.send_message(
                        content,
                        image_path=None,
                        stream=self.streaming,
                        show_thinking=self.show_thinking
                ):
                    if result["type"] == "final":
                        # Статистика
                        if result.get("iterations"):
                            max_iterations_label = "∞" if self.agent.max_iterations <= 0 else str(self.agent.max_iterations)
                            print(
                                f"\n{Colors.DIM}⚡ Итераций: {result['iterations']}/{max_iterations_label}{Colors.RESET}")

                        response_text = result["content"]

                        # При потоковом режиме ответ уже был выведен по мере генерации
                        if not self.streaming:
                            UI.print_assistant_response(response_text, "Ответ")

                        # Сохраняем ответ для отправки в Telegram
                        response_container["text"] = response_text

                        # Озвучивание НЕ включаем для Telegram сообщений

                        # Делаем скриншот экрана после ответа
                        screenshot_result = self._take_screenshot_for_telegram()
                        if screenshot_result:
                            response_container["screenshot"] = screenshot_result

            finally:
                # Восстанавливаем оригинальный системный промпт
                self.agent.system_prompt = original_system
                self.agent.refresh_system_prompt()
        finally:
            # Снимаем флаг Telegram режима
            self.telegram_mode = False

    def _take_screenshot_for_telegram(self) -> Optional[str]:
        """
        Сделать скриншот экрана для отправки в Telegram

        Returns:
            Путь к скриншоту или None
        """
        try:
            from PIL import ImageGrab
            import tempfile

            # Делаем скриншот
            screenshot = ImageGrab.grab()

            # Сохраняем во временный файл
            temp_path = os.path.join(tempfile.gettempdir(), f"tg_screenshot_{int(time.time())}.png")
            screenshot.save(temp_path, "PNG")

            print(f"{Colors.DIM}[Telegram] Скриншот сохранён: {temp_path}{Colors.RESET}")
            return temp_path

        except Exception as e:
            print(f"{Colors.YELLOW}[Telegram] Ошибка скриншота: {e}{Colors.RESET}")
            return None

    def _get_jarvis_status(self) -> str:
        """Получить статус Jarvis для Telegram"""
        status = "Jarvis онлайн\n\n"
        max_iterations_label = "∞" if self.agent.max_iterations <= 0 else str(self.agent.max_iterations)
        status += f"📊 Итераций максимум: {max_iterations_label}\n"
        status += f"🧠 Поток: {'вкл' if self.streaming else 'выкл'}\n"
        status += f"💭 Мысли: {'вкл' if self.show_thinking else 'выкл'}\n"

        if self.voice_enabled:
            status += "🎤 Голос: вкл\n"

        if self.telegram_enabled:
            status += "📱 Telegram: вкл\n"

        return status

    def _get_clipboard_image(self) -> Optional[str]:
        """Получить изображение из буфера"""
        try:
            from PIL import ImageGrab
            img = ImageGrab.grabclipboard()
            if img:
                temp_path = os.path.join(self.temp_dir, f"clipboard_{int(time.time())}.png")
                img.save(temp_path, "PNG")
                return temp_path
        except:
            pass

        if os.name == "nt":
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                if win32clipboard.IsClipboardFormatAvailable(15):
                    files = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
                    if files:
                        ext = os.path.splitext(files[0])[1].lower()
                        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
                            win32clipboard.CloseClipboard()
                            return files[0]
                win32clipboard.CloseClipboard()
            except:
                pass
        return None

    def get_model_presets(self) -> Dict[str, Dict[str, str]]:
        """Доступные пресеты llama-server."""
        return LLAMA_SERVER_PRESETS

    def get_selected_model_preset(self) -> Dict[str, str]:
        """Получить активный пресет модели."""
        presets = self.get_model_presets()
        if self.selected_model_key in presets:
            return presets[self.selected_model_key]
        if presets:
            first_key = next(iter(presets))
            self.selected_model_key = first_key
            return presets[first_key]
        raise ValueError("Нет сохранённых пресетов. Запустите настройку через jarvis_config.json.")

    def selected_model_supports_images(self) -> bool:
        """Поддерживает ли активный пресет входные изображения."""
        preset = self.get_selected_model_preset()
        return bool(preset.get("supports_images", False))

    def _choose_model_preset(self) -> str:
        """Спросить пользователя, какую модель запускать."""
        presets = list(self.get_model_presets().items())
        if not presets:
            raise ValueError("Нет сохранённых пресетов llama-server.")

        if not self.interactive_prompts:
            self.selected_model_key = presets[0][0]
            return self.selected_model_key

        print(f"\n{Colors.BRIGHT_CYAN}Выберите модель для запуска llama-server:{Colors.RESET}")
        for index, (key, preset) in enumerate(presets, 1):
            print(f"  {index}. {preset['label']} — {preset['description']}")

        while True:
            raw = input(f"{Colors.BRIGHT_GREEN}▶ Номер модели [1-{len(presets)}], Enter = 1:{Colors.RESET} ").strip()
            if not raw:
                self.selected_model_key = presets[0][0]
                return self.selected_model_key
            if raw.isdigit():
                selected_index = int(raw) - 1
                if 0 <= selected_index < len(presets):
                    self.selected_model_key = presets[selected_index][0]
                    return self.selected_model_key
            print(f"{Colors.YELLOW}Введите корректный номер модели.{Colors.RESET}")

    def _launch_llama_server_process(self, model_key: Optional[str] = None) -> str:
        """Запустить llama-server с указанным пресетом.

        Вывод сервера пишется в `llama_server.log` в корне проекта, а само
        консольное окно не показывается — это позволяет видеть причину
        падения, если процесс завершился сразу после запуска.
        """
        import subprocess

        model_key = model_key or self.selected_model_key or DEFAULT_MODEL_KEY
        preset = self.get_model_presets().get(model_key)
        if not preset:
            raise ValueError(f"Unknown model preset: {model_key}")

        self.selected_model_key = model_key
        launch_cwd = preset.get("cwd", "C:\\llama_server")

        # Предпочитаем готовый список аргументов. Если его нет — разбираем строку.
        args = preset.get("args")
        if not args:
            command = preset.get("command", "")
            if not command:
                raise ValueError(f"Preset {model_key} has no launch command")
            args = self._parse_command_args(command)

        if not args:
            raise ValueError(f"Preset {model_key} produced empty argument list")

        executable = args[0]
        if not os.path.exists(executable):
            raise FileNotFoundError(
                f"llama-server не найден по пути: {executable}\n"
                f"Проверьте настройки пресета в jarvis_config.json"
            )

        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "llama_server.log")
        log_path = os.path.normpath(log_path)
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")
        try:
            process = subprocess.Popen(
                args,
                cwd=launch_cwd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._last_llama_server_process = process
        finally:
            log_file.close()

        # Небольшая пауза, чтобы процесс либо упал с ошибкой, либо начал стартовать.
        time.sleep(1.5)
        if process.poll() is not None:
            log_tail = self._read_llama_server_log_tail(log_path)
            raise RuntimeError(
                f"llama-server завершился сразу после запуска (код {process.poll()}).\n"
                f"Последние строки лога ({log_path}):\n{log_tail}"
            )

        return preset["label"]

    @staticmethod
    def _read_llama_server_log_tail(log_path: str, lines: int = 40) -> str:
        """Вернуть последние строки лог-файла llama-server."""
        if not os.path.exists(log_path):
            return "(лог-файл не создан)"
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as exc:
            return f"(не удалось прочитать лог: {exc})"

    def shutdown_llama_server(self) -> bool:
        """Корректно завершить процесс llama-server, если он запущен."""
        process = getattr(self, "_last_llama_server_process", None)
        if process is None or process.poll() is not None:
            self._last_llama_server_process = None
            return False

        try:
            # Сначала мягко просим процесс завершиться.
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Если не завершился — принудительно убиваем.
                process.kill()
                process.wait(timeout=5)
            self._last_llama_server_process = None
            return True
        except Exception:
            return False

    @staticmethod
    def _parse_command_args(command: str) -> List[str]:
        """Разобрать командную строку в список аргументов (Windows-safe)."""
        import shlex

        try:
            args = shlex.split(command, posix=False)
        except ValueError:
            args = command.split()

        cleaned: List[str] = []
        for arg in args:
            arg = arg.strip()
            # shlex.split(posix=False) оставляет окружающие кавычки — убираем их
            if len(arg) >= 2 and arg[0] == arg[-1] == '"':
                arg = arg[1:-1]
            cleaned.append(arg)
        return cleaned

    def start_selected_llama_server(self, model_key: Optional[str] = None) -> bool:
        """Запустить выбранный preset llama-server и дождаться health-check."""
        UI.print_status("Сервер не найден. Запускаю llama-сервер...", "loading")

        try:
            if model_key:
                self.selected_model_key = model_key
            else:
                model_key = self._choose_model_preset()

            model_label = self._launch_llama_server_process(model_key)
            UI.print_status(f"Выбрана модель: {model_label}", "info")
            UI.print_status("Запуск сервера (может занять до 30 сек)...", "loading")

            for i in range(30, 0, -1):
                print(f"\r{Colors.BRIGHT_CYAN}⟳ Ожидание запуска: {i} сек...{Colors.RESET}", end="")
                sys.stdout.flush()

                if self.agent.check_health():
                    print()
                    UI.print_status("Сервер запущен и доступен!", "success")
                    return True

                time.sleep(1)

            print()
            UI.print_error("Таймаут ожидания сервера")
            return False
        except Exception as e:
            UI.print_error(f"Не удалось запустить сервер: {e}")
            return False

    def _start_llama_server(self):
        """Автозапуск llama-сервера (fallback для CLI)."""
        UI.print_status("Сервер не найден. Запускаю llama-сервер...", "loading")

        args = [
            r"C:\llama_server\llama-server.exe",
            "-m", r"C:\llama_server\Qwen3.5-9B.Q4_K_M.gguf",
            "--mmproj", r"C:\llama_server\mmproj.gguf",
            "--image-min-tokens", "1024",
            "-c", "18432",
            "-ngl", "99",
            "--flash-attn", "on",
        ]

        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "llama_server.log")
        log_path = os.path.normpath(log_path)
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")
        try:
            process = subprocess.Popen(
                args,
                cwd=r"C:\llama_server",
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._last_llama_server_process = process
        finally:
            log_file.close()

        time.sleep(1.5)
        if process.poll() is not None:
            log_tail = self._read_llama_server_log_tail(log_path)
            UI.print_error(
                f"llama-server завершился сразу после запуска (код {process.poll()}).\n"
                f"Последние строки лога ({log_path}):\n{log_tail}"
            )
            return False

        UI.print_status("Запуск сервера (может занять до 30 сек)...", "loading")
        server_ready = False
        for i in range(30, 0, -1):
            print(f"\r{Colors.BRIGHT_CYAN}⟳ Ожидание запуска: {i} сек...{Colors.RESET}", end="")
            sys.stdout.flush()

            if not server_ready and self.agent.check_health():
                server_ready = True
                print()
                UI.print_status("Сервер запущен и доступен!", "success")
                return True

            time.sleep(1)
        print()

        if server_ready:
            return True
        else:
            UI.print_error("Таймаут ожидания сервера")
            return False

    def run(self):
        """Запуск приложения"""
        # Красивый экран загрузки FRIDAY
        UI.print_loading_screen()

        UI.clear()
        UI.print_banner()

        UI.print_status("Проверка подключения к серверу...", "loading")

        # Если сервер не доступен — пробуем запустить
        if not self.agent.check_health():
            if self.start_selected_llama_server():
                # Проверяем ещё раз после запуска
                if not self.agent.check_health():
                    UI.print_error(
                        f"Не удалось подключиться к серверу {self.agent.base_url}\n\n"
                        f"Убедитесь, что сервер запущен"
                    )
                    UI.print_status("Нажмите Enter для выхода...", "warning")
                    input()
                    return
            else:
                UI.print_error(
                    f"Не удалось подключиться к серверу {self.agent.base_url}\n\n"
                    f"Убедитесь, что:\n"
                    f"  1. Файлы модели и llama-server указаны верно в jarvis_config.json\n"
                    f"  2. llama-server.exe действительно запущен и слушает порт 8080"
                )
                UI.print_status("Нажмите Enter для выхода...", "warning")
                input()
                return

        UI.print_status("Сервер доступен ✓", "success")
        UI.print_separator()

        # Запускаем голосовую активацию если доступна
        if self.voice_enabled and self.voice_activator:
            self.voice_activator.start_listening()
            UI.print_status("🎤 Голосовая активация запущена", "success")

        while self.running:
            try:
                self._handle_input()
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Прервано пользователем{Colors.RESET}")
                continue
            except Exception as e:
                UI.print_error(str(e))

        # Останавливаем голосовую активацию при выходе
        if self.voice_activator:
            self.voice_activator.stop_listening()

        # Останавливаем Telegram бота при выходе
        if self.telegram_bot:
            self.telegram_bot.stop_listening()

    def _handle_input(self):
        """Обработка ввода"""
        user_input = UI.print_input_prompt()

        if not user_input:
            return

        if user_input.lower() == '/paste':
            self._paste_from_clipboard()
            return

        if user_input.startswith('/'):
            self._handle_command(user_input)
            return

        # Проверка на путь к изображению
        stripped = user_input.strip('"\'')
        if os.path.exists(stripped):
            ext = os.path.splitext(stripped)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']:
                self.current_image_path = stripped
                UI.print_status(f"Изображение: {os.path.basename(stripped)}", "success")
                UI.print_status("Введите ваш вопрос (изображение прикрепится)", "info")
                return

        # Отправляем запрос агенту
        if self.current_image_path:
            image_path = self.current_image_path
            self.current_image_path = None
            self._send_message(user_input, image_path)
        else:
            self._send_message(user_input)

    def _paste_from_clipboard(self):
        """Вставить из буфера"""
        image_path = self._get_clipboard_image()
        if image_path:
            self.current_image_path = image_path
            UI.print_status("Изображение из буфера готово", "success")
            UI.print_status("Введите вопрос (изображение прикрепится)", "info")
        else:
            UI.print_error("Не удалось получить изображение\n\nСделайте скриншот (Win+Shift+S) и попробуйте снова")

    def _handle_command(self, command: str):
        """Обработка команд"""
        cmd = command.lower().strip()

        if cmd == '/help':
            UI.print_help()

        elif cmd == '/clear':
            UI.clear()
            UI.print_banner()
            UI.print_status("Экран очищен", "success")

        elif cmd == '/new':
            self.agent.reset_history()
            UI.print_status("История очищена", "success")

        elif cmd == '/think':
            self.show_thinking = not self.show_thinking
            UI.print_status(f"Мысли: {'вкл' if self.show_thinking else 'выкл'}", "info")

        elif cmd == '/stream':
            self.streaming = not self.streaming
            UI.print_status(f"Поток: {'вкл' if self.streaming else 'выкл'}", "info")

        elif cmd == '/tts':
            if not TTS_AVAILABLE:
                UI.print_error(
                    "Supertonic недоступен. Установите: pip install supertonic numpy sounddevice soundfile")
            elif TTS.is_enabled():
                TTS.disable()
                UI.print_status("Голосовой вывод выключен 🔇", "info")
            else:
                if TTS.enable():
                    UI.print_status("Голосовой вывод включен 🔊", "success")
                else:
                    UI.print_error("Не удалось загрузить Supertonic модель")

        elif cmd == '/voice':
            if not VOICE_AVAILABLE:
                UI.print_error("Голосовая активация недоступна")
            elif self.voice_activator is None:
                UI.print_error("Голосовая активация не инициализирована")
            elif self.voice_enabled:
                self.voice_enabled = False
                if self.voice_activator:
                    self.voice_activator.stop_listening()
            else:
                self.voice_enabled = True
                if self.voice_activator:
                    self.voice_activator.start_listening()

        elif cmd == '/tg' or cmd.startswith('/tg '):
            # Управление Telegram ботом
            self._handle_telegram_command(command)

        elif cmd == '/memory':
            # Показать содержимое памяти
            result = MemoryManager.read()
            if result["success"]:
                content = result["content"]
                last_updated = result.get("last_updated", "")
                UI.print_status(f"Память (обновлено: {last_updated})", "info")
                print(f"\n{Colors.DIM}────────────────────────────────────────{Colors.RESET}")
                # Вывод содержимого памяти (ограничено)
                if len(content) > 2000:
                    content = "..." + content[-2000:]
                print(f"{Colors.WHITE}{content}{Colors.RESET}")
                print(f"{Colors.DIM}────────────────────────────────────────{Colors.RESET}")
            else:
                UI.print_error(f"Ошибка чтения памяти: {result.get('error', 'Неизвестная ошибка')}")

        elif cmd == '/tools':
            UI.print_tools_list()

        elif cmd.startswith('/maxiter'):
            parts = command.split(maxsplit=1)
            if len(parts) > 1:
                try:
                    new_max = int(parts[1])
                    if new_max <= 0:
                        self.agent.max_iterations = -1
                        UI.print_status("Макс. итераций отключено: без лимита", "success")
                    elif 1 <= new_max <= 50:
                        self.agent.max_iterations = new_max
                        UI.print_status(f"Макс. итераций установлено: {new_max}", "success")
                    else:
                        UI.print_error("Значение должно быть от 1 до 50")
                except ValueError:
                    UI.print_error("Укажите числовое значение")
            else:
                current_max_label = "∞ (без лимита)" if self.agent.max_iterations <= 0 else str(self.agent.max_iterations)
                UI.print_status(f"Текущее макс. итераций: {current_max_label}", "info")

        elif cmd == '/exit':
            UI.print_status("До свидания! 👋", "success")
            self.running = False

        elif cmd.startswith('/image'):
            parts = command.split(maxsplit=1)
            if len(parts) > 1:
                path = parts[1].strip('"\'')
                if os.path.exists(path):
                    self.current_image_path = path
                    UI.print_status(f"Изображение: {os.path.basename(path)}", "success")
                else:
                    UI.print_error(f"File not found: {path}")
            else:
                print(f"\n{Colors.CYAN}Путь к изображению:{Colors.RESET}")
                try:
                    path = input("> ").strip().strip('"\'')
                    if os.path.exists(path):
                        self.current_image_path = path
                        UI.print_status(f"Изображение: {os.path.basename(path)}", "success")
                    else:
                        UI.print_error(f"File not found: {path}")
                except:
                    print()

        else:
            UI.print_error(f"Неизвестная команда: {command}")
            UI.print_help()

    def chat_once(self, content: str, image_path: Optional[str] = None,
                  stream: bool = False, show_thinking: bool = False,
                  image_urls: Optional[List[str]] = None) -> Dict[str, Any]:
        """Программный интерфейс для одного запроса без текстового input()."""
        final_result = {
            "type": "final",
            "content": "",
            "iterations": 0
        }

        for result in self.agent.send_message(
                content,
                image_path,
                stream=stream,
                show_thinking=show_thinking,
                image_urls=image_urls
        ):
            if result.get("type") == "final":
                final_result = result

        return final_result

    def _send_message(self, content: str, image_path: Optional[str] = None):
        """Отправка сообщения"""
        # Вывод сообщения
        display_content = content
        if image_path:
            display_content = f"{content}\n\n[Изображение: {os.path.basename(image_path)}]" if content else f"[Изображение: {os.path.basename(image_path)}]"
        UI.print_user_message(display_content if display_content else "[Изображение]")

        if not self.streaming:
            UI.print_thinking_animation()

        try:
            for result in self.agent.send_message(
                    content,
                    image_path,
                    stream=self.streaming,
                    show_thinking=self.show_thinking
            ):
                if result["type"] == "final":
                    # Статистика
                    if result.get("iterations"):
                        max_iterations_label = "∞" if self.agent.max_iterations <= 0 else str(self.agent.max_iterations)
                        print(
                            f"\n{Colors.DIM}⚡ Итераций: {result['iterations']}/{max_iterations_label}{Colors.RESET}")

                    response_text = result["content"]

                    # При потоковом режиме ответ уже был выведен по мере генерации
                    if not self.streaming:
                        UI.print_assistant_response(response_text, "Ответ")

                    # Озвучивание первого и последнего абзацев (если TTS включен)
                    if TTS.is_enabled():
                        # Разбиваем ответ на абзацы
                        paragraphs = [p.strip() for p in response_text.split('\n\n') if p.strip()]
                        # Фильтруем абзацы, убираем технические (списки инструментов, команды и т.д.)
                        content_paragraphs = []
                        for p in paragraphs:
                            # Пропускаем абзацы с маркерами списков и заголовками
                            if not (p.startswith('```') or p.startswith('1.') or p.startswith('•') or p.startswith(
                                    '-')):
                                content_paragraphs.append(p)

                        # Если нашли содержательные абзацы, озвучиваем
                        if content_paragraphs:
                            TTS.speak_paragraphs(content_paragraphs, context="ответ ассистента")

            UI.print_separator("single")

        except Exception as e:
            UI.print_error(str(e))

def main():
    """Точка входа"""
    if os.name == "nt":
        try:
            import colorama
            colorama.init()
        except ImportError:
            pass

    try:
        app = QwenAgentApp()
        app.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Выход...{Colors.RESET}")
    except Exception as e:
        UI.print_error(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

