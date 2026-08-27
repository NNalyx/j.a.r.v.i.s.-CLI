#!/usr/bin/env python3
"""
Модуль голосовой активации для Jarvis
- Кастомная запись wake word "джарвис" пользователем
- Сравнение через MFCC + косинусная схожесть
- Silero STT для распознавания команд
"""

import os
import json
import threading
import time
import numpy as np
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

# Librosa для аудио-анализа
try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    LIBROSA_AVAILABLE = False

# psutil для проверки RAM (опционально)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

# Silero STT
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

try:
    from silero import silero_stt
    STT_AVAILABLE = TORCH_AVAILABLE
except ImportError:
    STT_AVAILABLE = False

# Vosk STT (альтернатива)
try:
    from vosk import Model as VoskModel, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

# URL для загрузки модели Vosk (маленькая русская модель ~35MB)
VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
VOSK_MODEL_NAME = "vosk-model-small-ru-0.22"
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOSK_SMALL_MODEL_PATH = os.path.join(_BASE_DIR, "models", "vosk-model-small-ru-0.22")
VOSK_LARGE_MODEL_PATH = os.path.join(_BASE_DIR, "models", "vosk-model-ru-0.42")
DEFAULT_TRANSCRIPTION_BACKEND_KEY = "vosk"
LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY = "vosk_large"
LEGACY_FASTER_WHISPER_TRANSCRIPTION_BACKEND_KEY = "faster_whisper"
LEGACY_QWEN_TRANSCRIPTION_BACKEND_KEY = "qwen3_asr"

# Импорт цветов из основного модуля
try:
    from jarvis_agent_cli import Colors
except ImportError:
    class Colors:
        RESET = "\033[0m"
        BOLD = "\033[1m"
        DIM = "\033[2m"
        BRIGHT_CYAN = "\033[96m"
        BRIGHT_GREEN = "\033[92m"
        BRIGHT_YELLOW = "\033[93m"

# Конфиг менеджер для путей к Vosk
try:
    import config_manager
except ImportError:
    config_manager = None

# Микрофон
try:
    import sounddevice as sd
    MIC_AVAILABLE = True
except ImportError:
    MIC_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Константы
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000  # Частота дискретизации
CHUNK_SIZE = 512     # Размер чанка для записи (~32ms при 16kHz)
DURATION_WAKE_WORD = 1.5  # Секунд для записи wake word
SILENCE_THRESHOLD = 0.001  # Порог тишины для VAD (очень низкий для чувствительности)
SILENCE_DURATION = 0.5    # Секунд тишины для окончания записи команды (было 1.0)
POST_COMMAND_COOLDOWN = 1.8  # Защита от повторного ложного wake-trigger на хвосте той же фразы

# Wake word для распознавания через Vosk
WAKE_WORD = "пятница"

# Large Vosk: фоновая загрузка и защита от нехватки памяти
LARGE_VOSK_LOAD_TIMEOUT = 120.0   # секунд ожидания загрузки Large Vosk
LARGE_VOSK_MIN_FREE_RAM_GB = 2.5  # минимум свободной RAM для Large модели

# Путь к профилю
VOICE_PROFILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "jarvis_voice_profile.json"
)


def _get_vosk_small_path() -> str:
    """Получить путь к малой Vosk модели из конфига или дефолт."""
    if config_manager:
        config = config_manager.read_config()
        if config and config.get("vosk_small_model_path"):
            return config["vosk_small_model_path"]
    return VOSK_SMALL_MODEL_PATH


def _get_vosk_large_path() -> str:
    """Получить путь к большой Vosk модели из конфига или дефолт."""
    if config_manager:
        config = config_manager.read_config()
        if config and config.get("vosk_large_model_path"):
            return config["vosk_large_model_path"]
    return VOSK_LARGE_MODEL_PATH


def _normalize_backend_key(backend_key: Optional[str]) -> str:
    normalized = str(backend_key or DEFAULT_TRANSCRIPTION_BACKEND_KEY).strip().lower()
    if normalized in {LEGACY_QWEN_TRANSCRIPTION_BACKEND_KEY, LEGACY_FASTER_WHISPER_TRANSCRIPTION_BACKEND_KEY}:
        return LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY
    return normalized if normalized in {DEFAULT_TRANSCRIPTION_BACKEND_KEY, LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY} else DEFAULT_TRANSCRIPTION_BACKEND_KEY


def _supports_large_vosk() -> tuple[bool, str]:
    if not MIC_AVAILABLE:
        return False, "Микрофон недоступен"
    if not VOSK_AVAILABLE:
        return False, "Vosk недоступен"
    large_path = _get_vosk_large_path()
    if not os.path.exists(large_path):
        return False, f"Большая модель Vosk не найдена: {large_path}"
    return True, ""


