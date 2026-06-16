"""Memory management tool."""
from typing import Optional

from jarvis_memory.manager import MemoryManager
from jarvis_core.types import ToolResult


def manage_memory(operation: str, content: Optional[str] = None) -> ToolResult:
    """Управление долговременной памятью Jarvis

    Операции:
    - read: Прочитать память
    - write: Записать новую память (полная перезапись)
    - append: Добавить запись в память
    - clear: Очистить память
    """
    try:
        if operation == "read":
            result = MemoryManager.read()
            if result["success"]:
                return ToolResult(True, {
                    "operation": "read",
                    "content": result["content"],
                    "last_updated": result.get("last_updated", "")
                })
            else:
                return ToolResult(False, None, result.get("error", "Read error"))

        elif operation == "write":
            if not content:
                return ToolResult(False, None, "write operation requires 'content' argument")
            result = MemoryManager.write(content)
            if result["success"]:
                return ToolResult(True, {"operation": "write", "message": result["message"]})
            else:
                return ToolResult(False, None, result.get("error", "Write error"))

        elif operation == "append":
            if not content:
                return ToolResult(False, None, "append operation requires 'content' argument")
            result = MemoryManager.append(content)
            if result["success"]:
                return ToolResult(True, {"operation": "append", "message": result["message"]})
            else:
                return ToolResult(False, None, result.get("error", "Append error"))

        elif operation == "clear":
            result = MemoryManager.clear()
            if result["success"]:
                return ToolResult(True, {"operation": "clear", "message": "Memory cleared"})
            else:
                return ToolResult(False, None, result.get("error", "Clear error"))

        else:
            return ToolResult(False, None, f"Unknown operation: {operation}")

    except Exception as e:
        return ToolResult(False, None, f"Memory management error: {str(e)}")
