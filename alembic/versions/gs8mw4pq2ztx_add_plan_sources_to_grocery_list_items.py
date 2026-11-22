"""add plan_sources to grocery_list_items

An item imported from a week's shopping list can serve several dinners. The
column records each dinner and its share, so removing a dinner takes its share
off the list again.

Revision ID: gs8mw4pq2ztx
Revises: fb7kq2m9xw3d
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'gs8mw4pq2ztx'
down_revision: Union[str, None] = 'fb7kq2m9xw3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('grocery_list_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plan_sources', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('grocery_list_items', schema=None) as batch_op:
        batch_op.drop_column('plan_sources')
