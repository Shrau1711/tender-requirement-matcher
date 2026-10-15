from __future__ import annotations

from collections import Counter

from app.services.gold import Row, share
from app.services.match import Status

JUDGED: list[Status] = ["fully matched", "partially matched", "missing capability"]  # a person labels these; unsupported requirements are not compared
RANK = {"missing capability": 0, "partially matched": 1, "fully matched": 2}


def confusion(rows: list[Row]) -> Counter:
    """How often a person's label (gold) was answered with each status (ours)."""
    return Counter((r.gold, r.ours) for r in rows)


def per_status(rows: list[Row]) -> dict[str, dict[str, float | int | None]]:
    """For each status: how many of the system's answers were right (precision) and how many of the person's labels it found (recall)."""
    table = confusion(rows)
    result = {}
    for status in JUDGED:
        said = sum(n for (_, ours), n in table.items() if ours == status)
        labelled = sum(n for (gold, _), n in table.items() if gold == status)
        right = table[(status, status)]
        result[status] = {
            "said": said, "labelled": labelled, "right": right,
            "precision": right / said if said else None, "recall": right / labelled if labelled else None,
        }
    return result


def overclaims(rows: list[Row]) -> list[Row]:
    """Rows where the system said more than the person found. These are the costly mistakes: a bid manager would rely on them."""
    return [r for r in rows if RANK[r.ours] > RANK[r.gold]]


def underclaims(rows: list[Row]) -> list[Row]:
    return [r for r in rows if RANK[r.ours] < RANK[r.gold]]


def percent(value: float | None) -> str:
    return "n/a" if value is None else f"{100 * value:.0f}%"


def page_agreement(rows: list[Row]) -> tuple[int, int]:
    """Where both the person and the system found something: how often they cite a page the person also cited."""
    both = [r for r in rows if r.gold != "missing capability" and r.ours != "missing capability"]
    return sum(r.page_agrees for r in both), len(both)


def to_markdown(by_tender: dict[str, list[Row]]) -> str:
    """The whole evaluation as text for the write-up: agreement per tender, then per status, then the confusion matrix."""
    rows = [r for found in by_tender.values() for r in found]
    lines = ["# Evaluation against hand-labelled answer keys", "", "## Agreement per tender", "", "| Tender | Labelled rows | Checked by hand | Status agrees | Over-claims | Under-claims |", "|---|---|---|---|---|---|"]
    for tender, found in by_tender.items():
        lines.append(f"| {tender} | {len(found)} | {sum(r.checked for r in found)} | {share(sum(r.agrees for r in found), len(found))} | {len(overclaims(found))} | {len(underclaims(found))} |")
    lines.append(f"| **All** | {len(rows)} | {sum(r.checked for r in rows)} | {share(sum(r.agrees for r in rows), len(rows))} | {len(overclaims(rows))} | {len(underclaims(rows))} |")
    hit, total = page_agreement(rows)
    lines += ["", f"Page agreement where both found something: {share(hit, total)}.", "", "## Per status", "", "| Status | Labelled | System said | Right | Precision | Recall |", "|---|---|---|---|---|---|"]
    for status, s in per_status(rows).items():
        lines.append(f"| {status} | {s['labelled']} | {s['said']} | {s['right']} | {percent(s['precision'])} | {percent(s['recall'])} |")
    table = confusion(rows)
    lines += ["", "## Confusion matrix (rows: what the person found; columns: what the system said)", "", "| | " + " | ".join(JUDGED) + " |", "|---|---|---|---|"]
    for gold in JUDGED:
        lines.append(f"| {gold} | " + " | ".join(str(table[(gold, ours)]) for ours in JUDGED) + " |")
    lines += ["", "## Disagreements", ""]
    for r in (r for r in rows if not r.agrees):
        lines.append(f"- {r.attribute} / {r.manufacturer}: person {r.gold}, system {r.ours} ({r.score}). {r.reason}")
    return "\n".join(lines) + "\n"
