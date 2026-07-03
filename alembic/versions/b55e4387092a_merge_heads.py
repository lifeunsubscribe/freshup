"""merge_heads

Revision ID: b55e4387092a
Revises: nh0iocxw7qtr, pi1jpdky8rus
Create Date: 2026-05-03 18:11:01.503290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b55e4387092a'
down_revision: Union[str, None] = ('nh0iocxw7qtr', 'pi1jpdky8rus')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
