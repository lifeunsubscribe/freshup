"""merge phase 2.5a with processing tasks metadata

Revision ID: f3d7b193d9d1
Revises: qk2lrgyz0swx, nh0iocxw7qtr
Create Date: 2026-05-03 18:04:43.454744

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3d7b193d9d1'
down_revision: Union[str, None] = ('qk2lrgyz0swx', 'nh0iocxw7qtr')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
