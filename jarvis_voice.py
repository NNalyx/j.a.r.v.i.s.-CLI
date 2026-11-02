#!/usr/bin/env python3
"""
Модуль голосовой активации для Jarvis
- Кастомная запись wake word "джарвис" пользователем
- Сравнение через MFCC + косинусная схожесть
- Silero STT для распознавания команд
"""

import os
import json
import sys
import threading
import tempfile
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
    from transformers import AutoModel
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    AutoModel = None
    TRANSFORMERS_AVAILABLE = False

try:
    import soundfile as sf
    SOUNDFILE_AVAILABLE = True
except ImportError:
    sf = None
    SOUNDFILE_AVAILABLE = False

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

# Legacy Vosk constants are kept only for config/API compatibility.
VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
VOSK_MODEL_NAME = ""
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOSK_SMALL_MODEL_PATH = os.path.join(_BASE_DIR, "models", "vosk-model-small-ru-0.22")
VOSK_LARGE_MODEL_PATH = os.path.join(_BASE_DIR, "models", "vosk-model-ru-0.42")
GIGAAM_TRANSCRIPTION_BACKEND_KEY = "gigaam"
GIGAAM_MODEL_PATH = os.path.join(_BASE_DIR, "models", "GigaAM-Multilingual-ctc")
DEFAULT_TRANSCRIPTION_BACKEND_KEY = GIGAAM_TRANSCRIPTION_BACKEND_KEY
# Compatibility alias used by older Jarvis API code.
LARGE_VOSK_TRANSCRIPTION_BACKEND_KEY = GIGAAM_TRANSCRIPTION_BACKEND_KEY
LEGACY_FASTER_WHISPER_TRANSCRIPTION_BACKEND_KEY = "faster_whisper"
LEGACY_QWEN_TRANSCRIPTION_BACKEND_KEY = "qwen3_asr"

# Один общий экземпляр GigaAM для wake word и ручной записи. Без этого
# кнопка записи создавала второй VoiceActivator и повторно грузила ~800 MB.
_GIGAAM_SHARED_MODEL = None
_GIGAAM_SHARED_DEVICE = ""
_GIGAAM_SHARED_MODEL_LOCK = threading.Lock()
_AUDIO_STREAM_LOCK = threading.Lock()

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


def _preferred_input_device() -> Optional[int]:
    """Выбрать системный входной микрофон, затем доступный вход как fallback."""
    if not MIC_AVAILABLE:
        return None
    try:
        devices = sd.query_devices()
        try:
            default_input = int(sd.default.device[0])
        except (TypeError, ValueError, IndexError):
            default_input = -1

        if 0 <= default_input < len(devices):
            info = devices[default_input]
            if int(info.get("max_input_channels", 0)) > 0:
                print(f"[Voice] 🎙️ Используется системный микрофон: {info.get('name', default_input)}")
                return default_input

        input_devices = [
            (index, info) for index, info in enumerate(devices)
            if int(info.get("max_input_channels", 0)) > 0
        ]
        if sys.platform == "darwin":
            for index, info in input_devices:
                name = str(info.get("name", "")).lower()
                if any(marker in name for marker in ("built-in microphone", "macbook", "встроенн")):
                    print(f"[Voice] 🎙️ Используется встроенный микрофон: {info.get('name', index)}")
                    return index
        if input_devices:
            index, info = input_devices[0]
            print(f"[Voice] 🎙️ Используется доступный микрофон: {info.get('name', index)}")
            return index
    except Exception:
        pass
    return None


def _open_input_stream_with_retry():
    """Открыть микрофон с повтором после временной ошибки AUHAL."""
    last_error = None
    input_device = _preferred_input_device()
    if input_device is None:
        raise RuntimeError("Не найден доступный входной микрофон")
    for attempt in range(3):
        stream = None
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                blocksize=CHUNK_SIZE,
                dtype="float32",
                device=input_device,
            )
            stream.start()
            return stream
        except Exception as exc:
            last_error = exc
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            if attempt < 2:
                print(f"[Voice] ⚠️ Не удалось открыть микрофон, повторяю ({attempt + 1}/2)...")
                time.sleep(0.8)
    raise last_error


