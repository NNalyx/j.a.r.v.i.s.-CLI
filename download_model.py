import os
from huggingface_hub import hf_hub_download

repo_id = "Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-GGUF"
filename = "Qwen3.5-27B.Q4_K_M.gguf"
local_dir = "/Users/roma/models/qwen35"
os.makedirs(local_dir, exist_ok=True)

print(f"Downloading {filename} from {repo_id}...")
print(f"Target: {local_dir}")

path = hf_hub_download(
    repo_id=repo_id,
    filename=filename,
    local_dir=local_dir,
    local_dir_use_symlinks=False,
    resume_download=True,
)
print(f"Done: {path}")
