"""add_records_fetched_to_sync_state

Revision ID: 0b2fc5ebf885
Revises: 516100d2439b
Create Date: 2026-01-26 12:42:27.375560
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "0b2fc5ebf885"
down_revision = '516100d2439b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sync_state_new (
            endpoint VARCHAR(100) PRIMARY KEY,
            last_synced_schedule_code VARCHAR(20),
            last_synced_at TIMESTAMP,
            records_synced INTEGER DEFAULT 0,
            records_fetched INTEGER DEFAULT 0,
            sync_type VARCHAR(20)
        )
    """)
    op.execute("""
        INSERT INTO sync_state_new
        SELECT endpoint, last_synced_schedule_code, last_synced_at,
               CAST(records_synced AS INTEGER) as records_synced,
               0 as records_fetched,
               sync_type
        FROM sync_state
    """)
    op.execute("DROP TABLE sync_state")
    op.execute("ALTER TABLE sync_state_new RENAME TO sync_state")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE sync_state_old (
            endpoint VARCHAR(100) PRIMARY KEY,
            last_synced_schedule_code VARCHAR(20),
            last_synced_at TIMESTAMP,
            records_synced VARCHAR(50),
            sync_type VARCHAR(20)
        )
    """)
    op.execute("""
        INSERT INTO sync_state_old
        SELECT endpoint, last_synced_schedule_code, last_synced_at,
               CAST(records_synced AS VARCHAR(50)) as records_synced,
               sync_type
        FROM sync_state
    """)
    op.execute("DROP TABLE sync_state")
    op.execute("ALTER TABLE sync_state_old RENAME TO sync_state")
