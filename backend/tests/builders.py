import pymupdf

from app.chunking.base import Chunk, Chunker, maker
from app.chunking.strategies.table_rows import TableRows
from app.extraction.atomize import AtomicRequirement
from app.extraction.evidence import Evidence, Limit
from app.judging.match import match_all
from app.judging.measure import load_aliases
from app.reading.pdf_reader import PageRecord
from app.reporting.report import assemble
from app.tender.items import Item

CALLS = 100  # fakes cost nothing, so tests set their own call limit instead of reading LLM_MAX_CALLS from the shell


def req(attribute: str, kind: str, values: list[str], unit: str | None = None, operator: str = "equals") -> AtomicRequirement:
    return AtomicRequirement(
        item=Item(title="Valves", quantity=1), pdf_page=1, source_name="n", source_value="v",
        attribute=attribute, kind=kind, operator=operator, values=values, unit=unit, evidence="product",
    )


def ev(stated: str, shape: str = "text", numbers: list[float] | None = None, unit: str | None = None,
       items: list[str] | None = None, condition: str | None = None, product: str = "yes", limit: Limit | None = None, name: str = "P") -> Evidence:
    return Evidence(
        manufacturer="m", file="f.pdf", pdf_page=2, stated=stated, product=name, same_product_type=product, quote=stated,
        shape=shape, numbers=numbers or [], unit=unit, items=items or [], condition=condition, condition_limit=limit,
    )


def picture_only_pdf(path):
    """A one-page PDF whose only content is a picture, as a scanned catalogue page is."""
    source = pymupdf.open()
    source.new_page().insert_text((72, 100), "Size Range 40 to 500 mm", fontsize=20)
    png = source[0].get_pixmap(dpi=100).tobytes("png")
    doc = pymupdf.open()
    doc.new_page().insert_image(pymupdf.Rect(0, 0, 595, 842), stream=png)
    doc.save(path)
    return path


ALIASES = load_aliases()
SIZE = req("nominal_size", "number", ["125"], "mm")
BIG = ev("40mm to 500mm", "range", [40, 500], "mm", name="Wafer")


def run(atoms, table, makers=("a",), readable=None):
    makers = list(makers)
    readable = set(makers) if readable is None else readable
    outs = {m: match_all(atoms, [m], {k: v for k, v in table.items() if k[1] == m}, ALIASES, readable) for m in makers}
    by_product = {m: [(Item(title="Valves", quantity=1), "Wafer", outs[m])] for m in makers}
    return assemble("t", atoms, ["a note"], makers, table, readable, by_product, [o for m in makers for o in outs[m]])


def chunk_page(page: PageRecord, manufacturer: str, file: str, chunker: Chunker | None = None) -> list[Chunk]:
    """One page cut by one strategy (the default unless another is given)."""
    return (chunker or TableRows()).chunk([page], maker(manufacturer, file))


class DictCache:
    """A vector cache in a dict, standing in for the Chroma one (tests/vectorstore/test_vector_cache.py tests that)."""

    def __init__(self):
        self.rows, self.puts = {}, []

    def get(self, keys):
        return {k: self.rows[k] for k in keys if k in self.rows}

    def put(self, vectors):
        self.puts.append(len(vectors))
        self.rows.update(vectors)
