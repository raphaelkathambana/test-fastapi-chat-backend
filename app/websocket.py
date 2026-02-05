from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import Message, User
from app.utils.encryption import encrypt_message, decrypt_message
from app.utils.auth import decode_token
import json


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, username: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[username] = websocket
    
    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]
    
    async def send_personal_message(self, message: str, username: str):
        if username in self.active_connections:
            await self.active_connections[username].send_text(message)
    
    async def broadcast(self, message: str, exclude_user: str = None):
        for username, connection in self.active_connections.items():
            if username != exclude_user:
                try:
                    await connection.send_text(message)
                except Exception:
                    pass


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket, token: str):
    db = SessionLocal()
    username = None
    
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
        
        username = user.username
        await manager.connect(username, websocket)
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "system",
            "message": f"Connected as {username}"
        }))
        
        # Broadcast user joined
        await manager.broadcast(json.dumps({
            "type": "system",
            "message": f"{username} joined the chat"
        }), exclude_user=username)
        
        while True:
            # Receive message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                content = message_data.get("content", "")
                
                if content.strip():
                    # Encrypt and save to database
                    encrypted_content = encrypt_message(content)
                    new_message = Message(
                        user_id=user.id,
                        content=encrypted_content
                    )
                    db.add(new_message)
                    db.commit()
                    db.refresh(new_message)
                    
                    # Broadcast to all connected clients
                    broadcast_data = json.dumps({
                        "type": "message",
                        "username": username,
                        "content": content,
                        "timestamp": new_message.created_at.isoformat()
                    })
                    await manager.broadcast(broadcast_data)
    
    except WebSocketDisconnect:
        if username:
            manager.disconnect(username)
            await manager.broadcast(json.dumps({
                "type": "system",
                "message": f"{username} left the chat"
            }))
    except Exception as e:
        if username:
            manager.disconnect(username)
    finally:
        db.close()
