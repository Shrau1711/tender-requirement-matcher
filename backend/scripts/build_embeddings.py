"""Embed every passage of every manufacturer document once, and save the vectors, so a fresh install does not have to.

Usage: python -m scripts.build_embeddings <categories folder> <output .sqlite>
Scanned pages are read from the saved answers (data/demo_cache); a page that is not saved stops this with an error, so it can never spend anything.
It runs when the Docker image is built; the vectors are then found through SEED_EMBEDDINGS (see app/services/embed_cache.py).
"""
import sys
from pathlib import Path
from types import SimpleNamespace

from app.services.corpus import load_chunks
from app.services.embed_cache import embed_cached
from app.services.gemini import model_and_level
from app.services.llm_cache import CachedLLM
from app.services.llm_factory import CACHE_DIR, SEED_DIR
from app.services.ocr import reader_for
from scripts.export_demo_cache import NoCalls


def main(categories: str, out: str) -> None:
    model, level = model_and_level()  # no key is needed: the model is only named, so the saved answers are found
    llm = CachedLLM(NoCalls(SimpleNamespace(model=model, settings=f"thinking={level}")), CACHE_DIR, seed_dir=SEED_DIR)
    read_image = reader_for(llm)
    for folder in sorted(p for p in Path(categories).iterdir() if p.is_dir()):
        texts = [c.text for c in load_chunks(folder, read_image)]
        embed_cached(texts, Path(out), seed_file=None)
        print(f"{folder.name}: {len(texts)} passages")


if __name__ == "__main__":
    main(*sys.argv[1:])
