"""Core data types for Jarvis."""
from typing import Any, Dict, Optional


class ToolResult:
    """Результат выполнения инструмента"""

    def __init__(self, success: bool, data: Any, error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error
        }
