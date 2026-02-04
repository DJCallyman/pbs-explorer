"""add_schedule_code_to_prescribing_text_pk

Revision ID: d5de0e522718
Revises: bac77c33d8c0
Create Date: 2026-01-26 17:52:45.182141
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "d5de0e522718"
down_revision = 'bac77c33d8c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE prescribing_text_new (
            prescribing_txt_id INTEGER NOT NULL,
            schedule_code VARCHAR(20) NOT NULL,
            prescribing_txt TEXT,
            prescribing_type VARCHAR(100),
            complex_authority_rqrd_ind VARCHAR(1),
            assessment_type_code VARCHAR(50),
            apply_to_increase_mq_flag VARCHAR(1),
            apply_to_increase_nr_flag VARCHAR(1),
            created_at TIMESTAMP,
            PRIMARY KEY (prescribing_txt_id, schedule_code)
        )
    """)
    op.execute("""
        INSERT INTO prescribing_text_new
        SELECT prescribing_txt_id, 'current' as schedule_code, prescribing_txt, prescribing_type,
               complex_authority_rqrd_ind, assessment_type_code, apply_to_increase_mq_flag,
               apply_to_increase_nr_flag, created_at
        FROM prescribing_text
    """)
    op.execute("DROP TABLE prescribing_text")
    op.execute("ALTER TABLE prescribing_text_new RENAME TO prescribing_text")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE prescribing_text_old (
            prescribing_txt_id INTEGER PRIMARY KEY,
            prescribing_txt TEXT,
            prescribing_type VARCHAR(100),
            complex_authority_rqrd_ind VARCHAR(1),
            assessment_type_code VARCHAR(50),
            apply_to_increase_mq_flag VARCHAR(1),
            apply_to_increase_nr_flag VARCHAR(1),
            created_at TIMESTAMP
        )
    """)
    op.execute("""
        INSERT INTO prescribing_text_old
        SELECT prescribing_txt_id, prescribing_txt, prescribing_type, complex_authority_rqrd_ind,
               assessment_type_code, apply_to_increase_mq_flag, apply_to_increase_nr_flag, created_at
        FROM prescribing_text
    """)
    op.execute("DROP TABLE prescribing_text")
    op.execute("ALTER TABLE prescribing_text_old RENAME TO prescribing_text")
