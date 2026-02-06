"""Add hybrid sections system with metadata table

Revision ID: 004
Revises: 003
Create Date: 2026-02-06

This migration implements the hybrid sections approach:
- Adds GENERAL section and 10 more evaluation sections to SectionType enum
- Creates section_metadata table for rich section information
- Seeds metadata for all 16 sections

Benefits:
- Comments table keeps enum (fast queries, no JOIN)
- Metadata table provides flexibility (descriptions, ordering, icons)
- Can add/update metadata without migrations
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Alter SectionType enum to add new values
    # Note: PostgreSQL doesn't support ALTER TYPE ... DROP VALUE,
    # so we can only add values in upgrade, not remove in downgrade
    op.execute("""
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'general';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'engine';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'transmission';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'brakes';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'suspension';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'exhaust';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'interior';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'electronics';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'fluids';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'lights';
        ALTER TYPE sectiontype ADD VALUE IF NOT EXISTS 'ac_heating';
    """)

    # Step 2: Create section_metadata table
    op.create_table(
        'section_metadata',
        sa.Column('section_name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('order_num', sa.Integer(), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('section_name')
    )

    # Step 3: Seed section metadata
    section_metadata = table(
        'section_metadata',
        column('section_name', sa.String),
        column('display_name', sa.String),
        column('description', sa.Text),
        column('category', sa.String),
        column('order_num', sa.Integer),
        column('icon', sa.String),
        column('is_active', sa.Boolean)
    )

    op.bulk_insert(section_metadata, [
        # General (car-level comments)
        {
            'section_name': 'general',
            'display_name': 'General Comments',
            'description': 'Overall vehicle comments not specific to any section',
            'category': 'General',
            'order_num': 0,
            'icon': '📝',
            'is_active': True
        },

        # Online Evaluation (1-3)
        {
            'section_name': 'tire',
            'display_name': 'Tire Evaluation',
            'description': 'Tire condition, tread depth, wear patterns',
            'category': 'Online Evaluation',
            'order_num': 1,
            'icon': '🛞',
            'is_active': True
        },
        {
            'section_name': 'warranty',
            'display_name': 'Warranty',
            'description': 'Warranty status, coverage details, transferability',
            'category': 'Online Evaluation',
            'order_num': 2,
            'icon': '📜',
            'is_active': True
        },
        {
            'section_name': 'accident_damages',
            'display_name': 'Accident & Damages',
            'description': 'Accident history, damage reports, repairs',
            'category': 'Online Evaluation',
            'order_num': 3,
            'icon': '⚠️',
            'is_active': True
        },

        # Inspection (4-5)
        {
            'section_name': 'paint',
            'display_name': 'Paint Inspection',
            'description': 'Paint condition, scratches, rust, touch-ups',
            'category': 'Inspection',
            'order_num': 4,
            'icon': '🎨',
            'is_active': True
        },
        {
            'section_name': 'previous_owners',
            'display_name': 'Previous Owners',
            'description': 'Ownership history, number of owners, records',
            'category': 'Inspection',
            'order_num': 5,
            'icon': '👥',
            'is_active': True
        },

        # Mechanical (6-10)
        {
            'section_name': 'engine',
            'display_name': 'Engine Check',
            'description': 'Engine condition, performance, unusual noises',
            'category': 'Mechanical',
            'order_num': 6,
            'icon': '⚙️',
            'is_active': True
        },
        {
            'section_name': 'transmission',
            'display_name': 'Transmission',
            'description': 'Transmission performance, shifting quality',
            'category': 'Mechanical',
            'order_num': 7,
            'icon': '🔧',
            'is_active': True
        },
        {
            'section_name': 'brakes',
            'display_name': 'Brakes',
            'description': 'Brake pad condition, brake fluid, responsiveness',
            'category': 'Mechanical',
            'order_num': 8,
            'icon': '🛑',
            'is_active': True
        },
        {
            'section_name': 'suspension',
            'display_name': 'Suspension',
            'description': 'Shock absorbers, springs, alignment',
            'category': 'Mechanical',
            'order_num': 9,
            'icon': '📐',
            'is_active': True
        },
        {
            'section_name': 'exhaust',
            'display_name': 'Exhaust System',
            'description': 'Exhaust condition, emissions, leaks',
            'category': 'Mechanical',
            'order_num': 10,
            'icon': '💨',
            'is_active': True
        },

        # Additional (11-15)
        {
            'section_name': 'interior',
            'display_name': 'Interior',
            'description': 'Seats, dashboard, carpets, overall cabin condition',
            'category': 'Additional',
            'order_num': 11,
            'icon': '🪑',
            'is_active': True
        },
        {
            'section_name': 'electronics',
            'display_name': 'Electronics',
            'description': 'Infotainment, sensors, electronic features',
            'category': 'Additional',
            'order_num': 12,
            'icon': '📱',
            'is_active': True
        },
        {
            'section_name': 'fluids',
            'display_name': 'Fluids',
            'description': 'Oil, coolant, brake fluid, transmission fluid levels',
            'category': 'Additional',
            'order_num': 13,
            'icon': '💧',
            'is_active': True
        },
        {
            'section_name': 'lights',
            'display_name': 'Lights',
            'description': 'Headlights, taillights, indicators, interior lights',
            'category': 'Additional',
            'order_num': 14,
            'icon': '💡',
            'is_active': True
        },
        {
            'section_name': 'ac_heating',
            'display_name': 'AC & Heating',
            'description': 'Air conditioning, heating system, climate control',
            'category': 'Additional',
            'order_num': 15,
            'icon': '❄️',
            'is_active': True
        }
    ])


def downgrade() -> None:
    """
    Drop section_metadata table.

    Note: Cannot remove values from PostgreSQL enum types.
    The new enum values will remain even after downgrade.
    """
    op.drop_table('section_metadata')
