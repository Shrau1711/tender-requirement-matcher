"""Where the chunks of the manufacturers' documents and their vectors are kept, and the nearest ones found.

base.py is the interface every store follows; memory.py keeps everything in memory and compares exactly (the original
behaviour); chroma.py keeps it on disk with Chroma, so a document is read and embedded once; ingest.py puts a category's
documents into a store and builds the search index over them.
"""
