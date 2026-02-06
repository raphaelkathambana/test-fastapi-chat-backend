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
    """Evaluation sections"""
    # Online evaluation sections (1-3)
    TIRE = "tire"
    WARRANTY = "warranty"
    ACCIDENT_DAMAGES = "accident_damages"
    # Inspection sections (4-5)
    PAINT = "paint"
    PREVIOUS_OWNERS = "previous_owners"


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

