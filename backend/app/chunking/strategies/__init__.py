"""The chunking strategies, by name. A new strategy is one file here and one line in STRATEGIES."""
from __future__ import annotations

from app.chunking.base import Chunker
from app.chunking.strategies.parent_child import ParentChild
from app.chunking.strategies.recursive import Recursive
from app.chunking.strategies.sections import Sections
from app.chunking.strategies.semantic import Semantic
from app.chunking.strategies.structure import Structure
from app.chunking.strategies.table_rows import TableRows

STRATEGIES: dict[str, type] = {s.name: s for s in (TableRows, Recursive, Sections, ParentChild, Structure, Semantic)}


def strategy(name: str) -> Chunker:
    if name not in STRATEGIES:
        raise ValueError(f"Unknown chunking strategy {name!r}. Choose one of: {', '.join(STRATEGIES)}, or auto")
    return STRATEGIES[name]()
