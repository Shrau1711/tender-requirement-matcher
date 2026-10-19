from __future__ import annotations

from pydantic import BaseModel

from app.services.atomize import AtomicRequirement
from app.services.evidence import Evidence
from app.services.match import Outcome, Status
from app.services.roles import key_of, set_aside, wrong_type
from app.services.tender import Item

STATUSES: list[Status] = ["fully matched", "partially matched", "missing capability", "unsupported requirement"]

DEFINITIONS: dict[str, str] = {
    "fully matched": "The manufacturer's document states the requirement, and the stated value meets it (score 100).",
    "partially matched": (
        "The document says something relevant but not enough to be sure: the value is higher than asked (75), "
        "applies only under a condition or to a product that is not named (75), is the same kind of thing but not the grade or number asked for (50), "
        "meets the need only if a unit such as PN is read the other way (50), or cannot be compared at all, such as units that cannot be converted or a statement with no number (25). These are flagged for review, and the ones that cannot be compared are shown but left out of the compatibility."
    ),
    "missing capability": (
        "A catalogue could show this requirement and at least one manufacturer's documents speak to it, "
        "but this manufacturer's documents state nothing about it, or state something that does not meet it (score 0)."
    ),
    "unsupported requirement": (
        "A requirement about which no manufacturer can be judged from catalogues: it needs a certificate or other document, "
        "it only identifies the item or where it is used, or none of the collected documents covers it. It is not scored and not held against anyone; "
        "it is listed so the bid manager can confirm it with the manufacturer."
    ),
}

METHOD = (
    "Each requirement a catalogue can show gets a score: 100 fully matched, 75/50/25 partially matched (see the definitions), 0 missing capability. "
    "A manufacturer's compatibility for one tender item is the average of those scores, and every requirement of the item weighs the same. "
    "Unsupported requirements are left out of the average and listed separately. "
    "Each requirement is judged against one single product of the manufacturer (the one that suits the item best), so credit is never combined from different products. "
    "A manufacturer with no product of the tender's type in its documents, or whose best product fails the requirement that names the type (for example a horizontal pump against a vertical one), scores 0 for that item. "
    "An item that no manufacturer's documents can be judged for is not scored at all. "
    "The overall compatibility is the average over the scored items, each item weighing the same whatever its quantity. "
    "Coverage is the share of the counted requirements for which the documents state something, whether or not it meets the need. "
    "Statements that need a person to look (marked review) still count at their score, except those that cannot be compared at all (units that cannot be converted, a tender value that is not a plain number, a statement with no number): "
    "they are shown with their flag but left out of the average, so the compatibility rests only on what could be compared."
)


class Row(BaseModel):
    """One requirement judged for one manufacturer, with the evidence that decided it."""

    attribute: str
    wanted: str
    tender_file: str
    tender_page: int
    status: Status
    score: int
    review: bool
    flags: list[str] = []
    reason: str
    product: str | None = None
    document: str | None = None
    page: int | None = None
    quote: str | None = None


class ItemResult(BaseModel):
    item: str
    quantity: int | None
    product: str | None  # the single product the item was judged against
    scored: bool
    compatibility: float | None
    coverage: float | None
    counted: int
    left_out: int = 0  # counted requirements that could not be compared, so they are not in the compatibility
    note: str | None = None
    rows: list[Row]


class MakerResult(BaseModel):
    manufacturer: str
    rank: int | None
    compatibility: float | None  # headline: one product at a time
    coverage: float | None
    pooled_compatibility: float | None  # for comparison: best evidence for each requirement on its own, even from different products
    counts: dict[str, int]
    by_status: dict[str, list[str]]
    review_needed: int
    left_out: int = 0
    items: list[ItemResult]


class Unsupported(BaseModel):
    item: str
    wanted: str
    tender_file: str
    tender_page: int
    why: str


class Report(BaseModel):
    tender: str
    method: str
    definitions: dict[str, str]
    notes: list[str]
    unscored_items: list[str]
    unsupported: list[Unsupported]
    makers: list[MakerResult]  # best first; makers that could not be assessed last


def wanted_text(r: AtomicRequirement) -> str:
    return f"{' | '.join(r.values)} {r.unit or ''}".strip()


def label(r: AtomicRequirement) -> str:
    return f"{r.attribute}: {wanted_text(r)}"


def offered(outcomes: list[Outcome]) -> bool:
    """True when at least one statement is about a named product of the tender's type."""
    return any(o.evidence is not None and o.evidence.same_product_type == "yes" and o.evidence.product.strip().lower() != "unclear" for o in outcomes)


def set_apart(o: Outcome, why: str) -> Outcome:
    return o.model_copy(update={"status": "unsupported requirement", "score": 0, "review": False, "flags": [], "found": False, "evidence": None, "reason": why})


def row_of(o: Outcome) -> Row:
    e: Evidence | None = o.evidence
    r = o.requirement
    return Row(
        attribute=r.attribute, wanted=wanted_text(r), tender_file=r.file, tender_page=r.pdf_page, status=o.status, score=o.score,
        review=o.review, flags=o.flags, reason=o.reason, product=e.product if e else None, document=e.file if e else None,
        page=e.pdf_page if e else None, quote=e.quote if e else None,
    )


