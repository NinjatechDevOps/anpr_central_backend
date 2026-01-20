"""change_activity_type_to_string

Revision ID: 004_change_activity_type
Revises: 003_add_activity_detected
Create Date: 2026-01-02 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_change_activity_type'
down_revision: Union[str, None] = '003_add_activity_detected'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add client_detection_id column
    op.add_column('anpr_detections', sa.Column('client_detection_id', sa.String(100), nullable=True))
    op.create_index('ix_anpr_detections_client_detection_id', 'anpr_detections', ['client_detection_id'], unique=False)

    # Change activity_type from enum to varchar
    # First, alter the column type
    op.execute("ALTER TABLE anpr_detections ALTER COLUMN activity_type TYPE VARCHAR(10) USING activity_type::text")

    # Drop the old enum type
    op.execute("DROP TYPE IF EXISTS activitytype")


def downgrade() -> None:
    # Recreate the enum type
    op.execute("CREATE TYPE activitytype AS ENUM ('in', 'out')")

    # Change activity_type back to enum
    op.execute("ALTER TABLE anpr_detections ALTER COLUMN activity_type TYPE activitytype USING activity_type::activitytype")

    # Remove client_detection_id column
    op.drop_index('ix_anpr_detections_client_detection_id', table_name='anpr_detections')
    op.drop_column('anpr_detections', 'client_detection_id')
