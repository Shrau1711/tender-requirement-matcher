from app.chunking.base import chunk_document
from app.chunking.router import choose
from app.chunking.strategies.structure import Structure
from app.reading.pdf_reader import read_pdf
from scripts.eval.make_samples import BOXES, guide_pdf, specification_pdf


def test_a_drawn_flowchart_is_found_with_its_boxes_and_the_lines_between_them(tmp_path):
    guide_pdf(tmp_path / "guide.pdf")
    chart = read_pdf(tmp_path / "guide.pdf").pages[1]
    assert len(chart.boxes) == len(BOXES) and not chart.tables
    assert len(chart.links) == 10  # every arrow in the drawing


def test_each_box_of_a_flowchart_is_a_chunk_with_the_boxes_joined_to_it(tmp_path):
    guide_pdf(tmp_path / "guide.pdf")
    doc = read_pdf(tmp_path / "guide.pdf")
    assert choose(doc)[0] == "structure"
    texts = [c.text for c in chunk_document(doc, Structure()) if c.pdf_page == 2]
    assert "What does the line carry? ->\nSlurry\n-> Knife gate valve" in texts
    assert "Choosing a valve" in texts  # the title, outside the boxes


def test_a_specification_keeps_the_pump_it_is_about_when_a_clause_runs_onto_the_next_page(tmp_path):
    specification_pdf(tmp_path / "spec.pdf")
    doc = read_pdf(tmp_path / "spec.pdf")
    assert choose(doc)[0] == "structure"
    page_three = [c.text for c in chunk_document(doc, Structure()) if c.pdf_page == 3]
    assert page_three[0].startswith("2. Booster pump > 2.2 Construction\nImpeller in bronze")
