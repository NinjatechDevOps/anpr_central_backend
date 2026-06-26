"""widen_sync_jobs_status

Widen sync_jobs.status from VARCHAR(20) to VARCHAR(32). The value
"completed_with_errors" is 21 characters and overflowed the original
column, raising StringDataRightTruncation when a job finished with errors.

Revision ID: 009_widen_sync_jobs_status
Revises: 008_add_sync_jobs
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_widen_sync_jobs_status'
down_revision: Union[str, None] = '008_add_sync_jobs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'sync_jobs',
        'status',
        existing_type=sa.String(length=20),
        type_=sa.String(length=32),
        existing_nullable=False,
        existing_server_default='pending',
    )


def downgrade() -> None:
    op.alter_column(
        'sync_jobs',
        'status',
        existing_type=sa.String(length=32),
        type_=sa.String(length=20),
        existing_nullable=False,
        existing_server_default='pending',
    )
