from __future__ import annotations

RRF_K = 60  # the usual constant; larger values flatten the gap between ranks


# Reciprocal rank fusion: each list gives an item 1/(k+rank), the scores are added, and the items are sorted by total.
# Only ranks are used, so no score scales need matching.
def rrf(rankings: list[list[int]], k: int = RRF_K) -> list[tuple[int, float]]:
    """Merge ranked lists of ids. An id scores 1/(k+rank) in every list it appears in."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1 / (k + rank)
    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)