from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import Comment, User, Vehicle, Notification, SectionType
from app.utils.encryption import encrypt_message, decrypt_message
from app.utils.auth import decode_token
import json
import re


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

    async def broadcast_to_room(self, room_id: str, message: str, exclude_user: str = None):
        """Broadcast a message to all users in a specific room."""
        if room_id in self.rooms:
            for username, connection in list(self.rooms[room_id].items()):
                if username != exclude_user:
                    try:
                        await connection.send_text(message)
                    except Exception:
                        pass


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, token: str, vehicle_id: Optional[int] = None, section: Optional[str] = None):
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

        user = db.query(User).filter(User.username == token_data.username).first()
        if user is None:
            await websocket.close(code=1008, reason="User not found")
            return

        # Validate vehicle_id and section if provided
        if vehicle_id is not None:
            vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
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
                    db.commit()
                    db.refresh(new_comment)

                    # Parse @mentions and create notifications
                    mentioned_users = extract_mentions(content)
                    for mentioned_username in mentioned_users:
                        mentioned_user = db.query(User).filter(User.username == mentioned_username).first()
                        if mentioned_user and mentioned_user.id != user.id:
                            notification = Notification(
                                recipient_id=mentioned_user.id,
                                comment_id=new_comment.id,
                                is_read=False
                            )
                            db.add(notification)

                            # Send real-time notification if user is connected
                            await manager.send_personal_message(json.dumps({
                                "type": "mention",
                                "message": f"You were mentioned by {username} in {vehicle.make} {vehicle.model} - {section}",
                                "comment_id": new_comment.id,
                                "vehicle_id": vehicle_id,
                                "section": section
                            }), mentioned_username)

                    if mentioned_users:
                        db.commit()

                    # Broadcast comment to all users in the room
                    broadcast_data = json.dumps({
                        "type": "comment",
                        "comment_id": new_comment.id,
                        "username": username,
                        "content": content,
                        "vehicle_id": vehicle_id,
                        "section": section,
                        "timestamp": new_comment.created_at.isoformat(),
                        "mentions": mentioned_users
                    })
                    await manager.broadcast_to_room(room_id, broadcast_data)

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


def extract_mentions(content: str) -> List[str]:
    """Extract @username mentions from content."""
    pattern = r'@([a-zA-Z0-9_-]+)'
    mentions = re.findall(pattern, content)
    return list(set(mentions))  # Remove duplicates
