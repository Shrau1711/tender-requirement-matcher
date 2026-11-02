from __future__ import annotations

from pathlib import Path

from app.config import cache_dir, path_setting
from app.llm.gemini import GeminiLLM
from app.llm.llm_cache import CachedLLM

CACHE_DIR = cache_dir() / "llm"  # backend/.cache/llm unless CACHE_DIR says otherwise
SEED_DIR = path_setting("SEED_CACHE_DIR", Path(__file__).resolve().parents[3] / "data" / "demo_cache")  # answers shipped with the code (see scripts.cost.export_demo_cache)


def make_llm() -> CachedLLM:
    """The model every script and job should use: Gemini, with caching and call counting."""
    return CachedLLM(GeminiLLM(), CACHE_DIR, seed_dir=SEED_DIR)
