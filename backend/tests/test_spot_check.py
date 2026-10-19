import csv

from scripts.spot_check import COLUMNS, tally


def test_tally_counts_each_kind_of_row_separately_and_skips_unmarked_ones(tmp_path, capsys):
    rows = [
        {"kind": "cites evidence", "verdict": "y"},
        {"kind": "cites evidence", "verdict": "n"},
        {"kind": "cites evidence", "verdict": "Y "},
        {"kind": "found nothing", "verdict": "?"},
        {"kind": "found nothing", "verdict": ""},
    ]
    path = tmp_path / "spot.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, COLUMNS, restval="")
        writer.writeheader()
        writer.writerows(rows)
    tally(str(path))
    out = capsys.readouterr().out
    assert "cites evidence: right 2/3 (66%), wrong 1, could not tell 0" in out
    assert "found nothing: right no verdicts yet" not in out and "could not tell 1" in out
    assert "unmarked rows: 1" in out
