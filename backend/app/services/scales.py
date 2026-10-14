from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.services.atomize import AtomicRequirement

SCALES_FILE = Path(__file__).resolve().parents[2] / "config" / "scales.json"
EXCEEDS = 75  # rated higher on the scale than asked


@lru_cache
def load_scales(path: Path = SCALES_FILE) -> list[list[str]]:
    """Ordered scales, lowest first (efficiency classes IE1 < IE2 < IE3 ...), written as data."""
    return json.loads(path.read_text(encoding="utf-8"))


def squeeze(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def scale_of(values: list[str], scales: list[list[str]]) -> list[str] | None:
    """The scale that every wanted value is a step of, if there is one."""
    wanted = {squeeze(v) for v in values}
    return next((s for s in scales if wanted <= {squeeze(step) for step in s}), None)


def steps_stated(texts: list[str], scale: list[str]) -> set[int]:
    """Which steps of the scale the statement mentions ("IE3 (Premium)" -> the position of IE3)."""
    squeezed = " ".join(squeeze(t) for t in texts)
    return {i for i, step in enumerate(scale) if squeeze(step) in squeezed}


def scale_verdict(req: AtomicRequirement, texts: list[str], scales: list[list[str]] | None = None) -> tuple[int, str] | None:
    """(score, reason) when a step of an ordered scale is wanted and a higher step is stated; None when the words should be compared instead."""
    scale = scale_of(req.values, scales if scales is not None else load_scales())
    if scale is None or req.kind == "number":
        return None
    wanted = {i for i, step in enumerate(scale) if squeeze(step) in {squeeze(v) for v in req.values}}
    stated = steps_stated(texts, scale)
    if not stated or stated & wanted and req.operator != "at_least":
        return None  # nothing to rank, or the wanted step itself is stated: the ordinary comparison gives full credit
    best = max(stated)
    if req.operator == "at_least":
        return (100, f"states {scale[best]}, which is at least {scale[min(wanted)]}") if best >= min(wanted) else None
    if req.operator == "at_most":
        return (100, f"states {scale[min(stated)]}, which is no higher than {scale[max(wanted)]}") if min(stated) <= max(wanted) else None
    if best > max(wanted):
        return EXCEEDS, f"states {scale[best]}, which is higher than {' / '.join(req.values)} asked for"
    return None
