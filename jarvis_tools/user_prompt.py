"""Synchronous user-prompt tool for the agent."""
from jarvis_core import state
from jarvis_core.types import ToolResult


def ask_user(question: str, timeout: float = 120.0) -> ToolResult:
    """Ask the user a question and wait for an answer.

    In web mode the UI shows a modal dialog; in CLI mode it falls back to
    ``input()``. If the user cancels or the timeout expires, returns an error.
    """
    handler = state.user_prompt_handler
    if handler is not None:
        try:
            answer = handler(question, float(timeout))
            if answer is None:
                return ToolResult(False, None, "Пользователь не ответил или отменил запрос.")
            if answer == "__cancelled__":
                return ToolResult(False, None, "Пользователь отменил запрос.")
            return ToolResult(True, {"answer": answer})
        except Exception as exc:
            return ToolResult(False, None, f"Ошибка при ожидании ответа пользователя: {exc}")

    # Fallback to console input when no web handler is registered.
    try:
        answer = input(f"{question} ")
        return ToolResult(True, {"answer": answer})
    except EOFError:
        return ToolResult(False, None, "Не удалось получить ответ пользователя (EOF).")
    except Exception as exc:
        return ToolResult(False, None, f"Ошибка ввода: {exc}")
