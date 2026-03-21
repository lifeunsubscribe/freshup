"""merge_heads

Revision ID: 8a81d70e1bd9
Revises: 2a3b4c5d6e7f, d4a8c9e2b5f1
Create Date: 2026-03-20 21:19:57.827820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a81d70e1bd9'
down_revision: Union[str, None] = ('2a3b4c5d6e7f', 'd4a8c9e2b5f1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
