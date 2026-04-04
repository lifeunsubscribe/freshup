"""merge_all_phase_4_migrations

Revision ID: 5238c466e2a3
Revises: 4c5b54a88043, c1d2e3f4g5h6
Create Date: 2026-04-04 17:11:01.213070

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5238c466e2a3'
down_revision: Union[str, None] = ('4c5b54a88043', 'c1d2e3f4g5h6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
