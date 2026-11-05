from __future__ import annotations

from pathlib import Path

from app.config import cache_dir, path_setting
from app.llm.gemini import GeminiLLM, cache_settings
from app.llm.llm import Reply
from app.llm.llm_cache import CachedLLM

CACHE_DIR = cache_dir() / "llm"  # backend/.cache/llm unless CACHE_DIR says otherwise
SEED_DIR = path_setting("SEED_CACHE_DIR", Path(__file__).resolve().parents[3] / "data" / "demo_cache")  # answers shipped with the code (see scripts.cost.export_demo_cache)


def make_llm() -> CachedLLM:
    """The model every script and job should use: Gemini, with caching and call counting."""
    return CachedLLM(GeminiLLM(), CACHE_DIR, seed_dir=SEED_DIR)


class SavedOnly:
    """Stands in for Gemini where only saved answers may be used: the same model and settings, so the same cache keys,
    but no key is needed and nothing is ever asked."""

    def __init__(self) -> None:
        self.model, self.settings = cache_settings()

    def generate(self, system: str, user: str) -> Reply:
        raise RuntimeError("This answer is not saved, and nothing here may ask the model.")

    def transcribe(self, png: bytes, prompt: str) -> Reply:
        raise RuntimeError("This page's reading is not saved, and nothing here may ask the model.")


def saved_answers_only() -> CachedLLM:
    """Saved answers only, with no model call possible (the call limit is 0 as well): for showing what was already read."""
    return CachedLLM(SavedOnly(), CACHE_DIR, max_calls=0, seed_dir=SEED_DIR)
