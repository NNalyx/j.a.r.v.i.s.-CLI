"""Fast voice mode: classify short commands before invoking the full agent."""

from __future__ import annotations

import ast
import datetime as _dt
import math
import operator
import re
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, Callable, Dict, Optional


try:
    from laya import Router
except ImportError:  # Optional dependency; normal Jarvis must keep working.
    Router = None


class FastCommandRouter:
    """Small intent router with safe local handlers and a full-agent fallback."""

    def __init__(self) -> None:
        self._router = None
        self._local_model = self._find_local_multilingual_model()

    @staticmethod
    def _find_local_multilingual_model() -> Optional[str]:
        cache_root = Path.home() / ".cache" / "huggingface" / "hub" / "models--convaiinnovations--laya" / "snapshots"
        candidates = []
        if cache_root.exists():
            candidates.extend(path / "multilingual" for path in sorted(cache_root.iterdir(), reverse=True) if path.is_dir())
        for candidate in candidates:
            if (candidate / "model.safetensors").is_file() and (candidate / "rl_agent_config.json").is_file():
                return str(candidate)
        return None

    @property
    def available(self) -> bool:
        return Router is not None

    def _get_router(self):
        if Router is None:
            raise RuntimeError("Laya не установлена. Выполните: pip install laya")
        if self._router is None:
            if self._local_model:
                # Локальный путь исключает зависание на HF API при каждом
                # запросе и оставляет только саму быструю инференс-операцию.
                self._router = Router(
                    models={
                        "english": (self._local_model, None),
                        "multilingual": (self._local_model, None),
                    },
                    default="multilingual",
                    max_loaded=1,
                    device="mps",
                )
            else:
                self._router = Router(default="multilingual", max_loaded=1)
        return self._router

    @staticmethod
    def _questions() -> Dict[str, Any]:
        return {
            "intent": {
                "type": "choice",
                "instructions": "Определи тип короткой команды пользователя.",
                "criteria": {
                    "time": "спросить текущее время, дату или день недели",
                    "calculate": "посчитать математическое выражение",
                    "open_site": "открыть сайт, YouTube, Google или ссылку",
                    "open_app": "открыть приложение на компьютере",
                    "free": "свободный вопрос или другая команда, требующая Jarvis",
                },
            },
        }

    @staticmethod
    def _is_yes_no_question(command: str) -> bool:
        lower = command.lower().strip()
        return (
            " ли " in f" {lower} "
            or lower.startswith(("можно ", "нужно ", "стоит ", "правда ", "верно "))
            or lower.endswith("?") and any(word in lower for word in ("можно", "нужно", "правда", "стоит"))
        )

    def _answer_free_with_laya(self, command: str) -> str:
        """Answer a short yes/no question with Laya's calibrated noul head.

        Laya is used first for typed answers. Truly open-ended text is handled
        by the optional fallback supplied by the Fast-mode controller.
        """
        if not self._is_yes_no_question(command):
            return ""
        result = self._get_router().predict(
            command,
            {
                "answer": {
                    "type": "noul",
                    "instructions": "Ответь на вопрос пользователя. Вероятность должна отражать ответ Да.",
                    "criteria": {
                        "false": "нет, утверждение или действие неверно",
                        "true": "да, утверждение или действие верно",
                    },
                },
            },
            model="multilingual",
        )
        try:
            probability = float(result["answers"]["answer"]["noul"])
        except (KeyError, TypeError, ValueError):
            return "Не удалось определить ответ."
        return "Да." if probability >= 0.5 else "Нет."

    @staticmethod
    def _choice(result: Dict[str, Any]) -> str:
        try:
            return str(result["answers"]["intent"]["choice"]).strip().lower()
        except (KeyError, TypeError):
            return "free"

    @staticmethod
    def _looks_like_calculation(command: str) -> bool:
        lower = command.lower()
        has_math_word = any(word in lower for word in ("посчитай", "вычисли", "сколько будет", "умножь", "умножить", "раздели", "разделить"))
        has_math_symbol = bool(re.search(r"\d\s*[+*/%^×÷-]\s*\d", lower))
        return has_math_word or has_math_symbol

    @staticmethod
    def _looks_like_time(command: str) -> bool:
        lower = command.lower()
        return any(word in lower for word in ("сколько времени", "сколько время", "который час", "какое время", "текущая дата", "сегодняшняя дата"))

    @staticmethod
    def _looks_like_site(command: str) -> bool:
        lower = command.lower()
        return any(word in lower for word in ("открой youtube", "открой ютуб", "открой google", "открой гугл", "открой github", "открой ссылку", "http://", "https://"))

    @staticmethod
    def _looks_like_app(command: str) -> bool:
        lower = command.lower()
        return lower.startswith(("открой приложение", "запусти приложение", "открой терминал", "открой калькулятор", "открой сафари", "открой chrome", "открой хром"))

    @staticmethod
    def _time_answer(command: str) -> str:
        now = _dt.datetime.now()
        lower = command.lower()
        if "дат" in lower or "числ" in lower:
            return f"Сегодня {now.day:02d}.{now.month:02d}.{now.year}"
        if "день недели" in lower or "какой сегодня день" in lower:
            return f"Сегодня {now.strftime('%A')}"
        return f"Сейчас {now:%H:%M}"

    @staticmethod
    def _safe_calculate(command: str) -> str:
        expression = command.lower()
        expression = re.sub(r"^(пожалуйста,?\s*)?(посчитай|вычисли|сколько будет|реши)\s*", "", expression)
        number_words = {
            "ноль": "0", "один": "1", "одна": "1", "два": "2", "две": "2",
            "три": "3", "четыре": "4", "пять": "5", "шесть": "6",
            "семь": "7", "восемь": "8", "девять": "9", "десять": "10",
            "сто": "100", "тысяча": "1000",
        }
        compound_numbers = {
            "двадцать пять": "25", "двадцать четыре": "24", "двадцать три": "23", "двадцать два": "22", "двадцать один": "21",
            "тридцать пять": "35", "тридцать четыре": "34", "тридцать три": "33", "тридцать два": "32", "тридцать один": "31",
            "сорок пять": "45", "сорок четыре": "44", "сорок три": "43", "сорок два": "42", "сорок один": "41",
            "пятьдесят": "50", "сорок": "40", "тридцать": "30", "двадцать": "20",
            "одиннадцать": "11", "двенадцать": "12", "тринадцать": "13", "четырнадцать": "14", "пятнадцать": "15",
        }
        for phrase, value in sorted(compound_numbers.items(), key=lambda item: len(item[0]), reverse=True):
            expression = re.sub(rf"\b{phrase}\b", value, expression)
        for word, value in number_words.items():
            expression = re.sub(rf"\b{word}\b", value, expression)
        expression = re.sub(r"\s+(умножить|умножь)(?:\s+на)?\s+", " * ", expression)
        expression = re.sub(r"\s+(разделить|делить)(?:\s+на)?\s+", " / ", expression)
        expression = re.sub(r"\s+плюс\s+", " + ", expression)
        expression = re.sub(r"\s+минус\s+", " - ", expression)
        expression = expression.replace(",", ".").replace("×", "*").replace("÷", "/").replace("^", "**")
        expression = re.sub(r"[^0-9+\-*/().%\s]", "", expression).strip()
        if not expression:
            return "Не удалось выделить выражение для вычисления."

        binary_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
        }
        unary_ops = {ast.UAdd: operator.pos, ast.USub: operator.neg}

        def evaluate(node: ast.AST) -> float:
            if isinstance(node, ast.Expression):
                return evaluate(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return float(node.value)
            if isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
                left, right = evaluate(node.left), evaluate(node.right)
                if isinstance(node.op, ast.Pow) and abs(right) > 20:
                    raise ValueError("слишком большая степень")
                return binary_ops[type(node.op)](left, right)
            if isinstance(node, ast.UnaryOp) and type(node.op) in unary_ops:
                return unary_ops[type(node.op)](evaluate(node.operand))
            raise ValueError("недопустимое выражение")

        try:
            value = evaluate(ast.parse(expression, mode="eval"))
            if not math.isfinite(value):
                raise ValueError("результат не является числом")
            return str(int(value)) if value.is_integer() else f"{value:.6g}"
        except Exception:
            return "Не удалось безопасно вычислить это выражение."

    @staticmethod
    def _open_site(command: str) -> str:
        lower = command.lower()
        url_match = re.search(r"https?://\S+", command)
        if url_match:
            url = url_match.group(0).rstrip(".,!?)]")
        elif "youtube" in lower or "ютуб" in lower:
            url = "https://www.youtube.com"
        elif "google" in lower or "гугл" in lower:
            url = "https://www.google.com"
        elif "github" in lower:
            url = "https://github.com"
        else:
            return "Не понял, какой сайт открыть."
        webbrowser.open(url)
        return f"Открываю {url}"

    @staticmethod
    def _open_app(command: str) -> str:
        known = {
            "калькулятор": "Calculator",
            "calculator": "Calculator",
            "заметки": "Notes",
            "терминал": "Terminal",
            "terminal": "Terminal",
            "сафари": "Safari",
            "safari": "Safari",
            "хром": "Google Chrome",
            "chrome": "Google Chrome",
        }
        lower = command.lower()
        app_name = next((name for key, name in known.items() if key in lower), None)
        if not app_name:
            return "Не знаю это приложение. Откройте его через обычный режим Jarvis."
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", app_name])
            elif sys.platform == "win32":
                subprocess.Popen(["cmd", "/c", "start", "", app_name])
            else:
                subprocess.Popen([app_name])
            return f"Открываю {app_name}"
        except Exception as exc:
            return f"Не удалось открыть {app_name}: {exc}"

    def process(self, command: str, fallback: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
        text = str(command or "").strip()
        if not text:
            return {"intent": "empty", "answer": "Я не расслышал команду."}
        result: Dict[str, Any] = {"routing": {"model": "local-rules"}}
        if self._looks_like_calculation(text):
            intent = "calculate"
        elif self._looks_like_time(text):
            intent = "time"
        elif self._looks_like_site(text):
            intent = "open_site"
        elif self._looks_like_app(text):
            intent = "open_app"
        else:
            result = self._get_router().predict(text, self._questions(), model="multilingual")
            intent = self._choice(result)
        # Не полагаемся на классификатор там, где команда однозначно
        # математическая: это избавляет от редких ошибок маршрутизации Laya.
        if self._looks_like_calculation(text):
            intent = "calculate"
        if intent == "time":
            answer = self._time_answer(text)
        elif intent == "calculate":
            answer = self._safe_calculate(text)
            if answer.startswith("Не удалось") and fallback is not None:
                answer = fallback(text)
        elif intent == "open_site":
            answer = self._open_site(text)
            if answer.startswith("Не понял") and fallback is not None:
                answer = fallback(text)
        elif intent == "open_app":
            answer = self._open_app(text)
            if answer.startswith("Не знаю") and fallback is not None:
                answer = fallback(text)
        elif intent == "free":
            answer = self._answer_free_with_laya(text)
            if not answer and fallback is not None:
                answer = fallback(text)
            if not answer:
                answer = "Не удалось определить короткий ответ."
        elif fallback is not None:
            answer = fallback(text)
        else:
            answer = "Для этой команды нужен обычный режим Jarvis."
        understood = bool(answer)
        return {"intent": intent, "answer": answer, "understood": understood, "routing": result.get("routing", {})}
