from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import Date, Float, Integer, Numeric, TIMESTAMP
from sqlalchemy.orm import Session


def _generate_id(model, row: Dict[str, Any]) -> Optional[str]:
    """Generate ID for BaseReference if needed."""
    if model.__tablename__ == "base_reference" and "id" not in row:
        endpoint = row.get("endpoint", "")
        
        # For BaseReference with compound data, use all fields except metadata
        # to ensure complete uniqueness
        excluded_fields = {"_meta", "_links", "id", "endpoint"}
        id_fields = {k: v for k, v in row.items() if k not in excluded_fields}
        
        if id_fields:
            # Use full data payload for complete uniqueness - hash all fields
            combined = f"{endpoint}:{json.dumps(id_fields, sort_keys=True)}"
        else:
            # Fallback: use the entire row
            combined = f"{endpoint}:{json.dumps(row, sort_keys=True)}"
        
        return hashlib.md5(combined.encode()).hexdigest()
    return None


def _filter_row(model, row: Dict[str, Any]) -> Dict[str, Any]:
    columns = {column.name for column in model.__table__.columns}
    filtered = {key: value for key, value in row.items() if key in columns}
    if "data" in columns and "data" not in filtered:
        filtered["data"] = json.dumps(row, ensure_ascii=False)
    
    # Generate ID for BaseReference if missing
    generated_id = _generate_id(model, row)
    if generated_id:
        filtered["id"] = generated_id
    
    # Convert string dates and timestamps to proper Python objects, and handle empty strings
    for column in model.__table__.columns:
        col_name = column.name
        if col_name in filtered and filtered[col_name] is not None:
            value = filtered[col_name]
            
            # Convert empty strings to None for numeric and date columns
            if isinstance(value, str) and value == "":
                if isinstance(column.type, (Numeric, Float, Integer, Date, TIMESTAMP)):
                    filtered[col_name] = None
                    continue
            
            # Convert string dates to date objects
            if isinstance(column.type, Date) and isinstance(value, str):
                try:
                    # Handle ISO format dates (YYYY-MM-DD)
                    filtered[col_name] = datetime.fromisoformat(value).date()
                except (ValueError, AttributeError):
                    pass
            
            # Convert string timestamps to datetime objects
            elif isinstance(column.type, TIMESTAMP) and isinstance(value, str):
                try:
                    # Handle ISO format timestamps (handles timezone info)
                    filtered[col_name] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass
    
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
    seen_keys = set()
    
    for row in rows:
        filtered = _filter_row(model, row)
        if extra_fields:
            filtered.update(extra_fields)
        
        # Skip duplicate rows within this batch by checking key fields
        # This prevents duplicate constraint violations when the API returns duplicates
        key_values = tuple(filtered.get(key) for key in key_fields)
        if key_values in seen_keys:
            continue
        seen_keys.add(key_values)
        
        session.merge(model(**filtered))
        count += 1
    session.commit()
    return count
