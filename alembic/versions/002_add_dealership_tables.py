"""Add dealership tables: vehicles, comments, notifications

Revision ID: 002
Revises: 001
Create Date: 2026-02-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create vehicles table
    op.create_table(
        'vehicles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vin', sa.String(length=17), nullable=False),
        sa.Column('make', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=50), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'ONLINE_EVALUATION', 'INSPECTION', 'COMPLETED', 'REJECTED', name='vehiclestatus'), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('vin')
    )
    op.create_index(op.f('ix_vehicles_vin'), 'vehicles', ['vin'], unique=True)

    # Create comments table
    op.create_table(
        'comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('vehicle_id', sa.Integer(), nullable=False),
        sa.Column('section', sa.Enum('TIRE', 'WARRANTY', 'ACCIDENT_DAMAGES', 'PAINT', 'PREVIOUS_OWNERS', name='sectiontype'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_comments_vehicle_id'), 'comments', ['vehicle_id'], unique=False)
    op.create_index(op.f('ix_comments_section'), 'comments', ['section'], unique=False)

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_recipient_id'), 'notifications', ['recipient_id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_notifications_recipient_id'), table_name='notifications')
    op.drop_table('notifications')

    op.drop_index(op.f('ix_comments_section'), table_name='comments')
    op.drop_index(op.f('ix_comments_vehicle_id'), table_name='comments')
    op.drop_table('comments')

    op.drop_index(op.f('ix_vehicles_vin'), table_name='vehicles')
    op.drop_table('vehicles')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS vehiclestatus')
    op.execute('DROP TYPE IF EXISTS sectiontype')
