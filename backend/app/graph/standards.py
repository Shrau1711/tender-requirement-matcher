"""Standards as a graph: which names are the same standard, and which standards documents name together.

Two kinds of knowledge, kept apart because they are not equally sure:
- The same standard under another name. A national body that adopts a European or international standard keeps its
  number: "BS EN ISO 5208", "DIN EN ISO 5208", "EN ISO 5208" and "ISO 5208" are one document, and "BS EN 593" is "EN 593".
  This follows from the names alone, so each standard is one node and its spellings are that node's names.
- Named together. "API 600 / BS 1873" in a catalogue, or "ISO 21049/API 682" in a tender, puts two standards side by side.
  Sometimes they are the same document under two bodies' names; often they are not (a gate valve standard next to a
  globe valve standard). So these links only ever send a requirement to a person, never count as a match.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from functools import cache
from pathlib import Path

from app.config import path_setting, text_setting
from app.graph.graph import Graph

KNOWLEDGE_GRAPH = text_setting("KNOWLEDGE_GRAPH", "off")  # "on" lets judging use the standards graph; off keeps every result as before
GRAPH_FILE = path_setting("STANDARDS_GRAPH", Path(__file__).resolve().parents[3] / "data" / "graph" / "standards.json")

BODIES = r"ISO|IS|API|ASME|ANSI|BS|EN|DIN|IEC|NEMA|MSS|AWWA|JIS|ASTM"
# A body in capitals (or an adopting chain such as "BS EN ISO"), maybe "standard" or "SP", then a number such as 13095,
# B16.34, 10438-3, 6D or 6FA. Capitals only, so "pressure is 16 bar" is not the standard IS 16.
NAME = re.compile(rf"\b(?:(?:BS|DIN|NF|UNI)\s*EN(?:\s*ISO)?|EN\s*ISO|{BODIES})(?![A-Za-z])[\s:.-]{{0,2}}(?:(?i:standard)\s*|(?i:std)\.?\s*|SP[\s-]*)?[A-Z]?\d+(?:[.-]\d+)*(?:[A-Z]{{1,2}}(?![A-Za-z]))?")
PAIR = re.compile(rf"({NAME.pattern})\s*/\s*({NAME.pattern})")
ADOPTED = re.compile(r"^(?:BS|DIN|NF|UNI)?EN(ISO)?(\d.*)$")  # on a key: BSENISO5208, ENISO5208, BSEN593
# "EN 8", "EN 19" (steel grades), "EN 1.4408" (a material number), "EN A182": EN names that are not standards
NOT_A_STANDARD = re.compile(r"^EN(?:[A-Z]|\d{1,2}[A-Z]?$|1\.\d{4}$)")


def key(name: str) -> str:
    """One spelling for a name: "IS:13095-2008" and "IS 13095" -> IS13095; "API standard 614" -> API614; "EN 1092-1" -> EN1092-1."""
    text = re.sub(r"\b(?:standard|std)\b\.?", "", name, flags=re.IGNORECASE)
    text = re.sub(r"[:-]\s*(?:19|20)\d{2}$", "", text.strip())  # the edition year: "IS 13095:2008", "IS:13095-2008"
    text = re.sub(r"[^A-Z0-9.-]", "", text.upper())
    return re.sub(r"(?<!\d)[.-]|[.-](?!\d)", "", text)  # "API-610" -> API610, but "EN 1092-1" keeps its part: EN1092-1


def standard_of(name: str) -> str:
    """The standard a name stands for, with any adopting body's prefix removed: "BS EN ISO 5208" -> ISO5208."""
    k = key(name)
    adopted = ADOPTED.match(k)
    return k if not adopted else ("ISO" if adopted.group(1) else "EN") + adopted.group(2)


def is_standard(name: str) -> bool:
    return not NOT_A_STANDARD.match(standard_of(name))


def names_in(text: str) -> list[str]:
    return [name for m in NAME.finditer(text) if is_standard(name := " ".join(m.group(0).split()))]


def build(texts: Iterable[tuple[str, str]]) -> Graph:
    """The standards graph from (text, where it was read) pairs: every standard named, its spellings, and the pairs named together."""
    graph = Graph()
    for text, seen_in in texts:
        for name in names_in(text):
            graph.node(standard_of(name), "standard", standard_of(name), name)
        for first, second in PAIR.findall(text):
            a, b = standard_of(first), standard_of(second)
            if a != b and is_standard(first) and is_standard(second):
                graph.link(*sorted((a, b)), "named_together", seen_in)
    return graph


def link_between(graph: Graph, wanted: str, stated: str) -> tuple[str, str, str, list[str]] | None:
    """(relation, wanted name, stated name, where seen) for the first standard in `wanted` that one in `stated` is linked to.

    "same" when they are one standard under different names, "together" when some document named them side by side."""
    for w in names_in(wanted):
        for s in names_in(stated):
            if standard_of(w) == standard_of(s):
                return ("same", w, s, [])
            seen = graph.linked(standard_of(w), "named_together").get(standard_of(s))
            if seen:
                return ("together", w, s, seen)
    return None


@cache
def standards_graph(file: Path = GRAPH_FILE) -> Graph:
    """The saved standards graph (see scripts.run.build_graph), read once."""
    return Graph.load(file)
