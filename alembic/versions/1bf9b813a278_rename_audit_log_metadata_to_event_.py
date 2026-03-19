"""rename_audit_log_metadata_to_event_metadata

Revision ID: 1bf9b813a278
Revises: 425f03cb4131
Create Date: 2026-03-18 22:39:17.381625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1bf9b813a278'
down_revision: Union[str, None] = '425f03cb4131'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename metadata column to event_metadata to avoid SQLAlchemy reserved word conflict
    # Explicit type preservation improves portability across different database backends
    op.alter_column(
        'auth_audit_logs',
        'metadata',
        new_column_name='event_metadata',
        existing_type=sa.JSON(),
        existing_nullable=True
    )


def downgrade() -> None:
    # Revert the column name back to metadata
    # Explicit type preservation improves portability across different database backends
    op.alter_column(
        'auth_audit_logs',
        'event_metadata',
        new_column_name='metadata',
        existing_type=sa.JSON(),
        existing_nullable=True
    )
