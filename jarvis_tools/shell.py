"""Shell and Python execution tools."""
import re
import sys
from typing import Any, Dict, List

from jarvis_core.types import ToolResult


def run_cmd(command: str) -> ToolResult:
    """Выполнить команду в PowerShell или CMD с автоопределением оболочки

    Примеры использования:
    - Открыть сайт: Start-Process "https://youtube.com"
    - Открыть сайт (CMD): start https://youtube.com
    - Открыть файл в блокноте: notepad "C:\\path\\file.txt"
    - Открыть папку: explorer "C:\\Users\\Public"
    - Запустить приложение: Start-Process chrome
    - Закрыть процесс: Stop-Process -Name notepad
    - Получить информацию: Get-Process, Get-Service, Get-ChildItem

    По умолчанию предпочитает PowerShell, но умеет автоматически
    переключаться на CMD для классических команд Windows.
    """
    try:
        import subprocess
        import os
        import shutil
        import locale

        raw_command = str(command or "").strip()
        if not raw_command:
            return ToolResult(False, None, "Empty command")

        env = os.environ.copy()
        env['PYTHONUTF8'] = '1'

        def run_in_powershell(cmd: str):
            ps_command = (
                "$OutputEncoding = [System.Text.Encoding]::UTF8; "
                "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                f"{cmd}"
            )
            powershell_exe = shutil.which("powershell") or shutil.which("pwsh") or "powershell"
            return subprocess.run(
                [powershell_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30,
                env=env
            )

        def run_in_cmd(cmd: str):
            return subprocess.run(
                ["cmd.exe", "/d", "/s", "/c", cmd],
                capture_output=True,
                timeout=30,
                env=env
            )

        def decode_cmd_output(raw_value: Any) -> str:
            if raw_value is None:
                return ""
            if isinstance(raw_value, str):
                return raw_value

            encodings: List[str] = []
            preferred = locale.getpreferredencoding(False)
            if preferred:
                encodings.append(preferred)

            if os.name == "nt":
                try:
                    import ctypes
                    oem_cp = ctypes.windll.kernel32.GetOEMCP()
                    if oem_cp:
                        encodings.append(f"cp{oem_cp}")
                except Exception:
                    pass

            encodings.extend(["utf-8", "cp866", "cp1251", "latin-1"])

            seen = set()
            for encoding_name in encodings:
                normalized = str(encoding_name or "").lower()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                try:
                    return raw_value.decode(encoding_name)
                except Exception:
                    continue

            return raw_value.decode("utf-8", errors="replace")

        def is_warning_only(stderr_text: str) -> bool:
            stripped = (stderr_text or "").strip()
            if not stripped:
                return True
            upper = stripped.upper()
            return upper.startswith("WARNING") or upper.startswith("VERBOSE")

        def looks_like_cmd_command(cmd: str) -> bool:
            lowered = cmd.strip().lower()
            if lowered.startswith(("cmd /c ", "cmd.exe /c ", "cmd /k ", "cmd.exe /k ")):
                return True
            cmd_builtins = (
                "dir", "copy", "del", "erase", "move", "ren", "rename", "mkdir", "md",
                "rmdir", "rd", "type", "cls", "start", "assoc", "ftype", "tasklist",
                "taskkill", "systeminfo", "where", "tree", "xcopy", "robocopy",
                "cd", "chdir", "pushd", "popd", "call", "set", "echo", "if"
            )
            first_token = lowered.split(None, 1)[0] if lowered else ""
            if first_token in cmd_builtins:
                return True
            return False

        def looks_like_powershell_command(cmd: str) -> bool:
            lowered = cmd.lower()
            if re.search(r"\b(get|set|new|remove|start|stop|test|invoke|select|where|for(each)?|sort|measure)-[a-z]+\b", lowered):
                return True
            ps_markers = ("$env:", "$null", "$true", "$false", "out-file", "select-object")
            return any(marker in lowered for marker in ps_markers)

        def first_token(cmd: str) -> str:
            stripped = (cmd or "").strip()
            if not stripped:
                return ""
            return stripped.split(None, 1)[0].lower()

        def is_false_positive_powershell_success(original_cmd: str, shell_name: str, stdout: str, stderr: str) -> bool:
            # `where foo` in PowerShell is parsed as the `Where-Object` alias and may
            # report success with no output, even though the user meant CMD `where`.
            if shell_name != "powershell":
                return False
            if first_token(original_cmd) != "where":
                return False
            return not stdout.strip() and not stderr.strip()

        attempts: List[Dict[str, Any]] = []

        explicit_cmd_prefix = re.match(r"^(cmd(?:\.exe)?)\s+/(c|k)\s+", raw_command, flags=re.IGNORECASE)
        if explicit_cmd_prefix:
            stripped_command = re.sub(r"^(cmd(?:\.exe)?)\s+/(c|k)\s+", "", raw_command, count=1, flags=re.IGNORECASE)
            shell_order = [("cmd", stripped_command), ("powershell", raw_command)]
        elif looks_like_cmd_command(raw_command) and not looks_like_powershell_command(raw_command):
            shell_order = [("cmd", raw_command), ("powershell", raw_command)]
        else:
            shell_order = [("powershell", raw_command), ("cmd", raw_command)]

        result = None
        shell_used = None
        last_error = None

        for shell_name, shell_command in shell_order:
            current = run_in_cmd(shell_command) if shell_name == "cmd" else run_in_powershell(shell_command)
            if shell_name == "cmd":
                stdout = decode_cmd_output(current.stdout)
                stderr = decode_cmd_output(current.stderr)
            else:
                stdout = current.stdout or ""
                stderr = current.stderr or ""
            success = current.returncode == 0 and is_warning_only(stderr)
            if success and is_false_positive_powershell_success(raw_command, shell_name, stdout, stderr):
                success = False
                if not stderr.strip():
                    stderr = "PowerShell interpreted 'where' as the Where-Object alias and returned an empty result."
            attempts.append({
                "shell": shell_name,
                "command": shell_command,
                "returncode": current.returncode,
                "stdout": stdout[:2000],
                "stderr": stderr[:500]
            })
            if success:
                result = current
                shell_used = shell_name
                break
            last_error = stderr.strip() or stdout.strip() or f"Command failed in {shell_name}"

        if result is None:
            failed_attempt = attempts[-1] if attempts else {}
            return ToolResult(
                success=False,
                data={
                    "command": raw_command,
                    "shell": failed_attempt.get("shell"),
                    "stdout": failed_attempt.get("stdout", ""),
                    "stderr": failed_attempt.get("stderr", ""),
                    "returncode": failed_attempt.get("returncode"),
                    "attempts": attempts
                },
                error=(last_error or "Command execution failed")[:500]
            )

        return ToolResult(
            success=True,
            data={
                "command": raw_command,
                "shell": shell_used,
                "stdout": (result.stdout or "")[:5000],
                "stderr": (result.stderr or "")[:1000],
                "returncode": result.returncode,
                "attempts": attempts
            },
            error=None
        )
    except subprocess.TimeoutExpired:
        return ToolResult(False, None, "Command timeout (30 sec)")
    except Exception as e:
        return ToolResult(False, None, f"Execution error: {str(e)}")

def run_python(code: str) -> ToolResult:
    """Выполнить Python код"""
    try:
        import subprocess
        import os

        # Копируем текущие переменные окружения и настраиваем для корректной работы
        env = os.environ.copy()
        # Удаляем PYTHONHASHSEED если есть (может вызывать ошибки при запуске)
        env.pop('PYTHONHASHSEED', None)
        # Принудительно устанавливаем UTF-8 для Python
        env['PYTHONUTF8'] = '1'

        # Выполняем код через python -c
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30,
            env=env  # Используем настроенное окружение
        )
        output = result.stdout
        error = result.stderr

        return ToolResult(True, {
            "code": code[:1000],  # Показываем код (ограниченно)
            "stdout": output[:5000],
            "stderr": error[:1000],
            "returncode": result.returncode
        })
    except subprocess.TimeoutExpired:
        return ToolResult(False, None, "Execution timeout (30 sec)")
    except Exception as e:
        return ToolResult(False, None, f"Execution error: {str(e)}")

