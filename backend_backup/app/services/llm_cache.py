from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from pathlib import Path

from app.services.llm import LLM, Reply

MAX_CALLS = 300  # real model calls allowed per run; a safety net against runaway loops


class CachedLLM:
    """Wraps any LLM: repeats of a request are answered from disk, and real calls are counted."""

    def __init__(self, inner: LLM, cache_dir: Path, max_calls: int = MAX_CALLS) -> None:
        self.inner, self.cache_dir, self.max_calls = inner, cache_dir, max_calls
        self.lock = threading.Lock()  # calls may come from several threads
        self.calls = self.hits = self.input_tokens = self.output_tokens = 0
        cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, system: str, user: str) -> Path:
        model, settings = getattr(self.inner, "model", ""), getattr(self.inner, "settings", "")
        digest = hashlib.sha256(f"{model}\x00{settings}\x00{system}\x00{user}".encode()).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def generate(self, system: str, user: str) -> Reply:
        return self.cached(system, user, lambda: self.inner.generate(system, user))

    def transcribe(self, png: bytes, prompt: str) -> Reply:
        """The text on a page picture. The picture's fingerprint stands in for the user prompt in the cache key."""
        return self.cached(prompt, hashlib.sha256(png).hexdigest(), lambda: self.inner.transcribe(png, prompt))

    def cached(self, system: str, user: str, call: Callable[[], Reply]) -> Reply:
        path = self.path_for(system, user)
        if path.exists():
            with self.lock:
                self.hits += 1
            return Reply.model_validate_json(path.read_text(encoding="utf-8"))
        with self.lock:
            if self.calls >= self.max_calls:
                raise RuntimeError(f"Stopped after {self.calls} real model calls (limit {self.max_calls}).")
            self.calls += 1
        reply = call()
        with self.lock:
            self.input_tokens += reply.input_tokens
            self.output_tokens += reply.output_tokens
        path.write_text(reply.model_dump_json(), encoding="utf-8")
        return reply

    def summary(self) -> str:
        return (f"model calls {self.calls}, from cache {self.hits}, "
                f"tokens in {self.input_tokens} / out {self.output_tokens}")