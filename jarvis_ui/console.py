"""Console UI helpers."""
import json
import os
import re
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from jarvis_core.colors import Colors
from jarvis_core.types import ToolResult


class UI:
    """Красивый консольный UI"""

    WIDTH = 85
    THINGING_COLOR = Colors.DIM
    THINKING_COLOR = Colors.DIM
    ASSISTANT_COLOR = Colors.BRIGHT_CYAN
    USER_COLOR = Colors.BRIGHT_GREEN
    ERROR_COLOR = Colors.BRIGHT_RED
    TOOL_COLOR = Colors.BRIGHT_YELLOW
    SYSTEM_COLOR = Colors.DIM

    @staticmethod
    def clear():
        """Очистить экран"""
        if os.name == "nt":
            subprocess.run("cls", shell=True)
        else:
            subprocess.run("clear", shell=True)

    @staticmethod
    def print_banner():
        """Вывести красивый баннер"""
        banner = f"""
{Colors.BRIGHT_CYAN}╔══════════════════════════════════════════════════════════════════════╗
║{Colors.BRIGHT_WHITE}  ✦ Jarvis AI Assistant ▼ {Colors.DIM}— Ваш персональный агент{Colors.BRIGHT_CYAN}                    ║
║  {Colors.DIM}Локальный AI • Поиск • Управление ПК • Файлы • Скриншоты{Colors.BRIGHT_CYAN}            ║
╚══════════════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
        print(banner)

    @staticmethod
    def print_loading_screen():
        """
        Красивый экран загрузки с надписью FRIDAY.
        Показывать сразу при запуске приложения.
        """
        # Очищаем экран
        UI.clear()

        # Оранжевый цвет (используем BRIGHT_YELLOW как ближайший к оранжевому)
        orange = Colors.BRIGHT_YELLOW

        # Большая надпись FRIDAY
        friday_art = f"""
{orange}
8 8888888888   8 888888888o.   `8.`8888.      ,8' 8 888888888o.               .8.          `8.`8888.      ,8'
8 8888         8 8888    `88.   `8.`8888.    ,8'  8 8888    `^888.           .888.          `8.`8888.    ,8'
8 8888         8 8888     `88    `8.`8888.  ,8'   8 8888        `88.        :88888.          `8.`8888.  ,8'
8 8888         8 8888     ,88     `8.`8888.,8'    8 8888         `88       . `88888.          `8.`8888.,8'
8 888888888888 8 8888.   ,88'      `8.`88888'     8 8888          88      .8. `88888.          `8.`88888'
8 8888         8 888888888P'        `8. 8888      8 8888          88     .8`8. `88888.          `8. 8888
8 8888         8 8888`8b             `8 8888      8 8888         ,88    .8' `8. `88888.          `8 8888
8 8888         8 8888 `8b.            8 8888      8 8888        ,88'   .8'   `8. `88888.          8 8888
8 8888         8 8888   `8b.          8 8888      8 8888    ,o88P'    .888888888. `88888.         8 8888
8 8888         8 8888     `88.        8 8888      8 888888888P'      .8'       `8. `88888.        8 8888

{Colors.RESET}
{orange}              {Colors.RESET}
"""
        print(friday_art)

        # Небольшая задержка для эффекта
        time.sleep(1)

    @staticmethod
    def print_separator(style="double"):
        """Разделитель"""
        if style == "double":
            print(f"{Colors.DIM}{'─' * UI.WIDTH}{Colors.RESET}")
        elif style == "single":
            print(f"{Colors.DIM}{'─' * (UI.WIDTH // 2)}{Colors.RESET}")
        elif style == "dotted":
            print(f"{Colors.DIM}{'·' * UI.WIDTH}{Colors.RESET}")

    @staticmethod
    def print_tool_call(tool_name: str, args: Dict, iteration: int) -> threading.Event:
        """
        Вывод вызова инструмента.

        Возвращает threading.Event() для обратной совместимости,
        но реально анимация управляется через AnimationManager.
        """
        print(f"\n{UI.TOOL_COLOR}╭─{'─' * 40}╮{Colors.RESET}")
        print(
            f"{UI.TOOL_COLOR}│{Colors.BOLD} 🔧 Инструмент #{iteration}: {tool_name}{Colors.RESET}{UI.TOOL_COLOR}{' ' * (40 - 17 - len(tool_name))}│{Colors.RESET}")
        print(f"{UI.TOOL_COLOR}╰─{'─' * 40}╯{Colors.RESET}")

        # Аргументы
        if args:
            args_str = json.dumps(args, ensure_ascii=False, indent=2)
            for line in args_str.split('\n'):
                print(
                    f"{UI.TOOL_COLOR}│{Colors.DIM}  {UI.ljust_ansi(line, UI.WIDTH - 6)}{Colors.RESET}{UI.TOOL_COLOR}│{Colors.RESET}")
        else:
            print(
                f"{UI.TOOL_COLOR}│{Colors.DIM}  (без аргументов){' ' * (UI.WIDTH - 22)}{Colors.RESET}{UI.TOOL_COLOR}│{Colors.RESET}")

        print(f"{UI.TOOL_COLOR}╰{'─' * (UI.WIDTH - 2)}╯{Colors.RESET}")

        # Возвращаем dummy event для обратной совместимости
        return threading.Event()

    @staticmethod
    def print_tool_result(tool_name: str, result: ToolResult, iteration: int, stop_event: threading.Event = None):
        """
        Вывод результата инструмента.

        Анимация управляется через AnimationManager (уже остановлена перед вызовом),
        здесь только очистка на всякий случай и вывод в цвете.
        """
        # На случай если старая анимация ещё живёт — пробуем остановить
        if stop_event:
            stop_event.set()
            time.sleep(0.05)

            # Очищаем строку с анимацией
            sys.stdout.write("\r\033[A\033[2K\r")
            sys.stdout.flush()

        # Определяем цвет и символ в зависимости от результата
        if result.success:
            status = "✓"
            status_color = Colors.BRIGHT_GREEN
            status_text = "Успешно"
        else:
            status = "✗"
            status_color = Colors.BRIGHT_RED
            status_text = "Ошибка"

        print(f"\n{status_color}╭─{'─' * 40}╮{Colors.RESET}")
        print(
            f"{status_color}│{Colors.BOLD} {status} {status_text} #{iteration}: {tool_name}{Colors.RESET}{status_color}{' ' * (40 - 19 - len(status_text))}│{Colors.RESET}")
        print(f"{status_color}╰─{'─' * 40}╯{Colors.RESET}")

        if result.success:
            # Специальная обработка для edit_code — показываем красивый diff
            if tool_name == "edit_code" and isinstance(result.data, dict):
                preview = result.data.get("preview", "")
                print(f"\n{status_color}╭─{'─' * 40}╮{Colors.RESET}")
                print(
                    f"{status_color}│{Colors.BOLD} 📝 Изменения{Colors.RESET}{status_color}{' ' * (40 - 11)}│{Colors.RESET}")
                print(f"{status_color}╰─{'─' * 40}╯{Colors.RESET}")

                for line in preview.split('\n'):
                    stripped = line.strip()
                    # Подсвечиваем строки с --- и +++
                    if stripped.startswith("--- Было"):
                        print(
                            f"{status_color}│{Colors.RED}  {UI.ljust_ansi('--- Было: ---', UI.WIDTH - 6)}{Colors.RESET}")
                    elif stripped.startswith("--- Стало:"):
                        print(
                            f"{status_color}│{Colors.BRIGHT_GREEN}  {UI.ljust_ansi('+++ Стало: +++', UI.WIDTH - 6)}{Colors.RESET}")
                    elif stripped.startswith('-') and not stripped.startswith('---'):
                        # Удалённая строка
                        print(
                            f"{status_color}│{Colors.RED}  - {UI.ljust_ansi(stripped[1:].strip(), UI.WIDTH - 10)}{Colors.RESET}")
                    elif stripped.startswith('+') and not stripped.startswith('+++'):
                        # Добавленная строка (зелёный)
                        print(
                            f"{status_color}│{Colors.BRIGHT_GREEN}  + {UI.ljust_ansi(stripped[1:].strip(), UI.WIDTH - 10)}{Colors.RESET}")
                    else:
                        wrapped = UI.wrap_text(line, UI.WIDTH - 6)
                        for wrapped_line in wrapped:
                            print(
                                f"{status_color}│{Colors.DIM}  {UI.ljust_ansi(wrapped_line, UI.WIDTH - 6)}{Colors.RESET}")

                # Метаданные
                meta = f"Файл: {result.data.get('path')} | Строка {result.data.get('line')}-{result.data.get('end_line')} | Режим: {result.data.get('mode')}"
                print(
                    f"{status_color}│{Colors.DIM}  {UI.ljust_ansi(meta, UI.WIDTH - 6)}{Colors.RESET}{status_color}│{Colors.RESET}")
            else:
                # Форматируем результат
                if isinstance(result.data, dict):
                    data_str = json.dumps(result.data, ensure_ascii=False, indent=2)
                else:
                    data_str = str(result.data)[:500]  # Ограничение

                for line in data_str.split('\n'):
                    wrapped = UI.wrap_text(line, UI.WIDTH - 6)
                    for wrapped_line in wrapped:
                        print(
                            f"{status_color}│{Colors.DIM}  {UI.ljust_ansi(wrapped_line, UI.WIDTH - 6)}{Colors.RESET}{status_color}│{Colors.RESET}")
        else:
            error_lines = UI.wrap_text(f"Ошибка: {result.error}", UI.WIDTH - 6)
            for line in error_lines:
                print(
                    f"{status_color}│{Colors.DIM}  {UI.ljust_ansi(line, UI.WIDTH - 6)}{Colors.RESET}{status_color}│{Colors.RESET}")

        print(f"{status_color}╰{'─' * (UI.WIDTH - 2)}╯{Colors.RESET}")

    @staticmethod
    def print_thinking_block(content: str, block_num: int = 1):
        """Вывод блока мышления"""
        lines = content.split('\n')

        print(f"\n{UI.THINGING_COLOR}╭─{'─' * 40}╮{Colors.RESET}")
        print(
            f"{UI.THINGING_COLOR}│{Colors.BOLD} 🧠 МЫСЛЬ #{block_num}{Colors.RESET}{UI.THINGING_COLOR}{' ' * (40 - 11)}│{Colors.RESET}")
        print(f"{UI.THINGING_COLOR}╰─{'─' * 40}╯{Colors.RESET}")

        for line in lines:
            wrapped = UI.wrap_text(line, UI.WIDTH - 4)
            for wrapped_line in wrapped:
                print(
                    f"{UI.THINGING_COLOR}│{Colors.DIM} {UI.ljust_ansi(wrapped_line, UI.WIDTH - 4)} {Colors.RESET}{UI.THINGING_COLOR}│{Colors.RESET}")

        print(f"{UI.THINGING_COLOR}╰{'─' * (UI.WIDTH - 2)}╯{Colors.RESET}")

    @staticmethod
    def print_streaming_thinking(char: str, buffer: str, is_complete: bool = False):
        """Потоковый вывод мышления с выделением пунктов"""
        sys.stdout.write(f"{UI.THINGING_COLOR}{Colors.DIM}{char}{Colors.RESET}")
        sys.stdout.flush()

    @staticmethod
    def print_streaming_thinking_block(content: str):
        """Красивый вывод мышления в рамочке с потоковой генерацией"""
        lines = content.split('\n')

        print(f"\n{UI.THINKING_COLOR}╭─{'─' * 40}╮{Colors.RESET}")
        print(
            f"{UI.THINKING_COLOR}│{Colors.BOLD} 🧠 МЫШЛЕНИЕ{Colors.RESET}{UI.THINKING_COLOR}{' ' * (40 - 11)}│{Colors.RESET}")
        print(f"{UI.THINKING_COLOR}╰─{'─' * 40}╯{Colors.RESET}")

        for line in lines:
            # Форматируем markdown (жирный текст и т.д.)
            formatted = UI.format_markdown_text(line)
            wrapped = UI.wrap_text(formatted, UI.WIDTH - 6)
            for wrapped_line in wrapped:
                if wrapped_line.strip():
                    print(
                        f"{UI.THINKING_COLOR}│{Colors.DIM}  {UI.ljust_ansi(wrapped_line, UI.WIDTH - 6)}{Colors.RESET}")
                else:
                    print(
                        f"{UI.THINKING_COLOR}│{Colors.DIM}{' ' * (UI.WIDTH - 4)}{Colors.RESET}")

    @staticmethod
    def print_thinking_step(step_icon: str, step_text: str):
        """Вывод шага мышления"""
        print(f"{UI.THINGING_COLOR}{Colors.DIM}  {step_icon} {step_text}{Colors.RESET}")

    @staticmethod
    def parse_thinking_steps(content: str) -> List[Dict[str, str]]:
        """Распарсить пункты мышления из текста"""
        steps = []

        # Паттерн: 1.  **Заголовок:** или 1.  **Заголовок**
        pattern = r'^(\d+)\.\s+\*\*([^*]+)\*\*'

        lines = content.split('\n')
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            match = re.search(pattern, line_stripped)
            if match:
                num = match.group(1)
                title = match.group(2).strip().rstrip(':')

                # Берём текст после заголовка (остаток строки + следующие строки до следующего пункта)
                title_end = match.end()
                rest_of_line = line_stripped[title_end:].strip().lstrip(':').strip()

                # Собираем текст из следующих строк
                text_lines = [rest_of_line] if rest_of_line else []
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    # Если следующая строка пустая или начинается с нового пункта — стоп
                    if not next_line or re.match(r'^\d+\.\s+\*\*', next_line):
                        break
                    # Пропускаем строки с маркерами списка
                    if next_line.startswith('*') or next_line.startswith('-') or next_line.startswith('Wait'):
                        continue
                    text_lines.append(next_line)

                text = ' '.join(text_lines)[:200]
                steps.append({
                    "number": num,
                    "title": title,
                    "text": text
                })

        return steps

    @staticmethod
    def print_assistant_message(content: str, streaming: bool = False):
        """Вывод сообщения ассистента"""
        if streaming:
            sys.stdout.write(f"{UI.ASSISTANT_COLOR}│{Colors.RESET} ")
            sys.stdout.write(f"{Colors.WHITE}{content}{Colors.RESET}")
            sys.stdout.flush()
        else:
            lines = UI.wrap_and_format_text(content, UI.WIDTH - 4)
            print(f"\n{UI.ASSISTANT_COLOR}╭─{'─' * 40}╮{Colors.RESET}")
            print(
                f"{UI.ASSISTANT_COLOR}│{Colors.BOLD} ▼ Jarvis{Colors.RESET}{UI.ASSISTANT_COLOR}{' ' * (40 - 12)}│{Colors.RESET}")
            print(f"{UI.ASSISTANT_COLOR}╰─{'─' * 40}╯{Colors.RESET}")

            for wrapped_line in lines:
                # Не применяем DIM ко всей строке, чтобы сохранить форматирование
                print(
                    f"{UI.ASSISTANT_COLOR}│{Colors.RESET} {UI.ljust_ansi(wrapped_line, UI.WIDTH - 4)} {UI.ASSISTANT_COLOR}│{Colors.RESET}")

            print(f"{UI.ASSISTANT_COLOR}╰{'─' * (UI.WIDTH - 2)}╯{Colors.RESET}")

    @staticmethod
    def print_assistant_response(content: str, title: str = "Ответ"):
        """
        Вывод ответа ассистента с динамической шириной рамки.
        Только заголовок сверху и нижняя граница.
        """
        # Шаг 1: Разбиваем на абзацы
        paragraphs = content.split('\n\n')

        # Шаг 2: Обрабатываем каждый абзац — перенос строк БЕЗ форматирования
        all_lines = []
        for para in paragraphs:
            # Заменяем маркеры списков на временный символ (без цветов)
            para = re.sub(r'^(\s*)[-*]\s+', r'\1• ', para, flags=re.MULTILINE)
            para = re.sub(r'^(\s*)\d+\.\s+', r'\1• ', para, flags=re.MULTILINE)

            # Разбиваем на строки и делаем перенос
            para_lines = para.split('\n')
            for line in para_lines:
                if not line.strip():
                    all_lines.append('')
                elif len(line) <= 90:  # Максимальная ширина контента
                    all_lines.append(line)
                else:
                    # Переносим длинную строку
                    wrapped = UI.wrap_text(line, 90)
                    all_lines.extend(wrapped)

        # Шаг 3: Находим максимальную длину (без ANSI-кодов, их ещё нет)
        max_line_len = max((len(line) for line in all_lines), default=0)

        # Ограничиваем мин/макс ширину
        min_width = 50
        max_width = 100
        frame_width = max(min_width, min(max_width, max_line_len + 2))

        # Заголовок
        header_text = f"▼ {title}"
        header_width = max(frame_width, len(header_text) + 4)

        # Шаг 4: Рисуем верхнюю рамку с заголовком
        print(f"\n{UI.ASSISTANT_COLOR}╭─{'─' * (header_width - 2)}╮{Colors.RESET}")
        print(
            f"{UI.ASSISTANT_COLOR}│{Colors.BOLD} {header_text}{Colors.RESET}{UI.ASSISTANT_COLOR}{' ' * (header_width - len(header_text) - 2)}│{Colors.RESET}")
        print(f"{UI.ASSISTANT_COLOR}╰─{'─' * (header_width - 2)}╯{Colors.RESET}")

        # Шаг 5: Выводим строки с форматированием (левая рамка есть, правой нет)
        for line in all_lines:
            # Форматируем (добавляем цвета маркерам)
            formatted = UI.format_markdown_text(line)
            print(f"{UI.ASSISTANT_COLOR}│{Colors.RESET} {formatted}{Colors.RESET}")

        # Шаг 6: Нижняя граница
        print(f"{UI.ASSISTANT_COLOR}╰{'─' * (header_width - 2)}╯{Colors.RESET}")

    @staticmethod
    def start_streaming_response(title: str = "Ответ") -> Dict[str, Any]:
        """Начать потоковый вывод ответа ассистента без ломания markdown на полутокенах."""
        frame_width = 92
        header_text = f"▼ {title}"

        print(f"\n{UI.ASSISTANT_COLOR}╭─{'─' * (frame_width - 2)}╮{Colors.RESET}")
        print(
            f"{UI.ASSISTANT_COLOR}│{Colors.BOLD} {header_text}{Colors.RESET}"
            f"{UI.ASSISTANT_COLOR}{' ' * (frame_width - len(header_text) - 2)}│{Colors.RESET}"
        )
        print(f"{UI.ASSISTANT_COLOR}╰─{'─' * (frame_width - 2)}╯{Colors.RESET}")

        return {
            "buffer": "",
            "full_text": "",
            "content_width": frame_width - 4,
            "frame_width": frame_width,
            # Состояние для буферизации таблиц
            "table_buffer": [],  # Буфер строк таблицы
            "in_table": False,  # Флаг: внутри таблицы
            "lines_count": 0  # Счётчик выведенных строк (для очистки)
        }

    @staticmethod
    def start_streaming_thinking() -> Dict[str, Any]:
        """Начать потоковый вывод мышления."""
        frame_width = 92

        print(f"\n{UI.THINKING_COLOR}╭─{'─' * (frame_width - 2)}╮{Colors.RESET}")
        print(
            f"{UI.THINKING_COLOR}│{Colors.BOLD} 🧠 МЫШЛЕНИЕ{Colors.RESET}"
            f"{UI.THINKING_COLOR}{' ' * (frame_width - 13)}│{Colors.RESET}"
        )
        print(f"{UI.THINKING_COLOR}╰─{'─' * (frame_width - 2)}╯{Colors.RESET}")

        return {
            "buffer": "",
            "full_text": "",
            "content_width": frame_width - 4,
            "frame_width": frame_width
        }

    @staticmethod
    def _print_streaming_thinking_line(line: str, content_width: int):
        """Вывести одну или несколько строк потокового мышления с markdown-форматированием."""
        if line == "":
            print(f"{UI.THINKING_COLOR}│{Colors.RESET}")
            return

        # Форматируем markdown (жирный, код, маркеры списков)
        formatted = UI.format_markdown_text(line)

        wrapped_lines = UI.wrap_text(formatted, content_width)
        for wrapped_line in wrapped_lines:
            print(f"{UI.THINKING_COLOR}│{Colors.DIM}  {wrapped_line}{Colors.RESET}")

    @staticmethod
    def _is_table_row(line: str) -> bool:
        """Проверить, является ли строка частью markdown таблицы"""
        stripped = line.strip()
        if not stripped:
            return False
        # Строка таблицы: | ячейка | ячейка | или |---|---|
        if not (stripped.startswith('|') and stripped.endswith('|')):
            return False
        # Проверяем что есть хотя бы один | внутри
        return stripped.count('|') >= 3

    @staticmethod
    def _flush_table_buffer(state: Dict[str, Any]):
        """Вывести отформатированную таблицу из буфера"""
        table_rows = state.get("table_buffer", [])
        if not table_rows:
            return

        # Форматируем и выводим таблицу
        if len(table_rows) >= 2:
            # Парсим ячейки
            parsed_rows = []
            for row in table_rows:
                cells = [cell.strip() for cell in row.strip()[1:-1].split('|')]
                parsed_rows.append(cells)

            # Пропускаем разделитель (вторую строку)
            header_cells = parsed_rows[0] if len(parsed_rows) > 0 else []
            content_rows = []
            for i, cells in enumerate(parsed_rows):
                if i == 0:
                    continue  # Шапка
                elif i == 1:
                    # Проверяем что это разделитель
                    if all(c.replace('-', '').strip() == '' for c in cells):
                        continue
                    else:
                        content_rows.append(cells)
                else:
                    content_rows.append(cells)

            if header_cells and content_rows:
                # Вычисляем ширину колонок
                num_cols = len(header_cells)
                col_widths = []
                for col_idx in range(num_cols):
                    max_width = len(header_cells[col_idx])
                    for cells in content_rows:
                        if col_idx < len(cells):
                            max_width = max(max_width, len(cells[col_idx]))
                    col_widths.append(min(max_width, 35))  # Ограничиваем ширину

                # Выводим шапку
                header_line = f"{Colors.BRIGHT_CYAN}"
                for col_idx, cell in enumerate(header_cells):
                    if col_idx < len(col_widths):
                        width = col_widths[col_idx]
                        header_line += f"│ {UI.ljust_ansi(cell, width)} "
                header_line += f"│{Colors.RESET}"
                print(f"{UI.ASSISTANT_COLOR}│{Colors.RESET} {header_line}")

                # Выводим разделитель
                sep_line = f"{Colors.DIM}"
                for col_idx in range(num_cols):
                    width = col_widths[col_idx]
                    sep_line += "├" + "─" * (width + 2)
                sep_line += f"┤{Colors.RESET}"
                print(f"{UI.ASSISTANT_COLOR}│{Colors.RESET} {sep_line}")

                # Выводим данные
                for cells in content_rows:
                    data_line = f"{Colors.WHITE}"
                    for col_idx in range(num_cols):
                        if col_idx < len(col_widths):
                            width = col_widths[col_idx]
                            cell = cells[col_idx] if col_idx < len(cells) else ""
                            data_line += f"│ {UI.ljust_ansi(cell, width)} "
                    data_line += f"│{Colors.RESET}"
                    print(f"{UI.ASSISTANT_COLOR}│{Colors.RESET} {data_line}")

        # Очищаем буфер
        state["table_buffer"] = []
        state["in_table"] = False

    @staticmethod
    def _print_streaming_response_line(line: str, content_width: int):
        """Вывести одну или несколько строк потокового ответа с markdown-форматированием."""
        if line == "":
            print(f"{UI.ASSISTANT_COLOR}│{Colors.RESET}")
            return

        # Форматируем markdown (жирный, код, маркеры списков)
        formatted = UI.format_markdown_text(line)

        wrapped_lines = UI.wrap_text(formatted, content_width)
        for wrapped_line in wrapped_lines:
            print(f"{UI.ASSISTANT_COLOR}│{Colors.RESET} {wrapped_line}{Colors.RESET}")

    @staticmethod
    def update_streaming_response(state: Dict[str, Any], chunk: str):
        """Обновить потоковый вывод ответа очередным куском текста."""
        if not chunk:
            return

        chunk = chunk.replace('\r', '')
        state["full_text"] += chunk
        state["buffer"] += chunk
        printed_any = False

        while '\n' in state["buffer"]:
            line, state["buffer"] = state["buffer"].split('\n', 1)

            # Проверяем является ли строка частью таблицы
            is_table = UI._is_table_row(line)

            if is_table:
                # Начинаем или продолжаем буферизацию таблицы
                if not state["in_table"]:
                    state["in_table"] = True
                    state["table_buffer"] = []
                state["table_buffer"].append(line)
            else:
                # Не таблица
                if state["in_table"]:
                    # Таблица закончилась — выводим её
                    if AnimationManager.is_running():
                        AnimationManager.clear_line()
                    UI._flush_table_buffer(state)
                    printed_any = True
                # Выводим обычную строку
                if AnimationManager.is_running():
                    AnimationManager.clear_line()
                UI._print_streaming_response_line(line, state["content_width"])
                state["lines_count"] += 1
                printed_any = True

        # Проверяем буфер на переполнение
        if UI.ansi_len(state["buffer"]) > state["content_width"] * 4:
            # Если внутри таблицы и буфер переполнен — принудительно выводим
            if state["in_table"]:
                if AnimationManager.is_running():
                    AnimationManager.clear_line()
                UI._flush_table_buffer(state)
                printed_any = True
            else:
                wrapped_lines = UI.wrap_text(state["buffer"], state["content_width"])
                for wrapped_line in wrapped_lines[:-1]:
                    if AnimationManager.is_running():
                        AnimationManager.clear_line()
                    UI._print_streaming_response_line(wrapped_line, state["content_width"])
                    state["lines_count"] += 1
                    printed_any = True
                state["buffer"] = wrapped_lines[-1] if wrapped_lines else ""

        if AnimationManager.is_running() and (printed_any or state["buffer"]):
            AnimationManager.tick()

    @staticmethod
    def update_streaming_thinking(state: Dict[str, Any], chunk: str):
        """Обновить потоковый вывод мышления очередным куском текста."""
        if not chunk:
            return

        chunk = chunk.replace('\r', '')
        state["full_text"] += chunk
        state["buffer"] += chunk
        printed_any = False

        while '\n' in state["buffer"]:
            line, state["buffer"] = state["buffer"].split('\n', 1)
            if AnimationManager.is_running():
                AnimationManager.clear_line()
            UI._print_streaming_thinking_line(line, state["content_width"])
            printed_any = True

        if UI.ansi_len(state["buffer"]) > state["content_width"] * 2:
            wrapped_lines = UI.wrap_text(state["buffer"], state["content_width"])
            for wrapped_line in wrapped_lines[:-1]:
                if AnimationManager.is_running():
                    AnimationManager.clear_line()
                UI._print_streaming_thinking_line(wrapped_line, state["content_width"])
                printed_any = True
            state["buffer"] = wrapped_lines[-1] if wrapped_lines else ""

        if AnimationManager.is_running() and (printed_any or state["buffer"]):
            AnimationManager.tick()

    @staticmethod
    def finish_streaming_response(state: Optional[Dict[str, Any]]) -> str:
        """Завершить потоковый вывод и вернуть накопленный текст."""
        if not state:
            return ""

        # Если осталась таблица в буфере — выводим её
        if state["in_table"] and state["table_buffer"]:
            if AnimationManager.is_running():
                AnimationManager.clear_line()
            UI._flush_table_buffer(state)

        # Выводим остаток буфера
        if state["buffer"]:
            if AnimationManager.is_running():
                AnimationManager.clear_line()
            UI._print_streaming_response_line(state["buffer"], state["content_width"])
            state["buffer"] = ""

        if AnimationManager.is_running():
            AnimationManager.clear_line()
        print(f"{UI.ASSISTANT_COLOR}╰{'─' * (state['frame_width'] - 2)}╯{Colors.RESET}")
        return state["full_text"]

    @staticmethod
    def finish_streaming_thinking(state: Optional[Dict[str, Any]]) -> str:
        """Завершить потоковый вывод мышления."""
        if not state:
            return ""

        if state["buffer"]:
            if AnimationManager.is_running():
                AnimationManager.clear_line()
            UI._print_streaming_thinking_line(state["buffer"], state["content_width"])
            state["buffer"] = ""

        if AnimationManager.is_running():
            AnimationManager.clear_line()
        return state["full_text"]

    @staticmethod
    def print_user_message(content: str, prefix: str = None):
        """Вывод сообщения пользователя"""
        lines = content.split('\n')

        # Определяем заголовок
        header = prefix if prefix else "Вы"
        header_padding = 40 - 2 - len(header) - 4  # 4 = длина " 👤 "

        print(f"\n{UI.USER_COLOR}╭─{'─' * 40}╮{Colors.RESET}")
        print(
            f"{UI.USER_COLOR}│{Colors.BOLD} 👤 {header}{Colors.RESET}{UI.USER_COLOR}{' ' * header_padding}│{Colors.RESET}")
        print(f"{UI.USER_COLOR}╰─{'─' * 40}╯{Colors.RESET}")

        for line in lines:
            wrapped = UI.wrap_text(line, UI.WIDTH - 4)
            for wrapped_line in wrapped:
                print(
                    f"{UI.USER_COLOR}│{Colors.RESET} {UI.ljust_ansi(wrapped_line, UI.WIDTH - 4)} {UI.USER_COLOR}│{Colors.RESET}")

        print(f"{UI.USER_COLOR}╰{'─' * (UI.WIDTH - 2)}╯{Colors.RESET}")

    @staticmethod
    def print_error(message: str):
        """Вывод ошибки"""
        print(f"\n{UI.ERROR_COLOR}╭─{'─' * 40}╮{Colors.RESET}")
        print(f"{UI.ERROR_COLOR}│{Colors.BOLD} ⚠ Ошибка{Colors.RESET}{UI.ERROR_COLOR}{' ' * (40 - 12)}│{Colors.RESET}")
        print(f"{UI.ERROR_COLOR}╰─{'─' * 40}╯{Colors.RESET}")
        wrapped = UI.wrap_text(message, UI.WIDTH - 4)
        for line in wrapped:
            print(
                f"{UI.ERROR_COLOR}│{Colors.RESET} {UI.ljust_ansi(line, UI.WIDTH - 4)} {UI.ERROR_COLOR}│{Colors.RESET}")
        print(f"{UI.ERROR_COLOR}╰{'─' * (UI.WIDTH - 2)}╯{Colors.RESET}")

    @staticmethod
    def print_status(message: str, status: str = "info"):
        """Статусное сообщение"""
        icons = {
            "info": "ℹ",
            "success": "✓",
            "warning": "⚠",
            "error": "✗",
            "loading": "⟳",
            "tool": "🔧"
        }
        colors = {
            "info": Colors.BRIGHT_BLUE,
            "success": Colors.BRIGHT_GREEN,
            "warning": Colors.BRIGHT_YELLOW,
            "error": Colors.BRIGHT_RED,
            "loading": Colors.BRIGHT_CYAN,
            "tool": Colors.BRIGHT_YELLOW
        }

        color = colors.get(status, Colors.WHITE)
        icon = icons.get(status, "•")

        print(f"\n{color}{icon} {message}{Colors.RESET}")

    @staticmethod
    def print_agent_status(iteration: int, max_iterations: int = 45):
        """Статус агента (итерация)"""
        bar_len = 20
        if max_iterations <= 0:
            phase = iteration % bar_len
            bar = "░" * phase + "█" + "░" * (bar_len - phase - 1)
            print(f"\n{Colors.BRIGHT_MAGENTA}⟳ Агент: [{bar}] {iteration}/∞{Colors.RESET}")
            return

        filled = int((iteration / max_iterations) * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\n{Colors.BRIGHT_MAGENTA}⟳ Агент: [{bar}] {iteration}/{max_iterations}{Colors.RESET}")

    @staticmethod
    def print_input_prompt() -> str:
        """Вывести приглашение ко вводу и вернуть текст"""
        try:
            text = input(f"\n{Colors.BRIGHT_GREEN}❯{Colors.RESET} ")
        except (EOFError, KeyboardInterrupt):
            print()
            return ""

        # Очищаем строку ввода после получения текста
        if text:
            # Поднимаем курсор на 1 строку вверх и очищаем
            print(f"\033[A\033[2K", end="")

        return text.strip()

    @staticmethod
    def strip_ansi(text: str) -> str:
        """Удалить ANSI-коды из строки (для подсчёта видимой длины)"""
        ansi_pattern = r'\x1b\[[0-9;]*[a-zA-Z]'
        return re.sub(ansi_pattern, '', text)

    @staticmethod
    def ansi_len(text: str) -> int:
        """Подсчитать видимую длину строки (без учёта ANSI-кодов)"""
        return len(UI.strip_ansi(text))

    @staticmethod
    def ljust_ansi(text: str, width: int) -> str:
        """Выровнять строку по левому краю с учётом ANSI-кодов"""
        visible_len = UI.ansi_len(text)
        padding = width - visible_len
        if padding > 0:
            return text + ' ' * padding
        return text

    @staticmethod
    def wrap_text(text: str, width: int) -> List[str]:
        """Перенос длинных строк"""
        if len(text) <= width:
            return [text]

        lines = []
        current_line = ""

        words = text.split(' ')
        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                if current_line:
                    current_line += ' ' + word
                else:
                    current_line = word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    @staticmethod
    def render_math(text: str) -> str:
        r"""
        Преобразовать LaTeX математические выражения в Unicode для консоли.
        Поддерживает:
        - $...$ и $$...$$ — inline и display math
        - \frac{a}{b} → a/b
        - \sqrt[n]{x} → √x
        - ^{...} и _{...} → superscript/subscript
        - \infty → ∞, \cdot → ·, \times → ×, \div → ÷
        - \sum, \prod, \int → Σ, Π, ∫
        - \leq, \geq → ≤, ≥
        - \neq, \approx → ≠, ≈
        """
        import re

        # Проверяем есть ли математика в тексте
        has_math = '$' in text or '\\' in text
        if not has_math:
            return text

        # Карта символов для замены
        symbol_map = {
            r'\infty': '∞',
            r'\cdot': '·',
            r'\times': '×',
            r'\div': '÷',
            r'\pm': '±',
            r'\mp': '∓',
            r'\leq': '≤',
            r'\geq': '≥',
            r'\neq': '≠',
            r'\approx': '≈',
            r'\equiv': '≡',
            r'\sim': '∼',
            r'\simeq': '≃',
            r'\cong': '≅',
            r'\subset': '⊂',
            r'\supset': '⊃',
            r'\subseteq': '⊆',
            r'\supseteq': '⊇',
            r'\in': '∈',
            r'\notin': '∉',
            r'\sum': 'Σ',
            r'\prod': 'Π',
            r'\int': '∫',
            r'\oint': '∮',
            r'\partial': '∂',
            r'\nabla': '∇',
            r'\forall': '∀',
            r'\exists': '∃',
            r'\emptyset': '∅',
            r'\varnothing': '∅',
            r'\ldots': '…',
            r'\cdots': '⋯',
            r'\vdots': '⋮',
            r'\ddots': '⋱',
            r'\alpha': 'α',
            r'\beta': 'β',
            r'\gamma': 'γ',
            r'\delta': 'δ',
            r'\epsilon': 'ε',
            r'\varepsilon': 'ε',
            r'\zeta': 'ζ',
            r'\eta': 'η',
            r'\theta': 'θ',
            r'\iota': 'ι',
            r'\kappa': 'κ',
            r'\lambda': 'λ',
            r'\mu': 'μ',
            r'\nu': 'ν',
            r'\xi': 'ξ',
            r'\pi': 'π',
            r'\rho': 'ρ',
            r'\sigma': 'σ',
            r'\tau': 'τ',
            r'\upsilon': 'υ',
            r'\phi': 'φ',
            r'\chi': 'χ',
            r'\omega': 'ω',
            r'\Delta': 'Δ',
            r'\Theta': 'Θ',
            r'\Lambda': 'Λ',
            r'\Sigma': 'Σ',
            r'\Phi': 'Φ',
            r'\Psi': 'Ψ',
            r'\Omega': 'Ω',
        }

        # Обработка \frac{a}{b} → (a/b) с поддержкой опечаток
        def replace_frac(match):
            num = match.group(1).replace('X', '/').replace('H', '}').replace('(', '{')
            den = match.group(2).replace('X', '/').replace('H', '}').replace('(', '{')
            return f'({num}/{den})'

        # Основной паттерн \frac{...}{...}
        text = re.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', replace_frac, text)
        # Поддержка frac{...}{...} без backslash
        text = re.sub(r'(?<!\\)frac\{([^}]*)\}\{([^}]*)\}', replace_frac, text)
        # Поддержка опечаток: \frac{aXb}{c} или \frac{aHb}{c}
        text = re.sub(r'\\frac\{([^}]*[XH][^}]*)\}\{([^}]*)\}', replace_frac, text)
        text = re.sub(r'\\frac\{([^}]*)\}\{([^}]*[XH][^}]*)\}', replace_frac, text)

        # Обработка \sqrt[n]{x} → ⁿ√x или \sqrt{x} → √x
        def replace_sqrt(match):
            n = match.group(1)
            x = match.group(2)
            if n:
                # Superscript для показателя корня
                super_map = {'0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
                             '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹'}
                super_n = ''.join(super_map.get(c, c) for c in n)
                return f'{super_n}√{x}'
            return f'√{x}'

        text = re.sub(r'\\sqrt(?:\{([^}]*)\})?\{([^}]*)\}', replace_sqrt, text)
        # Поддержка sqrt без backslash
        text = re.sub(r'(?<!\\)sqrt(?:\{([^}]*)\})?\{([^}]*)\}', replace_sqrt, text)

        # Superscript для степеней: ^{...} или ^x
        super_map = {
            '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
            '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
            '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
            'n': 'ⁿ', 'i': 'ⁱ', 'x': 'ˣ'
        }

        def replace_superscript(match):
            content = match.group(1)
            result = ''.join(super_map.get(c, c) for c in content)
            return result

        text = re.sub(r'\^\{([^}]+)\}', replace_superscript, text)
        text = re.sub(r'\^([a-zA-Z0-9+-=])', replace_superscript, text)

        # Subscript для индексов: _{...} или _x
        sub_map = {
            '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
            '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
            '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
            'a': 'ₐ', 'e': 'ₑ', 'h': 'ₕ', 'i': 'ᵢ', 'j': 'ⱼ',
            'k': 'ₖ', 'l': 'ₗ', 'm': 'ₘ', 'n': 'ₙ', 'o': 'ₒ',
            'p': 'ₚ', 'r': 'ᵣ', 's': 'ₛ', 't': 'ₜ', 'u': 'ᵤ',
            'v': 'ᵥ', 'x': 'ₓ'
        }

        def replace_subscript(match):
            content = match.group(1)
            result = ''.join(sub_map.get(c, c) for c in content)
            return result

        text = re.sub(r'_\{([^}]+)\}', replace_subscript, text)
        text = re.sub(r'_([a-zA-Z0-9])', replace_subscript, text)

        # Замена символов
        for latex, unicode_char in symbol_map.items():
            text = text.replace(latex, unicode_char)

        # Убираем $ и $$ маркеры
        text = text.replace('$$', '')
        text = text.replace('$', '')

        # Убираем \left и \right (просто оставляем скобки) - ДО общей замены backslash
        text = re.sub(r'\\left\s*([\(\)\[\]\{\}])', r'\1', text)
        text = re.sub(r'\\right\s*([\(\)\[\]\{\}])', r'\1', text)
        text = re.sub(r'\\left\b', '', text)
        text = re.sub(r'\\right\b', '', text)

        # Убираем backslash у тригонометрических и других функций (они остаются как есть)
        # \cos → cos, \sin → sin, \log → log, \lim → lim, \max → max, \min → min
        trig_funcs = ['cos', 'sin', 'tan', 'cot', 'sec', 'csc', 'log', 'ln', 'exp',
                      'lim', 'max', 'min', 'sup', 'inf', 'det', 'dim', 'ker', 'deg',
                      'gcd', 'hom', 'arg', 'mod', 'Pr', 'injlim', 'projlim']
        for func in trig_funcs:
            text = text.replace(f'\\{func}', func)

        # Убираем backslash перед обычными символами
        text = re.sub(r'\\([a-zA-Z])', r'\1', text)

        return text

    @staticmethod
    def render_math_inline(text: str) -> str:
        """
        Обработать inline математику $...$ и $$...$$
        Выделяет математику цветом и конвертирует LaTeX → Unicode
        """
        import re

        # Обработка display math $$...$$
        def replace_display_math(match):
            content = match.group(1)
            rendered = UI.render_math(content)
            return f'{Colors.BRIGHT_WHITE}{Colors.BOLD}{rendered}{Colors.RESET}'

        # Обработка inline math $...$
        def replace_inline_math(match):
            content = match.group(1)
            rendered = UI.render_math(content)
            return f'{Colors.BRIGHT_WHITE}{Colors.BOLD}{rendered}{Colors.RESET}'

        # Обработка \boxed{x} вне математики (просто в тексте)
        def replace_boxed(match):
            content = match.group(1)
            return f'{Colors.BRIGHT_YELLOW}{Colors.BOLD}【{content}】{Colors.RESET}'

        # Сначала обрабатываем boxed вне $...$
        text = re.sub(r'\\boxed\{([^}]*)\}', replace_boxed, text)
        text = re.sub(r'(?<!\\)boxed\{([^}]*)\}', replace_boxed, text)

        # $$...$$ (display math)
        text = re.sub(r'\$\$\s*(.*?)\s*\$\$', replace_display_math, text, flags=re.DOTALL)

        # $...$ (inline math)
        text = re.sub(r'(?<!\$)\$(?!\$)(.*?)\$', replace_inline_math, text)

        return text

    @staticmethod
    def format_markdown_text(text: str) -> str:
        """
        Форматировать markdown-подобный текст с ANSI-кодами.
        Работает с ОДНОЙ строкой (для потокового режима).

        Поддерживает:
        - $...$ и $$...$$ → математика (Unicode, цветной)
        - **жирный текст** → яркий зелёный + жирный
        - `код` → cyan
        - - пункт / * пункт / 1. пункт → • пункт
        - ## заголовок → ярко-жёлтый + жирный
        - ### заголовок → ярко-синий + подчёркивание
        - --- / -- → разделительная линия (в любом месте)
        - _курсив_ → italic (не внутри математики)
        """
        import re

        # 0. Экранируем математику во временные плейсхолдеры
        math_blocks = []

        def save_math(match):
            math_blocks.append(match.group(0))
            return f"\x00MATH{len(math_blocks) - 1}\x00"

        # Сохраняем display math $$...$$
        result = re.sub(r'\$\$\s*(.*?)\s*\$\$', save_math, text, flags=re.DOTALL)
        # Сохраняем inline math $...$
        result = re.sub(r'(?<!\$)\$(?!\$)(.*?)\$', save_math, result)

        # 1. Разделитель: --- или -- → линия (в любом месте строки)
        result = re.sub(r'---', f'{Colors.DIM}{"─" * 40}{Colors.RESET}', result)
        result = re.sub(r'(?<!─)--(?!─)', f'{Colors.DIM}{"─" * 20}{Colors.RESET}', result)

        # 2. Заголовки ##
        header2_pattern = r'^(\s*)##\s+(.+)$'

        def format_header2(match):
            indent = match.group(1)
            header_text = match.group(2)
            return f"{indent}{Colors.BRIGHT_YELLOW}{Colors.BOLD}{header_text}{Colors.RESET}"

        result = re.sub(header2_pattern, format_header2, result, flags=re.MULTILINE)

        # 3. Заголовки ###
        header3_pattern = r'^(\s*)###\s+(.+)$'

        def format_header3(match):
            indent = match.group(1)
            header_text = match.group(2)
            return f"{indent}{Colors.BRIGHT_BLUE}{Colors.BOLD}{Colors.UNDERLINE}{header_text}{Colors.RESET}"

        result = re.sub(header3_pattern, format_header3, result, flags=re.MULTILINE)

        # 4. Жирный текст: **текст** (не внутри плейсхолдеров)
        bold_pattern = r'(?<!\x00)\*\*(.+?)\*\*(?!\x00)'
        result = re.sub(bold_pattern, f'{Colors.BRIGHT_GREEN}{Colors.BOLD}\\1{Colors.RESET}', result)

        # 5. Курсив: _текст_ (не внутри математики)
        italic_pattern = r'(?<!\w|\x00)_(.+?)_(?!\w|\x00)'
        result = re.sub(italic_pattern, f'{Colors.ITALIC}\\1{Colors.RESET}', result)

        # 6. Код: `код`
        code_pattern = r'(?<!\x00)`(.+?)`(?![\x00`])'
        result = re.sub(code_pattern, f'{Colors.BRIGHT_CYAN}\\1{Colors.RESET}', result)

        # 7. Маркеры списков
        bullet_list_pattern = r'^(\s*)[-*]\s+'
        result = re.sub(bullet_list_pattern, f'\\1{Colors.BRIGHT_MAGENTA}•{Colors.RESET} ', result, flags=re.MULTILINE)
        numbered_list_pattern = r'^(\s*)\d+\.\s+'
        result = re.sub(numbered_list_pattern, f'\\1{Colors.BRIGHT_MAGENTA}•{Colors.RESET} ', result,
                        flags=re.MULTILINE)

        # 8. Восстанавливаем математику с рендерингом
        for i, math in enumerate(math_blocks):
            rendered = UI.render_math(math)
            if Colors.BRIGHT_WHITE not in rendered:
                rendered = f'{Colors.BRIGHT_WHITE}{Colors.BOLD}{rendered}{Colors.RESET}'
            result = result.replace(f"\x00MATH{i}\x00", rendered)

        return result

    @staticmethod
    def format_markdown_block(text: str) -> str:
        """
        Форматировать блок текста с поддержкой таблиц.
        Вызывать для НЕ потокового режима.

        Поддерживает всё что format_markdown_text + таблицы markdown.
        """
        result = text

        # 0. Таблицы: обрабатываем ДО остальных правил
        lines = result.split('\n')
        table_rows = []
        in_table = False
        table_start_idx = -1

        for i, line in enumerate(lines):
            if '|' in line and line.strip().startswith('|') and line.strip().endswith('|'):
                if not in_table:
                    in_table = True
                    table_start_idx = i
                table_rows.append((i, line))
            else:
                if in_table:
                    result = UI._format_table(result, table_rows, table_start_idx)
                    in_table = False
                    table_rows = []

        if in_table and table_rows:
            result = UI._format_table(result, table_rows, table_start_idx)

        # Теперь применяем обычное форматирование
        return UI.format_markdown_text(result)

    @staticmethod
    def _format_table(text: str, table_rows: List[tuple], start_idx: int) -> str:
        """
        Отформатировать таблицу в тексте.

        Args:
            text: Исходный текст
            table_rows: Список кортежей (индекс_строки, содержимое)
            start_idx: Индекс начала таблицы

        Returns:
            Текст с отформатированной таблицей
        """
        lines = text.split('\n')

        # Парсим ячейки таблицы
        parsed_rows = []
        for idx, row in table_rows:
            # Разбираем ячейки: | яч1 | яч2 | → ["яч1", "яч2"]
            cells = [cell.strip() for cell in row.strip()[1:-1].split('|')]
            parsed_rows.append((idx, cells))

        if len(parsed_rows) < 2:
            return text  # Нужна как минимум шапка и разделитель

        # Пропускаем строку-разделитель (вторую строку с ---)
        content_rows = []
        for i, (idx, cells) in enumerate(parsed_rows):
            if i == 0:  # Шапка
                header_cells = cells
            elif i == 1:  # Разделитель ---
                # Проверяем, это действительно разделитель
                if all(c.replace('-', '').strip() == '' for c in cells):
                    continue
                else:
                    content_rows.append((idx, cells))
            else:  # Данные
                content_rows.append((idx, cells))

        if not content_rows:
            return text  # Нет данных

        # Вычисляем ширину каждой колонки
        num_cols = len(header_cells)
        col_widths = []
        for col_idx in range(num_cols):
            max_width = len(header_cells[col_idx])
            for _, cells in content_rows:
                if col_idx < len(cells):
                    max_width = max(max_width, len(cells[col_idx]))
            col_widths.append(min(max_width, 40))  # Ограничиваем ширину колонки

        # Форматируем строки таблицы
        formatted_lines = []

        # Шапка таблицы
        header_line = f"{Colors.BRIGHT_CYAN}"
        for col_idx, cell in enumerate(header_cells):
            if col_idx < len(col_widths):
                width = col_widths[col_idx]
                cell_formatted = UI.ljust_ansi(cell, width)
                header_line += f"│ {cell_formatted} "
        header_line += f"│{Colors.RESET}"
        formatted_lines.append(header_line)

        # Разделитель
        separator_line = f"{Colors.DIM}"
        for col_idx in range(num_cols):
            width = col_widths[col_idx]
            separator_line += "├" + "─" * (width + 2)
        separator_line += f"┤{Colors.RESET}"
        formatted_lines.append(separator_line)

        # Данные
        for _, cells in content_rows:
            data_line = f"{Colors.WHITE}"
            for col_idx in range(num_cols):
                if col_idx < len(col_widths):
                    width = col_widths[col_idx]
                    cell = cells[col_idx] if col_idx < len(cells) else ""
                    cell_formatted = UI.ljust_ansi(cell, width)
                    data_line += f"│ {cell_formatted} "
            data_line += f"│{Colors.RESET}"
            formatted_lines.append(data_line)

        # Заменяем оригинальные строки таблицы на отформатированные
        # Начинаем с конца чтобы индексы не сдвигались
        first_idx = parsed_rows[0][0]
        last_idx = parsed_rows[-1][0]

        # Удаляем старые строки
        for i in range(last_idx, first_idx - 1, -1):
            if any(idx == i for idx, _ in table_rows):
                lines.pop(i)

        # Вставляем отформатированные
        for i, formatted_line in enumerate(formatted_lines):
            lines.insert(first_idx + i, formatted_line)

        return '\n'.join(lines)

    @staticmethod
    def wrap_and_format_text(text: str, width: int) -> List[str]:
        """
        Обернуть текст с сохранением форматирования и заменой маркеров списков.
        Сначала форматируем markdown (с таблицами), затем делаем перенос строк.
        """
        # Сначала форматируем markdown (с поддержкой таблиц)
        formatted = UI.format_markdown_block(text)

        # Разбиваем на строки
        lines = formatted.split('\n')
        result = []

        for line in lines:
            # Проверяем, начинается ли строка с маркера списка (уже заменённого на •)
            is_list_item = line.strip().startswith('•')

            # Проверяем, является ли строка частью таблицы
            # Таблица содержит │ ├ ┤ ┼ ─ и начинается с одного из этих символов
            stripped = line.strip()
            is_table_row = (
                    stripped.startswith('│') or
                    stripped.startswith('├') or
                    stripped.startswith('┤') or
                    stripped.startswith('┼') or
                    ('├' in stripped and '┤' in stripped)
            )

            # Делаем перенос длинных строк
            wrapped = UI.wrap_text(line, width)

            for i, wrapped_line in enumerate(wrapped):
                # Если это продолжение пункта списка, добавляем отступ вместо маркера
                if is_list_item and i > 0:
                    # Заменяем маркер на отступ для продолжения
                    wrapped_line = '  ' + wrapped_line.lstrip()

                # Если это строка таблицы — не добавляем выравнивание, просто добавляем отступ
                if is_table_row:
                    # Таблица уже имеет свою рамку, просто добавляем пробел слева для отступа
                    wrapped_line = ' ' + wrapped_line

                # Выравниваем по правому краю с учётом ANSI-кодов
                wrapped_line = UI.ljust_ansi(wrapped_line, width)
                result.append(wrapped_line)

        return result

    @staticmethod
    def print_help():
        """Справка по командам"""
        help_text = f"""
{Colors.BOLD}Доступные команды:{Colors.RESET}
  {Colors.BRIGHT_CYAN}/help{Colors.RESET}         — Показать эту справку
  {Colors.BRIGHT_CYAN}/clear{Colors.RESET}        — Очистить экран
  {Colors.BRIGHT_CYAN}/new{Colors.RESET}          — Новый чат (очистить историю)
  {Colors.BRIGHT_CYAN}/think{Colors.RESET}        — Вкл/выкл отображение мыслей
  {Colors.BRIGHT_CYAN}/stream{Colors.RESET}       — Вкл/выкл потоковый вывод
  {Colors.BRIGHT_CYAN}/tts{Colors.RESET}          — Вкл/выкл голосовой вывод (TTS)
  {Colors.BRIGHT_CYAN}/voice{Colors.RESET}        — Вкл/выкл голосовую активацию (wake word: "Пятница")
  {Colors.BRIGHT_CYAN}/memory{Colors.RESET}       — Показать/управлять памятью
  {Colors.BRIGHT_CYAN}/tools{Colors.RESET}        — Показать доступные инструменты
  {Colors.BRIGHT_CYAN}/maxiter <N>{Colors.RESET}  — Установить макс. итераций (0 или меньше = без лимита)
  {Colors.BRIGHT_CYAN}/exit{Colors.RESET}         — Выйти из программы
  {Colors.BRIGHT_CYAN}/paste{Colors.RESET}        — Вставить изображение из буфера
  {Colors.BRIGHT_CYAN}/tg{Colors.RESET}           — Управление Telegram ботом

{Colors.BOLD}Инструменты:{Colors.RESET}
  🔍 {Colors.BRIGHT_YELLOW}search_web{Colors.RESET}   — Поиск в интернете (DuckDuckGo HTML)
  🌐 {Colors.BRIGHT_YELLOW}read_url{Colors.RESET}     — Прочитать веб-страницу по URL
  💻 {Colors.BRIGHT_YELLOW}run_cmd{Colors.RESET}      — Выполнить команду CMD
  🐍 {Colors.BRIGHT_YELLOW}run_python{Colors.RESET}   — Выполнить Python код
  📖 {Colors.BRIGHT_YELLOW}read_file{Colors.RESET}    — Читать файл
  ✏️ {Colors.BRIGHT_YELLOW}write_file{Colors.RESET}   — Записать файл
  📁 {Colors.BRIGHT_YELLOW}list_directory{Colors.RESET} — Список файлов

{Colors.BOLD}🖥️ Управление компьютером:{Colors.RESET}
  📸 {Colors.BRIGHT_CYAN}take_screenshot{Colors.RESET} — Скриншот экрана
  ⌨️ {Colors.BRIGHT_CYAN}type_text{Colors.RESET}      — Напечатать текст
  🔘 {Colors.BRIGHT_CYAN}press_key{Colors.RESET}      — Нажать клавишу
  ⌨️ {Colors.BRIGHT_CYAN}hotkey{Colors.RESET}         — Комбинация клавиш
  🚀 {Colors.BRIGHT_CYAN}launch_app{Colors.RESET}     — Запустить приложение
  🎯 {Colors.BRIGHT_MAGENTA}get_app_context{Colors.RESET} — Контекст активного окна через UI Automation
  🖱️ {Colors.BRIGHT_MAGENTA}do_action_in_app{Colors.RESET} — Найти элемент и выполнить действие

{Colors.DIM}Отправка изображений:{Colors.RESET}
  • {Colors.BRIGHT_CYAN}/paste{Colors.RESET} → вставить изображение из буфера
  • {Colors.BRIGHT_CYAN}/image "путь"{Colors.RESET} → прикрепить изображение по пути

{Colors.BOLD}📱 Telegram бот:{Colors.RESET}
  • {Colors.BRIGHT_CYAN}/tg{Colors.RESET} — показать статус
  • {Colors.BRIGHT_CYAN}/tg connect{Colors.RESET} — подключить бота
  • {Colors.BRIGHT_CYAN}/tg reset{Colors.RESET} — отвязать бота

{Colors.DIM}Ctrl+C прерывает текущий запрос{Colors.RESET}
"""
        print(help_text)

    @staticmethod
    def print_tools_list():
        """List of tools"""
        tools_info = f"""
{Colors.BOLD}🔧 Available Tools:{Colors.RESET}

{Colors.BRIGHT_YELLOW}1. search_web(query){Colors.RESET}
   Search the web via DuckDuckGo HTML
   Example: "AI news 2026"

{Colors.BRIGHT_YELLOW}2. read_url(url){Colors.RESET}
   Extract text content from a URL
   Example: https://example.com/article

{Colors.BRIGHT_YELLOW}3. run_cmd(command){Colors.RESET}
   Execute a Windows command with auto-detection (PowerShell/CMD)
   Example: dir, type file.txt, systeminfo, Get-Process
   🚀 **Open a site:** start https://youtube.com

{Colors.BRIGHT_YELLOW}4. run_python(code){Colors.RESET}
   Execute Python code
   Example: print(2+2), import os; print(os.getcwd())

{Colors.BRIGHT_YELLOW}5. read_file(path){Colors.RESET}
   Read a file (auto-detects encoding)

{Colors.BRIGHT_YELLOW}6. write_file(path, content){Colors.RESET}
   Write content to a file

{Colors.BRIGHT_YELLOW}7. list_directory(path){Colors.RESET}
   List directory contents

{Colors.BOLD}🖥️ Computer Control (GUI via VL):{Colors.RESET}

{Colors.BRIGHT_CYAN}8. take_screenshot(region){Colors.RESET}
   Take a screenshot (full screen or region)
   Example: take_screenshot()
   {Colors.DIM}→ Model receives a screenshot scaled to 1920x1080{Colors.RESET}

{Colors.BRIGHT_CYAN}9. click_text(text, threshold){Colors.RESET}
   Click on text via OCR (EasyOCR + fuzzy matching)
   Example: click_text(text="close", threshold=0.6)
   {Colors.DIM}→ Automatically takes screenshot, recognizes text, and clicks{Colors.RESET}

{Colors.BRIGHT_CYAN}10. type_text(text, interval){Colors.RESET}
   Type text via keyboard
   Example: type_text(text="Hello, world!")

{Colors.BRIGHT_CYAN}11. get_cursor_position(){Colors.RESET}
   Get current mouse cursor coordinates

{Colors.BRIGHT_CYAN}12. press_key(key){Colors.RESET}
   Press a single key
   Example: press_key(key="enter")

{Colors.BRIGHT_CYAN}13. hotkey(keys){Colors.RESET}
   Press a key combination
   Example: hotkey(keys=["ctrl", "c"])

{Colors.BRIGHT_CYAN}14. launch_app(app_name){Colors.RESET}
   Launch an application by name
   Example: launch_app(app_name="chrome")

{Colors.BRIGHT_MAGENTA}15. get_app_context(refresh, max_elements){Colors.RESET}
   Inspect the active app window via UI Automation and update the cached app map
   Example: get_app_context()
   {Colors.DIM}→ Returns a short summary of actionable UI elements{Colors.RESET}

{Colors.BRIGHT_MAGENTA}16. do_action_in_app(target, action, text){Colors.RESET}
   Find an element in the active app and perform an action on it
   Example: do_action_in_app(target="Моя волна", action="click")
   {Colors.DIM}→ Uses UI Automation instead of screenshots when possible{Colors.RESET}

{Colors.BRIGHT_MAGENTA}17. manage_memory(operation, content){Colors.RESET}
   Manage Jarvis long-term memory
   Examples:
   - Read: manage_memory(operation="read")
   - Write: manage_memory(operation="write", content="text")
   - Append: manage_memory(operation="append", content="text")
   - Clear: manage_memory(operation="clear")
   🧠 **Save important info**: user name, preferences, context

{Colors.BRIGHT_CYAN}18. wait(seconds){Colors.RESET}
   Wait for the specified number of seconds (0.1 - 300)
   Example: wait(seconds=5)
   🕐 **Use for waiting**: page loading, animations, processes

{Colors.BOLD}💡 VL Usage Examples:{Colors.RESET}

{Colors.DIM}# Open YouTube and click pause:{Colors.RESET}
1. run_cmd(command="start https://youtube.com")
2. take_screenshot()
3. click_text(text="pause")  # model sees where the pause button is

{Colors.DIM}# Close a dialog window:{Colors.RESET}
1. take_screenshot()
2. click_text(text="close") or click_text(text="OK")

{Colors.DIM}# Analyze an interface:{Colors.RESET}
1. take_screenshot() → model analyzes the image
2. click_text(text="desired button") → click on text

{Colors.DIM}The agent automatically chooses tools automatically.{Colors.RESET}

{Colors.BOLD}🔊 Voice Output:{Colors.RESET}
  Command {Colors.BRIGHT_CYAN}/tts{Colors.RESET} toggles voice output for responses.
  First and last paragraphs of response are spoken.

{Colors.BOLD}🧠 Memory:{Colors.RESET}
  Command {Colors.BRIGHT_CYAN}/memory{Colors.RESET} shows memory contents.
  Jarvis remembers information between sessions.
"""
        print(tools_info)

    @staticmethod
    def print_loading_animation(message: str = "Jarvis генерирует ответ", stop_event: Optional[Any] = None):
        """
        Красивая пульсирующая анимация загрузки в стиле Jarvis.
        Статичная (не скачет по экрану), с плавной пульсацией.

        DEPRECATED: используется AnimationManager вместо этого.
        """
        # Символы для пульсирующего ядра
        pulse_frames = ["●", "◉", "◎", "◉"]
        # Символы для внешнего кольца
        ring_frames = ["◜", "◠", "◝", "◞", "◡", "◟"]

        i = 0

        # Включаем виртуальную обработку ANSI для Windows
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            pass

        while stop_event is None or not stop_event.is_set():
            # Пульсация ядра
            pulse_char = pulse_frames[i % len(pulse_frames)]
            # Вращение кольца
            ring_char = ring_frames[i % len(ring_frames)]

            # Формируем красивую строку в стиле Jarvis (без прогресс-бара)
            line = (
                f"{Colors.BRIGHT_CYAN}[{ring_char}]{Colors.RESET} "
                f"{Colors.BRIGHT_MAGENTA}{pulse_char}{Colors.RESET} "
                f"{Colors.BOLD}{message}{Colors.RESET}"
            )

            # Вывод с возвратом каретки (остаёмся на той же строке)
            sys.stdout.write(f"\r{line}")
            sys.stdout.flush()

            time.sleep(0.12)
            i += 1

        # Очистка строки после завершения
        clear_line = "\r" + " " * (len(message) + 10) + "\r"
        sys.stdout.write(clear_line)
        sys.stdout.flush()

    @staticmethod
    def print_thinking_animation():
        """Анимация 'думает...' (быстрая, для показа перед ответом)"""
        ring_frames = ["◜", "◠", "◝", "◞", "◡", "◟"]
        pulse_frames = ["●", "◉", "◎", "◉"]

        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            pass

        for i in range(8):
            ring_char = ring_frames[i % len(ring_frames)]
            pulse_char = pulse_frames[i % len(pulse_frames)]
            sys.stdout.write(
                f"\r{Colors.BRIGHT_CYAN}[{ring_char}]{Colors.RESET} {Colors.BRIGHT_MAGENTA}{pulse_char} Jarvis думает...{Colors.RESET}   ")
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write('\r' + ' ' * 50 + '\r')
        sys.stdout.flush()

    @staticmethod
    def print_tool_loading_animation(tool_name: str, stop_event: Optional[threading.Event] = None):
        """
        Пульсирующая анимация выполнения инструмента (жёлтый цвет).
        Показывает что инструмент выполняется.

        DEPRECATED: используется AnimationManager вместо этого.
        """
        # Символы для пульсирующего ядра
        pulse_frames = ["●", "◉", "◎", "◉"]
        # Символы для внешнего кольца
        ring_frames = ["◜", "◠", "◝", "◞", "◡", "◟"]

        i = 0
        message = f"Выполняется: {tool_name}"

        # Включаем виртуальную обработку ANSI для Windows
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            pass

        while stop_event is None or not stop_event.is_set():
            # Пульсация ядра
            pulse_char = pulse_frames[i % len(pulse_frames)]
            # Вращение кольца
            ring_char = ring_frames[i % len(ring_frames)]

            # Формируем строку в жёлтом цвете (без прогресс-бара)
            line = (
                f"{Colors.BRIGHT_YELLOW}[{ring_char}]{Colors.RESET} "
                f"{Colors.BRIGHT_YELLOW}{pulse_char}{Colors.RESET} "
                f"{Colors.BOLD}{message}{Colors.RESET}"
            )

            # Вывод с возвратом каретки (остаёмся на той же строке)
            sys.stdout.write(f"\r{line}")
            sys.stdout.flush()

            time.sleep(0.12)
            i += 1

