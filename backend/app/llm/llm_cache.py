from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from pathlib import Path

from app.config import number_setting
from app.llm.llm import LLM, Reply

MAX_CALLS = number_setting("LLM_MAX_CALLS", 400)  # real model calls allowed per run; a safety net against runaway loops


def shipped_path(seed_dir: Path, name: str) -> Path:
    """Where a shipped answer lives: in a subfolder named by the first two characters of its name, so no folder holds hundreds of files."""
    return seed_dir / name[:2] / name


class CachedLLM:
    """Wraps any LLM: repeats of a request are answered from disk, and real calls are counted."""

    def __init__(self, inner: LLM, cache_dir: Path, max_calls: int = MAX_CALLS, seed_dir: Path | None = None) -> None:
        """seed_dir holds answers shipped with the code (read only): looked at when the live cache has none."""
        self.inner, self.cache_dir, self.max_calls, self.seed_dir = inner, cache_dir, max_calls, seed_dir
        self.lock = threading.Lock()  # calls may come from several threads
        self.calls = self.hits = self.input_tokens = self.output_tokens = 0
        self.used: set[Path] = set()  # the saved answers this run read or wrote, so a run's answers can be exported
        cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, system: str, user: str) -> Path:
        model, settings = getattr(self.inner, "model", ""), getattr(self.inner, "settings", "")
        digest = hashlib.sha256(f"{model}\x00{settings}\x00{system}\x00{user}".encode()).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def saved(self, system: str, user: str) -> Path | None:
        """Where the answer to this request is already saved: the live cache first, then the answers shipped with the code. None if it is nowhere."""
        path = self.path_for(system, user)
        return next((p for p in (path, shipped_path(self.seed_dir, path.name) if self.seed_dir else None) if p and p.exists()), None)

    def has(self, system: str, user: str) -> bool:
        return self.saved(system, user) is not None

    def generate(self, system: str, user: str) -> Reply:
        return self.cached(system, user, lambda: self.inner.generate(system, user))

    def transcribe(self, png: bytes, prompt: str) -> Reply:
        """The text on a page picture. The picture's fingerprint stands in for the user prompt in the cache key."""
        return self.cached(prompt, hashlib.sha256(png).hexdigest(), lambda: self.inner.transcribe(png, prompt))

    def cached(self, system: str, user: str, call: Callable[[], Reply]) -> Reply:
        path = self.path_for(system, user)
        saved = self.saved(system, user)
        if saved:
            with self.lock:
                self.hits += 1
                self.used.add(saved)
            return Reply.model_validate_json(saved.read_text(encoding="utf-8"))
        with self.lock:
            if self.calls >= self.max_calls:
                raise RuntimeError(f"Stopped after {self.calls} real model calls (limit {self.max_calls}).")
            self.calls += 1
        reply = call()
        with self.lock:
            self.input_tokens += reply.input_tokens
            self.output_tokens += reply.output_tokens
        path.write_text(reply.model_dump_json(), encoding="utf-8")
        with self.lock:
            self.used.add(path)
        return reply

    def summary(self) -> str:
        return (f"model calls {self.calls}, from cache {self.hits}, "
                f"tokens in {self.input_tokens} / out {self.output_tokens}")
