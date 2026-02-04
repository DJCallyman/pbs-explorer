"""add_event_type_code_to_item_pricing_pk

Revision ID: b74c3c824c18
Revises: 43b16f905c99
Create Date: 2026-01-26 19:35:00.000000
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "b74c3c824c18"
down_revision = '43b16f905c99'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE item_pricing_event_new (
            schedule_code VARCHAR(20) NOT NULL,
            li_item_id VARCHAR(100) NOT NULL,
            event_type_code VARCHAR(50) NOT NULL,
            percentage_applied NUMERIC(10, 4),
            created_at TIMESTAMP,
            PRIMARY KEY (schedule_code, li_item_id, event_type_code)
        )
    """)
    op.execute("""
        INSERT INTO item_pricing_event_new
        SELECT schedule_code, li_item_id, event_type_code, percentage_applied, created_at
        FROM item_pricing_event
    """)
    op.execute("DROP TABLE item_pricing_event")
    op.execute("ALTER TABLE item_pricing_event_new RENAME TO item_pricing_event")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE item_pricing_event_old (
            schedule_code VARCHAR(20) PRIMARY KEY,
            li_item_id VARCHAR(100) PRIMARY KEY,
            percentage_applied NUMERIC(10, 4),
            event_type_code VARCHAR(50),
            created_at TIMESTAMP
        )
    """)
    op.execute("""
        INSERT INTO item_pricing_event_old
        SELECT schedule_code, li_item_id, percentage_applied, event_type_code, created_at
        FROM item_pricing_event
    """)
    op.execute("DROP TABLE item_pricing_event")
    op.execute("ALTER TABLE item_pricing_event_old RENAME TO item_pricing_event")
