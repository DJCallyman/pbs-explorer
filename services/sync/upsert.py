from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session


def _filter_row(model, row: Dict[str, Any]) -> Dict[str, Any]:
    columns = {column.name for column in model.__table__.columns}
    filtered = {key: value for key, value in row.items() if key in columns}
    if "data" in columns and "data" not in filtered:
        filtered["data"] = json.dumps(row, ensure_ascii=False)
    return filtered


def upsert_rows(
    session: Session,
    model,
    rows: Iterable[Dict[str, Any]],
    key_fields: Iterable[str],
    extra_fields: Optional[Dict[str, Any]] = None,
) -> int:
    """Basic upsert for SQLAlchemy models using merge.

    Args:
        session: SQLAlchemy session.
        model: SQLAlchemy model class.
        rows: Iterable of row dictionaries.
        key_fields: Fields to identify existing rows (unused for merge but retained for interface).
        extra_fields: Extra fields to apply to every row (e.g., endpoint metadata).
    """
    count = 0
    for row in rows:
        filtered = _filter_row(model, row)
        if extra_fields:
            filtered.update(extra_fields)
        session.merge(model(**filtered))
        count += 1
    session.commit()
    return count
