"""File-system and code-editing tools."""
import os
from typing import Any, Dict, List, Optional, Tuple

from jarvis_core.types import ToolResult

from .utils import (
    _calculate_text_similarity,
    _code_text_to_lines,
    _locate_code_block,
    _normalize_code_for_compare,
    _normalize_search_queries,
    _read_text_file_lines,
)


def read_file(path: str) -> ToolResult:
    """Прочитать файл"""
    try:
        if not os.path.exists(path):
            return ToolResult(False, None, f"File not found: {path}")

        # Пробуем разные кодировки
        encodings = ['utf-8', 'cp1251', 'cp866', 'latin-1']
        content = None

        for encoding in encodings:
            try:
                with open(path, "r", encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            # Если текст не прочитался - читаем как бинарный
            with open(path, "rb") as f:
                content = f.read()[:5000].decode('utf-8', errors='replace')

        max_chars = 5000
        truncated = len(content) > max_chars
        return ToolResult(True, {
            "path": path,
            "content": content[:max_chars],
            "total_chars": len(content),
            "returned_chars": min(len(content), max_chars),
            "truncated": truncated,
            "note": "Content is truncated; use read_code for code files or long files." if truncated else ""
        })
    except Exception as e:
        return ToolResult(False, None, f"Read error: {str(e)}")

def search_text_in_file(path: str, query: Any, threshold: float = 0.6,
                        max_results: int = 20, case_sensitive: bool = False) -> ToolResult:
    """Найти текст или похожие строки в одном файле."""
    try:
        if not path or not str(path).strip():
            return ToolResult(False, None, "Missing required argument: path")
        if not os.path.exists(path):
            return ToolResult(False, None, f"File not found: {path}")
        if os.path.isdir(path):
            return ToolResult(False, None, f"Path is a directory, expected a file: {path}")

        queries = _normalize_search_queries(query)
        if not queries:
            return ToolResult(False, None, "Missing required argument: query")

        threshold = max(0.0, min(float(threshold), 1.0))
        max_results = max(1, min(int(max_results), 100))

        lines, encoding = _read_text_file_lines(path)
        if lines is None:
            return ToolResult(False, None, "Failed to read file: encoding not recognized")

        matches = []
        for line_number, raw_line in enumerate(lines, 1):
            line_text = raw_line.rstrip("\r\n")
            if not line_text.strip():
                continue

            haystack = line_text if case_sensitive else line_text.lower()
            best_match = None

            for item in queries:
                needle = item if case_sensitive else item.lower()
                if needle in haystack:
                    score = 1.0
                    match_type = "substring"
                else:
                    score = _calculate_text_similarity(item, line_text)
                    match_type = "fuzzy"

                if score < threshold:
                    continue

                candidate = {
                    "query": item,
                    "line_number": line_number,
                    "line": line_text[:500],
                    "score": round(score, 3),
                    "match_type": match_type,
                }
                if best_match is None or candidate["score"] > best_match["score"]:
                    best_match = candidate

            if best_match is not None:
                matches.append(best_match)

        matches.sort(key=lambda item: (-item["score"], item["line_number"]))
        matches = matches[:max_results]

        if not matches:
            return ToolResult(
                False,
                None,
                f"No matches found in file '{path}' for queries: {', '.join(queries)}"
            )

        preview_lines = [
            f"{item['line_number']}: [{item['score']:.3f}] {item['line']}"
            for item in matches
        ]
        return ToolResult(True, {
            "path": path,
            "encoding": encoding,
            "queries": queries,
            "threshold": threshold,
            "count": len(matches),
            "matches": matches,
            "preview": "\n".join(preview_lines)
        })
    except Exception as e:
        return ToolResult(False, None, f"Search text error: {str(e)}")

def write_file(path: str, content: str) -> ToolResult:
    """Записать в файл"""
    try:
        dir_path = os.path.dirname(path) if os.path.dirname(path) else "."
        if dir_path and not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path, exist_ok=True)
            except PermissionError:
                _user = getpass.getuser()
                _home = Path.home()
                return ToolResult(False, None,
                                  f"Permission denied: {dir_path}. Avoid non-ASCII characters in paths. Your user is: {_user}. Use '{_home}' as base path.")
            except Exception as e:
                return ToolResult(False, None, f"Directory creation error: {str(e)}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return ToolResult(True, {"path": path, "bytes_written": len(content)})
    except PermissionError:
        _user = getpass.getuser()
        _home = Path.home()
        return ToolResult(False, None,
                          f"Permission denied: {path}. Avoid non-ASCII characters in paths. Your user is: {_user}. Use '{_home}' as base path.")
    except Exception as e:
        return ToolResult(False, None, f"Write error: {str(e)}")

def list_directory(path: Optional[str] = None) -> ToolResult:
    """Показать содержимое директории"""
    try:
        if not path or not str(path).strip():
            return ToolResult(
                False,
                None,
                "Missing required argument: path. Call list_directory with an explicit directory path."
            )
        if not os.path.exists(path):
            return ToolResult(False, None, f"Directory not found: {path}")
        items = os.listdir(path)
        result = []
        for item in sorted(items):
            full_path = os.path.join(path, item)
            is_dir = os.path.isdir(full_path)
            prefix = "📁 " if is_dir else "📄 "
            result.append(f"{prefix}{item}")
        return ToolResult(True, {"path": path, "items": result, "count": len(result)})
    except Exception as e:
        return ToolResult(False, None, f"Error: {str(e)}")

def read_code(path: str, start_line: int = 1, end_line: Optional[int] = None,
              max_lines: int = 200, symbols: Optional[List[str]] = None) -> ToolResult:
    """Умное чтение кода — читает файл построчно или только нужные символы.

    Экономит токены: не читает весь файл целиком.

    Args:
        path: Путь к файлу
        start_line: Начальная строка (1-индексация)
        end_line: Конечная строка (включительно). Если None — до max_lines
        max_lines: Максимальное количество строк для чтения (по умолчанию 200)
        symbols: Список символов для поиска (имена функций/классов). Если указан — игнорирует start_line/end_line
    """
    try:
        if not os.path.exists(path):
            return ToolResult(False, None, f"File not found: {path}")

        encodings = ['utf-8', 'cp1251', 'cp866', 'latin-1']
        lines = None
        for encoding in encodings:
            try:
                with open(path, "r", encoding=encoding) as f:
                    lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue

        if lines is None:
            return ToolResult(False, None, f"Failed to read file: encoding not recognized")

        total_lines = len(lines)

        # Режим поиска символов
        if symbols:
            found_ranges = []
            for sym in symbols:
                for i, line in enumerate(lines):
                    if sym in line and (line.strip().startswith('def ') or
                                        line.strip().startswith('class ') or
                                        line.strip().startswith('async def ')):
                        # Нашли символ — берём контекст: от текущего отступ и до 30 строк вниз или до следующего def/class
                        start = max(0, i - 2)  # 2 строки контекста сверху
                        end = min(total_lines, i + 30)  # максимум 30 строк
                        # Продлеваем до следующего определения
                        for j in range(i + 1, min(total_lines, i + 50)):
                            stripped = lines[j].strip()
                            if (stripped.startswith('def ') or stripped.startswith('class ') or
                                stripped.startswith('async def ')) and j > i + 5:
                                end = j
                                break
                        found_ranges.append((start, end))

            if not found_ranges:
                # Fallback: ищем просто по вхождению
                found_ranges = []
                for sym in symbols:
                    for i, line in enumerate(lines):
                        if sym in line:
                            start = max(0, i - 2)
                            end = min(total_lines, i + 20)
                            found_ranges.append((start, end))
                    if found_ranges:
                        break

            if not found_ranges:
                return ToolResult(False, None,
                                  f"Символы {symbols} не найдены в файле ({total_lines} строк)")

            # Объединяем пересекающиеся диапазоны
            found_ranges.sort()
            merged = [found_ranges[0]]
            for s, e in found_ranges[1:]:
                if s <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], e))
                else:
                    merged.append((s, e))

            result_lines = []
            for s, e in merged:
                result_lines.append(f"--- строки {s + 1}-{e} ---\n")
                result_lines.extend(lines[s:e])

            return ToolResult(True, {
                "path": path,
                "total_lines": total_lines,
                "symbols_found": symbols,
                "content": "".join(result_lines),
                "lines_read": sum(e - s for s, e in merged)
            })

        # Построчное чтение
        start = max(0, start_line - 1)
        end = min(total_lines, start + max_lines) if end_line is None else min(total_lines, end_line)
        actual_lines = end - start

        content = "".join(lines[start:end])

        # Показываем контекст: сколько строк в файле всего и какие прочитаны
        return ToolResult(True, {
            "path": path,
            "total_lines": total_lines,
            "lines_read": actual_lines,
            "range": f"{start + 1}-{end}",
            "content": content
        })
    except Exception as e:
        return ToolResult(False, None, f"Code read error: {str(e)}")

