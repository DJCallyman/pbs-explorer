from __future__ import annotations

import asyncio
import logging
import sys

from db.session import get_session
from services.sync.orchestrator import SyncOrchestrator
from db.models import (
    ItemPrescribingTextRelationship,
    ItemRestrictionRelationship,
    RestrictionPrescribingTextRelationship,
)


RELATIONSHIP_SYNC_PLAN = {
    "item-restriction-relationships": {
        "model": ItemRestrictionRelationship,
        "key_fields": ["pbs_code", "res_code", "schedule_code"],
    },
    "item-prescribing-text-relationships": {
        "model": ItemPrescribingTextRelationship,
        "key_fields": ["pbs_code", "prescribing_txt_id", "schedule_code"],
    },
    "restriction-prescribing-text-relationships": {
        "model": RestrictionPrescribingTextRelationship,
        "key_fields": ["res_code", "prescribing_txt_id", "schedule_code"],
    },
}


async def run_relationship_sync() -> None:
    with get_session() as session:
        orchestrator = SyncOrchestrator(session, request_delay_seconds=0.5)
        await orchestrator.sync_all(RELATIONSHIP_SYNC_PLAN)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    print("Syncing relationship data only (should be ~5-10 minutes)...")
    asyncio.run(run_relationship_sync())
