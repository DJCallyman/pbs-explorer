from __future__ import annotations

import asyncio

from db.session import get_session
from services.sync.orchestrator import SyncOrchestrator
from services.sync.plan import SYNC_PLAN


async def run_sync() -> None:
    with get_session() as session:
        orchestrator = SyncOrchestrator(session)
        await orchestrator.sync_all(SYNC_PLAN)


if __name__ == "__main__":
    asyncio.run(run_sync())
