from __future__ import annotations

import sys
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")
BUSY = {429, 500, 502, 503, 504}  # the service is overloaded or briefly down; asking again later usually works
PERMANENT = ("spending cap", "billing")  # a 429 that waiting cannot cure: the project has used up its money


def retry(call: Callable[[], T], attempts: int = 6, wait: float = 2.0, sleep: Callable[[float], None] = time.sleep) -> T:
    """Run call, and when the service says it is busy, wait (2s, 4s, 8s ...) and ask again. Other errors pass straight through."""
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as error:
            if getattr(error, "code", None) not in BUSY or attempt == attempts or any(w in str(error).lower() for w in PERMANENT):
                raise
            pause = wait * 2 ** (attempt - 1)
            print(f"[llm] service busy ({error.code}), asking again in {pause:.0f}s", file=sys.stderr)
            sleep(pause)
    raise AssertionError("unreachable")
