"""add_limit_to_markup_band_pk

Revision ID: caa3e8d1e179
Revises: d5de0e522718
Create Date: 2026-01-26 18:15:14.260672
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "caa3e8d1e179"
down_revision = 'd5de0e522718'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE markup_band_new (
            schedule_code VARCHAR(20) NOT NULL,
            program_code VARCHAR(10) NOT NULL,
            dispensing_rule_mnem VARCHAR(100) NOT NULL,
            markup_band_code VARCHAR(50) NOT NULL,
            "limit" NUMERIC(15, 4) NOT NULL,
            variable NUMERIC(12, 2),
            offset NUMERIC(12, 2),
            fixed NUMERIC(15, 4),
            created_at TIMESTAMP,
            PRIMARY KEY (schedule_code, program_code, dispensing_rule_mnem, markup_band_code, "limit")
        )
    """)
    op.execute("""
        INSERT INTO markup_band_new
        SELECT schedule_code, program_code, dispensing_rule_mnem, markup_band_code,
               "limit", variable, offset, fixed, created_at
        FROM markup_band
    """)
    op.execute("DROP TABLE markup_band")
    op.execute("ALTER TABLE markup_band_new RENAME TO markup_band")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE markup_band_old (
            schedule_code VARCHAR(20) PRIMARY KEY,
            program_code VARCHAR(10) PRIMARY KEY,
            dispensing_rule_mnem VARCHAR(100) PRIMARY KEY,
            markup_band_code VARCHAR(50) PRIMARY KEY,
            "limit" NUMERIC(15, 4),
            variable NUMERIC(12, 2),
            offset NUMERIC(12, 2),
            fixed NUMERIC(15, 4),
            created_at TIMESTAMP
        )
    """)
    op.execute("""
        INSERT INTO markup_band_old
        SELECT schedule_code, program_code, dispensing_rule_mnem, markup_band_code,
               "limit", variable, offset, fixed, created_at
        FROM markup_band
    """)
    op.execute("DROP TABLE markup_band")
    op.execute("ALTER TABLE markup_band_old RENAME TO markup_band")
