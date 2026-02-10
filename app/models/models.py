from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum, Boolean, BigInteger
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from app.database import Base
import enum
from typing import List as TypingList, Optional


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    comments: Mapped[TypingList["Comment"]] = relationship("Comment", back_populates="user", foreign_keys="Comment.user_id")
    notifications: Mapped[TypingList["Notification"]] = relationship("Notification", back_populates="recipient", foreign_keys="Notification.recipient_id")
    attachments: Mapped[TypingList["Attachment"]] = relationship("Attachment", back_populates="uploader")


class VehicleStatus(str, enum.Enum):
    """Vehicle evaluation status"""
    PENDING = "pending"
    ONLINE_EVALUATION = "online_evaluation"
    INSPECTION = "inspection"
    COMPLETED = "completed"
    REJECTED = "rejected"


class SectionType(str, enum.Enum):
    """
    Evaluation sections for vehicle assessment.

    Sections are organized into categories:
    - GENERAL: Overall vehicle comments (not section-specific)
    - Online Evaluation: Remote assessment (sections 1-3)
    - Inspection: Physical inspection (sections 4-5)
    - Mechanical: Detailed mechanical checks (sections 6-10)
    - Additional: Extra evaluation areas (sections 11+)
    """
    # General comments (car-level, not tied to specific section)
    GENERAL = "general"

    # Online evaluation sections (1-3)
    TIRE = "tire"
    WARRANTY = "warranty"
    ACCIDENT_DAMAGES = "accident_damages"

    # Inspection sections (4-5)
    PAINT = "paint"
    PREVIOUS_OWNERS = "previous_owners"

    # Mechanical sections (6-10)
    ENGINE = "engine"
    TRANSMISSION = "transmission"
    BRAKES = "brakes"
    SUSPENSION = "suspension"
    EXHAUST = "exhaust"

    # Additional sections (11-15)
    INTERIOR = "interior"
    ELECTRONICS = "electronics"
    FLUIDS = "fluids"
    LIGHTS = "lights"
    AC_HEATING = "ac_heating"

    # Can add more as needed (up to 20-30 easily)
    # STEERING = "steering"
    # WHEELS = "wheels"
    # etc.


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vin: Mapped[str] = mapped_column(String(17), unique=True, index=True, nullable=False)  # Vehicle Identification Number
    make: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., Toyota, Honda
    model: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., Camry, Accord
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(SQLEnum(VehicleStatus, values_callable=lambda x: [e.value for e in x]), default=VehicleStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    comments: Mapped[TypingList["Comment"]] = relationship("Comment", back_populates="vehicle")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    section: Mapped[SectionType] = mapped_column(SQLEnum(SectionType, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted content
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="comments")
    user: Mapped["User"] = relationship("User", back_populates="comments", foreign_keys=[user_id])
    notifications: Mapped[TypingList["Notification"]] = relationship("Notification", back_populates="comment", cascade="all, delete-orphan")
    attachments: Mapped[TypingList["Attachment"]] = relationship("Attachment", back_populates="comment", cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    recipient_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    comment_id: Mapped[int] = mapped_column(Integer, ForeignKey("comments.id"), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    recipient: Mapped["User"] = relationship("User", back_populates="notifications", foreign_keys=[recipient_id])
    comment: Mapped["Comment"] = relationship("Comment", back_populates="notifications")


class SectionMetadata(Base):
    """
    Metadata for evaluation sections (hybrid approach).

    This table stores rich metadata about sections while keeping the
    section column as an enum in the comments table for performance.

    Benefits:
    - Fast queries (comments.section is enum, no JOIN needed)
    - Rich metadata (descriptions, icons, ordering)
    - Easy updates (change display name without migration)
    - Flexible (show/hide sections via is_active)
    """
    __tablename__ = "section_metadata"

    section_name: Mapped[str] = mapped_column(String(50), primary_key=True)  # Must match SectionType enum values
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # Human-readable name
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Detailed description
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # Group sections (e.g., "Online Evaluation")
    order_num: Mapped[int] = mapped_column(Integer, nullable=False)  # Display order (0 = general, 1+ = sections)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)  # Icon name/emoji for UI
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Hide sections without deleting
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AttachmentStatus(str, enum.Enum):
    """Lifecycle status of an uploaded attachment."""
    UPLOADING = "uploading"        # Chunked upload in progress
    PROCESSING = "processing"      # Validating, encrypting, scanning
    READY = "ready"                # Available for download
    QUARANTINED = "quarantined"    # Failed validation/scan
    ORPHANED = "orphaned"          # Never linked to a comment, pending cleanup


class Attachment(Base):
    """
    File attachment linked exclusively to a single comment.

    Attachments are independent entities with an exclusive, non-transferable
    binding to exactly one comment. They may exist temporarily without a
    comment during the upload phase, but once linked the bond is permanent.

    Encryption: Uses envelope encryption — each file is encrypted with its
    own AES-256 key, which is then wrapped with the application Fernet key.
    """
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID4
    comment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    uploader_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    upload_session: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)  # Sanitized original name
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)  # Validated MIME type
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Bytes
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)  # Path in storage
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)  # Hex digest

    # Envelope encryption: per-file AES key wrapped with Fernet master key
    encrypted_file_key: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional thumbnail for images/video
    thumbnail_storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Lifecycle
    status: Mapped[AttachmentStatus] = mapped_column(
        SQLEnum(AttachmentStatus, values_callable=lambda x: [e.value for e in x]),
        default=AttachmentStatus.UPLOADING, nullable=False, index=True
    )

    # Chunked upload tracking
    total_chunks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    received_chunks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    comment: Mapped[Optional["Comment"]] = relationship("Comment", back_populates="attachments")
    uploader: Mapped["User"] = relationship("User", back_populates="attachments")
