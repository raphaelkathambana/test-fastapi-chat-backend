from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, Vehicle, Comment, Notification, SectionType, VehicleStatus
from app.models.schemas import (
    VehicleCreate, VehicleUpdate, VehicleResponse,
    CommentCreate, CommentResponse,
    NotificationResponse, SectionInfo
)
from app.routes.chat import get_current_user
from app.utils.encryption import encrypt_message, decrypt_message
import re

router = APIRouter()


# Vehicle endpoints
@router.post("/vehicles", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    vehicle: VehicleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new vehicle for evaluation."""
    # Check if VIN already exists
    existing = db.query(Vehicle).filter(Vehicle.vin == vehicle.vin.upper()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vehicle with this VIN already exists"
        )

    new_vehicle = Vehicle(
        vin=vehicle.vin.upper(),
        make=vehicle.make,
        model=vehicle.model,
        year=vehicle.year,
        status=VehicleStatus.PENDING
    )
    db.add(new_vehicle)
    db.commit()
    db.refresh(new_vehicle)
    return new_vehicle


@router.get("/vehicles", response_model=List[VehicleResponse])
def list_vehicles(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all vehicles."""
    vehicles = db.query(Vehicle).order_by(Vehicle.created_at.desc()).offset(skip).limit(limit).all()
    return vehicles


@router.get("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific vehicle by ID."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )
    return vehicle


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    vehicle_update: VehicleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update vehicle information."""
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )

    if vehicle_update.status is not None:
        vehicle.status = vehicle_update.status
    if vehicle_update.make is not None:
        vehicle.make = vehicle_update.make
    if vehicle_update.model is not None:
        vehicle.model = vehicle_update.model
    if vehicle_update.year is not None:
        vehicle.year = vehicle_update.year

    db.commit()
    db.refresh(vehicle)
    return vehicle


# Section endpoints
@router.get("/sections", response_model=List[SectionInfo])
def list_sections(current_user: User = Depends(get_current_user)):
    """List all evaluation sections with metadata."""
    sections = [
        SectionInfo(
            name=SectionType.TIRE,
            display_name="Tire Evaluation",
            category="Online Evaluation",
            order=1
        ),
        SectionInfo(
            name=SectionType.WARRANTY,
            display_name="Warranty",
            category="Online Evaluation",
            order=2
        ),
        SectionInfo(
            name=SectionType.ACCIDENT_DAMAGES,
            display_name="Accident & Damages",
            category="Online Evaluation",
            order=3
        ),
        SectionInfo(
            name=SectionType.PAINT,
            display_name="Paint Inspection",
            category="Inspection",
            order=4
        ),
        SectionInfo(
            name=SectionType.PREVIOUS_OWNERS,
            display_name="Previous Owners",
            category="Inspection",
            order=5
        )
    ]
    return sections


# Comment endpoints
@router.post("/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    comment: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a comment on a vehicle section."""
    # Check if vehicle exists
    vehicle = db.query(Vehicle).filter(Vehicle.id == comment.vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )

    # Encrypt the comment content
    encrypted_content = encrypt_message(comment.content)

    # Create comment
    new_comment = Comment(
        vehicle_id=comment.vehicle_id,
        section=comment.section,
        user_id=current_user.id,
        content=encrypted_content
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # Parse @mentions and create notifications
    mentioned_users = extract_mentions(comment.content)
    for mentioned_username in mentioned_users:
        mentioned_user = db.query(User).filter(User.username == mentioned_username).first()
        if mentioned_user and mentioned_user.id != current_user.id:
            notification = Notification(
                recipient_id=mentioned_user.id,
                comment_id=new_comment.id,
                is_read=False
            )
            db.add(notification)

    if mentioned_users:
        db.commit()

    # Return decrypted comment
    return CommentResponse(
        id=new_comment.id,
        vehicle_id=new_comment.vehicle_id,
        section=new_comment.section,
        user_id=new_comment.user_id,
        username=current_user.username,
        content=comment.content,
        created_at=new_comment.created_at,
        mentioned_users=mentioned_users
    )


@router.get("/comments", response_model=List[CommentResponse])
def list_comments(
    vehicle_id: int,
    section: SectionType,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all comments for a specific vehicle section."""
    comments = db.query(Comment).filter(
        Comment.vehicle_id == vehicle_id,
        Comment.section == section
    ).order_by(Comment.created_at.asc()).all()

    result = []
    for comment in comments:
        try:
            decrypted_content = decrypt_message(comment.content)
            mentioned_users = extract_mentions(decrypted_content)
            result.append(CommentResponse(
                id=comment.id,
                vehicle_id=comment.vehicle_id,
                section=comment.section,
                user_id=comment.user_id,
                username=comment.user.username,
                content=decrypted_content,
                created_at=comment.created_at,
                mentioned_users=mentioned_users
            ))
        except Exception:
            # Skip comments that can't be decrypted
            continue

    return result


# Notification endpoints
@router.get("/notifications", response_model=List[NotificationResponse])
def list_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notifications for the current user."""
    query = db.query(Notification).filter(Notification.recipient_id == current_user.id)

    if unread_only:
        query = query.filter(Notification.is_read == False)

    notifications = query.order_by(Notification.created_at.desc()).limit(50).all()

    result = []
    for notification in notifications:
        try:
            decrypted_content = decrypt_message(notification.comment.content)
            mentioned_users = extract_mentions(decrypted_content)
            comment_response = CommentResponse(
                id=notification.comment.id,
                vehicle_id=notification.comment.vehicle_id,
                section=notification.comment.section,
                user_id=notification.comment.user_id,
                username=notification.comment.user.username,
                content=decrypted_content,
                created_at=notification.comment.created_at,
                mentioned_users=mentioned_users
            )
            result.append(NotificationResponse(
                id=notification.id,
                recipient_id=notification.recipient_id,
                comment_id=notification.comment_id,
                is_read=notification.is_read,
                created_at=notification.created_at,
                comment=comment_response
            ))
        except Exception:
            continue

    return result


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.recipient_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )

    notification.is_read = True
    db.commit()
    return {"status": "success", "message": "Notification marked as read"}


@router.patch("/notifications/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all notifications as read."""
    db.query(Notification).filter(
        Notification.recipient_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"status": "success", "message": "All notifications marked as read"}


# Helper function
def extract_mentions(content: str) -> List[str]:
    """Extract @username mentions from content."""
    # Match @username (alphanumeric, underscore, hyphen)
    pattern = r'@([a-zA-Z0-9_-]+)'
    mentions = re.findall(pattern, content)
    return list(set(mentions))  # Remove duplicates
