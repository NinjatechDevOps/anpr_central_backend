"""sync_job_logs_use_external_org_id

Drop the redundant local organization_id column from sync_job_logs.
The external_org_id (UUID) is sufficient to identify the org and look up
its name from the organizations table via organizations.external_org_id.

Also adds an index on external_org_id for fast lookups.

Revision ID: 011_sync_job_logs_ext_org
Revises: 010_add_sync_job_logs
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011_sync_job_logs_ext_org'
down_revision: Union[str, None] = '010_add_sync_job_logs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('ix_sync_job_logs_organization_id', table_name='sync_job_logs')
    op.drop_column('sync_job_logs', 'organization_id')
    op.create_index('ix_sync_job_logs_external_org_id', 'sync_job_logs', ['external_org_id'])


def downgrade() -> None:
    op.drop_index('ix_sync_job_logs_external_org_id', table_name='sync_job_logs')
    op.add_column('sync_job_logs', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_index('ix_sync_job_logs_organization_id', 'sync_job_logs', ['organization_id'])
