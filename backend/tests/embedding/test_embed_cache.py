import numpy as np
from builders import DictCache

from app.embedding.embed_cache import embed_cached, key_for


class Fake:
    """An embedder made of a plain function."""

    def __init__(self, embed, name="fake-model"):
        self.embed, self.name = embed, name


def counting_embed():
    asked: list[str] = []

    def embed(texts: list[str]) -> np.ndarray:
        asked.extend(texts)
        return np.array([[float(len(t)), 1.0] for t in texts])

    return Fake(embed), asked


def test_text_seen_before_is_not_embedded_again():
    embed, asked, cache = *counting_embed(), DictCache()
    first = embed_cached(["wafer", "lug"], cache, embed)
    second = embed_cached(["wafer", "lug"], cache, embed)
    assert asked == ["wafer", "lug"] and np.array_equal(first, second)


def test_only_new_text_goes_to_the_model_and_order_is_kept():
    embed, asked, cache = *counting_embed(), DictCache()
    embed_cached(["wafer"], cache, embed)
    vectors = embed_cached(["lug", "wafer", "lug"], cache, embed)
    assert asked == ["wafer", "lug"] and vectors[:, 0].tolist() == [3.0, 5.0, 3.0]


def test_new_text_is_embedded_in_small_batches_and_saved_as_it_goes(monkeypatch):
    monkeypatch.setattr("app.embedding.embed_cache.BATCH", 2)
    sizes, cache = [], DictCache()

    def fake(texts):
        sizes.append(len(texts))
        return np.ones((len(texts), 3))

    embed_cached(["a", "b", "c", "d", "e"], cache, Fake(fake))
    assert sizes == [2, 2, 1] and cache.puts == [2, 2, 1]
    embed_cached(["a", "e"], cache, Fake(fake))
    assert sizes == [2, 2, 1]  # nothing new, nothing embedded


def test_vectors_are_kept_as_float32_under_the_text_and_model_key():
    embed, _, cache = *counting_embed(), DictCache()
    embed_cached(["wafer"], cache, embed)
    assert list(cache.rows) == [key_for("wafer", "fake-model")] and cache.rows[key_for("wafer", "fake-model")].dtype == np.float32


def test_a_stored_vector_is_returned_as_stored_and_not_recomputed():
    embed, asked, cache = *counting_embed(), DictCache()
    cache.rows[key_for("wafer", "fake-model")] = np.array([0.25, 0.5], dtype=np.float32)  # as an imported seed vector
    assert embed_cached(["wafer"], cache, embed).tolist() == [[0.25, 0.5]] and asked == []
