"""add_external_device_id

Revision ID: 006_add_external_device_id
Revises: 005_add_external_sync
Create Date: 2026-03-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_external_device_id'
down_revision: Union[str, None] = '005_add_external_sync'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('anpr_detections', sa.Column('external_device_id', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('anpr_detections', 'external_device_id')
