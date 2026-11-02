"""Build the standards graph from the documents the project already has, and save it to data/graph/standards.json.

Usage: python -m scripts.run.build_graph [tenders dir]

Reads every manufacturer document of every category (from the vector store when it holds them) and the requirements of
every tender whose reading is saved. Asks no model: a tender whose reading is not saved is skipped. The file is plain
JSON so every link, and where it was seen, can be read and corrected by hand.
"""
import sys
from pathlib import Path

from app.categories.config import CATEGORIES_DIR, category_dirs
from app.graph.standards import GRAPH_FILE, build
from app.llm.llm_factory import make_llm
from app.pipeline.pipeline import read_atoms
from app.reading.ocr import reader_for
from app.vectorstore.ingest import open_index

TENDERS = CATEGORIES_DIR.parent / "tenders"


def texts(tenders: Path):
    llm = make_llm()
    read_image = reader_for(llm)
    for folder in category_dirs(CATEGORIES_DIR):
        for c in open_index(folder, read_image).chunks:
            yield c.text, f"{c.manufacturer}/{c.file} page {c.pdf_page}"
    for tender in sorted(p for p in tenders.glob("*/*") if p.is_dir()):
        try:
            atoms, _ = read_atoms(llm, tender, read_image)
        except RuntimeError:  # its reading is not saved, and the call limit stops a new one
            print(f"skipped {tender.name}: its reading is not saved")
            continue
        for a in atoms:
            yield a.source_value, f"tender {tender.name} page {a.pdf_page}"


def main(tenders: str = str(TENDERS)) -> None:
    graph = build(texts(Path(tenders)))
    graph.save(GRAPH_FILE)
    together = [l for l in graph.links if l.relation == "named_together"]
    print(f"{len(graph.nodes)} standards, {sum(len(n.names) > 1 for n in graph.nodes.values())} with more than one name, "
          f"{len(together)} pairs named together. Saved to {GRAPH_FILE}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
