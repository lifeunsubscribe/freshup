"""add source_health_checks table

Revision ID: rk3mshza1txb
Revises: qk2lrgyz0swx
Create Date: 2026-11-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'rk3mshza1txb'
down_revision: Union[str, None] = 'qk2lrgyz0swx'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create source_health_checks table."""
    op.create_table(
        'source_health_checks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('checked_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('detail', sa.String(500), nullable=True),
        sa.Column('import_mode', sa.String(20), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    # Index for the latest-per-source query (source_type lookup + time ordering)
    op.create_index('ix_source_health_checks_source_type', 'source_health_checks', ['source_type'])
    op.create_index(
        'ix_source_health_checks_source_type_checked_at',
        'source_health_checks',
        ['source_type', 'checked_at'],
    )


def downgrade() -> None:
    """Drop source_health_checks table."""
    op.drop_index('ix_source_health_checks_source_type_checked_at', table_name='source_health_checks')
    op.drop_index('ix_source_health_checks_source_type', table_name='source_health_checks')
    op.drop_table('source_health_checks')
