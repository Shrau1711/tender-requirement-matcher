from builders import ev, req

from app.services.chunker import Chunk
from app.services.coverage import inventory, matrix, nowhere, thin, to_markdown

A, B = req("pump_type", "text", ["x"]), req("noise_level", "number", ["85"], "dBA")


def chunk(maker: str, file: str, page: int, ocr: bool = False) -> Chunk:
    return Chunk(manufacturer=maker, file=file, pdf_page=page, kind="text", section=None, text="t", ocr=ocr)


def test_the_inventory_counts_pages_chunks_and_scanned_pages_per_file():
    docs = inventory([chunk("m", "a.pdf", 1), chunk("m", "a.pdf", 1), chunk("m", "a.pdf", 2, ocr=True)])
    assert docs == {"m": {"a.pdf": {"pages": 2, "chunks": 3, "scanned_pages": 1}}}


def test_the_matrix_counts_statements_and_skips_requirements_a_catalogue_cannot_show():
    paperwork = req("test_certificate", "text", ["x"]).model_copy(update={"evidence": "paperwork"})
    grid = matrix([A, B, paperwork], ["a", "b"], {(0, "a"): [ev("x"), ev("y")], (0, "b"): [ev("x")]})
    assert grid == {"pump_type": {"a": 2, "b": 1}, "noise_level": {"a": 0, "b": 0}}


def test_a_requirement_nobody_answers_is_a_data_gap_and_a_requirement_only_some_answer_is_a_thin_spot():
    grid = {"pump_type": {"a": 2, "b": 0}, "noise_level": {"a": 0, "b": 0}}
    assert nowhere(grid) == ["noise_level"] and thin(grid) == {"a": [], "b": ["pump_type"]}


def test_the_markdown_lists_documents_the_grid_and_the_gaps():
    text = to_markdown({"m": {"a.pdf": {"pages": 2, "chunks": 3, "scanned_pages": 0}}}, {"pump_type": {"a": 1, "b": 0}})
    assert "| m | a.pdf | 2 | 3 | 0 |" in text and "| pump_type | 1 | 0 |" in text and "**b**" in text
