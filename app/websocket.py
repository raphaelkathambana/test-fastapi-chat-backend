from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import Comment, User, Vehicle, SectionType, Attachment, AttachmentStatus
from app.utils.encryption import encrypt_message, decrypt_message
from app.utils.auth import decode_token
from app.events import event_bus
import json


class ConnectionManager:
    def __init__(self):
        # Store connections by room: {room_id: {username: websocket}}
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}
        # Store user's current room: {username: room_id}
        self.user_rooms: Dict[str, str] = {}

    def get_room_id(self, vehicle_id: int, section: str) -> str:
        """Generate room ID for vehicle+section combination."""
        return f"vehicle_{vehicle_id}_section_{section}"

    async def connect(self, username: str, room_id: str, websocket: WebSocket):
        """Connect a user to a specific room."""
        await websocket.accept()

        # Create room if it doesn't exist
        if room_id not in self.rooms:
            self.rooms[room_id] = {}

        # Add user to room
        self.rooms[room_id][username] = websocket
        self.user_rooms[username] = room_id

    def disconnect(self, username: str):
        """Disconnect a user from their current room."""
        if username in self.user_rooms:
            room_id = self.user_rooms[username]
            if room_id in self.rooms and username in self.rooms[room_id]:
                del self.rooms[room_id][username]

                # Clean up empty rooms
                if not self.rooms[room_id]:
                    del self.rooms[room_id]

            del self.user_rooms[username]

    async def send_personal_message(self, message: str, username: str):
        """Send a message to a specific user."""
        if username in self.user_rooms:
            room_id = self.user_rooms[username]
            if room_id in self.rooms and username in self.rooms[room_id]:
                try:
                    await self.rooms[room_id][username].send_text(message)
                except Exception:
                    pass

    async def broadcast_to_room(self, room_id: str, message: str, exclude_user: str | None = None):
        """Broadcast a message to all users in a specific room."""
        if room_id in self.rooms:
            for username, connection in list(self.rooms[room_id].items()):
                if username != exclude_user:
                    try:
                        await connection.send_text(message)
                    except Exception:
                        pass


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, token: str, vehicle_id: int | None = None, section: str | None = None):
    """Handle WebSocket connection for vehicle evaluation comments."""
    db = SessionLocal()
    username = None
    room_id = None

    try:
        # Authenticate user
        token_data = decode_token(token)
        if token_data is None or token_data.username is None:
            await websocket.close(code=1008, reason="Invalid token")
            return

        user = db.query(User).filter(
            User.username == token_data.username).first()
        if user is None:
            await websocket.close(code=1008, reason="User not found")
            return

        # Validate vehicle_id and section if provided
        if vehicle_id is not None:
            vehicle = db.query(Vehicle).filter(
                Vehicle.id == vehicle_id).first()
            if not vehicle:
                await websocket.close(code=1008, reason="Vehicle not found")
                return

            # Validate section
            if section:
                try:
                    section_enum = SectionType(section)
                except ValueError:
                    await websocket.close(code=1008, reason="Invalid section")
                    return

                room_id = manager.get_room_id(vehicle_id, section)
            else:
                await websocket.close(code=1008, reason="Section required")
                return
        else:
            await websocket.close(code=1008, reason="Vehicle ID and section required")
            return

        username = user.username
        await manager.connect(username, room_id, websocket)

        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "system",
            "message": f"Connected to {vehicle.make} {vehicle.model} - {section_enum.value} section"
        }))

        # Broadcast user joined to room
        await manager.broadcast_to_room(room_id, json.dumps({
            "type": "system",
            "message": f"{username} joined"
        }), exclude_user=username)

        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "comment":
                content = message_data.get("content", "")
                attachment_ids = message_data.get("attachment_ids", [])

                if content.strip():
                    # Encrypt and save comment to database
                    encrypted_content = encrypt_message(content)
                    new_comment = Comment(
                        vehicle_id=vehicle_id,
                        section=section_enum,
                        user_id=user.id,
                        content=encrypted_content
                    )
                    db.add(new_comment)
                    db.flush()

                    # Link attachments if provided
                    linked_attachments = []
                    for aid in attachment_ids:
                        attachment = db.query(Attachment).filter(
                            Attachment.id == aid,
                            Attachment.uploader_id == user.id,
                            Attachment.status == AttachmentStatus.READY,
                            Attachment.comment_id.is_(None),
                        ).first()
                        if attachment:
                            attachment.comment_id = new_comment.id
                            linked_attachments.append({
                                'id': attachment.id,
                                'filename': attachment.filename,
                                'content_type': attachment.content_type,
                                'file_size': attachment.file_size,
                            })

                    db.commit()
                    db.refresh(new_comment)

                    # Emit event - let handlers process it
                    # This decouples WebSocket logic from notifications and broadcasts
                    await event_bus.emit('comment.created', {
                        'comment_id': new_comment.id,
                        'author_id': user.id,
                        'username': username,
                        'content': content,  # Pass decrypted content for mention extraction
                        'vehicle_id': vehicle_id,
                        'vehicle_make': vehicle.make,
                        'vehicle_model': vehicle.model,
                        'section': section,
                        'timestamp': new_comment.created_at.isoformat(),
                        'attachments': linked_attachments,
                    })

    except WebSocketDisconnect:
        if username:
            manager.disconnect(username)
            if room_id:
                await manager.broadcast_to_room(room_id, json.dumps({
                    "type": "system",
                    "message": f"{username} left"
                }))
    except Exception as e:
        if username:
            manager.disconnect(username)
    finally:
        db.close()
