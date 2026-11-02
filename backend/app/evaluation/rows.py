"""Finding a requirement's answer-key entry by the tender row it was read from, not by the name the model gave it.

The answer key (data/eval/gold/<tender>.json) is keyed by the attribute names the model chose when the labels were made.
Another model, or another temperature, may name the same requirement differently ("end_connection" for
"valve_end_connection"), and then a match by name finds no label. The tender row a requirement came from (item, file,
page, the row's name and value) does not depend on that naming. So <tender>.rows.json records, for each tender row, the
answer-key entries it produced, in order (see scripts.gold.make_row_anchors), and scoring looks them up:
- a row that produced one entry: every requirement read from that row gets it;
- a row that produced several: the requirements are paired with them in order, when there are as many;
- otherwise, and for rows the anchors do not know (a reading that differs), the attribute name, as before.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from app.evaluation.gold import (
    GOLD_DIR,
    Gold,
    Row,
    compare,
    has_several,
    key_for,
    load_gold,
)
from app.extraction.atomize import AtomicRequirement
from app.judging.match import Outcome
from app.vocabulary.roles import key_of

Anchor = tuple[str, str, int, str, str]  # item title, file, page, row name, row value


def anchor_of(r: AtomicRequirement) -> Anchor:
    return (r.item.title, r.file, r.pdf_page, r.source_name, r.source_value)


def row_anchors(atoms: list[AtomicRequirement]) -> dict[Anchor, list[str]]:
    """For each tender row, the answer-key entries its requirements were given, in the order they were read."""
    several = has_several([a.item for a in atoms])
    anchors: dict[Anchor, list[str]] = {}
    for a in atoms:
        anchors.setdefault(anchor_of(a), []).append(key_for(a.item, a.attribute, several))
    return anchors


def save_anchors(anchors: dict[Anchor, list[str]], path: Path) -> None:
    rows = [{"item": a[0], "file": a[1], "page": a[2], "name": a[3], "value": a[4], "keys": keys} for a, keys in anchors.items()]
    path.write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


def load_anchors(path: Path) -> dict[Anchor, list[str]]:
    return {(r["item"], r["file"], r["page"], r["name"], r["value"]): r["keys"] for r in json.loads(path.read_text(encoding="utf-8"))}


def keys_by_row(atoms: list[AtomicRequirement], anchors: dict[Anchor, list[str]]) -> tuple[dict[int, str], Counter]:
    """The answer-key entry for each requirement (by its position in atoms), and how many were found by row and by name."""
    several = has_several([a.item for a in atoms])
    by_row: dict[Anchor, list[int]] = {}
    for i, a in enumerate(atoms):
        by_row.setdefault(anchor_of(a), []).append(i)
    keys, how = {}, Counter()
    for anchor, positions in by_row.items():
        known = anchors.get(anchor)
        for n, i in enumerate(positions):
            if known and len(set(known)) == 1:
                keys[i], way = known[0], "row"
            elif known and len(known) == len(positions):
                keys[i], way = known[n], "row"
            else:
                keys[i], way = key_for(atoms[i].item, atoms[i].attribute, several), "name"
            how[way] += 1
    return keys, how


def compare_by_row(outcomes: list[Outcome], gold: Gold, anchors: dict[Anchor, list[str]]) -> tuple[list[Row], Counter]:
    """compare, with each requirement's answer-key entry found by its tender row. Also says how the entries were found."""
    atoms = list({key_of(o.requirement): o.requirement for o in outcomes}.values())  # each requirement once, in reading order
    keys, how = keys_by_row(atoms, anchors)
    entry = {key_of(a): keys[i] for i, a in enumerate(atoms)}
    return compare(outcomes, gold, lambda r: entry[key_of(r)]), how


def anchors_file(tender: str) -> Path:
    return GOLD_DIR / f"{tender}.rows.json"


def score_against_key(outcomes: list[Outcome], tender: str) -> tuple[list[Row], Counter | None]:
    """The scoring rows for a labelled tender: by tender row when it has an anchors file, else by attribute name as before."""
    gold = load_gold(GOLD_DIR / f"{tender}.json")
    file = anchors_file(tender)
    return compare_by_row(outcomes, gold, load_anchors(file)) if file.exists() else (compare(outcomes, gold), None)
