import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis_mlx import IS_MLX_AVAILABLE
from jarvis_mlx.discovery import discover_models, find_single_model, prompt_for_model_path


def find_mtplx_executable():
    """Найти исполняемый файл mtplx (venv или PATH)."""
    path = shutil.which("mtplx")
    if path:
        return path
    venv_path = os.path.join(sys.prefix, "bin", "mtplx")
    if os.path.exists(venv_path):
        return venv_path
    return "mtplx"


def find_optiq_executable():
    """Найти исполняемый файл optiq (venv или PATH)."""
    path = shutil.which("optiq")
    if path:
        return path
    venv_path = os.path.join(sys.prefix, "bin", "optiq")
    if os.path.exists(venv_path):
        return venv_path
    return "optiq"

# Общий конфиг рядом с исполняемым файлом проекта
BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "jarvis_config.json"

_IS_DARWIN = sys.platform == "darwin"

DEFAULT_LLAMA_SERVER_PATHS = [
    os.path.join(BASE_DIR, "models", "llama-server.exe"),
    os.path.join(BASE_DIR, "llama-server.exe"),
    r"C:\llama_server\llama-server.exe",
    r"C:\llama_server_new\llama-server.exe",
    r"C:\llama.cpp\llama-server.exe",
    r".\llama-server.exe",
]

DEFAULT_MLX_MODEL_ROOTS = [
    os.path.join(Path.home(), ".mlx_models"),
    os.path.join(Path.home(), "models"),
    os.path.join(Path.home(), "MLXModels"),
]

DEFAULT_VOSK_SMALL_PATHS = [
    os.path.join(BASE_DIR, "models", "vosk-model-small-ru-0.22"),
    os.path.join(BASE_DIR, "vosk_models", "vosk-model-small-ru-0.22"),
    os.path.join(BASE_DIR, "vosk-model-small-ru-0.22"),
    os.path.join(BASE_DIR, "..", "vosk-model-small-ru-0.22"),
]

DEFAULT_VOSK_LARGE_PATHS = [
    os.path.join(BASE_DIR, "models", "vosk-model-ru-0.42"),
    os.path.join(BASE_DIR, "vosk_models", "vosk-model-ru-0.42"),
    os.path.join(BASE_DIR, "vosk-model-ru-0.42"),
    os.path.join(BASE_DIR, "..", "vosk-model-ru-0.42"),
]


def find_llama_server():
    """Автоматический поиск llama-server.exe в стандартных путях."""
    for path in DEFAULT_LLAMA_SERVER_PATHS:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            return abs_path
    return ""


def find_vosk_small_model():
    """Автоматический поиск малой Vosk модели."""
    for path in DEFAULT_VOSK_SMALL_PATHS:
        abs_path = os.path.abspath(path)
        if os.path.isdir(abs_path):
            return abs_path
    return ""


def find_vosk_large_model():
    """Автоматический поиск большой Vosk модели."""
    for path in DEFAULT_VOSK_LARGE_PATHS:
        abs_path = os.path.abspath(path)
        if os.path.isdir(abs_path):
            return abs_path
    return ""


def resolve_llama_server_executable(path: str) -> str:
    """llama.exe — CLI, для Jarvis нужен llama-server.exe."""
    normalized = normalize_path(path)
    base_name = os.path.basename(normalized).lower()
    server_dir = os.path.dirname(normalized)

    if base_name == "llama-server.exe":
        return normalized

    if base_name == "llama.exe":
        sibling = os.path.join(server_dir, "llama-server.exe")
        if os.path.exists(sibling):
            return sibling
        raise ValueError(
            "Указан llama.exe — это консольный клиент, а не сервер. "
            "Выберите llama-server.exe из той же папки."
        )

    if base_name.endswith(".exe") and "server" not in base_name:
        sibling = os.path.join(server_dir, "llama-server.exe")
        if os.path.exists(sibling):
            return sibling

    return normalized


def print_setup_instructions():
    print("\n" + "="*70)
    print(" 🚀 НАСТРОЙКА JARVIS WEB UI (LLAMA.CPP)")
    print("="*70)
    print("\n📌 ЧТО НУЖНО СКАЧАТЬ И КУДА:")
    print("1. llama-server (исполняемый файл):")
    print("   -> https://github.com/ggerganov/llama.cpp/releases")
    print("   -> Ищите архив вида 'llama-bXXXX-bin-win-cu12.X-x64.zip' (для NVIDIA GPU)")
    print("      или '...-x64.zip' (для CPU).")
    print("   -> Распакуйте `llama-server.exe` в папку, например, C:\\llama_server\\")
    print("\n2. Модель (.gguf файл):")
    print("   -> https://huggingface.co/models?search=gguf")
    print("   -> Рекомендуемые: Qwen2.5-7B-Instruct-GGUF, Llama-3-8B-Instruct-GGUF.")
    print("   -> Выбирайте квантование Q4_K_M или Q5_K_M для баланса скорости и качества.")
    print("\n3. Файл проектора (mmproj.gguf) - ОПЦИОНАЛЬНО:")
    print("   -> Нужен ТОЛЬКО если модель поддерживает зрение (Vision).")
    print("   -> Скачивается из того же репозитория Hugging Face, что и модель")
    print("      (файл с 'mmproj' или 'vision' в названии).")
    print("="*70 + "\n")

