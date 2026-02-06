"""Fix section order numbers to avoid conflict with back option

Revision ID: 005
Revises: 004
Create Date: 2026-02-06

This migration fixes the section numbering conflict where:
- General Comments had order_num = 0
- "Back to vehicles" option also uses 0
- This created ambiguity in the UI

Solution:
- Start General Comments at order_num = 1
- Shift all other sections up by 1 (1->2, 2->3, etc.)
- Reserve 0 exclusively for "Back" navigation
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Shift all section order numbers up by 1."""
    # Shift in reverse order to avoid constraint violations
    for old_num in range(15, -1, -1):
        new_num = old_num + 1
        op.execute(f"""
            UPDATE section_metadata
            SET order_num = {new_num}
            WHERE order_num = {old_num}
        """)


def downgrade() -> None:
    """Shift all section order numbers down by 1."""
    # Shift in forward order
    for old_num in range(1, 17):
        new_num = old_num - 1
        op.execute(f"""
            UPDATE section_metadata
            SET order_num = {new_num}
            WHERE order_num = {old_num}
        """)
