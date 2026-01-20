"""Initial ANPR schema - Organizations and ANPR Detections

Revision ID: 001_initial_anpr
Revises:
Create Date: 2025-12-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_anpr'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create organizations and anpr_detections tables."""

    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for organizations
    op.create_index('ix_organizations_id', 'organizations', ['id'], unique=False)
    op.create_index('ix_organizations_name', 'organizations', ['name'], unique=False)
    op.create_index('ix_organizations_code', 'organizations', ['code'], unique=True)
    op.create_index('ix_organizations_token', 'organizations', ['token'], unique=True)
    op.create_index('ix_organizations_is_active', 'organizations', ['is_active'], unique=False)

    # Create anpr_detections table
    op.create_table(
        'anpr_detections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('camera_id', sa.String(100), nullable=False),
        sa.Column('camera_name', sa.String(255), nullable=True),
        sa.Column('vehicle_class', sa.String(50), nullable=True),
        sa.Column('vehicle_track_id', sa.String(100), nullable=True),
        sa.Column('image_path', sa.String(512), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'PROCESSING', 'RETRYING', 'SUCCESS', 'FAILED',
                                     name='processingstatus'), nullable=False, server_default='PENDING'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('numberplate_available', sa.Boolean(), nullable=True),
        sa.Column('numberplate_text', sa.String(20), nullable=True),
        sa.Column('numberplate_color', sa.Enum('WHITE', 'YELLOW', 'BLACK', 'BLUE', 'RED', 'GREEN', 'UNKNOWN',
                                                name='numberplatecolor'), nullable=True),
        sa.Column('vehicle_side', sa.Enum('FRONT', 'BACK', 'SIDE', 'UNKNOWN',
                                          name='vehicleside'), nullable=True),
        sa.Column('llm_confidence', sa.String(512), nullable=True),
        sa.Column('llm_raw_response', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for anpr_detections
    op.create_index('ix_anpr_detections_id', 'anpr_detections', ['id'], unique=False)
    op.create_index('ix_anpr_detections_organization_id', 'anpr_detections', ['organization_id'], unique=False)
    op.create_index('ix_anpr_detections_camera_id', 'anpr_detections', ['camera_id'], unique=False)
    op.create_index('ix_anpr_detections_vehicle_class', 'anpr_detections', ['vehicle_class'], unique=False)
    op.create_index('ix_anpr_detections_vehicle_track_id', 'anpr_detections', ['vehicle_track_id'], unique=False)
    op.create_index('ix_anpr_detections_status', 'anpr_detections', ['status'], unique=False)
    op.create_index('ix_anpr_detections_numberplate_text', 'anpr_detections', ['numberplate_text'], unique=False)
    op.create_index('ix_anpr_detections_received_at', 'anpr_detections', ['received_at'], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('anpr_detections')
    op.drop_table('organizations')

    # Drop enums (PostgreSQL specific)
    op.execute('DROP TYPE IF EXISTS processingstatus')
    op.execute('DROP TYPE IF EXISTS numberplatecolor')
    op.execute('DROP TYPE IF EXISTS vehicleside')
