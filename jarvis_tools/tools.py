"""Public Tools API (backward-compatible static-method aliases)."""
from .definitions import TOOLS_DEFINITION, MULTIMODAL_TOOL_NAMES, TOOLS_MAP
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
from .uia import do_action_in_app, get_app_context
from .user_prompt import ask_user
from .wait import wait
from .web import read_url, search_web


class Tools:
    """Набор инструментов для агента (обратная совместимость)."""

    search_web = staticmethod(search_web)
    read_url = staticmethod(read_url)
    run_cmd = staticmethod(run_cmd)
    run_python = staticmethod(run_python)
    read_file = staticmethod(read_file)
    search_text_in_file = staticmethod(search_text_in_file)
    write_file = staticmethod(write_file)
    list_directory = staticmethod(list_directory)
    take_screenshot = staticmethod(take_screenshot)
    click_text = staticmethod(click_text)
    type_text = staticmethod(type_text)
    get_cursor_position = staticmethod(get_cursor_position)
    press_key = staticmethod(press_key)
    hotkey = staticmethod(hotkey)
    launch_app = staticmethod(launch_app)
    get_app_context = staticmethod(get_app_context)
    do_action_in_app = staticmethod(do_action_in_app)
    manage_memory = staticmethod(manage_memory)
    wait = staticmethod(wait)
    read_code = staticmethod(read_code)
    check_syntax = staticmethod(check_syntax)
    edit_code = staticmethod(edit_code)
    list_file = staticmethod(list_file)
    grep_code = staticmethod(grep_code)
    move_mouse = staticmethod(move_mouse)
    telegram_account_info = staticmethod(telegram_account_info)
    telegram_get_chats = staticmethod(telegram_get_chats)
    telegram_get_unread = staticmethod(telegram_get_unread)
    telegram_send_message = staticmethod(telegram_send_message)
    telegram_join_chat = staticmethod(telegram_join_chat)
    telegram_request_join = staticmethod(telegram_request_join)
    telegram_global_search = staticmethod(telegram_global_search)
    telegram_get_messages = staticmethod(telegram_get_messages)
    ask_user = staticmethod(ask_user)
