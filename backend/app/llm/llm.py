from __future__ import annotations

import json
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel

MAX_ATTEMPTS = 3
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")  # some models wrap JSON in a code fence

T = TypeVar("T", bound=BaseModel)


class Reply(BaseModel):
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLM(Protocol):
    """Anything that turns a system prompt and a user prompt into a reply."""

    def generate(self, system: str, user: str) -> Reply: ...


def parse_json(raw: str, schema: type[T]) -> T:
    return schema.model_validate(json.loads(FENCE.sub("", raw.strip())))


def request_system(system: str, schema: type[T]) -> str:
    """The system prompt the model really receives: the instructions plus the schema its reply must match. Saved answers are found by this text."""
    return f"{system}\n\nReply with JSON only, matching this schema:\n{json.dumps(schema.model_json_schema())}"


def ask(llm: LLM, system: str, user: str, schema: type[T], attempts: int = MAX_ATTEMPTS) -> T:
    """Get a reply that matches `schema`. A bad reply is sent back with the error, up to `attempts` times."""
    system = request_system(system, schema)
    prompt, error = user, None
    for _ in range(attempts):
        try:
            return parse_json(llm.generate(system, prompt).text, schema)
        except ValueError as err:  # covers bad JSON and schema mismatches
            error = err
            prompt = f"{user}\n\nYour previous reply was rejected: {err}\nReply again with corrected JSON only."
    raise ValueError(f"No valid reply after {attempts} attempts: {error}")
