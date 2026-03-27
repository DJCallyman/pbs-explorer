"""add_web_auth_and_saved_report_tables

Revision ID: e4f5g6h7i8j9
Revises: c1d2e3f4a5b6
Create Date: 2026-03-24 20:10:00.000000
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e4f5g6h7i8j9"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_user",
        sa.Column("username", sa.String(length=100), primary_key=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP()),
        sa.Column("updated_at", sa.TIMESTAMP()),
    )
    op.create_table(
        "web_session",
        sa.Column("session_id", sa.String(length=255), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP()),
        sa.Column("last_seen_at", sa.TIMESTAMP()),
        sa.Column("expires_at", sa.TIMESTAMP()),
        sa.Column("revoked_at", sa.TIMESTAMP()),
    )
    op.create_table(
        "saved_report",
        sa.Column("slug", sa.String(length=200), primary_key=True),
        sa.Column("owner", sa.String(length=100)),
        sa.Column("name", sa.String(length=255)),
        sa.Column("description", sa.Text()),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP()),
        sa.Column("updated_at", sa.TIMESTAMP()),
    )


def downgrade() -> None:
    op.drop_table("saved_report")
    op.drop_table("web_session")
    op.drop_table("web_user")
