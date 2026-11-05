"""Putting a category's manufacturer documents into a vector store once, and building the search index over them.

A file is read, chunked and embedded only if the store does not already hold it with the same content hash and the same
settings. The settings include a fingerprint of the reading and chunking code, so changing that code reads every file again.
"""
from __future__ import annotations

import hashlib
import threading
from functools import cache
from pathlib import Path

import numpy as np

from app.chunking.base import Chunk
from app.chunking.corpus import chunk_file, pdf_files
from app.chunking.router import CHUNKER
from app.config import cache_dir, path_setting, text_setting
from app.embedding.base import EmbedFn
from app.embedding.embed_cache import embed_cached
from app.embedding.embedder import DEFAULT, EMBEDDER, embedder
from app.reading.ocr import ImageReader, reader_setting
from app.reading.pdf_reader import sha256_file
from app.retrieval.base import Retriever
from app.retrieval.retrievers import RETRIEVER, retriever
from app.vectorstore.base import StoredDoc, VectorStore
from app.vectorstore.chroma import ChromaStore
from app.vectorstore.memory import MemoryStore

VECTOR_STORE = text_setting("VECTOR_STORE", "chroma")  # exact scores either way (see Index.meanings); chroma also keeps documents between starts
CHROMA_DIR = path_setting("CHROMA_DIR", cache_dir() / "chroma")  # inside the cache folder, which git ignores
WRITING = threading.Lock()  # two tenders started together may store the same file; one write at a time keeps the store whole
CODE = [Path(__file__).resolve().parents[1] / name for name in ("reading", "chunking")]  # the code that decides a file's chunks


@cache
def code_version() -> str:
    h = hashlib.sha256(embedder().name.encode())  # the vectors depend on the embedder too
    for file in sorted(f for folder in CODE for f in folder.rglob("*.py")):
        h.update(file.read_bytes().replace(b"\r\n", b"\n"))  # the same on Windows and Linux checkouts
    return h.hexdigest()[:16]


def settings_for(chunker: str, reads_pictures: bool) -> str:
    reader = reader_setting() if reads_pictures else ""  # empty for the default page reader, so its stored files still match
    return f"chunker={chunker};pictures={reads_pictures};code={code_version()}" + (f";ocr={reader}" if reader else "")


@cache
def chroma_store(folder: Path) -> ChromaStore:
    return ChromaStore(folder)  # one client per folder for the whole process


def open_store(name: str = VECTOR_STORE) -> VectorStore:
    """The store chosen by the VECTOR_STORE setting. A memory store is new each time and lives as long as its index."""
    if name == "memory":
        return MemoryStore()
    if name == "chroma":
        # Another embedder's vectors can have another length, which one Chroma collection cannot hold: they get their own folder.
        return chroma_store(CHROMA_DIR if EMBEDDER == DEFAULT else CHROMA_DIR.with_name(f"chroma-{EMBEDDER}"))
    raise ValueError(f"Unknown vector store {name!r}. Choose memory or chroma")


def ingest(category_dir: str | Path, store: VectorStore, read_image: ImageReader | None = None, chunker: str = CHUNKER,
           embed: EmbedFn = embed_cached) -> list[Chunk]:
    """Every chunk of the category, in file order. Files the store already holds unchanged are not read again."""
    category = Path(category_dir).name
    chunks: list[Chunk] = []
    for pdf in pdf_files(category_dir):
        doc = StoredDoc(category=category, manufacturer=pdf.parent.name, file=pdf.name, sha256=sha256_file(pdf),
                        settings=settings_for(chunker, read_image is not None))
        if not store.stored(doc):
            found = chunk_file(pdf, read_image, chunker)
            vectors = embed([c.text for c in found]) if found else np.zeros((0, 1), dtype=np.float32)
            with WRITING:
                store.put(doc, found, vectors)
        chunks += store.chunks(doc)
    return chunks


def open_index(category_dir: str | Path, read_image: ImageReader | None = None, chunker: str = CHUNKER,
               store: VectorStore | None = None, search: str = RETRIEVER) -> Retriever:
    """The search over a category's documents: the retriever chosen by RETRIEVER, over the store chosen by VECTOR_STORE
    unless one is given."""
    store = store or open_store()
    return retriever(ingest(category_dir, store, read_image, chunker), store, Path(category_dir).name, search)
