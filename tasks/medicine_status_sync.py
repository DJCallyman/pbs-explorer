from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.base import Base
from db.models import MedicineStatusEntry
from db.session import get_session
from services.medicine_status.sync import MedicineStatusSync


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync Medicines Status metadata into the PBS Explorer database.")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit the number of Medicines Status search pages to crawl.")
    parser.add_argument("--delay-seconds", type=float, default=0.5, help="Minimum delay between Medicines Status HTTP requests.")
    return parser


async def _run(args: argparse.Namespace) -> dict[str, int]:
    with get_session() as db:
        Base.metadata.create_all(bind=db.get_bind(), tables=[MedicineStatusEntry.__table__])
        sync = MedicineStatusSync(db, delay_seconds=args.delay_seconds)
        try:
            return await sync.run(max_pages=args.max_pages)
        finally:
            await sync.aclose()


def main() -> None:
    args = build_parser().parse_args()
    print(json.dumps(asyncio.run(_run(args)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
