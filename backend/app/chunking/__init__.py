"""Cutting manufacturer documents into passages that can be searched.

base.py holds the Chunk and the Chunker interface, strategies/ the ways of cutting, router.py the choice between them,
and corpus.py reads a category's documents with the chosen strategy.
"""
