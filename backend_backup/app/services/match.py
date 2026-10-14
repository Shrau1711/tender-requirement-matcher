from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.services.atomize import AtomicRequirement
from app.services.compare import verdict
from app.services.evidence import Evidence

Status = Literal["fully matched", "partially matched", "missing capability", "unsupported requirement"]


class Outcome(BaseModel):
    requirement: AtomicRequirement
    manufacturer: str
    status: Status
    score: int
    found: bool  # some evidence was found, whether or not it meets the requirement
    assessed: bool = True  # False when the manufacturer's documents could not be read at all
    review: bool
    reason: str
    evidence: Evidence | None = None


class Summary(BaseModel):
    manufacturer: str
    compatibility: float | None  # average score over the requirements a catalogue could show; None if nothing was assessed
    coverage: float | None  # share of those requirements for which any evidence was found
    counted: int


def status_for(score: int) -> Status:
    return "fully matched" if score == 100 else "partially matched" if score else "missing capability"


def match_requirement(
    req: AtomicRequirement, manufacturer: str, evidence: list[Evidence], aliases: dict[str, dict], readable: bool = True,
    context: list[AtomicRequirement] | None = None,
) -> Outcome:
    base = {"requirement": req, "manufacturer": manufacturer, "found": False, "review": False}
    if req.evidence == "paperwork":
        return Outcome(**base, status="unsupported requirement", score=0, reason="needs a certificate or document, which a catalogue cannot show")
    if not readable:
        return Outcome(**{**base, "assessed": False}, status="missing capability", score=0, reason="no readable text in this manufacturer's documents")
    if not evidence:
        return Outcome(**base, status="missing capability", score=0, reason="no evidence found in the documents")
    best, ev = max(((verdict(req, e, aliases, context), e) for e in evidence), key=lambda pair: (pair[0].score, not pair[0].review))
    reason = best.reason if best.score else f"found, but does not meet it: {best.reason}"
    return Outcome(**{**base, "found": True, "review": best.review}, status=status_for(best.score), score=best.score, reason=reason, evidence=ev)


def summarize(manufacturer: str, outcomes: list[Outcome]) -> Summary:
    counted = [o for o in outcomes if o.status != "unsupported requirement" and o.assessed]
    if not counted:
        return Summary(manufacturer=manufacturer, compatibility=None, coverage=None, counted=0)
    return Summary(
        manufacturer=manufacturer,
        compatibility=sum(o.score for o in counted) / len(counted),
        coverage=100 * sum(o.found for o in counted) / len(counted),
        counted=len(counted),
    )


def match_all(
    atoms: list[AtomicRequirement],
    makers: list[str],
    table: dict[tuple[int, str], list[Evidence]],
    aliases: dict[str, dict],
    readable: set[str],
) -> list[Outcome]:
    """One outcome for every requirement and manufacturer."""
    siblings = [[b for b in atoms if b.item == a.item] for a in atoms]  # the other requirements of the same item
    return [match_requirement(a, m, table.get((i, m), []), aliases, m in readable, siblings[i]) for i, a in enumerate(atoms) for m in makers]