def get_valid_path(prompt_text, default_path="", allow_empty=False):
    while True:
        path = input(f"{prompt_text}\n[{default_path}]\n> ").strip()
        if not path:
            path = default_path
            
        if not path and allow_empty:
            return ""
        if not path:
            print("⚠️ Путь не может быть пустым.")
            continue
        
        # Нормализация пути (раскрытие ~)
        path = os.path.abspath(os.path.expanduser(path))
        if sys.platform == "win32":
            path = path.replace('/', '\\')
        
        if os.path.exists(path):
            return path
        else:
            print(f"⚠️ Файл не найден по пути: {path}")
            retry = input("Продолжить с этим путем всё равно? (y/n) [n]: ").strip().lower()
            if retry == 'y':
                return path

def get_valid_int(prompt_text, default_val):
    while True:
        val = input(f"{prompt_text} [{default_val}]\n> ").strip()
        if not val:
            return default_val
        try:
            return int(val)
        except ValueError:
            print("⚠️ Введите корректное целое число.")

def setup_mlx_wizard():
    """Мастер настройки MLX-пресета для macOS."""
    print("\n" + "="*70)
    print(" 🍎 НАСТРОЙКА MLX ПРЕСЕТА (macOS)")
    print("="*70)

    preset_name = input("\nВведите название для этого пресета (например, 'Qwen-MLX-Vision')\n[MLX Default]\n> ").strip()
    if not preset_name:
        preset_name = "MLX Default"

    # Автообнаружение локальных моделей
    found_models = discover_models()
    model_path = ""
    if len(found_models) == 1:
        print(f"✅ Найдена локальная модель: {found_models[0]}")
        if ask_yes_no("Использовать её?", default=True):
            model_path = str(found_models[0])
    elif len(found_models) > 1:
        print("\nНайдено несколько локальных моделей:")
        for i, m in enumerate(found_models, 1):
            print(f"  {i}. {m}")
        print("  0. Указать путь вручную / скачать с HuggingFace")
        choice = get_valid_int("Выберите модель", 0)
        if 1 <= choice <= len(found_models):
            model_path = str(found_models[choice - 1])
    else:
        print("⚠️ Локальные MLX модели не найдены.")

    if not model_path:
        if ask_yes_no("Скачать модель с HuggingFace?", default=True):
            from jarvis_mlx.downloader import default_cli_progress, download_model
            repo_id = input("Введите HuggingFace repo_id (например, mlx-community/Qwen2-VL-7B-Instruct-mlx):\n> ").strip()
            if not repo_id:
                print("⚠️ repo_id не указан.")
                return setup_mlx_wizard()
            try:
                print(f"\n⬇️ Начинаю загрузку {repo_id}...")
                model_path = download_model(repo_id, progress_callback=default_cli_progress)
                print(f"\n✅ Модель сохранена: {model_path}")
            except Exception as exc:
                print(f"\n❌ Ошибка загрузки: {exc}")
                if ask_yes_no("Указать путь к локальной модели вручную?", default=True):
                    model_path = prompt_for_model_path()
                else:
                    raise
        else:
            model_path = prompt_for_model_path()

    temperature = get_valid_float("Temperature (0.0 - 2.0)", 0.7)
    max_tokens = get_valid_int("Максимум токенов для генерации", 512)
    port = get_valid_int("Порт для MLX-сервера", 8080)

    return {
        "name": preset_name,
        "backend": "mlx-vlm",
        "model_path": normalize_path(model_path),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "port": port,
    }


def get_valid_float(prompt_text, default_val):
    while True:
        val = input(f"{prompt_text} [{default_val}]\n> ").strip()
        if not val:
            return default_val
        try:
            return float(val)
        except ValueError:
            print("⚠️ Введите корректное число.")


def ask_yes_no(prompt_text: str, default: bool = False) -> bool:
    default_str = "Y/n" if default else "y/N"
    while True:
        val = input(f"{prompt_text} [{default_str}]: ").strip().lower()
        if not val:
            return default
        if val in ("y", "yes", "да"):
            return True
        if val in ("n", "no", "нет"):
            return False
        print("⚠️ Введите y или n.")


