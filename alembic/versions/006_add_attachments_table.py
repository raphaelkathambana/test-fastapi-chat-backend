"""Add attachments table for file uploads

Revision ID: 006
Revises: 005
Create Date: 2026-02-10

Adds the attachments table supporting:
- Exclusive binding to comments (nullable FK, set once)
- Envelope encryption (per-file AES key wrapped with Fernet)
- Chunked upload tracking
- Lifecycle status management (uploading → processing → ready/quarantined)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the attachments table."""
    op.create_table(
        'attachments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('comment_id', sa.Integer, sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('uploader_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('upload_session', sa.String(36), nullable=True, index=True),

        # File metadata
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('file_size', sa.BigInteger, nullable=False),
        sa.Column('storage_key', sa.String(500), nullable=False, unique=True),
        sa.Column('checksum_sha256', sa.String(64), nullable=False),

        # Envelope encryption
        sa.Column('encrypted_file_key', sa.Text, nullable=False),

        # Thumbnail
        sa.Column('thumbnail_storage_key', sa.String(500), nullable=True),

        # Lifecycle
        sa.Column('status', sa.Enum(
            'uploading', 'processing', 'ready', 'quarantined', 'orphaned',
            name='attachmentstatus'
        ), nullable=False, default='uploading', index=True),

        # Chunked upload tracking
        sa.Column('total_chunks', sa.Integer, nullable=True),
        sa.Column('received_chunks', sa.Integer, nullable=True, default=0),

        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    """Drop the attachments table."""
    op.drop_table('attachments')
    # Drop the enum type created by PostgreSQL
    op.execute("DROP TYPE IF EXISTS attachmentstatus")
