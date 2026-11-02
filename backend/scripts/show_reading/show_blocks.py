import sys

import pymupdf


def main(path: str, page: str) -> None:
    with pymupdf.open(path) as doc:
        for block in doc[int(page) - 1].get_text("blocks", sort=True):
            x0, y0, x1, y1, text = block[:5]
            print(f"[{x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}] {text.strip()!r}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])