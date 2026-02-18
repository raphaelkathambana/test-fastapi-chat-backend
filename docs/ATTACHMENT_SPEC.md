# Attachment System Design Specification

## Dealership Vehicle Evaluation Platform

| | |
|---|---|
| **Version** | 1.0 |
| **Date** | 2026-02-18 |
| **API Version** | 3.0.0 |
| **Status** | Living Document |

---

## Table of Contents

### Part I — System Description

- [1. System Overview](#1-system-overview)
- [2. Database Schema](#2-database-schema)
- [3. Pydantic Schemas](#3-pydantic-schemas)
- [4. API Routes](#4-api-routes)
- [5. Encryption Architecture](#5-encryption-architecture)
- [6. File Validation](#6-file-validation)
- [7. Storage Backend](#7-storage-backend)
- [8. Upload Lifecycle](#8-upload-lifecycle)
- [9. WebSocket Integration](#9-websocket-integration)
- [10. Configuration Reference](#10-configuration-reference)

### Part II — Frontend Migration Guide

- [11. Migration Overview](#11-migration-overview)
- [12. Backend Changes Required](#12-backend-changes-required)
- [13. Frontend Implementation Guide](#13-frontend-implementation-guide)
- [14. CDN and Scaling Considerations](#14-cdn-and-scaling-considerations)
- [15. Security Checklist](#15-security-checklist)
- [16. Future Enhancements](#16-future-enhancements)

### Appendices

- [A. curl Examples](#appendix-a-curl-examples)
- [B. Error Code Reference](#appendix-b-error-code-reference)
- [C. Glossary](#appendix-c-glossary)

---

# Part I — System Description

## 1. System Overview

The Dealership Vehicle Evaluation Platform enables technicians and evaluators to collaboratively inspect vehicles in real time. Each vehicle is divided into evaluation sections (tires, engine, body, etc.), and users communicate through a WebSocket-based comment system scoped to a specific vehicle + section room.

The attachment system adds file upload capability to comments. Users can attach images, video, audio, and PDF documents to any comment. Attachments are independent entities with an exclusive, permanent binding to exactly one comment — modeled after the WhatsApp approach where a message owns its media and no other message can reference it.

Two upload paths are supported: **simple multipart** for files under 5 MB (processed synchronously, immediately ready) and **chunked upload** for files up to 200 MB (uploaded in 100 KB chunks, reassembled and validated asynchronously). All files are encrypted at rest using envelope encryption (per-file AES-256-GCM key, wrapped with a Fernet master key).

```
┌──────────────────┐       REST / WebSocket       ┌──────────────────┐       ┌────────────┐
│                  │  ───────────────────────────> │                  │ ────> │ PostgreSQL │
│  Client          │       JWT Bearer Auth        │  FastAPI Backend  │       └────────────┘
│  (TUI / Browser) │  <─────────────────────────  │  (uvicorn)       │
│                  │                              │                  │
└──────────────────┘                              └────────┬─────────┘
                                                           │
                                                    ┌──────┴──────┐
                                                    │             │
                                              StorageBackend   EventBus
                                              (local / S3)     (pub/sub)
                                                    │
                                              ┌─────┴──────┐
                                              │  uploads/   │
                                              │ (encrypted) │
                                              └────────────┘
```

**Source files**: `app/routes/attachments.py`, `app/storage/`, `app/models/models.py`

---

## 2. Database Schema

### 2.1 Attachments Table

Alembic migration: `alembic/versions/006_add_attachments_table.py`
Model: `app/models/models.py` — class `Attachment`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `String(36)` | PK | UUID4 identifier |
| `comment_id` | `Integer` | FK → `comments.id` ON DELETE CASCADE, nullable, indexed | Exclusive binding to one comment. NULL during upload phase. |
| `uploader_id` | `Integer` | FK → `users.id`, NOT NULL, indexed | User who uploaded the file |
| `upload_session` | `String(36)` | nullable, indexed | Session token for chunked uploads |
| `filename` | `String(255)` | NOT NULL | Sanitized original filename |
| `content_type` | `String(100)` | NOT NULL | Validated MIME type |
| `file_size` | `BigInteger` | NOT NULL | File size in bytes (plaintext) |
| `storage_key` | `String(500)` | NOT NULL, UNIQUE | Sharded path in storage backend |
| `checksum_sha256` | `String(64)` | NOT NULL | SHA-256 hex digest of plaintext |
| `encrypted_file_key` | `Text` | NOT NULL | Fernet-wrapped AES-256 DEK |
| `thumbnail_storage_key` | `String(500)` | nullable | Reserved for future thumbnail support |
| `status` | `Enum(AttachmentStatus)` | NOT NULL, indexed, default=`uploading` | Current lifecycle state |
| `total_chunks` | `Integer` | nullable | Expected chunk count (chunked uploads only) |
| `received_chunks` | `Integer` | nullable, default=0 | Chunks received so far |
| `created_at` | `DateTime` | server_default=`now()` | Creation timestamp |
| `updated_at` | `DateTime` | server_default=`now()`, onupdate | Last modification |

### 2.2 Relationships

```
User (1) ──────── (*) Attachment    via uploader_id
Comment (1) ──── (0..*) Attachment  via comment_id (nullable, CASCADE delete)
```

- A user can have many attachments
- A comment can have many attachments
- An attachment belongs to exactly one user and at most one comment
- Deleting a comment cascades to its attachments

### 2.3 AttachmentStatus Enum

Defined in `app/models/models.py` — class `AttachmentStatus`

| Value | Description |
|-------|-------------|
| `uploading` | Chunked upload in progress — chunks being received |
| `processing` | Background task running: reassembly, validation, encryption |
| `ready` | Available for download and linking to a comment |
| `quarantined` | Failed validation (magic bytes, size, chunk ordering) |
| `orphaned` | Enum value exists but not actively used — cleanup deletes directly |

**State Machine:**

```
                               ┌─────────┐
     Simple upload ──────────> │  READY  │ ──── link to comment
                               └─────────┘
                                    ^
                                    │ background task succeeds
                                    │
┌───────────┐    /complete    ┌─────────────┐
│ UPLOADING │ ──────────────> │ PROCESSING  │
└───────────┘                 └──────┬──────┘
      │                              │
      │ orphan TTL expires           │ validation fails
      v                              v
   [deleted]                  ┌──────────────┐
                              │ QUARANTINED  │
                              └──────────────┘
```

---

## 3. Pydantic Schemas

Defined in `app/models/schemas.py`

### 3.1 AttachmentResponse

Returned by all attachment endpoints.

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "comment_id": null,
  "uploader_id": 7,
  "filename": "tire_damage.jpg",
  "content_type": "image/jpeg",
  "file_size": 245760,
  "status": "ready",
  "checksum_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "created_at": "2026-02-18T10:30:00"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | UUID4 attachment identifier |
| `comment_id` | `int \| null` | Linked comment ID, or null if pending |
| `uploader_id` | `int` | User ID of the uploader |
| `filename` | `str` | Sanitized filename |
| `content_type` | `str` | Validated MIME type |
| `file_size` | `int` | Size in bytes |
| `status` | `AttachmentStatus` | Current lifecycle state |
| `checksum_sha256` | `str` | SHA-256 hex digest |
| `created_at` | `datetime` | Upload timestamp |

### 3.2 ChunkedUploadInitRequest

Sent to `POST /api/attachments/upload/init` to begin a chunked upload.

```json
{
  "filename": "inspection_video.mp4",
  "content_type": "video/mp4",
  "total_size": 157286400,
  "total_chunks": 1536
}
```

| Field | Type | Validators |
|-------|------|------------|
| `filename` | `str` | Basename stripped, dangerous chars → `_`, max 255, no leading dot |
| `content_type` | `str` | Must be in MIME allowlist |
| `total_size` | `int` | Must be > 0 and <= 200 MB (209715200 bytes) |
| `total_chunks` | `int` | Must be > 0 and <= 2000 |

### 3.3 ChunkedUploadInitResponse

Returned after successful init.

```json
{
  "upload_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "upload_session": "f9e8d7c6-b5a4-3210-fedc-ba0987654321",
  "total_chunks": 1536
}
```

### 3.4 ChunkedUploadCompleteResponse

Returned after calling `/complete`.

```json
{
  "attachment": { "...AttachmentResponse with status: processing..." },
  "message": "Upload is being processed. Status will change to 'ready' when complete."
}
```

### 3.5 CommentCreateWithAttachments

Used for creating comments with attachments via the REST API.

```json
{
  "vehicle_id": 1,
  "section": "tire",
  "content": "Check this crack on the sidewall",
  "attachment_ids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `vehicle_id` | `int` | Target vehicle |
| `section` | `SectionType` | Evaluation section |
| `content` | `str` | Comment text |
| `attachment_ids` | `list[str] \| null` | Optional list of attachment UUIDs to link |

### 3.6 CommentResponse (with Attachments)

Comments now include their linked attachments.

```json
{
  "id": 42,
  "vehicle_id": 1,
  "section": "tire",
  "user_id": 7,
  "username": "alice",
  "content": "Check this crack on the sidewall",
  "created_at": "2026-02-18T10:30:00",
  "mentioned_users": ["bob"],
  "attachments": [
    {
      "id": "a1b2c3d4-...",
      "filename": "tire_damage.jpg",
      "content_type": "image/jpeg",
      "file_size": 245760,
      "status": "ready",
      "...": "..."
    }
  ]
}
```

---

## 4. API Routes

All attachment routes are registered under the prefix `/api/attachments`.
Authentication: Bearer JWT token required on all endpoints.

### 4.1 Route Summary

| Method | Path | Status Codes | Description |
|--------|------|:---:|-------------|
| `POST` | `/api/attachments/upload` | 201, 413, 422 | Simple multipart upload (< 5 MB) |
| `POST` | `/api/attachments/upload/init` | 201, 422 | Initialize chunked upload |
| `PATCH` | `/api/attachments/upload/{id}/chunk/{index}` | 200, 400, 404 | Upload a single chunk |
| `POST` | `/api/attachments/upload/{id}/complete` | 200, 400, 404 | Finalize chunked upload |
| `GET` | `/api/attachments/{id}/download` | 200, 404, 500 | Stream-download with decryption |
| `GET` | `/api/attachments/{id}` | 200, 404 | Get attachment metadata |
| `DELETE` | `/api/attachments/{id}` | 204, 400, 404 | Delete unlinked attachment |

### 4.2 POST /api/attachments/upload

**Simple multipart upload for files under 5 MB.**

- **Request**: `multipart/form-data` with field `file`
- **Response**: `201 Created` — `AttachmentResponse` with `status: "ready"`

Processing (synchronous, within the request):
1. Read entire file into memory
2. Reject if > 5 MB (413)
3. Validate: content type allowlist, magic bytes, file size by category, filename sanitization
4. Generate UUID, AES-256 DEK, wrap DEK with Fernet
5. Compute SHA-256 of plaintext
6. Encrypt file with AES-256-GCM
7. Store encrypted bytes via StorageBackend
8. Create `Attachment` record with `status=READY`

**Error responses:**

| Code | Detail |
|------|--------|
| 413 | File too large for simple upload. Use chunked upload for files > 5MB. |
| 422 | Content type not allowed / File content does not match claimed type / Size exceeds limit |

### 4.3 POST /api/attachments/upload/init

**Initialize a chunked upload session.**

- **Request**: JSON body — `ChunkedUploadInitRequest`
- **Response**: `201 Created` — `ChunkedUploadInitResponse`

Processing:
1. Validate content type against allowlist
2. Validate total_size against category limit
3. Sanitize filename
4. Generate UUID, upload_session UUID, AES-256 DEK, wrap DEK
5. Generate sharded storage key
6. Create `Attachment` record with `status=UPLOADING`, `received_chunks=0`

### 4.4 PATCH /api/attachments/upload/{id}/chunk/{index}

**Upload a single chunk.**

- **Path params**: `upload_id` (UUID), `chunk_index` (0-based integer)
- **Request**: `multipart/form-data` with field `file` containing chunk bytes
- **Response**: `200 OK`

```json
{
  "status": "ok",
  "chunk_index": 0,
  "received_chunks": 1,
  "total_chunks": 1536
}
```

Processing:
1. Look up attachment (must exist, owned by user, status=UPLOADING)
2. Validate chunk_index < total_chunks
3. Read chunk data, reject if empty
4. Unwrap DEK, encrypt chunk with AES-256-GCM (includes chunk index in envelope)
5. Store as `{storage_key}.chunk_{index:06d}`
6. Increment `received_chunks`

### 4.5 POST /api/attachments/upload/{id}/complete

**Finalize a chunked upload. Triggers asynchronous background processing.**

- **Response**: `200 OK` — `ChunkedUploadCompleteResponse` with `status: "processing"`

Processing (synchronous):
1. Verify `received_chunks == total_chunks`
2. Transition status to `PROCESSING`
3. Schedule background task `_process_chunked_upload()`
4. Return immediately

Background task `_process_chunked_upload()`:
1. Retrieve and decrypt each chunk in order
2. Verify chunk index ordering (quarantine on mismatch)
3. Concatenate into full plaintext
4. Validate magic bytes against claimed content type
5. Validate total file size against category limit
6. Compute SHA-256 checksum
7. Re-encrypt as single file with AES-256-GCM
8. Store encrypted full file, delete chunk files
9. Update record: `checksum_sha256`, `file_size`, `status=READY`
10. Emit `attachment.ready` event (WebSocket notification to uploader)

On any validation failure: `status=QUARANTINED`, chunk files deleted.

### 4.6 GET /api/attachments/{id}/download

**Stream-download with on-the-fly decryption and integrity verification.**

- **Response**: `200 OK` — binary stream with headers:
  - `Content-Type`: original MIME type
  - `Content-Disposition`: `attachment; filename="original_name.ext"`
  - `Content-Length`: file size in bytes
  - `X-Content-Type-Options`: `nosniff`

Processing:
1. Look up attachment (must have `status=READY`)
2. Retrieve encrypted bytes from storage
3. Unwrap DEK, decrypt with AES-256-GCM
4. Compute SHA-256 of decrypted data
5. Compare against stored checksum (500 on mismatch — potential tampering)
6. Stream decrypted bytes

### 4.7 GET /api/attachments/{id}

**Get attachment metadata.**

- **Response**: `200 OK` — `AttachmentResponse`

No decryption or file access. Returns the database record only.

### 4.8 DELETE /api/attachments/{id}

**Delete an unlinked attachment. Uploader only.**

- **Response**: `204 No Content`

Constraints:
- Only the uploader can delete
- Cannot delete if `comment_id` is set (400: "Delete the comment instead")
- Deletes from storage (file + thumbnail) and database

### 4.9 Comment Integration

Attachments are linked to comments through two paths:

**REST API** — `POST /api/dealership/comments`

Accepts `CommentCreateWithAttachments` with optional `attachment_ids`. For each ID, validates:
- Attachment exists
- `status == READY`
- `uploader_id == current_user.id`
- `comment_id IS NULL`

Sets `attachment.comment_id = comment.id` atomically within the transaction.

**WebSocket** — Send comment message with `attachment_ids`

```json
{"type": "comment", "content": "Check this out", "attachment_ids": ["uuid1", "uuid2"]}
```

Same validation rules. Links attachments within the database transaction, then broadcasts the comment (with attachment metadata) to the room.

**Binding rules:**
- Once `comment_id` is set, it is permanent — no re-linking or transferring
- Attachments not linked within the orphan TTL (default 60 minutes) are deleted

---

## 5. Encryption Architecture

### 5.1 Envelope Encryption Overview

The system uses **envelope encryption** to avoid running large files through Fernet (which is not designed for payloads > 1 MB). Each file gets its own random encryption key. That key is then protected by the application's master key.

```
┌─────────────────────────────────────┐
│  Environment Variable               │
│  ENCRYPTION_KEY (arbitrary string)  │
└──────────────┬──────────────────────┘
               │
               │  SHA-256 hash → base64url encode → Fernet key
               v
┌─────────────────────────────────────┐
│  Fernet Master Key (KEK)            │
│  AES-128-CBC + HMAC-SHA256          │
│  Used ONLY to wrap/unwrap DEKs      │
└──────────────┬──────────────────────┘
               │
               │  Fernet.encrypt(DEK) → stored in DB as text
               │  Fernet.decrypt(wrapped) → recovers DEK
               v
┌─────────────────────────────────────┐
│  Per-File Data Encryption Key (DEK) │
│  AES-256 (32 random bytes)          │
│  One per attachment                 │
└──────────────┬──────────────────────┘
               │
               │  AES-256-GCM encrypt / decrypt
               v
┌─────────────────────────────────────┐
│  File Data on Disk (ciphertext)     │
│  Unreadable without DEK             │
└─────────────────────────────────────┘
```

**Source files**: `app/utils/encryption.py` (master key derivation), `app/storage/encryption.py` (file encryption)

### 5.2 Master Key Derivation

```python
# app/utils/encryption.py
key = settings.encryption_key.encode()          # raw bytes of env var
hashed_key = hashlib.sha256(key).digest()       # 32 bytes
fernet_key = base64.urlsafe_b64encode(hashed_key)  # 44-char Fernet key
cipher = Fernet(fernet_key)
```

The same `ENCRYPTION_KEY` environment variable is used for both comment encryption (Fernet direct) and attachment DEK wrapping (Fernet wrap/unwrap).

### 5.3 Per-File Key Lifecycle

1. **Generate**: `os.urandom(32)` — 32 random bytes (AES-256 key)
2. **Wrap**: `Fernet(master_key).encrypt(dek_bytes)` → stored in `attachments.encrypted_file_key` as text
3. **Use**: Encrypt file data with AES-256-GCM using the DEK
4. **Unwrap on download**: `Fernet(master_key).decrypt(wrapped_text)` → recovers DEK
5. **Decrypt**: AES-256-GCM decryption with recovered DEK

### 5.4 Binary Formats

**Full file encryption** (`encrypt_file` / `decrypt_file`):

```
┌──────────────┬──────────────────────────────────────┐
│ 12 bytes     │ N bytes                              │
│ Nonce (IV)   │ AES-GCM ciphertext + 16-byte GCM tag│
└──────────────┴──────────────────────────────────────┘
```

**Chunk encryption** (`encrypt_chunk` / `decrypt_chunk`):

```
┌──────────────┬──────────────┬──────────────────────────────────────┐
│ 4 bytes      │ 12 bytes     │ N bytes                              │
│ chunk_index  │ Nonce (IV)   │ AES-GCM ciphertext + 16-byte GCM tag│
│ (uint32 LE)  │              │                                      │
└──────────────┴──────────────┴──────────────────────────────────────┘
```

- Nonce: 12 bytes, randomly generated per encrypt operation (`os.urandom(12)`)
- GCM tag: 16 bytes, appended to ciphertext by the AESGCM library
- Chunk index: 4 bytes, little-endian uint32, used to verify ordering during reassembly

### 5.5 Integrity Verification

- **Upload**: SHA-256 computed on the **plaintext** data before encryption
- **Download**: SHA-256 recomputed on the decrypted data and compared to the stored checksum
- **Mismatch**: HTTP 500 returned with `"File integrity check failed"`, logged as potential tampering

### 5.6 Key Rotation Considerations

The current system has no built-in key rotation mechanism.

**Impact of changing `ENCRYPTION_KEY`:**
- All wrapped DEKs in the database become unrecoverable
- All encrypted comments (Fernet direct) become unreadable
- All attachment files become permanently inaccessible

**Recommended approach for future implementation:**
1. Add a `key_version` column to the `attachments` table
2. Maintain a versioned key registry (e.g., `ENCRYPTION_KEY_V1`, `ENCRYPTION_KEY_V2`)
3. New uploads use the latest key version
4. Downloads check `key_version` to select the correct master key
5. Background migration job: re-wrap DEKs with the new master key (file data itself does not need re-encryption — only the DEK wrapper changes)

---

## 6. File Validation

Defined in `app/storage/validation.py` — class `FileValidator`

### 6.1 Allowed MIME Types

| Content Type | Category | Max Size | Magic Bytes | Offset |
|---|---|---:|---|---:|
| `image/jpeg` | image | 20 MB | `FF D8 FF` | 0 |
| `image/png` | image | 20 MB | `89 50 4E 47 0D 0A 1A 0A` | 0 |
| `image/gif` | image | 20 MB | `GIF87a` or `GIF89a` | 0 |
| `image/webp` | image | 20 MB | `RIFF` at 0 + `WEBP` at 8 | 0, 8 |
| `video/mp4` | video | 200 MB | `ftyp` | 4 |
| `video/webm` | video | 200 MB | `1A 45 DF A3` (EBML header) | 0 |
| `video/quicktime` | video | 200 MB | `ftyp` | 4 |
| `audio/mpeg` | audio | 50 MB | `FF FB`, `FF F3`, `FF F2`, or `ID3` | 0 |
| `audio/wav` | audio | 50 MB | `RIFF` at 0 + `WAVE` at 8 | 0, 8 |
| `audio/ogg` | audio | 50 MB | `OggS` | 0 |
| `application/pdf` | document | 30 MB | `%PDF` | 0 |

Any content type not in this list is rejected with HTTP 422.

### 6.2 Validation Pipeline

`FileValidator.validate_upload(data, content_type, filename)` runs four steps in order:

1. **Content type allowlist** — Is `content_type` in the 11 allowed types?
2. **File size** — Does the file size respect the category limit?
3. **Magic bytes** — Do the first bytes of the file match the expected signature for the claimed type?
4. **Filename sanitization** — Clean the filename for safe storage

The pipeline short-circuits: if any step fails, subsequent steps are skipped.

### 6.3 Filename Sanitization Rules

`FileValidator.sanitize_filename(filename)`:

1. Strip path components (`os.path.basename`) — prevents directory traversal
2. Replace characters matching `[^\w\s\-.]` with `_`
3. Collapse multiple underscores/spaces into a single `_`
4. Remove leading dots (hidden files)
5. Truncate to 255 characters, preserving the file extension
6. Default to `unnamed_file` if the result is empty

---

## 7. Storage Backend

Defined in `app/storage/backend.py`

### 7.1 StorageBackend Protocol

The storage layer uses Python's `Protocol` pattern, allowing backend implementations to be swapped without changing business logic.

```python
class StorageBackend(Protocol):
    async def store(self, key: str, data: bytes) -> None: ...
    async def retrieve(self, key: str) -> bytes: ...
    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def append_chunk(self, key: str, data: bytes) -> None: ...
```

### 7.2 LocalStorageBackend

The current (and only) implementation. Suitable for single-server deployments like dealership local servers.

| Aspect | Detail |
|--------|--------|
| **Base path** | Configurable via `STORAGE_LOCAL_PATH` (default: `./uploads`) |
| **Directory creation** | Auto-creates base path and subdirectories on demand |
| **Path traversal prevention** | Resolves paths and verifies they start with `base_path.resolve()` |
| **Cleanup** | Deletes empty parent directories after file deletion |
| **Instance** | Singleton via `get_storage_backend()` (module-level cache) |

### 7.3 Storage Key Format

Keys follow a sharded directory structure using the first 4 characters of the attachment UUID:

```
attachments/{uuid[0:2]}/{uuid[2:4]}/{uuid}/{sanitized_filename}
```

Example: for attachment `a1b2c3d4-...` with filename `tire.jpg`:

```
attachments/a1/b2/a1b2c3d4-e5f6-7890-abcd-ef1234567890/tire.jpg
```

This 2-level sharding prevents any single directory from containing more than ~256 subdirectories at each level.

### 7.4 Chunk Storage

During chunked uploads, individual encrypted chunks are stored as separate files:

```
{storage_key}.chunk_000000
{storage_key}.chunk_000001
...
{storage_key}.chunk_001535
```

After background processing reassembles and re-encrypts the full file, all `.chunk_*` files are deleted and replaced by a single file at the base `storage_key`.

---

## 8. Upload Lifecycle

### 8.1 Simple Upload (< 5 MB)

```
Client                           Server                           Storage
  │                                │                                │
  │ POST /upload (multipart)       │                                │
  │ ─────────────────────────────> │                                │
  │                                │ validate(type, size, magic)    │
  │                                │ generate DEK                   │
  │                                │ encrypt(data, DEK)             │
  │                                │ wrap(DEK, master_key)          │
  │                                │ SHA-256(plaintext)             │
  │                                │ ─── store(key, encrypted) ──> │
  │                                │ INSERT attachment (READY)      │
  │                                │                                │
  │ <───── 201 AttachmentResponse  │                                │
  │        status: "ready"         │                                │
```

Simple uploads skip the entire UPLOADING → PROCESSING pipeline. The file goes directly to READY in a single synchronous request.

### 8.2 Chunked Upload (> 5 MB)

```
Client                           Server                           Storage
  │                                │                                │
  │ POST /upload/init (JSON)       │                                │
  │ ─────────────────────────────> │                                │
  │                                │ validate type, size            │
  │                                │ generate DEK, wrap             │
  │                                │ INSERT attachment (UPLOADING)  │
  │ <── 201 {upload_id, session}   │                                │
  │                                │                                │
  │ PATCH /upload/{id}/chunk/0     │                                │
  │ ─────────────────────────────> │                                │
  │                                │ unwrap DEK                     │
  │                                │ encrypt_chunk(data, DEK, 0)    │
  │                                │ ─ store(key.chunk_000000) ──> │
  │                                │ received_chunks++              │
  │ <───── 200 {received: 1}       │                                │
  │                                │                                │
  │ ... repeat for all chunks ...  │                                │
  │                                │                                │
  │ POST /upload/{id}/complete     │                                │
  │ ─────────────────────────────> │                                │
  │                                │ verify all chunks received     │
  │                                │ status → PROCESSING            │
  │                                │ schedule background task       │
  │ <── 200 {status: processing}   │                                │
  │                                │                                │
  │                    ┌───────────┴──────────────┐                 │
  │                    │ Background task:          │                 │
  │                    │  retrieve + decrypt chunks│                 │
  │                    │  reassemble plaintext     │                 │
  │                    │  validate magic bytes     │                 │
  │                    │  validate size            │                 │
  │                    │  SHA-256(plaintext)        │                 │
  │                    │  encrypt full file        │                 │
  │                    │  store final file ───────>│────────────────>│
  │                    │  delete chunk files       │                 │
  │                    │  status → READY           │                 │
  │                    │  emit attachment.ready     │                 │
  │                    └───────────┬──────────────┘                 │
  │                                │                                │
  │ <── WS: {type: attachment_ready}                                │
  │     (sent only to uploader)    │                                │
```

### 8.3 Comment Linking

Both REST and WebSocket paths follow the same validation:

```
For each attachment_id in the request:
  ├── Attachment must exist in database
  ├── status must be READY
  ├── uploader_id must match current user
  └── comment_id must be NULL (not already linked)

If valid:
  └── SET comment_id = new_comment.id  (permanent, non-transferable)
```

### 8.4 Orphan Cleanup

A background task runs as part of the application lifespan.

| Parameter | Value |
|-----------|-------|
| **Check interval** | Every 5 minutes (300 seconds) |
| **TTL** | 60 minutes (configurable: `STORAGE_ORPHAN_TTL_MINUTES`) |
| **Query** | `comment_id IS NULL` AND `status IN (ready, uploading, quarantined)` AND `created_at < now() - TTL` |
| **Action** | Delete from storage (file + thumbnail), then delete DB record |
| **Lifecycle** | Starts on app startup, cancelled on shutdown |

Defined in `app/main.py` — `_orphan_cleanup_loop()`

---

## 9. WebSocket Integration

### 9.1 Connection

```
ws://{host}/ws/chat?token={JWT}&vehicle_id={int}&section={section_name}
```

Room ID format: `vehicle_{id}_section_{section_name}`

The `ConnectionManager` tracks connections as: `rooms[room_id][username] = WebSocket`

### 9.2 Message Types

**Outgoing: Comment with attachments** (client → server)

```json
{
  "type": "comment",
  "content": "Check this damage on the sidewall",
  "attachment_ids": ["uuid1", "uuid2"]
}
```

**Incoming: Comment broadcast** (server → all in room)

```json
{
  "type": "comment",
  "comment_id": 42,
  "username": "alice",
  "content": "Check this damage on the sidewall",
  "vehicle_id": 1,
  "section": "tire",
  "timestamp": "2026-02-18T10:30:00",
  "mentions": [],
  "attachments": [
    {
      "id": "uuid1",
      "filename": "crack.jpg",
      "content_type": "image/jpeg",
      "file_size": 245760
    }
  ]
}
```

**Incoming: Attachment ready** (server → uploader only)

```json
{
  "type": "attachment_ready",
  "attachment_id": "uuid1",
  "filename": "video.mp4",
  "content_type": "video/mp4",
  "file_size": 15728640
}
```

This event is sent only to the uploader via `manager.send_personal_message()` — not broadcast to the room.

### 9.3 Event Bus Flow

```
_process_chunked_upload()
  │
  │ emit('attachment.ready', {attachment_id, uploader_username, ...})
  │
  v
broadcast_attachment_ready()        [app/events/handlers/attachment_events.py]
  │
  │ manager.send_personal_message(message, uploader_username)
  │
  v
Uploader's WebSocket connection receives {type: "attachment_ready"}
```

```
websocket.handle_websocket()
  │
  │ emit('comment.created', {comment_id, username, content, attachments, ...})
  │
  v
broadcast_comment_to_room()         [app/events/handlers/websocket_broadcast.py]
  │
  │ manager.broadcast_to_room(room_id, message, exclude_user=author)
  │
  v
All other users in the room receive {type: "comment", attachments: [...]}
```

---

## 10. Configuration Reference

All settings from `app/config.py` — class `Settings`

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| `storage_backend` | `STORAGE_BACKEND` | `"local"` | Backend type (`"local"` only; `"s3"` future) |
| `storage_local_path` | `STORAGE_LOCAL_PATH` | `"./uploads"` | Local filesystem base path |
| `storage_max_file_size` | `STORAGE_MAX_FILE_SIZE` | `209715200` (200 MB) | Global maximum file size |
| `storage_chunk_size` | `STORAGE_CHUNK_SIZE` | `102400` (100 KB) | Recommended chunk size |
| `storage_orphan_ttl_minutes` | `STORAGE_ORPHAN_TTL_MINUTES` | `60` | Minutes before orphan cleanup |
| `encryption_key` | `ENCRYPTION_KEY` | *(required)* | Master encryption key string |
| `secret_key` | `SECRET_KEY` | *(required)* | JWT signing key |
| `cors_origins` | `CORS_ORIGINS` | `"http://localhost:3000,http://localhost:8080"` | Comma-separated allowed origins |
| `access_token_expire_minutes` | `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT token lifetime |

**Client-side constants** (in `dealership_client.py`):

| Constant | Value | Description |
|----------|-------|-------------|
| `SIMPLE_UPLOAD_LIMIT` | 5 MB | Threshold for simple vs chunked upload |
| `CHUNK_SIZE` | 100 KB | Bytes per chunk for chunked uploads |

---

# Part II — Frontend Migration Guide

## 11. Migration Overview

The backend is already a proper REST API with WebSocket support. The TUI client (`dealership_client.py`) consumes the same HTTP endpoints and WebSocket protocol that a browser frontend will use. **Backend changes are minimal.** The migration is primarily a client-side effort.

### What Stays the Same

| Concern | How It Works Today | Browser Changes |
|---------|-------------------|-----------------|
| Authentication | `POST /api/auth/login` → JWT | Same endpoint, `fetch()` instead of `requests` |
| Simple upload | `POST /api/attachments/upload` with `multipart/form-data` | `FormData` + `fetch` — identical wire format |
| Chunked upload | Sequential `PATCH` per chunk | `Blob.slice()` + `fetch` per chunk |
| Comment with attachments | WebSocket JSON with `attachment_ids` | `WebSocket.send()` — identical payload |
| Download | `GET /api/attachments/{id}/download` | `fetch` → `Blob` → Object URL or `<a download>` |
| Metadata | `GET /api/attachments/{id}` | Same endpoint |
| Delete | `DELETE /api/attachments/{id}` | Same endpoint |

### What Needs to Change

| Concern | Current State | What to Add |
|---------|--------------|-------------|
| **CORS** | Configured, localhost only | Add frontend domain to `CORS_ORIGINS` |
| **Auth refresh** | 30-min JWT, no refresh | Add refresh token endpoint |
| **Content headers** | `X-Content-Type-Options: nosniff` | Add `Content-Security-Policy` |
| **Thumbnails** | DB column exists, not populated | Implement generation + endpoint |
| **Rate limiting** | Auth routes only | Add limits on upload routes |
| **Reconnection** | TUI exits on disconnect | Browser must auto-reconnect |

---

## 12. Backend Changes Required

### 12.1 CORS Configuration — Priority: HIGH

**Current state**: CORS middleware is already configured in `app/main.py` lines 108-115 with `allow_credentials=True` and origins from the `CORS_ORIGINS` env var.

**Action**: Add the frontend domain to `CORS_ORIGINS`:

```bash
# .env
CORS_ORIGINS=http://localhost:3000,http://localhost:8080,https://eval.dealership.local
```

**Production hardening**: Replace `allow_headers=["*"]` with specific headers:

```python
allow_headers=["Authorization", "Content-Type", "X-Requested-With"]
```

### 12.2 Refresh Tokens — Priority: HIGH

**Current state**: JWT access token with 30-minute expiry. No refresh mechanism. The TUI works because sessions are short-lived.

**A browser SPA needs token refresh** — users should not be logged out mid-upload.

Recommended implementation:
1. Add `POST /api/auth/refresh` endpoint
2. Issue a refresh token (longer-lived, e.g., 7 days) alongside the access token at login
3. Store refresh token in an `httpOnly`, `Secure`, `SameSite=Strict` cookie
4. Access token stays in memory (not `localStorage` — XSS risk)
5. Implement refresh token rotation (single-use: each refresh issues a new refresh token)
6. Add a `refresh_tokens` table or use a separate long-lived JWT

### 12.3 Download Strategy — Priority: MEDIUM

**Current state**: `GET /api/attachments/{id}/download` decrypts server-side and streams the plaintext back. This works but has implications:

| Approach | Pros | Cons |
|----------|------|------|
| **Keep proxy download** (current) | Simple, secure, encryption key never leaves server | Server CPU bound per download, no CDN benefit |
| **Add inline preview endpoint** | Enables `<img src>` and PDF viewers | Need a separate endpoint with `Content-Disposition: inline` |
| **Pre-signed temp URLs** | CDN-compatible, offloads bandwidth | Plaintext briefly on disk; more complex; TTL management |

**Recommendation**: For a dealership internal tool, keep the proxy approach. Add an inline preview variant for images/PDFs:

```python
# Add query parameter: /api/attachments/{id}/download?inline=true
if inline:
    disposition = f'inline; filename="{attachment.filename}"'
else:
    disposition = f'attachment; filename="{attachment.filename}"'
```

**Important**: Because files are encrypted at rest with per-file keys, the server must always be in the decryption path. Sending the DEK to the browser for client-side decryption would be a security downgrade.

### 12.4 Thumbnail Generation — Priority: MEDIUM

The `thumbnail_storage_key` column exists in the database but is never populated.

Recommended implementation:
1. Add `Pillow` dependency for image thumbnails (256x256 max)
2. For video: extract first frame with `python-ffmpeg` (optional)
3. Generate during upload processing (after validation, before READY)
4. Encrypt and store like the main file: `{storage_key}.thumb`
5. Add `GET /api/attachments/{id}/thumbnail` endpoint
6. Return as `image/jpeg` regardless of source format (smaller size)

### 12.5 Content-Security-Policy — Priority: HIGH

When serving user-uploaded content to browsers, there is a risk of stored XSS (e.g., crafted PDFs with JavaScript, SVG with embedded scripts).

The current system already blocks SVG and HTML via the MIME allowlist (only 11 safe types), which mitigates the worst vectors.

Additional measures:
- Add `Content-Security-Policy: default-src 'none'` to download responses
- Serve attachments from a separate origin to isolate cookies (e.g., `files.dealership.local`)
- Never set `Content-Disposition: inline` for untrusted content types
- The existing `X-Content-Type-Options: nosniff` header is already in place

### 12.6 Rate Limiting — Priority: LOW

Current rate limits cover only auth routes (`5/minute` register, `10/minute` login). Upload routes have no rate limits.

Recommended limits for browser use:

| Endpoint | Suggested Limit |
|----------|----------------|
| `POST /upload` | 20/minute per user |
| `POST /upload/init` | 10/minute per user |
| `PATCH /upload/{id}/chunk/{index}` | 200/minute per user |
| `POST /upload/{id}/complete` | 10/minute per user |
| `GET /{id}/download` | 60/minute per user |

---

## 13. Frontend Implementation Guide

### 13.1 Simple Upload (< 5 MB)

```javascript
async function uploadSimple(file, token) {
  const formData = new FormData();
  formData.append('file', file);  // File object from <input type="file">

  const response = await fetch('/api/attachments/upload', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData,
    // Do NOT set Content-Type — browser sets multipart boundary automatically
  });

  if (!response.ok) throw new Error(await response.text());
  return await response.json();  // AttachmentResponse
}
```

### 13.2 Chunked Upload with Progress

```javascript
const CHUNK_SIZE = 100 * 1024;  // 100KB — must match server config

async function uploadChunked(file, token, onProgress) {
  const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

  // Phase 1: Init
  const initResp = await fetch('/api/attachments/upload/init', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      filename: file.name,
      content_type: file.type,
      total_size: file.size,
      total_chunks: totalChunks,
    }),
  });
  const { upload_id } = await initResp.json();

  // Phase 2: Upload chunks
  for (let i = 0; i < totalChunks; i++) {
    const start = i * CHUNK_SIZE;
    const end = Math.min(start + CHUNK_SIZE, file.size);
    const chunk = file.slice(start, end);  // Blob.slice() — zero-copy

    const chunkForm = new FormData();
    chunkForm.append('file', chunk, `chunk_${i}`);

    await fetch(`/api/attachments/upload/${upload_id}/chunk/${i}`, {
      method: 'PATCH',
      headers: { 'Authorization': `Bearer ${token}` },
      body: chunkForm,
    });

    onProgress?.((i + 1) / totalChunks);  // 0.0 → 1.0
  }

  // Phase 3: Complete
  const completeResp = await fetch(
    `/api/attachments/upload/${upload_id}/complete`,
    {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
    }
  );
  return await completeResp.json();  // ChunkedUploadCompleteResponse
}
```

**Upload dispatcher:**

```javascript
const SIMPLE_LIMIT = 5 * 1024 * 1024;

async function uploadFile(file, token, onProgress) {
  if (file.size <= SIMPLE_LIMIT) {
    return uploadSimple(file, token);
  } else {
    return uploadChunked(file, token, onProgress);
  }
}
```

### 13.3 Drag-and-Drop UX

Key considerations for the frontend:

1. **HTML5 Drag and Drop**: Use `dragenter`, `dragover`, `drop` events on the comment area
2. **Client-side preview**: Use `FileReader.readAsDataURL()` for immediate image thumbnails before upload starts
3. **Client-side type check**: Validate file extension against allowed types before upload (UX only, not security — server re-validates)
4. **Progress bar**: Show per-file progress for chunked uploads
5. **Multiple files**: Queue uploads, run them with a concurrency limit (e.g., 2 concurrent uploads)
6. **Pending badge**: Show count of uploaded-but-not-sent attachments
7. **Abort support**: Use `AbortController` to cancel in-progress uploads

### 13.4 WebSocket Reconnection

The TUI client has no reconnection logic. A browser frontend must handle disconnections gracefully.

Recommended pattern:

```javascript
class ReconnectingWebSocket {
  constructor(url, options = {}) {
    this.url = url;
    this.maxRetries = options.maxRetries ?? 10;
    this.baseDelay = options.baseDelay ?? 1000;   // 1 second
    this.maxDelay = options.maxDelay ?? 30000;     // 30 seconds
    this.retries = 0;
    this.listeners = { message: [], open: [], close: [] };
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.retries = 0;  // Reset on successful connect
      this.listeners.open.forEach(fn => fn());
    };

    this.ws.onmessage = (event) => {
      this.listeners.message.forEach(fn => fn(JSON.parse(event.data)));
    };

    this.ws.onclose = (event) => {
      if (event.code !== 1000) {  // Not a clean close
        this.scheduleReconnect();
      }
      this.listeners.close.forEach(fn => fn(event));
    };
  }

  scheduleReconnect() {
    if (this.retries >= this.maxRetries) return;
    const delay = Math.min(
      this.baseDelay * Math.pow(2, this.retries),
      this.maxDelay
    );
    this.retries++;
    setTimeout(() => this.connect(), delay);
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }
}
```

Additional considerations:
- **Token refresh before reconnect**: The JWT may have expired during disconnection
- **Visual indicator**: Show connection state (connected / reconnecting / disconnected)
- **Message buffering**: Queue outgoing messages while disconnected, send on reconnect
- **Re-subscribe**: Re-join the room after reconnecting

### 13.5 Download Handling in Browser

**Download to file:**

```javascript
async function downloadAttachment(attachmentId, filename, token) {
  const response = await fetch(`/api/attachments/${attachmentId}/download`, {
    headers: { 'Authorization': `Bearer ${token}` },
  });
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();

  URL.revokeObjectURL(url);
}
```

**Inline image preview:**

```javascript
async function getPreviewUrl(attachmentId, token) {
  const response = await fetch(`/api/attachments/${attachmentId}/download`, {
    headers: { 'Authorization': `Bearer ${token}` },
  });
  const blob = await response.blob();
  return URL.createObjectURL(blob);
  // Remember to revoke when the component unmounts
}

// Usage in React:
// <img src={previewUrl} alt={filename} />
```

**Inline PDF viewer:**

```html
<iframe src={previewUrl} type="application/pdf" width="100%" height="600px" />
```

Or use a library like `pdf.js` for more control.

---

## 14. CDN and Scaling Considerations

### 14.1 Current Architecture Limitations

- **Single server**: `LocalStorageBackend` stores files on the local filesystem
- **CPU-bound downloads**: Every download decrypts server-side
- **No caching layer**: Repeated downloads of the same file re-decrypt each time
- **No horizontal scaling**: File storage is not shared across instances

### 14.2 S3 Migration Path

The `StorageBackend` Protocol makes this straightforward:

1. Implement `S3StorageBackend` conforming to the 6-method Protocol
2. Use `aioboto3` for async S3 operations
3. Keep envelope encryption (encrypt before storing to S3)
4. Switch via config: `STORAGE_BACKEND=s3`
5. Add S3-specific settings: `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`

The Protocol abstraction means no business logic changes — only the storage implementation is swapped.

### 14.3 CDN with Encrypted Content

Since files are encrypted at rest, a CDN cannot serve them directly. Options:

| Approach | Description | Tradeoff |
|----------|-------------|----------|
| **Proxy** (current) | Server decrypts and streams | Simple, secure. CPU-bound. |
| **Edge decryption** | Lambda@Edge or equivalent decrypts at CDN | Complex. Key distribution to edge. |
| **Pre-decrypted cache** | Decrypt to temp storage with signed URLs and short TTL | Plaintext briefly exists outside the server. |

**Recommendation**: For a dealership internal tool with limited concurrent users, the proxy approach is sufficient. If scaling to multiple locations or many users, consider the pre-decrypted cache with 5-minute TTLs behind CloudFront signed URLs.

### 14.4 Multi-Instance Deployment

To run multiple FastAPI instances behind a load balancer:

1. **Shared storage**: Migrate to S3 or a shared NFS mount
2. **Sticky sessions for WebSocket**: Ensure WebSocket connections route to the same instance (or use Redis pub/sub for cross-instance broadcasting)
3. **Shared orphan cleanup**: Add distributed locking (e.g., PostgreSQL advisory locks) to prevent multiple instances from running cleanup simultaneously
4. **Shared rate limiting**: Move from in-memory to Redis-backed rate limiting

---

## 15. Security Checklist

For deploying with a browser frontend:

- [ ] Add frontend domain to `CORS_ORIGINS`
- [ ] Narrow `allow_headers` from `["*"]` to specific headers
- [ ] Implement refresh token flow with `httpOnly` cookie storage
- [ ] Serve API over HTTPS only (TLS termination at reverse proxy)
- [ ] Add `Content-Security-Policy: default-src 'none'` to download responses
- [ ] Serve uploaded content from a separate origin (cookie isolation)
- [ ] `X-Content-Type-Options: nosniff` on all responses (already on downloads)
- [ ] Validate file types client-side before upload (UX only, not security)
- [ ] Implement WebSocket token refresh before expiry
- [ ] Add upload rate limiting per user
- [ ] Ensure `Content-Disposition: attachment` for non-image downloads
- [ ] Review `ENCRYPTION_KEY` management (not in source control, use secrets manager)
- [ ] Set `Secure`, `HttpOnly`, `SameSite=Strict` on auth cookies
- [ ] Audit WebSocket message payloads for injection vectors
- [ ] Enable structured logging for security-relevant events (upload, download, delete, auth failure)

---

## 16. Future Enhancements

| Feature | Description | Complexity |
|---------|-------------|:---:|
| **Thumbnail generation** | Pillow for images, ffmpeg for video first-frame. Column already exists. | Medium |
| **Inline preview endpoint** | `Content-Disposition: inline` variant for images/PDFs | Low |
| **Virus scanning** | ClamAV integration in the PROCESSING stage before READY | Medium |
| **S3 storage backend** | Implement `S3StorageBackend` using `aioboto3` | Medium |
| **Upload resume** | Track which chunks were uploaded; allow resume after disconnection | Medium |
| **Batch upload** | Upload multiple files in a single chunked session | Medium |
| **Image gallery view** | Frontend component for swipe/zoom through comment attachments | Frontend |
| **Inline PDF viewer** | `pdf.js` integration for in-browser rendering | Frontend |
| **Attachment search** | Full-text search on filenames, filter by type/date/section | Low |
| **Key rotation** | Versioned master keys with background DEK re-wrapping | High |
| **Access control** | Per-attachment visibility (e.g., only evaluators in that section can download) | Medium |
| **Attachment versioning** | Replace a file while keeping version history | High |

---

# Appendices

## Appendix A: curl Examples

All examples assume `TOKEN` is set:

```bash
export TOKEN="your_jwt_token_here"
export BASE="http://127.0.0.1:8000"
```

**Simple upload:**

```bash
curl -X POST "$BASE/api/attachments/upload" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/image.jpg;type=image/jpeg"
```

**Init chunked upload:**

```bash
curl -X POST "$BASE/api/attachments/upload/init" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "video.mp4",
    "content_type": "video/mp4",
    "total_size": 15728640,
    "total_chunks": 154
  }'
```

**Upload a chunk:**

```bash
UPLOAD_ID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"

curl -X PATCH "$BASE/api/attachments/upload/$UPLOAD_ID/chunk/0" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/chunk_000"
```

**Complete chunked upload:**

```bash
curl -X POST "$BASE/api/attachments/upload/$UPLOAD_ID/complete" \
  -H "Authorization: Bearer $TOKEN"
```

**Get attachment metadata:**

```bash
ATT_ID="a1b2c3d4-e5f6-7890-abcd-ef1234567890"

curl "$BASE/api/attachments/$ATT_ID" \
  -H "Authorization: Bearer $TOKEN"
```

**Download attachment:**

```bash
curl -o downloaded_file.jpg \
  "$BASE/api/attachments/$ATT_ID/download" \
  -H "Authorization: Bearer $TOKEN"
```

**Delete attachment:**

```bash
curl -X DELETE "$BASE/api/attachments/$ATT_ID" \
  -H "Authorization: Bearer $TOKEN"
```

**Create comment with attachments (REST):**

```bash
curl -X POST "$BASE/api/dealership/comments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_id": 1,
    "section": "tire",
    "content": "Check this damage",
    "attachment_ids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
  }'
```

---

## Appendix B: Error Code Reference

| Code | Endpoint | Detail |
|:---:|----------|--------|
| 400 | `PATCH .../chunk/{i}` | Empty chunk |
| 400 | `PATCH .../chunk/{i}` | Chunk index {i} exceeds total chunks {n} |
| 400 | `POST .../complete` | Missing chunks: received {n}/{total} |
| 400 | `DELETE /{id}` | Cannot delete an attachment linked to a comment. Delete the comment instead. |
| 404 | `PATCH .../chunk/{i}` | Upload not found or not in uploading state |
| 404 | `POST .../complete` | Upload not found or not in uploading state |
| 404 | `GET /{id}/download` | Attachment not found or not ready |
| 404 | `GET /{id}/download` | Attachment file not found in storage |
| 404 | `GET /{id}` | Attachment not found |
| 404 | `DELETE /{id}` | Attachment not found or you don't have permission to delete it |
| 413 | `POST /upload` | File too large for simple upload. Use chunked upload for files > 5MB. |
| 422 | `POST /upload` | Content type not allowed: {type} |
| 422 | `POST /upload` | File content does not match claimed content type |
| 422 | `POST /upload` | File size {x}MB exceeds {category} limit of {y}MB |
| 422 | `POST /upload/init` | Content type not allowed: {type} |
| 422 | `POST /upload/init` | File size {x}MB exceeds {category} limit of {y}MB |
| 422 | `POST /upload/init` | Validation error (filename, total_size, total_chunks) |
| 500 | `GET /{id}/download` | File integrity check failed |

---

## Appendix C: Glossary

| Term | Definition |
|------|-----------|
| **AES-256-GCM** | Advanced Encryption Standard with 256-bit key and Galois/Counter Mode. Provides both confidentiality and integrity (authenticated encryption). |
| **DEK** | Data Encryption Key. The per-file AES-256 key used to encrypt the actual file content. |
| **KEK** | Key Encryption Key. The master Fernet key used to wrap (encrypt) DEKs. Also known as the wrapping key. |
| **Envelope encryption** | Pattern where data is encrypted with a DEK, and the DEK is encrypted with a KEK. Allows per-file keys without exposing the master key to bulk data. |
| **Fernet** | A symmetric encryption scheme from the `cryptography` library. Uses AES-128-CBC with HMAC-SHA256 for authentication. Used here only to wrap/unwrap DEKs. |
| **GCM tag** | A 16-byte authentication tag produced by AES-GCM. Verifies that ciphertext has not been tampered with during decryption. |
| **Magic bytes** | The first few bytes of a file that identify its type (e.g., JPEG starts with `FF D8 FF`). More reliable than file extensions. |
| **Nonce** | A 12-byte random value used once per AES-GCM encryption. Ensures the same plaintext produces different ciphertext each time. |
| **Orphan** | An attachment that was uploaded but never linked to a comment. Cleaned up after the configured TTL. |
| **Quarantined** | An attachment that failed validation (magic bytes mismatch, size exceeded, chunk ordering error). Cannot be used or downloaded. |
| **Storage key** | The logical path used to identify a file in the storage backend. Mapped to a filesystem path by `LocalStorageBackend`. |
| **Exclusive binding** | The design constraint that an attachment can be linked to at most one comment, and that link is permanent. Modeled after WhatsApp's media-to-message relationship. |
