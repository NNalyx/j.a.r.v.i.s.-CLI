"""FastAPI server wrapper around stable-diffusion.cpp (sd-cli) for image generation.

Runs on macOS Metal using Krea-2-Turbo GGUF components with optional LoRA.
"""
import base64
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


IS_MACOS = sys.platform == "darwin"

BASE_DIR = Path(__file__).resolve().parent

# Paths to the stable-diffusion.cpp binary and model components.
SD_CLI = os.environ.get(
    "SD_CLI",
    "/Users/roma/PycharmProjects/stable-diffusion.cpp/build/bin/sd-cli",
)
MODEL_DIR = Path(os.environ.get("SD_MODEL_DIR", "/Users/roma/models/krea2"))

DIFFUSION_MODEL = Path(os.environ.get("SD_DIFFUSION_MODEL", MODEL_DIR / "krea2_turbo-Q4_0.gguf"))
VAE_MODEL = Path(os.environ.get("SD_VAE_MODEL", MODEL_DIR / "wan_2.1_vae.safetensors"))
LLM_MODEL = Path(os.environ.get("SD_LLM_MODEL", MODEL_DIR / "Qwen3-VL-4B-Instruct-Q4_K_M.gguf"))
LORA_MODEL_DIR = Path(os.environ.get("SD_LORA_MODEL_DIR", MODEL_DIR / "lora"))

