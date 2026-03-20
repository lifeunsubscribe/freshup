"""remove_email_field_from_auth_audit_logs_for_PII_protection

Revision ID: 2a3b4c5d6e7f
Revises: 1bf9b813a278
Create Date: 2026-03-19 14:00:00.000000

Removes the email field from auth_audit_logs table to comply with data
minimization principles. Email addresses are PII and should not be stored
in audit logs where they could be exposed to unauthorized personnel.

User IDs are sufficient for security investigations - email addresses can
be looked up from the users table when needed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a3b4c5d6e7f'
down_revision: Union[str, None] = '1bf9b813a278'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Remove email column from auth_audit_logs table.

    This migration implements data minimization by removing PII (email addresses)
    from audit logs. Only user_id is stored, which can be used to look up user
    details when needed.
    """
    # Drop the email column and its index
    op.drop_index('ix_auth_audit_logs_email', table_name='auth_audit_logs')
    op.drop_column('auth_audit_logs', 'email')


def downgrade() -> None:
    """
    Restore email column to auth_audit_logs table.

    Note: Email data will be NULL for all existing records after downgrade,
    as the data was permanently removed during upgrade.
    """
    # Re-add the email column with index
    op.add_column(
        'auth_audit_logs',
        sa.Column('email', sa.String(255), nullable=True)
    )
    op.create_index('ix_auth_audit_logs_email', 'auth_audit_logs', ['email'])
