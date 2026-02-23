"""AES encryption/decryption utility for superap_accounts passwords.

Uses Fernet symmetric encryption (AES-128-CBC under the hood) from the
cryptography library. The encryption key is derived from AES_ENCRYPTION_KEY
(preferred) or falls back to SECRET_KEY if not set.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet() -> Fernet:
    """Get a Fernet instance derived from AES_ENCRYPTION_KEY or SECRET_KEY.

    Fernet requires a 32-byte URL-safe base64-encoded key.
    We derive it via SHA-256 and base64 encoding.
    Uses AES_ENCRYPTION_KEY if set, otherwise falls back to SECRET_KEY.
    """
    source_key = settings.AES_ENCRYPTION_KEY or settings.SECRET_KEY
    key_bytes = hashlib.sha256(source_key.encode()).digest()
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
