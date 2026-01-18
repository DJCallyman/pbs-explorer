from __future__ import annotations

from services.sync.parser import parse_csv


def test_parse_csv() -> None:
    content = "col1,col2\nvalue1,value2\n"
    rows = parse_csv(content)
    assert rows == [{"col1": "value1", "col2": "value2"}]