def _check_free_ram_gb() -> Optional[float]:
    """Вернуть свободную RAM в ГБ, если доступен psutil."""
    if not PSUTIL_AVAILABLE:
        return None
    try:
        return psutil.virtual_memory().available / (1024 ** 3)
    except Exception:
        return None


def get_transcription_backend_catalog(selected_key: Optional[str] = None) -> List[Dict[str, Any]]:
    selected_key = _normalize_backend_key(selected_key)
    large_vosk_available, large_vosk_reason = _supports_large_vosk()
    backends = [
        {
            "key": DEFAULT_TRANSCRIPTION_BACKEND_KEY,
            "label": "Vosk Small RU",
            "description": "Лёгкая и быстрая потоковая расшифровка, но менее точная.",
            "available": bool(MIC_AVAILABLE and VOSK_AVAILABLE),
            "requires_cuda": False,
            "streaming": True,
            "selected": selected_key == DEFAULT_TRANSCRIPTION_BACKEND_KEY,
            "reason": "" if (MIC_AVAILABLE and VOSK_AVAILABLE) else "Vosk или sounddevice недоступны",
        },
        {
            "key": LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY,
            "label": "Vosk Large RU 0.42",
            "description": "Большая русская модель Vosk для распознавания команды. Работает по тому же потоковому принципу, но точнее и тяжелее.",
            "available": large_vosk_available,
            "requires_cuda": False,
            "streaming": True,
            "selected": selected_key == LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY,
            "reason": large_vosk_reason,
        },
    ]
    return backends


