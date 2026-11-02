from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.chunking.base import Chunk
from app.judging.match import Outcome
from app.vocabulary.terms import candidates

Kind = Literal["found but does not meet it", "possibly missed by the search", "likely absent from the documents"]


class Finding(BaseModel):
    manufacturer: str
    requirement: str
    kind: Kind
    where: list[str] = []  # "file p12" for the chunks worth a look


def audit(outcomes: list[Outcome], chunks: list[Chunk]) -> list[Finding]:
    """Why each requirement a manufacturer was scored 0 on was scored so: a real mismatch, a likely miss by the search, or genuinely not in the documents."""
    by_maker: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_maker.setdefault(c.manufacturer, []).append(c)
    findings, seen = [], set()
    for o in outcomes:
        r = o.requirement
        label = f"{r.item.title}: {r.attribute}: {' | '.join(r.values)} {r.unit or ''}".strip()
        if o.status != "missing capability" or not o.assessed or (label, o.manufacturer) in seen:
            continue
        seen.add((label, o.manufacturer))
        if o.found:
            findings.append(Finding(manufacturer=o.manufacturer, requirement=label, kind="found but does not meet it"))
            continue
        near = candidates(r, by_maker.get(o.manufacturer, []))
        kind: Kind = "possibly missed by the search" if near else "likely absent from the documents"
        findings.append(Finding(manufacturer=o.manufacturer, requirement=label, kind=kind, where=[f"{c.file} p{c.pdf_page}" for c in near]))
    return findings


def to_markdown(findings: list[Finding]) -> str:
    lines = ["# Why requirements scored 0", "", "| Manufacturer | Found but does not meet it | Possibly missed by the search | Likely absent from the documents |", "|---|---|---|---|"]
    makers = sorted({f.manufacturer for f in findings})
    for m in makers:
        count = {k: sum(f.manufacturer == m and f.kind == k for f in findings) for k in ("found but does not meet it", "possibly missed by the search", "likely absent from the documents")}
        lines.append(f"| {m} | " + " | ".join(str(n) for n in count.values()) + " |")
    lines += ["", "## Possibly missed by the search: look at these pages", ""]
    lines += [f"- {f.manufacturer}: {f.requirement} -> {'; '.join(f.where)}" for f in findings if f.kind == "possibly missed by the search"] or ["- none"]
    lines += ["", "## Found but does not meet it", ""]
    lines += [f"- {f.manufacturer}: {f.requirement}" for f in findings if f.kind == "found but does not meet it"] or ["- none"]
    lines += ["", "## Likely absent from the documents", ""]
    lines += [f"- {f.manufacturer}: {f.requirement}" for f in findings if f.kind == "likely absent from the documents"] or ["- none"]
    return "\n".join(lines) + "\n"
