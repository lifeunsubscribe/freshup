"""add kind to feedback

What a note to the developer is about: wrong or badly shown information,
something not working, an idea, or other.

Revision ID: fk9wd2ms6qxe
Revises: ip4hx7nq2kzd
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fk9wd2ms6qxe'
down_revision: Union[str, None] = 'ip4hx7nq2kzd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('kind', sa.String(30), nullable=False, server_default='other')
        )


def downgrade() -> None:
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.drop_column('kind')
