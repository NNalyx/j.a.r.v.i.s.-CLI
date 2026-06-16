TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web via DuckDuckGo HTML by default. Use for getting current information, news, facts. Returns up to 10 results with titles and links.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Extract text content from a URL. Use for reading web pages, articles, documentation. Extracts title and main text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL of the page to read"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_cmd",
            "description": "Execute a Windows shell command with auto-detection between PowerShell and CMD. Use for system commands, file operations, system information, opening apps and URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string",
                                "description": "Command to execute (e.g.: Get-ChildItem, Get-Process, Start-Process chrome, explorer C:\\Users\\Public)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "Execute Python code. Use for calculations, data processing, code testing, file operations, subprocess execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents. Auto-detects encoding (utf-8, cp1251, cp866). ALWAYS pass the full file path in the path field.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "REQUIRED. Full path to the file, for example C:\\Users\\<username>\\Desktop\\snake_game.py"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_text_in_file",
            "description": "Search for text or similar lines inside a single file. Best for code/text lookup by file path. ALWAYS pass the same full path you used in read_code/read_file. Returns matched lines with line numbers, score, and match type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "REQUIRED. Full path to the file."},
                    "query": {
                        "description": "Text to find. Can be a single string, a comma-separated string, or an array of strings.",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "array", "items": {"type": "string"}}
                        ]
                    },
                    "threshold": {"type": "number", "description": "Similarity threshold from 0 to 1", "default": 0.6},
                    "max_results": {"type": "integer", "description": "Maximum number of matches to return", "default": 20},
                    "case_sensitive": {"type": "boolean", "description": "Use case-sensitive matching", "default": False}
                },
                "required": ["path", "query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write full content to a file. Creates directories if needed. Use ONLY for new files or full rewrites, not for small edits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List contents of a directory. Requires an explicit path argument.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot of the screen for visual inspection, reading on-screen information, or fallback verification. Do not use as the first choice for standard desktop app control when UI Automation tools can be used.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "object",
                        "description": "Screen region: {x, y, width, height}. If not specified, captures entire screen",
                        "properties": {
                            "x": {"type": "integer", "description": "X coordinate of top-left corner"},
                            "y": {"type": "integer", "description": "Y coordinate of top-left corner"},
                            "width": {"type": "integer", "description": "Width of the region"},
                            "height": {"type": "integer", "description": "Height of the region"}
                        }
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click_text",
            "description": "OCR fallback: click on text on screen via EasyOCR + fuzzy matching. Use only when get_app_context/do_action_in_app cannot access the target control or when the task is purely visual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string",
                             "description": "Text to search for (e.g., 'close', 'OK', 'submit', 'pause')"},
                    "threshold": {"type": "number", "description": "Fuzzy match threshold (0-1), default 0.8",
                                  "default": 0.8}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text via keyboard (simulated input).",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                    "interval": {"type": "number", "description": "Interval between keystrokes in seconds",
                                 "default": 0.05}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cursor_position",
            "description": "Get current mouse cursor coordinates.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a single key on the keyboard (Enter, Tab, Escape, F1-F12, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string",
                            "description": "Key name (e.g., enter, tab, escape, win, alt, ctrl, shift)"}
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "Press a key combination (e.g., ctrl+c, win+d, alt+tab).",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "array", "items": {"type": "string"},
                             "description": "List of keys for the combination"}
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": "Launch an application by name (fuzzy search). Searches Program Files, Start Menu, Desktop, and Windows Registry. Uses fuzzy name matching.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string",
                                 "description": "Application name (e.g., chrome, notepad, word, excel)"}
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_app_context",
            "description": "PRIMARY desktop app inspection tool. Inspect the active window, build/update the cached app map, and for web-app shells derive visual routes from OCR observations and visual controls.",
            "parameters": {
                "type": "object",
                "properties": {
                    "refresh": {"type": "boolean", "description": "Force a fresh scan of the active window", "default": False},
                    "max_elements": {"type": "integer", "description": "Maximum number of UI elements to scan", "default": 300}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "do_action_in_app",
            "description": "PRIMARY desktop app action tool. Execute actions through UI Automation elements or cached app-map routes. OCR is used only as an observation source for routes, not as a direct click target.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Element label, text, or semantic target to find in the active window"},
                    "action": {"type": "string", "description": "Action to perform: click, double_click, right_click, type, focus", "default": "click"},
                    "text": {"type": "string", "description": "Text to type when action='type'"}
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_memory",
            "description": "Manage Jarvis long-term memory. Read, write, append, and clear memory. Use for storing important user information, preferences, dialogue context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Operation: read, write, append, clear",
                        "enum": ["read", "write", "append", "clear"]
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write/append (required for write and append)"
                    }
                },
                "required": ["operation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Wait for the specified number of seconds (0.1 - 300). Use for waiting for web page loading, animations, process completion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "number",
                        "description": "Seconds to wait (0.1 - 300)"
                    }
                },
                "required": ["seconds"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_code",
            "description": "Smart code reader — reads file by line range or searches for symbols (functions/classes). Saves tokens by not reading the entire file. ALWAYS pass the full path. After read_code, reuse the exact same path in edit_code and check_syntax.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "REQUIRED. Full path to the source file. Do not omit this field."},
                    "start_line": {"type": "integer", "description": "Starting line number (1-indexed)", "default": 1},
                    "end_line": {"type": "integer",
                                 "description": "Ending line number (inclusive). If omitted, reads up to 200 lines"},
                    "symbols": {"type": "array", "items": {"type": "string"},
                                "description": "List of function/class names to search for. Overrides start_line/end_line"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_code",
            "description": "Edit source code by line number. Use read_code first. path is ALWAYS required, even if the file was read in the previous step. Copy the exact same full path from read_code into edit_code. For replace/delete, preferably pass expected_old_code so the tool can verify or relocate the target block safely. Modes: 'replace', 'insert_before', 'insert_after', 'delete'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "REQUIRED. Full path to the source file. Never omit path."},
                    "line": {"type": "integer", "description": "Target line number (1-indexed)"},
                    "new_code": {"type": "string",
                                 "description": "MANDATORY for replace/insert_before/insert_after modes — the actual code content to insert or use as replacement. WITHOUT this, the edit WILL FAIL. For delete mode only, omit this field."},
                    "mode": {"type": "string",
                             "description": "Edit mode: replace (requires new_code), insert_before (requires new_code), insert_after (requires new_code), delete (no new_code)",
                             "enum": ["replace", "insert_before", "insert_after", "delete"], "default": "replace"},
                    "end_line": {"type": "integer", "description": "End line for range operations (replace/delete)"},
                    "expected_old_code": {"type": "string", "description": "Optional but strongly recommended for replace/delete. The exact current code expected at the target lines. Prevents stale line-number edits and accidental duplication."}
                },
                "required": ["path", "line", "mode"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_file",
            "description": "Show file structure — list of functions, classes, and imports without reading full code. Use FIRST to explore a file, then read_code to read specific sections. ALWAYS pass the full file path. Saves tokens.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "REQUIRED. Full path to the source file."},
                    "show_imports": {"type": "boolean", "description": "Also show import statements", "default": True}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_code",
            "description": "Search for patterns (functions, classes, keywords) in files recursively. Supports regex patterns. Skips .venv, .git, node_modules, __pycache__.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Search pattern (regex or plain string)"},
                    "path": {"type": "string",
                             "description": "Directory or file to search in (default: current directory)"},
                    "ignore_case": {"type": "boolean", "description": "Case insensitive search", "default": True},
                    "max_results": {"type": "integer", "description": "Maximum number of results", "default": 50}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_account_info",
            "description": "Get a summary of the connected Telegram user account: name, username, phone, number of dialogs, total unread messages. Returns an error if the account is not configured.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_get_chats",
            "description": "List the user's Telegram dialogs (chats, groups, channels). Returns id, title, type and unread count for each dialog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of dialogs to return", "default": 50}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_get_unread",
            "description": "Fetch unread Telegram messages across all dialogs. Returns chat id/title, message id, date, text and sender info.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Maximum number of unread messages to return", "default": 50}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_send_message",
            "description": "Send a text message to a Telegram chat. The agent SHOULD use ask_user first if the action is sensitive. Entity can be a username (@user), chat id, or invite link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Target chat: @username, numeric id, or t.me link"},
                    "text": {"type": "string", "description": "Message text to send"}
                },
                "required": ["entity", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_join_chat",
            "description": "Join a public Telegram channel or group by @username or public link. For private invite links use telegram_request_join.",
            "parameters": {
                "type": "object",
                "properties": {
                    "link_or_username": {"type": "string", "description": "Public @username or t.me link"}
                },
                "required": ["link_or_username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_request_join",
            "description": "Send a join request to a private Telegram group using an invite link (t.me/+HASH or t.me/joinchat/HASH).",
            "parameters": {
                "type": "object",
                "properties": {
                    "invite_link": {"type": "string", "description": "Private invite link"}
                },
                "required": ["invite_link"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_global_search",
            "description": "Perform a global Telegram message search across all chats. Requires the user's account to be connected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Maximum number of results", "default": 20}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_get_messages",
            "description": "Read the latest messages in a specific Telegram chat. Entity can be a username, chat id, or chat title.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Chat identifier: @username, numeric id, or title"},
                    "limit": {"type": "integer", "description": "Number of messages to fetch", "default": 50}
                },
                "required": ["entity"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the user a clarifying question and wait for an answer. Use when the agent is unsure, needs permission for an irreversible action, or needs sensitive details (e.g. before sending Telegram messages). The UI shows a modal dialog; returns the user's answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question to show the user"},
                    "timeout": {"type": "number", "description": "Timeout in seconds (default 120)", "default": 120}
                },
                "required": ["question"]
            }
        }
    }
]

