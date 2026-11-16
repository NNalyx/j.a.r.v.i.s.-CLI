"""Transcribe a local audio/video file with Jarvis's already configured GigaAM."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from jarvis_core.types import ToolResult


def transcribe_video(path: str, activator: Any = None) -> ToolResult:
    """Return the speech transcript from a local video/audio path using GigaAM."""
    if not path or not str(path).strip():
        return ToolResult(False, None, "Укажи полный путь к видео- или аудиофайлу.")

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        return ToolResult(False, None, f"Файл не найден: {source}")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return ToolResult(False, None, "Для чтения аудио из видео нужен ffmpeg (на Mac: brew install ffmpeg).")

    try:
        import jarvis_voice
    except ImportError as exc:
        return ToolResult(False, None, f"Не удалось загрузить модуль GigaAM Jarvis: {exc}")

    available, reason = jarvis_voice._supports_gigaam()
    if not available:
        return ToolResult(False, None, f"Встроенная GigaAM недоступна: {reason}")

    # Reuse the desktop agent's activator so the already loaded weights and
    # inference lock are shared with voice input. No model download is started.
    if activator is None:
        activator = jarvis_voice.VoiceActivator(
            transcription_backend_key=jarvis_voice.GIGAAM_TRANSCRIPTION_BACKEND_KEY
        )
    if not activator._ensure_gigaam_model():
        detail = getattr(activator, "gigaam_last_error", "")
        return ToolResult(False, None, f"Не удалось инициализировать встроенную GigaAM. {detail}".strip())
    activator.gigaam_last_error = ""

    sample_rate = int(jarvis_voice.SAMPLE_RATE)
    chunk_seconds = int(jarvis_voice.GIGAAM_MAX_SHORT_AUDIO_SECONDS)
    chunk_bytes = sample_rate * chunk_seconds * 4  # mono float32 PCM
    command = [
        ffmpeg, "-nostdin", "-v", "error", "-i", str(source),
        "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(sample_rate),
        "-f", "f32le", "pipe:1",
    ]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as exc:
        return ToolResult(False, None, f"Не удалось запустить ffmpeg: {exc}")

    transcripts: list[str] = []
    try:
        assert process.stdout is not None
        while True:
            audio_bytes = process.stdout.read(chunk_bytes)
            if not audio_bytes:
                break
            audio_bytes = audio_bytes[: len(audio_bytes) - (len(audio_bytes) % 4)]
            if not audio_bytes:
                continue
            audio = np.frombuffer(audio_bytes, dtype="<f4").copy()
            text = activator._transcribe_gigaam_audio(audio).strip()
            if text:
                transcripts.append(text)
        stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
        return_code = process.wait()
    except Exception as exc:
        process.kill()
        process.wait()
        return ToolResult(False, None, f"Ошибка транскрибации {source.name}: {exc}")
    finally:
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()

    if return_code:
        reason = stderr.strip() or f"ffmpeg завершился с кодом {return_code}"
        return ToolResult(False, None, f"Не удалось извлечь аудио из {source.name}: {reason}")

    transcript = "\n".join(transcripts).strip()
    inference_error = getattr(activator, "gigaam_last_error", "")
    if inference_error:
        return ToolResult(False, {
            "source": str(source),
            "engine": "GigaAM Multilingual (Jarvis)",
            "transcript": transcript,
        }, f"Ошибка распознавания GigaAM: {inference_error}")
    return ToolResult(True, {
        "source": str(source),
        "engine": "GigaAM Multilingual (Jarvis)",
        "transcript": transcript,
        "characters": len(transcript),
    })
