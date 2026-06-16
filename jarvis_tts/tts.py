"""TTS public API."""
import jarvis_core.state as _state
from pathlib import Path
from typing import List, Optional

from jarvis_core.colors import Colors
from jarvis_core.constants import TTS_AVAILABLE

from .engine import _init_supertonic, _unload_supertonic, speak_now


class TTS:
    """Голосовой вывод (Text-to-Speech) поверх Supertonic 3."""

    _enabled = False
    _ref_audio_path = None  # Сохранено для совместимости старого API
    _ref_text = ""
    _volume = 1.0
    _speed = 1.0  # Скорость речи (0.5-2.0) - пока не поддерживается Supertonic
    _voice_name = "F1"
    _voice_style_path = None

    @classmethod
    def enable(cls):
        """Включить TTS"""
        if not TTS_AVAILABLE:
            print("[TTS] Supertonic недоступен. Установите: pip install supertonic numpy sounddevice soundfile")
            return False
        cls._enabled = True
        return True

    @classmethod
    def disable(cls):
        """Выключить TTS"""
        cls._enabled = False

    @classmethod
    def is_enabled(cls) -> bool:
        """Проверить статус TTS"""
        return cls._enabled

    @classmethod
    def is_available(cls) -> bool:
        """Проверить доступность TTS зависимостей."""
        return TTS_AVAILABLE

    @classmethod
    def is_model_loaded(cls) -> bool:
        """Проверить, загружена ли Supertonic модель в память."""
        return _state._tts_model is not None

    @classmethod
    def get_device(cls) -> Optional[str]:
        """Текущее устройство модели."""
        return _state._tts_device

    @classmethod
    def load_model(cls) -> bool:
        """Явно загрузить Supertonic модель."""
        if not TTS_AVAILABLE:
            return False

        with _state._tts_lock:
            loaded = _init_supertonic()
            if loaded:
                cls._enabled = True
            return loaded

    @classmethod
    def unload_model(cls) -> bool:
        """Явно выгрузить Supertonic модель из памяти."""
        with _state._tts_lock:
            cls._enabled = False
            return _unload_supertonic()

    @classmethod
    def set_ref_audio(cls, ref_audio_path: str,
                      ref_text: str = ""):
        """Сохранить старый reference path и попытаться найти style JSON рядом."""
        cls._ref_audio_path = ref_audio_path
        cls._ref_text = ref_text

        cls._voice_style_path = None
        if ref_audio_path:
            ref_path = Path(ref_audio_path)
            candidates = []
            if ref_path.suffix.lower() == ".json":
                candidates.append(ref_path)
            else:
                candidates.append(ref_path.with_suffix(".json"))
                candidates.append(ref_path.with_name(f"{ref_path.stem}.voice.json"))

            for candidate in candidates:
                if candidate.exists() and candidate.is_file():
                    cls._voice_style_path = str(candidate)
                    break

    @classmethod
    def set_volume(cls, volume: float):
        """Установить громкость (0.0-2.0)"""
        cls._volume = max(0.0, min(2.0, volume))

    @classmethod
    def set_speed(cls, speed: float):
        """Установить скорость речи (0.5-2.0) - зарезервировано для будущего использования"""
        cls._speed = max(0.5, min(2.0, speed))

    @classmethod
    def set_voice_name(cls, voice_name: str):
        """Выбрать встроенный голос Supertonic."""

        value = str(voice_name or "").strip().upper()
        cls._voice_name = value or "F1"
        cls._voice_style_path = None

        if _state._tts_model is not None:
            _state._tts_voice_style = _resolve_supertonic_voice_style()

    @classmethod
    def set_voice_style_path(cls, style_path: Optional[str]):
        """Подключить кастомный Supertonic voice-style JSON."""

        cls._voice_style_path = str(style_path).strip() if style_path else None
        if _state._tts_model is not None:
            _state._tts_voice_style = _resolve_supertonic_voice_style()

    @classmethod
    def speak(cls, text: str) -> bool:
        """Озвучить текст"""
        if not cls._enabled:
            return False
        if not TTS_AVAILABLE:
            print("[TTS] Supertonic недоступен")
            return False

        try:
            with _state._tts_lock:
                speak_now(
                    text=text,
                    ref_audio_path=cls._ref_audio_path,
                    ref_text=cls._ref_text,
                    speed=cls._speed,
                    volume=cls._volume
                )
            return True
        except Exception as e:
            print(f"{Colors.YELLOW}[TTS] Ошибка: {e}{Colors.RESET}")
            return False

    @classmethod
    def speak_paragraphs(cls, paragraphs: List[str], context: str = "") -> bool:
        """
        Озвучить первый и последний абзацы, объединённые в один текст.

        Args:
            paragraphs: Список абзацев текста
            context: Контекст для инструкции

        Returns:
            True если успешно, False иначе
        """
        if not cls._enabled or not paragraphs:
            return False

        # Фильтруем абзацы, убираем технические (списки инструментов, команды и т.д.)
        content_paragraphs = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            # Пропускаем абзацы с маркерами списков и заголовками
            if (p.startswith('```') or p.startswith('1.') or p.startswith('•') or
                    p.startswith('-') or p.startswith('[') or p.startswith('─')):
                continue
            content_paragraphs.append(p)

        if not content_paragraphs:
            return False

        # Объединяем первый и последний абзацы в один текст для озвучки
        first_para = content_paragraphs[0].strip()

        if len(content_paragraphs) > 1:
            last_para = content_paragraphs[-1].strip()
            # Если первый и последний абзацы разные, объединяем их
            if last_para != first_para:
                # Объединяем с паузой между абзацами
                combined_text = f"{first_para} ... {last_para}"
            else:
                combined_text = first_para
        else:
            combined_text = first_para

        # Озвучиваем объединённый текст
        return cls.speak(combined_text)

