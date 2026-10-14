import sys

import pymupdf


def main(path: str, page: str, y_min: str = "0", y_max: str = "99999") -> None:
    with pymupdf.open(path) as doc:
        for block in doc[int(page) - 1].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                x0, y0, _x1, _y1 = line["bbox"]
                if not float(y_min) <= y0 <= float(y_max):
                    continue
                text = "".join(span["text"] for span in line["spans"])
                first = line["spans"][0]
                print(
                    f"[{x0:.0f},{y0:.0f}] {first['font']} size={first['size']:.1f} "
                    f"bold={bool(first['flags'] & 16)} {text!r}"
                )


if __name__ == "__main__":
    main(*sys.argv[1:])