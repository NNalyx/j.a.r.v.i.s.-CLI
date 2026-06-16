import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Общий конфиг рядом с исполняемым файлом проекта
BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "jarvis_config.json"

DEFAULT_LLAMA_SERVER_PATHS = [
    os.path.join(BASE_DIR, "models", "llama-server.exe"),
    os.path.join(BASE_DIR, "llama-server.exe"),
    r"C:\llama_server\llama-server.exe",
    r"C:\llama_server_new\llama-server.exe",
    r"C:\llama.cpp\llama-server.exe",
    r".\llama-server.exe",
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
        
        # Нормализация пути (замена обратных слешей и раскрытие ~)
        path = os.path.abspath(os.path.expanduser(path)).replace('/', '\\')
        
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

def presets_to_runtime(config: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Преобразует jarvis_config.json в runtime-пресеты для jarvis_cli_gui."""
    if not config:
        return {}

    presets: Dict[str, Dict[str, Any]] = {}
    for i, preset in enumerate(config.get("presets", [])):
        key = f"preset_{i}"
        llama_server_path = preset.get("llama_server_path", "")
        try:
            llama_server_path = resolve_llama_server_executable(llama_server_path)
        except ValueError:
            llama_server_path = normalize_path(llama_server_path)
        args: List[str] = [
            llama_server_path,
            "-m", preset["model_path"],
            "-c", str(preset["context_size"]),
            "-ngl", str(preset["ngl"]),
            "--port", str(preset["port"]),
            "--host", "127.0.0.1",
        ]
        if preset.get("mmproj_path"):
            args.extend(["--mmproj", preset["mmproj_path"]])
        if preset.get("mtp_path"):
            args.extend([
                "--model-draft", preset["mtp_path"],
                "--spec-type", "draft-mtp",
                "--spec-draft-n-max", "2",
            ])

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
    return os.path.abspath(os.path.expanduser(cleaned)).replace("/", "\\")


def needs_setup() -> bool:
    config = read_config()
    return not config or not config.get("presets")


def preset_to_public(preset: Dict[str, Any], index: int, active_index: int) -> Dict[str, Any]:
    mmproj_path = preset.get("mmproj_path") or ""
    mtp_path = preset.get("mtp_path") or ""
    return {
        "index": index,
        "key": f"preset_{index}",
        "name": preset.get("name") or f"Preset {index + 1}",
        "llama_server_path": preset.get("llama_server_path", ""),
        "model_path": preset.get("model_path", ""),
        "mmproj_path": mmproj_path,
        "mtp_path": mtp_path,
        "context_size": int(preset.get("context_size", 18432)),
        "ngl": int(preset.get("ngl", 99)),
        "port": int(preset.get("port", 8080)),
        "supports_images": bool(mmproj_path),
        "selected": index == active_index,
        "enabled_tools": preset.get("enabled_tools"),
        "description": (
            f"Контекст: {preset.get('context_size', 18432)}, "
            f"GPU слои: {preset.get('ngl', 99)}"
            + (f", Vision" if mmproj_path else ", Текстовая")
            + (f", MTP" if mtp_path else "")
        ),
    }


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
        "detected_llama_server": find_llama_server(),
        "vosk_small_model_path": config.get("vosk_small_model_path", find_vosk_small_model()),
        "vosk_large_model_path": config.get("vosk_large_model_path", find_vosk_large_model()),
        "presets": [
            preset_to_public(preset, index, active_index)
            for index, preset in enumerate(presets)
        ],
    }


def build_preset_record(data: Dict[str, Any]) -> Dict[str, Any]:
    name = str(data.get("name") or "").strip() or "Default"
    llama_server_path = resolve_llama_server_executable(data.get("llama_server_path", ""))
    model_path = normalize_path(data.get("model_path", ""))
    mmproj_path = normalize_path(data.get("mmproj_path", ""), allow_empty=True)
    mtp_path = normalize_path(data.get("mtp_path", ""), allow_empty=True)

    try:
        context_size = int(data.get("context_size", 18432))
        ngl = int(data.get("ngl", 99))
        port = int(data.get("port", 8080))
    except (TypeError, ValueError) as error:
        raise ValueError("Контекст, GPU-слои и порт должны быть целыми числами") from error

    if context_size <= 0 or ngl < 0 or port <= 0:
        raise ValueError("Некорректные числовые параметры пресета")

    enabled_tools = data.get("enabled_tools")
    if enabled_tools is not None:
        enabled_tools = [
            str(tool_name).strip()
            for tool_name in enabled_tools
            if str(tool_name).strip()
        ]

    return {
        "name": name,
        "llama_server_path": llama_server_path,
        "model_path": model_path,
        "mmproj_path": mmproj_path,
        "mtp_path": mtp_path,
        "context_size": context_size,
        "ngl": ngl,
        "port": port,
        "enabled_tools": enabled_tools,
    }


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
        
    print(f"[{len(presets)+1}] Создать новый пресет")
    print("[0] Выйти")
    
    while True:
        choice = input("\nВыберите действие (введите номер): ").strip()
        if choice == "0":
            print("Выход из программы.")
            sys.exit(0)
        elif choice == str(len(presets) + 1):
            return setup_wizard()
        
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
        return None, None

    p = presets[idx]
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

    command = " ".join(f'"{arg}"' if " " in arg else arg for arg in args)
    return cwd, args, command