def _strip_wake_word_prefix(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""

    lower_text = normalized.lower()
    lower_wake = WAKE_WORD.lower()
    wake_index = lower_text.find(lower_wake)
    if wake_index == -1:
        return normalized

    stripped = normalized[wake_index + len(WAKE_WORD):].strip(" ,.!?-")
    return stripped or normalized


def _safe_json_loads(payload: Any) -> Dict[str, Any]:
    """Parse JSON safely, returning empty dict on failure."""
    if isinstance(payload, dict):
        return payload
    try:
        loaded = json.loads(payload or "{}")
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# VoiceProfile - Управление эталонами
# ─────────────────────────────────────────────────────────────────────────────
class VoiceProfile:
    """Профиль голоса пользователя для wake word"""
    
    def __init__(self, profile_path: str = VOICE_PROFILE_PATH):
        self.profile_path = profile_path
        self.samples: List[np.ndarray] = []  # MFCC-векторы эталонов
        self.is_trained = False
    
    def extract_mfcc(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
        """Извлечь MFCC-признаки из аудио"""
        # Вычисляем MFCC (13 коэффициентов)
        mfcc = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=13)
        # Усредняем по времени → получаем вектор признаков
        mfcc_mean = mfcc.mean(axis=1)
        # Нормализуем
        mfcc_mean = mfcc_mean / (np.linalg.norm(mfcc_mean) + 1e-8)
        return mfcc_mean
    
    def add_sample(self, audio: np.ndarray, sample_rate: int = SAMPLE_RATE):
        """Добавить эталонный образец"""
        mfcc = self.extract_mfcc(audio, sample_rate)
        self.samples.append(mfcc)
        self.is_trained = len(self.samples) >= 2
    
    def save(self):
        """Сохранить профиль в файл"""
        data = {
            "samples": [s.tolist() for s in self.samples],
            "created": datetime.now().isoformat(),
            "count": len(self.samples)
        }
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[VoiceProfile] ✅ Сохранено {len(self.samples)} образцов")
    
    def load(self) -> bool:
        """Загрузить профиль из файла"""
        if not os.path.exists(self.profile_path):
            return False
        
        try:
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.samples = [np.array(s) for s in data.get("samples", [])]
            self.is_trained = len(self.samples) >= 2
            print(f"[VoiceProfile] ✅ Загружено {len(self.samples)} образцов")
            return True
        except Exception as e:
            print(f"[VoiceProfile] ❌ Ошибка загрузки: {e}")
            return False
    
    def check_similarity(self, audio: np.ndarray, threshold: float = 0.7) -> tuple:
        """
        Проверить схожесть аудио с эталонами
        Returns: (is_match, max_similarity)
        """
        if not self.samples:
            return False, 0.0
        
        mfcc = self.extract_mfcc(audio)
        
        # Косинусная схожесть с каждым эталоном
        max_similarity = 0.0
        for sample in self.samples:
            similarity = np.dot(mfcc, sample)  # Косинусная схожесть
            max_similarity = max(max_similarity, similarity)
        
        is_match = max_similarity >= threshold
        return is_match, max_similarity


# ─────────────────────────────────────────────────────────────────────────────
# VoiceActivator
# ─────────────────────────────────────────────────────────────────────────────
class VoiceActivator:
    """
    Голосовая активация Jarvis.

    Wake word всегда отслеживается через Vosk для минимальной задержки.
    После активации команда распознаётся выбранным backend:
    - Vosk: лёгкий, быстрый, менее точный
    - Vosk Large RU 0.42: тот же потоковый принцип, но большая русская модель
    """

    def __init__(self, transcription_backend_key: str = DEFAULT_TRANSCRIPTION_BACKEND_KEY):
        self.profile = VoiceProfile()  # Теперь не используется для wake word
        self.stt_model = None  # Silero (не используется)
        self.vosk_model = None
        self.vosk_recognizer = None
        self.command_vosk_model = None
        self.command_vosk_recognizer = None
        self.command_vosk_last_error = ""
        self.command_backend_key = _normalize_backend_key(transcription_backend_key)

        self.is_running = False
        self.is_listening = False
        self.is_recording = False
        self.wake_word_detected = False
        self.pause_callback = False

        self.callback: Optional[Callable[[str], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None
        self.partial_callback: Optional[Callable[[str], None]] = None

        self._listen_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()
        self._wake_cooldown_until = 0.0

        # Фоновая загрузка Large Vosk (чтобы не блокировать UI при старте)
        self._large_vosk_load_thread: Optional[threading.Thread] = None
        self._large_vosk_load_lock = threading.Lock()
        self._large_vosk_ready = threading.Event()
        self._large_vosk_load_error = ""

        self.command_buffer = []
        self.full_transcript = ""

    def get_backend_options(self) -> List[Dict[str, Any]]:
        options = []
        for backend in get_transcription_backend_catalog(self.command_backend_key):
            item = dict(backend)
            if item["key"] == LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY and self.command_vosk_last_error:
                item["reason"] = self.command_vosk_last_error
            if item["key"] == self.command_backend_key:
                item["selected"] = True
            options.append(item)
        return options

    def set_command_backend(self, backend_key: str) -> None:
        backend_key = _normalize_backend_key(backend_key)
        if backend_key == self.command_backend_key:
            return

        old_key = self.command_backend_key
        self.command_backend_key = backend_key
        self.command_vosk_recognizer = None
        self.full_transcript = ""

        # Если уходим с Large Vosk — выгружаем её, чтобы освободить RAM
        if old_key == LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY and backend_key != LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY:
            self._unload_large_vosk_model()

    def init_models(self, force_reload: bool = False):
        """Инициализировать wake-word Vosk и выбранный backend расшифровки."""
        if not MIC_AVAILABLE:
            print("[Voice] ❌ sounddevice не доступен")
            return False

        # Всегда загружаем малую модель для wake-word
        wake_ready = self._ensure_wake_recognizer(force_reload=force_reload)

        # Large Vosk грузим лениво и в фоне, чтобы не блокировать старт/UI.
        # Если пользователь переключился на Large — проверяем доступность и
        # запускаем фоновую загрузку, но не ждём её здесь.
        if self.command_backend_key == LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY:
            supported, reason = _supports_large_vosk()
            if not supported:
                self.command_vosk_last_error = reason
                print(f"[Voice] ⚠️ Large Vosk недоступен: {reason}")
                return False
            self.command_vosk_last_error = ""
            self._start_large_vosk_background_load(force_reload=force_reload)
            return wake_ready

        command_ready = self._ensure_command_backend(force_reload=force_reload)
        return wake_ready and command_ready

    def _ensure_wake_recognizer(self, force_reload: bool = False) -> bool:
        if not VOSK_AVAILABLE:
            print("[Voice] ⚠️ Vosk не доступен")
            return False

        if self.vosk_model is not None and self.vosk_recognizer is not None and not force_reload:
            return True

        try:
            possible_paths = [
                _get_vosk_small_path(),
                os.path.join(os.path.expanduser("~"), ".vosk-models", VOSK_MODEL_NAME),
                os.path.join(os.path.dirname(__file__), VOSK_MODEL_NAME),
            ]

            vosk_model_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    vosk_model_path = path
                    break

            if vosk_model_path is None:
                print("[Voice] ⚠️ Модель Vosk не найдена. Попытка загрузки...")
                if download_vosk_model():
                    vosk_model_path = os.path.join(os.path.expanduser("~"), ".vosk-models", VOSK_MODEL_NAME)
                else:
                    print("[Voice] ⚠️ Не удалось загрузить модель Vosk")

            if vosk_model_path and os.path.exists(vosk_model_path):
                self.vosk_model = VoskModel(vosk_model_path)
                self.vosk_recognizer = KaldiRecognizer(self.vosk_model, SAMPLE_RATE)
                print(f"[Voice] ✅ Wake-word Vosk инициализирован: {vosk_model_path}")
                return True

            print("[Voice] ⚠️ Vosk модель не доступна. Wake word не будет работать.")
        except Exception as e:
            print(f"[Voice] ⚠️ Ошибка инициализации Vosk: {e}")
            self.vosk_model = None
            self.vosk_recognizer = None

        return False

    def _ensure_command_backend(self, force_reload: bool = False) -> bool:
        if self.command_backend_key == DEFAULT_TRANSCRIPTION_BACKEND_KEY:
            if self.vosk_model is None and not self._ensure_wake_recognizer(force_reload=force_reload):
                return False

            try:
                if self.command_vosk_recognizer is None or force_reload:
                    self.command_vosk_recognizer = KaldiRecognizer(self.vosk_model, SAMPLE_RATE)
                self.command_vosk_last_error = ""
                return True
            except Exception as e:
                print(f"[Voice] ⚠️ Ошибка инициализации command Vosk: {e}")
                self.command_vosk_recognizer = None
                return False

        if self.command_backend_key == LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY:
            return self._ensure_large_vosk_command_model(force_reload=force_reload)

        print(f"[Voice] ⚠️ Неизвестный backend распознавания: {self.command_backend_key}")
        return False

    def _unload_large_vosk_model(self) -> None:
        """Выгрузить Large Vosk модель и освободить RAM."""
        with self._large_vosk_load_lock:
            self.command_vosk_model = None
            self.command_vosk_recognizer = None
            self._large_vosk_ready.clear()
            self._large_vosk_load_error = ""
            self._large_vosk_load_thread = None
        try:
            import gc
            gc.collect()
        except Exception:
            pass
        print("[Voice] ✅ Large Vosk выгружен для освобождения памяти")

    def _start_large_vosk_background_load(self, force_reload: bool = False) -> None:
        """Запустить фоновую загрузку Large Vosk, если она ещё не идёт."""
        with self._large_vosk_load_lock:
            if self.command_vosk_model is not None and not force_reload:
                self._large_vosk_ready.set()
                return

            if self._large_vosk_load_thread is not None and self._large_vosk_load_thread.is_alive():
                return

            self._large_vosk_ready.clear()
            self._large_vosk_load_error = ""
            self._large_vosk_load_thread = threading.Thread(
                target=self._load_large_vosk_worker,
                args=(force_reload,),
                daemon=True,
                name="LargeVoskLoader"
            )
            self._large_vosk_load_thread.start()

    def _load_large_vosk_worker(self, force_reload: bool) -> None:
        """Рабочий поток загрузки Large Vosk."""
        try:
            large_path = _get_vosk_large_path()

            free_gb = _check_free_ram_gb()
            if free_gb is not None and free_gb < LARGE_VOSK_MIN_FREE_RAM_GB:
                raise MemoryError(
                    f"Недостаточно свободной RAM: {free_gb:.1f} ГБ "
                    f"(нужно минимум {LARGE_VOSK_MIN_FREE_RAM_GB} ГБ для Large Vosk)"
                )

            print(f"[Voice] ⏳ Фоновая загрузка command Vosk Large RU: {large_path}")
            self.command_vosk_model = VoskModel(large_path)
            self.command_vosk_recognizer = KaldiRecognizer(self.command_vosk_model, SAMPLE_RATE)
            self.command_vosk_last_error = ""
            print(f"[Voice] ✅ Command Vosk Large RU инициализирован: {large_path}")
            self._large_vosk_ready.set()
        except Exception as e:
            self.command_vosk_model = None
            self.command_vosk_recognizer = None
            err = str(e)
            self.command_vosk_last_error = err
            self._large_vosk_load_error = err
            print(f"[Voice] ⚠️ Ошибка фоновой загрузки Large Vosk: {e}")
            self._large_vosk_ready.clear()

    def _ensure_large_vosk_command_model(self, force_reload: bool = False, timeout: Optional[float] = None) -> bool:
        supported, reason = _supports_large_vosk()
        if not supported:
            self.command_vosk_last_error = reason
            print(f"[Voice] ⚠️ Большая модель Vosk недоступна: {reason}")
            return False

        if self.command_vosk_model is not None and self.command_vosk_recognizer is not None and not force_reload:
            return True

        self._start_large_vosk_background_load(force_reload=force_reload)
        timeout = timeout if timeout is not None else LARGE_VOSK_LOAD_TIMEOUT
        print(f"[Voice] ⏳ Ожидаю загрузку Large Vosk (timeout={timeout:.0f}s)...")
        ready = self._large_vosk_ready.wait(timeout=timeout)
        if not ready:
            self.command_vosk_last_error = f"Превышено время загрузки Large Vosk ({timeout:.0f}s)"
            print(f"[Voice] ⚠️ {self.command_vosk_last_error}")
            return False

        if self.command_vosk_model is None or self.command_vosk_recognizer is None:
            self.command_vosk_last_error = self._large_vosk_load_error or "Не удалось загрузить Large Vosk"
            print(f"[Voice] ⚠️ {self.command_vosk_last_error}")
            return False

        return True

    def set_callback(self, callback: Callable[[str], None]):
        """Установить callback для распознанной команды"""
        self.callback = callback
    
    def set_status_callback(self, callback: Callable[[str], None]):
        """Установить callback для обновления статуса"""
        self.status_callback = callback

    def set_partial_callback(self, callback: Callable[[str], None]):
        """Установить callback для текста команды в реальном времени"""
        self.partial_callback = callback

    def _set_status(self, status: str):
        """Обновить статус"""
        try:
            if self.status_callback:
                self.status_callback(status)
        except Exception:
            pass

    def _reset_command_state(self) -> None:
        self.wake_word_detected = False
        self.is_recording = False
        self.full_transcript = ""
        self.command_vosk_recognizer = None

    def _arm_wake_cooldown(self, seconds: float = POST_COMMAND_COOLDOWN) -> None:
        self._wake_cooldown_until = max(self._wake_cooldown_until, time.time() + max(0.0, seconds))
        try:
            if self.vosk_model is not None:
                self.vosk_recognizer = KaldiRecognizer(self.vosk_model, SAMPLE_RATE)
        except Exception as e:
            print(f"[Voice] ⚠️ Не удалось сбросить wake recognizer: {e}")

    def _wake_detection_blocked(self) -> bool:
        return time.time() < self._wake_cooldown_until

    def _dispatch_callback(self, final_text: str) -> None:
        if not final_text or not self.callback or self.pause_callback:
            return

        def _callback_worker():
            try:
                self.callback(final_text)
            except Exception as e:
                print(f"[Voice] ⚠️ Ошибка callback голосовой команды: {e}")

        threading.Thread(target=_callback_worker, daemon=True, name="VoiceCallbackWorker").start()

    def start_listening(self):
        """Запустить прослушивание wake word"""
        with self._state_lock:
            if self.is_running or (self._listen_thread and self._listen_thread.is_alive()):
                return

            if not self.vosk_recognizer and not self._ensure_wake_recognizer():
                return

            # Для Large Vosk дожидаемся фоновой загрузки, чтобы распознаватель
            # был готов к моменту захвата команды. Small грузится мгновенно.
            if self.command_backend_key == LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY:
                if not self._ensure_large_vosk_command_model(timeout=LARGE_VOSK_LOAD_TIMEOUT):
                    self._set_status("Не удалось загрузить Large Vosk")
                    return
            else:
                if not self._ensure_command_backend():
                    return

            self.is_running = True
            self.is_listening = True
            self._stop_event.clear()
            self.full_transcript = ""
            self.wake_word_detected = False
            self.is_recording = False
            self._set_status(f"Слушаю wake word '{WAKE_WORD}'")

            self._listen_thread = threading.Thread(
                target=self._listen_loop,
                daemon=True,
                name="VoiceActivator"
            )
            self._listen_thread.start()

    def stop_listening(self):
        """Остановить прослушивание"""
        with self._state_lock:
            self.is_running = False
            self.is_listening = False
            self.is_recording = False
            self._stop_event.set()
            listen_thread = self._listen_thread

        if listen_thread and listen_thread.is_alive() and threading.current_thread() is not listen_thread:
            listen_thread.join(timeout=2.0)

        with self._state_lock:
            if self._listen_thread is listen_thread:
                self._listen_thread = None

        self._set_status("Голосовая активация выключена")
        print("[Voice] 🛑 Прослушивание остановлено")

    def _begin_command_capture(self) -> None:
        self.wake_word_detected = True
        self.is_recording = True
        self.full_transcript = ""
        self._wake_cooldown_until = 0.0

        command_model = self.command_vosk_model if self.command_backend_key == LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY else self.vosk_model
        if command_model is not None:
            try:
                self.command_vosk_recognizer = KaldiRecognizer(command_model, SAMPLE_RATE)
            except Exception as e:
                self.command_vosk_recognizer = None
                self._set_status("Не удалось подготовить Vosk для команды")
                print(f"[Voice] ⚠️ Ошибка создания command Vosk recognizer: {e}")
                self._reset_command_state()
                return

        self._set_status("Wake word услышан. Говорите команду...")
        self._play_activation_sound()

    def _process_wake_recognizer(self, audio_int16: np.ndarray) -> bool:
        if not self.vosk_recognizer:
            return False

        try:
            if self.vosk_recognizer.AcceptWaveform(audio_int16.tobytes()):
                result = _safe_json_loads(self.vosk_recognizer.Result())
                text = str(result.get("text", "")).lower().strip()
                return bool(text and WAKE_WORD in text)

            partial = _safe_json_loads(self.vosk_recognizer.PartialResult())
            partial_text = str(partial.get("partial", "")).lower().strip()
            return bool(partial_text and WAKE_WORD in partial_text)
        except Exception as e:
            print(f"[Voice] ⚠️ Wake recognizer error: {e}")
            self.vosk_recognizer = None
            self._ensure_wake_recognizer(force_reload=True)
            return False

    def _emit_partial(self, text: str) -> None:
        cleaned = _strip_wake_word_prefix(text).strip()
        if not cleaned:
            return
        try:
            if self.partial_callback:
                self.partial_callback(cleaned)
        except Exception:
            pass

    def _feed_vosk_command(self, audio_int16: np.ndarray, last_partial: str) -> str:
        if not self.command_vosk_recognizer:
            return last_partial

        try:
            accepted = self.command_vosk_recognizer.AcceptWaveform(audio_int16.tobytes())

            # Result() только после завершённого сегмента. Иначе Vosk
            # сбрасывает незавершённую фразу на каждом аудиочанке.
            if accepted:
                result = _safe_json_loads(self.command_vosk_recognizer.Result())
                text = str(result.get("text", "")).strip()
                if text:
                    combined = f"{self.full_transcript} {text}".strip()
                    self.full_transcript = _strip_wake_word_prefix(combined).strip()
                    print(f"\r❯ {self.full_transcript}", end="", flush=True)
                    self._emit_partial(self.full_transcript)
                return ""

            try:
                partial = _safe_json_loads(self.command_vosk_recognizer.PartialResult())
            except Exception:
                return last_partial
            partial_text = _strip_wake_word_prefix(str(partial.get("partial", "")).strip()).strip()
            display_text = " ".join(piece for piece in [self.full_transcript, partial_text] if piece).strip()
            if display_text and display_text != last_partial:
                print(f"\r❯ {display_text}{' ' * max(0, len(last_partial) - len(display_text))}", end="", flush=True)
                self._emit_partial(display_text)
                return display_text
            return last_partial
        except Exception as e:
            print(f"[Voice] ⚠️ Command Vosk recognizer error: {e}")
            self.command_vosk_recognizer = None
            self._set_status("Ошибка Vosk во время распознавания команды")
            self._reset_command_state()
            self._set_status(f"Слушаю wake word '{WAKE_WORD}'")
            return ""

    def _finalize_command(self, last_partial: str) -> None:
        if last_partial:
            print(f"\r{' ' * (len(last_partial) + 3)}\r", end="", flush=True)

        final_text = self.full_transcript.strip()

        if self.command_vosk_recognizer is not None:
            try:
                result = _safe_json_loads(self.command_vosk_recognizer.FinalResult())
                final_piece = _strip_wake_word_prefix(str(result.get("text", "")).strip())
                final_text = f"{final_text} {final_piece}".strip() if final_piece else final_text
            except Exception:
                pass

        final_text = _strip_wake_word_prefix(final_text).strip()
        self._reset_command_state()
        self._arm_wake_cooldown()
        if final_text:
            self._set_status("Команда распознана. Отправляю...")
            self._dispatch_callback(final_text)

        self._set_status(f"Слушаю wake word '{WAKE_WORD}'")

    def _listen_loop(self):
        """Основной цикл прослушивания."""
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                blocksize=CHUNK_SIZE,
                dtype="float32"
            ) as stream:
                self.wake_word_detected = False
                self.full_transcript = ""
                silence_start = None
                last_partial = ""

                while self.is_running and not self._stop_event.is_set():
                    audio_data, overflowed = stream.read(CHUNK_SIZE)
                    if overflowed:
                        print("[Voice] ⚠️ Переполнение аудиобуфера")

                    audio_data = np.asarray(audio_data[:, 0], dtype=np.float32)
                    audio_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
                    rms = np.sqrt(np.mean(audio_data ** 2))
                    has_sound = rms > SILENCE_THRESHOLD

                    if (
                        not self.wake_word_detected
                        and not self._wake_detection_blocked()
                        and self._process_wake_recognizer(audio_int16)
                    ):
                        self._begin_command_capture()
                        silence_start = None
                        last_partial = ""
                        continue

                    if self.wake_word_detected:
                        if has_sound:
                            silence_start = None
                            last_partial = self._feed_vosk_command(audio_int16, last_partial)
                        else:
                            if silence_start is None:
                                silence_start = time.time()
                            elif time.time() - silence_start > SILENCE_DURATION:
                                self._finalize_command(last_partial)
                                silence_start = None
                                last_partial = ""

                        if len(self.full_transcript) > 500:
                            self._finalize_command(last_partial)
                            silence_start = None
                            last_partial = ""

        except Exception as e:
            import traceback
            print(f"[Voice] ❌ Ошибка: {e}")
            print(traceback.format_exc())
            self._set_status(f"Ошибка голосовой активации: {e}")
        finally:
            with self._state_lock:
                self.is_running = False
                self.is_listening = False
                self.is_recording = False
                self._listen_thread = None

    def _play_activation_sound(self):
        """Воспроизвести звук активации"""
        try:
            if os.name == "nt":
                import winsound
                threading.Thread(
                    target=lambda: winsound.Beep(880, 120),
                    daemon=True,
                    name="VoiceActivationBeep"
                ).start()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Функции для обучения (консольный интерфейс)
# ─────────────────────────────────────────────────────────────────────────────

def download_vosk_model(target_dir: str = None) -> bool:
    """
    Скачать модель Vosk для русского языка.
    На macOS Python может не видеть системные сертификаты, поэтому при
    SSL-ошибке используем отключённую проверку сертификата (известный URL).
    """
    if target_dir is None:
        target_dir = os.path.join(os.path.expanduser("~"), ".vosk-models")

    os.makedirs(target_dir, exist_ok=True)

    model_path = os.path.join(target_dir, VOSK_MODEL_NAME)
    zip_path = os.path.join(target_dir, f"{VOSK_MODEL_NAME}.zip")

    if os.path.exists(model_path):
        print(f"[Voice] ✅ Модель Vosk уже загружена: {model_path}")
        return True

    print(f"[Voice] 📥 Загрузка модели Vosk ({VOSK_MODEL_URL})...")
    print(f"[Voice] 📁 Путь: {target_dir}")

    import ssl as _ssl_mod
    import urllib.request
    import zipfile

    def _download_with_progress(url, zip_path):
        def report_progress(downloaded, total_size):
            percent = min(downloaded * 100 / total_size, 100) if total_size else 100
            print(f"\r[Voice] 📥 Загрузка: {percent:.1f}%", end="")

        ctx = _ssl_mod.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl_mod.CERT_NONE
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        original_opener = getattr(urllib.request, '_opener', None)
        try:
            urllib.request.install_opener(opener)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    with open(zip_path, 'ab') as f:
                        f.write(chunk)
                    downloaded += len(chunk)
                    report_progress(downloaded, total_size)
        finally:
            if original_opener is not None:
                urllib.request._opener = original_opener
            else:
                delattr(urllib.request, '_opener')
        print()  # Новая строка после прогресса

    try:
        # Попытка 1: стандартная загрузка с проверкой сертификата
        _download_with_progress(VOSK_MODEL_URL, zip_path)
    except urllib.error.URLError as exc:
        err_msg = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" in err_msg or "SSL" in err_msg.upper():
            print("[Voice] ⚠️ SSL certificate verify failed, retrying without verification...")
            try:
                _download_with_progress(VOSK_MODEL_URL, zip_path)
            except Exception as e:
                print(f"[Voice] ❌ Ошибка загрузки модели: {e}")
                return False
        else:
            print(f"[Voice] ❌ Ошибка загрузки модели: {exc}")
            return False
    except Exception as e:
        print(f"[Voice] ❌ Ошибка загрузки модели: {e}")
        return False

    try:
        # Распаковываем
        print("[Voice] 📦 Распаковка...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)

        # Удаляем zip
        os.remove(zip_path)

        print(f"[Voice] ✅ Модель загружена: {model_path}")
        return True
    except Exception as e:
        print(f"[Voice] ❌ Ошибка распаковки модели: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# One-shot voice message recording (used by the web UI composer mic button)
# ─────────────────────────────────────────────────────────────────────────────

def record_voice_message(
    backend_key: str = DEFAULT_TRANSCRIPTION_BACKEND_KEY,
    max_duration: float = 30.0,
    silence_duration: float = 0.5,
    stop_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """Record a short voice message and transcribe it with Vosk.

    This function does not touch the global VoiceActivator state; it opens a
    short-lived microphone stream and returns the recognized text.

    Returns:
        {"ok": True, "text": "...", "backend": backend_key}
        or
        {"ok": False, "error": "..."}
    """
    if not MIC_AVAILABLE:
        return {"ok": False, "error": "Microphone is not available. Install sounddevice."}
    if not VOSK_AVAILABLE:
        return {"ok": False, "error": "Vosk is not available. Install vosk."}

    backend_key = _normalize_backend_key(backend_key)

    # Resolve model path.
    if backend_key == LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY:
        model_path = _get_vosk_large_path()
        if not os.path.exists(model_path):
            return {"ok": False, "error": f"Large Vosk model not found: {model_path}"}
    else:
        model_path = _get_vosk_small_path()
        if not os.path.exists(model_path):
            # Try to download the small model if missing.
            target_dir = os.path.join(os.path.expanduser("~"), ".vosk-models")
            if download_vosk_model(target_dir):
                model_path = os.path.join(target_dir, VOSK_MODEL_NAME)
            if not os.path.exists(model_path):
                return {"ok": False, "error": f"Vosk model not found: {model_path}"}

    try:
        model = VoskModel(model_path)
        recognizer = KaldiRecognizer(model, SAMPLE_RATE)
    except Exception as exc:
        return {"ok": False, "error": f"Failed to load Vosk model: {exc}"}

    max_duration = max(1.0, float(max_duration))
    silence_duration = max(0.3, float(silence_duration))
    manual_stop = stop_event is not None

    full_text = ""
    silence_start: Optional[float] = None
    started_at = time.time()
    last_partial = ""

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=CHUNK_SIZE,
            dtype="float32",
        ) as stream:
            while time.time() - started_at < max_duration and not (stop_event and stop_event.is_set()):
                audio_data, overflowed = stream.read(CHUNK_SIZE)
                if overflowed:
                    print("[Voice] ⚠️ Audio buffer overflow during voice message recording")

                audio_data = np.asarray(audio_data[:, 0], dtype=np.float32)
                audio_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
                rms = np.sqrt(np.mean(audio_data ** 2))
                has_sound = rms > SILENCE_THRESHOLD

                # Result() можно вызывать только после того, как Vosk
                # сообщил о завершённом речевом сегменте. Вызов Result() на
                # каждом чанке сбрасывает внутреннее состояние распознавания.
                if recognizer.AcceptWaveform(audio_int16.tobytes()):
                    result = _safe_json_loads(recognizer.Result())
                    text = str(result.get("text", "")).strip()
                    if text:
                        full_text = f"{full_text} {text}".strip()
                        last_partial = ""
                else:
                    try:
                        partial = _safe_json_loads(recognizer.PartialResult())
                    except Exception:
                        partial = {}
                    partial_text = str(partial.get("partial", "")).strip()
                    display_text = f"{full_text} {partial_text}".strip()
                    if display_text != last_partial:
                        last_partial = display_text

                if has_sound:
                    silence_start = None
                else:
                    if silence_start is None:
                        silence_start = time.time()
                    elif not manual_stop and time.time() - silence_start > silence_duration:
                        break
    except Exception as exc:
        return {"ok": False, "error": f"Recording failed: {exc}"}

    try:
        final_result = _safe_json_loads(recognizer.FinalResult())
        final_piece = str(final_result.get("text", "")).strip()
        if final_piece:
            full_text = f"{full_text} {final_piece}".strip()
    except Exception:
        pass

    return {
        "ok": True,
        "text": full_text,
        "backend": backend_key,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Точка входа для тестирования
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🎤 Тестирование голосовой активации Jarvis (Vosk)\n")
    print(f"Wake word: '{WAKE_WORD}'\n")

    activator = VoiceActivator()

    def on_command(text: str):
        print(f"\n✅ КОМАНДА: {text}\n")

    def on_status(status: str):
        print(f"  → {status}")

    activator.set_callback(on_command)
    activator.set_status_callback(on_status)

    if activator.init_models():
        print(f"\n🎤 Скажите '{WAKE_WORD}' и затем команду...\n")
        activator.start_listening()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Остановка...")
            activator.stop_listening()
    else:
        print("\n❌ Не удалось инициализировать Vosk")
