"""MLX (macOS Apple Silicon) backend for Jarvis."""

import sys

IS_MLX_AVAILABLE = False
if sys.platform == "darwin":
    try:
        import mlx  # noqa: F401

        IS_MLX_AVAILABLE = True
    except Exception:
        IS_MLX_AVAILABLE = False
