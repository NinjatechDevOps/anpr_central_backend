"""add_sync_jobs_table

Revision ID: 008_add_sync_jobs
Revises: 007_add_soft_delete
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_sync_jobs'
down_revision: Union[str, None] = '007_add_soft_delete'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sync_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ip', sa.String(length=64), nullable=True),
        sa.Column('from_datetime', sa.DateTime(timezone=True), nullable=False),
        sa.Column('to_datetime', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('total_records', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fail_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('celery_task_id', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sync_jobs_id', 'sync_jobs', ['id'])
    op.create_index('ix_sync_jobs_ip', 'sync_jobs', ['ip'])
    op.create_index('ix_sync_jobs_from_datetime', 'sync_jobs', ['from_datetime'])
    op.create_index('ix_sync_jobs_to_datetime', 'sync_jobs', ['to_datetime'])
    op.create_index('ix_sync_jobs_status', 'sync_jobs', ['status'])
    op.create_index('ix_sync_jobs_celery_task_id', 'sync_jobs', ['celery_task_id'])


def downgrade() -> None:
    op.drop_index('ix_sync_jobs_celery_task_id', table_name='sync_jobs')
    op.drop_index('ix_sync_jobs_status', table_name='sync_jobs')
    op.drop_index('ix_sync_jobs_to_datetime', table_name='sync_jobs')
    op.drop_index('ix_sync_jobs_from_datetime', table_name='sync_jobs')
    op.drop_index('ix_sync_jobs_ip', table_name='sync_jobs')
    op.drop_index('ix_sync_jobs_id', table_name='sync_jobs')
    op.drop_table('sync_jobs')