# ─────────────────────────────────────────────────────────────────────────────
# Константы
# ─────────────────────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000  # Частота дискретизации
CHUNK_SIZE = 512     # Размер чанка для записи (~32ms при 16kHz)
DURATION_WAKE_WORD = 1.5  # Секунд для записи wake word
SILENCE_THRESHOLD = 0.0025  # Минимальный порог; дальше добавляется адаптация к шуму комнаты
SILENCE_DURATION = 0.35    # Короткая пауза, чтобы wake word не ждал лишнее время
POST_COMMAND_COOLDOWN = 1.8  # Защита от повторного ложного wake-trigger на хвосте той же фразы
GIGAAM_MAX_SHORT_AUDIO_SECONDS = 24.0  # Внутренний лимит ниже ограничения модели в 25 секунд

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
    if normalized in {
        "vosk",
        "vosk_large",
        LEGACY_QWEN_TRANSCRIPTION_BACKEND_KEY,
        LEGACY_FASTER_WHISPER_TRANSCRIPTION_BACKEND_KEY,
        GIGAAM_TRANSCRIPTION_BACKEND_KEY,
    }:
        return GIGAAM_TRANSCRIPTION_BACKEND_KEY
    return GIGAAM_TRANSCRIPTION_BACKEND_KEY


def _supports_large_vosk() -> tuple[bool, str]:
    if not MIC_AVAILABLE:
        return False, "Микрофон недоступен"
    if not VOSK_AVAILABLE:
        return False, "Vosk недоступен"
    large_path = _get_vosk_large_path()
    if not os.path.exists(large_path):
        return False, f"Большая модель Vosk не найдена: {large_path}"
    return True, ""


