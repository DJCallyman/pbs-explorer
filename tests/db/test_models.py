from __future__ import annotations

from db.models import Item


def test_item_model_fields() -> None:
    item = Item(li_item_id="1")
    assert getattr(item, "li_item_id") == "1"
