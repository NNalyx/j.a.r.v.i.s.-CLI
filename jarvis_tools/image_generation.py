"""Image generation tool using the local stable-diffusion.cpp server."""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

from jarvis_core.types import ToolResult
from jarvis_core import state


IMAGE_SERVER_HOST = os.environ.get("JARVIS_IMAGE_HOST", "127.0.0.1")
IMAGE_SERVER_PORT = int(os.environ.get("JARVIS_IMAGE_PORT", "8081"))
IMAGE_SERVER_URL = f"http://{IMAGE_SERVER_HOST}:{IMAGE_SERVER_PORT}"


def _report_image_progress(percent: int) -> None:
    """Relay image generation progress to the active web stream bridge if available."""
    handler = getattr(state, "image_progress_handler", None)
    tool_call_id = getattr(state, "current_tool_call_id", None)
    if handler and tool_call_id:
        try:
            handler(tool_call_id, int(percent))
        except Exception:
            pass


def _server_available(timeout: float = 2.0) -> bool:
    """Check whether the image generation server is reachable."""
    try:
        req = urllib.request.Request(
            f"{IMAGE_SERVER_URL}/health",
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _ensure_server_running() -> Optional[str]:
    """Start the image server if it isn't already running."""
    if _server_available():
        return None

    base_dir = Path(__file__).resolve().parent.parent
    server_script = base_dir / "jarvis_image_server.py"
    if not server_script.exists():
        return f"Image server script not found: {server_script}"

    env = os.environ.copy()
    env["JARVIS_IMAGE_HOST"] = IMAGE_SERVER_HOST
    env["JARVIS_IMAGE_PORT"] = str(IMAGE_SERVER_PORT)

    subprocess.Popen(
        [str(Path(sys.executable).resolve()), str(server_script)],
        cwd=str(base_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Wait for the server to come up.
    deadline = time.time() + 30.0
    while time.time() < deadline:
        if _server_available():
            return None
        time.sleep(0.5)

    return "Image server failed to start within 30 seconds"


def generate_image(
    prompt: str,
    width: int = 512,
    height: int = 512,
    steps: int = 4,
    cfg_scale: float = 1.0,
    seed: int = -1,
    input_image: Optional[str] = None,
    strength: float = 0.75,
    lora_model_dir: Optional[str] = None,
    lora_scale: float = 1.0,
    apply_lora: bool = True,
) -> ToolResult:
    """Generate or transform an image using the local Krea-2 server.

    Args:
        prompt: Text description of the image to generate or transform.
        width: Image width in pixels (multiple of 64, 256-2048).
        height: Image height in pixels (multiple of 64, 256-2048).
        steps: Number of diffusion steps (1-50). Krea-2 Turbo works well with 4-8.
        cfg_scale: Classifier-free guidance scale (0-30). Use 1.0 for distilled/turbo models.
        seed: Random seed, -1 for random.
        input_image: Path to an existing image or base64 data URL for img2img.
        strength: How much to change the input image, 0.0-1.0 (default 0.75).
        lora_model_dir: Directory with LoRA weights. None lets the server use its default.
        lora_scale: LoRA strength when auto-applying triggers.
        apply_lora: Whether to auto-append LoRA triggers to the prompt.
    """
    if not prompt or not prompt.strip():
        return ToolResult(False, None, "Prompt is empty")

    error = _ensure_server_running()
    if error:
        return ToolResult(False, None, error)

    init_image_b64 = None
    if input_image:
        if input_image.startswith("data:image/"):
            init_image_b64 = input_image
        elif os.path.isfile(input_image):
            try:
                with open(input_image, "rb") as f:
                    raw = f.read()
                mime = "image/png"
                ext = os.path.splitext(input_image)[1].lower()
                if ext in (".jpg", ".jpeg"):
                    mime = "image/jpeg"
                elif ext == ".webp":
                    mime = "image/webp"
                init_image_b64 = f"data:{mime};base64,{base64.b64encode(raw).decode('utf-8')}"
            except Exception as exc:
                return ToolResult(False, None, f"Failed to read input image: {exc}")
        else:
            return ToolResult(False, None, f"Input image not found: {input_image}")

    payload = {
        "prompt": prompt.strip(),
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "seed": seed,
    }
    if lora_model_dir is not None:
        payload["lora_model_dir"] = lora_model_dir
        payload["lora_scale"] = lora_scale
        payload["apply_lora"] = apply_lora
    if init_image_b64:
        payload["init_image"] = init_image_b64
        payload["strength"] = max(0.0, min(1.0, strength))

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{IMAGE_SERVER_URL}/generate/stream",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        result_data = None
        error_message = None
        with urllib.request.urlopen(req, timeout=600.0) as resp:
            buffer = b""
            while True:
                chunk = resp.read(1024)
                if not chunk:
                    break
                buffer += chunk
                while b"\n\n" in buffer:
                    event_block, _, buffer = buffer.partition(b"\n\n")
                    for line in event_block.split(b"\n"):
                        if not line.startswith(b"data: "):
                            continue
                        try:
                            event = json.loads(line[6:].decode("utf-8"))
                        except Exception:
                            continue
                        etype = event.get("type")
                        if etype == "progress":
                            _report_image_progress(event.get("percent", 0))
                        elif etype == "result":
                            result_data = event
                        elif etype == "error":
                            error_message = event.get("message", "Unknown error")
                        elif etype == "done":
                            break
    except Exception as exc:
        return ToolResult(False, None, f"Image generation request failed: {exc}")

    if error_message:
        return ToolResult(False, None, f"Image generation failed: {error_message}")
    if not result_data:
        return ToolResult(False, None, "Image generation produced no result")

    image_base64 = result_data.get("image_base64")
    if not image_base64:
        return ToolResult(False, None, "No image returned from server")

    # Save the returned image to a persistent file.
    output_dir = Path(__file__).resolve().parent.parent / "jarvis_agent_images"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"jarvis_gen_{int(time.time())}_{seed if seed >= 0 else 'rnd'}.png"
    output_path = output_dir / filename
    try:
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(image_base64))
    except Exception as exc:
        return ToolResult(False, None, f"Failed to save image: {exc}")

    return ToolResult(True, {
        "path": str(output_path),
        "width": width,
        "height": height,
        "seed": result_data.get("seed", seed),
        "elapsed_seconds": result_data.get("elapsed_seconds"),
        "message": f"Image saved: {output_path}",
    })
