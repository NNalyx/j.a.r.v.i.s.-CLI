"""Global constants, feature flags, and optional imports for Jarvis."""
import os
from pathlib import Path

# Base project directory (where jarvis_cli_gui.py lives)
BASE_DIR = Path(__file__).resolve().parent.parent

# Fuzzy search for click_text
try:
    from fuzzywuzzy import fuzz, process

    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False
    fuzz = None
    process = None

# Voice activation
try:
    from jarvis_voice import (
        DEFAULT_TRANSCRIPTION_BACKEND_KEY,
        VoiceActivator,
        get_transcription_backend_catalog,
    )

    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False
    VoiceActivator = None
    DEFAULT_TRANSCRIPTION_BACKEND_KEY = "vosk"

    def get_transcription_backend_catalog():
        return []

# Telegram bot
try:
    from jarvis_telegram import TelegramBotManager, init_bot, get_bot

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    TelegramBotManager = None
    init_bot = None
    get_bot = None

# TTS (Text-to-Speech) - Supertone Supertonic 3 (CPU)
try:
    import numpy as np
    from supertonic import TTS as SupertonicTTS

    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    np = None
    SupertonicTTS = None

# OCR for click_text (EasyOCR)
try:
    import easyocr

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    easyocr = None

# UI Automation
try:
    from pywinauto import Desktop

    UI_AUTOMATION_AVAILABLE = True
except ImportError:
    UI_AUTOMATION_AVAILABLE = False
    Desktop = None

APP_MAPS_FILE = BASE_DIR / "jarvis_app_maps.json"
MEMORY_FILE = BASE_DIR / "jarvis_memory.json"

DEFAULT_MODEL_KEY = "preset_0"

ENGLISH_TO_RUSSIAN = {
    "hello": "хелл+о", "world": "ворлд", "python": "п+айтон", "windows": "в+индоус",
    "linux": "л+инукс", "google": "гугл", "youtube": "ют+уб", "telegram": "телегр+ам",
    "android": "андр+оид", "iphone": "айф+он", "apple": "+эпл", "microsoft": "м+айкрософт",
    "facebook": "ф+ейсбук", "instagram": "инстагр+ам", "twitter": "тв+иттер", "email": "им+ейл",
    "internet": "интерн+ет", "computer": "комп+ьютер", "server": "с+ервер", "error": "+эррор",
    "warning": "в+орнинг", "update": "апд+ейт", "download": "д+аунлоад", "upload": "апл+оад",
    "file": "файл", "folder": "ф+олдер", "ok": "ок+ей", "yes": "йес", "no": "ноу",
    "please": "плиз", "thanks": "сэнкс", "sorry": "с+орри", "bye": "бай", "good": "гуд",
    "bad": "бэд", "jarvis": "дж+арвис", "sir": "сэр", "ai": "ай ай", "cpu": "си пи ю",
    "gpu": "джи пи ю", "ram": "рам", "ssd": "эс эс ди", "usb": "ю эс би", "wifi": "вай фай",
    "bluetooth": "блют+уз", "-": "минус", "+": "плюс",
}

TRANSLIT_MAP = {
    'a': 'а', 'b': 'б', 'c': 'к', 'd': 'д', 'e': 'е', 'f': 'ф', 'g': 'г', 'h': 'х', 'i': 'и',
    'j': 'дж', 'k': 'к', 'l': 'л', 'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п', 'q': 'к', 'r': 'р',
    's': 'с', 't': 'т', 'u': 'у', 'v': 'в', 'w': 'в', 'x': 'кс', 'y': 'й', 'z': 'з'
}
