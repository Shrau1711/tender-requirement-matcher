import pytest

from app.llm.gemini import temperature_setting


@pytest.mark.parametrize(("value", "expected"), [
    (None, (0.0, "")),  # the default: the cache key is the one every saved answer was made with
    ("0", (0.0, "")),
    ("0.0", (0.0, "")),
    ("DEFAULT", (None, ";temperature=DEFAULT")),  # the model's own temperature, as Google advises for Gemini 3
    ("default", (None, ";temperature=DEFAULT")),
    ("1", (1.0, ";temperature=1.0")),
])
def test_temperature_is_a_setting_and_only_a_changed_one_changes_the_cache_key(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    else:
        monkeypatch.setenv("LLM_TEMPERATURE", value)
    assert temperature_setting() == expected
