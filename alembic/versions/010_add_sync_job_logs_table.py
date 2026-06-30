"""add_sync_job_logs_table

Per-detection audit log for bulk sync jobs. Every record processed by
bulk_sync_detections_by_range (sent / skipped / failed) gets exactly one row.

Revision ID: 010_add_sync_job_logs
Revises: 009_widen_sync_jobs_status
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_add_sync_job_logs'
down_revision: Union[str, None] = '009_widen_sync_jobs_status'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'sync_job_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_job_id', sa.Integer(), nullable=False),
        sa.Column('detection_id', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('external_org_id', sa.String(length=100), nullable=True),
        sa.Column('camera_id', sa.String(length=100), nullable=True),
        sa.Column('external_device_id', sa.String(length=100), nullable=True),
        sa.Column('numberplate_text', sa.String(length=20), nullable=True),
        sa.Column('is_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('log_status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('external_vehicle_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['sync_job_id'], ['sync_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['detection_id'], ['anpr_detections.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sync_job_logs_id', 'sync_job_logs', ['id'])
    op.create_index('ix_sync_job_logs_sync_job_id', 'sync_job_logs', ['sync_job_id'])
    op.create_index('ix_sync_job_logs_detection_id', 'sync_job_logs', ['detection_id'])
    op.create_index('ix_sync_job_logs_organization_id', 'sync_job_logs', ['organization_id'])
    op.create_index('ix_sync_job_logs_log_status', 'sync_job_logs', ['log_status'])


def downgrade() -> None:
    op.drop_index('ix_sync_job_logs_log_status', table_name='sync_job_logs')
    op.drop_index('ix_sync_job_logs_organization_id', table_name='sync_job_logs')
    op.drop_index('ix_sync_job_logs_detection_id', table_name='sync_job_logs')
    op.drop_index('ix_sync_job_logs_sync_job_id', table_name='sync_job_logs')
    op.drop_index('ix_sync_job_logs_id', table_name='sync_job_logs')
    op.drop_table('sync_job_logs')
