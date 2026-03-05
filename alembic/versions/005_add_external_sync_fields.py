"""add_external_sync_fields

Revision ID: 005_add_external_sync
Revises: 004_change_activity_type
Create Date: 2026-03-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_external_sync'
down_revision: Union[str, None] = '004_change_activity_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Organizations - external server mapping
    op.add_column('organizations', sa.Column('external_org_id', sa.String(100), nullable=True))

    # AnprDetections - external server sync fields
    op.add_column('anpr_detections', sa.Column('external_vehicle_id', sa.String(100), nullable=True))
    op.add_column('anpr_detections', sa.Column('sync_status', sa.String(20), nullable=True))
    op.add_column('anpr_detections', sa.Column('sync_retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('anpr_detections', sa.Column('sync_error_message', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('anpr_detections', 'sync_error_message')
    op.drop_column('anpr_detections', 'sync_retry_count')
    op.drop_column('anpr_detections', 'sync_status')
    op.drop_column('anpr_detections', 'external_vehicle_id')
    op.drop_column('organizations', 'external_org_id')
