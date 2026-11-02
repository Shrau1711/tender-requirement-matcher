"""Write two small made-up manufacturer documents that have no tables, for the retrieval checks.

The real catalogues are mostly tables, so the free checks said little about other kinds of documents. These two are:
- a specification of numbered clauses, where a clause runs onto the next page without repeating which pump it is about;
- a selection guide with a real flowchart: separate boxes joined by arrows.
The makers and their products are invented. The PDFs and data/eval/retrieval_cases_samples.json are committed,
so this only needs running again after a change here.

Usage: python -m scripts.eval.make_samples [output category dir]
"""
import sys
from pathlib import Path

import pymupdf

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "eval" / "samples"
LEFT, TOP, LINE = 60, 70, 16

# Each inner list is one page; a line starting with a clause number is printed bold.
SPECIFICATION = [
    ["1. General", "1.1 Scope",
     "This specification covers two pump sets for the municipal water works: a booster pump and a transfer pump.",
     "1.2 Standards", "All pumps comply with ISO 9906 Grade 2B for performance and ISO 2858 for dimensions.",
     "Flanges are drilled to EN 1092-1 PN 16."],
    ["2. Booster pump", "2.1 Duty", "Rated flow 20 m3/h at a total head of 45 m.", "Speed 2900 rpm, single stage, end suction.",
     "2.2 Construction", "Casing in stainless steel AISI 316."],
    ["Impeller in bronze LG2, closed type, dynamically balanced.", "Shaft sealed by a mechanical seal with silicon carbide faces.",
     "2.3 Motor", "Totally enclosed fan cooled motor, 7.5 kW, 415 V, 50 Hz, efficiency class IE3."],
    ["3. Transfer pump", "3.1 Duty", "Rated flow 60 m3/h at a total head of 20 m.", "Speed 1450 rpm, split case.",
     "3.2 Construction", "Casing in cast iron FG 260, impeller in cast iron.", "Gland packing of braided PTFE.",
     "3.3 Motor", "Totally enclosed fan cooled motor, 5.5 kW, 415 V, 50 Hz, efficiency class IE2."],
    ["4. Inspection and testing", "4.1 Hydrostatic test",
     "Every casing is pressure tested with water at 1.5 times the maximum working pressure for 30 minutes.",
     "4.2 Performance test", "Flow, head, power and efficiency are recorded at five duty points.",
     "5. Painting", "Two coats of epoxy primer and one coat of polyurethane finish, shade RAL 5015."],
    ["6. Warranty", "Eighteen months from supply or twelve months from commissioning, whichever is earlier.",
     "7. Documents", "Performance curves, a general arrangement drawing and the operation manual are supplied with each pump."],
]

GUIDE_INTRO = ["Valve selection guide", "This guide helps choose an isolating valve for a pipeline.",
               "Follow the flowchart on the next page from the question at the top.",
               "All valves listed are available from DN 50 to DN 600."]
GUIDE_MATERIALS = ["Body materials", "For sea water use a body in duplex stainless steel or nickel aluminium bronze.",
                   "For potable water a ductile iron body with epoxy coating is approved.",
                   "Seals are EPDM for water and graphite for steam."]
# (text, column, row) of each flowchart box, and the arrows between them by index.
BOXES = [("What does the line carry?", 1, 0),
         ("Clean water", 0, 1), ("Slurry", 1, 1), ("Steam", 2, 1),
         ("Gate valve PN 16", 0, 2), ("Knife gate valve", 1, 2), ("Globe valve class 800", 2, 2),
         ("Can the flow reverse?", 1, 3), ("Add a swing check valve", 1, 4)]
ARROWS = [(0, 1), (0, 2), (0, 3), (1, 4), (2, 5), (3, 6), (4, 7), (5, 7), (6, 7), (7, 8)]
BOX_W, BOX_H, COL_GAP, ROW_GAP = 150, 40, 30, 50


def text_page(doc: pymupdf.Document, lines: list[str], numbered: bool = True) -> None:
    page = doc.new_page()
    y = TOP
    for i, line in enumerate(lines):
        heading = (numbered and line[0].isdigit()) or (not numbered and i == 0)
        if heading and i:
            y += LINE / 2  # a little space above a heading, as in a printed document
        page.insert_text((LEFT, y), line, fontsize=11 if heading else 10, fontname="hebo" if heading else "helv")
        y += LINE


def box_rect(column: int, row: int) -> pymupdf.Rect:
    x, y = LEFT + column * (BOX_W + COL_GAP), TOP + 40 + row * (BOX_H + ROW_GAP)
    return pymupdf.Rect(x, y, x + BOX_W, y + BOX_H)


def flowchart_page(doc: pymupdf.Document) -> None:
    page = doc.new_page()
    page.insert_text((LEFT, TOP), "Choosing a valve", fontsize=14, fontname="hebo")
    rects = [box_rect(column, row) for _, column, row in BOXES]
    for (text, _, _), rect in zip(BOXES, rects, strict=True):
        page.draw_rect(rect, color=(0, 0, 0), width=1)
        page.insert_textbox(rect + (6, 6, -6, -6), text, fontsize=10, fontname="helv", align=pymupdf.TEXT_ALIGN_CENTER)
    for start, end in ARROWS:
        page.draw_line(rects[start].bottom_left + ((rects[start].width / 2), 0), rects[end].top_left + ((rects[end].width / 2), 0))


def specification_pdf(path: Path) -> None:
    doc = pymupdf.open()
    for lines in SPECIFICATION:
        text_page(doc, lines)
    doc.save(path)


def guide_pdf(path: Path) -> None:
    doc = pymupdf.open()
    text_page(doc, GUIDE_INTRO, numbered=False)
    flowchart_page(doc)
    text_page(doc, GUIDE_MATERIALS, numbered=False)
    doc.save(path)


def main(out: str = str(SAMPLES)) -> None:
    for maker, name, write in [("clausemaker", "pump-specification.pdf", specification_pdf), ("flowmaker", "valve-selection-guide.pdf", guide_pdf)]:
        folder = Path(out, "manufacturers", maker)
        folder.mkdir(parents=True, exist_ok=True)
        write(folder / name)
        print(folder / name)


if __name__ == "__main__":
    main(*sys.argv[1:2])
