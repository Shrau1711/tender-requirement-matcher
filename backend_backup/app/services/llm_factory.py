from __future__ import annotations

from pathlib import Path

from app.services.gemini import GeminiLLM
from app.services.llm_cache import CachedLLM

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "llm"  # backend/.cache/llm


def make_llm() -> CachedLLM:
    """The model every script and job should use: Gemini, with caching and call counting."""
    return CachedLLM(GeminiLLM(), CACHE_DIR)