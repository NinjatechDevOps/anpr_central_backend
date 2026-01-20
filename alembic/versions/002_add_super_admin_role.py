"""add_super_admin_role

Revision ID: 002_add_super_admin
Revises: 001_initial_anpr
Create Date: 2025-12-25 14:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_super_admin'
down_revision: Union[str, None] = '001_initial_anpr'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add is_super_admin column to organizations table
    op.add_column('organizations', sa.Column('is_super_admin', sa.Boolean(), nullable=False, server_default='false'))
    op.create_index('ix_organizations_is_super_admin', 'organizations', ['is_super_admin'], unique=False)


def downgrade() -> None:
    # Remove is_super_admin column
    op.drop_index('ix_organizations_is_super_admin', table_name='organizations')
    op.drop_column('organizations', 'is_super_admin')
