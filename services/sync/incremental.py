from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import delete

from services.sync.client import PBSAPIClient
from services.sync.parser import parse_json
from services.sync.upsert import upsert_rows

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger("sync")


def _parse_json(data: Any) -> Any:
    """Parse JSON if string, otherwise return as-is."""
    if isinstance(data, str):
        return json.loads(data)
    return data


class IncrementalSync:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.client = PBSAPIClient()

    async def get_changes(
        self,
        source_schedule_code: str,
        target_schedule_code: str,
        endpoint_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch changes from summary-of-changes endpoint."""
        target_effective_date = await self._get_schedule_effective_date(target_schedule_code)
        if not target_effective_date:
            raise Exception(f"Could not get effective date for schedule {target_schedule_code}")
        
        filter_expr = f"source_schedule_code eq {source_schedule_code} and target_effective_date eq '{target_effective_date}'"
        if endpoint_filter:
            filter_expr += f" and changed_endpoint eq '{endpoint_filter}'"

        response = await self.client.get(
            "/summary-of-changes",
            params={
                "filter": filter_expr,
                "limit": 40000,
                "fields": "changed_endpoint,change_type,change_detail,previous_detail,changed_table,table_keys",
            },
        )

        rows, _ = parse_json(response.text)
        return rows

    async def _get_schedule_effective_date(self, schedule_code: str) -> Optional[str]:
        """Get the effective date for a schedule code from the API."""
        response = await self.client.get(
            "/schedules",
            params={
                "filter": f"schedule_code eq {schedule_code}",
                "limit": 1,
                "fields": "effective_date",
            },
        )
        rows, _ = parse_json(response.text)
        if rows:
            return rows[0].get("effective_date")
        return None

    async def apply_change(
        self,
        change: Dict[str, Any],
        model,
        key_fields: List[str],
    ) -> bool:
        """Apply a single change (INSERT, UPDATE, or DELETE)."""
        change_type = change.get("change_type", "").upper()
        change_detail = change.get("change_detail")
        previous_detail = change.get("previous_detail")

        if change_type == "INSERT":
            if change_detail:
                data = _parse_json(change_detail)
                if isinstance(data, dict):
                    upsert_rows(self.session, model, [data], key_fields)
                    return True

        elif change_type == "UPDATE":
            if change_detail:
                data = _parse_json(change_detail)
                if isinstance(data, dict):
                    upsert_rows(self.session, model, [data], key_fields)
                    return True

        elif change_type == "DELETE":
            table_keys = change.get("table_keys")
            if table_keys:
                keys = _parse_json(table_keys)
                if isinstance(keys, dict):
                    await self._delete_by_keys(model, key_fields, keys)
                    return True

        return False

    async def _delete_by_keys(
        self,
        model,
        key_fields: List[str],
        keys: Dict[str, Any],
    ) -> None:
        """Delete a record by its key values."""
        where_clauses = []
        for key_field in key_fields:
            if key_field in keys:
                column = getattr(model, key_field, None)
                if column is not None:
                    where_clauses.append(column == keys[key_field])

        if where_clauses:
            stmt = delete(model).where(*where_clauses)
            self.session.execute(stmt)
            self.session.commit()

    async def sync_endpoint_incremental(
        self,
        endpoint: str,
        model,
        key_fields: List[str],
        source_schedule: str,
        target_schedule: str,
    ) -> int:
        """Sync an endpoint incrementally using summary-of-changes."""
        logger.info(f"Starting incremental sync for {endpoint}: {source_schedule} -> {target_schedule}")

        changes = await self.get_changes(source_schedule, target_schedule, endpoint)

        if not changes:
            logger.info(f"No changes found for {endpoint}")
            return 0

        applied_count = 0
        for change in changes:
            try:
                success = await self.apply_change(change, model, key_fields)
                if success:
                    applied_count += 1
            except Exception as e:
                logger.error(f"Error applying change to {endpoint}: {e}")
                continue

        logger.info(f"Applied {applied_count} changes to {endpoint}")
        return applied_count

    async def get_latest_schedule_code(self) -> Optional[str]:
        """Get the latest available schedule code from the API (by effective_date)."""
        response = await self.client.get(
            "/schedules",
            params={
                "limit": 1,
                "sort": "desc",
                "sort_fields": "effective_date",
            },
        )

        rows, _ = parse_json(response.text)
        if rows:
            schedule_code = rows[0].get("schedule_code")
            return str(schedule_code) if schedule_code else None
        return None

    async def get_current_db_schedule(self) -> Optional[str]:
        """Get the latest schedule code currently in the database (by effective_date)."""
        from sqlalchemy import select, desc
        from db.models import Schedule

        result = self.session.execute(
            select(Schedule.schedule_code).order_by(desc(Schedule.effective_date)).limit(1)
        )
        row = result.fetchone()
        return row[0] if row else None

    async def get_previous_db_schedule(self, current_schedule: str) -> Optional[str]:
        """Get the previous schedule code before current in the database (by effective_date)."""
        from sqlalchemy import select, desc
        from db.models import Schedule

        # First get the effective_date of the current schedule
        current_result = self.session.execute(
            select(Schedule.effective_date).where(Schedule.schedule_code == current_schedule)
        )
        current_date = current_result.scalar()

        if not current_date:
            return None

        # Get the previous schedule by effective_date
        result = self.session.execute(
            select(Schedule.schedule_code)
            .where(Schedule.effective_date < current_date)
            .order_by(desc(Schedule.effective_date))
            .limit(1),
        )
        row = result.fetchone()
        return row[0] if row else None