def check_syntax(path: str) -> ToolResult:
    """Check file syntax via compilation."""
    import ast

    try:
        if not os.path.exists(path):
            return ToolResult(False, None, f"File not found: {path}")

        # Determine language by extension
        ext = os.path.splitext(path)[1].lower()

        # === PYTHON ===
        if ext in ('.py', '.pyw'):
            encodings = ['utf-8', 'cp1251', 'cp866', 'latin-1']
            code = None
            for encoding in encodings:
                try:
                    with open(path, 'r', encoding=encoding) as f:
                        code = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if code is None:
                return ToolResult(False, None, "Failed to read file: encoding not recognized")

            try:
                ast.parse(code)
                total_lines = len(code.splitlines())
                return ToolResult(True, {
                    "language": "Python",
                    "status": "✅ SYNTAX VALID",
                    "file": path,
                    "total_lines": total_lines,
                    "message": "Code is valid and ready to run!"
                })
            except SyntaxError as e:
                lines = code.splitlines()
                error_line = lines[e.lineno - 1] if e.lineno and e.lineno <= len(lines) else "N/A"
                return ToolResult(True, {
                    "language": "Python",
                    "status": "❌ SYNTAX ERROR",
                    "file": path,
                    "line": e.lineno,
                    "column": e.offset,
                    "message": e.msg,
                    "error_line": error_line.strip() if isinstance(error_line, str) else str(error_line),
                    "hint": f"Fix line {e.lineno} and re-run check"
                }, error=f"SyntaxError line {e.lineno}: {e.msg}")

        # === JSON ===
        elif ext == '.json':
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            try:
                json.loads(content)
                return ToolResult(True, {
                    "language": "JSON",
                    "status": "✅ SYNTAX VALID",
                    "file": path,
                    "message": "JSON is valid!"
                })
            except json.JSONDecodeError as e:
                return ToolResult(True, {
                    "language": "JSON",
                    "status": "❌ JSON ERROR",
                    "file": path,
                    "line": e.lineno,
                    "column": e.colno,
                    "message": str(e.msg),
                    "hint": f"Fix line {e.lineno}, column {e.colno}"
                }, error=f"JSONDecodeError: {e.msg}")

        # === HTML/XML ===
        elif ext in ('.html', '.htm', '.xml', '.svg'):
            from html.parser import HTMLParser
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            parser = HTMLParser()
            parser.feed(content)
            return ToolResult(True, {
                "language": "HTML/XML",
                "status": "✅ SYNTAX VALID",
                "file": path,
                "message": "HTML/XML is valid!"
            })

        # === YAML ===
        elif ext in ('.yml', '.yaml'):
            try:
                import yaml
                with open(path, 'r', encoding='utf-8') as f:
                    yaml.safe_load(f)
                return ToolResult(True, {
                    "language": "YAML",
                    "status": "✅ SYNTAX VALID",
                    "file": path,
                    "message": "YAML is valid!"
                })
            except yaml.YAMLError as e:
                return ToolResult(True, {
                    "language": "YAML",
                    "status": "❌ YAML ERROR",
                    "file": path,
                    "message": str(e),
                    "hint": "Check indentation and structure"
                }, error=str(e))
            except ImportError:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if len(content) > 0:
                    return ToolResult(True, {
                        "language": "YAML",
                        "status": "⚠️ CHECK (yaml not installed)",
                        "file": path,
                        "hint": "Install: pip install pyyaml for full validation"
                    })
                return ToolResult(False, None, "File is empty")

        # === CSS/SCSS ===
        elif ext in ('.css', '.scss', '.sass'):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if content.count('{') == content.count('}') and content.count('(') == content.count(')'):
                return ToolResult(True, {
                    "language": "CSS/SCSS",
                    "status": "✅ BRACES BALANCED",
                    "file": path,
                    "hint": "Basic check passed. Use a linter for full validation"
                })
            return ToolResult(True, {
                "language": "CSS/SCSS",
                "status": "❌ BRACES UNBALANCED",
                "file": path,
                "message": f"{{ = {content.count('{')} }} = {content.count('}')}",
                "hint": "Check opening/closing braces"
            }, error="Unbalanced braces")

        # === SHELL/BASH ===
        elif ext in ('.sh', '.bash', '.zsh', '.bat', '.cmd', '.ps1', '.fish'):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if content.count('(') == content.count(')'):
                return ToolResult(True, {
                    "language": "Shell",
                    "status": "✅ PARENTHESES BALANCED",
                    "file": path,
                    "hint": "Basic check passed"
                })
            return ToolResult(True, {
                "language": "Shell",
                "status": "⚠️ CHECK",
                "file": path,
                "hint": "Run bash -n file.sh for full validation"
            })

        # === JAVASCRIPT/TYPESCRIPT ===
        elif ext in ('.js', '.ts', '.jsx', '.tsx', '.mjs'):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if (content.count('(') == content.count(')') and
                    content.count('{') == content.count('}') and
                    content.count('[') == content.count(']')):
                return ToolResult(True, {
                    "language": "JavaScript/TypeScript",
                    "status": "✅ BRACKETS BALANCED",
                    "file": path,
                    "hint": "Basic check passed. For full: node --check file.js or npx tsc --noEmit"
                })
            return ToolResult(True, {
                "language": "JavaScript/TypeScript",
                "status": "❌ BRACKETS UNBALANCED",
                "file": path,
                "message": f"({content.count('(')} vs ){content.count(')')}",
                "hint": "Check opening/closing brackets"
            }, error="Unbalanced brackets")

        # === MARKDOWN ===
        elif ext in ('.md', '.markdown'):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if len(content.strip()) > 0:
                return ToolResult(True, {
                    "language": "Markdown",
                    "status": "✅ FILE VALID",
                    "file": path,
                    "hint": "Markdown doesn't require syntax checking"
                })
            return ToolResult(False, None, "File is empty")

        # === UNKNOWN ===
        else:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if len(content.strip()) > 0:
                return ToolResult(True, {
                    "language": f"Unknown ({ext})",
                    "status": "⚠️ CHECK",
                    "file": path,
                    "hint": f"Extension {ext} not supported. Use appropriate linter/compiler"
                })
            return ToolResult(False, None, "File is empty")

    except Exception as e:
        return ToolResult(False, None, f"Syntax check error: {str(e)}")

