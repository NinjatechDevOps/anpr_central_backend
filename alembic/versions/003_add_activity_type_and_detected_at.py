"""add_activity_type_and_detected_at_to_anpr_detections

Revision ID: 003_add_activity_detected
Revises: 002_add_super_admin
Create Date: 2026-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_activity_detected'
down_revision: Union[str, None] = '002_add_super_admin'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add activity_type column
    op.execute("CREATE TYPE activitytype AS ENUM ('in', 'out')")
    op.add_column('anpr_detections', sa.Column('activity_type', sa.Enum('in', 'out', name='activitytype'), nullable=True))
    op.create_index('ix_anpr_detections_activity_type', 'anpr_detections', ['activity_type'], unique=False)

    # Add detected_at column
    op.add_column('anpr_detections', sa.Column('detected_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_anpr_detections_detected_at', 'anpr_detections', ['detected_at'], unique=False)

    # Remove received_at column (redundant with created_at from BaseModel)
    op.drop_index('ix_anpr_detections_received_at', table_name='anpr_detections')
    op.drop_column('anpr_detections', 'received_at')


def downgrade() -> None:
    # Re-add received_at column
    op.add_column('anpr_detections', sa.Column('received_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')))
    op.create_index('ix_anpr_detections_received_at', 'anpr_detections', ['received_at'], unique=False)

    # Remove detected_at column
    op.drop_index('ix_anpr_detections_detected_at', table_name='anpr_detections')
    op.drop_column('anpr_detections', 'detected_at')

    # Remove activity_type column
    op.drop_index('ix_anpr_detections_activity_type', table_name='anpr_detections')
    op.drop_column('anpr_detections', 'activity_type')
    op.execute("DROP TYPE activitytype")