def item_result(item: Item, product: str | None, outcomes: list[Outcome], reasons: dict[tuple, str], assessed: bool) -> ItemResult:
    """One manufacturer's result for one item, before it is known whether the item can be scored at all."""
    outcomes = [set_apart(o, reasons[key_of(o.requirement)]) if key_of(o.requirement) in reasons else o for o in outcomes]
    counted = [o for o in outcomes if o.status != "unsupported requirement"]
    judged = [o for o in counted if o.judged]
    mismatch = wrong_type(outcomes)
    has_product = offered(outcomes) and mismatch is None
    absent = f"the product judged ({product}) is not the type the tender asks for: {mismatch}" if mismatch else "no product of this type is named in this manufacturer's documents"
    if not assessed:
        note, scored, comp, cov = "no readable text in this manufacturer's documents", False, None, None
    elif not counted:
        note, scored, comp, cov = "no requirement of this item can be judged from catalogues", False, None, None
    elif not has_product:
        note, scored, comp, cov = absent[0].upper() + absent[1:], True, 0.0, 0.0
    elif not judged:
        note, scored, comp, cov = "none of this item's requirements could be compared, so a person has to check them", False, None, None
    else:
        note, scored = None, True
        comp, cov = sum(o.score for o in judged) / len(judged), 100 * sum(o.found for o in counted) / len(counted)
    if not has_product and assessed and counted:
        outcomes = [o if o.status == "unsupported requirement" else o.model_copy(update={"score": 0, "status": "missing capability", "review": False, "flags": [], "reason": absent}) for o in outcomes]
    return ItemResult(
        item=item.title, quantity=item.quantity, product=product if has_product else None, scored=scored, compatibility=comp,
        coverage=cov, counted=len(counted) if scored else 0, left_out=len(counted) - len(judged) if scored else 0, note=note, rows=[row_of(o) for o in outcomes],
    )


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def pooled_by_item(outcomes: list[Outcome], reasons: dict[tuple, str], titles: list[str]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for title in titles:
        mine = [o for o in outcomes if o.requirement.item.title == title]
        counted = [o for o in mine if key_of(o.requirement) not in reasons and o.assessed and o.judged]
        result[title] = mean([float(o.score) for o in counted]) if counted and offered(mine) and wrong_type(mine) is None else (0.0 if counted else None)
    return result


def not_scored(r: ItemResult) -> ItemResult:
    return r.model_copy(update={"scored": False, "compatibility": None, "coverage": None, "counted": 0, "note": r.note or "not scored: no manufacturer's documents can be judged for this item"})


def maker_result(maker: str, items: list[ItemResult], pooled: dict[str, float | None]) -> MakerResult:
    live = [r for r in items if r.scored]
    rows = [(r.item, row) for r in live for row in r.rows]
    return MakerResult(
        manufacturer=maker, rank=None, compatibility=mean([r.compatibility for r in live]), coverage=mean([r.coverage for r in live]),
        pooled_compatibility=mean([pooled[r.item] for r in live if pooled.get(r.item) is not None]),
        counts={s: sum(row.status == s for _, row in rows) for s in STATUSES},
        by_status={s: [f"{item}: {row.attribute}: {row.wanted}" for item, row in rows if row.status == s] for s in STATUSES},
        review_needed=sum(row.review for _, row in rows), left_out=sum(r.left_out for r in live), items=items,
    )


def assemble(
    tender: str,
    atoms: list[AtomicRequirement],
    notes: list[str],
    makers: list[str],
    table: dict[tuple[int, str], list[Evidence]],
    readable: set[str],
    by_product: dict[str, list[tuple[Item, str | None, list[Outcome]]]],
    pooled: list[Outcome],
) -> Report:
    """The whole report, from results that are already computed. Plain code only; it makes no model calls."""
    reasons = set_aside(atoms, makers, table)
    results = {m: [item_result(item, product, outs, reasons, m in readable) for item, product, outs in by_product[m]] for m in makers}
    titles = [r.item for r in results[makers[0]]] if makers else []
    scorable = {r.item for rows in results.values() for r in rows if r.scored and r.counted and r.product}
    unscored = [t for t in titles if t not in scorable]
    made = []
    for m in makers:
        items = [r if r.item in scorable else not_scored(r) for r in results[m]]
        pooled_scores = pooled_by_item([o for o in pooled if o.manufacturer == m], reasons, titles)
        made.append(maker_result(m, items, pooled_scores))
    ranked = sorted((m for m in made if m.compatibility is not None), key=lambda m: (-m.compatibility, -(m.coverage or 0)))
    for i, m in enumerate(ranked, 1):
        m.rank = i
    unsupported, seen = [], set()
    for a in atoms:
        key = key_of(a)
        if key in reasons and key not in seen:
            seen.add(key)
            unsupported.append(Unsupported(item=a.item.title, wanted=label(a), tender_file=a.file, tender_page=a.pdf_page, why=reasons[key]))
    extra = [f"Item not scored: {t}. No manufacturer's documents can be judged for it." for t in unscored]
    return Report(
        tender=tender, method=METHOD, definitions=DEFINITIONS, notes=[*notes, *extra], unscored_items=unscored,
        unsupported=unsupported, makers=ranked + [m for m in made if m.compatibility is None],
    )
