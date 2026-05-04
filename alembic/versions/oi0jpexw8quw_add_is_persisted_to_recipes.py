"""add is_persisted to recipes

Revision ID: oi0jpexw8quw
Revises: nh9iocxw7qtv
Create Date: 2026-05-03 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'oi0jpexw8quw'
down_revision: Union[str, None] = 'nh9iocxw7qtv'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_persisted column to recipes table with default true."""
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_persisted', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Remove is_persisted column from recipes table."""
    with op.batch_alter_table('recipes', schema=None) as batch_op:
        batch_op.drop_column('is_persisted')
