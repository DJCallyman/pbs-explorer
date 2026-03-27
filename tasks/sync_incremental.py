from __future__ import annotations

import asyncio
import logging
import sys

from db.session import get_session
from services.sync.orchestrator import SyncOrchestrator


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)


async def run_incremental_sync() -> None:
    with get_session() as session:
        orchestrator = SyncOrchestrator(session)
        await orchestrator.sync_all_incremental()


if __name__ == "__main__":
    asyncio.run(run_incremental_sync())
