"""Auto-discovery of MLX / HuggingFace model directories."""
import os
from pathlib import Path
from typing import List, Optional


DEFAULT_SEARCH_ROOTS = [
    "~/.mlx_models",
    "~/models",
    "~/.cache/huggingface/hub",
    "~/.cache/lm-studio/models",
    "~/MLXModels",
]


def _is_model_directory(path: Path) -> bool:
    """Проверить, выглядит ли папка как загруженная HF/MLX модель."""
    if not path.is_dir():
        return False

    # Признаки HF-модели
    has_config = (path / "config.json").is_file()
    has_safetensors = any(path.glob("*.safetensors"))
    has_pytorch = any(path.glob("pytorch_model*.bin"))
    has_tokenizer = (path / "tokenizer.json").is_file() or (path / "tokenizer.model").is_file()
    has_optiq = (path / "optiq_metadata.json").is_file()

    # OptiQ-модели имеют стандартный MLX-формат + optiq_metadata.json
    if has_config and has_safetensors and has_tokenizer:
        return True
    # Дополнительный признак: явная OptiQ-модель с метаданными
    if has_optiq and has_config and (has_safetensors or has_pytorch):
        return True
    return False


def discover_models(extra_roots: Optional[List[str]] = None) -> List[Path]:
    """Найти локальные MLX/HF модели."""
    roots = [Path.home() / ".mlx_models", Path.home() / "models"]
    for raw in DEFAULT_SEARCH_ROOTS:
        expanded = Path(os.path.expanduser(raw))
        if expanded not in roots:
            roots.append(expanded)

    if extra_roots:
        for raw in extra_roots:
            expanded = Path(os.path.expanduser(raw))
            if expanded not in roots:
                roots.append(expanded)

    seen: set[str] = set()
    models: List[Path] = []

    for root in roots:
        if not root.exists():
            continue

        # Если в корне лежит сразу модель — берём корень
        if _is_model_directory(root):
            key = str(root.resolve())
            if key not in seen:
                seen.add(key)
                models.append(root)
            continue

        # Иначе ищем в подпапках на один уровень
        for candidate in root.iterdir():
            if not candidate.is_dir():
                continue
            if _is_model_directory(candidate):
                key = str(candidate.resolve())
                if key not in seen:
                    seen.add(key)
                    models.append(candidate)

    return models


def find_single_model(extra_roots: Optional[List[str]] = None) -> Optional[Path]:
    """Вернуть единственную найденную модель или None, если их 0 или >1."""
    models = discover_models(extra_roots=extra_roots)
    if len(models) == 1:
        return models[0]
    return None


def prompt_for_model_path() -> str:
    """Запросить путь к модели в интерактивном режиме."""
    while True:
        raw = input("Введите путь к папке с MLX/HF моделью: ").strip()
        if not raw:
            print("Путь не может быть пустым.")
            continue
        expanded = os.path.expanduser(raw)
        if not os.path.isdir(expanded):
            print(f"Папка не найдена: {expanded}")
            continue
        if not _is_model_directory(Path(expanded)):
            print("В папке не обнаружены признаки модели (config.json + safetensors/bin + tokenizer).")
            confirm = input("Использовать её всё равно? (y/n) [n]: ").strip().lower()
            if confirm != "y":
                continue
        return os.path.abspath(expanded)
