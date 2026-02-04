"""add_schedule_code_to_organisation_pk

Revision ID: 516100d2439b
Revises: ae2351fa6f28
Create Date: 2026-01-26 12:25:29.929816
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "516100d2439b"
down_revision = 'ae2351fa6f28'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite doesn't support altering primary keys, so we recreate the table
    op.execute("""
        CREATE TABLE organisation_new (
            organisation_id INTEGER NOT NULL,
            schedule_code VARCHAR(20) NOT NULL,
            name VARCHAR(500),
            abn VARCHAR(20),
            street_address VARCHAR(500),
            city VARCHAR(200),
            state VARCHAR(100),
            postcode VARCHAR(20),
            telephone_number VARCHAR(50),
            facsimile_number VARCHAR(50),
            created_at TIMESTAMP,
            PRIMARY KEY (organisation_id, schedule_code)
        )
    """)
    op.execute("""
        INSERT INTO organisation_new
        SELECT organisation_id, 'current' as schedule_code, name, abn, street_address,
               city, state, postcode, telephone_number, facsimile_number, created_at
        FROM organisation
    """)
    op.execute("DROP TABLE organisation")
    op.execute("ALTER TABLE organisation_new RENAME TO organisation")


def downgrade() -> None:
    # Recreate with original schema
    op.execute("""
        CREATE TABLE organisation_old (
            organisation_id INTEGER NOT NULL PRIMARY KEY,
            name VARCHAR(500),
            abn VARCHAR(20),
            street_address VARCHAR(500),
            city VARCHAR(200),
            state VARCHAR(100),
            postcode VARCHAR(20),
            telephone_number VARCHAR(50),
            facsimile_number VARCHAR(50),
            created_at TIMESTAMP
        )
    """)
    op.execute("""
        INSERT INTO organisation_old
        SELECT organisation_id, name, abn, street_address, city, state, postcode,
               telephone_number, facsimile_number, created_at
        FROM organisation
    """)
    op.execute("DROP TABLE organisation")
    op.execute("ALTER TABLE organisation_old RENAME TO organisation")
