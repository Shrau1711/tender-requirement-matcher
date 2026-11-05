"""Turning passages into vectors, cached on disk.

base.py is the interface every embedder follows; embedder.py holds the embedders by name and the one the EMBEDDER
setting chooses; embed_cache.py keeps every vector made, keyed by the model and the text, so a text is embedded once.
"""
