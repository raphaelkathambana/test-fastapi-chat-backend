"""Remove messages table (replaced by comments)

Revision ID: 003
Revises: 002
Create Date: 2026-02-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Drop the messages table.

    The messages table was part of the old chat system and has been
    replaced by the comments table which is tied to vehicles and sections.
    """
    op.drop_table('messages')


def downgrade() -> None:
    """
    Recreate the messages table.

    This allows rolling back if needed, though data will be lost.
    """
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
