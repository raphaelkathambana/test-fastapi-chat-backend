from app.models.schemas import TokenData
from app.config import get_settings
from jose import JWTError, jwt
import sys
import io
from typing import Optional
from datetime import datetime, timedelta, timezone

# Suppress bcrypt version warning during passlib import
# This is a known compatibility issue between passlib 1.7.4 and bcrypt 4.x
_stderr = sys.stderr
try:
    sys.stderr = io.StringIO()
    from passlib.context import CryptContext
finally:
    sys.stderr = _stderr


settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, settings.secret_key,
                             algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            return None
        return TokenData(username=username)
    except JWTError:
        return None
