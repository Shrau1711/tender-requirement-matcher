from __future__ import annotations

from collections import defaultdict

from app.chunking.base import Chunk
from app.evaluation.gold import has_several, key_for
from app.extraction.atomize import AtomicRequirement
from app.extraction.evidence import Evidence

Matrix = dict[str, dict[str, int]]  # requirement -> manufacturer -> how many statements were found


def inventory(chunks: list[Chunk]) -> dict[str, dict[str, dict[str, int]]]:
    """What was collected: for each manufacturer and file, how many pages gave text, how many chunks, and how many pages were read from pictures."""
    pages: dict[tuple[str, str], set[int]] = defaultdict(set)
    scanned: dict[tuple[str, str], set[int]] = defaultdict(set)
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for c in chunks:
        pages[(c.manufacturer, c.file)].add(c.pdf_page)
        counts[(c.manufacturer, c.file)] += 1
        if c.ocr:
            scanned[(c.manufacturer, c.file)].add(c.pdf_page)
    result: dict[str, dict[str, dict[str, int]]] = defaultdict(dict)
    for (maker, file), found in sorted(pages.items()):
        result[maker][file] = {"pages": len(found), "chunks": counts[(maker, file)], "scanned_pages": len(scanned[(maker, file)])}
    return dict(result)


def matrix(atoms: list[AtomicRequirement], makers: list[str], table: dict[tuple[int, str], list[Evidence]]) -> Matrix:
    """For every requirement a catalogue could answer, how many statements each manufacturer's documents gave."""
    several = has_several([a.item for a in atoms])
    result: Matrix = {}
    for i, a in enumerate(atoms):
        if a.evidence != "product":
            continue
        row = result.setdefault(key_for(a.item, a.attribute, several), dict.fromkeys(makers, 0))
        for m in makers:
            row[m] = max(row[m], len(table.get((i, m), [])))
    return result


def nowhere(grid: Matrix) -> list[str]:
    """Requirements that no manufacturer's documents say anything about: a gap in the collected data, not in any manufacturer."""
    return [req for req, row in grid.items() if not any(row.values())]


def thin(grid: Matrix) -> dict[str, list[str]]:
    """For each manufacturer, the requirements others answer but its own documents do not: the documents most worth looking for."""
    return {
        m: [req for req, row in grid.items() if not row[m] and any(row.values())]
        for m in next(iter(grid.values()), {})
    }


def to_markdown(docs: dict[str, dict[str, dict[str, int]]], grid: Matrix) -> str:
    makers = list(next(iter(grid.values()), {}))
    lines = ["# Data coverage", "", "## Documents collected", "", "| Manufacturer | File | Pages with text | Chunks | Pages read from pictures |", "|---|---|---|---|---|"]
    for maker, files in docs.items():
        for file, s in files.items():
            lines.append(f"| {maker} | {file} | {s['pages']} | {s['chunks']} | {s['scanned_pages']} |")
    lines += ["", "## Statements found per requirement (0 means the documents say nothing)", "", "| Requirement | " + " | ".join(makers) + " |", "|---|" + "---|" * len(makers)]
    for req, row in grid.items():
        lines.append(f"| {req} | " + " | ".join(str(row[m]) for m in makers) + " |")
    lines += ["", "## Not covered by any manufacturer's documents", ""]
    lines += [f"- {r}" for r in nowhere(grid)] or ["- none"]
    lines += ["", "## Covered for some manufacturers but not for these (documents worth looking for)", ""]
    for maker, reqs in thin(grid).items():
        lines.append(f"- **{maker}**: {len(reqs)} of {len(grid)} requirements" + (": " + "; ".join(reqs) if reqs else ""))
    return "\n".join(lines) + "\n"
