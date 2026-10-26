import pytest

from app.llm.llm import Reply


class FakeLLM:
    """Replies with canned text, in order, and remembers what it was asked."""

    def __init__(self, replies: list[str]) -> None:
        self.replies, self.prompts = list(replies), []

    def generate(self, system: str, user: str) -> Reply:
        self.prompts.append(user)
        return Reply(text=self.replies.pop(0), input_tokens=10, output_tokens=5)


@pytest.fixture
def fake_llm():
    return FakeLLM