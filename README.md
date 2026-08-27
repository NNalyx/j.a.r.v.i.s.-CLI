# Jarvis Desktop
<img width="868" height="432" alt="image" src="https://github.com/user-attachments/assets/ee8ee82f-47b0-4d70-a633-ffc71bdfea4f" />

Локальный голосовой ассистент для **Windows и macOS** с веб-интерфейсом. Работает поверх `llama-server` и умеет читать экран, управлять окнами, запускать команды, распознавать речь и озвучивать ответы. Поддерживает Apple Silicon (M1/M1X/M2/M3) через MLX-оптимизации.

> ⚠️ **Статус: альфа.** Проект создавался как личный помощник. Перед использованием внимательно прочитайте раздел [Безопасность](#безопасность).

## Об этом проекте


Это мой **первый серьёзный проект**. Большая часть кода, архитектурных решений и документации написана с применением современных ИИ, агентов. Я учусь, собирая ассистента.

Проект открыт, чтобы делиться прогрессом, получать обратную связь и, возможно, быть полезным другим начинающим разработчикам.

## Возможности

- 💬 Чат с локальными LLM через `llama-server` (GGUF)
- 🎙️ Голосовая активация и распознавание команд (Vosk)
- 🔊 TTS-озвучка ответов
- 🖼️ Мультимодальность (vision) через mmproj-модели
- 🖥️ Инструменты: скриншоты, OCR, управление окнами, запуск команд/Python-скриптов
- ✏️ Inline-редактирование сообщений прямо в чате
- 🎨 Переработанный UI: прямоугольные сообщения, кнопки «Скопировать / Изменить», плавная прокрутка пресетов
- 🔄 Автообновление: проверка новых версий на GitHub и one-click обновление прямо из приложения
- 💾 Персистентность чатов и настроек
- ✈️ Telegram-бот (опционально)
- 👤 Управление личным Telegram-аккаунтом через Telethon: чаты, непрочитанные сообщения, отправка сообщений, вступление в группы, глобальный поиск
- ❓ Инструмент `ask_user` — агент может задать уточняющий вопрос в модальном окне UI и дождаться ответа
- 🛑 Корректное завершение llama-server при закрытии приложения (освобождает VRAM)

## Требования

- **Windows:** Windows 10/11, NVIDIA GPU с CUDA (рекомендуется, но не обязательно)
- **macOS:** macOS 12+, Intel или Apple Silicon (M1/M1X/M2/M3). На Apple Silicon доступно ускорение через MLX
- Python 3.10+
- Скомпилированный `llama-server` для вашей платформы из [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)
- Модели Vosk (для голоса):
  - [vosk-model-small-ru-0.22](https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip)
  - [vosk-model-ru-0.42](https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip) (опционально, для лучшего качества)

## Установка

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/NNalyx/j.a.r.v.i.s.-CLI.git
cd j.a.r.v.i.s.-CLI

# 2. Создайте виртуальное окружение
python -m venv .venv

# 3. Активируйте окружение
# Windows:
.venv\Scripts\activate
# macOS:
source .venv/bin/activate

# 4. Установите зависимости
pip install -r requirements.txt

# 5. Скачайте модели Vosk и распакуйте, например в папку models/
#    j.a.r.v.i.s.-CLI/
#    ├── models/
#    │   ├── vosk-model-small-ru-0.22/
#    │   └── vosk-model-ru-0.42/
#    ...
```

## Настройка

1. Поместите бинарник `llama-server` (Windows: `llama-server.exe`, macOS: `llama-server`) в удобное место, например `C:\llama-server\` или `~/llama-server/`.
2. Поместите GGUF-модели в ту же папку или укажите пути в интерфейсе.
3. При первом запуске откроется мастер настройки пресетов — укажите путь к `llama-server`, модели и опциональный `mmproj`.
4. (Опционально) Для Telegram-бота введите токен через интерфейс. Токен хранится в `jarvis_telegram_secret.json`.
5. (Опционально) Для управления личным Telegram-аккаунтом подключите аккаунт в разделе **Настройки → Telegram-аккаунт**. Учётные данные и сессия хранятся в `jarvis_telegram_account_secret.json` и не попадают в основной конфиг.
<img width="2552" height="1377" alt="image" src="https://github.com/user-attachments/assets/1dd5ef21-f6f5-47f3-93c4-2f19dfaebdb0" />

## Запуск

**Windows:**
```powershell
.venv\Scripts\activate
python jarvis_web_desktop.py
```

**macOS:**
```bash
source .venv/bin/activate
python jarvis_web_desktop.py
```

Приложение откроет окно pywebview и поднимет локальный FastAPI-сервер на `http://127.0.0.1:8765`.
<img width="1415" height="948" alt="image" src="https://github.com/user-attachments/assets/03150bff-fd75-458d-8c09-b9337f8d7caf" />

## Автообновление

Приложение умеет проверять наличие новой версии на GitHub. Если на `origin/main` есть изменения, в интерфейсе появится плашка с предложением обновиться. После подтверждения выполняется `git pull` и приложение автоматически перезапускается.

> Требование: репозиторий должен быть клонирован через `git clone`, а не скачан как ZIP-архив.

## Безопасность

- API слушает только `127.0.0.1` и требует случайный токен, генерируемый при старте. Это защищает от вызовов из других процессов/вкладок.
- Инструменты агента (`run_cmd`, `run_python`, `write_file`) дают модели **локальный RCE-эквивалент**. Используйте только моделям, которым доверяете, и не открывайте порт наружу.
- Проект рассчитан на локальный запуск одним пользователем.

## Структура

```
jarvis/
├── jarvis_web_desktop.py   # FastAPI + pywebview
├── jarvis_cli_gui.py       # compatibility re-export (старое API)
├── jarvis_core/            # константы, типы, shared state, presets
├── jarvis_memory/          # память ассистента
├── jarvis_tts/             # текст-в-речь
├── jarvis_ui/              # консольная анимация и UI
├── jarvis_tools/           # инструменты агента (shell, files, web, OCR, UI automation, Telegram, ask_user)
│   ├── telegram_account.py
│   └── user_prompt.py
├── jarvis_agent/           # ядро агента и CLI/GUI приложение
├── jarvis_voice.py         # голосовая активация (Vosk)
├── jarvis_telegram.py      # Telegram-интеграция
├── jarvis_mlx/             # MLX-оптимизации для Apple Silicon
├── config_manager.py       # пресеты и настройки
├── app.js / app.css        # фронтенд
├── index.html              # UI
└── updater.py              # вспомогательный скрипт для автообновления
```

## Лицензия

[MIT](LICENSE)
