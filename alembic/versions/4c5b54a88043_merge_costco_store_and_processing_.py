"""merge_costco_store_and_processing_updates

Revision ID: 4c5b54a88043
Revises: mg8hnbcw6psr, jd7ekzbu3mnq
Create Date: 2026-04-04 17:10:50.319850

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c5b54a88043'
down_revision: Union[str, None] = ('mg8hnbcw6psr', 'jd7ekzbu3mnq')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