def presets_to_runtime(config: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Преобразует jarvis_config.json в runtime-пресеты для jarvis_cli_gui."""
    if not config:
        return {}

    presets: Dict[str, Dict[str, Any]] = {}
    for i, preset in enumerate(config.get("presets", [])):
        key = f"preset_{i}"
        backend = preset.get("backend", "llama-server")

        if backend == "mlx-vlm":
            model_path = preset["model_path"]
            port = int(preset.get("port", 8080))
            args: List[str] = [
                sys.executable,
                "-m",
                "jarvis_mlx.server",
                "--model", model_path,
                "--port", str(port),
                "--host", "127.0.0.1",
            ]
            if preset.get("temperature") is not None:
                args.extend(["--temp", str(preset["temperature"])])
            if preset.get("max_tokens") is not None:
                args.extend(["--max-tokens", str(preset["max_tokens"])])

            command = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
            presets[key] = {
                "label": preset["name"],
                "description": f"MLX backend | Порт: {port}",
                "supports_images": True,
                "cwd": str(BASE_DIR),
                "args": args,
                "command": command,
                "config_index": i,
                "backend": backend,
                "port": port,
                "context_size": int(preset.get("context_size", 32768)),
                "max_tokens": int(preset.get("max_tokens", 512)),
                "temperature": float(preset.get("temperature", 0.7)),
            }
            continue

        if backend == "mlx-optiq":
            model_path = preset["model_path"]
            port = int(preset.get("port", 8080))
            args = [
                find_optiq_executable(),
                "serve",
                "--model", model_path,
                "--port", str(port),
                "--host", "127.0.0.1",
                "--max-concurrent", str(int(preset.get("max_concurrent", 4))),
                "--no-auth",
            ]
            if preset.get("temperature") is not None:
                args.extend(["--temp", str(float(preset["temperature"]))])
            if preset.get("max_tokens") is not None:
                args.extend(["--max-tokens", str(int(preset["max_tokens"]))])
            if preset.get("context_size"):
                # OptiQ имеет нативный --max-context; mlx_lm.server --max-seq-length не понимает.
                args.extend(["--max-context", str(int(preset["context_size"]))])
            # OptiQ/MLX performance options
            if preset.get("kv_bits") in (4, 8):
                args.extend(["--kv-bits", str(int(preset["kv_bits"]))])
                if preset.get("kv_group_size") is not None:
                    args.extend(["--kv-group-size", str(int(preset["kv_group_size"]))])
                if preset.get("quantized_kv_start") is not None:
                    args.extend(["--quantized-kv-start", str(int(preset["quantized_kv_start"]))])
            elif preset.get("kv_config"):
                args.extend(["--kv-config", str(preset["kv_config"])])
            if preset.get("prefill_step_size") is not None:
                args.extend(["--prefill-step-size", str(int(preset["prefill_step_size"]))])
            if preset.get("prompt_cache_size") is not None:
                args.extend(["--prompt-cache-size", str(int(preset["prompt_cache_size"]))])
            if preset.get("prompt_cache_bytes") is not None:
                args.extend(["--prompt-cache-bytes", str(int(preset["prompt_cache_bytes"]))])
            if preset.get("pipeline"):
                args.append("--pipeline")
            if preset.get("mtp_enabled"):
                args.append("--mtp")
                if preset.get("mtp_depth") is not None:
                    args.extend(["--mtp-depth", str(int(preset["mtp_depth"]))])
            command = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
            presets[key] = {
                "label": preset["name"],
                "description": f"MLX-OptiQ backend | Порт: {port}",
                "supports_images": False,
                "cwd": str(BASE_DIR),
                "args": args,
                "command": command,
                "config_index": i,
                "backend": backend,
                "port": port,
                "context_size": int(preset.get("context_size", 32768)),
                "max_tokens": int(preset.get("max_tokens", 8192)),
                "temperature": float(preset.get("temperature", 0.6)),
            }
            continue

        if backend == "mtplx":
            model_path = preset["model_path"]
            port = int(preset.get("port", 8080))
            args = [
                find_mtplx_executable(),
                "serve",
                "--model", model_path,
                "--port", str(port),
                "--host", "127.0.0.1",
                "--profile", "sustained",
                "--unsafe-force-unverified",
                "--yes",
                "--no-stats-footer",
            ]
            # MTPLX v0.1.x управляет размером контекста через профиль (sustained
            # для длинного контекста); отдельного флага --context-window нет.
            if preset.get("max_tokens"):
                args.extend(["--max-tokens", str(int(preset["max_tokens"]))])
            if preset.get("temperature") is not None:
                args.extend(["--default-temperature", str(float(preset["temperature"]))])
            if preset.get("mtp_enabled") and preset.get("mtp_n_max"):
                args.extend(["--depth", str(int(preset["mtp_n_max"]))])
            else:
                args.append("--no-mtp")
            command = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
            presets[key] = {
                "label": preset["name"],
                "description": f"MTPLX backend | Порт: {port}",
                "supports_images": False,
                "cwd": str(BASE_DIR),
                "args": args,
                "command": command,
                "config_index": i,
                "backend": backend,
                "port": port,
                "context_size": int(preset.get("context_size", 32768)),
                "max_tokens": int(preset.get("max_tokens", 8192)),
                "temperature": float(preset.get("temperature", 0.6)),
            }
            continue

        llama_server_path = preset.get("llama_server_path", "")
        try:
            llama_server_path = resolve_llama_server_executable(llama_server_path)
        except ValueError:
            llama_server_path = normalize_path(llama_server_path)
        args = [
            llama_server_path,
            "-m", preset["model_path"],
            "-c", str(preset["context_size"]),
            "-ngl", str(preset["ngl"]),
            "--port", str(preset["port"]),
            "--host", "127.0.0.1",
        ]
        if preset.get("mmproj_path"):
            args.extend(["--mmproj", preset["mmproj_path"]])
        if preset.get("mtp_enabled") and not preset.get("mtp_path"):
            # Встроенный MTP (Qwen3.6 и аналогичные): draft-модель не нужна
            args.extend([
                "--spec-type", "draft-mtp",
                "--spec-draft-n-max", str(int(preset.get("mtp_n_max", 2))),
            ])
        elif preset.get("mtp_path"):
            args.extend([
                "--model-draft", preset["mtp_path"],
                "--spec-type", "draft-mtp",
                "--spec-draft-n-max", str(int(preset.get("mtp_n_max", 2))),
            ])
        if preset.get("chat_template_file"):
            args.extend(["--chat-template-file", preset["chat_template_file"]])
        extra_args = preset.get("extra_args")
        if isinstance(extra_args, list):
            args.extend([str(arg) for arg in extra_args if arg is not None])

        # command — строковое представление для совместимости и отладки
        command = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)

        presets[key] = {
            "label": preset["name"],
            "description": f"Контекст: {preset['context_size']}, GPU слои: {preset['ngl']}",
            "supports_images": bool(preset.get("mmproj_path")),
            "cwd": os.path.dirname(llama_server_path),
            "args": args,
            "command": command,
            "config_index": i,
            "backend": backend,
            "port": int(preset.get("port", 8080)),
        }
    return presets


def read_config() -> Optional[Dict[str, Any]]:
    """Прочитать конфиг без интерактивного мастера настройки."""
    if not CONFIG_FILE.exists():
        return None

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return None


def default_config() -> Dict[str, Any]:
    return {
        "presets": [],
        "active_preset_index": 0,
        "vosk_small_model_path": find_vosk_small_model(),
        "vosk_large_model_path": find_vosk_large_model(),
    }


def write_config(config: Dict[str, Any]) -> Dict[str, Any]:
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)
    return config


def normalize_path(path: str, allow_empty: bool = False) -> str:
    cleaned = (path or "").strip()
    if not cleaned:
        if allow_empty:
            return ""
        raise ValueError("Путь не может быть пустым")
    normalized = os.path.abspath(os.path.expanduser(cleaned))
    # На Windows используем обратные слеши, на остальных платформах оставляем как есть
    if sys.platform == "win32":
        return normalized.replace("/", "\\")
    return normalized


def needs_setup() -> bool:
    config = read_config()
    return not config or not config.get("presets")


def preset_to_public(preset: Dict[str, Any], index: int, active_index: int) -> Dict[str, Any]:
    mmproj_path = preset.get("mmproj_path") or ""
    mtp_path = preset.get("mtp_path") or ""
    mtp_enabled = bool(preset.get("mtp_enabled"))
    backend = preset.get("backend", "llama-server")

    base = {
        "index": index,
        "key": f"preset_{index}",
        "name": preset.get("name") or f"Preset {index + 1}",
        "backend": backend,
        "model_path": preset.get("model_path", ""),
        "chat_template_file": preset.get("chat_template_file", ""),
        "port": int(preset.get("port", 8080)),
        "selected": index == active_index,
        "enabled_tools": preset.get("enabled_tools"),
        "system_prompt_mode": preset.get("system_prompt_mode", "full"),
    }

    if backend == "mlx-vlm":
        base.update({
            "llama_server_path": "",
            "mmproj_path": "",
            "mtp_path": "",
            "context_size": 0,
            "ngl": 0,
            "supports_images": True,
            "temperature": float(preset.get("temperature", 0.7)),
            "max_tokens": int(preset.get("max_tokens", 512)),
            "description": (
                f"MLX backend | Порт: {preset.get('port', 8080)} | "
                f"temp: {preset.get('temperature', 0.7)} | "
                f"max_tokens: {preset.get('max_tokens', 512)}"
            ),
        })
        return base

    if backend == "mlx-optiq":
        base.update({
            "llama_server_path": "",
            "mmproj_path": "",
            "mtp_path": "",
            "context_size": int(preset.get("context_size", 32768)),
            "ngl": 0,
            "supports_images": False,
            "temperature": float(preset.get("temperature", 0.6)),
            "max_tokens": int(preset.get("max_tokens", 8192)),
            "max_concurrent": int(preset.get("max_concurrent", 4)),
            "kv_bits": preset.get("kv_bits"),
            "kv_group_size": int(preset.get("kv_group_size", 64)),
            "quantized_kv_start": int(preset.get("quantized_kv_start", 0)),
            "kv_config": preset.get("kv_config", ""),
            "prefill_step_size": int(preset.get("prefill_step_size", 2048)),
            "prompt_cache_size": preset.get("prompt_cache_size"),
            "prompt_cache_bytes": preset.get("prompt_cache_bytes"),
            "pipeline": bool(preset.get("pipeline", False)),
            "mtp_enabled": bool(preset.get("mtp_enabled", False)),
            "mtp_depth": int(preset.get("mtp_depth", 2)),
            "description": (
                f"MLX-OptiQ backend | Порт: {preset.get('port', 8080)} | "
                f"ctx: {preset.get('context_size', 32768)} | "
                f"temp: {preset.get('temperature', 0.6)} | "
                f"max: {preset.get('max_tokens', 8192)}"
            ),
        })
        return base

    if backend == "mtplx":
        mtp_enabled = bool(preset.get("mtp_enabled", True))
        base.update({
            "llama_server_path": "",
            "mmproj_path": "",
            "mtp_path": "",
            "context_size": int(preset.get("context_size", 32768)),
            "ngl": 0,
            "supports_images": False,
            "temperature": float(preset.get("temperature", 0.6)),
            "max_tokens": int(preset.get("max_tokens", 8192)),
            "mtp_enabled": mtp_enabled,
            "mtp_n_max": int(preset.get("mtp_n_max", 3)),
            "description": (
                f"MTPLX backend | Порт: {preset.get('port', 8080)} | "
                f"ctx: {preset.get('context_size', 32768)} | "
                f"temp: {preset.get('temperature', 0.6)} | "
                f"max: {preset.get('max_tokens', 8192)}"
                + (f", MTP depth {preset.get('mtp_n_max', 3)}" if mtp_enabled else ", AR only")
            ),
        })
        return base

    extra_args = preset.get("extra_args")
    if not isinstance(extra_args, list):
        extra_args = []
    base.update({
        "llama_server_path": preset.get("llama_server_path", ""),
        "mmproj_path": mmproj_path,
        "mtp_path": mtp_path,
        "mtp_enabled": mtp_enabled,
        "chat_template_file": preset.get("chat_template_file", ""),
        "context_size": int(preset.get("context_size", 18432)),
        "ngl": int(preset.get("ngl", 99)),
        "supports_images": bool(mmproj_path),
        "extra_args": extra_args,
        "description": (
            f"Контекст: {preset.get('context_size', 18432)}, "
            f"GPU слои: {preset.get('ngl', 99)}"
            + (f", Vision" if mmproj_path else ", Текстовая")
            + (f", MTP" if mtp_enabled or mtp_path else "")
            + (f", +{len(extra_args)} extra" if extra_args else "")
        ),
    })
    return base


def get_config_status() -> Dict[str, Any]:
    config = read_config() or default_config()
    presets = config.get("presets", [])
    active_index = int(config.get("active_preset_index", 0) or 0)
    if presets and active_index >= len(presets):
        active_index = 0

    return {
        "needs_setup": not presets,
        "config_path": str(CONFIG_FILE),
        "active_preset_index": active_index,
        "active_preset_key": f"preset_{active_index}" if presets else None,
        "is_macos": bool(_IS_DARWIN and IS_MLX_AVAILABLE),
        "detected_llama_server": find_llama_server(),
        "vosk_small_model_path": config.get("vosk_small_model_path", find_vosk_small_model()),
        "vosk_large_model_path": config.get("vosk_large_model_path", find_vosk_large_model()),
        "presets": [
            preset_to_public(preset, index, active_index)
            for index, preset in enumerate(presets)
        ],
    }


def build_preset_record(data: Dict[str, Any]) -> Dict[str, Any]:
    backend = str(data.get("backend", "llama-server")).strip().lower()
    if backend not in ("llama-server", "mlx-vlm", "mlx-optiq", "mtplx"):
        backend = "llama-server"

    name = str(data.get("name") or "").strip() or "Default"
    model_path = normalize_path(data.get("model_path", ""))

    try:
        port = int(data.get("port", 8080))
    except (TypeError, ValueError) as error:
        raise ValueError("Порт должен быть целым числом") from error
    if port <= 0:
        raise ValueError("Некорректный порт")

    enabled_tools = data.get("enabled_tools")
    if enabled_tools is not None:
        enabled_tools = [
            str(tool_name).strip()
            for tool_name in enabled_tools
            if str(tool_name).strip()
        ]

    record: Dict[str, Any] = {
        "name": name,
        "backend": backend,
        "model_path": model_path,
        "port": port,
        "enabled_tools": enabled_tools,
    }

    if backend == "mlx-vlm":
        try:
            temperature = float(data.get("temperature", 0.7))
            max_tokens = int(data.get("max_tokens", 512))
        except (TypeError, ValueError) as error:
            raise ValueError("Temperature и max_tokens должны быть числами") from error
        if temperature < 0 or max_tokens <= 0:
            raise ValueError("Некорректные параметры MLX")
        record["temperature"] = temperature
        record["max_tokens"] = max_tokens
        return record

    if backend == "mlx-optiq":
        try:
            temperature = float(data.get("temperature", 0.6))
            max_tokens = int(data.get("max_tokens", 8192))
            context_size = int(data.get("context_size", 32768))
            max_concurrent = int(data.get("max_concurrent", 4))
            kv_bits = data.get("kv_bits")
            if kv_bits is not None:
                kv_bits = int(kv_bits)
                if kv_bits not in (4, 8):
                    raise ValueError("kv_bits должен быть 4 или 8")
            kv_group_size = int(data.get("kv_group_size", 64))
            quantized_kv_start = int(data.get("quantized_kv_start", 0))
            prefill_step_size = int(data.get("prefill_step_size", 2048))
            prompt_cache_size = data.get("prompt_cache_size")
            if prompt_cache_size is not None:
                prompt_cache_size = int(prompt_cache_size)
            prompt_cache_bytes = data.get("prompt_cache_bytes")
            if prompt_cache_bytes is not None:
                prompt_cache_bytes = int(prompt_cache_bytes)
            mtp_depth = int(data.get("mtp_depth", 2))
        except (TypeError, ValueError) as error:
            raise ValueError("Параметры MLX-OptiQ имеют некорректный тип") from error
        if temperature < 0 or max_tokens <= 0 or context_size <= 0 or max_concurrent <= 0 or kv_group_size <= 0 or quantized_kv_start < 0 or prefill_step_size <= 0 or mtp_depth < 0:
            raise ValueError("Некорректные параметры MLX-OptiQ")
        record["temperature"] = temperature
        record["max_tokens"] = max_tokens
        record["context_size"] = context_size
        record["max_concurrent"] = max_concurrent
        if kv_bits is not None:
            record["kv_bits"] = kv_bits
        record["kv_group_size"] = kv_group_size
        record["quantized_kv_start"] = quantized_kv_start
        record["prefill_step_size"] = prefill_step_size
        if prompt_cache_size is not None:
            record["prompt_cache_size"] = prompt_cache_size
        if prompt_cache_bytes is not None:
            record["prompt_cache_bytes"] = prompt_cache_bytes
        record["pipeline"] = bool(data.get("pipeline", False))
        record["mtp_enabled"] = bool(data.get("mtp_enabled", False))
        record["mtp_depth"] = mtp_depth
        kv_config = str(data.get("kv_config", "")).strip()
        if kv_config:
            record["kv_config"] = kv_config
        return record

    if backend == "mtplx":
        try:
            temperature = float(data.get("temperature", 0.6))
            max_tokens = int(data.get("max_tokens", 12288))
            context_size = int(data.get("context_size", 65536))
            mtp_n_max = int(data.get("mtp_n_max", 3))
        except (TypeError, ValueError) as error:
            raise ValueError("Temperature, max_tokens, context_size и mtp_n_max должны быть числами") from error
        if temperature < 0 or max_tokens <= 0 or context_size <= 0 or mtp_n_max < 0:
            raise ValueError("Некорректные параметры MTPLX")
        record["temperature"] = temperature
        record["max_tokens"] = max_tokens
        record["context_size"] = context_size
        record["mtp_enabled"] = bool(data.get("mtp_enabled", True))
        record["mtp_n_max"] = mtp_n_max
        return record

    llama_server_path = resolve_llama_server_executable(data.get("llama_server_path", ""))
    mmproj_path = normalize_path(data.get("mmproj_path", ""), allow_empty=True)
    mtp_path = normalize_path(data.get("mtp_path", ""), allow_empty=True)
    mtp_enabled = bool(data.get("mtp_enabled"))
    chat_template_file = normalize_path(data.get("chat_template_file", ""), allow_empty=True)

    try:
        context_size = int(data.get("context_size", 18432))
        ngl = int(data.get("ngl", 99))
    except (TypeError, ValueError) as error:
        raise ValueError("Контекст, GPU-слои и порт должны быть целыми числами") from error

    if context_size <= 0 or ngl < 0:
        raise ValueError("Некорректные числовые параметры пресета")

    extra_args = data.get("extra_args")
    if isinstance(extra_args, list):
        extra_args = [str(arg) for arg in extra_args if arg is not None]
        if extra_args:
            record["extra_args"] = extra_args

    system_prompt_mode = str(data.get("system_prompt_mode", "full")).strip().lower()
    if system_prompt_mode not in {"full", "minimal", "none"}:
        system_prompt_mode = "full"
    record["system_prompt_mode"] = system_prompt_mode

    record.update({
        "llama_server_path": llama_server_path,
        "mmproj_path": mmproj_path,
        "mtp_path": mtp_path,
        "mtp_enabled": mtp_enabled,
        "chat_template_file": chat_template_file,
        "context_size": context_size,
        "ngl": ngl,
    })
    return record


def add_preset(data: Dict[str, Any], make_active: bool = True) -> Dict[str, Any]:
    preset = build_preset_record(data)
    config = read_config() or default_config()
    config.setdefault("presets", []).append(preset)
    if make_active:
        config["active_preset_index"] = len(config["presets"]) - 1
    write_config(config)
    return get_config_status()


def select_preset_index(index: int) -> Dict[str, Any]:
    config = read_config() or default_config()
    presets = config.get("presets", [])
    if not presets:
        raise ValueError("Нет сохранённых пресетов")
    if index < 0 or index >= len(presets):
        raise ValueError("Некорректный индекс пресета")

    config["active_preset_index"] = index
    write_config(config)
    return get_config_status()


def delete_preset_index(index: int) -> Dict[str, Any]:
    config = read_config() or default_config()
    presets = config.get("presets", [])
    if not presets:
        raise ValueError("Нет сохранённых пресетов")
    if index < 0 or index >= len(presets):
        raise ValueError("Некорректный индекс пресета")

    del presets[index]
    active_index = int(config.get("active_preset_index", 0) or 0)

    if active_index == index:
        if presets:
            config["active_preset_index"] = 0
        else:
            config.pop("active_preset_index", None)
    elif active_index > index:
        config["active_preset_index"] = active_index - 1

    write_config(config)
    return get_config_status()


def update_preset_tools(index: int, enabled_tools: List[str]) -> Dict[str, Any]:
    config = read_config() or default_config()
    presets = config.get("presets", [])
    if not presets:
        raise ValueError("Нет сохранённых пресетов")
    if index < 0 or index >= len(presets):
        raise ValueError("Некорректный индекс пресета")

    presets[index]["enabled_tools"] = [
        str(tool_name).strip()
        for tool_name in enabled_tools
        if str(tool_name).strip()
    ]
    write_config(config)
    return get_config_status()


def setup_wizard():
    if _IS_DARWIN and IS_MLX_AVAILABLE:
        print("\n🍎 Обнаружена macOS. Доступны два типа пресетов:")
        print("  1. MLX (рекомендуется для Apple Silicon)")
        print("  2. llama-server (GGUF модели)")
        choice = get_valid_int("Выберите тип пресета", 1)
        if choice == 1:
            return setup_mlx_wizard()

    print_setup_instructions()
    
    # 1. Llama Server Path
    auto_detected = find_llama_server()
    if auto_detected:
        print(f"✅ Автоматически найден llama-server: {auto_detected}")
    else:
        print("⚠️ llama-server не найден в стандартных путях (C:\\llama_server).")
    
    llama_path = get_valid_path(
        "Введите абсолютный путь к llama-server.exe", 
        auto_detected or r"C:\llama_server\llama-server.exe"
    )
    
    # 2. Preset Name
    preset_name = input("\nВведите название для этого пресета (например, 'Qwen-7B-Vision')\n[Default]\n> ").strip()
    if not preset_name:
        preset_name = "Default"
        
    # 3. Model Path
    model_path = get_valid_path(
        "Введите абсолютный путь к .gguf файлу модели",
        r"C:\llama_server\model.gguf"
    )
    
    # 4. MMProj Path
    mmproj_path = get_valid_path(
        "Введите абсолютный путь к mmproj.gguf (оставьте пустым, если модель текстовая)",
        r"C:\llama_server\mmproj.gguf",
        allow_empty=True
    )
    
    # 5. Context Size
    context_size = get_valid_int("Введите размер контекста (например, 8192, 18432, 32768)", 18432)
    
    # 6. NGL (GPU layers)
    ngl = get_valid_int("Количество слоев для загрузки на GPU (-ngl, 99 = все)", 99)
    
    # 7. Port
    port = get_valid_int("Порт для llama-server", 8080)
    
    # 8. Vosk Small Model Path (опционально)
    auto_vosk_small = find_vosk_small_model()
    if auto_vosk_small:
        print(f"\n✅ Автоматически найдена малая Vosk модель: {auto_vosk_small}")
    else:
        print("\n⚠️ Малая Vosk модель не найдена. Голосовой ввод будет недоступен.")
    vosk_small = get_valid_path(
        "Введите путь к папке малой Vosk модели (vosk-model-small-ru-0.22) или оставьте пустым",
        auto_vosk_small or "",
        allow_empty=True
    )
    
    # 9. Vosk Large Model Path (опционально)
    auto_vosk_large = find_vosk_large_model()
    if auto_vosk_large:
        print(f"✅ Автоматически найдена большая Vosk модель: {auto_vosk_large}")
    else:
        print("⚠️ Большая Vosk модель не найдена.")
    vosk_large = get_valid_path(
        "Введите путь к папке большой Vosk модели (vosk-model-ru-0.42) или оставьте пустым",
        auto_vosk_large or "",
        allow_empty=True
    )
    
    # Build preset
    new_preset = {
        "name": preset_name,
        "llama_server_path": llama_path,
        "model_path": model_path,
        "mmproj_path": mmproj_path,
        "context_size": context_size,
        "ngl": ngl,
        "port": port
    }
    
    config = {"presets": [], "active_preset_index": 0, "vosk_small_model_path": "", "vosk_large_model_path": ""}
    existing = read_config()
    if existing:
        config = existing
            
    config["presets"].append(new_preset)
    config["active_preset_index"] = len(config["presets"]) - 1
    if vosk_small:
        config["vosk_small_model_path"] = normalize_path(vosk_small)
    if vosk_large:
        config["vosk_large_model_path"] = normalize_path(vosk_large)
    
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
        
    print(f"\n✅ Конфигурация успешно сохранена в {CONFIG_FILE}")
    return config

def load_config():
    if not CONFIG_FILE.exists():
        print("⚠️ Файл конфигурации jarvis_config.json не найден.")
        print("Запуск мастера первоначальной настройки...\n")
        return setup_wizard()
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # Миграция: добавляем vosk пути в старые конфиги
        updated = False
        if not config.get("vosk_small_model_path"):
            config["vosk_small_model_path"] = find_vosk_small_model()
            updated = True
        if not config.get("vosk_large_model_path"):
            config["vosk_large_model_path"] = find_vosk_large_model()
            updated = True
        if updated:
            write_config(config)
            
        if not config.get("presets"):
            print("⚠️ В конфигурации нет сохраненных пресетов.")
            return setup_wizard()
            
        return config
    except Exception as e:
        print(f"⚠️ Ошибка чтения конфигурации: {e}")
        print("Запуск мастера настройки заново...\n")
        return setup_wizard()

def select_preset(config):
    presets = config.get("presets", [])
    print("\n" + "="*70)
    print(" 📂 СОХРАНЕННЫЕ ПРЕСЕТЫ")
    print("="*70)
    for i, p in enumerate(presets):
        active_marker = "👉 " if i == config.get("active_preset_index", 0) else "   "
        print(f"{active_marker}{i+1}. {p['name']}")
        print(f"      Модель: {p['model_path']}")
        mmproj_info = f" | MMProj: {p['mmproj_path']}" if p.get('mmproj_path') else " | Текстовая"
        print(f"      Контекст: {p['context_size']} | GPU слои: {p['ngl']}{mmproj_info}")
        print(f"      Сервер: {p['llama_server_path']} (Порт: {p['port']})")
        print("-" * 70)
        
    if _IS_DARWIN and IS_MLX_AVAILABLE:
        print(f"[{len(presets)+1}] Создать новый llama-server пресет")
        print(f"[{len(presets)+2}] Создать новый MLX пресет")
        print("[0] Выйти")
        mlx_option = True
    else:
        print(f"[{len(presets)+1}] Создать новый пресет")
        print("[0] Выйти")
        mlx_option = False
    
    while True:
        choice = input("\nВыберите действие (введите номер): ").strip()
        if choice == "0":
            print("Выход из программы.")
            sys.exit(0)
        elif choice == str(len(presets) + 1):
            return setup_wizard()
        elif mlx_option and choice == str(len(presets) + 2):
            return setup_mlx_wizard()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(presets):
                config["active_preset_index"] = idx
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                return config
        except ValueError:
            pass
        print("⚠️ Неверный выбор. Попробуйте снова.")

def get_active_preset_command(config):
    """Возвращает cwd и список аргументов для активного пресета."""
    presets = config.get("presets", [])
    idx = config.get("active_preset_index", 0)
    if not presets or idx >= len(presets):
        return None, None, None

    p = presets[idx]
    backend = p.get("backend", "llama-server")

    if backend == "mlx-vlm":
        port = int(p.get("port", 8080))
        args = [
            sys.executable,
            "-m",
            "jarvis_mlx.server",
            "--model", p["model_path"],
            "--port", str(port),
            "--host", "127.0.0.1",
        ]
        if p.get("temperature") is not None:
            args.extend(["--temp", str(p["temperature"])])
        if p.get("max_tokens") is not None:
            args.extend(["--max-tokens", str(p["max_tokens"])])
        command = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
        return str(BASE_DIR), args, command

    if backend == "mlx-optiq":
        port = int(p.get("port", 8080))
        args = [
            find_optiq_executable(),
            "serve",
            "--model", p["model_path"],
            "--port", str(port),
            "--host", "127.0.0.1",
            "--max-concurrent", str(int(p.get("max_concurrent", 4))),
            "--no-auth",
        ]
        if p.get("temperature") is not None:
            args.extend(["--temp", str(float(p["temperature"]))])
        if p.get("max_tokens") is not None:
            args.extend(["--max-tokens", str(int(p["max_tokens"]))])
        if p.get("context_size"):
            args.extend(["--max-context", str(int(p["context_size"]))])
        if p.get("kv_bits") in (4, 8):
            args.extend(["--kv-bits", str(int(p["kv_bits"]))])
            if p.get("kv_group_size") is not None:
                args.extend(["--kv-group-size", str(int(p["kv_group_size"]))])
            if p.get("quantized_kv_start") is not None:
                args.extend(["--quantized-kv-start", str(int(p["quantized_kv_start"]))])
        elif p.get("kv_config"):
            args.extend(["--kv-config", str(p["kv_config"])])
        if p.get("prefill_step_size") is not None:
            args.extend(["--prefill-step-size", str(int(p["prefill_step_size"]))])
        if p.get("prompt_cache_size") is not None:
            args.extend(["--prompt-cache-size", str(int(p["prompt_cache_size"]))])
        if p.get("prompt_cache_bytes") is not None:
            args.extend(["--prompt-cache-bytes", str(int(p["prompt_cache_bytes"]))])
        if p.get("pipeline"):
            args.append("--pipeline")
        if p.get("mtp_enabled"):
            args.append("--mtp")
            if p.get("mtp_depth") is not None:
                args.extend(["--mtp-depth", str(int(p["mtp_depth"]))])
        command = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
        return str(BASE_DIR), args, command

    if backend == "mtplx":
        port = int(p.get("port", 8080))
        args = [
            find_mtplx_executable(),
            "serve",
            "--model", p["model_path"],
            "--port", str(port),
            "--host", "127.0.0.1",
            "--profile", "sustained",
            "--unsafe-force-unverified",
            "--yes",
            "--no-stats-footer",
        ]
        # MTPLX v0.1.x управляет размером контекста через профиль (sustained
        # для длинного контекста); отдельного флага --context-window нет.
        if p.get("max_tokens"):
            args.extend(["--max-tokens", str(int(p["max_tokens"]))])
        if p.get("temperature") is not None:
            args.extend(["--default-temperature", str(float(p["temperature"]))])
        if p.get("mtp_enabled") and p.get("mtp_n_max"):
            args.extend(["--depth", str(int(p["mtp_n_max"]))])
        else:
            args.append("--no-mtp")
        command = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
        return str(BASE_DIR), args, command

    cwd = os.path.dirname(p["llama_server_path"])

    args = [
        p["llama_server_path"],
        "-m", p["model_path"],
        "-c", str(p["context_size"]),
        "-ngl", str(p["ngl"]),
        "--port", str(p["port"]),
        "--host", "127.0.0.1",
    ]
    if p.get("mmproj_path"):
        args.extend(["--mmproj", p["mmproj_path"]])
    if p.get("mtp_enabled") and not p.get("mtp_path"):
        args.extend([
            "--spec-type", "draft-mtp",
            "--spec-draft-n-max", str(int(p.get("mtp_n_max", 2))),
        ])
    elif p.get("mtp_path"):
        args.extend([
            "--model-draft", p["mtp_path"],
            "--spec-type", "draft-mtp",
            "--spec-draft-n-max", str(int(p.get("mtp_n_max", 2))),
        ])
    if p.get("chat_template_file"):
        args.extend(["--chat-template-file", p["chat_template_file"]])

    command = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
    return cwd, args, command
