"""fix_summary_of_change_pk

Revision ID: bac77c33d8c0
Revises: 0b2fc5ebf885
Create Date: 2026-01-26 13:19:35.367542
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "bac77c33d8c0"
down_revision = '0b2fc5ebf885'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE summary_of_change_new (
            schedule_code VARCHAR(20) NOT NULL,
            source_schedule_code VARCHAR(20) NOT NULL,
            changed_table VARCHAR(50) NOT NULL,
            table_keys TEXT NOT NULL,
            target_effective_date VARCHAR(20),
            source_effective_date VARCHAR(20),
            target_revision_number INTEGER,
            source_revision_number INTEGER,
            target_publication_status VARCHAR(20),
            source_publication_status VARCHAR(20),
            changed_endpoint VARCHAR(100),
            change_type VARCHAR(10),
            sql_statement TEXT,
            change_detail TEXT,
            previous_detail TEXT,
            deleted_ind VARCHAR(1),
            new_ind VARCHAR(1),
            modified_ind VARCHAR(1),
            created_at TIMESTAMP,
            PRIMARY KEY (schedule_code, source_schedule_code, changed_table, table_keys)
        )
    """)
    op.execute("""
        INSERT INTO summary_of_change_new
        SELECT schedule_code, source_schedule_code, changed_table, table_keys,
               target_effective_date, source_effective_date, target_revision_number,
               source_revision_number, target_publication_status, source_publication_status,
               changed_endpoint, change_type, sql_statement, change_detail, previous_detail,
               deleted_ind, new_ind, modified_ind, created_at
        FROM summary_of_change
    """)
    op.execute("DROP TABLE summary_of_change")
    op.execute("ALTER TABLE summary_of_change_new RENAME TO summary_of_change")


def downgrade() -> None:
    op.execute("""
        CREATE TABLE summary_of_change_old (
            schedule_code VARCHAR(20) PRIMARY KEY,
            source_schedule_code VARCHAR(20) PRIMARY KEY,
            target_effective_date VARCHAR(20),
            source_effective_date VARCHAR(20),
            target_revision_number INTEGER,
            source_revision_number INTEGER,
            target_publication_status VARCHAR(20),
            source_publication_status VARCHAR(20),
            changed_table VARCHAR(50),
            changed_endpoint VARCHAR(100),
            change_type VARCHAR(10),
            sql_statement TEXT,
            table_keys TEXT,
            change_detail TEXT,
            previous_detail TEXT,
            deleted_ind VARCHAR(1),
            new_ind VARCHAR(1),
            modified_ind VARCHAR(1),
            created_at TIMESTAMP
        )
    """)
    op.execute("""
        INSERT INTO summary_of_change_old
        SELECT schedule_code, source_schedule_code, target_effective_date, source_effective_date,
               target_revision_number, source_revision_number, target_publication_status,
               source_publication_status, changed_table, changed_endpoint, change_type,
               sql_statement, table_keys, change_detail, previous_detail, deleted_ind,
               new_ind, modified_ind, created_at
        FROM summary_of_change
    """)
    op.execute("DROP TABLE summary_of_change")
    op.execute("ALTER TABLE summary_of_change_old RENAME TO summary_of_change")
