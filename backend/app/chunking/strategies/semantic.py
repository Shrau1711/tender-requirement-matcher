"""Chunks cut where the meaning changes.

A page is split into its text blocks (a label stays with its value), and every block of the document is embedded. Two
neighbouring blocks on a page stay in one chunk while they are alike; a cut is made where they are least alike, judged
against the document itself: the BREAK_SHARE least alike neighbours of the document are cuts. A chunk is also cut before
it passes MAX_CHARS. A chunk never spans two pages, so every chunk keeps one page to cite.
"""
from __future__ import annotations

import numpy as np

from app.chunking.base import MAX_CHARS, Chunk, MakeChunk, block_texts, split_oversized
from app.embedding.base import EmbedFn
from app.embedding.embed_cache import embed_cached
from app.reading.pdf_reader import PageRecord

BREAK_SHARE = 0.25  # this share of a document's neighbouring blocks, the least alike, are cut apart


# A page's pieces: its text blocks, or its paragraphs when it has no blocks (a page read from a picture). None is too big for a chunk.
def pieces(page: PageRecord) -> list[str]:
    blocks = block_texts(page.lines) if page.lines else page.text.split("\n\n")
    return [p for block in blocks if block.strip() for p in (split_oversized(block, MAX_CHARS) if len(block) > MAX_CHARS else [block])]


# How alike each piece is to the one before it on the same page (None for the first piece of a page).
def likeness(pages: list[list[str]], vectors: np.ndarray) -> list[float | None]:
    out: list[float | None] = []
    at = 0
    for texts in pages:
        out += [None] + [float(vectors[at + i] @ vectors[at + i - 1]) for i in range(1, len(texts))]
        at += len(texts)
    return out


class Semantic:
    name = "semantic"

    def __init__(self, embed: EmbedFn = embed_cached) -> None:
        self.embed = embed  # the saved vectors by default, so a block is embedded once

    def chunk(self, pages: list[PageRecord], make: MakeChunk) -> list[Chunk]:
        texts = [pieces(page) for page in pages]
        flat = [t for page in texts for t in page]
        if not flat:
            return []
        alike = likeness(texts, self.embed(flat))
        known = [a for a in alike if a is not None]
        cut_below = float(np.quantile(known, BREAK_SHARE)) if known else 0.0
        out: list[Chunk] = []
        at = 0
        for page, page_texts in zip(pages, texts, strict=True):
            current = ""
            for text in page_texts:
                a = alike[at]
                at += 1
                if current and ((a is not None and a <= cut_below) or len(current) + len(text) + 1 > MAX_CHARS):
                    out.append(make(page, "text", None, current))
                    current = ""
                current = f"{current}\n{text}" if current else text
            if current:
                out.append(make(page, "text", None, current))
        return out
