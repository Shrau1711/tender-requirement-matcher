import pytest

from app.config import gemini_key


def test_picks_the_key_named_in_use(monkeypatch):
    monkeypatch.setenv("LLM_KEY_IN_USE", "MENTOR")
    monkeypatch.setenv("GEMINI_KEY_MENTOR", "m-key")
    monkeypatch.setenv("GEMINI_KEY_PERSONAL", "p-key")
    assert gemini_key() == ("MENTOR", "m-key")


def test_missing_setup_says_what_to_do(monkeypatch):
    monkeypatch.delenv("LLM_KEY_IN_USE", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match=".env"):
        gemini_key()


def test_a_plain_api_key_works_when_no_name_is_chosen(monkeypatch):
    monkeypatch.delenv("LLM_KEY_IN_USE", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "plain")
    assert gemini_key() == ("GEMINI_API_KEY", "plain")
    monkeypatch.setenv("LLM_KEY_IN_USE", "MENTOR")
    monkeypatch.setenv("GEMINI_KEY_MENTOR", "named")
    assert gemini_key() == ("MENTOR", "named")  # a named key wins


def test_the_cache_folder_can_be_moved(monkeypatch, tmp_path):
    from app.config import cache_dir

    assert cache_dir().name == ".cache"
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    assert cache_dir() == tmp_path
