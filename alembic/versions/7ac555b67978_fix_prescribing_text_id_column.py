"""fix_prescribing_text_id_column

Revision ID: 7ac555b67978
Revises: b74c3c824c18
Create Date: 2026-01-26 19:50:00.000000
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "7ac555b67978"
down_revision = 'b74c3c824c18'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE restriction_prescribing_text_relationships_new (
            res_code VARCHAR(100) NOT NULL,
            prescribing_text_id INTEGER NOT NULL,
            schedule_code VARCHAR(20) NOT NULL,
            pt_position INTEGER,
            PRIMARY KEY (res_code, prescribing_text_id, schedule_code)
        )
    """)
    op.execute("""
        INSERT INTO restriction_prescribing_text_relationships_new
        SELECT res_code, CAST(prescribing_txt_id AS INTEGER) as prescribing_text_id, schedule_code, pt_position
        FROM restriction_prescribing_text_relationships
    """)
    op.execute("DROP TABLE restriction_prescribing_text_relationships")
    op.execute("ALTER TABLE restriction_prescribing_text_relationships_new RENAME TO restriction_prescribing_text_relationships")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE restriction_prescribing_text_relationships_old (
            res_code VARCHAR(100) PRIMARY KEY,
            prescribing_txt_id VARCHAR(50) PRIMARY KEY,
            schedule_code VARCHAR(20) PRIMARY KEY,
            pt_position INTEGER
        )
    """)
    op.execute("""
        INSERT INTO restriction_prescribing_text_relationships_old
        SELECT res_code, CAST(prescribing_text_id AS VARCHAR(50)) as prescribing_txt_id, schedule_code, pt_position
        FROM restriction_prescribing_text_relationships
    """)
    op.execute("DROP TABLE restriction_prescribing_text_relationships")
    op.execute("ALTER TABLE restriction_prescribing_text_relationships_old RENAME TO restriction_prescribing_text_relationships")
