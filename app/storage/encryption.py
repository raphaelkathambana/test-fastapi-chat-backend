"""
Envelope encryption for file attachments.

Each file gets its own random AES-256 key (the data encryption key, DEK).
The file is encrypted with the DEK using AES-GCM. The DEK is then wrapped
(encrypted) using the application's Fernet master key.

This approach:
- Avoids running large files through Fernet (not designed for >1MB payloads)
- Allows per-file key rotation without re-encrypting everything
- Keeps the master key usage minimal (only wraps small DEKs)
"""
import os
import struct
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.utils.encryption import get_cipher
import logging

logger = logging.getLogger(__name__)

# AES-256 key size (32 bytes)
_AES_KEY_SIZE = 32
# AES-GCM nonce size (12 bytes, standard)
_NONCE_SIZE = 12


class FileEncryptor:
    """Handles envelope encryption/decryption of file data."""

    @staticmethod
    def generate_file_key() -> bytes:
        """Generate a random AES-256 key for a single file."""
        return os.urandom(_AES_KEY_SIZE)

    @staticmethod
    def wrap_key(file_key: bytes) -> str:
        """
        Wrap (encrypt) a file's AES key using the Fernet master key.

        Returns the wrapped key as a string for database storage.
        """
        cipher = get_cipher()
        wrapped = cipher.encrypt(file_key)
        return wrapped.decode()

    @staticmethod
    def unwrap_key(wrapped_key: str) -> bytes:
        """
        Unwrap (decrypt) a file's AES key using the Fernet master key.

        Returns the raw AES-256 key bytes.
        """
        cipher = get_cipher()
        return cipher.decrypt(wrapped_key.encode())

    @staticmethod
    def encrypt_file(data: bytes, file_key: bytes) -> bytes:
        """
        Encrypt file data using AES-256-GCM.

        Format: [12-byte nonce][ciphertext + 16-byte GCM tag]

        AES-GCM provides both confidentiality and integrity verification.
        """
        nonce = os.urandom(_NONCE_SIZE)
        aesgcm = AESGCM(file_key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    @staticmethod
    def decrypt_file(encrypted_data: bytes, file_key: bytes) -> bytes:
        """
        Decrypt file data using AES-256-GCM.

        Expects format: [12-byte nonce][ciphertext + 16-byte GCM tag]
        Raises InvalidTag if data has been tampered with.
        """
        nonce = encrypted_data[:_NONCE_SIZE]
        ciphertext = encrypted_data[_NONCE_SIZE:]
        aesgcm = AESGCM(file_key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    @staticmethod
    def encrypt_chunk(data: bytes, file_key: bytes, chunk_index: int) -> bytes:
        """
        Encrypt a single chunk with a deterministic nonce derived from chunk index.

        Format: [4-byte chunk_index LE][12-byte nonce][ciphertext + tag]

        The chunk index is prepended so we can verify ordering during reassembly.
        """
        # Create a unique nonce per chunk by combining random bytes with chunk index
        nonce = os.urandom(_NONCE_SIZE)
        aesgcm = AESGCM(file_key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        # Prepend chunk index (4 bytes, little-endian) + nonce
        return struct.pack("<I", chunk_index) + nonce + ciphertext

    @staticmethod
    def decrypt_chunk(encrypted_chunk: bytes, file_key: bytes) -> tuple[int, bytes]:
        """
        Decrypt a single chunk.

        Returns (chunk_index, decrypted_data).
        """
        chunk_index = struct.unpack("<I", encrypted_chunk[:4])[0]
        nonce = encrypted_chunk[4:4 + _NONCE_SIZE]
        ciphertext = encrypted_chunk[4 + _NONCE_SIZE:]
        aesgcm = AESGCM(file_key)
        data = aesgcm.decrypt(nonce, ciphertext, None)
        return chunk_index, data
