"""Long-term memory manager for Jarvis."""
import json
import os
from datetime import datetime
from typing import Dict

from jarvis_core.constants import MEMORY_FILE


class MemoryManager:
    """Менеджер долговременной памяти Jarvis"""

    MAX_CHARS = 5000  # Максимальный размер памяти

    @staticmethod
    def _get_default_memory() -> Dict:
        """Память по умолчанию"""
        return {
            "content": "Память пуста. Нет сохраненной информации о пользователе или сессиях.",
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    @staticmethod
    def read() -> Dict:
        """Прочитать память"""
        try:
            if os.path.exists(MEMORY_FILE):
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    memory = json.load(f)
            else:
                memory = MemoryManager._get_default_memory()
                MemoryManager.write(memory["content"])

            return {
                "success": True,
                "content": memory.get("content", ""),
                "last_updated": memory.get("last_updated", "")
            }
        except Exception as e:
            return {"success": False, "error": str(e), "content": ""}

    @staticmethod
    def write(content: str) -> Dict:
        """Записать новую память (полная перезапись)"""
        try:
            memory = {
                "content": content[:MemoryManager.MAX_CHARS],
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(memory, f, ensure_ascii=False, indent=2)
            return {"success": True, "message": "Память успешно записана"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def append(content: str) -> Dict:
        """Добавить запись в память"""
        try:
            current = MemoryManager.read()
            if not current["success"]:
                return current

            old_content = current["content"]
            if "Память пуста" in old_content:
                old_content = ""

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_entry = f"\n[{timestamp}] {content}"
            full_content = (old_content + new_entry)[-MemoryManager.MAX_CHARS:]

            return MemoryManager.write(full_content)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def clear() -> Dict:
        """Очистить память"""
        return MemoryManager.write("Память пуста.")

    @staticmethod
    def get_summary() -> str:
        """Получить краткое содержимое для промпта"""
        result = MemoryManager.read()
        if result["success"]:
            content = result["content"]
            # Если память слишком большая, берем последние 3000 символов
            if len(content) > 3000:
                content = "..." + content[-3000:]
            return content
        return "Не удалось загрузить память."

    @staticmethod
    def get_context_for_prompt() -> str:
        """
        Получить форматированный контекст памяти для добавления в системный промпт.
        Возвращает пустую строку если память пуста.
        """
        result = MemoryManager.read()
        if result["success"]:
            content = result["content"]
            # Если память пустая или содержит только стандартное сообщение
            if not content.strip() or "Память пуста" in content:
                return ""

            # Ограничиваем размер для контекста (последние 4000 символов)
            if len(content) > 4000:
                content = "..." + content[-4000:]

            return content
        return ""