MULTIMODAL_TOOL_NAMES = {"take_screenshot"}

from .desktop import (
    get_cursor_position,
    hotkey,
    launch_app,
    move_mouse,
    press_key,
    take_screenshot,
    type_text,
)
from .files import (
    check_syntax,
    edit_code,
    grep_code,
    list_directory,
    list_file,
    read_code,
    read_file,
    search_text_in_file,
    write_file,
)
from .memory_tool import manage_memory
from .ocr import click_text
from .shell import run_cmd, run_python
from .uia import do_action_in_app, get_app_context
from .telegram_account import (
    telegram_account_info,
    telegram_get_chats,
    telegram_get_messages,
    telegram_get_unread,
    telegram_global_search,
    telegram_join_chat,
    telegram_request_join,
    telegram_send_message,
)
from .user_prompt import ask_user
from .wait import wait
from .web import read_url, search_web

TOOLS_MAP = {
    "search_web": search_web,
    "read_url": read_url,
    "run_cmd": run_cmd,
    "run_python": run_python,
    "read_file": read_file,
    "search_text_in_file": search_text_in_file,
    "write_file": write_file,
    "list_directory": list_directory,
    "take_screenshot": take_screenshot,
    "click_text": click_text,
    "type_text": type_text,
    "get_cursor_position": get_cursor_position,
    "press_key": press_key,
    "hotkey": hotkey,
    "launch_app": launch_app,
    "get_app_context": get_app_context,
    "do_action_in_app": do_action_in_app,
    "manage_memory": manage_memory,
    "wait": wait,
    "read_code": read_code,
    "check_syntax": check_syntax,
    "edit_code": edit_code,
    "list_file": list_file,
    "grep_code": grep_code,
    "telegram_account_info": telegram_account_info,
    "telegram_get_chats": telegram_get_chats,
    "telegram_get_unread": telegram_get_unread,
    "telegram_send_message": telegram_send_message,
    "telegram_join_chat": telegram_join_chat,
    "telegram_request_join": telegram_request_join,
    "telegram_global_search": telegram_global_search,
    "telegram_get_messages": telegram_get_messages,
    "ask_user": ask_user,
}

