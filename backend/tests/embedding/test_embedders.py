import sqlite3

import numpy as np
import pytest
from builders import DictCache

from app.embedding.embed_cache import embed_cached, key_for
from app.embedding.embedder import DEFAULT, EMBEDDER, EMBEDDERS, FastEmbed, embedder
from app.vectorstore import ingest
from app.vectorstore.vector_cache import SEED_FILE

OLD_KEY_OF_WAFER = "5f9a37f1dfc704741071af4cb6d8e1423ad957bdc5157f5d9606ef1c036b618a"  # sha256("BAAI/bge-small-en-v1.5\0wafer")


class Twos:
    name = "twos-model"

    def embed(self, texts):
        return np.full((len(texts), 2), 2.0)


def test_the_default_embedder_is_the_model_every_saved_vector_was_made_with():
    assert EMBEDDER == DEFAULT == "bge-small"
    assert embedder().name == "BAAI/bge-small-en-v1.5"
    assert key_for("wafer", embedder().name) == OLD_KEY_OF_WAFER  # the key a vector was saved under before embedders were a setting


def test_the_shipped_vectors_are_found_under_the_default_embedder():
    with sqlite3.connect(f"{SEED_FILE.resolve().as_uri()}?mode=ro", uri=True) as seed:
        row = seed.execute("SELECT vector FROM vectors WHERE key = ?", (key_for("IS 13095", embedder().name),)).fetchone()
    assert row is not None and np.frombuffer(row[0], dtype=np.float32).shape == (384,)  # a query from the retrieval cases


def test_choosing_an_embedder_does_not_load_its_model():
    assert "model" not in vars(FastEmbed("BAAI/bge-small-en-v1.5"))  # loaded on first use only


def test_an_unknown_embedder_is_refused():
    with pytest.raises(ValueError, match="Unknown embedder"):
        embedder("no-such-model")


def test_a_new_embedder_is_one_line_and_keeps_its_own_vectors(tmp_path, monkeypatch):
    monkeypatch.setitem(EMBEDDERS, "twos", Twos)
    twos = embedder("twos")
    cache = DictCache()
    vectors = embed_cached(["wafer"], cache, twos)
    assert vectors.tolist() == [[2.0, 2.0]]

    class Threes(Twos):
        name = "threes-model"

        def embed(self, texts):
            return np.full((len(texts), 3), 3.0)

    # the same text under another model is embedded again, never served the first model's vector
    assert embed_cached(["wafer"], cache, Threes()).tolist() == [[3.0, 3.0, 3.0]]


def test_another_embedder_gets_its_own_chroma_folder(monkeypatch, tmp_path):
    opened = []
    monkeypatch.setattr(ingest, "chroma_store", opened.append)
    monkeypatch.setattr(ingest, "CHROMA_DIR", tmp_path / "chroma")
    ingest.open_store("chroma")
    monkeypatch.setattr(ingest, "EMBEDDER", "twos")
    ingest.open_store("chroma")
    assert opened == [tmp_path / "chroma", tmp_path / "chroma-twos"]  # vectors of another length never share a collection
