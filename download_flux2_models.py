#!/usr/bin/env python3
"""Download FLUX.2-klein-4B model files one by one into /Users/roma/models/flux2-klein."""
import os
import sys
import time
from huggingface_hub import hf_hub_download

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

DEST_DIR = "/Users/roma/models/flux2-klein"
LOG_PATH = os.path.join(DEST_DIR, "download.log")

# Load HF token from huggingface-cli cache if available
_HF_TOKEN_PATH = os.path.expanduser("~/.cache/huggingface/token")
if os.path.exists(_HF_TOKEN_PATH) and not os.environ.get("HF_TOKEN"):
    try:
        with open(_HF_TOKEN_PATH, "r", encoding="utf-8") as _f:
            _token = _f.read().strip()
        if _token:
            os.environ["HF_TOKEN"] = _token
    except Exception:
        pass

FILES = [
    {
        "repo_id": "unsloth/FLUX.2-klein-4B-GGUF",
        "filename": "flux-2-klein-4b-Q8_0.gguf",
        "desc": "DiT (diffusion transformer) Q8_0",
    },
    {
        "repo_id": "ponpoke/flux2-klein-4b-uncensored-text-encoder",
        "filename": "flux2-klein-4b-uncensored-q4_k_m.gguf",
        "desc": "uncensored text encoder Q4_K_M",
    },
    {
        "repo_id": "ai-toolkit/flux2_vae",
        "filename": "ae.safetensors",
        "desc": "VAE",
    },
]


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def progress_callback(desc):
    pbar = None

    def inner(current, total):
        nonlocal pbar
        if total is None:
            return
        if pbar is None:
            pbar = tqdm(total=total, unit="B", unit_scale=True, desc=desc, ncols=80)
        pbar.update(current - pbar.n)
        if current >= total and pbar is not None:
            pbar.close()

    return inner


def download_one(repo_id, filename, desc):
    log(f"Starting: {desc} ({repo_id}/{filename})")
    try:
        path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=DEST_DIR,
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        size_gb = os.path.getsize(path) / (1024 ** 3)
        log(f"Finished: {desc} -> {path} ({size_gb:.2f} GB)")
        return True
    except Exception as e:
        log(f"FAILED: {desc} -> {e}")
        return False


def main():
    os.makedirs(DEST_DIR, exist_ok=True)
    log("=" * 60)
    log("FLUX.2-klein-4B download started")
    log(f"Destination: {DEST_DIR}")
    for item in FILES:
        ok = download_one(item["repo_id"], item["filename"], item["desc"])
        if not ok:
            log("Stopping because download failed.")
            sys.exit(1)
    log("All downloads complete.")


if __name__ == "__main__":
    main()
