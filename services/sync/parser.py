from __future__ import annotations

import json
from typing import Dict, Iterable, List, Tuple


def parse_json(content: str) -> Tuple[List[dict], Dict]:
    """Parse JSON response from PBS API.
    
    Returns:
        Tuple of (rows, metadata) where metadata contains _meta and _links
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return [], {}
    
    # Extract metadata
    metadata = {
        "_meta": data.get("_meta", {}),
        "_links": data.get("_links", [])
    }
    
    # Extract data rows - API returns them in 'data' field
    rows = data.get("data", [])
    if not isinstance(rows, list):
        rows = []
    
    return rows, metadata


def parse_csv(content: str) -> List[dict]:
    """Legacy CSV parser - kept for backward compatibility."""
    import csv
    import io
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def iter_csv(content: str) -> Iterable[dict]:
    """Legacy CSV iterator - kept for backward compatibility."""
    import csv
    import io
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        yield row
