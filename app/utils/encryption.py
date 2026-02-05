from cryptography.fernet import Fernet
from app.config import get_settings
import base64
import hashlib

settings = get_settings()


def get_cipher():
    """Get Fernet cipher from encryption key."""
    # Convert the encryption key to a valid Fernet key
    key = settings.encryption_key.encode()
    # Hash to get 32 bytes, then base64 encode for Fernet
    hashed_key = hashlib.sha256(key).digest()
    fernet_key = base64.urlsafe_b64encode(hashed_key)
    return Fernet(fernet_key)


def encrypt_message(message: str) -> str:
    """Encrypt a message."""
    cipher = get_cipher()
    encrypted = cipher.encrypt(message.encode())
    return encrypted.decode()


def decrypt_message(encrypted_message: str) -> str:
    """Decrypt a message."""
    cipher = get_cipher()
    decrypted = cipher.decrypt(encrypted_message.encode())
    return decrypted.decode()
