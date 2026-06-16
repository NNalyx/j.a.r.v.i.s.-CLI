"""Console animation manager."""
import sys
import threading
import time

from jarvis_core.colors import Colors


class AnimationManager:
    """Менеджер анимации генерации.

    Анимация на ОДНОЙ строке — сразу под текстом.
    При каждом кадре перезаписывается на месте через \\r.
    При stop() строка стирается.

    Формат: [◠] ● ответ (456 ↓)
    """

    _lock = threading.Lock()
    _running = False
    _count = 0
    _mode = "generating"
    _label = "ответ"
    _frame = 0
    _max_len = 0

    @staticmethod
    def _reset_console():
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass

    @staticmethod
    def _frame_str(frame: int, mode: str, label: str, count: int) -> str:
        ring = ["◜", "◠", "◝", "◞", "◡", "◟"][frame % 6]
        pulse = ["●", "◉", "◎", "◉"][frame % 4]
        color = Colors.BRIGHT_CYAN if mode == "generating" else Colors.BRIGHT_YELLOW
        count_part = ""
        if mode == "tool" and count > 0:
            count_part = f" {Colors.DIM}({count} ↓){Colors.RESET}"

        return (
            f"{color}[{ring}]{Colors.RESET} "
            f"{color}{pulse}{Colors.RESET} "
            f"{Colors.BOLD}{label}{Colors.RESET} "
            f"{count_part}"
        )

    @classmethod
    def start(cls, mode="generating", label=None, initial_count: int = 0):
        cls._reset_console()
        with cls._lock:
            old_max = cls._max_len
            cls._running = True
            cls._count = max(0, initial_count)
            cls._mode = mode
            cls._label = label if label else (
                "ответ" if mode == "generating" else "инструмент")
            cls._frame = 0
            cls._max_len = 0
        # Если была старая строка длиннее — сначала затереть
        if old_max > 0:
            cls._erase(old_max)

    @classmethod
    def tick(cls):
        """Перезаписать строку анимации на месте (\\r)."""
        if not cls._running:
            return
        with cls._lock:
            cls._frame += 1
            s = cls._frame_str(cls._frame, cls._mode, cls._label, cls._count)
            ll = len(s)
            if ll > cls._max_len:
                cls._max_len = ll
        # Перезаписываем строку + стираем остатки старой
        cls._write(s, cls._max_len)
        # Возвращаем курсор назад — следующему print() на той же строке
        # (но это не нужно, он просто будет выше)

    @classmethod
    def update_count(cls, char_count: int = 0, increment: int = 0):
        with cls._lock:
            if increment > 0:
                cls._count += increment
            elif char_count > 0:
                cls._count = char_count

    @classmethod
    def stop(cls):
        with cls._lock:
            ml = cls._max_len
            cls._running = False
            cls._count = 0
            cls._max_len = 0
        # Стираем строку анимации
        cls._erase(ml)

    @classmethod
    def clear_line(cls):
        """Стереть теку строку анимации БЕЗ остановки (_running остаётся)."""
        with cls._lock:
            ml = cls._max_len
        cls._erase(ml)
        with cls._lock:
            cls._max_len = 0

    @classmethod
    def is_running(cls):
        return cls._running

    # ---- helpers ----
    _write_lock = threading.Lock()

    @classmethod
    def _write(cls, s: str, max_len: int):
        """Перезаписать теку строку."""
        with cls._write_lock:
            pad = ' ' * max(0, max_len - len(s))
            sys.stdout.write(f'\r{s}{pad}\r')
            sys.stdout.flush()

    @classmethod
    def _erase(cls, length: int = 120):
        """Стереть теку строку."""
        with cls._write_lock:
            sys.stdout.write('\r' + ' ' * length + '\r')
            sys.stdout.flush()

    # ---- фоновый режим ----
    _bg_thread = None
    _bg_stop = None
    _bg_frame = 0

    @classmethod
    def _bg_loop(cls, ev):
        cls._bg_frame = 0
        while not ev.is_set():
            if not cls._running:
                break
            with cls._lock:
                cls._frame = cls._bg_frame
                cls._bg_frame += 1
                s = cls._frame_str(cls._frame, cls._mode, cls._label, cls._count)
                ll = len(s)
                if ll > cls._max_len:
                    cls._max_len = ll
            cls._write(s, cls._max_len)
            time.sleep(0.12)
        with cls._lock:
            ml = cls._max_len
            cls._max_len = 0
        cls._erase(ml)

    @classmethod
    def start_bg(cls, mode="generating", label=None, initial_count: int = 0):
        with cls._lock:
            if cls._bg_thread and cls._bg_thread.is_alive():
                cls.stop_bg()
        cls.start(mode, label, initial_count=initial_count)
        cls._bg_stop = threading.Event()
        cls._bg_thread = threading.Thread(
            target=cls._bg_loop, args=(cls._bg_stop,), daemon=True)
        cls._bg_thread.start()

    @classmethod
    def stop_bg(cls):
        if cls._bg_stop:
            cls._bg_stop.set()
        if cls._bg_thread and cls._bg_thread.is_alive():
            cls._bg_thread.join(timeout=0.5)
        cls.stop()

