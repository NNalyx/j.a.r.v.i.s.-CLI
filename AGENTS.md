# Agent Notes for Jarvis Desktop

## Project Layout

- `jarvis_web_desktop.py` — FastAPI server + pywebview desktop window.
- `jarvis_cli_gui.py` — compatibility re-export module (keeps old public API).
- `jarvis_core/` — constants, feature flags, shared mutable state, colors, types, DPI, presets.
- `jarvis_memory/` — `MemoryManager`.
- `jarvis_tts/` — text preprocessing, TTS engine, `TTS` class.
- `jarvis_ui/` — `AnimationManager` and console `UI`.
- `jarvis_tools/` — agent tools split by domain: shell, files, web, desktop, OCR, UIA, definitions.
- `jarvis_agent/` — `QwenAgent` and `QwenAgentApp`.
- `jarvis_voice.py` — Vosk wake-word and command recognition.
- `jarvis_telegram.py` — optional Telegram bot integration.
- `config_manager.py` — preset/configuration persistence.
- `app.js`, `app.css`, `index.html` — frontend.

## Runtime Files (never commit)

The application creates these files at runtime. They are listed in `.gitignore`:

- `jarvis_config.json`
- `jarvis_memory.json`
- `jarvis_app_maps.json`
- `jarvis_voice_profile.json`
- `jarvis_telegram_secret.json`
- `jarvis_chats/`
- `tts_output.wav`
- `__pycache__/`

## Security Rules

- The local API is protected by a random token generated on startup (`API_TOKEN` in `jarvis_web_desktop.py`). The token is injected into `index.html` and must be sent as `X-API-Token` header (or `token` query parameter for SSE).
- Do **not** remove this protection or add endpoints that bypass it.
- Telegram bot token must be stored only in `jarvis_telegram_secret.json`, never in `jarvis_memory.json` or other shared config.
- Avoid hardcoding Windows user paths. Use `Path.home()` / `getpass.getuser()` for user-specific paths.
- Do not use `os.system` for launching processes; prefer `subprocess` with argument lists.

## Paths

- Project root: directory containing `jarvis_web_desktop.py`.
- Config path: `BASE_DIR / "jarvis_config.json"` (see `config_manager.py`).
- Suggested user models folder: `BASE_DIR / "models"`.

## Coding Style

- Keep changes minimal and focused.
- Do not introduce new heavy dependencies without discussion.
- When editing JavaScript/CSS, bump the cache-busting version query parameter in `index.html`.
- Test Python syntax with `python -m py_compile <file>` after changes.
