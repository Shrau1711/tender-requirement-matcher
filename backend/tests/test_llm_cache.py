import pytest

from app.services.llm_cache import CachedLLM


def test_repeat_request_is_served_from_disk(fake_llm, tmp_path):
    inner = fake_llm(["a"])
    llm = CachedLLM(inner, tmp_path)
    assert llm.generate("s", "u").text == "a"
    assert llm.generate("s", "u").text == "a"  # inner has no second reply, so this must be the cache
    assert (llm.calls, llm.hits) == (1, 1)


def test_different_requests_are_not_confused(fake_llm, tmp_path):
    llm = CachedLLM(fake_llm(["a", "b"]), tmp_path)
    assert [llm.generate("s", "u1").text, llm.generate("s", "u2").text] == ["a", "b"]


def test_tokens_count_real_calls_only(fake_llm, tmp_path):
    llm = CachedLLM(fake_llm(["a"]), tmp_path)
    llm.generate("s", "u")
    llm.generate("s", "u")
    assert (llm.input_tokens, llm.output_tokens) == (10, 5)


def test_call_limit_stops_a_runaway_loop(fake_llm, tmp_path):
    llm = CachedLLM(fake_llm(["a", "b"]), tmp_path, max_calls=1)
    llm.generate("s", "u1")
    with pytest.raises(RuntimeError, match="limit 1"):
        llm.generate("s", "u2")

def test_a_changed_setting_does_not_reuse_old_answers(fake_llm, tmp_path):
    first, second = fake_llm(["a"]), fake_llm(["b"])
    first.settings, second.settings = "thinking=LOW", "thinking=HIGH"
    assert CachedLLM(first, tmp_path).generate("s", "u").text == "a"
    assert CachedLLM(second, tmp_path).generate("s", "u").text == "b"