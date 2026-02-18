# Dealership Vehicle Evaluation System — Design Specification

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Database Models](#2-database-models)
3. [Schemas (Request / Response)](#3-schemas-request--response)
4. [API Routes](#4-api-routes)
5. [WebSocket Protocol](#5-websocket-protocol)
6. [Core Feature Internals](#6-core-feature-internals)
7. [Event-Driven Architecture](#7-event-driven-architecture)
8. [Authentication & Security](#8-authentication--security)
9. [Frontend Migration Guide](#9-frontend-migration-guide)

---

## 1. System Overview

The system is a real-time collaborative vehicle evaluation platform for dealerships. Multiple employees can simultaneously evaluate the same vehicle, leaving comments per evaluation section, tagging colleagues with `@mentions`, and receiving notifications.

**Workflow:**
```
Vehicle enters system (PENDING)
    → Online Evaluation   (Tire, Warranty, Accident/Damages)
    → Inspection          (Paint, Previous Owners)
    → Completed / Rejected
```

**Core capabilities:**
- Vehicle CRUD with status progression
- 16 evaluation sections organized by category
- Per-section threaded comments with encryption at rest
- Real-time collaboration via WebSocket rooms (one room = vehicle + section)
- @mention detection with instant + persisted notifications
- Event-driven architecture (comment saves → events → notifications + broadcasts)

---

## 2. Database Models

### `users`

| Column            | Type         | Constraints               |
|-------------------|--------------|---------------------------|
| `id`              | Integer      | PK, auto-increment        |
| `username`        | String(50)   | unique, indexed, not null |
| `hashed_password` | String(255)  | not null                  |
| `created_at`      | DateTime     | default: now              |

### `vehicles`

| Column       | Type            | Constraints                        |
|--------------|-----------------|------------------------------------|
| `id`         | Integer         | PK, auto-increment                 |
| `vin`        | String(17)      | unique, indexed, not null          |
| `make`       | String(50)      | not null                           |
| `model`      | String(50)      | not null                           |
| `year`       | Integer         | not null                           |
| `status`     | Enum            | not null, default: `pending`       |
| `created_at` | DateTime        | default: now                       |
| `updated_at` | DateTime        | default: now, on update: now       |

**`VehicleStatus` enum values** (stored as lowercase strings in DB):

| Value               | Meaning                         |
|---------------------|---------------------------------|
| `pending`           | Just entered, not yet evaluated |
| `online_evaluation` | Remote evaluation in progress   |
| `inspection`        | Physical inspection in progress |
| `completed`         | Evaluation done                 |
| `rejected`          | Vehicle rejected from inventory |

### `comments`

| Column       | Type       | Constraints                       |
|--------------|------------|-----------------------------------|
| `id`         | Integer    | PK, auto-increment                |
| `vehicle_id` | Integer    | FK → `vehicles.id`, indexed       |
| `section`    | Enum       | `SectionType`, indexed, not null  |
| `user_id`    | Integer    | FK → `users.id`, not null         |
| `content`    | Text       | Fernet-encrypted at rest          |
| `created_at` | DateTime   | default: now                      |

> **Note on encryption**: `content` is always stored encrypted. The API decrypts on read. Clients always receive plaintext; encryption/decryption is server-side only.

### `notifications`

| Column         | Type     | Constraints               |
|----------------|----------|---------------------------|
| `id`           | Integer  | PK, auto-increment        |
| `recipient_id` | Integer  | FK → `users.id`, indexed  |
| `comment_id`   | Integer  | FK → `comments.id`        |
| `is_read`      | Boolean  | default: False            |
| `created_at`   | DateTime | default: now              |

Notifications are created when a user is `@mentioned` in a comment. One notification per recipient per comment.

### `section_metadata`

| Column         | Type        | Constraints                       |
|----------------|-------------|-----------------------------------|
| `section_name` | String(50)  | PK, must match `SectionType` enum |
| `display_name` | String(100) | not null                          |
| `description`  | Text        | nullable                          |
| `category`     | String(50)  | not null (e.g., "Mechanical")     |
| `order_num`    | Integer     | not null (display sort order)     |
| `icon`         | String(50)  | nullable (emoji)                  |
| `is_active`    | Boolean     | default: True                     |
| `created_at`   | DateTime    | default: now                      |
| `updated_at`   | DateTime    | default: now, on update: now      |

This is the **hybrid sections** approach: the enum in `comments.section` provides type-safe fast queries (no JOIN needed), while this table provides rich metadata that can be updated without migrations.

### `SectionType` enum values

| Value              | Display Name        | Category          | Order |
|--------------------|---------------------|-------------------|-------|
| `general`          | General Comments    | General           | 1     |
| `tire`             | Tire Evaluation     | Online Evaluation | 2     |
| `warranty`         | Warranty            | Online Evaluation | 3     |
| `accident_damages` | Accident & Damages  | Online Evaluation | 4     |
| `paint`            | Paint Inspection    | Inspection        | 5     |
| `previous_owners`  | Previous Owners     | Inspection        | 6     |
| `engine`           | Engine Check        | Mechanical        | 7     |
| `transmission`     | Transmission        | Mechanical        | 8     |
| `brakes`           | Brakes              | Mechanical        | 9     |
| `suspension`       | Suspension          | Mechanical        | 10    |
| `exhaust`          | Exhaust System      | Mechanical        | 11    |
| `interior`         | Interior            | Additional        | 12    |
| `electronics`      | Electronics         | Additional        | 13    |
| `fluids`           | Fluids              | Additional        | 14    |
| `lights`           | Lights              | Additional        | 15    |
| `ac_heating`       | AC & Heating        | Additional        | 16    |

---

## 3. Schemas (Request / Response)

### Auth

**`UserCreate`** (request body for register/login)
```json
{
  "username": "john_doe",
  "password": "SecurePass1"
}
```
Validations: username 3–50 chars, alphanumeric+`_-`; password 8–128 chars, must contain uppercase, lowercase, digit.

**`Token`** (response from login)
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

---

### Vehicles

**`VehicleCreate`** (request)
```json
{
  "vin": "1HGBH41JXMN109186",
  "make": "Honda",
  "model": "Accord",
  "year": 2021
}
```
Validations: VIN exactly 17 chars, valid charset (no I/O/Q); year 1900 – current+1.

**`VehicleUpdate`** (request, all fields optional)
```json
{
  "status": "online_evaluation",
  "make": "Honda",
  "model": "Accord",
  "year": 2021
}
```

**`VehicleResponse`**
```json
{
  "id": 1,
  "vin": "1HGBH41JXMN109186",
  "make": "Honda",
  "model": "Accord",
  "year": 2021,
  "status": "pending",
  "created_at": "2026-01-01T10:00:00",
  "updated_at": "2026-01-01T10:00:00"
}
```

---

### Comments

**`CommentCreate`** (request)
```json
{
  "vehicle_id": 1,
  "section": "general",
  "content": "Looks good overall. @technician1 please check the engine."
}
```

**`CommentResponse`**
```json
{
  "id": 42,
  "vehicle_id": 1,
  "section": "general",
  "user_id": 3,
  "username": "john_doe",
  "content": "Looks good overall. @technician1 please check the engine.",
  "created_at": "2026-01-01T10:05:00",
  "mentioned_users": ["technician1"]
}
```
`mentioned_users` is derived at read time by running the mention regex over the decrypted content. It is **not** stored in the database.

---

### Notifications

**`NotificationResponse`**
```json
{
  "id": 7,
  "recipient_id": 5,
  "comment_id": 42,
  "is_read": false,
  "created_at": "2026-01-01T10:05:00",
  "comment": { ...CommentResponse... }
}
```
The `comment` field is the full `CommentResponse` of the comment that triggered the mention.

---

### Sections

**`SectionInfo`** (response from `GET /sections`)
```json
{
  "section_name": "tire",
  "display_name": "Tire Evaluation",
  "description": "Tire condition, tread depth, wear patterns",
  "category": "Online Evaluation",
  "order_num": 2,
  "icon": "🛞",
  "is_active": true
}
```

---

## 4. API Routes

All routes (except auth) require `Authorization: Bearer <token>` header.

### Authentication — `/api/auth`

| Method | Path        | Description              | Rate Limit     |
|--------|-------------|--------------------------|----------------|
| POST   | `/register` | Create a new user        | 5 / min per IP |
| POST   | `/login`    | Login and receive JWT    | 10 / min per IP|

---

### Vehicles — `/api/dealership/vehicles`

| Method | Path           | Description                     | Notes                          |
|--------|----------------|---------------------------------|--------------------------------|
| GET    | `/vehicles`    | List all vehicles               | Supports `skip`, `limit`       |
| POST   | `/vehicles`    | Create a new vehicle            | VIN must be unique, auto-uppercased |
| GET    | `/vehicles/{id}` | Get a single vehicle          | 404 if not found               |
| PATCH  | `/vehicles/{id}` | Update vehicle fields         | All fields optional            |

---

### Sections — `/api/dealership/sections`

| Method | Path        | Description              | Notes                           |
|--------|-------------|--------------------------|---------------------------------|
| GET    | `/sections` | List evaluation sections | `?include_inactive=true` to show hidden |

Returns sections ordered by `order_num`. Frontend should use this to build section tabs/list and cache the result.

---

### Comments — `/api/dealership/comments`

| Method | Path        | Description                            | Notes                         |
|--------|-------------|----------------------------------------|-------------------------------|
| GET    | `/comments` | List comments for a vehicle section    | Requires `?vehicle_id=X&section=Y` |
| POST   | `/comments` | Create a comment (HTTP, non-realtime)  | Triggers @mention notifications |

> **Dual path for comment creation**: Comments can be created via REST (POST `/comments`) or via WebSocket (`type: "comment"` message). Both paths encrypt and persist the comment, then emit the `comment.created` event.

---

### Notifications — `/api/dealership/notifications`

| Method | Path                              | Description                      |
|--------|-----------------------------------|----------------------------------|
| GET    | `/notifications`                  | List notifications (all or unread) |
| PATCH  | `/notifications/{id}/read`        | Mark one notification as read    |
| PATCH  | `/notifications/read-all`         | Mark all notifications as read   |

`GET /notifications` accepts `?unread_only=true`. Returns at most 50, newest first.

---

### Utility

| Method | Path      | Description                         |
|--------|-----------|-------------------------------------|
| GET    | `/`       | API info and endpoint index         |
| GET    | `/health` | Health check (no auth required)     |

---

## 5. WebSocket Protocol

**Connection URL:**
```
ws://host/ws/chat?token=<jwt>&vehicle_id=<int>&section=<section_name>
```

All three query parameters are required. The `section` must be a valid `SectionType` value (e.g., `general`, `tire`).

**Rooms:** Each `vehicle_id + section` combination is its own isolated room. Users only receive messages from their current room.

### Client → Server messages

```json
{ "type": "comment", "content": "Your comment text here @mention" }
```

### Server → Client messages

| Type       | When                              | Payload fields                               |
|------------|-----------------------------------|----------------------------------------------|
| `system`   | Connect, disconnect, user joined/left | `message: string`                        |
| `comment`  | A user in the room sends a comment | `username`, `content`, `timestamp`, `mentions: string[]` |
| `mention`  | You are @mentioned anywhere        | `message: string`, `comment_id`, `vehicle_id`, `section` |

### Connection lifecycle

```
Client connects with token + vehicle_id + section
  → Server authenticates JWT
  → Server validates vehicle exists
  → Server validates section enum value
  → Server adds user to room
  → Server sends "system: Connected to ..." to client
  → Server broadcasts "system: {username} joined" to room
  ...
  → Client disconnects (or drops connection)
  → Server removes user from room
  → Server broadcasts "system: {username} left" to room
```

If any validation fails (bad token, unknown vehicle, invalid section), the server closes with code `1008` before accepting the connection.

---

## 6. Core Feature Internals

### Comment Encryption

All comment content is encrypted using **Fernet** (AES-128-CBC + HMAC-SHA256) before writing to the database. Decryption happens on every read — the client always sees plaintext. The encryption key is stored in `.env` as `ENCRYPTION_KEY` and never in the database.

This means:
- A database breach does not expose comment content
- Changing the key invalidates all existing comments (no key rotation built in yet)
- The REST response and WebSocket broadcast both carry decrypted content

### @Mention Detection

The regex used is:
```python
r'(?:^|(?<=\s))@([a-zA-Z0-9_-]+)'
```

Rules:
- `@` must be preceded by whitespace or be at the start of the string
- This prevents matching email addresses (e.g., `admin@dealer.com` does not trigger a mention)
- Usernames can contain letters, numbers, underscores, and hyphens
- Duplicates are removed; a user is only notified once per comment even if mentioned twice

`mentioned_users` is re-derived from the content at read time. It is not stored, so it always reflects the actual content.

### Comment Creation Flow (via WebSocket)

```
1. Client sends: { type: "comment", content: "..." }
2. Server encrypts content → stores Comment in DB
3. Server emits 'comment.created' event with decrypted content
4. Handler: create_mention_notifications
   → Extracts @mentions
   → Queries DB for each username
   → Creates Notification records (skips self, skips duplicates)
5. Handler: broadcast_to_room
   → Broadcasts comment to all users in the same vehicle+section room
   → Sends personal 'mention' message to each mentioned user (regardless of their current room)
```

### Notification Personal Delivery

Mentioned users receive a real-time `mention` message **even if they are in a different room**. This works because `ConnectionManager.send_personal_message()` looks up the user's current room and delivers directly to their WebSocket. If the user is offline, only the persisted DB notification exists — they see it next time they poll `/notifications`.

---

## 7. Event-Driven Architecture

The system uses a lightweight in-process event bus (`app/events/bus.py`) instead of tying notification and broadcast logic directly into the WebSocket handler.

**Event bus pattern:**
```python
# Register a handler
@event_bus.on('comment.created')
async def my_handler(data: dict):
    ...

# Emit an event
await event_bus.emit('comment.created', { ... })
```

Handlers run sequentially. If one handler raises an exception, it is caught and logged — the next handler still runs.

**Registered events and handlers:**

| Event             | Handler file                          | What it does                              |
|-------------------|---------------------------------------|-------------------------------------------|
| `comment.created` | `handlers/notifications.py`           | Creates DB notifications for @mentions    |
| `comment.created` | `handlers/websocket_broadcast.py`     | Broadcasts comment to room, DMs mentions  |

Handlers are registered at import time. `main.py` imports them explicitly on startup:
```python
from app.events.handlers import notifications, websocket_broadcast  # noqa: F401
```

Adding a new reaction to a comment (e.g., audit logging, analytics) is a new handler file — no changes to existing code.

---

## 8. Authentication & Security

- **JWT** tokens, 30-minute expiry, signed with `SECRET_KEY` from `.env`
- **bcrypt** password hashing (12 rounds)
- **Authorization header** only — `Authorization: Bearer <token>`. The WebSocket uses the token as a query parameter (`?token=`) because browsers cannot set custom headers on WebSocket connections. This is the standard pattern but means tokens are visible in server logs; use HTTPS in production.
- **Rate limiting** via SlowAPI: 5 req/min on register, 10 req/min on login, per IP
- **CORS** origins are configured in `.env` as a comma-separated list — no wildcard in production
- **No secrets in code** — all secrets loaded from `.env`, application refuses to start if they are missing

---

## 9. Frontend Migration Guide

This section describes what changes when replacing the TUI (`dealership_client.py`) with a real frontend (e.g., React, Vue, Next.js) plus any backend changes needed.

### 9.1 What the Backend Already Does Correctly

These are production-ready and require no changes:

- REST API with proper HTTP methods, status codes, and JSON responses
- JWT auth with `Authorization: Bearer` header
- WebSocket endpoint with token in query string
- CORS configured for specific origins
- Request validation with descriptive error messages
- Encryption transparent to the client (plaintext in, plaintext out)
- Pagination support on `/vehicles` (`skip`, `limit`)
- `GET /sections` returns all metadata needed to render a section list (icon, display name, description, category, order)

### 9.2 Authentication Flow Changes

**TUI (current):**
- User types username/password once at startup
- Token stored in memory for the session lifetime

**Frontend:**
- Store token in `httpOnly` cookie (recommended) or `localStorage` (simpler but less secure)
- Implement token refresh or re-login prompt when token expires (currently 30 min)
- Consider adding a `POST /api/auth/logout` endpoint to invalidate tokens server-side if using a token blacklist

**Backend change needed:** Add a `GET /api/auth/me` endpoint to return the current user's profile, so the frontend can restore state after a page refresh without requiring a new login.

```python
@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

### 9.3 Replacing the WebSocket Client

**TUI (current):**
- Single persistent WebSocket connection via `websockets` library
- Handles one room at a time; user navigates between sections sequentially

**Frontend:**
- Use the browser's native `WebSocket` API or a library like `socket.io-client` (though the backend uses raw WebSockets, not Socket.IO)
- Reconnect automatically on disconnect (exponential backoff)
- Manage connection state in component/store (connected, connecting, disconnected)

**Example JavaScript connection:**
```javascript
const ws = new WebSocket(
  `ws://localhost:8000/ws/chat?token=${token}&vehicle_id=${vehicleId}&section=${section}`
);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'comment') { /* append to chat */ }
  if (data.type === 'mention') { /* show toast notification */ }
  if (data.type === 'system') { /* show system banner */ }
};

ws.send(JSON.stringify({ type: 'comment', content: messageText }));
```

**Important:** The WebSocket reconnects if the section tab changes. Close the old connection, open a new one with the new `section` parameter.

### 9.4 Comment Loading Pattern

**TUI (current):**
- Loads full comment history via REST on section entry, then switches to WebSocket for live updates

**Frontend (recommended — same pattern, works well):**
1. On section mount: `GET /api/dealership/comments?vehicle_id=X&section=Y` to load history
2. Open WebSocket connection for the section
3. Append incoming `comment` events to local state
4. On section unmount: close WebSocket

**Suggested backend addition:** Add `?since=<ISO timestamp>` to the comments endpoint to support loading only new comments since a known timestamp (useful for reconnections without reloading all history).

### 9.5 Notification UX

**TUI (current):**
- Notifications shown in a separate menu, require manual navigation
- `mention` WebSocket messages increment a counter in the header

**Frontend recommendations:**
- Show a badge/counter on a bell icon using the `mention` WebSocket message (already sent in real-time)
- On click: `GET /api/dealership/notifications?unread_only=true`
- Each notification links directly to the vehicle + section where the mention happened (all data is in `CommentResponse`)
- Call `PATCH /notifications/read-all` when the notification panel is opened
- Consider a toast/snackbar for real-time `mention` events

**The notification system requires no backend changes for this UX.**

### 9.6 Section Navigation

**TUI (current):**
- Linear navigation — select vehicle → select section → enter chat

**Frontend recommendations:**
- Sidebar or tab strip showing all sections grouped by category
- Indicate unread activity per section (requires a new backend endpoint — see below)
- General Comments section pinned at top, differentiated visually

**Suggested backend addition:** A per-section unread count endpoint:
```
GET /api/dealership/vehicles/{id}/activity
```
Returns the last comment timestamp and count per section, enabling the frontend to show activity indicators without loading all comments.

### 9.7 Vehicle Status Workflow

**TUI (current):**
- Status is shown but cannot be changed from the client

**Frontend recommendations:**
- Status badge with dropdown to advance status (Pending → Online Evaluation → Inspection → Completed/Rejected)
- Guard the transition logic: use `PATCH /api/dealership/vehicles/{id}` with `{ "status": "online_evaluation" }`
- Consider adding role-based permission checks server-side before allowing status changes (e.g., only managers can mark as Completed)

### 9.8 `@Mention` Autocomplete

**TUI (current):**
- No autocomplete; users type usernames manually

**Frontend recommendations:**
- On `@` keypress in the comment input, fetch user list and show a dropdown
- Requires a new endpoint:
  ```
  GET /api/dealership/users?q=<search_term>
  ```
  Returns users matching the query (for autocomplete). Limit to active users; limit response to 10 results.

### 9.9 Required Backend Additions Summary

These are the minimal backend changes needed for a complete frontend migration:

| Priority | Endpoint                                  | Purpose                                      |
|----------|-------------------------------------------|----------------------------------------------|
| High     | `GET /api/auth/me`                        | Restore session after page refresh           |
| High     | `GET /api/dealership/users?q=`            | @mention autocomplete                        |
| Medium   | `GET /api/dealership/vehicles/{id}/activity` | Per-section activity indicators           |
| Medium   | `GET /api/dealership/comments?since=`     | Efficient reconnection without full reload   |
| Low      | `POST /api/auth/logout`                   | Server-side token invalidation               |
| Low      | `DELETE /api/dealership/comments/{id}`    | Comment deletion (currently no delete)       |

### 9.10 CORS Configuration

Update `.env` to include your frontend origin:
```env
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

WebSocket connections are **not** subject to CORS in the browser, but the HTTP upgrade request is — ensure your frontend origin is in the list.

### 9.11 What Can Be Deleted When Migrating

Once a frontend exists, these files are no longer needed:

| File                   | Reason                                        |
|------------------------|-----------------------------------------------|
| `dealership_client.py` | Replaced by frontend application              |
| `seed_vehicles.py`     | Use an admin UI or direct API calls instead   |

The backend itself requires no structural changes — only the additions listed in §9.9.

---

## Appendix: Migrations

| Revision | Description                                    |
|----------|------------------------------------------------|
| `001`    | Initial schema (users table)                   |
| `002`    | Add vehicles, comments, notifications tables   |
| `003`    | Drop legacy messages table                     |
| `004`    | Add hybrid sections (enum values + metadata table, 16 sections seeded) |
| `005`    | Fix section order numbers (reserve 0 for navigation) |

To apply all migrations:
```bash
alembic upgrade head
```
