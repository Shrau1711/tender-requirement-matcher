from app.services.bid_details import category_of, parse_bid_details

PAGE = """Ministry Of Coal
वभाग का नाम/Department Name
Coal India Limited
संगठन का नाम/Organisation Name
Mahanadi Coalfields Limited
काया%लय का नाम/Office Name
Mcl Sambalpur Odisha
कुल मा ा/Total Quantity
19
व'तु (ेणी /Item Category
Horizontal Centrifugal Pump sets 38 LPS x 160 mtrs head
with FLP 550 Volts Electricals & accessories
GeMARPTS म* खोजी गई -'.ं/स / Searched
Strings used in GeMARPTS
"""


def test_the_buyer_and_product_are_read_from_the_bid_page():
    found = parse_bid_details(PAGE)
    assert found["buyer"] == "Mahanadi Coalfields Limited"
    assert found["product"] == "Horizontal Centrifugal Pump sets 38 LPS x 160 mtrs head with FLP 550 Volts Electricals & accessories"
    assert found["category"] == "pumps"


def test_a_page_without_those_fields_gives_empty_values():
    assert parse_bid_details("nothing here") == {"buyer": "", "product": "", "category": ""}


def test_the_category_comes_from_the_config_words():
    assert category_of("BALL VALVE 150 mm") == "valves"
    assert category_of("steel plate") == ""
