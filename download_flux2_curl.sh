#!/bin/bash
set -e

DEST_DIR="/Users/roma/models/flux2-klein"
LOG="$DEST_DIR/download.log"
TOKEN_FILE="$HOME/.cache/huggingface/token"
TOKEN=""

if [[ -f "$TOKEN_FILE" ]]; then
    TOKEN=$(cat "$TOKEN_FILE" | tr -d '[:space:]')
fi

mkdir -p "$DEST_DIR"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    echo "$msg" >> "$LOG"
}

log "============================================"
log "FLUX.2-klein-4B curl download started"
log "Destination: $DEST_DIR"

AUTH_HEADER=""
if [[ -n "$TOKEN" ]]; then
    AUTH_HEADER="Authorization: Bearer $TOKEN"
    log "HF token loaded"
else
    log "WARNING: no HF token found"
fi

download_one() {
    local url="$1"
    local out="$2"
    local desc="$3"

    log "Starting: $desc"
    log "URL: $url"

    if [[ -n "$AUTH_HEADER" ]]; then
        curl -L -C - \
            -H "$AUTH_HEADER" \
            --progress-bar \
            -o "$out.tmp" \
            "$url" 2>&1 | tee -a "$LOG"
    else
        curl -L -C - \
            --progress-bar \
            -o "$out.tmp" \
            "$url" 2>&1 | tee -a "$LOG"
    fi

    mv "$out.tmp" "$out"
    local size_gb
    size_gb=$(du -h "$out" | cut -f1)
    log "Finished: $desc -> $out ($size_gb)"
}

# 1. DiT
download_one \
    "https://huggingface.co/unsloth/FLUX.2-klein-4B-GGUF/resolve/main/flux-2-klein-4b-Q8_0.gguf" \
    "$DEST_DIR/flux-2-klein-4b-Q8_0.gguf" \
    "DiT Q8_0"

# 2. Text encoder
download_one \
    "https://huggingface.co/ponpoke/flux2-klein-4b-uncensored-text-encoder/resolve/main/flux2-klein-4b-uncensored-q4_k_m.gguf" \
    "$DEST_DIR/flux2-klein-4b-uncensored-q4_k_m.gguf" \
    "uncensored text encoder Q4_K_M"

# 3. VAE
download_one \
    "https://huggingface.co/ai-toolkit/flux2_vae/resolve/main/ae.safetensors" \
    "$DEST_DIR/ae.safetensors" \
    "VAE"

log "All downloads complete."
