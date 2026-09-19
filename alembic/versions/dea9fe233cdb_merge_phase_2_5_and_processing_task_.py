"""merge phase 2.5 and processing task metadata heads

Revision ID: dea9fe233cdb
Revises: qk2lrgyz0swx, nh0iocxw7qtr
Create Date: 2026-09-18 17:55:33.695332

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dea9fe233cdb'
down_revision: Union[str, None] = ('qk2lrgyz0swx', 'nh0iocxw7qtr')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
