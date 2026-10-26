import pytest
from pydantic import BaseModel

from app.llm.llm import ask


class Answer(BaseModel):
    bar: float


def test_plain_json_is_parsed(fake_llm):
    assert ask(fake_llm(['{"bar": 16}']), "s", "u", Answer).bar == 16


def test_code_fence_is_stripped(fake_llm):
    assert ask(fake_llm(['```json\n{"bar": 16}\n```']), "s", "u", Answer).bar == 16


def test_bad_reply_is_retried_with_the_error(fake_llm):
    llm = fake_llm(['{"bar": "lots"}', '{"bar": 16}'])
    assert ask(llm, "s", "u", Answer).bar == 16
    assert "rejected" in llm.prompts[1]


def test_gives_up_after_the_attempt_limit(fake_llm):
    with pytest.raises(ValueError, match="2 attempts"):
        ask(fake_llm(["nope", "still nope"]), "s", "u", Answer, attempts=2)