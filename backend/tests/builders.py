from app.services.atomize import AtomicRequirement
from app.services.evidence import Evidence, Limit
from app.services.tender import Item


def req(attribute: str, kind: str, values: list[str], unit: str | None = None, operator: str = "equals") -> AtomicRequirement:
    return AtomicRequirement(
        item=Item(title="Valves", quantity=1), pdf_page=1, source_name="n", source_value="v",
        attribute=attribute, kind=kind, operator=operator, values=values, unit=unit, evidence="product",
    )


def ev(stated: str, shape: str = "text", numbers: list[float] | None = None, unit: str | None = None,
       items: list[str] | None = None, condition: str | None = None, product: str = "yes", limit: Limit | None = None, name: str = "P") -> Evidence:
    return Evidence(
        manufacturer="m", file="f.pdf", pdf_page=2, stated=stated, product=name, same_product_type=product, quote=stated,
        shape=shape, numbers=numbers or [], unit=unit, items=items or [], condition=condition, condition_limit=limit,
    )