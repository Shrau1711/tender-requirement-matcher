from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # backend/.env, if it exists


def gemini_key() -> tuple[str, str]:
    """(name, key) for the key chosen by LLM_KEY_IN_USE, e.g. PERSONAL or MENTOR. A plain GEMINI_API_KEY works when no name is chosen."""
    name = os.environ.get("LLM_KEY_IN_USE", "")
    if not name and os.environ.get("GEMINI_API_KEY"):
        return "GEMINI_API_KEY", os.environ["GEMINI_API_KEY"]
    key = os.environ.get(f"GEMINI_KEY_{name}")
    if not key:
        raise RuntimeError("Set GEMINI_API_KEY, or LLM_KEY_IN_USE and a matching GEMINI_KEY_<NAME>, in backend/.env or the environment")
    return name, key


def number_setting(name: str, default: int) -> int:
    """A whole-number setting that can be overridden in backend/.env or the environment, e.g. LLM_MAX_CALLS=600."""
    return int(os.environ.get(name, default))


def path_setting(name: str, default: Path) -> Path:
    """A folder that can be moved with an environment variable, e.g. CATEGORIES_DIR, so a container can mount its own data."""
    return Path(os.environ.get(name, default))


def cache_dir() -> Path:
    """Where answers from the model and computed embeddings are kept. Move it with CACHE_DIR, e.g. to a mounted volume, so it survives a container being replaced."""
    return path_setting("CACHE_DIR", Path(__file__).resolve().parents[1] / ".cache")
