"""Fix enum values: rename uppercase to lowercase

Revision ID: 007
Revises: 006
Create Date: 2026-02-10

Migration 002 created PostgreSQL enums with uppercase member names
(PENDING, COMPLETED, TIRE, etc.) but the SQLAlchemy model uses
values_callable to map to lowercase .value attributes (pending,
completed, tire, etc.). This causes a LookupError when reading rows.

Fix: use ALTER TYPE ... RENAME VALUE (PostgreSQL 10+) to rename
the uppercase enum labels to their lowercase equivalents.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


# Uppercase → lowercase mappings for each enum type
VEHICLE_STATUS_RENAMES = {
    'PENDING': 'pending',
    'ONLINE_EVALUATION': 'online_evaluation',
    'INSPECTION': 'inspection',
    'COMPLETED': 'completed',
    'REJECTED': 'rejected',
}

SECTION_TYPE_RENAMES = {
    'TIRE': 'tire',
    'WARRANTY': 'warranty',
    'ACCIDENT_DAMAGES': 'accident_damages',
    'PAINT': 'paint',
    'PREVIOUS_OWNERS': 'previous_owners',
    # The following were added lowercase in migration 004, no rename needed:
    # general, engine, transmission, brakes, suspension, exhaust,
    # interior, electronics, fluids, lights, ac_heating
}


def upgrade() -> None:
    """Rename enum values from uppercase to lowercase."""
    for old, new in VEHICLE_STATUS_RENAMES.items():
        op.execute(f"ALTER TYPE vehiclestatus RENAME VALUE '{old}' TO '{new}'")

    for old, new in SECTION_TYPE_RENAMES.items():
        op.execute(f"ALTER TYPE sectiontype RENAME VALUE '{old}' TO '{new}'")


def downgrade() -> None:
    """Rename enum values from lowercase back to uppercase."""
    for old, new in VEHICLE_STATUS_RENAMES.items():
        op.execute(f"ALTER TYPE vehiclestatus RENAME VALUE '{new}' TO '{old}'")

    for old, new in SECTION_TYPE_RENAMES.items():
        op.execute(f"ALTER TYPE sectiontype RENAME VALUE '{new}' TO '{old}'")
