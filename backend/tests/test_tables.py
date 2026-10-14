from app.services.pdf_reader import RawTable
from app.services.tables import is_real_table, table_rows

TORQUE = RawTable(bbox=(0, 0, 1, 1), rows=[
    ["INCH", "DN", "Differential Pressure (P)", None, None, None],
    [None, None, "Standard Disc", None, "Oversized Disc", None],
    [None, None, "PN 10", "PN 12", "PN 16", "PN 20"],
    ["5", "125", "50", "52", "66", "119"],
])


def test_merged_headers_are_given_to_the_columns_they_span():
    row = table_rows(TORQUE)[0]
    assert "Oversized Disc > PN 16: 66" in row
    assert "Standard Disc > PN 12: 52" in row


def test_row_is_also_given_as_printed():
    assert table_rows(TORQUE)[0].endswith("Row as printed: 5 125 50 52 66 119")


def test_whole_page_in_one_cell_is_not_a_table():
    fake = RawTable(bbox=(0, 0, 1, 1), rows=[["x" * 500, None], ["", "www"]])
    assert not is_real_table(fake)