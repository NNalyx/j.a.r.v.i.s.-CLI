"""Wait tool."""
import time

from jarvis_core.colors import Colors
from jarvis_core.types import ToolResult


def wait(seconds: float) -> ToolResult:
    """
    Подождать указанное количество секунд.
    Полезно для ожидания загрузки страниц, анимаций и т.д.

    Args:
        seconds: Количество секунд для ожидания (0.1 - 300)
    """
    try:
        # Ограничиваем диапазон
        seconds = max(0.1, min(seconds, 300))  # от 0.1 до 300 секунд (5 мин)

        print(f"{Colors.CYAN}[WAIT] Ожидание {seconds:.1f} секунд...{Colors.RESET}")
        time.sleep(seconds)

        return ToolResult(True, {
            "waited_seconds": seconds,
            "message": f"Ожидание {seconds:.1f} сек завершено"
        })
    except Exception as e:
        return ToolResult(False, None, f"Wait error: {str(e)}")
