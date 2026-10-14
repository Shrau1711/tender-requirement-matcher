import sys

from app.services.pdf_reader import read_pdf


def main(path: str, page: str) -> None:
    doc = read_pdf(path)
    print(doc.pages[int(page) - 1].text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])