def _supports_gigaam() -> tuple[bool, str]:
    if not MIC_AVAILABLE:
        return False, "Микрофон недоступен"
    if not TORCH_AVAILABLE or not TRANSFORMERS_AVAILABLE:
        return False, "Для GigaAM нужны torch и transformers"
    if not SOUNDFILE_AVAILABLE:
        return False, "Для GigaAM нужен пакет soundfile"
    if not os.path.isfile(os.path.join(GIGAAM_MODEL_PATH, "pytorch_model.bin")):
        return False, f"Веса GigaAM не найдены: {GIGAAM_MODEL_PATH}"
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
    gigaam_available, gigaam_reason = _supports_gigaam()
    return [{
        "key": GIGAAM_TRANSCRIPTION_BACKEND_KEY,
        "label": "GigaAM Multilingual",
        "description": "Локальное распознавание речи на русском и ещё 4 языках. Модель CTC, 220M параметров.",
        "available": gigaam_available,
        "requires_cuda": False,
        "streaming": False,
        "selected": selected_key == GIGAAM_TRANSCRIPTION_BACKEND_KEY,
        "reason": gigaam_reason,
    }]


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

    Фразы сегментируются по паузам, а wake word и команды распознаются GigaAM.
    """

    def __init__(self, transcription_backend_key: str = DEFAULT_TRANSCRIPTION_BACKEND_KEY):
        self.profile = VoiceProfile()  # Теперь не используется для wake word
        self.stt_model = None  # Silero (не используется)
        self.gigaam_model = None
        self.gigaam_last_error = ""
        self._gigaam_load_lock = threading.Lock()
        self._gigaam_transcribe_lock = threading.Lock()
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
        self.audio_level_callback: Optional[Callable[[float], None]] = None

        self._listen_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._listen_ready_event = threading.Event()
        self._listen_start_error = ""
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
            if item["key"] == GIGAAM_TRANSCRIPTION_BACKEND_KEY and self.gigaam_last_error:
                item["reason"] = self.gigaam_last_error
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

    def init_models(self, force_reload: bool = False):
        """Инициализировать локальную GigaAM-модель распознавания речи."""
        if not MIC_AVAILABLE:
            print("[Voice] ❌ sounddevice не доступен")
            return False
        return self._ensure_gigaam_model(force_reload=force_reload)

    def _ensure_gigaam_model(self, force_reload: bool = False) -> bool:
        global _GIGAAM_SHARED_MODEL, _GIGAAM_SHARED_DEVICE

        supported, reason = _supports_gigaam()
        if not supported:
            self.gigaam_last_error = reason
            print(f"[Voice] ⚠️ GigaAM недоступен: {reason}")
            return False
        if self.gigaam_model is not None and not force_reload:
            return True

        with _GIGAAM_SHARED_MODEL_LOCK:
            if _GIGAAM_SHARED_MODEL is None or force_reload:
                try:
                    print(f"[Voice] ⏳ Загрузка GigaAM: {GIGAAM_MODEL_PATH}")
                    model = AutoModel.from_pretrained(
                        GIGAAM_MODEL_PATH,
                        trust_remote_code=True,
                        local_files_only=True,
                    )
                    _GIGAAM_SHARED_DEVICE = (
                        "mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu"
                    )
                    _GIGAAM_SHARED_MODEL = model.to(_GIGAAM_SHARED_DEVICE).eval()
                    print(f"[Voice] ✅ GigaAM инициализирована на {_GIGAAM_SHARED_DEVICE}")
                except Exception as exc:
                    _GIGAAM_SHARED_MODEL = None
                    self.gigaam_model = None
                    self.gigaam_last_error = str(exc)
                    print(f"[Voice] ⚠️ Ошибка загрузки GigaAM: {exc}")
                    return False

            self.gigaam_model = _GIGAAM_SHARED_MODEL
            self.gigaam_last_error = ""
            return True

    def _transcribe_gigaam_audio(self, audio: np.ndarray) -> str:
        if self.gigaam_model is None and not self._ensure_gigaam_model():
            return ""
        if sf is None:
            return ""
        audio = np.asarray(audio, dtype=np.float32).reshape(-1)
        if audio.size < int(SAMPLE_RATE * 0.15):
            return ""
        # GigaAM's regular transcribe() rejects audio longer than 25 seconds.
        # Split locally so this also works with the downloaded model variant,
        # which does not require the optional pyannote longform dependency.
        max_samples = int(SAMPLE_RATE * GIGAAM_MAX_SHORT_AUDIO_SECONDS)
        chunks = [audio[start:start + max_samples] for start in range(0, len(audio), max_samples)]
        texts = []
        try:
            with self._gigaam_transcribe_lock:
                for chunk in chunks:
                    if chunk.size < int(SAMPLE_RATE * 0.15):
                        continue
                    temp_path = None
                    try:
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                            temp_path = temp_file.name
                        sf.write(temp_path, chunk, SAMPLE_RATE, subtype="PCM_16")
                        result = self.gigaam_model.transcribe(temp_path)
                        text = str(getattr(result, "text", result) or "").strip()
                        if text:
                            texts.append(text)
                    finally:
                        if temp_path:
                            try:
                                os.unlink(temp_path)
                            except OSError:
                                pass
            return " ".join(texts).strip()
        except Exception as exc:
            self.gigaam_last_error = str(exc)
            print(f"[Voice] ⚠️ Ошибка распознавания GigaAM: {exc}")
            return ""

    def _ensure_wake_recognizer(self, force_reload: bool = False) -> bool:
        return self._ensure_gigaam_model(force_reload=force_reload)

    def _ensure_command_backend(self, force_reload: bool = False) -> bool:
        if self.command_backend_key == GIGAAM_TRANSCRIPTION_BACKEND_KEY:
            return self._ensure_gigaam_model(force_reload=force_reload)

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

    def set_audio_level_callback(self, callback: Optional[Callable[[float], None]]):
        """Передавать нормализованный уровень микрофона в UI."""
        self.audio_level_callback = callback

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

    def start_listening(self, startup_timeout: float = 6.0) -> bool:
        """Запустить прослушивание и дождаться открытия аудиовхода."""
        with self._state_lock:
            if self.is_running or (self._listen_thread and self._listen_thread.is_alive()):
                return True

            if not self._ensure_gigaam_model():
                error = self.gigaam_last_error or "Не удалось загрузить модель распознавания"
                self._set_status(f"Ошибка голосовой активации: {error}")
                return False

            self.is_running = True
            self.is_listening = False
            self._stop_event.clear()
            self._listen_ready_event.clear()
            self._listen_start_error = ""
            self.full_transcript = ""
            self.wake_word_detected = False
            self.is_recording = False
            self._set_status("Подключаю микрофон…")

            self._listen_thread = threading.Thread(
                target=self._listen_loop,
                daemon=True,
                name="VoiceActivator"
            )
            self._listen_thread.start()

        if not self._listen_ready_event.wait(timeout=max(0.5, float(startup_timeout))):
            error = "Не удалось подключить микрофон за отведённое время"
        else:
            error = self._listen_start_error

        if error:
            with self._state_lock:
                self.is_running = False
                self.is_listening = False
                self._stop_event.set()
                listen_thread = self._listen_thread
            if listen_thread and listen_thread.is_alive():
                listen_thread.join(timeout=2.0)
            with self._state_lock:
                if self._listen_thread is listen_thread and not listen_thread.is_alive():
                    self._listen_thread = None
            self._set_status(f"Ошибка голосовой активации: {error}")
            return False
        return True

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
        """Запись фраз по паузам и распознавание их через GigaAM."""
        audio_buffer: List[np.ndarray] = []
        speech_started = False
        silence_start = None
        transcription_in_progress = False
        noise_floor = SILENCE_THRESHOLD / 2

        def finish_utterance() -> None:
            nonlocal audio_buffer, speech_started, silence_start, transcription_in_progress
            if not audio_buffer:
                return
            audio = np.concatenate(audio_buffer)
            audio_buffer = []
            speech_started = False
            silence_start = None
            self.is_recording = False
            if transcription_in_progress:
                return
            transcription_in_progress = True

            def transcribe_worker() -> None:
                nonlocal transcription_in_progress
                try:
                    self._set_status("Распознаю фразу...")
                    text = self._transcribe_gigaam_audio(audio)
                    if not text:
                        self._set_status(f"Слушаю речь через GigaAM. Скажите '{WAKE_WORD}'")
                        return

                    print(f"[Voice] GigaAM: {text}")
                    normalized = text.lower().strip()
                    if WAKE_WORD.lower() in normalized:
                        command = _strip_wake_word_prefix(text).strip()
                        if command and command.lower() != normalized:
                            self._dispatch_callback(command)
                            self._arm_wake_cooldown()
                        else:
                            self.wake_word_detected = True
                            self._set_status("Wake word услышан. Говорите команду...")
                        return

                    if self.wake_word_detected:
                        self.wake_word_detected = False
                        self._arm_wake_cooldown()
                        self._set_status("Команда распознана. Отправляю...")
                        self._dispatch_callback(text)
                    else:
                        self._set_status(f"Слушаю речь через GigaAM. Скажите '{WAKE_WORD}'")
                finally:
                    transcription_in_progress = False

            threading.Thread(target=transcribe_worker, daemon=True, name="GigaAMTranscriber").start()

        try:
            lock_acquired = False
            lock_deadline = time.monotonic() + 5.0
            while self.is_running and not self._stop_event.is_set() and time.monotonic() < lock_deadline:
                if _AUDIO_STREAM_LOCK.acquire(timeout=0.2):
                    lock_acquired = True
                    break
            if not lock_acquired:
                if self.is_running and not self._stop_event.is_set():
                    raise RuntimeError("Микрофон занят другой записью")
                return
            stream = None
            try:
                stream = _open_input_stream_with_retry()
                self.wake_word_detected = False
                self.is_listening = True
                self._listen_ready_event.set()
                self._set_status(f"Слушаю wake word '{WAKE_WORD}'")

                while self.is_running and not self._stop_event.is_set():
                    audio_data, overflowed = stream.read(CHUNK_SIZE)
                    if overflowed:
                        print("[Voice] ⚠️ Переполнение аудиобуфера")

                    audio_data = np.asarray(audio_data[:, 0], dtype=np.float32)
                    rms = float(np.sqrt(np.mean(audio_data ** 2)))
                    try:
                        if self.audio_level_callback:
                            self.audio_level_callback(min(1.0, rms * 18.0))
                    except Exception:
                        pass

                    # Пока предыдущая фраза распознаётся, продолжаем читать
                    # микрофон, но не накапливаем новые данные бесконечно.
                    if transcription_in_progress:
                        continue

                    # Подстраиваемся под постоянный шум микрофона. Старый
                    # фиксированный порог 0.001 часто запускал запись от
                    # вентилятора/клавиатуры и создавал большую задержку.
                    if not speech_started:
                        noise_floor = 0.96 * noise_floor + 0.04 * rms
                    adaptive_threshold = max(SILENCE_THRESHOLD, noise_floor * 3.0)
                    has_sound = rms > adaptive_threshold

                    if has_sound or speech_started:
                        audio_buffer.append(audio_data.copy())
                        if has_sound:
                            speech_started = True
                            self.is_recording = True
                            silence_start = None
                        elif silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start > SILENCE_DURATION:
                            finish_utterance()

                        if sum(len(chunk) for chunk in audio_buffer) > SAMPLE_RATE * 25:
                            finish_utterance()
            finally:
                if stream is not None:
                    try:
                        stream.stop()
                    finally:
                        stream.close()
                if lock_acquired:
                    _AUDIO_STREAM_LOCK.release()

        except Exception as e:
            import traceback
            print(f"[Voice] ❌ Ошибка: {e}")
            print(traceback.format_exc())
            self._listen_start_error = str(e)
            self._listen_ready_event.set()
            self._set_status(f"Ошибка голосовой активации GigaAM: {e}")
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

def _record_gigaam_voice_message(
    max_duration: float,
    silence_duration: float,
    stop_event: Optional[threading.Event],
    audio_level_callback: Optional[Callable[[float], None]] = None,
    phase_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    if not _supports_gigaam()[0]:
        return {"ok": False, "error": _supports_gigaam()[1]}

    activator = VoiceActivator(GIGAAM_TRANSCRIPTION_BACKEND_KEY)
    if not activator.init_models():
        return {"ok": False, "error": activator.gigaam_last_error or "Не удалось загрузить GigaAM"}

    audio_chunks: List[np.ndarray] = []
    silence_start = None
    started_at = time.time()
    manual_stop = stop_event is not None
    try:
        if not _AUDIO_STREAM_LOCK.acquire(timeout=15.0):
            return {"ok": False, "error": "Микрофон занят другой записью"}
        stream = None
        try:
            stream = _open_input_stream_with_retry()
            while time.time() - started_at < max(1.0, float(max_duration)):
                if stop_event is not None and stop_event.is_set():
                    break
                audio_data, overflowed = stream.read(CHUNK_SIZE)
                audio_data = np.asarray(audio_data[:, 0], dtype=np.float32)
                audio_chunks.append(audio_data.copy())
                rms = float(np.sqrt(np.mean(audio_data ** 2)))
                has_sound = rms > SILENCE_THRESHOLD
                if audio_level_callback:
                    try:
                        audio_level_callback(min(1.0, rms * 18.0))
                    except Exception:
                        pass
                if has_sound:
                    silence_start = None
                elif silence_start is None:
                    silence_start = time.time()
                elif not manual_stop and time.time() - silence_start > max(0.3, float(silence_duration)):
                    break
        finally:
            if stream is not None:
                try:
                    stream.stop()
                finally:
                    stream.close()
            _AUDIO_STREAM_LOCK.release()
    except Exception as exc:
        return {"ok": False, "error": f"Recording failed: {exc}"}

    if phase_callback:
        try:
            phase_callback("transcribing")
        except Exception:
            pass
    text = activator._transcribe_gigaam_audio(np.concatenate(audio_chunks) if audio_chunks else np.array([], dtype=np.float32))
    return {"ok": True, "text": text, "backend": GIGAAM_TRANSCRIPTION_BACKEND_KEY}

def record_voice_message(
    backend_key: str = DEFAULT_TRANSCRIPTION_BACKEND_KEY,
    max_duration: float = 30.0,
    silence_duration: float = 0.5,
    stop_event: Optional[threading.Event] = None,
    audio_level_callback: Optional[Callable[[float], None]] = None,
    partial_callback: Optional[Callable[[str], None]] = None,
    phase_callback: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Record a short voice message and transcribe it with Vosk.

    Manual recording stays active until stop_event is set or max_duration expires.
    This function opens a short-lived microphone stream and returns recognized text.

    Returns:
        {"ok": True, "text": "...", "backend": backend_key}
        or
        {"ok": False, "error": "..."}
    """
    if not MIC_AVAILABLE:
        return {"ok": False, "error": "Microphone is not available. Install sounddevice."}
    backend_key = _normalize_backend_key(backend_key)

    if backend_key == GIGAAM_TRANSCRIPTION_BACKEND_KEY:
        return _record_gigaam_voice_message(
            max_duration,
            silence_duration,
            stop_event,
            audio_level_callback=audio_level_callback,
            phase_callback=phase_callback,
        )

    if not VOSK_AVAILABLE:
        return {"ok": False, "error": "Vosk is not available. Install vosk."}

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
    input_device = _preferred_input_device()
    if input_device is None:
        return {"ok": False, "error": "Не найден доступный входной микрофон"}

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=CHUNK_SIZE,
            dtype="float32",
            device=input_device,
        ) as stream:
            while time.time() - started_at < max_duration and not (stop_event and stop_event.is_set()):
                audio_data, overflowed = stream.read(CHUNK_SIZE)
                if overflowed:
                    print("[Voice] ⚠️ Audio buffer overflow during voice message recording")

                audio_data = np.asarray(audio_data[:, 0], dtype=np.float32)
                audio_int16 = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
                rms = float(np.sqrt(np.mean(audio_data ** 2)))
                has_sound = rms > SILENCE_THRESHOLD
                if audio_level_callback:
                    try:
                        audio_level_callback(min(1.0, rms * 18.0))
                    except Exception:
                        pass

                # Result() можно вызывать только после того, как Vosk
                # сообщил о завершённом речевом сегменте. Вызов Result() на
                # каждом чанке сбрасывает внутреннее состояние распознавания.
                if recognizer.AcceptWaveform(audio_int16.tobytes()):
                    result = _safe_json_loads(recognizer.Result())
                    text = str(result.get("text", "")).strip()
                    if text:
                        full_text = f"{full_text} {text}".strip()
                        last_partial = full_text
                        if partial_callback:
                            try:
                                partial_callback(full_text)
                            except Exception:
                                pass
                else:
                    try:
                        partial = _safe_json_loads(recognizer.PartialResult())
                    except Exception:
                        partial = {}
                    partial_text = str(partial.get("partial", "")).strip()
                    display_text = f"{full_text} {partial_text}".strip()
                    if display_text != last_partial:
                        last_partial = display_text
                        if partial_callback:
                            try:
                                partial_callback(display_text)
                            except Exception:
                                pass

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

    if phase_callback:
        try:
            phase_callback("transcribing")
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
    print("🎤 Тестирование голосовой активации Jarvis (GigaAM)\n")
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
        print("\n❌ Не удалось инициализировать GigaAM")
