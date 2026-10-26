"""Counting a question's input tokens before it is asked, for the budget and the cost estimate.

TOKEN_COUNTER chooses how:
- estimate (the default): characters / 4, the rule every estimate so far was made with. Free, no network, roughly right
  for English technical text.
- gemini: Gemini's own count_tokens for the model in use, which is exact. Counting is a request to Google, so it obeys
  LLM_MAX_CALLS like a model call: once this process has made that many counts, or if a count fails, the estimate is used.
Counting never changes a question, so it never changes which saved answers match.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from functools import cache

from app.config import text_setting
from app.llm.llm_cache import MAX_CALLS

TOKEN_COUNTER = text_setting("TOKEN_COUNTER", "estimate")
CHARS_PER_TOKEN = 4  # a rough rule for English technical text

Counter = Callable[[str, str], int]  # (system instructions, question) -> input tokens


def estimate(system: str, user: str) -> int:
    return (len(system) + len(user)) // CHARS_PER_TOKEN


class LimitedCounter:
    """Counts with `count` at most `limit` times, the same text once; after that, or on any error, it estimates."""

    def __init__(self, count: Counter, limit: int = MAX_CALLS) -> None:
        self.count, self.limit = count, limit
        self.lock = threading.Lock()
        self.used = 0   # counts asked for
        self.exact = 0  # counts that came back, so a report can say how many figures are exact
        self.known: dict[tuple[str, str], int] = {}

    def __call__(self, system: str, user: str) -> int:
        with self.lock:
            if (system, user) in self.known:
                return self.known[system, user]
            if self.used >= self.limit:
                return estimate(system, user)
            self.used += 1
        try:
            tokens = self.count(system, user)
        except Exception:  # noqa: BLE001 - a failed count must not stop a run; the estimate is a fine answer
            return estimate(system, user)
        with self.lock:
            self.known[system, user] = tokens
            self.exact += 1
        return tokens


@cache
def counter(name: str = TOKEN_COUNTER) -> Counter:
    if name == "estimate":
        return estimate
    if name == "gemini":
        from app.llm.gemini import GeminiLLM  # only needs a key when chosen

        return LimitedCounter(GeminiLLM().count_tokens)
    raise ValueError(f"Unknown token counter {name!r}. Choose estimate or gemini")


def count_tokens(system: str, user: str) -> int:
    return counter()(system, user)
