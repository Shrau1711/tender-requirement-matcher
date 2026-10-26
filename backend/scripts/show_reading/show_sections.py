import sys

from app.reading.layout import build_sections
from app.reading.pdf_reader import read_pdf


def main(path: str, page: str) -> None:
    for section in build_sections(read_pdf(path).pages[int(page) - 1].lines):
        print(f"\n## {section.heading}")
        for f in section.fields:
            print(f"   {f.label}: {f.value}")
        for s in section.statements:
            print(f"   (statement) {s}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])