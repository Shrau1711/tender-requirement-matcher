import sys

import pymupdf


def main(path: str, page: str) -> None:
    with pymupdf.open(path) as doc:
        found = doc[int(page) - 1].find_tables().tables
        print(f"{len(found)} tables found")
        for i, table in enumerate(found, start=1):
            print(f"\n--- table {i}")
            for row in table.extract():
                print(row)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])