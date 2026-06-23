"""add_soft_delete_to_anpr_detections

Revision ID: 007_add_soft_delete
Revises: 006_add_external_device_id
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_add_soft_delete'
down_revision: Union[str, None] = '006_add_external_device_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'anpr_detections',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false')
    )
    op.create_index('ix_anpr_detections_is_deleted', 'anpr_detections', ['is_deleted'])


def downgrade() -> None:
    op.drop_index('ix_anpr_detections_is_deleted', table_name='anpr_detections')
    op.drop_column('anpr_detections', 'is_deleted')
