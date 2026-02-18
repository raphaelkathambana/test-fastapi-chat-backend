"""
File validation module for attachment uploads.

Validates files by:
1. Magic bytes (file signature) — not trusting file extensions
2. MIME type allowlist — only permitting specific, safe content types
3. File size limits — per content-type category
"""
import os
import re
import logging

logger = logging.getLogger(__name__)

# Magic byte signatures for supported file types
# Maps content_type → list of (offset, signature_bytes)
MAGIC_SIGNATURES: dict[str, list[tuple[int, bytes]]] = {
    # Images
    "image/jpeg": [(0, b"\xff\xd8\xff")],
    "image/png": [(0, b"\x89PNG\r\n\x1a\n")],
    "image/webp": [(0, b"RIFF"), (8, b"WEBP")],
    "image/gif": [(0, b"GIF87a"), (0, b"GIF89a")],

    # Video
    "video/mp4": [(4, b"ftyp")],   # offset 4 for mp4 ftyp box
    "video/webm": [(0, b"\x1a\x45\xdf\xa3")],  # EBML header
    "video/quicktime": [(4, b"ftyp")],

    # Audio
    "audio/mpeg": [(0, b"\xff\xfb"), (0, b"\xff\xf3"), (0, b"\xff\xf2"), (0, b"ID3")],
    "audio/wav": [(0, b"RIFF"), (8, b"WAVE")],
    "audio/ogg": [(0, b"OggS")],

    # Documents
    "application/pdf": [(0, b"%PDF")],
}

# Size limits per category (bytes)
SIZE_LIMITS: dict[str, int] = {
    "image": 20 * 1024 * 1024,      # 20MB for images
    "video": 200 * 1024 * 1024,     # 200MB for video
    "audio": 50 * 1024 * 1024,      # 50MB for audio
    "document": 30 * 1024 * 1024,   # 30MB for documents (PDFs)
}

# Map content types to categories
CONTENT_TYPE_CATEGORIES: dict[str, str] = {
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
    "video/mp4": "video",
    "video/webm": "video",
    "video/quicktime": "video",
    "audio/mpeg": "audio",
    "audio/wav": "audio",
    "audio/ogg": "audio",
    "application/pdf": "document",
}

# All allowed content types (the allowlist)
ALLOWED_CONTENT_TYPES = set(CONTENT_TYPE_CATEGORIES.keys())


class FileValidator:
    """Validates uploaded files for type, size, and integrity."""

    @staticmethod
    def validate_content_type(content_type: str) -> bool:
        """Check if the content type is in our allowlist."""
        return content_type in ALLOWED_CONTENT_TYPES

    @staticmethod
    def validate_magic_bytes(data: bytes, claimed_content_type: str) -> bool:
        """
        Validate file content matches claimed type by checking magic bytes.

        This prevents attacks where a user claims a file is image/jpeg
        but uploads an executable.
        """
        if claimed_content_type not in MAGIC_SIGNATURES:
            logger.warning(f"No magic signature defined for {claimed_content_type}")
            return False

        signatures = MAGIC_SIGNATURES[claimed_content_type]

        for offset, signature in signatures:
            if len(data) < offset + len(signature):
                continue
            if data[offset:offset + len(signature)] == signature:
                return True

        logger.warning(
            f"Magic byte mismatch: claimed {claimed_content_type}, "
            f"header bytes: {data[:16].hex()}"
        )
        return False

    @staticmethod
    def validate_file_size(size: int, content_type: str) -> tuple[bool, str]:
        """
        Check if file size is within the limit for its content type category.

        Returns (is_valid, error_message).
        """
        category = CONTENT_TYPE_CATEGORIES.get(content_type)
        if not category:
            return False, f"Unknown content type: {content_type}"

        limit = SIZE_LIMITS.get(category, 0)
        if size > limit:
            limit_mb = limit / (1024 * 1024)
            size_mb = size / (1024 * 1024)
            return False, f"File size {size_mb:.1f}MB exceeds {category} limit of {limit_mb:.0f}MB"

        return True, ""

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize a filename for safe storage.

        - Strips path components (directory traversal prevention)
        - Removes non-alphanumeric characters (except . - _)
        - Limits length to 255 characters
        - Rejects hidden files (starting with .)
        """
        # Strip path components
        filename = os.path.basename(filename)

        # Replace dangerous characters
        filename = re.sub(r'[^\w\s\-.]', '_', filename)

        # Collapse multiple underscores/spaces
        filename = re.sub(r'[\s_]+', '_', filename)

        # Remove leading dots (hidden files)
        filename = filename.lstrip('.')

        # Truncate while preserving extension
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255 - len(ext)] + ext

        if not filename:
            filename = "unnamed_file"

        return filename

    @classmethod
    def validate_upload(
        cls,
        data: bytes,
        claimed_content_type: str,
        filename: str,
    ) -> tuple[bool, str, str]:
        """
        Full validation pipeline for a file upload.

        Returns (is_valid, error_message, sanitized_filename).
        """
        # 1. Check content type allowlist
        if not cls.validate_content_type(claimed_content_type):
            return False, f"Content type not allowed: {claimed_content_type}", ""

        # 2. Check file size
        size_ok, size_error = cls.validate_file_size(len(data), claimed_content_type)
        if not size_ok:
            return False, size_error, ""

        # 3. Validate magic bytes
        if not cls.validate_magic_bytes(data, claimed_content_type):
            return False, "File content does not match claimed content type", ""

        # 4. Sanitize filename
        safe_filename = cls.sanitize_filename(filename)

        return True, "", safe_filename
