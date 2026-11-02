"""Try a query against the keyword index.

Usage: python -m scripts.run.search <category_dir> "<query>" [manufacturer]
"""
import sys

from app.vectorstore.ingest import open_index


def main(category_dir: str, query: str, manufacturer: str | None) -> None:
    index = open_index(category_dir)
    for hit in index.search(query, manufacturer):
        c = hit.chunk
        print(f"\nkeyword {hit.keyword:5.2f}  meaning {hit.meaning:.2f}  {c.manufacturer} p{c.pdf_page} [{c.kind}]")
        print("   " + c.text[:300].replace("\n", "\n   "))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)