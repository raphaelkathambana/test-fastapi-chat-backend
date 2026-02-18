from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List
import re
from app.models.models import VehicleStatus, SectionType, AttachmentStatus


class UserCreate(BaseModel):
    username: str
    password: str

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format and length."""
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if len(v) > 50:
            raise ValueError('Username must be at most 50 characters long')
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscores, and hyphens')
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password complexity."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 128:
            raise ValueError('Password must be at most 128 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one digit')
        return v


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


# Vehicle schemas
class VehicleCreate(BaseModel):
    vin: str
    make: str
    model: str
    year: int

    @field_validator('vin')
    @classmethod
    def validate_vin(cls, v: str) -> str:
        """Validate VIN format."""
        v = v.upper().strip()
        if len(v) != 17:
            raise ValueError('VIN must be exactly 17 characters')
        if not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', v):
            raise ValueError('Invalid VIN format')
        return v

    @field_validator('year')
    @classmethod
    def validate_year(cls, v: int) -> int:
        """Validate vehicle year."""
        if v < 1900 or v > datetime.now().year + 1:
            raise ValueError(f'Year must be between 1900 and {datetime.now().year + 1}')
        return v


class VehicleUpdate(BaseModel):
    status: Optional[VehicleStatus] = None
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None


class VehicleResponse(BaseModel):
    id: int
    vin: str
    make: str
    model: str
    year: int
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Attachment schemas (before CommentResponse since it references AttachmentResponse)
class AttachmentResponse(BaseModel):
    id: str
    comment_id: Optional[int] = None
    uploader_id: int
    filename: str
    content_type: str
    file_size: int
    status: AttachmentStatus
    checksum_sha256: str
    created_at: datetime

    class Config:
        from_attributes = True


# Comment schemas
class CommentCreate(BaseModel):
    vehicle_id: int
    section: SectionType
    content: str


class CommentCreateWithAttachments(BaseModel):
    vehicle_id: int
    section: SectionType
    content: str
    attachment_ids: Optional[List[str]] = None


class CommentResponse(BaseModel):
    id: int
    vehicle_id: int
    section: SectionType
    user_id: int
    username: str
    content: str
    created_at: datetime
    mentioned_users: Optional[List[str]] = []
    attachments: Optional[List[AttachmentResponse]] = []

    class Config:
        from_attributes = True


# Notification schemas
class NotificationResponse(BaseModel):
    id: int
    recipient_id: int
    comment_id: int
    is_read: bool
    created_at: datetime
    comment: CommentResponse

    class Config:
        from_attributes = True


# Chunked upload schemas
class ChunkedUploadInitRequest(BaseModel):
    filename: str
    content_type: str
    total_size: int
    total_chunks: int

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Sanitize filename — strip path components, limit characters."""
        import os
        v = os.path.basename(v)
        v = re.sub(r'[^\w\s\-.]', '_', v)
        if len(v) > 255:
            name, ext = os.path.splitext(v)
            v = name[:255 - len(ext)] + ext
        if not v or v.startswith('.'):
            raise ValueError('Invalid filename')
        return v

    @field_validator('total_size')
    @classmethod
    def validate_total_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('File size must be positive')
        if v > 200 * 1024 * 1024:  # 200MB max
            raise ValueError('File size exceeds 200MB limit')
        return v

    @field_validator('total_chunks')
    @classmethod
    def validate_total_chunks(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('Total chunks must be positive')
        if v > 2000:  # 2000 chunks max (100KB each = 200MB)
            raise ValueError('Too many chunks')
        return v


class ChunkedUploadInitResponse(BaseModel):
    upload_id: str
    upload_session: str
    total_chunks: int


class ChunkedUploadCompleteResponse(BaseModel):
    attachment: AttachmentResponse
    message: str


# Section info schema
class SectionInfo(BaseModel):
    """Section information with metadata."""
    section_name: str  # Enum value (e.g., "tire", "general")
    display_name: str  # Human-readable (e.g., "Tire Evaluation")
    description: Optional[str] = None
    category: str
    order_num: int
    icon: Optional[str] = None
    is_active: bool = True

    class Config:
        from_attributes = True
