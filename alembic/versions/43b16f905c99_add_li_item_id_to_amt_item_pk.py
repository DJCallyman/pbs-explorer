"""add_li_item_id_to_amt_item_pk

Revision ID: 43b16f905c99
Revises: caa3e8d1e179
Create Date: 2026-01-26 19:22:55.752654
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "43b16f905c99"
down_revision = 'caa3e8d1e179'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE amt_item_new (
            pbs_concept_id VARCHAR(50) NOT NULL,
            schedule_code VARCHAR(20) NOT NULL,
            li_item_id VARCHAR(100) NOT NULL,
            concept_type_code VARCHAR(20),
            amt_code VARCHAR(50),
            preferred_term VARCHAR(500),
            exempt_ind VARCHAR(1),
            non_amt_code VARCHAR(50),
            pbs_preferred_term VARCHAR(500),
            created_at TIMESTAMP,
            PRIMARY KEY (pbs_concept_id, schedule_code, li_item_id)
        )
    """)
    op.execute("""
        INSERT INTO amt_item_new
        SELECT pbs_concept_id, schedule_code, li_item_id, concept_type_code,
               amt_code, preferred_term, exempt_ind, non_amt_code, pbs_preferred_term, created_at
        FROM amt_item
    """)
    op.execute("DROP TABLE amt_item")
    op.execute("ALTER TABLE amt_item_new RENAME TO amt_item")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE amt_item_old (
            pbs_concept_id VARCHAR(50) PRIMARY KEY,
            concept_type_code VARCHAR(20),
            schedule_code VARCHAR(20) PRIMARY KEY,
            amt_code VARCHAR(50),
            li_item_id VARCHAR(100),
            preferred_term VARCHAR(500),
            exempt_ind VARCHAR(1),
            non_amt_code VARCHAR(50),
            pbs_preferred_term VARCHAR(500),
            created_at TIMESTAMP
        )
    """)
    op.execute("""
        INSERT INTO amt_item_old
        SELECT pbs_concept_id, concept_type_code, schedule_code, amt_code,
               li_item_id, preferred_term, exempt_ind, non_amt_code, pbs_preferred_term, created_at
        FROM amt_item
    """)
    op.execute("DROP TABLE amt_item")
    op.execute("ALTER TABLE amt_item_old RENAME TO amt_item")
