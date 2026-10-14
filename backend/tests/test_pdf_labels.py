from app.services.pdf_reader import printed_label


class Page:
    def __init__(self, label=None, broken=False):
        self.label, self.broken = label, broken

    def get_label(self):
        if self.broken:
            raise IndexError("list index out of range")  # what pymupdf does with a broken page-label table
        return self.label


def test_a_printed_page_number_is_returned():
    assert printed_label(Page("iv")) == "iv"


def test_no_label_is_none():
    assert printed_label(Page("")) is None


def test_a_broken_label_table_costs_only_the_label():
    assert printed_label(Page(broken=True)) is None
