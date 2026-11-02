"""Check and install official Apple Silicon llama.cpp prerelease builds."""

from __future__ import annotations

import hashlib
import json
import html
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import urllib.request
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional

import config_manager


REPOSITORY = "ggml-org/llama.cpp"
BASE_DIR = Path(__file__).resolve().parent
RUNTIME_ROOT = BASE_DIR / "runtime" / "llama.cpp"
_UPDATE_LOCK = threading.Lock()


def _asset_for_platform() -> Optional[str]:
    if platform.system() == "Darwin" and platform.machine().lower() in {"arm64", "aarch64"}:
        return "macos-arm64"
    return None


def _get_config_and_active_server() -> tuple[Dict[str, Any], Dict[str, Any], str]:
    config = config_manager.read_config() or {}
    presets = config.get("presets") or []
    active_index = int(config.get("active_preset_index", 0) or 0)
    if not presets:
        raise RuntimeError("В JARVIS пока нет настроенного пресета с llama-server.")
    if active_index < 0 or active_index >= len(presets):
        active_index = 0
    active = presets[active_index]
    if str(active.get("backend", "llama-server")).lower() != "llama-server":
        active = next((p for p in presets if str(p.get("backend", "llama-server")).lower() == "llama-server"), None)
    if not active:
        raise RuntimeError("Не найден пресет JARVIS на базе llama-server.")
    raw_path = str(active.get("llama_server_path") or "").strip()
    if not raw_path:
        raise RuntimeError("В активном пресете не указан путь к llama-server.")
    path = os.path.abspath(os.path.expanduser(raw_path))
    lowered = path.lower().replace("\\", "/")
    if any(marker in lowered for marker in ("llama.cpp-prism", "llama.cpp-k2horizon", "llama.cpp-k2", "llama-server-custom")):
        raise RuntimeError("Активный пресет использует специальную сборку llama.cpp; автоматическую замену для неё отключил.")
    if not ("llama.cpp" in lowered or str(RUNTIME_ROOT).lower() in lowered):
        raise RuntimeError("Автообновление включено только для upstream llama.cpp, не для стороннего llama-server.")
    return config, active, path


def _server_version(binary: str) -> Dict[str, str]:
    path = Path(binary)
    if not path.is_file():
        return {"version": "не найден", "build": ""}
    result = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=15, check=False)
    output = (result.stdout or result.stderr or "").strip()
    match = (
        re.search(r"build\s+(\d+)\b", output, flags=re.IGNORECASE)
        or re.search(r"version:\s*b(\d+)\b", output, flags=re.IGNORECASE)
        or re.search(r"version:\s*(\d+)\b", output, flags=re.IGNORECASE)
        or re.search(r"\bb(\d+)\b", output, flags=re.IGNORECASE)
    )
    return {"version": f"b{match.group(1)}" if match else (output.splitlines()[0][:100] if output else "неизвестно"), "build": match.group(1) if match else ""}


def _latest_prerelease() -> Dict[str, Any]:
    arch = _asset_for_platform()
    if not arch:
        raise RuntimeError("Поиск и установка сборок настроены для Mac с Apple Silicon.")
    feed_url = f"https://github.com/{REPOSITORY}/releases.atom"
    feed_request = urllib.request.Request(feed_url, headers={"User-Agent": "Mozilla/5.0 JarvisDesktop"})
    try:
        with urllib.request.urlopen(feed_request, timeout=12) as response:
            feed = response.read().decode("utf-8", "replace")
    except Exception as exc:
        raise RuntimeError(f"Не удалось получить список сборок llama.cpp с GitHub: {exc}") from exc

    tags = re.findall(r"<title>\s*(b\d{4,})\s*(?::.*?)?</title>", feed, flags=re.IGNORECASE)
    for tag in tags:
        assets_url = f"https://github.com/{REPOSITORY}/releases/expanded_assets/{tag}"
        assets_request = urllib.request.Request(assets_url, headers={"User-Agent": "Mozilla/5.0 JarvisDesktop"})
        try:
            with urllib.request.urlopen(assets_request, timeout=8) as response:
                assets_html = response.read().decode("utf-8", "replace")
        except Exception:
            continue
        for href, link_text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', assets_html, flags=re.DOTALL | re.IGNORECASE):
            name = html.unescape(re.sub(r"<[^>]+>", " ", link_text)).strip()
            if name.endswith(f"{arch}.tar.gz"):
                if href.startswith("/"):
                    href = f"https://github.com{href}"
                asset = {"name": name, "browser_download_url": href, "size": None, "digest": None}
                release = {"tag_name": tag, "html_url": f"https://github.com/{REPOSITORY}/releases/tag/{tag}", "published_at": None}
                return {"release": release, "asset": asset}
    raise RuntimeError("Не удалось найти macOS arm64 пакет среди последних prerelease-сборок llama.cpp.")


def _lookup_asset_digest(tag: str, asset_name: str) -> Optional[str]:
    """Ask GitHub for an asset digest when its API rate limit permits."""
    url = f"https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}"
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "JarvisDesktop/llama-runtime"})
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            release = json.load(response)
        asset = next((item for item in release.get("assets", []) if item.get("name") == asset_name), None)
        return asset.get("digest") if asset else None
    except Exception:
        return None


