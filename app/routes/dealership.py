from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.models import (
    User, Vehicle, Comment, Notification, SectionType,
    VehicleStatus, SectionMetadata, Attachment, AttachmentStatus,
)
from app.models.schemas import (
    VehicleCreate, VehicleUpdate, VehicleResponse,
    CommentCreate, CommentResponse, AttachmentResponse,
    NotificationResponse, SectionInfo, CommentCreateWithAttachments,
)
from app.utils.dependencies import get_current_user
from app.utils.encryption import encrypt_message, decrypt_message
from app.events.handlers.notifications import extract_mentions
import logging

logger = logging.getLogger(__name__)

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
def list_sections(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all evaluation sections with metadata from database.

    Hybrid approach: Section enum in comments table (fast queries),
    metadata in separate table (flexible, no migrations needed for updates).

    Args:
        include_inactive: If True, includes inactive/hidden sections
    """
    query = db.query(SectionMetadata).order_by(SectionMetadata.order_num)

    if not include_inactive:
        query = query.filter(SectionMetadata.is_active == True)

    sections = query.all()
    return sections


def _build_attachment_responses(attachments: list) -> List[AttachmentResponse]:
    """Build attachment response list from ORM objects."""
    return [
        AttachmentResponse(
            id=a.id,
            comment_id=a.comment_id,
            uploader_id=a.uploader_id,
            filename=a.filename,
            content_type=a.content_type,
            file_size=a.file_size,
            status=a.status,
            checksum_sha256=a.checksum_sha256,
            created_at=a.created_at,
        )
        for a in attachments
        if a.status == AttachmentStatus.READY
    ]


# Comment endpoints
@router.post("/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    comment: CommentCreateWithAttachments,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a comment on a vehicle section, optionally with attachments.

    Attachment IDs reference previously uploaded files. Once linked here,
    the bond is permanent — attachments cannot be moved to another comment.
    """
    # Check if vehicle exists
    vehicle = db.query(Vehicle).filter(Vehicle.id == comment.vehicle_id).first()
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle not found"
        )

    # Validate attachment_ids before creating the comment
    linked_attachments: list[Attachment] = []
    if comment.attachment_ids:
        for aid in comment.attachment_ids:
            attachment = db.query(Attachment).filter(
                Attachment.id == aid,
                Attachment.uploader_id == current_user.id,
                Attachment.status == AttachmentStatus.READY,
            ).first()

            if not attachment:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Attachment {aid} not found, not ready, or not yours",
                )

            # Enforce exclusive binding — can't re-link an already-linked attachment
            if attachment.comment_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Attachment {aid} is already linked to comment {attachment.comment_id}",
                )

            linked_attachments.append(attachment)

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
    db.flush()  # Get comment ID without committing

    # Link attachments to the comment (the permanent bond)
    for attachment in linked_attachments:
        attachment.comment_id = new_comment.id

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

    db.commit()
    db.refresh(new_comment)

    # Return decrypted comment with attachments
    return CommentResponse(
        id=new_comment.id,
        vehicle_id=new_comment.vehicle_id,
        section=new_comment.section,
        user_id=new_comment.user_id,
        username=current_user.username,
        content=comment.content,
        created_at=new_comment.created_at,
        mentioned_users=mentioned_users,
        attachments=_build_attachment_responses(linked_attachments),
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
                mentioned_users=mentioned_users,
                attachments=_build_attachment_responses(comment.attachments),
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
                mentioned_users=mentioned_users,
                attachments=_build_attachment_responses(notification.comment.attachments),
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
