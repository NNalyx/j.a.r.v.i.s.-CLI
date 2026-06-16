#!/usr/bin/env python3
"""
Jarvis AI Assistant CLI - compatibility re-export module.

The implementation has been split into logical packages under:
  jarvis_core, jarvis_memory, jarvis_tts, jarvis_ui, jarvis_tools, jarvis_agent.

This module keeps the public API unchanged for existing importers
(e.g. jarvis_web_desktop.py).
"""
from jarvis_core.colors import Colors
from jarvis_core.config import reload_llama_server_presets
from jarvis_core.constants import DEFAULT_TRANSCRIPTION_BACKEND_KEY, VOICE_AVAILABLE
from jarvis_core.types import ToolResult
from jarvis_memory.manager import MemoryManager
from jarvis_tts.tts import TTS
from jarvis_ui.animation import AnimationManager
from jarvis_ui.console import UI
from jarvis_tools.definitions import MULTIMODAL_TOOL_NAMES, TOOLS_DEFINITION
from jarvis_tools.tools import Tools
from jarvis_agent.agent import QwenAgent
from jarvis_agent.app import QwenAgentApp, main

__all__ = [
    "AnimationManager",
    "Colors",
    "DEFAULT_TRANSCRIPTION_BACKEND_KEY",
    "MemoryManager",
    "MULTIMODAL_TOOL_NAMES",
    "QwenAgent",
    "QwenAgentApp",
    "TTS",
    "ToolResult",
    "TOOLS_DEFINITION",
    "Tools",
    "UI",
    "VOICE_AVAILABLE",
    "main",
    "reload_llama_server_presets",
]

if __name__ == "__main__":
    main()
