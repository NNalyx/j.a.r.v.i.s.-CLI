"""MLX-backed FastAPI server with OpenAI-compatible chat completions."""
import argparse
import base64
import io
import json
import os
import secrets
import sys
import time
import urllib.request
import warnings
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# mlx-vlm доступен только на macOS Apple Silicon.
try:
    from mlx_vlm import load as mlx_vlm_load
    from mlx_vlm.utils import load_image as mlx_load_image
    HAS_MLX_VLM = True
except Exception as import_exc:  # pragma: no cover
    HAS_MLX_VLM = False
    MLX_VLM_ERROR = str(import_exc)

    def mlx_vlm_load(*args, **kwargs):  # type: ignore
        raise RuntimeError(f"mlx-vlm недоступен: {MLX_VLM_ERROR}")

    def mlx_load_image(*args, **kwargs):  # type: ignore
        raise RuntimeError(f"mlx-vlm недоступен: {MLX_VLM_ERROR}")

try:
    from mlx_lm import load as mlx_lm_load, generate as mlx_lm_generate
    from mlx_lm import sample_utils as mlx_lm_sample_utils
    HAS_MLX_LM = True
except Exception as import_exc:  # pragma: no cover
    HAS_MLX_LM = False
    MLX_LM_ERROR = str(import_exc)

    def mlx_lm_load(*args, **kwargs):  # type: ignore
        raise RuntimeError(f"mlx-lm недоступен: {MLX_LM_ERROR}")

    def mlx_lm_generate(*args, **kwargs):  # type: ignore
        raise RuntimeError(f"mlx-lm недоступен: {MLX_LM_ERROR}")

    mlx_lm_sample_utils = None  # type: ignore

try:
    from PIL import Image
    HAS_PIL = True
except Exception:
    HAS_PIL = False
    Image = None  # type: ignore


app = FastAPI(title="Jarvis MLX Server", version="1.0.0")

# Глобальное состояние
MODEL_STATE: Dict[str, Any] = {
    "model": None,
    "processor": None,
    "config": None,
    "model_path": None,
    "loaded_at": None,
    "backend": None,
}


# ---------- Pydantic модели ----------

class MessageContent(BaseModel):
    type: str = "text"
    text: Optional[str] = None
    image_url: Optional[Dict[str, str]] = None


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str = "mlx-model"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 512
    top_p: Optional[float] = 1.0
    stream: Optional[bool] = False
    stop: Optional[Any] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "jarvis-mlx"


# ---------- Утилиты ----------

def _now() -> int:
    return int(time.time())


def _load_image_from_source(source: str) -> Any:
    """Загрузить изображение из URL или base64-строки."""
    if not HAS_PIL:
        raise RuntimeError("PIL недоступен, не могу обработать изображение")

    if source.startswith("data:image"):
        # data:image/png;base64,...
        header, _, b64 = source.partition(",")
        if not b64:
            raise ValueError("Некорректная base64-строка изображения")
        data = base64.b64decode(b64)
        return Image.open(io.BytesIO(data)).convert("RGB")

    if source.startswith("http://") or source.startswith("https://"):
        with urllib.request.urlopen(source, timeout=30) as response:
            data = response.read()
        return Image.open(io.BytesIO(data)).convert("RGB")

    if os.path.exists(source):
        return Image.open(source).convert("RGB")

    raise ValueError(f"Неизвестный источник изображения: {source[:80]}")


def _extract_images(messages: List[ChatMessage]) -> List[Any]:
    """Загрузить все изображения из сообщений OpenAI-формата."""
    images: List[Any] = []
    for msg in messages:
        content = msg.content
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    image_url = part.get("image_url", {})
                    url = image_url.get("url") if isinstance(image_url, dict) else image_url
                    if url:
                        images.append(_load_image_from_source(url))
    return images


