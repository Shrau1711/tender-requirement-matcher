from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class Category(BaseModel):
    name: str
    manufacturers: list[str]
    documents: int


def list_categories(root: Path) -> list[Category]:
    """Every folder under the categories folder that holds manufacturers. Adding a folder adds a category; no code changes."""
    found = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []:
        makers = folder / "manufacturers"
        if makers.is_dir():
            names = sorted(p.name for p in makers.iterdir() if p.is_dir())
            found.append(Category(name=folder.name, manufacturers=names, documents=len(list(makers.glob("*/*.[pP][dD][fF]")))))
    return found
