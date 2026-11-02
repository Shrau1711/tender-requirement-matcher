from __future__ import annotations

import json


def row_key(maker: str, item: str, attribute: str, wanted: str, tender_page: int) -> str:
    """The identity of one requirement row for one manufacturer. The frontend builds the same text with JSON.stringify."""
    return json.dumps([maker, item, attribute, wanted, tender_page], ensure_ascii=False, separators=(",", ":"))
