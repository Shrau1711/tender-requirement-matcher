from __future__ import annotations

from app.config import cache_dir
from app.services.gemini import GeminiLLM
from app.services.llm_cache import CachedLLM

CACHE_DIR = cache_dir() / "llm"  # backend/.cache/llm unless CACHE_DIR says otherwise


def make_llm() -> CachedLLM:
    """The model every script and job should use: Gemini, with caching and call counting."""
    return CachedLLM(GeminiLLM(), CACHE_DIR)
