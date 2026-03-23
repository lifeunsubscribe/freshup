"""merge heads a1b2c3d4e5f7 and b1c2d3e4f5g6

Revision ID: c1d2e3f4g5h6
Revises: a1b2c3d4e5f7, b1c2d3e4f5g6
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

revision: str = 'c1d2e3f4g5h6'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f7', 'b1c2d3e4f5g6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
