from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, Message
from app.models.schemas import MessageResponse
from app.utils.encryption import decrypt_message
from app.utils.auth import decode_token

router = APIRouter()


def get_current_user(token: str, db: Session) -> User:
    """Get current user from token."""
    token_data = decode_token(token)
    if token_data is None or token_data.username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user


@router.get("/messages", response_model=List[MessageResponse])
def get_messages(
    token: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get recent messages."""
    # Verify user authentication
    get_current_user(token, db)
    
    # Get messages with user information
    messages = db.query(Message).order_by(Message.created_at.desc()).limit(limit).all()
    
    # Decrypt and format messages
    result = []
    for msg in messages:
        try:
            decrypted_content = decrypt_message(msg.content)
            result.append(MessageResponse(
                id=msg.id,
                user_id=msg.user_id,
                username=msg.user.username,
                content=decrypted_content,
                created_at=msg.created_at
            ))
        except Exception:
            # Skip messages that can't be decrypted
            continue
    
    return list(reversed(result))
