from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.models import User, Message
from app.models.schemas import MessageResponse
from app.utils.encryption import decrypt_message
from app.utils.auth import decode_token

router = APIRouter()


def get_current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    """
    Get current user from Authorization header.

    Expected format: "Bearer <token>"
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Parse Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
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
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent messages. Requires Authorization header with Bearer token."""
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
