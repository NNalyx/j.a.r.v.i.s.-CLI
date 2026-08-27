#!/usr/bin/env python3
"""Бенчмарк скорости Fable с MTP depth 2 vs 3."""
import json
import subprocess
import time
import urllib.request
import urllib.error
import os
import signal

MODEL = "/Users/roma/models/fable/Qwen3.6-27B-Fable-Fus-711-UnHeretic-NM-DAU-NEO-MAX-NEO-MTP-Q4_K_M.gguf"
MMPROJ = "/Users/roma/models/fable/mmproj-BF16.gguf"
TEMPLATE = "/Users/roma/PycharmProjects/llama.cpp/models/templates/Qwen3.5-4B.jinja"
SERVER = "/Users/roma/PycharmProjects/llama.cpp/build/bin/llama-server"
PORT = 9999
HOST = "127.0.0.1"
CONTEXT = 4096  # тестовый контекст, чтобы быстро загрузилось
NG_LAYERS = 99

PROMPTS = [
    ("short", "Привет, как дела?"),
    ("medium", "Напиши подробное сравнение Python и JavaScript для веб-разработки." * 3),
    ("long", "Объясни принципы работы трансформеров в машинном обучении, приведи примеры архитектур." * 10),
]


def kill_servers():
    subprocess.run(["pkill", "-9", "-f", "llama-server"], capture_output=True)
    time.sleep(1)


def start_server(mtp_depth):
    kill_servers()
    cmd = [
        SERVER,
        "-m", MODEL,
        "--mmproj", MMPROJ,
        "--chat-template-file", TEMPLATE,
        "-c", str(CONTEXT),
        "-ngl", str(NG_LAYERS),
        "--host", HOST,
        "--port", str(PORT),
    ]
    if mtp_depth is not None:
        cmd.extend(["--spec-type", "draft-mtp", "--spec-draft-n-max", str(mtp_depth)])
        print(f"\n[Запуск] MTP depth={mtp_depth}")
    else:
        print("\n[Запуск] MTP отключен")
    print(" ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )
    # Ждем готовности
    for attempt in range(120):
        try:
            with urllib.request.urlopen(f"http://{HOST}:{PORT}/health", timeout=2) as resp:
                if resp.status == 200:
                    print(f"[Готов] сервер запущен за {attempt + 1} сек")
                    return proc
        except Exception:
            pass
        time.sleep(1)
        # выводим последние логи
        if attempt % 10 == 0 and proc.poll() is not None:
            out, _ = proc.communicate()
            print(out[-2000:])
            raise RuntimeError("Сервер упал при запуске")
    raise RuntimeError("Таймаут запуска сервера")


def benchmark_prompt(name: str, prompt: str, mtp_depth: int):
    payload = json.dumps({
        "prompt": prompt,
        "n_predict": 128,
        "temperature": 0.7,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"http://{HOST}:{PORT}/completion",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Ошибка] {name}: {e}")
        return None
    elapsed = time.time() - start
    timings = data.get("timings", {})
    prompt_tok = timings.get("prompt_n", 0)
    gen_tok = timings.get("predicted_n", 0)
    prompt_tps = timings.get("prompt_per_second", 0)
    gen_tps = timings.get("predicted_per_second", 0)
    return {
        "mtp_depth": mtp_depth,
        "prompt": name,
        "prompt_tokens": prompt_tok,
        "gen_tokens": gen_tok,
        "elapsed_sec": round(elapsed, 2),
        "prompt_tps": round(prompt_tps, 2),
        "gen_tps": round(gen_tps, 2),
    }


def run_benchmark(mtp_depth: int):
    proc = start_server(mtp_depth)
    try:
        results = []
        for name, prompt in PROMPTS:
            print(f"[Тест] {name} ({len(prompt)} chars)")
            res = benchmark_prompt(name, prompt, mtp_depth)
            if res:
                results.append(res)
                print(f"  -> prompt {res['prompt_tps']} t/s | gen {res['gen_tps']} t/s | {res['elapsed_sec']} sec")
            time.sleep(1)
        return results
    finally:
        print("[Остановка] сервер")
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        kill_servers()


def main():
    all_results = []
    for depth in (None, 2, 3):
        try:
            results = run_benchmark(depth)
            all_results.extend(results)
        except Exception as e:
            label = "off" if depth is None else depth
            print(f"[FAIL] MTP {label}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 70)
    print(f"{'MTP':>4} {'Prompt':>8} {'Prompt t/s':>12} {'Gen t/s':>12} {'Elapsed':>10}")
    for r in all_results:
        label = "off" if r['mtp_depth'] is None else r['mtp_depth']
        print(f"{label:>4} {r['prompt']:>8} {r['prompt_tps']:>12} {r['gen_tps']:>12} {r['elapsed_sec']:>10}")


if __name__ == "__main__":
    main()
