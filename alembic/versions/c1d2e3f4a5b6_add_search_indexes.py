"""add search indexes

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Item table: columns commonly used in search and filters
    op.create_index("ix_item_drug_name", "item", ["drug_name"])
    op.create_index("ix_item_brand_name", "item", ["brand_name"])
    op.create_index("ix_item_pbs_code", "item", ["pbs_code"])
    op.create_index("ix_item_program_code", "item", ["program_code"])
    op.create_index("ix_item_benefit_type_code", "item", ["benefit_type_code"])

    # Indication table: columns used in web search joins
    op.create_index("ix_indication_condition", "indication", ["condition"])
    op.create_index("ix_indication_severity", "indication", ["severity"])


def downgrade() -> None:
    op.drop_index("ix_indication_severity", table_name="indication")
    op.drop_index("ix_indication_condition", table_name="indication")
    op.drop_index("ix_item_benefit_type_code", table_name="item")
    op.drop_index("ix_item_program_code", table_name="item")
    op.drop_index("ix_item_pbs_code", table_name="item")
    op.drop_index("ix_item_brand_name", table_name="item")
    op.drop_index("ix_item_drug_name", table_name="item")