def _apply_chat_template(
    processor: Any, config: Any, messages: List[ChatMessage], num_images: int = 0,
    tools: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Применить чат-шаблон модели, если он доступен.

    Включаем thinking (enable_thinking=True), чтобы модель могла рассуждать
    перед ответом. Jarvis-клиент сам обрабатывает <think>...</think> блоки.
    """
    msgs = []
    for m in messages:
        if isinstance(m.content, str):
            msgs.append({"role": m.role, "content": m.content})
        elif isinstance(m.content, list):
            texts = [
                p.get("text", "")
                for p in m.content
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            image_parts = [
                p
                for p in m.content
                if isinstance(p, dict) and p.get("type") == "image_url"
            ]
            if image_parts and not texts:
                msgs.append({"role": m.role, "content": image_parts})
            else:
                msgs.append({"role": m.role, "content": " ".join(texts)})
        else:
            msgs.append({"role": m.role, "content": str(m.content)})

    backend = MODEL_STATE.get("backend")

    # 1) Пробуем нативный apply_chat_template токенизатора (mlx-lm)
    if backend == "mlx-lm":
        apply_fn = getattr(processor, "apply_chat_template", None)
        if apply_fn is None and hasattr(processor, "tokenizer"):
            apply_fn = getattr(processor.tokenizer, "apply_chat_template", None)
        if apply_fn is not None:
            try:
                kwargs = {"tokenize": False, "add_generation_prompt": True}
                if tools:
                    kwargs["tools"] = tools
                # Qwen3 / Qwopus шаблоны понимают enable_thinking
                try:
                    return apply_fn(msgs, **kwargs, enable_thinking=True)
                except TypeError:
                    return apply_fn(msgs, **kwargs)
            except Exception as exc:
                warnings.warn(f"tokenizer.apply_chat_template не сработал: {exc}")

    # 2) Fallback на mlx_vlm prompt utils
    try:
        from mlx_vlm.prompt_utils import apply_chat_template as _apply
        return _apply(
            processor,
            config,
            msgs,
            num_images=num_images,
            add_generation_prompt=True,
            enable_thinking=True,
        )
    except Exception:
        pass

    # 3) Last-resort fallback: просто склеиваем текст
    parts = []
    for m in msgs:
        content = m.get("content", "")
        if isinstance(content, str):
            parts.append(f"{m['role']}: {content}")
        else:
            parts.append(f"{m['role']}: {str(content)}")
    parts.append("assistant: ")
    return "\n".join(parts)


def _stop_at_tokens(text: str, stop_tokens: List[str]) -> str:
    """Обрезать текст при первом вхождении любого стоп-токена."""
    lower = text.lower()
    cut_pos = len(text)
    for token in stop_tokens:
        idx = text.find(token)
        if idx != -1:
            cut_pos = min(cut_pos, idx)
        # Также ищем lowercase варианты для user:/assistant:
        if token.lower() != token:
            idx = lower.find(token.lower())
            if idx != -1:
                cut_pos = min(cut_pos, idx)
    return text[:cut_pos].rstrip()


def _strip_thinking(text: str) -> str:
    """Удалить пустые/любые <think>...</think> блоки из ответа."""
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


STOP_TOKENS = ["<|im_end|>", "<|im_start|>", "<|endoftext|>", "</s>", "\nuser:", "\nassistant:"]


def _split_thinking(text: str) -> tuple[str, str]:
    """Разделить текст на (reasoning, content) по тегам <think>...</think>."""
    text = text.lstrip()
    if not text.startswith("<think>"):
        return "", text
    end = text.find("</think>")
    if end == -1:
        return text[len("<think>"):].strip(), ""
    reasoning = text[len("<think>"):end].strip()
    content = text[end + len("</think>"):].strip()
    return reasoning, content


def _generate_text(prompt: str, image: Optional[Any], temperature: float, max_tokens: int, top_p: float) -> tuple[str, str]:
    """Обычная (не-потоковая) генерация. Возвращает (content, reasoning)."""
    backend = MODEL_STATE.get("backend")
    model = MODEL_STATE["model"]
    processor = MODEL_STATE["processor"]

    if model is None or processor is None:
        raise RuntimeError("Модель не загружена")

    if backend == "mlx-lm":
        if image is not None:
            raise RuntimeError("mlx-lm backend не поддерживает изображения")
        sampler = mlx_lm_sample_utils.make_sampler(temp=temperature, top_p=top_p)
        text = str(
            mlx_lm_generate(
                model,
                processor,
                prompt,
                verbose=False,
                max_tokens=max_tokens,
                sampler=sampler,
            )
        )
        # Если чат-шаблон включил thinking (<think> в конце промпта),
        # а модель не вывела открывающий тег сама — добавляем его для корректного разделения.
        prompt_tail = prompt.rstrip()[-20:].lower()
        text_starts_think = text.lstrip().startswith("<think>")
        prefix = "<think>\n" if "<think>" in prompt_tail and not text_starts_think else ""
        full = _stop_at_tokens(prefix + text, STOP_TOKENS)
        reasoning, content = _split_thinking(full)
        return content, reasoning

    # mlx-vlm backend
    kwargs: Dict[str, Any] = {
        "temp": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "verbose": False,
        "skip_special_tokens": True,
    }

    try:
        from mlx_vlm import generate as mlx_generate
        if image is not None:
            output = mlx_generate(model, processor, prompt, image=image, **kwargs)
        else:
            output = mlx_generate(model, processor, prompt, **kwargs)
        if hasattr(output, "text"):
            text = str(output.text)
        else:
            text = str(output)
        return _split_thinking(text)
    except Exception as exc:
        # Fallback: используем processor напрямую
        warnings.warn(f"mlx_vlm.generate не сработал ({exc}), пробуем прямой generate")
        inputs = processor(prompt, images=image, return_tensors="pt") if image is not None else processor(prompt, return_tensors="pt")
        output_ids = model.generate(**inputs, max_new_tokens=max_tokens, temperature=temperature, top_p=top_p)
        text = processor.decode(output_ids[0], skip_special_tokens=True)
        return _split_thinking(text)


def _stream_generate_text(prompt: str, image: Optional[Any], temperature: float, max_tokens: int, top_p: float):
    """Потоковая генерация токенов.

    Yield'ит dict'и:
        {"reasoning_content": "..."}  — пока модель внутри <think>...</think>
        {"content": "..."}            — основной ответ после </think>
    """
    backend = MODEL_STATE.get("backend")
    model = MODEL_STATE["model"]
    processor = MODEL_STATE["processor"]

    if model is None or processor is None:
        raise RuntimeError("Модель не загружена")

    if backend == "mlx-lm":
        if image is not None:
            raise RuntimeError("mlx-lm backend не поддерживает изображения")
        sampler = mlx_lm_sample_utils.make_sampler(temp=temperature, top_p=top_p)
        try:
            from mlx_lm.generate import stream_generate as lm_stream_generate
            prompt_tail = prompt.rstrip()[-20:].lower()
            prefix = "<think>\n" if "<think>" in prompt_tail else ""
            buffer = prefix
            in_thinking = bool(prefix)
            reasoning_sent = len(prefix)  # не отправляем сам тег <think>\n
            content_sent = 0
            max_stop_len = max(len(t) for t in STOP_TOKENS)

            def _find_stop_cut(s: str) -> int:
                lower = s.lower()
                cut = len(s)
                for token in STOP_TOKENS:
                    idx = s.find(token)
                    if idx != -1:
                        cut = min(cut, idx)
                    if token.lower() != token:
                        idx = lower.find(token.lower())
                        if idx != -1:
                            cut = min(cut, idx)
                return cut

            for response in lm_stream_generate(
                model, processor, prompt, max_tokens=max_tokens, sampler=sampler
            ):
                buffer += response.text

                # Обрезаем по стоп-токену, если он уже полностью пришёл
                cut = _find_stop_cut(buffer)
                if cut < len(buffer):
                    buffer = buffer[:cut]

                if in_thinking:
                    think_end = buffer.find("</think>")
                    if think_end != -1:
                        # Отправляем остаток reasoning (без самого тега </think>)
                        if think_end > reasoning_sent:
                            yield {"reasoning_content": buffer[reasoning_sent:think_end]}
                            reasoning_sent = think_end
                        # Переключаемся на content
                        in_thinking = False
                        content_sent = think_end + len("</think>")
                    else:
                        # Пока в thinking — не отправляем последние max_stop_len символов,
                        # они могут быть частью стоп-токена.
                        safe_pos = max(reasoning_sent, len(buffer) - max_stop_len)
                        if safe_pos > reasoning_sent:
                            yield {"reasoning_content": buffer[reasoning_sent:safe_pos]}
                            reasoning_sent = safe_pos
                else:
                    safe_pos = max(content_sent, len(buffer) - max_stop_len)
                    if safe_pos > content_sent:
                        yield {"content": buffer[content_sent:safe_pos]}
                        content_sent = safe_pos

            # Конец генерации — выдаём остатки
            if in_thinking:
                if len(buffer) > reasoning_sent:
                    yield {"reasoning_content": buffer[reasoning_sent:]}
            else:
                if len(buffer) > content_sent:
                    yield {"content": buffer[content_sent:]}
        except Exception as exc:
            raise RuntimeError(f"Потоковая генерация mlx-lm не удалась: {exc}")
        return

    # mlx-vlm backend
    try:
        from mlx_vlm.utils import generate_step

        # Подготовка inputs
        if image is not None:
            inputs = processor(text=prompt, images=image, return_tensors="np")
        else:
            inputs = processor(text=prompt, return_tensors="np")

        input_ids = inputs["input_ids"]
        kwargs = {"temp": temperature, "top_p": top_p}

        eos_token_id = None
        for attr in ("eos_token_id", "tokenizer"):
            val = getattr(processor, attr, None)
            if attr == "tokenizer" and val is not None:
                eos_token_id = getattr(val, "eos_token_id", None)
            elif attr == "eos_token_id" and val is not None:
                eos_token_id = val
            if eos_token_id is not None:
                break

        buffer = ""
        in_thinking = False
        reasoning_sent = 0
        content_sent = 0
        generated = 0
        max_stop_len = max(len(t) for t in STOP_TOKENS)

        def _find_stop_cut(s: str) -> int:
            lower = s.lower()
            cut = len(s)
            for token in STOP_TOKENS:
                idx = s.find(token)
                if idx != -1:
                    cut = min(cut, idx)
                if token.lower() != token:
                    idx = lower.find(token.lower())
                    if idx != -1:
                        cut = min(cut, idx)
            return cut

        for token, _ in generate_step(model, input_ids, **kwargs):
            if eos_token_id is not None and token == eos_token_id:
                break
            decoded = processor.decode([token], skip_special_tokens=True)
            if not decoded:
                generated += 1
                if generated >= max_tokens:
                    break
                continue
            buffer += decoded

            cut = _find_stop_cut(buffer)
            if cut < len(buffer):
                buffer = buffer[:cut]

            if not in_thinking:
                think_start = buffer.find("<think>")
                if think_start != -1:
                    if think_start > content_sent:
                        yield {"content": buffer[content_sent:think_start]}
                    in_thinking = True
                    reasoning_sent = think_start + len("<think>")
                    content_sent = think_start + len("<think>")

            if in_thinking:
                think_end = buffer.find("</think>")
                if think_end != -1:
                    if think_end > reasoning_sent:
                        yield {"reasoning_content": buffer[reasoning_sent:think_end]}
                    in_thinking = False
                    content_sent = think_end + len("</think>")
                    reasoning_sent = think_end + len("</think>")
                else:
                    safe_pos = max(reasoning_sent, len(buffer) - max_stop_len)
                    if safe_pos > reasoning_sent:
                        yield {"reasoning_content": buffer[reasoning_sent:safe_pos]}
                        reasoning_sent = safe_pos
            else:
                safe_pos = max(content_sent, len(buffer) - max_stop_len)
                if safe_pos > content_sent:
                    yield {"content": buffer[content_sent:safe_pos]}
                    content_sent = safe_pos

            generated += 1
            if generated >= max_tokens:
                break

        # Конец генерации — выдаём остатки
        if in_thinking:
            if len(buffer) > reasoning_sent:
                yield {"reasoning_content": buffer[reasoning_sent:]}
        else:
            if len(buffer) > content_sent:
                yield {"content": buffer[content_sent:]}
    except Exception as exc:
        # Если потоковая генерация не поддерживается — падаем с понятной ошибкой
        raise RuntimeError(f"Потоковая генерация не удалась: {exc}")


# ---------- Эндпоинты ----------

@app.get("/health")
def health():
    if MODEL_STATE["model"] is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ok", "model": MODEL_STATE["model_path"]}


@app.get("/v1/models")
def list_models():
    model_id = MODEL_STATE["model_path"] or "mlx-model"
    return {"object": "list", "data": [ModelInfo(id=model_id).model_dump()]}


@app.post("/v1/chat/completions")
def chat_completions(request: ChatCompletionRequest):
    if MODEL_STATE["model"] is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    images = _extract_images(request.messages)
    prompt = _apply_chat_template(
        MODEL_STATE["processor"],
        MODEL_STATE["config"],
        request.messages,
        num_images=len(images),
        tools=request.tools,
    )
    image = images[0] if images else None

    model_id = MODEL_STATE["model_path"] or request.model
    created = _now()
    completion_id = f"chatcmpl-{secrets.token_hex(12)}"

    if request.stream:
        def event_stream():
            first = True
            try:
                for delta in _stream_generate_text(
                    prompt,
                    image,
                    temperature=request.temperature or 0.7,
                    max_tokens=request.max_tokens or 512,
                    top_p=request.top_p or 1.0,
                ):
                    if first:
                        chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_id,
                            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                        first = False

                    if "reasoning_content" in delta:
                        delta_payload = {"reasoning_content": delta["reasoning_content"]}
                    elif "content" in delta:
                        delta_payload = {"content": delta["content"]}
                    else:
                        delta_payload = {}

                    if delta_payload:
                        chunk = {
                            "id": completion_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model_id,
                            "choices": [{"index": 0, "delta": delta_payload, "finish_reason": None}],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

                chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_id,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(chunk)}\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # Non-streaming
    try:
        content, reasoning = _generate_text(
            prompt,
            image,
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens or 512,
            top_p=request.top_p or 1.0,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc

    message = {"role": "assistant", "content": content}
    if reasoning:
        message["reasoning_content"] = reasoning

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model_id,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": -1,
            "completion_tokens": -1,
            "total_tokens": -1,
        },
    }


# ---------- Загрузка модели и main ----------

def load_model(model_path: str):
    if not HAS_MLX_VLM and not HAS_MLX_LM:
        raise RuntimeError("Ни mlx-lm, ни mlx-vlm недоступны на этой платформе")

    if not os.path.isdir(model_path):
        raise FileNotFoundError(f"Папка модели не найдена: {model_path}")

    print(f"[MLX] Загрузка модели: {model_path}", flush=True)

    # Пробуем сначала mlx_lm — для многих MLX-моделей он работает лучше как text-only
    if HAS_MLX_LM:
        try:
            model, tokenizer = mlx_lm_load(model_path)
            MODEL_STATE["model"] = model
            MODEL_STATE["processor"] = tokenizer
            MODEL_STATE["tokenizer"] = tokenizer
            MODEL_STATE["config"] = getattr(model, "config", None)
            MODEL_STATE["model_path"] = os.path.abspath(model_path)
            MODEL_STATE["loaded_at"] = time.time()
            MODEL_STATE["backend"] = "mlx-lm"
            print("[MLX] Модель загружена (backend: mlx-lm)", flush=True)
            return
        except Exception as exc:
            print(f"[MLX] mlx-lm.load не подошёл: {exc}", flush=True)

    if not HAS_MLX_VLM:
        raise RuntimeError(f"mlx-vlm недоступен на этой платформе: {MLX_VLM_ERROR}")

    model, processor = mlx_vlm_load(model_path)

    # Попробуем получить config
    config: Any = None
    config_path = os.path.join(model_path, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            pass

    MODEL_STATE["model"] = model
    MODEL_STATE["processor"] = processor
    MODEL_STATE["tokenizer"] = getattr(processor, "tokenizer", processor)
    MODEL_STATE["config"] = config
    MODEL_STATE["model_path"] = os.path.abspath(model_path)
    MODEL_STATE["loaded_at"] = time.time()
    MODEL_STATE["backend"] = "mlx-vlm"
    print("[MLX] Модель загружена (backend: mlx-vlm)", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Jarvis MLX Server")
    parser.add_argument("--model", required=True, help="Путь к папке с MLX/HF моделью")
    parser.add_argument("--host", default="127.0.0.1", help="Хост")
    parser.add_argument("--port", type=int, default=8080, help="Порт")
    parser.add_argument("--temp", type=float, default=0.7, help="Temperature (не используется при старте, передаётся в запросах)")
    parser.add_argument("--max-tokens", type=int, default=512, help="Max tokens (не используется при старте)")
    args = parser.parse_args()

    load_model(args.model)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
