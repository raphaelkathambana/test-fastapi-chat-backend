"""
Attachment upload/download routes.

Supports two upload paths:
1. Simple multipart upload — for small files (< 5MB)
2. Chunked upload — for large files (init → chunks → complete)

All files are validated (magic bytes), encrypted (envelope encryption),
and stored via the storage backend abstraction.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import hashlib
import logging

from app.database import get_db
from app.models.models import User, Attachment, AttachmentStatus, Comment
from app.models.schemas import (
    AttachmentResponse,
    ChunkedUploadInitRequest,
    ChunkedUploadInitResponse,
    ChunkedUploadCompleteResponse,
)
from app.utils.dependencies import get_current_user
from app.storage.backend import get_storage_backend
from app.storage.encryption import FileEncryptor
from app.storage.validation import FileValidator
from app.config import get_settings
from app.events import event_bus

router = APIRouter()
logger = logging.getLogger(__name__)

SIMPLE_UPLOAD_LIMIT = 5 * 1024 * 1024  # 5MB — above this, use chunked


def _generate_storage_key(attachment_id: str, filename: str) -> str:
    """Generate a storage key with directory sharding to avoid flat directories."""
    # Use first 4 chars of UUID for 2-level sharding: ab/cd/full-uuid/filename
    shard = f"{attachment_id[:2]}/{attachment_id[2:4]}"
    return f"attachments/{shard}/{attachment_id}/{filename}"


def _build_attachment_response(attachment: Attachment) -> AttachmentResponse:
    """Build a Pydantic response from an Attachment ORM object."""
    return AttachmentResponse(
        id=attachment.id,
        comment_id=attachment.comment_id,
        uploader_id=attachment.uploader_id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        file_size=attachment.file_size,
        status=attachment.status,
        checksum_sha256=attachment.checksum_sha256,
        created_at=attachment.created_at,
    )


# ─── Simple Upload (< 5MB) ───────────────────────────────────────────

@router.post("/upload", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a small file (< 5MB) in a single request.

    For larger files, use the chunked upload endpoints.
    """
    # Read the full file into memory (bounded by SIMPLE_UPLOAD_LIMIT)
    data = await file.read()

    if len(data) > SIMPLE_UPLOAD_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large for simple upload ({len(data)} bytes). "
                   f"Use chunked upload for files > {SIMPLE_UPLOAD_LIMIT // (1024*1024)}MB.",
        )

    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unnamed_file"

    # Validate
    is_valid, error, safe_filename = FileValidator.validate_upload(data, content_type, filename)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error)

    # Generate IDs and keys
    attachment_id = str(uuid.uuid4())
    file_key = FileEncryptor.generate_file_key()
    wrapped_key = FileEncryptor.wrap_key(file_key)
    checksum = hashlib.sha256(data).hexdigest()
    storage_key = _generate_storage_key(attachment_id, safe_filename)

    # Encrypt file data
    encrypted_data = FileEncryptor.encrypt_file(data, file_key)

    # Store encrypted file
    storage = get_storage_backend()
    await storage.store(storage_key, encrypted_data)

    # Create database record
    attachment = Attachment(
        id=attachment_id,
        uploader_id=current_user.id,
        filename=safe_filename,
        content_type=content_type,
        file_size=len(data),
        storage_key=storage_key,
        checksum_sha256=checksum,
        encrypted_file_key=wrapped_key,
        status=AttachmentStatus.READY,  # Simple uploads skip the pipeline
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    logger.info(f"Simple upload complete: {attachment_id} ({safe_filename}, {len(data)} bytes)")

    return _build_attachment_response(attachment)


# ─── Chunked Upload ──────────────────────────────────────────────────

@router.post("/upload/init", response_model=ChunkedUploadInitResponse, status_code=status.HTTP_201_CREATED)
async def init_chunked_upload(
    request: ChunkedUploadInitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initialize a chunked upload session.

    Returns an upload_id and upload_session token for subsequent chunk uploads.
    """
    # Validate content type
    if not FileValidator.validate_content_type(request.content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Content type not allowed: {request.content_type}",
        )

    # Validate file size for this content type
    size_ok, size_error = FileValidator.validate_file_size(request.total_size, request.content_type)
    if not size_ok:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=size_error)

    # Sanitize filename
    safe_filename = FileValidator.sanitize_filename(request.filename)

    # Generate IDs
    attachment_id = str(uuid.uuid4())
    upload_session = str(uuid.uuid4())
    file_key = FileEncryptor.generate_file_key()
    wrapped_key = FileEncryptor.wrap_key(file_key)
    storage_key = _generate_storage_key(attachment_id, safe_filename)

    # Create attachment record in UPLOADING state
    attachment = Attachment(
        id=attachment_id,
        uploader_id=current_user.id,
        upload_session=upload_session,
        filename=safe_filename,
        content_type=request.content_type,
        file_size=request.total_size,
        storage_key=storage_key,
        checksum_sha256="",  # Will be computed on completion
        encrypted_file_key=wrapped_key,
        status=AttachmentStatus.UPLOADING,
        total_chunks=request.total_chunks,
        received_chunks=0,
    )
    db.add(attachment)
    db.commit()

    logger.info(
        f"Chunked upload initialized: {attachment_id} "
        f"({safe_filename}, {request.total_chunks} chunks, {request.total_size} bytes)"
    )

    return ChunkedUploadInitResponse(
        upload_id=attachment_id,
        upload_session=upload_session,
        total_chunks=request.total_chunks,
    )


@router.patch("/upload/{upload_id}/chunk/{chunk_index}")
async def upload_chunk(
    upload_id: str,
    chunk_index: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Upload a single chunk of a chunked upload.

    Chunks are encrypted individually and appended to the storage file.
    """
    # Look up the attachment
    attachment = db.query(Attachment).filter(
        Attachment.id == upload_id,
        Attachment.uploader_id == current_user.id,
        Attachment.status == AttachmentStatus.UPLOADING,
    ).first()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or not in uploading state",
        )

    # Validate chunk index
    if attachment.total_chunks is not None and chunk_index >= attachment.total_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunk index {chunk_index} exceeds total chunks {attachment.total_chunks}",
        )

    # Read chunk data
    chunk_data = await file.read()

    if not chunk_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty chunk",
        )

    # Encrypt the chunk
    file_key = FileEncryptor.unwrap_key(attachment.encrypted_file_key)
    encrypted_chunk = FileEncryptor.encrypt_chunk(chunk_data, file_key, chunk_index)

    # Store the encrypted chunk in a separate chunk file
    chunk_key = f"{attachment.storage_key}.chunk_{chunk_index:06d}"
    storage = get_storage_backend()
    await storage.store(chunk_key, encrypted_chunk)

    # Update received count
    if attachment.received_chunks is not None:
        attachment.received_chunks = attachment.received_chunks + 1
    else:
        attachment.received_chunks = 1
    db.commit()

    logger.debug(f"Chunk {chunk_index} uploaded for {upload_id} ({len(chunk_data)} bytes)")

    return {
        "status": "ok",
        "chunk_index": chunk_index,
        "received_chunks": attachment.received_chunks,
        "total_chunks": attachment.total_chunks,
    }


