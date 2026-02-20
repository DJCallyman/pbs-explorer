"""add_app_setting_table

Revision ID: a1b2c3d4e5f6
Revises: 7ac555b67978
Create Date: 2026-02-21 09:00:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "7ac555b67978"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_setting",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.String(500)),
        sa.Column("updated_at", sa.TIMESTAMP),
    )
    # Seed the default medicare stats end date
    op.execute(
        "INSERT INTO app_setting (key, value) VALUES ('medicare_stats_end_date', '202511')"
    )


def downgrade() -> None:
    op.drop_table("app_setting")
