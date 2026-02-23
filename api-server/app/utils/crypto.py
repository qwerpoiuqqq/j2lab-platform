"""AES encryption/decryption utility for superap_accounts passwords.

Uses Fernet symmetric encryption (AES-128-CBC under the hood) from the
cryptography library. The encryption key is derived from the app SECRET_KEY.

For production, a dedicated AES_KEY environment variable should be used.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet() -> Fernet:
    """Get a Fernet instance derived from SECRET_KEY.

    Fernet requires a 32-byte URL-safe base64-encoded key.
    We derive it from SECRET_KEY via SHA-256 and base64 encoding.
    """
    key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_password(plain_password: str) -> str:
    """Encrypt a plain-text password and return the encrypted string."""
    f = _get_fernet()
    encrypted = f.encrypt(plain_password.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt an encrypted password and return the plain text."""
    f = _get_fernet()
    decrypted = f.decrypt(encrypted_password.encode("utf-8"))
    return decrypted.decode("utf-8")
