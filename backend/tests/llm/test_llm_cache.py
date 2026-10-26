import pytest
from builders import CALLS

from app.llm.llm_cache import CachedLLM


def test_repeat_request_is_served_from_disk(fake_llm, tmp_path):
    inner = fake_llm(["a"])
    llm = CachedLLM(inner, tmp_path, max_calls=CALLS)
    assert llm.generate("s", "u").text == "a"
    assert llm.generate("s", "u").text == "a"  # inner has no second reply, so this must be the cache
    assert (llm.calls, llm.hits) == (1, 1)


def test_different_requests_are_not_confused(fake_llm, tmp_path):
    llm = CachedLLM(fake_llm(["a", "b"]), tmp_path, max_calls=CALLS)
    assert [llm.generate("s", "u1").text, llm.generate("s", "u2").text] == ["a", "b"]


def test_tokens_count_real_calls_only(fake_llm, tmp_path):
    llm = CachedLLM(fake_llm(["a"]), tmp_path, max_calls=CALLS)
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
    assert CachedLLM(first, tmp_path, max_calls=CALLS).generate("s", "u").text == "a"
    assert CachedLLM(second, tmp_path, max_calls=CALLS).generate("s", "u").text == "b"


def test_a_shipped_answer_is_used_without_calling_the_model_and_is_never_written_to(fake_llm, tmp_path):
    seed, live = tmp_path / "seed", tmp_path / "live"
    CachedLLM(fake_llm(["shipped"]), seed, max_calls=CALLS).generate("s", "u")
    inner = fake_llm([])  # no reply left: any real call would fail
    llm = CachedLLM(inner, live, max_calls=CALLS, seed_dir=seed)
    assert llm.generate("s", "u").text == "shipped"
    assert (llm.calls, llm.hits) == (0, 1)
    assert not list(live.glob("*.json"))


def test_has_looks_in_the_live_cache_and_in_the_shipped_answers(fake_llm, tmp_path):
    seed, live = tmp_path / "seed", tmp_path / "live"
    CachedLLM(fake_llm(["shipped"]), seed, max_calls=CALLS).generate("s", "shipped")
    llm = CachedLLM(fake_llm(["mine"]), live, max_calls=CALLS, seed_dir=seed)
    llm.generate("s", "mine")
    assert llm.has("s", "shipped") and llm.has("s", "mine") and not llm.has("s", "never asked")


def test_a_run_remembers_which_saved_answers_it_used(fake_llm, tmp_path):
    llm = CachedLLM(fake_llm(["a"]), tmp_path, max_calls=CALLS)
    llm.generate("s", "u")
    llm.generate("s", "u")
    assert llm.used == {llm.path_for("s", "u")}


def test_exported_answers_keep_their_names_and_are_not_copied_twice(tmp_path):
    from scripts.cost.export_demo_cache import copy_answers

    made = tmp_path / "live" / "abc.json"
    made.parent.mkdir()
    made.write_text("{}", encoding="utf-8")
    out = tmp_path / "ship"
    assert copy_answers({made}, out) == 1 and (out / "abc.json").exists()
    made.write_text('{"changed": 1}', encoding="utf-8")
    assert copy_answers({made}, out) == 1 and (out / "abc.json").read_text(encoding="utf-8") == "{}"
