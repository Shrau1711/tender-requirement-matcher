from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # backend/.env, if it exists


def gemini_key() -> tuple[str, str]:
    """(name, key) for the key chosen by LLM_KEY_IN_USE, e.g. PERSONAL or MENTOR."""
    name = os.environ.get("LLM_KEY_IN_USE", "")
    key = os.environ.get(f"GEMINI_KEY_{name}")
    if not key:
        raise RuntimeError("Set LLM_KEY_IN_USE and a matching GEMINI_KEY_<NAME> in backend/.env")
    return name, key