def edit_code(path: str, line: int, new_code: str = "", mode: str = "replace",
              end_line: Optional[int] = None, expected_old_code: Optional[str] = None) -> ToolResult:
    """Изменение кода в файле по номеру строки.

    Режимы:
    - 'replace': Заменить строки от line до end_line (или одну строку если end_line не указан)
    - 'insert_before': Вставить код перед строкой line
    - 'insert_after': Вставить код после строки line
    - 'delete': Удалить строки от line до end_line (или одну строку) — new_code не требуется!

    Args:
        path: Путь к файлу
        line: Номер строки (1-индексация)
        new_code: Новый код для вставки/замены (не требуется для режима delete)
        mode: Режим (replace, insert_before, insert_after, delete)
        end_line: Конечная строка диапазона (для replace/delete)
    """
    try:
        mode = str(mode or "replace").strip().lower()

        # Для режимов вставки/замены нужен new_code
        if mode in ("replace", "insert_before", "insert_after") and not new_code:
            hint = ""
            if mode == "replace":
                hint = "\n\nHOW TO FIX: Add 'new_code' to your tool call with the EXACT text you want to replace the lines with."
            elif mode in ("insert_before", "insert_after"):
                hint = f"\n\nHOW TO FIX: Add 'new_code' to your tool call with the code to insert {mode} line {line}."
            return ToolResult(False, None,
                              f"Error: mode '{mode}' requires 'new_code' argument but it was NOT provided.{hint}"
                              )
        if not os.path.exists(path):
            return ToolResult(False, None, f"File not found: {path}")

        encodings = ['utf-8', 'cp1251', 'cp866', 'latin-1']
        lines = None
        used_encoding = 'utf-8'
        for encoding in encodings:
            try:
                with open(path, "r", encoding=encoding) as f:
                    lines = f.readlines()
                used_encoding = encoding
                break
            except UnicodeDecodeError:
                continue

        if lines is None:
            return ToolResult(False, None, f"Failed to read file: encoding not recognized")

        total_lines = len(lines)

        if line < 1 or line > total_lines:
            return ToolResult(False, None,
                              f"Строка {line} вне диапазона (файл имеет {total_lines} строк)")

        if end_line is not None and (end_line < line or end_line > total_lines):
            return ToolResult(False, None,
                              f"end_line {end_line} вне диапазона (файл имеет {total_lines} строк)")

        if expected_old_code is not None and mode in ("replace", "delete"):
            candidate_end = end_line if end_line is not None else line
            current_code = "".join(lines[line - 1:candidate_end])
            expected_normalized = _normalize_code_for_compare(expected_old_code)
            current_normalized = _normalize_code_for_compare(current_code)

            if current_normalized != expected_normalized:
                located = _locate_code_block(lines, expected_old_code)
                if located is not None:
                    line, relocated_end_line = located
                    if end_line is not None or mode == "delete":
                        end_line = relocated_end_line
                else:
                    preview = current_code.rstrip()[:600] or "(empty)"
                    return ToolResult(
                        False,
                        None,
                        "Edit aborted: the code at the requested lines no longer matches 'expected_old_code'. "
                        "Read the file again and retry with fresh line numbers.\n\n"
                        f"Requested lines: {line}-{candidate_end}\n"
                        f"Current code there:\n{preview}"
                    )

        # Сохраняем старый код для показа изменений
        if mode == "delete":
            el = end_line if end_line else line
            old_lines = lines[line - 1:el]
            old_code = "".join(old_lines)
            del lines[line - 1:el]
            preview = old_code
        elif mode == "insert_before":
            inserted_lines = _code_text_to_lines(new_code)
            lines[line - 1:line - 1] = inserted_lines
            preview = f"+{len(inserted_lines)} строк(и) вставлено перед строкой {line}"
        elif mode == "insert_after":
            el = end_line if end_line else line
            inserted_lines = _code_text_to_lines(new_code)
            lines[el:el] = inserted_lines
            preview = f"+{len(inserted_lines)} строк(и) вставлено после строки {el}"
        elif mode == "replace":
            el = end_line if end_line else line
            old_lines = lines[line - 1:el]
            old_code = "".join(old_lines)
            replacement_lines = _code_text_to_lines(new_code)
            lines[line - 1:el] = replacement_lines
            preview = f"""--- Было (строки {line}-{el}): ---
{old_code.rstrip()}
--- Стало: ---
{new_code.rstrip()}"""
        else:
            return ToolResult(False, None,
                              f"Неизвестный режим: {mode}. Доступно: replace, insert_before, insert_after, delete")

        # Записываем обратно
        with open(path, "w", encoding=used_encoding) as f:
            f.writelines(lines)

        return ToolResult(True, {
            "path": path,
            "mode": mode,
            "line": line,
            "end_line": end_line if end_line else line,
            "total_lines": total_lines,
            "new_total_lines": len(lines),
            "preview": preview,
            "message": f"Код изменён: {path} (строка {line}, режим: {mode})"
        })
    except Exception as e:
        return ToolResult(False, None, f"Edit error: {str(e)}")

