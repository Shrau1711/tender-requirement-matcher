import numpy as np

from app.services.embed_cache import embed_cached


def counting_embed():
    asked: list[str] = []

    def embed(texts: list[str]) -> np.ndarray:
        asked.extend(texts)
        return np.array([[float(len(t)), 1.0] for t in texts])

    return embed, asked


def test_text_seen_before_is_not_embedded_again(tmp_path):
    embed, asked = counting_embed()
    first = embed_cached(["wafer", "lug"], tmp_path / "c.sqlite", embed)
    second = embed_cached(["wafer", "lug"], tmp_path / "c.sqlite", embed)
    assert asked == ["wafer", "lug"] and np.allclose(first, second)


def test_only_new_text_goes_to_the_model_and_order_is_kept(tmp_path):
    embed, asked = counting_embed()
    embed_cached(["wafer"], tmp_path / "c.sqlite", embed)
    vectors = embed_cached(["lug", "wafer", "lug"], tmp_path / "c.sqlite", embed)
    assert asked == ["wafer", "lug"] and vectors[:, 0].tolist() == [3.0, 5.0, 3.0]


def test_new_text_is_embedded_in_small_batches_and_saved_as_it_goes(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.embed_cache.BATCH", 2)
    sizes = []

    def fake(texts):
        sizes.append(len(texts))
        return np.ones((len(texts), 3))

    embed_cached(["a", "b", "c", "d", "e"], tmp_path / "e.sqlite", fake)
    assert sizes == [2, 2, 1]
    embed_cached(["a", "e"], tmp_path / "e.sqlite", fake)
    assert sizes == [2, 2, 1]  # nothing new, nothing embedded
