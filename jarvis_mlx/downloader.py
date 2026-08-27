"""Download MLX/HuggingFace models with progress and ETA."""
import os
import time
from pathlib import Path
from typing import Callable, Optional


def _parse_repo_id(raw: str) -> str:
    """Нормализовать ввод пользователя в repo_id."""
    raw = raw.strip()
    # Убираем префикс https://huggingface.co/
    if raw.startswith("https://huggingface.co/"):
        raw = raw[len("https://huggingface.co/"):]
    # Убираем trailing slash и ?...
    raw = raw.split("?")[0].rstrip("/")
    return raw


def _format_size(size_bytes: float) -> str:
    if size_bytes < 1024:
        return f"{size_bytes:.0f} B"
    for unit in ("KB", "MB", "GB", "TB"):
        size_bytes /= 1024
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
    return f"{size_bytes:.2f} PB"


def _format_time(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours}h {minutes}m"


class DownloadProgress:
    def __init__(self, callback: Optional[Callable[[str, float, float, float, float, Optional[float]], None]] = None):
        self.callback = callback
        self.started_at: Optional[float] = None
        self.total_files = 0
        self.completed_files = 0
        self.current_file_total = 0.0
        self.current_file_downloaded = 0.0

    def __call__(self, downloaded: float, total: float, finished: bool = False, filename: str = ""):
        if self.started_at is None:
            self.started_at = time.time()

        self.current_file_total = total
        self.current_file_downloaded = downloaded

        elapsed = time.time() - self.started_at
        speed = downloaded / elapsed if elapsed > 0 else 0.0
        eta = None
        if speed > 0 and total > downloaded:
            eta = (total - downloaded) / speed

        percent = (downloaded / total * 100) if total > 0 else 0.0

        message = filename or "Downloading..."
        if self.callback:
            self.callback(message, downloaded, total, percent, speed, eta)

    def file_finished(self):
        self.completed_files += 1


def download_model(
    repo_id: str,
    local_dir: Optional[str] = None,
    cache_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[str, float, float, float, float, Optional[float]], None]] = None,
    allow_patterns: Optional[list] = None,
    ignore_patterns: Optional[list] = None,
    hf_token: Optional[str] = None,
) -> str:
    """Скачать модель с HuggingFace Hub.

    Возвращает путь к папке с моделью.
    """
    repo_id = _parse_repo_id(repo_id)
    if not repo_id or "/" not in repo_id:
        raise ValueError(f"Некорректный HuggingFace repo_id: {repo_id}")

    if local_dir is None:
        # Сохраняем в ~/.mlx_models/<repo_id>
        base = Path.home() / ".mlx_models"
        local_dir = str(base / repo_id.replace("/", "--"))

    os.makedirs(local_dir, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub не установлен") from exc

    progress = DownloadProgress(callback=progress_callback)

    def _hf_progress_callback(bytes_downloaded: float, total_bytes: float, file_name: str = ""):
        progress(bytes_downloaded, total_bytes, filename=file_name or "Downloading...")

    kwargs: dict = {
        "repo_id": repo_id,
        "local_dir": local_dir,
        "local_dir_use_symlinks": False,
        "resume_download": True,
    }
    if allow_patterns:
        kwargs["allow_patterns"] = allow_patterns
    if ignore_patterns:
        kwargs["ignore_patterns"] = ignore_patterns
    if hf_token:
        kwargs["token"] = hf_token

    # Пробуем передать progress_callback, если библиотека поддерживает
    try:
        snapshot_download(**kwargs, progress_callback=_hf_progress_callback)
    except TypeError:
        # Старая версия huggingface_hub
        snapshot_download(**kwargs)

    return os.path.abspath(local_dir)


def default_cli_progress(message: str, downloaded: float, total: float, percent: float, speed: float, eta: Optional[float]):
    """Простой CLI progress bar."""
    bar_length = 30
    filled = int(bar_length * percent / 100)
    bar = "█" * filled + "░" * (bar_length - filled)
    eta_str = _format_time(eta) if eta is not None else "?"
    print(
        f"\r[{bar}] {percent:5.1f}% | {_format_size(downloaded)}/{_format_size(total)} | "
        f"{_format_size(speed)}/s | ETA {eta_str} | {message[:40]}",
        end="",
        flush=True,
    )
