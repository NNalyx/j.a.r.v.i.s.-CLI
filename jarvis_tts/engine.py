"""TTS engine helpers for Supertonic playback."""
import jarvis_core.state as _state
import gc
import json
import os
from pathlib import Path

from jarvis_core.colors import Colors
from jarvis_core.constants import TTS_AVAILABLE, SupertonicTTS, np

from .text import preprocess_text, _detect_tts_language


def _save_wav_pcm16(output_path: Path, wav_data, sample_rate: int) -> None:
    """Сохранить аудио в обычный PCM WAV без внешних зависимостей."""
    import wave

    array = np.asarray(wav_data, dtype=np.float32) if np is not None else wav_data
    array = np.clip(array, -1.0, 1.0)

    if getattr(array, "ndim", 1) > 1:
        array = array.reshape(-1)

    pcm16 = (array * 32767.0).astype(np.int16)

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm16.tobytes())

def _play_wav_windows(output_path: Path) -> bool:
    """Надёжное воспроизведение WAV в Windows через winsound."""
    if os.name != "nt":
        return False

    try:
        import winsound
        winsound.PlaySound(str(output_path), winsound.SND_FILENAME)
        return True
    except Exception:
        return False

def _load_voice_style_from_json(style_path: Path):
    """Загрузить кастомный voice-style JSON для Supertonic."""
    with open(style_path, "r", encoding="utf-8") as f:
        return json.load(f)

def _resolve_supertonic_voice_style():
    """Получить активный voice style: кастомный JSON или встроенный голос."""

    from .tts import TTS

    custom_path = TTS._voice_style_path
    if not custom_path:
        default_style_path = Path(__file__).parent / "jarvis_supertonic_voice_style.json"
        if default_style_path.exists() and default_style_path.is_file():
            custom_path = str(default_style_path)
            TTS._voice_style_path = custom_path

    if custom_path:
        style_path = Path(custom_path)
        if style_path.exists() and style_path.is_file():
            return _load_voice_style_from_json(style_path)

    return _state._tts_model.get_voice_style(voice_name=TTS._voice_name)

def _init_supertonic():
    """Инициализировать Supertonic модель."""

    if _state._tts_model is not None:
        return True

    if not TTS_AVAILABLE:
        return False

    try:
        _state._tts_device = "cpu"

        # Подавляем весь вывод при загрузке модели
        import sys
        import io
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        try:
            _state._tts_model = SupertonicTTS(auto_download=True)
            _state._tts_voice_style = _resolve_supertonic_voice_style()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        return True

    except Exception as e:
        print(f"{Colors.RED}[Supertonic] Ошибка инициализации: {e}{Colors.RESET}")
        return False

def _unload_supertonic():
    """Выгрузить Supertonic модель из памяти."""

    try:
        if _state._tts_model is not None:
            model = _state._tts_model
            _state._tts_model = None
            _state._tts_device = None
            _state._tts_voice_style = None
            del model

        gc.collect()

        return True
    except Exception as e:
        print(f"{Colors.YELLOW}[Supertonic] Ошибка выгрузки: {e}{Colors.RESET}")
        return False

def speak_now(text, ref_audio_path=None, ref_text=None, speed=1.0, volume=1.0,
              preprocess=True):
    """
    Озвучивает текст с помощью Supertonic 3

    Args:
        text: Текст для озвучивания
        ref_audio_path: Сохранён для совместимости старого API, не используется
        ref_text: Сохранён для совместимости старого API, не используется
        speed: Скорость речи (0.5-2.0) - пока не поддерживается Supertonic
        volume: Громкость (0.0-2.0)
        preprocess: Предобрабатывать текст
    """

    if not text or not TTS_AVAILABLE:
        return

    try:
        # Инициализируем модель если нужно
        if _state._tts_model is None:
            if not _init_supertonic():
                return

        if preprocess:
            text = preprocess_text(text[:1000])

        # Подавляем вывод при синтезе (перенаправляем stdout/stderr в StringIO)
        import sys
        import io
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        try:
            synth_kwargs = {
                "text": text,
                "lang": _detect_tts_language(text),
            }
            if _state._tts_voice_style is not None:
                synth_kwargs["voice_style"] = _state._tts_voice_style
            wav, _ = _state._tts_model.synthesize(**synth_kwargs)
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        if wav is not None:
            sr = 44100
            wav = np.asarray(wav, dtype=np.float32) if np is not None else wav
            wav = wav * volume
            wav = np.clip(wav, -1.0, 1.0) if np is not None else wav
            output_path = Path(__file__).parent / "tts_output.wav"

            try:
                import sounddevice as sd
                sd.play(wav, samplerate=sr)
                sd.wait()
            except Exception:
                try:
                    _save_wav_pcm16(output_path, wav, sr)
                    if not _play_wav_windows(output_path):
                        raise RuntimeError("winsound playback failed")
                except Exception as playback_error:
                    try:
                        _save_wav_pcm16(output_path, wav, sr)
                    except Exception as save_error:
                        print(f"{Colors.YELLOW}[Supertonic] Не удалось воспроизвести или сохранить звук: {save_error}{Colors.RESET}")
                    else:
                        print(f"{Colors.YELLOW}[Supertonic] Звук сохранён в {output_path}, но не был воспроизведён автоматически: {playback_error}{Colors.RESET}")

    except Exception as e:
        print(f"{Colors.YELLOW}[Supertonic] Ошибка: {e}{Colors.RESET}")