def list_file(path: str, show_imports: bool = True) -> ToolResult:
    """Показать структуру файла — список функций, классов и импортов без чтения кода.

    Полезно для экономии токенов: сначала смотрим оглавление файла,
    потом читаем только нужные участки через read_code.

    Args:
        path: Путь к файлу
        show_imports: Показывать ли импорты (по умолчанию да)
    """
    try:
        if not os.path.exists(path):
            return ToolResult(False, None, f"File not found: {path}")

        encodings = ['utf-8', 'cp1251', 'cp866', 'latin-1']
        lines = None
        for encoding in encodings:
            try:
                with open(path, "r", encoding=encoding) as f:
                    lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue

        if lines is None:
            return ToolResult(False, None, f"Failed to read file: encoding not recognized")

        functions = []
        classes = []
        imports = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Функции (включая вложенные, с учётом @декораторов)
            if stripped.startswith('def ') or stripped.startswith('async def '):
                name = stripped.split('(')[0].replace('def ', '').replace('async ', '')
                # Определяем уровень вложенности
                indent = len(line) - len(line.lstrip())
                level = indent // 4
                functions.append({
                    "name": name,
                    "line": i,
                    "indent": level
                })

            # Классы
            elif stripped.startswith('class '):
                name = stripped.split('(')[0].replace('class ', '').rstrip(':')
                classes.append({"name": name, "line": i})

            # Импорты
            elif show_imports and (stripped.startswith('import ') or stripped.startswith('from ')):
                imports.append({"line_num": i, "text": stripped[:120]})

        # Формируем вывод
        sections = []

        if classes:
            sections.append("📦 Классы:")
            for c in classes:
                sections.append(f"  {c['name']} (строка {c['line']})")

        if functions:
            sections.append("🔧 Функции и методы:")
            for f in functions:
                indent = "  " * (f["indent"] + 1)
                sections.append(f"{indent}def {f['name']} (строка {f['line']})")

        if imports:
            sections.append("📥 Импорты:")
            for imp in imports:
                sections.append(f"  L{imp['line_num']}: {imp['text']}")

        summary = (f"Строк в файле: {len(lines)}\n"
                   f"Классов: {len(classes)}\n"
                   f"Функций: {len(functions)}\n"
                   f"Импортов: {len(imports)}")

        return ToolResult(True, {
            "path": path,
            "total_lines": len(lines),
            "summary": summary,
            "content": "\n".join(sections) if sections else "Пустой файл или нет символов"
        })
    except Exception as e:
        return ToolResult(False, None, f"File analysis error: {str(e)}")

