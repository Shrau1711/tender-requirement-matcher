"""A small graph: named nodes and labelled links, each link remembering where it was seen. Saved as plain JSON."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class Node(BaseModel):
    kind: str            # "standard", "tender", "item", "row", "requirement"
    label: str           # how it is shown
    names: list[str] = []  # every spelling seen for it, e.g. "BS EN ISO 5208" and "ISO 5208"


class Link(BaseModel):
    source: str
    target: str
    relation: str          # "named_together", "has_item", "has_row", "splits_into", "cites"
    seen_in: list[str] = []  # where the link was found, so a person can check it


class Graph(BaseModel):
    nodes: dict[str, Node] = {}
    links: list[Link] = []

    def node(self, node_id: str, kind: str, label: str, name: str | None = None) -> None:
        found = self.nodes.setdefault(node_id, Node(kind=kind, label=label))
        if name and name not in found.names:
            found.names.append(name)

    def link(self, source: str, target: str, relation: str, seen_in: str | None = None) -> None:
        """Adds the link, or adds where it was seen to the link already there."""
        existing = next((l for l in self.links if (l.source, l.target, l.relation) == (source, target, relation)), None)
        if existing is None:
            existing = Link(source=source, target=target, relation=relation)
            self.links.append(existing)
        if seen_in and seen_in not in existing.seen_in:
            existing.seen_in.append(seen_in)

    def linked(self, node_id: str, relation: str) -> dict[str, list[str]]:
        """The nodes linked to this one by the relation, in either direction, each with where the link was seen."""
        out: dict[str, list[str]] = {}
        for l in self.links:
            if l.relation == relation and node_id in (l.source, l.target):
                out[l.target if l.source == node_id else l.source] = l.seen_in
        return out

    def below(self, node_id: str, relations: set[str]) -> set[str]:
        """Every node reached from this one by following the relations forwards."""
        seen, todo = set(), [node_id]
        while todo:
            current = todo.pop()
            for l in self.links:
                if l.source == current and l.relation in relations and l.target not in seen:
                    seen.add(l.target)
                    todo.append(l.target)
        return seen

    def to_mermaid(self) -> str:
        """A Mermaid flowchart of the graph, for reading it in a Markdown viewer."""
        ids = {node_id: f"n{i}" for i, node_id in enumerate(self.nodes)}
        lines = ["flowchart LR"]
        lines += [f'    {ids[i]}["{n.label.replace(chr(34), chr(39))}"]' for i, n in self.nodes.items()]
        lines += [f"    {ids[l.source]} -->|{l.relation}| {ids[l.target]}" for l in self.links]
        return "\n".join(lines)

    def save(self, file: Path) -> None:
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(self.model_dump_json(indent=1), encoding="utf-8")

    @classmethod
    def load(cls, file: Path) -> Graph:
        return cls.model_validate_json(file.read_text(encoding="utf-8")) if file.exists() else cls()