def check_for_update() -> Dict[str, Any]:
    config, active, current_path = _get_config_and_active_server()
    local = _server_version(current_path)
    latest = _latest_prerelease()
    release = latest["release"]
    tag = str(release.get("tag_name", ""))
    latest_build_match = re.search(r"(\d+)$", tag)
    latest_build = latest_build_match.group(1) if latest_build_match else ""
    current_number = int(local["build"] or 0)
    latest_number = int(latest_build or 0)
    return {
        "ok": True,
        "supported": True,
        "available": bool(latest_number and latest_number > current_number),
        "current_version": local["version"],
        "latest_version": tag,
        "current_build": local["build"],
        "latest_build": latest_build,
        "release_url": release.get("html_url", f"https://github.com/{REPOSITORY}/releases"),
        "published_at": release.get("published_at"),
        "asset_name": latest["asset"].get("name"),
        "asset_size": latest["asset"].get("size"),
        "server_path": current_path,
        "preset_name": active.get("name", "llama-server"),
    }


def _download_asset(asset: Dict[str, Any], archive_path: Path) -> None:
    request = urllib.request.Request(
        asset["browser_download_url"],
        headers={"User-Agent": "JarvisDesktop/llama-runtime"},
    )
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response, archive_path.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            output.write(chunk)
    expected = str(asset.get("digest") or "")
    if expected.startswith("sha256:") and digest.hexdigest().lower() != expected.split(":", 1)[1].lower():
        archive_path.unlink(missing_ok=True)
        raise RuntimeError("SHA-256 загруженной сборки не совпал с данными GitHub.")


def _extract_release(archive_path: Path, release_tag: str, stage: Path) -> Path:
    with tarfile.open(archive_path, "r:gz") as bundle:
        for member in bundle.getmembers():
            member_path = PurePosixPath(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError("Архив сборки содержит недопустимый путь.")
            if member.issym() or member.islnk():
                linked = PurePosixPath(os.path.normpath(os.path.join(str(member_path.parent), member.linkname)))
                if linked.is_absolute() or ".." in linked.parts:
                    raise RuntimeError("Архив сборки содержит недопустимую ссылку.")
            if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
                raise RuntimeError("Архив сборки содержит неподдерживаемый тип файла.")
        if sys.version_info >= (3, 12):
            bundle.extractall(stage, filter="data")
        else:
            bundle.extractall(stage)
    server = next(stage.rglob("llama-server"), None)
    if not server or not server.is_file():
        raise RuntimeError("В загруженной сборке не найден llama-server.")
    server.chmod(server.stat().st_mode | 0o111)
    version = _server_version(str(server))
    if not version["build"] or version["build"] != re.search(r"(\d+)$", release_tag).group(1):
        raise RuntimeError(f"Сборка из архива не соответствует ожидаемой версии {release_tag}: {version['version']}.")
    return server.parent


def install_latest() -> Dict[str, Any]:
    if not _UPDATE_LOCK.acquire(blocking=False):
        raise RuntimeError("Обновление llama.cpp уже выполняется.")
    try:
        status = check_for_update()
        latest = _latest_prerelease()
        release, asset = latest["release"], latest["asset"]
        tag = str(release["tag_name"])
        if not status["available"]:
            return {"ok": True, "updated": False, "message": "Установлена актуальная prerelease-сборка.", **status}

        RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
        version_dir = RUNTIME_ROOT / tag
        if not (version_dir / "llama-server").is_file():
            stage = RUNTIME_ROOT / f".staging-{uuid.uuid4().hex}"
            stage.mkdir()
            archive_path = stage / asset["name"]
            try:
                asset["digest"] = _lookup_asset_digest(tag, asset["name"])
                _download_asset(asset, archive_path)
                unpack_root = stage / "unpacked"
                unpack_root.mkdir()
                extracted_root = _extract_release(archive_path, tag, unpack_root)
                target_stage = stage / "payload"
                extracted_root.rename(target_stage)
                if version_dir.exists():
                    shutil.rmtree(version_dir)
                target_stage.rename(version_dir)
            finally:
                shutil.rmtree(stage, ignore_errors=True)

        installed_version = _server_version(str(version_dir / "llama-server"))
        if installed_version["build"] != status["latest_build"]:
            raise RuntimeError("Установленный бинарник не прошёл проверку версии.")

        config, _active, source_path = _get_config_and_active_server()
        stable_link = RUNTIME_ROOT / "current"
        temp_link = RUNTIME_ROOT / f".current-{uuid.uuid4().hex}"
        temp_link.symlink_to(tag)
        if stable_link.is_symlink():
            stable_link.unlink()
        elif stable_link.exists():
            raise RuntimeError(f"Не удалось безопасно заменить путь установки: {stable_link}")
        os.replace(temp_link, stable_link)
        target_path = str(stable_link / "llama-server")

        changed = 0
        for preset in config.get("presets", []):
            if str(preset.get("backend", "llama-server")).lower() != "llama-server":
                continue
            saved_path = os.path.abspath(os.path.expanduser(str(preset.get("llama_server_path") or "")))
            if saved_path == source_path:
                preset["llama_server_path"] = target_path
                changed += 1
        if changed:
            config_path = config_manager.CONFIG_FILE
            backup_path = config_path.with_suffix(config_path.suffix + ".bak")
            shutil.copy2(config_path, backup_path)
            temp_config = config_path.with_suffix(config_path.suffix + ".tmp")
            temp_config.write_text(json.dumps(config, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(temp_config, config_path)
        return {
            "ok": True,
            "updated": True,
            "latest_version": tag,
            "installed_path": target_path,
            "updated_presets": changed,
            "restart_required": True,
            "message": f"{tag} установлена. Перезапустите JARVIS, чтобы использовать обновлённый сервер.",
        }
    finally:
        _UPDATE_LOCK.release()
