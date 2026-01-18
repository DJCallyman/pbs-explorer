from __future__ import annotations

import csv
import io
from typing import Iterable, List


def parse_csv(content: str) -> List[dict]:
    reader = csv.DictReader(io.StringIO(content))
    return list(reader)


def iter_csv(content: str) -> Iterable[dict]:
    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        yield row