@router.post("/upload/{upload_id}/complete", response_model=ChunkedUploadCompleteResponse)
async def complete_chunked_upload(
    upload_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Finalize a chunked upload.

    Reassembles chunks, validates magic bytes, computes checksum,
    and transitions status to PROCESSING → READY.
    """
    attachment = db.query(Attachment).filter(
        Attachment.id == upload_id,
        Attachment.uploader_id == current_user.id,
        Attachment.status == AttachmentStatus.UPLOADING,
    ).first()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found or not in uploading state",
        )

    # Verify all chunks received
    if attachment.received_chunks != attachment.total_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing chunks: received {attachment.received_chunks}/{attachment.total_chunks}",
        )

    # Transition to PROCESSING
    attachment.status = AttachmentStatus.PROCESSING
    db.commit()

    # Schedule background processing
    background_tasks.add_task(
        _process_chunked_upload,
        attachment_id=upload_id,
    )

    return ChunkedUploadCompleteResponse(
        attachment=_build_attachment_response(attachment),
        message="Upload is being processed. Status will change to 'ready' when complete.",
    )


async def _process_chunked_upload(attachment_id: str) -> None:
    """
    Background task: reassemble chunks, validate, compute checksum.

    Runs after the HTTP response is sent to avoid blocking the client.
    """
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
        if not attachment:
            logger.error(f"Attachment {attachment_id} not found for processing")
            return

        storage = get_storage_backend()
        file_key = FileEncryptor.unwrap_key(attachment.encrypted_file_key)

        # Reassemble: decrypt each chunk, concatenate, validate, re-encrypt as single file
        reassembled = bytearray()
        total_chunks = attachment.total_chunks or 0

        for i in range(total_chunks):
            chunk_key = f"{attachment.storage_key}.chunk_{i:06d}"
            encrypted_chunk = await storage.retrieve(chunk_key)
            chunk_index, chunk_data = FileEncryptor.decrypt_chunk(encrypted_chunk, file_key)

            if chunk_index != i:
                logger.error(f"Chunk ordering mismatch: expected {i}, got {chunk_index}")
                attachment.status = AttachmentStatus.QUARANTINED
                db.commit()
                return

            reassembled.extend(chunk_data)

        plain_data = bytes(reassembled)

        # Validate magic bytes against claimed content type
        if not FileValidator.validate_magic_bytes(plain_data, attachment.content_type):
            logger.warning(f"Magic byte validation failed for {attachment_id}")
            attachment.status = AttachmentStatus.QUARANTINED
            db.commit()
            # Clean up chunks
            for i in range(total_chunks):
                chunk_key = f"{attachment.storage_key}.chunk_{i:06d}"
                await storage.delete(chunk_key)
            return

        # Validate actual size
        size_ok, size_error = FileValidator.validate_file_size(len(plain_data), attachment.content_type)
        if not size_ok:
            logger.warning(f"Size validation failed for {attachment_id}: {size_error}")
            attachment.status = AttachmentStatus.QUARANTINED
            db.commit()
            for i in range(total_chunks):
                chunk_key = f"{attachment.storage_key}.chunk_{i:06d}"
                await storage.delete(chunk_key)
            return

        # Compute checksum
        checksum = hashlib.sha256(plain_data).hexdigest()

        # Encrypt the full file and store
        encrypted_full = FileEncryptor.encrypt_file(plain_data, file_key)
        await storage.store(attachment.storage_key, encrypted_full)

        # Clean up individual chunk files
        for i in range(total_chunks):
            chunk_key = f"{attachment.storage_key}.chunk_{i:06d}"
            await storage.delete(chunk_key)

        # Update attachment record
        attachment.checksum_sha256 = checksum
        attachment.file_size = len(plain_data)
        attachment.status = AttachmentStatus.READY
        db.commit()

        logger.info(f"Chunked upload processed: {attachment_id} ({len(plain_data)} bytes, checksum={checksum[:16]}...)")

        # Emit event for WebSocket notification
        await event_bus.emit('attachment.ready', {
            'attachment_id': attachment_id,
            'uploader_id': attachment.uploader_id,
            'filename': attachment.filename,
            'content_type': attachment.content_type,
            'file_size': attachment.file_size,
        })

    except Exception as e:
        logger.error(f"Error processing chunked upload {attachment_id}: {e}", exc_info=True)
        try:
            attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
            if attachment:
                attachment.status = AttachmentStatus.QUARANTINED
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ─── Download ─────────────────────────────────────────────────────────

@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download an attachment with on-the-fly decryption.

    Auth-gated: requires valid JWT. Streams the decrypted file back to the client.
    """
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.status == AttachmentStatus.READY,
    ).first()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found or not ready",
        )

    # Retrieve and decrypt
    storage = get_storage_backend()
    try:
        encrypted_data = await storage.retrieve(attachment.storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment file not found in storage",
        )

    file_key = FileEncryptor.unwrap_key(attachment.encrypted_file_key)
    decrypted_data = FileEncryptor.decrypt_file(encrypted_data, file_key)

    # Verify integrity
    actual_checksum = hashlib.sha256(decrypted_data).hexdigest()
    if actual_checksum != attachment.checksum_sha256:
        logger.error(
            f"Checksum mismatch for {attachment_id}: "
            f"expected {attachment.checksum_sha256}, got {actual_checksum}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File integrity check failed",
        )

    # Stream response with correct content type and disposition
    return StreamingResponse(
        iter([decrypted_data]),
        media_type=attachment.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{attachment.filename}"',
            "Content-Length": str(attachment.file_size),
            "X-Content-Type-Options": "nosniff",
        },
    )


# ─── Metadata / Status ───────────────────────────────────────────────

@router.get("/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment_info(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get metadata about an attachment."""
    attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    return _build_attachment_response(attachment)


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    attachment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete an attachment. Only the uploader can delete.

    Once linked to a comment, attachments can only be deleted by deleting the comment.
    """
    attachment = db.query(Attachment).filter(
        Attachment.id == attachment_id,
        Attachment.uploader_id == current_user.id,
    ).first()

    if not attachment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found or you don't have permission to delete it",
        )

    # Can't delete attachments that are already linked to a comment
    if attachment.comment_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an attachment linked to a comment. Delete the comment instead.",
        )

    # Delete from storage
    storage = get_storage_backend()
    try:
        await storage.delete(attachment.storage_key)
        if attachment.thumbnail_storage_key:
            await storage.delete(attachment.thumbnail_storage_key)
    except Exception as e:
        logger.warning(f"Error deleting storage for {attachment_id}: {e}")

    # Delete from database
    db.delete(attachment)
    db.commit()

    logger.info(f"Attachment deleted: {attachment_id}")
