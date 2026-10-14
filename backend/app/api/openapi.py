from __future__ import annotations

from typing import Any


def with_file_pickers(node: Any) -> Any:
    """Describe uploads the older way ("format": "binary") so the /docs page shows a file picker instead of a text box."""
    if isinstance(node, dict):
        if node.get("type") == "string" and node.get("contentMediaType") == "application/octet-stream":
            return {"type": "string", "format": "binary"}
        return {key: with_file_pickers(value) for key, value in node.items()}
    if isinstance(node, list):
        return [with_file_pickers(item) for item in node]
    return node
