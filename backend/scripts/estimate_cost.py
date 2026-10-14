"""Estimate what matching a tender would cost, before spending it.

Usage: python -m scripts.estimate_cost <tender folder or pdf> <category_dir>

Reading the tender is real (and cached). Every question about a manufacturer's documents is counted, not asked.
Pages of the manufacturers' documents that are only pictures are not counted.
"""
import sys
import threading

from app.services.corpus import load_chunks, manufacturers
from app.services.evidence import TOP_K, evidence_table
from app.services.llm import Reply
from app.services.llm_cache import MAX_CALLS, CachedLLM
from app.services.llm_factory import make_llm
from app.services.ocr import reader_for
from app.services.pipeline import read_atoms
from app.services.queries import load_unit_views
from app.services.search import Index

CHARS_PER_TOKEN = 4  # a rough rule for English technical text


class DryRun:
    """Stands in for the model: notes what each question would cost and answers 'nothing found'."""

    def __init__(self, cache: CachedLLM) -> None:
        self.cache, self.lock = cache, threading.Lock()
        self.asked: list[tuple[bool, int]] = []  # (already cached, characters)

    def generate(self, system: str, user: str) -> Reply:
        with self.lock:
            self.asked.append((self.cache.path_for(system, user).exists(), len(system) + len(user)))
        return Reply(text='{"findings": []}')


def main(tender: str, category_dir: str) -> None:
    llm = make_llm()
    atoms, _ = read_atoms(llm, tender, reader_for(llm))
    print(f"reading the tender: {llm.summary()}")
    dry = DryRun(llm)
    evidence_table(dry, Index(load_chunks(category_dir)), atoms, manufacturers(category_dir), load_unit_views())
    new = [chars for cached, chars in dry.asked if not cached]
    print(f"\nreading the manufacturers' documents ({TOP_K} passages per question):")
    print(f"  {len(dry.asked)} questions, {len(dry.asked) - len(new)} already answered in the cache")
    print(f"  {len(new)} new calls, about {sum(new) // CHARS_PER_TOKEN:,} input tokens")
    if len(new) > MAX_CALLS:
        print(f"  note: this is over the limit of {MAX_CALLS} calls per run; set LLM_MAX_CALLS in backend/.env to allow it")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
