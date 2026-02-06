from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    comments = relationship("Comment", back_populates="user", foreign_keys="Comment.user_id")
    notifications = relationship("Notification", back_populates="recipient", foreign_keys="Notification.recipient_id")


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

    id = Column(Integer, primary_key=True, index=True)
    vin = Column(String(17), unique=True, index=True, nullable=False)  # Vehicle Identification Number
    make = Column(String(50), nullable=False)  # e.g., Toyota, Honda
    model = Column(String(50), nullable=False)  # e.g., Camry, Accord
    year = Column(Integer, nullable=False)
    status = Column(SQLEnum(VehicleStatus), default=VehicleStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    comments = relationship("Comment", back_populates="vehicle")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False, index=True)
    section = Column(SQLEnum(SectionType), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)  # Encrypted content
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    vehicle = relationship("Vehicle", back_populates="comments")
    user = relationship("User", back_populates="comments", foreign_keys=[user_id])
    notifications = relationship("Notification", back_populates="comment", cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    recipient = relationship("User", back_populates="notifications", foreign_keys=[recipient_id])
    comment = relationship("Comment", back_populates="notifications")


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

    section_name = Column(String(50), primary_key=True)  # Must match SectionType enum values
    display_name = Column(String(100), nullable=False)  # Human-readable name
    description = Column(Text)  # Detailed description
    category = Column(String(50), nullable=False)  # Group sections (e.g., "Online Evaluation")
    order_num = Column(Integer, nullable=False)  # Display order (0 = general, 1+ = sections)
    icon = Column(String(50))  # Icon name/emoji for UI
    is_active = Column(Boolean, default=True, nullable=False)  # Hide sections without deleting
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

