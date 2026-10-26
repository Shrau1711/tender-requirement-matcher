"""Estimate what matching a tender would cost, before spending it.

Usage: python -m scripts.cost.estimate_cost <tender folder or pdf> <category_dir>

Reading the tender is real (and cached). Every question about a manufacturer's documents is counted, not asked.
Tokens are characters / 4; with TOKEN_COUNTER=gemini the new questions are also counted exactly (see app.cost.tokens).
The manufacturers' scanned pages are read the same way the real run reads them (already-read pages come from the cache), so the passages, and so the cache hits, match the real run.
"""
import sys
import threading

from app.chunking.corpus import manufacturers
from app.cost.tokens import CHARS_PER_TOKEN, TOKEN_COUNTER, count_tokens, counter
from app.extraction.evidence import TOP_K, evidence_table
from app.llm.llm import Reply
from app.llm.llm_cache import MAX_CALLS, CachedLLM
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import read_atoms
from app.reading.ocr import reader_for
from app.retrieval.queries import load_unit_views
from app.vectorstore.ingest import open_index


class DryRun:
    """Stands in for the model: notes what each question would cost and answers 'nothing found'."""

    def __init__(self, cache: CachedLLM) -> None:
        self.cache, self.lock = cache, threading.Lock()
        self.asked: list[tuple[bool, int]] = []  # (already cached, characters)
        self.counted: list[int] = []  # tokens of the new questions, when an exact counter is chosen

    def generate(self, system: str, user: str) -> Reply:
        cached = self.cache.has(system, user)
        tokens = count_tokens(system, user) if TOKEN_COUNTER != "estimate" and not cached else None
        with self.lock:
            self.asked.append((cached, len(system) + len(user)))
            if tokens is not None:
                self.counted.append(tokens)
        return Reply(text='{"findings": []}')


def main(tender: str, category_dir: str) -> None:
    llm = make_llm()
    read_image = reader_for(llm)
    atoms, _ = read_atoms(llm, tender, read_image)
    print(f"reading the tender and the scanned pages: {llm.summary()}")
    dry = DryRun(llm)
    evidence_table(dry, open_index(category_dir, read_image), atoms, manufacturers(category_dir), load_unit_views())
    new = [chars for cached, chars in dry.asked if not cached]
    print(f"\nreading the manufacturers' documents ({TOP_K} passages per question):")
    print(f"  {len(dry.asked)} questions, {len(dry.asked) - len(new)} already answered in the cache")
    print(f"  {len(new)} new calls, about {sum(new) // CHARS_PER_TOKEN:,} input tokens")
    if dry.counted:
        exact = getattr(counter(), "exact", 0)
        print(f"  counted by {TOKEN_COUNTER}: {sum(dry.counted):,} input tokens ({exact} of {len(dry.counted)} counted exactly, the rest estimated)")
    if len(new) > MAX_CALLS:
        print(f"  note: this is over the limit of {MAX_CALLS} calls per run; set LLM_MAX_CALLS in backend/.env to allow it")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
