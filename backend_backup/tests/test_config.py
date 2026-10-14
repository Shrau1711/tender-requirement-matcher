import pytest

from app.config import gemini_key


def test_picks_the_key_named_in_use(monkeypatch):
    monkeypatch.setenv("LLM_KEY_IN_USE", "MENTOR")
    monkeypatch.setenv("GEMINI_KEY_MENTOR", "m-key")
    monkeypatch.setenv("GEMINI_KEY_PERSONAL", "p-key")
    assert gemini_key() == ("MENTOR", "m-key")


def test_missing_setup_says_what_to_do(monkeypatch):
    monkeypatch.delenv("LLM_KEY_IN_USE", raising=False)
    with pytest.raises(RuntimeError, match=".env"):
        gemini_key()