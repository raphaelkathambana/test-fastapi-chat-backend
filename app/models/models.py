from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from app.database import Base
import enum
from typing import List as TypingList


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    comments: Mapped[TypingList["Comment"]] = relationship("Comment", back_populates="user", foreign_keys="Comment.user_id")
    notifications: Mapped[TypingList["Notification"]] = relationship("Notification", back_populates="recipient", foreign_keys="Notification.recipient_id")


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
    status: Mapped[VehicleStatus] = mapped_column(SQLEnum(VehicleStatus), default=VehicleStatus.PENDING, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    comments: Mapped[TypingList["Comment"]] = relationship("Comment", back_populates="vehicle")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vehicle_id: Mapped[int] = mapped_column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    section: Mapped[SectionType] = mapped_column(SQLEnum(SectionType), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Encrypted content
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="comments")
    user: Mapped["User"] = relationship("User", back_populates="comments", foreign_keys=[user_id])
    notifications: Mapped[TypingList["Notification"]] = relationship("Notification", back_populates="comment", cascade="all, delete-orphan")


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

