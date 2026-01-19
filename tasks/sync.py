from __future__ import annotations

import asyncio
import logging
import sys

from db.session import get_session
from services.sync.orchestrator import SyncOrchestrator
from services.sync.plan import SYNC_PLAN


# Configure console logging for better visibility
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)


async def run_sync() -> None:
    with get_session() as session:
        orchestrator = SyncOrchestrator(session)
        await orchestrator.sync_all(SYNC_PLAN)


if __name__ == "__main__":
    asyncio.run(run_sync())