OUTPUT_DIR = Path(os.environ.get("SD_OUTPUT_DIR", BASE_DIR / "jarvis_agent_images"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
DEFAULT_STEPS = 4
DEFAULT_CFG_SCALE = 1.0
DEFAULT_SAMPLER = "euler"
DEFAULT_STRENGTH = 0.75

app = FastAPI(title="Jarvis Image Server", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Text prompt for the image")
    width: int = Field(DEFAULT_WIDTH, ge=256, le=2048, multiple_of=64)
    height: int = Field(DEFAULT_HEIGHT, ge=256, le=2048, multiple_of=64)
    steps: int = Field(DEFAULT_STEPS, ge=1, le=50)
    cfg_scale: float = Field(DEFAULT_CFG_SCALE, ge=0.0, le=30.0)
    sampler: str = Field(DEFAULT_SAMPLER)
    seed: int = Field(-1, ge=-1, le=2**31 - 1)
    init_image: Optional[str] = Field(None, description="Base64-encoded init image for img2img")
    strength: float = Field(DEFAULT_STRENGTH, ge=0.0, le=1.0)
    lora_model_dir: Optional[str] = Field(None, description="Directory containing LoRA models to apply")
    lora_scale: float = Field(1.0, ge=0.0, le=5.0, description="LoRA scale (used when auto-applying LoRA triggers)")
    apply_lora: bool = Field(True, description="Auto-append LoRA triggers from lora_model_dir to the prompt")


class HealthResponse(BaseModel):
    ok: bool
    sd_cli: str
    diffusion_model: str
    vae_model: str
    llm_model: str
    lora_model_dir: str
    output_dir: str
    img2img: bool = True


def _check_setup() -> Optional[str]:
    if not Path(SD_CLI).exists():
        return f"sd-cli not found: {SD_CLI}"
    for label, path in [
        ("diffusion model", DIFFUSION_MODEL),
        ("VAE", VAE_MODEL),
        ("LLM/text encoder", LLM_MODEL),
    ]:
        if not path.exists():
            return f"{label} not found: {path}"
    return None


def _build_command(req: GenerateRequest, output_path: Path, init_path: Optional[Path] = None) -> list[str]:
    seed = req.seed if req.seed >= 0 else random.randint(0, 2**31 - 1)

    prompt = req.prompt
    lora_dir = req.lora_model_dir
    if not lora_dir:
        lora_dir = str(LORA_MODEL_DIR) if LORA_MODEL_DIR.exists() else None
    if lora_dir:
        lora_path = Path(lora_dir)
        if not lora_path.is_absolute():
            lora_path = MODEL_DIR / lora_path
        if lora_path.exists():
            cmd = [
                str(SD_CLI),
                "--diffusion-model", str(DIFFUSION_MODEL),
                "--vae", str(VAE_MODEL),
                "--llm", str(LLM_MODEL),
                "--diffusion-fa",
                "--lora-model-dir", str(lora_path),
            ]
            if req.apply_lora and "<lora:" not in prompt:
                # Auto-append triggers for each safetensors/ckpt LoRA found in the dir.
                lora_triggers = []
                for lora_file in sorted(lora_path.glob("*.safetensors")) + sorted(lora_path.glob("*.ckpt")):
                    lora_name = lora_file.stem
                    lora_triggers.append(f"<lora:{lora_name}:{req.lora_scale:.2f}>")
                if lora_triggers:
                    prompt = f"{prompt} {', '.join(lora_triggers)}"
        else:
            cmd = [
                str(SD_CLI),
                "--diffusion-model", str(DIFFUSION_MODEL),
                "--vae", str(VAE_MODEL),
                "--llm", str(LLM_MODEL),
                "--diffusion-fa",
            ]
    else:
        cmd = [
            str(SD_CLI),
            "--diffusion-model", str(DIFFUSION_MODEL),
            "--vae", str(VAE_MODEL),
            "--llm", str(LLM_MODEL),
            "--diffusion-fa",
        ]

    cmd.extend([
        "-p", prompt,
        "-o", str(output_path),
        "-W", str(req.width),
        "-H", str(req.height),
        "--steps", str(req.steps),
        "--cfg-scale", str(req.cfg_scale),
        "--sampling-method", req.sampler,
        "--seed", str(seed),
        "-v",
    ])
    if init_path:
        cmd.extend(["--init-img", str(init_path), "--strength", str(req.strength)])
    return cmd


def _save_base64_image(data: str) -> Path:
    """Save a base64 image to a temporary file and return the path."""
    if "," in data:
        data = data.split(",", 1)[1]
    image_bytes = base64.b64decode(data)
    tmp_path = OUTPUT_DIR / f"init_{int(time.time())}_{random.randint(1000, 9999)}.png"
    with open(tmp_path, "wb") as f:
        f.write(image_bytes)
    return tmp_path


def _encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _run_generation(req: GenerateRequest, output_path: Path, progress_callback=None) -> Dict[str, Any]:
    """Run sd-cli and return generation metadata."""
    import re

    init_path = None
    if req.init_image:
        init_path = _save_base64_image(req.init_image)
    try:
        cmd = _build_command(req, output_path, init_path)
        start_time = time.time()

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=False,
            bufsize=0,
        )

        stdout_lines: list[str] = []
        stdout_buffer = b""
        progress_regex = re.compile(r"\[\s*=+\s*\]\s*(\d+)\/(\d+)")

        def emit_progress(step: int, total: int) -> None:
            if total <= 0:
                return
            percent = int(step / total * 100)
            if progress_callback:
                progress_callback({"type": "progress", "percent": percent})

        try:
            if proc.stdout:
                while True:
                    chunk = proc.stdout.read(4096)
                    if not chunk:
                        break
                    stdout_buffer += chunk
                    # sd-cli использует \r для обновления прогресса в одной строке,
                    # нормализуем в \n чтобы разбить на отдельные события.
                    normalized = stdout_buffer.replace(b"\r", b"\n")
                    parts = normalized.split(b"\n")
                    stdout_buffer = parts.pop()
                    for part in parts:
                        text = part.decode("utf-8", errors="replace").rstrip()
                        if not text:
                            continue
                        stdout_lines.append(text)
                        match = progress_regex.search(text)
                        if match:
                            emit_progress(int(match.group(1)), int(match.group(2)))
                        if progress_callback:
                            progress_callback({"type": "log", "line": text})

                # Хвост буфера
                if stdout_buffer:
                    text = stdout_buffer.decode("utf-8", errors="replace").rstrip()
                    if text:
                        stdout_lines.append(text)
                        match = progress_regex.search(text)
                        if match:
                            emit_progress(int(match.group(1)), int(match.group(2)))
                        if progress_callback:
                            progress_callback({"type": "log", "line": text})
        finally:
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        elapsed = time.time() - start_time

        if proc.returncode != 0:
            log_tail = "\n".join(stdout_lines[-30:])
            raise RuntimeError(f"sd-cli failed (code {proc.returncode}):\n{log_tail}")

        if not output_path.exists():
            raise RuntimeError("sd-cli finished but output image was not created")

        if progress_callback:
            progress_callback({"type": "progress", "percent": 100})

        return {
            "path": str(output_path),
            "seed": req.seed,
            "elapsed_seconds": round(elapsed, 2),
        }
    finally:
        if init_path and init_path.exists():
            try:
                init_path.unlink()
            except Exception:
                pass


@app.get("/health", response_model=HealthResponse)
def health():
    error = _check_setup()
    if error:
        raise HTTPException(status_code=503, detail=error)
    return HealthResponse(
        ok=True,
        sd_cli=SD_CLI,
        diffusion_model=str(DIFFUSION_MODEL),
        vae_model=str(VAE_MODEL),
        llm_model=str(LLM_MODEL),
        lora_model_dir=str(LORA_MODEL_DIR),
        output_dir=str(OUTPUT_DIR),
        img2img=True,
    )


@app.post("/generate")
def generate(req: GenerateRequest):
    error = _check_setup()
    if error:
        raise HTTPException(status_code=503, detail=error)

    output_name = f"generated_{int(time.time())}_{random.randint(1000, 9999)}.png"
    output_path = OUTPUT_DIR / output_name

    try:
        meta = _run_generation(req, output_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "success": True,
        "image_base64": _encode_image(output_path),
        "mime_type": "image/png",
        **meta,
    }


@app.post("/generate/stream")
def generate_stream(req: GenerateRequest):
    error = _check_setup()
    if error:
        raise HTTPException(status_code=503, detail=error)

    output_name = f"generated_{int(time.time())}_{random.randint(1000, 9999)}.png"
    output_path = OUTPUT_DIR / output_name

    def event_stream():
        queue: list[Dict[str, Any]] = []
        done = threading.Event()

        def on_progress(event: Dict[str, Any]):
            queue.append(event)

        def worker():
            try:
                queue.append({"type": "status", "message": "Загрузка моделей..."})
                meta = _run_generation(req, output_path, progress_callback=on_progress)
                queue.append({"type": "status", "message": "Готово"})
                queue.append({
                    "type": "result",
                    "image_base64": _encode_image(output_path),
                    "mime_type": "image/png",
                    **meta,
                })
            except Exception as exc:
                queue.append({"type": "error", "message": str(exc)})
            finally:
                done.set()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while not done.is_set() or queue:
            while queue:
                item = queue.pop(0)
                yield f"data: {_json_line(item)}\n\n"
            if not done.is_set():
                time.sleep(0.1)

        yield f"data: {_json_line({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _json_line(obj: Dict[str, Any]) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("JARVIS_IMAGE_PORT", "8081"))
    host = os.environ.get("JARVIS_IMAGE_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port)