def grep_code(pattern: str, path: str = ".", ignore_case: bool = True,
              max_results: int = 50) -> ToolResult:
    """Поиск по файлам — нахождение функций, классов или ключевых слов.

    Ищет паттерн (регулярное выражение или простая строка) во всех файлах
    указанной директории (рекурсивно).

    Args:
        pattern: Паттерн для поиска (строка или регулярное выражение)
        path: Путь к директории или файлу (по умолчанию текущая директория)
        ignore_case: Игнорировать регистр
        max_results: Максимальное количество результатов
    """
    try:
        import re as re_mod

        # Проверяем, это файл или директория
        if os.path.isfile(path):
            files_to_search = [path]
        elif os.path.isdir(path):
            files_to_search = []
            # Рекурсивный обход, пропускаем .venv, .git, node_modules, __pycache__
            skip_dirs = {'.venv', '.git', 'node_modules', '__pycache__', '.idea', '.vscode'}
            for root, dirs, filenames in os.walk(path):
                dirs[:] = [d for d in dirs if d not in skip_dirs]
                for fn in filenames:
                    # Только текстовые файлы
                    if fn.endswith(('.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml',
                                    '.md', '.txt', '.sh', '.bat', '.ini', '.cfg', '.toml', '.xml')):
                        files_to_search.append(os.path.join(root, fn))
        else:
            return ToolResult(False, None, f"Путь не найден: {path}")

        results = []
        flags = re_mod.IGNORECASE if ignore_case else 0

        for file_path in files_to_search:
            encodings = ['utf-8', 'cp1251', 'cp866', 'latin-1']
            lines = None
            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        lines = f.readlines()
                    break
                except (UnicodeDecodeError, Exception):
                    continue

            if lines is None:
                continue

            for i, line in enumerate(lines, 1):
                if re_mod.search(pattern, line, flags):
                    rel_path = os.path.relpath(file_path, path) if os.path.isdir(path) else file_path
                    results.append({
                        "file": rel_path,
                        "line_num": i,
                        "content": line.rstrip()[:200]
                    })

                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break

        if not results:
            return ToolResult(False, None,
                              f"Ничего не найдено по паттерну '{pattern}' в {path}")

        # Форматируем вывод
        formatted = []
        current_file = None
        for r in results:
            if r["file"] != current_file:
                current_file = r["file"]
                formatted.append(f"\n📄 {current_file}:")
            formatted.append(f"  L{r['line_num']}: {r['content']}")

        return ToolResult(True, {
            "pattern": pattern,
            "search_path": path,
            "total_matches": len(results),
            "content": "\n".join(formatted)
        })
    except Exception as e:
        return ToolResult(False, None, f"Search error: {str(e)}")

