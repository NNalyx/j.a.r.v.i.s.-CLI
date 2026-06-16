"""Llama-server preset loading helpers."""
from .colors import Colors

LLAMA_SERVER_PRESETS = {}


def _load_llama_server_presets():
    """Загружает пресеты из jarvis_config.json."""
    try:
        import config_manager

        config = config_manager.read_config()
        return config_manager.presets_to_runtime(config)
    except Exception as error:
        print(f"{Colors.YELLOW}⚠ Ошибка загрузки конфигурации llama-server: {error}{Colors.RESET}")
        return {}


def reload_llama_server_presets():
    """Перечитать пресеты после изменения jarvis_config.json.

    Изменяем существующий словарь, чтобы все модули, импортировавшие
    LLAMA_SERVER_PRESETS по ссылке, видели обновления без перезапуска.
    """
    global LLAMA_SERVER_PRESETS
    new_presets = _load_llama_server_presets()
    LLAMA_SERVER_PRESETS.clear()
    LLAMA_SERVER_PRESETS.update(new_presets)
    return LLAMA_SERVER_PRESETS


LLAMA_SERVER_PRESETS = _load_llama_server_presets()
