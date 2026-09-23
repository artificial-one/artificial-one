#!/usr/bin/env python3
"""Install the pinned, checksum-verified free edge model and llama.cpp runtime."""

from __future__ import annotations

import argparse
from hashlib import sha256
import os
from pathlib import Path
import shutil
import subprocess
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / ".edge-ai"
MODEL_PATH = CACHE_DIR / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
MODEL_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
    "qwen2.5-1.5b-instruct-q4_k_m.gguf?download=true"
)
MODEL_SHA256 = "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
LLAMA_REPOSITORY = "https://github.com/ggml-org/llama.cpp.git"
LLAMA_REF = "b10982"
LLAMA_COMMIT_PREFIX = "fc82583"
LLAMA_SOURCE = CACHE_DIR / "llama.cpp"
LLAMA_CLI = LLAMA_SOURCE / "build" / "bin" / "llama-cli"


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model(path: Path = MODEL_PATH) -> bool:
    return path.is_file() and file_sha256(path) == MODEL_SHA256


def download_model() -> None:
    if verify_model():
        return
    MODEL_PATH.unlink(missing_ok=True)
    temporary = MODEL_PATH.with_suffix(".download")
    temporary.unlink(missing_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    request = Request(MODEL_URL, headers={"User-Agent": "Artificial.One-edge-model-installer/1.0"})
    with urlopen(request, timeout=120) as response, temporary.open("wb") as target:
        shutil.copyfileobj(response, target, length=8 * 1024 * 1024)
    if file_sha256(temporary) != MODEL_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("Downloaded edge model failed SHA-256 verification")
    os.replace(temporary, MODEL_PATH)


def run_checked(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def verify_llama_source() -> bool:
    if not (LLAMA_SOURCE / ".git").exists():
        return False
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=LLAMA_SOURCE,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip().casefold().startswith(LLAMA_COMMIT_PREFIX)


def build_llama() -> None:
    if LLAMA_CLI.is_file() and verify_llama_source():
        return
    if LLAMA_SOURCE.exists() and not verify_llama_source():
        raise RuntimeError("Cached llama.cpp source does not match the pinned release commit")
    if not LLAMA_SOURCE.exists():
        run_checked([
            "git", "clone", "--depth", "1", "--branch", LLAMA_REF,
            "--filter=blob:none", LLAMA_REPOSITORY, str(LLAMA_SOURCE),
        ])
    if not verify_llama_source():
        raise RuntimeError("Downloaded llama.cpp source does not match the pinned release commit")
    run_checked([
        "cmake", "-S", str(LLAMA_SOURCE), "-B", str(LLAMA_SOURCE / "build"),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DGGML_NATIVE=OFF", "-DLLAMA_CURL=OFF", "-DBUILD_SHARED_LIBS=OFF",
        "-DLLAMA_BUILD_TESTS=OFF", "-DLLAMA_BUILD_EXAMPLES=ON",
    ])
    run_checked([
        "cmake", "--build", str(LLAMA_SOURCE / "build"),
        "--config", "Release", "--target", "llama-cli", "-j", "2",
    ])
    if not LLAMA_CLI.is_file():
        raise FileNotFoundError(f"llama-cli build did not produce {LLAMA_CLI}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--model-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        if not verify_model() or not LLAMA_CLI.is_file() or not verify_llama_source():
            raise SystemExit("Edge AI cache is incomplete or failed verification")
    elif args.model_only:
        download_model()
    else:
        download_model()
        build_llama()
    runtime = "model verified" if args.model_only else f"model and llama.cpp {LLAMA_REF} ready"
    print(f"Edge AI {runtime}: Qwen2.5 1.5B Q4_K_M ({MODEL_SHA256[:12]}…)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
